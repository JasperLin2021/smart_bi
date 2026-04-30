<template>
  <div class="page">
    <el-card>
      <template #header>
        <div class="card-header">
          <span class="card-header-title">指标配置</span>
          <div class="card-actions">
            <el-select
              v-model="selectedDatasourceFilter"
              size="small"
              clearable
              placeholder="按数据源筛选"
              style="width: 180px"
            >
              <el-option
                v-for="ds in datasourceStore.datasources"
                :key="ds.id"
                :label="ds.name"
                :value="ds.id"
              />
            </el-select>
            <el-button type="primary" size="small" @click="openDialog()">新增指标</el-button>
          </div>
        </div>
      </template>
      <el-table :data="filteredMetrics" v-loading="loading">
        <el-table-column label="数据源" width="160">
          <template #default="{ row }">
            {{ getDatasourceName(row.datasource_id) }}
          </template>
        </el-table-column>
        <el-table-column prop="name" label="指标名称" width="150" />
        <el-table-column prop="description" label="描述" />
        <el-table-column prop="table_name" label="表名" width="120" />
        <el-table-column prop="column_name" label="字段名" width="120" />
        <el-table-column prop="formula" label="计算公式" min-width="180" show-overflow-tooltip />
        <el-table-column prop="unit" label="单位" width="80" />
        <el-table-column prop="aggregation" label="聚合" width="90" />
        <el-table-column label="标签" width="160">
          <template #default="{ row }">
            <el-tag v-for="tag in row.tags || []" :key="tag" size="small" class="metric-tag">
              {{ tag }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="发布" width="90">
          <template #default="{ row }">
            <el-tag :type="row.status === 'published' ? 'success' : row.status === 'archived' ? 'info' : 'warning'">
              {{ statusLabel(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="启用" width="80">
          <template #default="{ row }">
            <el-tag :type="row.is_active ? 'success' : 'info'">
              {{ row.is_active ? '启用' : '禁用' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="150" fixed="right">
          <template #default="{ row }">
            <el-button size="small" @click="openDialog(row)">编辑</el-button>
            <el-button size="small" type="danger" @click="deleteMetric(row.id)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog v-model="dialogVisible" :title="editingId ? '编辑指标' : '新增指标'" width="720px">
      <el-form :model="form" label-width="100px">
        <el-form-item label="数据源" required>
          <el-select v-model="form.datasource_id" placeholder="请选择数据源" style="width: 100%">
            <el-option
              v-for="ds in datasourceStore.datasources"
              :key="ds.id"
              :label="ds.name"
              :value="ds.id"
            />
          </el-select>
        </el-form-item>
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
          <el-button class="inline-button" :loading="generatingFormula" @click="generateFormula">
            AI生成公式
          </el-button>
        </el-form-item>
        <el-row :gutter="12">
          <el-col :span="12">
            <el-form-item label="负责人">
              <el-input v-model="form.owner_name" placeholder="如：财务分析师" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="单位">
              <el-input v-model="form.unit" placeholder="如：元、%、单" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="12">
          <el-col :span="12">
            <el-form-item label="聚合方式">
              <el-select v-model="form.aggregation" style="width: 100%">
                <el-option label="求和" value="sum" />
                <el-option label="平均" value="avg" />
                <el-option label="计数" value="count" />
                <el-option label="最大值" value="max" />
                <el-option label="最小值" value="min" />
                <el-option label="比率" value="ratio" />
                <el-option label="自定义" value="custom" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="发布状态">
              <el-select v-model="form.status" style="width: 100%">
                <el-option label="草稿" value="draft" />
                <el-option label="已发布" value="published" />
                <el-option label="已归档" value="archived" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="标签">
          <el-input v-model="form.tags_text" placeholder="多个标签用逗号或换行分隔" />
        </el-form-item>
        <el-form-item label="适用维度">
          <el-input
            v-model="form.dimensions_text"
            type="textarea"
            :rows="2"
            placeholder="如：region, product, month"
          />
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
import { computed, onMounted, ref } from "vue"
import axios from "axios"
import { ElMessage, ElMessageBox } from "element-plus"
import { useDatasourceStore } from "@/store/datasource"

interface Metric {
  id: number
  datasource_id: number
  name: string
  description: string
  definition: string
  table_name: string
  column_name: string
  formula: string
  owner_name: string | null
  unit: string | null
  aggregation: string
  tags: string[] | null
  status: string
  dimensions: string[] | null
  is_active: number
}

interface MetricForm {
  datasource_id: number | null
  name: string
  description: string
  definition: string
  table_name: string
  column_name: string
  formula: string
  owner_name: string
  unit: string
  aggregation: string
  tags_text: string
  status: string
  dimensions_text: string
  is_active: number
}

const metrics = ref<Metric[]>([])
const loading = ref(false)
const dialogVisible = ref(false)
const editingId = ref<number | null>(null)
const saving = ref(false)
const generatingFormula = ref(false)
const datasourceStore = useDatasourceStore()
const selectedDatasourceFilter = ref<number | null>(null)

const emptyForm = (): MetricForm => ({
  datasource_id: null as number | null,
  name: "",
  description: "",
  definition: "",
  table_name: "",
  column_name: "",
  formula: "",
  owner_name: "",
  unit: "",
  aggregation: "sum",
  tags_text: "",
  status: "published",
  dimensions_text: "",
  is_active: 1
})

const form = ref<MetricForm>(emptyForm())

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

const filteredMetrics = computed(() => {
  if (!selectedDatasourceFilter.value) {
    return metrics.value
  }
  return metrics.value.filter(item => item.datasource_id === selectedDatasourceFilter.value)
})

const getDatasourceName = (datasourceId: number) => {
  return datasourceStore.datasources.find(ds => ds.id === datasourceId)?.name || `数据源 #${datasourceId}`
}

const statusLabel = (status: string) => {
  const labels: Record<string, string> = {
    draft: "草稿",
    published: "已发布",
    archived: "已归档",
  }
  return labels[status] || status
}

const parseList = (value: string) => {
  const items = value
    .split(/[\n,，]/)
    .map(item => item.trim())
    .filter(Boolean)
  return items.length > 0 ? items : null
}

const buildPayload = () => ({
  datasource_id: form.value.datasource_id,
  name: form.value.name,
  description: form.value.description || null,
  definition: form.value.definition,
  table_name: form.value.table_name || null,
  column_name: form.value.column_name || null,
  formula: form.value.formula || null,
  owner_name: form.value.owner_name || null,
  unit: form.value.unit || null,
  aggregation: form.value.aggregation || "sum",
  tags: parseList(form.value.tags_text),
  status: form.value.status || "published",
  dimensions: parseList(form.value.dimensions_text),
  is_active: form.value.is_active,
})

const openDialog = (metric?: Metric) => {
  if (metric) {
    editingId.value = metric.id
    form.value = {
      datasource_id: metric.datasource_id,
      name: metric.name || "",
      description: metric.description || "",
      definition: metric.definition || "",
      table_name: metric.table_name || "",
      column_name: metric.column_name || "",
      formula: metric.formula || "",
      owner_name: metric.owner_name || "",
      unit: metric.unit || "",
      aggregation: metric.aggregation || "sum",
      tags_text: (metric.tags || []).join(", "),
      status: metric.status || "published",
      dimensions_text: (metric.dimensions || []).join(", "),
      is_active: metric.is_active ?? 1,
    }
  } else {
    editingId.value = null
    form.value = emptyForm()
  }
  dialogVisible.value = true
}

const saveMetric = async () => {
  if (!form.value.datasource_id || !form.value.name || !form.value.definition) {
    ElMessage.warning("请填写必填项")
    return
  }
  saving.value = true
  try {
    const payload = buildPayload()
    if (editingId.value) {
      await axios.put(`/api/metrics/${editingId.value}`, payload)
    } else {
      await axios.post("/api/metrics", payload)
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

const generateFormula = async () => {
  if (!form.value.datasource_id || !form.value.name || !form.value.definition) {
    ElMessage.warning("请先选择数据源并填写指标名称、定义")
    return
  }
  generatingFormula.value = true
  try {
    const response = await axios.post("/api/metrics/generate-formula", buildPayload())
    form.value.formula = response.data.formula || ""
    ElMessage.success("已生成计算公式")
  } catch (error: any) {
    ElMessage.error(error.response?.data?.detail || "生成公式失败")
  } finally {
    generatingFormula.value = false
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
  datasourceStore.fetchDatasources()
  fetchMetrics()
})
</script>

<style scoped>
.metric-tag {
  margin-right: 4px;
  margin-bottom: 4px;
}

.inline-button {
  margin-top: 8px;
}
</style>
