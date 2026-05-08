"""
feature_demo_setup.py — 为三个新功能创建演示数据
运行方式: python feature_demo_setup.py
"""
import requests
import json
import random
from datetime import date, timedelta

API_BASE = "http://localhost:8001/api"  # 如果从docker外访问需要改端口

# ── 登录 ─────────────────────────────────────────────────────────────────────
def login(username="admin", password="admin123"):
    r = requests.post(f"{API_BASE}/auth/login", json={"username": username, "password": password})
    r.raise_for_status()
    return r.json()["access_token"]

# ── 在主数据库里建业务数据表 ──────────────────────────────────────────────────
CREATE_TABLES_SQL = """
-- 时序销售数据（用于预测分析演示）
CREATE TABLE IF NOT EXISTS demo_sales (
    id SERIAL PRIMARY KEY,
    sale_date DATE NOT NULL,
    category VARCHAR(32) NOT NULL,
    revenue NUMERIC(12,2) NOT NULL,
    order_count INTEGER NOT NULL
);

-- 产品库存数据（用于AI报告演示）
CREATE TABLE IF NOT EXISTS demo_products (
    id SERIAL PRIMARY KEY,
    name VARCHAR(64) NOT NULL,
    category VARCHAR(32) NOT NULL,
    price NUMERIC(10,2) NOT NULL,
    stock INTEGER NOT NULL,
    sold_last_30d INTEGER NOT NULL
);

-- 用户活跃数据（用于嵌入演示）
CREATE TABLE IF NOT EXISTS demo_user_activity (
    id SERIAL PRIMARY KEY,
    activity_date DATE NOT NULL,
    new_users INTEGER NOT NULL,
    active_users INTEGER NOT NULL,
    churned_users INTEGER NOT NULL
);
"""

# ── 生成时序销售数据（过去18个月）────────────────────────────────────────────
def gen_sales_data():
    categories = ["电子产品", "服装", "家居", "食品", "运动"]
    today = date.today()
    rows = []
    for month_offset in range(18, -1, -1):
        d = today.replace(day=1) - timedelta(days=30 * month_offset)
        for cat in categories:
            base = {"电子产品": 82000, "服装": 45000, "家居": 38000, "食品": 62000, "运动": 31000}[cat]
            trend = 1 + month_offset * 0.02  # 上涨趋势
            seasonal = 1.2 if d.month in (11, 12) else (0.85 if d.month in (1, 2) else 1.0)
            revenue = round(base * trend * seasonal * random.uniform(0.92, 1.08), 2)
            count = int(revenue / random.randint(180, 320))
            rows.append((str(d), cat, revenue, count))
    return rows

def gen_product_data():
    products = [
        ("iPhone 15", "电子产品", 6999, 234, 189),
        ("华为Mate60", "电子产品", 5999, 312, 278),
        ("小米14", "电子产品", 3999, 521, 445),
        ("耐克运动鞋", "运动", 899, 867, 523),
        ("阿迪运动裤", "服装", 459, 1203, 789),
        ("北面冲锋衣", "服装", 1899, 445, 312),
        ("宜家书桌", "家居", 1299, 234, 145),
        ("戴森吸尘器", "家居", 3299, 167, 89),
        ("农夫山泉(箱)", "食品", 32, 4521, 3890),
        ("元气森林气泡水", "食品", 58, 2340, 1980),
        ("乐高积木套装", "运动", 299, 678, 234),
        ("瑜伽垫", "运动", 129, 1234, 876),
    ]
    return products

def gen_activity_data():
    today = date.today()
    rows = []
    for week_offset in range(24, -1, -1):
        d = today - timedelta(weeks=week_offset)
        new_users = int(random.gauss(1200, 150) * (1 + week_offset * 0.01))
        active_users = int(random.gauss(8500, 800) * (1 + week_offset * 0.005))
        churned = int(random.gauss(350, 60))
        rows.append((str(d), max(50, new_users), max(1000, active_users), max(10, churned)))
    return rows

