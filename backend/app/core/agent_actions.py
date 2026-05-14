from typing import Dict, List


ALL_ROLES = ["user", "dept_admin", "org_admin", "super_admin"]
BI_ADMIN_ROLES = ["dept_admin", "org_admin", "super_admin"]
ORG_ADMIN_ROLES = ["org_admin", "super_admin"]
SUPER_ADMIN_ROLES = ["super_admin"]


ACTION_SPECS: Dict[str, dict] = {
    "navigate": {
        "risk": "low",
        "roles": ALL_ROLES,
        "description": "切换到某个页面路由",
        "params": ["route"],
    },
    "switch_datasource": {
        "risk": "low",
        "roles": ALL_ROLES,
        "description": "切换当前数据源",
        "params": ["datasource_name"],
    },
    "ask_query": {
        "risk": "low",
        "roles": ALL_ROLES,
        "description": "在智能问数里发起一个问题",
        "params": ["question"],
    },
    "create_datasource": {
        "risk": "medium",
        "roles": ORG_ADMIN_ROLES,
        "description": "创建数据源",
        "params": ["name", "slug", "source_type", "database_url"],
    },
    "update_datasource": {
        "risk": "medium",
        "roles": ORG_ADMIN_ROLES,
        "description": "更新数据源",
        "params": ["datasource_name"],
    },
    "delete_datasource": {
        "risk": "high",
        "roles": ORG_ADMIN_ROLES,
        "description": "删除数据源",
        "params": ["datasource_name"],
    },
    "test_datasource": {
        "risk": "low",
        "roles": ORG_ADMIN_ROLES,
        "description": "测试数据源连接",
        "params": ["datasource_name"],
    },
    "detect_schema": {
        "risk": "low",
        "roles": ORG_ADMIN_ROLES,
        "description": "自动检测数据源表结构",
        "params": ["datasource_name"],
    },
    "generate_drill_config": {
        "risk": "low",
        "roles": ORG_ADMIN_ROLES,
        "description": "生成数据源钻取候选规则",
        "params": ["datasource_name"],
    },
    "create_dataset": {
        "risk": "medium",
        "roles": ALL_ROLES,
        "description": "创建数据集",
        "params": ["name", "datasource_id", "fields_json"],
    },
    "update_dataset": {
        "risk": "medium",
        "roles": ALL_ROLES,
        "description": "更新数据集",
        "params": ["dataset_name"],
    },
    "publish_dataset": {
        "risk": "medium",
        "roles": ALL_ROLES,
        "description": "发布数据集",
        "params": ["dataset_name"],
    },
    "refresh_dataset": {
        "risk": "medium",
        "roles": ALL_ROLES,
        "description": "刷新数据集",
        "params": ["dataset_name"],
    },
    "delete_dataset": {
        "risk": "high",
        "roles": ALL_ROLES,
        "description": "删除数据集",
        "params": ["dataset_name"],
    },
    "create_dashboard": {
        "risk": "medium",
        "roles": ALL_ROLES,
        "description": "创建看板",
        "params": ["title"],
    },
    "update_dashboard": {
        "risk": "medium",
        "roles": ALL_ROLES,
        "description": "更新看板",
        "params": ["dashboard_title"],
    },
    "publish_dashboard": {
        "risk": "medium",
        "roles": ALL_ROLES,
        "description": "发布看板",
        "params": ["dashboard_title"],
    },
    "delete_dashboard": {
        "risk": "high",
        "roles": ALL_ROLES,
        "description": "删除看板",
        "params": ["dashboard_title"],
    },
    "create_pipeline": {
        "risk": "medium",
        "roles": BI_ADMIN_ROLES,
        "description": "创建数据加工管道",
        "params": ["name", "dataset_id", "dag_json"],
    },
    "run_pipeline": {
        "risk": "medium",
        "roles": BI_ADMIN_ROLES,
        "description": "运行数据加工管道",
        "params": ["pipeline_name", "mode"],
    },
    "delete_pipeline": {
        "risk": "high",
        "roles": ["org_admin", "super_admin"],
        "description": "删除数据加工管道",
        "params": ["pipeline_name"],
    },
    "create_analysis_view": {
        "risk": "medium",
        "roles": ALL_ROLES,
        "description": "创建自助分析视图",
        "params": ["name", "dataset_id", "dimensions", "measures", "chart_type"],
    },
    "update_analysis_view": {
        "risk": "medium",
        "roles": ALL_ROLES,
        "description": "更新自助分析视图",
        "params": ["view_name"],
    },
    "publish_analysis_view": {
        "risk": "medium",
        "roles": BI_ADMIN_ROLES,
        "description": "发布自助分析视图",
        "params": ["view_name"],
    },
    "create_report_template": {
        "risk": "medium",
        "roles": BI_ADMIN_ROLES,
        "description": "创建复杂报表模板",
        "params": ["name", "dataset_id", "report_type"],
    },
    "update_report_template": {
        "risk": "medium",
        "roles": BI_ADMIN_ROLES,
        "description": "更新复杂报表模板",
        "params": ["template_name"],
    },
    "delete_report_template": {
        "risk": "high",
        "roles": ["org_admin", "super_admin"],
        "description": "删除复杂报表模板",
        "params": ["template_name"],
    },
    "create_action_item": {
        "risk": "medium",
        "roles": ALL_ROLES,
        "description": "创建行动项",
        "params": ["title", "owner_id"],
    },
    "update_action_item": {
        "risk": "medium",
        "roles": ALL_ROLES,
        "description": "更新行动项",
        "params": ["action_item_title"],
    },
    "delete_action_item": {
        "risk": "high",
        "roles": ALL_ROLES,
        "description": "删除行动项",
        "params": ["action_item_title"],
    },
    "create_user": {
        "risk": "high",
        "roles": ORG_ADMIN_ROLES,
        "description": "创建用户",
        "params": ["username", "password", "role"],
    },
    "update_user": {
        "risk": "high",
        "roles": ORG_ADMIN_ROLES,
        "description": "更新用户",
        "params": ["username"],
    },
    "delete_user": {
        "risk": "high",
        "roles": ORG_ADMIN_ROLES,
        "description": "删除用户",
        "params": ["username"],
    },
    "create_organization": {
        "risk": "high",
        "roles": SUPER_ADMIN_ROLES,
        "description": "创建企业",
        "params": ["name", "slug"],
    },
    "update_organization": {
        "risk": "high",
        "roles": SUPER_ADMIN_ROLES,
        "description": "更新企业",
        "params": ["name"],
    },
    "delete_organization": {
        "risk": "high",
        "roles": SUPER_ADMIN_ROLES,
        "description": "删除企业",
        "params": ["name"],
    },
    "create_metric": {
        "risk": "high",
        "roles": SUPER_ADMIN_ROLES,
        "description": "创建指标",
        "params": ["name", "definition"],
    },
    "update_metric": {
        "risk": "high",
        "roles": SUPER_ADMIN_ROLES,
        "description": "更新指标",
        "params": ["name"],
    },
    "delete_metric": {
        "risk": "high",
        "roles": SUPER_ADMIN_ROLES,
        "description": "删除指标",
        "params": ["name"],
    },
    "update_llm_settings": {
        "risk": "high",
        "roles": SUPER_ADMIN_ROLES,
        "description": "更新大模型配置",
        "params": ["provider", "base_url", "model", "temperature", "agent_planner_mode"],
    },
    "refresh_llm_settings": {
        "risk": "medium",
        "roles": SUPER_ADMIN_ROLES,
        "description": "刷新大模型缓存配置",
        "params": [],
    },
    "install_agent_skill": {
        "risk": "high",
        "roles": SUPER_ADMIN_ROLES,
        "description": "安装外部 Agent Skill",
        "params": ["source"],
    },
}


def get_action_catalog(role: str) -> List[dict]:
    return [
        {"type": action_type, **spec}
        for action_type, spec in ACTION_SPECS.items()
        if role in spec["roles"]
    ]
