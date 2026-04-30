<template>
  <div class="page">
    <!-- Stats Cards -->
    <div class="stats-row">
      <div class="stat-card">
        <div class="stat-icon user-icon">
          <el-icon :size="24"><User /></el-icon>
        </div>
        <div class="stat-info">
          <div class="stat-value">{{ users.length }}</div>
          <div class="stat-label">总用户数</div>
        </div>
      </div>
      <div class="stat-card">
        <div class="stat-icon admin-icon">
          <el-icon :size="24"><UserFilled /></el-icon>
        </div>
        <div class="stat-info">
          <div class="stat-value">{{ adminCount }}</div>
          <div class="stat-label">管理员</div>
        </div>
      </div>
      <div class="stat-card">
        <div class="stat-icon org-icon">
          <el-icon :size="24"><OfficeBuilding /></el-icon>
        </div>
        <div class="stat-info">
          <div class="stat-value">{{ organizations.length }}</div>
          <div class="stat-label">企业数</div>
        </div>
      </div>
    </div>

    <!-- User Table -->
    <el-card class="table-card">
      <template #header>
        <div class="card-header">
          <div class="card-header-left">
            <span class="card-header-title">用户列表</span>
            <el-tag effect="plain" size="small">{{ users.length }} 个用户</el-tag>
          </div>
          <div class="card-header-actions">
            <el-button :icon="Refresh" @click="fetchUsers">刷新</el-button>
            <el-button type="primary" :icon="Plus" @click="openCreate">新增用户</el-button>
          </div>
        </div>
      </template>

      <el-table :data="users" stripe>
        <el-table-column prop="username" label="用户名" min-width="150">
          <template #default="{ row }">
            <div class="user-cell">
              <div class="user-avatar">{{ row.username.charAt(0).toUpperCase() }}</div>
              <span class="user-name">{{ row.username }}</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="role" label="角色" width="140">
          <template #default="{ row }">
            <el-tag :type="roleTagType(row.role)" size="small" effect="light">
              {{ roleLabel(row.role) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="org_name" label="所属企业" min-width="150">
          <template #default="{ row }">
            <span v-if="row.org_name" class="org-name">
              <el-icon><OfficeBuilding /></el-icon>
              {{ row.org_name }}
            </span>
            <span v-else class="no-org">-</span>
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
    <el-dialog v-model="dialogVisible" :title="isEdit ? '编辑用户' : '新增用户'" width="500px" destroy-on-close>
      <el-form :model="form" label-width="100px" class="user-form">
        <el-form-item label="用户名" required>
          <el-input v-model="form.username" placeholder="请输入用户名" />
        </el-form-item>
        <el-form-item label="密码" :required="!isEdit">
          <el-input v-model="form.password" type="password" show-password :placeholder="isEdit ? '留空则不修改密码' : '请输入密码'" />
        </el-form-item>
        <el-form-item label="角色" required>
          <el-select v-model="form.role" style="width: 100%" placeholder="选择角色">
            <el-option label="普通用户" value="user">
              <div class="role-option">
                <el-tag type="info" size="small">普通用户</el-tag>
                <span class="role-desc">可查询数据、管理本企业数据源</span>
              </div>
            </el-option>
            <el-option label="企业管理员" value="org_admin">
              <div class="role-option">
                <el-tag type="warning" size="small">企业管理员</el-tag>
                <span class="role-desc">可管理本企业用户和数据源</span>
              </div>
            </el-option>
            <el-option v-if="isSuperAdmin" label="超级管理员" value="super_admin">
              <div class="role-option">
                <el-tag type="danger" size="small">超级管理员</el-tag>
                <span class="role-desc">拥有所有权限</span>
              </div>
            </el-option>
          </el-select>
        </el-form-item>
        <el-form-item v-if="isSuperAdmin" label="所属企业">
          <el-select v-model="form.org_id" style="width: 100%" clearable placeholder="选择企业（超管可留空）">
            <el-option v-for="org in organizations" :key="org.id" :label="org.name" :value="org.id" />
          </el-select>
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
import { computed, onMounted, reactive, ref } from "vue"
import axios from "axios"
import { ElMessage, ElMessageBox } from "element-plus"
import { useAuthStore } from "@/store/auth"
import { User, UserFilled, OfficeBuilding, Refresh, Plus, Edit, Delete } from "@element-plus/icons-vue"

interface UserItem {
  id: number
  username: string
  role: string
  org_id: number | null
  org_name: string | null
}

interface OrgItem {
  id: number
  name: string
  slug: string
}

const authStore = useAuthStore()
const users = ref<UserItem[]>([])
const organizations = ref<OrgItem[]>([])
const dialogVisible = ref(false)
const isEdit = ref(false)
const editId = ref<number | null>(null)
const saving = ref(false)

const form = reactive({
  username: "",
  password: "",
  role: "user",
  org_id: null as number | null,
})

const isSuperAdmin = computed(() => authStore.profile?.role === "super_admin")
const adminCount = computed(() => users.value.filter(u => u.role !== "user").length)

const roleLabel = (role: string) => {
  const map: Record<string, string> = {
    user: "普通用户",
    org_admin: "企业管理员",
    super_admin: "超级管理员",
  }
  return map[role] || role
}

const roleTagType = (role: string) => {
  const map: Record<string, string> = {
    user: "info",
    org_admin: "warning",
    super_admin: "danger",
  }
  return map[role] || "info"
}

const fetchUsers = async () => {
  const res = await axios.get("/api/users")
  users.value = res.data
}

const fetchOrgs = async () => {
  if (isSuperAdmin.value) {
    const res = await axios.get("/api/organizations")
    organizations.value = res.data
  }
}

const openCreate = () => {
  isEdit.value = false
  editId.value = null
  form.username = ""
  form.password = ""
  form.role = "user"
  form.org_id = authStore.profile?.org_id || null
  dialogVisible.value = true
}

const openEdit = (row: UserItem) => {
  isEdit.value = true
  editId.value = row.id
  form.username = row.username
  form.password = ""
  form.role = row.role
  form.org_id = row.org_id
  dialogVisible.value = true
}

const handleSave = async () => {
  if (!form.username || (!isEdit.value && !form.password)) {
    ElMessage.warning("请填写必填字段")
    return
  }
  saving.value = true
  try {
    const payload: any = {
      username: form.username,
      role: form.role,
      org_id: form.org_id,
    }
    if (form.password) {
      payload.password = form.password
    }
    if (isEdit.value && editId.value) {
      await axios.put(`/api/users/${editId.value}`, payload)
      ElMessage.success("用户已更新")
    } else {
      await axios.post("/api/users", payload)
      ElMessage.success("用户已创建")
    }
    dialogVisible.value = false
    await fetchUsers()
  } catch (error: any) {
    ElMessage.error(error.response?.data?.detail || "保存失败")
  } finally {
    saving.value = false
  }
}

const handleDelete = async (id: number) => {
  try {
    await ElMessageBox.confirm("确定要删除此用户？", "提示", { type: "warning" })
    await axios.delete(`/api/users/${id}`)
    ElMessage.success("已删除")
    await fetchUsers()
  } catch {
    // cancelled
  }
}

onMounted(async () => {
  await fetchUsers()
  await fetchOrgs()
})
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
  border: 1px solid var(--app-border);
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

.user-icon { background: #0f766e; }
.admin-icon { background: linear-gradient(135deg, #f59e0b, #d97706); }
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
  border: 1px solid var(--app-border);
  box-shadow: var(--app-shadow-soft);
}

.table-card:hover {
  transform: none;
}

.table-card :deep(.el-card__header) {
  padding: 14px 18px;
  background: var(--app-surface);
  border-bottom: 1px solid var(--app-border);
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
  background: var(--app-primary);
  border-radius: 2px;
}

.card-header-actions {
  display: flex;
  gap: 12px;
}

.user-cell {
  display: flex;
  align-items: center;
  gap: 10px;
}

.user-avatar {
  width: 32px;
  height: 32px;
  border-radius: 8px;
  background: var(--app-primary);
  color: white;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 600;
  font-size: 14px;
}

.user-name {
  font-weight: 500;
}

.org-name {
  display: flex;
  align-items: center;
  gap: 6px;
  color: var(--app-text);
}

.org-name .el-icon {
  color: var(--app-text-muted);
}

.no-org {
  color: var(--app-text-light);
}

.user-form {
  padding: 8px 0;
}

.role-option {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 4px 0;
}

.role-desc {
  font-size: 12px;
  color: var(--app-text-muted);
}
</style>
