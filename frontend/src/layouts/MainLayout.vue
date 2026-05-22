<template>
  <el-container class="app-shell">
    <el-aside :width="sidebarWidth" class="app-sidebar" :class="{ collapsed: effectiveSidebarCollapsed }">
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
        <span v-if="!effectiveSidebarCollapsed" class="brand-text">Smart BI</span>
        <el-button
          class="sidebar-toggle"
          :icon="effectiveSidebarCollapsed ? Expand : Fold"
          circle
          text
          :aria-label="effectiveSidebarCollapsed ? '展开导航' : '收起导航'"
          @click="toggleSidebar"
        />
      </div>

      <!-- Navigation Menu -->
      <nav class="sidebar-nav">
        <el-menu
          :collapse="effectiveSidebarCollapsed"
          :default-active="activePath"
          :default-openeds="defaultOpeneds"
          router
          class="app-menu"
        >
          <template v-for="entry in visibleMenuEntries" :key="entry.type === 'item' ? entry.path : entry.key">
            <el-menu-item
              v-if="entry.type === 'item'"
              :index="entry.path"
            >
              <el-icon><component :is="entry.icon" /></el-icon>
              <span>{{ entry.label }}</span>
            </el-menu-item>
            <el-sub-menu v-else :index="entry.key">
              <template #title>
                <el-icon><component :is="entry.icon" /></el-icon>
                <span>{{ entry.label }}</span>
              </template>
              <el-menu-item
                v-for="item in entry.items"
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
          <div v-if="!effectiveSidebarCollapsed" class="user-info">
            <div class="user-name">{{ authStore.profile?.username }}</div>
            <div class="user-role">
              <el-tag :type="roleTagType" size="small" effect="plain">
                {{ roleLabel }}
              </el-tag>
            </div>
          </div>
        </div>
        <div v-if="authStore.profile?.org_name && !effectiveSidebarCollapsed" class="org-badge">
          <el-icon><OfficeBuilding /></el-icon>
          <span>{{ authStore.profile.org_name }}</span>
        </div>
      </div>

      <button
        v-if="!isMobileLayout"
        type="button"
        class="sidebar-edge-toggle"
        :class="{ collapsed: effectiveSidebarCollapsed }"
        :aria-label="effectiveSidebarCollapsed ? '展开侧边栏导航' : '收起侧边栏导航'"
        :title="effectiveSidebarCollapsed ? '展开侧边栏导航' : '收起侧边栏导航'"
        @click="toggleSidebar"
      >
        <span class="sidebar-edge-grip">
          <el-icon>
            <component :is="effectiveSidebarCollapsed ? Expand : Fold" />
          </el-icon>
        </span>
        <span class="visually-hidden">
          {{ effectiveSidebarCollapsed ? '展开侧边栏导航' : '收起侧边栏导航' }}
        </span>
      </button>
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
          <div id="smart-query-header-actions" class="smart-query-header-actions-target"></div>

          <el-button :icon="Refresh" circle @click="refresh" />

          <!-- Notification bell -->
          <el-popover
            v-model:visible="notifPopoverVisible"
            placement="bottom-end"
            :width="320"
            trigger="click"
            @show="fetchNotifications"
          >
            <template #reference>
              <el-badge :value="unreadCount || undefined" :max="99" :hidden="!unreadCount" type="danger">
                <el-button :icon="Bell" circle />
              </el-badge>
            </template>
            <div class="notif-panel">
              <div class="notif-header">
                <span>通知</span>
                <el-button v-if="notifications.length" text size="small" @click="markAllRead">全部已读</el-button>
              </div>
              <el-empty v-if="!notifications.length" description="暂无通知" :image-size="60" />
              <div v-else class="notif-list">
                <div
                  v-for="n in notifications"
                  :key="n.id"
                  class="notif-item"
                  :class="{ unread: !n.is_read }"
                  @click="handleNotifClick(n)"
                >
                  <div class="notif-msg">{{ n.message }}</div>
                  <div class="notif-time">{{ formatNotifTime(n.created_at) }}</div>
                </div>
              </div>
            </div>
          </el-popover>

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

    <FloatingAgent />
  </el-container>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, type Component } from "vue"
