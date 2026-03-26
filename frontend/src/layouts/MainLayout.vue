<template>
  <el-container class="app-shell">
    <el-aside width="240px" class="app-sidebar">
      <div class="brand">Smart BI</div>
      <div class="datasource-selector" v-if="datasourceStore.datasources.length > 0">
        <el-select
          v-model="selectedDatasource"
          size="small"
          placeholder="选择数据源"
          style="width: 100%; padding: 0 12px;"
          @change="onDatasourceChange"
        >
          <el-option
            v-for="ds in datasourceStore.datasources"
            :key="ds.id"
            :label="ds.name"
            :value="ds.id"
          />
        </el-select>
      </div>
      <el-menu :default-active="activePath" router class="app-menu">
        <el-menu-item index="/dashboard">Dashboard 仪表板</el-menu-item>
        <el-menu-item index="/smart-query">智能问数</el-menu-item>
        <el-menu-item index="/datasource-settings">数据源管理</el-menu-item>
        <el-menu-item v-if="isOrgAdmin" index="/user-management">用户管理</el-menu-item>
        <el-menu-item v-if="isSuperAdmin" index="/org-management">企业管理</el-menu-item>
        <el-menu-item index="/metric-settings">指标配置</el-menu-item>
        <el-menu-item v-if="isSuperAdmin" index="/llm-settings">大模型配置</el-menu-item>
      </el-menu>
    </el-aside>
    <el-container>
      <el-header class="layout-header">
        <div class="page-title">{{ pageTitle }}</div>
        <el-space class="header-actions">
          <el-button size="small" @click="refresh">刷新</el-button>
          <el-dropdown>
            <span class="user-trigger">
              {{ authStore.profile?.username || "管理员" }}
            </span>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item>个人中心</el-dropdown-item>
                <el-dropdown-item @click="logout">退出登录</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </el-space>
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

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()
const datasourceStore = useDatasourceStore()

const selectedDatasource = ref<number | null>(null)

const activePath = computed(() => route.path)
const pageTitle = computed(() => {
  if (route.path === "/smart-query") return "智能问数"
  if (route.path === "/datasource-settings") return "数据源管理"
  if (route.path === "/user-management") return "用户管理"
  if (route.path === "/org-management") return "企业管理"
  if (route.path === "/metric-settings") return "指标配置"
  if (route.path === "/llm-settings") return "大模型配置"
  return "Dashboard 仪表板"
})
const isOrgAdmin = computed(() => 
  authStore.profile?.role === 'org_admin' || authStore.profile?.role === 'super_admin'
)
const isSuperAdmin = computed(() => authStore.profile?.role === 'super_admin')

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
.datasource-selector {
  padding: 8px 0;
  border-bottom: 1px solid var(--el-border-color-lighter);
  margin-bottom: 4px;
}
</style>
