# 企业微信集成一期设计

## 背景

Smart BI 目前使用本地账号密码登录，后端已有 `Organization`、`User`、角色权限模板、菜单权限、操作权限和数据范围。通知侧已经支持企业微信群机器人和钉钉机器人，预警、定时报告已经有消息发送基础。

本期目标是在不推翻现有账号和权限体系的前提下，接入企业微信自建应用登录，并把企业微信组织、用户、部门信息映射到 Smart BI 的企业、账号和权限。同时统一企微消息流转，覆盖预警、定时报告、行动项、评论、看板分享和审批提醒。

## 目标

- 支持企业微信自建应用 OAuth 登录。
- 通过企微 `corp_id` 绑定本地 `organizations.id`。
- 通过企微 `userid` 自动绑定或创建本地 `users`。
- 首次登录默认创建普通用户。
- 支持按企微部门映射 `role`、`data_scope`、菜单权限、操作权限。
- 支持企业微信应用消息和已有群机器人消息。
- 把预警、定时报告、行动项、评论、看板分享、审批提醒统一接入消息服务。
- 为后续飞书、钉钉登录和企业微信第三方服务商模式预留 provider/corp 结构。

## 非目标

- 本期不实现飞书、钉钉登录。
- 本期不把企微管理员自动映射为 Smart BI `super_admin`。
- 本期不实现企业微信第三方服务商授权流程，但数据模型预留 `provider`、`corp_id`、外部身份字段。
- 本期不做企微通讯录全量同步，只在登录和映射配置时拉取必要用户/部门信息。

## 数据模型

### `integration_configs`

保存企业级集成配置。

- `id`
- `provider`: 当前为 `wechat_work`
- `name`
- `enabled`
- `corp_id`
- `agent_id`
- `app_secret`
- `callback_url`
- `robot_webhook_url`
- `created_at`
- `updated_at`

密钥字段不返回前端，只返回 `app_secret_set`。

### `external_org_bindings`

保存外部企业与本地组织绑定。

- `id`
- `provider`
- `external_corp_id`
- `org_id`
- `created_at`
- `updated_at`

唯一约束：`provider + external_corp_id`。

### `external_identities`

保存外部用户身份与本地用户绑定。

- `id`
- `provider`
- `external_corp_id`
- `external_user_id`
- `user_id`
- `display_name`
- `email`
- `mobile`
- `department_ids_json`
- `last_login_at`
- `created_at`
- `updated_at`

唯一约束：`provider + external_corp_id + external_user_id`。

### `external_permission_mappings`

保存部门到本地权限的映射。

- `id`
- `provider`
- `external_corp_id`
- `external_department_id`
- `org_id`
- `role`
- `data_scope`
- `menu_permissions`
- `action_permissions`
- `priority`
- `enabled`
- `created_at`
- `updated_at`

同一个用户命中多个部门时，按 `priority` 选中优先级最高的规则。没有命中规则时使用默认普通用户权限。

### `message_deliveries`

保存消息投递记录。

- `id`
- `provider`
- `channel`: `wechat_app` 或 `wechat_robot`
- `event_type`
- `recipient_user_id`
- `recipient_external_user_id`
- `org_id`
- `title`
- `content`
- `link_url`
- `status`: `pending`、`success`、`failed`
- `error_message`
- `retry_count`
- `created_at`
- `sent_at`

## 登录流程

1. 前端登录页展示「企业微信登录」按钮。
2. 前端请求 `GET /api/auth/wechat-work/login-url`。
3. 后端生成企业微信 OAuth URL，带 `state`。
4. 用户完成授权后跳回 `GET /api/auth/wechat-work/callback`。
5. 后端用 `code` 换企微用户身份。
6. 后端获取用户基础信息和部门 ID。
7. 根据 `corp_id` 查询 `external_org_bindings`。
8. 未绑定组织时拒绝登录，提示联系管理员绑定企业。
9. 根据 `provider + corp_id + userid` 查询 `external_identities`。
10. 已绑定则更新外部资料和最后登录时间。
11. 未绑定则自动创建本地 `User`，用户名建议为 `ww:{corp_id}:{userid}`，角色默认为 `user`。
12. 按部门映射规则更新用户角色、数据范围和权限覆盖。
13. 生成 Smart BI JWT，前端保存 token 后跳转 Dashboard。

