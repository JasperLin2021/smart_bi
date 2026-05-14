<template>
  <div class="chat-bubble" :class="[`chat-bubble--${message.role}`, { 'chat-bubble--error': message.status === 'error' }]">
    <!-- 头像 -->
    <div class="chat-avatar">
      <el-avatar :size="36" :class="message.role === 'user' ? 'avatar-user' : 'avatar-assistant'">
        {{ message.role === 'user' ? '我' : 'AI' }}
      </el-avatar>
    </div>
    
    <!-- 消息内容区 -->
    <div class="chat-content">
      <!-- 加载状态 -->
      <div v-if="message.status === 'sending'" class="chat-loading">
        <el-icon class="is-loading"><Loading /></el-icon>
        <span>正在思考中...</span>
      </div>
      
      <!-- 错误状态 -->
      <div v-else-if="message.status === 'error'" class="chat-error">
        <el-icon><WarningFilled /></el-icon>
        <span>{{ message.error || '请求失败，请重试' }}</span>
      </div>
      
      <!-- 正常消息 -->
      <template v-else>
        <!-- 用户消息 -->
        <div v-if="message.role === 'user'" class="bubble-text">
          {{ message.content }}
        </div>
        
        <!-- 助手消息 -->
        <div v-else class="assistant-content">
          <div v-if="message.drillContext" class="drill-context">
            <span class="drill-context-label">钻取路径</span>
            <div class="drill-context-body">
              <span class="drill-context-text">
                {{ breadcrumbText }}
              </span>
              <el-button
                v-if="message.drillContext.parentQuestion"
                size="small"
                text
                class="drill-back-btn"
                @click="goBackOneLevel"
              >
                返回上一层
              </el-button>
            </div>
          </div>

          <!-- 文字回复 -->
          <div v-if="message.content" class="bubble-text">
            {{ message.content }}
          </div>

          <div v-if="message.llmModel" class="model-chip">
            <span class="model-chip-label">实际模型</span>
            <code class="model-chip-value">{{ message.llmModel }}</code>
          </div>

          <div v-if="message.mode === 'explore'" class="explore-warning">
            探索结果，非认证口径
          </div>

          <div v-if="message.trustSignals?.length" class="trust-panel">
            <div class="trust-panel-title">
              <span>可信指标</span>
              <small>本次查询命中 {{ message.trustSignals.length }} 个统一口径</small>
            </div>
            <div class="trust-list">
              <div v-for="signal in message.trustSignals" :key="signal.metric_id" class="trust-item">
                <div class="trust-item-main">
                  <strong>{{ signal.metric_name }}</strong>
                  <span>{{ signal.owner_name || "未设置负责人" }} · {{ signal.caliber_version || "v1" }}</span>
                </div>
                <div class="trust-tags">
                  <el-tag size="small" :type="certificationTagType(signal.certification_status)" effect="plain">
                    {{ certificationLabel(signal.certification_status) }}
                  </el-tag>
                  <el-tag size="small" :type="qualityTagType(signal.quality_status)" effect="plain">
                    {{ qualityLabel(signal.quality_status) }}
                  </el-tag>
                </div>
                <p v-if="signal.quality_message">{{ signal.quality_message }}</p>
              </div>
            </div>
          </div>
          
          <!-- SQL 查询 (可折叠) -->
          <el-collapse v-if="message.sqlQuery" class="sql-collapse">
            <el-collapse-item title="技术细节 / SQL 查询语句" name="sql">
              <pre class="sql-code">{{ message.sqlQuery }}</pre>
            </el-collapse-item>
          </el-collapse>
          
          <!-- 分析总结 -->
          <div v-if="message.summary && message.summary !== message.content" class="summary-box">
            <div class="summary-title">
              <el-icon><DataAnalysis /></el-icon>
              <span>分析总结</span>
            </div>
            <div class="summary-text markdown-body" v-html="renderedSummary"></div>
          </div>

          <div v-if="canCreateAction" class="decision-action-bar">
            <div>
              <strong>生成行动项</strong>
              <span>把这次分析结论交给责任人跟踪处理</span>
            </div>
            <el-button size="small" type="primary" plain :icon="Tickets" @click="openActionDialog">
              创建
            </el-button>
          </div>

          <div v-if="hasResult" class="insight-action-bar">
            <div>
              <strong>智能洞察</strong>
              <span>自动识别贡献项、异常低值和可下钻方向</span>
            </div>
            <div class="insight-buttons">
              <el-button size="small" plain :loading="insightLoading" :icon="DataAnalysis" @click="runAutoInsights">
                自动洞察
              </el-button>
              <el-button size="small" plain :loading="attributionLoading" :icon="Tickets" @click="runAttribution">
                异常归因
              </el-button>
              <el-button v-if="props.message.historyId" size="small" plain :icon="CollectionTag" @click="saveInsightDialogVisible = true">
                保存为洞察
              </el-button>
            </div>
          </div>

          <div v-if="insightResult || attributionResult" class="insight-panel">
            <div v-if="insightResult" class="insight-section">
              <div class="insight-title">
                <span>自动洞察</span>
                <small>{{ insightResult.summary }}</small>
              </div>
              <div class="insight-list">
                <div v-for="item in insightResult.insights" :key="`${item.type}-${item.title}`" class="insight-item">
                  <el-tag size="small" :type="insightTagType(item.severity)" effect="light">{{ insightSeverityLabel(item.severity) }}</el-tag>
                  <div>
                    <strong>{{ item.title }}</strong>
                    <p>{{ item.description }}</p>
                  </div>
                </div>
              </div>
            </div>
            <div v-if="attributionResult" class="insight-section">
              <div class="insight-title">
                <span>异常归因</span>
                <small>{{ attributionResult.summary }}</small>
              </div>
              <div class="driver-list">
                <div v-for="driver in attributionResult.drivers" :key="`${driver.dimension}-${driver.value}`" class="driver-item">
                  <div>
                    <strong>{{ driver.dimension }} = {{ driver.value }}</strong>
                    <span>{{ driver.impact === 'negative' ? '负向' : '正向' }}贡献 {{ driver.contribution }}</span>
                  </div>
                  <el-progress :percentage="Math.min(driver.share, 100)" :stroke-width="8" />
                </div>
              </div>
              <div v-if="attributionResult.recommendations?.length" class="recommendation-strip">
                <span v-for="item in attributionResult.recommendations" :key="item">{{ item }}</span>
              </div>
            </div>
          </div>
          
          <!-- 查询结果图表 -->
          <div v-if="hasResult" class="chart-container">
            <MessageChart 
              :message="message"
              :columns="message.result!.columns" 
              :rows="message.result!.rows" 
              :sql-query="message.sqlQuery"
            />
          </div>
          
          <!-- 查询结果表格 -->
          <div v-if="hasResult" class="table-container">
            <MessageTable :message="message" :columns="message.result!.columns" :rows="message.result!.rows" />
          </div>
          
          <!-- 推荐标签 -->
          <div v-if="message.recommendations?.length" class="recommendations">
            <span class="rec-label">推荐维度：</span>
            <el-tag v-for="tag in message.recommendations" :key="tag" type="success" size="small" effect="plain">
              {{ tag }}
            </el-tag>
          </div>
        </div>
      </template>
      
      <!-- 时间戳 -->
      <div class="chat-time">
        {{ formatTime(message.timestamp) }}
      </div>
    </div>

    <el-dialog
      v-model="actionDialogVisible"
      title="从问数结果创建行动项"
      width="min(560px, calc(100vw - 32px))"
      destroy-on-close
    >
      <el-form label-position="top">
        <el-form-item label="行动项标题" required>
          <el-input v-model="actionForm.title" maxlength="160" placeholder="例：跟进本周销售额下滑" />
        </el-form-item>
        <el-form-item label="说明">
          <el-input v-model="actionForm.description" type="textarea" :rows="4" />
        </el-form-item>
        <el-row :gutter="12">
          <el-col :xs="24" :md="12">
            <el-form-item label="优先级">
              <el-select v-model="actionForm.priority" style="width: 100%">
                <el-option label="低" value="low" />
                <el-option label="中" value="medium" />
                <el-option label="高" value="high" />
                <el-option label="紧急" value="urgent" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :xs="24" :md="12">
            <el-form-item label="截止日期">
              <el-date-picker v-model="actionForm.due_date" type="date" value-format="YYYY-MM-DD" style="width: 100%" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="负责人 ID">
          <el-input-number v-model="actionForm.owner_id" :min="1" style="width: 180px" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="actionDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="actionSaving" @click="createActionItem">创建行动项</el-button>
      </template>
    </el-dialog>

    <!-- Save as insight dialog -->
    <el-dialog v-model="saveInsightDialogVisible" title="保存为洞察" width="440px">
      <el-form @submit.prevent>
        <el-form-item label="洞察标题">
          <el-input v-model="insightTitle" placeholder="为这条查询结果起个有意义的名字" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="saveInsightDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="savingInsight" @click="doSaveInsight">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, reactive, ref } from "vue"