# ── 通过 SQL API 执行建表和插入 ───────────────────────────────────────────────
def exec_sql(token, datasource_id, sql):
    r = requests.post(f"{API_BASE}/pinned-charts/preview", headers={"Authorization": f"Bearer {token}"},
                      json={"datasource_id": datasource_id, "sql_query": sql})
    if r.status_code != 200:
        print(f"  SQL错误: {r.json().get('detail','?')[:120]}")
        return False
    return True

def setup_tables(token, datasource_id):
    print("→ 创建业务数据表...")
    for stmt in CREATE_TABLES_SQL.strip().split(";\n\n"):
        stmt = stmt.strip()
        if stmt:
            ok = exec_sql(token, datasource_id, stmt)
            if not ok:
                print(f"  跳过: {stmt[:60]}...")

    print("→ 插入销售数据...")
    sales = gen_sales_data()
    # Insert in batches
    chunk = 50
    for i in range(0, len(sales), chunk):
        batch = sales[i:i+chunk]
        values = ", ".join(f"('{r[0]}', '{r[1]}', {r[2]}, {r[3]})" for r in batch)
        exec_sql(token, datasource_id, f"INSERT INTO demo_sales (sale_date, category, revenue, order_count) VALUES {values} ON CONFLICT DO NOTHING")

    print("→ 插入产品数据...")
    for p in gen_product_data():
        exec_sql(token, datasource_id, f"INSERT INTO demo_products (name, category, price, stock, sold_last_30d) VALUES ('{p[0]}', '{p[1]}', {p[2]}, {p[3]}, {p[4]}) ON CONFLICT (id) DO NOTHING")

    print("→ 插入用户活跃数据...")
    activity = gen_activity_data()
    for r in activity:
        exec_sql(token, datasource_id, f"INSERT INTO demo_user_activity (activity_date, new_users, active_users, churned_users) VALUES ('{r[0]}', {r[1]}, {r[2]}, {r[3]}) ON CONFLICT DO NOTHING")

# ── 创建固定图表 ─────────────────────────────────────────────────────────────
CHARTS = [
    {
        "title": "月度总销售额趋势（含预测）",
        "description": "按月汇总所有品类销售额，可用于时序预测分析",
        "sql_query": """SELECT TO_CHAR(DATE_TRUNC('month', sale_date), 'YYYY-MM') AS stat_month,
       SUM(revenue) AS total_revenue
FROM demo_sales
GROUP BY DATE_TRUNC('month', sale_date)
ORDER BY DATE_TRUNC('month', sale_date)""",
        "chart_type": "line",
        "sort_order": "none",
    },
    {
        "title": "各品类月度销售额趋势",
        "description": "电子产品、服装等5大品类销售走势",
        "sql_query": """SELECT TO_CHAR(DATE_TRUNC('month', sale_date), 'YYYY-MM') AS stat_month,
       category, SUM(revenue) AS revenue
FROM demo_sales
GROUP BY DATE_TRUNC('month', sale_date), category
ORDER BY DATE_TRUNC('month', sale_date), category""",
        "chart_type": "line",
        "sort_order": "none",
    },
    {
        "title": "品类销售额占比",
        "description": "过去18个月各品类营收占比分析",
        "sql_query": """SELECT category, SUM(revenue) AS total_revenue
FROM demo_sales
GROUP BY category
ORDER BY total_revenue DESC""",
        "chart_type": "donut",
        "sort_order": "desc",
    },
    {
        "title": "产品库存与销量分析",
        "description": "各SKU库存和近30天销量，可用于AI分析报告",
        "sql_query": """SELECT name, category, price, stock, sold_last_30d,
       ROUND(sold_last_30d::numeric / NULLIF(stock, 0) * 100, 1) AS turnover_rate
FROM demo_products
ORDER BY sold_last_30d DESC""",
        "chart_type": "table",
        "sort_order": "desc",
    },
    {
        "title": "产品类别平均售价对比",
        "description": "各品类平均售价横向对比",
        "sql_query": """SELECT category,
       ROUND(AVG(price), 0) AS avg_price,
       MAX(price) AS max_price,
       MIN(price) AS min_price
FROM demo_products
GROUP BY category
ORDER BY avg_price DESC""",
        "chart_type": "bar",
        "sort_order": "desc",
    },
    {
        "title": "周度用户活跃趋势",
        "description": "新增/活跃/流失用户周度趋势，适合时序预测",
        "sql_query": """SELECT activity_date AS stat_date,
       new_users, active_users, churned_users
FROM demo_user_activity
ORDER BY activity_date""",
        "chart_type": "area",
        "sort_order": "none",
    },
    {
        "title": "月度订单量趋势",
        "description": "各月订单数量趋势，适合预测分析",
        "sql_query": """SELECT TO_CHAR(DATE_TRUNC('month', sale_date), 'YYYY-MM') AS stat_month,
       SUM(order_count) AS total_orders
FROM demo_sales
GROUP BY DATE_TRUNC('month', sale_date)
ORDER BY DATE_TRUNC('month', sale_date)""",
        "chart_type": "bar",
        "sort_order": "none",
    },
    {
        "title": "品类销售额排名（KPI）",
        "description": "各品类18个月累计营收排名",
        "sql_query": """SELECT category, SUM(revenue) AS total_revenue
FROM demo_sales
GROUP BY category
ORDER BY total_revenue DESC
LIMIT 1""",
        "chart_type": "kpi",
        "sort_order": "desc",
    },
]

