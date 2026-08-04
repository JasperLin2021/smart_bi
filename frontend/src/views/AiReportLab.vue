<template>
  <div class="page ai-report-page">
    <section class="enterprise-hero ai-report-hero">
      <div>
        <p class="eyebrow">AI REPORTING</p>
        <h2>AI 报表</h2>
        <p>用对话描述你的分析诉求，AI 自动生成带图表的 HTML 报表，可保存、分享并转入报表中心。</p>
      </div>
      <div class="hero-actions">
        <el-button :icon="Clock" @click="openHistory">历史报表</el-button>
      </div>
    </section>

    <section class="ai-report-toolbar">
      <el-input
        v-model="reportTitle"
        class="report-title-input"
        maxlength="80"
        placeholder="报表标题（保存、分享前必填）"
        @input="titleTouched = true"
      />
      <div class="toolbar-actions">
        <el-button :icon="Collection" :loading="saving" :disabled="!reportHtml" @click="saveReport">
          保存报表
        </el-button>
        <el-button :icon="Share" :loading="sharing" :disabled="!reportHtml" @click="shareReport">
          分享
        </el-button>
        <el-button
          type="primary"
          :icon="Promotion"
          :loading="publishing"
          :disabled="!reportHtml"
          @click="publishToReportCenter"
        >
          转入报表中心
        </el-button>
      </div>
    </section>

    <div class="ai-report-workspace">
      <section class="chat-panel">
        <div ref="chatContainerRef" class="chat-messages">
          <div v-if="messages.length === 0" class="chat-empty">
            <div class="chat-empty-icon">
              <el-icon :size="22"><MagicStick /></el-icon>
            </div>
            <h3>描述你想生成的报表</h3>
            <p>AI 会自动查询数据、生成图表，并在右侧实时预览 HTML 报表。</p>
            <div class="prompt-suggestion-grid">
              <button
                v-for="prompt in examplePrompts"
                :key="prompt"
                type="button"
                class="prompt-suggestion-card"
                @click="sendMessage(prompt)"
              >
                <el-icon><ChatDotRound /></el-icon>
                <span>{{ prompt }}</span>
              </button>
            </div>
          </div>

          <template v-else>
            <div
              v-for="message in messages"
              :key="message.id"
              class="chat-message"
              :class="`is-${message.role}`"
            >
              <div class="message-bubble" :class="{ 'is-error': message.status === 'error' }">
                <template v-if="message.role === 'assistant' && message.traces.length">
                  <button type="button" class="trace-toggle" @click="message.showTraces = !message.showTraces">
                    <el-icon><component :is="message.showTraces ? ArrowDown : ArrowRight" /></el-icon>
                    执行步骤（{{ message.traces.length }}）
                  </button>
                  <ul v-show="message.showTraces" class="trace-steps">
                    <li
                      v-for="(step, index) in message.traces"
                      :key="index"
                      class="trace-step"
                      :class="{ 'is-done': step.stage === 'tool_end' }"
                    >
                      <span class="trace-icon">{{ step.stage === "tool_end" ? "✓" : "⏳" }}</span>
                      🔍 {{ toolLabel(step.tool) }} {{ step.tool }}
                      <span v-if="step.summary" class="trace-summary">{{ step.summary }}</span>
                    </li>
                  </ul>
                </template>
                <p v-if="message.content" class="message-text">{{ message.content }}</p>
                <p v-else-if="message.status === 'streaming'" class="message-text is-thinking">AI 正在生成报表…</p>
                <p v-if="message.status === 'error'" class="message-error-text">
                  {{ message.error || "生成失败，请稍后重试" }}
                </p>
              </div>
            </div>
          </template>
        </div>

        <div class="chat-composer">
          <el-input
            v-model="input"
            type="textarea"
            :rows="2"
            resize="none"
            placeholder="例如：生成本月销售经营分析报表"
            :disabled="sending"
            @keydown.enter.exact.prevent="sendMessage()"
          />
          <el-button
            type="primary"
            :icon="Promotion"
            :loading="sending"
            :disabled="!input.trim()"
            @click="sendMessage()"
          >
            发送
          </el-button>
        </div>
      </section>

      <section class="preview-panel">
        <header class="preview-header">
          <strong>{{ reportTitle || "报表预览" }}</strong>
          <el-tag v-if="savedReportId" size="small" type="success" effect="plain">已保存 #{{ savedReportId }}</el-tag>
          <el-tag v-else-if="reportHtml" size="small" type="warning" effect="plain">未保存</el-tag>
        </header>
        <div class="preview-body">
          <iframe
            v-if="reportHtml"
            class="report-preview-frame"
            sandbox="allow-scripts"
            :srcdoc="reportHtml"
            title="AI 报表预览"
          ></iframe>
          <div v-else class="preview-empty">
            <el-icon :size="28"><DataAnalysis /></el-icon>
            <p>{{ sending ? "报表生成中，稍候将在此预览…" : "生成的报表将在这里实时预览" }}</p>
          </div>
        </div>
      </section>
    </div>

    <el-drawer v-model="historyVisible" title="历史报表" size="380px">
      <div v-loading="historyLoading" class="history-list">
        <el-empty v-if="!historyLoading && historyList.length === 0" description="暂无已保存的报表" :image-size="80" />
        <button
          v-for="item in historyList"
          :key="item.id"
          type="button"
          class="history-item"
          :disabled="loadingHistoryId === item.id"
          @click="loadHistoryReport(item)"
        >
          <strong>{{ item.title }}</strong>
          <span>{{ formatDate(item.updated_at || item.created_at) }}</span>
        </button>
      </div>
    </el-drawer>
  </div>
