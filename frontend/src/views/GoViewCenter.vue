<template>
  <div class="goview-page">
    <header class="goview-toolbar">
      <div>
        <h2>{{ launchInfo?.title || "大屏中心" }}</h2>
        <p>{{ organizationText }}</p>
      </div>
      <div class="goview-actions">
        <el-segmented
          v-if="modeOptions.length > 1"
          class="page-segmented-tabs"
          v-model="activeMode"
          :options="modeOptions"
          @change="loadLaunch"
        />
        <el-button :loading="loading" @click="loadLaunch">刷新</el-button>
        <el-button type="primary" :disabled="!currentTarget" @click="openExternal">
          新窗口打开
        </el-button>
      </div>
    </header>

    <el-alert
      v-if="!loading && launchInfo && !launchInfo.enabled"
      type="warning"
      show-icon
      :closable="false"
      title="GoView 服务不可用"
      description="请确认 GoView 已启动，并检查 GOVIEW_BASE_URL / GOVIEW_EMBED_BASE_URL 是否是浏览器可访问地址。"
    />

    <section class="goview-frame-wrap">
      <el-skeleton v-if="loading" :rows="8" animated />
      <el-empty v-else-if="errorMessage" :description="errorMessage">
        <el-button type="primary" @click="loadLaunch">重试</el-button>
      </el-empty>
      <iframe
        v-else-if="currentTarget"
        :key="frameKey"
        class="goview-frame"
        :src="currentTarget"
        title="GoView"
        allow="fullscreen"
      />
      <el-empty v-else description="暂无可用 GoView 地址" />
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from "vue"
import axios from "axios"
import { ElMessage } from "element-plus"

interface GoViewLaunch {
  enabled: boolean
  reachable: boolean
  title: string
  modes: string[]
  default_mode: string
  embed: boolean
  organization: {
    id: number | null
    name: string
    scope: string
  }
  targets: Record<string, string>
}

const launchInfo = ref<GoViewLaunch | null>(null)
const activeMode = ref("")
const loading = ref(false)
const errorMessage = ref("")
const frameKey = ref(0)

const modeOptions = computed(() =>
  (launchInfo.value?.modes || []).map((mode) => ({
    label: mode === "design" ? "设计" : "查看",
    value: mode,
  }))
)

const currentTarget = computed(() => {
  if (!launchInfo.value) return ""
  return launchInfo.value.targets[activeMode.value] || ""
})

const organizationText = computed(() => {
  const organization = launchInfo.value?.organization
  if (!organization) return "由 Smart BI 控制访问权限"
  return organization.scope === "all" ? "全部组织" : organization.name
})

const loadLaunch = async () => {
  loading.value = true
  errorMessage.value = ""
  try {
    const response = await axios.get("/api/goview/launch", {
      params: { mode: activeMode.value || undefined },
    })
    launchInfo.value = response.data
    activeMode.value = response.data.default_mode || response.data.modes?.[0] || "view"
    frameKey.value += 1
  } catch (error: any) {
    errorMessage.value = error.response?.data?.detail || "GoView 入口加载失败"
    ElMessage.error(errorMessage.value)
  } finally {
    loading.value = false
  }
}

const openExternal = () => {
  if (!currentTarget.value) return
  window.open(currentTarget.value, "_blank", "noopener,noreferrer")
}

onMounted(loadLaunch)
</script>

<style scoped>
.goview-page {
  display: flex;
  flex-direction: column;
  gap: 14px;
  height: calc(100vh - 132px);
  min-height: 620px;
}

.goview-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 12px 14px;
  border: 1px solid var(--app-border);
  background: var(--app-surface);
}

.goview-toolbar h2 {
  margin: 0;
  font-size: 18px;
}

.goview-toolbar p {
  margin: 4px 0 0;
  color: var(--app-text-muted);
}

.goview-actions {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.goview-frame-wrap {
  flex: 1;
  min-height: 0;
  border: 1px solid var(--app-border);
  background: var(--app-surface);
}

.goview-frame {
  width: 100%;
  height: 100%;
  border: 0;
  background: #fff;
}

@media (max-width: 768px) {
  .goview-page {
    height: auto;
    min-height: 560px;
  }

  .goview-toolbar {
    align-items: flex-start;
    flex-direction: column;
  }

  .goview-frame-wrap {
    min-height: 520px;
  }
}
</style>