import axios from "axios"
import { useRouter } from "vue-router"
import { ElMessage } from "element-plus"
import { Loading, WarningFilled, DataAnalysis, Tickets, CollectionTag } from "@element-plus/icons-vue"
import { marked } from "marked"
import { useQueryStore, type ChatMessage, type DrillContext } from "@/store/query"
import { useAuthStore } from "@/store/auth"
import MessageChart from "./MessageChart.vue"
import MessageTable from "./MessageTable.vue"

const props = defineProps<{
  message: ChatMessage
}>()

const queryStore = useQueryStore()
const authStore = useAuthStore()
const router = useRouter()
const actionDialogVisible = ref(false)
const actionSaving = ref(false)
const saveInsightDialogVisible = ref(false)
const insightTitle = ref("")
const savingInsight = ref(false)

const doSaveInsight = async () => {
  if (!props.message.historyId) return
  savingInsight.value = true
  try {
    await axios.post("/api/query/save-insight", {
      history_id: props.message.historyId,
      title: insightTitle.value || props.message.content.slice(0, 100),
    })
    ElMessage.success("已保存为洞察")
    saveInsightDialogVisible.value = false
    insightTitle.value = ""
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || "保存失败")
  } finally {
    savingInsight.value = false
  }
}
const actionForm = reactive({
  title: "",
  description: "",
  priority: "medium",
  due_date: "",
  owner_id: null as number | null,
  linked_metric_id: null as number | null,
})
const insightLoading = ref(false)
const attributionLoading = ref(false)
const insightResult = ref<AutoInsightResponse | null>(null)
const attributionResult = ref<AttributionResponse | null>(null)