</template>

<script setup lang="ts">
import { nextTick, ref } from "vue"
import { useRouter } from "vue-router"
import axios from "axios"
import { ElMessage } from "element-plus"
import {
  ArrowDown,
  ArrowRight,
  ChatDotRound,
  Clock,
  Collection,
  DataAnalysis,
  MagicStick,
  Promotion,
  Share,
} from "@element-plus/icons-vue"

type TraceStep = { stage: string; tool?: string; summary?: string }

type ChatMessage = {
  id: string
  role: "user" | "assistant"
  content: string
  traces: TraceStep[]
  showTraces: boolean
  status: "success" | "streaming" | "error"
  error?: string
}

type AiReportSummary = {
  id: number
  title: string
  created_at?: string | null
  updated_at?: string | null
}

const router = useRouter()

const messages = ref<ChatMessage[]>([])
const input = ref("")
const sending = ref(false)
const reportTitle = ref("")
const titleTouched = ref(false)
const reportHtml = ref("")
const conversationId = ref<string | null>(null)
const savedReportId = ref<number | null>(null)
const savedSnapshot = ref("")
const saving = ref(false)
const sharing = ref(false)
const publishing = ref(false)
const historyVisible = ref(false)
const historyLoading = ref(false)
const historyList = ref<AiReportSummary[]>([])
const loadingHistoryId = ref<number | null>(null)
const chatContainerRef = ref<HTMLElement | null>(null)

const examplePrompts = [
  "生成本月销售经营分析报表",
  "生成各区域业绩对比分析报表",
  "生成库存周转与补货建议报表",
]

const toolLabels: Record<string, string> = {
  query_dataset: "查询数据集",
  query_datasource: "查询数据源",
  list_datasets: "列出数据集",
  run_sql: "执行 SQL",
  generate_chart: "生成图表",
}

const toolLabel = (tool?: string) => (tool && toolLabels[tool]) || "调用工具"

const generateId = () =>
  typeof crypto !== "undefined" && "randomUUID" in crypto
    ? crypto.randomUUID()
    : `msg-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`

const formatDate = (value?: string | null) => {
  if (!value) return "-"
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString("zh-CN", { hour12: false })
}

