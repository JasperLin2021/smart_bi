<template>
  <div class="smart-query-page">
    <div class="query-workspace query-compact-workspace" :data-active-mode="queryStore.mode">
      <div class="query-layout query-history-left-layout">
        <main class="conversation-shell">
          <section class="scope-console query-workbench-toolbar" :class="{ 'is-agentic': queryStore.mode === 'agentic' }">
            <el-radio-group v-model="queryStore.mode" class="mode-tabs query-mode-switcher" size="small">
              <el-radio-button label="business">
                <el-icon><DataAnalysis /></el-icon>
                <span>业务问数</span>
              </el-radio-button>
              <el-radio-button v-if="canUseAgenticMode" label="agentic">
                <el-icon><MagicStick /></el-icon>
                <span>探索模式</span>
              </el-radio-button>
            </el-radio-group>
            <div class="query-toolbar-scope">
              <span class="scope-label">{{ scopeLabel }}</span>
              <strong class="scope-current">{{ activeScopeText }}</strong>
              <el-select
                v-if="queryStore.mode === 'agentic'"
                v-model="queryStore.selectedDatasourceId"
                class="scope-select"
                filterable
                popper-class="query-scope-popper"
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
                popper-class="query-scope-popper"
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
              <el-tag class="scope-state-tag" size="small" :type="queryContextReady ? 'success' : 'warning'" effect="plain">
                {{ queryContextReady ? "已就绪" : "待选择" }}
              </el-tag>
            </div>
            <div class="query-toolbar-actions">
              <el-button type="primary" plain @click="startNewConversation">
                <el-icon><Plus /></el-icon>
                新建对话
              </el-button>
              <el-button text :disabled="queryStore.messages.length === 0" @click="clearChat">
                <el-icon><Delete /></el-icon>
                清空当前
              </el-button>
            </div>
          </section>

          <div ref="chatContainerRef" class="chat-container">
            <div v-if="queryStore.messages.length === 0" class="welcome-message welcome-panel query-start-panel">
              <div class="welcome-primary query-start-copy">
                <div class="welcome-icon query-start-icon">
                  <el-icon :size="22"><ChatDotRound /></el-icon>
                </div>
                <div class="welcome-copy">
                  <h2>提出一个问题，直接查看结果</h2>
                  <p>{{ composerHintText }}</p>
                </div>
              </div>
              <div class="prompt-suggestion-grid prompt-suggestion-rail query-prompt-list" aria-label="示例问题">
                <button
                  v-for="card in suggestionCards"
                  :key="card.title"
                  type="button"
                  class="prompt-suggestion-card query-prompt-action"
                  @click="useExample(card.title)"
                >
                  <el-icon><component :is="card.icon" /></el-icon>
                  <span>{{ card.title }}</span>
                </button>
              </div>
            </div>

            <div v-else class="messages-list">
              <ChatBubble
                v-for="message in queryStore.messages"
                :key="message.id"
                :message="message"
                @use-refinement="applyRefinementDraft"
              />
            </div>
          </div>

          <section
            class="command-composer"
            :class="{ 'is-composer-focused': composeFocused, 'is-disabled': !queryContextReady }"
          >
            <div class="composer-topline">
              <span>{{ composerStatusText }}</span>
              <el-tag size="small" effect="plain">{{ activeScopeTypeText }}</el-tag>
            </div>
            <el-input
              ref="composerInputRef"
              v-model="question"
              class="composer-input"
              type="textarea"
              :autosize="{ minRows: 2, maxRows: 5 }"
              :placeholder="inputPlaceholder"
              :disabled="queryStore.loading || !queryContextReady"
              resize="none"
              @focus="composeFocused = true"
              @blur="composeFocused = false"
              @keydown.enter="submitOnEnter"
            />
            <div class="composer-footer">
              <div class="composer-hints">
                <span>{{ composerHintText }}</span>
              </div>
              <el-button
                class="composer-submit"
                type="primary"
                :loading="queryStore.loading"
                :disabled="!question.trim() || !queryContextReady"
                @click="submit"
              >
                <el-icon><Promotion /></el-icon>
                发送
              </el-button>
            </div>
          </section>
        </main>

        <aside class="history-card query-side-panel">
          <div class="side-panel-header">
            <div>
              <span class="side-panel-eyebrow">History</span>
              <strong>查询历史</strong>
            </div>
            <el-tag class="history-count-tag" size="small" effect="plain">{{ historyCountText }}</el-tag>
          </div>
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
              :class="{ 'is-active': activeHistoryId === item.id, 'is-loading': historyLoadingId === item.id }"
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
                <el-icon v-if="historyLoadingId === item.id" class="history-loading-icon is-loading"><Loading /></el-icon>
                <div class="history-actions">
                  <el-button
                    size="small"
                    text
                    :type="item.favorite ? 'warning' : 'info'"
                    :icon="item.favorite ? StarFilled : Star"
                    :disabled="Boolean(historyLoadingId)"
                    @click.stop="queryStore.toggleFavorite(item.id)"
                  >
                    {{ item.favorite ? "取消收藏" : "收藏" }}
                  </el-button>
                  <el-button
                    size="small"
                    text
                    type="danger"
                    :icon="Close"
                    :disabled="Boolean(historyLoadingId)"
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
          <div class="side-panel-footer">
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
        </aside>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, ref, watch } from "vue"
