<template>
  <div class="page data-pipelines-page">
    <section class="enterprise-hero">
      <div>
        <p class="eyebrow">DATA PIPELINES</p>
        <h2>数据加工管道</h2>
        <p>用 DAG 编排抽取、清洗、质量校验、装载和补数任务，沉淀可观测的数据开发链路。</p>
      </div>
      <div class="hero-actions">
        <el-button :icon="Refresh" :loading="loading" @click="loadAll">刷新</el-button>
        <el-button type="primary" :icon="Plus" @click="openCreate">新建管道</el-button>
      </div>
    </section>

    <section class="pipeline-layout">
      <aside class="pipeline-list">
        <div class="panel-title">管道列表</div>
        <button
          v-for="item in pipelines"
          :key="item.id"
          type="button"
          class="pipeline-item"
          :class="{ active: selectedPipeline?.id === item.id }"
          @click="selectedId = item.id"
        >
          <strong>{{ item.name }}</strong>
          <span>{{ datasetName(item.dataset_id) }}</span>
          <el-tag :type="item.last_run_status === 'success' ? 'success' : 'info'" size="small" effect="plain">
            {{ item.status }}
          </el-tag>
        </button>
        <el-empty v-if="!pipelines.length" description="暂无管道" :image-size="72" />
      </aside>

      <main class="pipeline-main">
        <div class="pipeline-toolbar">
          <div>
            <h3>{{ selectedPipeline?.name || "选择一个数据加工管道" }}</h3>
            <span>{{ selectedPipeline ? `${flowNodes.length} 个节点 · ${flowEdges.length} 条依赖` : "DAG 将显示抽取、转换、质检、装载链路" }}</span>
          </div>
          <div class="hero-actions" v-if="selectedPipeline">
            <el-button :icon="VideoPlay" :loading="running" @click="runSelected('manual')">运行</el-button>
            <el-button type="warning" plain :icon="RefreshRight" :loading="running" @click="runSelected('backfill')">补数</el-button>
          </div>
        </div>

        <div class="flow-wrap">
          <VueFlow v-if="selectedPipeline" :nodes="flowNodes" :edges="flowEdges" fit-view-on-init class="pipeline-flow" />
          <el-empty v-else description="请选择或新建管道" />
        </div>

        <section class="pipeline-bottom">
          <el-card shadow="never">
            <template #header>
              <div class="card-header">
                <span>数据质量规则</span>
                <el-button v-if="selectedPipeline" size="small" :icon="Plus" @click="openRuleCreate">新增规则</el-button>
              </div>
            </template>
            <el-table :data="qualityRules" size="small" empty-text="暂无质量规则">
              <el-table-column prop="name" label="规则" min-width="140" />
              <el-table-column prop="rule_type" label="类型" width="110" />
              <el-table-column prop="field" label="字段" width="120" />
              <el-table-column prop="severity" label="级别" width="90">
                <template #default="{ row }">
                  <el-tag :type="row.severity === 'error' ? 'danger' : 'warning'" size="small" effect="plain">{{ row.severity }}</el-tag>
                </template>
              </el-table-column>
            </el-table>
          </el-card>

          <el-card shadow="never">
            <template #header>最近运行</template>
            <div class="run-summary" v-if="lastRun">
              <el-tag type="success" effect="plain">成功</el-tag>
              <strong>{{ lastRun.mode === "backfill" ? "补数" : "手动运行" }}</strong>
              <span>读取 {{ lastRun.records_read }} 行，写入 {{ lastRun.records_written }} 行</span>
            </div>
            <el-empty v-else description="暂无运行记录" :image-size="72" />
          </el-card>
        </section>
      </main>
    </section>

    <el-dialog v-model="dialogVisible" title="新建数据加工管道" width="min(720px, calc(100vw - 32px))" destroy-on-close>
      <el-form label-position="top">
        <el-row :gutter="16">
          <el-col :xs="24" :md="12">
            <el-form-item label="管道名称">
              <el-input v-model="form.name" placeholder="例：ERP 到经营数据集" />
            </el-form-item>
          </el-col>
          <el-col :xs="24" :md="12">
            <el-form-item label="目标数据集">
              <el-select v-model="form.dataset_id" placeholder="选择数据集" style="width: 100%">
                <el-option v-for="dataset in datasets" :key="dataset.id" :label="dataset.name" :value="dataset.id" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="调度">
          <el-input v-model="form.schedule_cron" placeholder="0 2 * * *" />
        </el-form-item>
        <el-alert type="info" :closable="false" show-icon title="默认生成 抽取 -> 清洗 -> 质量校验 -> 写入数据集 的 DAG，可保存后继续扩展节点。" />
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="savePipeline">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="ruleDialogVisible" title="新增质量规则" width="520px" destroy-on-close>
      <el-form label-position="top">
        <el-form-item label="规则名称">
          <el-input v-model="ruleForm.name" placeholder="例：关键指标不能为空" />
        </el-form-item>
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="规则类型">
              <el-select v-model="ruleForm.rule_type" style="width: 100%">
                <el-option label="非空" value="not_null" />
                <el-option label="唯一" value="unique" />
                <el-option label="范围" value="range" />
                <el-option label="新鲜度" value="freshness" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="字段">
              <el-input v-model="ruleForm.field" placeholder="字段名" />
            </el-form-item>
          </el-col>
        </el-row>
      </el-form>
      <template #footer>
        <el-button @click="ruleDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="savingRule" @click="saveRule">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue"
