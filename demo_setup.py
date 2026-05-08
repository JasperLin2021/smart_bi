"""
蓝途科技演示数据集生成 + 自动入库脚本
运行: python demo_setup.py
会生成 Excel 文件并通过 API 创建完整的演示数据源、指标和看板
"""

import json
import random
import sys
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import requests

# ── 配置 ────────────────────────────────────────────────────────────────────
API_BASE = "http://localhost:8002/api"
USERNAME = "admin"
PASSWORD = "admin123"
EXCEL_OUTPUT = Path(__file__).parent / "backend/uploads/excel/blueway_demo.xlsx"
EXCEL_OUTPUT.parent.mkdir(parents=True, exist_ok=True)

random.seed(42)

# ── 基础数据定义 ─────────────────────────────────────────────────────────────

REGIONS = ["华东", "华南", "华北", "华西"]
REGION_CITIES = {
    "华东": ["上海", "南京", "杭州", "苏州", "宁波"],
    "华南": ["广州", "深圳", "成都", "厦门", "佛山"],
    "华北": ["北京", "天津", "西安", "郑州", "济南"],
    "华西": ["成都", "重庆", "武汉", "长沙", "昆明"],
}
SALESPERSONS = {
    "华东": ["李明", "王芳", "张伟"],
    "华南": ["陈静", "刘洋", "赵磊"],
    "华北": ["孙丽", "周杰", "吴敏"],
    "华西": ["徐强", "林燕", "黄涛"],
}
INDUSTRIES = ["制造业", "金融服务", "医疗健康", "零售电商", "政府机构", "教育科研", "互联网", "能源化工"]
CHANNELS = ["线上官网", "合作伙伴", "直销团队", "展会推广", "老客户转介绍"]
PAYMENT_METHODS = ["银行转账", "网银支付", "信用证", "承兑汇票"]
STATUSES = ["已完成", "已完成", "已完成", "进行中", "已退款"]  # 权重

PRODUCTS = [
    # (product_id, name, category, unit_price, cost, margin_rate)
    ("P001", "企业云基础套餐", "云服务", 58000, 18000, 0.69),
    ("P002", "企业云高级套餐", "云服务", 128000, 38000, 0.70),
    ("P003", "私有云解决方案", "云服务", 380000, 120000, 0.68),
    ("P004", "混合云管理平台", "云服务", 218000, 65000, 0.70),
    ("P005", "云备份与容灾服务", "云服务", 36000, 10000, 0.72),
    ("P006", "端点安全防护", "网络安全", 48000, 14000, 0.71),
    ("P007", "下一代防火墙", "网络安全", 98000, 28000, 0.71),
    ("P008", "数据加密套件", "网络安全", 68000, 20000, 0.71),
    ("P009", "安全运营中心(SOC)", "网络安全", 298000, 90000, 0.70),
    ("P010", "零信任网络访问", "网络安全", 158000, 48000, 0.70),
    ("P011", "数据仓库基础版", "数据分析", 88000, 26000, 0.70),
    ("P012", "数据仓库企业版", "数据分析", 268000, 80000, 0.70),
    ("P013", "实时流分析引擎", "数据分析", 168000, 50000, 0.70),
    ("P014", "BI报表与可视化平台", "数据分析", 78000, 22000, 0.72),
    ("P015", "数据治理与目录", "数据分析", 118000, 34000, 0.71),
    ("P016", "AI开发与训练平台", "AI平台", 388000, 118000, 0.70),
    ("P017", "智能客服系统", "AI平台", 128000, 38000, 0.70),
    ("P018", "销售预测分析引擎", "AI平台", 198000, 60000, 0.70),
    ("P019", "计算机视觉套件", "AI平台", 288000, 86000, 0.70),
    ("P020", "企业NLP引擎", "AI平台", 168000, 50000, 0.70),
]

