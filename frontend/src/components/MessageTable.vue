<template>
  <div class="message-table">
    <div class="table-header">
      <span class="table-title">查询结果 ({{ rows.length }} 条)</span>
      <div class="table-actions">
        <el-button size="small" text @click="exportCsv">
          <el-icon><Download /></el-icon> 导出
        </el-button>
        <el-button size="small" text @click="toggleExpand">
          {{ expanded ? '收起' : '展开' }}
        </el-button>
      </div>
    </div>
    <div v-if="selectedRow && (drillLoading || drillActions.length || drillAttempted)" class="drill-bar">
      <div class="drill-bar-title">
        <span>已选中：{{ selectedSummary }}</span>
        <span v-if="drillLoading" class="drill-status-chip">后台生成中</span>
      </div>
      <div v-if="!drillLoading && !drillActions.length" class="drill-empty">当前记录没有可用的下钻建议</div>
      <div class="drill-actions">
        <el-button
          v-if="drillLoading && !drillActions.length"
          class="drill-action-loading"
          size="small"
          type="primary"
          plain
          disabled
          :loading="drillLoading"
        >
          下钻建议生成中
        </el-button>
        <el-button
          v-for="action in drillActions"
          :key="action.id"
          size="small"
          type="primary"
          plain
          @click="runDrill(action)"
        >
          {{ action.label }}
        </el-button>
      </div>
    </div>
    <div v-show="expanded" class="table-body">
      <el-table :data="displayRows" size="small" max-height="240" border @row-click="handleRowClick">
        <el-table-column
          v-for="col in columns"
          :key="col"
          :prop="col"
          :label="col"
          :min-width="100"
          show-overflow-tooltip
        />
      </el-table>
      <div v-if="rows.length > 10" class="table-footer">
        <el-pagination
          v-model:current-page="currentPage"
          :page-size="10"
          :total="rows.length"
          layout="prev, pager, next"
          small
        />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from "vue"
import { Download } from "@element-plus/icons-vue"
import { ElMessage } from "element-plus"
import { saveAs } from "file-saver"
import * as XLSX from "xlsx"
import { useQueryStore, type ChatMessage, type DrillAction } from "@/store/query"

const props = defineProps<{
  message: ChatMessage
  columns: string[]
  rows: Array<Record<string, any>>
}>()

const queryStore = useQueryStore()
const expanded = ref(true)
const currentPage = ref(1)
const selectedRow = ref<Record<string, any> | null>(null)
const drillActions = ref<DrillAction[]>([])
const drillLoading = ref(false)
const drillAttempted = ref(false)
let drillRequestId = 0

const displayRows = computed(() => {
  const start = (currentPage.value - 1) * 10
  return props.rows.slice(start, start + 10)
})

const selectedSummary = computed(() => {
  if (!selectedRow.value || !props.columns.length) return ""
  const firstTextColumn = props.columns.find((col) => {
    const value = selectedRow.value?.[col]
    return typeof value === "string" && value !== ""
  }) || props.columns[0]
  return `${firstTextColumn}: ${selectedRow.value[firstTextColumn]}`
})

const toggleExpand = () => {
  expanded.value = !expanded.value
}

const handleRowClick = async (row: Record<string, any>) => {
  const requestId = ++drillRequestId
  selectedRow.value = row
  drillActions.value = []
  drillAttempted.value = true
  drillLoading.value = true
  try {
    if (!props.message.sqlQuery || !props.message.sourceQuestion || !props.columns.length) {
      drillActions.value = []
      return
    }
    const preview = await queryStore.getDrillActions(
      props.message.sourceQuestion,
      props.message.sqlQuery,
      props.columns[0],
      props.columns,
      row,
      props.message.semanticContext?.dataset?.id
    )
    if (requestId !== drillRequestId) return
    drillActions.value = preview.actions
  } catch (error) {
    if (requestId !== drillRequestId) return
    drillActions.value = []
    ElMessage.error("加载钻取动作失败")
  } finally {
    if (requestId !== drillRequestId) return
    drillLoading.value = false
  }
}

const runDrill = async (action: DrillAction) => {
  await queryStore.ask(action.question, props.message.mode || "business", {
    pathLabel: action.label,
    sourceLabel: action.source_dimension_label,
    sourceValue: action.source_value,
    targetLabel: action.target_dimension_label,
    parentQuestion: props.message.sourceQuestion || props.message.content,
    parentContext: props.message.drillContext,
  }, props.message.historyId)
}

const exportCsv = () => {
  if (!props.rows.length) return
  const worksheet = XLSX.utils.json_to_sheet(props.rows)
  const csv = XLSX.utils.sheet_to_csv(worksheet)
  const blob = new Blob([csv], { type: "text/csv;charset=utf-8" })
  saveAs(blob, "query_result.csv")
}
</script>

<style scoped>
.message-table {
  width: 100%;
}

.table-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 12px;
  background: #fafafa;
  border-bottom: 1px solid #e4e7ed;
}

.table-title {
  font-size: 13px;
  font-weight: 500;
  color: #606266;
}

.table-actions {
  display: flex;
  gap: 4px;
}

.table-body {
  padding: 8px;
}

.drill-bar {
  padding: 10px 12px;
  border-bottom: 1px solid #e4e7ed;
  background: #f8fafc;
}

.drill-bar-title {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  font-size: 12px;
  color: #64748b;
  margin-bottom: 8px;
}

.drill-status-chip {
  display: inline-flex;
  align-items: center;
  min-height: 22px;
  padding: 0 8px;
  border: 1px solid #99f6e4;
  border-radius: 999px;
  background: #f0fdfa;
  color: #0f766e;
  font-weight: 700;
  white-space: nowrap;
}

.drill-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.drill-empty {
  margin-bottom: 8px;
  color: #909399;
  font-size: 13px;
}

.drill-action-loading {
  cursor: progress;
}

.table-footer {
  display: flex;
  justify-content: center;
  padding-top: 8px;
}
</style>
