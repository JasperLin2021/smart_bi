<template>
  <div class="smart-query-page">
    <el-row :gutter="16" class="page-row">
      <el-col :xs="24" :md="17" :lg="18">
        <el-card class="chat-card">
          <template #header>
            <div class="card-header">
              <span class="card-header-title">智能问数助手</span>
              <div class="header-actions">
                <el-radio-group v-model="queryStore.mode" size="small">
                  <el-radio-button label="business">业务问数</el-radio-button>
                  <el-radio-button v-if="canUseAgenticMode" label="agentic">探索模式</el-radio-button>
                </el-radio-group>
                <el-button size="small" type="primary" plain @click="startNewConversation">
                  <el-icon><Plus /></el-icon>
                  新建对话
                </el-button>
                <el-button size="small" text :disabled="queryStore.messages.length === 0" @click="clearChat">
                  <el-icon><Delete /></el-icon>
                  清空当前
                </el-button>
              </div>
            </div>
          </template>

          <div class="query-scope-panel" :class="{ 'is-agentic': queryStore.mode === 'agentic' }">
            <div class="scope-mode">
              <span class="scope-label">{{ scopeLabel }}</span>
              <el-tag v-if="queryStore.mode === 'agentic'" size="small" effect="plain" type="primary">规划、校验并自动执行</el-tag>
              <el-tag v-else size="small" effect="plain" type="success">默认使用可信指标和数据集语义层</el-tag>
            </div>
            <el-select
              v-if="queryStore.mode === 'agentic'"
              v-model="queryStore.selectedDatasourceId"
              class="scope-select"
              filterable
              placeholder="选择数据源"
              :loading="datasourceStore.datasources.length === 0"
            >
              <el-option
                v-for="datasource in datasourceStore.datasources"
                :key="datasource.id"
                :label="datasource.name"
                :value="datasource.id"
              >
                <div class="scope-option">
                  <strong>{{ datasource.name }}</strong>
                  <small>{{ datasource.source_type === "excel" ? "Excel 数据源" : "数据库数据源" }}</small>
                </div>
              </el-option>
            </el-select>
            <el-select
              v-else
              v-model="queryStore.selectedDatasetId"
              class="scope-select"
              filterable
              placeholder="选择数据集"
              :loading="datasetsLoading"
              :disabled="datasets.length === 0"
            >
              <el-option
                v-for="dataset in datasets"
                :key="dataset.id"
                :label="dataset.name"
                :value="dataset.id"
              >
                <div class="scope-option">
                  <strong>{{ dataset.name }}</strong>
                  <small>{{ datasourceName(dataset.datasource_id) }}</small>
                </div>
              </el-option>
            </el-select>
            <span class="scope-current">{{ activeScopeText }}</span>
          </div>

          <div ref="chatContainerRef" class="chat-container">
            <div v-if="queryStore.messages.length === 0" class="welcome-message">
              <div class="welcome-icon">
                <el-icon :size="48"><ChatDotRound /></el-icon>
              </div>
              <h3>欢迎使用智能问数助手</h3>
              <p>{{ welcomeDescription }}</p>
              <div class="welcome-examples">
                <span class="example-label">试试这样问：</span>
                <el-tag
                  v-for="example in examples"
                  :key="example"
                  type="info"
                  effect="plain"
                  class="example-tag"
                  @click="useExample(example)"
                >
                  {{ example }}
                </el-tag>
              </div>
            </div>

            <div v-else class="messages-list">
              <ChatBubble
                v-for="message in queryStore.messages"
                :key="message.id"
                :message="message"
              />
            </div>
          </div>

          <div class="input-area">
            <el-input
              v-model="question"
              :placeholder="inputPlaceholder"
              :disabled="queryStore.loading || !queryContextReady"
              size="large"
              @keyup.enter="submit"
            >
              <template #prefix>
                <el-icon><Search /></el-icon>
              </template>
              <template #append>
                <el-button
                  type="primary"
                  :loading="queryStore.loading"
                  :disabled="!question.trim() || !queryContextReady"
                  @click="submit"
                >
                  <el-icon><Promotion /></el-icon>
                  发送
                </el-button>
              </template>
            </el-input>
            <div class="input-tips">
              <span v-if="queryContextReady">
                {{ queryStore.mode === "business" ? "业务问数" : "探索模式" }}当前使用{{ activeScopeTypeText }}：{{ activeScopeText }}
              </span>
              <span v-else-if="queryStore.mode === 'business'">
                业务问数必须选择数据集
              </span>
              <span v-else>
                请先选择数据源
              </span>
            </div>
          </div>
        </el-card>
      </el-col>

      <el-col :xs="24" :md="7" :lg="6">
        <el-card class="history-card">
          <template #header>
            <div class="card-header">
              <div class="history-title-wrap">
                <span class="card-header-title">查询历史</span>
                <el-tag class="history-count-tag" size="small" effect="plain">{{ historyCountText }}</el-tag>
              </div>
              <div class="history-header-actions">
                <el-button size="small" text @click="queryStore.fetchHistory">
                  <el-icon><Refresh /></el-icon>
                  刷新
                </el-button>
                <el-button
                  size="small"
                  text
                  type="danger"
                  :disabled="!queryStore.history.length"
                  @click="deleteAllHistoryItems"
                >
                  清空历史
                </el-button>
              </div>
            </div>
          </template>
          <div class="history-toolbar">
            <el-input
              v-model="historySearch"
              class="history-search"
              size="small"
              clearable
              placeholder="搜索历史问题"
            >
              <template #prefix>
                <el-icon><Search /></el-icon>
              </template>
            </el-input>
            <el-segmented
              v-model="historyFilter"
              class="history-filter"
              size="small"
              :options="historyFilterOptions"
            />
          </div>
          <div class="history-list">
            <div
              v-for="item in filteredHistory"
              :key="item.id"
              class="history-item"
              :class="{ 'is-active': activeHistoryId === item.id }"
              @click="viewHistory(item)"
            >
              <div class="history-item-top">
                <el-tag size="small" :type="historyModeTagType(item.question)" effect="plain">
                  {{ historyModeLabel(item.question) }}
                </el-tag>
                <span class="history-date">{{ formatHistoryDate(item.created_at) }}</span>
              </div>
              <div class="history-content">
                <el-icon class="history-icon"><ChatLineSquare /></el-icon>
                <span class="history-text">{{ cleanHistoryText(item.question) }}</span>
              </div>
              <div class="history-meta">
                <span class="history-source">{{ item.favorite ? "已收藏" : "普通历史" }}</span>
                <div class="history-actions">
                  <el-button
                    size="small"
                    text
                    :type="item.favorite ? 'warning' : 'info'"
                    :icon="item.favorite ? StarFilled : Star"
                    @click.stop="queryStore.toggleFavorite(item.id)"
                  >
                    {{ item.favorite ? "取消收藏" : "收藏" }}
                  </el-button>
                  <el-button
                    size="small"
                    text
                    type="danger"
                    :icon="Close"
                    @click.stop="confirmDeleteHistoryItem(item)"
                  >
                    删除
                  </el-button>
                </div>
              </div>
            </div>
            <el-empty v-if="!filteredHistory.length" :description="historyEmptyDescription" :image-size="72">
              <div class="history-empty-actions">
                <el-button
                  v-if="historySearch || historyFilter !== 'all'"
                  size="small"
                  @click="resetHistoryFilters"
                >
                  重置筛选
                </el-button>
                <el-button size="small" type="primary" plain @click="startNewConversation">
                  新建对话
                </el-button>
              </div>
            </el-empty>
          </div>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, ref, watch } from "vue"