interface AutoInsightResponse {
  summary: string
  insights: Array<{
    type: string
    title: string
    description: string
    severity: string
  }>
  metadata: Record<string, unknown>
}

interface AttributionResponse {
  metric_column: string | null
  summary: string
  confidence: string
  drivers: Array<{
    dimension: string
    value: string
    contribution: number
    share: number
    impact: string
  }>
  recommendations: string[]
}

const hasResult = computed(() => {
  return props.message.result && 
         props.message.result.rows && 
         props.message.result.rows.length > 0
})

// 渲染 Markdown
const renderedSummary = computed(() => {
  if (!props.message.summary) return ""
  return marked(props.message.summary, { breaks: true })
})

const canCreateAction = computed(() =>
  props.message.role === "assistant" &&
  props.message.status === "success" &&
  Boolean(props.message.historyId || props.message.summary || props.message.result?.rows?.length)
)

const buildBreadcrumb = (context?: DrillContext): string[] => {
  if (!context) return []
  const previous = buildBreadcrumb(context.parentContext)
  return [
    ...previous,
    `${context.sourceLabel} = ${context.sourceValue}`,
    context.targetLabel,
  ]
}

const breadcrumbText = computed(() => buildBreadcrumb(props.message.drillContext).join(" -> "))

const goBackOneLevel = async () => {
  const drillContext = props.message.drillContext
  if (!drillContext?.parentQuestion) return
  await queryStore.ask(drillContext.parentQuestion, "business", drillContext.parentContext)
}

const openActionDialog = () => {
  const question = props.message.sourceQuestion || "跟进分析结论"
  actionForm.title = question.length > 36 ? `${question.slice(0, 36)}...` : question
  actionForm.description = props.message.summary || props.message.content || "请根据本次问数结果安排后续跟进。"
  actionForm.priority = props.message.trustSignals?.some(signal => signal.quality_status === "error") ? "high" : "medium"
  actionForm.due_date = ""
  actionForm.owner_id = authStore.profile?.id || null
  actionForm.linked_metric_id = props.message.trustSignals?.[0]?.metric_id || null
  actionDialogVisible.value = true
}

