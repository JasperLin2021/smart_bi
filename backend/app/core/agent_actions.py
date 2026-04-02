from typing import Dict, List


ACTION_SPECS: Dict[str, dict] = {
    "navigate": {
        "risk": "low",
        "roles": ["user", "org_admin", "super_admin"],
        "description": "切换到某个页面路由",
        "params": ["route"],
    },
    "switch_datasource": {
        "risk": "low",
        "roles": ["user", "org_admin", "super_admin"],
        "description": "切换当前数据源",
        "params": ["datasource_name"],
    },
    "ask_query": {
        "risk": "low",
        "roles": ["user", "org_admin", "super_admin"],
        "description": "在智能问数里发起一个问题",
        "params": ["question"],
    },
    "create_datasource": {
        "risk": "medium",
        "roles": ["org_admin", "super_admin"],
        "description": "创建数据源",
        "params": ["name", "slug", "source_type", "database_url"],
    },
    "update_datasource": {
        "risk": "medium",
        "roles": ["org_admin", "super_admin"],
        "description": "更新数据源",
        "params": ["datasource_name"],
    },
    "delete_datasource": {
        "risk": "high",
        "roles": ["org_admin", "super_admin"],
        "description": "删除数据源",
        "params": ["datasource_name"],
    },
    "test_datasource": {
        "risk": "low",
        "roles": ["org_admin", "super_admin"],
        "description": "测试数据源连接",
        "params": ["datasource_name"],
    },
    "detect_schema": {
        "risk": "low",
        "roles": ["org_admin", "super_admin"],
        "description": "自动检测数据源表结构",
        "params": ["datasource_name"],
    },
    "generate_drill_config": {
        "risk": "low",
        "roles": ["org_admin", "super_admin"],
        "description": "生成数据源钻取候选规则",
        "params": ["datasource_name"],
    },
    "create_user": {
        "risk": "high",
        "roles": ["org_admin", "super_admin"],
        "description": "创建用户",
        "params": ["username", "password", "role"],
    },
    "update_user": {
        "risk": "high",
        "roles": ["org_admin", "super_admin"],
        "description": "更新用户",
        "params": ["username"],
    },
    "delete_user": {
        "risk": "high",
        "roles": ["org_admin", "super_admin"],
        "description": "删除用户",
        "params": ["username"],
    },
    "create_organization": {
        "risk": "high",
        "roles": ["super_admin"],
        "description": "创建企业",
        "params": ["name", "slug"],
    },
    "update_organization": {
        "risk": "high",
        "roles": ["super_admin"],
        "description": "更新企业",
        "params": ["name"],
    },
    "delete_organization": {
        "risk": "high",
        "roles": ["super_admin"],
        "description": "删除企业",
        "params": ["name"],
    },
    "create_metric": {
        "risk": "high",
        "roles": ["super_admin"],
        "description": "创建指标",
        "params": ["name", "definition"],
    },
    "update_metric": {
        "risk": "high",
        "roles": ["super_admin"],
        "description": "更新指标",
        "params": ["name"],
    },
    "delete_metric": {
        "risk": "high",
        "roles": ["super_admin"],
        "description": "删除指标",
        "params": ["name"],
    },
    "update_llm_settings": {
        "risk": "high",
        "roles": ["super_admin"],
        "description": "更新大模型配置",
        "params": ["provider", "base_url", "model", "temperature", "agent_planner_mode"],
    },
    "refresh_llm_settings": {
        "risk": "medium",
        "roles": ["super_admin"],
        "description": "刷新大模型缓存配置",
        "params": [],
    },
    "install_agent_skill": {
        "risk": "high",
        "roles": ["super_admin"],
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
