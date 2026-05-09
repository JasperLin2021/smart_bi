-- MOCK DATA
-- Smart BI System - Comprehensive PostgreSQL Mock Data
-- Generated: 2026-05-08
-- DO NOT modify existing business records (orgs id=1-2, datasources id=1-5,
--   metrics id=1-10, dashboards id=1-4, catalog_categories id=1-4, data_assets id=1-17)

BEGIN;

-- ============================================================
-- 1. ORGANIZATION DEPARTMENT TREE
-- ============================================================

INSERT INTO departments (id, name, org_id, parent_id, sort_order)
VALUES
  (1,  '管理层',          1, NULL, 1),
  (2,  '生产运营部',      1, NULL, 2),
  (3,  '质量管理部',      1, NULL, 3),
  (4,  '数据分析部',      1, NULL, 4),
  (5,  'REPS3 产线组',   1, 2,    1),
  (6,  'RACK 产线组',    1, 2,    2),
  (7,  '管理层',          2, NULL, 1),
  (8,  '封测制造部',      2, NULL, 2),
  (9,  '质量工程部',      2, NULL, 3),
  (10, '数据平台部',      2, NULL, 4),
  (11, 'Die Attach 班组', 2, 8,    1),
  (12, 'Wire Bond 班组',  2, 8,    2)
ON CONFLICT (id) DO UPDATE SET
  name = EXCLUDED.name,
  org_id = EXCLUDED.org_id,
  parent_id = EXCLUDED.parent_id,
  sort_order = EXCLUDED.sort_order;

UPDATE users
SET
  department_id = CASE username
    WHEN 'nexteer_admin' THEN 1
    WHEN 'nexteer_certifier' THEN 3
    WHEN 'nexteer' THEN 4
    WHEN 'carsem_admin' THEN 7
    WHEN 'carsem_certifier' THEN 9
    WHEN 'carsem' THEN 10
    ELSE department_id
  END,
  department = CASE username
    WHEN 'nexteer_admin' THEN '管理层'
    WHEN 'nexteer_certifier' THEN '质量管理部'
    WHEN 'nexteer' THEN '数据分析部'
    WHEN 'carsem_admin' THEN '管理层'
    WHEN 'carsem_certifier' THEN '质量工程部'
    WHEN 'carsem' THEN '数据平台部'
    ELSE department
  END
WHERE username IN ('nexteer_admin','nexteer_certifier','nexteer','carsem_admin','carsem_certifier','carsem');

SELECT setval(pg_get_serial_sequence('departments', 'id'), GREATEST((SELECT MAX(id) FROM departments), 12), true);

-- ============================================================
-- 2. ADDITIONAL USERS (Nexteer org_id=1)
-- ============================================================

INSERT INTO users (id, username, hashed_password, role, org_id, department_id, department, data_scope, permission_override_enabled, menu_permissions, action_permissions)
VALUES
  (8,  'nexteer_analyst', '$2b$12$EixZaYVK1fsbw1ZfbX3OXePaWxn96p36WQoeG6Lruj3vjPGga31lW', 'user', 1, 4, '数据分析部', 'org', false, NULL, NULL),
  (9,  'nexteer_viewer',  '$2b$12$EixZaYVK1fsbw1ZfbX3OXePaWxn96p36WQoeG6Lruj3vjPGga31lW', 'user', 1, 4, '数据分析部', 'self', false, NULL, NULL)
ON CONFLICT (id) DO NOTHING;

-- ============================================================
-- 3. NOTIFICATION SETTINGS
-- ============================================================

INSERT INTO notification_settings
  (id, email_enabled, smtp_host, smtp_port, smtp_username, smtp_password, smtp_from, smtp_use_ssl,
   wechat_enabled, wechat_webhook_url,
   dingtalk_enabled, dingtalk_webhook_url, dingtalk_secret)
VALUES
  (1, true, 'smtp.exmail.qq.com', 465, 'bi-alert@nexteer-cn.com', 'MockSMTPPass@2026',
   'bi-alert@nexteer-cn.com', true,
   true, 'https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=mock-nexteer-wechat-key-2026',
   false, NULL, NULL)
ON CONFLICT (id) DO NOTHING;

-- ============================================================
-- 4. ALERTS (Nexteer, org context)
-- ============================================================

INSERT INTO alerts
  (id, name, datasource_id, metric_id, metric_name, time_range, time_range_unit,
   dimension_conditions, metric_conditions, check_period, check_period_unit,
   assignees, cc_users, notify_system, notify_email, notify_wechat, notify_dingtalk,
   email_recipients, content, is_active, created_by, auto_create_action_item, action_item_assignee_id,
   created_at, updated_at)
VALUES
  -- Alert 1: OEE预警 (auto creates action item)
  (1, 'OEE日均预警', 2, 2, 'OEE', 1, 'day',
   '[{"column":"LINE","operator":"=","value":"REPS3 Final"}]',
   '[{"metric":"OEE","operator":"<","value":85}]',
   1, 'hour',
   '[2, 6]', '[3]', true, true, true, false,
   'nexteer_admin@nexteer-cn.com,nexteer_certifier@nexteer-cn.com',
   'OEE低于85%预警：请相关责任人立即排查生产线异常，确认设备状态和人员配置。',
   true, 2, true, 6,
   NOW() - INTERVAL '60 days', NOW() - INTERVAL '60 days'),

  -- Alert 2: RTY预警
  (2, 'RTY良率预警', 2, NULL, 'RTY', 1, 'day',
   '[{"column":"SHIFTNAME","operator":"IN","value":"白班,夜班"}]',
   '[{"metric":"RTY","operator":"<","value":95}]',
   4, 'hour',
   '[2]', '[6]', true, true, false, false,
   'nexteer_admin@nexteer-cn.com',
   'RTY良率低于95%预警：直通率异常，请确认各工序NG情况并分析失效类型。',
   true, 2, false, NULL,
   NOW() - INTERVAL '55 days', NOW() - INTERVAL '55 days'),

  -- Alert 3: 日产出预警
  (3, '日产出不足预警', 2, 1, '产出', 1, 'day',
   '[{"column":"LINE","operator":"IN","value":"REPS3 Final,REPS3 BSI"}]',
   '[{"metric":"TOTALCOUNT","operator":"<","value":500}]',
   1, 'day',
   '[2, 3]', '[6]', true, false, true, false,
   NULL,
   '日产出低于500件预警：请确认排班计划是否按时执行，设备是否有异常停机。',
   true, 2, true, 3,
   NOW() - INTERVAL '50 days', NOW() - INTERVAL '50 days'),

  -- Alert 4: 蓝途销售预警 (datasource_id=4, metric_id=4)
  (4, '蓝途月销售额预警', 4, 4, '月销售额', 1, 'month',
   '[]',
   '[{"metric":"monthly_revenue","operator":"<","value":500000}]',
   1, 'day',
   '[2]', '[]', true, true, false, false,
   'nexteer_admin@nexteer-cn.com',
   '蓝途科技月销售额低于50万元预警：请销售团队分析原因并制定应对方案。',
   true, 2, false, NULL,
   NOW() - INTERVAL '45 days', NOW() - INTERVAL '45 days'),

  -- Alert 5: 夜班OEE专项预警
  (5, '夜班OEE专项预警', 2, 2, 'OEE', 1, 'day',
   '[{"column":"SHIFTNAME","operator":"=","value":"夜班"}]',
   '[{"metric":"OEE","operator":"<","value":80}]',
   2, 'hour',
   '[2, 6]', '[3]', true, true, true, false,
   'nexteer_admin@nexteer-cn.com,nexteer_certifier@nexteer-cn.com',
   '夜班OEE低于80%严重预警：夜班生产效率严重不足，请立即介入排查。',
   true, 2, true, 6,
   NOW() - INTERVAL '40 days', NOW() - INTERVAL '40 days'),

  -- Alert 6: RACK线NG率预警
  (6, 'RACK线NG率异常预警', 2, NULL, 'NG率', 7, 'day',
   '[{"column":"LINE","operator":"=","value":"REPS3 RACK"}]',
   '[{"metric":"ng_rate","operator":">","value":5}]',
   6, 'hour',
   '[2]', '[6, 3]', true, false, false, false,
   NULL,
   'REPS3 RACK线NG率超过5%预警：请质量工程师介入分析失效模式，确认是否需要批次隔离。',
   true, 2, false, NULL,
   NOW() - INTERVAL '35 days', NOW() - INTERVAL '35 days')
ON CONFLICT (id) DO NOTHING;

-- ============================================================
-- 5. ALERT HISTORY (15 records, last 30 days)
-- ============================================================

INSERT INTO alert_history
  (id, alert_id, alert_name, triggered_at, metric_value, condition_desc, notify_result, status)
VALUES
  (1,  1, 'OEE日均预警',       NOW() - INTERVAL '29 days 08:00', '82.3',  'OEE < 85%，当前值 82.3%，产线 REPS3 Final',    '{"system":true,"email":"success","wechat":"success"}', 'triggered'),
  (2,  2, 'RTY良率预警',       NOW() - INTERVAL '28 days 10:30', '93.1',  'RTY < 95%，当前值 93.1%',                       '{"system":true,"email":"success"}',                   'triggered'),
  (3,  3, '日产出不足预警',    NOW() - INTERVAL '27 days 09:00', '478',   'TOTALCOUNT < 500，当前值 478，REPS3 Final',       '{"system":true,"wechat":"success"}',                  'triggered'),
  (4,  1, 'OEE日均预警',       NOW() - INTERVAL '25 days 08:00', '88.7',  'OEE >= 85%，当前值 88.7%，产线 REPS3 Final',    '{"system":true,"email":"success","wechat":"success"}', 'normal'),
  (5,  5, '夜班OEE专项预警',   NOW() - INTERVAL '24 days 22:00', '76.5',  'OEE < 80%，当前值 76.5%，夜班',                 '{"system":true,"email":"success","wechat":"success"}', 'triggered'),
  (6,  2, 'RTY良率预警',       NOW() - INTERVAL '22 days 14:00', '96.2',  'RTY >= 95%，当前值 96.2%',                       '{"system":true,"email":"success"}',                   'normal'),
  (7,  6, 'RACK线NG率异常预警', NOW() - INTERVAL '21 days 16:00', '6.8',  'NG率 > 5%，当前值 6.8%，REPS3 RACK',            '{"system":true}',                                     'triggered'),
  (8,  1, 'OEE日均预警',       NOW() - INTERVAL '19 days 08:00', '79.4',  'OEE < 85%，当前值 79.4%，产线 REPS3 Final',    '{"system":true,"email":"success","wechat":"error"}',  'triggered'),
  (9,  3, '日产出不足预警',    NOW() - INTERVAL '17 days 09:00', '512',   'TOTALCOUNT >= 500，当前值 512，REPS3 Final',      '{"system":true,"wechat":"success"}',                  'normal'),
  (10, 4, '蓝途月销售额预警',  NOW() - INTERVAL '15 days 09:00', '423500','monthly_revenue < 500000，当前值 ¥423,500',      '{"system":true,"email":"success"}',                   'triggered'),
  (11, 5, '夜班OEE专项预警',   NOW() - INTERVAL '13 days 23:00', '83.1',  'OEE >= 80%，当前值 83.1%，夜班',                '{"system":true,"email":"success","wechat":"success"}', 'normal'),
  (12, 6, 'RACK线NG率异常预警', NOW() - INTERVAL '11 days 11:00', '7.3', 'NG率 > 5%，当前值 7.3%，REPS3 RACK',            '{"system":true}',                                     'triggered'),
  (13, 1, 'OEE日均预警',       NOW() - INTERVAL '8 days 08:00',  '84.9',  'OEE < 85%，当前值 84.9%，产线 REPS3 Final',    '{"system":true,"email":"success","wechat":"success"}', 'triggered'),
  (14, 2, 'RTY良率预警',       NOW() - INTERVAL '5 days 10:00',  '91.8',  'RTY < 95%，当前值 91.8%',                        '{"system":true,"email":"error"}',                     'triggered'),
  (15, 3, '日产出不足预警',    NOW() - INTERVAL '2 days 09:00',  '467',   'TOTALCOUNT < 500，当前值 467，REPS3 BSI',         '{"system":true,"wechat":"success"}',                  'triggered')
