<template>
  <div class="page">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>企业管理</span>
          <el-button type="primary" size="small" @click="openCreate">新增企业</el-button>
        </div>
      </template>

      <el-table :data="organizations" stripe>
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="name" label="企业名称" width="200" />
        <el-table-column prop="slug" label="标识" width="150" />
        <el-table-column prop="created_at" label="创建时间" width="180">
          <template #default="{ row }">
            {{ formatDate(row.created_at) }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="180">
          <template #default="{ row }">
            <el-button size="small" @click="openEdit(row)">编辑</el-button>
            <el-button size="small" type="danger" @click="handleDelete(row.id)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog v-model="dialogVisible" :title="isEdit ? '编辑企业' : '新增企业'" width="500px">
      <el-form :model="form" label-width="100px">
        <el-form-item label="企业名称" required>
          <el-input v-model="form.name" placeholder="如：嘉盛半导体" />
        </el-form-item>
        <el-form-item label="标识 (slug)" required>
          <el-input v-model="form.slug" placeholder="如：carsem（英文标识）" />
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
  return new Date(dateStr).toLocaleString("zh-CN")
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
    await ElMessageBox.confirm("确定要删除此企业？", "提示", { type: "warning" })
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
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
</style>
