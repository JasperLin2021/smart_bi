import { createRouter, createWebHistory } from "vue-router"
import { useAuthStore } from "@/store/auth"

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: "/", redirect: "/dashboard" },
    { path: "/login", component: () => import("@/views/Login.vue") },
    { path: "/dashboard", component: () => import("@/views/Dashboard.vue") },
    { path: "/dashboard-center", component: () => import("@/views/DashboardCenter.vue") },
    { path: "/big-screen-center", component: () => import("@/views/BigScreenCenter.vue") },
    { path: "/goview", component: () => import("@/views/GoViewCenter.vue") },
    { path: "/data-access", component: () => import("@/views/DataAccessCenter.vue") },
    { path: "/data-link", component: () => import("@/views/DataLink.vue") },
    { path: "/data-pipelines", component: () => import("@/views/DataPipelines.vue") },
    { path: "/data-development", component: () => import("@/views/DataSourceDatasetCenter.vue") },
    { path: "/data-catalog", component: () => import("@/views/DataCatalog.vue") },
    { path: "/dataset-center", redirect: { path: "/data-development", query: { tab: "datasets" } } },
    { path: "/smart-query", component: () => import("@/views/SmartQuery.vue") },
    { path: "/action-items", component: () => import("@/views/ActionItems.vue") },
    { path: "/datasource-settings", redirect: { path: "/data-development", query: { tab: "datasources" } } },
    {
      path: "/olap-status",
      component: () => import("@/views/OlapStatus.vue"),
      meta: { requiredRole: ['org_admin', 'super_admin'] }
    },
    {
      path: "/access-control",
      component: () => import("@/views/AccessControl.vue"),
      meta: { requiredRole: ['dept_admin', 'org_admin', 'super_admin'] }
    },
    { path: "/user-management", redirect: "/access-control" },
    { path: "/role-management", redirect: "/access-control" },
    { path: "/org-management", redirect: "/access-control" },
    { path: "/metric-settings", component: () => import("@/views/MetricSettings.vue") },
    { path: "/alert-settings", component: () => import("@/views/AlertSettings.vue") },
    { path: "/report-center", component: () => import("@/views/ReportCenter.vue") },
    { path: "/report-designer/:id", component: () => import("@/views/ReportDesigner.vue") },
    { path: "/analysis-workbench", component: () => import("@/views/AnalysisWorkbench.vue") },
    { path: "/scheduled-reports", component: () => import("@/views/ScheduledReports.vue") },
    {
      path: "/audit-logs",
      component: () => import("@/views/AuditLogs.vue"),
      meta: { requiredRole: ['org_admin', 'super_admin'] }
    },
    {
      path: "/operations",
      component: () => import("@/views/Operations.vue"),
      meta: { requiredRole: ['org_admin', 'super_admin'] }
    },
    {
      path: "/llm-settings",
      component: () => import("@/views/LlmSettings.vue"),
      meta: { requiredRole: ['super_admin'] }
    },
    {
      path: "/notification-settings",
      component: () => import("@/views/NotificationSettings.vue"),
      meta: { requiredRole: ['super_admin'] }
    },
    {
      path: "/wechat-work-integration",
      component: () => import("@/views/WechatWorkIntegration.vue"),
      meta: { requiredRole: ['super_admin'] }
    },
    {
      path: "/embed/:token",
      component: () => import("@/views/EmbedView.vue"),
      meta: { public: true },
    },
  ]
})

router.beforeEach(async (to) => {
  if (to.path === "/login" || to.meta.public) return true
  
  const token = localStorage.getItem("smart-bi-token")
  if (!token) return "/login"
  
  const authStore = useAuthStore()
  if (!authStore.profile) {
    try {
      await authStore.fetchProfile()
    } catch {
      return "/login"
    }
  }
  
  const requiredRoles = to.meta.requiredRole as string[] | undefined
  if (requiredRoles && authStore.profile) {
    if (!requiredRoles.includes(authStore.profile.role)) {
      return "/dashboard"
    }
  }
  
  return true
})

export default router