ON CONFLICT (id) DO NOTHING;

-- ============================================================
-- 6. ACTION ITEMS (12 items)
-- ============================================================

INSERT INTO action_items
  (id, title, description, source_type, source_id, source_payload,
   linked_metric_id, linked_dataset_id, linked_dashboard_id,
   owner_id, priority, due_date, status, outcome, org_id, created_by, closed_at, created_at, updated_at)
VALUES
  -- From alert (high priority, open)
  (1, 'REPS3 Final OEE下降根因分析',
   '2026-04-09 OEE降至82.3%，低于85%目标。需排查设备停机时间、换型时间和质量损失三大因素。',
   'alert', '1', '{"alert_id":1,"alert_name":"OEE日均预警","metric_value":"82.3","triggered_at":"2026-04-09T08:00:00"}',
   2, NULL, 1,
   6, 'high', '2026-05-15', 'open', NULL, 1, 2, NULL,
   NOW() - INTERVAL '29 days', NOW() - INTERVAL '29 days'),

  -- From alert (high priority, in_progress)
  (2, 'REPS3 RACK NG率超标整改',
   'RACK线NG率连续两次超过5%，需质量工程师排查失效模式，分析是否为批次性材料问题或工艺参数漂移。',
   'alert', '7', '{"alert_id":6,"alert_name":"RACK线NG率异常预警","metric_value":"6.8","triggered_at":"2026-04-17T16:00:00"}',
   NULL, NULL, NULL,
   2, 'high', '2026-05-12', 'in_progress',
   '已完成初步排查：确认为B批次轴承内径超差，已联系供应商更换，待确认改善效果。',
   1, 2, NULL,
   NOW() - INTERVAL '21 days', NOW() - INTERVAL '5 days'),

  -- From alert (medium, resolved)
  (3, '夜班OEE专项提升计划',
   '夜班OEE连续低于80%，需制定夜班专项改善计划，包括人员培训、预防性维护和夜班组长考核机制。',
   'alert', '5', '{"alert_id":5,"alert_name":"夜班OEE专项预警","metric_value":"76.5"}',
   2, NULL, 1,
   6, 'medium', '2026-04-30', 'resolved',
   '已制定夜班改善方案：增加关键工位OJT培训2次/周，调整PM计划至白班，夜班OEE已回升至83%以上。',
   1, 6, NOW() - INTERVAL '10 days',
   NOW() - INTERVAL '24 days', NOW() - INTERVAL '10 days'),

  -- From query (medium, in_progress)
  (4, 'REPS3 BSI产线产能瓶颈分析',
   '根据查询分析，BSI线日产出长期偏低，需识别瓶颈工位并制定产能提升方案。',
   'query', '15', '{"history_id":15,"question":"REPS3 BSI各工位CT分布分析"}',
   1, NULL, NULL,
   3, 'medium', '2026-05-20', 'in_progress', NULL, 1, 3, NULL,
   NOW() - INTERVAL '15 days', NOW() - INTERVAL '15 days'),

  -- Manual (low, open)
  (5, '更新生产数据看板图表配置',
   '当前Dashboard图表配色与公司VI规范不符，需统一调整为Nexteer标准蓝色系。',
   'manual', NULL, NULL,
   NULL, NULL, 2,
   8, 'low', '2026-05-30', 'open', NULL, 1, 2, NULL,
   NOW() - INTERVAL '12 days', NOW() - INTERVAL '12 days'),

  -- From alert (high, open)
  (6, '蓝途4月销售低迷分析与应对',
   '4月蓝途科技销售额42.35万，低于目标50万。需分析客户流失原因、竞品动态及渠道问题。',
   'alert', '10', '{"alert_id":4,"alert_name":"蓝途月销售额预警","metric_value":"423500"}',
   4, NULL, NULL,
   2, 'high', '2026-05-10', 'open', NULL, 1, 2, NULL,
   NOW() - INTERVAL '15 days', NOW() - INTERVAL '15 days'),

  -- Manual (medium, open)
  (7, '配置RTY指标异常自动化通知',
   'RTY告警当前仅系统内通知，需接入企业微信机器人实现实时推送，减少响应延迟。',
   'manual', NULL, NULL,
   NULL, NULL, NULL,
   2, 'medium', '2026-05-18', 'open', NULL, 1, 2, NULL,
   NOW() - INTERVAL '10 days', NOW() - INTERVAL '10 days'),

  -- From query (low, closed)
  (8, '核对4月各班次排班数据准确性',
   '发现查询结果中存在若干SHIFTSTARTTIME为NULL的记录，需与IE确认数据录入问题。',
   'query', '8', '{"history_id":8,"question":"4月各班次排班明细查询"}',
   NULL, NULL, NULL,
   9, 'low', '2026-04-25', 'closed',
   '已与MES系统管理员确认：涉及4条测试数据，已清除，正式数据无异常。',
   1, 3, NOW() - INTERVAL '20 days',
   NOW() - INTERVAL '30 days', NOW() - INTERVAL '20 days'),

  -- Manual (high, in_progress)
  (9, '制定OEE KPI考核机制',
   '将OEE指标纳入产线班组月度绩效考核，需与HR和生产部协商制定考核细则。',
   'manual', NULL, NULL,
   2, NULL, 1,
   6, 'high', '2026-05-31', 'in_progress', NULL, 1, 6, NULL,
   NOW() - INTERVAL '8 days', NOW() - INTERVAL '8 days'),

  -- From alert (medium, resolved)
  (10, 'RTY良率下降专项改善（5月第一周）',
   'RTY降至91.8%，需分析失效详情数据，识别TOP3失效模式并制定防错措施。',
   'alert', '14', '{"alert_id":2,"alert_name":"RTY良率预警","metric_value":"91.8"}',
   NULL, NULL, NULL,
   2, 'medium', '2026-05-12', 'resolved',
   '分析结果：主要失效模式为打孔毛刺（占比38%）和螺纹滑牙（占比27%）。已更换钻头并调整扭矩参数，RTY回升至95.5%。',
   1, 2, NOW() - INTERVAL '2 days',
   NOW() - INTERVAL '5 days', NOW() - INTERVAL '2 days'),

  -- Manual (low, open)
  (11, '整理并归档2026年Q1生产报告',
   '将Q1各月OEE、RTY、产出数据整理成标准模板并上传至数据目录，便于历史对比分析。',
   'manual', NULL, NULL,
   NULL, NULL, NULL,
   8, 'low', '2026-05-31', 'open', NULL, 1, 2, NULL,
   NOW() - INTERVAL '3 days', NOW() - INTERVAL '3 days'),

  -- From query (medium, open)
  (12, '验证REPS3 Pinion线产出数据异常',
   '5月初查询发现Pinion线单日TOTALCOUNT出现3次超过2000件的异常高值，疑似数据重复录入。',
   'query', '20', '{"history_id":20,"question":"REPS3 Pinion线近期产出趋势"}',
   1, NULL, NULL,
   3, 'medium', '2026-05-14', 'open', NULL, 1, 3, NULL,
   NOW() - INTERVAL '1 day', NOW() - INTERVAL '1 day')
ON CONFLICT (id) DO NOTHING;

-- ============================================================
-- 7. SCHEDULED REPORTS (4 reports)
-- ============================================================

INSERT INTO scheduled_reports
  (id, name, datasource_id, question, cron_expression,
   notify_email, notify_wechat, notify_dingtalk, email_recipients,
   is_active, created_by, last_run_at, created_at, updated_at)
VALUES
  -- Daily OEE report (weekdays 8:30am)
  (1, '每日OEE生产报告', 2,
   '请分析昨日各产线的OEE、RTY和TOTALCOUNT，按产线和班次分组，标注异常值并给出趋势判断。',
   '30 8 * * 1-5',
   true, true, false,
   'nexteer_admin@nexteer-cn.com,nexteer_certifier@nexteer-cn.com',
   true, 2, NOW() - INTERVAL '1 day 08:30', NOW() - INTERVAL '45 days', NOW() - INTERVAL '1 day'),

  -- Weekly sales summary (Monday 9am)
  (2, '每周蓝途销售汇总', 4,
   '请汇总本周各产品线的销售额、订单量、客户数，与上周对比，列出表现最好和最差的产品，并给出销售建议。',
   '0 9 * * 1',
   true, false, false,
   'nexteer_admin@nexteer-cn.com',
   true, 2, NOW() - INTERVAL '7 days 09:00', NOW() - INTERVAL '40 days', NOW() - INTERVAL '7 days'),

  -- Monthly RTY report (1st of month 7am)
  (3, '月度RTY良率分析报告', 2,
   '请生成上月各产线RTY良率的完整分析：按产线、班次、零件号分组统计，分析TOP5失效类型占比，与目标95%对比，输出改善建议。',
   '0 7 1 * *',
   true, true, false,
   'nexteer_admin@nexteer-cn.com,nexteer_certifier@nexteer-cn.com',
   true, 2, NOW() - INTERVAL '7 days 07:00', NOW() - INTERVAL '38 days', NOW() - INTERVAL '7 days'),

  -- Production trend (weekdays 5:30pm)
  (4, '生产趋势日报', 2,
   '请分析今日生产数据：输出各产线当班产出与计划的完成率，OEE趋势图数据，识别当日最大损失来源（停机/质量/速度），给出次日关注点。',
   '30 17 * * 1-5',
   true, true, false,
   'nexteer_admin@nexteer-cn.com',
   true, 2, NOW() - INTERVAL '1 day 17:30', NOW() - INTERVAL '30 days', NOW() - INTERVAL '1 day')
ON CONFLICT (id) DO NOTHING;

-- ============================================================
-- 8. REPORT EXECUTION LOGS (20 logs, last 14 days)
-- ============================================================

INSERT INTO report_execution_logs
  (id, report_id, report_name, status, content_preview, notify_result, error_message, run_at, org_id)
