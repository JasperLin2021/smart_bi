<template>
  <div class="dashboard-center-page">
    <div class="toolbar">
      <el-segmented v-model="statusFilter" :options="statusOptions" @change="fetchDashboards" />
      <el-button type="primary" :icon="Plus" @click="openCreate">新建看板</el-button>
    </div>

    <el-table v-loading="loading" :data="dashboards">
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
      <el-table-column label="操作" width="220" fixed="right">
        <template #default="{ row }">
          <el-button text type="primary" @click="preview(row)">预览</el-button>
          <el-button text type="primary" @click="edit(row)">编辑</el-button>
          <el-button v-if="row.status !== 'published'" text type="success" @click="publish(row)">发布</el-button>
          <el-button text type="danger" @click="remove(row)">删除</el-button>
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

    <el-drawer v-model="previewVisible" title="看板预览" size="520px">
      <template v-if="selectedDashboard">
        <h3 class="preview-title">{{ selectedDashboard.title }}</h3>
        <p class="preview-description">{{ selectedDashboard.description || "暂无描述" }}</p>
        <el-empty v-if="componentCount(selectedDashboard) === 0" description="暂无组件" />
        <div v-else class="component-list">
          <div v-for="item in selectedDashboard.layout_json?.components || []" :key="item.id" class="component-row">
            {{ item.title || item.id }}
          </div>
        </div>
      </template>
    </el-drawer>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from "vue"
import axios from "axios"
import { ElMessage, ElMessageBox } from "element-plus"
import { Plus } from "@element-plus/icons-vue"

interface DashboardItem {
  id: number
  title: string
  description: string | null
  layout_json: { components?: Array<{ id: string; title?: string }> } | null
  filters_json: Record<string, unknown> | null
  status: string
  visibility: string
}

const dashboards = ref<DashboardItem[]>([])
const loading = ref(false)
const saving = ref(false)
const editorVisible = ref(false)
const previewVisible = ref(false)
const selectedDashboard = ref<DashboardItem | null>(null)
const editingId = ref<number | null>(null)
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

const componentCount = (dashboard: DashboardItem) => dashboard.layout_json?.components?.length || 0

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
      layout_json: { components: [] },
      filters_json: {},
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

const remove = async (dashboard: DashboardItem) => {
  await ElMessageBox.confirm("确定要删除这个看板吗？", "提示", {
    confirmButtonText: "删除",
    cancelButtonText: "取消",
    type: "warning",
  })
  await axios.delete(`/api/dashboards/${dashboard.id}`)
  await fetchDashboards()
}

const preview = (dashboard: DashboardItem) => {
  selectedDashboard.value = dashboard
  previewVisible.value = true
}

onMounted(fetchDashboards)
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

.preview-title {
  margin: 0 0 8px;
  font-size: 18px;
}

.preview-description {
  margin: 0 0 20px;
  color: var(--app-text-muted);
}

.component-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.component-row {
  padding: 10px 12px;
  border: 1px solid var(--app-border);
  border-radius: 6px;
}
</style>
