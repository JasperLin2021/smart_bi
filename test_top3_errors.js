// TOP3 错误代码查询
{
  "dimensions": [
    "Code.errorCode",
    "Code.alarmTextChinese"
  ],
  "measures": [
    "Code.errorCodeCount"
  ],
  "order": {
    "Code.errorCodeCount": "desc"
  },
  "limit": 3,
  "timeDimensions": [
    {
      "dimension": "Detail.createdAt",
      "dateRange": "last 7 days" // 近期，可以根据需要调整
    }
  ],
  "joins": [
    {
      "name": "Detail",
      "relationship": "hasMany",
      "sql": `${Code}.error_code = ${Detail}.error_code`
    }
  ]
}