VALUES
  -- Report 1: Daily OEE (last 10 weekdays)
  (1,  1, '每日OEE生产报告', 'success',
   '## 2026-04-25 各产线OEE日报\n\n| 产线 | 班次 | OEE | RTY | 产出 |\n|------|------|-----|-----|------|\n| REPS3 Final | 白班 | 88.2% | 96.3% | 312 |\n| REPS3 Final | 夜班 | 83.5% | 94.8% | 298 |\n| REPS3 BSI | 白班 | 91.1% | 97.2% | 276 |\n\n**趋势判断**：REPS3 Final夜班OEE持续低于85%目标，建议重点关注。',
   '{"email":"success","wechat":"success"}', NULL, NOW() - INTERVAL '13 days 08:30', 1),

  (2,  1, '每日OEE生产报告', 'success',
   '## 2026-04-28 各产线OEE日报\n\n| 产线 | 班次 | OEE | RTY | 产出 |\n|------|------|-----|-----|------|\n| REPS3 Final | 白班 | 86.9% | 95.8% | 318 |\n| REPS3 BSI | 白班 | 89.3% | 96.7% | 281 |\n| REPS3 RACK | 白班 | 78.4% | 92.1% | 203 |\n\n**趋势判断**：REPS3 RACK RTY持续异常，需重点排查。',
   '{"email":"success","wechat":"success"}', NULL, NOW() - INTERVAL '10 days 08:30', 1),

  (3,  1, '每日OEE生产报告', 'error',
   NULL,
   '{"email":"error","wechat":"error"}',
   'Datasource connection timeout: Excel file locked by another process (mainrecord.xlsx)',
   NOW() - INTERVAL '9 days 08:30', 1),

  (4,  1, '每日OEE生产报告', 'success',
   '## 2026-04-30 各产线OEE日报\n\n全线OEE表现良好，REPS3 Final白班OEE达到91.4%，为本月最高值。REPS3 RACK整改措施生效，RTY回升至95.2%。',
   '{"email":"success","wechat":"success"}', NULL, NOW() - INTERVAL '8 days 08:30', 1),

  (5,  1, '每日OEE生产报告', 'success',
   '## 2026-05-06 各产线OEE日报\n\n| 产线 | 班次 | OEE | RTY | 产出 |\n|------|------|-----|-----|------|\n| REPS3 Final | 白班 | 87.6% | 96.1% | 308 |\n| REPS3 BSI | 夜班 | 79.2% | 93.4% | 261 |\n\n**关注**：BSI夜班OEE低于80%警戒线。',
   '{"email":"success","wechat":"success"}', NULL, NOW() - INTERVAL '2 days 08:30', 1),

  (6,  1, '每日OEE生产报告', 'success',
   '## 2026-05-07 各产线OEE日报\n\n整体运行平稳，所有产线OEE均高于85%目标。REPS3 Final白班OEE 90.3%，夜班85.7%。建议继续保持。',
   '{"email":"success","wechat":"success"}', NULL, NOW() - INTERVAL '1 day 08:30', 1),

  -- Report 2: Weekly Sales (last 2 Mondays)
  (7,  2, '每周蓝途销售汇总', 'success',
   '## 2026-04-27 周销售汇总（4月第4周）\n\n本周销售额：¥127,450，环比上周下降8.3%。\n\n**表现最好**：转向管柱总成（¥52,300，占比41%）\n**表现最差**：电动助力模块（¥18,200，较上周-22%）\n\n**建议**：重点跟进3家流失客户，推进季末促单。',
   '{"email":"success"}', NULL, NOW() - INTERVAL '11 days 09:00', 1),

  (8,  2, '每周蓝途销售汇总', 'success',
   '## 2026-05-04 周销售汇总（5月第1周）\n\n本周销售额：¥143,800，环比上周增长12.9%。劳动节后订单恢复，转向系统总成表现突出。\n\n**新客户**：2家新签，贡献¥28,600。',
   '{"email":"success"}', NULL, NOW() - INTERVAL '4 days 09:00', 1),

  -- Report 3: Monthly RTY (1st of month)
  (9,  3, '月度RTY良率分析报告', 'success',
   '## 2026年4月 RTY月度分析报告\n\n**全月平均RTY**：94.7%（目标95%，略低于目标）\n\n### TOP5 失效类型\n1. 打孔毛刺：38.2%\n2. 螺纹滑牙：27.1%\n3. 端面划痕：14.6%\n4. 尺寸超差：11.3%\n5. 焊缝不良：8.8%\n\n### 改善建议\n- 更换REPS3 Final打孔工位钻头（已执行）\n- 增加螺纹检具100%检验',
   '{"email":"success","wechat":"success"}', NULL, NOW() - INTERVAL '7 days 07:00', 1),

  (10, 3, '月度RTY良率分析报告', 'success',
   '## 2026年3月 RTY月度分析报告\n\n**全月平均RTY**：95.8%（目标95%，达成）\n\n3月整体良率达标，REPS3 BSA和REPS3 Pinion表现优异，均超过97%。REPS3 RACK为短板，需持续关注。',
   '{"email":"success","wechat":"success"}', NULL, NOW() - INTERVAL '37 days 07:00', 1),

  -- Report 4: Production Trend Daily (last 8 weekdays)
  (11, 4, '生产趋势日报', 'success',
   '## 2026-04-25 生产趋势日报\n\n今日完成率：96.3%（计划1250件，实际1204件）。最大损失源：计划性停机（换型）占比52%。次日关注：REPS3 RACK换型效率提升。',
   '{"email":"success","wechat":"success"}', NULL, NOW() - INTERVAL '13 days 17:30', 1),

  (12, 4, '生产趋势日报', 'success',
   '## 2026-04-28 生产趋势日报\n\n今日完成率：88.2%（计划1250件，实际1103件），低于目标。主要损失：REPS3 RACK设备故障停机2.3小时。次日关注：确认维修状态。',
   '{"email":"success","wechat":"success"}', NULL, NOW() - INTERVAL '10 days 17:30', 1),

  (13, 4, '生产趋势日报', 'error',
   NULL,
   '{"email":"error"}',
   'LLM API timeout after 30s: model did not respond in time',
   NOW() - INTERVAL '9 days 17:30', 1),

  (14, 4, '生产趋势日报', 'success',
   '## 2026-04-30 生产趋势日报\n\n月末冲刺！今日完成率：103.6%（计划1250件，实际1295件）。各线均超计划，OEE全线高于88%。月末绩效良好。',
   '{"email":"success","wechat":"success"}', NULL, NOW() - INTERVAL '8 days 17:30', 1),

  (15, 4, '生产趋势日报', 'success',
   '## 2026-05-06 生产趋势日报\n\n今日完成率：91.4%。REPS3 BSI夜班OEE偏低拉低整体指标。次日关注：BSI夜班人员配置及设备PM状态。',
   '{"email":"success","wechat":"success"}', NULL, NOW() - INTERVAL '2 days 17:30', 1),

  (16, 4, '生产趋势日报', 'success',
   '## 2026-05-07 生产趋势日报\n\n今日完成率：98.7%。各线运行平稳，OEE均高于85%。REPS3 Final白班创本周最高记录（OEE 90.3%）。',
   '{"email":"success","wechat":"success"}', NULL, NOW() - INTERVAL '1 day 17:30', 1),

  (17, 1, '每日OEE生产报告', 'success',
   '## 2026-05-05 各产线OEE日报\n\n劳动节后首个工作日，生产恢复正常节奏。REPS3 Final OEE 86.8%，RTY 95.9%。',
   '{"email":"success","wechat":"success"}', NULL, NOW() - INTERVAL '3 days 08:30', 1),

  (18, 2, '每周蓝途销售汇总', 'error',
   NULL,
   '{"email":"error"}',
   'Datasource query failed: column "product_line" does not exist in sheet "sales_q1"',
   NOW() - INTERVAL '18 days 09:00', 1),

  (19, 3, '月度RTY良率分析报告', 'error',
   NULL,
   '{"email":"error","wechat":"error"}',
   'LLM context length exceeded: query result too large (>32k tokens)',
   NOW() - INTERVAL '37 days 07:05', 1),

  (20, 4, '生产趋势日报', 'success',
   '## 2026-04-29 生产趋势日报\n\n今日完成率：94.1%（计划1250件，实际1177件）。小幅欠产，主因为Pinion线早班换型延误。次日建议：优化换型SOP，目标缩短换型时间20%。',
   '{"email":"success","wechat":"success"}', NULL, NOW() - INTERVAL '9 days 17:30', 1)
ON CONFLICT (id) DO NOTHING;

-- ============================================================
-- 9. QUERY HISTORY (20 queries)
-- ============================================================

INSERT INTO query_history
  (id, user_id, datasource_id, parent_history_id, question, created_at, favorite,
   sql_query, result_json, summary, mode, drill_context, llm_model,
   is_insight, insight_title, org_id)