def create_charts(token, datasource_id):
    print("→ 创建固定图表...")
    chart_ids = []
    for c in CHARTS:
        r = requests.post(f"{API_BASE}/pinned-charts",
                          headers={"Authorization": f"Bearer {token}"},
                          json={**c, "datasource_id": datasource_id})
        if r.status_code == 200:
            cid = r.json()["id"]
            chart_ids.append((cid, c["title"]))
            print(f"  ✓ 图表 #{cid}: {c['title']}")
        else:
            print(f"  ✗ 失败: {c['title']} — {r.json()}")
    return chart_ids

# ── 创建演示看板 ─────────────────────────────────────────────────────────────
def create_dashboards(token, chart_ids):
    print("→ 创建演示看板...")
    charts_by_title = {t: cid for cid, t in chart_ids}

    dashboards = [
        {
            "title": "销售分析看板（预测分析演示）",
            "description": "月度销售趋势与预测分析，包含时序预测和AI报告入口",
            "visibility": "org",
            "status": "published",
            "charts": [
                "月度总销售额趋势（含预测）",
                "各品类月度销售额趋势",
                "品类销售额占比",
                "月度订单量趋势",
            ],
        },
        {
            "title": "产品运营看板（AI分析演示）",
            "description": "产品库存、销量、价格分析，支持AI自然语言报告生成",
            "visibility": "org",
            "status": "published",
            "charts": [
                "产品库存与销量分析",
                "产品类别平均售价对比",
                "品类销售额排名（KPI）",
            ],
        },
        {
            "title": "用户增长看板（嵌入SDK演示）",
            "description": "用户新增/活跃/流失趋势，可通过Embed SDK嵌入到第三方系统",
            "visibility": "org",
            "status": "published",
            "charts": [
                "周度用户活跃趋势",
                "月度总销售额趋势（含预测）",
            ],
        },
    ]

    created = []
    for db_cfg in dashboards:
        chart_names = db_cfg.pop("charts")
        components = []
        chart_type_map = {t: ct for (_, t), ct_info in zip(chart_ids, CHARTS) for ct in [ct_info["chart_type"]]}

        for i, name in enumerate(chart_names):
            cid = charts_by_title.get(name)
            if not cid:
                continue
            ct = next((c["chart_type"] for c in CHARTS if c["title"] == name), "bar")
            w = 12 if ct == "table" else (6 if ct in ("kpi", "donut") else 6)
            h = 4 if ct == "table" else (2 if ct == "kpi" else 3)
            components.append({
                "id": f"comp-{cid}-{i}",
                "pinned_chart_id": cid,
                "title": name,
                "chart_type": ct,
                "sort_order": "none",
                "x": 0, "y": i, "w": w, "h": h,
            })

        r = requests.post(f"{API_BASE}/dashboards",
                          headers={"Authorization": f"Bearer {token}"},
                          json={**db_cfg, "layout_json": {"components": components}, "filters_json": {}})
        if r.status_code == 200:
            did = r.json()["id"]
            print(f"  ✓ 看板 #{did}: {db_cfg['title']}")
            # Publish
            requests.post(f"{API_BASE}/dashboards/{did}/publish",
                          headers={"Authorization": f"Bearer {token}"})
            created.append({"id": did, "title": db_cfg["title"]})
        else:
            print(f"  ✗ 失败: {db_cfg['title']} — {r.json()}")
    return created

