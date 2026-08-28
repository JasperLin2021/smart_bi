---
name: 修复运营后台 summary 接口 Windows 500 错误
overview: 修复 /api/operations/summary 在 Windows 环境下返回 500 的问题：os.getloadavg() 在 Windows 上不存在导致 AttributeError 未被捕获，需将其降级处理并补充回归测试。
todos:
  - id: fix-getloadavg-windows
    content: 修复 operations.py 中 _system_resources 对 os.getloadavg 的 Windows 兼容，缺失或异常时降级为 0.0
    status: completed
  - id: add-regression-test
    content: 在 tests/test_operations_usage.py 新增模拟 Windows 场景的回归测试，断言接口不抛异常且 cpu_load 结构完整
    status: completed
    dependencies:
      - fix-getloadavg-windows
  - id: verify-fix
    content: 运行 uv run pytest tests/test_operations_usage.py 与 ruff check 验证，并确认前端运营后台可正常加载
    status: completed
    dependencies:
      - fix-getloadavg-windows
      - add-regression-test
---

## 产品概述

修复 Windows 本地环境下点击侧边栏"运营后台"页面时报 500 错误的问题，使运营后台页面能够正常加载数据并展示。

## 核心功能

- 修复 `GET /api/operations/summary` 接口在 Windows 平台返回 500 的问题
- 系统资源卡片（CPU/内存/磁盘）在 Windows 环境下优雅降级展示，不再中断整页数据加载
- 保持 Linux 与 Docker 容器环境下的原有行为不变
- 补充回归测试，防止该问题再次出现

## 技术栈

- 后端：Python 3.12 + FastAPI（既有项目技术栈，无新增依赖）
- 测试：unittest + unittest.mock（沿用既有测试模式）

## 实现方案

### 根因

`backend/app/api/operations.py` 的 `_system_resources()` 中调用 `os.getloadavg()`，该函数仅 Unix 系统可用；Windows 上 `os` 模块无此属性，调用抛出 `AttributeError`，而现有代码只捕获 `except OSError`（`AttributeError` 非其子类），异常未捕获导致接口 500。

### 修复策略

将 `_system_resources()` 中的 CPU 负载采集改为存在性判断 + 异常兜底的双保险方式：

1. 先用 `getattr(os, "getloadavg", None)` 判断平台是否支持；
2. 调用时仍保留 `try/except (OSError, AttributeError)` 兜底；
3. 不支持或调用失败时降级为 `load_1m = 0.0`，CPU 负载卡片显示 `0 / N 核`，与内存卡片的"当前环境未暴露内存信息"降级策略保持一致。

此方案对 Linux/Docker 完全无行为变化（`getloadavg` 存在、正常返回），对 Windows 安全降级，改动面仅限单个函数，无架构影响。

### 回归测试

在 `tests/test_operations_usage.py` 中新增用例，通过 `unittest.mock.patch.object(os, "getloadavg", side_effect=AttributeError, create=True)` 模拟 Windows 场景（属性缺失），断言：

- `get_operations_summary` 不抛异常；
- 返回体中 `system_resources.cpu_load.used == 0` 且响应结构完整（含 label/detail/used_percent 字段）。

## 实施注意事项

- 不修改任何数据模型、路由注册或前端代码，仅修复后端单函数并补测试，控制爆炸半径。
- 无新增日志需求；如需排查可复用既有 logger，不打印敏感信息。
- 验证命令：`cd backend && uv run pytest tests/test_operations_usage.py -q && uv run ruff check .`
- 手动验证：重启后端 uvicorn 后，前端点击"运营后台"应正常加载，不再出现 500。