VALUES
  -- user_id=2 (nexteer_admin) queries
  (1, 2, 2, NULL,
   '昨日REPS3 Final产线OEE和RTY分别是多少？',
   NOW() - INTERVAL '28 days', true,
   'SELECT SHIFTNAME, AVG(OEE) as avg_oee, AVG(RTY) as avg_rty, SUM(TOTALCOUNT) as total_count FROM mainrecord WHERE LINE = ''REPS3 Final'' AND SHIFTSTARTTIME >= CURRENT_DATE - INTERVAL ''1 day'' GROUP BY SHIFTNAME ORDER BY SHIFTNAME',
   '[{"SHIFTNAME":"夜班","avg_oee":83.52,"avg_rty":94.83,"total_count":298},{"SHIFTNAME":"白班","avg_oee":88.21,"avg_rty":96.31,"total_count":312}]',
   'REPS3 Final昨日白班OEE 88.2%、RTY 96.3%，表现达标；夜班OEE 83.5%低于85%目标，RTY 94.8%略低于95%目标，需关注夜班生产效率。',
   'nl2sql', NULL, 'gpt-4o',
   false, NULL, 1),

  (2, 2, 2, NULL,
   '本月各产线的平均OEE排名',
   NOW() - INTERVAL '25 days', true,
   'SELECT LINE, AVG(OEE) as avg_oee, COUNT(*) as shift_count FROM mainrecord WHERE SHIFTSTARTTIME >= DATE_TRUNC(''month'', CURRENT_DATE) GROUP BY LINE ORDER BY avg_oee DESC',
   '[{"LINE":"REPS3 BSA","avg_oee":92.4,"shift_count":42},{"LINE":"REPS3 Pinion","avg_oee":90.1,"shift_count":38},{"LINE":"REPS3 Final","avg_oee":87.3,"shift_count":89},{"LINE":"REPS3 BSI","avg_oee":85.9,"shift_count":47},{"LINE":"REPS3 RACK","avg_oee":79.2,"shift_count":35}]',
   '本月OEE排名：BSA(92.4%)>Pinion(90.1%)>Final(87.3%)>BSI(85.9%)>RACK(79.2%)。RACK线明显低于其他产线，建议重点投入改善资源。',
   'nl2sql', NULL, 'gpt-4o',
   true, '本月各产线OEE对比：RACK线为最大短板', 1),

  (3, 2, 2, 2,
   '为什么REPS3 RACK的OEE这么低？帮我钻取分析',
   NOW() - INTERVAL '25 days', false,
   'SELECT SHIFTNAME, AVG(OEE) as avg_oee, AVG(RTY) as avg_rty, COUNT(*) as records FROM mainrecord WHERE LINE = ''REPS3 RACK'' AND SHIFTSTARTTIME >= DATE_TRUNC(''month'', CURRENT_DATE) GROUP BY SHIFTNAME ORDER BY avg_oee ASC',
   '[{"SHIFTNAME":"夜班","avg_oee":72.1,"avg_rty":90.3,"records":17},{"SHIFTNAME":"白班","avg_oee":84.8,"avg_rty":93.8,"records":18}]',
   'RACK线OEE低的主要原因在于夜班：夜班OEE仅72.1%，RTY 90.3%，均远低于白班水平。夜班人员技能和设备状态是关键因素。',
   'drill', '{"parent_id":2,"drill_type":"breakdown","dimension":"SHIFTNAME"}', 'gpt-4o',
   false, NULL, 1),

  (4, 2, 4, NULL,
   '蓝途科技本季度各产品销售额汇总',
   NOW() - INTERVAL '22 days', true,
   'SELECT product_category, SUM(revenue) as total_revenue, COUNT(order_id) as order_count FROM sales WHERE order_date >= ''2026-01-01'' GROUP BY product_category ORDER BY total_revenue DESC',
   '[{"product_category":"转向管柱总成","total_revenue":652300,"order_count":423},{"product_category":"电动助力模块","total_revenue":318700,"order_count":187},{"product_category":"传动轴","total_revenue":241500,"order_count":312}]',
   'Q1蓝途销售总额¥121.25万，转向管柱总成占比53.8%为主力产品，电动助力模块增长潜力大但订单量偏少。',
   'nl2sql', NULL, 'gpt-4o',
   true, 'Q1销售结构分析：转向管柱总成独大，需培育第二增长极', 1),

  -- user_id=3 (nexteer user) queries
  (5, 3, 2, NULL,
   '白班和夜班的RTY差异对比',
   NOW() - INTERVAL '20 days', false,
   'SELECT SHIFTNAME, AVG(RTY) as avg_rty, STDDEV(RTY) as stddev_rty, MIN(RTY) as min_rty, MAX(RTY) as max_rty FROM mainrecord GROUP BY SHIFTNAME',
   '[{"SHIFTNAME":"夜班","avg_rty":93.82,"stddev_rty":3.41,"min_rty":82.1,"max_rty":98.3},{"SHIFTNAME":"白班","avg_rty":95.94,"stddev_rty":1.87,"min_rty":90.2,"max_rty":99.1}]',
   '白班RTY平均95.9%，波动小（标准差1.87）；夜班RTY平均93.8%，波动大（标准差3.41），最低值仅82.1%。夜班稳定性亟待改善。',
   'nl2sql', NULL, 'gpt-4o',
   false, NULL, 1),

  (6, 3, 2, NULL,
   '近7天每日产出趋势',
   NOW() - INTERVAL '18 days', true,
   'SELECT DATE(SHIFTSTARTTIME) as shift_date, SUM(TOTALCOUNT) as daily_output FROM mainrecord WHERE SHIFTSTARTTIME >= CURRENT_DATE - INTERVAL ''7 days'' GROUP BY DATE(SHIFTSTARTTIME) ORDER BY shift_date',
   '[{"shift_date":"2026-04-18","daily_output":1187},{"shift_date":"2026-04-19","daily_output":1203},{"shift_date":"2026-04-20","daily_output":1156},{"shift_date":"2026-04-21","daily_output":1284},{"shift_date":"2026-04-22","daily_output":1319},{"shift_date":"2026-04-25","daily_output":1204},{"shift_date":"2026-04-26","daily_output":1231}]',
   '近7天日均产出1227件，4月22日最高（1319件），4月20日最低（1156件）。整体趋势稳中有升，周五产出明显较高。',
   'nl2sql', NULL, 'gpt-4o',
   false, NULL, 1),

  (7, 3, 2, 6,
   '产出最低的那天，各产线分布如何？',
   NOW() - INTERVAL '18 days', false,
   'SELECT LINE, SUM(TOTALCOUNT) as line_output, AVG(OEE) as avg_oee FROM mainrecord WHERE DATE(SHIFTSTARTTIME) = ''2026-04-20'' GROUP BY LINE ORDER BY line_output ASC',
   '[{"LINE":"REPS3 RACK","line_output":178,"avg_oee":72.3},{"LINE":"REPS3 BSI","line_output":241,"avg_oee":81.4},{"LINE":"REPS3 Final","line_output":301,"avg_oee":84.7},{"LINE":"REPS3 BSA","line_output":198,"avg_oee":88.2},{"LINE":"REPS3 Pinion","line_output":238,"avg_oee":85.9}]',
   '4月20日产出低迷主因：RACK线产出仅178件（OEE 72.3%），当日该线疑有设备故障，需结合停机记录确认。',
   'drill', '{"parent_id":6,"drill_type":"breakdown","date":"2026-04-20"}', 'gpt-4o',
   false, NULL, 1),

  -- user_id=8 (nexteer_analyst) queries
  (8, 8, 2, NULL,
   '4月各班次排班明细查询',
   NOW() - INTERVAL '16 days', false,
   'SELECT SHIFTNAME, SHIFTSTARTTIME, SHIFTENDTIME, LINE, PARTNO, STAFFNUM FROM mainrecord WHERE SHIFTSTARTTIME >= ''2026-04-01'' AND SHIFTSTARTTIME < ''2026-05-01'' ORDER BY SHIFTSTARTTIME LIMIT 100',
   '[{"SHIFTNAME":"白班","SHIFTSTARTTIME":"2026-04-01T08:00:00","SHIFTENDTIME":"2026-04-01T20:00:00","LINE":"REPS3 Final","PARTNO":"REP-001","STAFFNUM":12}]',
   '4月共查询到847条排班记录，发现4条SHIFTSTARTTIME为NULL的异常记录（疑为测试数据），其余数据完整。',
   'nl2sql', NULL, 'gpt-4o',
   false, NULL, 1),

  (9, 8, 2, NULL,
   'REPS3 Final各零件号产出占比分析',
   NOW() - INTERVAL '14 days', true,
   'SELECT PARTNO, SUM(TOTALCOUNT) as total, SUM(TOTALCOUNT) * 100.0 / SUM(SUM(TOTALCOUNT)) OVER () as pct FROM mainrecord WHERE LINE = ''REPS3 Final'' GROUP BY PARTNO ORDER BY total DESC',
   '[{"PARTNO":"REP-001","total":4823,"pct":38.2},{"PARTNO":"REP-002","total":3641,"pct":28.8},{"PARTNO":"REP-003","total":2187,"pct":17.3},{"PARTNO":"REP-004","total":1964,"pct":15.5},{"PARTNO":"OTHER","total":26,"pct":0.2}]',
   'REPS3 Final产出以REP-001和REP-002为主（合计67%），长尾零件数量极少。建议重点关注主料号的工艺稳定性。',
   'nl2sql', NULL, 'gpt-4o',
   true, 'REPS3 Final料号结构：TOP2料号贡献67%产出', 1),

  (10, 8, 2, NULL,
   'OEE与STAFFNUM的相关性分析',
   NOW() - INTERVAL '12 days', false,
   'SELECT STAFFNUM, ROUND(AVG(OEE)::numeric, 2) as avg_oee, COUNT(*) as record_count FROM mainrecord GROUP BY STAFFNUM ORDER BY STAFFNUM',
   '[{"STAFFNUM":8,"avg_oee":81.3,"record_count":23},{"STAFFNUM":10,"avg_oee":85.7,"record_count":67},{"STAFFNUM":12,"avg_oee":89.4,"record_count":142},{"STAFFNUM":14,"avg_oee":91.2,"record_count":38}]',
   '人员数量与OEE呈正相关：12人时OEE 89.4%表现最均衡（占比最高），8人时OEE仅81.3%。建议保证各班次不低于10人配置。',
   'nl2sql', NULL, 'gpt-4o',
   true, '人员配置与OEE正相关：建议不低于10人/班', 1),

  -- user_id=2 more queries
  (11, 2, 2, NULL,
   '哪个产线的OEE改善幅度最大（近30天 vs 上个30天）？',
   NOW() - INTERVAL '10 days', true,
   'SELECT LINE, AVG(CASE WHEN SHIFTSTARTTIME >= CURRENT_DATE - 30 THEN OEE END) as recent_oee, AVG(CASE WHEN SHIFTSTARTTIME < CURRENT_DATE - 30 THEN OEE END) as prev_oee FROM mainrecord GROUP BY LINE',
   '[{"LINE":"REPS3 RACK","recent_oee":82.1,"prev_oee":75.3},{"LINE":"REPS3 BSI","recent_oee":88.4,"prev_oee":86.9},{"LINE":"REPS3 Final","recent_oee":87.8,"prev_oee":87.2}]',
   'REPS3 RACK改善幅度最大（+6.8%），整改措施初显成效，但仍低于85%目标。持续跟进。',
   'nl2sql', NULL, 'gpt-4o',
   false, NULL, 1),

  (12, 2, 4, NULL,
   '蓝途科技哪个客户贡献销售额最高？',
   NOW() - INTERVAL '8 days', true,
   'SELECT customer_name, SUM(revenue) as total_revenue, COUNT(DISTINCT order_id) as orders FROM sales GROUP BY customer_name ORDER BY total_revenue DESC LIMIT 10',
   '[{"customer_name":"长城汽车","total_revenue":328900,"orders":87},{"customer_name":"奇瑞汽车","total_revenue":241300,"orders":63},{"customer_name":"理想汽车","total_revenue":187400,"orders":41}]',
   'TOP3客户：长城汽车（¥32.89万）、奇瑞汽车（¥24.13万）、理想汽车（¥18.74万），合计占总销售额65%。客户集中度较高，存在风险。',
   'nl2sql', NULL, 'gpt-4o',
   true, '蓝途TOP3客户贡献65%销售额，客户集中度风险需关注', 1),

  -- user_id=3 more
  (13, 3, 2, NULL,
   'CT（节拍时间）超标的班次有哪些？',
   NOW() - INTERVAL '7 days', false,
   'SELECT LINE, SHIFTNAME, CT, SHIFTPLAN, TOTALCOUNT FROM mainrecord WHERE CT > SHIFTPLAN * 1.1 ORDER BY CT DESC LIMIT 20',
   '[{"LINE":"REPS3 RACK","SHIFTNAME":"夜班","CT":68.3,"SHIFTPLAN":60,"TOTALCOUNT":189},{"LINE":"REPS3 BSI","SHIFTNAME":"夜班","CT":63.1,"SHIFTPLAN":58,"TOTALCOUNT":231}]',
   '发现8个班次CT超标（超计划10%以上），主要集中在夜班。REPS3 RACK夜班CT超标最严重（68.3s vs 计划60s）。',
   'nl2sql', NULL, 'gpt-4o',
   false, NULL, 1),

  (14, 3, 2, NULL,
   '近3个月OEE月度趋势',
   NOW() - INTERVAL '6 days', true,
   'SELECT TO_CHAR(DATE_TRUNC(''month'', SHIFTSTARTTIME), ''YYYY-MM'') as month, AVG(OEE) as avg_oee FROM mainrecord WHERE SHIFTSTARTTIME >= CURRENT_DATE - INTERVAL ''90 days'' GROUP BY month ORDER BY month',
   '[{"month":"2026-02","avg_oee":86.3},{"month":"2026-03","avg_oee":87.8},{"month":"2026-04","avg_oee":86.9}]',
   '近3个月OEE在86%-88%区间震荡，3月达到近期高点87.8%，4月略有回落。整体低于90%长期目标，需制定系统性提升计划。',
   'nl2sql', NULL, 'gpt-4o',
   false, NULL, 1),

  (15, 3, 2, NULL,
   'REPS3 BSI各工位CT分布分析',
   NOW() - INTERVAL '5 days', false,
   'SELECT PARTNO, AVG(CT) as avg_ct, STDDEV(CT) as ct_stddev, COUNT(*) as shifts FROM mainrecord WHERE LINE = ''REPS3 BSI'' GROUP BY PARTNO ORDER BY avg_ct DESC',
   '[{"PARTNO":"BSI-003","avg_ct":72.4,"ct_stddev":8.3,"shifts":24},{"PARTNO":"BSI-001","avg_ct":58.9,"ct_stddev":3.1,"shifts":38},{"PARTNO":"BSI-002","avg_ct":51.2,"ct_stddev":2.7,"shifts":29}]',
   'BSI-003零件CT均值72.4s（波动最大），为产线瓶颈工位。建议进行工艺改善或增加人员支援。',
   'nl2sql', NULL, 'gpt-4o',
   false, NULL, 1),

  (16, 8, 2, NULL,
   'REPS3 BSA产线满足OEE>90%的班次占比',
   NOW() - INTERVAL '4 days', false,
   'SELECT COUNT(CASE WHEN OEE >= 90 THEN 1 END) * 100.0 / COUNT(*) as high_oee_pct, COUNT(*) as total_shifts FROM mainrecord WHERE LINE = ''REPS3 BSA''',
   '[{"high_oee_pct":67.3,"total_shifts":52}]',
   'REPS3 BSA有67.3%的班次OEE达到90%以上，是全线最稳定的产线，可作为标杆产线推广最佳实践。',
   'nl2sql', NULL, 'gpt-4o',
   true, 'REPS3 BSA：67%班次OEE超90%，标杆产线最佳实践推广', 1),

  (17, 2, 2, NULL,
   '5月第一周各产线与4月同期对比',
   NOW() - INTERVAL '3 days', true,
   'SELECT LINE, AVG(CASE WHEN DATE_PART(''week'', SHIFTSTARTTIME) = 18 THEN OEE END) as may_wk1, AVG(CASE WHEN DATE_PART(''week'', SHIFTSTARTTIME) = 14 THEN OEE END) as apr_wk1 FROM mainrecord GROUP BY LINE',
   '[{"LINE":"REPS3 Final","may_wk1":87.6,"apr_wk1":85.2},{"LINE":"REPS3 RACK","may_wk1":82.4,"apr_wk1":78.9},{"LINE":"REPS3 BSI","may_wk1":86.1,"apr_wk1":88.3}]',
   '5月第1周vs4月同期：Final和RACK有所改善，BSI略有下降（-2.2%）。整体向好，RACK持续改善中。',
   'nl2sql', NULL, 'gpt-4o',
   false, NULL, 1),

  (18, 9, 2, NULL,
   '全产线今日实时产出情况',
   NOW() - INTERVAL '2 hours', false,
   'SELECT LINE, SHIFTNAME, TOTALCOUNT, OEE, RTY, SHIFTSTARTTIME FROM mainrecord WHERE DATE(SHIFTSTARTTIME) = CURRENT_DATE ORDER BY LINE, SHIFTSTARTTIME',
   '[{"LINE":"REPS3 BSA","SHIFTNAME":"白班","TOTALCOUNT":168,"OEE":91.2,"RTY":97.1,"SHIFTSTARTTIME":"2026-05-08T08:00:00"},{"LINE":"REPS3 Final","SHIFTNAME":"白班","TOTALCOUNT":155,"OEE":88.4,"RTY":96.2,"SHIFTSTARTTIME":"2026-05-08T08:00:00"}]',
   '今日白班进行中，BSA产线领先（OEE 91.2%），Final正常运行。截至查询时点，整体进度符合预期。',
   'nl2sql', NULL, 'gpt-4o',
   false, NULL, 1),

  (19, 2, 4, NULL,
   '蓝途科技5月订单流入情况',
   NOW() - INTERVAL '1 day', true,
   'SELECT DATE(order_date) as day, COUNT(order_id) as orders, SUM(revenue) as revenue FROM sales WHERE order_date >= ''2026-05-01'' GROUP BY DATE(order_date) ORDER BY day',
   '[{"day":"2026-05-05","orders":18,"revenue":43200},{"day":"2026-05-06","orders":22,"revenue":56800},{"day":"2026-05-07","orders":15,"revenue":38100}]',
   '5月前三个工作日日均20件订单，日均¥4.6万，节后恢复良好，若保持此节奏，5月全月可望达成销售目标。',
   'nl2sql', NULL, 'gpt-4o',
   false, NULL, 1),

  (20, 3, 2, NULL,
   'REPS3 Pinion线近期产出趋势',
   NOW() - INTERVAL '12 hours', false,
   'SELECT DATE(SHIFTSTARTTIME) as shift_date, SHIFTNAME, TOTALCOUNT, OEE FROM mainrecord WHERE LINE = ''REPS3 Pinion'' AND SHIFTSTARTTIME >= CURRENT_DATE - INTERVAL ''14 days'' ORDER BY SHIFTSTARTTIME DESC',
   '[{"shift_date":"2026-05-08","SHIFTNAME":"白班","TOTALCOUNT":2143,"OEE":88.3},{"shift_date":"2026-05-07","SHIFTNAME":"夜班","TOTALCOUNT":2187,"OEE":86.1},{"shift_date":"2026-05-07","SHIFTNAME":"白班","TOTALCOUNT":312,"OEE":89.2}]',
   '发现Pinion线5月8日白班TOTALCOUNT高达2143件，5月7日夜班2187件，与正常值（300件左右）严重偏离，高度疑似数据重复录入，需核查MES数据。',
   'nl2sql', NULL, 'gpt-4o',
   false, NULL, 1)
