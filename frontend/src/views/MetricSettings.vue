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
            <div class="modal-tab-content enterprise-caliber-workbench">
              <div class="caliber-overview">
                <div class="caliber-overview-main">
                  <span>口径成熟度</span>
                  <strong>{{ caliberCompleteness }}%</strong>
                  <el-progress :percentage="caliberCompleteness" :show-text="false" />
                </div>
                <div class="caliber-checklist">
                  <span
                    v-for="item in caliberChecklist"
                    :key="item.label"
                    class="caliber-check-item"
                    :class="{ 'is-done': item.done }"
                  >
                    {{ item.label }}
                  </span>
                </div>
                <el-button :loading="generatingFormula" @click="openFormulaAssistant">AI 生成公式</el-button>
              </div>

              <div class="caliber-grid">
                <section class="caliber-panel">
                  <div class="caliber-panel-head">
                    <strong>计算模型</strong>
                    <span>定义指标如何从数据集字段计算出来</span>
                  </div>
                  <div class="calculation-mode-switcher" role="list" aria-label="计算类型">
                    <button
                      v-for="mode in calculationModeOptions"
                      :key="mode.value"
                      type="button"
                      class="calculation-mode-card"
                      :class="{ 'is-active': isCalculationMode(mode.value) }"
                      @click="setCalculationMode(mode.value)"
                    >
                      <el-icon><component :is="mode.icon" /></el-icon>
                      <span>
                        <strong>{{ mode.label }}</strong>
                        <small>{{ mode.description }}</small>
                      </span>
                    </button>
                  </div>
                  <div class="calculation-mode-current">
                    <strong>{{ currentCalculationModeMeta.label }}</strong>
                    <span>{{ currentCalculationModeMeta.helper }}</span>
                  </div>
                  <div class="field-candidate-panel">
                    <div class="field-candidate-panel__head">
                      <strong>数据集字段候选项</strong>
                      <span>{{ currentDataset?.name || "先选择数据集后展示字段" }}</span>
                    </div>
                    <div v-if="allDatasetFieldOptions.length" class="field-candidate-tools">
                      <el-input
                        v-model="fieldCandidateKeyword"
                        class="field-candidate-search"
                        clearable
                        :prefix-icon="Search"
                        placeholder="搜索字段 / 别名 / 类型"
                      />
                      <div class="field-candidate-role-filter" role="group" aria-label="字段类型筛选">
                        <button
                          v-for="item in fieldCandidateFilterOptions"
                          :key="item.value"
                          type="button"
                          :class="{ 'is-active': fieldCandidateRoleFilter === item.value }"
                          @click="fieldCandidateRoleFilter = item.value"
                        >
                          {{ item.label }}
                          <small>{{ item.count }}</small>
                        </button>
                      </div>
                    </div>
                    <div v-if="allDatasetFieldOptions.length" class="field-insert-toolbar">
                      <span>插入到</span>
                      <el-select v-model="fieldInsertTarget" class="field-insert-target" size="small">
                        <el-option
                          v-for="item in fieldInsertTargetOptions"
                          :key="item.value"
                          :label="item.label"
                          :value="item.value"
                        />
                      </el-select>
                      <small>{{ fieldInsertHelper }}</small>
                    </div>
                    <div v-if="filteredCandidateFields.length" class="field-candidate-chips">
                      <button
                        v-for="field in filteredCandidateFields.slice(0, 12)"
                        :key="`${field.role}-${field.name}`"
                        type="button"
                        class="field-candidate-chip"
                        @click="insertCandidateField(field)"
                      >
                        <strong>
                          {{ field.label }}
                          <span class="field-candidate-chip__role">
                            {{ field.role === "dimension" ? "维度" : "指标" }}
                          </span>
                        </strong>
                        <small>{{ field.name }}</small>
                      </button>
                    </div>
                    <p v-else class="field-candidate-empty">
                      {{ allDatasetFieldOptions.length ? "没有匹配字段，请调整搜索词。" : "当前数据集暂无字段候选，请先在数据集开发中配置字段。" }}
                    </p>
                  </div>

                  <div v-if="isCalculationMode('aggregate')" class="mode-config-grid">
                    <el-form-item label="聚合字段">
                      <el-select
                        v-model="form.calculation_config.metric_field"
                        class="field-picker-select"
                        filterable
                        clearable
                        placeholder="选择指标字段"
                        style="width: 100%"
                      >
                        <el-option-group v-for="group in metricFieldOptionGroups" :key="group.label" :label="group.label">
                          <el-option v-for="field in group.options" :key="`${group.label}-${field.name}`" :label="fieldOptionLabel(field)" :value="field.name">
                            <div class="field-option-row">
                              <span>{{ field.label }}</span>
                              <small>{{ fieldOptionDetail(field) }}</small>
                            </div>
                          </el-option>
                        </el-option-group>
                      </el-select>
                    </el-form-item>
                    <el-form-item label="聚合方式">
                      <el-select v-model="form.aggregation" style="width: 100%">
                        <el-option v-for="item in aggregationFunctionOptions" :key="item.value" :label="item.label" :value="item.value" />
                      </el-select>
                    </el-form-item>
                    <el-form-item label="输出字段">
                      <el-input v-model="form.column_name" placeholder="指标落表或目录展示字段，如：gmv、order_count" />
                    </el-form-item>
                  </div>

                  <div v-if="isCalculationMode('ratio')" class="mode-config-grid structured-caliber-builder">
                    <el-form-item class="mode-config-grid__wide" label="分子指标">
                      <div class="metric-operand-picker">
                        <el-select v-model="form.calculation_config.numerator_aggregation" class="operand-aggregation-select" placeholder="聚合方式">
                          <el-option v-for="item in aggregationFunctionOptions" :key="`num-${item.value}`" :label="item.label" :value="item.value" />
                        </el-select>
                        <el-select
                          v-model="form.calculation_config.numerator_field"
                          class="field-picker-select"
                          filterable
                          clearable
                          placeholder="选择分子字段"
                          style="width: 100%"
                        >
                          <el-option-group v-for="group in metricFieldOptionGroups" :key="`num-${group.label}`" :label="group.label">
                            <el-option v-for="field in group.options" :key="`num-${group.label}-${field.name}`" :label="fieldOptionLabel(field)" :value="field.name">
                              <div class="field-option-row">
                                <span>{{ field.label }}</span>
                                <small>{{ fieldOptionDetail(field) }}</small>
                              </div>
                            </el-option>
                          </el-option-group>
                        </el-select>
                      </div>
                    </el-form-item>
                    <el-form-item class="mode-config-grid__wide" label="分母指标">
                      <div class="metric-operand-picker">
                        <el-select v-model="form.calculation_config.denominator_aggregation" class="operand-aggregation-select" placeholder="聚合方式">
                          <el-option v-for="item in aggregationFunctionOptions" :key="`den-${item.value}`" :label="item.label" :value="item.value" />
                        </el-select>
                        <el-select
                          v-model="form.calculation_config.denominator_field"
                          class="field-picker-select"
                          filterable
                          clearable
                          placeholder="选择分母字段"
                          style="width: 100%"
                        >
                          <el-option-group v-for="group in metricFieldOptionGroups" :key="`den-${group.label}`" :label="group.label">
                            <el-option v-for="field in group.options" :key="`den-${group.label}-${field.name}`" :label="fieldOptionLabel(field)" :value="field.name">
                              <div class="field-option-row">
                                <span>{{ field.label }}</span>
                                <small>{{ fieldOptionDetail(field) }}</small>
                              </div>
                            </el-option>
                          </el-option-group>
                        </el-select>
                      </div>
                    </el-form-item>
                    <el-form-item label="小数精度">
                      <el-input-number v-model="form.calculation_config.decimal_precision" :min="0" :max="8" style="width: 100%" />
                    </el-form-item>
                    <el-form-item label="输出字段">
                      <el-input v-model="form.column_name" placeholder="如：collection_rate、conversion_rate" />
                    </el-form-item>
                  </div>

                  <div v-if="isCalculationMode('derived')" class="mode-config-grid structured-caliber-builder">
                    <el-form-item class="mode-config-grid__wide" label="派生运算">
                      <div class="derived-builder">
                        <el-select
                          v-model="form.calculation_config.derived_left_field"
                          class="field-picker-select"
                          filterable
                          clearable
                          placeholder="选择左侧指标"
                          style="width: 100%"
                        >
                          <el-option-group v-for="group in derivedMetricOperandGroups" :key="`left-${group.label}`" :label="group.label">
                            <el-option v-for="field in group.options" :key="`left-${group.label}-${field.name}`" :label="fieldOptionLabel(field)" :value="field.name">
                              <div class="field-option-row">
                                <span>{{ field.label }}</span>
                                <small>{{ fieldOptionDetail(field) }}</small>
                              </div>
                            </el-option>
                          </el-option-group>
                        </el-select>
                        <div class="derived-operator-group" role="group" aria-label="派生运算">
                          <button
                            v-for="item in derivedOperatorOptions"
                            :key="item.value"
                            type="button"
                            class="derived-operator-button"
                            :class="{ 'is-active': form.calculation_config.derived_operator === item.value }"
                            :title="item.title"
                            @click="form.calculation_config.derived_operator = item.value"
                          >
                            {{ item.label }}
                          </button>
                        </div>
                        <el-select
                          v-model="form.calculation_config.derived_right_field"
                          class="field-picker-select"
                          filterable
                          clearable
                          placeholder="选择右侧指标"
                          style="width: 100%"
                        >
                          <el-option-group v-for="group in derivedMetricOperandGroups" :key="`right-${group.label}`" :label="group.label">
                            <el-option v-for="field in group.options" :key="`right-${group.label}-${field.name}`" :label="fieldOptionLabel(field)" :value="field.name">
                              <div class="field-option-row">
                                <span>{{ field.label }}</span>
                                <small>{{ fieldOptionDetail(field) }}</small>
                              </div>
                            </el-option>
                          </el-option-group>
                        </el-select>
                      </div>
                      <small class="builder-hint">{{ derivedDependencyText || "选择左右指标后，系统会自动生成依赖指标和计算公式。" }}</small>
                    </el-form-item>
                    <el-form-item label="输出别名">
                      <el-input v-model="form.calculation_config.output_alias" placeholder="如：gross_margin_rate" />
                    </el-form-item>
                  </div>

                  <div v-if="isCalculationMode('window')" class="mode-config-grid">
                    <el-form-item label="基础表达式">
                      <el-select
                        v-model="form.calculation_config.metric_field"
                        class="field-picker-select"
                        filterable
                        clearable
                        placeholder="选择基础字段"
                        style="width: 100%"
                      >
                        <el-option-group v-for="group in metricFieldOptionGroups" :key="group.label" :label="group.label">
                          <el-option v-for="field in group.options" :key="`${group.label}-${field.name}`" :label="fieldOptionLabel(field)" :value="field.name">
                            <div class="field-option-row">
                              <span>{{ field.label }}</span>
                              <small>{{ fieldOptionDetail(field) }}</small>
                            </div>
                          </el-option>
                        </el-option-group>
                      </el-select>
                    </el-form-item>
                    <el-form-item label="窗口函数">
                      <el-select v-model="form.calculation_config.window_function" style="width: 100%">
                        <el-option label="累计求和" value="sum_over" />
                        <el-option label="移动平均" value="avg_over" />
                        <el-option label="排名" value="rank" />
                        <el-option label="稠密排名" value="dense_rank" />
                        <el-option label="行号" value="row_number" />
                        <el-option label="环比 LAG" value="lag" />
                        <el-option label="提前 LEAD" value="lead" />
                      </el-select>
                    </el-form-item>
                    <el-form-item label="分区字段">
                      <el-select
                        v-model="form.calculation_config.partition_by"
                        class="field-picker-select"
                        filterable
                        clearable
                        placeholder="选择分区字段"
                        style="width: 100%"
                      >
                        <el-option-group v-for="group in fieldOptionGroups" :key="group.label" :label="group.label">
                          <el-option v-for="field in group.options" :key="`${group.label}-${field.name}`" :label="fieldOptionLabel(field)" :value="field.name">
                            <div class="field-option-row">
                              <span>{{ field.label }}</span>
                              <small>{{ fieldOptionDetail(field) }}</small>
                            </div>
                          </el-option>
                        </el-option-group>
                      </el-select>
                    </el-form-item>
                    <el-form-item label="排序字段">
                      <el-select
                        v-model="form.calculation_config.order_by"
                        class="field-picker-select"
                        filterable
                        clearable
                        placeholder="选择排序字段"
                        style="width: 100%"
                      >
                        <el-option-group v-for="group in fieldOptionGroups" :key="group.label" :label="group.label">
                          <el-option v-for="field in group.options" :key="`${group.label}-${field.name}`" :label="fieldOptionLabel(field)" :value="field.name">
                            <div class="field-option-row">
                              <span>{{ field.label }}</span>
                              <small>{{ fieldOptionDetail(field) }}</small>
                            </div>
                          </el-option>
                        </el-option-group>
                      </el-select>
                    </el-form-item>
                    <el-form-item label="排序方向">
                      <el-segmented v-model="form.calculation_config.order_direction" :options="orderDirectionOptions" style="width: 100%" />
                    </el-form-item>
                    <el-form-item class="mode-config-grid__wide" label="窗口范围">
                      <el-select v-model="form.calculation_config.window_frame" class="window-frame-select" style="width: 100%">
                        <el-option v-for="item in windowFrameOptions" :key="item.value" :label="item.label" :value="item.value" />
                      </el-select>
                    </el-form-item>
                  </div>

                  <div class="formula-preview-panel">
                    <div class="formula-preview-panel__head">
                      <div>
                        <strong>公式预览</strong>
                        <span>{{ formulaPreviewStatus }}</span>
                      </div>
                      <el-button size="small" type="primary" plain :disabled="!formulaPreview" @click="applyFormulaPreview">应用预览公式</el-button>
                    </div>
                    <pre v-if="formulaPreview">{{ formulaPreview }}</pre>
                    <p v-else>选择字段并补齐必要参数后自动生成预览。</p>
                  </div>
                </section>

                <section class="caliber-panel">
                  <div class="caliber-panel-head">
                    <strong>统计范围</strong>
                    <span>明确时间口径、可分析维度和数据刷新承诺</span>
                  </div>
                  <el-row :gutter="12">
                    <el-col :xs="24" :md="12">
                      <el-form-item label="统计周期">
                        <el-input v-model="form.calculation_config.statistical_window" placeholder="如：自然日、自然月、滚动 30 天" />
                      </el-form-item>
                    </el-col>
                    <el-col :xs="24" :md="12">
                      <el-form-item label="时间粒度">
                        <el-select v-model="form.calculation_config.time_grain" style="width: 100%">
                          <el-option label="明细" value="none" />
                          <el-option label="小时" value="hour" />
                          <el-option label="日" value="day" />
                          <el-option label="周" value="week" />
                          <el-option label="月" value="month" />
                          <el-option label="季度" value="quarter" />
                          <el-option label="年" value="year" />
                        </el-select>
                      </el-form-item>
                    </el-col>
                  </el-row>
                  <el-row :gutter="12">
                    <el-col :xs="24" :md="12">
                      <el-form-item label="时间字段">
                        <el-select
                          v-model="form.calculation_config.time_field"
                          class="field-picker-select"
                          filterable
                          clearable
                          placeholder="选择时间字段"
                          style="width: 100%"
                        >
                          <el-option v-for="field in timeFieldOptions" :key="`time-${field.name}`" :label="fieldOptionLabel(field)" :value="field.name">
                            <div class="field-option-row">
                              <span>{{ field.label }}</span>
                              <small>{{ fieldOptionDetail(field) }}</small>
                            </div>
                          </el-option>
                        </el-select>
                      </el-form-item>
                    </el-col>
                    <el-col :xs="24" :md="12">
                      <el-form-item label="刷新 SLA">
                        <el-input v-model="form.calculation_config.refresh_sla" placeholder="如：T+1 08:00 前完成刷新" />
                      </el-form-item>
                    </el-col>
                  </el-row>
                  <el-row :gutter="12">
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
                </section>
              </div>

              <section class="caliber-panel">
                <div class="caliber-panel-head with-action">
                  <div>
                    <strong>过滤 / 排除规则</strong>
                    <span>把统计对象、状态、组织范围等口径条件显式化，计算接口会复用这些条件</span>
                  </div>
                  <el-button :icon="Plus" @click="addCalculationFilter">添加规则</el-button>
                </div>
                <div class="filter-rule-list">
                  <div v-for="(rule, index) in form.calculation_config.filters" :key="index" class="filter-rule-row">
                    <el-select v-model="rule.logic" class="filter-logic" :disabled="index === 0">
                      <el-option label="AND" value="AND" />
                      <el-option label="OR" value="OR" />
                    </el-select>
                    <el-select
                      v-model="rule.field"
                      class="filter-field-select field-picker-select"
                      filterable
                      clearable
                      placeholder="选择过滤字段"
                    >
                      <el-option-group v-for="group in fieldOptionGroups" :key="group.label" :label="group.label">
                        <el-option v-for="field in group.options" :key="`${index}-${group.label}-${field.name}`" :label="fieldOptionLabel(field)" :value="field.name">
                          <div class="field-option-row">
                            <span>{{ field.label }}</span>
                            <small>{{ fieldOptionDetail(field) }}</small>
                          </div>
                        </el-option>
                      </el-option-group>
                    </el-select>
                    <el-select v-model="rule.operator" class="filter-operator">
                      <el-option label="=" value="=" />
                      <el-option label="!=" value="!=" />
                      <el-option label=">" value=">" />
                      <el-option label=">=" value=">=" />
                      <el-option label="<" value="<" />
                      <el-option label="<=" value="<=" />
                      <el-option label="包含 LIKE" value="LIKE" />
                      <el-option label="IN" value="IN" />
                      <el-option label="为空" value="IS NULL" />
                      <el-option label="不为空" value="IS NOT NULL" />
                    </el-select>
                    <el-input v-model="rule.value" placeholder="值，如 已完成；IN 用逗号分隔" />
                    <el-button :icon="Delete" circle text type="danger" aria-label="删除过滤规则" @click="removeCalculationFilter(index)" />
                  </div>
                </div>
              </section>

              <section class="caliber-panel metric-preview-panel">
                <div class="caliber-panel-head with-action">
                  <div>
                    <strong>实时数据预览</strong>
                    <span>{{ metricPreviewStatusText }}</span>
                  </div>
                  <el-button :icon="Refresh" :loading="metricPreviewLoading" :disabled="!editingId" @click="fetchMetricPreview">刷新</el-button>
                </div>
                <div class="metric-preview-controls">
                  <el-select
                    v-model="metricPreviewDimensions"
                    class="metric-preview-dimensions field-picker-select"
                    multiple
                    clearable
                    collapse-tags
                    collapse-tags-tooltip
                    filterable
                    placeholder="选择预览维度"
                    :disabled="!editingId"
                    @change="fetchMetricPreview"
                  >
                    <el-option
                      v-for="field in metricPreviewDimensionOptions"
                      :key="`preview-${field.name}`"
                      :label="fieldOptionLabel(field)"
                      :value="field.name"
                    >
                      <div class="field-option-row">
                        <span>{{ field.label }}</span>
                        <small>{{ fieldOptionDetail(field) }}</small>
                      </div>
                    </el-option>
                  </el-select>
                </div>
                <div v-if="metricPreviewError" class="metric-preview-error">
                  {{ metricPreviewError }}
                </div>
                <el-table
                  v-else
                  class="metric-preview-table"
                  :data="metricPreviewRows"
                  v-loading="metricPreviewLoading"
                  size="small"
                  border
                  empty-text="暂无预览数据"
                >
                  <el-table-column
                    v-for="column in metricPreviewColumns"
                    :key="column"
                    :label="column"
                    min-width="140"
                    show-overflow-tooltip
                  >
                    <template #default="{ row }">
                      {{ formatPreviewCell(row[column]) }}
                    </template>
                  </el-table-column>
                </el-table>
                <details v-if="metricPreviewSql" class="metric-preview-sql-details">
                  <summary>查看后端 SQL</summary>
                  <div class="metric-preview-sql-body">
                    <el-button
                      class="metric-preview-sql-copy"
                      size="small"
                      text
                      type="primary"
                      :icon="CopyDocument"
                      aria-label="复制 SQL 到剪贴板"
                      @click="copyMetricPreviewSql"
                    >
                      复制 SQL
                    </el-button>
                    <pre class="metric-preview-sql">{{ metricPreviewSql }}</pre>
                  </div>
                </details>
              </section>
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
      v-model="formulaAssistantVisible"
      title="AI 公式生成"
      width="min(920px, calc(100vw - 32px))"
      class="governance-modal formula-assistant-dialog"
      append-to-body
    >
      <div class="formula-assistant">
        <section class="formula-assistant-prompt">
          <div class="formula-assistant-context">
            <span>{{ currentDataset?.name || "未选择数据集" }}</span>
            <span>{{ currentCalculationModeMeta.label }}</span>
            <span>{{ form.unit || "无单位" }}</span>
          </div>
          <el-form label-position="top">
            <el-form-item label="自然语言描述">
              <el-input
                v-model="formulaAssistantPrompt"
                type="textarea"
                :rows="4"
                maxlength="1200"
                show-word-limit
                placeholder="例如：统计已完成订单的回款金额 / 应收金额，退款和测试订单不纳入，按自然月统计"
              />
            </el-form-item>
          </el-form>
          <div class="formula-assistant-actions">
            <el-button type="primary" :loading="generatingFormula" @click="generateFormulaCandidate">生成候选公式</el-button>
          </div>
        </section>

        <div class="formula-assistant-grid">
          <section class="formula-assistant-thread">
            <div class="formula-assistant-section-head">
              <strong>修正对话</strong>
              <span>{{ formulaAssistantMessages.length }} 条</span>
            </div>
            <div class="formula-assistant-messages">
              <div v-if="!formulaAssistantMessages.length" class="formula-assistant-empty">
                输入描述后生成候选公式，应用时会先尝试映射为图形化配置。
              </div>
              <div
                v-for="(message, index) in formulaAssistantMessages"
                :key="index"
                class="formula-assistant-message"
                :class="`is-${message.role}`"
              >
                <span>{{ message.role === "user" ? "你" : "AI" }}</span>
                <p>{{ message.content }}</p>
              </div>
            </div>
            <el-input
              v-model="formulaAssistantFeedback"
              type="textarea"
              :rows="3"
              maxlength="800"
              show-word-limit
              placeholder="例如：分母应该用应收金额；只统计已完成订单；需要排除退款单"
            />
            <div class="formula-assistant-actions">
              <el-button :loading="generatingFormula" :disabled="!formulaCandidates.length" @click="refineFormulaCandidate">继续修正</el-button>
            </div>
          </section>

          <section class="formula-assistant-candidates">
            <div class="formula-assistant-section-head">
              <strong>候选公式</strong>
              <span>{{ formulaCandidates.length }} 个</span>
            </div>
            <div v-if="!formulaCandidates.length" class="formula-assistant-empty">
              暂无候选公式。
            </div>
            <article
              v-for="candidate in formulaCandidates"
              :key="candidate.id"
              class="formula-candidate-card"
              :class="{ 'is-selected': selectedFormulaCandidateId === candidate.id }"
              @click="selectedFormulaCandidateId = candidate.id"
            >
              <div class="formula-candidate-card__head">
                <strong>候选公式 #{{ candidate.id }}</strong>
                <el-tag :type="candidate.status === 'applied' ? 'success' : candidate.status === 'rejected' ? 'warning' : 'info'" effect="plain" size="small">
                  {{ candidate.status === "applied" ? "已应用" : candidate.status === "rejected" ? "已反馈" : "待确认" }}
                </el-tag>
              </div>
              <pre>{{ candidate.formula }}</pre>
              <p v-if="candidate.feedback">{{ candidate.feedback }}</p>
              <div class="formula-candidate-card__actions">
                <el-button size="small" type="primary" @click.stop="applyFormulaCandidate(candidate)">映射到配置</el-button>
              </div>
            </article>
          </section>
        </div>
      </div>
      <template #footer>
        <div class="governance-modal-footer">
          <span class="governance-modal-footer-note">候选公式必须映射为图形化配置后才会应用。</span>
          <div class="governance-modal-footer-actions">
            <el-button @click="formulaAssistantVisible = false">关闭</el-button>
            <el-button type="primary" :disabled="!selectedFormulaCandidate" @click="applyFormulaCandidate()">映射选中公式</el-button>
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

                <div v-if="lineage.metric.calculation_config" class="lineage-caliber-panel">
                  <p class="lineage-section-label">企业级计算口径</p>
                  <div class="lineage-caliber-grid">
                    <div v-for="item in lineageCalculationItems" :key="item.label" class="lineage-caliber-item">
                      <span>{{ item.label }}</span>
                      <strong>{{ item.value || "—" }}</strong>
                    </div>
                  </div>
                  <div v-if="lineageFilterRules.length" class="lineage-dag-filters">
                    <span class="lineage-section-label" style="margin:0;white-space:nowrap">过滤规则</span>
                    <code v-for="rule in lineageFilterRules" :key="rule" class="lineage-filter-pill">{{ rule }}</code>
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
import * as echarts from "@/utils/echarts"
import axios from "axios"
import { ElMessage, ElMessageBox } from "element-plus"
import {
  Coin,
  Connection,
  CopyDocument,
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
  calculation_config: CalculationConfig | null
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

interface CalculationFilterRule {
  logic: "AND" | "OR"
  field: string
  operator: string
  value: string
}

type CalculationMode = "aggregate" | "ratio" | "derived" | "window"
type RawField = string | Record<string, any>
type FieldRole = "dimension" | "metric"
type FieldCandidateRoleFilter = "all" | "dimension" | "metric"
type ExpressionTarget = "numerator_expression" | "denominator_expression" | "derived_expression"
type FieldInsertTarget =
  | "auto"
  | "metric_field"
  | "numerator_field"
  | "denominator_field"
  | "derived_left_field"
  | "derived_right_field"
  | "partition_by"
  | "order_by"
type FormulaAssistantRole = "user" | "assistant"
type FormulaCandidateStatus = "candidate" | "applied" | "rejected"

interface CalculationConfig {
  calculation_mode: CalculationMode
  metric_field: string
  numerator_field: string
  numerator_aggregation: string
  numerator_expression: string
  denominator_field: string
  denominator_aggregation: string
  denominator_expression: string
  derived_left_field: string
  derived_operator: string
  derived_right_field: string
  derived_expression: string
  dependency_metrics: string
  window_function: string
  partition_by: string
  order_by: string
  order_direction: string
  window_frame: string
  custom_sql: string
  output_alias: string
  statistical_window: string
  time_field: string
  time_grain: string
  refresh_sla: string
  filters: CalculationFilterRule[]
  decimal_precision: number | null
}

interface MetricForm {
  dataset_id: number | null
  name: string
  description: string
  definition: string
  column_name: string
  formula: string
  calculation_config: CalculationConfig
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
    calculation_config: CalculationConfig | null
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
  fields_json?: {
    table?: string
    fields?: RawField[]
    dimensions?: RawField[]
    metrics?: RawField[]
  } | null
  aggregations_json?: { aggregations?: RawField[] } | null
  derived_columns_json?: { expressions?: RawField[] } | null
  semantic_model_json?: {
    dimensions?: RawField[]
    time_dimensions?: RawField[]
    metrics?: RawField[]
    measures?: RawField[]
  } | null
}

interface DatasetFieldOption {
  name: string
  label: string
  type: string
  role: FieldRole
  aggregation?: string
  expression?: string
  source?: "dataset_metric" | "trusted_metric" | "dataset_derived"
  datasetName?: string
}

interface FormulaAssistantMessage {
  role: FormulaAssistantRole
  content: string
}

interface FormulaCandidate {
  id: number
  formula: string
  status: FormulaCandidateStatus
  feedback?: string
}

interface MetricPreviewQuery {
  sql?: string
  dimensions?: string[]
  limit?: number
  metric_column?: string
}

interface MetricPreviewResult {
  columns: string[]
  rows: Record<string, any>[]
  row_count: number
  query?: MetricPreviewQuery
}

interface FieldInsertTargetOption {
  label: string
  value: FieldInsertTarget
  helper: string
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
const formulaAssistantVisible = ref(false)
const formulaAssistantPrompt = ref("")
const formulaAssistantFeedback = ref("")
const formulaAssistantMessages = ref<FormulaAssistantMessage[]>([])
const formulaCandidates = ref<FormulaCandidate[]>([])
const selectedFormulaCandidateId = ref<number | null>(null)
const formulaCandidateCounter = ref(0)
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
const fieldCandidateKeyword = ref("")
const fieldCandidateRoleFilter = ref<FieldCandidateRoleFilter>("all")
const fieldInsertTarget = ref<FieldInsertTarget>("auto")
const metricPreviewDimensions = ref<string[]>([])
const metricPreviewColumns = ref<string[]>([])
const metricPreviewRows = ref<Record<string, any>[]>([])
const metricPreviewLoading = ref(false)
const metricPreviewError = ref("")
const metricPreviewRowCount = ref(0)
const metricPreviewSql = ref("")

const emptyCalculationFilter = (): CalculationFilterRule => ({
  logic: "AND",
  field: "",
  operator: "=",
  value: "",
})

const calculationModeOptions = [
  {
    value: "aggregate",
    label: "聚合指标",
    description: "单字段汇总",
    helper: "适合销售额、订单数、库存量等按维度汇总的经营指标。",
    formulaPlaceholder: "由聚合字段与聚合方式自动生成",
    icon: Histogram,
  },
  {
    value: "ratio",
    label: "比率指标",
    description: "分子 / 分母",
    helper: "适合回款率、转化率、达成率等需要明确分子、分母和展示精度的指标。",
    formulaPlaceholder: "由分子、分母字段和聚合方式自动生成",
    icon: Connection,
  },
  {
    value: "derived",
    label: "派生指标",
    description: "基于指标计算",
    helper: "适合毛利率、客单价等由已治理指标二次计算的复合指标。",
    formulaPlaceholder: "由左右操作数和运算按钮自动生成",
    icon: Operation,
  },
  {
    value: "window",
    label: "窗口指标",
    description: "排名 / 累计 / 滚动",
    helper: "适合累计销售额、移动平均、TOP 排名、环比等依赖分区和排序的指标。",
    formulaPlaceholder: "由窗口函数、分区、排序和窗口范围自动生成",
    icon: DataLine,
  },
] as const

const aggregationFunctionOptions = [
  { label: "求和", value: "sum" },
  { label: "平均", value: "avg" },
  { label: "计数", value: "count" },
  { label: "去重计数", value: "count_distinct" },
  { label: "最大值", value: "max" },
  { label: "最小值", value: "min" },
]

const derivedOperatorOptions = [
  { label: "+", value: "+", title: "相加" },
  { label: "-", value: "-", title: "相减" },
  { label: "x", value: "*", title: "相乘" },
  { label: "÷", value: "/", title: "相除，自动处理除零" },
]

const windowFrameOptions = [
  { label: "累计至当前行", value: "ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW" },
  { label: "近 7 行窗口", value: "ROWS BETWEEN 6 PRECEDING AND CURRENT ROW" },
  { label: "近 30 行窗口", value: "ROWS BETWEEN 29 PRECEDING AND CURRENT ROW" },
  { label: "仅当前行", value: "ROWS BETWEEN CURRENT ROW AND CURRENT ROW" },
]

const orderDirectionOptions = [
  { label: "升序", value: "ASC" },
  { label: "降序", value: "DESC" },
]

const normalizeCalculationMode = (mode?: string | null): CalculationMode => {
  return calculationModeOptions.some(item => item.value === mode) ? (mode as CalculationMode) : "aggregate"
}

const defaultCalculationConfig = (): CalculationConfig => ({
  calculation_mode: "aggregate",
  metric_field: "",
  numerator_field: "",
  numerator_aggregation: "sum",
  numerator_expression: "",
  denominator_field: "",
  denominator_aggregation: "sum",
  denominator_expression: "",
  derived_left_field: "",
  derived_operator: "/",
  derived_right_field: "",
  derived_expression: "",
  dependency_metrics: "",
  window_function: "sum_over",
  partition_by: "",
  order_by: "",
  order_direction: "ASC",
  window_frame: "ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW",
  custom_sql: "",
  output_alias: "",
  statistical_window: "自然日",
  time_field: "",
  time_grain: "day",
  refresh_sla: "T+1 08:00 前完成刷新",
  filters: [emptyCalculationFilter()],
  decimal_precision: 2,
})

const emptyForm = (): MetricForm => ({
  dataset_id: null,
  name: "",
  description: "",
  definition: "",
  column_name: "",
  formula: "",
  calculation_config: defaultCalculationConfig(),
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

const currentDataset = computed(() => datasets.value.find((item) => item.id === form.value.dataset_id) || null)
const asRawFieldList = (value: unknown): RawField[] => Array.isArray(value) ? value : []
const fieldSimpleName = (name: string) => name.includes(".") ? name.split(".").pop() || name : name
const rawFieldName = (field: RawField) => {
  if (typeof field === "string") return field.trim()
  return String(field.field || field.name || field.key || field.column || "").trim()
}
const rawFieldLabel = (field: RawField, fallback: string) => {
  if (typeof field === "string") return fieldSimpleName(fallback)
  return String(field.alias || field.label || field.display_name || field.title || fieldSimpleName(fallback)).trim()
}
const rawFieldType = (field: RawField) => {
  if (typeof field === "string") return "string"
  return String(field.type || field.data_type || field.column_type || "string").trim()
}
const rawFieldAggregation = (field: RawField) => {
  if (typeof field === "string") return "sum"
  return String(field.aggregation || field.fn || field.aggregate || "sum").toLowerCase()
}
const normalizeDatasetField = (field: RawField, role: FieldRole): DatasetFieldOption | null => {
  const name = rawFieldName(field)
  if (!name) return null
  return {
    name,
    label: rawFieldLabel(field, name),
    type: rawFieldType(field),
    role,
    aggregation: role === "metric" ? rawFieldAggregation(field) : undefined,
    source: role === "metric" ? "dataset_metric" : undefined,
  }
}
const dedupeDatasetFields = (fields: Array<DatasetFieldOption | null>) => {
  const seen = new Set<string>()
  return fields.filter((field): field is DatasetFieldOption => {
    if (!field) return false
    const key = `${field.role}:${field.name}`
    if (seen.has(key)) return false
    seen.add(key)
    return true
  })
}

const dimensionFieldOptions = computed(() => {
  const dataset = currentDataset.value
  if (!dataset) return []
  const fieldsJson = dataset.fields_json || {}
  const semantic = dataset.semantic_model_json || {}
  const legacyDimensions = asRawFieldList(fieldsJson.fields).filter((field) => {
    if (typeof field === "string") return true
    const role = String(field.role || field.semantic_type || "").toLowerCase()
    return role !== "metric" && role !== "measure"
  })
  const derivedColumnsJson = dataset.derived_columns_json || {}
  const derivedDimensions = asRawFieldList(derivedColumnsJson.expressions)
    .map((item) => {
      const text = typeof item === "string" ? item.trim() : ""
      const name = text.split("=")[0]?.trim()
      if (!name) return null
      return {
        name,
        label: name,
        type: "derived",
        role: "dimension" as const,
        source: "dataset_derived" as const,
      }
    })
  return dedupeDatasetFields([
    ...asRawFieldList(fieldsJson.dimensions).map((field) => normalizeDatasetField(field, "dimension")),
    ...legacyDimensions.map((field) => normalizeDatasetField(field, "dimension")),
    ...asRawFieldList(semantic.dimensions).map((field) => normalizeDatasetField(field, "dimension")),
    ...asRawFieldList(semantic.time_dimensions).map((field) => normalizeDatasetField(field, "dimension")),
    ...derivedDimensions,
  ])
})

const metricPreviewDimensionOptions = computed(() => dimensionFieldOptions.value)

const metricFieldOptions = computed(() => {
  const dataset = currentDataset.value
  if (!dataset) return []
  const fieldsJson = dataset.fields_json || {}
  const aggregations = dataset.aggregations_json || {}
  const semantic = dataset.semantic_model_json || {}
  const legacyMetrics = asRawFieldList(fieldsJson.fields).filter((field) => {
    if (typeof field === "string") return false
    const role = String(field.role || field.semantic_type || "").toLowerCase()
    return role === "metric" || role === "measure"
  })
  return dedupeDatasetFields([
    ...asRawFieldList(fieldsJson.metrics).map((field) => normalizeDatasetField(field, "metric")),
    ...legacyMetrics.map((field) => normalizeDatasetField(field, "metric")),
    ...asRawFieldList(aggregations.aggregations).map((field) => normalizeDatasetField(field, "metric")),
    ...asRawFieldList(semantic.metrics).map((field) => normalizeDatasetField(field, "metric")),
    ...asRawFieldList(semantic.measures).map((field) => normalizeDatasetField(field, "metric")),
  ])
})

const datasetFieldOptions = computed(() => dedupeDatasetFields(metricFieldOptions.value))
const allDatasetFieldOptions = computed(() =>
  dedupeDatasetFields([...dimensionFieldOptions.value, ...metricFieldOptions.value])
)
const fieldOptionGroups = computed(() => [
  { label: "维度字段", options: dimensionFieldOptions.value },
  { label: "指标字段", options: metricFieldOptions.value },
].filter(group => group.options.length))
const metricFieldOptionGroups = computed(() => {
  if (!metricFieldOptions.value.length) return []
  return [{ label: "指标字段", options: metricFieldOptions.value }]
})
const isTimeLikeField = (field: DatasetFieldOption) => {
  const text = `${field.name} ${field.label} ${field.type}`.toLowerCase()
  return /(date|time|日期|时间|day|month|year|created|updated|biz_date)/.test(text)
}
const timeFieldOptions = computed(() => {
  const matches = datasetFieldOptions.value.filter(isTimeLikeField)
  return matches.length ? matches : datasetFieldOptions.value
})
const fieldCandidateFilterOptions = computed(() => [
  { label: "全部字段", value: "all" as const, count: allDatasetFieldOptions.value.length },
  { label: "维度", value: "dimension" as const, count: dimensionFieldOptions.value.length },
  { label: "指标", value: "metric" as const, count: metricFieldOptions.value.length },
])
const filteredCandidateFields = computed(() => {
  const keyword = fieldCandidateKeyword.value.trim().toLowerCase()
  const role = fieldCandidateRoleFilter.value
  return allDatasetFieldOptions.value.filter((field) => {
    const matchRole = role === "all" || field.role === role
    const text = `${field.name} ${field.label} ${field.type}`.toLowerCase()
    return matchRole && (!keyword || text.includes(keyword))
  })
})
const fieldInsertTargetOptions = computed<FieldInsertTargetOption[]>(() => {
  const autoOption: FieldInsertTargetOption = {
    label: "智能填充",
    value: "auto",
    helper: "按当前计算类型自动填入最合适的位置。",
  }
  const mode = form.value.calculation_config.calculation_mode

  if (mode === "aggregate") {
    return [
      autoOption,
      { label: "聚合字段", value: "metric_field", helper: "直接替换当前聚合字段。" },
    ]
  }
  if (mode === "ratio") {
    return [
      autoOption,
      { label: "分子字段", value: "numerator_field", helper: "作为比率计算的分子字段。" },
      { label: "分母字段", value: "denominator_field", helper: "作为比率计算的分母字段。" },
    ]
  }
  if (mode === "derived") {
    return [
      autoOption,
      { label: "左侧指标", value: "derived_left_field", helper: "作为派生运算左侧操作数。" },
      { label: "右侧指标", value: "derived_right_field", helper: "作为派生运算右侧操作数。" },
    ]
  }
  if (mode === "window") {
    return [
      autoOption,
      { label: "基础表达式", value: "metric_field", helper: "直接替换窗口函数的基础字段。" },
      { label: "分区字段", value: "partition_by", helper: "追加到 PARTITION BY 字段列表。" },
      { label: "排序字段", value: "order_by", helper: "追加到 ORDER BY 字段列表。" },
    ]
  }
  return [autoOption]
})
const fieldInsertHelper = computed(() => {
  return fieldInsertTargetOptions.value.find(item => item.value === fieldInsertTarget.value)?.helper || fieldInsertTargetOptions.value[0].helper
})
const fieldOptionLabel = (field: DatasetFieldOption) => {
  if (field.source === "trusted_metric") {
    return `${field.label}（已有可信指标）`
  }
  if (field.source === "dataset_derived") {
    return `${field.label}（派生列）`
  }
  return `${field.label}（${field.name}）`
}
const expressionToken = (fieldName: string, aggregation?: string) => {
  const fn = String(aggregation || "").toLowerCase()
  if (fn === "count_distinct") return `COUNT(DISTINCT ${fieldName})`
  if (["sum", "avg", "count", "max", "min"].includes(fn)) return `${fn.toUpperCase()}(${fieldName})`
  return fieldName
}
const trustedMetricReferenceKey = (metric: Metric) => `metric:${metric.id}`
const trustedMetricExpression = (metric: Metric) => {
  const formula = String(metric.formula || "").trim()
  if (formula) return formula
  const config = metric.calculation_config
  if (config?.derived_expression) return config.derived_expression.trim()
  if (config?.numerator_expression && config?.denominator_expression) {
    return `${config.numerator_expression} / NULLIF(${config.denominator_expression}, 0)`
  }
  if (config?.metric_field) {
    return expressionToken(config.metric_field, metric.aggregation || config.numerator_aggregation)
  }
  return expressionToken(String(metric.column_name || metric.name).trim(), metric.aggregation || "sum")
}
const fieldOptionDetail = (field: DatasetFieldOption) => {
  if (field.source === "trusted_metric") {
    return [field.datasetName || "可信指标", field.type].filter(Boolean).join(" · ")
  }
  if (field.source === "dataset_derived") {
    return `派生列 · ${field.name}`
  }
  return `${field.name} · ${field.type}`
}
const existingTrustedMetricOptions = computed<DatasetFieldOption[]>(() => {
  const datasetId = form.value.dataset_id
  if (!datasetId) return []
  return metrics.value
    .filter(metric => metric.id !== editingId.value)
    .filter(metric => metric.dataset_id === datasetId)
    .filter(metric => metric.is_active !== 0 && metric.status !== "archived")
    .map(metric => ({
      name: trustedMetricReferenceKey(metric),
      label: metric.name,
      type: metric.unit ? `可信指标 · ${metric.unit}` : "可信指标",
      role: "metric" as const,
      aggregation: undefined,
      expression: trustedMetricExpression(metric),
      source: "trusted_metric" as const,
      datasetName: datasets.value.find(item => item.id === metric.dataset_id)?.name || "当前数据集",
    }))
})
const derivedMetricOperandOptions = computed(() => dedupeDatasetFields([
  ...metricFieldOptions.value,
  ...existingTrustedMetricOptions.value,
]))
const derivedMetricOperandGroups = computed(() => [
  { label: "数据集指标", options: metricFieldOptions.value },
  { label: "已有可信指标", options: existingTrustedMetricOptions.value },
].filter(group => group.options.length))
const appendToken = (value: string, token: string) => {
  const trimmed = value.trim()
  return trimmed ? `${trimmed} ${token}` : token
}
const appendListToken = (value: string, token: string) => {
  const trimmed = value.trim()
  return trimmed ? `${trimmed}, ${token}` : token
}
const expressionAggregationForField = (field: DatasetFieldOption) => {
  return field.role === "metric" ? field.aggregation || "sum" : undefined
}
const findDatasetField = (fieldName: string) => {
  const normalized = fieldName.trim()
  return datasetFieldOptions.value.find(field => field.name === normalized) || null
}
const findMetricOperand = (fieldName: string) => {
  const normalized = fieldName.trim()
  if (!normalized) return null
  return derivedMetricOperandOptions.value.find(field => field.name === normalized) || null
}
const controlledMetricExpression = (fieldName: string, aggregation?: string) => {
  const normalizedField = fieldName.trim()
  if (!normalizedField) return ""
  const field = findMetricOperand(normalizedField) || findDatasetField(normalizedField)
  if (field?.source === "trusted_metric" && field.expression) return field.expression
  const normalizedAggregation = aggregation || field?.aggregation || "sum"
  return expressionToken(normalizedField, normalizedAggregation)
}
const wrapDerivedMetricExpression = (expression: string) => {
  const trimmed = expression.trim()
  return trimmed ? `(${trimmed})` : ""
}
const buildDerivedExpression = (config = form.value.calculation_config) => {
  const left = wrapDerivedMetricExpression(controlledMetricExpression(config.derived_left_field))
  const right = wrapDerivedMetricExpression(controlledMetricExpression(config.derived_right_field))
  const operator = derivedOperatorOptions.some(item => item.value === config.derived_operator) ? config.derived_operator : "/"
  if (!left || !right) return ""
  if (operator === "/") return `${left} / NULLIF(${right}, 0)`
  return `${left} ${operator} ${right}`
}
const derivedDependencyText = computed(() => {
  const config = form.value.calculation_config
  const fields = [config.derived_left_field, config.derived_right_field]
    .map(fieldName => findMetricOperand(fieldName))
    .filter((field): field is DatasetFieldOption => Boolean(field))
  return fields.map(field => field.label || field.name).join(" / ")
})
const appendExpressionField = (target: ExpressionTarget, fieldName: string, aggregation?: string) => {
  const token = expressionToken(fieldName, aggregation)
  form.value.calculation_config[target] = appendToken(form.value.calculation_config[target], token)
}
const setPrimaryField = (field: DatasetFieldOption) => {
  form.value.calculation_config.metric_field = field.name
  if (!form.value.column_name) {
    form.value.column_name = fieldSimpleName(field.name)
  }
}
const setRatioOperand = (target: "numerator" | "denominator", field: DatasetFieldOption) => {
  const config = form.value.calculation_config
  const aggregation = expressionAggregationForField(field) || (target === "numerator" ? config.numerator_aggregation : config.denominator_aggregation)
  if (target === "numerator") {
    config.numerator_field = field.name
    config.numerator_aggregation = aggregation || "sum"
  } else {
    config.denominator_field = field.name
    config.denominator_aggregation = aggregation || "sum"
  }
}
const setDerivedOperand = (target: "left" | "right", field: DatasetFieldOption) => {
  if (target === "left") {
    form.value.calculation_config.derived_left_field = field.name
  } else {
    form.value.calculation_config.derived_right_field = field.name
  }
}
const pickCandidateField = (field: DatasetFieldOption) => {
  const config = form.value.calculation_config
  if (config.calculation_mode === "aggregate" || config.calculation_mode === "window") {
    setPrimaryField(field)
    return
  }
  if (config.calculation_mode === "ratio") {
    if (!config.numerator_field.trim()) {
      setRatioOperand("numerator", field)
    } else if (!config.denominator_field.trim()) {
      setRatioOperand("denominator", field)
    } else {
      setRatioOperand("numerator", field)
    }
    return
  }
  if (config.calculation_mode === "derived") {
    if (!config.derived_left_field.trim()) {
      setDerivedOperand("left", field)
    } else if (!config.derived_right_field.trim()) {
      setDerivedOperand("right", field)
    } else {
      setDerivedOperand("left", field)
    }
    return
  }
}
const insertCandidateField = (field: DatasetFieldOption) => {
  const config = form.value.calculation_config
  const target = fieldInsertTarget.value
  if (target === "auto") {
    pickCandidateField(field)
    return
  }
  if (target === "metric_field") {
    setPrimaryField(field)
    return
  }
  if (target === "numerator_field") {
    setRatioOperand("numerator", field)
    return
  }
  if (target === "denominator_field") {
    setRatioOperand("denominator", field)
    return
  }
  if (target === "derived_left_field") {
    setDerivedOperand("left", field)
    return
  }
  if (target === "derived_right_field") {
    setDerivedOperand("right", field)
    return
  }
  if (target === "partition_by") {
    config.partition_by = appendListToken(config.partition_by, field.name)
    return
  }
  if (target === "order_by") {
    config.order_by = appendListToken(config.order_by, field.name)
    return
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

const lineageCalculationConfig = computed(() => lineage.value?.metric.calculation_config || null)

const lineageCalculationItems = computed(() => {
  const config = lineageCalculationConfig.value
  if (!config) return []
  const modeSpecificItems: Array<{ label: string; value: string | number | null | undefined }> = []
  if (config.calculation_mode === "aggregate") {
    modeSpecificItems.push(
      { label: "聚合字段", value: config.metric_field },
    )
  }
  if (config.calculation_mode === "ratio") {
    modeSpecificItems.push(
      { label: "分子字段", value: config.numerator_field },
      { label: "分子聚合", value: config.numerator_aggregation },
      { label: "分母字段", value: config.denominator_field },
      { label: "分母聚合", value: config.denominator_aggregation },
      { label: "小数精度", value: config.decimal_precision },
    )
  }
  if (config.calculation_mode === "derived") {
    modeSpecificItems.push(
      { label: "左侧指标", value: config.derived_left_field },
      { label: "派生运算", value: config.derived_operator },
      { label: "右侧指标", value: config.derived_right_field },
      { label: "依赖指标", value: config.dependency_metrics },
      { label: "输出别名", value: config.output_alias },
    )
  }
  if (config.calculation_mode === "window") {
    modeSpecificItems.push(
      { label: "基础表达式", value: config.metric_field },
      { label: "窗口函数", value: config.window_function },
      { label: "分区字段", value: config.partition_by },
      { label: "排序字段", value: config.order_by },
      { label: "排序方向", value: config.order_direction },
      { label: "窗口范围", value: config.window_frame },
    )
  }
  return [
    { label: "计算类型", value: calculationModeLabel(config.calculation_mode) },
    ...modeSpecificItems,
    { label: "统计周期", value: config.statistical_window },
    { label: "时间粒度", value: config.time_grain },
    { label: "时间字段", value: config.time_field },
    { label: "刷新 SLA", value: config.refresh_sla },
  ].filter(item => item.value)
})

const lineageFilterRules = computed(() => {
  const filters = lineageCalculationConfig.value?.filters || []
  return filters
    .filter(rule => rule.field)
    .map((rule, index) => `${index === 0 ? "" : `${rule.logic} `}${rule.field} ${rule.operator} ${rule.value}`.trim())
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

const formatPreviewCell = (value: unknown) => {
  if (value === null || value === undefined || value === "") return "—"
  if (typeof value === "number") {
    return Number.isInteger(value) ? String(value) : String(Number(value.toFixed(4)))
  }
  return String(value)
}

const metricPreviewStatusText = computed(() => {
  if (!editingId.value) return "保存指标后可预览"
  if (metricPreviewLoading.value) return "正在读取最新数据"
  if (metricPreviewError.value) return "预览失败"
  if (metricPreviewColumns.value.length) return `${metricPreviewRowCount.value} 行`
  return "待预览"
})

const resetMetricPreview = () => {
  metricPreviewDimensions.value = []
  metricPreviewColumns.value = []
  metricPreviewRows.value = []
  metricPreviewError.value = ""
  metricPreviewRowCount.value = 0
  metricPreviewSql.value = ""
}

const fetchMetricPreview = async () => {
  if (!editingId.value) {
    resetMetricPreview()
    return
  }
  metricPreviewLoading.value = true
  metricPreviewError.value = ""
  try {
    const response = await axios.post<MetricPreviewResult>(`/api/metrics/${editingId.value}/preview`, {
      dimensions: metricPreviewDimensions.value,
      limit: 50,
    })
    metricPreviewColumns.value = response.data.columns || []
    metricPreviewRows.value = response.data.rows || []
    metricPreviewRowCount.value = response.data.row_count || metricPreviewRows.value.length
    metricPreviewSql.value = response.data.query?.sql || ""
  } catch (error: any) {
    metricPreviewColumns.value = []
    metricPreviewRows.value = []
    metricPreviewRowCount.value = 0
    metricPreviewSql.value = ""
    metricPreviewError.value = error.response?.data?.detail || "实时数据预览失败"
  } finally {
    metricPreviewLoading.value = false
  }
}

const copyMetricPreviewSql = async () => {
  try {
    await navigator.clipboard.writeText(metricPreviewSql.value)
    ElMessage.success("SQL 已复制")
  } catch {
    ElMessage.error("复制失败")
  }
}

const selectedFormulaCandidate = computed(() => {
  return formulaCandidates.value.find(candidate => candidate.id === selectedFormulaCandidateId.value) || null
})

const trustScore = (metric: Metric) => {
  let score = 20
  if (metric.definition) score += 15
  if (metric.formula) score += 20
  if (metric.calculation_config?.statistical_window) score += 5
  if (metric.calculation_config?.filters?.some(rule => rule.field)) score += 5
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

const normalizeCalculationConfig = (value?: Partial<CalculationConfig> | null): CalculationConfig => {
  const base = defaultCalculationConfig()
  const config = (value && typeof value === "object" ? value : {}) as Partial<CalculationConfig>
  const filters: CalculationFilterRule[] = Array.isArray(config.filters)
    ? config.filters
        .map((rule): CalculationFilterRule => {
          const logic: CalculationFilterRule["logic"] = rule.logic === "OR" ? "OR" : "AND"
          return {
            logic,
            field: String(rule.field || "").trim(),
            operator: String(rule.operator || "=").trim() || "=",
            value: String(rule.value || "").trim(),
          }
        })
        .filter(rule => rule.field || rule.value)
    : []
  return {
    ...base,
    ...config,
    calculation_mode: normalizeCalculationMode(config.calculation_mode),
    metric_field: String(config.metric_field || "").trim(),
    numerator_field: String(config.numerator_field || "").trim(),
    numerator_aggregation: String(config.numerator_aggregation || base.numerator_aggregation).trim() || base.numerator_aggregation,
    numerator_expression: String(config.numerator_expression || "").trim(),
    denominator_field: String(config.denominator_field || "").trim(),
    denominator_aggregation: String(config.denominator_aggregation || base.denominator_aggregation).trim() || base.denominator_aggregation,
    denominator_expression: String(config.denominator_expression || "").trim(),
    derived_left_field: String(config.derived_left_field || "").trim(),
    derived_operator: derivedOperatorOptions.some(item => item.value === config.derived_operator) ? String(config.derived_operator) : base.derived_operator,
    derived_right_field: String(config.derived_right_field || "").trim(),
    derived_expression: String(config.derived_expression || "").trim(),
    dependency_metrics: String(config.dependency_metrics || "").trim(),
    window_function: String(config.window_function || base.window_function).trim() || base.window_function,
    partition_by: String(config.partition_by || "").trim(),
    order_by: String(config.order_by || "").trim(),
    order_direction: String(config.order_direction || base.order_direction).toUpperCase() === "DESC" ? "DESC" : "ASC",
    window_frame: String(config.window_frame || base.window_frame).trim() || base.window_frame,
    custom_sql: String(config.custom_sql || "").trim(),
    output_alias: String(config.output_alias || "").trim(),
    filters: filters.length ? filters : [emptyCalculationFilter()],
    decimal_precision:
      config.decimal_precision === null || config.decimal_precision === undefined
        ? base.decimal_precision
        : Number(config.decimal_precision),
  }
}

const isCalculationMode = (mode: CalculationMode) => form.value.calculation_config.calculation_mode === mode

const currentCalculationModeMeta = computed(() => {
  return calculationModeOptions.find(item => item.value === form.value.calculation_config.calculation_mode) || calculationModeOptions[0]
})

const calculationModeLabel = (mode?: string | null) => {
  return calculationModeOptions.find(item => item.value === mode)?.label || "聚合指标"
}

const setCalculationMode = (mode: CalculationMode) => {
  form.value.calculation_config.calculation_mode = mode
  fieldInsertTarget.value = "auto"
  const defaultAggregationByMode: Record<CalculationMode, string> = {
    aggregate: form.value.aggregation === "ratio" || form.value.aggregation === "custom" ? "sum" : form.value.aggregation,
    ratio: "ratio",
    derived: "custom",
    window: "custom",
  }
  form.value.aggregation = defaultAggregationByMode[mode]
}

const buildAggregationExpression = (aggregation: string, field: string, dedupKey = "") => {
  const normalizedAggregation = String(aggregation || "sum").toLowerCase()
  const metricField = field.trim()
  const distinctKey = dedupKey.trim() || metricField
  const alreadyAggregated = /\b(sum|avg|count|max|min)\s*\(/i.test(metricField)

  if (normalizedAggregation === "count_distinct") {
    return distinctKey ? `COUNT(DISTINCT ${distinctKey})` : ""
  }
  if (normalizedAggregation === "count") {
    return metricField ? `COUNT(${metricField})` : "COUNT(*)"
  }
  if (["sum", "avg", "max", "min"].includes(normalizedAggregation)) {
    if (!metricField) return ""
    return alreadyAggregated ? metricField : `${normalizedAggregation.toUpperCase()}(${metricField})`
  }
  return metricField
}

const buildWindowOverClause = (includeFrame = true) => {
  const config = form.value.calculation_config
  const partitionBy = config.partition_by.trim()
  const orderBy = config.order_by.trim()
  const orderDirection = config.order_direction === "DESC" ? "DESC" : "ASC"
  const orderByExpression = orderBy && /\b(ASC|DESC)\b/i.test(orderBy) ? orderBy : orderBy ? `${orderBy} ${orderDirection}` : ""
  const windowFrame = config.window_frame.trim()
  const parts = [
    partitionBy ? `PARTITION BY ${partitionBy}` : "",
    orderByExpression ? `ORDER BY ${orderByExpression}` : "",
    includeFrame && orderByExpression && windowFrame ? windowFrame : "",
  ].filter(Boolean)
  return parts.length ? `OVER (${parts.join(" ")})` : ""
}

const formulaPreview = computed(() => {
  const config = form.value.calculation_config
  if (config.calculation_mode === "aggregate") {
    return buildAggregationExpression(form.value.aggregation, config.metric_field)
  }
  if (config.calculation_mode === "ratio") {
    const numerator = controlledMetricExpression(config.numerator_field, config.numerator_aggregation)
    const denominator = controlledMetricExpression(config.denominator_field, config.denominator_aggregation)
    if (!numerator || !denominator) return ""
    const ratioExpression = `${numerator} / NULLIF(${denominator}, 0)`
    if (config.decimal_precision === null || config.decimal_precision === undefined) return ratioExpression
    return `ROUND(${ratioExpression}, ${config.decimal_precision})`
  }
  if (config.calculation_mode === "derived") {
    return buildDerivedExpression(config)
  }
  if (config.calculation_mode === "window") {
    const baseField = config.metric_field.trim()
    const functionName = config.window_function
    const includeFrame = !["rank", "dense_rank", "row_number"].includes(functionName)
    const overClause = buildWindowOverClause(includeFrame)
    if (!overClause) return ""

    if (functionName === "rank") return `RANK() ${overClause}`
    if (functionName === "dense_rank") return `DENSE_RANK() ${overClause}`
    if (functionName === "row_number") return `ROW_NUMBER() ${overClause}`
    if (!baseField) return ""
    if (functionName === "avg_over") return `AVG(${baseField}) ${overClause}`
    if (functionName === "lag") return `LAG(${baseField}) ${overClause}`
    if (functionName === "lead") return `LEAD(${baseField}) ${overClause}`
    return `SUM(${baseField}) ${overClause}`
  }
  return ""
})

const effectiveFormula = computed(() => formulaPreview.value.trim())

const formulaPreviewStatus = computed(() => {
  if (formulaPreview.value) return "根据当前配置实时生成，可一键应用"

  const config = form.value.calculation_config
  if (!form.value.dataset_id) return "先选择数据集，再从字段候选项中快速填充"
  if (config.calculation_mode === "aggregate" && form.value.aggregation !== "count") return "请选择聚合字段"
  if (config.calculation_mode === "ratio") return "请补齐分子字段和分母字段"
  if (config.calculation_mode === "derived") return "请选择左右指标并通过按钮确定派生运算"
  if (config.calculation_mode === "window") return "请选择基础字段，并至少配置分区或排序字段"
  return "补齐必要配置后自动生成"
})

const isCalculationModelConfigured = computed(() => {
  const config = form.value.calculation_config
  if (config.calculation_mode === "aggregate") {
    return Boolean(config.metric_field.trim() || form.value.column_name.trim())
  }
  if (config.calculation_mode === "ratio") {
    return Boolean(config.numerator_field.trim() && config.denominator_field.trim())
  }
  if (config.calculation_mode === "derived") {
    return Boolean(config.derived_left_field.trim() && config.derived_operator && config.derived_right_field.trim())
  }
  if (config.calculation_mode === "window") {
    return Boolean(config.metric_field.trim() && config.window_function && config.order_by.trim())
  }
  return false
})

const caliberChecklist = computed(() => [
  { label: "业务定义", done: Boolean(form.value.definition.trim()) },
  { label: "计算配置", done: isCalculationModelConfigured.value },
  { label: "统计范围", done: Boolean(form.value.calculation_config.statistical_window && form.value.calculation_config.time_grain) },
  { label: "过滤规则", done: form.value.calculation_config.filters.some(rule => Boolean(rule.field.trim())) },
])

const caliberCompleteness = computed(() => {
  const done = caliberChecklist.value.filter(item => item.done).length
  return Math.round((done / caliberChecklist.value.length) * 100)
})

const addCalculationFilter = () => {
  form.value.calculation_config.filters.push(emptyCalculationFilter())
}

const removeCalculationFilter = (index: number) => {
  form.value.calculation_config.filters.splice(index, 1)
  if (!form.value.calculation_config.filters.length) {
    form.value.calculation_config.filters.push(emptyCalculationFilter())
  }
}

const buildPayload = () => {
  const calculationConfig = normalizeCalculationConfig(form.value.calculation_config)
  ;["null_handling", "dedup_key", "denominator_zero_policy", "exception_handling", "validation_rule"].forEach((key) => {
    delete (calculationConfig as unknown as Record<string, unknown>)[key]
  })
  calculationConfig.custom_sql = ""
  calculationConfig.numerator_expression = controlledMetricExpression(calculationConfig.numerator_field, calculationConfig.numerator_aggregation)
  calculationConfig.denominator_expression = controlledMetricExpression(calculationConfig.denominator_field, calculationConfig.denominator_aggregation)
  calculationConfig.derived_expression = buildDerivedExpression(calculationConfig)
  if (calculationConfig.calculation_mode === "derived") {
    calculationConfig.dependency_metrics = [calculationConfig.derived_left_field, calculationConfig.derived_right_field]
      .map(fieldName => findMetricOperand(fieldName)?.label || fieldName)
      .filter(Boolean)
      .join(", ")
  }
  const generatedFormula = formulaPreview.value.trim()
  const outputColumn =
    form.value.column_name ||
    calculationConfig.output_alias ||
    calculationConfig.metric_field ||
    null

  return {
    dataset_id: form.value.dataset_id,
    name: form.value.name,
    description: form.value.description || null,
    definition: form.value.definition,
    column_name: outputColumn,
    formula: generatedFormula || null,
    calculation_config: calculationConfig,
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
  }
}

const openDialog = (metric?: Metric) => {
  dialogActiveTab.value = "basic"
  fieldInsertTarget.value = "auto"
  resetMetricPreview()
  if (metric) {
    editingId.value = metric.id
    form.value = {
      dataset_id: metric.dataset_id,
      name: metric.name || "",
      description: metric.description || "",
      definition: metric.definition || "",
      column_name: metric.column_name || "",
      formula: metric.formula || "",
      calculation_config: normalizeCalculationConfig(metric.calculation_config),
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
    nextTick(fetchMetricPreview)
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

const openFormulaAssistant = () => {
  if (!form.value.dataset_id || !form.value.name) {
    ElMessage.warning("请先选择数据集并填写指标名称")
    return
  }
  formulaAssistantPrompt.value = form.value.definition || form.value.description || ""
  formulaAssistantFeedback.value = ""
  formulaAssistantMessages.value = []
  formulaCandidates.value = []
  selectedFormulaCandidateId.value = null
  formulaCandidateCounter.value = 0
  formulaAssistantVisible.value = true
}

const buildFormulaAssistantPayload = (feedback = "") => {
  const availableFields = form.value.calculation_config.calculation_mode === "derived"
    ? derivedMetricOperandOptions.value
    : datasetFieldOptions.value
  const fieldContext = availableFields
    .map(field => `${field.source === "trusted_metric" ? "已有可信指标" : "指标"}：${field.label}(${field.name}, ${field.type})`)
    .join("\n")
  const candidateContext = formulaCandidates.value
    .map(candidate => `候选公式 #${candidate.id}: ${candidate.formula}${candidate.feedback ? `\n用户反馈：${candidate.feedback}` : ""}`)
    .join("\n")
  const assistantDefinition = [
    `指标名称：${form.value.name}`,
    form.value.definition ? `现有指标定义：${form.value.definition}` : "",
    form.value.description ? `指标描述：${form.value.description}` : "",
    `计算类型：${currentCalculationModeMeta.value.label}`,
    `自然语言描述：${formulaAssistantPrompt.value.trim()}`,
    fieldContext ? `可用字段：\n${fieldContext}` : "",
    candidateContext ? `历史候选：\n${candidateContext}` : "",
    feedback ? `本轮修正要求：${feedback}` : "",
    "请只返回一个可执行的公式文本，不要解释。",
  ].filter(Boolean).join("\n\n")

  return {
    ...buildPayload(),
    definition: assistantDefinition,
    formula: null,
  }
}

const addFormulaCandidate = (formula: string) => {
  const candidate: FormulaCandidate = {
    id: formulaCandidateCounter.value + 1,
    formula,
    status: "candidate",
  }
  formulaCandidateCounter.value = candidate.id
  formulaCandidates.value.unshift(candidate)
  selectedFormulaCandidateId.value = candidate.id
  formulaAssistantMessages.value.push({
    role: "assistant",
    content: `候选公式 #${candidate.id}：${formula}`,
  })
}

const requestFormulaCandidate = async (feedback = "") => {
  const prompt = formulaAssistantPrompt.value.trim()
  if (!form.value.dataset_id || !form.value.name || !prompt) {
    ElMessage.warning("请先选择数据集、填写指标名称和自然语言描述")
    return
  }
  generatingFormula.value = true
  try {
    const response = await axios.post("/api/metrics/generate-formula", buildFormulaAssistantPayload(feedback))
    const formula = String(response.data.formula || "").trim()
    if (!formula) {
      ElMessage.warning("未生成有效公式")
      return
    }
    addFormulaCandidate(formula)
    ElMessage.success("已生成候选公式")
  } catch (error: any) {
    ElMessage.error(error.response?.data?.detail || "生成公式失败")
  } finally {
    generatingFormula.value = false
  }
}

const generateFormulaCandidate = async () => {
  const prompt = formulaAssistantPrompt.value.trim()
  if (prompt) {
    formulaAssistantMessages.value.push({ role: "user", content: prompt })
  }
  await requestFormulaCandidate()
}

const refineFormulaCandidate = async () => {
  const feedback = formulaAssistantFeedback.value.trim()
  if (!feedback) {
    ElMessage.warning("请填写修正反馈")
    return
  }
  const selected = selectedFormulaCandidate.value
  if (selected) {
    selected.status = "rejected"
    selected.feedback = feedback
  }
  formulaAssistantMessages.value.push({ role: "user", content: feedback })
  formulaAssistantFeedback.value = ""
  await requestFormulaCandidate(feedback)
}

const escapeRegExp = (value: string) => value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")
const extractFormulaOperands = (formula: string) => {
  const operands: Array<{ field: string; aggregation: string }> = []
  const tokenPattern = /COUNT\s*\(\s*DISTINCT\s+([^)]+)\s*\)|\b(SUM|AVG|COUNT|MAX|MIN)\s*\(\s*([^)]+)\s*\)/gi
  let match = tokenPattern.exec(formula)
  while (match) {
    operands.push({
      field: String(match[1] || match[3] || "").trim(),
      aggregation: match[1] ? "count_distinct" : String(match[2] || "sum").toLowerCase(),
    })
    match = tokenPattern.exec(formula)
  }
  if (operands.length) return operands

  const operandPool = form.value.calculation_config.calculation_mode === "derived"
    ? derivedMetricOperandOptions.value
    : datasetFieldOptions.value
  return operandPool
    .filter((field) => {
      const pattern = new RegExp(`(^|[^\\w.])${escapeRegExp(field.name)}([^\\w.]|$)`, "i")
      return pattern.test(formula)
    })
    .map(field => ({ field: field.name, aggregation: field.aggregation || "sum" }))
}

const applyFormulaToGraphicalConfig = (formula: string) => {
  const config = form.value.calculation_config
  const operands = extractFormulaOperands(formula)
  if (config.calculation_mode === "aggregate") {
    const operand = operands[0]
    if (!operand) return false
    config.metric_field = operand.field
    form.value.aggregation = operand.aggregation
    return true
  }
  if (config.calculation_mode === "ratio") {
    if (operands.length < 2) return false
    config.numerator_field = operands[0].field
    config.numerator_aggregation = operands[0].aggregation
    config.denominator_field = operands[1].field
    config.denominator_aggregation = operands[1].aggregation
    const precision = formula.match(/\bROUND\s*\([\s\S]+,\s*(\d+)\s*\)\s*$/i)?.[1]
    if (precision) config.decimal_precision = Number(precision)
    return true
  }
  if (config.calculation_mode === "derived") {
    if (operands.length < 2) return false
    config.derived_left_field = operands[0].field
    config.derived_right_field = operands[1].field
    if (formula.includes("/")) config.derived_operator = "/"
    else if (formula.includes("*")) config.derived_operator = "*"
    else if (formula.includes("+")) config.derived_operator = "+"
    else if (/\s-\s/.test(formula)) config.derived_operator = "-"
    return true
  }
  if (config.calculation_mode === "window") {
    if (/\bRANK\s*\(/i.test(formula)) config.window_function = "rank"
    else if (/\bDENSE_RANK\s*\(/i.test(formula)) config.window_function = "dense_rank"
    else if (/\bROW_NUMBER\s*\(/i.test(formula)) config.window_function = "row_number"
    else if (/\bAVG\s*\(/i.test(formula)) config.window_function = "avg_over"
    else if (/\bLAG\s*\(/i.test(formula)) config.window_function = "lag"
    else if (/\bLEAD\s*\(/i.test(formula)) config.window_function = "lead"
    else config.window_function = "sum_over"
    if (operands[0]) config.metric_field = operands[0].field
    return Boolean(config.order_by.trim() || /\bOVER\s*\(/i.test(formula))
  }
  return false
}

const applyGeneratedFormula = (formula: string) => {
  const preview = formulaPreview.value.trim()
  if (preview && formula.trim() === preview) {
    form.value.formula = preview
    return true
  }
  const applied = applyFormulaToGraphicalConfig(formula)
  if (applied) {
    form.value.formula = formulaPreview.value.trim()
  }
  return applied
}

const applyFormulaPreview = () => {
  const preview = formulaPreview.value.trim()
  if (!preview) {
    ElMessage.warning("暂无可应用的公式预览")
    return
  }
  if (!applyGeneratedFormula(preview)) {
    ElMessage.warning("公式预览无法映射为图形化配置")
    return
  }
  ElMessage.success("已应用预览公式")
}

const applyFormulaCandidate = (candidate?: FormulaCandidate) => {
  const target = candidate || selectedFormulaCandidate.value
  if (!target) {
    ElMessage.warning("请选择候选公式")
    return
  }
  if (!applyGeneratedFormula(target.formula)) {
    ElMessage.warning("候选公式无法安全映射为图形化配置，请使用字段选择器和运算按钮配置")
    return
  }
  target.status = "applied"
  selectedFormulaCandidateId.value = target.id
  formulaAssistantVisible.value = false
  ElMessage.success("已应用候选公式")
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

.enterprise-caliber-workbench {
  gap: 14px;
}

.formula-assistant {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.formula-assistant-prompt,
.formula-assistant-thread,
.formula-assistant-candidates {
  min-width: 0;
  padding: 14px;
  border: 1px solid var(--app-border);
  border-radius: var(--app-radius-sm);
  background: var(--app-surface);
}

.formula-assistant-context {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-bottom: 12px;
}

.formula-assistant-context span {
  display: inline-flex;
  align-items: center;
  min-height: 26px;
  padding: 0 9px;
  border: 1px solid rgba(15, 118, 110, 0.18);
  border-radius: 999px;
  color: var(--app-primary);
  background: rgba(15, 118, 110, 0.07);
  font-size: 12px;
  font-weight: 700;
}

.formula-assistant-grid {
  display: grid;
  grid-template-columns: minmax(0, 0.95fr) minmax(0, 1.05fr);
  gap: 14px;
}

.formula-assistant-section-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  margin-bottom: 10px;
}

.formula-assistant-section-head strong {
  color: var(--app-text);
  font-size: 14px;
  line-height: 1.4;
}

.formula-assistant-section-head span {
  color: var(--app-text-muted);
  font-size: 12px;
}

.formula-assistant-messages {
  display: flex;
  flex-direction: column;
  gap: 8px;
  min-height: 146px;
  max-height: 260px;
  margin-bottom: 10px;
  overflow: auto;
}

.formula-assistant-message {
  display: grid;
  grid-template-columns: 36px minmax(0, 1fr);
  gap: 8px;
  align-items: flex-start;
}

.formula-assistant-message span {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  min-height: 24px;
  border-radius: 999px;
  background: var(--app-surface-muted);
  color: var(--app-text-muted);
  font-size: 12px;
  font-weight: 700;
}

.formula-assistant-message p {
  margin: 0;
  padding: 8px 10px;
  border-radius: 8px;
  background: var(--app-surface-muted);
  color: var(--app-text);
  font-size: 13px;
  line-height: 1.55;
  white-space: pre-wrap;
  word-break: break-word;
}

.formula-assistant-message.is-assistant p {
  background: rgba(15, 118, 110, 0.07);
}

.formula-assistant-empty {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 96px;
  border: 1px dashed var(--app-border);
  border-radius: var(--app-radius-sm);
  color: var(--app-text-muted);
  background: var(--app-surface-muted);
  font-size: 13px;
}

.formula-assistant-actions,
.formula-candidate-card__actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  margin-top: 10px;
}

.formula-assistant-candidates {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.formula-candidate-card {
  min-width: 0;
  padding: 12px;
  border: 1px solid var(--app-border);
  border-radius: var(--app-radius-sm);
  background: var(--app-surface);
  cursor: pointer;
  transition: border-color 0.15s ease, background 0.15s ease, box-shadow 0.15s ease;
}

.formula-candidate-card:hover,
.formula-candidate-card.is-selected {
  border-color: rgba(15, 118, 110, 0.34);
  background: rgba(15, 118, 110, 0.045);
}

.formula-candidate-card.is-selected {
  box-shadow: inset 0 0 0 1px rgba(15, 118, 110, 0.16);
}

.formula-candidate-card__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  margin-bottom: 8px;
}

.formula-candidate-card__head strong {
  color: var(--app-text);
  font-size: 13px;
}

.formula-candidate-card pre {
  margin: 0;
  padding: 10px 12px;
  border-radius: 8px;
  background: #0f172a;
  color: #7dd3fc;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
  font-size: 12px;
  line-height: 1.6;
  white-space: pre-wrap;
  word-break: break-all;
}

.formula-candidate-card p {
  margin: 8px 0 0;
  color: var(--app-text-muted);
  font-size: 12px;
  line-height: 1.5;
}

.caliber-overview {
  display: grid;
  grid-template-columns: minmax(180px, 240px) minmax(0, 1fr) auto;
  align-items: center;
  gap: 12px;
  padding: 12px;
  border: 1px solid rgba(15, 118, 110, 0.18);
  border-radius: var(--app-radius-sm);
  background: linear-gradient(180deg, rgba(15, 118, 110, 0.055), rgba(15, 118, 110, 0)), var(--app-surface);
}

.caliber-overview-main {
  display: grid;
  grid-template-columns: auto 1fr;
  align-items: center;
  gap: 6px 10px;
  min-width: 0;
}

.caliber-overview-main span {
  color: var(--app-text-muted);
  font-size: 12px;
  font-weight: 700;
}

.caliber-overview-main strong {
  color: var(--app-primary);
  font-size: 20px;
  line-height: 1;
  font-variant-numeric: tabular-nums;
}

.caliber-overview-main :deep(.el-progress) {
  grid-column: 1 / -1;
}

.caliber-checklist {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
  min-width: 0;
}

.caliber-check-item {
  display: inline-flex;
  align-items: center;
  min-height: 26px;
  padding: 0 9px;
  border: 1px solid var(--app-border);
  border-radius: 999px;
  color: var(--app-text-muted);
  background: var(--app-surface);
  font-size: 12px;
  font-weight: 700;
}

.caliber-check-item.is-done {
  border-color: rgba(15, 118, 110, 0.22);
  color: var(--app-primary);
  background: rgba(15, 118, 110, 0.08);
}

.caliber-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
}

.caliber-panel {
  min-width: 0;
  padding: 14px;
  border: 1px solid var(--app-border);
  border-radius: var(--app-radius-sm);
  background: var(--app-surface);
}

.caliber-panel-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
}

.caliber-panel-head strong,
.caliber-panel-head span {
  display: block;
}

.caliber-panel-head strong {
  color: var(--app-text);
  font-size: 14px;
  line-height: 1.4;
}

.caliber-panel-head span {
  margin-top: 3px;
  color: var(--app-text-muted);
  font-size: 12px;
  line-height: 1.45;
}

.caliber-panel-head.with-action {
  align-items: center;
}

.calculation-mode-switcher {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(132px, 1fr));
  gap: 8px;
  margin-bottom: 10px;
}

.calculation-mode-card {
  display: grid;
  grid-template-columns: 28px minmax(0, 1fr);
  align-items: center;
  gap: 8px;
  min-width: 0;
  min-height: 58px;
  padding: 9px 10px;
  border: 1px solid var(--app-border);
  border-radius: var(--app-radius-sm);
  background: var(--app-surface);
  color: var(--app-text);
  text-align: left;
  cursor: pointer;
  transition: border-color 0.15s ease, background 0.15s ease, box-shadow 0.15s ease;
}

.calculation-mode-card:hover,
.calculation-mode-card.is-active {
  border-color: rgba(15, 118, 110, 0.34);
  background: rgba(15, 118, 110, 0.06);
}

.calculation-mode-card.is-active {
  box-shadow: inset 0 0 0 1px rgba(15, 118, 110, 0.18);
}

.calculation-mode-card .el-icon {
  width: 28px;
  height: 28px;
  border-radius: 8px;
  background: var(--app-surface-muted);
  color: var(--app-primary);
}

.calculation-mode-card span,
.calculation-mode-card strong,
.calculation-mode-card small {
  display: block;
  min-width: 0;
}

.calculation-mode-card strong {
  color: var(--app-text);
  font-size: 12px;
  line-height: 1.35;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.calculation-mode-card small {
  margin-top: 2px;
  color: var(--app-text-muted);
  font-size: 11px;
  line-height: 1.35;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.calculation-mode-current {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
  padding: 9px 12px;
  border-radius: var(--app-radius-sm);
  background: var(--app-surface-muted);
}

.calculation-mode-current strong {
  flex: 0 0 auto;
  color: var(--app-primary);
  font-size: 13px;
  line-height: 1.4;
}

.calculation-mode-current span {
  min-width: 0;
  color: var(--app-text-muted);
  font-size: 12px;
  line-height: 1.45;
}

.mode-config-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 4px 12px;
}

.mode-config-grid__wide {
  grid-column: 1 / -1;
}

.structured-caliber-builder {
  align-items: start;
}

.metric-operand-picker,
.derived-builder {
  display: grid;
  grid-template-columns: minmax(120px, 150px) minmax(0, 1fr);
  align-items: center;
  gap: 8px;
  width: 100%;
}

.operand-aggregation-select {
  width: 100%;
}

.derived-builder {
  grid-template-columns: minmax(0, 1fr) auto minmax(0, 1fr);
}

.derived-operator-group {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 3px;
  border: 1px solid var(--app-border);
  border-radius: 9px;
  background: var(--app-surface-muted);
}

.derived-operator-button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 30px;
  min-height: 30px;
  border: 0;
  border-radius: 7px;
  background: transparent;
  color: var(--app-text-muted);
  font-size: 14px;
  font-weight: 800;
  cursor: pointer;
  transition: color 0.15s ease, background 0.15s ease, box-shadow 0.15s ease;
}

.derived-operator-button:hover,
.derived-operator-button.is-active {
  color: var(--app-primary);
  background: rgba(15, 118, 110, 0.08);
  box-shadow: inset 0 0 0 1px rgba(15, 118, 110, 0.18);
}

.builder-hint {
  display: block;
  margin-top: 6px;
  color: var(--app-text-muted);
  font-size: 12px;
  line-height: 1.45;
}

.field-candidate-panel {
  margin-bottom: 12px;
  padding: 10px 12px;
  border: 1px solid var(--app-border);
  border-radius: var(--app-radius-sm);
  background: var(--app-surface-muted);
}

.field-candidate-panel__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  margin-bottom: 8px;
}

.field-candidate-panel__head strong {
  color: var(--app-text);
  font-size: 13px;
  line-height: 1.4;
}

.field-candidate-panel__head span,
.field-candidate-empty {
  color: var(--app-text-muted);
  font-size: 12px;
  line-height: 1.45;
}

.field-candidate-empty {
  margin: 0;
}

.field-candidate-tools {
  display: grid;
  grid-template-columns: minmax(180px, 1fr) auto;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
  min-width: 0;
}

.field-candidate-search {
  min-width: 0;
}

.field-candidate-role-filter {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 3px;
  border: 1px solid var(--app-border);
  border-radius: 9px;
  background: var(--app-surface);
}

.field-candidate-role-filter button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 4px;
  min-height: 28px;
  padding: 0 8px;
  border: 0;
  border-radius: 7px;
  background: transparent;
  color: var(--app-text-muted);
  font-size: 12px;
  font-weight: 700;
  cursor: pointer;
  transition: color 0.15s ease, background 0.15s ease, box-shadow 0.15s ease;
}

.field-candidate-role-filter button:hover,
.field-candidate-role-filter button.is-active {
  color: var(--app-primary);
  background: rgba(15, 118, 110, 0.08);
}

.field-candidate-role-filter button.is-active {
  box-shadow: inset 0 0 0 1px rgba(15, 118, 110, 0.18);
}

.field-candidate-role-filter small {
  color: inherit;
  font-size: 11px;
  font-weight: 800;
  font-variant-numeric: tabular-nums;
}

.field-insert-toolbar {
  display: grid;
  grid-template-columns: auto minmax(140px, 180px) minmax(0, 1fr);
  align-items: center;
  gap: 8px;
  margin: 0 0 9px;
  padding: 8px;
  border: 1px solid rgba(15, 118, 110, 0.16);
  border-radius: 9px;
  background: rgba(15, 118, 110, 0.055);
}

.field-insert-toolbar > span {
  color: var(--app-text-muted);
  font-size: 12px;
  font-weight: 700;
  white-space: nowrap;
}

.field-insert-target {
  width: 100%;
  min-width: 0;
}

.field-insert-toolbar small {
  min-width: 0;
  color: var(--app-text-muted);
  font-size: 12px;
  line-height: 1.45;
}

.field-candidate-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  min-width: 0;
}

.field-candidate-chip {
  min-width: 0;
  border: 1px solid var(--app-border);
  border-radius: 8px;
  background: var(--app-surface);
  color: var(--app-text);
  cursor: pointer;
  max-width: 178px;
  padding: 6px 9px;
  text-align: left;
}

.field-candidate-chip:hover {
  border-color: rgba(15, 118, 110, 0.34);
  color: var(--app-primary);
  background: rgba(15, 118, 110, 0.06);
}

.field-candidate-chip strong,
.field-candidate-chip small {
  display: block;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.field-candidate-chip strong {
  font-size: 12px;
  line-height: 1.35;
}

.field-candidate-chip__role {
  margin-left: 4px;
  padding: 1px 4px;
  border-radius: 4px;
  background: var(--app-surface-muted);
  color: var(--app-text-muted);
  font-size: 10px;
  font-weight: 500;
}

.field-candidate-chip small {
  margin-top: 2px;
  color: var(--app-text-muted);
  font-size: 11px;
  line-height: 1.3;
}

.formula-preview-panel {
  margin: 12px 0;
  padding: 11px 12px;
  border: 1px solid rgba(15, 118, 110, 0.18);
  border-radius: var(--app-radius-sm);
  background: linear-gradient(180deg, rgba(15, 118, 110, 0.05), rgba(15, 118, 110, 0.01)), var(--app-surface);
}

.formula-preview-panel__head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 10px;
  margin-bottom: 8px;
}

.formula-preview-panel__head div,
.formula-preview-panel__head strong,
.formula-preview-panel__head span {
  display: block;
  min-width: 0;
}

.formula-preview-panel__head strong {
  color: var(--app-text);
  font-size: 13px;
  line-height: 1.4;
}

.formula-preview-panel__head span {
  margin-top: 2px;
  color: var(--app-text-muted);
  font-size: 12px;
  line-height: 1.45;
}

.formula-preview-panel pre {
  margin: 0;
  padding: 10px 12px;
  border-radius: 8px;
  background: #0f172a;
  color: #7dd3fc;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
  font-size: 12px;
  line-height: 1.6;
  white-space: pre-wrap;
  word-break: break-all;
}

.formula-preview-panel p {
  margin: 0;
  color: var(--app-text-muted);
  font-size: 12px;
  line-height: 1.5;
}

.metric-preview-panel {
  margin-top: 14px;
}

.metric-preview-controls {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 10px;
  min-width: 0;
}

.metric-preview-dimensions {
  width: min(520px, 100%);
}

.metric-preview-table {
  width: 100%;
}

.metric-preview-table :deep(.el-table__cell) {
  font-size: 12px;
}

.metric-preview-error {
  min-height: 40px;
  padding: 10px 12px;
  border: 1px solid rgba(220, 38, 38, 0.22);
  border-radius: var(--app-radius-sm);
  background: rgba(220, 38, 38, 0.06);
  color: #b91c1c;
  font-size: 12px;
  line-height: 1.5;
}

.metric-preview-sql-details {
  margin-top: 10px;
  border: 1px solid var(--app-border);
  border-radius: var(--app-radius-sm);
  background: var(--app-surface);
}

.metric-preview-sql-details summary {
  cursor: pointer;
  padding: 8px 12px;
  font-size: 12px;
  font-weight: 600;
  color: var(--app-text-muted);
  list-style: none;
  user-select: none;
}

.metric-preview-sql-details summary::-webkit-details-marker {
  display: none;
}

.metric-preview-sql-details[open] summary {
  border-bottom: 1px solid var(--app-border-light);
}

.metric-preview-sql-body {
  display: flex;
  flex-direction: column;
  align-items: stretch;
  padding: 0 12px 12px;
}

.metric-preview-sql-copy {
  align-self: flex-end;
  margin: 6px 0;
}

.metric-preview-sql {
  max-height: 300px;
  overflow: auto;
  margin: 0;
  padding: 10px 12px;
  border: 1px solid var(--app-border-light);
  border-radius: var(--app-radius-sm);
  background: #0f172a;
  color: #dbe4f0;
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, "Liberation Mono", monospace;
  font-size: 12px;
  line-height: 1.6;
  white-space: pre-wrap;
  word-break: break-all;
}

.field-option-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  min-width: 0;
}

.field-option-row span {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: var(--app-text);
}

.field-option-row small {
  flex: 0 1 auto;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: var(--app-text-muted);
  font-size: 11px;
}

.field-picker-select {
  min-width: 0;
}

.filter-rule-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.filter-rule-row {
  display: grid;
  grid-template-columns: 84px minmax(140px, 1fr) 126px minmax(160px, 1fr) 36px;
  align-items: center;
  gap: 8px;
  min-width: 0;
}

.filter-logic,
.filter-operator {
  width: 100%;
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

.lineage-caliber-panel {
  margin-top: 16px;
  padding: 14px;
  border: 1px solid rgba(15, 118, 110, 0.2);
  border-radius: var(--app-radius-sm);
  background: rgba(15, 118, 110, 0.045);
}

.lineage-caliber-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 8px;
}

.lineage-caliber-item {
  min-width: 0;
  padding: 9px 10px;
  border: 1px solid var(--app-border);
  border-radius: var(--app-radius-xs);
  background: var(--app-surface);
}

.lineage-caliber-item span,
.lineage-caliber-item strong {
  display: block;
}

.lineage-caliber-item span {
  color: var(--app-text-muted);
  font-size: 11px;
  line-height: 1.4;
}

.lineage-caliber-item strong {
  margin-top: 3px;
  color: var(--app-text);
  font-size: 12px;
  line-height: 1.45;
  word-break: break-word;
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
  .caliber-overview,
  .caliber-grid,
  .calculation-mode-switcher,
  .field-insert-toolbar,
  .field-candidate-tools,
  .metric-operand-picker,
  .derived-builder,
  .mode-config-grid,
  .formula-assistant-grid {
    grid-template-columns: 1fr;
  }

  .caliber-overview {
    align-items: stretch;
  }

  .calculation-mode-current {
    align-items: flex-start;
    flex-direction: column;
    gap: 4px;
  }

  .field-candidate-role-filter {
    justify-content: space-between;
    width: 100%;
  }

  .field-candidate-role-filter button {
    flex: 1 1 0;
  }

  .derived-operator-group {
    justify-content: space-between;
    width: 100%;
  }

  .derived-operator-button {
    flex: 1 1 0;
  }

  .formula-preview-panel__head {
    align-items: stretch;
    flex-direction: column;
  }

  .filter-rule-row {
    grid-template-columns: 1fr;
  }

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
  .lineage-meta-grid,
  .lineage-caliber-grid {
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