import { useRoute, useRouter } from "vue-router"
import axios from "axios"
import FloatingAgent from "@/components/FloatingAgent.vue"
import { useAuthStore } from "@/store/auth"
import { useDatasourceStore } from "@/store/datasource"
import {
  DataLine, ChatDotRound, Coin, User, OfficeBuilding,
  TrendCharts, Setting, Refresh, SwitchButton, Bell, AlarmClock,
  Grid, FolderOpened, Document, Fold, Expand, Tickets, SetUp
} from '@element-plus/icons-vue'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()
const datasourceStore = useDatasourceStore()

const isSidebarCollapsed = ref(false)

// ── Notifications ─────────────────────────────────────────────────────────────
interface NotifItem {
  id: number
  asset_id: number
  message: string
  is_read: boolean
  created_at: string | null
}

const notifPopoverVisible = ref(false)
const unreadCount = ref(0)
const notifications = ref<NotifItem[]>([])
let notifPollTimer: ReturnType<typeof setInterval> | null = null

const fetchUnreadCount = async () => {
  if (!authStore.token) return
  try {
    const { data } = await axios.get("/api/catalog/notifications", { params: { unread: true } })
    unreadCount.value = data.unread_count
  } catch {
    /* ignore */
  }
}

const fetchNotifications = async () => {
  try {
    const { data } = await axios.get("/api/catalog/notifications")
    notifications.value = data.items
    unreadCount.value = data.unread_count
  } catch {
    /* ignore */
  }
}

const markAllRead = async () => {
  try {
    await axios.put("/api/catalog/notifications/read-all")
    notifications.value.forEach(n => { n.is_read = true })
    unreadCount.value = 0
  } catch {
    /* ignore */
  }
}

const handleNotifClick = async (n: NotifItem) => {
  if (!n.is_read) {
    await axios.put(`/api/catalog/notifications/${n.id}/read`)
    n.is_read = true
    unreadCount.value = Math.max(0, unreadCount.value - 1)
  }
  notifPopoverVisible.value = false
  router.push("/data-catalog")
}

const formatNotifTime = (val: string | null) => {
  if (!val) return ""
  const d = new Date(val)
  return isNaN(d.getTime()) ? val : d.toLocaleString("zh-CN", { hour12: false })
}
const isMobileLayout = ref(false)

const activePath = computed(() => route.path)
const effectiveSidebarCollapsed = computed(() => isSidebarCollapsed.value || isMobileLayout.value)
const sidebarWidth = computed(() => (effectiveSidebarCollapsed.value ? "72px" : "224px"))

type MenuRole = "dept_admin" | "org_admin" | "super_admin"
type MenuItem = {
  path: string
  label: string
  icon: Component
  roles?: MenuRole[]
}

type StandaloneMenuItem = MenuItem & {
  type: "item"
}

type MenuGroup = {
  type: "group"
  key: string
  label: string
  icon: Component
  items: MenuItem[]
}

type MenuEntry = StandaloneMenuItem | MenuGroup

