<template>
  <el-drawer
    v-model="visible"
    title="AI 数据分析报告"
    size="640px"
    direction="rtl"
    :destroy-on-close="true"
  >
    <div class="report-body">
      <div class="report-actions">
        <el-button
          type="primary"
          :loading="loading"
          :disabled="loading"
          @click="generate"
        >
          <el-icon><MagicStick /></el-icon>
          {{ loading ? "生成中…" : "生成报告" }}
        </el-button>
        <el-button v-if="markdown" text @click="copy">
          <el-icon><CopyDocument /></el-icon> 复制
        </el-button>
      </div>

      <el-alert v-if="error" type="error" :title="error" :closable="false" style="margin:12px 0" />

      <div v-if="loading" class="report-skeleton">
        <el-skeleton :rows="8" animated />
      </div>

      <div v-else-if="markdown" class="report-content" v-html="renderedMarkdown" />

      <el-empty v-else-if="!error" description="点击生成报告让 AI 分析当前图表数据" :image-size="80" />
    </div>
  </el-drawer>
</template>

<script setup lang="ts">
import { computed, ref, watch } from "vue"
import { marked } from "marked"
import { ElMessage } from "element-plus"
import { MagicStick, CopyDocument } from "@element-plus/icons-vue"
import axios from "axios"

const props = defineProps<{
  chartId?: number | null
  title?: string
  question?: string
  datasourceId?: number | null
  columns?: string[]
  rows?: Array<Record<string, any>>
}>()

const visible = defineModel<boolean>({ required: true })

const loading = ref(false)
const error = ref("")
const markdown = ref("")

const renderedMarkdown = computed(() => {
  if (!markdown.value) return ""
  return marked.parse(markdown.value) as string
})

async function generate() {
  loading.value = true
  error.value = ""
  markdown.value = ""
  try {
    const resp = await axios.post("/api/report-gen", {
      chart_id: props.chartId ?? null,
      title: props.title ?? "",
      question: props.question ?? "",
      columns: props.columns ?? [],
      rows: props.rows ?? [],
      datasource_id: props.datasourceId ?? null,
    })
    markdown.value = resp.data.markdown
  } catch (e: any) {
    error.value = e?.response?.data?.detail || "报告生成失败"
  } finally {
    loading.value = false
  }
}

async function copy() {
  try {
    await navigator.clipboard.writeText(markdown.value)
    ElMessage.success("已复制到剪贴板")
  } catch {
    ElMessage.error("复制失败")
  }
}

watch(visible, (v) => {
  if (!v) {
    markdown.value = ""
    error.value = ""
  }
})
</script>

<style scoped>
.report-body { display: flex; flex-direction: column; gap: 16px; padding: 4px 0; }
.report-actions { display: flex; gap: 8px; align-items: center; }
.report-skeleton { padding: 8px 0; }
.report-content {
  line-height: 1.8;
  font-size: 14px;
  color: var(--app-text);
}
.report-content :deep(h2) {
  font-size: 16px;
  font-weight: 600;
  margin: 20px 0 8px;
  color: var(--app-primary);
}
.report-content :deep(ul), .report-content :deep(ol) {
  padding-left: 20px;
  margin: 8px 0;
}
.report-content :deep(li) { margin: 4px 0; }
.report-content :deep(strong) { color: var(--app-text); }
.report-content :deep(p) { margin: 8px 0; }
</style>
