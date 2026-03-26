# Text2SQL 功能测试

## 测试步骤：

1. 首先配置LLM设置（访问 http://localhost:5173/llm-settings）
   - 设置合适的LLM提供商（如OpenAI、Deepseek等）
   - 配置API密钥
   - 可以自定义Text2SQL提示词

2. 测试查询（访问 http://localhost:5173/smart-query）
   - 选择"Text2SQL模式"
   - 输入自然语言查询，例如：
     - "查询最近7天各产线的异常数量"
     - "统计错误代码为119的设备数量"
     - "显示本周各设备的总异常时长"

## 预期结果：

- Text2SQL模式应该能直接生成SQL并执行
- 返回结果包含查询到的数据
- 显示生成的SQL语句
- 提供分析总结

## 提示词配置示例：

### 默认Text2SQL提示词：
```
你是SQL专家，根据用户问题生成标准SQL查询语句。

数据库表结构信息：
- detail 表：包含异常详情记录
  - id: 主键
  - sum_datetime: 时间戳
  - line: 产线（如 A线, B线）
  - error_code: 错误代码
  - count: 异常数量
  - equipmentid: 设备ID
  - duration: 异常持续时间

- code 表：包含错误代码定义
  - error_code: 错误代码（主键）
  - alarm_text_chinese: 中文告警内容

请只输出纯SQL语句，不要包含任何解释或markdown格式。
```

### 自定义提示词（可根据需要修改）：
可以添加更多表结构信息、查询约束、优化建议等。