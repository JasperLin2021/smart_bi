<template>
  <el-container class="app-shell">
    <el-aside :width="sidebarWidth" class="app-sidebar" :class="{ collapsed: isSidebarCollapsed }">
      <!-- Brand -->
      <div class="sidebar-brand">
        <div class="brand-logo">
          <svg viewBox="0 0 32 32" fill="none" xmlns="http://www.w3.org/2000/svg">
            <rect width="32" height="32" rx="8" fill="url(#brand-gradient)"/>
            <path d="M9 24V8h3v16H9zm5-6V8h3v10h-3zm5 3V8h3v13h-3z" fill="white"/>
            <defs>
              <linearGradient id="brand-gradient" x1="0" y1="0" x2="32" y2="32">
                <stop stop-color="#0f766e"/>
                <stop offset="1" stop-color="#2563eb"/>
              </linearGradient>
            </defs>
          </svg>
        </div>
        <span v-if="!isSidebarCollapsed" class="brand-text">Smart BI</span>
        <el-button
          class="sidebar-toggle"
          :icon="isSidebarCollapsed ? Expand : Fold"
          circle
          text
          :aria-label="isSidebarCollapsed ? '展开导航' : '收起导航'"
          @click="toggleSidebar"
        />
      </div>

      <!-- Navigation Menu -->
      <nav class="sidebar-nav">
        <el-menu
          :collapse="isSidebarCollapsed"
          :default-active="activePath"
          :default-openeds="defaultOpeneds"
          router
          class="app-menu"
        >
          <template v-for="group in visibleMenuGroups" :key="group.key">
            <el-sub-menu :index="group.key">
              <template #title>
                <el-icon><component :is="group.icon" /></el-icon>
                <span>{{ group.label }}</span>
              </template>
              <el-menu-item
                v-for="item in group.items"
                :key="item.path"
                :index="item.path"
              >
                <el-icon><component :is="item.icon" /></el-icon>
                <span>{{ item.label }}</span>
              </el-menu-item>
            </el-sub-menu>
          </template>
        </el-menu>
      </nav>

      <!-- User Info -->
      <div class="sidebar-footer">
        <div class="user-card">
          <div class="user-avatar">
            {{ authStore.profile?.username?.charAt(0).toUpperCase() }}
          </div>
          <div v-if="!isSidebarCollapsed" class="user-info">
            <div class="user-name">{{ authStore.profile?.username }}</div>
            <div class="user-role">
              <el-tag :type="roleTagType" size="small" effect="plain">
                {{ roleLabel }}
              </el-tag>
            </div>
          </div>
        </div>
        <div v-if="authStore.profile?.org_name && !isSidebarCollapsed" class="org-badge">
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
import { computed, onMounted, ref, type Component } from "vue"
import { useRoute, useRouter } from "vue-router"
import { useAuthStore } from "@/store/auth"
import { useDatasourceStore } from "@/store/datasource"
import {
  DataLine, ChatDotRound, Coin, User, OfficeBuilding,
  TrendCharts, Setting, Refresh, SwitchButton, Bell, AlarmClock,
  Grid, FolderOpened, Document, Fold, Expand
} from '@element-plus/icons-vue'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()
const datasourceStore = useDatasourceStore()

const isSidebarCollapsed = ref(false)

const activePath = computed(() => route.path)
const sidebarWidth = computed(() => (isSidebarCollapsed.value ? "72px" : "260px"))

type MenuRole = "org_admin" | "super_admin"
type MenuItem = {
  path: string
  label: string
  icon: Component
  roles?: MenuRole[]
}

type MenuGroup = {
  key: string
  label: string
  icon: Component
  items: MenuItem[]
}

const menuGroups: MenuGroup[] = [
  {
    key: "workspace",
    label: "工作台",
    icon: DataLine,
    items: [
      { path: "/dashboard", label: "Dashboard", icon: DataLine },
      { path: "/smart-query", label: "智能问数", icon: ChatDotRound },
    ],
  },
  {
    key: "bi-assets",
    label: "BI 分析",
    icon: Grid,
    items: [
      { path: "/dashboard-center", label: "看板中心", icon: Grid },
      { path: "/big-screen-center", label: "大屏中心", icon: DataLine },
      { path: "/dataset-center", label: "数据集中心", icon: Document },
      { path: "/data-catalog", label: "数据目录", icon: FolderOpened },
    ],
  },
  {
    key: "data-governance",
    label: "数据治理",
    icon: Coin,
    items: [
      { path: "/datasource-settings", label: "数据源管理", icon: Coin },
      { path: "/metric-settings", label: "指标配置", icon: TrendCharts },
      { path: "/alert-settings", label: "预警管理", icon: Bell },
      { path: "/scheduled-reports", label: "定时报告", icon: AlarmClock },
    ],
  },
  {
    key: "system-admin",
    label: "系统管理",
    icon: Setting,
    items: [
      { path: "/user-management", label: "用户管理", icon: User, roles: ["org_admin", "super_admin"] },
      { path: "/org-management", label: "企业管理", icon: OfficeBuilding, roles: ["super_admin"] },
      { path: "/audit-logs", label: "审计日志", icon: Document, roles: ["org_admin", "super_admin"] },
      { path: "/operations", label: "运营后台", icon: DataLine, roles: ["org_admin", "super_admin"] },
      { path: "/llm-settings", label: "大模型配置", icon: Setting, roles: ["super_admin"] },
    ],
  },
]

