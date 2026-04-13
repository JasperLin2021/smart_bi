"""
APScheduler-based scheduler for:
  - Alert evaluation jobs (interval-based)
  - Scheduled report jobs (cron-based)

All scheduler interactions must go through this module so that job IDs
stay in sync with the database.
"""
import asyncio
import json
import logging
from datetime import datetime
from typing import Optional

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

logger = logging.getLogger(__name__)

_scheduler: Optional[BackgroundScheduler] = None

# ─────────────────────────── lifecycle ───────────────────────────


def get_scheduler() -> BackgroundScheduler:
    global _scheduler
    if _scheduler is None:
        _scheduler = BackgroundScheduler(timezone="Asia/Shanghai")
    return _scheduler


def start_scheduler() -> None:
    scheduler = get_scheduler()
    if not scheduler.running:
        scheduler.start()
        logger.info("APScheduler started")
    _load_all_jobs()


def stop_scheduler() -> None:
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("APScheduler stopped")


# ─────────────────────── initial job load ────────────────────────


def _load_all_jobs() -> None:
    """Load all active alerts and scheduled reports from DB into the scheduler."""
    from app.db.session import SessionLocal
    from app.models.alert import Alert
    from app.models.scheduled_report import ScheduledReport

    db = SessionLocal()
    try:
        alerts = db.query(Alert).filter(Alert.is_active == True).all()  # noqa: E712
        for alert in alerts:
            _schedule_alert(alert)

        reports = db.query(ScheduledReport).filter(ScheduledReport.is_active == True).all()  # noqa: E712
        for report in reports:
            _schedule_report(report)
    finally:
        db.close()


# ─────────────────────── alert jobs ──────────────────────────────

_PERIOD_SECONDS = {"minute": 60, "hour": 3600, "day": 86400}


def _alert_job_id(alert_id: int) -> str:
    return f"alert_{alert_id}"


def _schedule_alert(alert) -> None:
    scheduler = get_scheduler()
    job_id = _alert_job_id(alert.id)
    seconds = (alert.check_period or 1) * _PERIOD_SECONDS.get(
        alert.check_period_unit or "hour", 3600
    )
    trigger = IntervalTrigger(seconds=max(seconds, 60))
    from app.core.alert_evaluator import evaluate_alert

    if scheduler.get_job(job_id):
        scheduler.reschedule_job(job_id, trigger=trigger)
    else:
        scheduler.add_job(
            evaluate_alert,
            trigger=trigger,
            args=[alert.id],
            id=job_id,
            replace_existing=True,
            misfire_grace_time=300,
        )
    logger.info("Scheduled alert job %s every %ds", job_id, seconds)


def upsert_alert_job(alert_id: int) -> None:
    """Call after creating or updating an alert."""
    from app.db.session import SessionLocal
    from app.models.alert import Alert

    db = SessionLocal()
    try:
        alert = db.query(Alert).filter(Alert.id == alert_id).first()
        if not alert or not alert.is_active:
            remove_alert_job(alert_id)
            return
        _schedule_alert(alert)
    finally:
        db.close()


def remove_alert_job(alert_id: int) -> None:
    """Call after deleting or deactivating an alert."""
    scheduler = get_scheduler()
    job_id = _alert_job_id(alert_id)
    if scheduler.get_job(job_id):
        scheduler.remove_job(job_id)
        logger.info("Removed alert job %s", job_id)


# ─────────────────────── report jobs ─────────────────────────────


def _report_job_id(report_id: int) -> str:
    return f"report_{report_id}"


def _schedule_report(report) -> None:
    scheduler = get_scheduler()
    job_id = _report_job_id(report.id)
    try:
        parts = (report.cron_expression or "0 9 * * 1-5").split()
        if len(parts) != 5:
            raise ValueError("cron must have 5 fields")
        trigger = CronTrigger(
            minute=parts[0],
            hour=parts[1],
            day=parts[2],
            month=parts[3],
            day_of_week=parts[4],
            timezone="Asia/Shanghai",
        )
    except Exception as exc:
        logger.error("Report %d invalid cron '%s': %s", report.id, report.cron_expression, exc)
        return

    if scheduler.get_job(job_id):
        scheduler.reschedule_job(job_id, trigger=trigger)
    else:
        scheduler.add_job(
            run_scheduled_report,
            trigger=trigger,
            args=[report.id],
            id=job_id,
            replace_existing=True,
            misfire_grace_time=600,
        )
    logger.info("Scheduled report job %s cron='%s'", job_id, report.cron_expression)


def upsert_report_job(report_id: int) -> None:
    """Call after creating or updating a scheduled report."""
    from app.db.session import SessionLocal
    from app.models.scheduled_report import ScheduledReport

    db = SessionLocal()
    try:
        report = db.query(ScheduledReport).filter(ScheduledReport.id == report_id).first()
        if not report or not report.is_active:
            remove_report_job(report_id)
            return
        _schedule_report(report)
    finally:
        db.close()


def remove_report_job(report_id: int) -> None:
    """Call after deleting or deactivating a scheduled report."""
    scheduler = get_scheduler()
    job_id = _report_job_id(report_id)
    if scheduler.get_job(job_id):
        scheduler.remove_job(job_id)
        logger.info("Removed report job %s", job_id)


# ─────────────────────── report runner ───────────────────────────


