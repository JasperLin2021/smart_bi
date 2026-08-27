-- =====================================================================
-- Smart BI 跨境电商演示数据（组织：跨海优选 / crossborder）
-- ---------------------------------------------------------------------
-- 适用数据库: PostgreSQL 16+
-- 导入方式:   psql -h <host> -U <user> -d <db> -f demo_data_crossborder.sql
--             (或 pgAdmin 查询工具直接执行)
--
-- 内容概览:
--   01. 业务数据层  - 10 张跨境电商业务表(cb_* 前缀) + 2024-01~2025-12 拟真数据
--   02. RBAC 基础   - 组织/部门/用户/角色（演示账号可直接登录）
--   03. 资产生产    - 数据源/数据集(含刷新日志)/可信指标(含认证/血缘/质量)
--   04. 分析可视化  - 查询历史/固定图表/看板(含评论)/自助分析视图/大屏/嵌入Token
--   05. 运营闭环    - 告警/预警历史/行动项/定时报告/复杂报表/数据流水线/数据目录
--   06. 治理安全    - RLS/审计/访问申请/Webhook/外部集成/消息投递/数据连接/AI报告/Agent
--
-- 说明:
--   * 全部语句位于单个事务内，重复执行安全（ON CONFLICT 幂等）。
--   * 不触碰已有业务记录（orgs id=1-2、datasources id=1-5、metrics id=1-13、
--     dashboards id=1-4、catalog_categories id=1-4、data_assets id=1-23 等）。
--   * 新组织数据统一使用 id>=100 段，与存量数据完全隔离。
--   * 业务表与平台应用同库，数据源 database_url 指向应用库；如部署环境不同，
--     请按实际连接串修改 demo_data_crossborder.sql 中第 4 节 datasources 的 URL。
--   * 演示账号密码见第 2 节注释。
-- =====================================================================

BEGIN;

-- =====================================================================
-- 01. 业务数据层
-- =====================================================================

-- 01.1 店铺/站点维度
CREATE TABLE IF NOT EXISTS cb_shops (
    shop_id     SERIAL PRIMARY KEY,
    shop_name   VARCHAR(128) NOT NULL,
    platform    VARCHAR(32)  NOT NULL,   -- amazon / shopee / tiktok / d2c(独立站)
    site        VARCHAR(32)  NOT NULL,   -- us / de / uk / jp / sg / th
    currency    VARCHAR(8)   NOT NULL,
    open_date   DATE
);

-- 01.2 商品 SKU 维度
CREATE TABLE IF NOT EXISTS cb_products (
    sku          VARCHAR(32) PRIMARY KEY,
    product_name VARCHAR(256) NOT NULL,
    category     VARCHAR(64)  NOT NULL,
    listing_price NUMERIC(10,2) NOT NULL,
    cost         NUMERIC(10,2) NOT NULL,
    weight_kg    NUMERIC(8,2)  DEFAULT 0,
    is_active    INTEGER      DEFAULT 1
);

-- 01.3 客户维度
CREATE TABLE IF NOT EXISTS cb_customers (
    customer_id      VARCHAR(32) PRIMARY KEY,
    customer_name    VARCHAR(128) NOT NULL,
    country          VARCHAR(64)  NOT NULL,
    channel          VARCHAR(32),        -- direct / ads / organic / marketplace
    tier             VARCHAR(16)  DEFAULT 'C',
    first_order_date DATE,
    total_orders     INTEGER      DEFAULT 0,
    total_amount     NUMERIC(12,2) DEFAULT 0
);

-- 01.4 订单事实表
CREATE TABLE IF NOT EXISTS cb_orders (
    order_id        VARCHAR(64) PRIMARY KEY,
    order_date      DATE NOT NULL,
    platform        VARCHAR(32) NOT NULL,
    site            VARCHAR(32) NOT NULL,
    shop_id         INTEGER,
    customer_id     VARCHAR(32),
    product_sku     VARCHAR(32),
    quantity        INTEGER     DEFAULT 1,
    unit_price      NUMERIC(10,2) NOT NULL,
    amount          NUMERIC(12,2) NOT NULL,
    currency        VARCHAR(8),
    order_status    VARCHAR(32) DEFAULT 'completed',  -- completed/refunded/cancelled
    payment_method  VARCHAR(32),
    shipping_country VARCHAR(64),
    refund_flag     INTEGER     DEFAULT 0
);

-- 01.5 订单明细表
CREATE TABLE IF NOT EXISTS cb_order_items (
    order_item_id  VARCHAR(64) PRIMARY KEY,
    order_id       VARCHAR(64) NOT NULL,
    product_sku    VARCHAR(32),
    quantity       INTEGER DEFAULT 1,
    unit_price     NUMERIC(10,2) NOT NULL,
    subtotal       NUMERIC(12,2) NOT NULL
);

-- 01.6 跨境物流表
CREATE TABLE IF NOT EXISTS cb_logistics (
    logistics_id   VARCHAR(64) PRIMARY KEY,
    order_id       VARCHAR(64) NOT NULL,
    carrier        VARCHAR(64),
    ship_date      DATE,
    delivery_date  DATE,
    status         VARCHAR(32) DEFAULT 'delivered',  -- delivered / in_transit / exception
    shipping_cost  NUMERIC(10,2) DEFAULT 0,
    tracking_no    VARCHAR(64)
);

-- 01.7 支付流水表
CREATE TABLE IF NOT EXISTS cb_payments (
    payment_id     VARCHAR(64) PRIMARY KEY,
    order_id       VARCHAR(64) NOT NULL,
    payment_method VARCHAR(32),
    amount         NUMERIC(12,2) NOT NULL,
    currency       VARCHAR(8),
    status         VARCHAR(32) DEFAULT 'succeeded',  -- succeeded / pending / refunded / failed
    paid_at        DATE
);

-- 01.8 会员表
CREATE TABLE IF NOT EXISTS cb_members (
    member_id        VARCHAR(32) PRIMARY KEY,
    customer_id      VARCHAR(32),
    membership_level VARCHAR(16) DEFAULT 'silver',   -- bronze/silver/gold/platinum
    points           INTEGER DEFAULT 0,
    join_date        DATE,
    last_active_date DATE,
    total_spent      NUMERIC(12,2) DEFAULT 0
);

-- 01.9 月度 KPI 汇总表
CREATE TABLE IF NOT EXISTS cb_monthly_kpi (
    kpi_id         SERIAL PRIMARY KEY,
    stat_month     VARCHAR(7) NOT NULL,   -- 'YYYY-MM'
    platform       VARCHAR(32) NOT NULL,
    site           VARCHAR(32) NOT NULL,
    gmv            NUMERIC(14,2) DEFAULT 0,
    orders         INTEGER DEFAULT 0,
    refund_amount  NUMERIC(12,2) DEFAULT 0,
    ad_spend       NUMERIC(12,2) DEFAULT 0,
    new_customers  INTEGER DEFAULT 0,
    active_members INTEGER DEFAULT 0,
    roi            NUMERIC(8,2) DEFAULT 0,
    CONSTRAINT uq_cb_monthly_kpi UNIQUE (stat_month, platform, site)
);

-- 01.10 广告投放明细表
CREATE TABLE IF NOT EXISTS cb_ad_spend (
    ad_id      VARCHAR(64) PRIMARY KEY,
    ad_date    DATE NOT NULL,
    platform   VARCHAR(32) NOT NULL,
    site       VARCHAR(32) NOT NULL,
    campaign   VARCHAR(128),
    spend      NUMERIC(10,2) DEFAULT 0,
    impressions INTEGER DEFAULT 0,
    clicks     INTEGER DEFAULT 0,
    conversions INTEGER DEFAULT 0,
    orders     INTEGER DEFAULT 0
);

-- 01.11 店铺数据（6 个店铺/站点）
INSERT INTO cb_shops (shop_id, shop_name, platform, site, currency, open_date)
VALUES
  (1, '跨海优选 Amazon 美国站', 'amazon', 'us', 'USD', DATE '2021-03-15'),
  (2, '跨海优选 Amazon 德国站', 'amazon', 'de', 'EUR', DATE '2021-09-01'),
  (3, '跨海优选 Amazon 英国站', 'amazon', 'uk', 'GBP', DATE '2022-01-20'),
  (4, '跨海优选 Amazon 日本站', 'amazon', 'jp', 'JPY', DATE '2022-06-10'),
  (5, '跨海优选 Shopee 东南亚站', 'shopee', 'sg', 'SGD', DATE '2023-02-14'),
  (6, '跨海优选 TikTok 美国站', 'tiktok', 'us', 'USD', DATE '2023-11-01'),
  (7, '跨海优选 独立站', 'd2c', 'us', 'USD', DATE '2024-01-08')
ON CONFLICT (shop_id) DO NOTHING;

-- 01.12 商品 SKU（20 个，覆盖 5 大品类）
INSERT INTO cb_products (sku, product_name, category, listing_price, cost, weight_kg, is_active)
VALUES
  ('SKU01', '便携式榨汁杯 500ml',   '厨房电器', 29.99, 11.20, 0.85, 1),
  ('SKU02', '无线蓝牙耳机 Pro',     '3C数码',   59.99, 24.80, 0.32, 1),
  ('SKU03', '智能手表 S2',          '3C数码',   89.99, 41.50, 0.28, 1),
  ('SKU04', 'LED化妆镜 带灯',       '美妆个护', 24.99,  9.60, 0.60, 1),
  ('SKU05', '瑜伽垫加厚防滑',       '运动户外', 19.99,  7.40, 1.10, 1),
  ('SKU06', '车载手机支架',         '汽车用品', 14.99,  5.20, 0.22, 1),
  ('SKU07', '记忆棉旅行枕',         '居家生活', 22.99,  8.90, 0.45, 1),
  ('SKU08', '便携咖啡机手冲套装',   '厨房电器', 34.99, 15.30, 1.20, 1),
  ('SKU09', '宠物自动喂食器',       '宠物用品', 49.99, 22.10, 1.05, 1),
  ('SKU10', '儿童益智积木 200pcs',  '母婴玩具', 32.99, 13.80, 0.95, 1),
  ('SKU11', '保温杯 大容量 1L',     '居家生活', 18.99,  6.90, 0.40, 1),
  ('SKU12', '无线充电宝 20000mAh',  '3C数码',   39.99, 17.60, 0.50, 1),
  ('SKU13', '电动牙刷 声波款',      '美妆个护', 27.99, 12.40, 0.35, 1),
  ('SKU14', '折叠收纳箱 3件套',     '居家生活', 26.99, 10.70, 2.10, 1),
  ('SKU15', '跑步运动腰包',         '运动户外', 13.99,  4.80, 0.18, 1),
  ('SKU16', '智能体脂秤',           '运动户外', 29.99, 12.90, 1.30, 1),
  ('SKU17', '香薰加湿器 静音',      '居家生活', 21.99,  8.20, 0.55, 1),
  ('SKU18', '车载吸尘器 无线',      '汽车用品', 44.99, 20.30, 0.80, 1),
  ('SKU19', '猫咪玩具 逗猫棒套装',  '宠物用品', 12.99,  4.10, 0.15, 1),
  ('SKU20', '数码相机收纳包',       '3C数码',   23.99,  9.50, 0.38, 1)
ON CONFLICT (sku) DO NOTHING;

-- 01.13 客户数据（200 个，国家与平台站点对应）
INSERT INTO cb_customers (customer_id, customer_name, country, channel, tier, first_order_date, total_orders, total_amount)
SELECT
  'C' || LPAD(g::text, 3, '0'),
  'Customer_' || LPAD(g::text, 3, '0'),
  (ARRAY['US','US','US','DE','DE','UK','JP','JP','SG','TH','US','CA','FR','IT','AU'])[1 + mod(g * 7, 15)],
  (ARRAY['direct','ads','organic','marketplace'])[1 + mod(g * 13, 4)],
  (ARRAY['A','B','C'])[1 + mod(g * 3, 3)],
  DATE '2023-06-01' + (mod(g * 137, 700)) * INTERVAL '1 day',
  1 + mod(g * 5, 25),
  (20 + mod(g * 11, 800)) * 10.00
FROM generate_series(1, 200) AS g
ON CONFLICT (customer_id) DO NOTHING;

-- 01.14 订单事实表（2024-01-01 ~ 2025-12-30，共 12000 单，确定性伪随机可复现）
INSERT INTO cb_orders
  (order_id, order_date, platform, site, shop_id, customer_id, product_sku, quantity,
   unit_price, amount, currency, order_status, payment_method, shipping_country, refund_flag)
SELECT
  'CB' || LPAD(g::text, 6, '0'),
  DATE '2024-01-01' + (g % 730) * INTERVAL '1 day',
  (ARRAY['amazon','amazon','amazon','amazon','shopee','tiktok','d2c'])[1 + mod(g * 5, 7)],
  (ARRAY['us','de','uk','jp','sg','us','us'])[1 + mod(g * 5, 7)],
  1 + mod(g * 5, 7),
  'C' || LPAD((1 + mod(g * 3, 200))::text, 3, '0'),
  p.sku,
  1 + mod(g * 7, 3),
  p.listing_price,
  p.listing_price * (1 + mod(g * 7, 3)),
  (ARRAY['USD','EUR','GBP','JPY','SGD','USD','USD'])[1 + mod(g * 5, 7)],
  CASE WHEN g % 20 = 0 THEN 'refunded'
       WHEN g % 30 = 5 THEN 'cancelled'
       ELSE 'completed' END,
  (ARRAY['credit_card','paypal','apple_pay','cod'])[1 + mod(g * 11, 4)],
  (ARRAY['US','DE','UK','JP','SG','TH'])[1 + mod(g * 5, 6)],
  CASE WHEN g % 20 = 0 THEN 1 ELSE 0 END
FROM generate_series(1, 12000) AS g
JOIN cb_products p ON p.sku = 'SKU' || LPAD((1 + mod(g * 9, 20))::text, 2, '0')
ON CONFLICT (order_id) DO NOTHING;

-- 01.15 订单明细（与订单 1:1，简化：每单一个 SKU）
INSERT INTO cb_order_items
  (order_item_id, order_id, product_sku, quantity, unit_price, subtotal)
SELECT
  'OI' || order_id,
  order_id,
  product_sku,
  quantity,
  unit_price,
  amount
FROM cb_orders
ON CONFLICT (order_item_id) DO NOTHING;

-- 01.16 跨境物流（每单一条，含时效数据用于物流监控）
INSERT INTO cb_logistics
  (logistics_id, order_id, carrier, ship_date, delivery_date, status, shipping_cost, tracking_no)
SELECT
  'LG' || order_id,
  order_id,
  (ARRAY['DHL','FedEx','UPS','USPS','4PX','YunExpress'])[1 + mod(substr(order_id,3)::int * 17, 6)],
  order_date + 1,
  order_date + 4 + mod(substr(order_id,3)::int * 7, 10),
  CASE WHEN order_status = 'refunded' THEN 'exception'
       WHEN order_date + 4 + mod(substr(order_id,3)::int * 7, 10) > CURRENT_DATE THEN 'in_transit'
       ELSE 'delivered' END,
  8.5 + mod(substr(order_id,3)::int * 3, 40),
  'TRK' || order_id
FROM cb_orders
ON CONFLICT (logistics_id) DO NOTHING;

-- 01.17 支付流水（每单一条）
INSERT INTO cb_payments
  (payment_id, order_id, payment_method, amount, currency, status, paid_at)
