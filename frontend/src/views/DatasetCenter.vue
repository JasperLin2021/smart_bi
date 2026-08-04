<template>
  <div class="dataset-page" :class="{ 'dataset-page--embedded': embedded }">
    <section v-if="!embedded" class="dataset-toolbar" aria-label="数据集工具栏">
      <div class="dataset-toolbar-title">
        <strong>数据集中心</strong>
        <span>{{ filteredDatasets.length }} / {{ datasets.length }} 个数据集</span>
      </div>
      <div class="dataset-toolbar-actions">
        <el-input
          v-model="keyword"
          :prefix-icon="Search"
          class="search-input"
          clearable
          placeholder="搜索数据集 / 数据源"
        />
        <el-segmented
          class="page-segmented-tabs"
          v-model="statusFilter"
          :options="statusOptions"
          @change="fetchDatasets"
        />
        <el-button type="primary" :icon="Plus" @click="openCreate()">新建数据集</el-button>
      </div>
    </section>

    <el-card v-if="!embedded" class="dataset-card" shadow="never">
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
        <el-table-column label="维度 / 指标" min-width="260" show-overflow-tooltip>
          <template #default="{ row }">
            <div class="dataset-model-cell">
              <span>维度：{{ dimensionText(row.fields_json) }}</span>
              <span>指标：{{ metricText(row.fields_json, row.aggregations_json) }}</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="口径" min-width="180">
          <template #default="{ row }">
            <div class="logic-tags">
              <el-tag v-if="countList(row.filters_json, 'filters')" size="small" effect="plain">
                筛选 {{ countList(row.filters_json, "filters") }}
              </el-tag>
              <el-tag v-if="countList(row.aggregations_json, 'aggregations')" size="small" effect="plain">
                指标 {{ countList(row.aggregations_json, "aggregations") }}
              </el-tag>
              <span v-if="!hasBusinessLogic(row)" class="muted">无</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="datasetStatusTagType(row.status)" effect="plain">
              {{ datasetStatusLabel(row.status) }}
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
        <el-table-column label="操作" width="380" fixed="right">
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
            <el-button text type="primary" :icon="EditPen" @click.stop="openSemanticModel(row)">语义层</el-button>
            <el-button
              v-if="row.status === 'pending_review' && canApproveDatasets"
              text
              type="success"
              @click.stop="approveDataset(row)"
            >
              审批发布
            </el-button>
            <el-button
              v-else-if="row.status !== 'published' && row.status !== 'pending_review'"
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
    <div v-else class="dataset-embedded-anchor" aria-hidden="true"></div>

    <el-drawer
      v-model="drawerVisible"
      :title="editingId ? '编辑数据集' : '新建数据集'"
      :size="embedded ? 'min(1040px, 96vw)' : '92%'"
      :class="['dataset-drawer', { 'dataset-drawer--embedded': embedded }]"
      :modal-class="embedded ? 'dataset-drawer-modal dataset-drawer-modal--embedded' : 'dataset-drawer-modal'"
      :close-on-click-modal="false"
      :append-to-body="embedded"
      destroy-on-close
      @closed="handleDrawerClosed"
    >
      <div class="designer-shell" :class="{ 'embedded-designer-shell': embedded }">
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
            <div class="section-head fields-section-head">
              <div>
                <h3>配置维度与指标</h3>
                <p>把字段定义为可分析的维度和可计算的指标，预览会按当前口径实时生成。</p>
              </div>
              <div class="fields-head-actions">
                <div class="fields-health-pill">
                  <span>{{ selectedColumns.length }} 维度</span>
                  <span>{{ metricConfigs.length }} 指标</span>
                  <span>{{ filters.length }} 筛选</span>
                </div>
                <el-button
                  :loading="aiConfigLoading"
                  :disabled="!form.datasource_id || !form.table"
                  @click="generateDatasetAiConfig"
                >
                  AI 自动配置
                </el-button>
                <el-button type="primary" :loading="previewLoading" :disabled="!form.table" @click="fetchPreview">
                  预览数据
                </el-button>
              </div>
            </div>

            <div class="field-layout">
              <section class="field-panel">
                <div class="field-panel-hero">
                  <div>
                    <span class="eyebrow">字段候选区</span>
                    <strong>{{ form.table || "可选字段" }}</strong>
                    <small>{{ currentColumns.length }} 个字段，可按用途快速筛选</small>
                  </div>
                  <el-tag effect="plain">{{ visibleFieldConfigs.length }} 可见</el-tag>
                </div>

                <div class="field-mode-tabs" aria-label="字段用途筛选">
                  <button
                    v-for="tab in fieldRoleTabs"
                    :key="tab.value"
                    type="button"
                    class="field-mode-tab"
                    :class="{ active: fieldRoleView === tab.value }"
                    @click="fieldRoleView = tab.value"
                  >
                    <span>{{ tab.label }}</span>
                    <strong>{{ tab.count }}</strong>
                  </button>
                </div>

                <el-input
                  v-model="fieldKeyword"
                  :prefix-icon="Search"
                  class="field-search"
                  clearable
                  placeholder="搜索字段名、别名、类型或描述"
                />
                <div class="field-config-list" role="list">
                  <div
                    v-for="config in visibleFieldConfigs"
                    :key="config.key"
                    class="field-config-row"
                    :class="`role-${config.role}`"
                    role="listitem"
                  >
                    <div class="field-config-top">
                      <div class="field-config-main">
                        <span class="role-dot" />
                        <div>
                          <strong>{{ config.column }}</strong>
                          <small>{{ config.description || config.key }}</small>
                        </div>
                      </div>
                      <div class="field-config-tags">
                        <el-tag size="small" effect="plain">{{ config.type }}</el-tag>
                        <span class="role-label">{{ fieldRoleLabel(config.role) }}</span>
                      </div>
                    </div>

                    <div class="field-config-controls">
                      <label class="control-field control-role">
                        <span>字段用途</span>
                        <el-segmented
                          v-model="config.role"
                          :options="roleOptions"
                          class="role-segmented"
                          @change="handleRoleChange(config)"
                        />
                      </label>
                      <label class="control-field">
                        <span>显示名称</span>
                        <el-input
                          v-model="config.alias"
                          clearable
                          class="alias-input"
                          placeholder="用于图表、问数和语义层"
                        />
                      </label>
                      <label v-if="config.role === 'metric'" class="control-field">
                        <span>计算方式</span>
                        <el-select
                          v-model="config.aggregation"
                          class="aggregation-select"
                          placeholder="计算方式"
                        >
                          <el-option
                            v-for="option in aggregationOptions"
                            :key="option.value"
                            :label="option.label"
                            :value="option.value"
                          />
                        </el-select>
                      </label>
                      <div v-else class="field-role-hint">
                        {{ fieldRoleHint(config.role) }}
                      </div>
                    </div>
                  </div>
                </div>
                <el-empty
                  v-if="form.table && visibleFieldConfigs.length === 0"
                  :image-size="72"
                  description="没有匹配字段"
                />
              </section>

              <section class="logic-panel">
                <div class="model-overview">
                  <div
                    v-for="item in modelQualityItems"
                    :key="item.label"
                    class="model-overview-item"
                    :class="`tone-${item.tone}`"
                  >
                    <span>{{ item.label }}</span>
                    <strong>{{ item.value }}</strong>
                    <small>{{ item.hint }}</small>
                  </div>
                </div>

                <div class="model-summary-grid">
                  <div class="selected-summary dimension-summary">
                    <div class="selected-summary-head">
                      <div>
                        <span>维度字段</span>
                        <small>用于分组、钻取、筛选和联动</small>
                      </div>
                      <small>{{ selectedColumns.length }} 个</small>
                    </div>
                    <div class="selected-field-list compact">
                      <el-tag
                        v-for="field in selectedColumns"
                        :key="field.key"
                        closable
                        effect="plain"
                        class="selected-field-chip dimension-chip"
                        @close="setFieldRole(field.key, 'ignore')"
                      >
                        {{ field.alias || field.column }}
                      </el-tag>
                      <span v-if="selectedColumns.length === 0" class="empty-inline">从左侧字段卡片切换为维度</span>
                    </div>
                  </div>
                  <div class="selected-summary metric-summary">
                    <div class="selected-summary-head">
                      <div>
                        <span>指标字段</span>
                        <small>用于聚合计算、趋势和 KPI</small>
                      </div>
                      <small>{{ metricConfigs.length }} 个</small>
                    </div>
                    <div class="selected-field-list compact">
                      <el-tag
                        v-for="metric in metricConfigs"
                        :key="metric.key"
                        closable
                        effect="plain"
                        class="selected-field-chip metric-chip"
                        @close="setFieldRole(metric.key, 'ignore')"
                      >
                        {{ metric.alias || metric.column }}
                        <code>{{ metricExpressionLabel(metric) }}</code>
                      </el-tag>
                      <span v-if="metricConfigs.length === 0" class="empty-inline">从左侧字段卡片切换为指标</span>
                    </div>
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

                  <el-tab-pane name="drill">
                    <template #label>下钻配置 {{ drillConfig.paths.length }}</template>
                    <div class="logic-card drill-config-card">
                      <div class="panel-title drill-config-title">
                        <div>
                          <span>数据集下钻路径</span>
                          <small>点击图表或明细行时，优先使用这里的路径生成下钻动作</small>
                        </div>
                        <div class="drill-config-actions">
                          <el-button size="small" :loading="aiConfigLoading" @click="generateDatasetAiConfig">
                            AI 生成
                          </el-button>
                          <el-button size="small" @click="generateLocalDrillPaths">从当前字段生成</el-button>
                        </div>
                      </div>

                      <div class="drill-summary-grid">
                        <div>
                          <span>维度</span>
                          <strong>{{ drillConfig.dimensions.length }}</strong>
                        </div>
                        <div>
                          <span>指标</span>
                          <strong>{{ drillConfig.metrics.length }}</strong>
                        </div>
                        <div>
                          <span>路径</span>
                          <strong>{{ drillConfig.paths.length }}</strong>
                        </div>
                      </div>

                      <div class="drill-path-builder">
                        <el-select v-model="newDrillPath.source_dimension_id" placeholder="起点维度" filterable>
                          <el-option
                            v-for="dimension in drillDimensionOptions"
                            :key="dimension.id"
                            :label="dimension.label"
                            :value="dimension.id"
                          />
                        </el-select>
                        <span class="drill-path-arrow">→</span>
                        <el-select v-model="newDrillPath.target_dimension_id" placeholder="下钻维度" filterable>
                          <el-option
                            v-for="dimension in drillDimensionOptions"
                            :key="dimension.id"
                            :label="dimension.label"
                            :value="dimension.id"
                          />
                        </el-select>
                        <el-input v-model="newDrillPath.label" placeholder="按钮文案，如：看设备分布" />
                        <el-button type="primary" @click="addDrillPath">添加路径</el-button>
                      </div>

                      <div v-if="drillConfig.paths.length" class="drill-path-list">
                        <div
                          v-for="path in drillConfig.paths"
                          :key="path.id"
                          class="drill-path-row"
                          :class="{ disabled: !path.enabled }"
                        >
                          <div class="drill-path-flow">
                            <strong>{{ drillDimensionLabel(path.source_dimension_id) }}</strong>
                            <span>→</span>
                            <strong>{{ drillDimensionLabel(path.target_dimension_id) }}</strong>
                          </div>
                          <el-input v-model="path.label" class="drill-path-label-input" />
                          <el-switch v-model="path.enabled" />
                          <el-button text type="danger" @click="removeDrillPath(path.id)">删除</el-button>
                        </div>
                      </div>
                      <el-empty v-else :image-size="64" description="暂无下钻路径，可用 AI 生成或从当前字段生成" />
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

                            <div class="candidate-section">
                              <div class="candidate-section-head">
                                <span>可插入指标</span>
                                <small>{{ derivedMetricCandidates.length ? "点击插入聚合表达式" : "请先配置指标字段" }}</small>
                              </div>
                              <div v-if="derivedMetricCandidates.length" class="field-token-panel metric-token-panel">
                                <button
                                  v-for="metric in derivedMetricCandidates"
                                  :key="metric.key"
                                  type="button"
                                  :title="metric.expression"
                                  @click="appendDerivedToken(metric.expression)"
                                >
                                  <strong>{{ metric.label }}</strong>
                                  <small>{{ metric.expression }}</small>
                                </button>
                              </div>
                              <div v-else class="metric-token-empty">
                                在字段配置中把可计算字段标记为指标后，可在这里插入。
                              </div>
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
                <el-alert
                  v-if="form.visibility === 'org'"
                  class="visibility-approval-alert"
                  :type="orgVisibilityApprovalRequired ? 'warning' : 'success'"
                  :closable="false"
                  show-icon
                >
                  <template #title>
                    {{ orgVisibilityApprovalRequired ? "待部门管理员审批" : "你具备组织内发布权限" }}
                  </template>
                  <template #default>
                    {{ orgVisibilityApprovalRequired ? "提交后状态会变为待审批，审批通过前仅创建者和管理员可见。" : "保存发布后会直接组织内可见。" }}
                  </template>
                </el-alert>
                <el-checkbox v-model="saveAndPublish" class="publish-check">
                  {{ orgVisibilityApprovalRequired ? "保存后提交审批" : "保存后立即发布" }}
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
                  <el-descriptions-item label="维度">{{ selectedColumns.length }} 个</el-descriptions-item>
                  <el-descriptions-item label="筛选">{{ filters.length }} 条</el-descriptions-item>
                  <el-descriptions-item label="指标">{{ aggregations.length }} 个</el-descriptions-item>
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

    <el-dialog
      v-model="semanticModelVisible"
      :title="semanticModelTitle"
      width="72%"
      class="semantic-dialog"
      destroy-on-close
    >
      <div class="semantic-dialog-body">
        <div class="semantic-stat-row">
          <div>
            <span>维度</span>
            <strong>{{ semanticModelCounts.dimensions }}</strong>
          </div>
          <div>
            <span>指标</span>
            <strong>{{ semanticModelCounts.metrics }}</strong>
          </div>
          <div>
            <span>时间维度</span>
            <strong>{{ semanticModelCounts.timeDimensions }}</strong>
          </div>
          <div>
            <span>同义词</span>
            <strong>{{ semanticModelCounts.synonyms }}</strong>
          </div>
        </div>
        <el-input
          v-model="semanticModelText"
          v-loading="semanticModelLoading"
          class="semantic-json-editor"
          type="textarea"
          :rows="20"
          spellcheck="false"
        />
      </div>
      <template #footer>
        <div class="semantic-footer">
          <el-button @click="semanticModelVisible = false">取消</el-button>
          <div>
            <el-button :loading="semanticModelValidating" @click="validateSemanticModel">校验</el-button>
            <el-button type="primary" :loading="semanticModelSaving" @click="saveSemanticModel">
              保存语义层
            </el-button>
          </div>
        </div>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from "vue"
