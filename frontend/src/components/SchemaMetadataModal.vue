<template>
  <el-dialog
    v-model="visible"
    title="表结构管理"
    width="900px"
    :close-on-click-modal="false"
    @close="handleClose"
  >
    <div class="schema-modal">
      <!-- Toolbar -->
      <div class="schema-toolbar">
        <el-button type="primary" size="small" @click="detectSchema" :loading="detecting">
          <el-icon><RefreshRight /></el-icon>
          自动检测
        </el-button>
        <el-button size="small" @click="addTable">
          <el-icon><Plus /></el-icon>
          添加表
        </el-button>
        <el-button size="small" @click="addRelationship">
          <el-icon><Connection /></el-icon>
          添加关联
        </el-button>
      </div>

      <!-- Tables Accordion -->
      <el-collapse v-model="activeTableNames" class="tables-collapse">
        <el-collapse-item
          v-for="(table, tableIndex) in schema.tables"
          :key="table.name"
          :name="table.name"
        >
          <template #title>
            <div class="table-header">
              <el-icon><Grid /></el-icon>
              <span class="table-name">{{ table.name }}</span>
              <el-tag size="small" type="info">{{ table.columns.length }} 列</el-tag>
              <span v-if="table.description" class="table-desc">{{ table.description }}</span>
            </div>
          </template>
          
          <div class="table-content">
            <!-- Table Info -->
            <el-form :inline="true" size="small" class="table-info-form">
              <el-form-item label="表名">
                <el-input v-model="table.name" style="width: 150px" />
              </el-form-item>
              <el-form-item label="描述">
                <el-input v-model="table.description" style="width: 200px" placeholder="表的中文描述" />
              </el-form-item>
              <el-form-item>
                <el-button type="danger" size="small" text @click="removeTable(tableIndex)">
                  删除表
                </el-button>
              </el-form-item>
            </el-form>

            <!-- Columns Table -->
            <el-table :data="table.columns" size="small" border class="columns-table">
              <el-table-column prop="name" label="列名" width="150">
                <template #default="{ row }">
                  <el-input v-model="row.name" size="small" />
                </template>
              </el-table-column>
              <el-table-column prop="type" label="类型" width="120">
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
              <el-table-column prop="description" label="说明" min-width="200">
                <template #default="{ row }">
                  <el-input v-model="row.description" size="small" placeholder="列的中文说明" />
                </template>
              </el-table-column>
              <el-table-column label="操作" width="80" align="center">
                <template #default="{ $index }">
                  <el-button type="danger" size="small" text @click="removeColumn(tableIndex, $index)">
                    <el-icon><Delete /></el-icon>
                  </el-button>
                </template>
              </el-table-column>
            </el-table>
            
            <el-button size="small" text type="primary" @click="addColumn(tableIndex)" class="add-column-btn">
              <el-icon><Plus /></el-icon>
              添加列
            </el-button>
          </div>
        </el-collapse-item>
      </el-collapse>

      <!-- Relationships -->
      <div class="relationships-section" v-if="schema.relationships.length > 0">
        <div class="section-title">
          <el-icon><Connection /></el-icon>
          表关联关系
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
      </div>

      <!-- Empty State -->
      <el-empty v-if="schema.tables.length === 0" description="暂无表结构，请点击「自动检测」或手动添加" />
    </div>

    <template #footer>
      <el-button @click="handleClose">取消</el-button>
      <el-button type="primary" @click="handleSave" :loading="saving">保存</el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, reactive, watch, computed } from 'vue'
import { ElMessage } from 'element-plus'
import { RefreshRight, Plus, Delete, Grid, Connection } from '@element-plus/icons-vue'
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

const activeTableNames = ref<string[]>([])
const detecting = ref(false)
const saving = ref(false)

// Initialize schema from props
watch(() => props.initialSchema, (newVal) => {
  if (newVal) {
    schema.tables = JSON.parse(JSON.stringify(newVal.tables || []))
    schema.relationships = JSON.parse(JSON.stringify(newVal.relationships || []))
    activeTableNames.value = schema.tables.map(t => t.name)
  } else {
    schema.tables = []
    schema.relationships = []
    activeTableNames.value = []
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
    activeTableNames.value = schema.tables.map(t => t.name)
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
  activeTableNames.value.push(newName)
}

const removeTable = (index: number) => {
  const tableName = schema.tables[index].name
  schema.tables.splice(index, 1)
  activeTableNames.value = activeTableNames.value.filter(n => n !== tableName)
  // Remove related relationships
  schema.relationships = schema.relationships.filter(
    r => r.from_table !== tableName && r.to_table !== tableName
  )
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

const getTableColumns = (tableName: string): Column[] => {
  const table = schema.tables.find(t => t.name === tableName)
  return table?.columns || []
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
  max-height: 60vh;
  overflow-y: auto;
}

.schema-toolbar {
  display: flex;
  gap: 8px;
  margin-bottom: 16px;
  padding-bottom: 16px;
  border-bottom: 1px solid var(--app-border-light);
}

.tables-collapse {
  border: none;
}

.tables-collapse :deep(.el-collapse-item__header) {
  background: var(--app-surface-muted);
  padding: 0 16px;
  border-radius: 8px;
  margin-bottom: 8px;
}

.tables-collapse :deep(.el-collapse-item__wrap) {
  border: none;
}

.tables-collapse :deep(.el-collapse-item__content) {
  padding: 16px;
  background: var(--app-surface);
  border: 1px solid var(--app-border-light);
  border-radius: 0 0 8px 8px;
  margin-top: -8px;
  margin-bottom: 12px;
}

.table-header {
  display: flex;
  align-items: center;
  gap: 8px;
  flex: 1;
}

.table-name {
  font-weight: 600;
  color: var(--app-primary);
}

.table-desc {
  color: var(--app-text-muted);
  font-size: 13px;
  margin-left: auto;
}

.table-content {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.table-info-form {
  margin-bottom: 8px;
}

.columns-table {
  border-radius: 8px;
  overflow: hidden;
}

.add-column-btn {
  margin-top: 8px;
}

.relationships-section {
  margin-top: 24px;
  padding-top: 16px;
  border-top: 1px solid var(--app-border-light);
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
</style>
