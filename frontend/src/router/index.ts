import { createRouter, createWebHistory } from "vue-router"
import DashboardView from "@/views/Dashboard.vue"
import SmartQueryView from "@/views/SmartQuery.vue"
import LoginView from "@/views/Login.vue"
import LlmSettingsView from "@/views/LlmSettings.vue"
import MetricSettingsView from "@/views/MetricSettings.vue"
import DataSourceSettingsView from "@/views/DataSourceSettings.vue"

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: "/", redirect: "/dashboard" },
    { path: "/login", component: LoginView },
    { path: "/dashboard", component: DashboardView },
    { path: "/smart-query", component: SmartQueryView },
    { path: "/llm-settings", component: LlmSettingsView },
    { path: "/metric-settings", component: MetricSettingsView },
    { path: "/datasource-settings", component: DataSourceSettingsView },
  ]
})

router.beforeEach((to) => {
  if (to.path === "/login") {
    return true
  }
  const token = localStorage.getItem("smart-bi-token")
  if (!token) {
    return "/login"
  }
  return true
})

export default router