CUSTOMER_NAMES = [
    "鑫华制造集团", "远洋金融科技", "博济医疗器械", "乐天电商平台", "华联数字政务",
    "卓越教育集团", "速途互联网", "能源智联集团", "前程金融控股", "万达制造科技",
    "汇丰智能电气", "蓝海生物科技", "建设数字银行", "华为生态合作伙伴", "联合汽车零部件",
    "天合光能储能", "美的智能制造", "中粮数字农业", "京东云战略伙伴", "招商银行数字部",
    "宁德时代数字化", "比亚迪智能系统", "海尔工业互联网", "格力智能工厂", "小米生态链",
    "阿里云ISV合作商", "腾讯政务云项目", "百度智能交通", "字节跳动数字营销", "平安科技集团",
    "中国人寿数科", "国家电网数字化", "中石油信息化", "中铁建数字工程", "央企数字转型",
    "省级医保数字化", "市级政务平台", "区级智慧城市", "高校信息化工程", "科研院所算力",
    "创业科技企业A", "创业科技企业B", "中型制造企业A", "中型制造企业B", "区域连锁零售",
    "跨境电商企业", "供应链科技公司", "物流数字化企业", "健康管理平台", "在线教育头部",
    "汽车经销集团", "房地产数字化", "消费金融科技", "社区团购平台", "餐饮连锁数字",
    "生鲜冷链物流", "新能源充电网络", "智慧停车集团", "工业互联平台", "智慧园区运营",
]


def gen_customers():
    rows = []
    for i, name in enumerate(CUSTOMER_NAMES):
        region = REGIONS[i % 4]
        city = random.choice(REGION_CITIES[region])
        tier = random.choices(["A", "B", "C"], weights=[0.2, 0.5, 0.3])[0]
        join = date(2022, 1, 1) + timedelta(days=random.randint(0, 700))
        rows.append({
            "customer_id": f"C{i+1:03d}",
            "company_name": name,
            "industry": random.choice(INDUSTRIES),
            "region": region,
            "city": city,
            "tier": tier,
            "acquisition_channel": random.choice(CHANNELS),
            "first_order_date": str(join),
        })
    return pd.DataFrame(rows)


def gen_products():
    rows = []
    for pid, name, cat, price, cost, margin in PRODUCTS:
        rows.append({
            "product_id": pid,
            "product_name": name,
            "category": cat,
            "list_price": price,
            "cost_price": cost,
            "margin_rate": margin,
            "is_active": 1,
        })
    return pd.DataFrame(rows)


def gen_orders_and_items(customers_df, products_df):
    orders, items = [], []
    order_id = 1
    item_id = 1

    # 生成 2024-01 到 2025-03 的订单，带有业务趋势
    start = date(2024, 1, 1)
    end = date(2025, 3, 31)
    d = start
    while d <= end:
        # 月末冲刺：最后5天订单量翻倍
        month_end_boost = 2.0 if d.day >= 26 else 1.0
        # Q4旺季
        q4_boost = 1.4 if d.month in (10, 11, 12) else 1.0
        # 年初淡季
        jan_dip = 0.6 if d.month == 1 else 1.0
        # 2025年增长
        growth = 1.25 if d.year == 2025 else 1.0

        daily_orders = int(random.gauss(2.2, 0.8) * month_end_boost * q4_boost * jan_dip * growth)
        daily_orders = max(0, daily_orders)

        for _ in range(daily_orders):
            cust = customers_df.sample(1).iloc[0]
            region = cust["region"]
            salesperson = random.choice(SALESPERSONS[region])

            # 选1-3个产品
            n_items = random.choices([1, 2, 3], weights=[0.55, 0.33, 0.12])[0]
            chosen_products = products_df.sample(n_items)

            order_total = 0
            for _, prod in chosen_products.iterrows():
                qty = random.randint(1, 5)
                discount = random.choices([0, 0.05, 0.08, 0.1, 0.15], weights=[0.4, 0.2, 0.2, 0.15, 0.05])[0]
                subtotal = round(prod["list_price"] * qty * (1 - discount), 2)
                order_total += subtotal
                items.append({
                    "item_id": f"I{item_id:05d}",
                    "order_id": f"ORD{order_id:05d}",
                    "product_id": prod["product_id"],
                    "product_name": prod["product_name"],
                    "category": prod["category"],
                    "quantity": qty,
                    "unit_price": prod["list_price"],
                    "discount_rate": discount,
                    "subtotal": subtotal,
                })
                item_id += 1

            status = random.choices(["已完成", "进行中", "已退款"],
                                    weights=[0.82, 0.14, 0.04])[0]
            orders.append({
                "order_id": f"ORD{order_id:05d}",
                "customer_id": cust["customer_id"],
                "customer_name": cust["company_name"],
                "order_date": str(d),
                "region": region,
                "city": cust["city"],
                "salesperson": salesperson,
                "total_amount": round(order_total, 2),
                "status": status,
                "payment_method": random.choice(PAYMENT_METHODS),
            })
            order_id += 1

        d += timedelta(days=1)

    return pd.DataFrame(orders), pd.DataFrame(items)


