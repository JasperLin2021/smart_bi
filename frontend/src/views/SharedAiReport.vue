<template>
  <div class="shared-ai-report">
    <div v-if="loading" class="shared-state">
      <el-icon class="is-loading" :size="28"><Loading /></el-icon>
      <p>报表加载中…</p>
    </div>
    <div v-else-if="error" class="shared-state">
      <el-icon :size="40"><WarningFilled /></el-icon>
      <h2>报表加载失败</h2>
      <p>{{ error }}</p>
    </div>
    <iframe
      v-else
      class="shared-report-frame"
      sandbox="allow-scripts"
      :srcdoc="reportHtml"
      :title="title || 'AI 报表'"
    ></iframe>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from "vue"
import { useRoute } from "vue-router"
import axios from "axios"
import { Loading, WarningFilled } from "@element-plus/icons-vue"

const route = useRoute()

const loading = ref(true)
const error = ref("")
const title = ref("")
const reportHtml = ref("")

onMounted(async () => {
  const token = route.params.token
  try {
    const { data } = await axios.get(`/api/ai-reports/shared/${token}`)
    title.value = data.title || ""
    reportHtml.value = data.html || ""
    if (title.value) document.title = `${title.value} - Smart BI`
  } catch (err: any) {
    error.value = err.response?.data?.detail || "链接无效或报表已取消分享"
  } finally {
    loading.value = false
  }
})
</script>

<style scoped>
.shared-ai-report {
  position: fixed;
  inset: 0;
  background: #ffffff;
}

.shared-report-frame {
  width: 100%;
  height: 100%;
  border: none;
}

.shared-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  height: 100%;
  color: #637083;
}

.shared-state h2 {
  margin: 0;
  color: #102033;
}

.shared-state p {
  margin: 0;
}
</style>