SELECT
  'PAY' || order_id,
  order_id,
  payment_method,
  amount,
  currency,
  CASE WHEN order_status = 'refunded' THEN 'refunded'
       WHEN g0 = 1 THEN 'failed'
       ELSE 'succeeded' END,
  order_date
FROM (
  SELECT o.*, mod(substr(o.order_id,3)::int * 5, 100) AS g0
  FROM cb_orders o
) t
ON CONFLICT (payment_id) DO NOTHING;

-- 01.18 会员数据（200 客户中 150 位注册会员）
INSERT INTO cb_members
  (member_id, customer_id, membership_level, points, join_date, last_active_date, total_spent)
SELECT
  'MB' || LPAD(g::text, 3, '0'),
  'C' || LPAD(g::text, 3, '0'),
  (ARRAY['silver','gold','gold','platinum','bronze'])[1 + mod(g * 7, 5)],
  mod(g * 977, 12000),
  DATE '2023-01-15' + (mod(g * 131, 900)) * INTERVAL '1 day',
  CURRENT_DATE - mod(g * 19, 60) * INTERVAL '1 day',
  (50 + mod(g * 23, 3000)) * 10.00
FROM generate_series(1, 150) AS g
ON CONFLICT (member_id) DO NOTHING;

-- 01.19 月度 KPI（24 个月 × 7 个平台站点，含旺季季节因子）
INSERT INTO cb_monthly_kpi
  (stat_month, platform, site, gmv, orders, refund_amount, ad_spend, new_customers, active_members, roi)
SELECT
  TO_CHAR(DATE '2024-01-01' + (m - 1) * INTERVAL '1 month', 'YYYY-MM'),
  (ARRAY['amazon','amazon','amazon','amazon','shopee','tiktok','d2c'])[1 + mod(m * 3, 7)],
  (ARRAY['us','de','uk','jp','sg','us','us'])[1 + mod(m * 3, 7)],
  round((30000 + mod(m * 7919, 40000)) * CASE WHEN mod(m, 12) IN (10, 11) THEN 2.1 ELSE 1.0 END, 2),
  500 + mod(m * 97, 900),
  1200 + mod(m * 131, 2600),
  5000 + mod(m * 911, 8000),
  80 + mod(m * 17, 300),
  900 + mod(m * 29, 2500),
  round(3.0 + mod(m * 53, 200) / 100.0, 2)
FROM generate_series(1, 24) AS m
ON CONFLICT (stat_month, platform, site) DO NOTHING;

-- 01.20 广告投放明细（2024-01-01 起每日每平台一条，730 天 × 5 平台 = 3650 条）
INSERT INTO cb_ad_spend
  (ad_id, ad_date, platform, site, campaign, spend, impressions, clicks, conversions, orders)
SELECT
  'AD' || LPAD(g::text, 6, '0'),
  DATE '2024-01-01' + g * INTERVAL '1 day',
  (ARRAY['amazon','amazon','shopee','tiktok','d2c'])[1 + mod(g * 7, 5)],
  (ARRAY['us','de','sg','us','us'])[1 + mod(g * 7, 5)],
  (ARRAY['品牌词','竞品词','品类词','新品推广','大促引流'])[1 + mod(g * 11, 5)],
  round(80 + mod(g * 733, 420), 2),
  8000 + mod(g * 103, 40000),
  120 + mod(g * 37, 1500),
  2 + mod(g * 53, 60),
  1 + mod(g * 29, 35)
FROM generate_series(1, 730) AS g
ON CONFLICT (ad_id) DO NOTHING;

-- 02.1 组织（id=1 nexteer / id=2 carsem 为存量，新组织从 id=3 开始）
INSERT INTO organizations (id, name, slug)
VALUES (3, '跨海优选', 'crossborder')
ON CONFLICT (id) DO NOTHING;

-- 02.2 部门（6 个一级部门）
INSERT INTO departments (id, name, org_id, parent_id, sort_order)
VALUES
  (100, '总经理办公室', 3, NULL, 1),
  (101, '跨境电商运营部', 3, NULL, 2),
  (102, '海外销售部', 3, NULL, 3),
  (103, '供应链与物流部', 3, NULL, 4),
  (104, '数据分析部', 3, NULL, 5),
  (105, '财务部', 3, NULL, 6),
  (106, '客服部', 3, 101, 7),
  (107, '仓储部', 3, 103, 8)
ON CONFLICT (id) DO NOTHING;

-- 02.3 用户（演示账号；密码见注释，登录名即 username）
-- 账号: cb_admin/Cb@2026Admin(超管) cb_certifier/Cb@2026Admin(指标认证)
--       cb_analyst/Cb@2026User(分析师) cb_seller/Cb@2026Seller(运营) cb_viewer/Cb@2026Viewer(只读)
INSERT INTO users
  (id, username, hashed_password, role, org_id, department_id, department,
   data_scope, permission_override_enabled, menu_permissions, action_permissions)
VALUES
  (100, 'cb_admin', '$2b$12$5lO6kKsgmcvXhheolF4uTuQoP25FT4ThufVcPufglwIuKQMuYMMBu', 'super_admin', 3, 100, '总经理办公室', 'all', TRUE,
   '{"dashboard":true,"chat":true,"catalog":true,"admin":true}',
   '{"dashboard:create":true,"dashboard:edit":true,"dashboard:delete":true,"chat:ask":true,"chat:pin":true,"catalog:manage":true,"data:manage":true,"user:manage":true,"role:manage":true,"alert:manage":true,"report:manage":true,"pipeline:manage":true}'),
  (101, 'cb_certifier', '$2b$12$5lO6kKsgmcvXhheolF4uTuQoP25FT4ThufVcPufglwIuKQMuYMMBu', 'org_admin', 3, 104, '数据分析部', 'org', FALSE,
   '{"dashboard":true,"chat":true,"catalog":true}',
   '{"dashboard:create":true,"dashboard:edit":true,"chat:ask":true,"chat:pin":true,"catalog:manage":true,"metric:certify":true,"data:manage":true}'),
  (102, 'cb_analyst', '$2b$12$4A5PMieL5OE6GneWjlkR9ed58WwIrEenK4WSnkVxZImi6azIeRcla', 'user', 3, 104, '数据分析部', 'dept', FALSE,
   '{"dashboard":true,"chat":true,"catalog":true}',
   '{"dashboard:create":true,"dashboard:edit":true,"chat:ask":true,"chat:pin":true,"catalog:view":true,"alert:create":true,"report:create":true}'),
  (103, 'cb_seller', '$2b$12$hF4EYp.ospBlYAquTt98feiRZCbPg7MJKNU4JMbbCji6JL2Ujw//K', 'user', 3, 101, '跨境电商运营部', 'dept', FALSE,
   '{"dashboard":true,"chat":true,"catalog":true}',
   '{"dashboard:view":true,"chat:ask":true,"catalog:view":true,"alert:view":true}'),
  (104, 'cb_viewer', '$2b$12$Lle.n5oCS7Qxo8jZMqnIneXhtv.ciBwQQM4dj0Z8a9H3DCh2kPFjG', 'user', 3, 105, '财务部', 'self', FALSE,
   '{"dashboard":true,"chat":true}',
   '{"dashboard:view":true,"chat:ask":true,"catalog:view":true}')
ON CONFLICT (id) DO NOTHING;

-- 02.4 角色（组织级自定义角色，code+org_id 唯一）
INSERT INTO roles
  (id, code, name, description, org_id, is_builtin, data_scope, menu_permissions, action_permissions)
VALUES
  (100, 'crossborder_admin',  '组织管理员', '跨海优选组织管理员，拥有全部管理权限', 3, FALSE, 'all',
   '[{"title":"经营总览","key":"dashboard","children":[]},{"title":"智能问数","key":"chat","children":[]},{"title":"数据目录","key":"catalog","children":[]},{"title":"系统管理","key":"admin","children":[]}]',
   '["*"]'),
  (101, 'crossborder_analyst','数据分析师', '数据分析与看板制作', 3, FALSE, 'org',
   '[{"title":"经营总览","key":"dashboard","children":[]},{"title":"智能问数","key":"chat","children":[]},{"title":"数据目录","key":"catalog","children":[]}]',
   '["dashboard:create","dashboard:edit","chat:ask","chat:pin","catalog:view","alert:create"]'),
  (102, 'crossborder_seller', '店铺运营', '负责各平台店铺日常运营', 3, FALSE, 'dept',
   '[{"title":"经营总览","key":"dashboard","children":[]},{"title":"智能问数","key":"chat","children":[]}]',
   '["dashboard:view","chat:ask"]'),
  (103, 'crossborder_viewer', '只读访客', '仅可查看已授权内容', 3, FALSE, 'self',
   '[{"title":"智能问数","key":"chat","children":[]}]',
   '["dashboard:view"]')
ON CONFLICT (code, org_id) DO NOTHING;

-- 03.1 数据源（id=6 起新增；database_url 指向应用库，按部署环境调整）
-- PostgreSQL 连接串默认: postgresql+psycopg2://bi_user:bi_password@localhost:5432/smart_bi
INSERT INTO datasources
  (id, name, slug, database_url, source_type, metadata_prompt, schema_metadata,
   drill_config, metrics_prompt, text2sql_prompt, recommend_questions, is_active, org_id)
VALUES
  (6, '跨海优选-电商主库', 'crossborder-db',
   'postgresql+psycopg2://bi_user:bi_password@localhost:5432/smart_bi',
   'database',
   '这是跨境电商企业"跨海优选"的业务数据库，包含店铺(cb_shops)、商品(cb_products)、客户(cb_customers)、订单(cb_orders)、订单明细(cb_order_items)、物流(cb_logistics)、支付(cb_payments)、会员(cb_members)、月度KPI(cb_monthly_kpi)、广告投放(cb_ad_spend)共10张表。货币字段含USD/EUR/GBP/JPY/SGD等，查询金额类指标时注意按平台站点过滤。',
   '{"tables":[{"name":"cb_orders","comment":"订单事实表，含金额/状态/退款标记/支付方式/收货国家"},{"name":"cb_order_items","comment":"订单明细，每单一条SKU"},{"name":"cb_products","comment":"商品SKU，含成本与挂牌价"},{"name":"cb_customers","comment":"客户维度，含国家/渠道/等级"},{"name":"cb_shops","comment":"店铺维度，含平台/站点/币种"},{"name":"cb_logistics","comment":"物流时效，含承运商/发货/妥投日期"},{"name":"cb_payments","comment":"支付流水，含支付方式/状态"},{"name":"cb_members","comment":"会员，含等级/积分/消费"},{"name":"cb_monthly_kpi","comment":"月度汇总KPI，含GMV/退款/广告/ROI"},{"name":"cb_ad_spend","comment":"广告投放日明细，含花费/曝光/点击/转化"}],"relationships":[{"from_table":"cb_orders","from_column":"product_sku","to_table":"cb_products","to_column":"sku"},{"from_table":"cb_orders","from_column":"customer_id","to_table":"cb_customers","to_column":"customer_id"},{"from_table":"cb_orders","from_column":"shop_id","to_table":"cb_shops","to_column":"shop_id"},{"from_table":"cb_order_items","from_column":"order_id","to_table":"cb_orders","to_column":"order_id"},{"from_table":"cb_logistics","from_column":"order_id","to_table":"cb_orders","to_column":"order_id"}]}',
   '{"dimensions":[{"id":"cb_shops.platform","table":"cb_shops","column":"platform","label":"平台","kind":"string"},{"id":"cb_shops.site","table":"cb_shops","column":"site","label":"站点","kind":"string"},{"id":"cb_products.category","table":"cb_products","column":"category","label":"品类","kind":"string"},{"id":"cb_products.product","table":"cb_products","column":"product","label":"商品","kind":"string"},{"id":"cb_customers.country","table":"cb_customers","column":"country","label":"国家","kind":"string"},{"id":"cb_customers.channel","table":"cb_customers","column":"channel","label":"渠道","kind":"string"},{"id":"cb_customers.tier","table":"cb_customers","column":"tier","label":"等级","kind":"string"},{"id":"cb_orders.order_date","table":"cb_orders","column":"order_date","label":"月份","kind":"date"}],"metrics":[{"id":"cb_orders.amount","table":"cb_orders","column":"amount","label":"GMV","aggregation":"sum"},{"id":"cb_orders.id","table":"cb_orders","column":"id","label":"订单量","aggregation":"count"},{"id":"cb_orders.amount","table":"cb_orders","column":"amount","label":"退款率","aggregation":"custom"},{"id":"cb_orders.amount","table":"cb_orders","column":"amount","label":"ROI","aggregation":"custom"},{"id":"cb_ad_spend.spend","table":"cb_ad_spend","column":"spend","label":"广告花费","aggregation":"sum"},{"id":"cb_orders.amount","table":"cb_orders","column":"amount","label":"客单价","aggregation":"custom"},{"id":"cb_members.total_spend","table":"cb_members","column":"total_spend","label":"LTV","aggregation":"custom"}],"paths":[{"id":"path_platform_site","source_dimension_id":"cb_shops.platform","target_dimension_id":"cb_shops.site","label":"平台→站点","action":"drill_down"},{"id":"path_site_category","source_dimension_id":"cb_shops.site","target_dimension_id":"cb_products.category","label":"站点→品类","action":"drill_down"},{"id":"path_category_product","source_dimension_id":"cb_products.category","target_dimension_id":"cb_products.product","label":"品类→商品","action":"drill_down"},{"id":"path_country_channel","source_dimension_id":"cb_customers.country","target_dimension_id":"cb_customers.channel","label":"国家→渠道","action":"drill_down"},{"id":"path_channel_tier","source_dimension_id":"cb_customers.channel","target_dimension_id":"cb_customers.tier","label":"渠道→等级","action":"drill_down"}]}',
   '可用指标：GMV(总销售额)、订单量、退款率、客单价AOV、广告ROI、广告花费、新客数、活跃会员数、物流妥投时效。常用维度：平台(amazon/shopee/tiktok/d2c)、站点(us/de/uk/jp/sg)、品类、月份。',
   '生成SQL时遵守：1)金额按币种分组时使用currency字段；2)退款率=退款订单金额/总金额；3)按月份比较时使用order_date的YYYY-MM；4)广告ROI=当月GMV/当月广告花费；5)涉及成本利润时用cb_products的cost与listing_price。',
   '["各平台本月销售额是多少？","德国站近三个月退款率趋势如何？","哪个品类客单价最高？","美国站广告ROI环比变化","Top10热销SKU有哪些？","各店铺月度GMV对比"]',
   1, 3)
ON CONFLICT (id) DO NOTHING;

-- 03.2 数据集（4 个：订单明细/商品分析/月度KPI/广告分析，含语义模型与钻取配置）
INSERT INTO datasets
  (id, name, description, datasource_id, fields_json, filters_json, derived_columns_json,
   joins_json, aggregations_json, pipeline_json, semantic_model_json, drill_config_json,
   status, visibility, last_refresh_status, last_refresh_at, last_refresh_row_count,
   materialization_status, materialization_mode, materialized_table_name, materialized_at,
   incremental_key, incremental_watermark, materialization_message, org_id, owner_id)