import axios from "axios"
import { ElMessage } from "element-plus"
import { Plus, Refresh, RefreshRight, VideoPlay } from "@element-plus/icons-vue"
import { VueFlow } from "@vue-flow/core"
import "@vue-flow/core/dist/style.css"
import "@vue-flow/core/dist/theme-default.css"

type DatasetItem = { id: number; name: string }
type Pipeline = {
  id: number
  name: string
  dataset_id: number
  dag_json: { nodes?: Array<Record<string, any>>; edges?: Array<Record<string, any>> }
  status: string
  last_run_status?: string | null
}
type QualityRule = { id: number; name: string; rule_type: string; field?: string | null; severity: string }
type PipelineRun = { id: number; mode: string; records_read: number; records_written: number }

const loading = ref(false)
const saving = ref(false)
const running = ref(false)
const savingRule = ref(false)
const dialogVisible = ref(false)
const ruleDialogVisible = ref(false)
const selectedId = ref<number | null>(null)
const pipelines = ref<Pipeline[]>([])
const datasets = ref<DatasetItem[]>([])
const qualityRules = ref<QualityRule[]>([])
const lastRun = ref<PipelineRun | null>(null)
const form = reactive({ name: "", dataset_id: null as number | null, schedule_cron: "0 2 * * *" })
const ruleForm = reactive({ name: "", rule_type: "not_null", field: "", severity: "error" })

const selectedPipeline = computed(() => pipelines.value.find((item) => item.id === selectedId.value) || pipelines.value[0] || null)
const flowNodes = computed(() => {
  const nodes = selectedPipeline.value?.dag_json?.nodes || []
  return nodes.map((node, index) => ({
    id: String(node.id),
    label: String(node.label || node.id),
    position: { x: 80 + (index % 3) * 220, y: 70 + Math.floor(index / 3) * 120 },
    data: { type: node.type || "task" },
  }))
})
const flowEdges = computed(() => {
  const edges = selectedPipeline.value?.dag_json?.edges || []
  return edges.map((edge, index) => ({
    id: `edge-${index}`,
    source: String(edge.source),
    target: String(edge.target),
    animated: true,
  }))
})

const datasetName = (id: number) => datasets.value.find((item) => item.id === id)?.name || `数据集 #${id}`

const defaultDag = () => ({
  nodes: [
    { id: "extract", type: "extract", label: "抽取源数据" },
    { id: "transform", type: "transform", label: "清洗转换" },
    { id: "quality", type: "quality", label: "质量校验" },
    { id: "load", type: "load", label: "写入数据集" },
  ],
  edges: [
    { source: "extract", target: "transform" },
    { source: "transform", target: "quality" },
    { source: "quality", target: "load" },
  ],
})

const loadQualityRules = async () => {
  if (!selectedPipeline.value) {
    qualityRules.value = []
    return
  }
  const { data } = await axios.get("/api/quality-rules", { params: { pipeline_id: selectedPipeline.value.id } })
  qualityRules.value = data || []
}

const loadAll = async () => {
  loading.value = true
  try {
    const [pipelineResp, datasetResp] = await Promise.all([
      axios.get("/api/pipelines"),
      axios.get("/api/datasets"),
    ])
    pipelines.value = pipelineResp.data || []
    datasets.value = datasetResp.data.items || []
    selectedId.value = selectedPipeline.value?.id || pipelines.value[0]?.id || null
    await loadQualityRules()
  } catch (error: any) {
    ElMessage.error(error.response?.data?.detail || "数据加工管道加载失败")
  } finally {
    loading.value = false
  }
}

const openCreate = () => {
  form.name = ""
  form.dataset_id = datasets.value[0]?.id || null
  form.schedule_cron = "0 2 * * *"
  dialogVisible.value = true
}

