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
    <div v-show="expanded" class="table-body">
      <el-table :data="displayRows" size="small" max-height="240" border>
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
import { saveAs } from "file-saver"
import * as XLSX from "xlsx"

const props = defineProps<{
  columns: string[]
  rows: Array<Record<string, any>>
}>()

const expanded = ref(true)
const currentPage = ref(1)

const displayRows = computed(() => {
  const start = (currentPage.value - 1) * 10
  return props.rows.slice(start, start + 10)
})

const toggleExpand = () => {
  expanded.value = !expanded.value
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

.table-footer {
  display: flex;
  justify-content: center;
  padding-top: 8px;
}
</style>
