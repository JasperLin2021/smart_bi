"""create tables that previously only existed via Base.metadata.create_all

Revision ID: 20260731_0038
Revises: 20260729_0037
Create Date: 2026-07-31

These tables were historically created by the ``create_all`` fallback in
``app/main.py`` and never had an alembic migration, so a fresh database that
only runs ``alembic upgrade head`` ended up missing them. Column definitions
mirror the current models in ``app/models/`` (including the columns that
guarded add-column migrations 0033/0034/0037 would add on existing
databases).

The migration is idempotent: on databases where ``create_all`` already built
the tables it skips creation and only backfills columns that are safe to add
(nullable columns, or NOT NULL columns carrying a server default). NOT NULL
columns without a server default cannot be added to a populated table
portably, so they are created-only — every known deployment already has them
via ``create_all``.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20260731_0038"
down_revision: Union[str, None] = "20260729_0037"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_table(table_name: str) -> bool:
    return sa.inspect(op.get_bind()).has_table(table_name)


def _has_column(table_name: str, column_name: str) -> bool:
    if not _has_table(table_name):
        return False
    return any(column["name"] == column_name for column in sa.inspect(op.get_bind()).get_columns(table_name))


def _create_or_sync(table_name: str, columns: list[sa.Column], *constraints) -> None:
    if not _has_table(table_name):
        op.create_table(table_name, *columns, *constraints)
        return
    # Table already exists (created by create_all): backfill missing columns
    # where that can be done without rewriting existing rows.
    for column in columns:
        if column.name == "id":
            continue
        if _has_column(table_name, column.name):
            continue
        if column.nullable or column.server_default is not None:
            op.add_column(table_name, column)


def upgrade() -> None:
    # --- 数据集成 (app/models/data_link.py) ---
    _create_or_sync(
        "data_links",
        [
            sa.Column("id", sa.Integer(), primary_key=True, index=True),
            sa.Column("name", sa.String(128), nullable=False),
            sa.Column("connector_type", sa.String(32), nullable=False, index=True),
            sa.Column("config_json", sa.JSON(), nullable=True),
            sa.Column("status", sa.String(16), nullable=True),
            sa.Column("last_test_at", sa.DateTime(), nullable=True),
            sa.Column("last_test_message", sa.Text(), nullable=True),
            sa.Column("org_id", sa.Integer(), nullable=True, index=True),
            sa.Column("created_by", sa.Integer(), nullable=True),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
        ],
    )
    _create_or_sync(
        "data_link_tasks",
        [
            sa.Column("id", sa.Integer(), primary_key=True, index=True),
            sa.Column("link_id", sa.Integer(), nullable=False, index=True),
            sa.Column("name", sa.String(128), nullable=False),
            sa.Column("source_object", sa.String(64), nullable=False),
            sa.Column("target_datasource_id", sa.Integer(), nullable=True),
            sa.Column("target_table", sa.String(128), nullable=True),
            sa.Column("sync_mode", sa.String(16), nullable=True),
            sa.Column("incremental_field", sa.String(64), nullable=True),
            sa.Column("incremental_watermark", sa.String(64), nullable=True),
            sa.Column("field_mapping_json", sa.JSON(), nullable=True),
            sa.Column("filter_json", sa.JSON(), nullable=True),
            sa.Column("cron_expression", sa.String(64), nullable=True),
            sa.Column("is_active", sa.Boolean(), nullable=True),
            sa.Column("last_run_at", sa.DateTime(), nullable=True),
            sa.Column("last_run_status", sa.String(16), nullable=True),
            sa.Column("last_run_records", sa.Integer(), nullable=True),
            sa.Column("org_id", sa.Integer(), nullable=True, index=True),
            sa.Column("created_by", sa.Integer(), nullable=True),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
        ],
    )
    _create_or_sync(
        "data_link_logs",
        [
            sa.Column("id", sa.Integer(), primary_key=True, index=True),
            sa.Column("task_id", sa.Integer(), nullable=False, index=True),
            sa.Column("link_id", sa.Integer(), nullable=False, index=True),
            sa.Column("status", sa.String(16), nullable=False),
            sa.Column("records_read", sa.Integer(), nullable=True),
            sa.Column("records_written", sa.Integer(), nullable=True),
            sa.Column("records_failed", sa.Integer(), nullable=True),
            sa.Column("error_message", sa.Text(), nullable=True),
            sa.Column("started_at", sa.DateTime(), server_default=sa.func.now()),
            sa.Column("finished_at", sa.DateTime(), nullable=True),
            sa.Column("org_id", sa.Integer(), nullable=True, index=True),
        ],
    )

    # --- 嵌入 (app/models/embed_token.py) ---
    _create_or_sync(
        "embed_tokens",
        [
            sa.Column("id", sa.Integer(), primary_key=True, index=True),
            sa.Column("token", sa.String(64), nullable=False, unique=True, index=True),
            sa.Column("label", sa.String(128), nullable=True),
            sa.Column("resource_type", sa.String(32), nullable=False),
            sa.Column("resource_id", sa.Integer(), nullable=False),
            sa.Column("allowed_domains", sa.Text(), nullable=True),
            sa.Column("created_by", sa.Integer(), nullable=True),
            sa.Column("expires_at", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        ],
    )

    # --- 复杂报表 (app/models/report_template.py) ---
    _create_or_sync(
        "report_templates",
        [
            sa.Column("id", sa.Integer(), primary_key=True, index=True),
            sa.Column("name", sa.String(160), nullable=False, index=True),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("dataset_id", sa.Integer(), nullable=False, index=True),
            sa.Column("report_type", sa.String(32), nullable=False, server_default="paginated", index=True),
            sa.Column("layout_json", sa.JSON(), nullable=True),
            sa.Column("parameter_schema_json", sa.JSON(), nullable=True),
            sa.Column("binding_json", sa.JSON(), nullable=True),
            sa.Column("style_json", sa.JSON(), nullable=True),
            sa.Column("permission_json", sa.JSON(), nullable=True),
            sa.Column("fill_schema_json", sa.JSON(), nullable=True),
            sa.Column("distribution_json", sa.JSON(), nullable=True),
            sa.Column("status", sa.String(32), nullable=False, server_default="draft", index=True),
            sa.Column("visibility", sa.String(32), nullable=False, server_default="private", index=True),
            sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("org_id", sa.Integer(), nullable=True, index=True),
            sa.Column("owner_id", sa.Integer(), nullable=True, index=True),
            sa.Column("created_by", sa.Integer(), nullable=True, index=True),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
        ],
    )
    _create_or_sync(
        "report_template_versions",
        [
            sa.Column("id", sa.Integer(), primary_key=True, index=True),
            sa.Column("template_id", sa.Integer(), nullable=False, index=True),
            sa.Column("version", sa.Integer(), nullable=False, index=True),
            sa.Column("snapshot_json", sa.JSON(), nullable=False),
            sa.Column("changelog", sa.Text(), nullable=True),
            sa.Column("created_by", sa.Integer(), nullable=True, index=True),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        ],
    )
    _create_or_sync(
        "report_runs",
        [
            sa.Column("id", sa.Integer(), primary_key=True, index=True),
            sa.Column("template_id", sa.Integer(), nullable=False, index=True),
            sa.Column("version", sa.Integer(), nullable=True),
            sa.Column("run_type", sa.String(32), nullable=False, server_default="preview", index=True),
            sa.Column("export_type", sa.String(32), nullable=True, index=True),
            sa.Column("status", sa.String(32), nullable=False, server_default="queued", index=True),
            sa.Column("parameters_json", sa.JSON(), nullable=True),
            sa.Column("output_uri", sa.String(512), nullable=True),
            sa.Column("content_preview", sa.Text(), nullable=True),
            sa.Column("error_message", sa.Text(), nullable=True),
            sa.Column("org_id", sa.Integer(), nullable=True, index=True),
            sa.Column("created_by", sa.Integer(), nullable=True, index=True),
            sa.Column("started_at", sa.DateTime(), server_default=sa.func.now()),
            sa.Column("finished_at", sa.DateTime(), nullable=True),
        ],
    )
    _create_or_sync(
        "report_fill_records",
        [
            sa.Column("id", sa.Integer(), primary_key=True, index=True),
            sa.Column("template_id", sa.Integer(), nullable=False, index=True),
            sa.Column("payload_json", sa.JSON(), nullable=False),
            sa.Column("validation_status", sa.String(32), nullable=False, server_default="pending", index=True),
            sa.Column("validation_errors_json", sa.JSON(), nullable=True),
            sa.Column("writeback_status", sa.String(32), nullable=False, server_default="pending", index=True),
            # also added by guarded migration 20260729_0037 on existing databases
            sa.Column("writeback_error", sa.Text(), nullable=True),
            sa.Column("org_id", sa.Integer(), nullable=True, index=True),
            sa.Column("submitted_by", sa.Integer(), nullable=True, index=True),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        ],
    )

    # --- ETL (app/models/data_pipeline.py) ---
    # data_pipeline_versions is already created by 20260514_0034.
    _create_or_sync(
        "data_pipelines",
        [
            sa.Column("id", sa.Integer(), primary_key=True, index=True),
            sa.Column("name", sa.String(160), nullable=False, index=True),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("dataset_id", sa.Integer(), nullable=False, index=True),
            sa.Column("dag_json", sa.JSON(), nullable=False),
            sa.Column("schedule_cron", sa.String(64), nullable=True),
            sa.Column("run_mode", sa.String(32), nullable=False, server_default="manual", index=True),
            sa.Column("status", sa.String(32), nullable=False, server_default="draft", index=True),
            # columns below match guarded add-column migrations 20260511_0033 / 20260514_0034
            sa.Column("environment", sa.String(32), nullable=False, server_default="prod", index=True),
            sa.Column("priority", sa.String(16), nullable=False, server_default="medium", index=True),
            sa.Column("sla_minutes", sa.Integer(), nullable=False, server_default="120"),
            sa.Column("retry_count", sa.Integer(), nullable=False, server_default="2"),
            sa.Column("timeout_minutes", sa.Integer(), nullable=False, server_default="60"),
            sa.Column("alert_policy_json", sa.JSON(), nullable=True),
            sa.Column("state_json", sa.JSON(), nullable=True),
            sa.Column("current_version", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("published_version", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("last_run_status", sa.String(32), nullable=True, index=True),
            sa.Column("last_run_at", sa.DateTime(), nullable=True),
            sa.Column("org_id", sa.Integer(), nullable=True, index=True),
            sa.Column("owner_id", sa.Integer(), nullable=True, index=True),
            sa.Column("created_by", sa.Integer(), nullable=True, index=True),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
        ],
    )
    _create_or_sync(
        "data_pipeline_runs",
        [
            sa.Column("id", sa.Integer(), primary_key=True, index=True),
            sa.Column("pipeline_id", sa.Integer(), nullable=False, index=True),
            sa.Column("mode", sa.String(32), nullable=False, server_default="manual", index=True),
            sa.Column("status", sa.String(32), nullable=False, server_default="running", index=True),
            sa.Column("reason", sa.Text(), nullable=True),
            sa.Column("node_logs_json", sa.JSON(), nullable=True),
            sa.Column("records_read", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("records_written", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("records_failed", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("error_message", sa.Text(), nullable=True),
            # columns below match guarded add-column migration 20260514_0034
            sa.Column("notify_result_json", sa.JSON(), nullable=True),
            sa.Column("scheduled_job_id", sa.String(128), nullable=True, index=True),
            sa.Column("duration_ms", sa.Integer(), nullable=True),
            sa.Column("org_id", sa.Integer(), nullable=True, index=True),
            sa.Column("triggered_by_id", sa.Integer(), nullable=True, index=True),
            sa.Column("started_at", sa.DateTime(), server_default=sa.func.now()),
            sa.Column("finished_at", sa.DateTime(), nullable=True),
        ],
    )
    _create_or_sync(
        "data_quality_rules",
        [
            sa.Column("id", sa.Integer(), primary_key=True, index=True),
            sa.Column("pipeline_id", sa.Integer(), nullable=True, index=True),
            sa.Column("dataset_id", sa.Integer(), nullable=False, index=True),
            sa.Column("name", sa.String(160), nullable=False, index=True),
            sa.Column("rule_type", sa.String(32), nullable=False, index=True),
            sa.Column("field", sa.String(128), nullable=True),
            sa.Column("operator", sa.String(32), nullable=True),
            sa.Column("threshold", sa.String(128), nullable=True),
            sa.Column("severity", sa.String(16), nullable=False, server_default="warning", index=True),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("last_status", sa.String(32), nullable=True, index=True),
            sa.Column("last_checked_at", sa.DateTime(), nullable=True),
            sa.Column("org_id", sa.Integer(), nullable=True, index=True),
            sa.Column("created_by", sa.Integer(), nullable=True, index=True),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        ],
    )

    # --- 遗留老表 ---
    _create_or_sync(
        "alerts",
        [
            sa.Column("id", sa.Integer(), primary_key=True, index=True),
            sa.Column("name", sa.String(128), nullable=False),
            sa.Column("dataset_id", sa.Integer(), nullable=True, index=True),
            sa.Column("datasource_id", sa.Integer(), nullable=True, index=True),
            sa.Column("metric_id", sa.Integer(), nullable=True),
            sa.Column("metric_name", sa.String(128), nullable=True),
            sa.Column("time_range", sa.Integer(), nullable=True),
            sa.Column("time_range_unit", sa.String(16), nullable=True),
            sa.Column("dimension_conditions", sa.Text(), nullable=True),
            sa.Column("metric_conditions", sa.Text(), nullable=True),
            sa.Column("check_period", sa.Integer(), nullable=True),
            sa.Column("check_period_unit", sa.String(16), nullable=True),
            sa.Column("assignees", sa.Text(), nullable=True),
            sa.Column("cc_users", sa.Text(), nullable=True),
            sa.Column("notify_system", sa.Boolean(), nullable=True),
            sa.Column("notify_email", sa.Boolean(), nullable=True),
            sa.Column("notify_wechat", sa.Boolean(), nullable=True),
            sa.Column("notify_dingtalk", sa.Boolean(), nullable=True),
            sa.Column("email_recipients", sa.Text(), nullable=True),
            sa.Column("content", sa.Text(), nullable=True),
            sa.Column("auto_create_action_item", sa.Boolean(), nullable=True),
            sa.Column("action_item_assignee_id", sa.Integer(), nullable=True),
            sa.Column("is_active", sa.Boolean(), nullable=True),
            sa.Column("created_by", sa.Integer(), nullable=True),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
        ],
    )
    _create_or_sync(
        "alert_history",
        [
            sa.Column("id", sa.Integer(), primary_key=True, index=True),
            sa.Column("alert_id", sa.Integer(), nullable=False, index=True),
            sa.Column("alert_name", sa.String(128), nullable=True),
            sa.Column("triggered_at", sa.DateTime(), server_default=sa.func.now()),
            sa.Column("metric_value", sa.String(64), nullable=True),
            sa.Column("condition_desc", sa.String(512), nullable=True),
            sa.Column("notify_result", sa.Text(), nullable=True),
            sa.Column("status", sa.String(32), nullable=True),
        ],
    )
    _create_or_sync(
        "notification_settings",
        [
            sa.Column("id", sa.Integer(), primary_key=True, index=True),
            sa.Column("email_enabled", sa.Boolean(), nullable=True),
            sa.Column("smtp_host", sa.String(256), nullable=True),
            sa.Column("smtp_port", sa.Integer(), nullable=True),
            sa.Column("smtp_username", sa.String(256), nullable=True),
            sa.Column("smtp_password", sa.String(256), nullable=True),
            sa.Column("smtp_from", sa.String(256), nullable=True),
            sa.Column("smtp_use_ssl", sa.Boolean(), nullable=True),
            sa.Column("wechat_enabled", sa.Boolean(), nullable=True),
            sa.Column("wechat_webhook_url", sa.String(512), nullable=True),
            sa.Column("dingtalk_enabled", sa.Boolean(), nullable=True),
            sa.Column("dingtalk_webhook_url", sa.String(512), nullable=True),
            sa.Column("dingtalk_secret", sa.String(256), nullable=True),
        ],
    )
    _create_or_sync(
        "scheduled_reports",
        [
            sa.Column("id", sa.Integer(), primary_key=True, index=True),
            sa.Column("name", sa.String(128), nullable=False),
            sa.Column("dataset_id", sa.Integer(), nullable=True, index=True),
            sa.Column("datasource_id", sa.Integer(), nullable=True, index=True),
            sa.Column("question", sa.Text(), nullable=False),
            sa.Column("cron_expression", sa.String(64), nullable=True),
            sa.Column("notify_email", sa.Boolean(), nullable=True),
            sa.Column("notify_wechat", sa.Boolean(), nullable=True),
            sa.Column("notify_dingtalk", sa.Boolean(), nullable=True),
            sa.Column("email_recipients", sa.Text(), nullable=True),
            sa.Column("is_active", sa.Boolean(), nullable=True),
            sa.Column("created_by", sa.Integer(), nullable=True),
            sa.Column("last_run_at", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
        ],
    )
    _create_or_sync(
        "query_history",
        [
            sa.Column("id", sa.Integer(), primary_key=True, index=True),
            sa.Column("user_id", sa.Integer(), nullable=False, index=True),
            sa.Column("datasource_id", sa.Integer(), nullable=True, index=True),
            sa.Column("parent_history_id", sa.Integer(), nullable=True, index=True),
            sa.Column("question", sa.String(512), nullable=False),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
            sa.Column("favorite", sa.Boolean(), nullable=True),
            sa.Column("sql_query", sa.Text(), nullable=True),
            sa.Column("result_json", sa.Text(), nullable=True),
            sa.Column("summary", sa.Text(), nullable=True),
            sa.Column("mode", sa.String(32), nullable=True),
            sa.Column("drill_context", sa.Text(), nullable=True),
            sa.Column("llm_model", sa.String(128), nullable=True),
            sa.Column("is_insight", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("insight_title", sa.String(200), nullable=True),
            sa.Column("org_id", sa.Integer(), nullable=True, index=True),
        ],
    )
    _create_or_sync(
        "pinned_charts",
        [
            sa.Column("id", sa.Integer(), primary_key=True, index=True),
            sa.Column("user_id", sa.Integer(), nullable=False, index=True),
            sa.Column("datasource_id", sa.Integer(), nullable=True, index=True),
            sa.Column("title", sa.String(128), nullable=False),
            sa.Column("description", sa.String(256), nullable=True),
            sa.Column("sql_query", sa.Text(), nullable=False),
            sa.Column("chart_type", sa.String(32), nullable=True),
            sa.Column("sort_order", sa.String(16), nullable=True),
            sa.Column("display_order", sa.Integer(), nullable=True),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
        ],
    )
    _create_or_sync(
        "agent_runs",
        [
            sa.Column("id", sa.Integer(), primary_key=True, index=True),
            sa.Column("user_id", sa.Integer(), nullable=False, index=True),
            sa.Column("route", sa.String(128), nullable=False),
            sa.Column("prompt", sa.Text(), nullable=False),
            sa.Column("plan_json", sa.Text(), nullable=True),
            sa.Column("execution_json", sa.Text(), nullable=True),
            sa.Column("status", sa.String(32), nullable=False, server_default="planned"),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
        ],
    )
    _create_or_sync(
        "llm_settings",
        [
            sa.Column("id", sa.Integer(), primary_key=True, index=True),
            sa.Column("provider", sa.String(32), nullable=True),
            sa.Column("base_url", sa.String(256), nullable=False),
            sa.Column("api_key", sa.String(256), nullable=False),
            sa.Column("model", sa.String(128), nullable=False),
            sa.Column("temperature", sa.Float(), nullable=True),
            sa.Column("agent_planner_mode", sa.String(32), nullable=True),
            sa.Column("text2sql_prompt", sa.Text(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
        ],
    )
    _create_or_sync(
        "roles",
        [
            sa.Column("id", sa.Integer(), primary_key=True, index=True),
            sa.Column("code", sa.String(64), nullable=False, index=True),
            sa.Column("name", sa.String(128), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("org_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=True, index=True),
            sa.Column("is_builtin", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("data_scope", sa.String(32), nullable=True),
            sa.Column("menu_permissions", sa.Text(), nullable=True),
            sa.Column("action_permissions", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
        ],
        sa.UniqueConstraint("code", "org_id", name="uq_roles_code_org"),
    )


_TABLES = [
    "roles",
    "llm_settings",
    "agent_runs",
    "pinned_charts",
    "query_history",
    "scheduled_reports",
    "notification_settings",
    "alert_history",
    "alerts",
    "data_quality_rules",
    "data_pipeline_runs",
    "data_pipelines",
    "report_fill_records",
    "report_runs",
    "report_template_versions",
    "report_templates",
    "embed_tokens",
    "data_link_logs",
    "data_link_tasks",
    "data_links",
]


def downgrade() -> None:
    for table_name in _TABLES:
        if _has_table(table_name):
            op.drop_table(table_name)
