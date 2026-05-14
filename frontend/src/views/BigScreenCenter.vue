<template>
  <div class="bigscreen-page">
    <div class="toolbar">
      <el-segmented class="page-segmented-tabs" v-model="statusFilter" :options="statusOptions" @change="fetchScreens" />
      <div class="toolbar-actions">
        <el-button @click="openGoViewDesigner">GoView 设计器</el-button>
        <el-button type="primary" @click="openCreate">新建大屏</el-button>
      </div>
    </div>

    <el-table v-loading="loading" :data="screens" @row-click="openDesigner">
      <el-table-column prop="title" label="大屏名称" min-width="180" />
      <el-table-column prop="description" label="描述" min-width="220" show-overflow-tooltip />
      <el-table-column label="组件数" width="100">
        <template #default="{ row }">{{ widgetCount(row) }}</template>
      </el-table-column>
      <el-table-column label="状态" width="100">
        <template #default="{ row }">
          <el-tag :type="row.status === 'published' ? 'success' : 'info'" effect="plain">
            {{ row.status === 'published' ? '已发布' : '草稿' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="230" fixed="right">
        <template #default="{ row }">
          <el-button text type="primary" @click.stop="openDesigner(row)">设计</el-button>
          <el-button text type="primary" @click.stop="openEdit(row)">编辑</el-button>
          <el-button v-if="row.status !== 'published'" text type="success" @click.stop="publishScreen(row)">发布</el-button>
          <el-button text type="danger" @click.stop="deleteScreen(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-dialog v-model="dialogVisible" :title="editingId ? '编辑大屏' : '新建大屏'" width="560px">
      <el-form :model="form" label-width="88px">
        <el-form-item label="名称" required>
          <el-input v-model="form.title" maxlength="128" />
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
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="saveScreen">保存</el-button>
      </template>
    </el-dialog>

    <el-drawer v-model="designerVisible" :with-header="false" size="94%" class="bigscreen-designer">
      <div v-if="designingScreen" class="designer-shell">
        <aside class="designer-panel">
          <h3>组件</h3>
          <el-button plain @click="addWidget('kpi')">指标卡</el-button>
          <el-button plain @click="addWidget('chart')">趋势图</el-button>
          <el-button plain @click="addWidget('table')">明细表</el-button>
          <el-button plain @click="addWidget('text')">文本</el-button>
        </aside>

        <main class="designer-main">
          <header class="designer-topbar">
            <div>
              <h2>{{ designingScreen.title }}</h2>
              <p>{{ designingScreen.description || "面向会议室和监控屏的大屏画布" }}</p>
            </div>
            <div class="designer-actions">
              <el-button @click="designerVisible = false">关闭</el-button>
              <el-button type="primary" :loading="designerSaving" @click="saveDesigner">保存画布</el-button>
            </div>
          </header>
          <section class="screen-canvas">
            <div
              v-for="widget in widgets"
              :key="widget.id"
              class="screen-widget"
              :class="{ selected: selectedWidgetId === widget.id }"
              :style="{ gridColumn: `span ${widget.w}`, minHeight: `${widget.h * 90}px` }"
              @click="selectedWidgetId = widget.id"
            >
              <div class="widget-title">
                <span>{{ widget.title }}</span>
                <el-button text type="danger" @click.stop="removeWidget(widget.id)">删除</el-button>
              </div>
              <div class="widget-body">{{ widgetPreview(widget.type) }}</div>
            </div>
            <el-empty v-if="widgets.length === 0" description="添加组件开始设计大屏" />
          </section>
        </main>

        <aside class="designer-panel">
          <h3>属性</h3>
          <template v-if="selectedWidget">
            <el-form label-position="top">
              <el-form-item label="标题">
                <el-input v-model="selectedWidget.title" />
              </el-form-item>
              <el-form-item label="宽度">
                <el-slider v-model="selectedWidget.w" :min="3" :max="12" />
              </el-form-item>
              <el-form-item label="高度">
                <el-slider v-model="selectedWidget.h" :min="2" :max="6" />
              </el-form-item>
              <el-form-item label="数据绑定">
                <el-input v-model="selectedWidget.binding" type="textarea" :rows="3" placeholder="metric:销售额 或 SQL/接口说明" />
              </el-form-item>
            </el-form>
          </template>
          <el-empty v-else description="选择组件后编辑属性" :image-size="72" />
        </aside>
      </div>
    </el-drawer>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue"
import { useRouter } from "vue-router"
import axios from "axios"
import { ElMessage, ElMessageBox } from "element-plus"

interface ScreenWidget {
  id: string
  type: string
  title: string
  w: number
  h: number
  binding?: string
}

interface BigScreenItem {
  id: number
  title: string
  description: string | null
  canvas_json: { widgets?: ScreenWidget[] } | null
  data_bindings_json: Record<string, unknown> | null
  status: string
  visibility: string
}

const screens = ref<BigScreenItem[]>([])
const router = useRouter()
const widgets = ref<ScreenWidget[]>([])
const loading = ref(false)
const saving = ref(false)
const designerSaving = ref(false)
const dialogVisible = ref(false)
const designerVisible = ref(false)
const editingId = ref<number | null>(null)
const designingScreen = ref<BigScreenItem | null>(null)
const selectedWidgetId = ref("")
const statusFilter = ref("all")
const statusOptions = [
  { label: "全部", value: "all" },
  { label: "已发布", value: "published" },
  { label: "草稿", value: "draft" },
]

const form = reactive({
  title: "",
  description: "",
  visibility: "private",
})

const selectedWidget = computed(() => widgets.value.find((widget) => widget.id === selectedWidgetId.value) || null)

const widgetCount = (screen: BigScreenItem) => screen.canvas_json?.widgets?.length || 0

const widgetPreview = (type: string) => {
  const labels: Record<string, string> = {
    kpi: "关键指标展示",
    chart: "趋势/排行图表",
    table: "明细数据表",
    text: "说明文字",
  }
  return labels[type] || type
}

const fetchScreens = async () => {
  loading.value = true
  try {
    const response = await axios.get("/api/big-screens", {
      params: { status: statusFilter.value === "all" ? undefined : statusFilter.value },
    })
    screens.value = response.data.items
  } catch {
    ElMessage.error("大屏列表加载失败")
  } finally {
    loading.value = false
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
  dialogVisible.value = true
}

const openGoViewDesigner = () => {
  router.push("/goview")
}

const openEdit = (screen: BigScreenItem) => {
  editingId.value = screen.id
  form.title = screen.title
  form.description = screen.description || ""
  form.visibility = screen.visibility
  dialogVisible.value = true
}

const saveScreen = async () => {
  if (!form.title.trim()) {
    ElMessage.warning("请输入大屏名称")
    return
  }
  saving.value = true
  try {
    const payload = {
      title: form.title.trim(),
      description: form.description.trim() || null,
      visibility: form.visibility,
      canvas_json: editingId.value ? undefined : { widgets: [] },
      data_bindings_json: editingId.value ? undefined : {},
    }
    if (editingId.value) {
      await axios.put(`/api/big-screens/${editingId.value}`, payload)
    } else {
      await axios.post("/api/big-screens", payload)
    }
    dialogVisible.value = false
    await fetchScreens()
  } catch (error: any) {
    ElMessage.error(error.response?.data?.detail || "大屏保存失败")
  } finally {
    saving.value = false
  }
}

const openDesigner = (screen: BigScreenItem) => {
  designingScreen.value = screen
  widgets.value = (screen.canvas_json?.widgets || []).map((widget) => ({ ...widget }))
  selectedWidgetId.value = widgets.value[0]?.id || ""
  designerVisible.value = true
}

const addWidget = (type: string) => {
  const widget: ScreenWidget = {
    id: `widget-${Date.now()}`,
    type,
    title: widgetPreview(type),
    w: type === "kpi" ? 3 : 6,
    h: type === "kpi" ? 2 : 3,
    binding: "",
  }
  widgets.value.push(widget)
  selectedWidgetId.value = widget.id
}

const removeWidget = (id: string) => {
  widgets.value = widgets.value.filter((widget) => widget.id !== id)
  selectedWidgetId.value = widgets.value[0]?.id || ""
}

const saveDesigner = async () => {
  if (!designingScreen.value) return
  designerSaving.value = true
  try {
    const response = await axios.put(`/api/big-screens/${designingScreen.value.id}`, {
      canvas_json: { widgets: widgets.value },
      data_bindings_json: {
        bindings: widgets.value.map((widget) => ({ id: widget.id, binding: widget.binding || "" })),
      },
    })
    const index = screens.value.findIndex((screen) => screen.id === response.data.id)
    if (index !== -1) screens.value[index] = response.data
    designingScreen.value = response.data
    ElMessage.success("大屏画布已保存")
  } catch (error: any) {
    ElMessage.error(error.response?.data?.detail || "画布保存失败")
  } finally {
    designerSaving.value = false
  }
}

const publishScreen = async (screen: BigScreenItem) => {
  await axios.post(`/api/big-screens/${screen.id}/publish`)
  ElMessage.success("大屏已发布")
  await fetchScreens()
}

const deleteScreen = async (screen: BigScreenItem) => {
  await ElMessageBox.confirm("确定删除这个大屏吗？", "提示", { type: "warning" })
  await axios.delete(`/api/big-screens/${screen.id}`)
  await fetchScreens()
}

onMounted(fetchScreens)
</script>

<style scoped>
.bigscreen-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.toolbar,
.toolbar-actions,
.designer-topbar,
.widget-title {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.toolbar-actions {
  flex-wrap: wrap;
  justify-content: flex-end;
}

.bigscreen-designer :deep(.el-drawer__body) {
  padding: 0;
}

.designer-shell {
  display: grid;
  grid-template-columns: 220px minmax(0, 1fr) 280px;
  min-height: 100vh;
  background: #0b1020;
}

.designer-panel {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 16px;
  background: #111827;
  color: #f8fafc;
  border-right: 1px solid rgba(148, 163, 184, 0.2);
}

.designer-panel:last-child {
  border-right: 0;
  border-left: 1px solid rgba(148, 163, 184, 0.2);
}

.designer-panel h3,
.designer-topbar h2 {
  margin: 0;
}

.designer-main {
  min-width: 0;
}

.designer-topbar {
  padding: 16px 20px;
  background: #0f172a;
  color: #f8fafc;
}

.designer-topbar p {
  margin: 6px 0 0;
  color: #94a3b8;
}

.screen-canvas {
  display: grid;
  grid-template-columns: repeat(12, minmax(0, 1fr));
  gap: 14px;
  padding: 18px;
  min-height: calc(100vh - 76px);
  align-content: start;
}

.screen-widget {
  min-width: 0;
  padding: 14px;
  border: 1px solid rgba(45, 212, 191, 0.18);
  background: rgba(15, 23, 42, 0.92);
  color: #f8fafc;
}

.screen-widget.selected {
  border-color: #2dd4bf;
}

.widget-body {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 72px;
  color: #94a3b8;
}
</style>
