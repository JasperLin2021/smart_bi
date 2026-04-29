<template>
  <el-container class="app-shell">
    <el-aside width="260px" class="app-sidebar">
      <!-- Brand -->
      <div class="sidebar-brand">
        <div class="brand-logo">
          <svg viewBox="0 0 32 32" fill="none" xmlns="http://www.w3.org/2000/svg">
            <rect width="32" height="32" rx="8" fill="url(#brand-gradient)"/>
            <path d="M9 24V8h3v16H9zm5-6V8h3v10h-3zm5 3V8h3v13h-3z" fill="white"/>
            <defs>
              <linearGradient id="brand-gradient" x1="0" y1="0" x2="32" y2="32">
                <stop stop-color="#6366f1"/>
                <stop offset="1" stop-color="#8b5cf6"/>
              </linearGradient>
            </defs>
          </svg>
        </div>
        <span class="brand-text">Smart BI</span>
      </div>

      <!-- Datasource Selector -->
      <div class="datasource-selector" v-if="datasourceStore.datasources.length > 0">
        <label class="selector-label">当前数据源</label>
        <el-select
          v-model="selectedDatasource"
          size="default"
          placeholder="选择数据源"
          @change="onDatasourceChange"
        >
          <el-option
            v-for="ds in datasourceStore.datasources"
            :key="ds.id"
            :label="ds.name"
            :value="ds.id"
          >
            <div class="ds-option">
              <span class="ds-icon">{{ ds.source_type === 'excel' ? '📊' : '🗄️' }}</span>
              <span>{{ ds.name }}</span>
            </div>
          </el-option>
        </el-select>
      </div>

      <!-- Navigation Menu -->
      <nav class="sidebar-nav">
        <div class="nav-section">
          <div class="nav-section-title">主要功能</div>
          <el-menu :default-active="activePath" router class="app-menu">
            <el-menu-item index="/dashboard">
              <el-icon><DataLine /></el-icon>
              <span>Dashboard</span>
            </el-menu-item>
            <el-menu-item index="/dashboard-center">
              <el-icon><Grid /></el-icon>
              <span>看板中心</span>
            </el-menu-item>
            <el-menu-item index="/data-catalog">
              <el-icon><FolderOpened /></el-icon>
              <span>数据目录</span>
            </el-menu-item>
            <el-menu-item index="/smart-query">
              <el-icon><ChatDotRound /></el-icon>
              <span>智能问数</span>
            </el-menu-item>
          </el-menu>
        </div>

        <div class="nav-section">
          <div class="nav-section-title">配置管理</div>
          <el-menu :default-active="activePath" router class="app-menu">
            <el-menu-item index="/datasource-settings">
              <el-icon><Coin /></el-icon>
              <span>数据源管理</span>
            </el-menu-item>
            <el-menu-item v-if="isOrgAdmin" index="/user-management">
              <el-icon><User /></el-icon>
              <span>用户管理</span>
            </el-menu-item>
            <el-menu-item v-if="isSuperAdmin" index="/org-management">
              <el-icon><OfficeBuilding /></el-icon>
              <span>企业管理</span>
            </el-menu-item>
            <el-menu-item index="/metric-settings">
              <el-icon><TrendCharts /></el-icon>
              <span>指标配置</span>
            </el-menu-item>
            <el-menu-item index="/alert-settings">
              <el-icon><Bell /></el-icon>
              <span>预警管理</span>
            </el-menu-item>
            <el-menu-item index="/scheduled-reports">
              <el-icon><AlarmClock /></el-icon>
              <span>定时报告</span>
            </el-menu-item>
            <el-menu-item v-if="isSuperAdmin" index="/llm-settings">
              <el-icon><Setting /></el-icon>
              <span>大模型配置</span>
            </el-menu-item>
          </el-menu>
        </div>
      </nav>

      <!-- User Info -->
      <div class="sidebar-footer">
        <div class="user-card">
          <div class="user-avatar">
            {{ authStore.profile?.username?.charAt(0).toUpperCase() }}
          </div>
          <div class="user-info">
            <div class="user-name">{{ authStore.profile?.username }}</div>
            <div class="user-role">
              <el-tag :type="roleTagType" size="small" effect="plain">
                {{ roleLabel }}
              </el-tag>
            </div>
          </div>
        </div>
        <div v-if="authStore.profile?.org_name" class="org-badge">
          <el-icon><OfficeBuilding /></el-icon>
          <span>{{ authStore.profile.org_name }}</span>
        </div>
      </div>
    </el-aside>

    <el-container class="main-container">
      <el-header class="layout-header">
        <div class="header-left">
          <h1 class="page-title">{{ pageTitle }}</h1>
          <el-breadcrumb separator="/">
            <el-breadcrumb-item>首页</el-breadcrumb-item>
            <el-breadcrumb-item>{{ pageTitle }}</el-breadcrumb-item>
          </el-breadcrumb>
        </div>
        <div class="header-right">
          <el-button :icon="Refresh" circle @click="refresh" />
          <el-dropdown trigger="click">
            <el-button :icon="User" circle />
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item disabled>
                  <div class="dropdown-user">
                    <strong>{{ authStore.profile?.username }}</strong>
                    <span class="dropdown-role">{{ roleLabel }}</span>
                  </div>
                </el-dropdown-item>
                <el-dropdown-item divided @click="logout">
                  <el-icon><SwitchButton /></el-icon>
                  退出登录
                </el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </el-header>
      <el-main class="layout-content">
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from "vue"
import { useRoute, useRouter } from "vue-router"
import { useAuthStore } from "@/store/auth"
import { useDatasourceStore } from "@/store/datasource"
import {
  DataLine, ChatDotRound, Coin, User, OfficeBuilding,
  TrendCharts, Setting, Refresh, SwitchButton, Bell, AlarmClock,
  Grid, FolderOpened
} from '@element-plus/icons-vue'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()
const datasourceStore = useDatasourceStore()

