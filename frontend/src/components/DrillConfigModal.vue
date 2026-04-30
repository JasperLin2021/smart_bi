<template>
  <el-dialog
    v-model="visible"
    title="钻取规则配置"
    width="min(1180px, calc(100vw - 32px))"
    :close-on-click-modal="false"
    @close="handleClose"
  >
    <div class="drill-modal">
      <div class="drill-toolbar">
        <div class="drill-toolbar-info">
          <p class="modal-kicker">DRILL PATHS</p>
          <div class="drill-toolbar-title">{{ datasourceName || "当前数据源" }}</div>
          <div class="drill-toolbar-subtitle">把字段关系转成业务能点击的下钻路径，支持从总览自然定位到明细。</div>
        </div>
        <el-button type="primary" @click="emit('generate')" :loading="generating">自动生成候选规则</el-button>
      </div>

      <div class="drill-metrics">
        <div>
          <span>维度候选</span>
          <strong>{{ draft.dimensions.length }}</strong>
        </div>
        <div>
          <span>指标候选</span>
          <strong>{{ draft.metrics.length }}</strong>
        </div>
        <div>
          <span>可用路径</span>
          <strong>{{ enabledPathCount }}</strong>
        </div>
      </div>

      <el-empty
        v-if="draft.dimensions.length === 0 && draft.metrics.length === 0 && draft.paths.length === 0"
        description="还没有钻取配置，先点击“自动生成候选规则”"
      />

      <div v-else class="drill-sections">
        <el-card shadow="never" class="drill-section">
          <template #header>
            <div class="section-header">
              <span>维度候选</span>
              <el-tag size="small" type="info">{{ draft.dimensions.length }}</el-tag>
            </div>
          </template>
          <el-table :data="draft.dimensions" size="small" border>
            <el-table-column label="启用" width="80" align="center">
              <template #default="{ row }">
                <el-switch v-model="row.enabled" />
              </template>
            </el-table-column>
            <el-table-column prop="table" label="表" width="130" />
            <el-table-column prop="column" label="字段" width="140" />
            <el-table-column prop="kind" label="类型" width="110" />
            <el-table-column label="显示名" min-width="220">
              <template #default="{ row }">
                <el-input v-model="row.label" size="small" />
              </template>
            </el-table-column>
          </el-table>
        </el-card>

        <el-card shadow="never" class="drill-section">
          <template #header>
            <div class="section-header">
              <span>指标候选</span>
              <el-tag size="small" type="info">{{ draft.metrics.length }}</el-tag>
            </div>
          </template>
          <el-table :data="draft.metrics" size="small" border>
            <el-table-column label="启用" width="80" align="center">
              <template #default="{ row }">
                <el-switch v-model="row.enabled" />
              </template>
            </el-table-column>
            <el-table-column prop="table" label="表" width="130" />
            <el-table-column prop="column" label="字段" width="140" />
            <el-table-column prop="aggregation" label="聚合" width="110" />
            <el-table-column label="显示名" min-width="220">
              <template #default="{ row }">
                <el-input v-model="row.label" size="small" />
              </template>
            </el-table-column>
          </el-table>
        </el-card>

        <el-card shadow="never" class="drill-section">
          <template #header>
            <div class="section-header">
              <span>钻取路径</span>
              <el-tag size="small" type="info">{{ draft.paths.length }}</el-tag>
            </div>
          </template>
          <el-table :data="draft.paths" size="small" border>
            <el-table-column label="启用" width="80" align="center">
              <template #default="{ row }">
                <el-switch v-model="row.enabled" />
              </template>
            </el-table-column>
            <el-table-column label="起点" min-width="220">
              <template #default="{ row }">
                {{ dimensionLabelMap[row.source_dimension_id] || row.source_dimension_id }}
              </template>
            </el-table-column>
            <el-table-column label="目标" min-width="220">
              <template #default="{ row }">
                {{ dimensionLabelMap[row.target_dimension_id] || row.target_dimension_id }}
              </template>
            </el-table-column>
            <el-table-column label="按钮文案" min-width="220">
              <template #default="{ row }">
                <el-input v-model="row.label" size="small" />
              </template>
            </el-table-column>
            <el-table-column label="动作" width="120">
              <template #default="{ row }">
                <el-select v-model="row.action" size="small">
                  <el-option label="分组下钻" value="group_by" />
                  <el-option label="查看明细" value="detail" />
                </el-select>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </div>
    </div>

    <template #footer>
      <el-button @click="handleClose">取消</el-button>
      <el-button type="primary" :loading="saving" @click="handleSave">保存配置</el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { computed, reactive, watch } from "vue"