ON CONFLICT (id) DO NOTHING;

-- ============================================================
-- 10. PINNED CHARTS (8 charts for Nexteer users)
-- ============================================================

INSERT INTO pinned_charts
  (id, user_id, datasource_id, title, description, sql_query, chart_type, sort_order, display_order, created_at, updated_at)
VALUES
  -- user_id=2 (nexteer_admin)
  (1, 2, 2,
   '各产线月均OEE对比',
   '按产线统计本月平均OEE，用于横向对比产线效能',
   'SELECT LINE, ROUND(AVG(OEE)::numeric, 2) as avg_oee FROM mainrecord WHERE SHIFTSTARTTIME >= DATE_TRUNC(''month'', CURRENT_DATE) GROUP BY LINE ORDER BY avg_oee DESC',
   'bar', 'desc', 1,
   NOW() - INTERVAL '25 days', NOW() - INTERVAL '25 days'),

  (2, 2, 2,
   '近14天日产出趋势',
   '全产线合计日产出趋势折线图',
   'SELECT DATE(SHIFTSTARTTIME) as shift_date, SUM(TOTALCOUNT) as daily_total FROM mainrecord WHERE SHIFTSTARTTIME >= CURRENT_DATE - INTERVAL ''14 days'' GROUP BY DATE(SHIFTSTARTTIME) ORDER BY shift_date',
   'line', 'none', 2,
   NOW() - INTERVAL '22 days', NOW() - INTERVAL '22 days'),

  (3, 2, 2,
   'OEE vs RTY 散点分析',
   '分析OEE与RTY的相关性，识别双低班次',
   'SELECT LINE, SHIFTNAME, ROUND(OEE::numeric,1) as oee, ROUND(RTY::numeric,1) as rty, TOTALCOUNT FROM mainrecord WHERE SHIFTSTARTTIME >= CURRENT_DATE - INTERVAL ''30 days'' ORDER BY oee ASC',
   'scatter', 'none', 3,
   NOW() - INTERVAL '20 days', NOW() - INTERVAL '20 days'),

  (4, 2, 2,
   '白班/夜班RTY对比',
   '按班次汇总RTY均值，对比白夜班差异',
   'SELECT SHIFTNAME, ROUND(AVG(RTY)::numeric, 2) as avg_rty, COUNT(*) as shift_count FROM mainrecord WHERE SHIFTSTARTTIME >= DATE_TRUNC(''month'', CURRENT_DATE) GROUP BY SHIFTNAME',
   'bar', 'desc', 4,
   NOW() - INTERVAL '18 days', NOW() - INTERVAL '18 days'),

  (5, 2, 2,
   '月度OEE KPI达标率',
   '统计各产线OEE>=85%的班次占比',
   'SELECT LINE, ROUND(100.0 * COUNT(CASE WHEN OEE >= 85 THEN 1 END) / COUNT(*)::numeric, 1) as target_hit_pct, COUNT(*) as total_shifts FROM mainrecord WHERE SHIFTSTARTTIME >= DATE_TRUNC(''month'', CURRENT_DATE) GROUP BY LINE ORDER BY target_hit_pct DESC',
   'bar', 'desc', 5,
   NOW() - INTERVAL '15 days', NOW() - INTERVAL '15 days'),

  -- user_id=3 (nexteer user)
  (6, 3, 2,
   '我的产线今日产出',
   'REPS3 Final今日各班次产出详情',
   'SELECT SHIFTNAME, TOTALCOUNT, OEE, RTY, STAFFNUM FROM mainrecord WHERE LINE = ''REPS3 Final'' AND DATE(SHIFTSTARTTIME) = CURRENT_DATE ORDER BY SHIFTSTARTTIME',
   'table', 'none', 1,
   NOW() - INTERVAL '12 days', NOW() - INTERVAL '12 days'),

  (7, 3, 2,
   'REPS3 Final近30天OEE趋势',
   '我负责的产线近一个月OEE走势',
   'SELECT DATE(SHIFTSTARTTIME) as shift_date, ROUND(AVG(OEE)::numeric, 2) as daily_avg_oee FROM mainrecord WHERE LINE = ''REPS3 Final'' AND SHIFTSTARTTIME >= CURRENT_DATE - INTERVAL ''30 days'' GROUP BY shift_date ORDER BY shift_date',
   'line', 'none', 2,
   NOW() - INTERVAL '10 days', NOW() - INTERVAL '10 days'),

  (8, 3, 2,
   '各零件号NG情况汇总',
   'Final线各PARTNO的RTY排名，快速识别问题料号',
   'SELECT PARTNO, ROUND(AVG(RTY)::numeric, 2) as avg_rty, SUM(TOTALCOUNT) as total_output FROM mainrecord WHERE LINE = ''REPS3 Final'' AND SHIFTSTARTTIME >= CURRENT_DATE - INTERVAL ''30 days'' GROUP BY PARTNO ORDER BY avg_rty ASC LIMIT 10',
   'bar', 'asc', 3,
   NOW() - INTERVAL '8 days', NOW() - INTERVAL '8 days')
ON CONFLICT (id) DO NOTHING;

-- ============================================================
-- 11. DASHBOARD COMMENTS (8 comments on dashboards id=1-4)
-- ============================================================

INSERT INTO dashboard_comments
  (id, dashboard_id, user_id, username, content, created_at)
VALUES
  (1, 1, 2, 'nexteer_admin',
   '这个看板的OEE趋势图非常直观，建议增加与目标线（85%）的对比参考线，方便快速判断是否达标。',
   NOW() - INTERVAL '20 days'),

  (2, 1, 6, 'nexteer_certifier',
   '同意，另外建议在图表下方增加近7天平均值的数字展示，方便晨会汇报时快速读数。',
   NOW() - INTERVAL '19 days'),

  (3, 1, 3, 'nexteer',
   '我发现4月20日那个低谷点，当天确实有设备故障，已经在行动项里记录了根因分析任务。',
   NOW() - INTERVAL '18 days'),

  (4, 2, 2, 'nexteer_admin',
   '销售看板数据更新频率能否提高到每小时？目前每日更新有些滞后，销售会议时无法看到实时数据。',
   NOW() - INTERVAL '15 days'),

  (5, 2, 8, 'nexteer_analyst',
   '已和IT同事确认，蓝途数据源的Excel文件每天18:00更新一次，若需要实时数据，建议升级为数据库直连。',
   NOW() - INTERVAL '14 days'),

  (6, 3, 2, 'nexteer_admin',
   'RTY分析看板的饼图建议改为帕累托图，更容易识别TOP失效模式的累计贡献，便于质量改善优先排序。',
   NOW() - INTERVAL '10 days'),

  (7, 3, 6, 'nexteer_certifier',
   '这个看板已共享给质量部门，他们反映失效类型的中文标签在手机上显示不全，建议缩短标签长度。',
   NOW() - INTERVAL '8 days'),

  (8, 4, 2, 'nexteer_admin',
   '生产综合看板可以考虑增加今日完成率的KPI大数字卡片，让管理层进入看板第一眼就能看到关键指标。',
   NOW() - INTERVAL '3 days')
