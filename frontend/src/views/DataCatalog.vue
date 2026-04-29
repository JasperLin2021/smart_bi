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
        <el-option label="看板" value="dashboard" />
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
        <el-button
          v-if="selectedAsset.asset_type === 'dashboard' && selectedAsset.asset_id"
          type="primary"
          @click="openDashboard(selectedAsset.asset_id)"
        >
          打开看板
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
  const labels: Record<string, string> = { metric: "指标", table: "数据表", dashboard: "看板" }
  return labels[type] || type
}

const statusLabel = (value: string) => {
  const labels: Record<string, string> = { draft: "草稿", published: "已发布", archived: "已归档" }
  return labels[value] || value
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
</style>