def gen_monthly_kpi(orders_df):
    """生成月度目标 vs 实际数据"""
    rows = []
    for year in [2024, 2025]:
        max_month = 12 if year == 2024 else 3
        for month in range(1, max_month + 1):
            ym = f"{year}-{month:02d}"
            for region in REGIONS:
                # 实际销售额
                mask = (
                    orders_df["order_date"].str.startswith(ym) &
                    (orders_df["region"] == region) &
                    (orders_df["status"] == "已完成")
                )
                actual = float(orders_df[mask]["total_amount"].sum())

                # 目标（实际的 90%~115%，制造紧张感）
                target_rate = random.uniform(0.9, 1.15)
                target = round(actual * target_rate, -3)  # 取整到千

                # 新客数
                new_custs = random.randint(1, 6)

                # 净推荐值 NPS
                nps = random.randint(28, 72)

                rows.append({
                    "year_month": ym,
                    "year": year,
                    "month": month,
                    "region": region,
                    "revenue_target": target,
                    "actual_revenue": round(actual, 2),
                    "achievement_rate": round(actual / target, 4) if target > 0 else 0,
                    "new_customers": new_custs,
                    "nps_score": nps,
                })
    return pd.DataFrame(rows)


def write_excel(customers_df, products_df, orders_df, items_df, kpi_df):
    with pd.ExcelWriter(str(EXCEL_OUTPUT), engine="openpyxl") as writer:
        customers_df.to_excel(writer, sheet_name="customers-客户", index=False)
        products_df.to_excel(writer, sheet_name="products-产品", index=False)
        orders_df.to_excel(writer, sheet_name="orders-订单", index=False)
        items_df.to_excel(writer, sheet_name="order_items-订单明细", index=False)
        kpi_df.to_excel(writer, sheet_name="monthly_kpi-月度KPI", index=False)
    print(f"✓ Excel 已生成: {EXCEL_OUTPUT}")
    return str(EXCEL_OUTPUT)


# ── API 调用 ──────────────────────────────────────────────────────────────────

def login():
    r = requests.post(f"{API_BASE}/auth/login", json={"username": USERNAME, "password": PASSWORD})
    r.raise_for_status()
    token = r.json()["access_token"]
    print(f"✓ 登录成功 ({USERNAME})")
    return {"Authorization": f"Bearer {token}"}