import axios from "axios"
import { ElMessage, ElMessageBox } from "element-plus"
import { useRoute, useRouter } from "vue-router"
import { EditPen, Plus, Refresh, Search, View as ViewIcon } from "@element-plus/icons-vue"
import { useDatasourceStore } from "@/store/datasource"
import { useAuthStore } from "@/store/auth"

const props = withDefaults(defineProps<{
  embedded?: boolean
  autoCreate?: boolean
  preferredDatasourceId?: number | null
}>(), {
  embedded: false,
  autoCreate: false,
  preferredDatasourceId: null,
})

const emit = defineEmits<{
  (event: "saved", payload: { datasource_id: number | null }): void
  (event: "closed"): void
}>()

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
  semantic_model_json: Record<string, unknown> | null
  drill_config_json: Record<string, unknown> | null
  last_refresh_status: string | null
  last_refresh_row_count: number
  last_refresh_at: string | null
  status: string
  visibility: string
}

type StepKey = "source" | "fields" | "publish"
type FieldRole = "ignore" | "dimension" | "metric"
type FieldRoleFilter = FieldRole | "all"

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

interface FieldRoleConfig {
  key: string
  table: string
  column: string
  type: string
  description: string
  role: FieldRole
  alias: string
  aggregation: string
}

const datasourceStore = useDatasourceStore()
const authStore = useAuthStore()
const route = useRoute()
const router = useRouter()
const embedded = computed(() => props.embedded)
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
const fieldRoleView = ref<FieldRoleFilter>("all")
const fieldRoleConfigs = ref<FieldRoleConfig[]>([])
const filters = ref<string[]>([])
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
const previewLoading = ref(false)
const aiConfigLoading = ref(false)
const previewRows = ref<Record<string, unknown>[]>([])
const rawPreviewColumns = ref<string[]>([])
const semanticModelDraft = ref<Record<string, unknown> | null>(null)
const drillConfig = ref<DrillConfig>({ dimensions: [], metrics: [], paths: [] })
const newDrillPath = reactive({
  source_dimension_id: "",
  target_dimension_id: "",
  label: "",
})
const saveAndPublish = ref(false)
const datasetPreviewVisible = ref(false)
const datasetPreviewLoading = ref(false)
const datasetPreviewTitle = ref("数据集预览")
const datasetPreviewRows = ref<Record<string, unknown>[]>([])
const datasetPreviewColumns = ref<string[]>([])
const datasetRefreshLoading = ref<Record<number, boolean>>({})
const semanticModelVisible = ref(false)
const semanticModelLoading = ref(false)
const semanticModelSaving = ref(false)
const semanticModelValidating = ref(false)
const semanticModelText = ref("")
const semanticDataset = reactive<{ id: number | null; name: string }>({
  id: null,
  name: "",
})