const createActionItem = async () => {
  if (!actionForm.title.trim()) {
    ElMessage.warning("请输入行动项标题")
    return
  }
  actionSaving.value = true
  try {
    await axios.post("/api/action-items", {
      title: actionForm.title.trim(),
      description: actionForm.description || null,
      source_type: "query",
      source_id: props.message.historyId ? String(props.message.historyId) : props.message.id,
      source_payload: {
        question: props.message.sourceQuestion,
        summary: props.message.summary || props.message.content,
        sql_query: props.message.sqlQuery,
        row_count: props.message.result?.rows?.length || 0,
      },
      owner_id: actionForm.owner_id,
      priority: actionForm.priority,
      due_date: actionForm.due_date || null,
      linked_metric_id: actionForm.linked_metric_id,
    })
    ElMessage.success("行动项已创建")
    actionDialogVisible.value = false
    router.push("/action-items")
  } catch (error: any) {
    ElMessage.error(error.response?.data?.detail || "行动项创建失败")
  } finally {
    actionSaving.value = false
  }
}

const runAutoInsights = async () => {
  if (!props.message.result) return
  insightLoading.value = true
  try {
    const res = await axios.post("/api/insights/auto-insights", {
      columns: props.message.result.columns,
      rows: props.message.result.rows,
    })
    insightResult.value = res.data
  } catch (error: any) {
    ElMessage.error(error.response?.data?.detail || "自动洞察生成失败")
  } finally {
    insightLoading.value = false
  }
}

const runAttribution = async () => {
  if (!props.message.result) return
  attributionLoading.value = true
  try {
    const res = await axios.post("/api/insights/anomaly-attribution", {
      columns: props.message.result.columns,
      rows: props.message.result.rows,
    })
    attributionResult.value = res.data
  } catch (error: any) {
    ElMessage.error(error.response?.data?.detail || "异常归因生成失败")
  } finally {
    attributionLoading.value = false
  }
}

const insightSeverityLabel = (severity: string) => {
  const labels: Record<string, string> = {
    success: "机会",
    warning: "关注",
    danger: "风险",
    info: "洞察",
  }
  return labels[severity] || "洞察"
}

const insightTagType = (severity: string) => {
  const types: Record<string, "success" | "warning" | "info" | "danger"> = {
    success: "success",
    warning: "warning",
    danger: "danger",
    info: "info",
  }
  return types[severity] || "info"
}

const certificationLabel = (status: string) => {
  const labels: Record<string, string> = {
    draft: "草稿",
    pending_review: "待审核",
    certified: "已认证",
    deprecated: "已废弃",
  }
  return labels[status] || status
}

const certificationTagType = (status: string) => {
  const types: Record<string, "success" | "warning" | "info" | "danger"> = {
    draft: "info",
    pending_review: "warning",
    certified: "success",
    deprecated: "danger",
  }
  return types[status] || "info"
}

const qualityLabel = (status: string) => {
  const labels: Record<string, string> = {
    unknown: "未知",
    normal: "正常",
    stale: "过期",
    error: "异常",
  }
  return labels[status] || status
}

const qualityTagType = (status: string) => {
  const types: Record<string, "success" | "warning" | "info" | "danger"> = {
    unknown: "info",
    normal: "success",
    stale: "warning",
    error: "danger",
  }
  return types[status] || "info"
}

const formatTime = (date: Date) => {
  const d = new Date(date)
  return d.toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" })
}
</script>

<style scoped>
.chat-bubble {
  display: flex;
  gap: 12px;
  margin-bottom: 20px;
  max-width: 85%;
  animation: fadeInUp 0.3s ease-out;
}

