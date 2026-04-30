<template>
  <el-dialog
    v-model="visible"
    title="表结构管理"
    width="min(1200px, calc(100vw - 32px))"
    class="governance-modal schema-governance-dialog"
    :close-on-click-modal="false"
    @close="handleClose"
  >
    <div class="schema-modal">
      <div class="schema-hero">
        <div>
          <p class="modal-kicker">SCHEMA SEMANTICS</p>
          <h3>让系统理解业务表结构</h3>
          <p>表、字段和关联关系会生成元数据提示词，直接影响智能问数和数据集建模质量。</p>
        </div>
        <div class="schema-toolbar">
          <el-button type="primary" @click="detectSchema" :loading="detecting">
            <el-icon><RefreshRight /></el-icon>
            自动检测
          </el-button>
          <el-button @click="addTable">
            <el-icon><Plus /></el-icon>
            添加表
          </el-button>
        </div>
      </div>

      <div class="schema-flow">
        <div class="schema-flow-item" :class="{ 'is-done': schema.tables.length > 0 }">
          <strong>自动检测</strong>
          <span>读取数据表和字段</span>
        </div>
        <div class="schema-flow-item" :class="{ 'is-done': totalColumns > 0 }">
          <strong>补字段说明</strong>
          <span>把字段翻译成业务语义</span>
        </div>
        <div class="schema-flow-item" :class="{ 'is-done': schema.relationships.length > 0 }">
          <strong>确认关联</strong>
          <span>维护主外键和 Join 关系</span>
        </div>
        <div class="schema-flow-item">
          <strong>保存生效</strong>
          <span>生成问数元数据提示词</span>
        </div>
      </div>

      <div class="schema-metrics">
        <div>
          <span>数据表</span>
          <strong>{{ schema.tables.length }}</strong>
        </div>
        <div>
          <span>字段</span>
          <strong>{{ totalColumns }}</strong>
        </div>
        <div>
          <span>关联关系</span>
          <strong>{{ schema.relationships.length }}</strong>
        </div>
      </div>

      <el-empty
        v-if="schema.tables.length === 0"
        description="暂无表结构，请点击「自动检测」或手动添加"
      />

      <div v-else class="schema-workspace">
        <aside class="schema-sidebar">
          <div class="sidebar-header">
            <span class="sidebar-title">数据表</span>
            <el-tag size="small" type="info">{{ schema.tables.length }}</el-tag>
          </div>

          <div class="table-nav">
            <button
              v-for="(table, tableIndex) in schema.tables"
              :key="`${table.name}-${tableIndex}`"
              type="button"
              class="table-nav-item"
              :class="{ 'is-active': tableIndex === selectedTableIndex }"
              @click="selectTable(tableIndex)"
            >
              <span class="table-nav-main">
                <el-icon><Grid /></el-icon>
                <span class="table-nav-name">{{ table.name || `未命名表 ${tableIndex + 1}` }}</span>
              </span>
              <span class="table-nav-meta">{{ table.columns.length }} 列</span>
            </button>
          </div>
        </aside>

        <section class="schema-content">
          <div v-if="selectedTable" class="editor-panel">
            <div class="editor-header">
              <div class="editor-heading">
                <div class="editor-title-row">
                  <span class="editor-title">{{ selectedTable.name || "未命名表" }}</span>
                  <el-tag size="small" type="info">{{ selectedTable.columns.length }} 列</el-tag>
                </div>
                <span v-if="selectedTable.description" class="editor-desc">{{ selectedTable.description }}</span>
              </div>
              <div class="editor-header-actions">
                <el-button
                  size="small"
                  type="primary"
                  plain
                  :loading="generatingDescriptions"
                  @click="fillColumnDescriptions"
                >
                  <el-icon><MagicStick /></el-icon>
                  AI补全字段说明
                </el-button>
                <el-button type="danger" size="small" text @click="removeTable(selectedTableIndex)">
                  删除表
                </el-button>
              </div>
            </div>

            <el-form :inline="true" size="small" class="table-info-form">
              <el-form-item label="表名">
                <el-input v-model="selectedTable.name" style="width: 180px" />
              </el-form-item>
              <el-form-item label="描述">
                <el-input
                  v-model="selectedTable.description"
                  style="width: 260px"
                  placeholder="表的中文描述"
                />
              </el-form-item>
            </el-form>

            <el-tabs v-model="activeEditorTab" class="editor-tabs">
              <el-tab-pane label="字段管理" name="columns">
                <div class="tab-panel">
                  <el-table :data="selectedTable.columns" size="small" border class="columns-table">
                    <el-table-column prop="name" label="列名" width="180">
                      <template #default="{ row }">
                        <el-input v-model="row.name" size="small" />
                      </template>
                    </el-table-column>
                    <el-table-column prop="type" label="类型" width="140">
                      <template #default="{ row }">
                        <el-select v-model="row.type" size="small" style="width: 100%">
                          <el-option label="VARCHAR" value="VARCHAR" />
                          <el-option label="INTEGER" value="INTEGER" />
                          <el-option label="FLOAT" value="FLOAT" />
                          <el-option label="BOOLEAN" value="BOOLEAN" />
                          <el-option label="DATETIME" value="DATETIME" />
                          <el-option label="TEXT" value="TEXT" />
                        </el-select>
                      </template>
                    </el-table-column>
                    <el-table-column prop="description" label="说明" min-width="240">
                      <template #default="{ row }">
                        <el-input v-model="row.description" size="small" placeholder="列的中文说明" />
                      </template>
                    </el-table-column>
                    <el-table-column label="操作" width="80" align="center">
                      <template #default="{ $index }">
                        <el-button
                          type="danger"
                          size="small"
                          text
                          @click="removeColumn(selectedTableIndex, $index)"
                        >
                          <el-icon><Delete /></el-icon>
                        </el-button>
                      </template>
                    </el-table-column>
                  </el-table>

                  <el-button
                    size="small"
                    text
                    type="primary"
                    @click="addColumn(selectedTableIndex)"
                    class="add-column-btn"
                  >
                    <el-icon><Plus /></el-icon>
                    添加列
                  </el-button>
                </div>
              </el-tab-pane>

              <el-tab-pane label="关联关系" name="relationships">
                <div class="tab-panel">
                  <div class="relationships-toolbar">
                    <div class="section-title">
                      <el-icon><Connection /></el-icon>
                      表关联关系
                    </div>
                    <el-button size="small" type="primary" plain @click="addRelationship">
                      <el-icon><Plus /></el-icon>
                      添加关联
                    </el-button>
                  </div>

                  <el-table :data="schema.relationships" size="small" border>
                    <el-table-column label="来源表" width="150">
                      <template #default="{ row }">
                        <el-select v-model="row.from_table" size="small" style="width: 100%">
                          <el-option v-for="t in schema.tables" :key="t.name" :label="t.name" :value="t.name" />
                        </el-select>
                      </template>
                    </el-table-column>
                    <el-table-column label="来源列" width="150">
                      <template #default="{ row }">
                        <el-select v-model="row.from_column" size="small" style="width: 100%">
                          <el-option
                            v-for="c in getTableColumns(row.from_table)"
                            :key="c.name"
                            :label="c.name"
                            :value="c.name"
                          />
                        </el-select>
                      </template>
                    </el-table-column>
                    <el-table-column label="" width="50" align="center">
                      <template #default>→</template>
                    </el-table-column>
                    <el-table-column label="目标表" width="150">
                      <template #default="{ row }">
                        <el-select v-model="row.to_table" size="small" style="width: 100%">
                          <el-option v-for="t in schema.tables" :key="t.name" :label="t.name" :value="t.name" />
                        </el-select>
                      </template>
                    </el-table-column>
                    <el-table-column label="目标列" width="150">
                      <template #default="{ row }">
                        <el-select v-model="row.to_column" size="small" style="width: 100%">
                          <el-option
                            v-for="c in getTableColumns(row.to_table)"
                            :key="c.name"
                            :label="c.name"
                            :value="c.name"
                          />
                        </el-select>
                      </template>
                    </el-table-column>
                    <el-table-column label="操作" width="80" align="center">
                      <template #default="{ $index }">
                        <el-button type="danger" size="small" text @click="removeRelationship($index)">
                          <el-icon><Delete /></el-icon>
                        </el-button>
                      </template>
                    </el-table-column>
                  </el-table>

                  <el-empty
                    v-if="schema.relationships.length === 0"
                    description="暂无关联关系，可在这里手动添加"
                  />
                </div>
              </el-tab-pane>
            </el-tabs>
          </div>
          <el-empty v-else description="请选择左侧数据表开始编辑" />
        </section>
      </div>
    </div>

    <template #footer>
      <div class="governance-modal-footer">
        <span class="governance-modal-footer-note">保存后会同步更新 Text2SQL 的元数据提示词，影响问数和数据集建模结果。</span>
        <div class="governance-modal-footer-actions">
          <el-button @click="handleClose">取消</el-button>
          <el-button type="primary" @click="handleSave" :loading="saving">保存</el-button>
        </div>
      </div>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, reactive, watch, computed } from 'vue'
