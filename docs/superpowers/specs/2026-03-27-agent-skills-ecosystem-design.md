# Agent Skills Ecosystem Design

**Goal**

为网页 Agent 增加与 Codex / Claude Code 风格一致的 skills 机制，兼容 `SKILL.md` 目录式 skill 包，并支持第一期从 GitHub 安装开源 skills。

**Current State**

- 页面 Agent 已有受控 action catalog、planner、确认层和审计日志。
- 当前 Agent 不支持 skill 发现、选择、安装和 skill 约束规划。
- 本地环境已经存在可复用的 skill 包格式：目录下以 `SKILL.md` 为入口，可选 `references/`、`scripts/`、`assets/`。

**Design**

- Skill 包格式兼容目录式 skill：
  - `skill-name/SKILL.md`
  - 可选 `references/`、`scripts/`、`assets/`
- Skill 源支持两类：
  - 项目级：`.agent-skills/`
  - 用户级兼容目录：`~/.codex/skills/`
- 后端新增 skill registry：
  - 扫描本地 skills
  - 读取 `SKILL.md` frontmatter 的 `name`、`description`
  - 记录安装来源、来源 URL、本地路径、状态
- 后端新增 GitHub 安装器：
  - 支持 `owner/repo/path` 或 GitHub tree URL
  - 将 skill 安装到 `.agent-skills/<skill-name>`
  - 安装后自动刷新 registry
- Agent planner 新增 skill 选择层：
  - 每轮先根据用户消息和当前上下文选择 skill
  - 再在 `角色权限 ∩ skill 允许动作` 范围内生成 action plan
- 前端 Agent 窗口显示：
  - 当前选中的 skill
  - skill 说明
  - 执行计划
- 数据源管理页新增 skills 管理入口：
  - 查看已安装 skills
  - 从 GitHub 安装新 skill
  - 启用/禁用 skill

**Safety Boundary**

- Skill 不直接执行代码，不直接突破 action catalog。
- Skill 只能缩小 planner 的动作范围，不能扩大权限。
- 删除、创建、修改类动作仍由风险级别控制确认。
- 远程安装只接受目录式 skill 包；解析失败或缺少 `SKILL.md` 时拒绝安装。
- 审计日志记录 skill 选择结果、安装来源和执行动作。

**Validation**

- 本地 skills 可被扫描并列出。
- GitHub 上的目录式 skill 可安装到项目本地目录。
- Agent 规划结果包含 skill 信息。
- skill 能限制 planner 动作范围。
- 前端可查看和安装 skills。