import axios from "axios"
import { ElMessage, ElMessageBox } from "element-plus"
import {
  ChatDotRound, Search, Promotion, Delete, Refresh,
  ChatLineSquare, Star, StarFilled, Close, Plus
} from "@element-plus/icons-vue"
import ChatBubble from "@/components/ChatBubble.vue"
import { useQueryStore } from "@/store/query"
import { useDatasourceStore } from "@/store/datasource"
import { useAuthStore } from "@/store/auth"

const queryStore = useQueryStore()
const datasourceStore = useDatasourceStore()
const authStore = useAuthStore()
const question = ref("")
const chatContainerRef = ref<HTMLDivElement | null>(null)
const datasetsLoading = ref(false)
const historySearch = ref("")
const historyFilter = ref<"all" | "favorite">("all")
const activeHistoryId = ref<number | null>(null)
const historyFilterOptions = [
  { label: "全部", value: "all" },
  { label: "收藏", value: "favorite" },
]

interface DatasetItem {
  id: number
  name: string
  description: string | null
  datasource_id: number
  status: string
  visibility: string
}

interface HistoryItem {
  id: number
  question: string
  created_at: string
  favorite: boolean
}

const datasets = ref<DatasetItem[]>([])

const canUseAgenticMode = computed(() => authStore.canUseAgenticMode)
const agenticDefaultRoles = new Set(["dept_admin", "department_admin", "org_admin", "super_admin"])
const isDeptAdminOrAbove = computed(() => agenticDefaultRoles.has(authStore.profile?.role || ""))
const roleDefaultApplied = ref(false)

