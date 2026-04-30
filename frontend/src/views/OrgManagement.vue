<template>
  <div class="page org-page">
    <div class="org-hero">
      <div>
        <p class="eyebrow">Tenant Operations</p>
        <h1>企业与套餐</h1>
        <p>统一管理企业隔离、套餐配额和白标品牌，避免资源失控。</p>
      </div>
      <div class="hero-actions">
        <el-button :icon="Refresh" @click="fetchOrgs">刷新</el-button>
        <el-button type="primary" :icon="Plus" @click="openCreate">新增企业</el-button>
      </div>
    </div>

    <div class="stats-row">
      <div class="stat-card">
        <div class="stat-icon org-icon">
          <el-icon :size="22"><OfficeBuilding /></el-icon>
        </div>
        <div>
          <div class="stat-value">{{ organizations.length }}</div>
          <div class="stat-label">企业总数</div>
        </div>
      </div>
      <div class="stat-card">
        <div class="stat-icon plan-icon">
          <el-icon :size="22"><TrendCharts /></el-icon>
        </div>
        <div>
          <div class="stat-value">{{ enterpriseCount }}</div>
          <div class="stat-label">企业版套餐</div>
        </div>
      </div>
      <div class="stat-card">
        <div class="stat-icon brand-icon">
          <el-icon :size="22"><Brush /></el-icon>
        </div>
        <div>
          <div class="stat-value">{{ whiteLabelCount }}</div>
          <div class="stat-label">已开启白标</div>
        </div>
      </div>
    </div>

    <el-card class="table-card">
      <template #header>
        <div class="card-header">
          <div>
            <span class="card-header-title">企业列表</span>
            <small>套餐、资源用量和品牌配置集中在这里维护</small>
          </div>
          <el-tag effect="plain" size="small">{{ organizations.length }} 个企业</el-tag>
        </div>
      </template>

      <el-table :data="organizations" stripe row-key="id" v-loading="loading">
        <el-table-column prop="name" label="企业" min-width="220">
          <template #default="{ row }">
            <div class="org-cell">
              <div class="org-avatar" :style="{ background: brandColor(row) }">{{ row.name?.charAt(0) || '企' }}</div>
              <div>
                <div class="org-name">{{ row.name }}</div>
                <div class="org-slug">{{ row.slug }}</div>
              </div>
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="plan_type" label="套餐" width="130">
          <template #default="{ row }">
            <el-tag :type="planTagType(row.plan_type)" effect="light">{{ planLabel(row.plan_type) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="资源用量" min-width="360">
          <template #default="{ row }">
            <div class="usage-grid">
              <div v-for="item in usageItems(row)" :key="item.key" class="usage-item">
                <div class="usage-top">
                  <span>{{ item.label }}</span>
                  <strong>{{ item.used }} / {{ item.limit }}</strong>
                </div>
                <el-progress
                  :percentage="item.percent"
                  :show-text="false"
                  :status="item.percent >= 90 ? 'exception' : item.percent >= 70 ? 'warning' : undefined"
                />
              </div>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="白标" width="130">
          <template #default="{ row }">
            <el-tag :type="row.white_label_enabled ? 'success' : 'info'" effect="plain">
              {{ row.white_label_enabled ? '已开启' : '未开启' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" width="170">
          <template #default="{ row }">
            <span class="date-text">
              <el-icon><Calendar /></el-icon>
              {{ formatDate(row.created_at) }}
            </span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="150" fixed="right">
          <template #default="{ row }">
            <el-button size="small" type="primary" text @click="openEdit(row)">
              <el-icon><Edit /></el-icon> 编辑
            </el-button>
            <el-button size="small" type="danger" text @click="handleDelete(row.id)">
              <el-icon><Delete /></el-icon>
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog
      v-model="dialogVisible"
      :title="isEdit ? '编辑企业' : '新增企业'"
      width="min(760px, calc(100vw - 32px))"
      destroy-on-close
      class="org-dialog"
    >
      <el-form :model="form" label-position="top" class="org-form">
        <section class="form-section">
          <div class="section-title">基础信息</div>
          <el-row :gutter="14">
            <el-col :xs="24" :md="12">
              <el-form-item label="企业名称" required>
                <el-input v-model="form.name" placeholder="如：嘉盛半导体" />
              </el-form-item>
            </el-col>
            <el-col :xs="24" :md="12">
              <el-form-item label="企业标识" required>
                <el-input v-model="form.slug" placeholder="carsem" />
              </el-form-item>
            </el-col>
          </el-row>
        </section>

        <section class="form-section">
          <div class="section-title">套餐限制</div>
          <el-form-item label="套餐类型">
            <el-segmented v-model="form.plan_type" :options="planOptions" />
          </el-form-item>
          <div class="limit-grid">
            <el-form-item label="用户数">
              <el-input-number v-model="form.user_limit" :min="0" controls-position="right" placeholder="默认" />
            </el-form-item>
            <el-form-item label="数据源">
              <el-input-number v-model="form.datasource_limit" :min="0" controls-position="right" placeholder="默认" />
            </el-form-item>
            <el-form-item label="看板">
              <el-input-number v-model="form.dashboard_limit" :min="0" controls-position="right" placeholder="默认" />
            </el-form-item>
            <el-form-item label="大屏">
              <el-input-number v-model="form.big_screen_limit" :min="0" controls-position="right" placeholder="默认" />
            </el-form-item>
            <el-form-item label="月度问数">
              <el-input-number v-model="form.monthly_query_limit" :min="0" controls-position="right" placeholder="默认" />
            </el-form-item>
          </div>
        </section>

        <section class="form-section">
          <div class="section-title">品牌白标</div>
          <div class="brand-row">
            <el-switch v-model="whiteLabelEnabled" active-text="开启白标" inactive-text="关闭" />
          </div>
          <el-row :gutter="14">
            <el-col :xs="24" :md="8">
              <el-form-item label="品牌名">
                <el-input v-model="form.branding_json.brand_name" placeholder="Smart BI" />
              </el-form-item>
            </el-col>
            <el-col :xs="24" :md="8">
              <el-form-item label="主色">
                <el-color-picker v-model="form.branding_json.primary_color" />
              </el-form-item>
            </el-col>
            <el-col :xs="24" :md="8">
              <el-form-item label="Logo URL">
                <el-input v-model="form.branding_json.logo_url" placeholder="https://..." />
              </el-form-item>
            </el-col>
          </el-row>
        </section>
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
import { Brush, Calendar, Delete, Edit, OfficeBuilding, Plus, Refresh, TrendCharts } from "@element-plus/icons-vue"

type PlanType = "free" | "team" | "enterprise"

interface OrgItem {
  id: number
  name: string
  slug: string
  plan_type: PlanType
  user_limit: number | null
  datasource_limit: number | null
  dashboard_limit: number | null
  big_screen_limit: number | null
  monthly_query_limit: number | null
  white_label_enabled: number
  branding_json: {
    brand_name?: string
    logo_url?: string
    primary_color?: string
  } | null
  created_at: string
}

interface OrgUsage {
  usage: Record<string, number>
  limits: Record<string, number | null>
  usage_rate: Record<string, number>
}

const organizations = ref<OrgItem[]>([])
const usages = ref<Record<number, OrgUsage>>({})
const loading = ref(false)
const dialogVisible = ref(false)
const isEdit = ref(false)
const editId = ref<number | null>(null)
const saving = ref(false)

const planOptions = [
  { label: "免费版", value: "free" },
  { label: "团队版", value: "team" },
  { label: "企业版", value: "enterprise" },
]

const defaultBranding = () => ({
  brand_name: "",
  logo_url: "",
  primary_color: "#0f766e",
})

const form = reactive({
  name: "",
  slug: "",
  plan_type: "team" as PlanType,
  user_limit: null as number | null,
  datasource_limit: null as number | null,
  dashboard_limit: null as number | null,
  big_screen_limit: null as number | null,
  monthly_query_limit: null as number | null,
  white_label_enabled: 0,
  branding_json: defaultBranding(),
})

const whiteLabelEnabled = computed({
  get: () => Boolean(form.white_label_enabled),
  set: (value: boolean) => {
    form.white_label_enabled = value ? 1 : 0
  },
})

const enterpriseCount = computed(() => organizations.value.filter(item => item.plan_type === "enterprise").length)
const whiteLabelCount = computed(() => organizations.value.filter(item => item.white_label_enabled).length)

const formatDate = (dateStr: string) => new Date(dateStr).toLocaleString("zh-CN", {
  year: "numeric",
  month: "2-digit",
  day: "2-digit",
  hour: "2-digit",
  minute: "2-digit",
})

const planLabel = (plan: string) => {
  const labels: Record<string, string> = {
    free: "免费版",
    team: "团队版",
    enterprise: "企业版",
  }
  return labels[plan] || plan
}

const planTagType = (plan: string) => {
  const types: Record<string, "info" | "success" | "warning"> = {
    free: "info",
    team: "success",
    enterprise: "warning",
  }
  return types[plan] || "info"
}

const brandColor = (row: OrgItem) => row.branding_json?.primary_color || "#0f766e"

const displayLimit = (limit: number | null | undefined) => limit === null || limit === undefined ? "不限" : String(limit)

const usageItems = (row: OrgItem) => {
  const usage = usages.value[row.id]
  const fallbackLimits = {
    users: row.user_limit,
    datasources: row.datasource_limit,
    dashboards: row.dashboard_limit,
    big_screens: row.big_screen_limit,
  }
  return [
    { key: "users", label: "用户" },
    { key: "datasources", label: "数据源" },
    { key: "dashboards", label: "看板" },
    { key: "big_screens", label: "大屏" },
  ].map(item => ({
    ...item,
    used: usage?.usage[item.key] ?? 0,
    limit: displayLimit(usage?.limits[item.key] ?? fallbackLimits[item.key as keyof typeof fallbackLimits]),
    percent: usage?.usage_rate[item.key] ?? 0,
  }))
}

const fetchUsage = async (orgs: OrgItem[]) => {
  const entries = await Promise.all(orgs.map(async org => {
    try {
      const res = await axios.get(`/api/organizations/${org.id}/usage`)
      return [org.id, res.data] as const
    } catch {
      return [org.id, null] as const
    }
  }))
  usages.value = Object.fromEntries(entries.filter((entry): entry is readonly [number, OrgUsage] => Boolean(entry[1])))
}

const fetchOrgs = async () => {
  loading.value = true
  try {
    const res = await axios.get("/api/organizations")
    organizations.value = res.data
    await fetchUsage(organizations.value)
  } finally {
    loading.value = false
  }
}

const resetForm = () => {
  Object.assign(form, {
    name: "",
    slug: "",
    plan_type: "team",
    user_limit: null,
    datasource_limit: null,
    dashboard_limit: null,
    big_screen_limit: null,
    monthly_query_limit: null,
    white_label_enabled: 0,
    branding_json: defaultBranding(),
  })
}

const openCreate = () => {
  isEdit.value = false
  editId.value = null
  resetForm()
  dialogVisible.value = true
}

const openEdit = (row: OrgItem) => {
  isEdit.value = true
  editId.value = row.id
  Object.assign(form, {
    name: row.name,
    slug: row.slug,
    plan_type: row.plan_type || "team",
    user_limit: row.user_limit,
    datasource_limit: row.datasource_limit,
    dashboard_limit: row.dashboard_limit,
    big_screen_limit: row.big_screen_limit,
    monthly_query_limit: row.monthly_query_limit,
    white_label_enabled: row.white_label_enabled ? 1 : 0,
    branding_json: {
      ...defaultBranding(),
      ...(row.branding_json || {}),
    },
  })
  dialogVisible.value = true
}

const buildPayload = () => ({
  name: form.name.trim(),
  slug: form.slug.trim(),
  plan_type: form.plan_type,
  user_limit: form.user_limit,
  datasource_limit: form.datasource_limit,
  dashboard_limit: form.dashboard_limit,
  big_screen_limit: form.big_screen_limit,
  monthly_query_limit: form.monthly_query_limit,
  white_label_enabled: form.white_label_enabled,
  branding_json: {
    brand_name: form.branding_json.brand_name?.trim() || null,
    logo_url: form.branding_json.logo_url?.trim() || null,
    primary_color: form.branding_json.primary_color || "#0f766e",
  },
})

const handleSave = async () => {
  if (!form.name.trim() || !form.slug.trim()) {
    ElMessage.warning("请填写企业名称和标识")
    return
  }
  saving.value = true
  try {
    const payload = buildPayload()
    if (isEdit.value && editId.value) {
      await axios.put(`/api/organizations/${editId.value}`, payload)
      ElMessage.success("企业已更新")
    } else {
      await axios.post("/api/organizations", payload)
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
    await ElMessageBox.confirm("确定要删除此企业？删除后该企业下的用户将无法登录。", "提示", { type: "warning" })
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
.org-page {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.org-hero {
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
  gap: 20px;
  padding: 22px 24px;
  border: 1px solid var(--app-border);
  border-radius: var(--app-radius);
  background: var(--app-surface);
  box-shadow: var(--app-shadow-soft);
}

.eyebrow {
  margin: 0 0 6px;
  color: var(--app-primary);
  font-size: 12px;
  font-weight: 700;
  text-transform: uppercase;
}

.org-hero h1 {
  margin: 0;
  font-size: 24px;
  color: var(--app-text);
}

.org-hero p:last-child {
  margin: 8px 0 0;
  color: var(--app-text-muted);
  font-size: 14px;
}

.hero-actions {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}

.stats-row {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 16px;
}

.stat-card {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 18px;
  background: var(--app-surface);
  border: 1px solid var(--app-border);
  border-radius: var(--app-radius);
  box-shadow: var(--app-shadow-soft);
}

.stat-icon {
  width: 44px;
  height: 44px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
}

.org-icon { background: #0f766e; }
.plan-icon { background: #1d4ed8; }
.brand-icon { background: #7c3aed; }

.stat-value {
  font-size: 24px;
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
  gap: 12px;
}

.card-header-title {
  display: block;
  font-weight: 700;
  font-size: 16px;
  color: var(--app-text);
}

.card-header small {
  display: block;
  color: var(--app-text-muted);
  margin-top: 4px;
}

.org-cell {
  display: flex;
  align-items: center;
  gap: 10px;
}

.org-avatar {
  width: 38px;
  height: 38px;
  border-radius: 8px;
  color: white;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 700;
  font-size: 16px;
}

.org-name {
  font-weight: 600;
  color: var(--app-text);
}

.org-slug {
  margin-top: 2px;
  color: var(--app-text-muted);
  font-size: 12px;
}

.usage-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(130px, 1fr));
  gap: 10px 14px;
}

.usage-item {
  min-width: 0;
}

.usage-top {
  display: flex;
  justify-content: space-between;
  gap: 10px;
  margin-bottom: 5px;
  color: var(--app-text-muted);
  font-size: 12px;
}

.usage-top strong {
  color: var(--app-text);
  font-weight: 600;
}

.date-text {
  display: flex;
  align-items: center;
  gap: 6px;
  color: var(--app-text-muted);
  font-size: 13px;
}

.org-form {
  display: flex;
  flex-direction: column;
  gap: 16px;
  max-height: min(68vh, 680px);
  overflow-y: auto;
  padding-right: 4px;
}

.form-section {
  padding: 14px 16px 4px;
  border: 1px solid var(--app-border);
  border-radius: 10px;
  background: var(--app-surface);
}

.section-title {
  margin-bottom: 12px;
  font-size: 14px;
  font-weight: 700;
  color: var(--app-text);
}

.limit-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  gap: 0 14px;
}

.limit-grid :deep(.el-input-number) {
  width: 100%;
}

.brand-row {
  margin-bottom: 12px;
}

@media (max-width: 720px) {
  .org-hero {
    align-items: flex-start;
    flex-direction: column;
  }

  .usage-grid {
    grid-template-columns: 1fr;
  }
}
</style>