const steps: { key: StepKey; title: string; subtitle: string }[] = [
  { key: "source", title: "数据范围", subtitle: "数据源与主表" },
  { key: "fields", title: "业务口径", subtitle: "维度、筛选、指标" },
  { key: "publish", title: "保存发布", subtitle: "权限与摘要" },
]

const routeDatasourceId = computed(() => {
  const raw = route.query.datasource_id
  const value = Array.isArray(raw) ? raw[0] : raw
  const numericValue = Number(value)
  return Number.isFinite(numericValue) && numericValue > 0 ? numericValue : null
})
const shouldOpenCreateFromRoute = computed(() => route.query.create === "dataset")

const statusOptions = [
  { label: "全部", value: "all" },
  { label: "已发布", value: "published" },
  { label: "待审批", value: "pending_review" },
  { label: "草稿", value: "draft" },
]

const roleOptions = [
  { label: "忽略", value: "ignore" },
  { label: "维度", value: "dimension" },
  { label: "指标", value: "metric" },
]

const aggregationOptions = [
  { label: "求和 SUM", value: "SUM" },
  { label: "计数 COUNT", value: "COUNT" },
  { label: "平均 AVG", value: "AVG" },
  { label: "最大 MAX", value: "MAX" },
  { label: "最小 MIN", value: "MIN" },
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
const canApproveDatasets = computed(() =>
  ["dept_admin", "org_admin", "super_admin"].includes(authStore.profile?.role || "")
)
const orgVisibilityApprovalRequired = computed(() =>
  form.visibility === "org" && saveAndPublish.value && !canApproveDatasets.value
)

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

const visibleFieldConfigs = computed(() => {
  const q = fieldKeyword.value.trim().toLowerCase()
  const byRole = fieldRoleView.value === "all"
    ? fieldRoleConfigs.value
    : fieldRoleConfigs.value.filter((config) => config.role === fieldRoleView.value)
  if (!q) return byRole
  return byRole.filter((config) =>
    [config.column, config.key, config.type, config.description, config.alias].some((item) =>
      item.toLowerCase().includes(q)
    )
  )
})

const dimensionConfigs = computed(() =>
  fieldRoleConfigs.value.filter((config) => config.role === "dimension")
)

const metricConfigs = computed(() =>
  fieldRoleConfigs.value.filter((config) => config.role === "metric")
)

const fieldRoleTabs = computed(() => {
  const counts: Record<FieldRoleFilter, number> = {
    all: fieldRoleConfigs.value.length,
    dimension: dimensionConfigs.value.length,
    metric: metricConfigs.value.length,
    ignore: fieldRoleConfigs.value.filter((config) => config.role === "ignore").length,
  }
  return [
    { label: "全部", value: "all" as const, count: counts.all },
    { label: "维度", value: "dimension" as const, count: counts.dimension },
    { label: "指标", value: "metric" as const, count: counts.metric },
    { label: "忽略", value: "ignore" as const, count: counts.ignore },
  ]
})

const modelQualityItems = computed(() => [
  {
    label: "维度",
    value: selectedColumns.value.length,
    hint: selectedColumns.value.length ? "分析粒度已设置" : "至少选择一个分组字段",
    tone: "dimension",
  },
  {
    label: "指标",
    value: metricConfigs.value.length,
    hint: metricConfigs.value.length ? "可生成聚合结果" : "建议选择数值字段",
    tone: "metric",
  },
  {
    label: "筛选",
    value: filters.value.length,
    hint: filters.value.length ? "已限制数据范围" : "可选，用于控制数据集范围",
    tone: "filter",
  },
])

const selectedColumns = computed(() =>
  dimensionConfigs.value.map((config) => ({
    ...config,
    label: config.alias || config.key,
  }))
)

const dimensionPayloads = computed(() =>
  dimensionConfigs.value.map((config) => ({
    field: config.key,
    alias: config.alias.trim() || config.column,
  }))
)

const metricPayloads = computed(() =>
  metricConfigs.value.map((config) => ({
    field: config.key,
    aggregation: config.aggregation,
    alias: config.alias.trim() || defaultMetricAlias(config),
  }))
)

const metricExpressions = computed(() =>
  metricConfigs.value.map((config) => `${config.aggregation}(${config.key})`)
)

const derivedMetricCandidates = computed(() =>
  metricConfigs.value.map((config) => ({
    key: `${config.aggregation}:${config.key}`,
    label: config.alias.trim() || defaultMetricAlias(config),
    expression: `${config.aggregation}(${config.key})`,
  }))
)

const aggregations = metricExpressions

const drillDimensionOptions = computed(() => {
  const dimensions = drillConfig.value.dimensions.length
    ? drillConfig.value.dimensions
    : drillConfigFromSemantic(buildSemanticModelFromCurrentFields()).dimensions
  return dimensions.filter((dimension) => dimension.enabled)
})

const previewColumns = computed(() => {
  return rawPreviewColumns.value
})

const filterValueDisabled = computed(() => ["IS NULL", "IS NOT NULL"].includes(filterOperator.value))

const derivedPreviewText = computed(() => {
  const name = derivedName.value.trim()
  const expression = derivedExpression.value.trim()
  return name && expression ? `${name} = ${expression}` : ""
})

const joinLeftColumnOptions = computed(() => columnsForTable(joinLeftTable.value))
const joinRightColumnOptions = computed(() => columnsForTable(joinRightTable.value))

const semanticModelTitle = computed(() =>
  semanticDataset.name ? `${semanticDataset.name} - 语义层` : "语义层"
)

const semanticModelCounts = computed(() => {
  const model = parseSemanticModelText(false)
  return {
    dimensions: Array.isArray(model?.dimensions) ? model.dimensions.length : 0,
    metrics: Array.isArray(model?.metrics) ? model.metrics.length : 0,
    timeDimensions: Array.isArray(model?.time_dimensions) ? model.time_dimensions.length : 0,
    synonyms: Array.isArray(model?.synonyms) ? model.synonyms.length : 0,
  }
})

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

const datasetStatusLabel = (status: string) => {
  const map: Record<string, string> = {
    published: "已发布",
    pending_review: "待审批",
    draft: "草稿",
    archived: "已归档",
  }
  return map[status] || status
}

const datasetStatusTagType = (status: string) => {
  const map: Record<string, "success" | "warning" | "info"> = {
    published: "success",
    pending_review: "warning",
    draft: "info",
    archived: "info",
  }
  return map[status] || "info"
}

const normalizeList = (value: unknown) => (Array.isArray(value) ? value.map(String).filter(Boolean) : [])
const rawList = (value: unknown) => (Array.isArray(value) ? value : [])

const countList = (value: Record<string, unknown> | null, key: string) => normalizeList(value?.[key]).length

const fieldItemName = (item: unknown) => {
  if (typeof item === "object" && item !== null) {
    const value = item as Record<string, unknown>
    return String(value.field || value.name || value.key || "").trim()
  }
  return String(item || "").trim()
}

const fieldItemAlias = (item: unknown) => {
  if (typeof item === "object" && item !== null) {
    const value = item as Record<string, unknown>
    return String(value.alias || value.label || value.display_name || "").trim()
  }
  return ""
}

const fieldItemText = (item: unknown) => {
  const name = fieldItemName(item)
  const alias = fieldItemAlias(item)
  return alias && alias !== name ? `${alias} (${name})` : name
}

const textFromJson = (value: Record<string, unknown> | null, key: string) =>
  rawList(value?.[key]).map(fieldItemText).filter(Boolean).join(", ")

const dimensionText = (value: Record<string, unknown> | null) =>
  textFromJson(value, "dimensions") || textFromJson(value, "fields") || "-"

const metricText = (
  fieldsJson: Record<string, unknown> | null,
  aggregationsJson: Record<string, unknown> | null
) => textFromJson(aggregationsJson, "aggregations") || textFromJson(fieldsJson, "metrics") || "-"

const hasBusinessLogic = (row: DatasetItem) =>
  countList(row.filters_json, "filters") > 0 ||
  countList(row.aggregations_json, "aggregations") > 0 ||
  countList(row.fields_json, "metrics") > 0 ||
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

const fieldRoleLabel = (role: FieldRole) => {
  const map: Record<FieldRole, string> = {
    ignore: "未使用",
    dimension: "维度",
    metric: "指标",
  }
  return map[role]
}

const fieldRoleHint = (role: FieldRole) => {
  if (role === "dimension") return "作为分组、筛选和下钻字段"
  if (role === "ignore") return "不会进入当前数据集口径"
  return ""
}

const metricExpressionLabel = (config: FieldRoleConfig) => `${config.aggregation}(${config.column})`

const firstTableExcept = (tableName: string) =>
  schemaTables.value.find((table) => table.name !== tableName)?.name || tableName

const firstColumnName = (tableName: string) => columnsForTable(tableName)[0]?.name || ""

const isNumericColumn = (column: SchemaColumn) =>
  /(int|number|decimal|numeric|float|double|real|money|amount|price|qty|quantity)/i.test(
    `${column.type} ${column.name}`
  ) && !/(^id$|_id$|code|no|number|phone|year|month|day|date|time)/i.test(column.name)

const defaultAggregationForColumn = (column: SchemaColumn) => (isNumericColumn(column) ? "SUM" : "COUNT")

const defaultMetricAlias = (config: FieldRoleConfig) =>
  `${config.aggregation.toLowerCase()}_${config.column}`

const suggestedRoleForColumn = (column: SchemaColumn, index: number): FieldRole => {
  if (index >= 12) return "ignore"
  return isNumericColumn(column) ? "metric" : "dimension"
}

const createFieldRoleConfig = (
  tableName: string,
  column: SchemaColumn,
  index: number,
  role?: FieldRole
): FieldRoleConfig => ({
  key: columnKey(tableName, column.name),
  table: tableName,
  column: column.name,
  type: column.type,
  description: column.description || "",
  role: role || suggestedRoleForColumn(column, index),
  alias: column.name,
  aggregation: defaultAggregationForColumn(column),
})

const cloneJson = <T,>(value: T): T => JSON.parse(JSON.stringify(value))

const semanticId = (value: string, seen: Set<string>) => {
  const base = value
    .toLowerCase()
    .replace(/[^a-z0-9_]/g, "_")
    .replace(/^_+|_+$/g, "") || "field"
  const normalized = /^[a-z_]/.test(base) ? base : `f_${base}`
  let candidate = normalized
  let index = 2
  while (seen.has(candidate)) {
    candidate = `${normalized}_${index}`
    index += 1
  }
  seen.add(candidate)
  return candidate
}

const isTimeColumnConfig = (config: FieldRoleConfig) =>
  /(date|time|datetime|timestamp|day|month|year)/i.test(`${config.type} ${config.column}`)

const semanticFieldColumn = (field: string) => {
  const index = field.indexOf(".")
  return index === -1 ? field : field.slice(index + 1)
}

const semanticFieldTable = (field: string) => {
  const index = field.indexOf(".")
  return index === -1 ? form.table : field.slice(0, index)
}

const buildSemanticModelFromCurrentFields = () => {
  const seen = new Set<string>()
  const dimensions: Array<Record<string, unknown>> = []
  const timeDimensions: Array<Record<string, unknown>> = []
  const metrics: Array<Record<string, unknown>> = []
  const draftDimensionIds = new Map<string, string>()
  rawList(semanticModelDraft.value?.dimensions).forEach((item) => {
    if (!item || typeof item !== "object") return
    const value = item as Record<string, unknown>
    draftDimensionIds.set(String(value.field || "").toLowerCase(), String(value.id || ""))
  })
  rawList(semanticModelDraft.value?.time_dimensions).forEach((item) => {
    if (!item || typeof item !== "object") return
    const value = item as Record<string, unknown>
    draftDimensionIds.set(String(value.field || "").toLowerCase(), String(value.id || ""))
  })
  const draftMetricIds = new Map<string, string>()
  rawList(semanticModelDraft.value?.metrics).forEach((item) => {
    if (!item || typeof item !== "object") return
    const value = item as Record<string, unknown>
    const key = `${String(value.aggregation || "").toLowerCase()}:${String(value.field || "").toLowerCase()}`
    draftMetricIds.set(key, String(value.id || ""))
  })

  dimensionConfigs.value.forEach((config) => {
    const item = {
      id: semanticId(draftDimensionIds.get(config.key.toLowerCase()) || config.column, seen),
      field: config.key,
      label: config.alias.trim() || config.column,
    }
    if (isTimeColumnConfig(config)) {
      timeDimensions.push({ ...item, granularity: "day" })
    } else {
      dimensions.push(item)
    }
  })

  metricConfigs.value.forEach((config) => {
    const metricKey = `${config.aggregation.toLowerCase()}:${config.key.toLowerCase()}`
    metrics.push({
      id: semanticId(draftMetricIds.get(metricKey) || `${config.aggregation.toLowerCase()}_${config.column}`, seen),
      field: config.key,
      label: config.alias.trim() || defaultMetricAlias(config),
      aggregation: config.aggregation.toLowerCase(),
    })
  })

  const draftSynonyms = rawList(semanticModelDraft.value?.synonyms)
  const validIds = new Set([...dimensions, ...timeDimensions, ...metrics].map((item) => String(item.id)))
  const synonyms = draftSynonyms.filter((item) => {
    if (!item || typeof item !== "object") return false
    const targetId = String((item as Record<string, unknown>).target_id || "")
    return !targetId || validIds.has(targetId)
  })

  return {
    dimensions,
    metrics,
    time_dimensions: timeDimensions,
    synonyms,
  }
}

const drillKindForColumn = (column: string, time = false) => {
  const lower = column.toLowerCase()
  if (time) return "time"
  if (lower.includes("equip")) return "equipment"
  if (lower.includes("alarm") || lower.includes("error")) return "alarm"
  if (lower.includes("site")) return "site"
  if (lower.includes("line")) return "line"
  if (lower.includes("shift")) return "shift"
  if (lower.includes("step") || lower.includes("process")) return "process"
  if (lower.includes("product") || lower.includes("sku") || lower.includes("part")) return "product"
  if (lower.endsWith("id") || lower.includes("code")) return "code"
  return "category"
}

const drillConfigFromSemantic = (semanticModel: Record<string, any>): DrillConfig => {
  const dimensions: DrillDimension[] = []
  const dimensionItems = rawList(semanticModel.dimensions)
  const timeItems = rawList(semanticModel.time_dimensions)
  dimensionItems.forEach((item) => {
    if (!item || typeof item !== "object") return
    const value = item as Record<string, unknown>
    const field = String(value.field || "")
    const column = semanticFieldColumn(field)
    dimensions.push({
      id: String(value.id || column),
      table: semanticFieldTable(field),
      column,
      label: String(value.label || value.id || column),
      kind: drillKindForColumn(column),
      enabled: true,
    })
  })
  timeItems.forEach((item) => {
    if (!item || typeof item !== "object") return
    const value = item as Record<string, unknown>
    const field = String(value.field || "")
    const column = semanticFieldColumn(field)
    dimensions.push({
      id: String(value.id || column),
      table: semanticFieldTable(field),
      column,
      label: String(value.label || value.id || column),
      kind: drillKindForColumn(column, true),
      enabled: true,
    })
  })

  const metrics: DrillMetric[] = rawList(semanticModel.metrics).flatMap((item) => {
    if (!item || typeof item !== "object") return []
    const value = item as Record<string, unknown>
    const field = String(value.field || "")
    const column = field === "*" ? "*" : semanticFieldColumn(field)
    return [{
      id: String(value.id || column),
      table: field === "*" ? form.table : semanticFieldTable(field),
      column,
      label: String(value.label || value.id || column),
      aggregation: String(value.aggregation || "sum"),
      enabled: true,
    }]
  })

  return { dimensions, metrics, paths: [] }
}

const normalizeDrillConfig = (value: unknown): DrillConfig => {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    return { dimensions: [], metrics: [], paths: [] }
  }
  const source = value as Record<string, unknown>
  const dimensions = rawList(source.dimensions).flatMap((item) => {
    if (!item || typeof item !== "object") return []
    const value = item as Record<string, unknown>
    return [{
      id: String(value.id || ""),
      table: String(value.table || form.table),
      column: String(value.column || ""),
      label: String(value.label || value.column || value.id || ""),
      kind: String(value.kind || "category"),
      enabled: value.enabled !== false,
    }]
  }).filter((item) => item.id && item.column)
  const metrics = rawList(source.metrics).flatMap((item) => {
    if (!item || typeof item !== "object") return []
    const value = item as Record<string, unknown>
    return [{
      id: String(value.id || ""),
      table: String(value.table || form.table),
      column: String(value.column || ""),
      label: String(value.label || value.column || value.id || ""),
      aggregation: String(value.aggregation || "sum"),
      enabled: value.enabled !== false,
    }]
  }).filter((item) => item.id && item.column)
  const paths = rawList(source.paths).flatMap((item) => {
    if (!item || typeof item !== "object") return []
    const value = item as Record<string, unknown>
    return [{
      id: String(value.id || `${value.source_dimension_id}__${value.target_dimension_id}`),
      source_dimension_id: String(value.source_dimension_id || ""),
      target_dimension_id: String(value.target_dimension_id || ""),
      label: String(value.label || "继续下钻"),
      action: String(value.action || "group_by"),
      enabled: value.enabled !== false,
    }]
  }).filter((item) => item.id && item.source_dimension_id && item.target_dimension_id)
  return { dimensions, metrics, paths }
}