const businessExamples = [
  "最近 30 天各渠道销售额趋势",
  "华东区毛利率为什么下降？",
  "蓝途科技订单量 TOP10 商品"
]

const agenticExamples = [
  "先判断可用表，再统计最近 30 天各区域销售额",
  "分析订单数据里最适合回答复购率的问题并查询",
  "基于当前数据源生成一条安全 SQL 查看异常趋势"
]

const examples = computed(() => {
  if (queryStore.mode === "agentic") return agenticExamples
  return businessExamples
})

const welcomeDescription = computed(() => {
  if (queryStore.mode === "agentic") {
    return "探索模式会先规划查询路径，再生成和校验只读 SQL，并自动执行返回结果"
  }
  return "您可以用自然语言提问，我会优先使用可信指标、数据集指标和维度生成分析结果"
})

const inputPlaceholder = computed(() => {
  if (!queryContextReady.value) return "请先选择问数范围..."
  if (queryStore.mode === "business") return "基于数据集、可信指标和维度提问..."
  if (queryStore.mode === "agentic") return "基于数据源进行探索..."
  return "请输入问题..."
})

const scopeLabel = computed(() => {
  if (queryStore.mode === "business") return "业务数据集"
  if (queryStore.mode === "agentic") return "探索数据源"
  return "业务数据集"
})

const selectedDataset = computed(() =>
  datasets.value.find((dataset) => dataset.id === queryStore.selectedDatasetId) || null
)

const activeDatasource = computed(() =>
  datasourceStore.datasources.find((datasource) => datasource.id === queryStore.selectedDatasourceId) || null
)

const queryContextReady = computed(() => {
  if (queryStore.mode === "business") return Boolean(queryStore.selectedDatasetId)
  if (queryStore.mode === "agentic") return Boolean(queryStore.selectedDatasourceId)
  return false
})

const activeScopeText = computed(() => {
  if (queryStore.mode === "business") return selectedDataset.value?.name || "未选择数据集"
  if (queryStore.mode === "agentic") return activeDatasource.value?.name || "未选择数据源"
  return "未选择数据源"
})

const activeScopeTypeText = computed(() => {
  if (queryStore.mode === "business") return "数据集"
  if (queryStore.mode === "agentic") return "数据源"
  return "数据源"
})

const filteredHistory = computed(() => {
  const keyword = historySearch.value.trim().toLowerCase()
  return queryStore.history.filter((item) => {
    if (historyFilter.value === "favorite" && !item.favorite) return false
    if (!keyword) return true
    return cleanHistoryText(item.question).toLowerCase().includes(keyword)
  })
})

const historyCountText = computed(() => {
  const total = queryStore.history.length
  if (historySearch.value || historyFilter.value !== "all") {
    return `${filteredHistory.value.length}/${total} 条`
  }
  return `${total} 条`
})

const historyEmptyDescription = computed(() => {
  if (!queryStore.history.length) return "暂无历史记录，开始一次新对话后会自动保存"
  return "没有匹配的历史记录"
})

const datasourceName = (id: number) =>
  datasourceStore.datasources.find((datasource) => datasource.id === id)?.name || `数据源 #${id}`

const fetchDatasets = async () => {
  datasetsLoading.value = true
  try {
    const response = await axios.get("/api/datasets")
    datasets.value = response.data.items || []
  } catch {
    ElMessage.error("数据集加载失败")
  } finally {
    datasetsLoading.value = false
  }
}

const applyRoleDefaultMode = () => {
  if (roleDefaultApplied.value || !authStore.profile?.role) return
  if (isDeptAdminOrAbove.value) {
    queryStore.mode = "agentic"
  }
  roleDefaultApplied.value = true
}