const scrollToBottom = async () => {
  await nextTick()
  const container = chatContainerRef.value
  if (container) container.scrollTop = container.scrollHeight
}

const parseStreamEvent = (block: string) => {
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
}

const sendMessage = async (preset?: string) => {
  const text = (preset ?? input.value).trim()
  if (!text || sending.value) return
  input.value = ""

  messages.value.push({ id: generateId(), role: "user", content: text, traces: [], showTraces: false, status: "success" })
  const assistant: ChatMessage = {
    id: generateId(),
    role: "assistant",
    content: "",
    traces: [],
    showTraces: true,
    status: "streaming",
  }
  messages.value.push(assistant)
  sending.value = true
  scrollToBottom()

  try {
    const token = localStorage.getItem("smart-bi-token")
    const response = await fetch("/agent-api/reports/chat", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: JSON.stringify({
        conversation_id: conversationId.value || undefined,
        message: text,
      }),
    })

    if (!response.ok) {
      const detail = await response.json().catch(() => ({} as Record<string, unknown>))
      throw new Error((detail?.detail as string) || (detail?.message as string) || `请求失败（${response.status}）`)
    }
    if (!response.body) {
      throw new Error("浏览器不支持 ReadableStream 流式响应")
    }

    const reader = response.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ""
    let finalized = false

    const processStreamBlock = (block: string) => {
      if (!block.trim()) return
      const { eventName, payload } = parseStreamEvent(block)
      if (eventName === "trace") {
        assistant.traces.push(payload as TraceStep)
      } else if (eventName === "text") {
        assistant.content += payload.delta || ""
        scrollToBottom()
      } else if (eventName === "report") {
        reportHtml.value = payload.html || ""
        if (payload.title && !titleTouched.value) {
          reportTitle.value = payload.title
        }
      } else if (eventName === "final") {
        finalized = true
        conversationId.value = payload.conversation_id || conversationId.value
        assistant.status = "success"
        if (!assistant.content) assistant.content = "报表已生成，可在右侧预览后继续对话调整。"
      } else if (eventName === "error") {
        assistant.status = "error"
        assistant.error = payload.message || "生成失败，请稍后重试"
        ElMessage.error(assistant.error)
      }
    }

    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      const blocks = buffer.split(/\n\n/)
      buffer = blocks.pop() || ""
      for (const block of blocks) processStreamBlock(block)
    }
    if (buffer.trim()) processStreamBlock(buffer)

    if (!finalized && assistant.status === "streaming") {
      assistant.status = "error"
      assistant.error = "流式响应提前结束"
      ElMessage.error("流式响应提前结束")
    }
  } catch (error: any) {
    assistant.status = "error"
    assistant.error = error?.message || "网络异常，请稍后重试"
    ElMessage.error(assistant.error)
  } finally {
    sending.value = false
    scrollToBottom()
  }
}

const currentSnapshot = () => `${reportTitle.value.trim()}::${reportHtml.value}`

const ensureSaved = async (): Promise<number | null> => {
  if (!reportHtml.value) {
    ElMessage.warning("请先生成报表")
    return null
  }
  if (!reportTitle.value.trim()) {
    ElMessage.warning("请先填写报表标题")
    return null
  }
  if (savedReportId.value && savedSnapshot.value === currentSnapshot()) {
    return savedReportId.value
  }
  saving.value = true
  try {
    const { data } = await axios.post("/api/ai-reports", {
      title: reportTitle.value.trim(),
      html: reportHtml.value,
      conversation_json: JSON.stringify({
        conversation_id: conversationId.value,
        messages: messages.value.map((message) => ({
          role: message.role,
          content: message.content,
        })),
      }),
    })
    savedReportId.value = data.id
    savedSnapshot.value = currentSnapshot()
    return data.id as number
  } catch (error: any) {
    ElMessage.error(error.response?.data?.detail || "保存失败")
    return null
  } finally {
    saving.value = false
  }
}