VALUES
  (100, '跨境电商订单分析', '订单/明细/客户/商品多表关联分析，支持平台站点品类钻取', 6,
   '{"fields":[{"name":"order_date","type":"date","label":"下单日期"},{"name":"platform","type":"string","label":"平台"},{"name":"site","type":"string","label":"站点"},{"name":"product_sku","type":"string","label":"SKU"},{"name":"category","type":"string","label":"品类"},{"name":"amount","type":"numeric","label":"销售额"},{"name":"quantity","type":"int","label":"数量"},{"name":"refund_flag","type":"int","label":"是否退款"},{"name":"country","type":"string","label":"国家"}]}',
   '{"logic":"AND","rules":[{"field":"order_status","op":"=","value":"completed"},{"field":"order_date","op":">=","value":"2024-01-01"}]}',
   '{"columns":[{"name":"month","expr":"to_char(order_date, ''YYYY-MM'')","type":"string","label":"月份"},{"name":"gmv","expr":"amount * (1 - refund_flag)","type":"numeric","label":"有效销售额"},{"name":"aov","expr":"amount / quantity","type":"numeric","label":"客单价"}]}',
   '{"joins":[{"type":"left","table":"cb_products","on":"cb_orders.product_sku = cb_products.sku"},{"type":"left","table":"cb_customers","on":"cb_orders.customer_id = cb_customers.customer_id"},{"type":"left","table":"cb_shops","on":"cb_orders.shop_id = cb_shops.shop_id"}]}',
   '{"measures":[{"name":"sum_amount","func":"sum","column":"amount"},{"name":"count_orders","func":"count","column":"order_id"},{"name":"avg_aov","func":"avg","column":"aov"},{"name":"refund_rate","func":"avg","column":"refund_flag"}]}',
   '{"steps":[{"type":"source","table":"cb_orders"},{"type":"join","config":"cb_products/cb_customers/cb_shops"},{"type":"derive","config":"month,gmv,aov"},{"type":"aggregate","config":"platform,site,month"}]}',
   '{"metrics":[{"name":"gmv","definition":"sum(amount*(1-refund_flag))","type":"sum"},{"name":"orders","definition":"count(order_id)","type":"count"},{"name":"aov","definition":"sum(amount)/count(order_id)","type":"ratio"},{"name":"refund_rate","definition":"sum(refund_flag)/count(order_id)","type":"ratio"}]}',
   '{"dims":["platform","site","category","country"],"metrics":["gmv","orders","aov","refund_rate"],"drill":["platform>site>category","country>channel"]}',
   'published', 'org', 'success', NOW() - INTERVAL '2 hours', 12000,
   'enabled', 'incremental', 'mart_order_daily', NOW() - INTERVAL '2 hours',
   'order_date', '2025-12-30', '每日增量物化，上次同步 12000 行', 3, 102),
  (101, '跨境电商月度KPI', 'GMV/退款/广告/ROI 月度汇总分析', 6,
   '{"fields":[{"name":"stat_month","type":"string","label":"月份"},{"name":"platform","type":"string","label":"平台"},{"name":"site","type":"string","label":"站点"},{"name":"gmv","type":"numeric","label":"GMV"},{"name":"orders","type":"int","label":"订单量"},{"name":"refund_amount","type":"numeric","label":"退款金额"},{"name":"ad_spend","type":"numeric","label":"广告花费"},{"name":"roi","type":"numeric","label":"ROI"},{"name":"new_customers","type":"int","label":"新客数"},{"name":"active_members","type":"int","label":"活跃会员"}]}',
   NULL, NULL, NULL,
   '{"measures":[{"name":"sum_gmv","func":"sum","column":"gmv"},{"name":"sum_orders","func":"sum","column":"orders"},{"name":"avg_roi","func":"avg","column":"roi"}]}',
   '{"steps":[{"type":"source","table":"cb_monthly_kpi"},{"type":"aggregate","config":"platform,site,stat_month"}]}',
   '{"metrics":[{"name":"gmv","definition":"sum(gmv)","type":"sum"},{"name":"orders","definition":"sum(orders)","type":"sum"},{"name":"roi","definition":"sum(gmv)/sum(ad_spend)","type":"ratio"},{"name":"refund_rate","definition":"sum(refund_amount)/sum(gmv)","type":"ratio"}]}',
   '{"dims":["stat_month","platform","site"],"metrics":["gmv","orders","roi","refund_rate"],"drill":["platform>site>month"]}',
   'published', 'org', 'success', NOW() - INTERVAL '1 day', 168,
   'enabled', 'full', 'mart_kpi_monthly', NOW() - INTERVAL '1 day',
   NULL, NULL, '月度全量物化', 3, 102),
  (102, '跨境电商广告分析', '广告投放明细与效果归因分析', 6,
   '{"fields":[{"name":"ad_date","type":"date","label":"投放日期"},{"name":"platform","type":"string","label":"平台"},{"name":"campaign","type":"string","label":"广告活动"},{"name":"spend","type":"numeric","label":"花费"},{"name":"impressions","type":"int","label":"曝光"},{"name":"clicks","type":"int","label":"点击"},{"name":"conversions","type":"int","label":"转化"},{"name":"orders","type":"int","label":"带来订单"}]}',
   NULL, '{"columns":[{"name":"ctr","expr":"clicks/impressions","type":"numeric","label":"点击率"},{"name":"cpc","expr":"spend/clicks","type":"numeric","label":"单次点击成本"},{"name":"cvr","expr":"conversions/clicks","type":"numeric","label":"转化率"}]}',
   NULL,
   '{"measures":[{"name":"sum_spend","func":"sum","column":"spend"},{"name":"sum_orders","func":"sum","column":"orders"},{"name":"avg_cpc","func":"avg","column":"cpc"}]}',
   '{"steps":[{"type":"source","table":"cb_ad_spend"},{"type":"derive","config":"ctr,cpc,cvr"},{"type":"aggregate","config":"platform,site,ad_date"}]}',
   '{"metrics":[{"name":"ad_spend","definition":"sum(spend)","type":"sum"},{"name":"orders","definition":"sum(orders)","type":"sum"},{"name":"ctr","definition":"sum(clicks)/sum(impressions)","type":"ratio"},{"name":"cpc","definition":"sum(spend)/sum(clicks)","type":"ratio"}]}',
   '{"dims":["ad_date","platform","campaign"],"metrics":["ad_spend","orders","ctr","cpc"],"drill":["platform>campaign>date"]}',
   'published', 'org', 'success', NOW() - INTERVAL '3 hours', 3650,
   'enabled', 'incremental', 'mart_ad_daily', NOW() - INTERVAL '3 hours',
   'ad_date', '2025-12-30', '日增量物化，上次同步 3650 行', 3, 102),
  (103, '跨境电商物流时效', '物流承运、妥投时效与异常监控分析', 6,
   '{"fields":[{"name":"order_id","type":"string","label":"订单号"},{"name":"carrier","type":"string","label":"承运商"},{"name":"ship_date","type":"date","label":"发货日期"},{"name":"delivery_date","type":"date","label":"妥投日期"},{"name":"status","type":"string","label":"物流状态"},{"name":"shipping_cost","type":"numeric","label":"运费"},{"name":"tracking_no","type":"string","label":"运单号"}]}',
   NULL, '{"columns":[{"name":"lead_time","expr":"delivery_date - ship_date","type":"int","label":"妥投时效(天)"},{"name":"country","expr":"(select shipping_country from cb_orders o where o.order_id = cb_logistics.order_id)","type":"string","label":"收货国家"}]}',
   '{"joins":[{"type":"left","table":"cb_orders","on":"cb_logistics.order_id = cb_orders.order_id"}]}',
   '{"measures":[{"name":"avg_lead_time","func":"avg","column":"lead_time"},{"name":"count_lg","func":"count","column":"logistics_id"},{"name":"count_exception","func":"count_if","column":"status=''exception''"}]}',
   '{"steps":[{"type":"source","table":"cb_logistics"},{"type":"join","config":"cb_orders"},{"type":"derive","config":"lead_time,country"},{"type":"aggregate","config":"carrier,status"}]}',
   '{"metrics":[{"name":"avg_lead_time","definition":"avg(delivery_date-ship_date)","type":"avg"},{"name":"exception_rate","definition":"count(status=''exception'')/count(*)","type":"ratio"}]}',
   '{"dims":["carrier","status","country"],"metrics":["avg_lead_time","exception_rate"],"drill":["carrier>country>month"]}',
   'published', 'org', 'success', NOW() - INTERVAL '4 hours', 12000,
   'enabled', 'incremental', 'mart_logistics_daily', NOW() - INTERVAL '4 hours',
   'ship_date', '2025-12-30', '日增量物化', 3, 102)
ON CONFLICT (id) DO NOTHING;

-- 03.3 数据集刷新日志
INSERT INTO dataset_refresh_logs (id, dataset_id, status, row_count, message, org_id, triggered_by_id, created_at)
VALUES
  (100, 100, 'success', 12000, '全量刷新成功，新增订单 12000 行', 3, 102, NOW() - INTERVAL '2 hours'),
  (101, 101, 'success', 168, '月度KPI全量刷新成功', 3, 102, NOW() - INTERVAL '1 day'),
  (102, 102, 'success', 3650, '广告明细增量刷新成功', 3, 102, NOW() - INTERVAL '3 hours'),
  (103, 103, 'success', 12000, '物流数据增量刷新成功', 3, 102, NOW() - INTERVAL '4 hours'),
  (104, 100, 'warning', 12000, '刷新完成，但检测到 3 笔订单币种异常', 3, 101, NOW() - INTERVAL '2 hours' - INTERVAL '1 day')
ON CONFLICT (id) DO NOTHING;

-- 03.4 可信指标（含认证、血缘、质量状态；name 全局唯一）
INSERT INTO metrics
  (id, dataset_id, datasource_id, name, description, definition, column_name, formula,
   calculation_config, owner_name, unit, aggregation, tags, status, dimensions,
   certification_status, certified_by, certified_at, caliber_version, last_value,
   last_computed_at, data_updated_at, quality_status, quality_message, is_active)
VALUES
  (100, 100, 6, 'GMV 总销售额', '已完成订单的有效销售额合计（扣除退款）',
   'sum(cb_orders.amount * (1 - cb_orders.refund_flag))', 'amount', 'sum(amount*(1-refund_flag))',
   '{"scope":"cb_orders","filters":[{"field":"order_status","op":"=","value":"completed"}]}',
   '王伟', 'USD', 'sum', '["核心","收入"]', 'published',
   '["platform","site","category","month","country"]',
   'certified', 'cb_certifier', NOW() - INTERVAL '30 days', 'v2', 3285000.00,
   NOW() - INTERVAL '2 hours', NOW() - INTERVAL '2 hours', 'healthy', '数据质量检查通过，完整率 99.8%', 1),
  (101, 100, 6, '订单量', '已完成订单的数量',
   'count(cb_orders.order_id) where order_status=''completed''', 'order_id', 'count(order_id)',
   '{"scope":"cb_orders","filters":[{"field":"order_status","op":"=","value":"completed"}]}',
   '王伟', '单', 'count', '["核心","销量"]', 'published',
   '["platform","site","month","category"]',
   'certified', 'cb_certifier', NOW() - INTERVAL '30 days', 'v1', 9600.00,
   NOW() - INTERVAL '2 hours', NOW() - INTERVAL '2 hours', 'healthy', '数据质量检查通过', 1),
  (102, 100, 6, '客单价 AOV', '每笔订单的平均成交金额',
   'sum(cb_orders.amount)/count(cb_orders.order_id)', 'amount', 'sum(amount)/count(order_id)',
   '{"scope":"cb_orders","filters":[{"field":"order_status","op":"=","value":"completed"}]}',
   '李婷', 'USD', 'avg', '["核心","效率"]', 'published',
   '["platform","site","category","month"]',
   'certified', 'cb_certifier', NOW() - INTERVAL '20 days', 'v1', 34.20,
   NOW() - INTERVAL '2 hours', NOW() - INTERVAL '2 hours', 'healthy', '口径：金额含税、扣退款', 1),
  (103, 100, 6, '退款率', '退款订单金额占总销售额比例',
   'sum(cb_orders.amount * cb_orders.refund_flag) / sum(cb_orders.amount)', 'refund_flag', 'sum(amount*refund_flag)/sum(amount)',
   '{"scope":"cb_orders"}', '李婷', '%', 'avg', '["售后","质量"]', 'published',
   '["platform","site","category","month"]',
   'certified', 'cb_certifier', NOW() - INTERVAL '20 days', 'v1', 3.2,
   NOW() - INTERVAL '2 hours', NOW() - INTERVAL '2 hours', 'healthy', '口径：退款金额占比', 1),
  (104, 102, 6, '广告花费', '各平台广告总花费',
   'sum(cb_ad_spend.spend)', 'spend', 'sum(spend)',
   '{"scope":"cb_ad_spend"}', '陈晨', 'USD', 'sum', '["营销","成本"]', 'published',
   '["platform","site","campaign","month"]',
   'certified', 'cb_certifier', NOW() - INTERVAL '15 days', 'v1', 185200.00,
   NOW() - INTERVAL '3 hours', NOW() - INTERVAL '3 hours', 'healthy', '口径：各渠道广告消耗', 1),
  (105, 102, 6, '广告 ROI', '广告投入产出比，GMV/广告花费',
   'sum(cb_monthly_kpi.gmv)/sum(cb_monthly_kpi.ad_spend)', 'roi', 'sum(gmv)/sum(ad_spend)',
   '{"scope":"cb_monthly_kpi"}', '陈晨', 'x', 'avg', '["营销","效率"]', 'published',
   '["platform","site","month"]',
   'certified', 'cb_certifier', NOW() - INTERVAL '15 days', 'v2', 4.35,
   NOW() - INTERVAL '1 day', NOW() - INTERVAL '1 day', 'healthy', '口径：月度GMV/月度广告花费', 1),
  (106, 101, 6, '新增客户数', '每月新增客户数量',
   'count(distinct cb_customers.customer_id)', 'customer_id', 'count(distinct customer_id)',
   '{"scope":"cb_customers"}', '赵敏', '人', 'count', '["增长","获客"]', 'published',
   '["platform","channel","month"]',
   'certified', 'cb_certifier', NOW() - INTERVAL '10 days', 'v1', 4200.00,
   NOW() - INTERVAL '1 day', NOW() - INTERVAL '1 day', 'healthy', '口径：按首单日期统计', 1),
  (107, 103, 6, '物流妥投时效', '订单从发货到妥投的平均天数',
   'avg(cb_logistics.delivery_date - cb_logistics.ship_date)', 'delivery_date', 'avg(delivery_date-ship_date)',
   '{"scope":"cb_logistics","filters":[{"field":"status","op":"=","value":"delivered"}]}',
   '刘洋', '天', 'avg', '["履约","时效"]', 'published',
   '["carrier","country","month"]',
   'certified', 'cb_certifier', NOW() - INTERVAL '10 days', 'v1', 8.5,
   NOW() - INTERVAL '4 hours', NOW() - INTERVAL '4 hours', 'healthy', '口径：妥投日期-发货日期', 1),
  (108, 103, 6, '物流异常率', '物流异常(拒收/退回)订单占比',
   'count(cb_logistics.logistics_id) filter (where status=''exception'')/count(*)', 'status', 'count(status=''exception'')/count(*)',
   '{"scope":"cb_logistics"}', '刘洋', '%', 'avg', '["履约","质量"]', 'published',
   '["carrier","country"]',
   'draft', NULL, NULL, 'v1', 2.1,
   NOW() - INTERVAL '4 hours', NOW() - INTERVAL '4 hours', 'warning', '该指标样本量偏小，建议复核口径', 1),
  (109, 100, 6, '退货率（待复核）', '近7天退款率，疑似数据波动异常',
   'sum(cb_orders.amount * cb_orders.refund_flag) / sum(cb_orders.amount)', 'refund_flag', NULL,
   '{"scope":"cb_orders","filters":[{"field":"order_date","op":">=","value":"now-7d"}]}',
   '孙强', '%', 'avg', '["测试","异常"]', 'draft',
   '["platform","site"]',
   'draft', NULL, NULL, 'v1', NULL,
   NULL, NULL, 'error', '最近7天退款率环比上升 45%，已触发数据质量告警，待业务复核', 1),
  (110, 101, 6, '会员活跃数', '近30天有消费或互动的活跃会员数量',
   'count(distinct cb_members.member_id)', 'member_id', 'count(distinct member_id)',
   '{"scope":"cb_members"}', '赵敏', '人', 'count', '["用户","运营"]', 'published',
   '["membership_level","month"]',
   'draft', NULL, NULL, 'v1', 86.00,
   NOW() - INTERVAL '1 day', NOW() - INTERVAL '1 day', 'unknown', NULL, 1)