ON CONFLICT (id) DO NOTHING;

-- ============================================================
-- 12. RLS RULES (3 rules for Nexteer)
-- ============================================================

INSERT INTO rls_rules
  (id, datasource_id, org_id, user_id, table_name, column_name, operator, filter_value, is_active, created_at)
VALUES
  -- Rule 1: nexteer user (id=3) restricted to REPS3 Final line only
  (1, 2, NULL, 3, 'mainrecord', 'LINE', '=', 'REPS3 Final', 1, NOW() - INTERVAL '30 days'),

  -- Rule 2: nexteer user (id=3) restricted to view only their shift data in ngtype
  (2, 2, NULL, 3, 'ngtype', 'LINE', '=', 'REPS3 Final', 1, NOW() - INTERVAL '30 days'),

  -- Rule 3: nexteer_analyst (id=8) can see all Nexteer lines but not production_ok raw data
  (3, 2, NULL, 9, 'mainrecord', 'SHIFTNAME', 'IN', '白班,夜班', 1, NOW() - INTERVAL '15 days')
ON CONFLICT (id) DO NOTHING;

-- ============================================================
-- 13. ACCESS REQUESTS (5 requests)
-- ============================================================

INSERT INTO access_requests
  (id, requester_id, resource_type, resource_id, resource_name, reason, status,
   reviewer_id, review_comment, reviewed_at, org_id, created_at)
VALUES
  -- Approved: nexteer_analyst wants access to PostgreSQL datasource
  (1, 8, 'datasource', 3, 'Mock PostgreSQL 销售分析',
   '需要访问销售分析数据库以开展季度销售趋势研究，当前只有Excel数据源权限，无法做实时分析。',
   'approved', 2,
   '分析师工作需要，已审批通过，请注意只读权限。',
   NOW() - INTERVAL '18 days', 1, NOW() - INTERVAL '20 days'),

  -- Pending: nexteer_viewer wants dataset access
  (2, 9, 'dataset', 1, 'Nexteer生产数据集',
   '作为查看者需要访问生产数据集，用于日常生产报告的核对和归档工作。',
   'pending', NULL, NULL, NULL, 1, NOW() - INTERVAL '5 days'),

  -- Rejected: nexteer_viewer wants cross-org access
  (3, 9, 'datasource', 1, '嘉盛半导体',
   '希望了解半导体供应商的数据结构，用于标杆学习。',
   'rejected', 2,
   '跨组织数据访问不符合数据安全规范，已拒绝。如需对标分析，请通过正式合作流程申请。',
   NOW() - INTERVAL '12 days', 1, NOW() - INTERVAL '14 days'),

  -- Pending: nexteer_analyst wants more dataset access
  (4, 8, 'dataset', 2, '蓝途科技销售数据集',
   '需要蓝途销售数据集的完整字段访问权限，当前部分字段被脱敏，影响客户流失分析准确性。',
   'pending', NULL, NULL, NULL, 1, NOW() - INTERVAL '2 days'),

  -- Approved: nexteer user wants rtyinfo table access
  (5, 3, 'datasource', 2, 'nexteer (Excel)',
   '需要访问rtyinfo数据，以完成当前负责的RTY失效模式追踪分析任务。',
   'approved', 6,
   'RTY分析工作需要，已确认与产线负责人对应，审批通过，限rtyinfo表查看权限。',
   NOW() - INTERVAL '8 days', 1, NOW() - INTERVAL '10 days')
ON CONFLICT (id) DO NOTHING;

-- ============================================================
-- 14. CATALOG CATEGORIES (4 subcategories under existing ones)
-- ============================================================

INSERT INTO catalog_categories
  (id, name, parent_id, org_id, sort_order, created_at)
VALUES
  -- Under id=1 (销售分析)
  (5, '蓝途销售分析', 1, 1, 1, NOW() - INTERVAL '40 days'),
  -- Under id=2 (生产管理)
  (6, 'OEE专项分析', 2, 1, 1, NOW() - INTERVAL '35 days'),
  (7, 'RTY质量管理', 2, 1, 2, NOW() - INTERVAL '35 days'),
  -- Under id=4 (其他)
  (8, '基础数据维护', 4, 1, 1, NOW() - INTERVAL '30 days')
ON CONFLICT (id) DO NOTHING;

-- ============================================================
-- 15. DATA ASSETS (6 new assets)
-- ============================================================

INSERT INTO data_assets
  (id, asset_type, asset_id, name, description, datasource_id, org_id, owner_id,
   category_id, status, tags, metadata_json, view_count, created_at, updated_at)
VALUES
  -- Asset 18: OEE分析看板 (dashboard)
  (18, 'dashboard', 1, 'OEE生产效率看板',
   '实时展示Nexteer各产线OEE、RTY和日产出，支持按产线和班次下钻分析。',
   2, 1, 2, 6,
   'published',
   '["OEE","生产管理","产线监控","KPI"]',
   '{"refresh_interval":"5min","chart_count":6,"data_range":"rolling_30d"}',
   342, NOW() - INTERVAL '60 days', NOW() - INTERVAL '1 day'),

  -- Asset 19: 蓝途销售数据集
  (19, 'dataset', 4, '蓝途科技销售明细数据集',
   '蓝途科技全量销售订单数据，含客户、产品、渠道、金额等维度，用于销售分析。',
   4, 1, 2, 5,
   'published',
   '["销售","蓝途","客户分析","订单"]',
   '{"row_count":12847,"columns":["customer_name","product_category","revenue","order_date","salesperson"],"update_frequency":"daily"}',
   128, NOW() - INTERVAL '50 days', NOW() - INTERVAL '2 days'),

  -- Asset 20: RTY一次通过率指标
  (20, 'metric', 2, 'RTY一次通过率指标',
   '衡量产品一次通过全部工序的质量指标，用于质量趋势监控、班次对比和失效模式改善。',
   2, 1, 6, 7,
   'published',
   '["RTY","质量","一次通过率","认证指标"]',
   '{"formula":"合格流转件数 / 投入件数 * 100%","unit":"%","aggregation":"avg","target":95,"certification_status":"certified"}',
   89, NOW() - INTERVAL '45 days', NOW() - INTERVAL '7 days'),

  -- Asset 21: mainrecord 原始数据表
  (21, 'table', NULL, 'mainrecord 班次主数据表',
   'Nexteer生产班次主数据，含所有产线每个班次的OEE、RTY、产出等核心指标原始记录。',
   2, 1, 2, 6,
   'published',
   '["原始数据","班次","生产","mainrecord"]',
   '{"table_name":"mainrecord","row_count":4823,"columns":["ID","ASI","LINE","SHIFTID","CT","PARTNO","SHIFTSTARTMIN","SHIFTPLAN","SHIFTSTARTTIME","SHIFTENDTIME","SHIFTNAME","OEE","RTY","TOTALCOUNT","STAFFNUM"],"update_frequency":"realtime"}',
   267, NOW() - INTERVAL '55 days', NOW() - INTERVAL '1 day'),

  -- Asset 22: 蓝途销售经营大屏
  (22, 'big_screen', NULL, '蓝途销售经营大屏',
   '面向管理层的蓝途销售经营大屏，集中展示销售额、产品结构、客户贡献和渠道表现。',
   4, 1, 8, 5,
   'published',
   '["销售分析","经营大屏","产品结构","客户贡献"]',
   '{"component_count":8,"data_bindings":[{"dataset_id":4,"metric":"revenue"}],"refresh_interval":"15min"}',
   54, NOW() - INTERVAL '22 days', NOW() - INTERVAL '22 days'),

  -- Asset 23: OEE综合效率指标
  (23, 'metric', 1, 'OEE综合效率指标',
   '综合衡量产线时间开动率、性能效率和质量良率的核心生产效率指标。',
   2, 1, 2, 6,
   'published',
   '["OEE","生产效率","KPI","认证指标"]',
   '{"formula":"时间开动率 * 性能效率 * 质量良率","unit":"%","aggregation":"avg","target":85,"certification_status":"certified"}',
   156, NOW() - INTERVAL '70 days', NOW() - INTERVAL '30 days')
ON CONFLICT (id) DO UPDATE SET
  asset_type = EXCLUDED.asset_type,
  asset_id = EXCLUDED.asset_id,
  name = EXCLUDED.name,
  description = EXCLUDED.description,
  datasource_id = EXCLUDED.datasource_id,
  org_id = EXCLUDED.org_id,
  owner_id = EXCLUDED.owner_id,
  category_id = EXCLUDED.category_id,
  status = EXCLUDED.status,
  tags = EXCLUDED.tags,
  metadata_json = EXCLUDED.metadata_json,
  view_count = EXCLUDED.view_count,
  updated_at = EXCLUDED.updated_at;

-- ============================================================
-- 16. ASSET LINEAGE (4 lineage relationships)
-- ============================================================

INSERT INTO asset_lineage
  (id, source_id, target_id, rel_type, org_id, created_at)
VALUES
  -- mainrecord table -> OEE看板 (table drives dashboard)
  (1, 21, 18, 'derives_from', 1, NOW() - INTERVAL '40 days'),
  -- mainrecord table -> RTY指标 (table drives metric)
  (2, 21, 20, 'derives_from', 1, NOW() - INTERVAL '38 days'),
  -- 蓝途销售数据集 -> 蓝途销售经营大屏 (dataset drives big screen)
  (3, 19, 22, 'derives_from', 1, NOW() - INTERVAL '22 days'),
  -- mainrecord table -> OEE指标 (table drives metric)
  (4, 21, 23, 'derives_from', 1, NOW() - INTERVAL '30 days')
ON CONFLICT (id) DO UPDATE SET
  source_id = EXCLUDED.source_id,
  target_id = EXCLUDED.target_id,
  rel_type = EXCLUDED.rel_type,
  org_id = EXCLUDED.org_id;

-- ============================================================
-- 17. ASSET SUBSCRIPTIONS (5 subscriptions)
-- ============================================================

INSERT INTO asset_subscriptions
  (id, user_id, asset_id, created_at)
VALUES
  (1, 2, 18, NOW() - INTERVAL '25 days'),   -- nexteer_admin -> OEE看板
  (2, 2, 20, NOW() - INTERVAL '22 days'),   -- nexteer_admin -> RTY指标
  (3, 3, 18, NOW() - INTERVAL '20 days'),   -- nexteer user -> OEE看板
  (4, 6, 21, NOW() - INTERVAL '18 days'),   -- nexteer_certifier -> mainrecord表
  (5, 8, 19, NOW() - INTERVAL '10 days')    -- nexteer_analyst -> 蓝途销售数据集
ON CONFLICT ON CONSTRAINT uq_asset_subscription DO NOTHING;

-- ============================================================
-- 18. ASSET NOTIFICATIONS (6 notifications, some unread)
-- ============================================================

INSERT INTO asset_notifications
  (id, user_id, asset_id, message, is_read, created_at)
VALUES
  (1, 2, 18,
   '您订阅的【OEE生产效率看板】已更新，新增夜班OEE专项监控图表，请查看。',
   true, NOW() - INTERVAL '15 days'),

  (2, 2, 20,
   '您订阅的【RTY一次通过率指标】已完成本月口径复核，4月均值94.7%，低于95%目标，请重点关注。',
   true, NOW() - INTERVAL '7 days'),

  (3, 3, 18,
   '您订阅的【OEE生产效率看板】检测到REPS3 Final夜班OEE连续3天低于85%，已触发预警。',
   false, NOW() - INTERVAL '3 days'),

  (4, 6, 21,
   '您订阅的【mainrecord 班次主数据表】数据质量检测发现4条NULL值记录（SHIFTSTARTTIME字段），请核查。',
   false, NOW() - INTERVAL '2 days'),

  (5, 8, 19,
   '您订阅的【蓝途科技销售明细数据集】已完成4月数据同步更新，新增1,247条订单记录。',
   false, NOW() - INTERVAL '1 day'),

  (6, 2, 21,
   '【mainrecord 班次主数据表】字段元数据已更新至v2.1版本，新增STAFFNUM字段取值规范说明。',
   true, NOW() - INTERVAL '30 days')