const saveReport = async () => {
  const id = await ensureSaved()
  if (id) ElMessage.success("报表已保存")
}

const copyToClipboard = async (text: string) => {
  if (navigator.clipboard?.writeText) {
    await navigator.clipboard.writeText(text)
    return
  }
  const textarea = document.createElement("textarea")
  textarea.value = text
  document.body.appendChild(textarea)
  textarea.select()
  document.execCommand("copy")
  document.body.removeChild(textarea)
}

const shareReport = async () => {
  const id = await ensureSaved()
  if (!id) return
  sharing.value = true
  try {
    const { data } = await axios.post(`/api/ai-reports/${id}/share`)
    const url = `${location.origin}/report-shared/${data.share_token}`
    await copyToClipboard(url)
    ElMessage.success("分享链接已复制到剪贴板")
  } catch (error: any) {
    ElMessage.error(error.response?.data?.detail || "分享失败")
  } finally {
    sharing.value = false
  }
}

const publishToReportCenter = async () => {
  const id = await ensureSaved()
  if (!id) return
  publishing.value = true
  try {
    await axios.post(`/api/ai-reports/${id}/publish-to-report-center`)
    ElMessage.success("已转入报表中心")
    router.push("/report-center")
  } catch (error: any) {
    ElMessage.error(error.response?.data?.detail || "转入报表中心失败")
  } finally {
    publishing.value = false
  }
}

const openHistory = async () => {
  historyVisible.value = true
  historyLoading.value = true
  try {
    const { data } = await axios.get("/api/ai-reports")
    historyList.value = Array.isArray(data) ? data : data.items || []
  } catch {
    ElMessage.error("历史报表加载失败")
  } finally {
    historyLoading.value = false
  }
}

const loadHistoryReport = async (item: AiReportSummary) => {
  if (loadingHistoryId.value) return
  loadingHistoryId.value = item.id
  try {
    const { data } = await axios.get(`/api/ai-reports/${item.id}`)
    reportTitle.value = data.title || item.title
    titleTouched.value = true
    reportHtml.value = data.html || ""
    savedReportId.value = data.id
    savedSnapshot.value = currentSnapshot()
    conversationId.value = null
    if (data.conversation_json) {
      try {
        const conversation = JSON.parse(data.conversation_json)
        conversationId.value = conversation?.conversation_id || null
      } catch {
        conversationId.value = null
      }
    }
    historyVisible.value = false
    ElMessage.success("已载入历史报表，可继续对话调整")
  } catch (error: any) {
    ElMessage.error(error.response?.data?.detail || "载入失败")
  } finally {
    loadingHistoryId.value = null
  }
}
</script>

<style scoped>
.ai-report-page {
  height: calc(100vh - 120px);
  min-height: 560px;
}

.enterprise-hero {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 16px;
  padding: 20px;
  background: var(--app-surface);
  border: 1px solid var(--app-border);
  border-radius: var(--app-radius);
}

.enterprise-hero h2 {
  margin: 4px 0 8px;
  font-size: 24px;
}

.enterprise-hero p {
  margin: 0;
  max-width: 720px;
  color: var(--app-text-muted);
  line-height: 1.6;
}

.eyebrow {
  color: var(--app-primary);
  font-size: 12px;
  font-weight: 700;
}

.hero-actions,
.toolbar-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.ai-report-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 12px 16px;
  background: var(--app-surface);
  border: 1px solid var(--app-border);
  border-radius: var(--app-radius);
}

.report-title-input {
  max-width: 420px;
}

.ai-report-workspace {
  flex: 1;
  min-height: 0;
  display: grid;
  grid-template-columns: minmax(340px, 420px) minmax(0, 1fr);
  gap: var(--app-spacing-16);
}

.chat-panel,
.preview-panel {
  display: flex;
  flex-direction: column;
  min-height: 0;
  background: var(--app-surface);
  border: 1px solid var(--app-border);
  border-radius: var(--app-radius);
  overflow: hidden;
}

.chat-messages {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: 16px;
}

