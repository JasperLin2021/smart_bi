import { defineStore } from "pinia"
import axios from "axios"
import { ElMessage } from "element-plus"
import { useDatasourceStore } from "@/store/datasource"

export type QueryScopeMode = "datasource" | "dataset"

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
  mode?: "text2sql" | "chat"
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

export const useQueryStore = defineStore("query", {
  state: () => ({
    loading: false,
    messages: [] as ChatMessage[],
    history: [] as QueryHistoryItem[],
    mode: "text2sql" as "text2sql" | "chat",
    scopeMode: "datasource" as QueryScopeMode,
    selectedDatasourceId: null as number | null,
    selectedDatasetId: null as number | null,
  }),
  actions: {
    generateId() {
      return Date.now().toString(36) + Math.random().toString(36).substr(2)
    },
    
    async ask(
      question: string,
      queryMode?: "text2sql" | "chat",
      drillContext?: DrillContext,
      parentHistoryId?: number | null
    ) {
      const mode = queryMode || this.mode
      
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
        const datasetId = this.scopeMode === "dataset" ? this.selectedDatasetId : null
        const response = await axios.post("/api/query/ask", {
          question,
          mode,
          datasource_id: datasourceId,
          dataset_id: datasetId,
          drill_context: drillContext || null,
          parent_history_id: parentHistoryId || null,
        })
        
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
            sourceQuestion: question,
            drillContext
          }
        }
        
        await this.fetchHistory()
      } catch (error: any) {
        // 更新助手消息为错误状态
        const idx = this.messages.findIndex(m => m.id === assistantMessage.id)
        if (idx !== -1) {
          this.messages[idx] = {
            ...assistantMessage,
            content: "查询失败",
            status: "error",
            error: error.response?.data?.detail || error.message || "请稍后重试",
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
        
        // 清空当前消息
        this.messages = []
        
        // 添加用户消息
        const cleanQuestion = data.question.replace(/^\[(SQL|闲聊)\]\s*/, "")
        const userMessage: ChatMessage = {
          id: this.generateId(),
          role: "user",
          content: cleanQuestion,
          timestamp: new Date(data.created_at),
          status: "success"
        }
        this.messages.push(userMessage)
        
        // 添加助手消息
        const assistantMessage: ChatMessage = {
          id: this.generateId(),
          role: "assistant",
          content: data.mode === "chat" ? data.summary : "已加载历史查询结果。",
          timestamp: new Date(data.created_at),
          status: "success",
          historyId: data.id,
          sqlQuery: data.sql_query,
          result: data.result,
          summary: data.summary,
          llmModel: data.llm_model,
          mode: data.mode,
          trustSignals: data.trust_signals || [],
          sourceQuestion: cleanQuestion,
          drillContext: data.drill_context || undefined,
        }
        this.messages.push(assistantMessage)
        
        this.mode = data.mode || "text2sql"
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