ON CONFLICT (id) DO NOTHING;

-- ============================================================
-- 19. P1 ENTERPRISE CAPABILITIES: COMPLEX REPORTS
-- ============================================================

INSERT INTO report_templates
  (id, name, description, dataset_id, report_type, layout_json, parameter_schema_json,
   binding_json, style_json, permission_json, fill_schema_json, distribution_json,
   status, visibility, version, org_id, owner_id, created_by, created_at, updated_at)
VALUES
  (1, 'Nexteer OEE 分页周报',
   '面向工厂管理层的分页报表，按产线、班次和日期展示 OEE、RTY、产出与异常说明，可导出 Excel/PDF。',
   1, 'paginated',
   '{"paper":"A4","cells":[{"row":1,"col":"A","value":"Nexteer OEE 周报","bold":true,"merge":true},{"row":3,"col":"A","value":"产线","bold":true},{"row":3,"col":"B","value":"班次","bold":true},{"row":3,"col":"C","value":"OEE","bold":true},{"row":3,"col":"D","value":"RTY","bold":true},{"row":3,"col":"E","value":"产出","bold":true},{"row":4,"col":"A","value":"{{ LINE }}"},{"row":4,"col":"B","value":"{{ SHIFTNAME }}"},{"row":4,"col":"C","value":"{{ OEE }}"},{"row":4,"col":"D","value":"{{ RTY }}"},{"row":4,"col":"E","value":"{{ TOTALCOUNT }}"}]}',
   '{"date_range":{"type":"date_range","label":"日期范围"},"line":{"type":"select","label":"产线","options":["REPS3 Final","REPS3 BSI","REPS3 RACK"]}}',
   '{"bands":[{"dataset_id":1,"name":"明细区","repeat":"detail","start_row":4}],"summary":{"group_by":["LINE","SHIFTNAME"]}}',
   '{"font":"Microsoft YaHei","density":"compact","print_margin":"12mm"}',
   '{"cell_permissions":[{"range":"C:E","roles":["org_admin","dept_admin"]}]}',
   NULL,
   '{"channels":["email","wechat"],"dynamic_recipients":[{"field":"LINE","mapping":"line_owner"}]}',
   'published', 'org', 2, 1, 2, 2, NOW() - INTERVAL '20 days', NOW() - INTERVAL '2 days'),

  (2, 'RTY 质量填报月报',
   '质量部门用于月度 RTY 复盘的填报报表，包含失效模式确认、改善措施、责任人和完成日期。',
   1, 'fill_form',
   '{"paper":"A4","cells":[{"row":1,"col":"A","value":"RTY 质量填报月报","bold":true,"merge":true},{"row":3,"col":"A","value":"失效模式"},{"row":3,"col":"B","value":"占比"},{"row":3,"col":"C","value":"改善措施"},{"row":3,"col":"D","value":"责任人"}]}',
   '{"month":{"type":"month","label":"月份"},"line":{"type":"select","label":"产线"}}',
   '{"bands":[{"dataset_id":1,"name":"质量明细","repeat":"group","start_row":5}]}',
   '{"font":"Microsoft YaHei","density":"standard"}',
   '{"fill_roles":["org_admin","dept_admin"]}',
   '{"fields":[{"name":"failure_mode","label":"失效模式","required":true},{"name":"countermeasure","label":"改善措施","required":true},{"name":"owner","label":"责任人","required":true},{"name":"due_date","label":"完成日期","type":"date","required":true}],"writeback":{"target_table":"quality_monthly_actions","mode":"append"}}',
   '{"channels":["email"],"recipients":["quality@nexteer-cn.com"]}',
   'published', 'org', 1, 1, 6, 6, NOW() - INTERVAL '16 days', NOW() - INTERVAL '6 days'),

  (3, '蓝途销售经营 Word 报告',
   '销售团队月度经营复盘模板，组合指标表、趋势图说明和管理层摘要，可导出 Word。',
   4, 'word',
   '{"paper":"A4","cells":[{"row":1,"col":"A","value":"蓝途销售经营报告","bold":true},{"row":2,"col":"A","value":"{{ executive_summary }}"}]}',
   '{"month":{"type":"month","label":"月份"},"customer_segment":{"type":"select","label":"客户分层"}}',
   '{"bands":[{"dataset_id":4,"name":"销售汇总","repeat":"summary","start_row":4}]}',
   '{"font":"Microsoft YaHei","density":"presentation"}',
   '{"view_roles":["org_admin","dept_admin","user"]}',
   NULL,
   '{"channels":["email"],"recipients":["sales@nexteer-cn.com"]}',
   'draft', 'org', 1, 1, 8, 8, NOW() - INTERVAL '7 days', NOW() - INTERVAL '7 days')
ON CONFLICT (id) DO UPDATE SET
  name = EXCLUDED.name,
  description = EXCLUDED.description,
  dataset_id = EXCLUDED.dataset_id,
  report_type = EXCLUDED.report_type,
  layout_json = EXCLUDED.layout_json,
  parameter_schema_json = EXCLUDED.parameter_schema_json,
  binding_json = EXCLUDED.binding_json,
  style_json = EXCLUDED.style_json,
  permission_json = EXCLUDED.permission_json,
  fill_schema_json = EXCLUDED.fill_schema_json,
  distribution_json = EXCLUDED.distribution_json,
  status = EXCLUDED.status,
  visibility = EXCLUDED.visibility,
  version = EXCLUDED.version,
  org_id = EXCLUDED.org_id,
  owner_id = EXCLUDED.owner_id,
  updated_at = EXCLUDED.updated_at;

INSERT INTO report_template_versions
  (id, template_id, version, snapshot_json, changelog, created_by, created_at)
VALUES
  (1, 1, 1, '{"name":"Nexteer OEE 分页周报","version":1,"paper":"A4"}', '初始分页模板', 2, NOW() - INTERVAL '20 days'),
  (2, 1, 2, '{"name":"Nexteer OEE 分页周报","version":2,"paper":"A4","added":"dynamic_recipients"}', '增加动态收件人与单元格权限', 2, NOW() - INTERVAL '2 days'),
  (3, 2, 1, '{"name":"RTY 质量填报月报","version":1,"writeback":"quality_monthly_actions"}', '初始填报模板', 6, NOW() - INTERVAL '16 days'),
  (4, 3, 1, '{"name":"蓝途销售经营 Word 报告","version":1,"export":"word"}', '初始 Word 报告模板', 8, NOW() - INTERVAL '7 days')
ON CONFLICT (id) DO UPDATE SET
  snapshot_json = EXCLUDED.snapshot_json,
  changelog = EXCLUDED.changelog;

INSERT INTO report_runs
  (id, template_id, version, run_type, export_type, status, parameters_json, output_uri,
   content_preview, error_message, org_id, created_by, started_at, finished_at)
VALUES
  (1, 1, 2, 'export', 'excel', 'success',
   '{"date_range":["2026-05-01","2026-05-07"],"line":"REPS3 Final"}',
   'exports/reports/nexteer-oee-weekly-20260507.xlsx',
   'Nexteer OEE 周报导出完成，共 5 页，覆盖 3 条产线和 2 个班次。',
   NULL, 1, 2, NOW() - INTERVAL '2 days 09:00', NOW() - INTERVAL '2 days 09:01'),
  (2, 1, 2, 'export', 'pdf', 'queued',
   '{"date_range":["2026-05-01","2026-05-07"],"line":"ALL"}',
   NULL,
   'Nexteer OEE 周报 PDF 导出任务已排队。',
   NULL, 1, 2, NOW() - INTERVAL '1 day 10:00', NULL),
  (3, 3, 1, 'export', 'word', 'success',
   '{"month":"2026-04","customer_segment":"重点客户"}',
   'exports/reports/lantu-sales-review-202604.docx',
   '蓝途销售经营 Word 报告导出完成，包含销售额、客户贡献和渠道表现章节。',
   NULL, 1, 8, NOW() - INTERVAL '3 days 15:00', NOW() - INTERVAL '3 days 15:02')
ON CONFLICT (id) DO UPDATE SET
  status = EXCLUDED.status,
  output_uri = EXCLUDED.output_uri,
  content_preview = EXCLUDED.content_preview,
  finished_at = EXCLUDED.finished_at;

INSERT INTO report_fill_records
  (id, template_id, payload_json, validation_status, validation_errors_json, writeback_status,
   org_id, submitted_by, created_at)
VALUES
  (1, 2,
   '{"failure_mode":"打孔毛刺","countermeasure":"更换钻头并调整点检频率","owner":"quality.engineer","due_date":"2026-05-15"}',
   'valid', NULL, 'pending', 1, 6, NOW() - INTERVAL '5 days'),
  (2, 2,
   '{"failure_mode":"螺纹滑牙","countermeasure":"","owner":"process.engineer"}',
   'error', '{"missing":["countermeasure","due_date"]}', 'blocked', 1, 6, NOW() - INTERVAL '4 days')
ON CONFLICT (id) DO UPDATE SET
  payload_json = EXCLUDED.payload_json,
  validation_status = EXCLUDED.validation_status,
  validation_errors_json = EXCLUDED.validation_errors_json,
  writeback_status = EXCLUDED.writeback_status;

-- ============================================================
-- 20. P1 ENTERPRISE CAPABILITIES: DATA PIPELINES
-- ============================================================

INSERT INTO data_pipelines
  (id, name, description, dataset_id, dag_json, schedule_cron, run_mode, status,
   last_run_status, last_run_at, org_id, owner_id, created_by, created_at, updated_at)
VALUES
  (1, 'Nexteer 生产明细日同步',
   '每天凌晨从生产数据源抽取 mainrecord、ngtype、rtyinfo，完成清洗、质量校验后写入生产数据集。',
   1,
   '{"nodes":[{"id":"extract_mainrecord","type":"extract","label":"抽取 mainrecord"},{"id":"clean_shift","type":"transform","label":"班次字段清洗"},{"id":"quality_oee","type":"quality","label":"OEE/RTY 质量校验"},{"id":"load_dataset","type":"load","label":"写入生产数据集"}],"edges":[{"source":"extract_mainrecord","target":"clean_shift"},{"source":"clean_shift","target":"quality_oee"},{"source":"quality_oee","target":"load_dataset"}]}',
   '0 2 * * *', 'scheduled', 'active', 'success', NOW() - INTERVAL '1 day 02:04',
   1, 2, 2, NOW() - INTERVAL '25 days', NOW() - INTERVAL '1 day'),

  (2, '蓝途销售增量同步',
   '每小时同步蓝途销售订单增量数据，支持失败重试和月底补数。',
   4,
   '{"nodes":[{"id":"extract_sales_api","type":"extract","label":"抽取销售 API"},{"id":"dedupe_order","type":"transform","label":"订单去重"},{"id":"load_sales_dataset","type":"load","label":"写入销售数据集"}],"edges":[{"source":"extract_sales_api","target":"dedupe_order"},{"source":"dedupe_order","target":"load_sales_dataset"}]}',
   '0 * * * *', 'incremental', 'active', 'success', NOW() - INTERVAL '1 hour',
   1, 8, 8, NOW() - INTERVAL '18 days', NOW() - INTERVAL '1 hour')
