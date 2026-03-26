#!/bin/bash

# 获取token
TOKEN=$(curl -s -X POST http://localhost:8000/api/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"username":"admin","password":"admin123"}' | \
  grep -o '"access_token":"[^"]*"' | cut -d'"' -f4)

echo "Token: $TOKEN"

# 指标1: 全局Top N Alarm
curl -s -X POST http://localhost:8000/api/metrics \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "global_top_alarms",
    "description": "计算指定时间段内累计发生次数最多的Top N告警",
    "definition": "从daily_top10_alarms表中，按时间段汇总各alarm_id的occurrence_count，取累计次数最高的N条",
    "table_name": "daily_top10_alarms",
    "column_name": "occurrence_count",
    "formula": "WITH global_top_alarms AS (SELECT alarm_id, SUM(occurrence_count) as total_occurrence FROM daily_top10_alarms WHERE stat_date BETWEEN start_date AND end_date GROUP BY alarm_id ORDER BY total_occurrence DESC LIMIT top_n) SELECT * FROM global_top_alarms",
    "is_active": 1
  }'
echo ""

# 指标2: 全局Top10设备
curl -s -X POST http://localhost:8000/api/metrics \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "top_devices_global",
    "description": "在指定告警中，按设备汇总totaltimes，取发生次数最多的Top N设备（不区分告警类型）",
    "definition": "从detail表中筛选指定alarm_id的记录，按equipmentid汇总totaltimes，取前N名设备",
    "table_name": "detail",
    "column_name": "totaltimes",
    "formula": "SELECT equipmentid, SUM(totaltimes) as device_total FROM detail WHERE error_code IN (alarm_ids) AND sumdatetime::DATE BETWEEN start_date AND end_date GROUP BY equipmentid ORDER BY device_total DESC LIMIT top_n",
    "is_active": 1
  }'
echo ""

# 指标3: 每个Alarm的Top10设备
curl -s -X POST http://localhost:8000/api/metrics \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "top_devices_per_alarm",
    "description": "每个告警各自的Top N设备，使用窗口函数分组排名",
    "definition": "从detail表中，按error_code分组，对每组内的设备按totaltimes排名",
    "table_name": "detail",
    "column_name": "totaltimes",
    "formula": "SELECT equipmentid, error_code, SUM(totaltimes) as device_alarm_total, ROW_NUMBER() OVER (PARTITION BY error_code ORDER BY SUM(totaltimes) DESC) as rank_in_alarm FROM detail WHERE error_code IN (alarm_ids) AND sumdatetime::DATE BETWEEN start_date AND end_date GROUP BY equipmentid, error_code",
    "is_active": 1
  }'
echo ""

# 指标4: 设备每日趋势
curl -s -X POST http://localhost:8000/api/metrics \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "device_daily_trend",
    "description": "指定设备在指定告警下的每日发生次数趋势",
    "definition": "按日期、设备、告警汇总totaltimes，用于展示时间序列趋势",
    "table_name": "detail",
    "column_name": "totaltimes",
    "formula": "SELECT sumdatetime::DATE as stat_date, equipmentid, error_code as alarm_id, SUM(totaltimes) as occurrence_count FROM detail WHERE equipmentid IN (device_ids) AND error_code IN (alarm_ids) AND sumdatetime::DATE BETWEEN start_date AND end_date GROUP BY sumdatetime::DATE, equipmentid, error_code",
    "is_active": 1
  }'
echo ""

# 指标5: 告警总次数统计
curl -s -X POST http://localhost:8000/api/metrics \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "alarm_occurrence_sum",
    "description": "统计指定时间段内各告警的总发生次数",
    "definition": "从daily_top10_alarms表按alarm_id汇总occurrence_count",
    "table_name": "daily_top10_alarms",
    "column_name": "occurrence_count",
    "formula": "SELECT alarm_id, alarm_text_chinese, SUM(occurrence_count) as total FROM daily_top10_alarms WHERE stat_date BETWEEN start_date AND end_date GROUP BY alarm_id, alarm_text_chinese",
    "is_active": 1
  }'
echo ""

echo "Done!"