import axios from "axios"
import { ElMessage, ElMessageBox } from "element-plus"
import {
  ChatDotRound, Search, Promotion, Delete, Refresh,
  ChatLineSquare, Star, StarFilled, Close, Plus,
  DataAnalysis, MagicStick, Monitor, TrendCharts, Compass, Loading
} from "@element-plus/icons-vue"
import ChatBubble from "@/components/ChatBubble.vue"
import { useQueryStore } from "@/store/query"
import { useDatasourceStore } from "@/store/datasource"
import { useAuthStore } from "@/store/auth"

const queryStore = useQueryStore()
const datasourceStore = useDatasourceStore()
const authStore = useAuthStore()
const question = ref("")
const composerInputRef = ref<any>(null)
const chatContainerRef = ref<HTMLDivElement | null>(null)
const datasetsLoading = ref(false)
const historySearch = ref("")
const historyFilter = ref<"all" | "favorite">("all")
const activeHistoryId = ref<number | null>(null)
const historyLoadingId = ref<number | null>(null)
const isRestoringHistory = ref(false)
const composeFocused = ref(false)
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

const suggestionCards = computed(() => {
  const icons = queryStore.mode === "agentic"
    ? [MagicStick, Compass, TrendCharts]
    : [TrendCharts, DataAnalysis, Monitor]
  return examples.value.map((title, index) => ({
    title,
    icon: icons[index] || DataAnalysis,
  }))
})