import { ElMessage } from 'element-plus'
import { RefreshRight, Plus, Delete, Grid, Connection, MagicStick } from '@element-plus/icons-vue'
import axios from 'axios'

interface Column {
  name: string
  type: string
  description: string | null
}

interface Table {
  name: string
  description: string | null
  columns: Column[]
}

interface Relationship {
  from_table: string
  from_column: string
  to_table: string
  to_column: string
}

interface Schema {
  tables: Table[]
  relationships: Relationship[]
}

const props = defineProps<{
  modelValue: boolean
  datasourceId: number | null
  initialSchema: Schema | null
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', value: boolean): void
  (e: 'save', schema: Schema): void
}>()

const visible = computed({
  get: () => props.modelValue,
  set: (val) => emit('update:modelValue', val)
})

const schema = reactive<Schema>({
  tables: [],
  relationships: []
})

const selectedTableIndex = ref(0)
const activeEditorTab = ref("columns")
const detecting = ref(false)
const saving = ref(false)
const generatingDescriptions = ref(false)

const selectedTable = computed<Table | null>(() => schema.tables[selectedTableIndex.value] || null)
const totalColumns = computed(() =>
  schema.tables.reduce((sum, table) => sum + table.columns.length, 0)
)

// Initialize schema from props
watch(() => props.initialSchema, (newVal) => {
  if (newVal) {
    schema.tables = JSON.parse(JSON.stringify(newVal.tables || []))
    schema.relationships = JSON.parse(JSON.stringify(newVal.relationships || []))
    selectedTableIndex.value = schema.tables.length > 0 ? 0 : -1
  } else {
    schema.tables = []
    schema.relationships = []
    selectedTableIndex.value = -1
  }
}, { immediate: true })