ON CONFLICT (id) DO NOTHING;

-- 04.1 查询历史（智能问数对话记录，含SQL/结果/摘要/钻取上下文）
INSERT INTO query_history
  (id, user_id, datasource_id, parent_history_id, question, created_at, favorite,
   sql_query, result_json, summary, mode, drill_context, llm_model, is_insight, insight_title, org_id)
VALUES
  (100, 102, 6, NULL, '各平台本月销售额是多少？', NOW() - INTERVAL '3 hours', TRUE,
   'SELECT o.platform, SUM(o.amount * (1 - o.refund_flag)) AS gmv FROM cb_orders o WHERE to_char(o.order_date, ''YYYY-MM'') = to_char(CURRENT_DATE, ''YYYY-MM'') GROUP BY o.platform ORDER BY gmv DESC',
   '{"columns":["platform","gmv"],"rows":[["amazon",1320000],["tiktok",580000],["shopee",410000],["d2c",360000]]}',
   '本月各平台销售额：Amazon 132万居首，TikTok 58万次之，独立站 36万。',
   'ask', NULL, 'deepseek-v3', FALSE, NULL, 3),
  (101, 102, 6, 100, '按站点再细分看看', NOW() - INTERVAL '3 hours', FALSE,
   'SELECT o.site, SUM(o.amount * (1 - o.refund_flag)) AS gmv FROM cb_orders o WHERE to_char(o.order_date, ''YYYY-MM'') = to_char(CURRENT_DATE, ''YYYY-MM'') GROUP BY o.site ORDER BY gmv DESC',
   '{"columns":["site","gmv"],"rows":[["us",1280000],["de",460000],["uk",320000],["jp",290000]]}',
   '按站点细分：美国站销售额最高 128万，德国站 46万，英国站 32万。',
   'drill', '{"parent_id":100,"dimension":"platform→site"}', 'deepseek-v3', FALSE, NULL, 3),
  (102, 103, 6, NULL, '德国站近三个月退款率趋势', NOW() - INTERVAL '1 day', TRUE,
   'SELECT to_char(o.order_date, ''YYYY-MM'') AS month, SUM(o.amount*o.refund_flag)/SUM(o.amount) AS refund_rate FROM cb_orders o WHERE o.site=''de'' AND o.order_date >= CURRENT_DATE - INTERVAL ''3 months'' GROUP BY month ORDER BY month',
   '{"columns":["month","refund_rate"],"rows":[["2025-10",0.031],["2025-11",0.029],["2025-12",0.036]]}',
   '德国站退款率近三月在 2.9%~3.6% 区间，12月略升至 3.6%，需关注。',
   'ask', NULL, 'deepseek-v3', FALSE, NULL, 3),
  (103, 103, 6, NULL, '哪个品类客单价最高？', NOW() - INTERVAL '2 days', TRUE,
   'SELECT p.category, SUM(o.amount)/COUNT(o.order_id) AS aov FROM cb_orders o JOIN cb_products p ON o.product_sku=p.sku GROUP BY p.category ORDER BY aov DESC',
   '{"columns":["category","aov"],"rows":[["3C数码",52.4],["厨房电器",41.2],["汽车用品",38.6],["宠物用品",30.1],["母婴玩具",28.7]]}',
   '客单价最高的是 3C数码品类 52.4 美元，其次是厨房电器 41.2 美元。',
   'ask', NULL, 'deepseek-v3', FALSE, NULL, 3),
  (104, 102, 6, NULL, '美国站广告ROI环比变化', NOW() - INTERVAL '4 days', TRUE,
   'SELECT k.stat_month, SUM(k.gmv)/SUM(k.ad_spend) AS roi FROM cb_monthly_kpi k WHERE k.site=''us'' GROUP BY k.stat_month ORDER BY k.stat_month DESC LIMIT 6',
   '{"columns":["stat_month","roi"],"rows":[["2025-12",4.1],["2025-11",4.6],["2025-10",3.9],["2025-09",4.2],["2025-08",3.8]]}',
   '美国站广告ROI环比变化：11月达 4.6 峰值，12月回落至 4.1。',
   'ask', NULL, 'deepseek-v3', FALSE, NULL, 3),
  (105, 102, 6, NULL, 'Top10热销SKU是哪些？', NOW() - INTERVAL '5 days', TRUE,
   'SELECT p.product_name, COUNT(*) AS orders, SUM(o.quantity) AS qty FROM cb_orders o JOIN cb_products p ON o.product_sku=p.sku WHERE o.order_status=''completed'' GROUP BY p.product_name ORDER BY orders DESC LIMIT 10',
   '{"columns":["product_name","orders","qty"],"rows":[["便携式榨汁杯 500ml",820,2100],["无线蓝牙耳机 Pro",780,1800],["智能手表 S2",710,1500],["保温杯 大容量 1L",660,1900],["LED化妆镜 带灯",640,1600]]}',
   'Top10热销SKU：便携式榨汁杯 820 单居首，无线蓝牙耳机 780 单、智能手表 710 单紧随其后。',
   'ask', NULL, 'deepseek-v3', FALSE, NULL, 3),
  (106, 103, 6, 105, '这些商品的利润情况如何？', NOW() - INTERVAL '5 days', FALSE,
   'SELECT p.product_name, SUM(o.amount) AS gmv, SUM(o.quantity*p.cost) AS cost, SUM(o.amount)-SUM(o.quantity*p.cost) AS profit FROM cb_orders o JOIN cb_products p ON o.product_sku=p.sku GROUP BY p.product_name ORDER BY gmv DESC LIMIT 10',
   '{"columns":["product_name","gmv","cost","profit"],"rows":[["便携式榨汁杯 500ml",24500,9200,15300],["无线蓝牙耳机 Pro",46800,19300,27500]]}',
   'Top SKU 利润测算：蓝牙耳机毛利最高约 2.75万，榨汁杯毛利 1.53万。',
   'drill', '{"parent_id":105,"dimension":"SKU→利润"}', 'deepseek-v3', FALSE, NULL, 3),
  (107, 102, 6, NULL, '最近30天物流妥投时效与异常率', NOW() - INTERVAL '6 days', FALSE,
   'SELECT l.carrier, AVG(l.delivery_date-l.ship_date) AS lead_time, COUNT(*) FILTER (WHERE l.status=''exception'')/COUNT(*)::float AS exception_rate FROM cb_logistics l GROUP BY l.carrier',
   '{"columns":["carrier","lead_time","exception_rate"],"rows":[["DHL",6.2,0.012],["UPS",7.1,0.018],["4PX",9.8,0.034],["USPS",10.5,0.041]]}',
   'DHL 时效最快 6.2 天且异常率最低，USPS 时效最慢约 10.5 天。',
   'ask', NULL, 'deepseek-v3', FALSE, NULL, 3),
  (108, 102, 6, NULL, '生成一份12月经营复盘报表', NOW() - INTERVAL '7 days', TRUE,
   NULL,
   '{"sections":["本月经营概览","平台销售结构","广告ROI","物流时效","会员运营","下月计划"]}',
   '已生成 12 月经营复盘 AI 报表，覆盖销售/广告/物流/会员四大板块。',
   'report', NULL, 'deepseek-v3', TRUE, '2025年12月跨境电商经营复盘', 3),
  (109, 103, 6, NULL, '各店铺月度GMV对比', NOW() - INTERVAL '8 days', FALSE,
   'SELECT s.shop_name, SUM(o.amount*(1-o.refund_flag)) AS gmv FROM cb_orders o JOIN cb_shops s ON o.shop_id=s.shop_id GROUP BY s.shop_name ORDER BY gmv DESC',
   '{"columns":["shop_name","gmv"],"rows":[["跨海优选 Amazon 美国站",2100000],["跨海优选 Amazon 德国站",980000],["跨海优选 TikTok 美国站",870000]]}',
   '各店铺GMV：Amazon美国站 210万 居首，德国站 98万，TikTok美国站 87万。',
   'ask', NULL, 'deepseek-v3', FALSE, NULL, 3)
ON CONFLICT (id) DO NOTHING;

-- 04.2 固定图表（从智能问数固定到看板的图表）
INSERT INTO pinned_charts
  (id, user_id, datasource_id, title, description, sql_query, chart_type, sort_order, display_order)
VALUES
  (100, 102, 6, '各平台本月GMV', '本月各平台销售额柱状图', 
   'SELECT o.platform, SUM(o.amount*(1-o.refund_flag)) AS gmv FROM cb_orders o WHERE to_char(o.order_date,''YYYY-MM'')=to_char(CURRENT_DATE,''YYYY-MM'') GROUP BY o.platform ORDER BY gmv DESC',
   'bar', 'desc', 1),
  (101, 102, 6, '月度GMV趋势', '近12个月GMV折线趋势',
   'SELECT to_char(o.order_date,''YYYY-MM'') AS month, SUM(o.amount*(1-o.refund_flag)) AS gmv FROM cb_orders o WHERE o.order_date >= CURRENT_DATE - INTERVAL ''12 months'' GROUP BY month ORDER BY month',
   'line', 'none', 2),
  (102, 102, 6, '品类销售额占比', '各品类销售额占比环形图',
   'SELECT p.category, SUM(o.amount*(1-o.refund_flag)) AS gmv FROM cb_orders o JOIN cb_products p ON o.product_sku=p.sku GROUP BY p.category',
   'donut', 'desc', 3),
  (103, 102, 6, '站点退款率对比', '各站点退款率条形图',
   'SELECT o.site, SUM(o.amount*o.refund_flag)/SUM(o.amount) AS rate FROM cb_orders o WHERE o.order_date >= CURRENT_DATE - INTERVAL ''6 months'' GROUP BY o.site ORDER BY rate DESC',
   'bar', 'desc', 4),
  (104, 102, 6, '广告ROI月度趋势', '美国站广告ROI折线趋势',
   'SELECT k.stat_month, SUM(k.gmv)/SUM(k.ad_spend) AS roi FROM cb_monthly_kpi k WHERE k.site=''us'' GROUP BY k.stat_month ORDER BY k.stat_month',
   'line', 'none', 5),
  (105, 102, 6, '核心KPI卡片', '本月GMV/订单量/退款率/客单价 KPI 卡片',
   'SELECT SUM(o.amount*(1-o.refund_flag)) AS gmv, COUNT(*) AS orders, SUM(o.amount*o.refund_flag)/SUM(o.amount) AS refund_rate, SUM(o.amount)/COUNT(*) AS aov FROM cb_orders o WHERE to_char(o.order_date,''YYYY-MM'')=to_char(CURRENT_DATE,''YYYY-MM'')',
   'kpi', 'none', 0),
  (106, 103, 6, '承运商时效对比', '各承运商妥投时效与异常率组合图',
   'SELECT l.carrier, AVG(l.delivery_date-l.ship_date) AS lead_time, COUNT(*) FILTER (WHERE l.status=''exception'')/COUNT(*)::float AS exception_rate FROM cb_logistics l GROUP BY l.carrier',
   'combo', 'none', 6)
ON CONFLICT (id) DO NOTHING;

-- 04.3 看板（3 个：经营总览/广告分析/物流监控，含布局/筛选/分享）
INSERT INTO dashboards
  (id, title, description, layout_json, filters_json, status, visibility, is_public,
   share_token, shared_user_ids, version, org_id, owner_id)
VALUES
  (100, '跨境电商经营总览', '跨海优选核心经营指标总览：销售、退款、广告、会员',
   '{"widgets":[{"id":"w1","chart_id":105,"x":0,"y":0,"w":3,"h":1,"type":"kpi"},{"id":"w2","chart_id":100,"x":3,"y":0,"w":5,"h":4,"type":"bar"},{"id":"w3","chart_id":101,"x":8,"y":0,"w":5,"h":4,"type":"line"},{"id":"w4","chart_id":102,"x":0,"y":4,"w":5,"h":4,"type":"donut"},{"id":"w5","chart_id":103,"x":5,"y":4,"w":4,"h":4,"type":"bar"},{"id":"w6","chart_id":104,"x":9,"y":4,"w":4,"h":4,"type":"line"}]}',
   '{"filters":[{"key":"platform","type":"select","options":["amazon","shopee","tiktok","d2c"]},{"key":"site","type":"select","options":["us","de","uk","jp","sg"]},{"key":"month","type":"month"}]}',
   'published', 'org', 1, 'cb_dash_overview_a1b2c3', '[103,104]', 3, 3, 102),
  (101, '广告投放分析', '广告花费、ROI、CTR、CPC 多维分析',
   '{"widgets":[{"id":"w1","chart_id":104,"x":0,"y":0,"w":6,"h":4,"type":"line"},{"id":"w2","chart_id":100,"x":6,"y":0,"w":6,"h":4,"type":"bar"},{"id":"w3","chart_id":106,"x":0,"y":4,"w":12,"h":4,"type":"combo"}]}',
   '{"filters":[{"key":"platform","type":"select","options":["amazon","shopee","tiktok","d2c"]}]}',
   'published', 'org', 0, NULL, NULL, 2, 3, 102),
  (102, '物流时效监控', '各承运商时效、异常率与目的地时效监控',
   '{"widgets":[{"id":"w1","chart_id":106,"x":0,"y":0,"w":12,"h":5,"type":"combo"},{"id":"w2","chart_id":107,"x":0,"y":5,"w":12,"h":4,"type":"table"}]}',
   '{"filters":[{"key":"carrier","type":"select","options":["DHL","FedEx","UPS","USPS","4PX","YunExpress"]}]}',
   'published', 'org', 0, NULL, NULL, 1, 3, 103)
ON CONFLICT (id) DO NOTHING;

-- 04.4 看板评论
INSERT INTO dashboard_comments (id, dashboard_id, user_id, username, content, created_at)
VALUES
  (100, 100, 102, 'cb_analyst', '12月美国站GMV环比下滑明显，建议下钻查看品类结构。', NOW() - INTERVAL '2 days'),
  (101, 100, 103, 'cb_seller', '已同步运营群，美国站12月促销前置，预计1月回升。', NOW() - INTERVAL '1 day'),
  (102, 101, 102, 'cb_analyst', 'TikTok渠道ROI持续走高，建议12月加预算。', NOW() - INTERVAL '12 hours')
ON CONFLICT (id) DO NOTHING;

-- 04.5 自助分析视图（3 个：平台月度销售/品类利润/会员运营）
INSERT INTO analysis_views
  (id, name, description, dataset_id, chart_type, dimensions, measures, filters,
   sorts, calculation_fields_json, visual_config_json, interaction_json,
   status, visibility, org_id, owner_id)