const syncDrillConfigFromSemantic = (semanticModel: Record<string, any>) => {
  const base = drillConfigFromSemantic(semanticModel)
  const validDimensionIds = new Set(base.dimensions.map((item) => item.id))
  const existingPaths = drillConfig.value.paths.filter((path) =>
    validDimensionIds.has(path.source_dimension_id) && validDimensionIds.has(path.target_dimension_id)
  )
  drillConfig.value = {
    ...base,
    paths: existingPaths,
  }
}

const drillConfigForSave = () => {
  const semanticModel = buildSemanticModelFromCurrentFields()
  const base = drillConfigFromSemantic(semanticModel)
  const validDimensionIds = new Set(base.dimensions.map((item) => item.id))
  return {
    ...base,
    paths: drillConfig.value.paths.filter((path) =>
      validDimensionIds.has(path.source_dimension_id) && validDimensionIds.has(path.target_dimension_id)
    ),
  }
}

const drillDimensionLabel = (id: string) =>
  drillDimensionOptions.value.find((dimension) => dimension.id === id)?.label || id

const resetNewDrillPath = () => {
  newDrillPath.source_dimension_id = ""
  newDrillPath.target_dimension_id = ""
  newDrillPath.label = ""
}

const uniquePush = (list: string[], value: string) => {
  const normalized = value.trim()
  if (normalized && !list.includes(normalized)) {
    list.push(normalized)
  }
}

