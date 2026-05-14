<template>
  <div class="data-development-page">
    <section class="development-tabs-shell" aria-label="数据源与数据集工作台">
      <div class="page-tabbar development-tabbar">
        <button
          v-for="tab in workbenchTabs"
          :key="tab.key"
          class="page-tab page-tab--stacked"
          :class="{ 'is-active': activeTab === tab.key }"
          type="button"
          @click="activeTab = tab.key"
        >
          <el-icon><component :is="tab.icon" /></el-icon>
          <span class="page-tab-text">
            <strong>{{ tab.label }}</strong>
            <small>{{ tab.description }}</small>
          </span>
        </button>
      </div>
      <div class="development-tab-content">
        <DataSourceSettings v-show="activeTab === 'datasources'" />
        <DatasetCenter v-show="activeTab === 'datasets'" />
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed } from "vue"
import { useRoute, useRouter } from "vue-router"
import { Coin, Document } from "@element-plus/icons-vue"
import DataSourceSettings from "@/views/DataSourceSettings.vue"
import DatasetCenter from "@/views/DatasetCenter.vue"

type WorkbenchTab = "datasources" | "datasets"

const route = useRoute()
const router = useRouter()

const normalizeTab = (tab: unknown): WorkbenchTab => (tab === "datasets" ? "datasets" : "datasources")
const tabRouteQueries: Record<WorkbenchTab, { tab: WorkbenchTab }> = {
  datasources: { tab: "datasources" },
  datasets: { tab: "datasets" },
}
const workbenchTabs = [
  { key: "datasources" as const, label: "数据源管理", description: "连接、凭证、表结构", icon: Coin },
  { key: "datasets" as const, label: "数据集开发", description: "维度指标、预览发布", icon: Document },
]

const activeTab = computed<WorkbenchTab>({
  get: () => normalizeTab(route.query.tab),
  set: (tab) => {
    const nextTab = normalizeTab(tab)
    if (route.path === "/data-development" && normalizeTab(route.query.tab) === nextTab) return
    router.replace({
      path: "/data-development",
      query: { ...route.query, ...tabRouteQueries[nextTab] },
    })
  },
})

</script>

<style scoped>
.data-development-page {
  display: flex;
  flex-direction: column;
  gap: 0;
}

.development-tabs-shell {
  padding: 14px 16px 16px;
  border: 1px solid #dbe3ef;
  border-radius: 8px;
  background: #fff;
}

.development-tabbar {
  margin-bottom: 12px;
}

.development-tab-content {
  padding-top: 0;
}

:deep(.datasource-page),
:deep(.dataset-page) {
  padding: 0;
}

@media (max-width: 720px) {
  .development-tabs-shell {
    padding: 12px 10px;
  }

  .development-tabbar :deep(.page-tab-text small) {
    display: none;
  }
}
</style>
