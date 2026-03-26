<template>
  <div class="page">
    <el-row :gutter="16">
      <el-col :span="24">
        <el-card>
          <template #header>
            <div class="card-header">
              <span class="card-header-title">数据源管理</span>
              <el-button type="primary" size="small" @click="openCreate">新增数据源</el-button>
            </div>
          </template>

          <el-table :data="datasources" stripe>
            <el-table-column prop="name" label="名称" width="160" />
            <el-table-column prop="slug" label="标识" width="120" />
            <el-table-column prop="source_type" label="类型" width="100">
              <template #default="{ row }">
                <el-tag :type="row.source_type === 'excel' ? 'warning' : 'primary'" size="small">
                  {{ row.source_type === 'excel' ? 'Excel' : '数据库' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="is_active" label="状态" width="80">
              <template #default="{ row }">
                <el-tag :type="row.is_active ? 'success' : 'info'" size="small">
                  {{ row.is_active ? '启用' : '禁用' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="元数据提示词" min-width="200">
              <template #default="{ row }">
                <span class="truncate-text">{{ row.metadata_prompt?.substring(0, 80) }}...</span>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="240" fixed="right">
              <template #default="{ row }">
                <el-button size="small" @click="testConnection(row.id)">测试连接</el-button>
                <el-button size="small" type="primary" @click="openEdit(row)">编辑</el-button>
                <el-button size="small" type="danger" @click="handleDelete(row.id)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-col>
    </el-row>

    <!-- 创建/编辑对话框 -->
    <el-dialog v-model="dialogVisible" :title="isEdit ? '编辑数据源' : '新增数据源'" width="700px">
      <el-form :model="form" label-width="120px">
        <el-form-item label="名称" required>
          <el-input v-model="form.name" placeholder="如：嘉盛半导体" />
        </el-form-item>
        <el-form-item label="标识 (slug)" required>
          <el-input v-model="form.slug" placeholder="如：carsem（英文标识，URL友好）" />
        </el-form-item>
        <el-form-item label="数据源类型" required>
          <el-select v-model="form.source_type" placeholder="选择类型" style="width: 100%">
            <el-option label="数据库 (PostgreSQL等)" value="database" />
            <el-option label="Excel 文件" value="excel" />
          </el-select>
        </el-form-item>
        <el-form-item :label="form.source_type === 'excel' ? '文件路径' : '数据库连接'" required>
          <el-input
            v-model="form.database_url"
            :placeholder="form.source_type === 'excel' ? '/path/to/file.xlsx' : 'postgresql+psycopg2://user:pass@host:port/dbname'"
            type="textarea"
            :rows="2"
          />
        </el-form-item>
        <el-form-item label="表结构描述" :required="form.source_type !== 'excel'">
          <el-input
            v-model="form.metadata_prompt"
            type="textarea"
            :rows="8"
            :placeholder="form.source_type === 'excel' ? '留空则自动从Excel文件生成' : '描述数据库的表结构信息，供LLM生成SQL时参考。\n例如：\n- users 表：用户信息\n  - id: 主键\n  - name: 用户名'"
          />
        </el-form-item>
        <el-form-item label="指标描述">
          <el-input
            v-model="form.metrics_prompt"
            type="textarea"
            :rows="3"
            placeholder="可用的业务指标描述（可选）"
          />
        </el-form-item>
        <el-form-item label="推荐问题">
          <el-input
            v-model="recommendQuestionsText"
            type="textarea"
            :rows="3"
            placeholder="每行一个推荐问题（可选）"
          />
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
import { useDatasourceStore } from "@/store/datasource"
import { useRouter } from "vue-router"

interface DataSourceDetail {
  id: number
  name: string
  slug: string
  source_type: string
  database_url?: string
  metadata_prompt: string
  metrics_prompt: string | null
  text2sql_prompt: string | null
  recommend_questions: string[] | null
  is_active: number
}

const authStore = useAuthStore()
const datasourceStore = useDatasourceStore()
const router = useRouter()

const datasources = ref<DataSourceDetail[]>([])
const dialogVisible = ref(false)
const isEdit = ref(false)
const editId = ref<number | null>(null)
const saving = ref(false)

const form = reactive({
  name: "",
  slug: "",
  source_type: "database",
  database_url: "",
  metadata_prompt: "",
  metrics_prompt: "",
})

const recommendQuestionsText = ref("")

const fetchAll = async () => {
  const response = await axios.get("/api/datasources")
  // Fetch full details for each
  const details = await Promise.all(
    response.data.map((ds: any) => axios.get(`/api/datasources/${ds.id}`))
  )
  datasources.value = details.map(r => r.data)
}

const openCreate = () => {
  isEdit.value = false
  editId.value = null
  form.name = ""
  form.slug = ""
  form.source_type = "database"
  form.database_url = ""
  form.metadata_prompt = ""
  form.metrics_prompt = ""
  recommendQuestionsText.value = ""
  dialogVisible.value = true
}

const openEdit = (row: DataSourceDetail) => {
  isEdit.value = true
  editId.value = row.id
  form.name = row.name
  form.slug = row.slug
  form.source_type = row.source_type || "database"
  form.database_url = ""  // Don't show existing URL for security
  form.metadata_prompt = row.metadata_prompt
  form.metrics_prompt = row.metrics_prompt || ""
  recommendQuestionsText.value = (row.recommend_questions || []).join("\n")
  dialogVisible.value = true
}

const handleSave = async () => {
  // Validate required fields - metadata_prompt is optional for Excel
  const metadataRequired = form.source_type !== 'excel'
  if (!form.name || !form.slug || (!isEdit.value && !form.database_url) || (metadataRequired && !form.metadata_prompt)) {
    ElMessage.warning("请填写必填字段")
    return
  }

  saving.value = true
  try {
    const questions = recommendQuestionsText.value
      .split("\n")
      .map(s => s.trim())
      .filter(Boolean)

    const payload: any = {
      name: form.name,
      slug: form.slug,
      source_type: form.source_type,
      metadata_prompt: form.metadata_prompt || "",
      metrics_prompt: form.metrics_prompt || null,
      recommend_questions: questions.length > 0 ? questions : null,
    }

    if (form.database_url) {
      payload.database_url = form.database_url
    }

    if (isEdit.value && editId.value) {
      await axios.put(`/api/datasources/${editId.value}`, payload)
      ElMessage.success("数据源已更新")
    } else {
      await axios.post("/api/datasources", payload)
      ElMessage.success("数据源已创建")
    }

    dialogVisible.value = false
    await fetchAll()
    await datasourceStore.fetchDatasources()
  } catch (error: any) {
    ElMessage.error(error.response?.data?.detail || "保存失败")
  } finally {
    saving.value = false
  }
}

const handleDelete = async (id: number) => {
  try {
    await ElMessageBox.confirm("确定要删除此数据源？", "提示", { type: "warning" })
    await axios.delete(`/api/datasources/${id}`)
    ElMessage.success("已删除")
    await fetchAll()
    await datasourceStore.fetchDatasources()
  } catch {
    // cancelled
  }
}

const testConnection = async (id: number) => {
  try {
    const response = await axios.post(`/api/datasources/${id}/test`)
    if (response.data.status === "ok") {
      ElMessage.success("连接成功")
    } else {
      ElMessage.error(response.data.message)
    }
  } catch {
    ElMessage.error("测试失败")
  }
}

onMounted(async () => {
  if (!authStore.profile && authStore.token) {
    await authStore.fetchProfile()
  }
  if (authStore.profile && authStore.profile.role !== "admin") {
    router.push("/dashboard")
    return
  }
  await fetchAll()
})
</script>

<style scoped>
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.card-header-title {
  font-weight: 600;
  font-size: 16px;
}

.truncate-text {
  color: #909399;
  font-size: 12px;
}
</style>
