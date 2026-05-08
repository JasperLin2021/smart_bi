<template>
  <div class="governance-page metric-page">
    <!-- ── Page header with donut chart ── -->
    <div class="page-header">
      <div class="page-header__chart-area">
        <div ref="donutRef" class="page-donut" />
        <div class="page-legend">
          <div class="page-legend__item" v-for="item in legendItems" :key="item.label">
            <span class="page-legend__dot" :style="{ background: item.color }" />
            <span class="page-legend__label">{{ item.label }}</span>
            <strong class="page-legend__value" :style="{ color: item.color }">{{ item.value }}</strong>
          </div>
        </div>
      </div>
      <div class="page-header__actions">
        <el-button :icon="Refresh" @click="fetchMetrics" :loading="loading">刷新</el-button>
        <el-button type="primary" :icon="Plus" @click="openDialog()">新增指标</el-button>
      </div>
    </div>

    <el-card class="governance-workbench metric-card" shadow="never">
      <div class="governance-toolbar">
        <div class="governance-filters">
          <el-input
            v-model="keyword"
            class="governance-search"
            clearable
            :prefix-icon="Search"
            placeholder="搜索指标 / 口径 / 负责人"
          />
          <el-select v-model="selectedDatasetFilter" clearable filterable placeholder="数据集" class="governance-filter">
            <el-option
              v-for="dataset in datasets"
              :key="dataset.id"
              :label="dataset.name"
              :value="dataset.id"
            />
          </el-select>
          <el-select v-model="certificationFilter" clearable placeholder="认证状态" class="governance-filter">
            <el-option label="草稿" value="draft" />
            <el-option label="待审核" value="pending_review" />
            <el-option label="已认证" value="certified" />
            <el-option label="已废弃" value="deprecated" />
          </el-select>
          <el-select v-model="qualityFilter" clearable placeholder="质量状态" class="governance-filter">
            <el-option label="未知" value="unknown" />
            <el-option label="正常" value="normal" />
            <el-option label="过期" value="stale" />
            <el-option label="异常" value="error" />
          </el-select>
        </div>
        <div class="governance-quick-filters">
          <button
            v-for="item in metricQuickFilters"
            :key="item.value"
            type="button"
            class="governance-pill"
            :class="{ 'is-active': quickFilter === item.value }"
            @click="quickFilter = item.value"
          >
            {{ item.label }}
          </button>
        </div>
        <span class="governance-muted">共 {{ filteredMetrics.length }} 个结果</span>
      </div>
      <div class="metric-mobile-list" v-loading="loading">
        <div v-if="!filteredMetrics.length && !loading" class="governance-empty metric-mobile-empty">
          <strong>还没有匹配的可信指标</strong>
          <span>新增指标并补齐口径、公式、负责人和质量说明后，问数、看板与数据目录会复用同一套定义。</span>
          <el-button type="primary" :icon="Plus" @click="openDialog()">新增指标</el-button>
        </div>
        <article
          v-for="row in filteredMetrics"
          :key="row.id"
          class="metric-mobile-card"
          @click="openDialog(row)"
        >
          <div class="metric-mobile-card__head">
            <div class="metric-mobile-card__title">
              <div class="metric-title-row">
                <strong>{{ row.name }}</strong>
                <el-tag v-if="row.unit" size="small" effect="plain">{{ row.unit }}</el-tag>
              </div>
              <p>{{ row.description || row.definition || "未填写口径说明" }}</p>
            </div>
            <el-tag :type="certificationTagType(row.certification_status)" effect="plain">
              {{ certificationLabel(row.certification_status) }}
            </el-tag>
          </div>
          <div class="tag-row" v-if="row.tags?.length">
            <el-tag v-for="tag in row.tags" :key="tag" size="small" effect="plain">
              {{ tag }}
            </el-tag>
          </div>
          <div class="metric-mobile-card__meta">
            <div>
              <span>质量</span>
              <strong>{{ qualityLabel(row.quality_status) }}</strong>
            </div>
            <div>
              <span>数据集</span>
              <strong>{{ getDatasetName(row.dataset_id) }}</strong>
            </div>
            <div>
              <span>最新值</span>
              <strong>{{ row.last_value ?? "未计算" }}</strong>
            </div>
            <div>
              <span>发布</span>
              <strong>{{ statusLabel(row.status) }}</strong>
            </div>
          </div>
          <div class="metric-mobile-card__actions metric-icon-actions" @click.stop>
            <el-tooltip content="查看血缘" placement="top" :show-after="500">
              <el-button class="metric-icon-button" text circle type="primary" :icon="Connection" aria-label="查看血缘" @click="openLineage(row)" />
            </el-tooltip>
            <el-tooltip content="编辑指标" placement="top" :show-after="500">
              <el-button class="metric-icon-button" text circle type="primary" :icon="Edit" aria-label="编辑指标" @click="openDialog(row)" />
            </el-tooltip>
            <el-tooltip content="计算指标" placement="top" :show-after="500">
              <el-button class="metric-icon-button" text circle type="success" :icon="Refresh" :loading="computingId === row.id" aria-label="计算指标" @click="computeMetric(row)" />
            </el-tooltip>
            <el-tooltip content="删除指标" placement="top" :show-after="500">
              <el-button class="metric-icon-button" text circle type="danger" :icon="Delete" aria-label="删除指标" @click="deleteMetric(row.id)" />
            </el-tooltip>
          </div>
        </article>
      </div>
      <el-table
        class="governance-table"
        :data="filteredMetrics"
        v-loading="loading"
        row-key="id"
        empty-text="暂无指标"
        @row-click="openDialog"
      >
        <template #empty>
          <div class="governance-empty">
            <strong>还没有匹配的可信指标</strong>
            <span>新增指标并补齐口径、公式、负责人和质量说明后，问数、看板与数据目录会复用同一套定义。</span>
            <el-button type="primary" :icon="Plus" @click="openDialog()">新增指标</el-button>
          </div>
        </template>
        <el-table-column label="指标与口径" min-width="260">
          <template #default="{ row }">
            <div class="metric-name-cell">
              <div class="metric-title-row">
                <strong>{{ row.name }}</strong>
                <el-tag v-if="row.unit" size="small" effect="plain">{{ row.unit }}</el-tag>
              </div>
              <span>{{ row.description || row.definition || "未填写口径说明" }}</span>
              <div class="tag-row" v-if="row.tags?.length">
                <el-tag v-for="tag in row.tags" :key="tag" size="small" effect="plain">
                  {{ tag }}
                </el-tag>
              </div>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="可信状态" width="150">
          <template #default="{ row }">
            <div class="status-stack">
              <el-tag :type="certificationTagType(row.certification_status)" effect="plain">
                {{ certificationLabel(row.certification_status) }}
              </el-tag>
              <small v-if="row.certified_by">认证人：{{ row.certified_by }}</small>
              <div class="governance-progress" :aria-label="`可信完整度 ${trustScore(row)}%`">
                <span :style="{ width: `${trustScore(row)}%` }"></span>
              </div>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="质量" width="140">
          <template #default="{ row }">
            <div class="status-stack">
              <el-tag :type="qualityTagType(row.quality_status)" effect="plain">
                {{ qualityLabel(row.quality_status) }}
              </el-tag>
              <small>{{ row.quality_message || "暂无说明" }}</small>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="数据集 / 来源" min-width="190">
          <template #default="{ row }">
            <div class="source-cell">
              <strong>{{ getDatasetName(row.dataset_id) }}</strong>
              <span>{{ row.column_name || "未绑定字段" }}</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="公式" min-width="220" show-overflow-tooltip>
          <template #default="{ row }">{{ row.formula || row.definition }}</template>
        </el-table-column>
        <el-table-column label="最新值" width="160">
          <template #default="{ row }">
            <div v-if="row.last_value != null" class="version-cell">
              <strong style="color: var(--el-color-primary)">{{ row.last_value }}</strong>
              <span>{{ formatDate(row.last_computed_at) }}</span>
            </div>
            <el-text v-else type="info" size="small">未计算</el-text>
          </template>
        </el-table-column>
        <el-table-column label="版本 / 更新" width="170">
          <template #default="{ row }">
            <div class="version-cell">
              <strong>{{ row.caliber_version || "v1" }}</strong>
              <span>{{ formatDate(row.data_updated_at) }}</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="发布" width="100">
          <template #default="{ row }">
            <el-tag :type="row.status === 'published' ? 'success' : row.status === 'archived' ? 'info' : 'warning'" effect="plain">
              {{ statusLabel(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="152" align="center">
          <template #default="{ row }">
            <div class="governance-action-group metric-icon-actions" @click.stop>
              <el-tooltip content="查看血缘" placement="top" :show-after="500">
                <el-button class="metric-icon-button" text circle type="primary" :icon="Connection" aria-label="查看血缘" @click="openLineage(row)" />
              </el-tooltip>
              <el-tooltip content="编辑指标" placement="top" :show-after="500">
                <el-button class="metric-icon-button" text circle type="primary" :icon="Edit" aria-label="编辑指标" @click="openDialog(row)" />
              </el-tooltip>
              <el-tooltip content="计算指标" placement="top" :show-after="500">
                <el-button class="metric-icon-button" text circle type="success" :icon="Refresh" :loading="computingId === row.id" aria-label="计算指标" @click="computeMetric(row)" />
              </el-tooltip>
              <el-tooltip content="删除指标" placement="top" :show-after="500">
                <el-button class="metric-icon-button" text circle type="danger" :icon="Delete" aria-label="删除指标" @click="deleteMetric(row.id)" />
              </el-tooltip>
            </div>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog
      v-model="dialogVisible"
      :title="editingId ? '编辑可信指标' : '新增可信指标'"
      width="min(1080px, calc(100vw - 32px))"
      class="metric-dialog governance-modal"
      destroy-on-close
    >
      <el-form :model="form" label-position="top">
        <el-tabs v-model="dialogActiveTab" class="modal-tabs">
          <el-tab-pane label="基础信息" name="basic">
            <div class="modal-tab-content">
              <el-row :gutter="16">
                <el-col :xs="24" :md="12">
                  <el-form-item label="数据集" required>
                    <el-select v-model="form.dataset_id" filterable placeholder="请选择数据集" style="width: 100%">
                      <el-option
                        v-for="dataset in datasets"
                        :key="dataset.id"
                        :label="dataset.name"
                        :value="dataset.id"
                      >
                        <div class="scope-option">
                          <strong>{{ dataset.name }}</strong>
                          <small>{{ getDatasourceName(dataset.datasource_id) }}</small>
                        </div>
                      </el-option>
                    </el-select>
                  </el-form-item>
                </el-col>
                <el-col :xs="24" :md="12">
                  <el-form-item label="指标名称" required>
                    <el-input v-model="form.name" maxlength="128" placeholder="如：回款率、月活客户数" />
                  </el-form-item>
                </el-col>
              </el-row>
              <el-row :gutter="16">
                <el-col :xs="24" :md="12">
                  <el-form-item label="负责人">
                    <el-input v-model="form.owner_name" placeholder="如：财务负责人、销售运营" />
                  </el-form-item>
                </el-col>
                <el-col :xs="24" :md="12">
                  <el-form-item label="单位">
                    <el-input v-model="form.unit" placeholder="如：元、%、单、个" />
                  </el-form-item>
                </el-col>
              </el-row>
              <el-form-item label="一句话描述">
                <el-input v-model="form.description" type="textarea" :rows="2" placeholder="在列表、目录和问数结果中展示的简短解释" />
              </el-form-item>
              <el-form-item label="指标定义" required>
                <el-input v-model="form.definition" type="textarea" :rows="3" placeholder="清楚说明统计对象、时间范围、包含/排除规则和业务口径" />
              </el-form-item>
            </div>
          </el-tab-pane>

          <el-tab-pane label="计算口径" name="formula">
            <div class="modal-tab-content">
              <div class="modal-tab-action-row">
                <el-button :loading="generatingFormula" @click="generateFormula">AI 生成公式</el-button>
              </div>
              <el-row :gutter="16">
                <el-col :xs="24" :md="12">
                  <el-form-item label="字段名">
                    <el-input v-model="form.column_name" placeholder="如：net_amount（数据集中的聚合字段名）" />
                  </el-form-item>
                </el-col>
                <el-col :xs="24" :md="12">
                  <el-form-item label="聚合方式">
                    <el-select v-model="form.aggregation" style="width: 100%">
                      <el-option label="求和" value="sum" />
                      <el-option label="平均" value="avg" />
                      <el-option label="计数" value="count" />
                      <el-option label="最大值" value="max" />
                      <el-option label="最小值" value="min" />
                      <el-option label="比率" value="ratio" />
                      <el-option label="自定义" value="custom" />
                    </el-select>
                  </el-form-item>
                </el-col>
              </el-row>
              <el-form-item label="计算公式">
                <el-input v-model="form.formula" type="textarea" :rows="3" placeholder="如：SUM(received_amount) / SUM(receivable_amount)" />
              </el-form-item>
              <el-row :gutter="16">
                <el-col :xs="24" :md="12">
                  <el-form-item label="标签">
                    <el-input v-model="form.tags_text" placeholder="多个标签用逗号或换行分隔" />
                  </el-form-item>
                </el-col>
                <el-col :xs="24" :md="12">
                  <el-form-item label="适用维度">
                    <el-input v-model="form.dimensions_text" placeholder="如：region, channel, month" />
                  </el-form-item>
                </el-col>
              </el-row>
            </div>
          </el-tab-pane>

          <el-tab-pane label="可信治理" name="trust">
            <div class="modal-tab-content">
              <el-row :gutter="16">
                <el-col :xs="24" :md="8">
                  <el-form-item label="认证状态">
                    <el-select v-model="form.certification_status" style="width: 100%">
                      <el-option label="草稿" value="draft" />
                      <el-option label="待审核" value="pending_review" />
                      <el-option label="已认证" value="certified" />
                      <el-option label="已废弃" value="deprecated" />
                    </el-select>
                  </el-form-item>
                </el-col>
                <el-col :xs="24" :md="8">
                  <el-form-item label="发布状态">
                    <el-select v-model="form.status" style="width: 100%">
                      <el-option label="草稿" value="draft" />
                      <el-option label="已发布" value="published" />
                      <el-option label="已归档" value="archived" />
                    </el-select>
                  </el-form-item>
                </el-col>
                <el-col :xs="24" :md="8">
                  <el-form-item label="质量状态">
                    <el-select v-model="form.quality_status" style="width: 100%">
                      <el-option label="未知" value="unknown" />
                      <el-option label="正常" value="normal" />
                      <el-option label="过期" value="stale" />
                      <el-option label="异常" value="error" />
                    </el-select>
                  </el-form-item>
                </el-col>
              </el-row>
              <el-form-item label="认证人" required>
                <el-tree-select
                  v-model="form.certified_by"
                  class="certifier-tree-select"
                  :data="certifierTreeData"
                  :loading="certifierLoading"
                  filterable
                  clearable
                  check-strictly
                  node-key="value"
                  placeholder="按企业 / 角色选择系统认证人"
                  style="width: 100%"
                />
                <div class="certifier-helper">仅展示具备指标认证权限的系统用户。</div>
              </el-form-item>
              <el-row :gutter="16">
                <el-col :xs="24" :md="12">
                  <el-form-item label="口径版本">
                    <el-input v-model="form.caliber_version" placeholder="如：v2026.04" />
                  </el-form-item>
                </el-col>
                <el-col :xs="24" :md="12">
                  <el-form-item label="数据更新时间">
                    <el-date-picker v-model="form.data_updated_at" type="datetime" value-format="YYYY-MM-DDTHH:mm:ss" placeholder="选择最近一次数据更新时间" style="width: 100%" />
                  </el-form-item>
                </el-col>
              </el-row>
              <el-form-item label="质量说明">
                <el-input v-model="form.quality_message" type="textarea" :rows="2" placeholder="如：与财务月结口径一致；最近一次刷新失败原因" />
              </el-form-item>
              <el-form-item label="启用状态">
                <el-switch v-model="form.is_active" :active-value="1" :inactive-value="0" />
              </el-form-item>
            </div>
          </el-tab-pane>
        </el-tabs>
      </el-form>
      <template #footer>
        <div class="governance-modal-footer">
          <span class="governance-modal-footer-note">建议补齐定义、公式和负责人。</span>
          <div class="governance-modal-footer-actions">
            <el-button @click="dialogVisible = false">取消</el-button>
            <el-button type="primary" @click="saveMetric" :loading="saving">保存指标</el-button>
          </div>
        </div>
      </template>
    </el-dialog>

    <el-dialog
      v-model="lineageVisible"
      title="指标血缘与可信说明"
      width="min(860px, calc(100vw - 32px))"
      class="governance-modal lineage-governance-dialog"
    >
      <div v-loading="lineageLoading" class="lineage-dialog">
        <template v-if="lineage">

          <!-- 固定头：指标标识 + 状态标签 -->
          <div class="lineage-header-bar">
            <div class="lineage-header-identity">
              <span class="lineage-header-ds">{{ lineage.dataset.name || lineage.datasource.name || "—" }}</span>
              <h3 class="lineage-header-name">{{ lineage.metric.name }}</h3>
            </div>
            <div class="lineage-header-tags">
              <el-tag :type="certificationTagType(lineage.trust.certification_status)" effect="plain" size="small">
                {{ certificationLabel(lineage.trust.certification_status) }}
              </el-tag>
              <el-tag :type="qualityTagType(lineage.trust.quality_status)" effect="plain" size="small">
                {{ qualityLabel(lineage.trust.quality_status) }}
              </el-tag>
              <span class="lineage-version-chip">{{ lineage.metric.caliber_version }}</span>
            </div>
          </div>

          <!-- Tab 面板 -->
          <el-tabs v-model="lineageActiveTab" class="lineage-tabs">

            <!-- ① 血缘链路 -->
            <el-tab-pane label="血缘链路" name="lineage">
              <div class="lineage-tab-content">
                <div class="lineage-complexity-banner" :class="{ 'is-join': isJoinAggregationLineage }">
                  <el-icon><Connection v-if="isJoinAggregationLineage" /><DataLine v-else /></el-icon>
                  <div>
                    <strong>{{ isJoinAggregationLineage ? "多表 Join 聚合" : "单表指标" }}</strong>
                    <span v-if="isJoinAggregationLineage">
                      {{ joinTables.length }} 张表参与，{{ join_conditions.length || "未配置" }} 个关联条件，{{ group_by_fields.length }} 个分组维度。
                    </span>
                    <span v-else>来源表、字段、聚合方式和指标输出保持线性展示。</span>
                  </div>
                </div>

                <!-- JOIN多表关联: 复杂链路视图 -->
                <template v-if="isJoinAggregationLineage">

                  <div class="lineage-dag">
                    <div class="lineage-node lineage-node--source">
                      <el-icon class="lineage-node-icon"><Coin /></el-icon>
                      <div class="lineage-node-body">
                        <span class="lineage-node-type">数据源</span>
                        <strong class="lineage-node-name">{{ lineage.datasource.name || "未知" }}</strong>
                        <span class="lineage-node-meta">{{ lineage.datasource.source_type || "" }}</span>
                      </div>
                    </div>
                    <div class="lineage-arrow">→</div>
                    <div class="lineage-node lineage-node--dataset">
                      <el-icon class="lineage-node-icon"><FolderOpened /></el-icon>
                      <div class="lineage-node-body">
                        <span class="lineage-node-type">数据集</span>
                        <strong class="lineage-node-name">{{ lineage.dataset.name || "未知" }}</strong>
                        <span class="lineage-node-meta">{{ lineage.dataset.main_table || "" }}</span>
                      </div>
                    </div>
                    <div class="lineage-arrow">→</div>
                    <div class="lineage-dag-tables-wrap">
                      <div class="lineage-dag-tables">
                        <div v-for="jt in joinTables" :key="jt.table" class="lineage-node lineage-node--table lineage-node--sm">
                          <el-icon class="lineage-node-icon"><Document /></el-icon>
                          <div class="lineage-node-body">
                            <span class="lineage-node-type">
                              <span v-if="jt.join_type" class="join-type-badge">{{ jt.join_type }}</span>
                              <span v-else>主表 (FROM)</span>
                            </span>
                            <strong class="lineage-node-name">{{ jt.table }}</strong>
                            <span v-if="jt.join_on" class="lineage-node-meta lineage-join-on">ON {{ jt.join_on }}</span>
                            <span v-if="jt.columns?.length" class="lineage-node-meta">
                              {{ jt.columns.slice(0, 3).join(", ") }}{{ jt.columns.length > 3 ? "…" : "" }}
                            </span>
                          </div>
                        </div>
                      </div>
                      <div class="lineage-dag-bracket"></div>
                    </div>
                    <div class="lineage-arrow">→</div>
                    <div class="lineage-node lineage-node--join">
                      <el-icon class="lineage-node-icon"><Connection /></el-icon>
                      <div class="lineage-node-body">
                        <span class="lineage-node-type">关联合并</span>
                        <strong class="lineage-node-name">JOIN</strong>
                        <span class="lineage-node-meta">{{ joinTables.length }} 张表</span>
                      </div>
                    </div>
                    <div class="lineage-arrow">→</div>
                    <div class="lineage-node lineage-node--column lineage-step--aggregate">
                      <el-icon class="lineage-node-icon"><Histogram /></el-icon>
                      <div class="lineage-node-body">
                        <span class="lineage-node-type">聚合字段</span>
                        <strong class="lineage-node-name">{{ aggregateFieldsText }}</strong>
                        <span class="lineage-node-meta">{{ lineage.metric.aggregation }}</span>
                      </div>
                    </div>
                    <div class="lineage-arrow">→</div>
                    <div class="lineage-node lineage-node--metric">
                      <el-icon class="lineage-node-icon"><DataLine /></el-icon>
                      <div class="lineage-node-body">
                        <span class="lineage-node-type">指标</span>
                        <strong class="lineage-node-name">{{ lineage.metric.name }}</strong>
                        <span class="lineage-node-meta">{{ lineage.metric.unit ? `单位：${lineage.metric.unit}` : "" }}</span>
                      </div>
                    </div>
                    <template v-if="lineage.metric.formula">
                      <div class="lineage-arrow">→</div>
                      <div class="lineage-node lineage-node--formula">
                        <el-icon class="lineage-node-icon"><Operation /></el-icon>
                        <div class="lineage-node-body">
                          <span class="lineage-node-type">计算公式</span>
                          <code class="lineage-node-formula">{{ lineage.metric.formula }}</code>
                        </div>
                      </div>
                    </template>
                  </div>
                  <div v-if="join_conditions.length" class="lineage-dag-filters">
                    <span class="lineage-section-label" style="margin:0;white-space:nowrap">关联条件</span>
                    <code v-for="f in join_conditions" :key="f" class="lineage-filter-pill">ON {{ f }}</code>
                  </div>
                  <div v-if="group_by_fields.length" class="lineage-dag-filters lineage-dag-groups">
                    <span class="lineage-section-label" style="margin:0;white-space:nowrap">分组维度</span>
                    <code v-for="field in group_by_fields" :key="field" class="lineage-filter-pill">GROUP BY {{ field }}</code>
                  </div>
                </template>

                <!-- 单表: 线性流视图 -->
                <template v-else>
                  <div class="lineage-flow">
                    <div class="lineage-node lineage-node--source">
                      <el-icon class="lineage-node-icon"><Coin /></el-icon>
                      <div class="lineage-node-body">
                        <span class="lineage-node-type">数据源</span>
                        <strong class="lineage-node-name">{{ lineage.datasource.name || "未知" }}</strong>
                        <span class="lineage-node-meta">{{ lineage.datasource.source_type || "" }}</span>
                      </div>
                    </div>
                    <div class="lineage-arrow">→</div>
                    <div class="lineage-node lineage-node--dataset">
                      <el-icon class="lineage-node-icon"><FolderOpened /></el-icon>
                      <div class="lineage-node-body">
                        <span class="lineage-node-type">数据集</span>
                        <strong class="lineage-node-name">{{ lineage.dataset.name || "未知" }}</strong>
                        <span class="lineage-node-meta">{{ lineage.dataset.fields?.length ? `${lineage.dataset.fields.length} 个字段` : "" }}</span>
                      </div>
                    </div>
                    <div class="lineage-arrow">→</div>
                    <div class="lineage-node lineage-node--table">
                      <el-icon class="lineage-node-icon"><Document /></el-icon>
                      <div class="lineage-node-body">
                        <span class="lineage-node-type">数据表</span>
                        <strong class="lineage-node-name">{{ lineage.dataset.main_table || "未配置" }}</strong>
                      </div>
                    </div>
                    <div class="lineage-arrow">→</div>
                    <div class="lineage-node lineage-node--column">
                      <el-icon class="lineage-node-icon"><Histogram /></el-icon>
                      <div class="lineage-node-body">
                        <span class="lineage-node-type">字段</span>
                        <strong class="lineage-node-name">{{ lineage.source.column_name || "未配置" }}</strong>
                        <span class="lineage-node-meta">{{ lineage.metric.aggregation }}</span>
                      </div>
                    </div>
                    <div class="lineage-arrow">→</div>
                    <div class="lineage-node lineage-node--metric">
                      <el-icon class="lineage-node-icon"><DataLine /></el-icon>
                      <div class="lineage-node-body">
                        <span class="lineage-node-type">指标</span>
                        <strong class="lineage-node-name">{{ lineage.metric.name }}</strong>
                        <span class="lineage-node-meta">{{ lineage.metric.unit ? `单位：${lineage.metric.unit}` : "" }}</span>
                      </div>
                    </div>
                    <template v-if="lineage.metric.formula">
                      <div class="lineage-arrow">→</div>
                      <div class="lineage-node lineage-node--formula">
                        <el-icon class="lineage-node-icon"><Operation /></el-icon>
                        <div class="lineage-node-body">
                          <span class="lineage-node-type">计算公式</span>
                          <code class="lineage-node-formula">{{ lineage.metric.formula }}</code>
                        </div>
                      </div>
                    </template>
                  </div>
                </template>
              </div>
            </el-tab-pane>

            <!-- ② 口径定义 -->
            <el-tab-pane label="口径定义" name="definition">
              <div class="lineage-tab-content">
                <blockquote class="lineage-def-block">{{ lineage.metric.definition }}</blockquote>
                <pre v-if="lineage.metric.formula" class="lineage-formula-block">{{ lineage.metric.formula }}</pre>

                <div class="lineage-meta-grid">
                  <div class="lineage-meta-item">
                    <span>聚合方式</span>
                    <strong>{{ lineage.metric.aggregation }}</strong>
                  </div>
                  <div class="lineage-meta-item">
                    <span>单位</span>
                    <strong>{{ lineage.metric.unit || "—" }}</strong>
                  </div>
                  <div class="lineage-meta-item">
                    <span>来源字段</span>
                    <strong>{{ [lineage.dataset.main_table, lineage.source.column_name].filter(Boolean).join(".") || "—" }}</strong>
                  </div>
                  <div class="lineage-meta-item">
                    <span>负责人</span>
                    <strong>{{ lineage.metric.owner_name || "—" }}</strong>
                  </div>
                </div>

                <!-- JOIN: 关联关系表格 -->
                <template v-if="isJoinAggregationLineage">
                  <p class="lineage-section-label" style="margin-top:20px;margin-bottom:10px">关联关系</p>
                  <div class="lineage-join-table-wrap">
                    <table class="lineage-join-table">
                      <thead>
                        <tr>
                          <th>数据表</th>
                          <th>关联类型</th>
                          <th>关联条件</th>
                          <th>涉及字段</th>
                        </tr>
                      </thead>
                      <tbody>
                        <tr v-for="jt in joinTables" :key="jt.table">
                          <td>
                            <strong>{{ jt.table }}</strong>
                            <span v-if="jt.alias" class="join-alias"> ({{ jt.alias }})</span>
                          </td>
                          <td>
                            <span v-if="jt.join_type" class="join-type-badge">{{ jt.join_type }}</span>
                            <span v-else class="join-type-badge join-type-primary">FROM</span>
                          </td>
                          <td>
                            <code v-if="jt.join_on">{{ jt.join_on }}</code>
                            <span v-else class="lineage-node-meta">—</span>
                          </td>
                          <td class="join-cols-cell">{{ jt.columns?.join(", ") || "—" }}</td>
                        </tr>
                      </tbody>
                    </table>
                  </div>
                  <div v-if="join_conditions.length" class="lineage-dag-filters" style="margin-top:10px">
                    <span class="lineage-section-label" style="margin:0;white-space:nowrap">关联条件</span>
                    <code v-for="f in join_conditions" :key="f" class="lineage-filter-pill">ON {{ f }}</code>
                  </div>
                  <div v-if="group_by_fields.length" class="lineage-dag-filters lineage-dag-groups" style="margin-top:10px">
                    <span class="lineage-section-label" style="margin:0;white-space:nowrap">分组维度</span>
                    <code v-for="field in group_by_fields" :key="field" class="lineage-filter-pill">GROUP BY {{ field }}</code>
                  </div>
                </template>
              </div>
            </el-tab-pane>

            <!-- ③ 质量与认证 -->
            <el-tab-pane label="质量与认证" name="trust">
              <div class="lineage-tab-content">
                <div class="lineage-trust-grid">
                  <!-- 认证卡片 -->
                  <div class="lineage-trust-card">
                    <p class="lineage-section-label">认证状态</p>
                    <div class="lineage-trust-badge">
                      <el-tag :type="certificationTagType(lineage.trust.certification_status)" effect="light" size="large">
                        {{ certificationLabel(lineage.trust.certification_status) }}
                      </el-tag>
                    </div>
                    <dl class="lineage-trust-dl">
                      <dt>认证人</dt>
                      <dd>{{ lineage.trust.certified_by || "—" }}</dd>
                      <dt>认证时间</dt>
                      <dd>{{ formatDate(lineage.trust.certified_at) }}</dd>
                      <dt>口径版本</dt>
                      <dd>{{ lineage.metric.caliber_version || "v1" }}</dd>
                    </dl>
                  </div>
                  <!-- 质量卡片 -->
                  <div class="lineage-trust-card">
                    <p class="lineage-section-label">质量状态</p>
                    <div class="lineage-trust-badge">
                      <el-tag :type="qualityTagType(lineage.trust.quality_status)" effect="light" size="large">
                        {{ qualityLabel(lineage.trust.quality_status) }}
                      </el-tag>
                    </div>
                    <dl class="lineage-trust-dl">
                      <dt>质量说明</dt>
                      <dd>{{ lineage.trust.quality_message || "—" }}</dd>
                      <dt>数据更新</dt>
                      <dd>{{ formatDate(lineage.trust.data_updated_at) }}</dd>
                    </dl>
                  </div>
                </div>
              </div>
            </el-tab-pane>

          </el-tabs>
        </template>
      </div>
      <template #footer>
        <div class="governance-modal-footer">
          <span class="governance-modal-footer-note">血缘用于解释问数结果。</span>
          <div class="governance-modal-footer-actions">
            <el-button @click="lineageVisible = false">关闭</el-button>
          </div>
        </div>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue"
import * as echarts from "echarts"
import axios from "axios"
import { ElMessage, ElMessageBox } from "element-plus"
import {
  Coin,
  Connection,
  DataLine,
  Delete,
  Document,
  Edit,
  FolderOpened,
  Grid,
  Histogram,
  Operation,
  Plus,
  Refresh,
  Search,
  SetUp,
} from "@element-plus/icons-vue"
import { useDatasourceStore } from "@/store/datasource"

interface Metric {
  id: number
  dataset_id: number | null
  datasource_id: number
  name: string
  description: string | null
  definition: string
  column_name: string | null
  formula: string | null
  owner_name: string | null
  unit: string | null
  aggregation: string
  tags: string[] | null
  status: string
  dimensions: string[] | null
  certification_status: string
  certified_by: string | null
  certified_at: string | null
  caliber_version: string
  data_updated_at: string | null
  quality_status: string
  quality_message: string | null
  is_active: number
  last_value: number | null
  last_computed_at: string | null
}

interface MetricForm {
  dataset_id: number | null
  name: string
  description: string
  definition: string
  column_name: string
  formula: string
  owner_name: string
  unit: string
  aggregation: string
  tags_text: string
  status: string
  dimensions_text: string
  certification_status: string
  certified_by: string
  caliber_version: string
  data_updated_at: string | null
  quality_status: string
  quality_message: string
  is_active: number
}

interface MetricLineage {
  metric: {
    id: number
    name: string
    definition: string
    formula: string | null
    unit: string | null
    aggregation: string
    caliber_version: string
    owner_name: string | null
  }
  dataset: {
    id: number | null
    name: string | null
    description: string | null
    main_table: string | null
    fields: Array<{ name: string; label: string; type: string }> | null
    joins: Array<{ table: string; join_type: string; join_on: string }> | null
  }
  datasource: {
    id: number | null
    name: string | null
    source_type: string | null
  }
  source: {
    table_name: string | null
    column_name: string | null
  }
  trust: {
    certification_status: string
    certified_by: string | null
    certified_at: string | null
    quality_status: string
    quality_message: string | null
    data_updated_at: string | null
  }
  usage: {
    catalog_asset: string
    datasource_id: number | null
  }
}

interface DatasetItem {
  id: number
  name: string
  description: string | null
  datasource_id: number
  status: string
  visibility: string
}

interface CertifierUser {
  id: number
  username: string
  role: string
  org_id: number | null
  org_name: string | null
  can_certify_metric: boolean
}

interface CertifierTreeNode {
  value: string
  label: string
  disabled?: boolean
  children?: CertifierTreeNode[]
}

const metrics = ref<Metric[]>([])
const datasets = ref<DatasetItem[]>([])
const loading = ref(false)
const dialogVisible = ref(false)
const editingId = ref<number | null>(null)
const saving = ref(false)
const generatingFormula = ref(false)
const datasourceStore = useDatasourceStore()
const selectedDatasetFilter = ref<number | null>(null)
const certificationFilter = ref("")
const qualityFilter = ref("")
const quickFilter = ref("all")
const keyword = ref("")
const dialogActiveTab = ref("basic")
const lineageVisible = ref(false)
const lineageLoading = ref(false)
const lineageActiveTab = ref("lineage")
const lineage = ref<MetricLineage | null>(null)
const certifierUsers = ref<CertifierUser[]>([])
const certifierLoading = ref(false)

const emptyForm = (): MetricForm => ({
  dataset_id: null,
  name: "",
  description: "",
  definition: "",
  column_name: "",
  formula: "",
  owner_name: "",
  unit: "",
  aggregation: "sum",
  tags_text: "",
  status: "published",
  dimensions_text: "",
  certification_status: "draft",
  certified_by: "",
  caliber_version: "v1",
  data_updated_at: null,
  quality_status: "unknown",
  quality_message: "",
  is_active: 1,
})

const form = ref<MetricForm>(emptyForm())

const metricQuickFilters = [
  { label: "全部", value: "all" },
  { label: "已认证", value: "certified" },
  { label: "待审核", value: "pending" },
  { label: "质量风险", value: "risk" },
  { label: "未绑定字段", value: "unbound" },
]

const certifierRoleLabel = (role: string) => {
  const labels: Record<string, string> = {
    super_admin: "超级管理员",
    org_admin: "企业管理员",
    user: "普通用户",
  }
  return labels[role] || role
}

const certifierTreeData = computed<CertifierTreeNode[]>(() => {
  const orgMap = new Map<string, CertifierTreeNode>()
  certifierUsers.value.forEach((user) => {
    const orgKey = user.org_id ? `org-${user.org_id}` : "org-global"
    if (!orgMap.has(orgKey)) {
      orgMap.set(orgKey, {
        value: orgKey,
        label: user.org_name || "全局管理员",
        disabled: true,
        children: [],
      })
    }
    const orgNode = orgMap.get(orgKey)!
    const roleKey = `${orgKey}-${user.role}`
    let roleNode = orgNode.children?.find((item) => item.value === roleKey)
    if (!roleNode) {
      roleNode = {
        value: roleKey,
        label: certifierRoleLabel(user.role),
        disabled: true,
        children: [],
      }
      orgNode.children?.push(roleNode)
    }
    roleNode.children?.push({
      value: user.username,
      label: user.username,
    })
  })
  return Array.from(orgMap.values())
})

const fetchCertifiers = async () => {
  certifierLoading.value = true
  try {
    const response = await axios.get("/api/metrics/certifiers")
    certifierUsers.value = response.data.items || []
  } catch (error: any) {
    if (error.response?.status !== 403) {
      ElMessage.error("加载认证人列表失败")
    }
  } finally {
    certifierLoading.value = false
  }
}

const fetchMetrics = async () => {
  loading.value = true
  try {
    const response = await axios.get("/api/metrics")
    metrics.value = response.data.items
  } catch (error) {
    ElMessage.error("加载指标列表失败")
  } finally {
    loading.value = false
  }
}

const fetchDatasets = async () => {
  try {
    const response = await axios.get("/api/datasets", { params: { page: 1, page_size: 200 } })
    datasets.value = response.data.items || []
  } catch {
    ElMessage.error("加载数据集列表失败")
  }
}

const metricStats = computed(() => {
  const total = metrics.value.length
  const certified = metrics.value.filter(item => item.certification_status === "certified").length
  const pending = metrics.value.filter(item => item.certification_status === "pending_review").length
  const risk = metrics.value.filter(item => ["stale", "error"].includes(item.quality_status)).length
  return { total, certified, pending, risk }
})

const filteredMetrics = computed(() => {
  const normalizedKeyword = keyword.value.trim().toLowerCase()
  return metrics.value.filter(item => {
    if (quickFilter.value === "certified" && item.certification_status !== "certified") return false
    if (quickFilter.value === "pending" && item.certification_status !== "pending_review") return false
    if (quickFilter.value === "risk" && !["stale", "error"].includes(item.quality_status)) return false
    if (quickFilter.value === "unbound" && item.column_name) return false
    if (selectedDatasetFilter.value && item.dataset_id !== selectedDatasetFilter.value) {
      return false
    }
    if (certificationFilter.value && item.certification_status !== certificationFilter.value) {
      return false
    }
    if (qualityFilter.value && item.quality_status !== qualityFilter.value) {
      return false
    }
    if (!normalizedKeyword) {
      return true
    }
    return [item.name, item.description, item.definition, item.owner_name, item.formula]
      .filter(Boolean)
      .some(value => String(value).toLowerCase().includes(normalizedKeyword))
  })
})

interface JoinTable {
  table: string
  alias?: string
  role?: string
  join_type?: string | null
  join_on?: string | null
  columns?: string[]
}

type LineageRecord = Record<string, unknown>

// lineageData now reads from the dataset's joins/fields (server provides structured data)
const lineageData = computed<LineageRecord>(() => {
  const ds = lineage.value?.dataset
  if (!ds) return {}
  return {
    source_tables: ds.main_table ? [ds.main_table] : [],
    joins: (ds.joins || []).map(j => ({
      table: j.table,
      join_type: j.join_type,
      join_on: j.join_on,
      condition: j.join_on,
    })),
    join_conditions: (ds.joins || []).map(j => j.join_on).filter(Boolean),
  }
})

const valueToString = (item: unknown) => {
  if (typeof item === "string" || typeof item === "number") {
    return String(item).trim()
  }
  if (item && typeof item === "object" && !Array.isArray(item)) {
    const record = item as LineageRecord
    return String(record.table || record.name || record.field || record.column || "").trim()
  }
  return ""
}

const toStringList = (value: unknown): string[] => {
  if (Array.isArray(value)) {
    return value.map(valueToString).filter(Boolean)
  }
  if (typeof value === "string") {
    return value.split(/[\n,，;]/).map(item => item.trim()).filter(Boolean)
  }
  return []
}

const toRecordList = (value: unknown): LineageRecord[] => {
  if (!Array.isArray(value)) {
    return []
  }
  return value.filter((item): item is LineageRecord => Boolean(item) && typeof item === "object" && !Array.isArray(item))
}

const conditionToString = (item: unknown) => {
  if (typeof item === "string" || typeof item === "number") {
    return String(item).trim()
  }
  if (item && typeof item === "object" && !Array.isArray(item)) {
    const record = item as LineageRecord
    const direct = record.condition || record.join_on || record.on || record.expression
    if (direct) {
      return String(direct).trim()
    }
    const left = record.left || record.left_field || record.source_field
    const right = record.right || record.right_field || record.target_field
    const operator = record.operator || "="
    if (left && right) {
      return `${left} ${operator} ${right}`
    }
  }
  return ""
}

const toConditionList = (value: unknown): string[] => {
  if (Array.isArray(value)) {
    return value.map(conditionToString).filter(Boolean)
  }
  if (typeof value === "string") {
    return value.split(/[\n,，;]/).map(item => item.trim()).filter(Boolean)
  }
  return []
}

const source_tables = computed(() => {
  const explicit = [
    ...toStringList(lineageData.value.source_tables),
    ...toStringList(lineageData.value.tables),
  ]
  const joined = toStringList(lineageData.value.joins)
  // handle upstream: [{type:"table", name:"..."}, ...] format
  const upstreamRaw = lineageData.value.upstream
  const upstream = Array.isArray(upstreamRaw)
    ? toStringList(
        (upstreamRaw as unknown[]).filter((item) => {
          if (!item || typeof item !== "object") return true
          const t = (item as LineageRecord).type
          return !t || t === "table"
        })
      )
    : []
  const fallback = lineage.value?.dataset.main_table ? [lineage.value.dataset.main_table] : []
  return Array.from(new Set([...explicit, ...joined, ...upstream, ...fallback].filter(Boolean)))
})

const join_conditions = computed(() => {
  const explicit = [
    ...toConditionList(lineageData.value.join_conditions),
    ...toConditionList(lineageData.value.filters),
  ]
  const fromJoins = toRecordList(lineageData.value.joins)
    .map(item => conditionToString(item.join_on || item.on || item.condition || item))
    .filter(Boolean)
  return Array.from(new Set([...explicit, ...fromJoins]))
})

const group_by_fields = computed(() => {
  return Array.from(new Set([
    ...toStringList(lineageData.value.group_by_fields),
    ...toStringList(lineageData.value.group_by),
    ...toStringList(lineageData.value.dimensions),
  ]))
})

const aggregate_fields = computed(() => {
  const fields = [
    ...toStringList(lineageData.value.aggregate_fields),
    ...toStringList(lineageData.value.aggregation_fields),
    ...toStringList(lineageData.value.measures),
  ]
  if (lineage.value?.source.column_name) {
    fields.push(lineage.value.source.column_name)
  }
  return Array.from(new Set(fields.filter(Boolean)))
})

const aggregateFieldsText = computed(() => {
  if (aggregate_fields.value.length) {
    return aggregate_fields.value.join(", ")
  }
  return lineage.value?.metric.aggregation || "聚合"
})

const joinTables = computed<JoinTable[]>(() => {
  const joinRecords = toRecordList(lineageData.value.joins)
  if (joinRecords.length) {
    const recordsByTable = new Map(
      joinRecords
        .map((item, index) => [String(item.table || source_tables.value[index] || `表${index + 1}`), item] as const)
    )
    const orderedTables = source_tables.value.length ? source_tables.value : Array.from(recordsByTable.keys())
    return orderedTables.map((table, index) => {
      const item = (recordsByTable.get(table) || {}) as LineageRecord
      return {
        table,
        alias: item.alias ? String(item.alias) : undefined,
        role: item.role ? String(item.role) : undefined,
        join_type: item.join_type ? String(item.join_type) : index === 0 ? null : "JOIN",
        join_on: item.join_on ? String(item.join_on) : index > 0 ? join_conditions.value[index - 1] || null : null,
        columns: toStringList(item.columns),
      }
    })
  }
  return source_tables.value.map((table, index) => ({
    table,
    join_type: index === 0 ? null : "JOIN",
    join_on: index > 0 ? join_conditions.value[index - 1] || null : null,
    columns: [],
  }))
})

const isJoinAggregationLineage = computed(() => {
  const kind = String(lineageData.value.type || lineageData.value.kind || lineageData.value.model_type || "").toLowerCase()
  const formula = String(lineage.value?.metric.formula || "").toLowerCase()
  const hasJoinSignal =
    kind.includes("join") ||
    source_tables.value.length > 1 ||
    join_conditions.value.length > 0 ||
    /\bjoin\b/.test(formula)
  const hasAggregationSignal =
    Boolean(lineage.value?.metric.aggregation) ||
    aggregate_fields.value.length > 0 ||
    group_by_fields.value.length > 0 ||
    /\b(sum|count|avg|min|max)\s*\(/.test(formula)

  return hasJoinSignal && hasAggregationSignal
})

const lineageSourceTables = computed(() => {
  return source_tables.value
})

const lineageJsonText = computed(() => {
  if (!lineage.value?.dataset) return "{}"
  return JSON.stringify(lineage.value.dataset, null, 2)
})

const getDatasourceName = (datasourceId: number) => {
  return datasourceStore.datasources.find(ds => ds.id === datasourceId)?.name || `数据源 #${datasourceId}`
}

const getDatasetName = (datasetId: number | null) => {
  if (!datasetId) return "未绑定数据集"
  return datasets.value.find(dataset => dataset.id === datasetId)?.name || `数据集 #${datasetId}`
}

const statusLabel = (status: string) => {
  const labels: Record<string, string> = {
    draft: "草稿",
    published: "已发布",
    archived: "已归档",
  }
  return labels[status] || status
}

const certificationLabel = (status: string) => {
  const labels: Record<string, string> = {
    draft: "草稿",
    pending_review: "待审核",
    certified: "已认证",
    deprecated: "已废弃",
  }
  return labels[status] || status
}

const certificationTagType = (status: string) => {
  const types: Record<string, "success" | "warning" | "info" | "danger"> = {
    draft: "info",
    pending_review: "warning",
    certified: "success",
    deprecated: "danger",
  }
  return types[status] || "info"
}

const qualityLabel = (status: string) => {
  const labels: Record<string, string> = {
    unknown: "未知",
    normal: "正常",
    stale: "过期",
    error: "异常",
  }
  return labels[status] || status
}

const qualityTagType = (status: string) => {
  const types: Record<string, "success" | "warning" | "info" | "danger"> = {
    unknown: "info",
    normal: "success",
    stale: "warning",
    error: "danger",
  }
  return types[status] || "info"
}

const formatDate = (value?: string | null) => {
  if (!value) {
    return "未记录"
  }
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) {
    return value
  }
  return date.toLocaleString("zh-CN", { hour12: false })
}

const trustScore = (metric: Metric) => {
  let score = 20
  if (metric.definition) score += 15
  if (metric.formula) score += 20
  if (metric.owner_name) score += 10
  if (metric.certification_status === "certified") score += 20
  if (metric.quality_status === "normal") score += 10
  if (metric.dataset_id) score += 5
  return Math.min(score, 100)
}

const parseList = (value: string) => {
  const items = value
    .split(/[\n,，]/)
    .map(item => item.trim())
    .filter(Boolean)
  return items.length > 0 ? items : null
}


const buildPayload = () => ({
  dataset_id: form.value.dataset_id,
  name: form.value.name,
  description: form.value.description || null,
  definition: form.value.definition,
  column_name: form.value.column_name || null,
  formula: form.value.formula || null,
  owner_name: form.value.owner_name || null,
  unit: form.value.unit || null,
  aggregation: form.value.aggregation || "sum",
  tags: parseList(form.value.tags_text),
  status: form.value.status || "published",
  dimensions: parseList(form.value.dimensions_text),
  certification_status: form.value.certification_status || "draft",
  certified_by: form.value.certified_by || null,
  caliber_version: form.value.caliber_version || "v1",
  data_updated_at: form.value.data_updated_at || null,
  quality_status: form.value.quality_status || "unknown",
  quality_message: form.value.quality_message || null,
  is_active: form.value.is_active,
})

const openDialog = (metric?: Metric) => {
  dialogActiveTab.value = "basic"
  if (metric) {
    editingId.value = metric.id
    form.value = {
      dataset_id: metric.dataset_id,
      name: metric.name || "",
      description: metric.description || "",
      definition: metric.definition || "",
      column_name: metric.column_name || "",
      formula: metric.formula || "",
      owner_name: metric.owner_name || "",
      unit: metric.unit || "",
      aggregation: metric.aggregation || "sum",
      tags_text: (metric.tags || []).join(", "),
      status: metric.status || "published",
      dimensions_text: (metric.dimensions || []).join(", "),
      certification_status: metric.certification_status || "draft",
      certified_by: metric.certified_by || "",
      caliber_version: metric.caliber_version || "v1",
      data_updated_at: metric.data_updated_at || null,
      quality_status: metric.quality_status || "unknown",
      quality_message: metric.quality_message || "",
      is_active: metric.is_active ?? 1,
    }
  } else {
    editingId.value = null
    form.value = emptyForm()
  }
  dialogVisible.value = true
}

const saveMetric = async () => {
  if (!form.value.dataset_id || !form.value.name || !form.value.definition) {
    ElMessage.warning("请填写数据集、指标名称和指标定义")
    return
  }
  if (!form.value.certified_by) {
    ElMessage.warning("请选择认证人")
    return
  }
  saving.value = true
  try {
    const payload = buildPayload()
    if (editingId.value) {
      await axios.put(`/api/metrics/${editingId.value}`, payload)
    } else {
      await axios.post("/api/metrics", payload)
    }
    ElMessage.success("保存成功")
    dialogVisible.value = false
    fetchMetrics()
  } catch (error: any) {
    ElMessage.error(error.response?.data?.detail || "保存失败")
  } finally {
    saving.value = false
  }
}

const generateFormula = async () => {
  if (!form.value.dataset_id || !form.value.name || !form.value.definition) {
    ElMessage.warning("请先选择数据集并填写指标名称、定义")
    return
  }
  generatingFormula.value = true
  try {
    const response = await axios.post("/api/metrics/generate-formula", buildPayload())
    form.value.formula = response.data.formula || ""
    ElMessage.success("已生成计算公式")
  } catch (error: any) {
    ElMessage.error(error.response?.data?.detail || "生成公式失败")
  } finally {
    generatingFormula.value = false
  }
}

const openLineage = async (metric: Metric) => {
  lineageVisible.value = true
  lineageLoading.value = true
  lineage.value = null
  lineageActiveTab.value = "lineage"
  try {
    const response = await axios.get(`/api/metrics/${metric.id}/lineage`)
    lineage.value = response.data
  } catch (error: any) {
    ElMessage.error(error.response?.data?.detail || "加载指标血缘失败")
  } finally {
    lineageLoading.value = false
  }
}

const computingId = ref<number | null>(null)
const computeMetric = async (row: Metric) => {
  computingId.value = row.id
  try {
    const res = await axios.post(`/api/metrics/${row.id}/compute`)
    row.last_value = res.data.last_value
    row.last_computed_at = res.data.computed_at
    ElMessage.success(`计算完成：${res.data.last_value}`)
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || "计算失败")
  } finally {
    computingId.value = null
  }
}

const deleteMetric = async (id: number) => {
  try {
    await ElMessageBox.confirm("确定删除该指标？删除后数据目录中的指标资产也会同步移除。", "提示", { type: "warning" })
    await axios.delete(`/api/metrics/${id}`)
    ElMessage.success("删除成功")
    fetchMetrics()
  } catch (error: any) {
    if (error !== "cancel") {
      ElMessage.error("删除失败")
    }
  }
}

// ── Donut chart ───────────────────────────────────────────────────────────
const donutRef = ref<HTMLElement | null>(null)
let donutChart: echarts.ECharts | null = null

const DONUT_COLORS = {
  certified: "#16a34a",
  pending:   "#d97706",
  risk:      "#dc2626",
  other:     "#94a3b8",
}

const legendItems = computed(() => [
  { label: "全部指标", value: metricStats.value.total,     color: "#3b82f6" },
  { label: "已认证",   value: metricStats.value.certified, color: DONUT_COLORS.certified },
  { label: "待审核",   value: metricStats.value.pending,   color: DONUT_COLORS.pending },
  { label: "质量风险", value: metricStats.value.risk,      color: DONUT_COLORS.risk },
])

const updateDonut = () => {
  if (!donutRef.value) return
  if (!donutChart) donutChart = echarts.init(donutRef.value)
  const { total, certified, pending, risk } = metricStats.value
  const other = Math.max(0, total - certified - pending - risk)
  const data = [
    { value: certified, name: "已认证",   itemStyle: { color: DONUT_COLORS.certified } },
    { value: pending,   name: "待审核",   itemStyle: { color: DONUT_COLORS.pending } },
    { value: risk,      name: "质量风险", itemStyle: { color: DONUT_COLORS.risk } },
    { value: other,     name: "其他",     itemStyle: { color: DONUT_COLORS.other } },
  ].filter(d => d.value > 0)
  if (!data.length) data.push({ value: 1, name: "暂无数据", itemStyle: { color: "#e2e8f0" } })
  donutChart.setOption({
    tooltip: { trigger: "item", formatter: "{b}: {c} ({d}%)" },
    series: [{
      type: "pie",
      radius: ["52%", "80%"],
      center: ["50%", "50%"],
      avoidLabelOverlap: false,
      label: {
        show: true,
        position: "center",
        formatter: () => `{total|${total}}\n{label|指标总数}`,
        rich: {
          total: { fontSize: 22, fontWeight: 700, color: "#1e293b", lineHeight: 28 },
          label: { fontSize: 11, color: "#94a3b8", lineHeight: 18 },
        },
      },
      emphasis: { label: { show: true } },
      labelLine: { show: false },
      data,
    }],
  }, true)
}

watch(metricStats, () => nextTick(updateDonut), { deep: true })

onBeforeUnmount(() => { donutChart?.dispose(); donutChart = null })

onMounted(() => {
  datasourceStore.fetchDatasources()
  fetchDatasets()
  fetchCertifiers()
  fetchMetrics()
  nextTick(updateDonut)
})
</script>

<style scoped>
.metric-page {
  padding: 0;
}

.metric-card {
  border-radius: var(--app-radius);
}

.metric-card :deep(.el-table .cell) {
  line-height: 1.5;
}

.metric-name-cell,
.source-cell,
.version-cell,
.status-stack {
  display: flex;
  flex-direction: column;
  gap: 6px;
  min-width: 0;
}

.metric-title-row {
  display: flex;
  gap: 8px;
  align-items: center;
  min-width: 0;
}

.metric-title-row strong,
.source-cell strong,
.version-cell strong {
  color: var(--app-text);
}

.metric-name-cell span,
.source-cell span,
.version-cell span,
.status-stack small {
  color: var(--app-text-muted);
  line-height: 1.45;
}

.tag-row {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
}

.scope-option {
  display: flex;
  flex-direction: column;
  gap: 2px;
  line-height: 1.3;
}

.scope-option strong {
  color: var(--app-text);
  font-weight: 500;
}

.scope-option small {
  color: var(--app-text-muted);
  font-size: 12px;
}

.metric-mobile-list {
  display: none;
}

.metric-mobile-card {
  border: 1px solid var(--app-border);
  border-radius: var(--app-radius-sm);
  background: var(--app-surface);
  padding: 14px;
}

.metric-mobile-card__head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.metric-mobile-card__title {
  min-width: 0;
}

.metric-mobile-card__title p {
  margin: 6px 0 0;
  color: var(--app-text-muted);
  font-size: 13px;
  line-height: 1.45;
}

.metric-mobile-card__meta {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
  margin-top: 12px;
}

.metric-mobile-card__meta div {
  display: flex;
  flex-direction: column;
  gap: 3px;
  min-width: 0;
  padding: 8px;
  border-radius: 8px;
  background: var(--app-surface-muted);
}

.metric-mobile-card__meta span {
  color: var(--app-text-muted);
  font-size: 12px;
}

.metric-mobile-card__meta strong {
  color: var(--app-text);
  font-size: 13px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.metric-mobile-card__actions {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  justify-content: flex-end;
  margin-top: 12px;
}

.metric-mobile-card__actions :deep(.el-button + .el-button) {
  margin-left: 0;
}

.metric-icon-actions {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  flex-wrap: wrap;
}

.metric-icon-actions :deep(.el-button + .el-button) {
  margin-left: 0;
}

.metric-icon-button {
  width: 32px;
  height: 32px;
  min-height: 32px;
  padding: 0;
}

.metric-mobile-card__actions.metric-icon-actions {
  justify-content: flex-end;
}

.metric-mobile-empty {
  min-height: 220px;
}


.code-input :deep(textarea) {
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
}

.certifier-tree-select {
  min-width: 0;
}

.certifier-helper {
  margin-top: 6px;
  font-size: 12px;
  line-height: 1.5;
  color: var(--app-text-muted);
}

.lineage-dialog {
  min-height: 180px;
  padding: 0;
}

/* ── 顶部固定头 ────────────────────────────────────────────────── */
.lineage-header-bar {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  padding: 18px 20px 14px;
  border-bottom: 1px solid var(--app-border);
}

.lineage-header-identity {
  display: flex;
  flex-direction: column;
  gap: 3px;
  min-width: 0;
}

.lineage-header-ds {
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.6px;
  color: var(--app-primary);
  font-weight: 600;
}

.lineage-header-name {
  margin: 0;
  font-size: 17px;
  font-weight: 700;
  color: var(--app-text);
  line-height: 1.3;
}

.lineage-header-tags {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
  flex-wrap: wrap;
  justify-content: flex-end;
}

.lineage-version-chip {
  display: inline-block;
  padding: 2px 8px;
  font-size: 11px;
  font-weight: 600;
  border-radius: 99px;
  background: var(--app-surface-muted);
  border: 1px solid var(--app-border);
  color: var(--app-text-muted);
}

/* ── Tab 容器 ──────────────────────────────────────────────────── */
.lineage-tabs {
  padding: 0;
}

.lineage-tabs :deep(.el-tabs__header) {
  margin: 0;
  padding: 0 20px;
  border-bottom: 1px solid var(--app-border);
  background: var(--app-surface-muted);
}

.lineage-tabs :deep(.el-tabs__nav-wrap::after) {
  display: none;
}

.lineage-tabs :deep(.el-tabs__item) {
  height: 40px;
  line-height: 40px;
  font-size: 13px;
  color: var(--app-text-muted);
  padding: 0 14px;
}

.lineage-tabs :deep(.el-tabs__item.is-active) {
  color: var(--app-primary);
  font-weight: 600;
}

.lineage-tabs :deep(.el-tabs__active-bar) {
  background: var(--app-primary);
  height: 2px;
}

.lineage-tabs :deep(.el-tabs__content) {
  padding: 0;
}

/* Tab 内容区公共内边距 */
.lineage-tab-content {
  padding: 20px;
}

.lineage-complexity-banner {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 14px;
  padding: 12px 14px;
  border: 1px solid rgba(8, 145, 178, 0.22);
  border-left: 4px solid #0891b2;
  border-radius: var(--app-radius-sm);
  background: rgba(8, 145, 178, 0.06);
  color: var(--app-text);
}

.lineage-complexity-banner.is-join {
  border-color: rgba(5, 150, 105, 0.24);
  border-left-color: #059669;
  background: rgba(5, 150, 105, 0.06);
}

.lineage-complexity-banner > .el-icon {
  flex: 0 0 auto;
  width: 32px;
  height: 32px;
  border-radius: var(--app-radius-sm);
  background: var(--app-surface);
  color: #0891b2;
}

.lineage-complexity-banner.is-join > .el-icon {
  color: #059669;
}

.lineage-complexity-banner strong,
.lineage-complexity-banner span {
  display: block;
}

.lineage-complexity-banner strong {
  font-size: 14px;
  line-height: 1.4;
}

.lineage-complexity-banner span {
  margin-top: 2px;
  font-size: 12px;
  line-height: 1.5;
  color: var(--app-text-muted);
}


/* ── 口径定义 Tab ──────────────────────────────────────────────── */
.lineage-def-block {
  margin: 0 0 14px;
  padding: 12px 16px;
  border-left: 3px solid var(--app-primary);
  background: var(--app-surface-muted);
  border-radius: 0 var(--app-radius-sm) var(--app-radius-sm) 0;
  color: var(--app-text);
  font-size: 14px;
  line-height: 1.7;
}

.lineage-formula-block {
  margin: 0 0 14px;
  padding: 12px 16px;
  border: 1px solid var(--app-border);
  border-radius: var(--app-radius-sm);
  background: #0f172a;
  color: #7dd3fc;
  font-family: ui-monospace, Menlo, monospace;
  font-size: 12px;
  line-height: 1.7;
  white-space: pre-wrap;
  word-break: break-all;
}

.lineage-meta-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px;
}

.lineage-meta-item {
  padding: 10px 12px;
  border: 1px solid var(--app-border);
  border-radius: var(--app-radius-sm);
  background: var(--app-surface);
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.lineage-meta-item span {
  font-size: 11px;
  color: var(--app-text-muted);
  text-transform: uppercase;
  letter-spacing: 0.4px;
}

.lineage-meta-item strong {
  font-size: 13px;
  color: var(--app-text);
  font-weight: 600;
  word-break: break-all;
}

/* JOIN 关联表格 */
.lineage-join-table-wrap {
  overflow-x: auto;
  border: 1px solid var(--app-border);
  border-radius: var(--app-radius-sm);
}

.lineage-join-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}

.lineage-join-table th {
  padding: 8px 12px;
  text-align: left;
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.4px;
  color: var(--app-text-muted);
  background: var(--app-surface-muted);
  border-bottom: 1px solid var(--app-border);
  white-space: nowrap;
}

.lineage-join-table td {
  padding: 9px 12px;
  border-bottom: 1px solid var(--app-border);
  color: var(--app-text);
  vertical-align: top;
}

.lineage-join-table tr:last-child td {
  border-bottom: none;
}

.lineage-join-table tr:hover td {
  background: var(--app-surface-muted);
}

.lineage-join-table code {
  font-family: ui-monospace, Menlo, monospace;
  font-size: 11px;
  color: #0369a1;
}

.join-alias {
  font-size: 11px;
  color: var(--app-text-muted);
}

.join-cols-cell {
  font-size: 11px;
  color: var(--app-text-muted);
  max-width: 180px;
}

.join-type-primary {
  background: rgba(99, 102, 241, 0.12) !important;
  color: #4f46e5 !important;
}

/* ── 质量与认证 Tab ────────────────────────────────────────────── */
.lineage-trust-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 14px;
}

.lineage-trust-card {
  padding: 16px;
  border: 1px solid var(--app-border);
  border-radius: var(--app-radius-sm);
  background: var(--app-surface);
}

.lineage-trust-badge {
  margin: 8px 0 14px;
}

.lineage-trust-dl {
  display: grid;
  grid-template-columns: 64px 1fr;
  gap: 10px 12px;
  margin: 0;
}

.lineage-trust-dl dt {
  font-size: 12px;
  color: var(--app-text-muted);
}

.lineage-trust-dl dd {
  margin: 0;
  font-size: 13px;
  color: var(--app-text);
  word-break: break-word;
}

@media (max-width: 768px) {
  .metric-card .governance-table {
    display: none;
  }

  .metric-mobile-list {
    display: flex;
    flex-direction: column;
    gap: 12px;
    padding: 0 12px 12px;
  }

  .metric-title-row {
    flex-wrap: wrap;
  }

  .metric-mobile-card__head {
    flex-direction: column;
  }

  .metric-mobile-card__actions {
    justify-content: flex-start;
  }
}

@media (max-width: 640px) {
  .lineage-meta-grid {
    grid-template-columns: 1fr 1fr;
  }

  .lineage-trust-grid {
    grid-template-columns: 1fr;
  }

  .lineage-header-bar {
    flex-direction: column;
    gap: 10px;
  }

  .lineage-header-tags {
    justify-content: flex-start;
  }
}

.lineage-flow-section {
  margin-bottom: 20px;
}

.lineage-section-label {
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.8px;
  color: var(--app-text-muted);
  margin: 0 0 10px;
}

.lineage-flow {
  display: flex;
  align-items: stretch;
  gap: 0;
  overflow-x: auto;
  padding-bottom: 4px;
}

.lineage-arrow {
  display: flex;
  align-items: center;
  padding: 0 6px;
  color: var(--app-text-muted);
  font-size: 18px;
  flex-shrink: 0;
}

.lineage-node {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  padding: 10px 14px;
  border: 1.5px solid var(--app-border);
  border-radius: var(--app-radius-sm);
  background: var(--app-surface);
  min-width: 120px;
  max-width: 180px;
  flex-shrink: 0;
}

.lineage-node--source  { border-color: #6366f1; background: rgba(99,102,241,.05); }
.lineage-node--dataset { border-color: #0f766e; background: rgba(15,118,110,.05); }
.lineage-node--table   { border-color: #0891b2; background: rgba(8,145,178,.05); }
.lineage-node--column  { border-color: #059669; background: rgba(5,150,105,.05); }
.lineage-node--metric  { border-color: #d97706; background: rgba(217,119,6,.05); }
.lineage-node--formula { border-color: #dc2626; background: rgba(220,38,38,.05); }
.lineage-step--aggregate { border-color: #059669; background: rgba(5,150,105,.08); }

.lineage-node-icon {
  flex: 0 0 auto;
  width: 18px;
  height: 18px;
  font-size: 18px;
  line-height: 1;
  margin-top: 2px;
}

.lineage-node-body {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}

.lineage-node-type {
  font-size: 10px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  color: var(--app-text-muted);
}

.lineage-node-name {
  font-size: 13px;
  font-weight: 600;
  color: var(--app-text);
  word-break: break-all;
}

.lineage-node-meta {
  font-size: 11px;
  color: var(--app-text-muted);
}

.lineage-node-formula {
  font-family: ui-monospace, Menlo, monospace;
  font-size: 11px;
  color: var(--app-text);
  word-break: break-all;
}

/* ── JOIN DAG 视图 ─────────────────────────────────────────────── */
.lineage-dag {
  display: flex;
  align-items: center;
  gap: 0;
  overflow-x: auto;
  padding-bottom: 4px;
}

/* 多表堆叠容器：表节点列 + 括号 */
.lineage-dag-tables-wrap {
  display: flex;
  align-items: stretch;
}

.lineage-dag-tables {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

/* CSS 括号：右侧 ╗╝ 形状，把多张表收拢到一个出口 */
.lineage-dag-bracket {
  flex-shrink: 0;
  width: 14px;
  margin-left: 6px;
  border-top: 2px solid #0891b2;
  border-right: 2px solid #0891b2;
  border-bottom: 2px solid #0891b2;
  border-radius: 0 6px 6px 0;
  align-self: stretch;
}

/* JOIN 合并节点颜色 */
.lineage-node--join {
  border-color: #7c3aed;
  background: rgba(124, 58, 237, 0.05);
}

/* 在多表堆叠里用的紧凑表节点 */
.lineage-node--sm {
  min-width: 130px;
  max-width: 210px;
}

/* JOIN 类型徽章 */
.join-type-badge {
  display: inline-block;
  padding: 1px 5px;
  border-radius: 3px;
  background: rgba(8, 145, 178, 0.12);
  color: #0369a1;
  font-size: 9px;
  font-weight: 700;
  letter-spacing: 0.3px;
  text-transform: uppercase;
}

/* ON 条件字体 */
.lineage-join-on {
  font-family: ui-monospace, Menlo, monospace;
  font-size: 10px;
  word-break: break-all;
}

/* 过滤条件行 */
.lineage-dag-filters {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  margin-top: 10px;
  padding: 8px 12px;
  border-radius: var(--app-radius-sm);
  background: rgba(217, 119, 6, 0.05);
  border: 1px solid rgba(217, 119, 6, 0.15);
}

.lineage-filter-pill {
  font-family: ui-monospace, Menlo, monospace;
  font-size: 11px;
  padding: 2px 8px;
  background: rgba(217, 119, 6, 0.1);
  border: 1px solid rgba(217, 119, 6, 0.25);
  border-radius: 4px;
  color: #92400e;
}

.lineage-dag-groups {
  background: rgba(5, 150, 105, 0.05);
  border-color: rgba(5, 150, 105, 0.18);
}

.lineage-dag-groups .lineage-filter-pill {
  background: rgba(5, 150, 105, 0.1);
  border-color: rgba(5, 150, 105, 0.24);
  color: #047857;
}

/* lineage-list 里的 JOIN 条件行 */
.lineage-join-condition {
  margin-top: 2px;
}
.lineage-join-condition code {
  font-family: ui-monospace, Menlo, monospace;
  font-size: 11px;
  color: var(--app-text);
}
</style>
