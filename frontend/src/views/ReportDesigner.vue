<template>
  <div class="page report-designer-page">
    <section class="designer-header">
      <div>
        <p class="eyebrow">REPORT DESIGNER</p>
        <h2>类 Excel 设计器</h2>
        <p>{{ template?.name || "加载中" }} · 支持参数报表、主子报表、交叉表、多级表头和数据填报。</p>
      </div>
      <div class="designer-actions">
        <el-button :icon="Back" @click="router.push('/report-center')">返回</el-button>
        <el-button :icon="Refresh" :loading="loading" @click="loadTemplate">刷新</el-button>
        <el-button type="primary" :icon="Check" :loading="saving" @click="saveTemplate">保存版本</el-button>
      </div>
    </section>

    <section class="designer-shell">
      <aside class="designer-panel">
        <div class="panel-title">模板设置</div>
        <el-form label-position="top">
          <el-form-item label="报表名称">
            <el-input v-model="form.name" />
          </el-form-item>
          <el-form-item label="纸张">
            <el-segmented v-model="paper" :options="['A4', 'A3', 'Letter']" />
          </el-form-item>
          <el-form-item label="参数报表">
            <div class="feature-list">
              <el-tag size="small" effect="plain">日期范围</el-tag>
              <el-tag size="small" effect="plain">组织/产线</el-tag>
              <el-tag size="small" effect="plain">动态收件人</el-tag>
            </div>
          </el-form-item>
          <el-form-item label="数据填报">
            <el-switch v-model="fillEnabled" active-text="启用" inactive-text="关闭" />
          </el-form-item>
        </el-form>

        <div class="panel-title">当前单元格</div>
        <el-form label-position="top">
          <el-form-item label="内容">
            <el-input v-model="selectedCell.value" type="textarea" :rows="4" placeholder="{{ field }} 或固定文本" />
          </el-form-item>
          <el-form-item label="格式">
            <el-checkbox v-model="selectedCell.bold">加粗</el-checkbox>
            <el-checkbox v-model="selectedCell.merge">合并</el-checkbox>
          </el-form-item>
        </el-form>
      </aside>

      <main class="grid-stage">
        <div class="grid-toolbar">
          <div class="tool-group">
            <el-button :icon="Document" @click="insertTitle">标题</el-button>
            <el-button :icon="Grid" @click="insertTableHeader">多级表头</el-button>
            <el-button :icon="Connection" @click="insertBinding">数据绑定</el-button>
          </div>
          <div class="tool-group">
            <el-button @click="exportType = 'excel'">Excel</el-button>
            <el-button @click="exportType = 'pdf'">PDF</el-button>
            <el-button @click="exportType = 'word'">Word</el-button>
          </div>
        </div>

        <div class="excel-grid" :class="`paper-${paper.toLowerCase()}`">
          <div class="corner-cell"></div>
          <div v-for="col in columns" :key="`col-${col}`" class="column-head">{{ col }}</div>
          <template v-for="row in rows" :key="`row-${row}`">
            <div class="row-head">{{ row }}</div>
            <button
              v-for="col in columns"
              :key="`${row}-${col}`"
              type="button"
              class="grid-cell"
              :class="{ selected: selectedCell.row === row && selectedCell.col === col, bold: cellAt(row, col)?.bold }"
              @click="selectCell(row, col)"
            >
              {{ cellAt(row, col)?.value || "" }}
            </button>
          </template>
        </div>
      </main>

      <aside class="designer-panel">
        <div class="panel-title">数据绑定</div>
        <div class="binding-card">
          <span>绑定数据集</span>
          <strong>{{ datasetName }}</strong>
          <small>按模板区域重复渲染明细、分组和汇总。</small>
        </div>
        <div class="panel-title">版本记录</div>
        <div class="version-list">
          <div v-for="version in versions" :key="version.id" class="version-item">
            <strong>v{{ version.version }}</strong>
            <span>{{ version.changelog || "模板更新" }}</span>
          </div>
          <el-empty v-if="!versions.length" description="暂无版本" :image-size="64" />
        </div>
      </aside>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from "vue"
