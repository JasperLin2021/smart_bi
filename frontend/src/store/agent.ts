import { defineStore } from "pinia"
import axios from "axios"
import { ElMessage } from "element-plus"
import type { RouteLocationRaw } from "vue-router"

import router from "@/router"
import { useDatasourceStore } from "@/store/datasource"
import { useQueryStore } from "@/store/query"

export interface AgentAction {
  type: string
  label: string
  risk: "low" | "medium" | "high"
  params: Record<string, any>
}

export interface AgentSkill {
  name: string
  description: string
  source: string
  path?: string | null
  allowed_actions: string[]
}

export interface AgentMessage {
  id: string
  role: "user" | "assistant"
  content: string
  status?: "pending" | "success" | "error"
  reasoning?: string
  skill?: AgentSkill | null
  actions?: AgentAction[]
  requiresConfirmation?: boolean
  runId?: number
  execution?: Array<{ action: string; status: string; detail: string }>
}

function makeId() {
  return Date.now().toString(36) + Math.random().toString(36).slice(2)
}

const agentRouteAliases: Record<string, RouteLocationRaw> = {
  "/datasource-settings": { path: "/data-development", query: { tab: "datasources" } },
  "/dataset-center": { path: "/data-development", query: { tab: "datasets" } },
  "/user-management": "/access-control",
  "/role-management": "/access-control",
  "/org-management": "/access-control",
  "/goview": "/big-screen-center",
  "数据源管理": { path: "/data-development", query: { tab: "datasources" } },
  "数据集开发": { path: "/data-development", query: { tab: "datasets" } },
  "数据接入": "/data-development",
  "数据源与数据集": "/data-development",
  "用户管理": "/access-control",
  "企业管理": "/access-control",
  "角色管理": "/access-control",
  "可视化ETL": "/data-pipelines",
  "数据加工管道": "/data-pipelines",
  "数据集成管道": "/data-pipelines",
  "连接器接入": "/data-link",
  "数据平台": "/olap-status",
  "OLAP 数据平台": "/olap-status",
  "自助分析": "/analysis-workbench",
  "看板中心": "/dashboard-center",
  "大屏中心": "/big-screen-center",
  "行动闭环": "/action-items",
  "运营后台": "/operations",
}

export function normalizeAgentRoute(value: unknown): RouteLocationRaw {
  const raw = String(value || "").trim()
  if (!raw) return "/dashboard"
  const aliased = agentRouteAliases[raw]
  if (aliased) return aliased
  if (raw.includes("?")) {
    const [path, queryString] = raw.split("?", 2)
    const pathAlias = agentRouteAliases[path]
    if (pathAlias && typeof pathAlias !== "string") return pathAlias
    const query = Object.fromEntries(new URLSearchParams(queryString).entries())
    return { path, query }
  }
  return raw
}

function formatAgentRoute(route: RouteLocationRaw) {
  if (typeof route === "string") return route
  const query = route.query
    ? `?${new URLSearchParams(
        Object.entries(route.query)
          .filter(([, value]) => value !== undefined && value !== null)
          .map(([key, value]) => [key, String(Array.isArray(value) ? value[0] : value)])
      ).toString()}`
    : ""
  return `${route.path || ""}${query}`
}

function asItems(data: any): any[] {
  if (Array.isArray(data)) return data
  if (Array.isArray(data?.items)) return data.items
  return []
}

function firstParam(params: Record<string, any>, keys: string[]) {
  for (const key of keys) {
    const value = params[key]
    if (value !== undefined && value !== null && String(value).trim() !== "") return value
  }
  return undefined
}

function buildUpdatePayload(params: Record<string, any>, omitKeys: string[]) {
  if (params.payload && typeof params.payload === "object") return params.payload
  const payload = { ...params }
  omitKeys.forEach((key) => delete payload[key])
  return payload
}

async function resolveEntity(
  endpoint: string,
  params: Record<string, any>,
  idKeys: string[],
  nameKeys: string[],
  nameFields: string[],
  label: string,
) {
  const id = firstParam(params, idKeys)
  if (id !== undefined) return { id, name: firstParam(params, nameKeys) || id }
  const name = firstParam(params, nameKeys)
  if (name === undefined) throw new Error(`缺少${label}名称或 ID`)
  const response = await axios.get(endpoint)
  const target = asItems(response.data).find((item) => nameFields.some((field) => item[field] === name))
  if (!target) throw new Error(`未找到${label} ${name}`)
  return target
}