# ── 创建Embed Token示例 ──────────────────────────────────────────────────────
def create_embed_tokens(token, dashboards):
    print("→ 创建嵌入Token示例...")
    for db in dashboards[:2]:
        r = requests.post(f"{API_BASE}/embed/tokens",
                          headers={"Authorization": f"Bearer {token}"},
                          json={
                              "label": f"{db['title']} - 演示Token",
                              "resource_type": "dashboard",
                              "resource_id": db["id"],
                              "expires_days": 30,
                          })
        if r.status_code == 200:
            t = r.json()["token"]
            print(f"  ✓ Token: {t[:16]}... → {db['title']}")
            print(f"    嵌入URL: http://localhost:16006/embed/{t}")
        else:
            print(f"  ✗ 失败: {r.json()}")

# ── 主流程 ───────────────────────────────────────────────────────────────────
def main():
    print("=" * 60)
    print("Smart BI 功能演示数据初始化")
    print("=" * 60)

    print("\n[1/5] 登录...")
    token = login()
    print("  ✓ 登录成功")

    # 获取datasource ID
    r = requests.get(f"{API_BASE}/datasources", headers={"Authorization": f"Bearer {token}"})
    datasources = r.json()
    if not datasources:
        print("  ✗ 未找到数据源，请先配置数据源")
        return
    ds_id = datasources[0]["id"]
    print(f"  使用数据源: {datasources[0]['name']} (id={ds_id})")

    print("\n[2/5] 创建业务数据表...")
    setup_tables(token, ds_id)
    print("  ✓ 业务数据表就绪")

    print("\n[3/5] 创建演示图表...")
    chart_ids = create_charts(token, ds_id)
    print(f"  ✓ 共创建 {len(chart_ids)} 个图表")

    print("\n[4/5] 创建演示看板...")
    dashboards = create_dashboards(token, chart_ids)
    print(f"  ✓ 共创建 {len(dashboards)} 个看板")

    print("\n[5/5] 创建嵌入Token...")
    create_embed_tokens(token, dashboards)

    print("\n" + "=" * 60)
    print("✅ 初始化完成！三个功能的使用路径：")
    print("=" * 60)
    print("""
【1】预测分析（时序预测）
  ① 进入「看板中心」→「销售分析看板」→「编辑」
  ② 或直接点「新建图表」→ 数据查询 → 写SQL后点「预览」
  ③ 预览 Tab 上方出现「预测分析」按钮 → 点击打开
  ④ 设置预测周期（默认6），点「运行预测」

【2】自然语言生成报告
  ① 进入「看板中心」→「产品运营看板」→「编辑」
  ② 在左侧图表库中，任意图表右侧有✨按钮 → 点击
  ③ 或新建图表预览后，Preview Tab 上「AI分析报告」按钮
  ④ 点「生成报告」等待LLM返回Markdown报告

【3】嵌入式 BI / Embed SDK
  ① 进入「看板中心」→ 任意看板 → 点「分享」
  ② 切换到「嵌入SDK」Tab
  ③ 输入Token名称 → 点「生成Token」
  ④ 点「复制代码」获取嵌入代码片段
  ⑤ 直接访问: http://localhost:16006/embed/<token>
  ⑥ 已预创建的Token在上方日志中
""")

if __name__ == "__main__":
    main()