import { useRoute, useRouter } from "vue-router"
import axios from "axios"
import { ElMessage } from "element-plus"
import { Back, Check, Connection, Document, Grid, Refresh } from "@element-plus/icons-vue"

type LayoutCell = { row: number; col: string; value: string; bold?: boolean; merge?: boolean }
type ReportTemplate = {
  id: number
  name: string
  dataset_id: number
  version: number
  layout_json?: { paper?: string; cells?: LayoutCell[] } | null
  fill_schema_json?: Record<string, unknown> | null
}
type VersionItem = { id: number; version: number; changelog?: string | null }

const route = useRoute()
const router = useRouter()
const loading = ref(false)
const saving = ref(false)
const template = ref<ReportTemplate | null>(null)
const versions = ref<VersionItem[]>([])
const exportType = ref("excel")
const rows = Array.from({ length: 18 }, (_, index) => index + 1)
const columns = Array.from({ length: 10 }, (_, index) => String.fromCharCode(65 + index))
const form = reactive({ name: "", layout_json: { paper: "A4", cells: [] as LayoutCell[] } })
const selectedCell = reactive<LayoutCell>({ row: 1, col: "A", value: "", bold: false, merge: false })

const paper = computed({
  get: () => form.layout_json.paper || "A4",
  set: (value: string) => { form.layout_json.paper = value },
})
const fillEnabled = computed({
  get: () => Boolean(template.value?.fill_schema_json),
  set: (enabled: boolean) => {
    if (!template.value) return
    template.value.fill_schema_json = enabled ? { fields: [{ name: "comment", label: "填报说明", required: true }] } : null
  },
})
const datasetName = computed(() => template.value ? `数据集 #${template.value.dataset_id}` : "-")

const cellAt = (row: number, col: string) => form.layout_json.cells.find((cell) => cell.row === row && cell.col === col)

const selectCell = (row: number, col: string) => {
  const existing = cellAt(row, col)
  Object.assign(selectedCell, existing || { row, col, value: "", bold: false, merge: false })
}

watch(
  () => ({ ...selectedCell }),
  (cell) => {
    const index = form.layout_json.cells.findIndex((item) => item.row === cell.row && item.col === cell.col)
    if (!cell.value && index >= 0) {
      form.layout_json.cells.splice(index, 1)
      return
    }
    if (!cell.value) return
    if (index >= 0) form.layout_json.cells[index] = { ...cell }
    else form.layout_json.cells.push({ ...cell })
  },
  { deep: true },
)

const loadTemplate = async () => {
  loading.value = true
  try {
    const id = String(route.params.id)
    const [templateResp, versionResp] = await Promise.all([
      axios.get(`/api/report-templates/${id}`),
      axios.get(`/api/report-templates/${id}/versions`),
    ])
    template.value = templateResp.data
    form.name = templateResp.data.name
    form.layout_json = {
      paper: templateResp.data.layout_json?.paper || "A4",
      cells: templateResp.data.layout_json?.cells || [],
    }
    versions.value = versionResp.data || []
    selectCell(1, "A")
  } catch {
    // 错误提示由全局拦截器统一处理
  } finally {
    loading.value = false
  }
}

const saveTemplate = async () => {
  if (!template.value) return
  saving.value = true
  try {
    await axios.put(`/api/report-templates/${template.value.id}`, {
      name: form.name,
      layout_json: form.layout_json,
      fill_schema_json: template.value.fill_schema_json,
      changelog: `设计器保存为 ${exportType.value.toUpperCase()} 友好布局`,
    })
    ElMessage.success("模板版本已保存")
    await loadTemplate()
  } catch (error: any) {
    ElMessage.error(error.response?.data?.detail || "保存失败")
  } finally {
    saving.value = false
  }
}

