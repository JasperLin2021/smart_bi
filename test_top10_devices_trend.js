// TOP3错误代码中TOP10设备的趋势图查询
{
  "dimensions": [
    "Detail.equipmentId",
    "Detail.createdAt"
  ],
  "measures": [
    "Detail.deviceErrorCount",
    "Detail.totalDuration"
  ],
  "filters": [
    {
      "member": "Code.errorCode",
      "operator": "equals",
      "values": ["119", "120", "121"] // 这里填入TOP3的错误代码
    }
  ],
  "order": {
    "Detail.deviceErrorCount": "desc"
  },
  "limit": 10,
  "timeDimensions": [
    {
      "dimension": "Detail.createdAt",
      "dateRange": "last 30 days", // 趋势图时间范围
      "granularity": "day" // 按天展示趋势
    }
  ],
  "joins": [
    {
      "name": "Code",
      "relationship": "belongsTo",
      "sql": `${Detail}.error_code = ${Code}.error_code`
    }
  ]
}