const hasRole = (roles?: MenuRole[]) => {
  if (!roles?.length) return true
  const role = authStore.profile?.role as MenuRole | undefined
  return Boolean(role && roles.includes(role))
}

const visibleMenuGroups = computed(() =>
  menuGroups
    .map((group) => ({
      ...group,
      items: group.items.filter((item) => hasRole(item.roles)),
    }))
    .filter((group) => group.items.length > 0)
)

const defaultOpeneds = computed(() =>
  visibleMenuGroups.value
    .filter((group) => group.items.some((item) => item.path === activePath.value))
    .map((group) => group.key)
)

const pageTitleMap = computed(() =>
  Object.fromEntries(
    menuGroups.flatMap((group) => group.items.map((item) => [item.path, item.label]))
  ) as Record<string, string>
)

const pageTitle = computed(() => {
  return pageTitleMap.value[route.path] || "Dashboard"
})

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

const toggleSidebar = () => {
  isSidebarCollapsed.value = !isSidebarCollapsed.value
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
})
</script>

<style scoped>
.app-shell {
  height: 100vh;
  background: var(--app-bg);
}

.app-sidebar {
  background: #ffffff;
  border-right: 1px solid var(--app-border);
  display: flex;
  flex-direction: column;
  overflow: hidden;
  transition: width 0.18s ease;
}

.sidebar-brand {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 18px 18px 14px;
  border-bottom: 1px solid var(--app-border);
}

.app-sidebar.collapsed .sidebar-brand {
  justify-content: center;
  padding: 16px 10px 12px;
  gap: 8px;
  flex-wrap: wrap;
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
  color: var(--app-text);
  letter-spacing: 0;
}

.sidebar-toggle {
  margin-left: auto;
  color: var(--app-text-muted);
}

.app-sidebar.collapsed .sidebar-toggle {
  margin-left: 0;
}

.ds-option {
  display: flex;
  align-items: center;
  gap: 8px;
}

.ds-icon {
  font-size: 15px;
  color: var(--app-primary);
}

.sidebar-nav {
  flex: 1;
  overflow-y: auto;
  padding: 10px 0 12px;
}

.app-menu {
  background: transparent;
  border: none;
  padding: 0 12px;
}

.app-sidebar.collapsed .app-menu {
  padding: 0 6px;
}

.app-menu:not(.el-menu--collapse) :deep(.el-sub-menu) {
  margin-bottom: 4px;
}

.app-menu :deep(.el-sub-menu__title),
.app-menu :deep(.el-menu-item) {
  min-height: 42px;
  height: 42px;
  line-height: 42px;
  margin: 2px 0;
  border-radius: var(--app-radius-sm);
  color: var(--app-text-muted);
  transition: all 0.2s;
}

.app-menu :deep(.el-sub-menu__title:hover),
.app-menu :deep(.el-menu-item:hover) {
  background: var(--app-surface-muted);
  color: var(--app-text);
}

.app-menu :deep(.el-sub-menu.is-active > .el-sub-menu__title) {
  color: var(--app-primary-dark);
  font-weight: 600;
}

.app-menu :deep(.el-menu-item.is-active) {
  background: rgba(15, 118, 110, 0.1);
  color: var(--app-primary-dark);
  font-weight: 600;
}

.app-menu :deep(.el-sub-menu__title .el-icon),
.app-menu :deep(.el-menu-item .el-icon) {
  margin-right: 10px;
  font-size: 18px;
}

.app-menu:not(.el-menu--collapse) :deep(.el-sub-menu .el-menu-item) {
  margin-left: 12px;
  padding-left: 42px !important;
  min-width: 0;
}

.app-menu.el-menu--collapse {
  width: auto;
}

.app-menu.el-menu--collapse :deep(.el-sub-menu__title),
.app-menu.el-menu--collapse :deep(.el-menu-item) {
  justify-content: center;
  padding: 0 !important;
}

.app-menu.el-menu--collapse :deep(.el-sub-menu__title .el-icon),
.app-menu.el-menu--collapse :deep(.el-menu-item .el-icon) {
  margin-right: 0;
}

.sidebar-footer {
  padding: 14px;
  border-top: 1px solid var(--app-border);
  background: var(--app-surface-muted);
}

.app-sidebar.collapsed .sidebar-footer {
  padding: 12px 10px;
}

.user-card {
  display: flex;
  align-items: center;
  gap: 12px;
}

.app-sidebar.collapsed .user-card {
  justify-content: center;
}

.user-avatar {
  width: 40px;
  height: 40px;
  border-radius: var(--app-radius-sm);
  background: var(--app-primary);
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
  color: var(--app-text);
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
  background: #ffffff;
  border: 1px solid var(--app-border);
  border-radius: var(--app-radius-sm);
  color: var(--app-text-muted);
  font-size: 12px;
}

.main-container {
  background: var(--app-bg);
}

.layout-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 22px;
  height: 64px;
  background: var(--app-surface);
  border-bottom: 1px solid var(--app-border);
}

.header-left {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.page-title {
  font-size: 18px;
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
  padding: 18px;
  overflow-y: auto;
}
</style>
