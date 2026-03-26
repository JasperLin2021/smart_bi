import { defineStore } from "pinia"
import axios from "axios"
import { ElMessage } from "element-plus"
import { useDatasourceStore } from "@/store/datasource"

export interface QueryResult {
  columns: string[]
  rows: Array<Record<string, string | number>>
}

export interface ChatMessage {
  id: string
  role: "user" | "assistant"
  content: string
  timestamp: Date
  status: "sending" | "success" | "error"
  // 助手消息附加数据
  sqlQuery?: string
  result?: QueryResult
  summary?: string
  recommendations?: string[]
  mode?: "text2sql" | "chat"
  error?: string
}

export interface QueryHistoryItem {
  id: number
  question: string
  created_at: string
  favorite: boolean
}

export const useQueryStore = defineStore("query", {
  state: () => ({
    loading: false,
    messages: [] as ChatMessage[],
    history: [] as QueryHistoryItem[],
    mode: "text2sql" as "text2sql" | "chat"
  }),
  actions: {
    generateId() {
      return Date.now().toString(36) + Math.random().toString(36).substr(2)
    },
    
    async ask(question: string, queryMode?: "text2sql" | "chat") {
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
        mode
      }
      this.messages.push(assistantMessage)
      this.loading = true
      
      try {
        const dsStore = useDatasourceStore()
        const response = await axios.post("/api/query/ask", {
          question,
          mode,
          datasource_id: dsStore.currentId,
        })
        
        // 更新助手消息
        const idx = this.messages.findIndex(m => m.id === assistantMessage.id)
        if (idx !== -1) {
          this.messages[idx] = {
            ...assistantMessage,
            content: response.data.answer || response.data.summary || "查询完成",
            status: "success",
            sqlQuery: response.data.sql_query,
            result: response.data.result,
            summary: response.data.summary,
            recommendations: response.data.recommendations || []
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
            error: error.response?.data?.detail || error.message || "请稍后重试"
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
        if (dsStore.currentId) params.datasource_id = dsStore.currentId
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
          sqlQuery: data.sql_query,
          result: data.result,
          summary: data.summary,
          mode: data.mode
        }
        this.messages.push(assistantMessage)
        
        this.mode = data.mode || "text2sql"
      } catch (error) {
        ElMessage.error("加载历史记录失败")
      } finally {
        this.loading = false
      }
    }
  }
})