interface DrillDimension {
  id: string
  table: string
  column: string
  label: string
  kind: string
  enabled: boolean
}

interface DrillMetric {
  id: string
  table: string
  column: string
  label: string
  aggregation: string
  enabled: boolean
}

interface DrillPath {
  id: string
  source_dimension_id: string
  target_dimension_id: string
  label: string
  action: string
  enabled: boolean
}

interface DrillConfig {
  dimensions: DrillDimension[]
  metrics: DrillMetric[]
  paths: DrillPath[]
}

const props = defineProps<{
  modelValue: boolean
  datasourceName: string
  config: DrillConfig | null
  generating: boolean
  saving: boolean
}>()

const emit = defineEmits<{
  (e: "update:modelValue", value: boolean): void
  (e: "save", config: DrillConfig): void
  (e: "generate"): void
}>()

const visible = computed({
  get: () => props.modelValue,
  set: (value: boolean) => emit("update:modelValue", value),
})

const draft = reactive<DrillConfig>({
  dimensions: [],
  metrics: [],
  paths: [],
})

const cloneConfig = (config: DrillConfig | null) => ({
  dimensions: JSON.parse(JSON.stringify(config?.dimensions || [])),
  metrics: JSON.parse(JSON.stringify(config?.metrics || [])),
  paths: JSON.parse(JSON.stringify(config?.paths || [])),
})

watch(
  () => props.config,
  (config) => {
    const next = cloneConfig(config)
    draft.dimensions = next.dimensions
    draft.metrics = next.metrics
    draft.paths = next.paths
  },
  { immediate: true }
)

const dimensionLabelMap = computed<Record<string, string>>(() =>
  Object.fromEntries(draft.dimensions.map((item) => [item.id, item.label]))
)

const enabledPathCount = computed(() => draft.paths.filter(item => item.enabled).length)

const handleSave = () => {
  emit("save", cloneConfig(draft))
}

const handleClose = () => {
  visible.value = false
}
</script>

<style scoped>
.drill-modal {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.drill-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
  padding: 16px;
  border: 1px solid var(--app-border-light);
  border-radius: 12px;
  background: var(--app-surface-muted);
}

.modal-kicker {
  margin: 0 0 6px;
  color: var(--app-primary);
  font-size: 12px;
  font-weight: 700;
}

.drill-toolbar-title {
  font-size: 16px;
  font-weight: 700;
  color: var(--app-text);
}

.drill-toolbar-subtitle {
  margin-top: 4px;
  color: var(--app-text-muted);
  font-size: 13px;
}

.drill-metrics {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
}

.drill-metrics div {
  padding: 12px;
  border: 1px solid var(--app-border-light);
  border-radius: 10px;
  background: var(--app-surface);
}

.drill-metrics span {
  display: block;
  margin-bottom: 6px;
  color: var(--app-text-muted);
  font-size: 12px;
}

.drill-metrics strong {
  color: var(--app-text);
  font-size: 20px;
}

.drill-sections {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.drill-section {
  border: 1px solid var(--app-border-light);
}

.section-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

@media (max-width: 760px) {
  .drill-toolbar {
    align-items: stretch;
    flex-direction: column;
  }

  .drill-metrics {
    grid-template-columns: 1fr;
  }
}
</style>