const ensureScopeDefaults = (useRoleDefault = false) => {
  if (useRoleDefault) applyRoleDefaultMode()
  if (!canUseAgenticMode.value && queryStore.mode === "agentic") {
    queryStore.mode = "business"
  }
  if (queryStore.mode === "agentic") {
    queryStore.scopeMode = "datasource"
  } else {
    queryStore.scopeMode = "dataset"
  }
  if (!queryStore.selectedDatasourceId) {
    queryStore.selectedDatasourceId = datasourceStore.currentId || datasourceStore.datasources[0]?.id || null
  }
  if (queryStore.mode === "business" && !queryStore.selectedDatasetId && datasets.value.length > 0) {
    queryStore.selectedDatasetId = datasets.value[0].id
  }
  if (queryStore.mode === "business" && selectedDataset.value) {
    queryStore.selectedDatasourceId = selectedDataset.value.datasource_id
  }
}

const submit = async () => {
  const q = question.value.trim()
  if (!q || queryStore.loading) return
  if (!queryContextReady.value) {
    ElMessage.warning("请先选择问数范围")
    return
  }

  question.value = ""
  await queryStore.ask(q)
  scrollToBottom()
}

const useExample = (example: string) => {
  question.value = example
}

const viewHistory = async (item: HistoryItem) => {
  activeHistoryId.value = item.id
  await queryStore.loadHistoryDetail(item.id)
  scrollToBottom()
}

const confirmDeleteHistoryItem = async (item: HistoryItem) => {
  const title = cleanHistoryText(item.question).slice(0, 64)
  try {
    await ElMessageBox.confirm(
      `将删除这条查询历史：${title || `#${item.id}`}。删除后不可恢复，是否继续？`,
      "删除历史",
      {
        confirmButtonText: "删除",
        cancelButtonText: "取消",
        type: "warning",
      }
    )
    await queryStore.deleteHistory(item.id)
    if (activeHistoryId.value === item.id) {
      startNewConversation()
    }
  } catch {
    return
  }
}

const deleteAllHistoryItems = async () => {
  if (!queryStore.history.length) return
  try {
    await ElMessageBox.confirm(
      "将删除当前数据源下的全部查询历史，筛选条件不会影响清空范围。删除后不可恢复，是否继续？",
      "清空历史",
      {
        confirmButtonText: "删除",
        cancelButtonText: "取消",
        type: "warning",
      }
    )
    await queryStore.deleteAllHistory()
    historySearch.value = ""
    historyFilter.value = "all"
    activeHistoryId.value = null
    question.value = ""
  } catch {
    return
  }
}

const cleanHistoryText = (text: string) => {
  return text.replace(/^\[(SQL|闲聊|业务问数|探索问数|探索模式|Agentic问数)\]\s*/, "")
}

const historyModeLabel = (text: string) => {
  if (/^\[(探索模式|探索问数|Agentic问数)\]/.test(text)) return "探索"
  if (/^\[业务问数\]/.test(text)) return "业务"
  if (/^\[SQL\]/.test(text)) return "SQL"
  return "问数"
}

const historyModeTagType = (text: string) => {
  const label = historyModeLabel(text)
  if (label === "探索") return "primary"
  if (label === "业务") return "success"
  if (label === "SQL") return "warning"
  return "info"
}