const selectedDatasource = ref<number | null>(null)

const activePath = computed(() => route.path)

const pageTitle = computed(() => {
  const titles: Record<string, string> = {
    "/dashboard-center": "看板中心",
    "/data-catalog": "数据目录",
    "/smart-query": "智能问数",
    "/datasource-settings": "数据源管理",
    "/user-management": "用户管理",
    "/org-management": "企业管理",
    "/metric-settings": "指标配置",
    "/alert-settings": "预警管理",
    "/scheduled-reports": "定时报告",
    "/llm-settings": "大模型配置",
  }
  return titles[route.path] || "Dashboard"
})

const isOrgAdmin = computed(() => 
  authStore.profile?.role === 'org_admin' || authStore.profile?.role === 'super_admin'
)
const isSuperAdmin = computed(() => authStore.profile?.role === 'super_admin')

const roleLabel = computed(() => {
  const labels: Record<string, string> = {
    super_admin: '超级管理员',
    org_admin: '企业管理员',
    user: '普通用户',
  }
  return labels[authStore.profile?.role || ''] || authStore.profile?.role
})

const roleTagType = computed(() => {
  const types: Record<string, string> = {
    super_admin: 'danger',
    org_admin: 'warning',
    user: 'info',
  }
  return types[authStore.profile?.role || ''] || 'info'
})

const onDatasourceChange = (id: number) => {
  datasourceStore.switchDatasource(id)
}

const refresh = () => {
  window.location.reload()
}

const logout = () => {
  authStore.logout()
  router.push("/login")
}

onMounted(async () => {
  if (!authStore.profile && authStore.token) {
    authStore.fetchProfile()
  }
  await datasourceStore.fetchDatasources()
  if (datasourceStore.currentId) {
    selectedDatasource.value = datasourceStore.currentId
  }
})
</script>

<style scoped>
.app-shell {
  height: 100vh;
  background: var(--app-bg);
}

