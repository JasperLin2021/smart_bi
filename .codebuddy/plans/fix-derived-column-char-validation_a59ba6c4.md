---
name: fix-derived-column-char-validation
overview: 修复派生列表达式白名单校验过严导致 DATE_FORMAT 等含单引号/百分号/中文字符的表达式无法使用的问题，并补充回归测试。
todos:
  - id: relax-derived-whitelist
    content: 放宽 datasets.py 派生列字符白名单，支持单引号、百分号与中文字符
    status: completed
  - id: add-derived-tests
    content: 在 test_dataset_pipeline.py 新增含字符串字面量与格式符的派生列测试
    status: completed
    dependencies:
      - relax-derived-whitelist
  - id: verify-backend
    content: 运行 pytest 与 ruff 验证修复无回归
    status: completed
    dependencies:
      - add-derived-tests
---

## 产品概述

修复数据集派生列表达式校验过严的问题，使包含字符串字面量、百分号格式符及中文字符的合法表达式（如 `Datetime = DATE_FORMAT(order_approved_at,'%Y年-%m月')`）可以正常保存与预览，同时保持 SQL 注入防护能力不降低。

## 核心功能

- 放宽派生列表达式字符白名单，允许单引号 `'`、百分号 `%` 及中文字符（用于字符串字面量与日期格式化文本）
- 保留现有安全拦截：分号 `;`、注释符 `--`、`/*`、`*/` 仍被拒绝；字段引用与别名仍按既有机制转义与校验
- 补充回归测试，覆盖含字符串字面量 + `%` 格式符 + 中文的派生列表达式（SQLite 环境下使用 `strftime`）

## 技术栈

- 既有项目：Python 3.12 + FastAPI + SQLAlchemy 2（backend/），沿用现有模块与测试约定
- 修改范围：仅后端 `datasets.py` 一处白名单正则 + 对应测试，不改动前端、数据库迁移或数据模型

## 实现方案

### 方案概述

问题根因在 `backend/app/api/datasets.py` 的 `_render_derived_expression`（约 442-463 行）：第 461 行 `re.fullmatch(r"[A-Za-z0-9_\.\"`\[\]\s\+\-\*/\(\),]+", rendered)` 白名单过严，未包含单引号、百分号与中文字符，导致 `DATE_FORMAT(order_approved_at,'%Y年-%m月')` 校验失败。方案为将白名单正则提取为模块级常量并补充这三类字符，其余安全机制（第 443 行黑名单、`_quote_column_ref` 转义、`_assert_safe_identifier` 标识符校验）全部保留。

### 关键决策与安全分析

- **白名单扩展**：新增单引号 `'`（字符串字面量必需）、`%`（DATE_FORMAT/LIKE/strftime 格式符必需）、`\u4e00-\u9fff`（中文格式文本）。不额外放开 `&`、`|`、`\` 等其他字符，遵循最小放宽原则（YAGNI）。
- **注入防护不降级**：即使开放 `'` 与 `%`，第 443 行黑名单仍拦截 `;`、`--`、`/*`、`*/`，无法构造第二条语句或注释逃逸；字段引用仍经 `_quote_column_ref` 加引号，alias 仍走 `SAFE_IDENTIFIER_RE` 校验（本次不修改该正则）。
- **兼容性**：`DATE_FORMAT` 为 MySQL 专有函数，SQLite 测试环境改用 `strftime('%Y年%m月', ...)`（SQLite 内置、格式符同为 `%`）；修复代码本身不涉及函数实现，仅放宽字符校验。
- **不扩大范围**：无前缀字段引用（如 `order_approved_at`）不被 456-460 行 re.sub 替换的问题仅作文档提示，不纳入本次修复，避免影响面扩大。

### 实施细节

1. 在 `SAFE_IDENTIFIER_RE`（63 行）附近新增模块级常量：

```python
ALLOWED_DERIVED_CHARS = re.compile(
r"[A-Za-z0-9_\u4e00-\u9fff\.\"`\[\]\s\+\-\*/\(\),'%]+"
)
```

2. 将 461 行校验改为 `if not ALLOWED_DERIVED_CHARS.fullmatch(rendered):`，错误信息不变。
3. 在 `backend/tests/test_dataset_pipeline.py` 新增独立测试方法，复用 `_source_database()` 与 `_dataset_fixture()`，派生列表达式使用 `month_label = strftime('%Y年%m月', '2026-08-28')`，断言 columns 与 rows 输出（期望值 `2026年08月`）。
4. 验证：`cd backend && uv run pytest tests/test_dataset_pipeline.py -q && uv run ruff check .`

## 架构设计

- 单一函数局部修改，不引入新架构模式，不新增依赖；模块级常量便于未来复用与单测引用。
- 数据流不变：数据集派生列表达式 → `_render_derived_expression` 渲染（替换字段引用 + 白名单校验）→ 拼接 SELECT SQL → 执行预览。

## 目录结构

```
backend/
├── app/
│   └── api/
│       └── datasets.py              # [MODIFY] 新增 ALLOWED_DERIVED_CHARS 常量（63 行附近）；
│                                    #           将 461 行白名单校验改为引用该常量（允许 '、%、中文）
└── tests/
    └── test_dataset_pipeline.py     # [MODIFY] 新增派生列含字符串字面量+%格式符+中文的预览测试方法
```