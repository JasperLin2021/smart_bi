<template>
  <div class="page olap-page">
    <section class="olap-hero">
      <div>
        <p class="eyebrow">DATA PLATFORM</p>
        <h2>OLAP 数据平台</h2>
        <p class="hero-copy">统一承接数据集物化、刷新任务和高并发分析查询。</p>
      </div>
      <div class="hero-actions">
        <el-button :icon="Refresh" :loading="loadingStatus" @click="fetchStatus">刷新状态</el-button>
      </div>
    </section>

    <section class="status-grid">
      <div class="status-card">
        <span>引擎</span>
        <strong>{{ status.engine || "Apache Doris" }}</strong>
      </div>
      <div class="status-card">
        <span>启用状态</span>
        <strong>{{ status.enabled ? "已启用" : "未启用" }}</strong>
      </div>
      <div class="status-card">
        <span>连接健康</span>
        <strong>{{ status.healthy ? "正常" : "异常/未连接" }}</strong>
      </div>
      <div class="status-card">
        <span>已物化数据集</span>
        <strong>{{ materializedCount }}</strong>
      </div>
    </section>

    <el-alert
      v-if="status.message"
      :type="status.healthy ? 'success' : status.enabled ? 'warning' : 'info'"
      :title="status.message"
      show-icon
      :closable="false"
    />

    <el-card class="platform-card" shadow="never">
      <template #header>
        <div class="card-header-line">
          <div>
            <span class="card-header-title">数据集物化</span>
            <small>Doris 优先读取已就绪的数据集；未物化或异常时保留原直连路径。</small>
          </div>
          <el-button :icon="Refresh" :loading="loadingDatasets" @click="fetchDatasets">刷新列表</el-button>
        </div>
      </template>

      <el-table v-loading="loadingDatasets" :data="datasets" row-key="id" empty-text="暂无数据集">
        <el-table-column label="数据集" min-width="220">
          <template #default="{ row }">
            <div class="dataset-name-cell">
              <strong>{{ row.name }}</strong>
              <span>{{ row.description || "未填写描述" }}</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="Doris 状态" width="130">
          <template #default="{ row }">
            <el-tag :type="materializationTag(row.materialization_status)" effect="plain">
              {{ materializationText(row.materialization_status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="物化表" min-width="190" show-overflow-tooltip>
          <template #default="{ row }">{{ row.materialized_table_name || "-" }}</template>
        </el-table-column>
        <el-table-column label="刷新结果" width="150">
          <template #default="{ row }">
            <div class="refresh-cell">
              <span>{{ row.last_refresh_status === "success" ? "成功" : row.last_refresh_status === "error" ? "失败" : "未刷新" }}</span>
              <small v-if="row.last_refresh_row_count">{{ row.last_refresh_row_count }} 行</small>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="增量水位" min-width="180" show-overflow-tooltip>
          <template #default="{ row }">{{ row.incremental_watermark || "-" }}</template>
        </el-table-column>
        <el-table-column label="操作" width="250" fixed="right">
          <template #default="{ row }">
            <el-button
              text
              type="primary"
              :icon="Upload"
              :loading="Boolean(materializing[row.id])"
              :disabled="!status.enabled"
              @click="materializeDataset(row, 'full')"
            >
              全量物化
            </el-button>
            <el-button
              text
              type="primary"
              :icon="Refresh"
              :loading="Boolean(materializing[row.id])"
              :disabled="!status.enabled"
              @click="materializeDataset(row, 'incremental')"
            >
              增量
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from "vue"
import axios from "axios"
import { ElMessage } from "element-plus"
import { Refresh, Upload } from "@element-plus/icons-vue"

interface OlapStatus {
  enabled: boolean
  engine: string
  host: string
  query_port: number
  http_port: number
  database: string
  healthy: boolean
  message: string
}

interface DatasetItem {
  id: number
  name: string
  description: string | null
  materialization_status: string | null
  materialization_mode: string | null
  materialized_table_name: string | null
  incremental_key: string | null
  incremental_watermark: string | null
  last_refresh_status: string | null
  last_refresh_row_count: number
}

const defaultStatus: OlapStatus = {
  enabled: false,
  engine: "Apache Doris",
  host: "",
  query_port: 0,
  http_port: 0,
  database: "",
  healthy: false,
  message: "",
}

const status = ref<OlapStatus>({ ...defaultStatus })
const datasets = ref<DatasetItem[]>([])
const loadingStatus = ref(false)
const loadingDatasets = ref(false)
const materializing = ref<Record<number, boolean>>({})

const materializedCount = computed(() =>
  datasets.value.filter((dataset) => dataset.materialization_status === "ready").length
)

const materializationText = (value: string | null) => {
  if (value === "ready") return "已就绪"
  if (value === "running") return "运行中"
  if (value === "error") return "失败"
  return "未物化"
}

const materializationTag = (value: string | null) => {
  if (value === "ready") return "success"
  if (value === "running") return "warning"
  if (value === "error") return "danger"
  return "info"
}

const fetchStatus = async () => {
  loadingStatus.value = true
  try {
    const response = await axios.get("/api/olap/status")
    status.value = response.data
  } catch (error: any) {
    ElMessage.error(error.response?.data?.detail || "Doris 状态加载失败")
  } finally {
    loadingStatus.value = false
  }
}

const fetchDatasets = async () => {
  loadingDatasets.value = true
  try {
    const response = await axios.get("/api/datasets")
    datasets.value = response.data.items || []
  } catch (error: any) {
    ElMessage.error(error.response?.data?.detail || "数据集加载失败")
  } finally {
    loadingDatasets.value = false
  }
}

const materializeDataset = async (dataset: DatasetItem, mode: "full" | "incremental") => {
  materializing.value = { ...materializing.value, [dataset.id]: true }
  try {
    await axios.post(`/api/datasets/${dataset.id}/materialize`, {
      mode,
      incremental_key: dataset.incremental_key || undefined,
    })
    ElMessage.success(mode === "full" ? "全量物化已完成" : "增量物化已完成")
    await fetchDatasets()
  } catch (error: any) {
    ElMessage.error(error.response?.data?.detail || "数据集物化失败")
  } finally {
    materializing.value = { ...materializing.value, [dataset.id]: false }
  }
}

onMounted(async () => {
  await Promise.all([fetchStatus(), fetchDatasets()])
})
</script>

<style scoped>
.olap-page {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.olap-hero {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 16px;
}

.hero-copy {
  margin: 6px 0 0;
  color: #64748b;
}

.hero-actions {
  display: flex;
  gap: 10px;
}

.status-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
}

.status-card {
  border: 1px solid #dbe3ef;
  border-radius: 8px;
  background: #fff;
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.status-card span,
.dataset-name-cell span,
.card-header-line small,
.refresh-cell small {
  color: #64748b;
  font-size: 12px;
}

.status-card strong {
  color: #0f172a;
  font-size: 22px;
}

.platform-card {
  border-radius: 8px;
}

.card-header-line {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.card-header-title {
  display: block;
  font-weight: 700;
  color: #0f172a;
}

.dataset-name-cell,
.refresh-cell {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

@media (max-width: 900px) {
  .olap-hero,
  .card-header-line {
    align-items: stretch;
    flex-direction: column;
  }

  .status-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 560px) {
  .status-grid {
    grid-template-columns: 1fr;
  }
}
</style>
