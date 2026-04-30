<template>
  <div class="dashboard-center-page">
    <div class="toolbar">
      <el-segmented v-model="statusFilter" :options="statusOptions" @change="fetchDashboards" />
      <div class="toolbar-actions">
        <el-button @click="openTemplateDialog">模板创建</el-button>
        <el-button type="primary" :icon="Plus" @click="openCreate">新建看板</el-button>
      </div>
    </div>

    <el-table
      v-loading="loading"
      :data="dashboards"
      class="dashboard-table"
      @row-click="openDesigner"
    >
      <el-table-column prop="title" label="看板名称" min-width="180" />
      <el-table-column prop="description" label="描述" min-width="220" show-overflow-tooltip />
      <el-table-column label="状态" width="100">
        <template #default="{ row }">
          <el-tag :type="row.status === 'published' ? 'success' : 'info'" effect="plain">
            {{ row.status === 'published' ? '已发布' : '草稿' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="可见范围" width="120">
        <template #default="{ row }">{{ row.visibility === 'org' ? '组织内' : '仅自己' }}</template>
      </el-table-column>
      <el-table-column label="组件数" width="100">
        <template #default="{ row }">{{ componentCount(row) }}</template>
      </el-table-column>
      <el-table-column label="操作" width="270" fixed="right">
        <template #default="{ row }">
          <el-button text type="primary" @click.stop="preview(row)">预览</el-button>
          <el-button text type="primary" @click.stop="edit(row)">编辑</el-button>
          <el-button text type="primary" @click.stop="openShare(row)">分享</el-button>
          <el-button v-if="row.status !== 'published'" text type="success" @click.stop="publish(row)">发布</el-button>
          <el-button text type="danger" @click.stop="remove(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-dialog v-model="editorVisible" :title="editingId ? '编辑看板' : '新建看板'" width="560px">
      <el-form :model="form" label-width="88px">
        <el-form-item label="名称">
          <el-input v-model="form.title" maxlength="128" show-word-limit />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="form.description" type="textarea" :rows="3" />
        </el-form-item>
        <el-form-item label="可见范围">
          <el-radio-group v-model="form.visibility">
            <el-radio value="private">仅自己</el-radio>
            <el-radio value="org">组织内</el-radio>
          </el-radio-group>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editorVisible = false">取消</el-button>
        <el-button type="primary" @click="save" :loading="saving">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="templateVisible" title="从模板创建看板" width="720px">
      <el-table v-loading="templateLoading" :data="templates">
        <el-table-column prop="name" label="模板名称" width="180" />
        <el-table-column prop="description" label="适用场景" />
        <el-table-column label="操作" width="100">
          <template #default="{ row }">
            <el-button text type="primary" @click="createFromTemplate(row)">使用</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-dialog>

    <el-dialog v-model="shareVisible" title="看板分享" width="560px">
      <el-form label-width="96px">
        <el-form-item label="公开链接">
          <el-switch v-model="sharePublic" />
        </el-form-item>
        <el-form-item label="协作用户">
          <el-input v-model="shareUserIdsText" placeholder="用户 ID，用逗号分隔" />
        </el-form-item>
        <el-form-item v-if="shareTarget?.share_token" label="访问地址">
          <el-input :model-value="shareLink" readonly />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="shareVisible = false">取消</el-button>
        <el-button type="primary" :loading="shareSaving" @click="saveShare">保存分享</el-button>
      </template>
    </el-dialog>

    <el-drawer v-model="previewVisible" title="看板预览" size="72%">
      <template v-if="selectedDashboard">
        <div class="preview-header">
          <div>
            <h3 class="preview-title">{{ selectedDashboard.title }}</h3>
            <p class="preview-description">{{ selectedDashboard.description || "暂无描述" }}</p>
          </div>
          <el-tag effect="plain">{{ componentCount(selectedDashboard) }} 个组件</el-tag>
        </div>
        <el-empty v-if="componentCount(selectedDashboard) === 0" description="暂无组件" />
        <div v-else class="preview-grid">
          <div
            v-for="item in selectedDashboard.layout_json?.components || []"
            :key="item.id"
            class="preview-component"
            :style="componentStyle(item)"
          >
            <PinnedChartCard :chart="chartForComponent(item)" @delete="noop" />
          </div>
        </div>
      </template>
    </el-drawer>

    <el-drawer v-model="designerVisible" :with-header="false" size="92%" class="designer-drawer">
      <div v-if="designingDashboard" class="designer-shell">
        <aside class="designer-sidebar">
          <div class="designer-panel-header">
            <div>
              <h3>图表库</h3>
              <span>{{ pinnedCharts.length }} 个固定图表</span>
            </div>
            <div class="designer-panel-actions">
              <el-button type="primary" size="small" :icon="Plus" @click="openChartCreator">新建图表</el-button>
              <el-button :icon="Refresh" circle text :loading="chartLoading" @click="fetchPinnedCharts" />
            </div>
          </div>

          <el-input
            v-model="chartKeyword"
            class="chart-search"
            placeholder="搜索图表"
            clearable
            :prefix-icon="Search"
          />

          <div class="chart-type-picker">
            <span>拖入类型</span>
            <el-select v-model="libraryChartType" size="small">
              <el-option label="使用原图" value="auto" />
              <el-option
                v-for="option in chartTypeOptions"
                :key="option.value"
                :label="option.label"
                :value="option.value"
              />
            </el-select>
          </div>

          <div class="chart-library">
            <div
              v-for="chart in filteredPinnedCharts"
              :key="chart.id"
              class="chart-library-item"
              draggable="true"
              @dragstart="startLibraryDrag(chart)"
            >
              <div class="library-title">{{ chart.title }}</div>
              <div class="library-meta">
                <el-tag size="small" effect="plain">{{ chartTypeLabel(chart.chart_type) }}</el-tag>
                <span>{{ chart.rows.length }} 行</span>
              </div>
              <el-button size="small" plain @click.stop="addChartToCanvas(chart)">添加</el-button>
            </div>
            <el-empty v-if="!filteredPinnedCharts.length" description="暂无可用图表" :image-size="68">
              <el-button type="primary" size="small" @click="openChartCreator">新建图表</el-button>
            </el-empty>
          </div>
        </aside>

        <main class="designer-main">
          <header class="designer-topbar">
            <div>
              <h2>{{ designingDashboard.title }}</h2>
              <p>{{ designingDashboard.description || "拖拽左侧图表到画布，调整尺寸后保存" }}</p>
            </div>
            <div class="designer-actions">
              <el-button @click="designerVisible = false">关闭</el-button>
              <el-button type="primary" :loading="designerSaving" @click="saveDesigner">保存布局</el-button>
            </div>
          </header>

          <section class="designer-canvas-wrap">
            <div class="canvas-ruler">
              <span v-for="column in 12" :key="column">{{ column }}</span>
            </div>
            <div class="designer-canvas" @dragover.prevent @drop="dropOnCanvas">
              <div v-if="!designerComponents.length" class="canvas-empty">
                <el-icon><Plus /></el-icon>
                <span>拖入图表开始设计看板</span>
              </div>
              <div
                v-for="(component, index) in designerComponents"
                :key="component.id"
                class="canvas-component"
                :class="{ selected: selectedComponentId === component.id }"
                :style="componentStyle(component)"
                draggable="true"
                @click="selectComponent(component.id)"
                @dragstart="startComponentDrag(index)"
                @dragover.prevent
                @drop.stop="dropComponent(index)"
              >
                <div class="canvas-component-toolbar">
                  <span>{{ component.title }}</span>
                  <div class="component-actions">
                    <el-tag size="small" effect="plain">{{ chartTypeLabel(component.chart_type) }}</el-tag>
                    <el-button text size="small" :disabled="index === 0" @click.stop="moveComponent(index, -1)">上移</el-button>
                    <el-button text size="small" :disabled="index === designerComponents.length - 1" @click.stop="moveComponent(index, 1)">下移</el-button>
                    <el-button text size="small" type="danger" @click.stop="removeComponent(component.id)">删除</el-button>
                  </div>
                </div>
                <PinnedChartCard :chart="chartForComponent(component)" @delete="removeComponent(component.id)" />
              </div>
            </div>
          </section>
        </main>

        <aside class="designer-properties">
          <div class="designer-panel-header">
            <div>
              <h3>属性</h3>
              <span>{{ selectedComponent ? "组件设置" : "未选择组件" }}</span>
            </div>
          </div>

          <template v-if="selectedComponent">
            <el-form label-position="top" class="property-form">
              <el-form-item label="标题">
                <el-input v-model="selectedComponent.title" maxlength="128" />
              </el-form-item>
              <el-form-item label="宽度">
                <el-slider v-model="selectedComponent.w" :min="3" :max="12" show-stops />
              </el-form-item>
              <el-form-item label="高度">
                <el-slider v-model="selectedComponent.h" :min="2" :max="6" show-stops />
              </el-form-item>
              <el-form-item label="图表类型">
                <el-select v-model="selectedComponent.chart_type">
                  <el-option
                    v-for="option in chartTypeOptions"
                    :key="option.value"
                    :label="option.label"
                    :value="option.value"
                  />
                </el-select>
              </el-form-item>
            </el-form>
          </template>
          <el-empty v-else description="选择画布组件后编辑属性" :image-size="72" />
        </aside>
      </div>
    </el-drawer>

    <el-dialog
      v-model="chartCreatorVisible"
      title="新建图表"
      width="860px"
      append-to-body
      class="chart-creator-dialog"
    >
      <el-form :model="chartForm" label-position="top" class="chart-creator-form">
        <el-row :gutter="12">
          <el-col :xs="24" :sm="12">
            <el-form-item label="标题">
              <el-input v-model="chartForm.title" maxlength="128" />
            </el-form-item>
          </el-col>
          <el-col :xs="24" :sm="12">
            <el-form-item label="数据源">
              <el-select v-model="chartForm.datasource_id" style="width: 100%">
                <el-option
                  v-for="datasource in datasourceStore.datasources"
                  :key="datasource.id"
                  :label="datasource.name"
                  :value="datasource.id"
                />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :xs="24" :sm="12">
            <el-form-item label="图表类型">
              <el-select v-model="chartForm.chart_type" style="width: 100%">
                <el-option
                  v-for="option in chartTypeOptions"
                  :key="option.value"
                  :label="option.label"
                  :value="option.value"
                />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :xs="24" :sm="12">
            <el-form-item label="排序">
              <el-select v-model="chartForm.sort_order" style="width: 100%">
                <el-option label="默认" value="none" />
                <el-option label="降序" value="desc" />
                <el-option label="升序" value="asc" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>

        <el-form-item label="创建方式">
          <el-segmented v-model="chartCreateMode" :options="chartCreateModeOptions" />
        </el-form-item>

        <el-form-item v-if="chartCreateMode === 'nl'" label="问题">
          <el-input
            v-model="chartForm.question"
            type="textarea"
            :rows="3"
            placeholder="例如：统计每个月的销售额趋势"
          />
        </el-form-item>

        <el-form-item label="SQL">
          <el-input
            v-model="chartForm.sql_query"
            type="textarea"
            :rows="6"
            placeholder="SELECT ..."
          />
        </el-form-item>

        <el-form-item label="描述">
          <el-input v-model="chartForm.description" type="textarea" :rows="2" />
        </el-form-item>

        <section class="chart-preview-panel">
          <PinnedChartCard
            v-if="chartPreviewResult && chartPreviewResult.rows.length"
            :chart="chartPreviewCard"
            @delete="noop"
          />
          <el-empty v-else description="暂无预览数据" :image-size="72" />
        </section>
      </el-form>
      <template #footer>
        <el-button @click="chartCreatorVisible = false">取消</el-button>
        <el-button :loading="chartPreviewLoading" @click="previewChartDraft">预览</el-button>
        <el-button type="primary" :loading="chartCreateLoading" @click="saveCreatedChart">保存并加入画布</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue"
import axios from "axios"
import { ElMessage, ElMessageBox } from "element-plus"
import { Plus, Refresh, Search } from "@element-plus/icons-vue"
import PinnedChartCard from "@/components/PinnedChartCard.vue"
import { useDatasourceStore } from "@/store/datasource"

interface DashboardComponent {
  id: string
  pinned_chart_id: number
  title: string
  description?: string | null
  chart_type: string
  sort_order: string
  x: number
  y: number
  w: number
  h: number
}

interface DashboardLayout {
  components?: DashboardComponent[]
}

interface DashboardItem {
  id: number
  title: string
  description: string | null
  layout_json: DashboardLayout | null
  filters_json: Record<string, unknown> | null
  status: string
  visibility: string
  is_public: number
  share_token: string | null
  shared_user_ids: number[] | null
  version: number
}

interface PinnedChartData {
  id: number
  title: string
  description: string | null
  chart_type: string
  sort_order: string
  columns: string[]
  rows: Array<Record<string, unknown>>
}

interface ChartPreviewResult {
  columns: string[]
  rows: Array<Record<string, unknown>>
}

interface DashboardTemplate {
  id: string
  name: string
  description: string
}

const datasourceStore = useDatasourceStore()
const dashboards = ref<DashboardItem[]>([])
const pinnedCharts = ref<PinnedChartData[]>([])
const designerComponents = ref<DashboardComponent[]>([])
const loading = ref(false)
const saving = ref(false)
const chartLoading = ref(false)
const designerSaving = ref(false)
const chartPreviewLoading = ref(false)
const chartCreateLoading = ref(false)
const editorVisible = ref(false)
const previewVisible = ref(false)
const designerVisible = ref(false)
const chartCreatorVisible = ref(false)
const templateVisible = ref(false)
const templateLoading = ref(false)
const shareVisible = ref(false)
const selectedDashboard = ref<DashboardItem | null>(null)
const designingDashboard = ref<DashboardItem | null>(null)
const shareTarget = ref<DashboardItem | null>(null)
const selectedComponentId = ref("")
const draggedChartId = ref<number | null>(null)
const draggedComponentIndex = ref<number | null>(null)
const editingId = ref<number | null>(null)
const statusFilter = ref("all")
const chartKeyword = ref("")
const libraryChartType = ref("auto")
const chartCreateMode = ref("nl")
const chartPreviewResult = ref<ChartPreviewResult | null>(null)
const templates = ref<DashboardTemplate[]>([])
const sharePublic = ref(false)
const shareUserIdsText = ref("")
const shareSaving = ref(false)
const statusOptions = [
  { label: "全部", value: "all" },
  { label: "已发布", value: "published" },
  { label: "草稿", value: "draft" },
]
const chartCreateModeOptions = [
  { label: "自然语言", value: "nl" },
  { label: "SQL", value: "sql" },
]
const chartTypeOptions = [
  { label: "指标卡", value: "kpi" },
  { label: "明细表", value: "table" },
  { label: "柱状图", value: "bar" },
  { label: "条形图", value: "horizontal_bar" },
  { label: "折线图", value: "line" },
  { label: "面积图", value: "area" },
  { label: "饼图", value: "pie" },
  { label: "环形图", value: "donut" },
  { label: "散点图", value: "scatter" },
  { label: "组合图", value: "combo" },
]

const form = reactive({
  title: "",
  description: "",
  visibility: "private",
})

const chartForm = reactive({
  title: "",
  description: "",
  question: "",
  sql_query: "",
  datasource_id: null as number | null,
  chart_type: "bar",
  sort_order: "desc",
})

const selectedComponent = computed(() =>
  designerComponents.value.find((component) => component.id === selectedComponentId.value) || null
)

const shareLink = computed(() => {
  if (!shareTarget.value?.share_token) return ""
  return `${window.location.origin}/api/dashboards/public/${shareTarget.value.share_token}`
})

const chartPreviewCard = computed<PinnedChartData>(() => ({
  id: 0,
  title: chartForm.title || "预览图表",
  description: chartForm.description || null,
  chart_type: chartForm.chart_type,
  sort_order: chartForm.sort_order,
  columns: chartPreviewResult.value?.columns || [],
  rows: chartPreviewResult.value?.rows || [],
}))

const filteredPinnedCharts = computed(() => {
  const keyword = chartKeyword.value.trim().toLowerCase()
  if (!keyword) return pinnedCharts.value
  return pinnedCharts.value.filter((chart) =>
    [chart.title, chart.description || ""].some((value) => value.toLowerCase().includes(keyword))
  )
})

const componentCount = (dashboard: DashboardItem) => dashboard.layout_json?.components?.length || 0

const componentStyle = (component: DashboardComponent) => ({
  gridColumn: `span ${Math.min(Math.max(component.w || 6, 3), 12)}`,
  minHeight: `${Math.min(Math.max(component.h || 3, 2), 6) * 96}px`,
})

const chartTypeLabel = (type: string) => {
  return chartTypeOptions.find((option) => option.value === type)?.label || type
}

const resolveLibraryChartType = (chart: PinnedChartData) => (
  libraryChartType.value === "auto" ? chart.chart_type : libraryChartType.value
)

const defaultComponentSize = (chartType: string) => {
  const sizes: Record<string, Pick<DashboardComponent, "w" | "h">> = {
    kpi: { w: 3, h: 2 },
    table: { w: 12, h: 4 },
    pie: { w: 4, h: 3 },
    donut: { w: 4, h: 3 },
    scatter: { w: 6, h: 4 },
    combo: { w: 8, h: 4 },
  }
  return sizes[chartType] || { w: 6, h: 3 }
}

const noop = () => {}

const apiErrorMessage = (error: unknown, fallback: string) => {
  if (axios.isAxiosError(error)) {
    const detail = error.response?.data?.detail
    if (typeof detail === "string") return detail
  }
  return fallback
}

const cloneComponents = (dashboard: DashboardItem): DashboardComponent[] =>
  (dashboard.layout_json?.components || []).map((component, index) => ({
    id: component.id || `component-${Date.now()}-${index}`,
    pinned_chart_id: component.pinned_chart_id,
    title: component.title,
    description: component.description || null,
    chart_type: component.chart_type || "bar",
    sort_order: component.sort_order || "desc",
    x: component.x || 0,
    y: component.y ?? index,
    w: component.w || 6,
    h: component.h || 3,
  }))

const chartForComponent = (component: DashboardComponent): PinnedChartData => {
  const chart = pinnedCharts.value.find((item) => item.id === component.pinned_chart_id)
  return {
    id: component.pinned_chart_id,
    title: component.title,
    description: component.description || chart?.description || null,
    chart_type: component.chart_type || chart?.chart_type || "bar",
    sort_order: component.sort_order || chart?.sort_order || "desc",
    columns: chart?.columns || [],
    rows: chart?.rows || [],
  }
}

const fetchDashboards = async () => {
  loading.value = true
  try {
    const response = await axios.get("/api/dashboards", {
      params: { status: statusFilter.value === "all" ? undefined : statusFilter.value },
    })
    dashboards.value = response.data.items
  } catch (error) {
    ElMessage.error("看板加载失败")
  } finally {
    loading.value = false
  }
}

const fetchPinnedCharts = async () => {
  chartLoading.value = true
  try {
    const response = await axios.get("/api/pinned-charts/with-data")
    pinnedCharts.value = response.data
  } catch (error) {
    ElMessage.error("图表库加载失败")
  } finally {
    chartLoading.value = false
  }
}

const fetchTemplates = async () => {
  templateLoading.value = true
  try {
    const response = await axios.get("/api/dashboard-templates")
    templates.value = response.data.items
  } catch (error) {
    ElMessage.error("模板加载失败")
  } finally {
    templateLoading.value = false
  }
}

const resetForm = () => {
  editingId.value = null
  form.title = ""
  form.description = ""
  form.visibility = "private"
}

const openCreate = () => {
  resetForm()
  editorVisible.value = true
}

const openTemplateDialog = async () => {
  templateVisible.value = true
  if (!templates.value.length) {
    await fetchTemplates()
  }
}

const createFromTemplate = async (template: DashboardTemplate) => {
  try {
    await axios.post(`/api/dashboard-templates/${template.id}/dashboards`, null, {
      params: { title: template.name },
    })
    templateVisible.value = false
    ElMessage.success("已从模板创建看板")
    await fetchDashboards()
  } catch (error) {
    ElMessage.error(apiErrorMessage(error, "模板创建失败"))
  }
}

const edit = (dashboard: DashboardItem) => {
  editingId.value = dashboard.id
  form.title = dashboard.title
  form.description = dashboard.description || ""
  form.visibility = dashboard.visibility
  editorVisible.value = true
}

const save = async () => {
  if (!form.title.trim()) {
    ElMessage.warning("请输入看板名称")
    return
  }
  saving.value = true
  try {
    const payload = {
      title: form.title.trim(),
      description: form.description || null,
      visibility: form.visibility,
      layout_json: editingId.value ? undefined : { components: [] },
      filters_json: editingId.value ? undefined : {},
    }
    if (editingId.value) {
      await axios.put(`/api/dashboards/${editingId.value}`, payload)
    } else {
      await axios.post("/api/dashboards", payload)
    }
    editorVisible.value = false
    await fetchDashboards()
  } catch (error) {
    ElMessage.error("看板保存失败")
  } finally {
    saving.value = false
  }
}

const publish = async (dashboard: DashboardItem) => {
  await axios.post(`/api/dashboards/${dashboard.id}/publish`)
  ElMessage.success("看板已发布")
  await fetchDashboards()
}

const openShare = (dashboard: DashboardItem) => {
  shareTarget.value = dashboard
  sharePublic.value = !!dashboard.is_public
  shareUserIdsText.value = (dashboard.shared_user_ids || []).join(", ")
  shareVisible.value = true
}

const saveShare = async () => {
  if (!shareTarget.value) return
  shareSaving.value = true
  try {
    const sharedUserIds = shareUserIdsText.value
      .split(/[\n,，]/)
      .map((item) => Number(item.trim()))
      .filter((item) => Number.isFinite(item) && item > 0)
    const response = await axios.put(`/api/dashboards/${shareTarget.value.id}/share`, {
      is_public: sharePublic.value,
      shared_user_ids: sharedUserIds,
    })
    const index = dashboards.value.findIndex((dashboard) => dashboard.id === response.data.id)
    if (index !== -1) dashboards.value[index] = response.data
    shareTarget.value = response.data
    ElMessage.success("分享配置已保存")
  } catch (error) {
    ElMessage.error(apiErrorMessage(error, "分享配置保存失败"))
  } finally {
    shareSaving.value = false
  }
}

const remove = async (dashboard: DashboardItem) => {
  await ElMessageBox.confirm("确定要删除这个看板吗？", "提示", {
    confirmButtonText: "删除",
    cancelButtonText: "取消",
    type: "warning",
  })
  await axios.delete(`/api/dashboards/${dashboard.id}`)
  await fetchDashboards()
}

const preview = async (dashboard: DashboardItem) => {
  if (!pinnedCharts.value.length) await fetchPinnedCharts()
  selectedDashboard.value = dashboard
  previewVisible.value = true
}

const openDesigner = async (dashboard: DashboardItem) => {
  if (!pinnedCharts.value.length) await fetchPinnedCharts()
  if (!datasourceStore.datasources.length) await datasourceStore.fetchDatasources().catch(() => undefined)
  designingDashboard.value = dashboard
  designerComponents.value = cloneComponents(dashboard)
  selectedComponentId.value = designerComponents.value[0]?.id || ""
  designerVisible.value = true
}

const startLibraryDrag = (chart: PinnedChartData) => {
  draggedChartId.value = chart.id
  draggedComponentIndex.value = null
}

const startComponentDrag = (index: number) => {
  draggedComponentIndex.value = index
  draggedChartId.value = null
}

const addChartToCanvas = (chart: PinnedChartData, chartTypeOverride?: string) => {
  const nextIndex = designerComponents.value.length
  const chartType = chartTypeOverride || resolveLibraryChartType(chart)
  const size = defaultComponentSize(chartType)
  const component: DashboardComponent = {
    id: `component-${chart.id}-${Date.now()}`,
    pinned_chart_id: chart.id,
    title: chart.title,
    description: chart.description,
    chart_type: chartType,
    sort_order: chart.sort_order,
    x: 0,
    y: nextIndex,
    w: size.w,
    h: size.h,
  }
  designerComponents.value.push(component)
  selectedComponentId.value = component.id
}

const resetChartForm = () => {
  chartCreateMode.value = "nl"
  chartForm.title = ""
  chartForm.description = ""
  chartForm.question = ""
  chartForm.sql_query = ""
  chartForm.datasource_id = datasourceStore.currentId || datasourceStore.datasources[0]?.id || null
  chartForm.chart_type = libraryChartType.value === "auto" ? "bar" : libraryChartType.value
  chartForm.sort_order = "desc"
  chartPreviewResult.value = null
}

const ensureChartDatasource = async () => {
  if (!datasourceStore.datasources.length) {
    await datasourceStore.fetchDatasources()
  }
  if (!chartForm.datasource_id) {
    chartForm.datasource_id = datasourceStore.currentId || datasourceStore.datasources[0]?.id || null
  }
  return !!chartForm.datasource_id
}

const openChartCreator = async () => {
  try {
    if (!(await ensureChartDatasource())) {
      ElMessage.warning("请先配置数据源")
      return
    }
    resetChartForm()
    chartCreatorVisible.value = true
  } catch (error) {
    ElMessage.error(apiErrorMessage(error, "数据源加载失败"))
  }
}

const generateChartFromQuestion = async () => {
  const question = chartForm.question.trim()
  if (!question) {
    ElMessage.warning("请输入问题")
    return false
  }
  if (!(await ensureChartDatasource())) {
    ElMessage.warning("请先配置数据源")
    return false
  }

  const response = await axios.post("/api/query/ask", {
    question,
    mode: "text2sql",
    datasource_id: chartForm.datasource_id,
  })
  chartForm.sql_query = response.data.sql_query || ""
  chartPreviewResult.value = response.data.result || { columns: [], rows: [] }
  if (!chartForm.title.trim()) {
    chartForm.title = question.slice(0, 64)
  }
  return true
}

const previewChartSql = async () => {
  const sql = chartForm.sql_query.trim()
  if (!sql) {
    ElMessage.warning("请输入 SQL")
    return false
  }
  if (!(await ensureChartDatasource())) {
    ElMessage.warning("请先配置数据源")
    return false
  }

  const response = await axios.post("/api/pinned-charts/preview", {
    sql_query: sql,
    datasource_id: chartForm.datasource_id,
  })
  chartPreviewResult.value = response.data
  return true
}

const previewChartDraft = async () => {
  chartPreviewLoading.value = true
  try {
    const ok = chartCreateMode.value === "nl"
      ? await generateChartFromQuestion()
      : await previewChartSql()
    if (ok && chartPreviewResult.value && !chartPreviewResult.value.rows.length) {
      ElMessage.warning("查询成功，但没有返回数据")
    }
    return ok
  } catch (error) {
    ElMessage.error(apiErrorMessage(error, "图表预览失败"))
    return false
  } finally {
    chartPreviewLoading.value = false
  }
}

const saveCreatedChart = async () => {
  if (!chartForm.title.trim()) {
    ElMessage.warning("请输入图表标题")
    return
  }
  if (!chartForm.sql_query.trim()) {
    const ok = await previewChartDraft()
    if (!ok || !chartForm.sql_query.trim()) return
  }
  if (!chartPreviewResult.value) {
    const ok = await previewChartDraft()
    if (!ok) return
  }

  chartCreateLoading.value = true
  try {
    const response = await axios.post("/api/pinned-charts", {
      title: chartForm.title.trim(),
      description: chartForm.description.trim() || null,
      sql_query: chartForm.sql_query.trim(),
      chart_type: chartForm.chart_type,
      sort_order: chartForm.sort_order,
      datasource_id: chartForm.datasource_id,
    })
    await fetchPinnedCharts()
    const createdChart = pinnedCharts.value.find((chart) => chart.id === response.data.id) || {
      id: response.data.id,
      title: response.data.title,
      description: response.data.description,
      chart_type: response.data.chart_type,
      sort_order: response.data.sort_order,
      columns: chartPreviewResult.value?.columns || [],
      rows: chartPreviewResult.value?.rows || [],
    }
    addChartToCanvas(createdChart, chartForm.chart_type)
    chartCreatorVisible.value = false
    ElMessage.success("图表已创建并加入画布")
  } catch (error) {
    ElMessage.error(apiErrorMessage(error, "图表创建失败"))
  } finally {
    chartCreateLoading.value = false
  }
}

const dropOnCanvas = () => {
  if (!draggedChartId.value) return
  const chart = pinnedCharts.value.find((item) => item.id === draggedChartId.value)
  if (chart) addChartToCanvas(chart)
  draggedChartId.value = null
}

const dropComponent = (targetIndex: number) => {
  if (draggedComponentIndex.value === null || draggedComponentIndex.value === targetIndex) return
  const [component] = designerComponents.value.splice(draggedComponentIndex.value, 1)
  designerComponents.value.splice(targetIndex, 0, component)
  designerComponents.value = designerComponents.value.map((item, index) => ({ ...item, y: index }))
  draggedComponentIndex.value = null
}

const selectComponent = (id: string) => {
  selectedComponentId.value = id
}

const moveComponent = (index: number, direction: -1 | 1) => {
  const targetIndex = index + direction
  if (targetIndex < 0 || targetIndex >= designerComponents.value.length) return
  const next = [...designerComponents.value]
  const [component] = next.splice(index, 1)
  next.splice(targetIndex, 0, component)
  designerComponents.value = next.map((item, itemIndex) => ({ ...item, y: itemIndex }))
}

const removeComponent = (id: string | number) => {
  const componentId = String(id)
  designerComponents.value = designerComponents.value
    .filter((component) => component.id !== componentId)
    .map((component, index) => ({ ...component, y: index }))
  if (selectedComponentId.value === componentId) {
    selectedComponentId.value = designerComponents.value[0]?.id || ""
  }
}

const saveDesigner = async () => {
  if (!designingDashboard.value) return
  designerSaving.value = true
  try {
    const response = await axios.put(`/api/dashboards/${designingDashboard.value.id}`, {
      layout_json: { components: designerComponents.value },
      filters_json: designingDashboard.value.filters_json || {},
    })
    const index = dashboards.value.findIndex((dashboard) => dashboard.id === response.data.id)
    if (index !== -1) dashboards.value[index] = response.data
    designingDashboard.value = response.data
    ElMessage.success("布局已保存")
  } catch (error) {
    ElMessage.error("布局保存失败")
  } finally {
    designerSaving.value = false
  }
}

onMounted(async () => {
  await Promise.all([
    fetchDashboards(),
    fetchPinnedCharts(),
    datasourceStore.fetchDatasources().catch(() => undefined),
  ])
})
</script>

<style scoped>
.dashboard-center-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
}

.toolbar-actions {
  display: flex;
  align-items: center;
  gap: 10px;
}

.dashboard-table :deep(.el-table__row) {
  cursor: pointer;
}

.dashboard-table :deep(.el-table__row:hover > td) {
  background: rgba(15, 118, 110, 0.05) !important;
}

.preview-header,
.designer-topbar,
.designer-panel-header,
.canvas-component-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.preview-title {
  margin: 0 0 8px;
  font-size: 18px;
}

.preview-description,
.designer-topbar p,
.designer-panel-header span {
  margin: 0;
  color: var(--app-text-muted);
}

.preview-grid,
.designer-canvas {
  display: grid;
  grid-template-columns: repeat(12, minmax(0, 1fr));
  gap: 14px;
}

.preview-component,
.canvas-component {
  min-width: 0;
}

.designer-drawer :deep(.el-drawer__body) {
  padding: 0;
}

.designer-shell {
  display: grid;
  grid-template-columns: 280px minmax(0, 1fr) 280px;
  min-height: 100vh;
  background: var(--app-bg);
}

.designer-sidebar,
.designer-properties {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 14px;
  background: var(--app-surface);
  border-right: 1px solid var(--app-border);
}

.designer-properties {
  border-right: 0;
  border-left: 1px solid var(--app-border);
}

.designer-panel-header h3,
.designer-topbar h2 {
  margin: 0;
}

.designer-panel-header h3 {
  font-size: 15px;
}

.designer-panel-actions {
  display: flex;
  align-items: center;
  gap: 6px;
}

.chart-search {
  width: 100%;
}

.chart-type-picker {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.chart-type-picker span {
  color: var(--app-text-muted);
  font-size: 12px;
}

.chart-library {
  display: flex;
  flex-direction: column;
  gap: 10px;
  overflow: auto;
}

.chart-library-item {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 12px;
  border: 1px solid var(--app-border);
  border-radius: var(--app-radius-sm);
  background: var(--app-surface);
  cursor: grab;
  transition: border-color 0.2s, box-shadow 0.2s;
}

.chart-library-item:hover {
  border-color: rgba(15, 118, 110, 0.36);
  box-shadow: var(--app-shadow-soft);
}

.library-title {
  font-weight: 600;
  color: var(--app-text);
}

.library-meta {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  color: var(--app-text-muted);
  font-size: 12px;
}

.designer-main {
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.designer-topbar {
  padding: 14px 18px;
  background: var(--app-surface);
  border-bottom: 1px solid var(--app-border);
}

.designer-actions {
  display: flex;
  gap: 10px;
}

.designer-canvas-wrap {
  padding: 14px 18px 20px;
  overflow: auto;
}

.canvas-ruler {
  display: grid;
  grid-template-columns: repeat(12, minmax(0, 1fr));
  gap: 14px;
  margin-bottom: 8px;
  color: var(--app-text-muted);
  font-size: 12px;
  text-align: center;
}

.designer-canvas {
  position: relative;
  min-height: calc(100vh - 130px);
  padding: 16px;
  border: 1px dashed #b7c5d3;
  border-radius: var(--app-radius);
  background:
    linear-gradient(#ffffff, #ffffff) padding-box,
    repeating-linear-gradient(
      90deg,
      rgba(15, 118, 110, 0.05) 0,
      rgba(15, 118, 110, 0.05) 1px,
      transparent 1px,
      transparent calc((100% - 154px) / 12 + 14px)
    );
  align-content: start;
}

.canvas-empty {
  grid-column: 1 / -1;
  min-height: 280px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  color: var(--app-text-muted);
  border: 1px dashed var(--app-border);
  border-radius: var(--app-radius);
  background: rgba(255, 255, 255, 0.7);
}

.canvas-component {
  padding: 8px;
  border: 1px solid transparent;
  border-radius: var(--app-radius);
  background: var(--app-surface);
  cursor: grab;
  transition: border-color 0.2s, box-shadow 0.2s;
}

.canvas-component.selected {
  border-color: var(--app-primary);
  box-shadow: 0 0 0 3px rgba(15, 118, 110, 0.14);
}

.canvas-component-toolbar {
  padding: 4px 4px 8px;
  font-weight: 600;
  color: var(--app-text);
}

.component-actions {
  display: flex;
  align-items: center;
  gap: 4px;
  flex-wrap: wrap;
  justify-content: flex-end;
}

.property-form {
  width: 100%;
}

.chart-creator-form {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.chart-preview-panel {
  min-height: 260px;
  padding: 10px;
  border: 1px solid var(--app-border);
  border-radius: var(--app-radius);
  background: var(--app-surface-muted);
}

@media (max-width: 1120px) {
  .designer-shell {
    grid-template-columns: 240px minmax(0, 1fr);
  }

  .designer-properties {
    grid-column: 1 / -1;
    min-height: auto;
    border-left: 0;
    border-top: 1px solid var(--app-border);
  }
}

@media (max-width: 760px) {
  .designer-shell {
    grid-template-columns: 1fr;
  }

  .designer-sidebar {
    border-right: 0;
    border-bottom: 1px solid var(--app-border);
  }

  .designer-topbar {
    align-items: flex-start;
    flex-direction: column;
  }

  .preview-grid,
  .designer-canvas {
    grid-template-columns: 1fr;
  }

  .preview-component,
  .canvas-component {
    grid-column: 1 / -1 !important;
  }

  .canvas-ruler {
    display: none;
  }
}
</style>