const inputPlaceholder = computed(() => {
  if (!queryContextReady.value) return "请先选择问数范围..."
  if (queryStore.mode === "business") return "输入业务问题，例如：最近 30 天销售额趋势"
  if (queryStore.mode === "agentic") return "输入探索问题，例如：先判断可用表，再统计异常趋势"
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

const composerStatusText = computed(() => {
  if (queryStore.loading) return "正在分析"
  if (!queryContextReady.value && queryStore.mode === "business") return "业务问数必须选择数据集"
  if (!queryContextReady.value) return "请先选择数据源"
  return `${queryStore.mode === "business" ? "业务问数" : "探索模式"} · ${activeScopeText.value}`
})

const composerHintText = computed(() => {
  if (!queryContextReady.value) return "选择问数范围后即可开始"
  if (queryStore.mode === "agentic") return "描述目标、时间范围和维度，探索模式会生成安全 SQL 并执行"
  return "围绕已选数据集提问，可直接获得图表、表格和分析总结"
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

const submitOnEnter = (event: KeyboardEvent) => {
  if (event.shiftKey) return
  event.preventDefault()
  submit()
}

const useExample = (example: string) => {
  question.value = example
  composeFocused.value = true
}

const applyRefinementDraft = async (draftQuestion: string) => {
  const nextQuestion = draftQuestion.trim()
  if (!nextQuestion) return
  question.value = nextQuestion
  composeFocused.value = true
  await nextTick()
  composerInputRef.value?.focus?.()
  ElMessage.success("已填入建议问题，可编辑后发送")
}

const viewHistory = async (item: HistoryItem) => {
  if (historyLoadingId.value || queryStore.loading) return
  historyLoadingId.value = item.id
  isRestoringHistory.value = true
  try {
    await queryStore.loadHistoryDetail(item.id)
    activeHistoryId.value = item.id
    await scrollToBottom()
  } finally {
    isRestoringHistory.value = false
    historyLoadingId.value = null
  }
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

const refreshHistoryForScope = () => {
  if (isRestoringHistory.value) return
  queryStore.fetchHistory()
}

watch(() => queryStore.messages.length, () => {
  scrollToBottom()
})

watch(() => queryStore.scopeMode, () => {
  ensureScopeDefaults()
  refreshHistoryForScope()
})

watch(() => queryStore.mode, () => {
  ensureScopeDefaults()
  refreshHistoryForScope()
})

watch(() => queryStore.selectedDatasourceId, (id) => {
  if (id) datasourceStore.switchDatasource(id)
  if (queryStore.mode === "agentic") {
    refreshHistoryForScope()
  }
})

watch(() => queryStore.selectedDatasetId, () => {
  if (queryStore.mode === "business" && selectedDataset.value) {
    queryStore.selectedDatasourceId = selectedDataset.value.datasource_id
    datasourceStore.switchDatasource(selectedDataset.value.datasource_id)
  }
  if (queryStore.mode === "business") {
    refreshHistoryForScope()
  }
})

watch(() => authStore.profile?.role, () => {
  ensureScopeDefaults(true)
  refreshHistoryForScope()
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
  --query-primary: #0f766e;
  --query-primary-hover: #0d9488;
  --query-primary-soft: #f0fdfa;
  --query-primary-tint: #ecfdf5;
  --query-primary-border: #a7f3d0;
  --query-surface: #ffffff;
  --query-surface-muted: #f8fafc;
  --query-border: #dbe4f0;
  --query-border-soft: #eef2f7;
  --query-text: #0f172a;
  --query-text-soft: #334155;
  --query-muted: #64748b;
  --query-light: #94a3b8;
  --query-danger: #dc2626;
  --query-danger-soft: #fef2f2;
  --query-warning: #a16207;
  --query-warning-soft: #fffbeb;
  --query-radius: 8px;
  --query-radius-lg: 12px;
  --query-control-height: 36px;
  --query-shadow-sm: 0 1px 0 rgba(15, 23, 42, 0.03);
  --query-shadow-md: 0 10px 22px rgba(15, 23, 42, 0.08);
  --query-shadow-panel: 0 12px 26px rgba(15, 23, 42, 0.07);
  --query-focus-ring: 0 0 0 3px rgba(15, 118, 110, 0.13);
  --el-color-primary: var(--query-primary);
  --el-border-radius-base: var(--query-radius);
  min-height: calc(100vh - 120px);
  height: calc(100vh - 120px);
  padding: 0;
  background:
    linear-gradient(180deg, #f8fafc 0%, #eef7f5 54%, #f8fafc 100%);
  color: var(--query-text);
}

.query-workspace {
  display: grid;
  grid-template-columns: 1fr;
  grid-template-rows: minmax(0, 1fr);
  height: 100%;
  padding: 10px;
}

.query-layout {
  grid-column: 1 / -1;
}

.smart-query-page :deep(.el-button) {
  min-height: var(--query-control-height);
  padding: 8px 12px;
  border: 1px solid var(--query-border);
  border-radius: var(--query-radius);
  background: var(--query-surface);
  color: var(--query-text-soft);
  box-shadow: none;
  font-weight: 650;
  transition:
    color 0.16s ease,
    background 0.16s ease,
    border-color 0.16s ease,
    box-shadow 0.16s ease,
    transform 0.16s ease;
}

.smart-query-page :deep(.el-button:hover),
.smart-query-page :deep(.el-button:focus) {
  border-color: rgba(15, 118, 110, 0.38);
  background: var(--query-primary-soft);
  color: var(--query-primary);
  transform: translateY(-1px);
}

.smart-query-page :deep(.el-button:focus-visible) {
  outline: 0;
  box-shadow: var(--query-focus-ring);
}

.smart-query-page :deep(.el-button.is-disabled),
.smart-query-page :deep(.el-button.is-disabled:hover) {
  border-color: var(--query-border-soft);
  background: var(--query-surface-muted);
  color: var(--query-light);
  transform: none;
  opacity: 0.78;
}

.smart-query-page :deep(.el-button--primary) {
  border-color: var(--query-primary);
  background: var(--query-primary);
  color: #ffffff;
  box-shadow: 0 8px 18px rgba(15, 118, 110, 0.18);
}

.smart-query-page :deep(.el-button--primary:hover),
.smart-query-page :deep(.el-button--primary:focus) {
  border-color: var(--query-primary-hover);
  background: var(--query-primary-hover);
  color: #ffffff;
}

.smart-query-page :deep(.el-button--primary.is-plain) {
  border-color: var(--query-primary-border);
  background: var(--query-primary-soft);
  color: var(--query-primary);
  box-shadow: none;
}

.smart-query-page :deep(.el-button--primary.is-plain:hover),
.smart-query-page :deep(.el-button--primary.is-plain:focus) {
  border-color: rgba(15, 118, 110, 0.45);
  background: var(--query-primary-tint);
  color: var(--query-primary);
}

.smart-query-page :deep(.el-button.is-text) {
  min-height: 32px;
  padding: 6px 8px;
  border-color: transparent;
  background: transparent;
  color: var(--query-muted);
  box-shadow: none;
}

.smart-query-page :deep(.el-button.is-text:hover),
.smart-query-page :deep(.el-button.is-text:focus) {
  background: var(--query-surface-muted);
  color: var(--query-primary);
  transform: none;
}

.smart-query-page :deep(.el-button--danger.is-text) {
  color: var(--query-danger);
}

.smart-query-page :deep(.el-button--danger.is-text:hover),
.smart-query-page :deep(.el-button--danger.is-text:focus) {
  background: var(--query-danger-soft);
  color: var(--query-danger);
}

.smart-query-page :deep(.el-button--warning.is-text) {
  color: var(--query-warning);
}

.smart-query-page :deep(.el-tag) {
  height: 24px;
  padding: 0 8px;
  border: 1px solid var(--query-border);
  border-radius: 999px;
  background: var(--query-surface);
  color: var(--query-muted);
  font-weight: 700;
}

.smart-query-page :deep(.el-tag--info) {
  border-color: var(--query-border);
  background: var(--query-surface-muted);
  color: var(--query-muted);
}

.smart-query-page :deep(.el-tag--primary),
.smart-query-page :deep(.el-tag--success) {
  border-color: var(--query-primary-border);
  background: var(--query-primary-soft);
  color: var(--query-primary);
}

.smart-query-page :deep(.el-tag--warning) {
  border-color: #fde68a;
  background: var(--query-warning-soft);
  color: var(--query-warning);
}

.smart-query-page :deep(.el-tag--danger) {
  border-color: #fecaca;
  background: var(--query-danger-soft);
  color: var(--query-danger);
}

.scope-select :deep(.el-select__wrapper),
.history-search :deep(.el-input__wrapper) {
  min-height: var(--query-control-height);
  border-radius: var(--query-radius);
  background: var(--query-surface);
  box-shadow: inset 0 0 0 1px var(--query-border);
  transition: box-shadow 0.16s ease, background 0.16s ease;
}

.scope-select :deep(.el-select__wrapper:hover),
.history-search :deep(.el-input__wrapper:hover) {
  box-shadow: inset 0 0 0 1px rgba(15, 118, 110, 0.38);
}

.scope-select :deep(.el-select__wrapper.is-focused),
.history-search :deep(.el-input__wrapper.is-focus) {
  box-shadow:
    inset 0 0 0 1px rgba(15, 118, 110, 0.62),
    var(--query-focus-ring);
}

.scope-select :deep(.el-select__placeholder),
.history-search :deep(.el-input__inner::placeholder),
.composer-input :deep(.el-textarea__inner::placeholder) {
  color: var(--query-light);
}

.history-search {
  min-width: 0;
}

.history-filter {
  min-height: var(--query-control-height);
  padding: 3px;
  border: 1px solid var(--query-border);
  border-radius: var(--query-radius-lg);
  background: var(--query-surface-muted);
  box-shadow: none;
  flex-shrink: 0;
}

.history-filter :deep(.el-segmented) {
  min-height: 100%;
  padding: 0;
  border: 0;
  border-radius: var(--query-radius-lg);
  background: transparent;
  box-shadow: none;
}

.history-filter :deep(.el-segmented__group) {
  gap: 2px;
}

.history-filter :deep(.el-segmented__item) {
  min-height: 28px;
  border-radius: var(--query-radius);
  color: var(--query-muted);
  font-weight: 700;
}

.history-filter :deep(.el-segmented__item:hover) {
  color: var(--query-primary);
  background: var(--query-primary-soft);
}

.history-filter :deep(.el-segmented__item-selected),
.history-filter :deep(.el-segmented__item.is-selected) {
  background: var(--query-primary);
  color: #ffffff;
  box-shadow: 0 8px 18px rgba(15, 118, 110, 0.2);
}

.history-filter :deep(.el-segmented__item-selected .el-segmented__item-label),
.history-filter :deep(.el-segmented__item.is-selected .el-segmented__item-label) {
  color: #ffffff;
}

.history-list :deep(.el-empty) {
  padding: 32px 16px;
}

.history-list :deep(.el-empty__description p) {
  color: var(--query-muted);
  font-size: 12px;
}

.history-list :deep(.el-empty__image) {
  opacity: 0.72;
}

:global(.query-scope-popper) {
  --query-primary: #0f766e;
  --query-primary-soft: #f0fdfa;
  --query-primary-tint: #ecfdf5;
  --query-border: #dbe4f0;
  --query-text-soft: #334155;
  --query-muted: #64748b;
  --query-radius: 8px;
  --query-radius-lg: 12px;
  --query-shadow-panel: 0 12px 26px rgba(15, 23, 42, 0.07);
  border: 1px solid var(--query-border) !important;
  border-radius: var(--query-radius-lg) !important;
  box-shadow: var(--query-shadow-panel) !important;
}

:global(.query-scope-popper .el-select-dropdown__list) {
  padding: 6px;
}

:global(.query-scope-popper .el-select-dropdown__item) {
  height: auto;
  min-height: 42px;
  margin: 2px 0;
  padding: 7px 10px;
  border-radius: var(--query-radius);
  color: var(--query-text-soft);
  line-height: 1.35;
}

:global(.query-scope-popper .el-select-dropdown__item.is-hovering),
:global(.query-scope-popper .el-select-dropdown__item:hover) {
  background: var(--query-primary-soft);
  color: var(--query-primary);
}

:global(.query-scope-popper .el-select-dropdown__item.is-selected) {
  background: var(--query-primary-tint);
  color: var(--query-primary);
  font-weight: 750;
}

:global(.query-scope-popper .scope-option) {
  display: grid;
  gap: 2px;
}

:global(.query-scope-popper .scope-option strong) {
  color: inherit;
  font-size: 13px;
}

:global(.query-scope-popper .scope-option small) {
  color: var(--query-muted);
  font-size: 11px;
}

.mode-tabs {
  padding: 3px;
  border: 1px solid var(--query-border);
  border-radius: var(--query-radius-lg);
  background: var(--query-surface-muted);
}

.mode-tabs :deep(.el-radio-button__inner) {
  min-height: 34px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 7px 12px;
  border: 0;
  border-radius: var(--query-radius);
  background: transparent;
  color: var(--query-muted);
  font-weight: 600;
  box-shadow: none;
  transition: background 0.18s ease, color 0.18s ease, box-shadow 0.18s ease, transform 0.18s ease;
}

.mode-tabs :deep(.el-radio-button__original-radio:checked + .el-radio-button__inner) {
  background: var(--query-primary);
  color: #ffffff;
  box-shadow: 0 8px 18px rgba(15, 118, 110, 0.22);
}

.mode-tabs :deep(.el-radio-button__inner:hover) {
  color: var(--query-primary);
  background: var(--query-primary-tint);
}

.mode-tabs :deep(.el-radio-button__original-radio:checked + .el-radio-button__inner:hover) {
  color: #ffffff;
  background: var(--query-primary);
}

.query-mode-switcher {
  justify-self: start;
  flex-shrink: 0;
}

.query-layout {
  min-height: 0;
  display: grid;
  grid-template-columns: minmax(280px, 318px) minmax(0, 1fr);
  grid-template-areas: "history chat";
  gap: 10px;
}

.conversation-shell,
.query-side-panel {
  min-height: 0;
  border: 1px solid rgba(148, 163, 184, 0.28);
  border-radius: var(--query-radius-lg);
  background: rgba(255, 255, 255, 0.94);
  box-shadow: var(--query-shadow-panel);
  overflow: hidden;
}

.conversation-shell {
  grid-area: chat;
  display: grid;
  grid-template-rows: auto minmax(0, 1fr) auto;
}

.scope-console {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) auto;
  align-items: center;
  gap: 12px;
  padding: 8px 10px;
  border-bottom: 1px solid var(--query-border);
  background: var(--query-surface);
}

.query-toolbar-scope {
  display: grid;
  grid-template-columns: auto minmax(120px, 0.55fr) minmax(260px, 1fr) auto;
  align-items: center;
  gap: 8px;
  min-width: 0;
  padding-inline: 10px;
  border-inline: 1px solid var(--query-border-soft);
}

.scope-current {
  min-width: 0;
  color: var(--query-text);
  font-size: 13px;
  font-weight: 650;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.query-toolbar-actions {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  flex-wrap: wrap;
  gap: 8px;
}

.scope-label {
  color: var(--query-muted);
  font-size: 11px;
  white-space: nowrap;
}

.scope-select {
  width: 100%;
}

.scope-state-tag {
  justify-self: end;
}

.chat-container {
  min-height: 0;
  overflow-y: auto;
  padding: 14px;
  background: var(--query-surface-muted);
}

.welcome-message {
  min-height: 100%;
  width: min(100%, 760px);
  display: grid;
  grid-template-columns: 1fr;
  align-items: center;
  align-content: center;
  justify-content: stretch;
  gap: 8px;
  margin: 0 auto;
  padding: 14px;
  text-align: left;
}

.welcome-primary {
  position: relative;
  display: grid;
  grid-template-columns: auto minmax(0, 1fr);
  align-items: center;
  align-content: center;
  gap: 11px;
  min-width: 0;
  min-height: 82px;
  padding: 14px 15px 14px 17px;
  border: 1px solid var(--query-border);
  border-radius: var(--query-radius);
  background: var(--query-surface);
  box-shadow: 0 8px 20px rgba(15, 23, 42, 0.05);
  overflow: hidden;
}

.query-start-copy::before {
  content: "";
  position: absolute;
  left: 0;
  top: 14px;
  bottom: 14px;
  width: 3px;
  border-radius: 999px;
  background: var(--query-primary);
}

.welcome-icon {
  width: 38px;
  height: 38px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 0;
  border-radius: var(--query-radius);
  color: var(--query-primary);
  background: var(--query-primary-soft);
  border: 1px solid var(--query-primary-border);
  box-shadow: none;
}

.welcome-copy {
  min-width: 0;
}

.welcome-message h2 {
  margin: 0 0 5px;
  color: var(--query-text);
  font-size: 17px;
  line-height: 1.25;
}

.welcome-message p {
  max-width: 620px;
  margin: 0;
  color: var(--query-muted);
  font-size: 12px;
  line-height: 1.45;
}

.prompt-suggestion-grid {
  display: grid;
  gap: 8px;
  width: 100%;
}

.prompt-suggestion-rail {
  grid-template-columns: 1fr;
  align-content: start;
}

.prompt-suggestion-card {
  display: grid;
  grid-template-columns: 30px minmax(0, 1fr);
  align-items: center;
  gap: 10px;
  min-height: 44px;
  padding: 8px 10px;
  border: 1px solid var(--query-border);
  border-radius: var(--query-radius);
  background: var(--query-surface);
  color: var(--query-text);
  text-align: left;
  cursor: pointer;
  box-shadow: var(--query-shadow-sm);
  transition: transform 0.16s ease, box-shadow 0.16s ease, border-color 0.16s ease, background 0.16s ease;
}

.prompt-suggestion-card:hover {
  transform: translateX(3px);
  border-color: rgba(15, 118, 110, 0.38);
  background: #fbfefd;
  box-shadow: var(--query-shadow-md);
}

.prompt-suggestion-card:focus-visible {
  outline: 3px solid rgba(15, 118, 110, 0.18);
  outline-offset: 2px;
}

.prompt-suggestion-card .el-icon {
  width: 28px;
  height: 28px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  margin-top: 0;
  border-radius: var(--query-radius);
  color: var(--query-primary);
  background: var(--query-primary-soft);
}

.prompt-suggestion-card span {
  color: var(--query-text-soft);
  font-size: 13px;
  font-weight: 520;
  line-height: 1.35;
}

.messages-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.command-composer {
  display: grid;
  gap: 8px;
  padding: 9px 10px;
  border-top: 1px solid var(--query-border);
  background: var(--query-surface);
  transition: box-shadow 0.18s ease, background 0.18s ease;
}

.command-composer.is-composer-focused {
  box-shadow: 0 -12px 34px rgba(15, 118, 110, 0.11);
}

.command-composer.is-disabled {
  background: var(--query-surface-muted);
}

.composer-topline,
.composer-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.composer-topline span,
.composer-hints span {
  color: var(--query-muted);
  font-size: 12px;
}

.composer-input :deep(.el-textarea__inner) {
  min-height: 44px !important;
  padding: 9px 11px;
  border-radius: var(--query-radius);
  border: 1px solid var(--query-border);
  box-shadow: none;
  color: var(--query-text);
  line-height: 1.45;
  transition: border-color 0.18s ease, box-shadow 0.18s ease;
}

.composer-input :deep(.el-textarea__inner:focus) {
  border-color: rgba(15, 118, 110, 0.55);
  box-shadow: 0 0 0 3px rgba(15, 118, 110, 0.12);
}

.composer-submit {
  min-width: 92px;
  min-height: 36px;
}

.query-side-panel {
  grid-area: history;
  display: grid;
  grid-template-rows: auto auto minmax(0, 1fr) auto;
}

.side-panel-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  padding: 10px 12px;
  border-bottom: 1px solid var(--query-border);
}

.side-panel-header > div {
  display: grid;
  gap: 3px;
}

.side-panel-eyebrow {
  color: var(--query-muted);
  font-size: 11px;
  font-weight: 700;
  text-transform: uppercase;
}

.side-panel-header strong {
  color: var(--query-text);
  font-size: 14px;
}

.history-toolbar {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 8px;
  padding: 9px 10px;
  border-bottom: 1px solid var(--query-border-soft);
  background: var(--query-surface);
}

.history-list {
  max-height: none;
  min-height: 0;
  overflow-y: auto;
}

.history-item {
  padding: 10px 12px;
  border-bottom: 1px solid var(--query-border-soft);
  cursor: pointer;
  transition: background 0.18s ease, border-color 0.18s ease, transform 0.18s ease;
}

.history-item:hover {
  background: var(--query-surface-muted);
  transform: translateX(2px);
}

.history-item.is-active {
  background: var(--query-primary-tint);
  border-left: 3px solid var(--query-primary);
  padding-left: 11px;
}

.history-item.is-loading {
  background: #f0fdfa;
  pointer-events: none;
}

.history-item-top,
.history-meta {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.history-item-top {
  margin-bottom: 6px;
}

.history-content {
  display: flex;
  align-items: flex-start;
  gap: 9px;
  margin-bottom: 6px;
}

.history-icon {
  flex-shrink: 0;
  color: var(--query-primary);
  margin-top: 2px;
}

.history-text {
  color: var(--query-text-soft);
  font-size: 12px;
  line-height: 1.4;
  overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
}

.history-date,
.history-source {
  color: var(--query-light);
  font-size: 11px;
}

.history-loading-icon {
  flex-shrink: 0;
  color: var(--query-primary);
}

.history-actions {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-shrink: 0;
}

.history-actions :deep(.el-button) {
  min-height: 28px;
  padding: 4px 6px;
}

.history-empty-actions {
  display: flex;
  justify-content: center;
  gap: 8px;
  flex-wrap: wrap;
}

.side-panel-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  padding: 9px 12px;
  border-top: 1px solid var(--query-border);
  background: var(--query-surface);
}

@media (prefers-reduced-motion: reduce) {
  .prompt-suggestion-card,
  .history-item,
  .command-composer,
  .composer-input :deep(.el-textarea__inner) {
    transition: none;
  }

  .prompt-suggestion-card:hover,
  .history-item:hover {
    transform: none;
  }
}

@media (max-width: 1180px) {
  .query-workspace {
    grid-template-columns: 1fr;
    grid-template-rows: minmax(0, 1fr);
  }

  .query-layout {
    grid-template-columns: 1fr;
    grid-template-areas:
      "chat"
      "history";
  }

  .query-side-panel {
    min-height: 360px;
  }
}

@media (max-width: 900px) {
  .smart-query-page {
    height: auto;
  }

  .query-workspace {
    height: auto;
    min-height: calc(100vh - 120px);
    padding: 12px;
  }

  .prompt-suggestion-grid {
    grid-template-columns: 1fr;
  }

  .scope-console {
    grid-template-columns: 1fr;
    align-items: stretch;
  }

  .query-mode-switcher {
    justify-self: stretch;
  }

  .query-toolbar-scope {
    grid-template-columns: auto minmax(0, 1fr);
    padding-inline: 0;
    border-inline: 0;
  }

  .query-toolbar-scope .scope-select,
  .query-toolbar-scope .scope-state-tag {
    grid-column: 1 / -1;
  }

  .query-toolbar-actions {
    justify-content: flex-start;
  }

  .scope-state-tag {
    justify-self: start;
  }
}

@media (max-width: 760px) {
  .welcome-message {
    grid-template-columns: 1fr;
    align-content: start;
    width: 100%;
  }

  .welcome-primary {
    grid-template-columns: auto minmax(0, 1fr);
    justify-items: start;
    min-height: auto;
    text-align: left;
  }
}

@media (max-width: 640px) {
  .mode-tabs {
    width: 100%;
  }

  .query-toolbar-actions :deep(.el-button) {
    flex: 1;
  }

  .mode-tabs :deep(.el-radio-button) {
    width: 50%;
  }

  .mode-tabs :deep(.el-radio-button__inner) {
    width: 100%;
  }

  .chat-container {
    padding: 14px;
  }

  .welcome-message {
    padding: 16px 8px;
  }

  .composer-footer {
    align-items: stretch;
    flex-direction: column;
  }

  .composer-submit {
    width: 100%;
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
