<template>
  <div class="data-development-page">
    <section class="development-tabs-shell" aria-label="数据源与数据集工作台">
      <el-tabs v-model="activeTab" class="development-tabs" @tab-change="handleTabChange">
        <el-tab-pane name="datasources">
          <template #label>
            <span class="tab-label">
              <el-icon><Coin /></el-icon>
              <span>
                <strong>数据源管理</strong>
                <small>连接、凭证、表结构</small>
              </span>
            </span>
          </template>
          <DataSourceSettings />
        </el-tab-pane>
        <el-tab-pane name="datasets">
          <template #label>
            <span class="tab-label">
              <el-icon><Document /></el-icon>
              <span>
                <strong>数据集开发</strong>
                <small>维度指标、预览发布</small>
              </span>
            </span>
          </template>
          <DatasetCenter />
        </el-tab-pane>
      </el-tabs>
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

const handleTabChange = (tab: string | number) => {
  activeTab.value = normalizeTab(tab)
}
</script>

<style scoped>
.data-development-page {
  display: flex;
  flex-direction: column;
  gap: 0;
}

.development-tabs-shell {
  padding: 0 16px 16px;
  border: 1px solid #dbe3ef;
  border-radius: 8px;
  background: #fff;
}

.development-tabs {
  --el-color-primary: #0f766e;
}

.tab-label {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  min-width: 154px;
}

.tab-label span {
  display: flex;
  flex-direction: column;
  gap: 2px;
  line-height: 1.2;
}

.tab-label strong {
  color: #0f172a;
  font-size: 14px;
  font-weight: 700;
}

.tab-label small {
  color: #64748b;
  font-size: 12px;
  font-weight: 500;
}

:deep(.el-tabs__header) {
  margin: 0;
}

:deep(.el-tabs__nav-wrap::after) {
  height: 1px;
  background: #e2e8f0;
}

:deep(.el-tabs__item) {
  height: 58px;
  padding: 0 18px;
  color: #475569;
}

:deep(.el-tabs__item.is-active) {
  color: #0f766e;
}

:deep(.el-tabs__content) {
  padding-top: 12px;
}

:deep(.datasource-page),
:deep(.dataset-page) {
  padding: 0;
}

@media (max-width: 720px) {
  .development-tabs-shell {
    padding: 0 10px 12px;
  }

  .tab-label {
    min-width: 0;
  }

  .tab-label small {
    display: none;
  }
}
</style>