ON CONFLICT (id) DO UPDATE SET
  name = EXCLUDED.name,
  description = EXCLUDED.description,
  dataset_id = EXCLUDED.dataset_id,
  dag_json = EXCLUDED.dag_json,
  schedule_cron = EXCLUDED.schedule_cron,
  run_mode = EXCLUDED.run_mode,
  status = EXCLUDED.status,
  last_run_status = EXCLUDED.last_run_status,
  last_run_at = EXCLUDED.last_run_at,
  updated_at = EXCLUDED.updated_at;

INSERT INTO data_pipeline_runs
  (id, pipeline_id, mode, status, reason, node_logs_json, records_read, records_written,
   records_failed, error_message, org_id, triggered_by_id, started_at, finished_at)
VALUES
  (1, 1, 'scheduled', 'success', '每日调度',
   '{"summary":{"node_count":4,"edge_count":3,"quality":"passed"},"nodes":[{"node_id":"extract_mainrecord","status":"success","records":4823},{"node_id":"clean_shift","status":"success","records":4823},{"node_id":"quality_oee","status":"success","records":4823},{"node_id":"load_dataset","status":"success","records":4823}]}',
   4823, 4823, 0, NULL, 1, 2, NOW() - INTERVAL '1 day 02:00', NOW() - INTERVAL '1 day 02:04'),
  (2, 1, 'backfill', 'success', '补齐五一假期生产记录',
   '{"summary":{"node_count":4,"edge_count":3,"quality":"passed"},"nodes":[{"node_id":"extract_mainrecord","status":"success","records":1260},{"node_id":"clean_shift","status":"success","records":1260},{"node_id":"quality_oee","status":"success","records":1260},{"node_id":"load_dataset","status":"success","records":1260}]}',
   1260, 1260, 0, NULL, 1, 2, NOW() - INTERVAL '3 days 13:00', NOW() - INTERVAL '3 days 13:03'),
  (3, 2, 'incremental', 'success', '小时级增量同步',
   '{"summary":{"node_count":3,"edge_count":2,"quality":"passed"},"nodes":[{"node_id":"extract_sales_api","status":"success","records":84},{"node_id":"dedupe_order","status":"success","records":83},{"node_id":"load_sales_dataset","status":"success","records":83}]}',
   84, 83, 1, NULL, 1, 8, NOW() - INTERVAL '1 hour 5 minutes', NOW() - INTERVAL '1 hour')
ON CONFLICT (id) DO UPDATE SET
  status = EXCLUDED.status,
  node_logs_json = EXCLUDED.node_logs_json,
  records_read = EXCLUDED.records_read,
  records_written = EXCLUDED.records_written,
  records_failed = EXCLUDED.records_failed,
  finished_at = EXCLUDED.finished_at;

INSERT INTO data_quality_rules
  (id, pipeline_id, dataset_id, name, rule_type, field, operator, threshold, severity,
   is_active, last_status, last_checked_at, org_id, created_by, created_at)
VALUES
  (1, 1, 1, 'OEE 不为空', 'not_null', 'OEE', NULL, NULL, 'error', true, 'passed', NOW() - INTERVAL '1 day 02:03', 1, 2, NOW() - INTERVAL '25 days'),
  (2, 1, 1, 'RTY 合理范围', 'range', 'RTY', 'between', '0,100', 'error', true, 'passed', NOW() - INTERVAL '1 day 02:03', 1, 2, NOW() - INTERVAL '25 days'),
  (3, 2, 4, '订单号唯一', 'unique', 'order_id', NULL, NULL, 'error', true, 'passed', NOW() - INTERVAL '1 hour', 1, 8, NOW() - INTERVAL '18 days'),
  (4, 2, 4, '销售数据新鲜度', 'freshness', 'order_date', '<=', '2h', 'warning', true, 'passed', NOW() - INTERVAL '1 hour', 1, 8, NOW() - INTERVAL '18 days')
ON CONFLICT (id) DO UPDATE SET
  name = EXCLUDED.name,
  rule_type = EXCLUDED.rule_type,
  field = EXCLUDED.field,
  severity = EXCLUDED.severity,
  last_status = EXCLUDED.last_status,
  last_checked_at = EXCLUDED.last_checked_at;

-- ============================================================
-- 21. P1 ENTERPRISE CAPABILITIES: SELF-SERVICE ANALYSIS
-- ============================================================

UPDATE datasets
SET
  name = 'Nexteer 生产 OEE 数据集',
  description = '基于 ChatBI 生产 Excel 的 mainrecord 班次主数据，提供产线、班次、时间、零件号维度和 OEE/RTY/产出指标。',
  datasource_id = 2,
  fields_json = '{
    "table":"mainrecord",
    "dimensions":[
      {"name":"mainrecord.LINE","alias":"产线","type":"string"},
      {"name":"mainrecord.SHIFTNAME","alias":"班次","type":"string"},
      {"name":"mainrecord.SHIFTSTARTTIME","alias":"班次开始时间","type":"datetime"},
      {"name":"mainrecord.PARTNO","alias":"零件号","type":"string"}
    ],
    "metrics":[
      {"name":"mainrecord.OEE","alias":"OEE","type":"decimal","aggregation":"avg"},
      {"name":"mainrecord.RTY","alias":"RTY","type":"decimal","aggregation":"avg"},
      {"name":"mainrecord.TOTALCOUNT","alias":"总产出","type":"integer","aggregation":"sum"}
    ]
  }',
  aggregations_json = '{
    "aggregations":[
      {"field":"mainrecord.OEE","aggregation":"avg","alias":"平均OEE"},
      {"field":"mainrecord.RTY","aggregation":"avg","alias":"平均RTY"},
      {"field":"mainrecord.TOTALCOUNT","aggregation":"sum","alias":"总产出"}
    ]
  }',
  semantic_model_json = '{
    "dimensions":[
      {"name":"LINE","label":"产线"},
      {"name":"SHIFTNAME","label":"班次"},
      {"name":"PARTNO","label":"零件号"}
    ],
    "time_dimensions":[{"name":"SHIFTSTARTTIME","label":"班次开始时间"}],
    "metrics":[
      {"name":"OEE","label":"OEE","aggregation":"avg"},
      {"name":"RTY","label":"RTY","aggregation":"avg"},
      {"name":"TOTALCOUNT","label":"总产出","aggregation":"sum"}
    ],
    "synonyms":{"产线":["LINE"],"班次":["SHIFTNAME"],"产出":["TOTALCOUNT"]}
  }',
  status = 'published',
  visibility = 'org',
  org_id = 1,
  owner_id = 2
WHERE id = 1;

UPDATE datasets
SET
  name = '蓝途科技销售明细数据集',
  description = '基于蓝途销售 Excel 的 order_items 订单明细，提供产品、品类维度和销售额/销量指标。',
  datasource_id = 4,
  fields_json = '{
    "table":"order_items",
    "dimensions":[
      {"name":"order_items.product_name","alias":"产品名称","type":"string"},
      {"name":"order_items.category","alias":"产品品类","type":"string"},
      {"name":"order_items.product_id","alias":"产品ID","type":"string"}
    ],
    "metrics":[
      {"name":"order_items.subtotal","alias":"销售额","type":"decimal","aggregation":"sum"},
      {"name":"order_items.quantity","alias":"销量","type":"integer","aggregation":"sum"}
    ]
  }',
  aggregations_json = '{
    "aggregations":[
      {"field":"order_items.subtotal","aggregation":"sum","alias":"销售额"},
      {"field":"order_items.quantity","aggregation":"sum","alias":"销量"}
    ]
  }',
  semantic_model_json = '{
    "dimensions":[
      {"name":"product_name","label":"产品名称"},
      {"name":"category","label":"产品品类"},
      {"name":"product_id","label":"产品ID"}
    ],
    "time_dimensions":[],
    "metrics":[
      {"name":"subtotal","label":"销售额","aggregation":"sum"},
      {"name":"quantity","label":"销量","aggregation":"sum"}
    ],
    "synonyms":{"产品":["product_name"],"品类":["category"],"销售额":["subtotal"],"销量":["quantity"]}
  }',
  status = 'published',
  visibility = 'org',
  org_id = 1,
  owner_id = 8
WHERE id = 4;

INSERT INTO analysis_views
  (id, name, description, dataset_id, chart_type, dimensions, measures, filters, sorts,
   calculation_fields_json, visual_config_json, interaction_json, status, visibility,
   org_id, owner_id, created_at, updated_at)
VALUES
  (1, '产线 OEE 趋势自助分析',
   '生产经理按产线和班次查看 OEE 趋势，支持同环比、钻取到失效模式和加入看板。',
   1, 'line',
   '["LINE","SHIFTNAME"]',
   '[{"field":"OEE","aggregation":"avg","alias":"平均OEE"},{"field":"TOTALCOUNT","aggregation":"sum","alias":"总产出"}]',
   '[{"field":"SHIFTSTARTTIME","operator":">=","value":"2026-05-01"}]',
   '[{"field":"SHIFTSTARTTIME","direction":"asc"}]',
   '{"calculations":["yoy","mom","cumulative"]}',
   '{"palette":"operations","show_target_line":true,"target":85}',
   '{"drill":true,"linkage":true,"drill_path":["LINE","SHIFTNAME","PARTNO"]}',
   'published', 'org', 1, 3, NOW() - INTERVAL '12 days', NOW() - INTERVAL '1 day'),

  (2, 'RTY 失效模式 Pareto 分析',
   '质量工程师用于识别 TOP 失效模式、占比和改善优先级。',
   1, 'bar',
   '["LINE"]',
   '[{"field":"RTY","aggregation":"avg","alias":"平均RTY"}]',
   '[{"field":"RTY","operator":"<","value":95}]',
   '[{"field":"RTY","direction":"asc"}]',
   '{"calculations":["rank","ratio"]}',
   '{"palette":"quality","pareto":true}',
   '{"drill":true,"linkage":false,"drill_path":["LINE","PARTNO"]}',
   'published', 'org', 1, 6, NOW() - INTERVAL '10 days', NOW() - INTERVAL '2 days'),

  (3, '蓝途产品销售贡献分析',
   '销售分析师按产品和品类分析订单明细销售额贡献，支持数量筛选、排名和占比。',
   4, 'bar',
   '["product_name","category"]',
   '[{"field":"subtotal","aggregation":"sum","alias":"销售额"}]',
   '[{"field":"quantity","operator":"=","value":5}]',
   '[{"field":"subtotal","direction":"desc"}]',
   '{"calculations":["rank","ratio","mom"]}',
   '{"palette":"sales","show_legend":true}',
   '{"drill":true,"linkage":true,"drill_path":["category","product_name","product_id"]}',
   'published', 'org', 1, 8, NOW() - INTERVAL '8 days', NOW() - INTERVAL '1 day')
ON CONFLICT (id) DO UPDATE SET
  name = EXCLUDED.name,
  description = EXCLUDED.description,
  dataset_id = EXCLUDED.dataset_id,
  chart_type = EXCLUDED.chart_type,
  dimensions = EXCLUDED.dimensions,
  measures = EXCLUDED.measures,
  filters = EXCLUDED.filters,
  sorts = EXCLUDED.sorts,
  calculation_fields_json = EXCLUDED.calculation_fields_json,
  visual_config_json = EXCLUDED.visual_config_json,
  interaction_json = EXCLUDED.interaction_json,
  status = EXCLUDED.status,
  visibility = EXCLUDED.visibility,
  updated_at = EXCLUDED.updated_at;

COMMIT;
-- END
