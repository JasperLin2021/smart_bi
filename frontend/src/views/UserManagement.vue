<template>
  <div class="page">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>用户管理</span>
          <el-button type="primary" size="small" @click="openCreate">新增用户</el-button>
        </div>
      </template>

      <el-table :data="users" stripe>
        <el-table-column prop="username" label="用户名" width="150" />
        <el-table-column prop="role" label="角色" width="120">
          <template #default="{ row }">
            <el-tag :type="roleTagType(row.role)" size="small">
              {{ roleLabel(row.role) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="org_name" label="所属企业" width="150" />
        <el-table-column label="操作" width="180">
          <template #default="{ row }">
            <el-button size="small" @click="openEdit(row)">编辑</el-button>
            <el-button size="small" type="danger" @click="handleDelete(row.id)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog v-model="dialogVisible" :title="isEdit ? '编辑用户' : '新增用户'" width="500px">
      <el-form :model="form" label-width="100px">
        <el-form-item label="用户名" required>
          <el-input v-model="form.username" />
        </el-form-item>
        <el-form-item label="密码" :required="!isEdit">
          <el-input v-model="form.password" type="password" :placeholder="isEdit ? '留空则不修改' : ''" />
        </el-form-item>
        <el-form-item label="角色" required>
          <el-select v-model="form.role" style="width: 100%">
            <el-option label="普通用户" value="user" />
            <el-option label="企业管理员" value="org_admin" />
            <el-option v-if="isSuperAdmin" label="超级管理员" value="super_admin" />
          </el-select>
        </el-form-item>
        <el-form-item v-if="isSuperAdmin" label="所属企业">
          <el-select v-model="form.org_id" style="width: 100%" clearable placeholder="无（超级管理员）">
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
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
</style>