export const useAgentStore = defineStore("agent", {
  state: () => ({
    open: false,
    planning: false,
    executing: false,
    loadingSkills: false,
    installingSkill: false,
    input: "",
    messages: [] as AgentMessage[],
    skills: [] as AgentSkill[],
  }),
  actions: {
    toggle() {
      this.open = !this.open
    },
    async fetchSkills() {
      this.loadingSkills = true
      try {
        const response = await axios.get("/api/agent/skills")
        this.skills = response.data || []
      } finally {
        this.loadingSkills = false
      }
    },
    async installSkill(source: string) {
      this.installingSkill = true
      try {
        const response = await axios.post("/api/agent/skills/install", { source })
        const installed = response.data as AgentSkill
        const existingIndex = this.skills.findIndex((item) => item.name === installed.name)
        if (existingIndex >= 0) {
          this.skills.splice(existingIndex, 1, installed)
        } else {
          this.skills.unshift(installed)
        }
        ElMessage.success(`已安装 skill ${installed.name}`)
        return installed
      } finally {
        this.installingSkill = false
      }
    },
    async send() {
      const message = this.input.trim()
      if (!message || this.planning || this.executing) return

      const userMessage: AgentMessage = {
        id: makeId(),
        role: "user",
        content: message,
        status: "success",
      }
      this.messages.push(userMessage)
      this.input = ""
      this.planning = true

      try {
        const dsStore = useDatasourceStore()
        const response = await axios.post("/api/agent/plan", {
          message,
          route: router.currentRoute.value.fullPath,
          datasource_id: dsStore.currentId,
          datasource_name: dsStore.current?.name || null,
        })

        const assistantMessage: AgentMessage = {
          id: makeId(),
          role: "assistant",
          content: response.data.reply,
          reasoning: response.data.reasoning,
          skill: response.data.skill || null,
          actions: response.data.actions || [],
          requiresConfirmation: response.data.requires_confirmation,
          runId: response.data.run_id,
          status: "success",
        }
        this.messages.push(assistantMessage)

        if (response.data.missing_fields?.length) {
          assistantMessage.content += `\n缺少信息：${response.data.missing_fields.join("、")}`
          return
        }

        if (!assistantMessage.actions?.length) {
          return
        }

        const allLowRisk = assistantMessage.actions.every((item) => item.risk === "low")
        if (allLowRisk && !assistantMessage.requiresConfirmation) {
          await this.executePlan(assistantMessage)
        }
      } catch (error: any) {
        this.messages.push({
          id: makeId(),
          role: "assistant",
          content: error.response?.data?.detail || "Agent 规划失败",
          status: "error",
        })
      } finally {
        this.planning = false
      }
    },

    async confirm(messageId: string) {
      const message = this.messages.find((item) => item.id === messageId)
      if (!message) return
      await this.executePlan(message)
    },

    async executePlan(message: AgentMessage) {
      if (!message.actions?.length || !message.runId) return

      this.executing = true
      const execution: Array<{ action: string; status: string; detail: string }> = []
      try {
        for (const action of message.actions) {
          try {
            const detail = await this.executeAction(action)
            execution.push({ action: action.label, status: "success", detail })
          } catch (error: any) {
            execution.push({
              action: action.label,
              status: "error",
              detail: error.response?.data?.detail || error.message || "执行失败",
            })
            break
          }
        }

        message.execution = execution
        await axios.post(`/api/agent/runs/${message.runId}/complete`, {
          status: execution.every((item) => item.status === "success") ? "completed" : "failed",
          execution,
        })
      } finally {
        this.executing = false
      }
    },

    async executeAction(action: AgentAction) {
      const dsStore = useDatasourceStore()
      const queryStore = useQueryStore()

      switch (action.type) {
        case "navigate": {
          const targetRoute = normalizeAgentRoute(action.params.route || action.params.path || action.params.page)
          await router.push(targetRoute)
          return `已打开 ${formatAgentRoute(targetRoute)}`
        }
        case "switch_datasource": {
          await dsStore.fetchDatasources()
          const matched = dsStore.datasources.find((item) => item.name === action.params.datasource_name)
          if (!matched) throw new Error(`未找到数据源 ${action.params.datasource_name}`)
          dsStore.switchDatasource(matched.id)
          return `已切换到数据源 ${matched.name}`
        }
        case "ask_query":
          if (router.currentRoute.value.path !== "/smart-query") {
            await router.push("/smart-query")
          }
          await queryStore.ask(action.params.question, "business")
          return "已发起智能问数"
        case "create_datasource":
          await axios.post("/api/datasources", { ...action.params, metadata_prompt: action.params.metadata_prompt || "" })
          return `已创建数据源 ${action.params.name}`
        case "update_datasource": {
          const list = await axios.get("/api/datasources")
          const target = list.data.find((item: any) => item.name === action.params.datasource_name)
          if (!target) throw new Error(`未找到数据源 ${action.params.datasource_name}`)
          await axios.put(`/api/datasources/${target.id}`, action.params.payload || {})
          return `已更新数据源 ${action.params.datasource_name}`
        }
        case "delete_datasource": {
          const list = await axios.get("/api/datasources")
          const target = list.data.find((item: any) => item.name === action.params.datasource_name)
          if (!target) throw new Error(`未找到数据源 ${action.params.datasource_name}`)
          await axios.delete(`/api/datasources/${target.id}`)
          return `已删除数据源 ${action.params.datasource_name}`
        }
        case "test_datasource": {
          const list = await axios.get("/api/datasources")
          const target = list.data.find((item: any) => item.name === action.params.datasource_name)
          if (!target) throw new Error(`未找到数据源 ${action.params.datasource_name}`)
          await axios.post(`/api/datasources/${target.id}/test`)
          return `已测试数据源 ${action.params.datasource_name}`
        }
        case "detect_schema": {
          const list = await axios.get("/api/datasources")
          const target = list.data.find((item: any) => item.name === action.params.datasource_name)
          if (!target) throw new Error(`未找到数据源 ${action.params.datasource_name}`)
          await axios.post(`/api/datasources/${target.id}/detect-schema`)
          return `已检测数据源 ${action.params.datasource_name} 的表结构`
        }
        case "generate_drill_config": {
          const list = await axios.get("/api/datasources")
          const target = list.data.find((item: any) => item.name === action.params.datasource_name)
          if (!target) throw new Error(`未找到数据源 ${action.params.datasource_name}`)
          await axios.post(`/api/datasources/${target.id}/generate-drill-config`)
          return `已生成数据源 ${action.params.datasource_name} 的钻取规则候选`
        }
        case "create_user":
          await axios.post("/api/users", action.params)
          return `已创建用户 ${action.params.username}`
        case "update_user": {
          const users = await axios.get("/api/users")
          const target = users.data.find((item: any) => item.username === action.params.username)
          if (!target) throw new Error(`未找到用户 ${action.params.username}`)
          await axios.put(`/api/users/${target.id}`, action.params.payload || {})
          return `已更新用户 ${action.params.username}`
        }
        case "delete_user": {
          const users = await axios.get("/api/users")
          const target = users.data.find((item: any) => item.username === action.params.username)
          if (!target) throw new Error(`未找到用户 ${action.params.username}`)
          await axios.delete(`/api/users/${target.id}`)
          return `已删除用户 ${action.params.username}`
        }
        case "create_organization":
          await axios.post("/api/organizations", action.params)
          return `已创建企业 ${action.params.name}`
        case "update_organization": {
          const orgs = await axios.get("/api/organizations")
          const target = orgs.data.find((item: any) => item.name === action.params.name)
          if (!target) throw new Error(`未找到企业 ${action.params.name}`)
          await axios.put(`/api/organizations/${target.id}`, action.params.payload || {})
          return `已更新企业 ${action.params.name}`
        }
        case "delete_organization": {
          const orgs = await axios.get("/api/organizations")
          const target = orgs.data.find((item: any) => item.name === action.params.name)
          if (!target) throw new Error(`未找到企业 ${action.params.name}`)
          await axios.delete(`/api/organizations/${target.id}`)
          return `已删除企业 ${action.params.name}`
        }
        case "create_metric":
          await axios.post("/api/metrics", action.params)
          return `已创建指标 ${action.params.name}`
        case "update_metric": {
          const metrics = await axios.get("/api/metrics")
          const target = metrics.data.items.find((item: any) => item.name === action.params.name)
          if (!target) throw new Error(`未找到指标 ${action.params.name}`)
          await axios.put(`/api/metrics/${target.id}`, action.params.payload || {})
          return `已更新指标 ${action.params.name}`
        }
        case "delete_metric": {
          const metrics = await axios.get("/api/metrics")
          const target = metrics.data.items.find((item: any) => item.name === action.params.name)
          if (!target) throw new Error(`未找到指标 ${action.params.name}`)
          await axios.delete(`/api/metrics/${target.id}`)
          return `已删除指标 ${action.params.name}`
        }
        case "create_dataset":
          await axios.post("/api/datasets", action.params)
          return `已创建数据集 ${action.params.name}`
        case "update_dataset": {
          const target = await resolveEntity(
            "/api/datasets",
            action.params,
            ["dataset_id", "id"],
            ["dataset_name", "name"],
            ["name"],
            "数据集",
          )
          await axios.put(
            `/api/datasets/${target.id}`,
            buildUpdatePayload(action.params, ["dataset_id", "id", "dataset_name"])
          )
          return `已更新数据集 ${target.name}`
        }
        case "publish_dataset": {
          const target = await resolveEntity(
            "/api/datasets",
            action.params,
            ["dataset_id", "id"],
            ["dataset_name", "name"],
            ["name"],
            "数据集",
          )
          await axios.post(`/api/datasets/${target.id}/publish`)
          return `已发布数据集 ${target.name}`
        }
        case "refresh_dataset": {
          const target = await resolveEntity(
            "/api/datasets",
            action.params,
            ["dataset_id", "id"],
            ["dataset_name", "name"],
            ["name"],
            "数据集",
          )
          await axios.post(`/api/datasets/${target.id}/refresh`)
          return `已刷新数据集 ${target.name}`
        }
        case "delete_dataset": {
          const target = await resolveEntity(
            "/api/datasets",
            action.params,
            ["dataset_id", "id"],
            ["dataset_name", "name"],
            ["name"],
            "数据集",
          )
          await axios.delete(`/api/datasets/${target.id}`)
          return `已删除数据集 ${target.name}`
        }
        case "create_dashboard":
          await axios.post("/api/dashboards", action.params)
          return `已创建看板 ${action.params.title || action.params.name}`
        case "update_dashboard": {
          const target = await resolveEntity(
            "/api/dashboards",
            action.params,
            ["dashboard_id", "id"],
            ["dashboard_title", "dashboard_name", "title", "name"],
            ["title", "name"],
            "看板",
          )
          await axios.put(
            `/api/dashboards/${target.id}`,
            buildUpdatePayload(action.params, ["dashboard_id", "id", "dashboard_title", "dashboard_name"])
          )
          return `已更新看板 ${target.title || target.name}`
        }
        case "publish_dashboard": {
          const target = await resolveEntity(
            "/api/dashboards",
            action.params,
            ["dashboard_id", "id"],
            ["dashboard_title", "dashboard_name", "title", "name"],
            ["title", "name"],
            "看板",
          )
          await axios.post(`/api/dashboards/${target.id}/publish`)
          return `已发布看板 ${target.title || target.name}`
        }
        case "delete_dashboard": {
          const target = await resolveEntity(
            "/api/dashboards",
            action.params,
            ["dashboard_id", "id"],
            ["dashboard_title", "dashboard_name", "title", "name"],
            ["title", "name"],
            "看板",
          )
          await axios.delete(`/api/dashboards/${target.id}`)
          return `已删除看板 ${target.title || target.name}`
        }
        case "create_pipeline":
          await axios.post("/api/pipelines", action.params)
          return `已创建可视化ETL ${action.params.name}`
        case "run_pipeline": {
          const target = await resolveEntity(
            "/api/pipelines",
            action.params,
            ["pipeline_id", "id"],
            ["pipeline_name", "name"],
            ["name"],
            "可视化ETL",
          )
          await axios.post(`/api/pipelines/${target.id}/run`, {
            mode: action.params.mode || "full",
            reason: action.params.reason || "Agent 触发",
          })
          return `已运行可视化ETL ${target.name}`
        }
        case "delete_pipeline": {
          const target = await resolveEntity(
            "/api/pipelines",
            action.params,
            ["pipeline_id", "id"],
            ["pipeline_name", "name"],
            ["name"],
            "可视化ETL",
          )
          await axios.delete(`/api/pipelines/${target.id}`)
          return `已删除可视化ETL ${target.name}`
        }
        case "create_analysis_view":
          await axios.post("/api/analysis-views", action.params)
          return `已创建自助分析 ${action.params.name}`
        case "update_analysis_view": {
          const target = await resolveEntity(
            "/api/analysis-views",
            action.params,
            ["view_id", "analysis_view_id", "id"],
            ["view_name", "analysis_name", "name"],
            ["name"],
            "自助分析",
          )
          await axios.put(
            `/api/analysis-views/${target.id}`,
            buildUpdatePayload(action.params, ["view_id", "analysis_view_id", "id", "view_name", "analysis_name"])
          )
          return `已更新自助分析 ${target.name}`
        }
        case "publish_analysis_view": {
          const target = await resolveEntity(
            "/api/analysis-views",
            action.params,
            ["view_id", "analysis_view_id", "id"],
            ["view_name", "analysis_name", "name"],
            ["name"],
            "自助分析",
          )
          await axios.post(`/api/analysis-views/${target.id}/publish`, {
            status: action.params.status || "published",
            visibility: action.params.visibility || "org",
          })
          return `已发布自助分析 ${target.name}`
        }
        case "create_report_template":
          await axios.post("/api/report-templates", action.params)
          return `已创建复杂报表模板 ${action.params.name}`
        case "update_report_template": {
          const target = await resolveEntity(
            "/api/report-templates",
            action.params,
            ["template_id", "report_template_id", "id"],
            ["template_name", "report_name", "name"],
            ["name"],
            "复杂报表模板",
          )
          await axios.put(
            `/api/report-templates/${target.id}`,
            buildUpdatePayload(action.params, ["template_id", "report_template_id", "id", "template_name", "report_name"])
          )
          return `已更新复杂报表模板 ${target.name}`
        }
        case "delete_report_template": {
          const target = await resolveEntity(
            "/api/report-templates",
            action.params,
            ["template_id", "report_template_id", "id"],
            ["template_name", "report_name", "name"],
            ["name"],
            "复杂报表模板",
          )
          await axios.delete(`/api/report-templates/${target.id}`)
          return `已删除复杂报表模板 ${target.name}`
        }
        case "create_action_item":
          await axios.post("/api/action-items", action.params)
          return `已创建行动项 ${action.params.title}`
        case "update_action_item": {
          const target = await resolveEntity(
            "/api/action-items",
            action.params,
            ["action_item_id", "item_id", "id"],
            ["action_item_title", "title", "name"],
            ["title", "name"],
            "行动项",
          )
          await axios.put(
            `/api/action-items/${target.id}`,
            buildUpdatePayload(action.params, ["action_item_id", "item_id", "id", "action_item_title"])
          )
          return `已更新行动项 ${target.title || target.name}`
        }
        case "delete_action_item": {
          const target = await resolveEntity(
            "/api/action-items",
            action.params,
            ["action_item_id", "item_id", "id"],
            ["action_item_title", "title", "name"],
            ["title", "name"],
            "行动项",
          )
          await axios.delete(`/api/action-items/${target.id}`)
          return `已删除行动项 ${target.title || target.name}`
        }
        case "update_llm_settings":
          await axios.put("/api/settings/llm", action.params)
          return "已更新大模型配置"
        case "refresh_llm_settings":
          await axios.post("/api/settings/llm/refresh")
          return "已刷新大模型缓存"
        case "install_agent_skill": {
          const installed = await this.installSkill(action.params.source)
          return `已安装 skill ${installed.name}`
        }
        default:
          throw new Error(`不支持的动作 ${action.type}`)
      }
    },

    reset() {
      this.messages = []
      this.input = ""
    },
  },
})