## 权限规则

- 默认角色为 `user`。
- 部门映射可以授予 `user` 或 `org_admin`。
- `super_admin` 只能由本地超级管理员手动授予。
- 部门映射写入用户的 `permission_override_enabled`、`data_scope`、`menu_permissions`、`action_permissions`。
- 如果映射规则被禁用，用户下一次登录时回落到默认或其他命中的规则。
- 登录、绑定、权限变更都写审计日志。

## 后端 API

### 认证

- `GET /api/auth/wechat-work/login-url`
- `GET /api/auth/wechat-work/callback`

### 集成配置

- `GET /api/integrations/wechat-work/config`
- `PUT /api/integrations/wechat-work/config`
- `POST /api/integrations/wechat-work/test`

### 组织绑定

- `GET /api/integrations/wechat-work/org-bindings`
- `POST /api/integrations/wechat-work/org-bindings`
- `DELETE /api/integrations/wechat-work/org-bindings/{id}`

### 权限映射

- `GET /api/integrations/wechat-work/permission-mappings`
- `POST /api/integrations/wechat-work/permission-mappings`
- `PUT /api/integrations/wechat-work/permission-mappings/{id}`
- `DELETE /api/integrations/wechat-work/permission-mappings/{id}`

### 消息

- `POST /api/integrations/wechat-work/message/test`
- `GET /api/integrations/wechat-work/message-deliveries`

## 前端页面

新增系统管理菜单「企业微信集成」。

页面包括：

- 基础配置：CorpID、AgentID、Secret、回调地址、启用状态。
- 组织绑定：企微 CorpID 绑定本地企业。
- 部门权限映射：部门 ID、角色、数据范围、菜单权限、操作权限、优先级。
- 消息配置：应用消息启用、机器人 Webhook、测试发送。
- 投递记录：消息类型、接收人、状态、失败原因、发送时间。

登录页新增「企业微信登录」按钮。未启用企微登录时不展示或置灰。

## 消息流转

新增统一消息服务 `message_dispatcher`，业务模块只提交标准事件：

- `alert.triggered`
- `scheduled_report.generated`
- `action_item.assigned`
- `action_item.status_changed`
- `dashboard.comment.created`
- `dashboard.shared`
- `approval.requested`

消息服务负责：

- 查找接收人本地用户。
- 查找接收人的企微外部身份。
- 生成企微应用消息内容。
- 调用企微发送接口。
- 写入 `message_deliveries`。
- 失败时记录错误，不阻断原业务流程。

已有预警和定时报告的企微机器人通知继续保留，但底层调用逐步迁移到统一消息服务。

## 错误处理

- 未配置企微应用：登录 URL 接口返回 400。
- 回调 code 无效：返回登录失败页面或重定向登录页并带错误提示。
- 未绑定组织：拒绝登录，提示管理员绑定 CorpID。
- 企微接口超时或失败：记录审计和错误日志。
- 消息发送失败：写 `message_deliveries.failed`，不影响主业务提交。

## 测试计划

### 后端

- 企微回调成功后自动创建用户。
- 已有外部身份登录时复用原用户。
- 未绑定组织时拒绝登录。
- 部门映射能正确更新角色和权限。
- 不允许企微映射自动授予 `super_admin`。
- 消息投递成功写入 `message_deliveries.success`。
- 消息投递失败写入 `message_deliveries.failed`。

### 前端

- 登录页展示企微登录按钮。
- 企业微信集成页面可保存配置。
- Secret 不回显，只显示已配置。
- 权限映射可增删改。
- 投递记录可查看状态和错误。

### 集成

- 使用 mock 企微客户端覆盖 OAuth、用户信息、部门信息和消息发送。
- 生产环境用真实企微自建应用做一次端到端验证。

## 实施顺序

1. 新增数据模型、迁移和基础配置 API。
2. 实现企微客户端封装。
3. 实现企微 OAuth 登录与用户自动绑定。
4. 实现组织绑定和部门权限映射。
5. 新增前端登录按钮和企业微信集成管理页。
6. 实现统一消息服务和投递记录。
7. 接入预警、定时报告、行动项、评论、看板分享、审批提醒。
8. 补齐测试和部署文档。