VALUES
  (100, '平台月度销售分析', '按平台/站点查看月度销售额与订单量', 100, 'bar',
   '["platform","site","month"]',
   '[{"name":"gmv","agg":"sum","label":"销售额"},{"name":"orders","agg":"count","label":"订单量"}]',
   '[{"field":"order_status","op":"=","value":"completed"}]',
   '[{"field":"gmv","order":"desc"}]',
   '{"fields":[{"name":"profit_rate","expr":"(amount-cost*quantity)/amount","label":"毛利率"}]}',
   '{"legend":"top","show_values":true,"color_scheme":"blue"}',
   '{"drilldown":true,"cross_filter":true,"link_to_dashboard":100}',
   'published', 'org', 3, 102),
  (101, '品类利润结构', '各品类销售额、成本与毛利分析', 100, 'combo',
   '["category"]',
   '[{"name":"gmv","agg":"sum","label":"销售额"},{"name":"cost","agg":"sum","label":"成本"},{"name":"profit","agg":"sum","label":"毛利"}]',
   '[]', '[{"field":"profit","order":"desc"}]',
   '{"fields":[{"name":"profit","expr":"sum(amount)-sum(cost*quantity)","label":"毛利"}]}',
   '{"show_values":true,"color_scheme":"green"}',
   '{"drilldown":true,"link_to_dashboard":100}',
   'published', 'org', 3, 103),
  (102, '会员等级运营', '不同会员等级的消费与活跃分析', 100, 'pie',
   '["membership_level"]',
   '[{"name":"total_spent","agg":"sum","label":"消费金额"}]',
   '[{"field":"join_date","op":">=","value":"2024-01-01"}]',
   '[]', NULL,
   '{"show_legend":true}',
   '{"link_to_metric":110}',
   'published', 'org', 3, 102)
ON CONFLICT (id) DO NOTHING;

-- 04.6 大屏（2 个：跨境作战大屏/广告实时监控大屏）
INSERT INTO big_screens
  (id, title, description, canvas_json, data_bindings_json, status, visibility, org_id, owner_id)
VALUES
  (100, '跨境电商全球作战大屏', '全球店铺销售、物流、广告一站式监控',
   '{"background":"dark","rows":3,"cols":4,"widgets":[{"id":"g1","title":"全球GMV","x":0,"y":0,"w":1,"h":1,"type":"kpi","source":"sql"},{"id":"g2","title":"平台销售结构","x":1,"y":0,"w":1,"h":2,"type":"pie","source":"sql"},{"id":"g3","title":"月度GMV趋势","x":2,"y":0,"w":2,"h":2,"type":"line","source":"sql"},{"id":"g4","title":"物流异常预警","x":0,"y":2,"w":2,"h":1,"type":"list","source":"sql"},{"id":"g5","title":"广告ROI","x":2,"y":2,"w":1,"h":1,"type":"gauge","source":"sql"},{"id":"g6","title":"实时订单数","x":3,"y":2,"w":1,"h":1,"type":"counter","source":"api"}]}',
   '{"bindings":[{"widget":"g1","sql":"SELECT SUM(amount*(1-refund_flag)) FROM cb_orders WHERE order_date=CURRENT_DATE"},{"widget":"g2","sql":"SELECT platform,SUM(amount) FROM cb_orders WHERE order_date >= CURRENT_DATE-30 GROUP BY platform"},{"widget":"g3","sql":"SELECT to_char(order_date,''YYYY-MM''),SUM(amount) FROM cb_orders GROUP BY 1 ORDER BY 1"},{"widget":"g4","sql":"SELECT order_id,status FROM cb_logistics WHERE status=''exception'' LIMIT 10"},{"widget":"g5","sql":"SELECT SUM(gmv)/SUM(ad_spend) FROM cb_monthly_kpi WHERE stat_month=to_char(CURRENT_DATE,''YYYY-MM'')"}]}',
   'published', 'org', 3, 102),
  (101, '广告投放实时监控大屏', '各渠道广告花费、CTR、转化实时监控',
   '{"background":"light","rows":2,"cols":3,"widgets":[{"id":"a1","title":"花费趋势","x":0,"y":0,"w":2,"h":1,"type":"line"},{"id":"a2","title":"渠道占比","x":2,"y":0,"w":1,"h":2,"type":"pie"},{"id":"a3","title":"CTR/CPC","x":0,"y":1,"w":2,"h":1,"type":"kpi"}]}',
   '{"bindings":[{"widget":"a1","sql":"SELECT ad_date,SUM(spend) FROM cb_ad_spend GROUP BY ad_date ORDER BY ad_date DESC LIMIT 30"},{"widget":"a2","sql":"SELECT platform,SUM(spend) FROM cb_ad_spend WHERE ad_date>=CURRENT_DATE-7 GROUP BY platform"},{"widget":"a3","sql":"SELECT SUM(clicks)/SUM(impressions) AS ctr, SUM(spend)/SUM(clicks) AS cpc FROM cb_ad_spend WHERE ad_date=CURRENT_DATE"}]}',
   'published', 'org', 3, 103)
ON CONFLICT (id) DO NOTHING;

-- 04.7 嵌入 Token（图表/看板对外嵌入）
INSERT INTO embed_tokens (id, token, label, resource_type, resource_id, allowed_domains, created_by, expires_at)
VALUES
  (100, 'cb_embed_dash_7f3a9c1e2b4d5f6a', '经营总览-对外分享', 'dashboard', 100, 'partner.example.com,ops.example.com', 102, NOW() + INTERVAL '365 days'),
  (101, 'cb_embed_chart_9d2f4e8a1c3b5d7f', '广告ROI-供应商', 'chart', 104, 'ads.example.com', 102, NOW() + INTERVAL '180 days')
ON CONFLICT (id) DO NOTHING;

-- 05.1 数据告警（6 个：退款率/广告ROI/物流异常/库存/KPI 阈值预警）
INSERT INTO alerts
  (id, name, dataset_id, datasource_id, metric_id, metric_name, time_range, time_range_unit,
   dimension_conditions, metric_conditions, check_period, check_period_unit,
   assignees, cc_users, notify_system, notify_email, notify_wechat, notify_dingtalk,
   email_recipients, content, auto_create_action_item, action_item_assignee_id,
   is_active, created_by)
VALUES
  (100, '德国站退款率异常预警', 100, 6, 103, '退款率', 7, 'day',
   '[{"dimension":"site","operator":"=","value":"de"}]',
   '[{"metric":"退款率","operator":">","value":0.05}]', 1, 'day',
   '[103]', '[102]', TRUE, TRUE, TRUE, FALSE, 'ops@kuahai.com',
   '德国站近7天退款率超过5%，请立即排查物流与商品质量问题。', TRUE, 103, TRUE, 102),
  (101, '广告ROI跌破阈值', 101, 6, 105, '广告ROI', 30, 'day',
   '[{"dimension":"platform","operator":"=","value":"amazon"}]',
   '[{"metric":"广告ROI","operator":"<","value":3.0}]', 1, 'day',
   '[102,103]', '[]', TRUE, FALSE, TRUE, FALSE, NULL,
   '美国站广告ROI近30天低于3.0，建议调整投放策略。', TRUE, 103, TRUE, 102),
  (102, '物流异常率监控', 103, 6, 108, '物流异常率', 1, 'day',
   NULL,
   '[{"metric":"物流异常率","operator":">","value":0.05}]', 2, 'hour',
   '[103]', '[100]', TRUE, FALSE, TRUE, TRUE, NULL,
   '近24小时物流异常率超过5%，涉及DHL与4PX渠道，请核实。', FALSE, NULL, TRUE, 103),
  (103, '月度GMV目标达成预警', 101, 6, 100, 'GMV 总销售额', 1, 'month',
   NULL,
   '[{"metric":"GMV 总销售额","operator":"<","value":2800000}]', 1, 'day',
   '[100,102]', '[104]', TRUE, TRUE, FALSE, FALSE, 'finance@kuahai.com',
   '本月GMV尚未达到280万目标，距离月末还有10天，请关注冲刺节奏。', TRUE, 100, TRUE, 100),
  (104, '日本站客单价下滑', 100, 6, 102, '客单价 AOV', 14, 'day',
   '[{"dimension":"site","operator":"=","value":"jp"}]',
   '[{"metric":"客单价 AOV","operator":"<","value":25.0}]', 1, 'day',
   '[103]', '[]', TRUE, FALSE, FALSE, FALSE, NULL,
   '日本站近两周客单价低于25美元，可能受促销折扣影响，需关注毛利。', FALSE, NULL, TRUE, 102),
  (105, '库存周转慢预警', 100, 6, NULL, NULL, 7, 'day',
   '[{"dimension":"category","operator":"=","value":"居家生活"}]',
   '[{"metric":"quantity","operator":">","value":500}]', 1, 'day',
   '[103]', '[100]', TRUE, FALSE, TRUE, FALSE, NULL,
   '居家生活品类近7天销量放缓，叠加在途库存，建议暂停补货计划。', TRUE, 103, TRUE, 103)
ON CONFLICT (id) DO NOTHING;

-- 05.2 预警历史（告警触发与通知结果记录）
INSERT INTO alert_history
  (id, alert_id, alert_name, triggered_at, metric_value, condition_desc, notify_result, status)
VALUES
  (100, 100, '德国站退款率异常预警', NOW() - INTERVAL '2 days', '0.056', '退款率 > 5% (实际 5.6%)',
   '{"system":"success","email":"success","wechat":"success"}', 'triggered'),
  (101, 100, '德国站退款率异常预警', NOW() - INTERVAL '9 days', '0.052', '退款率 > 5% (实际 5.2%)',
   '{"system":"success","email":"success","wechat":"success"}', 'triggered'),
  (102, 101, '广告ROI跌破阈值', NOW() - INTERVAL '1 day', '2.87', '广告ROI < 3.0 (实际 2.87)',
   '{"system":"success","wechat":"success"}', 'triggered'),
  (103, 102, '物流异常率监控', NOW() - INTERVAL '5 hours', '0.061', '物流异常率 > 5% (实际 6.1%)',
   '{"system":"success","wechat":"success","dingtalk":"success"}', 'triggered'),
  (104, 103, '月度GMV目标达成预警', NOW() - INTERVAL '3 days', '2410000', 'GMV < 2800000 (实际 241万)',
   '{"system":"success","email":"success"}', 'triggered'),
  (105, 104, '日本站客单价下滑', NOW() - INTERVAL '6 days', '23.4', '客单价 < 25 (实际 23.4)',
   '{"system":"success"}', 'triggered'),
  (106, 105, '库存周转慢预警', NOW() - INTERVAL '2 days', '620', '近7天销量放缓(库存>500)',
   '{"system":"success","wechat":"success"}', 'triggered'),
  (107, 102, '物流异常率监控', NOW() - INTERVAL '2 days' - INTERVAL '3 hours', '0.048', '物流异常率接近阈值(4.8%)',
   '{"system":"success"}', 'triggered')
ON CONFLICT (id) DO NOTHING;

-- 05.3 行动项（告警联动 + 手动创建，形成发现→处置→复盘闭环）
INSERT INTO action_items
  (id, title, description, source_type, source_id, source_payload, linked_metric_id,
   linked_dataset_id, linked_dashboard_id, owner_id, priority, due_date, status,
   outcome, org_id, created_by, closed_at)
VALUES
  (100, '排查德国站退款原因', '德国站退款率连续两周超5%，重点核查物流破损与产品兼容性问题。',
   'alert', '100', '{"alert_id":100,"metric":"退款率"}', 103, 100, 100,
   103, 'high', CURRENT_DATE + 3, 'in_progress',
   NULL, 3, 102, NULL),
  (101, '调整美国站广告出价', '美国站广告ROI低于3.0，建议将品牌词预算提高、竞品词出价下调15%。',
   'alert', '101', '{"alert_id":101,"metric":"广告ROI"}', 105, 101, 101,
   103, 'medium', CURRENT_DATE + 5, 'open',
   NULL, 3, 102, NULL),
  (102, '跟进物流异常订单', '6.1%物流异常率中DHL占比最高，与承运商确认赔付与时效承诺。',
   'alert', '102', '{"alert_id":102,"metric":"物流异常率"}', 108, 103, 102,
   103, 'high', CURRENT_DATE + 2, 'in_progress',
   NULL, 3, 103, NULL),
  (103, '12月GMV冲刺复盘', '本月GMV目标280万，实际预计246万，召开复盘会明确差距与改进措施。',
   'manual', NULL, NULL, 100, 101, 100,
   100, 'high', CURRENT_DATE + 7, 'open',
   NULL, 3, 100, NULL),
  (104, '日本站客单价优化', '日本站客单价低于25美元，评估促销结构并推出组合装提升客单。',
   'alert', '104', '{"alert_id":104,"metric":"客单价 AOV"}', 102, 100, 100,
   103, 'medium', CURRENT_DATE + 10, 'open',
   NULL, 3, 102, NULL),
  (105, '优化4PX渠道时效', '4PX渠道妥投时效最慢且异常率偏高，评估切换线路或增补备选承运商。',
   'manual', NULL, NULL, 107, 103, 102,
   103, 'medium', CURRENT_DATE + 14, 'done',
   '已与4PX商务沟通，2月起启用新专线，预计时效提升20%。', 3, 102, NOW() - INTERVAL '3 days'),
  (106, '居家生活品类补货评审', '该品类销量放缓，暂停本月补货计划并复核在途库存。',
   'alert', '105', '{"alert_id":105,"category":"居家生活"}', NULL, 100, NULL,
   103, 'low', CURRENT_DATE + 6, 'open',
   NULL, 3, 103, NULL)
ON CONFLICT (id) DO NOTHING;

-- 05.4 定时报告（3 个：日报/周报/月报）
INSERT INTO scheduled_reports
  (id, name, dataset_id, datasource_id, question, cron_expression,
   notify_email, notify_wechat, notify_dingtalk, email_recipients,
   is_active, created_by, last_run_at)
VALUES
  (100, '跨境电商销售日报', 100, 6, '汇总昨日各平台销售额、订单量与退款率，输出数据表格',
   '0 8 * * *', TRUE, TRUE, FALSE, 'ops@kuahai.com,sales@kuahai.com', TRUE, 102,
   NOW() - INTERVAL '8 hours'),
  (101, '广告投放周报', 102, 6, '本周各渠道广告花费、CTR、CPC、ROI 周环比分析',
   '0 9 * * 1', TRUE, FALSE, TRUE, 'mkt@kuahai.com', TRUE, 102,
   NOW() - INTERVAL '6 days'),
  (102, '月度经营复盘报告', 101, 6, '本月经营复盘：GMV达成率、退款率、广告ROI、物流时效、会员运营综合分析',
   '0 10 1 * *', TRUE, FALSE, FALSE, 'ceo@kuahai.com,finance@kuahai.com', TRUE, 100,
   NOW() - INTERVAL '24 days')
ON CONFLICT (id) DO NOTHING;

-- 05.5 定时报告执行日志
INSERT INTO report_execution_logs
  (id, report_id, report_name, status, content_preview, notify_result, error_message, run_at, org_id)