const savePipeline = async () => {
  if (!form.name.trim() || !form.dataset_id) {
    ElMessage.warning("请填写管道名称并选择数据集")
    return
  }
  saving.value = true
  try {
    const { data } = await axios.post("/api/pipelines", {
      name: form.name,
      dataset_id: form.dataset_id,
      schedule_cron: form.schedule_cron,
      dag_json: defaultDag(),
    })
    ElMessage.success("数据加工管道已创建")
    dialogVisible.value = false
    await loadAll()
    selectedId.value = data.id
  } catch (error: any) {
    ElMessage.error(error.response?.data?.detail || "保存失败")
  } finally {
    saving.value = false
  }
}

const runSelected = async (mode: "manual" | "backfill") => {
  if (!selectedPipeline.value) return
  running.value = true
  try {
    const { data } = await axios.post(`/api/pipelines/${selectedPipeline.value.id}/run`, {
      mode,
      reason: mode === "backfill" ? "界面触发补数" : "界面手动运行",
    })
    lastRun.value = data
    ElMessage.success(mode === "backfill" ? "补数任务执行完成" : "管道运行完成")
    await loadAll()
  } catch (error: any) {
    ElMessage.error(error.response?.data?.detail || "运行失败")
  } finally {
    running.value = false
  }
}

const openRuleCreate = () => {
  ruleForm.name = ""
  ruleForm.rule_type = "not_null"
  ruleForm.field = ""
  ruleForm.severity = "error"
  ruleDialogVisible.value = true
}

const saveRule = async () => {
  if (!selectedPipeline.value || !ruleForm.name.trim()) return
  savingRule.value = true
  try {
    await axios.post("/api/quality-rules", {
      ...ruleForm,
      pipeline_id: selectedPipeline.value.id,
      dataset_id: selectedPipeline.value.dataset_id,
    })
    ElMessage.success("质量规则已保存")
    ruleDialogVisible.value = false
    await loadQualityRules()
  } catch (error: any) {
    ElMessage.error(error.response?.data?.detail || "质量规则保存失败")
  } finally {
    savingRule.value = false
  }
}

onMounted(loadAll)
</script>

<style scoped>
.enterprise-hero,
.pipeline-list,
.pipeline-main,
.pipeline-bottom :deep(.el-card) {
  background: #ffffff;
  border: 1px solid var(--app-border);
  border-radius: var(--app-radius);
}

.enterprise-hero {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  padding: 20px;
}

.enterprise-hero h2,
.pipeline-toolbar h3 {
  margin: 4px 0 8px;
  letter-spacing: 0;
}

.enterprise-hero p,
.pipeline-toolbar span,
.pipeline-item span,
.run-summary span {
  color: var(--app-text-muted);
}

.eyebrow {
  color: var(--app-primary);
  font-size: 12px;
  font-weight: 700;
}

.hero-actions,
.pipeline-toolbar,
.card-header,
.run-summary {
  display: flex;
  align-items: center;
  gap: 8px;
}

.pipeline-layout {
  display: grid;
  grid-template-columns: 280px minmax(0, 1fr);
  gap: 16px;
}

.pipeline-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 16px;
}

.panel-title {
  font-weight: 700;
  margin-bottom: 8px;
}

.pipeline-item {
  display: grid;
  grid-template-columns: 1fr auto;
  gap: 4px 8px;
  width: 100%;
  padding: 12px;
  text-align: left;
  background: #ffffff;
  border: 1px solid var(--app-border);
  border-radius: var(--app-radius-sm);
  cursor: pointer;
}

.pipeline-item.active {
  border-color: var(--app-primary);
  background: rgba(15, 118, 110, 0.06);
}

.pipeline-item span {
  grid-column: 1 / -1;
}

.pipeline-main {
  padding: 16px;
  min-width: 0;
}

.pipeline-toolbar {
  justify-content: space-between;
  margin-bottom: 12px;
}

.flow-wrap {
  height: 360px;
  overflow: hidden;
  border: 1px solid var(--app-border);
  border-radius: var(--app-radius-sm);
  background: #f8fafc;
}

.pipeline-flow {
  height: 100%;
}

.pipeline-bottom {
  display: grid;
  grid-template-columns: 1fr 360px;
  gap: 12px;
  margin-top: 12px;
}

.run-summary {
  min-height: 108px;
  align-items: flex-start;
  flex-direction: column;
}

@media (max-width: 1000px) {
  .enterprise-hero,
  .pipeline-toolbar,
  .hero-actions {
    align-items: stretch;
    flex-direction: column;
  }

  .pipeline-layout,
  .pipeline-bottom {
    grid-template-columns: 1fr;
  }
}
</style>