def create_datasource(headers, excel_path):
    # 上传文件
    with open(excel_path, "rb") as f:
        r = requests.post(f"{API_BASE}/datasources/upload-excel",
                          files={"file": ("blueway_demo.xlsx", f, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
                          headers=headers)
    r.raise_for_status()
    upload_url = r.json()["database_url"]
    print(f"✓ 文件上传成功")

    # 检查是否已存在
    existing = requests.get(f"{API_BASE}/datasources", headers=headers).json()
    for ds in existing:
        if ds.get("slug") == "blueway-demo":
            print(f"  数据源已存在 (id={ds['id']})，跳过创建")
            return ds["id"]

    payload = {
        "name": "蓝途科技销售数据",
        "slug": "blueway-demo",
        "source_type": "excel",
        "database_url": upload_url,
        "metadata_prompt": METADATA_PROMPT,
        "metrics_prompt": METRICS_PROMPT,
        "recommend_questions": RECOMMEND_QUESTIONS,
    }
    r = requests.post(f"{API_BASE}/datasources", json=payload, headers=headers)
    r.raise_for_status()
    ds_id = r.json()["id"]
    print(f"✓ 数据源已创建 (id={ds_id})")
    return ds_id


def detect_and_save_schema(headers, ds_id):
    r = requests.post(f"{API_BASE}/datasources/{ds_id}/detect-schema", headers=headers)
    if not r.ok:
        print(f"  Schema 检测失败: {r.text}")
        return
    schema = r.json()
    print(f"✓ Schema 检测完成: {len(schema['tables'])} 张表")

    # 生成 prompt
    r2 = requests.post(f"{API_BASE}/datasources/{ds_id}/generate-prompt",
                        json=schema, headers=headers)
    if r2.ok:
        new_prompt = r2.json().get("metadata_prompt", "")
        requests.put(f"{API_BASE}/datasources/{ds_id}",
                     json={"schema_metadata": schema, "metadata_prompt": new_prompt or METADATA_PROMPT},
                     headers=headers)
        print(f"✓ 元数据提示词已生成")


def create_metrics(headers, ds_id):
    metrics = [
        {
            "datasource_id": ds_id,
            "name": "销售总额",
            "definition": "所有已完成订单的 total_amount 求和",
            "formula": "SUM(orders.total_amount) WHERE status = '已完成'",
            "table_name": "orders",
            "column_name": "total_amount",
            "aggregation": "SUM",
            "unit": "元",
            "description": "统计周期内全部已完成订单的销售金额总和，是最核心的营收指标",
            "certification_status": "certified",
            "certified_by": "admin",
            "quality_status": "normal",
            "caliber_version": "v2.1",
            "owner_name": "数据分析团队",
        },
        {
            "datasource_id": ds_id,
            "name": "订单数量",
            "definition": "已完成订单的总数",
            "formula": "COUNT(orders.order_id) WHERE status = '已完成'",
            "table_name": "orders",
            "column_name": "order_id",
            "aggregation": "COUNT",
            "unit": "单",
            "description": "统计周期内已完成的订单笔数",
            "certification_status": "certified",
            "certified_by": "admin",
            "quality_status": "normal",
            "caliber_version": "v1.0",
            "owner_name": "销售运营",
        },
        {
            "datasource_id": ds_id,
            "name": "客单价",
            "definition": "销售总额 ÷ 订单数量",
            "formula": "AVG(orders.total_amount) WHERE status = '已完成'",
            "table_name": "orders",
            "column_name": "total_amount",
            "aggregation": "AVG",
            "unit": "元/单",
            "description": "已完成订单的平均金额，反映客户购买力和产品组合水平",
            "certification_status": "certified",
            "certified_by": "admin",
            "quality_status": "normal",
            "caliber_version": "v1.2",
            "owner_name": "商业分析",
        },
        {
            "datasource_id": ds_id,
            "name": "目标达成率",
            "definition": "实际销售额 ÷ 销售目标 × 100%",
            "formula": "AVG(monthly_kpi.achievement_rate)",
            "table_name": "monthly_kpi",
            "column_name": "achievement_rate",
            "aggregation": "AVG",
            "unit": "%",
            "description": "月度销售目标完成百分比，低于 90% 触发预警",
            "certification_status": "certified",
            "certified_by": "admin",
            "quality_status": "normal",
            "caliber_version": "v1.0",
            "owner_name": "销售管理",
        },
        {
            "datasource_id": ds_id,
            "name": "毛利率",
            "definition": "（销售额 - 产品成本）÷ 销售额",
            "formula": "AVG(products.margin_rate)",
            "table_name": "products",
            "column_name": "margin_rate",
            "aggregation": "AVG",
            "unit": "%",
            "description": "产品平均毛利率，反映盈利能力",
            "certification_status": "draft",
            "quality_status": "normal",
            "caliber_version": "v0.9",
            "owner_name": "财务分析",
        },
        {
            "datasource_id": ds_id,
            "name": "NPS净推荐值",
            "definition": "客户满意度净推荐值",
            "formula": "AVG(monthly_kpi.nps_score)",
            "table_name": "monthly_kpi",
            "column_name": "nps_score",
            "aggregation": "AVG",
            "unit": "分",
            "description": "衡量客户满意度和忠诚度的核心指标，行业均值约 45",
            "certification_status": "draft",
            "quality_status": "stale",
            "quality_message": "NPS 数据上次更新于上季度末，待本季度核实",
            "caliber_version": "v1.0",
            "owner_name": "客户成功",
        },
        # ── 跨表关联指标 (JOIN示例) ──────────────────────────────────
        {
            "datasource_id": ds_id,
            "name": "大区产品类别销售汇总",
            "definition": (
                "关联订单、客户、订单明细和产品四张表，统计各大区 × 各产品类别的销售总额。"
                "SQL:\n"
                "SELECT c.region AS 大区, p.category AS 产品类别,\n"
                "       COUNT(DISTINCT o.id) AS 订单数,\n"
                "       SUM(o.total_amount)  AS 销售总额,\n"
                "       ROUND(SUM(o.total_amount) / COUNT(DISTINCT o.id), 2) AS 客单价\n"
                "FROM orders o\n"
                "LEFT JOIN customers   c  ON o.customer_id = c.id\n"
                "LEFT JOIN order_items oi ON o.id = oi.order_id\n"
                "LEFT JOIN products    p  ON oi.product_id = p.id\n"
                "WHERE o.status = '已完成'\n"
                "GROUP BY c.region, p.category\n"
                "ORDER BY 销售总额 DESC"
            ),
            "formula": "SUM(o.total_amount) / COUNT(DISTINCT o.id) — 多表 JOIN 聚合",
            "table_name": "orders",          # 主表
            "column_name": "total_amount",
            "aggregation": "SUM",
            "unit": "元",
            "description": "多维度交叉分析：大区 × 产品类别下的销售总额、订单数和客单价，需关联四张表",
            "certification_status": "certified",
            "certified_by": "admin",
            "quality_status": "normal",
            "caliber_version": "v1.0",
            "owner_name": "数据分析团队",
            "lineage_json": {
                "type": "join",
                "description": "通过关联订单、客户、订单明细和产品表，支持按大区和产品类别多维度分析销售数据",
                "joins": [
                    {
                        "table": "orders",
                        "alias": "o",
                        "role": "primary",
                        "join_type": None,
                        "join_on": None,
                        "columns": ["id", "customer_id", "total_amount", "status", "order_date"],
                    },
                    {
                        "table": "customers",
                        "alias": "c",
                        "role": "dimension",
                        "join_type": "LEFT JOIN",
                        "join_on": "o.customer_id = c.id",
                        "columns": ["id", "region", "industry"],
                    },
                    {
                        "table": "order_items",
                        "alias": "oi",
                        "role": "bridge",
                        "join_type": "LEFT JOIN",
                        "join_on": "o.id = oi.order_id",
                        "columns": ["order_id", "product_id", "quantity", "unit_price"],
                    },
                    {
                        "table": "products",
                        "alias": "p",
                        "role": "dimension",
                        "join_type": "LEFT JOIN",
                        "join_on": "oi.product_id = p.id",
                        "columns": ["id", "category", "name"],
                    },
                ],
                "filters": ["o.status = '已完成'"],
            },
        },
    ]

    existing_resp = requests.get(f"{API_BASE}/metrics", headers=headers).json()
    existing = existing_resp if isinstance(existing_resp, list) else existing_resp.get("items", existing_resp.get("data", []))
    existing_names = {m["name"] for m in existing}

    created = 0
    for m in metrics:
        if m["name"] in existing_names:
            continue
        r = requests.post(f"{API_BASE}/metrics", json=m, headers=headers)
        if r.ok:
            created += 1
        else:
            print(f"  指标创建失败: {m['name']} - {r.text[:80]}")

    print(f"✓ 指标创建完成 ({created} 个新建，{len(metrics)-created} 个已存在)")


METADATA_PROMPT = """
# 蓝途科技销售数据库

这是一个 SaaS 软件企业的销售数据集，包含订单、客户、产品、明细和月度KPI共5张表。

## 表结构

### orders（订单主表）
核心事实表，每行一张订单。
- order_id: 订单唯一编号（如 ORD00001）
- customer_id: 客户编号，关联 customers 表
- customer_name: 客户公司名称
- order_date: 下单日期（YYYY-MM-DD）
- region: 大区（华东/华南/华北/华西）
- city: 城市
- salesperson: 负责销售人员姓名
- total_amount: 订单总金额（元）
- status: 订单状态（已完成/进行中/已退款）
- payment_method: 付款方式

### order_items（订单明细表）
每行为订单中的一个产品行项目。
- item_id: 明细编号
- order_id: 关联 orders.order_id
- product_id: 关联 products.product_id
- product_name: 产品名称
- category: 产品类别（云服务/网络安全/数据分析/AI平台）
- quantity: 数量
- unit_price: 单价（元）
- discount_rate: 折扣率（0~0.15）
- subtotal: 小计金额（元）

### products（产品表）
产品目录，共20款产品。
- product_id: 产品编号（P001~P020）
- product_name: 产品名称
- category: 类别（云服务/网络安全/数据分析/AI平台）
- list_price: 定价（元）
- cost_price: 成本价（元）
- margin_rate: 毛利率
- is_active: 是否在售

### customers（客户表）
60家企业客户信息。
- customer_id: 客户编号（C001~C060）
- company_name: 公司名称
- industry: 行业
- region: 所属大区
- city: 城市
- tier: 客户等级（A/B/C，A为最高价值）
- acquisition_channel: 获客渠道
- first_order_date: 首次下单日期

### monthly_kpi（月度KPI表）
各大区月度销售目标与完成情况，2024-01 至 2025-03。
- year_month: 年月（YYYY-MM）
- year: 年份
- month: 月份
- region: 大区
- revenue_target: 销售目标（元）
- actual_revenue: 实际完成（元）
- achievement_rate: 达成率（小数，如 0.95 = 95%）
- new_customers: 新增客户数
- nps_score: NPS净推荐值（0~100）

## 业务背景
- 时间范围：2024年1月 - 2025年3月
- 销售大区：华东（最强）> 华北 > 华南 > 华西
- 产品增长最快：AI平台 > 数据分析 > 云服务 > 网络安全
- Q4 为旺季，1月为淡季
- 目标达成率低于 90% 需重点关注
""".strip()

METRICS_PROMPT = """
核心业务指标定义：
- 销售总额 = SUM(orders.total_amount) WHERE status='已完成'，单位：元
- 订单数量 = COUNT(orders.order_id) WHERE status='已完成'，单位：单
- 客单价 = AVG(orders.total_amount) WHERE status='已完成'，单位：元/单
- 目标达成率 = AVG(monthly_kpi.achievement_rate)，单位：%（低于0.9为预警）
- 毛利率 = AVG(products.margin_rate)，整体约70%
- NPS净推荐值 = AVG(monthly_kpi.nps_score)，满分100

常用维度拆解：
- 按大区(region)：华东、华南、华北、华西
- 按产品类别(category)：云服务、网络安全、数据分析、AI平台
- 按客户等级(tier)：A/B/C
- 按时间：order_date 按月/季度/年
- 按销售人员(salesperson)

订单状态：已完成（统计核心）/ 进行中（在途）/ 已退款（剔除）
""".strip()

RECOMMEND_QUESTIONS = [
    "2024年各大区的销售总额是多少？",
    "哪个产品类别增长最快？",
    "各销售人员2024年Q4的业绩排名",
    "华东区2024年每月销售趋势",
    "目标达成率最低的大区是哪个？",
    "客户等级A的平均客单价是多少？",
    "2025年Q1与2024年Q1的对比",
    "哪些客户在2024年下了5单以上？",
]


def main():
    print("=" * 55)
    print("  蓝途科技演示数据集 — 自动化安装脚本")
    print("=" * 55)

    # 1. 生成数据
    print("\n[1/4] 生成演示数据...")
    customers_df = gen_customers()
    products_df = gen_products()
    orders_df, items_df = gen_orders_and_items(customers_df, products_df)
    kpi_df = gen_monthly_kpi(orders_df)

    print(f"  客户: {len(customers_df)} 家")
    print(f"  产品: {len(products_df)} 款")
    print(f"  订单: {len(orders_df)} 笔  |  明细: {len(items_df)} 行")
    print(f"  KPI:  {len(kpi_df)} 行（{kpi_df['year_month'].min()} ~ {kpi_df['year_month'].max()}）")

    total_revenue = orders_df[orders_df["status"] == "已完成"]["total_amount"].sum()
    print(f"  ✦ 总销售额: ¥{total_revenue/1e6:.1f}M")

    write_excel(customers_df, products_df, orders_df, items_df, kpi_df)

    # 2. API 操作
    print("\n[2/4] 登录 API...")
    try:
        headers = login()
    except Exception as e:
        print(f"  ✗ 登录失败: {e}")
        print("  请确认后端运行在 http://localhost:8002")
        sys.exit(1)

    print("\n[3/4] 创建数据源并检测 Schema...")
    ds_id = create_datasource(headers, str(EXCEL_OUTPUT))
    detect_and_save_schema(headers, ds_id)

    print("\n[4/4] 创建演示指标（含血缘信息）...")
    create_metrics(headers, ds_id)

    print("\n" + "=" * 55)
    print("  ✅ 演示数据集安装完成！")
    print("=" * 55)
    print(f"""
  数据源名称:  蓝途科技销售数据
  数据源标识:  blueway-demo

  推荐演示路径:
  1. 「数据源管理」→ 查看表结构和关联关系
  2. 「指标管理」→ 查看 6 个指标的血缘可视化
  3. 「智能问数」→ 选择「蓝途科技销售数据」开始提问
  4. 固定图表后，进入「看板」体验联动过滤

  示例问题:
  • 2024年各大区销售总额是多少？
  • 哪个产品类别增长最快？
  • 目标达成率最低的大区
  • 2025年Q1 vs 2024年Q1 对比
""")


if __name__ == "__main__":
    main()
