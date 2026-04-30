<template>
  <div class="dataset-page">
    <section class="dataset-hero">
      <div>
        <p class="eyebrow">DATASET CENTER</p>
        <h2>数据集中心</h2>
        <p class="hero-copy">
          {{ datasourceStore.datasources.length }} 个数据源，{{ datasetStats.published }} 个已发布数据集
        </p>
      </div>
      <div class="hero-actions">
        <el-input
          v-model="keyword"
          :prefix-icon="Search"
          class="search-input"
          clearable
          placeholder="搜索数据集 / 数据源"
        />
        <el-segmented v-model="statusFilter" :options="statusOptions" @change="fetchDatasets" />
        <el-button type="primary" :icon="Plus" @click="openCreate">新建数据集</el-button>
      </div>
    </section>

    <section class="summary-grid">
      <div class="summary-card">
        <span class="summary-label">全部数据集</span>
        <strong>{{ datasetStats.total }}</strong>
      </div>
      <div class="summary-card">
        <span class="summary-label">已发布</span>
        <strong>{{ datasetStats.published }}</strong>
      </div>
      <div class="summary-card">
        <span class="summary-label">草稿</span>
        <strong>{{ datasetStats.draft }}</strong>
      </div>
      <div class="summary-card">
        <span class="summary-label">可用数据源</span>
        <strong>{{ datasourceStore.datasources.length }}</strong>
      </div>
    </section>

    <el-card class="dataset-card" shadow="never">
      <el-table
        v-loading="loading"
        :data="filteredDatasets"
        row-key="id"
        empty-text="暂无数据集"
        @row-click="openEdit"
      >
        <el-table-column min-width="220" label="数据集">
          <template #default="{ row }">
            <div class="dataset-name-cell">
              <strong>{{ row.name }}</strong>
              <span>{{ row.description || "未填写描述" }}</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="数据源" min-width="170">
          <template #default="{ row }">
            <el-tag effect="plain">{{ datasourceName(row.datasource_id) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="字段" min-width="230" show-overflow-tooltip>
          <template #default="{ row }">{{ fieldText(row.fields_json) }}</template>
        </el-table-column>
        <el-table-column label="口径" min-width="180">
          <template #default="{ row }">
            <div class="logic-tags">
              <el-tag v-if="countList(row.filters_json, 'filters')" size="small" effect="plain">
                筛选 {{ countList(row.filters_json, "filters") }}
              </el-tag>
              <el-tag v-if="countList(row.aggregations_json, 'aggregations')" size="small" effect="plain">
                聚合 {{ countList(row.aggregations_json, "aggregations") }}
              </el-tag>
              <span v-if="!hasBusinessLogic(row)" class="muted">无</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="row.status === 'published' ? 'success' : 'info'" effect="plain">
              {{ row.status === "published" ? "已发布" : "草稿" }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="刷新" width="140">
          <template #default="{ row }">
            <div class="refresh-cell">
              <el-tag
                v-if="row.last_refresh_status"
                :type="row.last_refresh_status === 'success' ? 'success' : 'danger'"
                size="small"
                effect="plain"
              >
                {{ row.last_refresh_status === "success" ? "成功" : "失败" }}
              </el-tag>
              <span v-else class="muted">未刷新</span>
              <small v-if="row.last_refresh_row_count">{{ row.last_refresh_row_count }} 行</small>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="可见范围" width="110">
          <template #default="{ row }">{{ row.visibility === "org" ? "组织内" : "仅自己" }}</template>
        </el-table-column>
        <el-table-column label="操作" width="300" fixed="right">
          <template #default="{ row }">
            <el-button text type="primary" :icon="ViewIcon" @click.stop="previewDataset(row)">预览</el-button>
            <el-button
              text
              type="primary"
              :icon="Refresh"
              :loading="Boolean(datasetRefreshLoading[row.id])"
              @click.stop="refreshDataset(row)"
            >
              刷新
            </el-button>
            <el-button text type="primary" @click.stop="openEdit(row)">编辑</el-button>
            <el-button
              v-if="row.status !== 'published'"
              text
              type="success"
              @click.stop="publishDataset(row)"
            >
              发布
            </el-button>
            <el-button text type="danger" @click.stop="deleteDataset(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-drawer
      v-model="drawerVisible"
      :title="editingId ? '编辑数据集' : '新建数据集'"
      size="92%"
      class="dataset-drawer"
      :close-on-click-modal="false"
      destroy-on-close
    >
      <div class="designer-shell">
        <aside class="step-rail">
          <button
            v-for="(step, index) in steps"
            :key="step.key"
            class="step-item"
            :class="{ active: activeStep === step.key, done: stepIndex(step.key) < currentStepIndex }"
            type="button"
            @click="activeStep = step.key"
          >
            <span class="step-number">{{ index + 1 }}</span>
            <span>
              <strong>{{ step.title }}</strong>
              <small>{{ step.subtitle }}</small>
            </span>
          </button>
        </aside>

        <main class="designer-panel">
          <section v-if="activeStep === 'source'" class="designer-section">
            <div class="section-head">
              <div>
                <h3>选择数据范围</h3>
                <p>{{ form.datasource_id ? datasourceName(form.datasource_id) : "未选择数据源" }}</p>
              </div>
              <el-button
                v-if="form.datasource_id"
                :loading="schemaLoading"
                @click="detectSchema"
              >
                检测表结构
              </el-button>
            </div>

            <el-form class="dataset-form" label-position="top">
              <el-row :gutter="16">
                <el-col :xs="24" :md="12">
                  <el-form-item label="数据集名称" required>
                    <el-input v-model="form.name" maxlength="128" placeholder="如：月度销售分析" />
                  </el-form-item>
                </el-col>
                <el-col :xs="24" :md="12">
                  <el-form-item label="数据源" required>
                    <el-select
                      v-model="form.datasource_id"
                      filterable
                      placeholder="选择数据源"
                      style="width: 100%"
                      @change="handleDatasourceChange"
                    >
                      <el-option
                        v-for="datasource in datasourceStore.datasources"
                        :key="datasource.id"
                        :label="datasource.name"
                        :value="datasource.id"
                      />
                    </el-select>
                  </el-form-item>
                </el-col>
              </el-row>

              <el-form-item label="描述">
                <el-input
                  v-model="form.description"
                  type="textarea"
                  :rows="3"
                  placeholder="说明这个数据集的业务范围、适用场景或统计口径"
                />
              </el-form-item>
            </el-form>

            <div class="table-picker-wrap">
              <div class="panel-title">
                <span>主表</span>
                <small>{{ schemaTables.length }} 张表</small>
              </div>
              <el-empty v-if="form.datasource_id && schemaTables.length === 0" description="暂无表结构">
                <el-button :loading="schemaLoading" @click="detectSchema">检测表结构</el-button>
              </el-empty>
              <el-empty v-else-if="!form.datasource_id" description="请选择数据源" />
              <div v-else class="table-picker">
                <button
                  v-for="table in schemaTables"
                  :key="table.name"
                  type="button"
                  class="table-tile"
                  :class="{ active: form.table === table.name }"
                  @click="selectTable(table.name)"
                >
                  <strong>{{ table.name }}</strong>
                  <span>{{ table.description || `${table.columns.length} 个字段` }}</span>
                </button>
              </div>
            </div>
          </section>

          <section v-else-if="activeStep === 'fields'" class="designer-section">
            <div class="section-head">
              <div>
                <h3>配置字段与口径</h3>
                <p>{{ selectedColumns.length }} 个字段，{{ filters.length }} 条筛选，{{ aggregations.length }} 个聚合</p>
              </div>
              <el-button :loading="previewLoading" :disabled="!form.table" @click="fetchPreview">
                预览数据
              </el-button>
            </div>

            <div class="field-layout">
              <section class="field-panel">
                <div class="panel-title">
                  <span>{{ form.table || "字段" }}</span>
                  <small>{{ currentColumns.length }} 个字段</small>
                </div>
                <el-input
                  v-model="fieldKeyword"
                  :prefix-icon="Search"
                  class="field-search"
                  clearable
                  placeholder="搜索字段"
                />
                <div class="field-list" role="listbox">
                  <div
                    v-for="column in visibleColumns"
                    :key="columnKey(form.table, column.name)"
                    class="field-row"
                    :class="{ selected: isFieldSelected(columnKey(form.table, column.name)) }"
                    role="checkbox"
                    tabindex="0"
                    :aria-checked="isFieldSelected(columnKey(form.table, column.name))"
                    @click="toggleField(columnKey(form.table, column.name))"
                    @keydown.enter.prevent="toggleField(columnKey(form.table, column.name))"
                    @keydown.space.prevent="toggleField(columnKey(form.table, column.name))"
                  >
                    <input
                      class="field-checkbox"
                      type="checkbox"
                      :checked="isFieldSelected(columnKey(form.table, column.name))"
                      @click.stop
                      @change="onFieldCheckboxChange(columnKey(form.table, column.name), $event)"
                    />
                    <span class="field-main">
                      <strong>{{ column.name }}</strong>
                      <small v-if="column.description">{{ column.description }}</small>
                    </span>
                    <el-tag size="small" effect="plain">{{ column.type }}</el-tag>
                  </div>
                </div>
                <el-empty v-if="form.table && visibleColumns.length === 0" description="没有匹配字段" />
              </section>

              <section class="logic-panel">
                <div class="selected-summary">
                  <div class="selected-summary-head">
                    <span>已选字段</span>
                    <small>{{ selectedColumns.length }} 个</small>
                  </div>
                  <div class="selected-field-list compact">
                    <el-tag
                      v-for="field in selectedColumns"
                      :key="field.key"
                      closable
                      effect="plain"
                      @close="removeField(field.key)"
                    >
                      {{ field.label }}
                    </el-tag>
                    <span v-if="selectedColumns.length === 0" class="muted">至少选择一个字段</span>
                  </div>
                </div>

                <el-tabs v-model="logicTab" class="logic-tabs">
                  <el-tab-pane name="filters">
                    <template #label>筛选条件 {{ filters.length }}</template>
                    <div class="logic-card">
                      <div class="panel-title">
                        <span>筛选条件</span>
                        <small>控制数据集范围</small>
                      </div>
                      <div class="filter-builder">
                        <el-select v-model="filterField" placeholder="字段" filterable>
                          <el-option
                            v-for="field in currentFieldOptions"
                            :key="field.key"
                            :label="field.label"
                            :value="field.key"
                          />
                        </el-select>
                        <el-select v-model="filterOperator" placeholder="条件">
                          <el-option
                            v-for="operator in filterOperators"
                            :key="operator.value"
                            :label="operator.label"
                            :value="operator.value"
                          />
                        </el-select>
                        <el-input
                          v-model="filterValue"
                          :disabled="filterValueDisabled"
                          placeholder="值"
                          @keyup.enter="addFilter"
                        />
                        <el-button @click="addFilter">添加</el-button>
                      </div>
                      <div v-if="filters.length" class="condition-list">
                        <div v-for="filter in filters" :key="filter" class="condition-item">
                          <span>{{ filter }}</span>
                          <el-button text type="danger" @click="removeFilter(filter)">删除</el-button>
                        </div>
                      </div>
                      <el-empty v-else :image-size="64" description="暂无筛选条件" />
                    </div>
                  </el-tab-pane>

                  <el-tab-pane name="aggregations">
                    <template #label>聚合指标 {{ aggregations.length }}</template>
                    <div class="logic-card">
                      <div class="panel-title">
                        <span>聚合指标</span>
                        <small>生成汇总口径</small>
                      </div>
                      <div class="aggregation-builder">
                        <el-select v-model="aggregationField" placeholder="字段" filterable>
                          <el-option
                            v-for="field in selectedColumns"
                            :key="field.key"
                            :label="field.label"
                            :value="field.key"
                          />
                        </el-select>
                        <el-select v-model="aggregationFn" placeholder="聚合">
                          <el-option label="求和 SUM" value="SUM" />
                          <el-option label="计数 COUNT" value="COUNT" />
                          <el-option label="平均 AVG" value="AVG" />
                          <el-option label="最大 MAX" value="MAX" />
                          <el-option label="最小 MIN" value="MIN" />
                        </el-select>
                        <el-button @click="addAggregation">添加</el-button>
                      </div>
                      <div v-if="aggregations.length" class="condition-list">
                        <div v-for="aggregation in aggregations" :key="aggregation" class="condition-item">
                          <span>{{ aggregation }}</span>
                          <el-button text type="danger" @click="removeAggregation(aggregation)">删除</el-button>
                        </div>
                      </div>
                      <el-empty v-else :image-size="64" description="暂无聚合指标" />
                    </div>
                  </el-tab-pane>

                  <el-tab-pane name="advanced">
                    <template #label>高级建模 {{ derivedColumns.length + joins.length }}</template>
                    <div class="advanced-workbench">
                      <section class="advanced-section">
                        <div class="advanced-card-head">
                          <div>
                            <strong>派生列</strong>
                            <span>{{ derivedPreviewText || "新字段 = 计算表达式" }}</span>
                          </div>
                          <el-tag effect="plain">{{ derivedColumns.length }} 个</el-tag>
                        </div>

                        <div class="advanced-builder-grid">
                          <div class="builder-form">
                            <label class="builder-label">新字段名</label>
                            <el-input v-model="derivedName" placeholder="如 gross_margin" />

                            <label class="builder-label">计算表达式</label>
                            <el-input
                              v-model="derivedExpression"
                              class="formula-input"
                              type="textarea"
                              :rows="4"
                              placeholder="如 revenue - cost"
                            />

                            <div class="operator-row">
                              <button
                                v-for="operator in derivedOperators"
                                :key="operator"
                                type="button"
                                @click="appendDerivedToken(operator)"
                              >
                                {{ operator }}
                              </button>
                            </div>

                            <div v-if="selectedColumns.length" class="field-token-panel">
                              <button
                                v-for="field in selectedColumns"
                                :key="field.key"
                                type="button"
                                @click="appendDerivedToken(field.label)"
                              >
                                {{ field.column }}
                              </button>
                            </div>

                            <el-button type="primary" class="builder-primary" @click="addDerivedColumn">
                              添加派生列
                            </el-button>
                          </div>

                          <div class="builder-aside">
                            <div class="preview-box">
                              <span>预览</span>
                              <code>{{ derivedPreviewText || "等待输入" }}</code>
                            </div>
                            <div v-if="derivedColumns.length" class="condition-list">
                              <div v-for="item in derivedColumns" :key="item" class="condition-item">
                                <span>{{ item }}</span>
                                <el-button text type="danger" @click="removeDerivedColumn(item)">删除</el-button>
                              </div>
                            </div>
                            <el-empty v-else :image-size="64" description="暂无派生列" />
                          </div>
                        </div>
                      </section>

                      <section class="advanced-section">
                        <div class="advanced-card-head">
                          <div>
                            <strong>Join 关系</strong>
                            <span>{{ joinPreviewText || "选择左右字段建立关联" }}</span>
                          </div>
                          <el-tag effect="plain">{{ joins.length }} 条</el-tag>
                        </div>

                        <div class="advanced-builder-grid">
                          <div class="builder-form">
                            <div class="join-meta-row">
                              <el-select v-model="joinType" placeholder="Join 类型">
                                <el-option
                                  v-for="type in joinTypes"
                                  :key="type"
                                  :label="type"
                                  :value="type"
                                />
                              </el-select>
                              <el-select v-model="joinOperator" placeholder="关系">
                                <el-option label="=" value="=" />
                                <el-option label="!=" value="!=" />
                              </el-select>
                            </div>

                            <div class="join-sides">
                              <div class="join-side">
                                <span>左侧</span>
                                <el-select v-model="joinLeftTable" filterable @change="handleJoinLeftTableChange">
                                  <el-option
                                    v-for="table in schemaTables"
                                    :key="table.name"
                                    :label="table.name"
                                    :value="table.name"
                                  />
                                </el-select>
                                <el-select v-model="joinLeftColumn" filterable>
                                  <el-option
                                    v-for="column in joinLeftColumnOptions"
                                    :key="column.name"
                                    :label="column.name"
                                    :value="column.name"
                                  />
                                </el-select>
                              </div>

                              <div class="join-link-symbol">{{ joinOperator }}</div>

                              <div class="join-side">
                                <span>右侧</span>
                                <el-select v-model="joinRightTable" filterable @change="handleJoinRightTableChange">
                                  <el-option
                                    v-for="table in schemaTables"
                                    :key="table.name"
                                    :label="table.name"
                                    :value="table.name"
                                  />
                                </el-select>
                                <el-select v-model="joinRightColumn" filterable>
                                  <el-option
                                    v-for="column in joinRightColumnOptions"
                                    :key="column.name"
                                    :label="column.name"
                                    :value="column.name"
                                  />
                                </el-select>
                              </div>
                            </div>

                            <el-button type="primary" class="builder-primary" @click="addJoin">
                              添加 Join
                            </el-button>
                          </div>

                          <div class="builder-aside">
                            <div class="preview-box">
                              <span>预览</span>
                              <code>{{ joinPreviewText || "等待选择字段" }}</code>
                            </div>
                            <div v-if="joins.length" class="condition-list">
                              <div v-for="join in joins" :key="join" class="condition-item">
                                <span>{{ join }}</span>
                                <el-button text type="danger" @click="removeJoin(join)">删除</el-button>
                              </div>
                            </div>
                            <el-empty v-else :image-size="64" description="暂无 Join 关系" />
                          </div>
                        </div>
                      </section>
                    </div>
                  </el-tab-pane>
                </el-tabs>
              </section>
            </div>

            <section class="preview-panel">
              <div class="panel-title">
                <span>数据预览</span>
                <small>{{ previewRows.length }} 行</small>
              </div>
              <el-table
                v-loading="previewLoading"
                :data="previewRows"
                height="260"
                border
                empty-text="点击预览数据"
              >
                <el-table-column
                  v-for="column in previewColumns"
                  :key="column"
                  :prop="column"
                  :label="column"
                  min-width="140"
                  show-overflow-tooltip
                />
              </el-table>
            </section>
          </section>

          <section v-else class="designer-section">
            <div class="section-head">
              <div>
                <h3>发布设置</h3>
                <p>{{ form.visibility === "org" ? "组织内可见" : "仅自己可见" }}</p>
              </div>
            </div>

            <div class="publish-layout">
              <section class="publish-panel">
                <div class="panel-title">
                  <span>可见范围</span>
                </div>
                <el-radio-group v-model="form.visibility" class="visibility-group">
                  <el-radio-button value="private">仅自己</el-radio-button>
                  <el-radio-button value="org">组织内</el-radio-button>
                </el-radio-group>
                <el-checkbox v-model="saveAndPublish" class="publish-check">
                  保存后立即发布
                </el-checkbox>
              </section>

              <section class="summary-panel">
                <div class="panel-title">
                  <span>数据集摘要</span>
                </div>
                <el-descriptions :column="1" border>
                  <el-descriptions-item label="名称">{{ form.name || "-" }}</el-descriptions-item>
                  <el-descriptions-item label="数据源">
                    {{ form.datasource_id ? datasourceName(form.datasource_id) : "-" }}
                  </el-descriptions-item>
                  <el-descriptions-item label="主表">{{ form.table || "-" }}</el-descriptions-item>
                  <el-descriptions-item label="字段">{{ selectedColumns.length }} 个</el-descriptions-item>
                  <el-descriptions-item label="筛选">{{ filters.length }} 条</el-descriptions-item>
                  <el-descriptions-item label="聚合">{{ aggregations.length }} 个</el-descriptions-item>
                </el-descriptions>
              </section>
            </div>
          </section>
        </main>
      </div>

      <template #footer>
        <div class="drawer-footer">
          <el-button @click="drawerVisible = false">取消</el-button>
          <div class="footer-actions">
            <el-button :disabled="currentStepIndex === 0" @click="goPrev">上一步</el-button>
            <el-button v-if="activeStep !== 'publish'" type="primary" @click="goNext">下一步</el-button>
            <el-button v-else type="primary" :loading="saving" @click="saveDataset">保存数据集</el-button>
          </div>
        </div>
      </template>
    </el-drawer>

    <el-dialog v-model="datasetPreviewVisible" :title="datasetPreviewTitle" width="78%">
      <el-table
        v-loading="datasetPreviewLoading"
        :data="datasetPreviewRows"
        height="420"
        border
        empty-text="暂无预览数据"
      >
        <el-table-column
          v-for="column in datasetPreviewColumns"
          :key="column"
          :prop="column"
          :label="column"
          min-width="140"
          show-overflow-tooltip
        />
      </el-table>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue"
import axios from "axios"
import { ElMessage, ElMessageBox } from "element-plus"
import { Plus, Refresh, Search, View as ViewIcon } from "@element-plus/icons-vue"
import { useDatasourceStore } from "@/store/datasource"

interface SchemaColumn {
  name: string
  type: string
  description: string | null
}

interface SchemaTable {
  name: string
  description: string | null
  columns: SchemaColumn[]
}

interface SchemaMetadata {
  tables: SchemaTable[]
}

interface DataSourceDetail {
  id: number
  name: string
  slug: string
  source_type?: string
  schema_metadata: SchemaMetadata | null
  metadata_prompt?: string
  is_active: number
}

interface DatasetItem {
  id: number
  name: string
  description: string | null
  datasource_id: number
  fields_json: Record<string, unknown> | null
  filters_json: Record<string, unknown> | null
  derived_columns_json: Record<string, unknown> | null
  joins_json: Record<string, unknown> | null
  aggregations_json: Record<string, unknown> | null
  last_refresh_status: string | null
  last_refresh_row_count: number
  last_refresh_at: string | null
  status: string
  visibility: string
}

type StepKey = "source" | "fields" | "publish"

const datasourceStore = useDatasourceStore()
const datasets = ref<DatasetItem[]>([])
const datasourceDetails = ref<Record<number, DataSourceDetail>>({})
const loading = ref(false)
const saving = ref(false)
const schemaLoading = ref(false)
const drawerVisible = ref(false)
const editingId = ref<number | null>(null)
const keyword = ref("")
const statusFilter = ref("all")
const activeStep = ref<StepKey>("source")
const logicTab = ref("filters")
const fieldKeyword = ref("")
const selectedFieldKeys = ref<string[]>([])
const filters = ref<string[]>([])
const aggregations = ref<string[]>([])
const derivedColumns = ref<string[]>([])
const joins = ref<string[]>([])
const filterField = ref("")
const filterOperator = ref("=")
const filterValue = ref("")
const derivedName = ref("")
const derivedExpression = ref("")
const joinLeftTable = ref("")
const joinLeftColumn = ref("")
const joinRightTable = ref("")
const joinRightColumn = ref("")
const joinType = ref("LEFT JOIN")
const joinOperator = ref("=")
const aggregationField = ref("")
const aggregationFn = ref("SUM")
const previewLoading = ref(false)
const previewRows = ref<Record<string, unknown>[]>([])
const rawPreviewColumns = ref<string[]>([])
const saveAndPublish = ref(false)
const datasetPreviewVisible = ref(false)
const datasetPreviewLoading = ref(false)
const datasetPreviewTitle = ref("数据集预览")
const datasetPreviewRows = ref<Record<string, unknown>[]>([])
const datasetPreviewColumns = ref<string[]>([])
const datasetRefreshLoading = ref<Record<number, boolean>>({})

const steps: { key: StepKey; title: string; subtitle: string }[] = [
  { key: "source", title: "数据范围", subtitle: "数据源与主表" },
  { key: "fields", title: "业务口径", subtitle: "字段、筛选、聚合" },
  { key: "publish", title: "保存发布", subtitle: "权限与摘要" },
]

const statusOptions = [
  { label: "全部", value: "all" },
  { label: "已发布", value: "published" },
  { label: "草稿", value: "draft" },
]

const filterOperators = [
  { label: "等于", value: "=" },
  { label: "不等于", value: "!=" },
  { label: "大于", value: ">" },
  { label: "大于等于", value: ">=" },
  { label: "小于", value: "<" },
  { label: "小于等于", value: "<=" },
  { label: "包含", value: "LIKE" },
  { label: "为空", value: "IS NULL" },
  { label: "不为空", value: "IS NOT NULL" },
]

const joinTypes = ["LEFT JOIN", "INNER JOIN", "RIGHT JOIN", "FULL JOIN"]
const derivedOperators = ["+", "-", "*", "/", "(", ")", "CASE", "WHEN", "THEN", "ELSE", "END"]

const form = reactive({
  name: "",
  description: "",
  datasource_id: null as number | null,
  table: "",
  visibility: "private",
})

const currentStepIndex = computed(() => stepIndex(activeStep.value))

const datasetStats = computed(() => ({
  total: datasets.value.length,
  published: datasets.value.filter((dataset) => dataset.status === "published").length,
  draft: datasets.value.filter((dataset) => dataset.status !== "published").length,
}))

const filteredDatasets = computed(() => {
  const q = keyword.value.trim().toLowerCase()
  if (!q) return datasets.value
  return datasets.value.filter((dataset) => {
    const datasource = datasourceName(dataset.datasource_id)
    return [dataset.name, dataset.description || "", datasource].some((item) =>
      item.toLowerCase().includes(q)
    )
  })
})

const currentDatasource = computed(() => {
  if (!form.datasource_id) return null
  return datasourceDetails.value[form.datasource_id] || null
})

const schemaTables = computed(() => currentDatasource.value?.schema_metadata?.tables || [])

const currentTable = computed(() =>
  schemaTables.value.find((table) => table.name === form.table) || null
)

const currentColumns = computed(() => currentTable.value?.columns || [])

const currentFieldOptions = computed(() =>
  currentColumns.value.map((column) => ({
    key: columnKey(form.table, column.name),
    label: columnKey(form.table, column.name),
    column,
  }))
)

const visibleColumns = computed(() => {
  const q = fieldKeyword.value.trim().toLowerCase()
  if (!q) return currentColumns.value
  return currentColumns.value.filter((column) =>
    [column.name, column.type, column.description || ""].some((item) => item.toLowerCase().includes(q))
  )
})

const selectedColumns = computed(() =>
  selectedFieldKeys.value.map((key) => {
    const [tableName, columnName] = splitColumnKey(key)
    const table = schemaTables.value.find((item) => item.name === tableName)
    const column = table?.columns.find((item) => item.name === columnName)
    return {
      key,
      table: tableName,
      column: columnName,
      label: columnName ? `${tableName}.${columnName}` : key,
      type: column?.type || "",
      description: column?.description || "",
    }
  })
)

const previewColumns = computed(() => {
  const selectedNames = selectedColumns.value
    .filter((field) => field.table === form.table)
    .map((field) => field.column)
  const columns = selectedNames.length > 0 ? selectedNames : rawPreviewColumns.value
  return columns.filter((column) => rawPreviewColumns.value.includes(column))
})

const filterValueDisabled = computed(() => ["IS NULL", "IS NOT NULL"].includes(filterOperator.value))

const derivedPreviewText = computed(() => {
  const name = derivedName.value.trim()
  const expression = derivedExpression.value.trim()
  return name && expression ? `${name} = ${expression}` : ""
})

const joinLeftColumnOptions = computed(() => columnsForTable(joinLeftTable.value))
const joinRightColumnOptions = computed(() => columnsForTable(joinRightTable.value))

const joinPreviewText = computed(() => {
  const left = joinFieldLabel(joinLeftTable.value, joinLeftColumn.value)
  const right = joinFieldLabel(joinRightTable.value, joinRightColumn.value)
  return left && right ? `${joinType.value} ${left} ${joinOperator.value} ${right}` : ""
})

const stepIndex = (key: StepKey) => steps.findIndex((step) => step.key === key)

const datasourceName = (id: number) =>
  datasourceDetails.value[id]?.name ||
  datasourceStore.datasources.find((datasource) => datasource.id === id)?.name ||
  `数据源 #${id}`

const normalizeList = (value: unknown) => (Array.isArray(value) ? value.map(String).filter(Boolean) : [])

const countList = (value: Record<string, unknown> | null, key: string) => normalizeList(value?.[key]).length

const textFromJson = (value: Record<string, unknown> | null, key: string) => normalizeList(value?.[key]).join(", ")

const fieldText = (value: Record<string, unknown> | null) => textFromJson(value, "fields") || "-"

const hasBusinessLogic = (row: DatasetItem) =>
  countList(row.filters_json, "filters") > 0 ||
  countList(row.aggregations_json, "aggregations") > 0 ||
  countList(row.derived_columns_json, "expressions") > 0 ||
  countList(row.joins_json, "joins") > 0

const columnKey = (table: string, column: string) => `${table}.${column}`

const splitColumnKey = (key: string) => {
  const index = key.indexOf(".")
  if (index === -1) return [form.table, key]
  return [key.slice(0, index), key.slice(index + 1)]
}

const columnsForTable = (tableName: string) =>
  schemaTables.value.find((table) => table.name === tableName)?.columns || []

const joinFieldLabel = (tableName: string, columnName: string) =>
  tableName && columnName ? columnKey(tableName, columnName) : ""

const firstTableExcept = (tableName: string) =>
  schemaTables.value.find((table) => table.name !== tableName)?.name || tableName

const firstColumnName = (tableName: string) => columnsForTable(tableName)[0]?.name || ""

const uniquePush = (list: string[], value: string) => {
  const normalized = value.trim()
  if (normalized && !list.includes(normalized)) {
    list.push(normalized)
  }
}

const fetchDatasourceDetail = async (id: number) => {
  const response = await axios.get(`/api/datasources/${id}`)
  datasourceDetails.value = {
    ...datasourceDetails.value,
    [id]: response.data,
  }
  return response.data as DataSourceDetail
}

const fetchDatasourceDetails = async () => {
  await Promise.all(
    datasourceStore.datasources.map((datasource) =>
      fetchDatasourceDetail(datasource.id).catch(() => undefined)
    )
  )
}

const fetchDatasets = async () => {
  loading.value = true
  try {
    const response = await axios.get("/api/datasets", {
      params: { status: statusFilter.value === "all" ? undefined : statusFilter.value },
    })
    datasets.value = response.data.items
  } catch {
    ElMessage.error("数据集加载失败")
  } finally {
    loading.value = false
  }
}

const resetForm = () => {
  editingId.value = null
  activeStep.value = "source"
  form.name = ""
  form.description = ""
  form.datasource_id = datasourceStore.currentId || datasourceStore.datasources[0]?.id || null
  form.table = ""
  form.visibility = "private"
  selectedFieldKeys.value = []
  filters.value = []
  aggregations.value = []
  derivedColumns.value = []
  joins.value = []
  logicTab.value = "filters"
  filterField.value = ""
  filterOperator.value = "="
  filterValue.value = ""
  derivedName.value = ""
  derivedExpression.value = ""
  joinLeftTable.value = ""
  joinLeftColumn.value = ""
  joinRightTable.value = ""
  joinRightColumn.value = ""
  joinType.value = "LEFT JOIN"
  joinOperator.value = "="
  aggregationField.value = ""
  aggregationFn.value = "SUM"
  fieldKeyword.value = ""
  previewRows.value = []
  rawPreviewColumns.value = []
  saveAndPublish.value = false
}

const ensureDatasourceReady = async () => {
  if (!form.datasource_id) return
  if (!datasourceDetails.value[form.datasource_id]) {
    await fetchDatasourceDetail(form.datasource_id)
  }
  if (!form.table && schemaTables.value.length > 0) {
    selectTable(schemaTables.value[0].name)
  }
}

const openCreate = async () => {
  resetForm()
  await ensureDatasourceReady()
  drawerVisible.value = true
}

const openEdit = async (dataset: DatasetItem) => {
  resetForm()
  editingId.value = dataset.id
  form.name = dataset.name
  form.description = dataset.description || ""
  form.datasource_id = dataset.datasource_id
  form.visibility = dataset.visibility
  saveAndPublish.value = dataset.status === "published"
  await ensureDatasourceReady()

  const savedTable = typeof dataset.fields_json?.table === "string" ? dataset.fields_json.table : ""
  form.table = savedTable || inferTableFromFields(dataset.fields_json) || schemaTables.value[0]?.name || ""
  selectedFieldKeys.value = normalizeList(dataset.fields_json?.fields).map((field) =>
    field.includes(".") ? field : columnKey(form.table, field)
  )
  filters.value = normalizeList(dataset.filters_json?.filters)
  aggregations.value = normalizeList(dataset.aggregations_json?.aggregations)
  derivedColumns.value = normalizeList(dataset.derived_columns_json?.expressions)
  joins.value = normalizeList(dataset.joins_json?.joins)
  activeStep.value = "source"
  drawerVisible.value = true
}

const inferTableFromFields = (fieldsJson: Record<string, unknown> | null) => {
  const firstField = normalizeList(fieldsJson?.fields)[0]
  if (!firstField?.includes(".")) return ""
  return firstField.split(".")[0]
}

const handleDatasourceChange = async () => {
  form.table = ""
  selectedFieldKeys.value = []
  filterField.value = ""
  aggregationField.value = ""
  previewRows.value = []
  rawPreviewColumns.value = []
  await ensureDatasourceReady()
}

const selectTable = (tableName: string) => {
  form.table = tableName
  selectedFieldKeys.value = selectedFieldKeys.value.filter((key) => key.startsWith(`${tableName}.`))
  if (selectedFieldKeys.value.length === 0) {
    selectedFieldKeys.value = currentColumns.value.slice(0, 8).map((column) => columnKey(tableName, column.name))
  }
  filterField.value = currentFieldOptions.value[0]?.key || ""
  aggregationField.value = selectedFieldKeys.value[0] || ""
  joinLeftTable.value = tableName
  joinLeftColumn.value = firstColumnName(tableName)
  joinRightTable.value = firstTableExcept(tableName)
  joinRightColumn.value = firstColumnName(joinRightTable.value)
  previewRows.value = []
  rawPreviewColumns.value = []
}

const detectSchema = async () => {
  if (!form.datasource_id) {
    ElMessage.warning("请先选择数据源")
    return
  }
  schemaLoading.value = true
  try {
    const schemaResponse = await axios.post(`/api/datasources/${form.datasource_id}/detect-schema`)
    const promptResponse = await axios.post(
      `/api/datasources/${form.datasource_id}/generate-prompt`,
      schemaResponse.data
    )
    await axios.put(`/api/datasources/${form.datasource_id}`, {
      schema_metadata: schemaResponse.data,
      metadata_prompt: promptResponse.data.metadata_prompt,
    })
    await fetchDatasourceDetail(form.datasource_id)
    if (!form.table && schemaTables.value.length > 0) {
      selectTable(schemaTables.value[0].name)
    }
    ElMessage.success("表结构已更新")
  } catch (error: any) {
    ElMessage.error(error.response?.data?.detail || "表结构检测失败")
  } finally {
    schemaLoading.value = false
  }
}

const removeField = (key: string) => {
  selectedFieldKeys.value = selectedFieldKeys.value.filter((item) => item !== key)
  if (aggregationField.value === key) {
    aggregationField.value = selectedFieldKeys.value[0] || ""
  }
}

const isFieldSelected = (key: string) => selectedFieldKeys.value.includes(key)

const setFieldSelected = (key: string, selected: boolean) => {
  if (selected && !selectedFieldKeys.value.includes(key)) {
    selectedFieldKeys.value = [...selectedFieldKeys.value, key]
  }
  if (!selected) {
    selectedFieldKeys.value = selectedFieldKeys.value.filter((item) => item !== key)
  }
  if (aggregationField.value && !selectedFieldKeys.value.includes(aggregationField.value)) {
    aggregationField.value = selectedFieldKeys.value[0] || ""
  }
  if (!aggregationField.value && selectedFieldKeys.value.length > 0) {
    aggregationField.value = selectedFieldKeys.value[0]
  }
}

const toggleField = (key: string) => {
  setFieldSelected(key, !isFieldSelected(key))
}

const onFieldCheckboxChange = (key: string, event: Event) => {
  setFieldSelected(key, (event.target as HTMLInputElement).checked)
}

const addFilter = () => {
  if (!filterField.value) {
    ElMessage.warning("请选择筛选字段")
    return
  }
  if (!filterValueDisabled.value && !filterValue.value.trim()) {
    ElMessage.warning("请填写筛选值")
    return
  }
  const field = currentFieldOptions.value.find((item) => item.key === filterField.value)
  const label = field?.label || filterField.value
  const expression = filterValueDisabled.value
    ? `${label} ${filterOperator.value}`
    : `${label} ${filterOperator.value} ${filterValue.value.trim()}`
  uniquePush(filters.value, expression)
  filterValue.value = ""
}

const removeFilter = (filter: string) => {
  filters.value = filters.value.filter((item) => item !== filter)
}

const addAggregation = () => {
  if (!aggregationField.value) {
    ElMessage.warning("请选择聚合字段")
    return
  }
  const field = selectedColumns.value.find((item) => item.key === aggregationField.value)
  uniquePush(aggregations.value, `${aggregationFn.value}(${field?.label || aggregationField.value})`)
}

const removeAggregation = (aggregation: string) => {
  aggregations.value = aggregations.value.filter((item) => item !== aggregation)
}

const appendDerivedToken = (field: string) => {
  const expression = derivedExpression.value.trim()
  derivedExpression.value = expression ? `${expression} ${field}` : field
}

const addDerivedColumn = () => {
  if (!derivedName.value.trim() || !derivedExpression.value.trim()) {
    ElMessage.warning("请填写派生列名称和表达式")
    return
  }
  uniquePush(derivedColumns.value, derivedPreviewText.value)
  derivedName.value = ""
  derivedExpression.value = ""
}

const removeDerivedColumn = (item: string) => {
  derivedColumns.value = derivedColumns.value.filter((value) => value !== item)
}

const handleJoinLeftTableChange = () => {
  joinLeftColumn.value = firstColumnName(joinLeftTable.value)
}

const handleJoinRightTableChange = () => {
  joinRightColumn.value = firstColumnName(joinRightTable.value)
}

const addJoin = () => {
  if (!joinLeftTable.value || !joinLeftColumn.value || !joinRightTable.value || !joinRightColumn.value) {
    ElMessage.warning("请选择 Join 左右字段")
    return
  }
  uniquePush(joins.value, joinPreviewText.value)
}

const removeJoin = (join: string) => {
  joins.value = joins.value.filter((item) => item !== join)
}

const fetchPreview = async () => {
  if (!form.datasource_id || !form.table) {
    ElMessage.warning("请先选择数据源和主表")
    return
  }
  previewLoading.value = true
  try {
    const response = await axios.get(`/api/datasources/${form.datasource_id}/preview`, {
      params: { table: form.table, limit: 30 },
    })
    rawPreviewColumns.value = response.data.columns || []
    previewRows.value = response.data.rows || []
  } catch (error: any) {
    ElMessage.error(error.response?.data?.detail || "数据预览失败")
  } finally {
    previewLoading.value = false
  }
}

const previewDataset = async (dataset: DatasetItem) => {
  datasetPreviewVisible.value = true
  datasetPreviewLoading.value = true
  datasetPreviewTitle.value = `${dataset.name} - 数据预览`
  datasetPreviewRows.value = []
  datasetPreviewColumns.value = []
  try {
    const response = await axios.post(`/api/datasets/${dataset.id}/preview`, { limit: 100 })
    datasetPreviewColumns.value = response.data.columns || []
    datasetPreviewRows.value = response.data.rows || []
  } catch (error: any) {
    ElMessage.error(error.response?.data?.detail || "数据集预览失败")
  } finally {
    datasetPreviewLoading.value = false
  }
}

const refreshDataset = async (dataset: DatasetItem) => {
  datasetRefreshLoading.value = { ...datasetRefreshLoading.value, [dataset.id]: true }
  try {
    await axios.post(`/api/datasets/${dataset.id}/refresh`)
    ElMessage.success("数据集刷新完成")
    await fetchDatasets()
  } catch (error: any) {
    ElMessage.error(error.response?.data?.detail || "数据集刷新失败")
  } finally {
    datasetRefreshLoading.value = { ...datasetRefreshLoading.value, [dataset.id]: false }
  }
}

const validateSourceStep = () => {
  if (!form.name.trim() || !form.datasource_id) {
    ElMessage.warning("请填写名称并选择数据源")
    return false
  }
  if (!form.table) {
    ElMessage.warning("请选择主表")
    return false
  }
  return true
}

const validateFieldsStep = () => {
  if (selectedFieldKeys.value.length === 0) {
    ElMessage.warning("请至少选择一个字段")
    return false
  }
  return true
}

const goNext = () => {
  if (activeStep.value === "source" && !validateSourceStep()) return
  if (activeStep.value === "fields" && !validateFieldsStep()) return
  activeStep.value = steps[Math.min(currentStepIndex.value + 1, steps.length - 1)].key
}

const goPrev = () => {
  activeStep.value = steps[Math.max(currentStepIndex.value - 1, 0)].key
}

const buildPayload = () => ({
  name: form.name.trim(),
  description: form.description.trim() || null,
  datasource_id: form.datasource_id,
  fields_json: {
    table: form.table,
    fields: selectedFieldKeys.value,
    field_labels: selectedColumns.value,
  },
  filters_json: { filters: filters.value },
  derived_columns_json: { expressions: derivedColumns.value },
  joins_json: { joins: joins.value },
  aggregations_json: { aggregations: aggregations.value },
  visibility: form.visibility,
  status: saveAndPublish.value ? "published" : "draft",
})

const saveDataset = async () => {
  if (!validateSourceStep() || !validateFieldsStep()) return
  saving.value = true
  try {
    const payload = buildPayload()
    if (editingId.value) {
      await axios.put(`/api/datasets/${editingId.value}`, payload)
    } else {
      await axios.post("/api/datasets", payload)
    }
    if (saveAndPublish.value) {
      ElMessage.success("数据集已保存并发布")
    } else {
      ElMessage.success("数据集已保存")
    }
    drawerVisible.value = false
    await fetchDatasets()
  } catch (error: any) {
    ElMessage.error(error.response?.data?.detail || "数据集保存失败")
  } finally {
    saving.value = false
  }
}

const publishDataset = async (dataset: DatasetItem) => {
  await axios.post(`/api/datasets/${dataset.id}/publish`)
  ElMessage.success("数据集已发布")
  await fetchDatasets()
}

const deleteDataset = async (dataset: DatasetItem) => {
  await ElMessageBox.confirm("确定删除这个数据集吗？", "提示", { type: "warning" })
  await axios.delete(`/api/datasets/${dataset.id}`)
  ElMessage.success("数据集已删除")
  await fetchDatasets()
}

onMounted(async () => {
  await datasourceStore.fetchDatasources().catch(() => undefined)
  await fetchDatasourceDetails()
  await fetchDatasets()
})
</script>

<style scoped>
.dataset-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.dataset-hero {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 20px;
  padding: 20px;
  border: 1px solid var(--app-border);
  border-radius: var(--app-radius);
  background: var(--app-surface);
  box-shadow: var(--app-shadow-soft);
}

.eyebrow {
  margin: 0 0 6px;
  color: var(--app-primary);
  font-size: 12px;
  font-weight: 700;
}

.dataset-hero h2 {
  margin: 0;
  color: var(--app-text);
  font-size: 24px;
  line-height: 1.3;
}

.hero-copy {
  max-width: 640px;
  margin: 8px 0 0;
  color: var(--app-text-muted);
  line-height: 1.6;
}

.hero-actions {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 10px;
  flex-wrap: wrap;
}

.search-input {
  width: 260px;
}

.summary-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
}

.summary-card {
  min-height: 88px;
  padding: 16px;
  border: 1px solid var(--app-border);
  border-radius: var(--app-radius);
  background: var(--app-surface);
}

.summary-card strong {
  display: block;
  margin-top: 8px;
  color: var(--app-text);
  font-size: 28px;
  line-height: 1;
}

.summary-label,
.muted,
.panel-title small,
.step-item small,
.dataset-name-cell span {
  color: var(--app-text-muted);
}

.dataset-card {
  border: 1px solid var(--app-border);
}

.dataset-card :deep(.el-card__body) {
  padding: 0;
}

.dataset-card :deep(.el-table__row) {
  cursor: pointer;
}

.dataset-name-cell {
  display: flex;
  flex-direction: column;
  gap: 5px;
}

.dataset-name-cell strong {
  color: var(--app-text);
  font-size: 14px;
}

.logic-tags,
.tag-list,
.selected-field-list {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.refresh-cell {
  display: flex;
  flex-direction: column;
  gap: 4px;
  align-items: flex-start;
}

.refresh-cell small {
  color: var(--app-text-muted);
}

.designer-shell {
  display: grid;
  grid-template-columns: 220px minmax(0, 1fr);
  gap: 20px;
  min-height: calc(100vh - 190px);
}

.step-rail {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 4px;
}

.step-item {
  display: grid;
  grid-template-columns: 34px minmax(0, 1fr);
  gap: 10px;
  width: 100%;
  min-height: 72px;
  padding: 12px;
  text-align: left;
  border: 1px solid var(--app-border);
  border-radius: var(--app-radius);
  background: var(--app-surface);
  color: var(--app-text);
  cursor: pointer;
  transition: border-color var(--app-transition), background var(--app-transition);
}

.step-item.active {
  border-color: var(--app-primary);
  background: rgba(15, 118, 110, 0.08);
}

.step-item.done .step-number {
  background: var(--app-primary);
  color: #fff;
}

.step-number {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 30px;
  height: 30px;
  border-radius: 999px;
  background: var(--app-surface-subtle);
  color: var(--app-text);
  font-weight: 700;
}

.step-item strong,
.step-item small {
  display: block;
}

.step-item small {
  margin-top: 4px;
  font-size: 12px;
}

.designer-panel {
  min-width: 0;
}

.designer-section {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.section-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  padding: 18px;
  border: 1px solid var(--app-border);
  border-radius: var(--app-radius);
  background: var(--app-surface);
}

.section-head h3 {
  margin: 0;
  font-size: 18px;
  line-height: 1.4;
}

.section-head p {
  margin: 6px 0 0;
  color: var(--app-text-muted);
  line-height: 1.6;
}

.dataset-form,
.table-picker-wrap,
.field-panel,
.logic-panel,
.preview-panel,
.publish-panel,
.summary-panel {
  padding: 18px;
  border: 1px solid var(--app-border);
  border-radius: var(--app-radius);
  background: var(--app-surface);
}

.panel-title {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
  font-weight: 700;
}

.table-picker {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: 10px;
}

.table-tile {
  min-height: 78px;
  padding: 14px;
  text-align: left;
  border: 1px solid var(--app-border);
  border-radius: var(--app-radius-sm);
  background: var(--app-surface-muted);
  color: var(--app-text);
  cursor: pointer;
}

.table-tile.active {
  border-color: var(--app-primary);
  background: rgba(15, 118, 110, 0.08);
}

.table-tile strong,
.table-tile span {
  display: block;
}

.table-tile span {
  margin-top: 8px;
  color: var(--app-text-muted);
  line-height: 1.45;
}

.field-layout,
.publish-layout {
  display: grid;
  grid-template-columns: minmax(320px, 0.88fr) minmax(360px, 1.12fr);
  gap: 16px;
}

.field-search {
  margin-bottom: 12px;
}

.field-list {
  display: flex;
  flex-direction: column;
  max-height: 520px;
  overflow: auto;
  border: 1px solid var(--app-border-light);
  border-radius: var(--app-radius-sm);
}

.field-row {
  display: grid;
  grid-template-columns: 22px minmax(0, 1fr) auto;
  align-items: center;
  gap: 10px;
  min-height: 58px;
  padding: 10px 12px;
  border-bottom: 1px solid var(--app-border-light);
  background: var(--app-surface);
  color: var(--app-text);
  cursor: pointer;
  transition: background var(--app-transition), box-shadow var(--app-transition);
}

.field-row:last-child {
  border-bottom: 0;
}

.field-row:hover {
  background: var(--app-surface-muted);
}

.field-row.selected {
  background: rgba(15, 118, 110, 0.08);
  box-shadow: inset 3px 0 0 var(--app-primary);
}

.field-row:focus-visible {
  outline: 2px solid rgba(15, 118, 110, 0.3);
  outline-offset: -2px;
}

.field-checkbox {
  width: 18px;
  height: 18px;
  margin: 0;
  accent-color: var(--app-primary);
  cursor: pointer;
}

.field-main {
  min-width: 0;
  line-height: 1.35;
}

.field-main strong,
.field-main small {
  display: block;
}

.field-main strong {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: var(--app-text);
  font-size: 14px;
  font-weight: 700;
  line-height: 20px;
}

.field-main small {
  margin-top: 3px;
  color: var(--app-text-muted);
  font-size: 12px;
  line-height: 16px;
}

.logic-panel,
.preview-panel,
.publish-panel,
.summary-panel {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.logic-card {
  padding: 14px;
  border: 1px solid var(--app-border-light);
  border-radius: var(--app-radius-sm);
  background: var(--app-surface-muted);
}

.selected-summary {
  padding: 12px 14px;
  border: 1px solid var(--app-border-light);
  border-radius: var(--app-radius-sm);
  background: var(--app-surface);
}

.selected-summary-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 10px;
  font-weight: 700;
}

.selected-field-list.compact {
  max-height: 76px;
  overflow: auto;
}

.logic-tabs {
  min-height: 100%;
}

.logic-tabs :deep(.el-tabs__header) {
  margin: 0 0 12px;
}

.logic-tabs :deep(.el-tabs__nav-wrap::after) {
  height: 1px;
  background: var(--app-border-light);
}

.filter-builder,
.aggregation-builder {
  display: grid;
  gap: 8px;
  margin-bottom: 12px;
}

.filter-builder {
  grid-template-columns: minmax(160px, 1fr) 120px minmax(150px, 1fr) auto;
}

.aggregation-builder {
  grid-template-columns: minmax(0, 1fr) 150px auto;
}

.condition-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.condition-item {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  align-items: center;
  gap: 10px;
  min-height: 40px;
  padding: 8px 10px;
  border: 1px solid var(--app-border-light);
  border-radius: var(--app-radius-xs);
  background: var(--app-surface);
}

.condition-item span {
  min-width: 0;
  overflow: hidden;
  color: var(--app-text);
  text-overflow: ellipsis;
  white-space: nowrap;
}

.advanced-workbench {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.advanced-section {
  padding: 14px;
  border: 1px solid var(--app-border-light);
  border-radius: var(--app-radius-sm);
  background: var(--app-surface);
}

.advanced-card-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.advanced-card-head strong,
.advanced-card-head span {
  display: block;
}

.advanced-card-head strong {
  color: var(--app-text);
  font-size: 14px;
}

.advanced-card-head span {
  margin-top: 4px;
  color: var(--app-text-muted);
  font-size: 12px;
}

.advanced-builder-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.05fr) minmax(260px, 0.95fr);
  gap: 14px;
  margin-top: 14px;
}

.builder-form,
.builder-aside {
  min-width: 0;
}

.builder-form {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.builder-label {
  color: var(--app-text-muted);
  font-size: 12px;
  font-weight: 700;
}

.operator-row,
.field-token-panel {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(42px, 1fr));
  gap: 6px;
}

.field-token-panel {
  grid-template-columns: repeat(auto-fill, minmax(88px, 1fr));
  max-height: 96px;
  overflow: auto;
  padding: 8px;
  border: 1px solid var(--app-border-light);
  border-radius: var(--app-radius-xs);
  background: var(--app-surface-muted);
}

.operator-row button,
.field-token-panel button {
  min-height: 32px;
  padding: 5px 8px;
  border: 1px solid var(--app-border);
  border-radius: var(--app-radius-xs);
  background: var(--app-surface);
  color: var(--app-text);
  cursor: pointer;
  font-size: 12px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.operator-row button:hover,
.field-token-panel button:hover {
  border-color: var(--app-primary);
  color: var(--app-primary);
}

.builder-primary {
  width: 100%;
}

.preview-box {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-bottom: 12px;
  padding: 12px;
  border: 1px solid rgba(15, 118, 110, 0.22);
  border-radius: var(--app-radius-xs);
  background: rgba(15, 118, 110, 0.07);
}

.preview-box span {
  color: var(--app-primary-dark);
  font-size: 12px;
  font-weight: 700;
}

.preview-box code {
  color: var(--app-text);
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  font-size: 12px;
  line-height: 1.5;
  word-break: break-word;
  white-space: pre-wrap;
}

.join-meta-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 96px;
  gap: 8px;
}

.join-sides {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 40px minmax(0, 1fr);
  gap: 10px;
  align-items: center;
}

.join-side {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 10px;
  border: 1px solid var(--app-border-light);
  border-radius: var(--app-radius-xs);
  background: var(--app-surface-muted);
}

.join-side span {
  color: var(--app-text-muted);
  font-size: 12px;
  font-weight: 700;
}

.join-link-symbol {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 36px;
  border-radius: 999px;
  background: var(--app-surface-subtle);
  color: var(--app-primary-dark);
  font-weight: 800;
}

.preview-panel {
  min-height: 340px;
}

.visibility-group {
  align-self: flex-start;
}

.publish-check {
  margin-top: 4px;
}

.drawer-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
}

.footer-actions {
  display: flex;
  gap: 8px;
}

@media (max-width: 1100px) {
  .dataset-hero,
  .section-head {
    flex-direction: column;
  }

  .hero-actions,
  .search-input {
    width: 100%;
  }

  .summary-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .designer-shell,
  .field-layout,
  .publish-layout,
  .advanced-builder-grid,
  .join-sides {
    grid-template-columns: 1fr;
  }

  .step-rail {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
}

@media (max-width: 680px) {
  .summary-grid,
  .step-rail {
    grid-template-columns: 1fr;
  }

  .aggregation-builder,
  .filter-builder,
  .join-meta-row {
    grid-template-columns: 1fr;
  }

  .join-link-symbol {
    justify-self: flex-start;
    width: 40px;
  }
}
</style>