VALUES
  (100, 100, '跨境电商销售日报', 'success',
   '# 跨境电商销售日报\n\n## 昨日销售概览\n| 平台 | 销售额 | 订单量 |\n|---|---|---|\n| amazon | $43,200 | 1,280 |\n| tiktok | $18,900 | 640 |\n| shopee | $12,400 | 410 |\n| d2c | $11,800 | 360 |\n\n## 退款率\n昨日整体退款率 3.1%，环比下降 0.4pp。',
   '{"email":"success","wechat":"success"}', NULL, NOW() - INTERVAL '8 hours', 3),
  (101, 101, '广告投放周报', 'success',
   '# 广告投放周报\n\n## 本周广告概览\n- 总花费: $15,800\n- 平均CTR: 2.8%\n- 平均CPC: $1.24\n- 整体ROI: 4.35\n\n## 渠道明细\n| 渠道 | 花费 | ROI |\n|---|---|---|\n| amazon | $8,200 | 4.1 |\n| tiktok | $4,600 | 5.2 |\n| shopee | $1,900 | 3.8 |\n| d2c | $1,100 | 4.6 |',
   '{"email":"success","dingtalk":"success"}', NULL, NOW() - INTERVAL '6 days', 3),
  (102, 102, '月度经营复盘报告', 'success',
   '# 12月经营复盘\n\n## 核心指标\n- GMV: 246万 (目标280万, 达成率 87.9%)\n- 退款率: 3.4%\n- 广告ROI: 4.2\n- 平均妥投时效: 8.7天\n\n## 亮点\n- TikTok渠道GMV同比增长 65%\n- 会员复购率提升 8pp\n\n## 风险\n- 美国站12月GMV环比下滑 12%\n- 日本站客单价持续走低',
   '{"email":"success"}', NULL, NOW() - INTERVAL '24 days', 3)
ON CONFLICT (id) DO NOTHING;

-- 05.6 复杂报表模板（月度经营报表/费用填报/商品价格表）
INSERT INTO report_templates
  (id, name, description, dataset_id, report_type, layout_json, parameter_schema_json,
   binding_json, style_json, permission_json, fill_schema_json, distribution_json,
   status, visibility, version, org_id, owner_id, created_by)
VALUES
  (100, '月度经营分析报表', '按月输出经营核心指标的结构化报表，支持导出PDF/Excel', 101, 'paginated',
   '{"sections":[{"title":"经营概览","blocks":["KPI卡片","GMV趋势图","平台占比图"]},{"title":"广告分析","blocks":["广告表","ROI图"]},{"title":"物流与售后","blocks":["物流时效表","退款率图"]}]}',
   '{"params":[{"name":"month","type":"month","required":true,"default":"current"},{"name":"platform","type":"select","options":["all","amazon","shopee","tiktok","d2c"]}]}',
   '{"bindings":[{"block":"KPI卡片","sql":"SELECT SUM(gmv) AS gmv, SUM(orders) AS orders FROM cb_monthly_kpi WHERE stat_month=$month$"},{"block":"GMV趋势图","sql":"SELECT stat_month,SUM(gmv) FROM cb_monthly_kpi WHERE platform=$platform$ OR $platform$=''all'' GROUP BY stat_month ORDER BY stat_month"}]}',
   '{"theme":"professional","header_logo":true,"footer_org":"跨海优选","font":"default"}',
   '{"viewers":["dept"],"editors":[100],"fillers":[]}',
   NULL, '{"emails":["ceo@kuahai.com"],"attach_pdf":true,"schedule":"0 10 1 * *"}',
   'published', 'org', 2, 3, 102, 102),
  (101, '运营费用填报单', '各站点运营费用月度填报，支持在线填报与汇总', NULL, 'fill',
   '{"sections":[{"title":"费用明细","blocks":["广告费","物流费","仓储费","人工费"]}]}',
   NULL, NULL,
   '{"theme":"form","layout":"table"}',
   '{"viewers":[100,104],"editors":[],"fillers":[103]}',
   '{"fields":[{"name":"ad_fee","label":"广告费","type":"currency","required":true},{"name":"logistics_fee","label":"物流费","type":"currency","required":true},{"name":"storage_fee","label":"仓储费","type":"currency"},{"name":"labor_fee","label":"人工费","type":"currency"}]}',
   '{"emails":["finance@kuahai.com"],"deadline":"每月5日"}',
   'published', 'org', 1, 3, 102, 102),
  (102, '商品价格调整表', '月度商品调价方案登记表，用于审批与归档', 100, 'paginated',
   '{"sections":[{"title":"调价明细","blocks":["商品清单表"]}]}',
   '{"params":[{"name":"effective_date","type":"date","required":true}]}',
   '{"bindings":[{"block":"商品清单表","sql":"SELECT sku,product_name,listing_price,cost FROM cb_products WHERE is_active=1"}]}',
   '{"theme":"simple"}',
   '{"viewers":[100,104],"editors":[102],"fillers":[]}',
   NULL, NULL,
   'draft', 'org', 1, 3, 102, 102)
ON CONFLICT (id) DO NOTHING;

-- 05.7 报表模板版本
INSERT INTO report_template_versions (id, template_id, version, snapshot_json, changelog, created_by)
VALUES
  (100, 100, 1, '{"name":"月度经营分析报表","layout":"v1","bindings":5}', '初版发布', 102),
  (101, 100, 2, '{"name":"月度经营分析报表","layout":"v2","bindings":5,"added":["物流时效表"]}', '新增物流时效板块', 102),
  (102, 101, 1, '{"name":"运营费用填报单","layout":"v1","fill_fields":4}', '初版发布', 102)
ON CONFLICT (id) DO NOTHING;

-- 05.8 报表运行记录
INSERT INTO report_runs
  (id, template_id, version, run_type, export_type, status, parameters_json, output_uri,
   content_preview, error_message, org_id, created_by, started_at, finished_at)
VALUES
  (100, 100, 2, 'preview', 'html', 'success',
   '{"month":"2025-12","platform":"all"}',
   'reports/monthly_202512_preview.html',
   '## 经营概览\nGMV: 246万 | 订单: 7,800 | 退款率: 3.4%\n\n## 平台分布\n| 平台 | GMV |\n|---|---|\n| amazon | 132万 |\n| tiktok | 58万 |\n| shopee | 41万 |\n| d2c | 36万 |',
   NULL, 3, 102, NOW() - INTERVAL '20 days', NOW() - INTERVAL '20 days' + INTERVAL '3 minutes'),
  (101, 100, 2, 'scheduled', 'pdf', 'success',
   '{"month":"2025-12","platform":"all"}',
   'reports/monthly_202512.pdf',
   'PDF已生成，共8页，已通过邮件分发。',
   NULL, 3, 102, NOW() - INTERVAL '20 days', NOW() - INTERVAL '20 days' + INTERVAL '8 minutes'),
  (102, 102, 1, 'preview', 'html', 'success',
   '{"effective_date":"2026-01-15"}',
   'reports/price_adjust_20260115.html',
   '## 商品调价明细\n| SKU | 品名 | 现价 | 成本 |\n|---|---|---|---|\n| SKU01 | 便携式榨汁杯 | 29.99 | 11.20 |\n| SKU02 | 无线蓝牙耳机 | 59.99 | 24.80 |',
   NULL, 3, 102, NOW() - INTERVAL '2 days', NOW() - INTERVAL '2 days' + INTERVAL '2 minutes'),
  (103, 100, 1, 'preview', 'html', 'error',
   '{"month":"2025-12","platform":"all"}',
   NULL, NULL,
   '数据绑定失败：block "GMV趋势图" 的SQL参数解析异常',
   3, 102, NOW() - INTERVAL '25 days', NOW() - INTERVAL '25 days' + INTERVAL '1 minute')
ON CONFLICT (id) DO NOTHING;

-- 05.9 报表填报记录
INSERT INTO report_fill_records
  (id, template_id, payload_json, validation_status, validation_errors_json, writeback_status,
   writeback_error, org_id, submitted_by)
VALUES
  (100, 101, '{"ad_fee":18500,"logistics_fee":32000,"storage_fee":8600,"labor_fee":12000,"month":"2025-12","site":"us"}',
   'passed', NULL, 'success', NULL, 3, 103),
  (101, 101, '{"ad_fee":9200,"logistics_fee":14800,"storage_fee":3900,"labor_fee":8000,"month":"2025-12","site":"de"}',
   'passed', NULL, 'success', NULL, 3, 103),
  (102, 101, '{"ad_fee":12000,"logistics_fee":21000,"storage_fee":5600,"labor_fee":9000,"month":"2025-12","site":"jp"}',
   'failed', '[{"field":"logistics_fee","error":"超出预算上限 20000"}]', 'pending',
   NULL, 3, 103)
ON CONFLICT (id) DO NOTHING;

-- 05.10 数据流水线（订单增量同步→汇总层构建→质量校验）
INSERT INTO data_pipelines
  (id, name, description, dataset_id, dag_json, schedule_cron, run_mode, status,
   environment, priority, sla_minutes, retry_count, timeout_minutes, alert_policy_json,
   state_json, current_version, published_version, last_run_status, last_run_at,
   org_id, owner_id, created_by)
VALUES
  (100, '订单数据增量同步', '每日从业务库抽取订单/明细/物流，增量写入明细层', 100,
   '{"nodes":[{"id":"n1","type":"source","label":"cb_orders"},{"id":"n2","type":"source","label":"cb_order_items"},{"id":"n3","type":"join","label":"订单-明细关联"},{"id":"n4","type":"transform","label":"去重与清洗"},{"id":"n5","type":"sink","label":"ods_order_daily"}],"edges":[["n1","n3"],["n2","n3"],["n3","n4"],["n4","n5"]]}',
   '0 2 * * *', 'scheduled', 'active', 'prod', 'high', 120, 3, 60,
   '{"on_failure":["notify_owner","notify_wechat"],"retry":true,"rules":[{"metric":"records_failed","op":">","value":100}]}',
   '{"last_sync":{"start":"2025-12-30 02:00:00","end":"2025-12-30 02:04:32","records":12000}}',
   3, 3, 'success', NOW() - INTERVAL '2 hours', 3, 102, 102),
  (101, '月度KPI汇总层构建', '聚合订单/广告数据生成月度KPI宽表', 101,
   '{"nodes":[{"id":"n1","type":"source","label":"ods_order_daily"},{"id":"n2","type":"source","label":"cb_ad_spend"},{"id":"n3","type":"agg","label":"月度聚合"},{"id":"n4","type":"calc","label":"ROI计算"},{"id":"n5","type":"sink","label":"mart_kpi_monthly"}],"edges":[["n1","n3"],["n2","n3"],["n3","n4"],["n4","n5"]]}',
   '0 3 1 * *', 'scheduled', 'active', 'prod', 'medium', 240, 2, 120,
   '{"on_failure":["notify_owner"],"retry":true}',
   '{"last_run":{"records":168,"duration_ms":48000}}',
   2, 2, 'success', NOW() - INTERVAL '24 days', 3, 102, 102),
  (102, '广告效果归因计算', '按渠道/活动归因广告订单，产出转化数据', 102,
   '{"nodes":[{"id":"n1","type":"source","label":"cb_ad_spend"},{"id":"n2","type":"transform","label":"归因规则"},{"id":"n3","type":"calc","label":"CTR/CPC/CVR"},{"id":"n4","type":"sink","label":"mart_ad_daily"}],"edges":[["n1","n2"],["n2","n3"],["n3","n4"]]}',
   '0 4 * * *', 'scheduled', 'active', 'prod', 'medium', 90, 2, 30,
   '{"on_failure":["notify_owner"],"retry":true}',
   '{"last_run":{"records":3650,"duration_ms":22000}}',
   2, 2, 'success', NOW() - INTERVAL '3 hours', 3, 103, 103)
ON CONFLICT (id) DO NOTHING;

-- 05.11 流水线版本
INSERT INTO data_pipeline_versions
  (id, pipeline_id, version, status, dag_json, config_json, comment, org_id, created_by, published_at)
VALUES
  (100, 100, 1, 'archived', '{"nodes":["n1","n2","n3"]}', '{"mode":"full_refresh"}', '初版：全量刷新', 3, 102, NOW() - INTERVAL '30 days'),
  (101, 100, 2, 'published', '{"nodes":["n1","n2","n3","n4","n5"]}', '{"mode":"incremental","key":"order_date"}', 'v2：改为增量同步并增加清洗', 3, 102, NOW() - INTERVAL '15 days'),
  (102, 101, 1, 'published', '{"nodes":["n1","n2","n3","n4","n5"]}', '{"mode":"monthly"}', '初版发布', 3, 102, NOW() - INTERVAL '25 days'),
  (103, 102, 1, 'published', '{"nodes":["n1","n2","n3","n4"]}', '{"mode":"daily"}', '初版发布', 3, 103, NOW() - INTERVAL '10 days')
ON CONFLICT (id) DO NOTHING;

-- 05.12 流水线运行记录
INSERT INTO data_pipeline_runs
  (id, pipeline_id, mode, status, reason, node_logs_json, records_read, records_written,
   records_failed, error_message, notify_result_json, scheduled_job_id, duration_ms,
   org_id, triggered_by_id, started_at, finished_at)
VALUES
  (100, 100, 'scheduled', 'success', 'schedule: 0 2 * * *',
   '{"summary":{"node_count":3,"status":"success"},"nodes":[{"node_id":"n1","status":"ok","rows":12000},{"node_id":"n3","status":"ok","rows":12000},{"node_id":"n5","status":"ok","rows":12000}]}',
   12000, 12000, 0, NULL, '{"notify":"none"}', 'job-20251230-0200', 272000, 3, 102,
   NOW() - INTERVAL '2 hours', NOW() - INTERVAL '2 hours' + INTERVAL '4 minutes'),
  (101, 101, 'scheduled', 'success', 'schedule: 0 3 1 * *',
   '{"summary":{"node_count":3,"status":"success"},"nodes":[{"node_id":"n1","status":"ok","rows":12000},{"node_id":"n3","status":"ok","rows":168},{"node_id":"n5","status":"ok","rows":168}]}',
   12000, 168, 0, NULL, '{"notify":"none"}', 'job-20251201-0300', 48000, 3, 102,
   NOW() - INTERVAL '24 days', NOW() - INTERVAL '24 days' + INTERVAL '48 seconds'),
  (102, 102, 'scheduled', 'success', 'schedule: 0 4 * * *',
   '{"summary":{"node_count":2,"status":"success"},"nodes":[{"node_id":"n1","status":"ok","rows":3650},{"node_id":"n4","status":"ok","rows":3650}]}',
   3650, 3650, 0, NULL, '{"notify":"none"}', 'job-20251230-0400', 22000, 3, 103,
   NOW() - INTERVAL '3 hours', NOW() - INTERVAL '3 hours' + INTERVAL '22 seconds'),
  (103, 100, 'manual', 'error', '手动触发测试',
   '{"summary":{"node_count":2,"status":"error"},"nodes":[{"node_id":"n1","status":"ok","rows":12000},{"node_id":"n3","status":"error","rows":0}]}',
   12000, 0, 300, 'join失败：订单与明细主键冲突', '{"notify":"wechat","result":"sent"}',
   NULL, 15000, 3, 102,
   NOW() - INTERVAL '5 days', NOW() - INTERVAL '5 days' + INTERVAL '15 seconds')
ON CONFLICT (id) DO NOTHING;

-- 05.13 数据质量规则（含通过/告警/失败状态）
INSERT INTO data_quality_rules
  (id, pipeline_id, dataset_id, name, rule_type, field, operator, threshold, severity,
   is_active, last_status, last_checked_at, org_id, created_by)