const menuEntries: MenuEntry[] = [
  {
    type: "group",
    key: "workspace",
    label: "工作台",
    icon: DataLine,
    items: [
      { path: "/smart-query", label: "智能问数", icon: ChatDotRound },
      { path: "/dashboard", label: "仪表盘", icon: DataLine },
      { path: "/action-items", label: "行动闭环", icon: Tickets },
    ],
  },
  {
    type: "group",
    key: "data-access",
    label: "数据准备",
    icon: Coin,
    items: [
      { path: "/data-development", label: "数据接入", icon: Document },
      { path: "/data-link", label: "连接器接入", icon: Coin },
      { path: "/data-pipelines", label: "可视化ETL", icon: SetUp, roles: ["org_admin", "super_admin"] },
      { path: "/olap-status", label: "OLAP 数据平台", icon: DataLine, roles: ["org_admin", "super_admin"] },
      { path: "/data-catalog", label: "数据目录", icon: FolderOpened },
    ],
  },
  {
    type: "group",
    key: "bi-assets",
    label: "BI 分析",
    icon: Grid,
    items: [
      { path: "/dashboard-center", label: "看板中心", icon: Grid },
      { path: "/metric-settings", label: "可信指标", icon: TrendCharts },
      { path: "/alert-settings", label: "预警管理", icon: Bell },
      { path: "/scheduled-reports", label: "定时报告", icon: AlarmClock },
    ],
  },
  {
    type: "group",
    key: "system-admin",
    label: "系统管理",
    icon: Setting,
    items: [
      { path: "/access-control", label: "用户与权限", icon: User, roles: ["dept_admin", "org_admin", "super_admin"] },
      { path: "/audit-logs", label: "审计日志", icon: Document, roles: ["org_admin", "super_admin"] },
      { path: "/operations", label: "运营后台", icon: DataLine, roles: ["org_admin", "super_admin"] },
      { path: "/llm-settings", label: "大模型配置", icon: Setting, roles: ["super_admin"] },
      { path: "/notification-settings", label: "通知配置", icon: Bell, roles: ["super_admin"] },
      { path: "/wechat-work-integration", label: "企业微信集成", icon: OfficeBuilding, roles: ["super_admin"] },
    ],
  },
]

const hiddenPageTitles: Record<string, string> = {
  "/big-screen-center": "大屏中心",
}

const hasRole = (roles?: MenuRole[]) => {
  if (!roles?.length) return true
  const role = authStore.profile?.role as MenuRole | undefined
  return Boolean(role && roles.includes(role))
}

const visibleMenuEntries = computed(() => {
  const entries: MenuEntry[] = []
  menuEntries.forEach((entry) => {
    if (entry.type === "item") {
      if (hasRole(entry.roles)) entries.push(entry)
      return
    }

    const items = entry.items.filter((item) => hasRole(item.roles))
    if (items.length > 0) {
      entries.push({ ...entry, items })
    }
  })
  return entries
})

const defaultOpeneds = computed(() =>
  visibleMenuEntries.value
    .filter((entry): entry is MenuGroup => entry.type === "group" && entry.items.some((item) => item.path === activePath.value))
    .map((group) => group.key)
)

const flattenMenuItems = (entries: MenuEntry[]) =>
  entries.flatMap((entry) => (entry.type === "item" ? [entry] : entry.items))

const pageTitleMap = computed(() =>
  Object.fromEntries(
    flattenMenuItems(menuEntries).map((item) => [item.path, item.label])
  ) as Record<string, string>
)

const pageTitle = computed(() => {
  return pageTitleMap.value[route.path] || hiddenPageTitles[route.path] || "Dashboard"
})

const roleLabel = computed(() => {
  const labels: Record<string, string> = {
    super_admin: '超级管理员',
    org_admin: '企业管理员',
    dept_admin: '部门管理员',
    user: '普通用户',
  }
  return labels[authStore.profile?.role || ''] || authStore.profile?.role
})

const roleTagType = computed(() => {
  const types: Record<string, string> = {
    super_admin: 'danger',
    org_admin: 'warning',
    dept_admin: 'warning',
    user: 'info',
  }
  return types[authStore.profile?.role || ''] || 'info'
})

const toggleSidebar = () => {
  if (isMobileLayout.value) return
  isSidebarCollapsed.value = !isSidebarCollapsed.value
}

const syncViewport = () => {
  isMobileLayout.value = window.innerWidth <= 768
}

const refresh = () => {
  window.location.reload()
}

const logout = () => {
  authStore.logout()
  router.push("/login")
}

onMounted(async () => {
  syncViewport()
  window.addEventListener("resize", syncViewport)
  if (!authStore.profile && authStore.token) {
    authStore.fetchProfile()
  }
  await datasourceStore.fetchDatasources()
  fetchUnreadCount()
  notifPollTimer = setInterval(fetchUnreadCount, 60_000)
})