.app-sidebar {
  background: linear-gradient(180deg, #1e1b4b 0%, #312e81 100%);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.sidebar-brand {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 20px 20px 16px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
}

.brand-logo {
  width: 36px;
  height: 36px;
  flex-shrink: 0;
}

.brand-logo svg {
  width: 100%;
  height: 100%;
}

.brand-text {
  font-size: 20px;
  font-weight: 700;
  color: white;
  letter-spacing: 0.5px;
}

.datasource-selector {
  padding: 16px 16px 8px;
}

.selector-label {
  display: block;
  font-size: 11px;
  color: rgba(255, 255, 255, 0.5);
  text-transform: uppercase;
  letter-spacing: 0.5px;
  margin-bottom: 8px;
  padding-left: 4px;
}

.datasource-selector :deep(.el-select) {
  width: 100%;
}

.datasource-selector :deep(.el-input__wrapper) {
  background: rgba(255, 255, 255, 0.1);
  border: 1px solid rgba(255, 255, 255, 0.15);
  border-radius: 10px;
  box-shadow: none;
}

.datasource-selector :deep(.el-input__inner) {
  color: white;
}

.datasource-selector :deep(.el-input__inner::placeholder) {
  color: rgba(255, 255, 255, 0.5);
}

.ds-option {
  display: flex;
  align-items: center;
  gap: 8px;
}

.ds-icon {
  font-size: 14px;
}

.sidebar-nav {
  flex: 1;
  overflow-y: auto;
  padding: 8px 0;
}

.nav-section {
  margin-bottom: 8px;
}

.nav-section-title {
  font-size: 11px;
  color: rgba(255, 255, 255, 0.4);
  text-transform: uppercase;
  letter-spacing: 0.5px;
  padding: 12px 20px 8px;
}

.app-menu {
  background: transparent;
  border: none;
  padding: 0 12px;
}

.app-menu :deep(.el-menu-item) {
  height: 44px;
  line-height: 44px;
  margin: 2px 0;
  border-radius: 10px;
  color: rgba(255, 255, 255, 0.7);
  transition: all 0.2s;
}

.app-menu :deep(.el-menu-item:hover) {
  background: rgba(255, 255, 255, 0.1);
  color: white;
}

.app-menu :deep(.el-menu-item.is-active) {
  background: rgba(99, 102, 241, 0.3);
  color: white;
}

.app-menu :deep(.el-menu-item .el-icon) {
  margin-right: 10px;
  font-size: 18px;
}

.sidebar-footer {
  padding: 16px;
  border-top: 1px solid rgba(255, 255, 255, 0.1);
  background: rgba(0, 0, 0, 0.1);
}

.user-card {
  display: flex;
  align-items: center;
  gap: 12px;
}

.user-avatar {
  width: 40px;
  height: 40px;
  border-radius: 10px;
  background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  font-weight: 600;
  font-size: 16px;
}

.user-info {
  flex: 1;
  min-width: 0;
}

.user-name {
  color: white;
  font-weight: 500;
  font-size: 14px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.user-role {
  margin-top: 4px;
}

.org-badge {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-top: 12px;
  padding: 8px 12px;
  background: rgba(255, 255, 255, 0.1);
  border-radius: 8px;
  color: rgba(255, 255, 255, 0.8);
  font-size: 12px;
}

.main-container {
  background: var(--app-bg);
}

.layout-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 24px;
  height: 72px;
  background: var(--app-surface);
  border-bottom: 1px solid var(--app-border);
}

.header-left {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.page-title {
  font-size: 20px;
  font-weight: 600;
  margin: 0;
  color: var(--app-text);
}

.header-left :deep(.el-breadcrumb) {
  font-size: 12px;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 12px;
}

.dropdown-user {
  display: flex;
  flex-direction: column;
  padding: 4px 0;
}

.dropdown-role {
  font-size: 12px;
  color: var(--app-text-muted);
  margin-top: 2px;
}

.layout-content {
  padding: 24px;
  overflow-y: auto;
}
</style>
