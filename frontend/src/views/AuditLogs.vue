<template>
  <div class="page audit-page">
    <el-card>
      <template #header>
        <div class="card-header">
          <div>
            <span class="card-header-title">审计日志</span>
            <p class="card-header-subtitle">数据源、问数、看板和用户权限操作记录</p>
          </div>
          <el-button :icon="Refresh" :loading="loading" @click="fetchLogs">刷新</el-button>
        </div>
      </template>

      <div class="filter-bar">
        <el-select v-model="filters.action" clearable placeholder="操作类型" @change="handleFilterChange">
          <el-option v-for="item in actionOptions" :key="item.value" :label="item.label" :value="item.value" />
        </el-select>
        <el-select v-model="filters.resource_type" clearable placeholder="资源类型" @change="handleFilterChange">
          <el-option label="数据源" value="datasource" />
          <el-option label="智能问数" value="query" />
          <el-option label="看板" value="dashboard" />
          <el-option label="用户" value="user" />
        </el-select>
        <el-select v-model="filters.status" clearable placeholder="状态" @change="handleFilterChange">
          <el-option label="成功" value="success" />
          <el-option label="失败" value="error" />
        </el-select>
      </div>

      <el-table v-loading="loading" :data="logs" stripe>
        <el-table-column label="时间" width="170">
          <template #default="{ row }">{{ formatDate(row.created_at) }}</template>
        </el-table-column>
        <el-table-column prop="actor_username" label="操作者" width="120" />
        <el-table-column label="角色" width="110">
          <template #default="{ row }">
            <el-tag size="small" effect="plain">{{ roleLabel(row.actor_role) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" min-width="170">
          <template #default="{ row }">
            <span class="action-name">{{ actionLabel(row.action) }}</span>
            <span class="action-code">{{ row.action }}</span>
          </template>
        </el-table-column>
        <el-table-column label="资源" min-width="180" show-overflow-tooltip>
          <template #default="{ row }">
            {{ resourceLabel(row.resource_type) }} / {{ row.resource_name || row.resource_id || "-" }}
          </template>
        </el-table-column>
        <el-table-column label="状态" width="90">
          <template #default="{ row }">
            <el-tag :type="row.status === 'error' ? 'danger' : 'success'" size="small" effect="plain">
              {{ row.status === "error" ? "失败" : "成功" }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="message" label="说明" min-width="180" show-overflow-tooltip />
        <el-table-column label="详情" min-width="220" show-overflow-tooltip>
          <template #default="{ row }">{{ detailText(row.detail) }}</template>
        </el-table-column>
      </el-table>

      <div class="pagination-row">
        <span>共 {{ total }} 条</span>
        <el-pagination
          background
          layout="prev, pager, next"
          :total="total"
          :page-size="filters.page_size"
          v-model:current-page="filters.page"
          @current-change="fetchLogs"
        />
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from "vue"
import axios from "axios"
import { ElMessage } from "element-plus"
import { Refresh } from "@element-plus/icons-vue"

interface AuditLogItem {
  id: number
  actor_user_id?: number | null
  actor_username?: string | null
  actor_role?: string | null
  org_id?: number | null
  action: string
  resource_type: string
  resource_id?: string | null
  resource_name?: string | null
  status: string
  message?: string | null
  detail?: unknown
  created_at?: string | null
}

const logs = ref<AuditLogItem[]>([])
const total = ref(0)
const loading = ref(false)

const filters = reactive({
  action: "",
  resource_type: "",
  status: "",
  page: 1,
  page_size: 50,
})

const actionOptions = [
  { label: "数据源创建", value: "datasource.create" },
  { label: "数据源更新", value: "datasource.update" },
  { label: "数据源删除", value: "datasource.delete" },
  { label: "连接测试", value: "datasource.test" },
  { label: "表结构检测", value: "datasource.detect_schema" },
  { label: "生成元数据", value: "datasource.generate_prompt" },
  { label: "生成字段说明", value: "datasource.generate_column_descriptions" },
  { label: "生成钻取规则", value: "datasource.generate_drill_config" },
  { label: "智能问数", value: "query.ask" },
  { label: "看板创建", value: "dashboard.create" },
  { label: "看板更新", value: "dashboard.update" },
  { label: "看板发布", value: "dashboard.publish" },
  { label: "看板删除", value: "dashboard.delete" },
  { label: "用户创建", value: "user.create" },
  { label: "用户更新", value: "user.update" },
  { label: "用户删除", value: "user.delete" },
]

const actionLabel = (value: string) => actionOptions.find(item => item.value === value)?.label || value

const resourceLabel = (value: string) => {
  const labels: Record<string, string> = {
    datasource: "数据源",
    query: "智能问数",
    dashboard: "看板",
    user: "用户",
  }
  return labels[value] || value
}

const roleLabel = (value?: string | null) => {
  const labels: Record<string, string> = {
    super_admin: "超级管理员",
    org_admin: "企业管理员",
    user: "普通用户",
  }
  return labels[value || ""] || value || "-"
}

const detailText = (detail: unknown) => {
  if (!detail) return "-"
  if (typeof detail === "string") return detail
  return JSON.stringify(detail)
}

const formatDate = (value?: string | null) => {
  if (!value) return "-"
  return new Date(value).toLocaleString("zh-CN", { hour12: false })
}

const fetchLogs = async () => {
  loading.value = true
  try {
    const params: Record<string, string | number> = {
      page: filters.page,
      page_size: filters.page_size,
    }
    if (filters.action) params.action = filters.action
    if (filters.resource_type) params.resource_type = filters.resource_type
    if (filters.status) params.status = filters.status

    const response = await axios.get("/api/audit-logs", { params })
    logs.value = response.data.items
    total.value = response.data.total
  } catch (error: any) {
    ElMessage.error(error.response?.data?.detail || "审计日志加载失败")
  } finally {
    loading.value = false
  }
}

const handleFilterChange = () => {
  filters.page = 1
  fetchLogs()
}

onMounted(fetchLogs)
</script>

<style scoped>
.audit-page {
  gap: 16px;
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.card-header-title {
  display: block;
  font-size: 16px;
  font-weight: 600;
  color: var(--app-text);
}

.card-header-subtitle {
  margin: 4px 0 0;
  color: var(--app-text-muted);
  font-size: 13px;
}

.filter-bar {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
  margin-bottom: 14px;
}

.filter-bar .el-select {
  width: 180px;
}

.action-name {
  display: block;
  color: var(--app-text);
  font-weight: 600;
}

.action-code {
  display: block;
  margin-top: 2px;
  color: var(--app-text-muted);
  font-size: 12px;
}

.pagination-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding-top: 14px;
  color: var(--app-text-muted);
  font-size: 13px;
}
</style>
