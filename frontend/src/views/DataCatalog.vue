<template>
  <div class="catalog-page">
    <div class="toolbar">
      <el-input
        v-model="keyword"
        class="search-input"
        placeholder="搜索资产名称"
        clearable
        :prefix-icon="Search"
        @keyup.enter="fetchAssets"
        @clear="fetchAssets"
      />
      <el-select v-model="assetType" class="filter-select" placeholder="资产类型" clearable @change="fetchAssets">
        <el-option label="指标" value="metric" />
        <el-option label="数据表" value="table" />
        <el-option label="数据集" value="dataset" />
        <el-option label="看板" value="dashboard" />
        <el-option label="大屏" value="big_screen" />
      </el-select>
      <el-select v-model="status" class="filter-select" placeholder="状态" clearable @change="fetchAssets">
        <el-option label="已发布" value="published" />
        <el-option label="草稿" value="draft" />
        <el-option label="已归档" value="archived" />
      </el-select>
      <el-button type="primary" :icon="Search" @click="fetchAssets" :loading="loading">查询</el-button>
    </div>

    <el-table v-loading="loading" :data="assets" class="asset-table">
      <el-table-column prop="name" label="资产名称" min-width="180" />
      <el-table-column label="类型" width="110">
        <template #default="{ row }">
          <el-tag effect="plain">{{ assetTypeLabel(row.asset_type) }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="可信指标" width="190">
        <template #default="{ row }">
          <div v-if="row.asset_type === 'metric'" class="trust-cell">
            <el-tag :type="certificationTagType(row.metadata_json?.certification_status)" effect="plain">
              {{ certificationLabel(row.metadata_json?.certification_status) }}
            </el-tag>
            <el-tag :type="qualityTagType(row.metadata_json?.quality_status)" effect="plain">
              {{ qualityLabel(row.metadata_json?.quality_status) }}
            </el-tag>
          </div>
          <span v-else class="muted">-</span>
        </template>
      </el-table-column>
      <el-table-column prop="description" label="描述" min-width="220" show-overflow-tooltip />
      <el-table-column label="状态" width="100">
        <template #default="{ row }">
          <el-tag :type="row.status === 'published' ? 'success' : 'info'" effect="plain">
            {{ statusLabel(row.status) }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="标签" min-width="160">
        <template #default="{ row }">
          <el-space wrap>
            <el-tag v-for="tag in row.tags || []" :key="tag" size="small" effect="plain">{{ tag }}</el-tag>
          </el-space>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="130" fixed="right">
        <template #default="{ row }">
          <el-button text type="primary" @click="showDetail(row)">详情</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-drawer v-model="detailVisible" title="资产详情" size="420px">
      <template v-if="selectedAsset">
        <dl class="detail-list">
          <dt>名称</dt>
          <dd>{{ selectedAsset.name }}</dd>
          <dt>类型</dt>
          <dd>{{ assetTypeLabel(selectedAsset.asset_type) }}</dd>
          <dt>状态</dt>
          <dd>{{ statusLabel(selectedAsset.status) }}</dd>
          <dt>描述</dt>
          <dd>{{ selectedAsset.description || "-" }}</dd>
        </dl>
        <section v-if="selectedAsset.asset_type === 'metric'" class="trust-detail">
          <div class="trust-detail-head">
            <strong>可信指标说明</strong>
            <div class="trust-cell">
              <el-tag :type="certificationTagType(selectedAsset.metadata_json?.certification_status)" effect="plain">
                {{ certificationLabel(selectedAsset.metadata_json?.certification_status) }}
              </el-tag>
              <el-tag :type="qualityTagType(selectedAsset.metadata_json?.quality_status)" effect="plain">
                {{ qualityLabel(selectedAsset.metadata_json?.quality_status) }}
              </el-tag>
            </div>
          </div>
          <dl class="detail-list trust-list">
            <dt>负责人</dt>
            <dd>{{ selectedAsset.metadata_json?.owner_name || "-" }}</dd>
            <dt>口径版本</dt>
            <dd>{{ selectedAsset.metadata_json?.caliber_version || "v1" }}</dd>
            <dt>认证人</dt>
            <dd>{{ selectedAsset.metadata_json?.certified_by || "-" }}</dd>
            <dt>数据更新</dt>
            <dd>{{ formatDate(selectedAsset.metadata_json?.data_updated_at) }}</dd>
            <dt>计算公式</dt>
            <dd>{{ selectedAsset.metadata_json?.formula || "-" }}</dd>
            <dt>质量说明</dt>
            <dd>{{ selectedAsset.metadata_json?.quality_message || "-" }}</dd>
          </dl>
        </section>
        <el-button
          v-if="selectedAsset.asset_type === 'dashboard' && selectedAsset.asset_id"
          type="primary"
          @click="openDashboard(selectedAsset.asset_id)"
        >
          打开看板
        </el-button>
        <el-button
          v-if="selectedAsset.asset_type === 'dataset' && selectedAsset.asset_id"
          type="primary"
          @click="openDataset"
        >
          打开数据集
        </el-button>
        <el-button
          v-if="selectedAsset.asset_type === 'big_screen' && selectedAsset.asset_id"
          type="primary"
          @click="openBigScreen"
        >
          打开大屏
        </el-button>
      </template>
    </el-drawer>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from "vue"
import { useRouter } from "vue-router"
import axios from "axios"
import { ElMessage } from "element-plus"
import { Search } from "@element-plus/icons-vue"

interface DataAsset {
  id: number
  asset_type: string
  asset_id: number | null
  name: string
  description: string | null
  status: string
  tags: string[] | null
  metadata_json: Record<string, any> | null
}

const router = useRouter()
const assets = ref<DataAsset[]>([])
const loading = ref(false)
const keyword = ref("")
const assetType = ref("")
const status = ref("")
const detailVisible = ref(false)
const selectedAsset = ref<DataAsset | null>(null)

const assetTypeLabel = (type: string) => {
  const labels: Record<string, string> = {
    metric: "指标",
    table: "数据表",
    dataset: "数据集",
    dashboard: "看板",
    big_screen: "大屏",
  }
  return labels[type] || type
}

const statusLabel = (value: string) => {
  const labels: Record<string, string> = { draft: "草稿", published: "已发布", archived: "已归档" }
  return labels[value] || value
}

const certificationLabel = (status?: string) => {
  const labels: Record<string, string> = {
    draft: "草稿",
    pending_review: "待审核",
    certified: "已认证",
    deprecated: "已废弃",
  }
  return labels[status || ""] || "未认证"
}

const certificationTagType = (status?: string) => {
  const types: Record<string, "success" | "warning" | "info" | "danger"> = {
    draft: "info",
    pending_review: "warning",
    certified: "success",
    deprecated: "danger",
  }
  return types[status || ""] || "info"
}

const qualityLabel = (status?: string) => {
  const labels: Record<string, string> = {
    unknown: "未知",
    normal: "正常",
    stale: "过期",
    error: "异常",
  }
  return labels[status || ""] || "未知"
}

const qualityTagType = (status?: string) => {
  const types: Record<string, "success" | "warning" | "info" | "danger"> = {
    unknown: "info",
    normal: "success",
    stale: "warning",
    error: "danger",
  }
  return types[status || ""] || "info"
}

const formatDate = (value?: string) => {
  if (!value) return "-"
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleString("zh-CN", { hour12: false })
}

const fetchAssets = async () => {
  loading.value = true
  try {
    const response = await axios.get("/api/catalog/assets", {
      params: {
        q: keyword.value || undefined,
        asset_type: assetType.value || undefined,
        status: status.value || undefined,
      },
    })
    assets.value = response.data.items
  } catch (error) {
    ElMessage.error("数据目录加载失败")
  } finally {
    loading.value = false
  }
}

const showDetail = (asset: DataAsset) => {
  selectedAsset.value = asset
  detailVisible.value = true
}

const openDashboard = (id: number) => {
  router.push({ path: "/dashboard-center", query: { dashboard_id: id } })
}

const openDataset = () => {
  router.push("/dataset-center")
}

const openBigScreen = () => {
  router.push("/big-screen-center")
}

onMounted(fetchAssets)
</script>

<style scoped>
.catalog-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.toolbar {
  display: flex;
  gap: 12px;
  align-items: center;
  flex-wrap: wrap;
}

.search-input {
  max-width: 320px;
}

.filter-select {
  width: 150px;
}

.asset-table {
  width: 100%;
}

.detail-list {
  display: grid;
  grid-template-columns: 80px 1fr;
  gap: 12px 16px;
  margin: 0 0 24px;
}

.detail-list dt {
  color: var(--app-text-muted);
}

.detail-list dd {
  margin: 0;
  color: var(--app-text);
}

.trust-cell {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.muted {
  color: var(--app-text-muted);
}

.trust-detail {
  margin: 0 0 20px;
  padding: 14px;
  border: 1px solid var(--app-border);
  border-radius: 8px;
  background: var(--app-bg-soft);
}

.trust-detail-head {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: center;
  margin-bottom: 14px;
}

.trust-detail-head strong {
  color: var(--app-text);
}

.trust-list {
  margin-bottom: 0;
}
</style>