const detectSchema = async () => {
  if (!props.datasourceId) {
    ElMessage.warning('请先保存数据源')
    return
  }
  
  detecting.value = true
  try {
    const response = await axios.post(`/api/datasources/${props.datasourceId}/detect-schema`)
    schema.tables = response.data.tables || []
    schema.relationships = response.data.relationships || []
    selectedTableIndex.value = schema.tables.length > 0 ? 0 : -1
    activeEditorTab.value = "columns"
    ElMessage.success(`检测到 ${schema.tables.length} 个表`)
  } catch (error: any) {
    ElMessage.error(error.response?.data?.detail || '检测失败')
  } finally {
    detecting.value = false
  }
}

const addTable = () => {
  const newName = `table_${schema.tables.length + 1}`
  schema.tables.push({
    name: newName,
    description: null,
    columns: []
  })
  selectedTableIndex.value = schema.tables.length - 1
  activeEditorTab.value = "columns"
}

const removeTable = (index: number) => {
  if (index < 0 || index >= schema.tables.length) {
    return
  }
  const tableName = schema.tables[index].name
  schema.tables.splice(index, 1)
  // Remove related relationships
  schema.relationships = schema.relationships.filter(
    r => r.from_table !== tableName && r.to_table !== tableName
  )
  if (schema.tables.length === 0) {
    selectedTableIndex.value = -1
    return
  }
  if (selectedTableIndex.value >= schema.tables.length) {
    selectedTableIndex.value = schema.tables.length - 1
    return
  }
  if (index <= selectedTableIndex.value && selectedTableIndex.value > 0) {
    selectedTableIndex.value -= 1
  }
}

const addColumn = (tableIndex: number) => {
  schema.tables[tableIndex].columns.push({
    name: '',
    type: 'VARCHAR',
    description: null
  })
}

const removeColumn = (tableIndex: number, colIndex: number) => {
  schema.tables[tableIndex].columns.splice(colIndex, 1)
}

const addRelationship = () => {
  if (schema.tables.length < 2) {
    ElMessage.warning('至少需要2个表才能创建关联')
    return
  }
  schema.relationships.push({
    from_table: schema.tables[0]?.name || '',
    from_column: '',
    to_table: schema.tables[1]?.name || '',
    to_column: ''
  })
}

const removeRelationship = (index: number) => {
  schema.relationships.splice(index, 1)
}

const selectTable = (index: number) => {
  selectedTableIndex.value = index
}

const getTableColumns = (tableName: string): Column[] => {
  const table = schema.tables.find(t => t.name === tableName)
  return table?.columns || []
}

const fillColumnDescriptions = async () => {
  if (!props.datasourceId || !selectedTable.value) {
    ElMessage.warning('请先选择并保存数据源')
    return
  }

  generatingDescriptions.value = true
  try {
    const response = await axios.post(
      `/api/datasources/${props.datasourceId}/generate-column-descriptions`,
      selectedTable.value
    )
    schema.tables[selectedTableIndex.value] = response.data.table
    ElMessage.success(`已补全 ${response.data.filled_count || 0} 个字段说明`)
  } catch (error: any) {
    ElMessage.error(error.response?.data?.detail || '生成字段说明失败')
  } finally {
    generatingDescriptions.value = false
  }
}

