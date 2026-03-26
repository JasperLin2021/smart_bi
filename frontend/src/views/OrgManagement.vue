<template>
  <div class="page">
    <!-- Stats Card -->
    <div class="stats-row">
      <div class="stat-card">
        <div class="stat-icon org-icon">
          <el-icon :size="24"><OfficeBuilding /></el-icon>
        </div>
        <div class="stat-info">
          <div class="stat-value">{{ organizations.length }}</div>
          <div class="stat-label">企业总数</div>
        </div>
      </div>
    </div>

    <!-- Org Table -->
    <el-card class="table-card">
      <template #header>
        <div class="card-header">
          <div class="card-header-left">
            <span class="card-header-title">企业列表</span>
            <el-tag effect="plain" size="small">{{ organizations.length }} 个企业</el-tag>
          </div>
          <div class="card-header-actions">
            <el-button :icon="Refresh" @click="fetchOrgs">刷新</el-button>
            <el-button type="primary" :icon="Plus" @click="openCreate">新增企业</el-button>
          </div>
        </div>
      </template>

      <el-table :data="organizations" stripe>
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="name" label="企业名称" min-width="200">
          <template #default="{ row }">
            <div class="org-cell">
              <div class="org-avatar">{{ row.name.charAt(0) }}</div>
              <span class="org-name">{{ row.name }}</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="slug" label="标识" width="150">
          <template #default="{ row }">
            <el-tag effect="plain" size="small">{{ row.slug }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" width="180">
          <template #default="{ row }">
            <span class="date-text">
              <el-icon><Calendar /></el-icon>
              {{ formatDate(row.created_at) }}
            </span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="180" fixed="right">
          <template #default="{ row }">
            <el-button size="small" type="primary" text @click="openEdit(row)">
              <el-icon><Edit /></el-icon> 编辑
            </el-button>
            <el-button size="small" type="danger" text @click="handleDelete(row.id)">
              <el-icon><Delete /></el-icon> 删除
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- Dialog -->
    <el-dialog v-model="dialogVisible" :title="isEdit ? '编辑企业' : '新增企业'" width="500px" destroy-on-close>
      <el-form :model="form" label-width="100px" class="org-form">
        <el-form-item label="企业名称" required>
          <el-input v-model="form.name" placeholder="如：嘉盛半导体" />
        </el-form-item>
        <el-form-item label="标识 (slug)" required>
          <el-input v-model="form.slug" placeholder="如：carsem（英文标识，URL友好）" />
          <div class="form-tip">标识用于区分不同企业，建议使用英文小写字母</div>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="handleSave">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from "vue"
import axios from "axios"
import { ElMessage, ElMessageBox } from "element-plus"
import { OfficeBuilding, Refresh, Plus, Edit, Delete, Calendar } from "@element-plus/icons-vue"

interface OrgItem {
  id: number
  name: string
  slug: string
  created_at: string
}

const organizations = ref<OrgItem[]>([])
const dialogVisible = ref(false)
const isEdit = ref(false)
const editId = ref<number | null>(null)
const saving = ref(false)

const form = reactive({
  name: "",
  slug: "",
})

const formatDate = (dateStr: string) => {
  return new Date(dateStr).toLocaleString("zh-CN", {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit'
  })
}

const fetchOrgs = async () => {
  const res = await axios.get("/api/organizations")
  organizations.value = res.data
}

const openCreate = () => {
  isEdit.value = false
  editId.value = null
  form.name = ""
  form.slug = ""
  dialogVisible.value = true
}

const openEdit = (row: OrgItem) => {
  isEdit.value = true
  editId.value = row.id
  form.name = row.name
  form.slug = row.slug
  dialogVisible.value = true
}

const handleSave = async () => {
  if (!form.name || !form.slug) {
    ElMessage.warning("请填写必填字段")
    return
  }
  saving.value = true
  try {
    if (isEdit.value && editId.value) {
      await axios.put(`/api/organizations/${editId.value}`, form)
      ElMessage.success("企业已更新")
    } else {
      await axios.post("/api/organizations", form)
      ElMessage.success("企业已创建")
    }
    dialogVisible.value = false
    await fetchOrgs()
  } catch (error: any) {
    ElMessage.error(error.response?.data?.detail || "保存失败")
  } finally {
    saving.value = false
  }
}

const handleDelete = async (id: number) => {
  try {
    await ElMessageBox.confirm("确定要删除此企业？删除后该企业下的用户将无法登录。", "提示", { type: "warning" })
    await axios.delete(`/api/organizations/${id}`)
    ElMessage.success("已删除")
    await fetchOrgs()
  } catch {
    // cancelled
  }
}

onMounted(fetchOrgs)
</script>

<style scoped>
.stats-row {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 20px;
  margin-bottom: 24px;
}

.stat-card {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 20px 24px;
  background: var(--app-surface);
  border-radius: var(--app-radius);
  box-shadow: var(--app-shadow-soft);
}

.stat-icon {
  width: 48px;
  height: 48px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
}

.org-icon { background: linear-gradient(135deg, #10b981, #059669); }

.stat-value {
  font-size: 28px;
  font-weight: 700;
  color: var(--app-text);
}

.stat-label {
  font-size: 13px;
  color: var(--app-text-muted);
  margin-top: 2px;
}

.table-card {
  border: none;
  box-shadow: var(--app-shadow-soft);
}

.table-card:hover {
  transform: none;
}

.table-card :deep(.el-card__header) {
  padding: 20px 24px;
  background: linear-gradient(135deg, #f8fafc 0%, #f1f5f9 100%);
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.card-header-left {
  display: flex;
  align-items: center;
  gap: 12px;
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
  background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%);
  border-radius: 2px;
}

.card-header-actions {
  display: flex;
  gap: 12px;
}

.org-cell {
  display: flex;
  align-items: center;
  gap: 10px;
}

.org-avatar {
  width: 36px;
  height: 36px;
  border-radius: 8px;
  background: linear-gradient(135deg, #10b981, #059669);
  color: white;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 600;
  font-size: 16px;
}

.org-name {
  font-weight: 500;
  color: var(--app-text);
}

.date-text {
  display: flex;
  align-items: center;
  gap: 6px;
  color: var(--app-text-muted);
  font-size: 13px;
}

.org-form {
  padding: 8px 0;
}

.form-tip {
  font-size: 12px;
  color: var(--app-text-light);
  margin-top: 4px;
}
</style>