const insertTitle = () => {
  Object.assign(selectedCell, { row: 1, col: "A", value: form.name || "经营分析报表", bold: true, merge: true })
}

const insertTableHeader = () => {
  const headers = ["日期", "组织", "指标", "实际值", "目标值"]
  headers.forEach((value, index) => {
    const col = columns[index]
    const existingIndex = form.layout_json.cells.findIndex((cell) => cell.row === 3 && cell.col === col)
    const next = { row: 3, col, value, bold: true }
    if (existingIndex >= 0) form.layout_json.cells[existingIndex] = next
    else form.layout_json.cells.push(next)
  })
}

const insertBinding = () => {
  Object.assign(selectedCell, { row: selectedCell.row, col: selectedCell.col, value: "{{ dataset.field }}", bold: false, merge: false })
}

onMounted(loadTemplate)
</script>

<style scoped>
.designer-header,
.designer-shell,
.designer-panel,
.grid-stage {
  background: #ffffff;
  border: 1px solid var(--app-border);
  border-radius: var(--app-radius);
}

.designer-header {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  padding: 18px 20px;
}

.designer-header h2 {
  margin: 4px 0 8px;
  font-size: 24px;
  letter-spacing: 0;
}

.designer-header p {
  margin: 0;
  color: var(--app-text-muted);
}

.eyebrow {
  color: var(--app-primary);
  font-size: 12px;
  font-weight: 700;
}

.designer-actions,
.grid-toolbar,
.tool-group,
.feature-list {
  display: flex;
  align-items: center;
  gap: 8px;
}

.designer-shell {
  display: grid;
  grid-template-columns: 260px minmax(0, 1fr) 260px;
  gap: 0;
  overflow: hidden;
}

.designer-panel {
  border: none;
  border-radius: 0;
  padding: 16px;
  background: var(--app-surface-muted);
}

.panel-title {
  margin: 0 0 12px;
  font-weight: 700;
  color: var(--app-text);
}

.grid-stage {
  border-top: none;
  border-bottom: none;
  border-radius: 0;
  padding: 16px;
  overflow: auto;
}

.grid-toolbar {
  justify-content: space-between;
  margin-bottom: 12px;
}

.excel-grid {
  display: grid;
  grid-template-columns: 42px repeat(10, minmax(92px, 1fr));
  min-width: 980px;
  border-top: 1px solid var(--app-border);
  border-left: 1px solid var(--app-border);
  background: #ffffff;
}

.corner-cell,
.column-head,
.row-head,
.grid-cell {
  min-height: 34px;
  border-right: 1px solid var(--app-border);
  border-bottom: 1px solid var(--app-border);
}

.column-head,
.row-head,
.corner-cell {
  display: flex;
  align-items: center;
  justify-content: center;
  background: #f3f6f9;
  color: var(--app-text-muted);
  font-size: 12px;
  font-weight: 600;
}

.grid-cell {
  padding: 6px 8px;
  background: #ffffff;
  color: var(--app-text);
  text-align: left;
  cursor: pointer;
}

.grid-cell.selected {
  outline: 2px solid var(--app-primary);
  outline-offset: -2px;
  background: rgba(15, 118, 110, 0.06);
}

.grid-cell.bold {
  font-weight: 700;
}

.binding-card,
.version-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 12px;
  border: 1px solid var(--app-border);
  border-radius: var(--app-radius-sm);
  background: #ffffff;
}

.binding-card small,
.version-item span {
  color: var(--app-text-muted);
}

.version-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

@media (max-width: 1100px) {
  .designer-header,
  .designer-actions,
  .grid-toolbar {
    align-items: stretch;
    flex-direction: column;
  }

  .tool-group {
    flex-wrap: wrap;
  }

  .designer-shell {
    grid-template-columns: 1fr;
  }
}
</style>