@keyframes fadeInUp {
  from {
    opacity: 0;
    transform: translateY(10px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.chat-bubble--user {
  flex-direction: row-reverse;
  margin-left: auto;
}

.chat-bubble--assistant {
  flex-direction: row;
  margin-right: auto;
}

.chat-avatar {
  flex-shrink: 0;
}

.avatar-user {
  background: #0f766e;
  color: #fff;
  font-weight: 600;
}

.avatar-assistant {
  background: #102033;
  color: #fff;
  font-weight: 600;
}

.chat-content {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.chat-bubble--user .chat-content {
  align-items: flex-end;
}

.chat-bubble--assistant .chat-content {
  align-items: flex-start;
}

.bubble-text {
  background: var(--app-surface-muted);
  padding: 14px 18px;
  border-radius: 16px;
  line-height: 1.7;
  word-break: break-word;
  white-space: pre-wrap;
  font-size: 14px;
}

.chat-bubble--user .bubble-text {
  background: var(--app-primary);
  color: #fff;
  border-bottom-right-radius: 6px;
  box-shadow: 0 4px 12px rgba(15, 118, 110, 0.18);
}

.chat-bubble--assistant .bubble-text {
  background: var(--app-surface);
  border: 1px solid var(--app-border-light);
  border-bottom-left-radius: 6px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.04);
}

.chat-loading {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 14px 18px;
  background: var(--app-surface);
  border: 1px solid var(--app-border-light);
  border-radius: 16px;
  color: var(--app-text-muted);
}

.chat-loading .el-icon {
  color: var(--app-primary);
}

.chat-error {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 14px 18px;
  background: #fef2f2;
  border: 1px solid #fecaca;
  border-radius: 16px;
  color: #ef4444;
}

.chat-time {
  font-size: 11px;
  color: var(--app-text-light);
}

.assistant-content {
  display: flex;
  flex-direction: column;
  gap: 14px;
  width: 100%;
}

.drill-context {
  display: inline-flex;
  align-items: flex-start;
  gap: 8px;
  padding: 8px 12px;
  border-radius: 16px;
  background: #ecfdf5;
  color: #0f766e;
  font-size: 12px;
  border: 1px solid #b7e4d8;
}

.drill-context-label {
  font-weight: 600;
}

.drill-context-arrow {
  margin: 0 4px;
}

.drill-context-body {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.drill-back-btn {
  padding: 0;
}

.sql-collapse {
  background: var(--app-surface);
  border-radius: 12px;
  border: 1px solid var(--app-border-light);
  overflow: hidden;
}

.model-chip {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  border-radius: 999px;
  background: #f8fafc;
  border: 1px solid #dbe4f0;
  color: #334155;
  font-size: 12px;
}

.model-chip-label {
  color: #64748b;
  font-weight: 500;
}

.model-chip-value {
  font-family: "JetBrains Mono", "Fira Code", "Consolas", monospace;
  font-size: 12px;
  color: #0f172a;
}

.explore-warning {
  width: fit-content;
  max-width: 100%;
  padding: 8px 12px;
  border: 1px solid rgba(217, 119, 6, 0.28);
  border-radius: 10px;
  background: rgba(217, 119, 6, 0.08);
  color: #92400e;
  font-size: 12px;
  font-weight: 600;
}

.trust-panel {
  width: 100%;
  padding: 12px;
  border: 1px solid #c7d2fe;
  border-radius: 12px;
  background: #f8fafc;
}

.trust-panel-title {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: center;
  margin-bottom: 10px;
}

.trust-panel-title span {
  font-weight: 600;
  color: #1e3a8a;
}

.trust-panel-title small {
  color: #64748b;
}

.trust-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.trust-item {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 8px 12px;
  padding: 10px;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  background: #fff;
}

.trust-item-main {
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 0;
}

.trust-item-main strong {
  color: #0f172a;
}

.trust-item-main span,
.trust-item p {
  color: #64748b;
  font-size: 12px;
  line-height: 1.5;
}

.trust-tags {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 6px;
}

.trust-item p {
  grid-column: 1 / -1;
  margin: 0;
}

.sql-collapse :deep(.el-collapse-item__header) {
  padding: 0 16px;
  font-size: 13px;
  height: 44px;
  font-weight: 500;
  color: var(--app-text);
}

.sql-collapse :deep(.el-collapse-item__content) {
  padding: 0;
}

.sql-code {
  background: #1e1b4b;
  color: #e0e7ff;
  padding: 16px;
  border-radius: 0 0 12px 12px;
  font-family: "JetBrains Mono", "Fira Code", "Consolas", monospace;
  font-size: 13px;
  overflow-x: auto;
  margin: 0;
  white-space: pre-wrap;
  word-break: break-all;
  line-height: 1.6;
}

.summary-box {
  background: linear-gradient(135deg, #ecfdf5 0%, #d1fae5 100%);
  border: 1px solid #a7f3d0;
  border-radius: 12px;
  padding: 16px;
}

.summary-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-weight: 600;
  color: #059669;
  margin-bottom: 10px;
}

.summary-text {
  color: var(--app-text);
  line-height: 1.7;
}

.summary-text.markdown-body {
  font-size: 14px;
}

.summary-text.markdown-body :deep(h1),
.summary-text.markdown-body :deep(h2),
.summary-text.markdown-body :deep(h3) {
  margin: 14px 0 10px;
  font-weight: 600;
  color: var(--app-text);
}

.summary-text.markdown-body :deep(h1) { font-size: 18px; }
.summary-text.markdown-body :deep(h2) { font-size: 16px; }
.summary-text.markdown-body :deep(h3) { font-size: 15px; }

.summary-text.markdown-body :deep(p) {
  margin: 10px 0;
}

.summary-text.markdown-body :deep(ul),
.summary-text.markdown-body :deep(ol) {
  padding-left: 20px;
  margin: 10px 0;
}

.summary-text.markdown-body :deep(li) {
  margin: 6px 0;
}

.summary-text.markdown-body :deep(code) {
  background: rgba(0, 0, 0, 0.06);
  padding: 2px 6px;
  border-radius: 4px;
  font-family: "JetBrains Mono", "Fira Code", monospace;
  font-size: 13px;
}

.summary-text.markdown-body :deep(pre) {
  background: #1e1b4b;
  color: #e0e7ff;
  padding: 14px;
  border-radius: 8px;
  overflow-x: auto;
}

.summary-text.markdown-body :deep(pre code) {
  background: transparent;
  padding: 0;
}

.summary-text.markdown-body :deep(table) {
  width: 100%;
  border-collapse: collapse;
  margin: 14px 0;
}

.summary-text.markdown-body :deep(th),
.summary-text.markdown-body :deep(td) {
  border: 1px solid var(--app-border);
  padding: 10px 14px;
  text-align: left;
}

.summary-text.markdown-body :deep(th) {
  background: var(--app-surface-muted);
  font-weight: 600;
}

.summary-text.markdown-body :deep(strong) {
  font-weight: 600;
  color: var(--app-text);
}

.decision-action-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 12px 14px;
  border: 1px solid var(--app-border-light);
  border-radius: 10px;
  background: var(--app-surface-muted);
}

.insight-action-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 12px 14px;
  border: 1px solid #bfdbfe;
  border-radius: 10px;
  background: #eff6ff;
}

.insight-action-bar > div:first-child {
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 0;
}

.insight-action-bar strong {
  color: #1e3a8a;
  font-size: 14px;
}

.insight-action-bar span {
  color: #475569;
  font-size: 12px;
}

.insight-buttons {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  justify-content: flex-end;
}

.insight-panel {
  width: 100%;
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 14px;
  border: 1px solid #dbe4f0;
  border-radius: 12px;
  background: #fff;
}

.insight-section {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.insight-title {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: center;
}

.insight-title span {
  font-weight: 700;
  color: var(--app-text);
}

.insight-title small {
  color: var(--app-text-muted);
  text-align: right;
}

.insight-list,
.driver-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.insight-item {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr);
  gap: 10px;
  padding: 10px;
  border: 1px solid var(--app-border-light);
  border-radius: 8px;
  background: var(--app-surface-muted);
}

.insight-item strong,
.driver-item strong {
  display: block;
  color: var(--app-text);
  font-size: 13px;
}

.insight-item p,
.driver-item span {
  margin: 4px 0 0;
  color: var(--app-text-muted);
  font-size: 12px;
  line-height: 1.5;
}

.driver-item {
  display: grid;
  grid-template-columns: minmax(0, 220px) minmax(160px, 1fr);
  gap: 12px;
  align-items: center;
  padding: 10px;
  border: 1px solid var(--app-border-light);
  border-radius: 8px;
}

.recommendation-strip {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.recommendation-strip span {
  padding: 6px 10px;
  border-radius: 999px;
  background: #f8fafc;
  color: #475569;
  font-size: 12px;
  border: 1px solid #e2e8f0;
}

.decision-action-bar div {
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 0;
}

.decision-action-bar strong {
  color: var(--app-text);
  font-size: 14px;
}

.decision-action-bar span {
  color: var(--app-text-muted);
  font-size: 12px;
}

.chart-container,
.table-container {
  background: var(--app-surface);
  border: 1px solid var(--app-border-light);
  border-radius: 12px;
  overflow: hidden;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.04);
}

.recommendations {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 10px;
}

.rec-label {
  font-size: 13px;
  color: var(--app-text-muted);
  font-weight: 500;
}

.recommendations :deep(.el-tag) {
  border-radius: 20px;
  padding: 4px 12px;
}

@media (max-width: 640px) {
  .decision-action-bar,
  .insight-action-bar {
    align-items: stretch;
    flex-direction: column;
  }

  .driver-item {
    grid-template-columns: 1fr;
  }
}
</style>
