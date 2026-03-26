// 完整的查询流程：先获取TOP3错误代码，再获取对应设备的趋势

// 第一步：获取TOP3错误代码
async function getTop3ErrorCodes() {
  const query = {
    dimensions: ["Code.errorCode", "Code.alarmTextChinese"],
    measures: ["Code.errorCodeCount"],
    order: { "Code.errorCodeCount": "desc" },
    limit: 3,
    timeDimensions: [{
      dimension: "Detail.createdAt",
      dateRange: "last 7 days"
    }]
  };
  
  // 返回结果示例：
  // [{ errorCode: "119", alarmTextChinese: "温度过高", errorCodeCount: 156 },
  //  { errorCode: "120", alarmTextChinese: "压力异常", errorCodeCount: 98 },
  //  { errorCode: "121", alarmTextChinese: "速度超限", errorCodeCount: 87 }]
}

// 第二步：基于TOP3错误代码获取设备趋势
async function getTop10DevicesTrend(top3ErrorCodes) {
  const query = {
    dimensions: ["Detail.equipmentId", "Detail.createdAt.day"],
    measures: ["Detail.deviceErrorCount", "Detail.totalDuration"],
    filters: [{
      member: "Code.errorCode",
      operator: "equals",
      values: top3ErrorCodes.map(item => item.errorCode)
    }],
    order: { "Detail.deviceErrorCount": "desc" },
    limit: 10,
    timeDimensions: [{
      dimension: "Detail.createdAt",
      dateRange: "last 30 days",
      granularity: "day"
    }]
  };
  
  // 返回结果适合绘制趋势图，每个设备一条线
}

// 使用示例
const top3Errors = await getTop3ErrorCodes();
const deviceTrends = await getTop10DevicesTrend(top3Errors);