VALUES
  (100, 100, 100, '订单量日环比波动', 'volatility', 'order_date', '>', '30%', 'warning',
   TRUE, 'passed', NOW() - INTERVAL '2 hours', 3, 102),
  (101, 100, 100, '订单金额非负校验', 'range', 'amount', '>=', '0', 'critical',
   TRUE, 'passed', NOW() - INTERVAL '2 hours', 3, 102),
  (102, 101, 101, 'KPI合计完整性', 'completeness', 'gmv', '>', '95%', 'warning',
   TRUE, 'passed', NOW() - INTERVAL '1 day', 3, 102),
  (103, 102, 102, '广告花费日环比', 'volatility', 'spend', '>', '50%', 'warning',
   TRUE, 'warning', NOW() - INTERVAL '3 hours', 3, 103),
  (104, 100, 100, '退款率异常阈值', 'threshold', 'refund_flag', '>', '10%', 'critical',
   TRUE, 'failed', NOW() - INTERVAL '5 days', 3, 102),
  (105, NULL, 103, '物流时效超时监控', 'threshold', 'lead_time', '>', '15天', 'warning',
   TRUE, 'passed', NOW() - INTERVAL '4 hours', 3, 103)
ON CONFLICT (id) DO NOTHING;

-- 05.14 数据目录分类（id=5 起新增；跨海优选目录）
INSERT INTO catalog_categories (id, name, parent_id, org_id, sort_order)
VALUES
  (5, '跨境电商', NULL, 3, 1),
  (6, '经营分析', 5, 3, 1),
  (7, '营销广告', 5, 3, 2),
  (8, '供应链', 5, 3, 3),
  (9, '财务', 5, 3, 4)
ON CONFLICT (id) DO NOTHING;

-- 05.15 数据资产（数据集/指标/看板/报表/大屏入目录，含标签与元数据）
INSERT INTO data_assets
  (id, asset_type, asset_id, name, description, datasource_id, org_id, owner_id,
   category_id, status, tags, metadata_json, view_count)
VALUES
  (100, 'dataset', 100, '跨境电商订单分析', '订单/明细/客户/商品多表关联数据集', 6, 3, 102, 6,
   'published', '["订单","销售","核心"]',
   '{"fields":9,"records":12000,"refresh":"每日增量","owner":"cb_analyst"}', 356),
  (101, 'dataset', 101, '跨境电商月度KPI', 'GMV/退款/广告/ROI 月度汇总数据集', 6, 3, 102, 6,
   'published', '["KPI","月度"]',
   '{"fields":10,"records":168,"refresh":"每月","owner":"cb_analyst"}', 280),
  (102, 'dataset', 102, '跨境电商广告分析', '广告投放明细与效果归因数据集', 6, 3, 102, 7,
   'published', '["广告","ROI"]',
   '{"fields":8,"records":3650,"refresh":"每日","owner":"cb_analyst"}', 198),
  (103, 'dataset', 103, '跨境电商物流时效', '物流承运、妥投时效与异常监控数据集', 6, 3, 102, 8,
   'published', '["物流","时效"]',
   '{"fields":7,"records":12000,"refresh":"每日","owner":"cb_analyst"}', 145),
  (104, 'metric', 100, 'GMV 总销售额', '已完成订单有效销售额（扣退款）', 6, 3, 102, 6,
   'published', '["核心","收入","已认证"]',
   '{"certified":true,"caliber":"v2","last_value":3285000}', 512),
  (105, 'metric', 105, '广告 ROI', 'GMV/广告花费投入产出比', 6, 3, 102, 7,
   'published', '["营销","效率","已认证"]',
   '{"certified":true,"caliber":"v2","last_value":4.35}', 420),
  (106, 'dashboard', 100, '跨境电商经营总览', '跨海优选核心经营指标总览看板', 6, 3, 102, 6,
   'published', '["看板","经营"]',
   '{"widgets":6,"public":true}', 720),
  (107, 'dashboard', 101, '广告投放分析', '广告花费、ROI、CTR、CPC 多维分析看板', 6, 3, 102, 7,
   'published', '["看板","广告"]',
   '{"widgets":3}', 310),
  (108, 'big_screen', 100, '跨境电商全球作战大屏', '全球店铺销售、物流、广告一站式监控大屏', 6, 3, 102, 6,
   'published', '["大屏","全球"]',
   '{"widgets":6}', 88),
  (109, 'report', 100, '月度经营分析报表', '按月输出经营核心指标的结构化报表', 6, 3, 102, 6,
   'published', '["报表","月度"]',
   '{"version":2,"distribute":"ceo@kuahai.com"}', 64),
  (110, 'metric', 109, '退货率（待复核）', '近7天退款率，疑似数据波动异常', 6, 3, 102, 6,
   'draft', '["异常","待复核"]',
   '{"quality":"error","note":"环比上升45%"}', 12),
  (111, 'dataset', 100, '订单数据增量同步', '每日订单/明细/物流增量同步流水线', 6, 3, 102, 6,
   'published', '["流水线","增量"]',
   '{"type":"pipeline","records":12000,"status":"success"}', 35)
ON CONFLICT (id) DO NOTHING;

-- 05.16 资产血缘（数据集/指标/看板派生关系）
INSERT INTO asset_lineage (id, source_id, target_id, rel_type, org_id)
VALUES
  (100, 100, 101, 'derives_from', 3),
  (101, 100, 104, 'derives_from', 3),
  (102, 102, 105, 'derives_from', 3),
  (103, 100, 106, 'derives_from', 3),
  (104, 102, 107, 'derives_from', 3),
  (105, 101, 106, 'feeds_into', 3),
  (106, 104, 109, 'feeds_into', 3),
  (107, 111, 100, 'derives_from', 3)
ON CONFLICT (id) DO NOTHING;

-- 05.17 资产订阅与通知
INSERT INTO asset_subscriptions (id, user_id, asset_id)
VALUES
  (100, 102, 104),
  (101, 102, 106),
  (102, 103, 107),
  (103, 103, 101),
  (104, 104, 106)
ON CONFLICT (id) DO NOTHING;

INSERT INTO asset_notifications (id, user_id, asset_id, message, is_read)
VALUES
  (100, 102, 104, '您订阅的指标「GMV 总销售额」数据已更新至 328.5万。', FALSE),
  (101, 102, 106, '看板「跨境电商经营总览」有新的评论。', FALSE),
  (102, 103, 101, '数据集「跨境电商月度KPI」刷新成功。', TRUE),
  (103, 104, 106, '您被加入了看板「跨境电商经营总览」共享名单。', TRUE)
ON CONFLICT (id) DO NOTHING;

-- 06.1 行级安全策略（RLS）
-- 例：cb_orders 按国家控制（美国站用户仅能看 US 站点数据）
INSERT INTO rls_rules
  (id, datasource_id, org_id, user_id, table_name, column_name, operator, filter_value, is_active)
VALUES
  (100, 6, 3, NULL, 'cb_orders', 'site', 'IN', 'us,de,uk,jp,sg', 1),
  (101, 6, NULL, 104, 'cb_orders', 'site', '=', 'us', 1),
  (102, 6, 3, NULL, 'cb_monthly_kpi', 'platform', 'IN', 'amazon,shopee,tiktok,d2c', 1),
  (103, 6, NULL, 103, 'cb_orders', 'site', 'IN', 'us,de', 1)
ON CONFLICT (id) DO NOTHING;

-- 06.2 审计日志（登录/查询/导出/权限变更等关键操作留痕）
INSERT INTO audit_logs
  (id, actor_user_id, actor_username, actor_role, org_id, action, resource_type,
   resource_id, resource_name, status, message, detail_json, ip_address)
VALUES
  (100, 102, 'cb_analyst', 'user', 3, 'login', 'session', NULL, NULL, 'success',
   '用户登录成功', '{"method":"password","ttl":"7d"}', '10.10.1.23'),
  (101, 102, 'cb_analyst', 'user', 3, 'query.execute', 'query', '100', '各平台本月销售额',
   'success', '智能问数执行SQL成功', '{"sql":"SELECT o.platform...","cost_ms":830,"model":"deepseek-v3"}', '10.10.1.23'),
  (102, 102, 'cb_analyst', 'user', 3, 'chart.pin', 'chart', '100', '各平台本月GMV',
   'success', '固定图表到看板', '{"dashboard_id":100}', '10.10.1.23'),
  (103, 103, 'cb_seller', 'user', 3, 'dashboard.view', 'dashboard', '100', '跨境电商经营总览',
   'success', '查看看板', '{"source":"web"}', '10.10.2.88'),
  (104, 102, 'cb_analyst', 'user', 3, 'report.run', 'report', '100', '月度经营分析报表',
   'success', '运行报表并导出PDF', '{"export":"pdf","pages":8}', '10.10.1.23'),
  (105, 100, 'cb_admin', 'super_admin', 3, 'user.create', 'user', '104', 'cb_viewer',
   'success', '创建用户', '{"role":"user","org":"crossborder"}', '10.10.0.5'),
  (106, 100, 'cb_admin', 'super_admin', 3, 'rls.create', 'rls_rule', '100', 'RLS-订单国家',
   'success', '新增行级安全策略', '{"table":"cb_orders","column":"site"}', '10.10.0.5'),
  (107, 101, 'cb_certifier', 'org_admin', 3, 'metric.certify', 'metric', '100', 'GMV 总销售额',
   'success', '完成指标认证', '{"caliber":"v2"}', '10.10.1.66'),
  (108, 102, 'cb_analyst', 'user', 3, 'dashboard.share', 'dashboard', '100', '跨境电商经营总览',
   'success', '公开分享看板', '{"is_public":true,"token":"cb_dash_overview_a1b2c3"}', '10.10.1.23'),
  (109, 103, 'cb_seller', 'user', 3, 'query.execute', 'query', '103', '哪个品类客单价最高？',
   'success', '智能问数执行SQL成功', '{"sql":"SELECT p.category...","cost_ms":640}', '10.10.2.88'),
  (110, 104, 'cb_viewer', 'user', 3, 'login', 'session', NULL, NULL, 'success',
   '用户登录成功', '{"method":"password"}', '10.10.3.12')
ON CONFLICT (id) DO NOTHING;

-- 06.3 访问申请（数据资源访问审批流）
INSERT INTO access_requests
  (id, requester_id, resource_type, resource_id, resource_name, reason, status,
   reviewer_id, review_comment, reviewed_at, org_id)
VALUES
  (100, 103, 'dataset', 101, '跨境电商月度KPI', '需要月度KPI数据支撑运营周报', 'approved',
   102, '同意，注意数据仅限内部使用。', NOW() - INTERVAL '3 days', 3),
  (101, 104, 'dataset', 100, '跨境电商订单分析', '财务对账需要订单明细数据', 'approved',
   100, '已开通只读权限。', NOW() - INTERVAL '1 day', 3),
  (102, 104, 'datasource', 6, '跨海优选-电商主库', '申请直接访问数据源执行自定义分析', 'pending',
   NULL, NULL, NULL, 3),
  (103, 103, 'dashboard', 102, '物流时效监控', '物流团队需要该看板协作', 'rejected',
   102, '物流看板权限已通过共享列表配置，无需单独申请。', NOW() - INTERVAL '5 days', 3)
ON CONFLICT (id) DO NOTHING;

-- 06.4 Webhook 订阅（数据变更/告警事件推送）
INSERT INTO webhook_subscriptions
  (id, org_id, name, target_url, events, secret, enabled, created_by)
VALUES
  (100, 3, '告警事件→企业微信机器人', 'https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=crossborder-alert',
   '["alert.triggered","alert.resolved"]', 'whsec_cb_alert_9f8a', 1, 102),
  (101, 3, '数据资产变更→钉钉群', 'https://oapi.dingtalk.com/robot/send?access_token=cb_asset_ding',
   '["asset.published","asset.updated","dataset.refreshed"]', 'whsec_cb_asset_7d2b', 1, 102)
ON CONFLICT (id) DO NOTHING;

-- 06.5 消息通知设置（邮件/企微/钉钉开关）
INSERT INTO notification_settings
  (id, email_enabled, smtp_host, smtp_port, smtp_username, smtp_password, smtp_from,
   smtp_use_ssl, wechat_enabled, wechat_webhook_url, dingtalk_enabled, dingtalk_webhook_url,
   dingtalk_secret)
VALUES
  (1, TRUE, 'smtp.example.com', 465, 'noreply@kuahai.com', 'smtp_pass_demo', 'Smart BI <noreply@kuahai.com>',
   TRUE, TRUE, 'https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=crossborder-alert',
   TRUE, 'https://oapi.dingtalk.com/robot/send?access_token=cb_asset_ding', 'SEC_demo_secret')
ON CONFLICT (id) DO NOTHING;

-- 06.6 企业微信集成（外部组织绑定/身份映射/权限映射）
INSERT INTO integration_configs
  (id, provider, name, enabled, corp_id, agent_id, app_secret, callback_url, robot_webhook_url)
VALUES
  (100, 'wechat_work', '跨海优选企业微信', TRUE, 'ww_crossborder_corp', '1000002',
   'demo_app_secret_wechat', 'https://bi.kuahai.com/api/integrations/wechat_work/callback',
   'https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=crossborder-alert'),
  (101, 'dingtalk', '跨海优选钉钉', FALSE, 'ding_crossborder_corp', 'ding10001',
   'demo_app_secret_ding', 'https://bi.kuahai.com/api/integrations/dingtalk/callback',
   'https://oapi.dingtalk.com/robot/send?access_token=cb_asset_ding')
ON CONFLICT (id) DO NOTHING;

INSERT INTO external_org_bindings (id, provider, external_corp_id, org_id)
VALUES
  (100, 'wechat_work', 'ww_crossborder_corp', 3)
ON CONFLICT (id) DO NOTHING;

INSERT INTO external_identities
  (id, provider, external_corp_id, external_user_id, user_id, display_name, email,
   mobile, department_ids_json, last_login_at)
VALUES
  (100, 'wechat_work', 'ww_crossborder_corp', 'wxu_zhangwei', 102, '张伟', 'zhangwei@kuahai.com',
   '13800000001', '["100"]', NOW() - INTERVAL '1 day'),
  (101, 'wechat_work', 'ww_crossborder_corp', 'wxu_liting', 103, '李婷', 'liting@kuahai.com',
   '13800000002', '["101"]', NOW() - INTERVAL '2 days')
ON CONFLICT (id) DO NOTHING;

INSERT INTO external_permission_mappings
  (id, provider, external_corp_id, external_department_id, org_id, role, data_scope,
   menu_permissions, action_permissions, priority, enabled)
VALUES
  (100, 'wechat_work', 'ww_crossborder_corp', '100', 3, 'org_admin', 'all',
   '[{"title":"经营总览","key":"dashboard","children":[]},{"title":"系统管理","key":"admin","children":[]}]',
   '["*"]', 100, TRUE),
  (101, 'wechat_work', 'ww_crossborder_corp', '101', 3, 'user', 'dept',
   '[{"title":"经营总览","key":"dashboard","children":[]}]',
   '["dashboard:view","chat:ask"]', 200, TRUE)
ON CONFLICT (id) DO NOTHING;

-- 06.7 消息投递记录（告警/报告经企微/钉钉/邮件分发）
INSERT INTO message_deliveries
  (id, provider, channel, event_type, recipient_user_id, recipient_external_user_id,
   org_id, title, content, link_url, status, error_message, retry_count, sent_at)
