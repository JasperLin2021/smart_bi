"""
Alert evaluation engine.
Runs as a background job (APScheduler thread). Evaluates metric conditions
against the target datasource, then fires notification channels on trigger.
"""
import json
import logging
from datetime import datetime
from typing import Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.alert_notifier import (
    send_dingtalk_sync,
    send_email_sync,
    send_wechat_sync,
)
from app.db.session import SessionLocal, get_datasource_engine
from app.models.alert import Alert
from app.models.alert_history import AlertHistory
from app.models.metric import Metric
from app.models.notification_setting import NotificationSetting

logger = logging.getLogger(__name__)


def _check_condition(val: float, operator: str, threshold: float) -> bool:
    return {
        "gt": val > threshold,
        "gte": val >= threshold,
        "lt": val < threshold,
        "lte": val <= threshold,
        "eq": val == threshold,
    }.get(operator, False)


def _build_where_clause(dim_conditions: list) -> str:
    parts = []
    for cond in dim_conditions:
        field = (cond.get("field") or "").strip()
        op = cond.get("operator", "eq")
        val = cond.get("value", "")
        if not field:
            continue
        safe_val = str(val).replace("'", "''")
        if op == "eq":
            parts.append(f"{field} = '{safe_val}'")
        elif op == "neq":
            parts.append(f"{field} != '{safe_val}'")
        elif op == "contains":
            parts.append(f"{field} LIKE '%{safe_val}%'")
        elif op == "in":
            vals = [v.strip().replace("'", "''") for v in str(val).split(",")]
            val_list = ", ".join(f"'{v}'" for v in vals)
            parts.append(f"{field} IN ({val_list})")
    return " AND ".join(parts)


def _op_label(op: str) -> str:
    return {"gt": ">", "gte": ">=", "lt": "<", "lte": "<=", "eq": "="}.get(op, op)


def _render(template: str, ctx: dict) -> str:
    for k, v in ctx.items():
        template = template.replace(f"{{{{{k}}}}}", str(v))
    return template


def _get_metric_value(
    alert: Alert, metric: Metric, db: Session
) -> Optional[float]:
    """Execute the metric formula against the alert's datasource and return the scalar value."""
    from app.models.datasource import DataSource

    ds = db.query(DataSource).filter(DataSource.id == alert.datasource_id).first()
    if not ds:
        logger.warning("Alert %d: datasource %d not found", alert.id, alert.datasource_id)
        return None

    formula = (metric.formula or "").strip()
    table = (metric.table_name or "").strip()
    if not formula or not table:
        logger.warning("Alert %d: metric %d has no formula/table", alert.id, metric.id)
        return None

    dim_conditions = json.loads(alert.dimension_conditions or "[]")
    where = _build_where_clause(dim_conditions)
    sql = f"SELECT {formula} AS _val FROM {table}"
    if where:
        sql += f" WHERE {where}"

    try:
        engine = get_datasource_engine(ds.database_url)
        with engine.connect() as conn:
            row = conn.execute(text(sql)).fetchone()
        if row is None or row[0] is None:
            return None
        return float(row[0])
    except Exception as exc:
        logger.error("Alert %d SQL error: %s | sql=%s", alert.id, exc, sql)
        return None