const handleSave = () => {
  // Validate
  for (const table of schema.tables) {
    if (!table.name) {
      ElMessage.warning('表名不能为空')
      return
    }
    for (const col of table.columns) {
      if (!col.name) {
        ElMessage.warning(`表 ${table.name} 中存在空列名`)
        return
      }
    }
  }
  
  saving.value = true
  emit('save', { tables: schema.tables, relationships: schema.relationships })
  saving.value = false
}

const handleClose = () => {
  visible.value = false
}
</script>

<style scoped>
.schema-modal {
  padding: 20px;
  max-height: 68vh;
  overflow-y: auto;
}

.schema-hero {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: flex-start;
  padding: 16px;
  margin-bottom: 12px;
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

.schema-hero h3 {
  margin: 0;
  color: var(--app-text);
  font-size: 18px;
}

.schema-hero p:not(.modal-kicker) {
  margin: 8px 0 0;
  color: var(--app-text-muted);
  line-height: 1.6;
}

.schema-toolbar {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  justify-content: flex-end;
}

.schema-flow {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px;
  margin-bottom: 12px;
}

.schema-flow-item {
  position: relative;
  padding: 12px;
  border: 1px solid var(--app-border-light);
  border-radius: var(--app-radius);
  background: var(--app-surface);
}

.schema-flow-item.is-done {
  border-color: rgba(18, 128, 92, 0.28);
  background: rgba(18, 128, 92, 0.06);
}

.schema-flow-item strong {
  display: block;
  color: var(--app-text);
  font-size: 13px;
}

.schema-flow-item span {
  display: block;
  margin-top: 5px;
  color: var(--app-text-muted);
  font-size: 12px;
  line-height: 1.45;
}

.schema-metrics {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
  margin-bottom: 16px;
}

.schema-metrics div {
  padding: 12px;
  border: 1px solid var(--app-border-light);
  border-radius: 10px;
  background: var(--app-surface);
}

.schema-metrics span {
  display: block;
  margin-bottom: 6px;
  color: var(--app-text-muted);
  font-size: 12px;
}

.schema-metrics strong {
  color: var(--app-text);
  font-size: 20px;
}

.schema-workspace {
  display: grid;
  grid-template-columns: 240px minmax(0, 1fr);
  gap: 16px;
  min-height: 480px;
}

.schema-sidebar {
  border: 1px solid var(--app-border-light);
  border-radius: 12px;
  background: var(--app-surface-muted);
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 12px;
  max-height: 480px;
  overflow-y: auto;
}

.sidebar-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.sidebar-title {
  font-weight: 600;
  color: var(--app-text);
}

.table-nav {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.table-nav-item {
  width: 100%;
  border: 1px solid transparent;
  border-radius: 10px;
  background: var(--app-surface);
  padding: 12px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  cursor: pointer;
  text-align: left;
  transition: border-color 0.2s ease, background 0.2s ease;
}

.table-nav-item:hover,
.table-nav-item.is-active {
  border-color: var(--app-primary);
  background: color-mix(in srgb, var(--app-primary) 8%, white);
}

.table-nav-main {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}

.table-nav-name {
  font-weight: 600;
  color: var(--app-text);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.table-nav-meta {
  color: var(--app-text-muted);
  font-size: 12px;
  flex-shrink: 0;
}

.schema-content {
  min-width: 0;
}

.editor-panel {
  border: 1px solid var(--app-border-light);
  border-radius: 12px;
  background: var(--app-surface);
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 16px;
  min-height: 100%;
}

.editor-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
}

.editor-header-actions {
  display: flex;
  gap: 8px;
  align-items: center;
  flex-wrap: wrap;
  justify-content: flex-end;
  flex-shrink: 0;
}

.editor-heading {
  display: flex;
  flex-direction: column;
  gap: 6px;
  min-width: 0;
}

.editor-title-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.editor-title {
  font-size: 18px;
  font-weight: 700;
  color: var(--app-primary);
}

.editor-desc {
  color: var(--app-text-muted);
  font-size: 13px;
}

.table-info-form {
  margin-bottom: 0;
}

.editor-tabs {
  min-width: 0;
}

.tab-panel {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.columns-table {
  border-radius: 8px;
  overflow: hidden;
}

.add-column-btn {
  margin-top: 8px;
}

.relationships-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.section-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-weight: 600;
  margin-bottom: 12px;
  color: var(--app-text);
}

:deep(.el-empty) {
  padding: 40px 0;
}

@media (max-width: 960px) {
  .schema-workspace {
    grid-template-columns: 1fr;
  }

  .schema-hero {
    flex-direction: column;
  }

  .schema-toolbar {
    justify-content: flex-start;
  }

  .schema-flow {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 640px) {
  .schema-metrics,
  .schema-flow {
    grid-template-columns: 1fr;
  }

  .editor-header,
  .editor-header-actions {
    align-items: stretch;
    flex-direction: column;
  }
}
</style>