VALUES
  (100, 'wechat_work', 'wechat', 'alert.triggered', 103, 'wxu_liting', 3,
   '德国站退款率异常预警', '德国站近7天退款率 5.6%，超过阈值 5%，请及时处理。',
   'https://bi.kuahai.com/alerts/100', 'success', NULL, 0, NOW() - INTERVAL '2 days'),
  (101, 'wechat_work', 'wechat', 'alert.triggered', 103, 'wxu_liting', 3,
   '物流异常率监控', '近24小时物流异常率 6.1%，涉及DHL与4PX渠道。',
   'https://bi.kuahai.com/alerts/102', 'success', NULL, 0, NOW() - INTERVAL '5 hours'),
  (102, 'dingtalk', 'dingtalk', 'report.delivered', NULL, NULL, 3,
   '广告投放周报', '本周广告周报已生成，请查收。', 'https://bi.kuahai.com/reports/101',
   'success', NULL, 0, NOW() - INTERVAL '6 days'),
  (103, 'smtp', 'email', 'report.delivered', NULL, NULL, 3,
   '跨境电商销售日报', '每日销售日报已发送。', NULL,
   'success', NULL, 0, NOW() - INTERVAL '8 hours'),
  (104, 'wechat_work', 'wechat', 'alert.triggered', 102, 'wxu_zhangwei', 3,
   '月度GMV目标达成预警', '本月GMV 241万，距离280万目标尚有差距。',
   'https://bi.kuahai.com/alerts/103', 'success', NULL, 0, NOW() - INTERVAL '3 days'),
  (105, 'dingtalk', 'dingtalk', 'alert.triggered', 103, NULL, 3,
   '物流异常率监控', '物流异常率告警（钉钉通知）', NULL,
   'failed', 'timeout: 请求钉钉接口超时', 2, NULL)
ON CONFLICT (id) DO NOTHING;

-- 06.8 数据连接（ERP/WMS 等业务系统连接器）
INSERT INTO data_links
  (id, name, connector_type, config_json, status, last_test_at, last_test_message, org_id, created_by)
VALUES
  (100, '聚水潭ERP-订单同步', 'jushuitan',
   '{"endpoint":"https://open.jushuitan.com","app_key":"demo_jst_key","app_secret":"demo_jst_secret"}',
   'active', NOW() - INTERVAL '1 day', '连接成功，API 版本 v2', 3, 102),
  (101, '易仓WMS-库存同步', 'yicang',
   '{"endpoint":"https://open.ec-wms.com","app_id":"demo_yc_id","secret":"demo_yc_secret"}',
   'active', NOW() - INTERVAL '2 days', '连接成功，可同步库存与仓发数据', 3, 102),
  (102, '分销平台-商品数据', 'fenxiang',
   '{"endpoint":"https://open.fenxiang.com","token":"demo_fx_token"}',
   'error', NOW() - INTERVAL '5 days', '连接失败：API 凭据过期', 3, 103)
ON CONFLICT (id) DO NOTHING;

-- 06.9 数据同步任务与日志
INSERT INTO data_link_tasks
  (id, link_id, name, source_object, target_datasource_id, target_table, sync_mode,
   incremental_field, incremental_watermark, field_mapping_json, filter_json,
   cron_expression, is_active, last_run_at, last_run_status, last_run_records, org_id, created_by)
VALUES
  (100, 100, '订单数据同步', 'orders', 6, 'cb_orders', 'incremental',
   'modified', '2025-12-30 02:00:00',
   '[{"src":"oid","dst":"order_id","type":"string"},{"src":"amount","dst":"amount","type":"numeric"},{"src":"status","dst":"order_status","type":"string"}]',
   '{"status":"completed"}', '0 2 * * *', TRUE, NOW() - INTERVAL '2 hours', 'success', 12000, 3, 102),
  (101, 101, '库存同步', 'inventory', 6, 'cb_products', 'incremental',
   'sync_time', '2025-12-30 01:00:00',
   '[{"src":"sku","dst":"sku","type":"string"},{"src":"qty","dst":"stock_qty","type":"int"}]',
   NULL, '0 1 * * *', TRUE, NOW() - INTERVAL '2 hours', 'success', 20, 3, 102),
  (102, 102, '商品资料同步', 'products', 6, 'cb_products', 'full',
   NULL, NULL,
   '[{"src":"sku","dst":"sku","type":"string"},{"src":"name","dst":"product_name","type":"string"}]',
   NULL, '0 3 * * *', FALSE, NOW() - INTERVAL '5 days', 'error', 0, 3, 103)
ON CONFLICT (id) DO NOTHING;

INSERT INTO data_link_logs
  (id, task_id, link_id, status, records_read, records_written, records_failed,
   error_message, started_at, finished_at, org_id)
VALUES
  (100, 100, 100, 'success', 12000, 12000, 0, NULL,
   NOW() - INTERVAL '2 hours', NOW() - INTERVAL '2 hours' + INTERVAL '3 minutes', 3),
  (101, 101, 101, 'success', 20, 20, 0, NULL,
   NOW() - INTERVAL '2 hours', NOW() - INTERVAL '2 hours' + INTERVAL '1 minute', 3),
  (102, 102, 102, 'error', 0, 0, 0, 'API 凭据过期，401 Unauthorized',
   NOW() - INTERVAL '5 days', NOW() - INTERVAL '5 days' + INTERVAL '5 seconds', 3),
  (103, 100, 100, 'success', 11800, 11800, 2, NULL,
   NOW() - INTERVAL '2 days', NOW() - INTERVAL '2 days' + INTERVAL '3 minutes', 3)
ON CONFLICT (id) DO NOTHING;

-- 06.10 AI 报表（对话生成 HTML 报表快照，可分享）
INSERT INTO ai_reports
  (id, org_id, owner_id, title, html, conversation_json, status, share_token)
VALUES
  (100, 3, 102, '2025年12月跨境电商经营复盘',
   '<html><head><style>body{font-family:system-ui;padding:24px;color:#1f2937}h1{font-size:22px}h2{font-size:16px;border-left:4px solid #2563eb;padding-left:8px;margin-top:24px}table{border-collapse:collapse;width:100%}th,td{border:1px solid #e5e7eb;padding:8px;text-align:left}.kpi{display:flex;gap:16px;margin:16px 0}.card{flex:1;border:1px solid #e5e7eb;border-radius:8px;padding:16px}.card b{display:block;font-size:24px;color:#2563eb}</style></head><body><h1>2025年12月跨境电商经营复盘</h1><div class="kpi"><div class="card">GMV<b>$246万</b></div><div class="card">订单量<b>7,800</b></div><div class="card">退款率<b>3.4%</b></div><div class="card">广告ROI<b>4.2</b></div></div><h2>平台销售结构</h2><table><tr><th>平台</th><th>GMV</th><th>占比</th></tr><tr><td>Amazon</td><td>$132万</td><td>53.7%</td></tr><tr><td>TikTok</td><td>$58万</td><td>23.6%</td></tr><tr><td>Shopee</td><td>$41万</td><td>16.7%</td></tr><tr><td>独立站</td><td>$36万</td><td>14.6%</td></tr></table><h2>亮点与风险</h2><p><b>亮点：</b>TikTok渠道GMV同比增长65%，会员复购率提升8pp。</p><p><b>风险：</b>美国站12月GMV环比下滑12%，日本站客单价持续走低。</p></body></html>',
   '[{"role":"user","content":"生成一份12月经营复盘报表"},{"role":"assistant","content":"已生成12月经营复盘AI报表，覆盖经营概览、平台结构、广告、物流、会员五大板块。"}]',
   'published', 'cb_ai_report_5f8e2d'),
  (101, 3, 103, '2026年1月第一周销售周报',
   '<html><head><style>body{font-family:system-ui;padding:24px}h1{font-size:20px}table{border-collapse:collapse}th,td{border:1px solid #ddd;padding:6px}</style></head><body><h1>2026年1月第一周销售周报</h1><p>本周销售额 $82.4万，环比 +6.2%。美国站表现最佳。</p></body></html>',
   '[{"role":"user","content":"本周销售情况如何？做成周报"},{"role":"assistant","content":"已生成周报。"}]',
   'draft', NULL)
ON CONFLICT (id) DO NOTHING;

-- 06.11 Agent 运行记录（智能体执行历史）
INSERT INTO agent_runs
  (id, user_id, route, prompt, plan_json, execution_json, status)
VALUES
  (100, 102, 'text2sql', '各平台本月销售额是多少？',
   '{"steps":[{"step":1,"action":"identify_tables","detail":"定位cb_orders"},{"step":2,"action":"generate_sql"},{"step":3,"action":"execute_sql"},{"step":4,"action":"summarize"}]}',
   '{"sql":"SELECT o.platform, SUM(o.amount*(1-o.refund_flag)) AS gmv ...","rows":4,"cost_ms":830}',
   'completed'),
  (101, 102, 'drill', '按站点再细分看看',
   '{"steps":[{"step":1,"action":"inherit_context","detail":"parent_query=100"},{"step":2,"action":"add_dimension","detail":"site"},{"step":3,"action":"execute_sql"}]}',
   '{"sql":"SELECT o.site, SUM(...) FROM cb_orders o GROUP BY o.site ...","rows":4}',
   'completed'),
  (102, 103, 'report', '生成一份12月经营复盘报表',
   '{"steps":[{"step":1,"action":"collect_metrics"},{"step":2,"action":"render_html"},{"step":3,"action":"save_report"}]}',
   '{"report_id":100,"html_size":"18KB"}',
   'completed'),
  (103, 102, 'text2sql', '统计各站点退款金额Top5',
   '{"steps":[{"step":1,"action":"generate_sql"},{"step":2,"action":"execute_sql"}]}',
   '{"error":"SQL执行超时(10s)","retry":true}',
   'failed')
ON CONFLICT (id) DO NOTHING;

-- =====================================================================
-- 07. 序列重置（将各表自增序列调整到已用最大值之后）
-- =====================================================================
SELECT setval('cb_shops_shop_id_seq', (SELECT COALESCE(MAX(shop_id),1) FROM cb_shops));
SELECT setval('cb_monthly_kpi_kpi_id_seq', (SELECT COALESCE(MAX(kpi_id),1) FROM cb_monthly_kpi));
SELECT setval('organizations_id_seq', (SELECT COALESCE(MAX(id),1) FROM organizations));
SELECT setval('departments_id_seq', (SELECT COALESCE(MAX(id),1) FROM departments));
SELECT setval('users_id_seq', (SELECT COALESCE(MAX(id),1) FROM users));
SELECT setval('roles_id_seq', (SELECT COALESCE(MAX(id),1) FROM roles));
SELECT setval('datasources_id_seq', (SELECT COALESCE(MAX(id),1) FROM datasources));
SELECT setval('datasets_id_seq', (SELECT COALESCE(MAX(id),1) FROM datasets));
SELECT setval('dataset_refresh_logs_id_seq', (SELECT COALESCE(MAX(id),1) FROM dataset_refresh_logs));
SELECT setval('metrics_id_seq', (SELECT COALESCE(MAX(id),1) FROM metrics));
SELECT setval('query_history_id_seq', (SELECT COALESCE(MAX(id),1) FROM query_history));
SELECT setval('pinned_charts_id_seq', (SELECT COALESCE(MAX(id),1) FROM pinned_charts));
SELECT setval('dashboards_id_seq', (SELECT COALESCE(MAX(id),1) FROM dashboards));
SELECT setval('dashboard_comments_id_seq', (SELECT COALESCE(MAX(id),1) FROM dashboard_comments));
SELECT setval('analysis_views_id_seq', (SELECT COALESCE(MAX(id),1) FROM analysis_views));
SELECT setval('big_screens_id_seq', (SELECT COALESCE(MAX(id),1) FROM big_screens));
SELECT setval('embed_tokens_id_seq', (SELECT COALESCE(MAX(id),1) FROM embed_tokens));
SELECT setval('alerts_id_seq', (SELECT COALESCE(MAX(id),1) FROM alerts));
SELECT setval('alert_history_id_seq', (SELECT COALESCE(MAX(id),1) FROM alert_history));
SELECT setval('action_items_id_seq', (SELECT COALESCE(MAX(id),1) FROM action_items));
SELECT setval('scheduled_reports_id_seq', (SELECT COALESCE(MAX(id),1) FROM scheduled_reports));
SELECT setval('report_execution_logs_id_seq', (SELECT COALESCE(MAX(id),1) FROM report_execution_logs));
SELECT setval('report_templates_id_seq', (SELECT COALESCE(MAX(id),1) FROM report_templates));
SELECT setval('report_template_versions_id_seq', (SELECT COALESCE(MAX(id),1) FROM report_template_versions));
SELECT setval('report_runs_id_seq', (SELECT COALESCE(MAX(id),1) FROM report_runs));
SELECT setval('report_fill_records_id_seq', (SELECT COALESCE(MAX(id),1) FROM report_fill_records));
SELECT setval('data_pipelines_id_seq', (SELECT COALESCE(MAX(id),1) FROM data_pipelines));
SELECT setval('data_pipeline_runs_id_seq', (SELECT COALESCE(MAX(id),1) FROM data_pipeline_runs));
SELECT setval('data_pipeline_versions_id_seq', (SELECT COALESCE(MAX(id),1) FROM data_pipeline_versions));
SELECT setval('data_quality_rules_id_seq', (SELECT COALESCE(MAX(id),1) FROM data_quality_rules));
SELECT setval('catalog_categories_id_seq', (SELECT COALESCE(MAX(id),1) FROM catalog_categories));
SELECT setval('data_assets_id_seq', (SELECT COALESCE(MAX(id),1) FROM data_assets));
SELECT setval('asset_lineage_id_seq', (SELECT COALESCE(MAX(id),1) FROM asset_lineage));
SELECT setval('asset_subscriptions_id_seq', (SELECT COALESCE(MAX(id),1) FROM asset_subscriptions));
SELECT setval('asset_notifications_id_seq', (SELECT COALESCE(MAX(id),1) FROM asset_notifications));
SELECT setval('rls_rules_id_seq', (SELECT COALESCE(MAX(id),1) FROM rls_rules));
SELECT setval('access_requests_id_seq', (SELECT COALESCE(MAX(id),1) FROM access_requests));
SELECT setval('audit_logs_id_seq', (SELECT COALESCE(MAX(id),1) FROM audit_logs));
SELECT setval('webhook_subscriptions_id_seq', (SELECT COALESCE(MAX(id),1) FROM webhook_subscriptions));
SELECT setval('integration_configs_id_seq', (SELECT COALESCE(MAX(id),1) FROM integration_configs));
SELECT setval('external_org_bindings_id_seq', (SELECT COALESCE(MAX(id),1) FROM external_org_bindings));
SELECT setval('external_identities_id_seq', (SELECT COALESCE(MAX(id),1) FROM external_identities));
SELECT setval('external_permission_mappings_id_seq', (SELECT COALESCE(MAX(id),1) FROM external_permission_mappings));
SELECT setval('message_deliveries_id_seq', (SELECT COALESCE(MAX(id),1) FROM message_deliveries));
SELECT setval('data_links_id_seq', (SELECT COALESCE(MAX(id),1) FROM data_links));
SELECT setval('data_link_tasks_id_seq', (SELECT COALESCE(MAX(id),1) FROM data_link_tasks));
SELECT setval('data_link_logs_id_seq', (SELECT COALESCE(MAX(id),1) FROM data_link_logs));
SELECT setval('ai_reports_id_seq', (SELECT COALESCE(MAX(id),1) FROM ai_reports));
SELECT setval('agent_runs_id_seq', (SELECT COALESCE(MAX(id),1) FROM agent_runs));

COMMIT;