def _dispatch_notifications(
    alert: Alert,
    ns: Optional[NotificationSetting],
    markdown_body: str,
    html_body: str,
    subject: str,
) -> dict:
    result: dict = {}

    if alert.notify_wechat:
        if not (ns and ns.wechat_enabled and ns.wechat_webhook_url):
            result["wechat"] = "skipped: channel not configured"
        else:
            try:
                send_wechat_sync(ns.wechat_webhook_url, markdown_body)
                result["wechat"] = "success"
            except Exception as exc:
                result["wechat"] = f"error: {exc}"
                logger.error("Alert %d wechat error: %s", alert.id, exc)

    if alert.notify_dingtalk:
        if not (ns and ns.dingtalk_enabled and ns.dingtalk_webhook_url):
            result["dingtalk"] = "skipped: channel not configured"
        else:
            try:
                send_dingtalk_sync(
                    ns.dingtalk_webhook_url, ns.dingtalk_secret, markdown_body
                )
                result["dingtalk"] = "success"
            except Exception as exc:
                result["dingtalk"] = f"error: {exc}"
                logger.error("Alert %d dingtalk error: %s", alert.id, exc)

    if alert.notify_email:
        if not (ns and ns.email_enabled and ns.smtp_host):
            result["email"] = "skipped: channel not configured"
        else:
            # Collect recipients from alert.email_recipients field
            raw = (getattr(alert, "email_recipients", None) or "").strip()
            recipients = [e.strip() for e in raw.split(",") if e.strip()] if raw else []
            if not recipients:
                result["email"] = "skipped: no recipients"
            else:
                try:
                    send_email_sync(
                        smtp_host=ns.smtp_host,
                        smtp_port=ns.smtp_port or 465,
                        smtp_username=ns.smtp_username or "",
                        smtp_password=ns.smtp_password or "",
                        smtp_from=ns.smtp_from or ns.smtp_username or "",
                        use_ssl=ns.smtp_use_ssl if ns.smtp_use_ssl is not None else True,
                        recipients=recipients,
                        subject=subject,
                        html_content=html_body,
                    )
                    result["email"] = "success"
                except Exception as exc:
                    result["email"] = f"error: {exc}"
                    logger.error("Alert %d email error: %s", alert.id, exc)

    return result


def evaluate_alert(alert_id: int) -> None:
    """Entry point called by the scheduler for each active alert."""
    db: Session = SessionLocal()
    try:
        alert = (
            db.query(Alert)
            .filter(Alert.id == alert_id, Alert.is_active == True)  # noqa: E712
            .first()
        )
        if not alert:
            return

        if not alert.metric_id:
            logger.debug("Alert %d has no metric_id, skipping", alert_id)
            return

        metric = db.query(Metric).filter(Metric.id == alert.metric_id).first()
        if not metric:
            return

        val = _get_metric_value(alert, metric, db)
        if val is None:
            return

        # Evaluate conditions
        metric_conditions = json.loads(alert.metric_conditions or "[]")
        if not metric_conditions:
            return

        triggered_parts = []
        any_triggered = False
        for cond in metric_conditions:
            op = cond.get("operator", "gt")
            threshold = float(cond.get("value", 0))
            if _check_condition(val, op, threshold):
                any_triggered = True
                triggered_parts.append(
                    f"{metric.name} {_op_label(op)} {threshold}（实际: {val:.4g}）"
                )

        if not any_triggered:
            return

        # Build notification content
        time_str = datetime.now().strftime("%Y-%m-%d %H:%M")
        condition_str = "；".join(triggered_parts)
        ctx = {
            "alert_name": alert.name,
            "metric": metric.name,
            "value": f"{val:.4g}",
            "condition": condition_str,
            "time": time_str,
        }
        default_template = (
            "预警「{{alert_name}}」已触发\n"
            "触发条件：{{condition}}\n"
            "触发时间：{{time}}"
        )
        plain = _render(alert.content or default_template, ctx)

        markdown_body = (
            f"## Smart BI 预警通知\n\n"
            f"**预警名称**: {alert.name}\n\n"
            f"**触发条件**: {condition_str}\n\n"
            f"**触发时间**: {time_str}"
        )
        html_body = (
            f"<h2>Smart BI 预警通知</h2>"
            f"<p><b>预警名称</b>: {alert.name}</p>"
            f"<p><b>触发条件</b>: {condition_str}</p>"
            f"<p><b>触发时间</b>: {time_str}</p>"
        )
        subject = f"[Smart BI 预警] {alert.name}"

        ns = db.query(NotificationSetting).first()
        notify_result = _dispatch_notifications(
            alert, ns, markdown_body, html_body, subject
        )

        # Persist history
        history = AlertHistory(
            alert_id=alert.id,
            alert_name=alert.name,
            metric_value=f"{val:.4g}",
            condition_desc=condition_str,
            notify_result=json.dumps(notify_result, ensure_ascii=False),
            status="triggered",
        )
        db.add(history)
        db.commit()
        logger.info("Alert %d triggered: %s | notify=%s", alert_id, condition_str, notify_result)

    except Exception as exc:
        logger.exception("Alert %d evaluation failed: %s", alert_id, exc)
    finally:
        db.close()