.chat-empty {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 8px;
  padding: 24px 8px;
}

.chat-empty h3 {
  margin: 0;
  font-size: 17px;
}

.chat-empty p {
  margin: 0 0 8px;
  color: var(--app-text-muted);
  line-height: 1.6;
}

.chat-empty-icon {
  display: grid;
  place-items: center;
  width: 40px;
  height: 40px;
  color: var(--app-primary);
  background: var(--app-surface-subtle);
  border-radius: var(--app-radius);
}

.prompt-suggestion-grid {
  display: flex;
  flex-direction: column;
  gap: 8px;
  width: 100%;
}

.prompt-suggestion-card {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 12px;
  color: var(--app-text);
  text-align: left;
  background: var(--app-surface-muted);
  border: 1px solid var(--app-border-light);
  border-radius: var(--app-radius-sm);
  cursor: pointer;
  transition: border-color var(--app-transition), color var(--app-transition);
}

.prompt-suggestion-card:hover {
  color: var(--app-primary);
  border-color: var(--app-primary-light);
}

.chat-message {
  display: flex;
  margin-bottom: 12px;
}

.chat-message.is-user {
  justify-content: flex-end;
}

.message-bubble {
  max-width: 92%;
  padding: 10px 12px;
  background: var(--app-surface-muted);
  border: 1px solid var(--app-border-light);
  border-radius: var(--app-radius-sm);
}

.chat-message.is-user .message-bubble {
  color: #ffffff;
  background: var(--app-primary);
  border-color: var(--app-primary);
}

.message-bubble.is-error {
  border-color: var(--app-danger);
}

.message-text {
  margin: 0;
  line-height: 1.6;
  white-space: pre-wrap;
  word-break: break-word;
}

.message-text.is-thinking {
  color: var(--app-text-muted);
}

.message-error-text {
  margin: 6px 0 0;
  color: var(--app-danger);
}

.trace-toggle {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  margin-bottom: 6px;
  padding: 0;
  color: var(--app-text-muted);
  font-size: 12px;
  background: none;
  border: none;
  cursor: pointer;
}

.trace-steps {
  margin: 0 0 8px;
  padding: 0;
  list-style: none;
}

.trace-step {
  display: flex;
  align-items: baseline;
  gap: 6px;
  padding: 3px 0;
  color: var(--app-text-muted);
  font-size: 12px;
}

.trace-step.is-done {
  color: var(--app-success);
}

.trace-icon {
  font-size: 11px;
}

.trace-summary {
  color: var(--app-text-light);
}

.chat-composer {
  display: flex;
  align-items: flex-end;
  gap: 8px;
  padding: 12px;
  border-top: 1px solid var(--app-border-light);
}

.preview-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 16px;
  border-bottom: 1px solid var(--app-border-light);
}

.preview-body {
  position: relative;
  flex: 1;
  min-height: 0;
}

.report-preview-frame {
  width: 100%;
  height: 100%;
  border: none;
  background: #ffffff;
}

.preview-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 10px;
  height: 100%;
  color: var(--app-text-light);
}

.history-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.history-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 12px;
  text-align: left;
  background: var(--app-surface-muted);
  border: 1px solid var(--app-border-light);
  border-radius: var(--app-radius-sm);
  cursor: pointer;
  transition: border-color var(--app-transition);
}

.history-item:hover {
  border-color: var(--app-primary-light);
}

.history-item strong {
  color: var(--app-text);
}

.history-item span {
  color: var(--app-text-muted);
  font-size: 12px;
}

@media (max-width: 1100px) {
  .ai-report-page {
    height: auto;
  }

  .ai-report-workspace {
    grid-template-columns: 1fr;
  }

  .chat-panel {
    min-height: 420px;
  }

  .preview-body {
    min-height: 480px;
  }

  .ai-report-toolbar {
    align-items: stretch;
    flex-direction: column;
  }

  .report-title-input {
    max-width: none;
  }
}
</style>