const formatSemanticModel = (value: unknown) =>
  JSON.stringify(
    value || { dimensions: [], metrics: [], time_dimensions: [], synonyms: [] },
    null,
    2
  )

const parseSemanticModelText = (showMessage = true): Record<string, any> | null => {
  try {
    const value = JSON.parse(semanticModelText.value || "{}")
    if (!value || typeof value !== "object" || Array.isArray(value)) {
      throw new Error("语义模型必须是 JSON 对象")
    }
    return value as Record<string, any>
  } catch (error: any) {
    if (showMessage) {
      ElMessage.error(error.message || "语义模型 JSON 不合法")
    }
    return null
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

const syncFieldRoleConfigs = (roleMode: "suggest" | "ignore" = "suggest") => {
  const previous = new Map(fieldRoleConfigs.value.map((config) => [config.key, config]))
  fieldRoleConfigs.value = currentColumns.value.map((column, index) => {
    const key = columnKey(form.table, column.name)
    const old = previous.get(key)
    if (old) {
      return {
        ...old,
        table: form.table,
        column: column.name,
        type: column.type,
        description: column.description || "",
      }
    }
    return createFieldRoleConfig(
      form.table,
      column,
      index,
      roleMode === "ignore" ? "ignore" : undefined
    )
  })
}

const parseMetricConfig = (item: unknown) => {
  if (typeof item === "object" && item !== null) {
    const value = item as Record<string, unknown>
    const expression = String(value.expression || "").trim()
    if (expression) {
      const match = expression.match(/^\s*(SUM|AVG|COUNT|MIN|MAX)\s*\(\s*(.*?)\s*\)\s*$/i)
      if (match) {
        return {
          field: match[2],
          aggregation: match[1].toUpperCase(),
          alias: fieldItemAlias(value),
        }
      }
    }
    return {
      field: fieldItemName(value),
      aggregation: String(value.aggregation || value.fn || "SUM").toUpperCase(),
      alias: fieldItemAlias(value),
    }
  }
  const text = String(item || "").trim()
  const match = text.match(/^\s*(SUM|AVG|COUNT|MIN|MAX)\s*\(\s*(.*?)\s*\)\s*$/i)
  if (!match) return null
  return {
    field: match[2],
    aggregation: match[1].toUpperCase(),
    alias: "",
  }
}

const applySavedFieldModel = (dataset: DatasetItem) => {
  syncFieldRoleConfigs("ignore")
  const byKey = new Map(fieldRoleConfigs.value.map((config) => [config.key, config]))
  const savedDimensions = rawList(dataset.fields_json?.dimensions)
  const legacyFields = rawList(dataset.fields_json?.fields)
  for (const item of savedDimensions.length ? savedDimensions : legacyFields) {
    const field = fieldItemName(item)
    const key = field.includes(".") ? field : columnKey(form.table, field)
    const config = byKey.get(key)
    if (config) {
      config.role = "dimension"
      config.alias = fieldItemAlias(item) || config.alias || config.column
    }
  }

  const savedMetricItems = rawList(dataset.fields_json?.metrics)
  const legacyMetricItems = rawList(dataset.aggregations_json?.aggregations)
  for (const item of savedMetricItems.length ? savedMetricItems : legacyMetricItems) {
    const metric = parseMetricConfig(item)
    if (!metric?.field) continue
    const key = metric.field.includes(".") ? metric.field : columnKey(form.table, metric.field)
    const config = byKey.get(key)
    if (config) {
      config.role = "metric"
      config.aggregation = metric.aggregation
      config.alias = metric.alias || config.alias || defaultMetricAlias(config)
    }
  }
}

const resetForm = (preferredDatasourceId: number | null = null) => {
  editingId.value = null
  activeStep.value = "source"
  form.name = ""
  form.description = ""
  form.datasource_id = preferredDatasourceId || props.preferredDatasourceId || datasourceStore.currentId || datasourceStore.datasources[0]?.id || null
  form.table = ""
  form.visibility = "private"
  fieldRoleConfigs.value = []
  filters.value = []
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
  fieldKeyword.value = ""
  previewRows.value = []
  rawPreviewColumns.value = []
  semanticModelDraft.value = null
  drillConfig.value = { dimensions: [], metrics: [], paths: [] }
  resetNewDrillPath()
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

const openCreate = async (preferredDatasourceId: number | null = null) => {
  resetForm(preferredDatasourceId)
  await ensureDatasourceReady()
  drawerVisible.value = true
}

const clearCreateDatasetQuery = () => {
  const nextQuery = { ...route.query }
  delete nextQuery.create
  delete nextQuery.datasource_id
  delete nextQuery.from
  router.replace({ path: route.path, query: nextQuery })
}

const openCreateFromRoute = async () => {
  if (embedded.value) return
  if (!shouldOpenCreateFromRoute.value) return
  await openCreate(routeDatasourceId.value)
  clearCreateDatasetQuery()
}

const handleDrawerClosed = () => {
  if (embedded.value) {
    emit("closed")
  }
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
  applySavedFieldModel(dataset)
  filters.value = normalizeList(dataset.filters_json?.filters)
  derivedColumns.value = normalizeList(dataset.derived_columns_json?.expressions)
  joins.value = normalizeList(dataset.joins_json?.joins)
  semanticModelDraft.value = dataset.semantic_model_json ? cloneJson(dataset.semantic_model_json) : null
  drillConfig.value = normalizeDrillConfig(dataset.drill_config_json)
  activeStep.value = "source"
  drawerVisible.value = true
}

const inferTableFromFields = (fieldsJson: Record<string, unknown> | null) => {
  const firstField = normalizeList(fieldsJson?.dimensions)[0] || normalizeList(fieldsJson?.fields)[0]
  if (!firstField?.includes(".")) return ""
  return firstField.split(".")[0]
}

const handleDatasourceChange = async () => {
  form.table = ""
  fieldRoleConfigs.value = []
  filterField.value = ""
  previewRows.value = []
  rawPreviewColumns.value = []
  semanticModelDraft.value = null
  drillConfig.value = { dimensions: [], metrics: [], paths: [] }
  resetNewDrillPath()
  await ensureDatasourceReady()
}

const selectTable = (tableName: string) => {
  form.table = tableName
  syncFieldRoleConfigs("suggest")
  filterField.value = currentFieldOptions.value[0]?.key || ""
  joinLeftTable.value = tableName
  joinLeftColumn.value = firstColumnName(tableName)
  joinRightTable.value = firstTableExcept(tableName)
  joinRightColumn.value = firstColumnName(joinRightTable.value)
  previewRows.value = []
  rawPreviewColumns.value = []
  semanticModelDraft.value = null
  drillConfig.value = { dimensions: [], metrics: [], paths: [] }
  resetNewDrillPath()
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

const setFieldRole = (key: string, role: FieldRole) => {
  const config = fieldRoleConfigs.value.find((item) => item.key === key)
  if (!config) return
  config.role = role
  handleRoleChange(config)
}

const handleRoleChange = (config: FieldRoleConfig) => {
  semanticModelDraft.value = null
  if (config.role === "metric") {
    const column = currentColumns.value.find((item) => item.name === config.column)
    if (column && config.aggregation === "SUM" && !isNumericColumn(column)) {
      config.aggregation = "COUNT"
    }
  }
  if (!config.alias.trim()) {
    config.alias = config.role === "metric" ? defaultMetricAlias(config) : config.column
  }
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

const applyAiFieldRoles = (roles: Array<Record<string, unknown>>) => {
  const byKey = new Map(fieldRoleConfigs.value.map((config) => [config.key.toLowerCase(), config]))
  roles.forEach((role) => {
    const field = String(role.field || "")
    if (!field || field === "*") return
    const key = field.includes(".") ? field : columnKey(form.table, field)
    const config = byKey.get(key.toLowerCase())
    if (!config) return
    const nextRole = role.role === "metric" ? "metric" : "dimension"
    config.role = nextRole
    config.alias = String(role.alias || config.alias || config.column)
    if (nextRole === "metric") {
      config.aggregation = String(role.aggregation || config.aggregation || "SUM").toUpperCase()
    }
    handleRoleChange(config)
  })
}

const generateDatasetAiConfig = async () => {
  if (!form.datasource_id || !form.table) {
    ElMessage.warning("请先选择数据源和主表")
    return
  }
  aiConfigLoading.value = true
  try {
    const response = await axios.post("/api/datasets/ai-config/suggest", {
      dataset_id: editingId.value || null,
      datasource_id: form.datasource_id,
      table: form.table,
      fields_json: {
        table: form.table,
        dimensions: dimensionPayloads.value,
        fields: dimensionPayloads.value.map((item) => item.field),
        metrics: metricPayloads.value,
      },
      aggregations_json: { aggregations: metricExpressions.value },
      semantic_model_json: buildSemanticModelFromCurrentFields(),
      drill_config_json: drillConfig.value,
    })
    const nextSemanticModel = response.data.semantic_model || null
    applyAiFieldRoles(response.data.field_roles || [])
    semanticModelDraft.value = nextSemanticModel
    drillConfig.value = normalizeDrillConfig(response.data.drill_config)
    const warnings = response.data.warnings || []
    if (warnings.length) {
      ElMessage.warning(warnings[0])
    } else {
      ElMessage.success("AI 自动配置已应用到当前草稿")
    }
    logicTab.value = "drill"
  } catch (error: any) {
    ElMessage.error(error.response?.data?.detail || "AI 自动配置失败")
  } finally {
    aiConfigLoading.value = false
  }
}

const generateLocalDrillPaths = () => {
  const semanticModel = buildSemanticModelFromCurrentFields()
  const base = drillConfigFromSemantic(semanticModel)
  const dimensions = base.dimensions.filter((dimension) => dimension.kind !== "time")
  const timeDimensions = base.dimensions.filter((dimension) => dimension.kind === "time")
  const paths: DrillPath[] = []
  dimensions.forEach((source) => {
    const targets = [...dimensions.filter((dimension) => dimension.id !== source.id), ...timeDimensions.slice(0, 1)]
    targets.slice(0, 3).forEach((target) => {
      const id = `${source.id}__${target.id}`
      if (paths.some((path) => path.id === id)) return
      paths.push({
        id,
        source_dimension_id: source.id,
        target_dimension_id: target.id,
        label: target.kind === "time" ? "看时间趋势" : `看${target.label}分布`,
        action: "group_by",
        enabled: true,
      })
    })
  })
  drillConfig.value = { ...base, paths }
  resetNewDrillPath()
  logicTab.value = "drill"
}

const addDrillPath = () => {
  const sourceId = newDrillPath.source_dimension_id
  const targetId = newDrillPath.target_dimension_id
  if (!sourceId || !targetId || sourceId === targetId) {
    ElMessage.warning("请选择不同的起点维度和下钻维度")
    return
  }
  if (!drillConfig.value.dimensions.length) {
    syncDrillConfigFromSemantic(buildSemanticModelFromCurrentFields())
  }
  const id = `${sourceId}__${targetId}`
  if (drillConfig.value.paths.some((path) => path.id === id)) {
    ElMessage.warning("这条下钻路径已存在")
    return
  }
  drillConfig.value.paths.push({
    id,
    source_dimension_id: sourceId,
    target_dimension_id: targetId,
    label: newDrillPath.label.trim() || `看${drillDimensionLabel(targetId)}分布`,
    action: "group_by",
    enabled: true,
  })
  resetNewDrillPath()
}

const removeDrillPath = (id: string) => {
  drillConfig.value.paths = drillConfig.value.paths.filter((path) => path.id !== id)
}

const fetchPreview = async () => {
  if (!form.datasource_id || !form.table) {
    ElMessage.warning("请先选择数据源和主表")
    return
  }
  previewLoading.value = true
  try {
    const response = await axios.post("/api/datasets/preview-draft", {
      ...buildPayload(),
      limit: 30,
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

const openSemanticModel = async (dataset: DatasetItem) => {
  semanticDataset.id = dataset.id
  semanticDataset.name = dataset.name
  semanticModelVisible.value = true
  semanticModelLoading.value = true
  semanticModelText.value = formatSemanticModel(dataset.semantic_model_json)
  try {
    const response = await axios.get(`/api/datasets/${semanticDataset.id}/semantic-model`)
    semanticModelText.value = formatSemanticModel(response.data.semantic_model)
  } catch (error: any) {
    ElMessage.error(error.response?.data?.detail || "语义层加载失败")
  } finally {
    semanticModelLoading.value = false
  }
}

const validateSemanticModel = async () => {
  if (!semanticDataset.id) return
  const semanticModel = parseSemanticModelText()
  if (!semanticModel) return
  semanticModelValidating.value = true
  try {
    const response = await axios.post(`/api/datasets/${semanticDataset.id}/validate-semantic-model`, {
      semantic_model: semanticModel,
    })
    semanticModelText.value = formatSemanticModel(response.data.semantic_model)
    ElMessage.success("语义层校验通过")
  } catch (error: any) {
    ElMessage.error(error.response?.data?.detail || "语义层校验失败")
  } finally {
    semanticModelValidating.value = false
  }
}

const saveSemanticModel = async () => {
  if (!semanticDataset.id) return
  const semanticModel = parseSemanticModelText()
  if (!semanticModel) return
  semanticModelSaving.value = true
  try {
    const response = await axios.put(`/api/datasets/${semanticDataset.id}/semantic-model`, {
      semantic_model: semanticModel,
    })
    semanticModelText.value = formatSemanticModel(response.data.semantic_model)
    ElMessage.success("语义层已保存")
    semanticModelVisible.value = false
    await fetchDatasets()
  } catch (error: any) {
    ElMessage.error(error.response?.data?.detail || "语义层保存失败")
  } finally {
    semanticModelSaving.value = false
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
  if (dimensionConfigs.value.length === 0 && metricConfigs.value.length === 0) {
    ElMessage.warning("请至少选择一个维度字段或指标")
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
    dimensions: dimensionPayloads.value,
    fields: dimensionPayloads.value.map((item) => item.field),
    dimension_labels: selectedColumns.value,
    field_labels: selectedColumns.value,
    metrics: metricPayloads.value,
  },
  filters_json: { filters: filters.value },
  derived_columns_json: { expressions: derivedColumns.value },
  joins_json: { joins: joins.value },
  aggregations_json: { aggregations: metricExpressions.value },
  semantic_model_json: buildSemanticModelFromCurrentFields(),
  drill_config_json: drillConfigForSave(),
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
    if (orgVisibilityApprovalRequired.value) {
      ElMessage.success("数据集已保存并提交审批")
    } else if (saveAndPublish.value) {
      ElMessage.success("数据集已保存并发布")
    } else {
      ElMessage.success("数据集已保存")
    }
    drawerVisible.value = false
    await fetchDatasets()
    if (embedded.value) {
      emit("saved", { datasource_id: form.datasource_id })
    }
  } catch (error: any) {
    ElMessage.error(error.response?.data?.detail || "数据集保存失败")
  } finally {
    saving.value = false
  }
}

const publishDataset = async (dataset: DatasetItem) => {
  const response = await axios.post(`/api/datasets/${dataset.id}/publish`)
  ElMessage.success(response.data?.status === "pending_review" ? "数据集已提交审批" : "数据集已发布")
  await fetchDatasets()
}

const approveDataset = async (dataset: DatasetItem) => {
  await axios.post(`/api/datasets/${dataset.id}/approve`)
  ElMessage.success("数据集已审批发布")
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
  // 数据源详情（schema/drill_config 等重字段）改为在打开数据集表单时按需懒加载
  // （见 ensureDatasourceReady），避免此处对每个数据源发一次详情请求造成 N+1。
  await fetchDatasets()
  if (embedded.value && props.autoCreate) {
    await openCreate(props.preferredDatasourceId)
    return
  }
  await openCreateFromRoute()
})

watch(
  () => [route.query.create, route.query.datasource_id, route.query.tab],
  async () => {
    if (embedded.value) return
    if (route.query.tab !== "datasets") return
    await openCreateFromRoute()
  }
)

watch(
  () => [props.autoCreate, props.preferredDatasourceId],
  async () => {
    if (!embedded.value || !props.autoCreate) return
    await openCreate(props.preferredDatasourceId)
  }
)
</script>

<style scoped>
.dataset-page {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.dataset-page--embedded,
.dataset-embedded-anchor {
  display: contents;
}

:global(.dataset-drawer-modal--embedded) {
  overflow-x: hidden;
}

:global(.dataset-drawer-modal--embedded .el-overlay-dialog) {
  overflow-x: hidden;
}

:global(.dataset-drawer-modal--embedded .el-drawer) {
  max-width: calc(100vw - 16px);
}

:global(.dataset-drawer-modal--embedded .el-drawer__body) {
  overflow-x: hidden;
}

.dataset-drawer--embedded :deep(.el-drawer__body) {
  padding: 14px;
  overflow-x: hidden;
}

.dataset-drawer--embedded :deep(.el-drawer__footer) {
  padding: 12px 14px;
}

.dataset-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  min-height: 36px;
}

.dataset-toolbar-title {
  display: flex;
  align-items: baseline;
  gap: 8px;
  min-width: 0;
}

.dataset-toolbar-title strong {
  color: var(--app-text);
  font-size: 16px;
  line-height: 1.4;
  white-space: nowrap;
}

.dataset-toolbar-title span {
  color: var(--app-text-muted);
  font-size: 12px;
  line-height: 1.4;
  white-space: nowrap;
}

.eyebrow {
  margin: 0 0 6px;
  color: var(--app-primary);
  font-size: 12px;
  font-weight: 700;
}

.dataset-toolbar-actions {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 8px;
  flex-wrap: wrap;
  margin-left: auto;
}

.dataset-toolbar-actions .page-segmented-tabs {
  flex-shrink: 0;
}

.search-input {
  width: 240px;
}

.muted,
.panel-title small,
.step-item small,
.dataset-name-cell span,
.dataset-model-cell span {
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

.dataset-model-cell {
  display: flex;
  flex-direction: column;
  gap: 4px;
  line-height: 1.35;
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

.embedded-designer-shell {
  grid-template-columns: minmax(0, 1fr);
  gap: 14px;
  min-height: min(760px, calc(100vh - 170px));
  max-width: 100%;
  overflow-x: hidden;
}

.embedded-designer-shell .step-rail {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 8px;
  min-width: 0;
}

.embedded-designer-shell .designer-panel,
.embedded-designer-shell .designer-section,
.embedded-designer-shell .field-panel,
.embedded-designer-shell .logic-panel,
.embedded-designer-shell .preview-panel,
.embedded-designer-shell .publish-panel,
.embedded-designer-shell .summary-panel {
  min-width: 0;
  max-width: 100%;
}

.embedded-designer-shell .field-layout,
.embedded-designer-shell .publish-layout,
.embedded-designer-shell .field-config-controls,
.embedded-designer-shell .advanced-builder-grid,
.embedded-designer-shell .model-summary-grid,
.embedded-designer-shell .join-sides,
.embedded-designer-shell .filter-builder,
.embedded-designer-shell .aggregation-builder,
.embedded-designer-shell .join-meta-row {
  grid-template-columns: minmax(0, 1fr);
}

.embedded-designer-shell .field-config-list,
.embedded-designer-shell .field-token-panel,
.embedded-designer-shell .selected-field-list.compact {
  max-width: 100%;
}

.embedded-designer-shell .section-head,
.embedded-designer-shell .fields-section-head,
.embedded-designer-shell .field-panel-hero,
.embedded-designer-shell .field-config-top,
.embedded-designer-shell .fields-head-actions {
  align-items: stretch;
  flex-direction: column;
}

.embedded-designer-shell .fields-head-actions,
.embedded-designer-shell .fields-health-pill {
  width: 100%;
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

.fields-section-head {
  align-items: flex-start;
}

.fields-section-head p {
  max-width: 680px;
}

.fields-head-actions {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
  justify-content: flex-end;
}

.fields-health-pill {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 5px;
  border: 1px solid var(--app-border-light);
  border-radius: 999px;
  background: var(--app-surface);
}

.fields-health-pill span {
  padding: 4px 10px;
  border-radius: 999px;
  color: var(--app-text-muted);
  background: var(--app-surface-muted);
  font-size: 12px;
  font-weight: 700;
  white-space: nowrap;
}

.field-layout,
.publish-layout {
  display: grid;
  grid-template-columns: minmax(420px, 1.04fr) minmax(420px, 0.96fr);
  gap: 16px;
}

.field-panel {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.field-panel-hero {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  padding: 14px;
  border: 1px solid rgba(15, 118, 110, 0.16);
  border-radius: var(--app-radius-sm);
  background:
    linear-gradient(135deg, rgba(15, 118, 110, 0.08), rgba(37, 99, 235, 0.05)),
    var(--app-surface);
}

.field-panel-hero strong,
.field-panel-hero small {
  display: block;
}

.field-panel-hero strong {
  margin-top: 3px;
  color: var(--app-text);
  font-size: 17px;
}

.field-panel-hero small {
  margin-top: 4px;
  color: var(--app-text-muted);
  line-height: 1.45;
}

.eyebrow {
  color: var(--app-primary);
  font-size: 12px;
  font-weight: 800;
}

.field-mode-tabs {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 8px;
}

.field-mode-tab {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  min-height: 40px;
  padding: 9px 10px;
  border: 1px solid var(--app-border-light);
  border-radius: var(--app-radius-xs);
  background: var(--app-surface-muted);
  color: var(--app-text-muted);
  cursor: pointer;
  transition: background var(--app-transition), border-color var(--app-transition), color var(--app-transition), transform var(--app-transition);
}

.field-mode-tab:hover {
  color: var(--app-text);
  background: var(--app-surface);
}

.field-mode-tab.active {
  border-color: rgba(15, 118, 110, 0.3);
  color: var(--app-primary);
  background: rgba(15, 118, 110, 0.08);
}

.field-mode-tab strong {
  font-size: 13px;
  font-variant-numeric: tabular-nums;
}

.field-search {
  margin-bottom: 0;
}

.field-config-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
  max-height: 560px;
  overflow: auto;
}

.field-config-row {
  position: relative;
  display: flex;
  flex-direction: column;
  gap: 10px;
  min-height: 132px;
  padding: 14px;
  border: 1px solid var(--app-border-light);
  border-radius: var(--app-radius-sm);
  background: var(--app-surface);
  overflow: hidden;
  transition: border-color var(--app-transition), box-shadow var(--app-transition), transform var(--app-transition);
}

.field-config-row:hover {
  border-color: rgba(15, 118, 110, 0.24);
  box-shadow: 0 10px 24px rgba(15, 23, 42, 0.08);
}

.field-config-row::before {
  content: "";
  position: absolute;
  inset: 0 auto 0 0;
  width: 4px;
  background: #cbd5e1;
}

.field-config-row.role-dimension {
  border-color: rgba(15, 118, 110, 0.28);
}

.field-config-row.role-metric {
  border-color: rgba(37, 99, 235, 0.28);
}

.field-config-row.role-dimension::before {
  background: var(--app-primary);
}

.field-config-row.role-metric::before {
  background: #2563eb;
}

.field-config-top {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  min-width: 0;
}

.field-config-main {
  display: flex;
  align-items: flex-start;
  gap: 9px;
  min-width: 0;
  flex: 1;
}

.role-dot {
  width: 9px;
  height: 9px;
  margin-top: 6px;
  border-radius: 50%;
  background: #cbd5e1;
  flex-shrink: 0;
}

.role-dimension .role-dot {
  background: var(--app-primary);
}

.role-metric .role-dot {
  background: #2563eb;
}

.field-config-main strong,
.field-config-main small {
  display: block;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.field-config-main strong {
  color: var(--app-text);
  font-size: 14px;
  line-height: 20px;
}

.field-config-main small {
  margin-top: 3px;
  color: var(--app-text-muted);
  font-size: 12px;
}

.field-config-tags {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-shrink: 0;
}

.role-label {
  display: inline-flex;
  align-items: center;
  min-height: 24px;
  padding: 0 8px;
  border-radius: 999px;
  color: var(--app-text-muted);
  background: var(--app-surface-muted);
  font-size: 12px;
  font-weight: 700;
}

.role-dimension .role-label {
  color: var(--app-primary);
  background: rgba(15, 118, 110, 0.1);
}

.role-metric .role-label {
  color: #1d4ed8;
  background: rgba(37, 99, 235, 0.1);
}

.field-config-controls {
  display: grid;
  grid-template-columns: minmax(170px, 0.85fr) minmax(170px, 1fr) minmax(132px, 0.72fr);
  align-items: end;
  gap: 10px;
}

.control-field {
  display: flex;
  flex-direction: column;
  gap: 6px;
  min-width: 0;
}

.control-field > span,
.field-role-hint {
  color: var(--app-text-muted);
  font-size: 12px;
  font-weight: 700;
}

.field-role-hint {
  display: flex;
  align-items: center;
  min-height: 32px;
  padding: 0 10px;
  border: 1px dashed var(--app-border-light);
  border-radius: var(--app-radius-xs);
  background: var(--app-surface-muted);
}

.role-segmented,
.alias-input,
.aggregation-select {
  width: 100%;
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

.model-overview {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
}

.model-overview-item {
  position: relative;
  padding: 13px 14px;
  border: 1px solid var(--app-border-light);
  border-radius: var(--app-radius-sm);
  background: var(--app-surface);
  overflow: hidden;
}

.model-overview-item::before {
  content: "";
  position: absolute;
  inset: 0 0 auto;
  height: 3px;
  background: #94a3b8;
}

.model-overview-item.tone-dimension::before {
  background: var(--app-primary);
}

.model-overview-item.tone-metric::before {
  background: #2563eb;
}

.model-overview-item.tone-filter::before {
  background: #d97706;
}

.model-overview-item span,
.model-overview-item small {
  display: block;
}

.model-overview-item span {
  color: var(--app-text-muted);
  font-size: 12px;
  font-weight: 700;
}

.model-overview-item strong {
  display: block;
  margin-top: 5px;
  color: var(--app-text);
  font-size: 24px;
  line-height: 1;
  font-variant-numeric: tabular-nums;
}

.model-overview-item small {
  margin-top: 7px;
  color: var(--app-text-muted);
  line-height: 1.35;
}

.logic-card {
  padding: 14px;
  border: 1px solid var(--app-border-light);
  border-radius: var(--app-radius-sm);
  background: var(--app-surface-muted);
}

.drill-config-card {
  display: grid;
  gap: 12px;
}

.drill-config-title {
  align-items: flex-start;
}

.drill-config-title div:first-child span,
.drill-config-title div:first-child small {
  display: block;
}

.drill-config-title div:first-child small {
  margin-top: 3px;
  color: var(--app-text-muted);
  font-size: 12px;
  font-weight: 500;
}

.drill-config-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  justify-content: flex-end;
}

.drill-summary-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
}

.drill-summary-grid div {
  min-height: 72px;
  padding: 12px;
  border: 1px solid rgba(15, 118, 110, 0.16);
  border-radius: var(--app-radius-xs);
  background: var(--app-surface);
}

.drill-summary-grid span,
.drill-summary-grid strong {
  display: block;
}

.drill-summary-grid span {
  color: var(--app-text-muted);
  font-size: 12px;
  font-weight: 700;
}

.drill-summary-grid strong {
  margin-top: 7px;
  color: var(--app-primary-dark);
  font-size: 22px;
  line-height: 1;
  font-variant-numeric: tabular-nums;
}

.drill-path-builder {
  display: grid;
  grid-template-columns: minmax(140px, 1fr) 24px minmax(140px, 1fr) minmax(180px, 1.2fr) auto;
  gap: 8px;
  align-items: center;
}

.drill-path-arrow {
  color: var(--app-primary);
  font-weight: 900;
  text-align: center;
}

.drill-path-list {
  display: grid;
  gap: 8px;
}

.drill-path-row {
  display: grid;
  grid-template-columns: minmax(180px, 0.85fr) minmax(180px, 1fr) auto auto;
  gap: 10px;
  align-items: center;
  min-height: 48px;
  padding: 9px 10px;
  border: 1px solid var(--app-border-light);
  border-radius: var(--app-radius-xs);
  background: var(--app-surface);
}

.drill-path-row.disabled {
  opacity: 0.62;
}

.drill-path-flow {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
  color: var(--app-text);
  font-size: 12px;
}

.drill-path-flow strong {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.drill-path-flow span {
  color: var(--app-primary);
  font-weight: 900;
}

.drill-path-label-input {
  min-width: 0;
}

.model-summary-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}

.selected-summary {
  padding: 12px 14px;
  border: 1px solid var(--app-border-light);
  border-radius: var(--app-radius-sm);
  background: var(--app-surface);
}

.dimension-summary {
  border-color: rgba(15, 118, 110, 0.18);
  background: linear-gradient(180deg, rgba(15, 118, 110, 0.055), rgba(15, 118, 110, 0)), var(--app-surface);
}

.metric-summary {
  border-color: rgba(37, 99, 235, 0.18);
  background: linear-gradient(180deg, rgba(37, 99, 235, 0.055), rgba(37, 99, 235, 0)), var(--app-surface);
}

.selected-summary-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 10px;
  font-weight: 700;
}

.selected-summary-head span,
.selected-summary-head small {
  display: block;
}

.selected-summary-head div small {
  margin-top: 3px;
  color: var(--app-text-muted);
  font-weight: 500;
  line-height: 1.35;
}

.selected-field-list.compact {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  max-height: 76px;
  overflow: auto;
}

.selected-field-chip {
  min-height: 28px;
  border-radius: 999px;
}

.selected-field-chip code {
  margin-left: 6px;
  color: inherit;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", monospace;
  font-size: 11px;
  opacity: 0.72;
}

.dimension-chip {
  border-color: rgba(15, 118, 110, 0.28);
  color: var(--app-primary);
  background: rgba(15, 118, 110, 0.08);
}

.metric-chip {
  border-color: rgba(37, 99, 235, 0.28);
  color: #1d4ed8;
  background: rgba(37, 99, 235, 0.08);
}

.empty-inline {
  display: inline-flex;
  align-items: center;
  min-height: 28px;
  padding: 0 10px;
  border: 1px dashed var(--app-border-light);
  border-radius: 999px;
  color: var(--app-text-muted);
  background: var(--app-surface-muted);
  font-size: 12px;
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

.candidate-section {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.candidate-section-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  color: var(--app-text-muted);
  font-size: 12px;
  line-height: 1.35;
}

.candidate-section-head span {
  color: var(--app-text);
  font-weight: 700;
}

.candidate-section-head small {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
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

.metric-token-panel {
  grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
  max-height: 132px;
}

.metric-token-panel button {
  display: flex;
  min-height: 50px;
  flex-direction: column;
  align-items: flex-start;
  justify-content: center;
  gap: 2px;
  text-align: left;
  white-space: normal;
}

.metric-token-panel strong,
.metric-token-panel small {
  display: block;
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.metric-token-panel strong {
  font-size: 12px;
  line-height: 1.35;
}

.metric-token-panel small {
  color: var(--app-text-muted);
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  font-size: 11px;
  line-height: 1.35;
}

.metric-token-empty {
  display: flex;
  align-items: center;
  min-height: 44px;
  padding: 10px 12px;
  border: 1px dashed var(--app-border);
  border-radius: var(--app-radius-xs);
  background: var(--app-surface-muted);
  color: var(--app-text-muted);
  font-size: 12px;
  line-height: 1.45;
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

.semantic-dialog-body {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.semantic-stat-row {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px;
}

.semantic-stat-row div {
  min-height: 70px;
  padding: 12px;
  border: 1px solid var(--app-border);
  border-radius: var(--app-radius-sm);
  background: var(--app-surface-muted);
}

.semantic-stat-row span,
.semantic-stat-row strong {
  display: block;
}

.semantic-stat-row span {
  color: var(--app-text-muted);
  font-size: 12px;
}

.semantic-stat-row strong {
  margin-top: 8px;
  color: var(--app-text);
  font-size: 24px;
  line-height: 1;
}

.semantic-json-editor :deep(.el-textarea__inner) {
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  font-size: 12px;
  line-height: 1.55;
}

.semantic-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.visibility-group {
  align-self: flex-start;
}

.visibility-approval-alert {
  max-width: 560px;
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
  .section-head {
    flex-direction: column;
  }

  .dataset-toolbar {
    align-items: flex-start;
    flex-direction: column;
  }

  .dataset-toolbar-actions,
  .fields-head-actions,
  .search-input {
    width: 100%;
  }

  .dataset-toolbar-actions,
  .fields-head-actions {
    justify-content: flex-start;
  }

  .dataset-toolbar-actions .page-segmented-tabs {
    max-width: 100%;
  }

  .designer-shell,
  .field-layout,
  .publish-layout,
  .field-config-controls,
      .advanced-builder-grid,
      .model-summary-grid,
      .drill-path-builder,
      .drill-path-row,
      .join-sides {
        grid-template-columns: 1fr;
      }

  .step-rail {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
}

@media (max-width: 680px) {
  .field-mode-tabs,
  .model-overview,
  .step-rail {
    grid-template-columns: 1fr;
  }

  .dataset-toolbar-actions {
    align-items: stretch;
    flex-direction: column;
  }

  .dataset-toolbar-actions :deep(.el-button) {
    width: 100%;
  }

  .field-panel-hero,
  .field-config-top,
  .fields-head-actions {
    flex-direction: column;
    align-items: stretch;
  }

  .fields-health-pill {
    width: 100%;
    justify-content: space-between;
    border-radius: var(--app-radius-sm);
  }

      .aggregation-builder,
      .filter-builder,
      .drill-summary-grid,
      .join-meta-row {
        grid-template-columns: 1fr;
      }

  .join-link-symbol {
    justify-self: flex-start;
    width: 40px;
  }
}
</style>
