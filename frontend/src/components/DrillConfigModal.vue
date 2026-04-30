<template>
  <el-dialog
    v-model="visible"
    title="钻取规则配置"
    width="min(1180px, calc(100vw - 32px))"
    class="governance-modal drill-governance-dialog"
    :close-on-click-modal="false"
    @close="handleClose"
  >
    <div class="drill-modal">
      <aside class="drill-rail">
        <div class="drill-toolbar-info">
          <p class="modal-kicker">DRILL PATHS</p>
          <h3>{{ datasourceName || "当前数据源" }}</h3>
          <span>配置图表点击后的下钻路径。</span>
        </div>
        <el-button type="primary" @click="emit('generate')" :loading="generating">自动生成候选规则</el-button>

        <div class="drill-metrics">
          <div>
            <span>启用维度</span>
            <strong>{{ enabledDimensionCount }}/{{ draft.dimensions.length }}</strong>
          </div>
          <div>
            <span>启用指标</span>
            <strong>{{ enabledMetricCount }}/{{ draft.metrics.length }}</strong>
          </div>
          <div>
            <span>可用路径</span>
            <strong>{{ enabledPathCount }}/{{ draft.paths.length }}</strong>
          </div>
        </div>

        <div class="drill-flow">
          <div class="drill-flow-item" :class="{ 'is-done': draft.dimensions.length > 0 || draft.metrics.length > 0 }">
            <strong>生成候选</strong>
            <span>识别维度和指标</span>
          </div>
          <div class="drill-flow-item" :class="{ 'is-done': enabledDimensionCount > 0 && enabledMetricCount > 0 }">
            <strong>人工确认</strong>
            <span>保留可用字段</span>
          </div>
          <div class="drill-flow-item" :class="{ 'is-done': enabledPathCount > 0 }">
            <strong>路径生效</strong>
            <span>图表可继续下钻</span>
          </div>
        </div>
      </aside>

      <section class="drill-content">
        <el-empty
          v-if="draft.dimensions.length === 0 && draft.metrics.length === 0 && draft.paths.length === 0"
          class="drill-empty"
          description="还没有钻取配置，先点击“自动生成候选规则”"
        />

        <div v-else class="drill-sections">
          <section class="drill-section">
            <div class="section-header">
              <div>
                <span>维度候选</span>
                <small>选择可下钻对象。</small>
              </div>
              <el-tag size="small" type="info">{{ draft.dimensions.length }}</el-tag>
            </div>
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
          </section>

          <section class="drill-section">
            <div class="section-header">
              <div>
                <span>指标候选</span>
                <small>选择默认指标。</small>
              </div>
              <el-tag size="small" type="info">{{ draft.metrics.length }}</el-tag>
            </div>
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
          </section>

          <section class="drill-section">
            <div class="section-header">
              <div>
                <span>钻取路径</span>
                <small>配置点击入口。</small>
              </div>
              <el-tag size="small" type="info">{{ draft.paths.length }}</el-tag>
            </div>
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
          </section>
        </div>
      </section>
    </div>

    <template #footer>
      <div class="governance-modal-footer">
        <span class="governance-modal-footer-note">保存后图表会显示下钻入口。</span>
        <div class="governance-modal-footer-actions">
          <el-button @click="handleClose">取消</el-button>
          <el-button type="primary" :loading="saving" @click="handleSave">保存配置</el-button>
        </div>
      </div>
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

const enabledDimensionCount = computed(() => draft.dimensions.filter(item => item.enabled).length)
const enabledMetricCount = computed(() => draft.metrics.filter(item => item.enabled).length)
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
  display: grid;
  grid-template-columns: 280px minmax(0, 1fr);
  height: min(680px, calc(100vh - 178px));
  min-height: 0;
  overflow: hidden;
}

.drill-rail {
  display: flex;
  flex-direction: column;
  gap: 12px;
  min-height: 0;
  padding: 16px;
  overflow-y: auto;
  border-right: 1px solid var(--app-border-light);
  background: #f3f7fa;
}

.drill-content {
  min-width: 0;
  min-height: 0;
  overflow-y: auto;
  padding: 20px;
}

.modal-kicker {
  margin: 0 0 6px;
  color: var(--app-primary);
  font-size: 12px;
  font-weight: 700;
}

.drill-toolbar-info h3 {
  margin: 0;
  font-size: 18px;
  font-weight: 700;
  color: var(--app-text);
}

.drill-toolbar-info span {
  display: block;
  margin-top: 8px;
  color: var(--app-text-muted);
  font-size: 13px;
  line-height: 1.6;
}

.drill-metrics {
  display: grid;
  grid-template-columns: 1fr;
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
  font-size: 18px;
}

.drill-flow {
  display: grid;
  gap: 10px;
}

.drill-flow-item {
  padding: 12px;
  border: 1px solid var(--app-border-light);
  border-radius: var(--app-radius);
  background: rgba(255, 255, 255, 0.78);
}

.drill-flow-item.is-done {
  border-color: rgba(18, 128, 92, 0.28);
  background: rgba(18, 128, 92, 0.07);
}

.drill-flow-item strong {
  display: block;
  color: var(--app-text);
  font-size: 13px;
}

.drill-flow-item span {
  display: block;
  margin-top: 4px;
  color: var(--app-text-muted);
  font-size: 12px;
  line-height: 1.45;
}

.drill-empty {
  min-height: 420px;
  border: 1px dashed var(--app-border);
  border-radius: var(--app-radius);
  background: var(--app-surface);
}

.drill-sections {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.drill-section {
  padding: 16px;
  border: 1px solid var(--app-border-light);
  border-radius: var(--app-radius);
  background: var(--app-surface);
}

.section-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
}

.section-header span {
  color: var(--app-text);
  font-weight: 700;
}

.section-header small {
  display: block;
  margin-top: 4px;
  color: var(--app-text-muted);
  font-size: 12px;
}

@media (max-width: 900px) {
  .drill-modal {
    grid-template-columns: 1fr;
    max-height: none;
  }

  .drill-rail {
    border-right: 0;
    border-bottom: 1px solid var(--app-border-light);
  }

  .drill-metrics {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
}

@media (max-width: 640px) {
  .drill-metrics {
    grid-template-columns: 1fr;
  }
}
</style>
