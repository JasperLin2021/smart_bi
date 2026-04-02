import { defineStore } from "pinia"
import axios from "axios"
import { ElMessage } from "element-plus"

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
          route: router.currentRoute.value.path,
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
        case "navigate":
          await router.push(action.params.route)
          return `已打开 ${action.params.route}`
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
          await queryStore.ask(action.params.question, "text2sql")
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
