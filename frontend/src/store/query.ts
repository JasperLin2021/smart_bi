import { defineStore } from "pinia"
import axios from "axios"
import { ElMessage } from "element-plus"
import { useDatasourceStore } from "@/store/datasource"

export type QueryScopeMode = "datasource" | "dataset"
export type QueryMode = "business" | "agentic"

const normalizeQueryMode = (mode?: string | null): QueryMode => {
  return mode === "agentic" || mode === "explore" ? "agentic" : "business"
}

export interface QueryResult {
  columns: string[]
  rows: Array<Record<string, string | number>>
}

export interface SemanticQueryRequest {
  dataset_id: number
  dimensions: string[]
  metrics: string[]
  filters?: Array<Record<string, unknown>>
  limit?: number
}

export interface SemanticQueryResponse {
  dataset_id: number
  columns: string[]
  labels: Record<string, string>
  rows: Array<Record<string, unknown>>
  sql_query: string
}

export interface MetricTrustSignal {
  metric_id: number
  metric_name: string
  definition?: string | null
  formula?: string | null
  owner_name?: string | null
  unit?: string | null
  certification_status: string
  certified_by?: string | null
  certified_at?: string | null
  caliber_version: string
  data_updated_at?: string | null
  quality_status: string
  quality_message?: string | null
}

export interface AgentTraceStep {
  stage: string
  status: string
  message: string
  detail?: Record<string, unknown> | null
}

export interface AgenticRefinementAction {
  label: string
  question: string
}

export interface AgenticQueryNotes {
  assumptions: string[]
  risk_flags: string[]
  suggested_refinements: AgenticRefinementAction[]
  confidence?: string | null
}

export interface EmptyDiagnostics {
  reason: string
  checks: string[]
  suggested_actions: AgenticRefinementAction[]
}

export interface ChartSpec {
  chart_type: "line" | "bar" | "horizontal_bar" | "area" | "pie" | "scatter" | "table" | "kpi" | string
  title?: string | null
  x_field?: string | null
  y_field?: string | null
  series_fields?: string[]
  layout?: "single" | "tabs_by_field" | string
  facet_field?: string | null
  sort_order?: "none" | "asc" | "desc" | string
  reason?: string | null
}

export interface DrillAction {
  id: string
  label: string
  action: string
  source_dimension_id: string
  source_dimension_label: string
  source_column: string
  source_value: string | number
  target_dimension_id: string
  target_dimension_label: string
  target_column: string
  question: string
}

export interface DrillPreviewResult {
  actions: DrillAction[]
  detail_action?: DrillAction | null
}

export interface DrillContext {
  pathLabel: string
  sourceLabel: string
  sourceValue: string | number
  targetLabel: string
  parentQuestion?: string
  parentContext?: DrillContext
}

export interface ChatMessage {
  id: string
  role: "user" | "assistant"
  content: string
  timestamp: Date
  status: "sending" | "success" | "error"
  historyId?: number
  // 助手消息附加数据
  sqlQuery?: string
  result?: QueryResult
  summary?: string
  llmModel?: string
  recommendations?: string[]
  trustSignals?: MetricTrustSignal[]
  agentTrace?: AgentTraceStep[]
  chartSpec?: ChartSpec | null
  agentNotes?: AgenticQueryNotes | null
  emptyDiagnostics?: EmptyDiagnostics | null
  mode?: QueryMode
  error?: string
  sourceQuestion?: string
  drillContext?: DrillContext
}

export interface QueryHistoryItem {
  id: number
  question: string
  created_at: string
  favorite: boolean
  parent_history_id?: number | null
}

export interface QueryHistoryDetail {
  id: number
  datasource_id?: number | null
  question: string
  created_at: string
  sql_query?: string | null
  result?: QueryResult
  summary?: string
  llm_model?: string | null
  mode?: string | null
  trust_signals?: MetricTrustSignal[]
  agent_trace?: AgentTraceStep[]
  chart_spec?: ChartSpec | null
  agent_notes?: AgenticQueryNotes | null
  empty_diagnostics?: EmptyDiagnostics | null
  drill_context?: DrillContext | null
  parent_history_id?: number | null
}