onBeforeUnmount(() => {
  window.removeEventListener("resize", syncViewport)
  if (notifPollTimer) clearInterval(notifPollTimer)
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
  overflow: visible;
  position: relative;
  transition: width 0.18s ease;
  z-index: 20;
}

.sidebar-brand {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 18px 14px 14px;
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
  width: 40px;
  height: 40px;
  min-width: 40px;
  margin-left: auto;
  color: var(--app-text-muted);
}

.app-sidebar.collapsed .sidebar-toggle {
  margin-left: 0;
}

.sidebar-edge-toggle {
  position: absolute;
  top: 50%;
  right: -22px;
  z-index: 30;
  width: 44px;
  min-height: 96px;
  padding: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  border: 0;
  background: transparent;
  color: var(--app-text-muted);
  cursor: pointer;
  touch-action: manipulation;
  transform: translateY(-50%);
}

.sidebar-edge-grip {
  width: 28px;
  height: 72px;
  display: flex;
  align-items: center;
  justify-content: center;
  border: 1px solid var(--app-border);
  border-left-color: rgba(15, 118, 110, 0.18);
  border-radius: 0 12px 12px 0;
  background: #ffffff;
  box-shadow: 0 12px 26px rgba(15, 23, 42, 0.12);
  transition: color 0.16s ease, transform 0.16s ease, box-shadow 0.16s ease, border-color 0.16s ease;
}

.sidebar-edge-toggle:hover .sidebar-edge-grip,
.sidebar-edge-toggle:active .sidebar-edge-grip {
  color: var(--app-primary);
  border-color: rgba(15, 118, 110, 0.28);
  box-shadow: 0 14px 30px rgba(15, 23, 42, 0.16);
  transform: translateX(2px);
}

.sidebar-edge-toggle:focus-visible {
  outline: none;
}

.sidebar-edge-toggle:focus-visible .sidebar-edge-grip {
  color: var(--app-primary);
  border-color: var(--app-primary);
  box-shadow: 0 0 0 3px rgba(15, 118, 110, 0.18), 0 14px 30px rgba(15, 23, 42, 0.14);
}

.sidebar-edge-toggle.collapsed .sidebar-edge-grip {
  color: var(--app-primary-dark);
}

.visually-hidden {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
  border: 0;
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
  padding: 0 10px;
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
  margin-left: 8px;
  padding-left: 38px !important;
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
  gap: 18px;
  padding: 0 22px;
  height: 64px;
  background: var(--app-surface);
  border-bottom: 1px solid var(--app-border);
}

.header-left {
  display: flex;
  flex-direction: column;
  flex-shrink: 0;
  gap: 4px;
  min-width: 0;
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
  justify-content: flex-end;
  flex: 1;
  gap: 12px;
  min-width: 0;
}

.smart-query-header-actions-target {
  min-width: 0;
  display: flex;
  align-items: center;
  justify-content: flex-end;
  flex: 1 1 auto;
}

.smart-query-header-actions-target:empty {
  display: none;
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

.notif-panel {
  display: flex;
  flex-direction: column;
  gap: 0;
}

.notif-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0 0 10px;
  font-weight: 600;
  font-size: 14px;
}

.notif-list {
  max-height: 320px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.notif-item {
  padding: 10px 12px;
  border-radius: 6px;
  cursor: pointer;
  transition: background 0.15s;
}

.notif-item:hover {
  background: var(--el-fill-color-light);
}

.notif-item.unread {
  background: var(--el-color-primary-light-9);
}

.notif-item.unread:hover {
  background: var(--el-color-primary-light-8);
}

.notif-msg {
  font-size: 13px;
  color: var(--app-text);
  line-height: 1.4;
}

.notif-time {
  font-size: 11px;
  color: var(--app-text-muted);
  margin-top: 4px;
}

@media (max-width: 768px) {
  .sidebar-edge-toggle {
    display: none;
  }
}

@media (prefers-reduced-motion: reduce) {
  .app-sidebar,
  .sidebar-edge-grip {
    transition: none;
  }
}
</style>