const formatHistoryDate = (value: string) => {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value || "-"
  return date.toLocaleString("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  })
}

const resetHistoryFilters = () => {
  historySearch.value = ""
  historyFilter.value = "all"
}

const startNewConversation = () => {
  question.value = ""
  activeHistoryId.value = null
  queryStore.clearMessages()
  nextTick(() => {
    if (chatContainerRef.value) {
      chatContainerRef.value.scrollTop = 0
    }
  })
}

const clearChat = () => {
  startNewConversation()
}

const scrollToBottom = async () => {
  await nextTick()
  if (chatContainerRef.value) {
    chatContainerRef.value.scrollTop = chatContainerRef.value.scrollHeight
  }
}

watch(() => queryStore.messages.length, () => {
  scrollToBottom()
})

watch(() => queryStore.scopeMode, () => {
  ensureScopeDefaults()
  queryStore.fetchHistory()
})

watch(() => queryStore.mode, () => {
  ensureScopeDefaults()
  queryStore.fetchHistory()
})

watch(() => queryStore.selectedDatasourceId, (id) => {
  if (id) datasourceStore.switchDatasource(id)
  if (queryStore.mode === "agentic") {
    queryStore.fetchHistory()
  }
})

watch(() => queryStore.selectedDatasetId, () => {
  if (queryStore.mode === "business" && selectedDataset.value) {
    queryStore.selectedDatasourceId = selectedDataset.value.datasource_id
    datasourceStore.switchDatasource(selectedDataset.value.datasource_id)
  }
  if (queryStore.mode === "business") {
    queryStore.fetchHistory()
  }
})

watch(() => authStore.profile?.role, () => {
  ensureScopeDefaults(true)
  queryStore.fetchHistory()
})

onMounted(async () => {
  await datasourceStore.fetchDatasources()
  await fetchDatasets()
  ensureScopeDefaults(true)
  queryStore.fetchHistory()
})
</script>

<style scoped>
.smart-query-page {
  height: calc(100vh - 120px);
}

.page-row {
  height: 100%;
}

.chat-card {
  height: 100%;
  display: flex;
  flex-direction: column;
  border: 1px solid var(--app-border);
  box-shadow: var(--app-shadow-soft);
}

.chat-card:hover {
  transform: none;
}

.chat-card :deep(.el-card__header) {
  padding: 14px 16px;
  background: var(--app-surface);
}

.chat-card :deep(.el-card__body) {
  flex: 1;
  display: flex;
  flex-direction: column;
  padding: 0;
  overflow: hidden;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.card-header-title {
  font-weight: 600;
  font-size: 16px;
  display: flex;
  align-items: center;
  gap: 8px;
}

.card-header-title::before {
  content: '';
  width: 4px;
  height: 18px;
  background: var(--app-primary);
  border-radius: 2px;
}

.header-actions,
.history-header-actions {
  display: flex;
  align-items: center;
  gap: 12px;
}

.history-title-wrap {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
}

.history-count-tag {
  flex-shrink: 0;
}

.query-scope-panel {
  display: grid;
  grid-template-columns: auto minmax(220px, 340px) minmax(0, 1fr);
  align-items: center;
  gap: 12px;
  padding: 12px 16px;
  border-bottom: 1px solid var(--app-border);
  background: var(--app-surface);
}

.scope-mode {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
}

.scope-label {
  color: var(--app-text-muted);
  font-size: 12px;
  white-space: nowrap;
}

.scope-select {
  width: 100%;
}

.scope-option {
  display: flex;
  flex-direction: column;
  gap: 2px;
  line-height: 1.3;
}

.scope-option strong {
  color: var(--app-text);
  font-weight: 500;
}

.scope-option small,
.scope-current {
  color: var(--app-text-muted);
  font-size: 12px;
}

.scope-current {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.chat-container {
  flex: 1;
  overflow-y: auto;
  padding: 20px;
  background: var(--app-surface-muted);
}

.welcome-message {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  text-align: center;
  padding: 40px;
}

.welcome-icon {
  width: 64px;
  height: 64px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(15, 118, 110, 0.1);
  border: 1px solid rgba(15, 118, 110, 0.18);
  border-radius: var(--app-radius);
  margin-bottom: 20px;
  color: var(--app-primary);
}

.welcome-message h3 {
  margin: 0 0 12px;
  font-size: 20px;
  font-weight: 600;
  color: var(--app-text);
}

.welcome-message p {
  margin: 0 0 32px;
  color: var(--app-text-muted);
  font-size: 15px;
}

.welcome-examples {
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: 10px;
  width: 100%;
  max-width: 500px;
  min-width: 0;
}

.example-label {
  width: 100%;
  margin-bottom: 8px;
  font-size: 13px;
  color: var(--app-text-light);
}

.example-tag {
  cursor: pointer;
  max-width: 100%;
  height: auto;
  min-height: 32px;
  padding: 7px 12px;
  border-radius: 999px;
  transition: all 0.2s;
  background: var(--app-surface);
  border: 1px solid var(--app-border);
  white-space: normal;
}

.example-tag :deep(.el-tag__content) {
  line-height: 1.45;
  overflow-wrap: anywhere;
  text-align: left;
  white-space: normal;
}

.example-tag:hover {
  background: rgba(15, 118, 110, 0.08);
  color: var(--app-primary-dark);
  border-color: rgba(15, 118, 110, 0.24);
  transform: none;
  box-shadow: none;
}

.messages-list {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.input-area {
  padding: 16px;
  border-top: 1px solid var(--app-border);
  background: var(--app-surface);
}

.input-area :deep(.el-input__wrapper) {
  border-radius: var(--app-radius-sm);
  padding: 4px 4px 4px 16px;
  box-shadow: 0 0 0 1px var(--app-border);
}

.input-area :deep(.el-input-group__append) {
  background: var(--app-primary);
  border: none;
  padding: 0;
  border-radius: 0 var(--app-radius-sm) var(--app-radius-sm) 0;
}

.input-area :deep(.el-input-group__append .el-button) {
  margin: 0;
  padding: 0 24px;
  height: 100%;
  border: none;
  color: white;
  font-weight: 500;
}

.input-area :deep(.el-input-group__append .el-button:hover) {
  background: transparent;
}

.input-tips {
  margin-top: 10px;
  font-size: 12px;
  color: var(--app-text-light);
}

.history-card {
  height: 100%;
  border: 1px solid var(--app-border);
  box-shadow: var(--app-shadow-soft);
}

.history-card:hover {
  transform: none;
}

.history-card :deep(.el-card__header) {
  padding: 14px 16px;
  background: var(--app-surface);
}

.history-card :deep(.el-card__body) {
  padding: 0;
  overflow: hidden;
}

.history-toolbar {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 8px;
  padding: 12px;
  border-bottom: 1px solid var(--app-border-light);
  background: var(--app-surface);
}

.history-search {
  min-width: 0;
}

.history-filter {
  flex-shrink: 0;
}

.history-list {
  max-height: calc(100vh - 282px);
  overflow-y: auto;
}

.history-item {
  padding: 12px 14px;
  border-bottom: 1px solid var(--app-border-light);
  cursor: pointer;
  transition: background 0.2s, border-color 0.2s;
}

.history-item:hover {
  background: rgba(15, 118, 110, 0.05);
}

.history-item.is-active {
  background: rgba(15, 118, 110, 0.08);
  border-left: 3px solid var(--app-primary);
  padding-left: 11px;
}

.history-item-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 8px;
}

.history-content {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  margin-bottom: 8px;
}

.history-icon {
  flex-shrink: 0;
  color: var(--app-primary);
  margin-top: 2px;
}

.history-text {
  font-size: 13px;
  color: var(--app-text);
  line-height: 1.6;
  overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
}

.history-meta {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 10px;
}

.history-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}

.history-actions :deep(.el-button) {
  min-height: 28px;
  padding: 4px 6px;
}

.history-date,
.history-source {
  font-size: 11px;
  color: var(--app-text-light);
}

.history-source {
  min-width: 0;
}

.history-empty-actions {
  display: flex;
  justify-content: center;
  gap: 8px;
  flex-wrap: wrap;
}

.favorite-icon {
  color: var(--app-text-light);
  cursor: pointer;
  transition: all 0.2s;
}

.favorite-icon:hover,
.favorite-icon.is-favorite {
  color: var(--app-warning);
  transform: scale(1.1);
}

.delete-icon {
  color: var(--app-text-light);
  cursor: pointer;
  transition: all 0.2s;
}

.delete-icon:hover {
  color: var(--app-danger);
  transform: scale(1.1);
}

@media (max-width: 1024px) {
  .smart-query-page {
    height: auto;
    min-height: calc(100vh - 120px);
  }

  .page-row {
    height: auto;
  }

  .card-header {
    align-items: flex-start;
    flex-direction: column;
    gap: 10px;
  }

  .header-actions,
  .history-header-actions {
    flex-wrap: wrap;
    gap: 8px;
  }

  .query-scope-panel {
    grid-template-columns: 1fr;
    align-items: stretch;
  }

  .scope-mode {
    justify-content: space-between;
  }

  .chat-card,
  .history-card {
    height: auto;
  }

  .history-card {
    margin-top: 16px;
  }

  .history-list {
    max-height: 320px;
  }
}

@media (max-width: 640px) {
  .chat-container {
    padding: 14px;
  }

  .welcome-message {
    min-height: 420px;
    padding: 28px 12px;
  }

  .welcome-message p {
    margin-bottom: 24px;
    font-size: 14px;
  }

  .input-area {
    padding: 12px;
  }

  .input-area :deep(.el-input-group__append .el-button) {
    padding: 0 14px;
  }

  .history-toolbar {
    grid-template-columns: 1fr;
  }

  .history-meta {
    align-items: flex-start;
    flex-direction: column;
  }

  .history-actions {
    width: 100%;
    justify-content: flex-end;
  }
}
</style>