export const useQueryStore = defineStore("query", {
  state: () => ({
    loading: false,
    messages: [] as ChatMessage[],
    history: [] as QueryHistoryItem[],
    mode: "business" as QueryMode,
    scopeMode: "dataset" as QueryScopeMode,
    selectedDatasourceId: null as number | null,
    selectedDatasetId: null as number | null,
    currentConversationRootHistoryId: null as number | null,
    currentConversationContextKey: null as string | null,
  }),
  actions: {
    generateId() {
      return Date.now().toString(36) + Math.random().toString(36).substr(2)
    },

    buildConversationContextKey(mode: QueryMode, datasourceId?: number | null) {
      return `${mode}:${datasourceId || "none"}`
    },

    updateMessage(id: string, patch: Partial<ChatMessage>) {
      const idx = this.messages.findIndex(m => m.id === id)
      if (idx !== -1) {
        this.messages[idx] = {
          ...this.messages[idx],
          ...patch,
        }
      }
    },

    parseStreamEvent(block: string) {
      let eventName = "message"
      let data = ""
      for (const line of block.split(/\r?\n/)) {
        if (line.startsWith("event:")) {
          eventName = line.slice(6).trim()
        } else if (line.startsWith("data:")) {
          data += line.slice(5).trimStart()
        }
      }
      return { eventName, payload: data ? JSON.parse(data) : {} }
    },

    async askAgenticStream(
      requestPayload: Record<string, unknown>,
      assistantMessage: ChatMessage,
      question: string,
      drillContext: DrillContext | undefined,
      conversationContextKey: string
    ) {
      const token = localStorage.getItem("smart-bi-token")
      const response = await fetch("/api/query/ask-stream", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify(requestPayload),
      })

      if (!response.ok) {
        const detail = await response.json().catch(() => ({}))
        throw { response: { status: response.status, data: detail } }
      }
      if (!response.body) {
        throw new Error("浏览器不支持 ReadableStream 流式响应")
      }

      const reader = response.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ""
      let completed = false

      const processStreamBlock = (block: string) => {
        if (!block.trim()) return true
        const { eventName, payload } = this.parseStreamEvent(block)
        if (eventName === "trace") {
          const current = this.messages.find(m => m.id === assistantMessage.id)
          this.updateMessage(assistantMessage.id, {
            agentTrace: [...(current?.agentTrace || []), payload as AgentTraceStep],
          })
        } else if (eventName === "final") {
          completed = true
          if (
            payload.history_id &&
            (!this.currentConversationRootHistoryId || this.currentConversationContextKey !== conversationContextKey)
          ) {
            this.currentConversationRootHistoryId = Number(payload.history_id)
            this.currentConversationContextKey = conversationContextKey
          }
          this.updateMessage(assistantMessage.id, {
            content: payload.answer || payload.summary || "查询完成",
            status: "success",
            historyId: payload.history_id,
            sqlQuery: payload.sql_query,
            result: payload.result,
            summary: payload.summary,
            llmModel: payload.llm_model,
            recommendations: payload.recommendations || [],
            trustSignals: payload.trust_signals || [],
            chartSpec: payload.chart_spec || null,
            agentNotes: payload.agent_notes || null,
            emptyDiagnostics: payload.empty_diagnostics || null,
            agentTrace: payload.agent_trace || this.messages.find(m => m.id === assistantMessage.id)?.agentTrace || [],
            sourceQuestion: question,
            drillContext,
          })
        } else if (eventName === "error") {
          const current = this.messages.find(m => m.id === assistantMessage.id)
          const payloadTrace = Array.isArray(payload.agent_trace) ? payload.agent_trace : []
          this.updateMessage(assistantMessage.id, {
            content: "查询失败",
            status: "error",
            error: payload.message || "请稍后重试",
            sqlQuery: payload.sql_query,
            llmModel: payload.llm_model,
            agentTrace: payloadTrace.length ? payloadTrace : current?.agentTrace || [],
            sourceQuestion: question,
            drillContext,
          })
          ElMessage.error("查询失败，请查看探索模式执行过程")
          return false
        }
        return true
      }

      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })
        const blocks = buffer.split(/\n\n/)
        buffer = blocks.pop() || ""

        for (const block of blocks) {
          if (!processStreamBlock(block)) return false
        }
      }

      if (buffer.trim()) {
        if (!processStreamBlock(buffer)) return false
      }

      if (!completed) {
        throw new Error("流式响应提前结束")
      }
      return true
    },
    
    async ask(
      question: string,
      queryMode?: QueryMode,
      drillContext?: DrillContext,
      parentHistoryId?: number | null
    ) {
      const mode = normalizeQueryMode(queryMode || this.mode)
      
      // 添加用户消息
      const userMessage: ChatMessage = {
        id: this.generateId(),
        role: "user",
        content: question,
        timestamp: new Date(),
        status: "success"
      }
      this.messages.push(userMessage)
      
      // 添加助手消息占位（加载中）
      const assistantMessage: ChatMessage = {
        id: this.generateId(),
        role: "assistant",
        content: "",
        timestamp: new Date(),
        status: "sending",
        mode,
        sourceQuestion: question,
        drillContext
      }
      this.messages.push(assistantMessage)
      this.loading = true
      
      try {
        const dsStore = useDatasourceStore()
        const datasourceId = this.selectedDatasourceId || dsStore.currentId
        const datasetId = mode === "business" ? this.selectedDatasetId : null
        const conversationContextKey = this.buildConversationContextKey(mode, datasourceId)
        const canContinueConversation = this.currentConversationContextKey === conversationContextKey
        const effectiveParentHistoryId = parentHistoryId ?? (canContinueConversation ? this.currentConversationRootHistoryId : null)
        const requestPayload = {
          question,
          mode,
          datasource_id: datasourceId,
          dataset_id: datasetId,
          drill_context: drillContext || null,
          parent_history_id: effectiveParentHistoryId || null,
        }

        if (mode === "agentic") {
          const completed = await this.askAgenticStream(
            requestPayload,
            assistantMessage,
            question,
            drillContext,
            conversationContextKey,
          )
          if (completed) await this.fetchHistory()
          return
        }

        const response = await axios.post("/api/query/ask", requestPayload)
        if (
          response.data.history_id &&
          (!this.currentConversationRootHistoryId || !canContinueConversation)
        ) {
          this.currentConversationRootHistoryId = Number(response.data.history_id)
          this.currentConversationContextKey = conversationContextKey
        }
        
        // 更新助手消息
        const idx = this.messages.findIndex(m => m.id === assistantMessage.id)
        if (idx !== -1) {
          this.messages[idx] = {
            ...assistantMessage,
            content: response.data.answer || response.data.summary || "查询完成",
            status: "success",
            historyId: response.data.history_id,
            sqlQuery: response.data.sql_query,
            result: response.data.result,
            summary: response.data.summary,
            llmModel: response.data.llm_model,
            recommendations: response.data.recommendations || [],
            trustSignals: response.data.trust_signals || [],
            chartSpec: response.data.chart_spec || null,
            agentNotes: response.data.agent_notes || null,
            emptyDiagnostics: response.data.empty_diagnostics || null,
            agentTrace: response.data.agent_trace || [],
            sourceQuestion: question,
            drillContext
          }
        }
        
        await this.fetchHistory()
      } catch (error: any) {
        const errorDetail = error.response?.data?.detail
        const structuredError = errorDetail && typeof errorDetail === "object" ? errorDetail : null
        const errorAgentTrace = Array.isArray(structuredError?.agent_trace)
          ? structuredError.agent_trace
          : []
        const errorMessage = typeof errorDetail === "string"
          ? errorDetail
          : structuredError?.message || error.message || "请稍后重试"
        // 更新助手消息为错误状态
        const idx = this.messages.findIndex(m => m.id === assistantMessage.id)
        if (idx !== -1) {
          this.messages[idx] = {
            ...assistantMessage,
            content: "查询失败",
            status: "error",
            error: errorMessage,
            sqlQuery: structuredError?.sql_query,
            llmModel: structuredError?.llm_model,
            agentTrace: errorAgentTrace,
            sourceQuestion: question,
            drillContext
          }
        }
        ElMessage.error("查询失败，请稍后重试")
      } finally {
        this.loading = false
      }
    },
    
    clearMessages() {
      this.messages = []
      this.currentConversationRootHistoryId = null
      this.currentConversationContextKey = null
    },

    resetConversationContext() {
      this.currentConversationRootHistoryId = null
      this.currentConversationContextKey = null
    },
    
    async fetchHistory() {
      try {
        const dsStore = useDatasourceStore()
        const params: Record<string, any> = {}
        const datasourceId = this.selectedDatasourceId || dsStore.currentId
        if (datasourceId) params.datasource_id = datasourceId
        const response = await axios.get("/api/query/history", { params })
        this.history = response.data.items
      } catch (error) {
        ElMessage.error("历史记录加载失败")
      }
    },
    
    async toggleFavorite(id: number) {
      try {
        await axios.post(`/api/query/history/${id}/favorite`)
        await this.fetchHistory()
      } catch (error) {
        ElMessage.error("收藏操作失败")
      }
    },
    
    async deleteHistory(id: number) {
      try {
        await axios.delete(`/api/query/history/${id}`)
        await this.fetchHistory()
        if (this.currentConversationRootHistoryId === id) {
          this.clearMessages()
        }
        ElMessage.success("已删除")
      } catch (error) {
        ElMessage.error("删除失败")
      }
    },

    async deleteAllHistory() {
      try {
        const dsStore = useDatasourceStore()
        const params: Record<string, any> = {}
        const datasourceId = this.selectedDatasourceId || dsStore.currentId
        if (datasourceId) params.datasource_id = datasourceId
        await axios.delete("/api/query/history", { params })
        this.history = []
        this.messages = []
        this.currentConversationRootHistoryId = null
        this.currentConversationContextKey = null
        ElMessage.success("历史记录已清空")
      } catch (error) {
        ElMessage.error("清空失败")
      }
    },
    
    async loadHistoryDetail(id: number) {
      this.loading = true
      try {
        const response = await axios.get(`/api/query/history/${id}`)
        const data = response.data
        const conversation = Array.isArray(data.conversation) && data.conversation.length
          ? data.conversation as QueryHistoryDetail[]
          : [data as QueryHistoryDetail]
        const conversationRootId = data.parent_history_id || data.id
        const conversationDatasourceId = data.datasource_id || conversation[0]?.datasource_id || this.selectedDatasourceId || useDatasourceStore().currentId
        
        // 清空当前消息
        this.messages = []
        this.currentConversationRootHistoryId = conversationRootId
        
        let loadedMode: QueryMode = "business"
        conversation.forEach((turn) => {
          const cleanQuestion = turn.question.replace(/^\[(SQL|闲聊|业务问数|探索问数|探索模式|Agentic问数)\]\s*/, "")
          const historyMode = (turn.mode === "explore" ? "agentic" : normalizeQueryMode(turn.mode)) as QueryMode
          loadedMode = historyMode
          this.messages.push({
            id: this.generateId(),
            role: "user",
            content: cleanQuestion,
            timestamp: new Date(turn.created_at),
            status: "success",
          })
          this.messages.push({
            id: this.generateId(),
            role: "assistant",
            content: "已加载历史查询结果。",
            timestamp: new Date(turn.created_at),
            status: "success",
            historyId: turn.id,
            sqlQuery: turn.sql_query || undefined,
            result: turn.result,
            summary: turn.summary,
            llmModel: turn.llm_model || undefined,
            mode: historyMode,
            trustSignals: turn.trust_signals || [],
            agentTrace: turn.agent_trace || [],
            chartSpec: turn.chart_spec || null,
            agentNotes: turn.agent_notes || null,
            emptyDiagnostics: turn.empty_diagnostics || null,
            sourceQuestion: cleanQuestion,
            drillContext: turn.drill_context || undefined,
          })
        })

        this.mode = loadedMode
        this.currentConversationContextKey = this.buildConversationContextKey(loadedMode, conversationDatasourceId)
      } catch (error) {
        ElMessage.error("加载历史记录失败")
      } finally {
        this.loading = false
      }
    },

    async getDrillActions(
      question: string,
      sqlQuery: string,
      selectedColumn: string,
      columns: string[],
      row: Record<string, any>
    ): Promise<DrillPreviewResult> {
      const dsStore = useDatasourceStore()
      const datasourceId = this.selectedDatasourceId || dsStore.currentId
      if (!datasourceId) return { actions: [], detail_action: null }
      const response = await axios.post("/api/query/drill-preview", {
        datasource_id: datasourceId,
        question,
        sql_query: sqlQuery,
        selected_column: selectedColumn,
        columns,
        row,
      })
      return {
        actions: (response.data.actions || []) as DrillAction[],
        detail_action: (response.data.detail_action || null) as DrillAction | null,
      }
    },

    async runSemanticQuery(payload: SemanticQueryRequest): Promise<SemanticQueryResponse> {
      const response = await axios.post("/api/query/semantic", payload)
      return response.data as SemanticQueryResponse
    }
  }
})