def run_scheduled_report(report_id: int) -> None:
    """
    Execute an NL question against the datasource and send results
    via configured notification channels. Called from a scheduler thread.
    """
    from app.db.session import SessionLocal, get_datasource_engine
    from app.models.datasource import DataSource
    from app.models.notification_setting import NotificationSetting
    from app.models.scheduled_report import ScheduledReport
    from app.core.alert_notifier import (
        send_dingtalk_sync,
        send_email_sync,
        send_wechat_sync,
    )

    db = SessionLocal()
    try:
        report = (
            db.query(ScheduledReport)
            .filter(ScheduledReport.id == report_id, ScheduledReport.is_active == True)  # noqa: E712
            .first()
        )
        if not report:
            return

        ds = db.query(DataSource).filter(DataSource.id == report.datasource_id).first()
        if not ds:
            logger.error("Report %d: datasource %d not found", report_id, report.datasource_id)
            return

        # Run the NL→SQL pipeline in a fresh event loop (scheduler thread has none)
        sql, rows, columns = _run_nl_query(report.question, ds)

        # Format result
        time_str = datetime.now().strftime("%Y-%m-%d %H:%M")
        markdown_body = _format_report_markdown(report.name, report.question, sql, rows, columns, time_str)
        html_body = _format_report_html(report.name, report.question, sql, rows, columns, time_str)
        subject = f"[Smart BI 定时报告] {report.name} - {time_str}"

        ns = db.query(NotificationSetting).first()
        notify_result: dict = {}

        if report.notify_wechat and ns and ns.wechat_enabled and ns.wechat_webhook_url:
            try:
                send_wechat_sync(ns.wechat_webhook_url, markdown_body)
                notify_result["wechat"] = "success"
            except Exception as exc:
                notify_result["wechat"] = f"error: {exc}"
                logger.error("Report %d wechat error: %s", report_id, exc)

        if report.notify_dingtalk and ns and ns.dingtalk_enabled and ns.dingtalk_webhook_url:
            try:
                send_dingtalk_sync(ns.dingtalk_webhook_url, ns.dingtalk_secret, markdown_body)
                notify_result["dingtalk"] = "success"
            except Exception as exc:
                notify_result["dingtalk"] = f"error: {exc}"
                logger.error("Report %d dingtalk error: %s", report_id, exc)

        if report.notify_email and ns and ns.email_enabled and ns.smtp_host:
            raw = (report.email_recipients or "").strip()
            recipients = [e.strip() for e in raw.split(",") if e.strip()]
            if recipients:
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
                    notify_result["email"] = "success"
                except Exception as exc:
                    notify_result["email"] = f"error: {exc}"
                    logger.error("Report %d email error: %s", report_id, exc)

        # Update last_run_at
        report.last_run_at = datetime.now()
        db.commit()
        logger.info("Report %d executed: notify=%s", report_id, notify_result)

    except Exception as exc:
        logger.exception("Report %d failed: %s", report_id, exc)
    finally:
        db.close()


def _run_nl_query(question: str, datasource) -> tuple[str, list, list]:
    """Run NL→SQL→execute in a new asyncio event loop (called from a thread)."""
    return asyncio.run(_async_run_nl_query(question, datasource))


async def _async_run_nl_query(question: str, datasource) -> tuple[str, list, list]:
    from sqlalchemy import text as sa_text
    from app.core.llm import generate_sql_query
    from app.db.session import get_datasource_engine
    from app.core.excel_executor import execute_excel_query

    result = await generate_sql_query(question, datasource=datasource)
    sql = result.get("sql", "").strip()
    if not sql:
        return "", [], []

    try:
        source_type = getattr(datasource, "source_type", "database")
        if source_type == "excel":
            exec_result = execute_excel_query(datasource, sql)
            rows = exec_result.get("rows", [])
            columns = exec_result.get("columns", [])
        else:
            engine = get_datasource_engine(datasource.database_url)
            with engine.connect() as conn:
                res = conn.execute(sa_text(sql))
                columns = list(res.keys())
                rows = [list(row) for row in res.fetchmany(50)]  # cap at 50 rows
    except Exception as exc:
        logger.error("Report SQL execution error: %s | sql=%s", exc, sql)
        return sql, [], []

    return sql, rows, columns


def _format_report_markdown(
    name: str, question: str, sql: str, rows: list, columns: list, time_str: str
) -> str:
    lines = [
        f"## Smart BI 定时报告: {name}",
        f"> **问题**: {question}",
        f"> **生成时间**: {time_str}",
        "",
    ]
    if not rows:
        lines.append("本次查询无数据返回。")
        return "\n".join(lines)

    # Table header
    lines.append("| " + " | ".join(str(c) for c in columns) + " |")
    lines.append("| " + " | ".join(["---"] * len(columns)) + " |")
    for row in rows[:20]:
        lines.append("| " + " | ".join(str(v) if v is not None else "-" for v in row) + " |")
    if len(rows) > 20:
        lines.append(f"\n*（仅显示前 20 条，共 {len(rows)} 条）*")
    return "\n".join(lines)


def _format_report_html(
    name: str, question: str, sql: str, rows: list, columns: list, time_str: str
) -> str:
    header = (
        f"<h2>Smart BI 定时报告: {name}</h2>"
        f"<p><b>问题</b>: {question}</p>"
        f"<p><b>生成时间</b>: {time_str}</p>"
    )
    if not rows:
        return header + "<p>本次查询无数据返回。</p>"

    th = "".join(f"<th>{c}</th>" for c in columns)
    trs = ""
    for row in rows[:50]:
        td = "".join(f"<td>{v if v is not None else '-'}</td>" for v in row)
        trs += f"<tr>{td}</tr>"
    table = (
        f"<table border='1' cellpadding='4' cellspacing='0' style='border-collapse:collapse'>"
        f"<thead><tr>{th}</tr></thead><tbody>{trs}</tbody></table>"
    )
    if len(rows) > 50:
        table += f"<p><i>仅显示前 50 条，共 {len(rows)} 条</i></p>"
    return header + table
