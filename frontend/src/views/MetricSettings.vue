<template>
  <div class="page">
    <el-card>
      <template #header>
        <div class="card-header">
          <span class="card-header-title">指标配置</span>
          <el-button type="primary" size="small" @click="openDialog()">新增指标</el-button>
        </div>
      </template>
      <el-table :data="metrics" v-loading="loading">
        <el-table-column prop="name" label="指标名称" width="150" />
        <el-table-column prop="description" label="描述" />
        <el-table-column prop="table_name" label="表名" width="120" />
        <el-table-column prop="column_name" label="字段名" width="120" />
        <el-table-column prop="formula" label="计算公式" />
        <el-table-column label="状态" width="80">
          <template #default="{ row }">
            <el-tag :type="row.is_active ? 'success' : 'info'">
              {{ row.is_active ? '启用' : '禁用' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="150">
          <template #default="{ row }">
            <el-button size="small" @click="openDialog(row)">编辑</el-button>
            <el-button size="small" type="danger" @click="deleteMetric(row.id)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog v-model="dialogVisible" :title="editingId ? '编辑指标' : '新增指标'" width="600px">
      <el-form :model="form" label-width="100px">
        <el-form-item label="指标名称" required>
          <el-input v-model="form.name" placeholder="如：异常数量" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="form.description" type="textarea" :rows="2" placeholder="指标说明" />
        </el-form-item>
        <el-form-item label="定义" required>
          <el-input v-model="form.definition" type="textarea" :rows="3" placeholder="指标的详细定义" />
        </el-form-item>
        <el-form-item label="表名">
          <el-input v-model="form.table_name" placeholder="如：detail" />
        </el-form-item>
        <el-form-item label="字段名">
          <el-input v-model="form.column_name" placeholder="如：count" />
        </el-form-item>
        <el-form-item label="计算公式">
          <el-input v-model="form.formula" type="textarea" :rows="2" placeholder="如：SUM(count)" />
        </el-form-item>
        <el-form-item label="状态">
          <el-switch v-model="form.is_active" :active-value="1" :inactive-value="0" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="saveMetric" :loading="saving">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from "vue"
import axios from "axios"
import { ElMessage, ElMessageBox } from "element-plus"

interface Metric {
  id: number
  name: string
  description: string
  definition: string
  table_name: string
  column_name: string
  formula: string
  is_active: number
}

const metrics = ref<Metric[]>([])
const loading = ref(false)
const dialogVisible = ref(false)
const editingId = ref<number | null>(null)
const saving = ref(false)

const form = ref({
  name: "",
  description: "",
  definition: "",
  table_name: "",
  column_name: "",
  formula: "",
  is_active: 1
})

const fetchMetrics = async () => {
  loading.value = true
  try {
    const response = await axios.get("/api/metrics")
    metrics.value = response.data.items
  } catch (error) {
    ElMessage.error("加载指标列表失败")
  } finally {
    loading.value = false
  }
}

const openDialog = (metric?: Metric) => {
  if (metric) {
    editingId.value = metric.id
    form.value = { ...metric }
  } else {
    editingId.value = null
    form.value = {
      name: "",
      description: "",
      definition: "",
      table_name: "",
      column_name: "",
      formula: "",
      is_active: 1
    }
  }
  dialogVisible.value = true
}

const saveMetric = async () => {
  if (!form.value.name || !form.value.definition) {
    ElMessage.warning("请填写必填项")
    return
  }
  saving.value = true
  try {
    if (editingId.value) {
      await axios.put(`/api/metrics/${editingId.value}`, form.value)
    } else {
      await axios.post("/api/metrics", form.value)
    }
    ElMessage.success("保存成功")
    dialogVisible.value = false
    fetchMetrics()
  } catch (error: any) {
    ElMessage.error(error.response?.data?.detail || "保存失败")
  } finally {
    saving.value = false
  }
}

const deleteMetric = async (id: number) => {
  try {
    await ElMessageBox.confirm("确定删除该指标？", "提示", { type: "warning" })
    await axios.delete(`/api/metrics/${id}`)
    ElMessage.success("删除成功")
    fetchMetrics()
  } catch (error: any) {
    if (error !== "cancel") {
      ElMessage.error("删除失败")
    }
  }
}

onMounted(() => {
  fetchMetrics()
})
</script>
