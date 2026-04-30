import { createRouter, createWebHistory } from "vue-router"
import { useAuthStore } from "@/store/auth"

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: "/", redirect: "/dashboard" },
    { path: "/login", component: () => import("@/views/Login.vue") },
    { path: "/dashboard", component: () => import("@/views/Dashboard.vue") },
    { path: "/dashboard-center", component: () => import("@/views/DashboardCenter.vue") },
    { path: "/big-screen-center", component: () => import("@/views/GoViewCenter.vue") },
    { path: "/goview", redirect: "/big-screen-center" },
    { path: "/internal-big-screen-center", component: () => import("@/views/BigScreenCenter.vue") },
    { path: "/data-catalog", component: () => import("@/views/DataCatalog.vue") },
    { path: "/dataset-center", component: () => import("@/views/DatasetCenter.vue") },
    { path: "/smart-query", component: () => import("@/views/SmartQuery.vue") },
    { path: "/datasource-settings", component: () => import("@/views/DataSourceSettings.vue") },
    { 
      path: "/user-management", 
      component: () => import("@/views/UserManagement.vue"),
      meta: { requiredRole: ['org_admin', 'super_admin'] }
    },
    { 
      path: "/org-management", 
      component: () => import("@/views/OrgManagement.vue"),
      meta: { requiredRole: ['super_admin'] }
    },
    { path: "/metric-settings", component: () => import("@/views/MetricSettings.vue") },
    { path: "/alert-settings", component: () => import("@/views/AlertSettings.vue") },
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
  ]
})

router.beforeEach(async (to) => {
  if (to.path === "/login") return true
  
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
