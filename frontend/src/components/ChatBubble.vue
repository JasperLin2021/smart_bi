<template>
  <div
    class="chat-bubble"
    :class="[
      `chat-bubble--${message.role}`,
      {
        'chat-bubble--error': message.status === 'error',
        'chat-bubble--with-result': showInlineResultPreview,
      },
    ]"
  >
    <!-- 头像 -->
    <div class="chat-avatar">
      <el-avatar :size="36" :class="message.role === 'user' ? 'avatar-user' : 'avatar-assistant'">
        {{ message.role === 'user' ? '我' : 'AI' }}
      </el-avatar>
    </div>
    
    <!-- 消息内容区 -->
    <div class="chat-content">
      <!-- 加载状态 -->
      <div v-if="message.status === 'sending'" class="chat-loading">
        <div class="chat-loading-line">
          <el-icon class="is-loading"><Loading /></el-icon>
          <span>正在思考中...</span>
        </div>
        <div v-if="message.agentTrace?.length" class="compact-result-actions compact-result-actions--loading">
          <button type="button" class="result-mini-action-button result-mini-action--trace" @click="openAgentTraceDialog">
            <el-icon><Compass /></el-icon>
            <span>过程</span>
            <small>{{ traceSummary }}</small>
          </button>
        </div>
      </div>
      
      <!-- 错误状态 -->
      <div v-else-if="message.status === 'error'" class="chat-error">
        <div class="chat-error-line">
          <el-icon><WarningFilled /></el-icon>
          <span>{{ message.error || '请求失败，请重试' }}</span>
        </div>
        <div v-if="message.agentTrace?.length" class="compact-result-actions compact-result-actions--error">
          <button type="button" class="result-mini-action-button result-mini-action--trace" @click="openAgentTraceDialog">
            <el-icon><Compass /></el-icon>
            <span>过程</span>
            <small>{{ traceSummary }}</small>
          </button>
        </div>
      </div>
      
      <!-- 正常消息 -->
      <template v-else>
        <!-- 用户消息 -->
        <div v-if="message.role === 'user'" class="bubble-text">
          {{ message.content }}
        </div>
        
        <!-- 助手消息 -->
        <div v-else class="assistant-content">
          <div v-if="message.drillContext" class="drill-context">
            <span class="drill-context-label">钻取路径</span>
            <div class="drill-context-body">
              <span class="drill-context-text">
                {{ breadcrumbText }}
              </span>
              <el-button
                v-if="message.drillContext.parentQuestion"
                size="small"
                text
                class="drill-back-btn"
                @click="goBackOneLevel"
              >
                返回上一层
              </el-button>
            </div>
          </div>

          <!-- 文字回复 -->
          <div v-if="showAssistantContent" class="bubble-text">
            {{ message.content }}
          </div>

          <div v-if="!props.compactResult && message.llmModel" class="model-chip">
            <span class="model-chip-label">实际模型</span>
            <code class="model-chip-value">{{ message.llmModel }}</code>
          </div>

          <div v-if="!props.compactResult && message.trustSignals?.length" class="trust-panel">
            <div class="trust-panel-title">
              <span>可信指标</span>
              <small>本次查询命中 {{ message.trustSignals.length }} 个统一口径</small>
            </div>
            <div class="trust-list">
              <div v-for="signal in message.trustSignals" :key="signal.metric_id" class="trust-item">
                <div class="trust-item-main">
                  <strong>{{ signal.metric_name }}</strong>
                  <span>{{ signal.owner_name || "未设置负责人" }} · {{ signal.caliber_version || "v1" }}</span>
                </div>
                <div class="trust-tags">
                  <el-tag size="small" :type="certificationTagType(signal.certification_status)" effect="plain">
                    {{ certificationLabel(signal.certification_status) }}
                  </el-tag>
                  <el-tag size="small" :type="qualityTagType(signal.quality_status)" effect="plain">
                    {{ qualityLabel(signal.quality_status) }}
                  </el-tag>
                </div>
                <p v-if="signal.quality_message">{{ signal.quality_message }}</p>
              </div>
            </div>
          </div>

          <!-- 查询结果图表 -->
          <div v-if="showInlineResultPreview" class="chart-container result-inline-panel">
            <div class="result-inline-toolbar">
              <span>
                <el-icon><TrendCharts /></el-icon>
                可视化预览
              </span>
              <div class="result-inline-toolbar-actions">
                <el-button text size="small" :icon="FullScreen" @click="openResultDetail('chart')">
                  放大查看
                </el-button>
                <el-button text size="small" @click="openResultDetail('table')">
                  明细
                </el-button>
                <el-button v-if="message.sqlQuery" text size="small" @click="openResultDetail('sql')">
                  SQL
                </el-button>
                <el-button v-if="message.summary" text size="small" @click="openResultDetail('summary')">
                  总结
                </el-button>
              </div>
            </div>
            <MessageChart
              :message="message"
              :columns="message.result!.columns"
              :rows="message.result!.rows"
              :sql-query="message.sqlQuery"
              :chart-spec="message.chartSpec"
            />
          </div>
          
          <!-- 分析总结 -->
          <div
            v-if="message.summary && message.summary !== message.content"
            class="summary-box"
            :class="{ 'summary-box--clickable': props.compactResult && hasResult }"
            :role="props.compactResult && hasResult ? 'button' : undefined"
            :tabindex="props.compactResult && hasResult ? 0 : undefined"
            @click="openResultFromSummary"
            @keydown.enter.prevent="openResultFromSummary"
            @keydown.space.prevent="openResultFromSummary"
          >
            <div class="summary-title">
              <el-icon><DataAnalysis /></el-icon>
              <span>分析总结</span>
              <small v-if="props.compactResult && hasResult">打开结果</small>
            </div>
            <div class="summary-text markdown-body" v-html="renderedSummary"></div>
          </div>

          <div v-if="hasEmptyDiagnostics" class="empty-diagnostics-panel">
            <div class="empty-diagnostics-head">
              <div class="empty-diagnostics-icon">
                <el-icon><WarningFilled /></el-icon>
              </div>
              <div>
                <strong>未查到结果</strong>
                <span>查询已执行成功，下面是自动排查方向。</span>
              </div>
            </div>
            <div class="empty-check-list">
              <span v-for="check in emptyDiagnosticChecks" :key="check">{{ check }}</span>
            </div>
            <div v-if="emptyDiagnosticActions.length" class="refinement-actions empty-actions">
              <button
                v-for="action in emptyDiagnosticActions"
                :key="`${action.label}-${action.question}`"
                type="button"
                @click="emitRefinement(action.question)"
              >
                {{ action.label }}，填入输入框
              </button>
            </div>
          </div>

          <div v-if="showResultQuickActions" class="compact-result-actions" aria-label="结果操作">
            <button
              v-if="hasAgentNotes"
              type="button"
              class="result-mini-action-button result-mini-action--notes"
              @click="openAgentNotesDialog"
            >
              <el-icon><MagicStick /></el-icon>
              <span>假设</span>
            </button>
            <button
              v-if="message.agentTrace?.length"
              type="button"
              class="result-mini-action-button result-mini-action--trace"
              @click="openAgentTraceDialog"
            >
              <el-icon><Compass /></el-icon>
              <span>过程</span>
            </button>
            <button
              v-if="canCreateAction"
              type="button"
              class="result-mini-action-button result-mini-action--action"
              @click="openActionDialog"
            >
              <el-icon><Tickets /></el-icon>
              <span>生成行动项</span>
            </button>
            <button
              v-if="hasResult"
              type="button"
              class="result-mini-action-button result-mini-action--attribution"
              :disabled="attributionActionDisabled"
              @click="openAttributionDialog"
            >
              <el-icon :class="{ 'is-loading': attributionLoading || attributionPrecheckLoading }">
                <Loading v-if="attributionLoading || attributionPrecheckLoading" />
                <Aim v-else />
              </el-icon>
              <span>{{ attributionActionLabel }}</span>
              <small class="result-mini-action-beta-badge attribution-beta-badge">Beta</small>
            </button>
            <button
              v-if="props.message.historyId"
              type="button"
              class="result-mini-action-button result-mini-action--metric"
              :disabled="metricDraftLoading"
              @click="openMetricDraftDrawer"
            >
              <el-icon :class="{ 'is-loading': metricDraftLoading }">
                <Loading v-if="metricDraftLoading" />
                <DocumentAdd v-else />
              </el-icon>
              <span>保存指标</span>
              <small class="result-mini-action-beta-badge metric-beta-badge">Beta</small>
            </button>
          </div>

          <!-- 推荐标签 -->
          <div v-if="!props.compactResult && message.recommendations?.length" class="recommendations">
            <span class="rec-label">推荐维度：</span>
            <el-tag v-for="tag in message.recommendations" :key="tag" type="success" size="small" effect="plain">
              {{ tag }}
            </el-tag>
          </div>
        </div>
      </template>
      
      <!-- 时间戳 -->
      <div class="chat-time">
        {{ formatTime(message.timestamp) }}
      </div>
    </div>

    <el-dialog
      v-model="actionDialogVisible"
      title="从问数结果创建行动项"
      width="min(600px, calc(100vw - 32px))"
      destroy-on-close
    >
      <el-form label-position="top">
        <el-form-item label="行动项标题" required>
          <el-input v-model="actionForm.title" maxlength="160" placeholder="例：跟进本周销售额下滑" />
        </el-form-item>
        <el-form-item label="说明">
          <el-input v-model="actionForm.description" type="textarea" :rows="4" />
        </el-form-item>
        <el-row :gutter="12">
          <el-col :xs="24" :md="12">
            <el-form-item label="优先级">
              <el-select v-model="actionForm.priority" style="width: 100%">
                <el-option label="低" value="low" />
                <el-option label="中" value="medium" />
                <el-option label="高" value="high" />
                <el-option label="紧急" value="urgent" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :xs="24" :md="12">
            <el-form-item label="截止日期">
              <el-date-picker v-model="actionForm.due_date" type="date" value-format="YYYY-MM-DD" style="width: 100%" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="负责人">
          <el-tree-select
            v-model="actionForm.owner_id"
            class="action-owner-tree-select"
            :data="actionAssignableTree"
            :props="{ label: 'label', children: 'children', value: 'value', disabled: 'disabled' }"
            :loading="actionAssignableLoading"
            placeholder="按部门选择负责人"
            filterable
            clearable
            check-strictly
            style="width: 100%"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="actionDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="actionSaving" @click="createActionItem">创建行动项</el-button>
      </template>
    </el-dialog>

    <el-dialog
      v-model="agentNotesDialogVisible"
      title="查询假设"
      width="min(760px, calc(100vw - 32px))"
      class="agent-notes-dialog"
      destroy-on-close
    >
      <section class="assumption-panel assumption-panel--modal">
        <div class="assumption-panel-head">
          <div class="assumption-icon">
            <el-icon><MagicStick /></el-icon>
          </div>
          <div>
            <strong>已按 {{ agentAssumptionCount }} 个默认假设完成查询</strong>
            <span>{{ agentConfidenceText }}</span>
          </div>
        </div>
        <div v-if="agentAssumptions.length" class="assumption-list">
          <span v-for="item in agentAssumptions" :key="item">{{ item }}</span>
        </div>
        <div v-if="agentRiskFlags.length" class="assumption-risk-list">
          <span v-for="item in agentRiskFlags" :key="item">{{ riskFlagLabel(item) }}</span>
        </div>
        <div class="assumption-refinement-workbench">
          <div class="assumption-refinement-head">
            <div>
              <strong>批量澄清</strong>
              <span>选择要调整的假设，编辑后直接重新查询。</span>
            </div>
            <div v-if="assumptionRefinementItems.length" class="assumption-refinement-actions">
              <button type="button" @click="selectAllAssumptionRefinements">全选</button>
              <button type="button" @click="clearAssumptionRefinements">清空</button>
            </div>
          </div>
          <div
            v-for="item in assumptionRefinementItems"
            :key="item.key"
            class="refinement-draft-item refinement-draft-editor"
            :class="{ 'is-selected': assumptionRefinementSelection.includes(item.key) }"
          >
            <label class="refinement-draft-check">
              <input
                v-model="assumptionRefinementSelection"
                type="checkbox"
                :value="item.key"
                :aria-label="`选择${item.label}`"
              />
              <span>{{ item.label }}</span>
            </label>
            <el-input
              v-model="assumptionRefinementDrafts[item.key]"
              class="refinement-draft-textarea"
              type="textarea"
              :rows="2"
              resize="none"
              :disabled="!assumptionRefinementSelection.includes(item.key)"
            />
          </div>
          <div class="assumption-custom-field">
            <span>补充澄清</span>
            <el-input
              v-model="customAssumptionClarification"
              type="textarea"
              :rows="2"
              resize="none"
              placeholder="可以一次补充多个条件，例如时间范围、字段含义、筛选口径"
            />
          </div>
          <div class="assumption-batch-preview">
            <span>将发送</span>
            <pre>{{ assumptionBatchQuestion || "选择或填写澄清内容后生成" }}</pre>
          </div>
        </div>
      </section>
      <template #footer>
        <div class="agent-notes-footer">
          <button type="button" class="agent-notes-secondary" @click="agentNotesDialogVisible = false">
            取消
          </button>
          <button
            type="button"
            class="agent-notes-primary"
            :disabled="assumptionRefinementSubmitting || !assumptionBatchQuestion.trim()"
            @click="runAssumptionBatchRefinement"
          >
            <el-icon v-if="assumptionRefinementSubmitting" class="is-loading"><Loading /></el-icon>
            <span>按这些澄清重新查询</span>
          </button>
        </div>
      </template>
    </el-dialog>

    <el-dialog
      v-model="agentTraceDialogVisible"
      title="探索模式执行过程"
      width="min(860px, calc(100vw - 32px))"
      class="agent-trace-dialog"
      destroy-on-close
    >
      <el-collapse v-model="agentTracePanelOpen" class="agent-trace-collapse" @change="handleTracePanelChange">
        <el-collapse-item name="agent-trace">
          <template #title>
            <div class="agent-trace-title">
              <span>探索模式执行过程</span>
              <small>{{ traceSummary }}</small>
            </div>
          </template>
          <div class="agent-trace-compact" :class="traceCurrentStatusClass">
            <div class="trace-summary-strip">
              <div class="trace-summary-main">
                <span class="trace-stage-pill">{{ latestTraceStep ? traceStageLabel(latestTraceStep.stage) : "等待开始" }}</span>
                <strong>{{ latestTraceStep ? latestTraceStep.message : "等待探索模式开始执行" }}</strong>
              </div>
              <div class="trace-summary-chips">
                <span class="trace-summary-chip">{{ completedTraceCount }}/{{ agentTraceSteps.length }} 完成</span>
                <span v-if="warningTraceCount" class="trace-summary-chip trace-summary-chip--warning">{{ warningTraceCount }} 警告</span>
                <span v-if="failedTraceCount" class="trace-summary-chip trace-summary-chip--error">{{ failedTraceCount }} 失败</span>
                <span class="trace-summary-chip trace-summary-chip--status">{{ traceRunningText }}</span>
              </div>
            </div>
            <div class="trace-progress-line" aria-hidden="true">
              <i :style="{ width: `${traceProgressPercent}%` }"></i>
            </div>

            <div v-if="agentTraceSteps.length" class="trace-stepper" role="list" aria-label="探索模式执行步骤">
              <div class="trace-stepper-track" aria-hidden="true">
                <i :style="{ width: `${traceProgressPercent}%` }"></i>
              </div>
              <button
                v-for="(step, index) in agentTraceSteps"
                :key="`${step.stage}-${step.message}-${index}`"
                type="button"
                class="trace-stepper-node"
                :class="[
                  `trace-stepper-node--${step.status}`,
                  { 'trace-stepper-node--active': index === activeTraceStepIndex }
                ]"
                role="listitem"
                :aria-current="index === activeTraceStepIndex ? 'step' : undefined"
                @click="selectTraceStep(index)"
              >
                <span class="trace-stepper-circle">
                  <span class="trace-stepper-icon" aria-hidden="true">
                    <component :is="traceStageIcon(step.stage)" />
                  </span>
                  <span class="trace-step-dot" :class="`trace-step-dot--${step.status}`"></span>
                </span>
                <span class="trace-stepper-label">{{ traceStageLabel(step.stage) }}</span>
                <small>{{ traceStatusLabel(step.status) }}</small>
              </button>
            </div>

            <div
              v-if="selectedTraceStep"
              class="trace-selected-panel"
              :class="`trace-selected-panel--${selectedTraceStep.status}`"
            >
              <div class="trace-selected-meta">
                <span class="trace-step-index">#{{ selectedTraceStepIndex + 1 }}</span>
                <span class="trace-stage-pill trace-stage-pill--soft">{{ traceStageLabel(selectedTraceStep.stage) }}</span>
                <span class="trace-summary-chip trace-summary-chip--status">
                  {{ selectedTraceStepIndex === latestTraceIndex ? "最新" : "已选" }} · {{ traceStatusLabel(selectedTraceStep.status) }}
                </span>
              </div>
              <div class="trace-row-message">
                <strong>{{ selectedTraceStep.message }}</strong>
              </div>
              <pre v-if="selectedTraceStep.detail" class="trace-detail trace-detail-panel">{{ formatTraceDetail(selectedTraceStep.detail) }}</pre>
            </div>
          </div>
        </el-collapse-item>
      </el-collapse>
    </el-dialog>

    <el-dialog
      v-model="attributionDialogVisible"
      :title="attributionPanelTitle"
      width="min(780px, calc(100vw - 32px))"
      class="attribution-dialog"
      destroy-on-close
    >
      <div v-if="attributionLoading" class="modal-loading-state">
        <el-icon class="is-loading"><Loading /></el-icon>
        <span>{{ attributionActionLabel }}生成中...</span>
      </div>
      <section v-else-if="attributionResult" class="attribution-section">
        <div class="attribution-summary-card">
          <div>
            <span>分析结论</span>
            <p>{{ attributionResult.summary }}</p>
          </div>
          <el-tag size="small" :type="attributionConfidenceType" effect="plain">
            {{ attributionConfidenceLabel }}
          </el-tag>
        </div>
        <div class="attribution-overview">
          <div>
            <span>分析指标</span>
            <strong>{{ attributionResult.metric_column || "自动识别" }}</strong>
          </div>
          <div>
            <span>驱动因素</span>
            <strong>{{ attributionResult.drivers.length }}</strong>
          </div>
          <div>
            <span>分析方式</span>
            <strong>{{ attributionModelLabel }}</strong>
          </div>
        </div>
        <div v-if="attributionResult.drivers.length" class="driver-list">
          <div v-for="driver in attributionResult.drivers" :key="`${driver.dimension}-${driver.value}`" class="driver-item">
            <div class="driver-main">
              <strong>{{ driver.dimension }} = {{ driver.value }}</strong>
              <span>{{ driverImpactLabel(driver.impact) }}贡献 {{ formatContribution(driver.contribution) }}</span>
            </div>
            <div class="driver-progress">
              <el-progress :percentage="safePercentage(driver.share)" :stroke-width="8" :status="driverImpactProgressStatus(driver.impact)" />
              <small>占比 {{ safePercentage(driver.share) }}%</small>
            </div>
          </div>
        </div>
        <el-empty v-else description="暂未识别出主要归因因子" :image-size="56" />
        <div v-if="attributionResult.recommendations?.length" class="recommendation-strip">
          <span v-for="item in attributionResult.recommendations" :key="item">{{ item }}</span>
        </div>
      </section>
      <section v-else class="modal-empty-state">
        <strong>{{ precheckStatusText }}</strong>
        <p>{{ attributionPrecheckResult?.summary || attributionActionDescription }}</p>
        <el-button type="primary" :disabled="attributionActionDisabled" @click="runAttribution">
          开始分析
        </el-button>
      </section>
    </el-dialog>

    <el-dialog
      v-model="resultDetailVisible"
      title="问数结果详情"
      width="min(1080px, calc(100vw - 32px))"
      class="result-detail-dialog"
      destroy-on-close
    >
      <div class="result-detail-summary">
        <div>
          <span>原始问题</span>
          <strong>{{ resultQuestionText }}</strong>
        </div>
        <div class="result-detail-metrics">
          <span>{{ resultRowCount }} 行</span>
          <span>{{ resultColumnCount }} 字段</span>
          <span v-if="message.chartSpec">图表建议</span>
          <span v-if="message.sqlQuery">SQL 已生成</span>
        </div>
      </div>
      <el-tabs v-model="resultDetailTab" class="result-detail-tabs">
        <el-tab-pane label="图表" name="chart" lazy>
          <div class="result-detail-pane result-detail-pane--chart">
            <MessageChart
              v-if="hasResult"
              :message="message"
              :columns="message.result!.columns"
              :rows="message.result!.rows"
              :sql-query="message.sqlQuery"
              :chart-spec="message.chartSpec"
            />
          </div>
        </el-tab-pane>
        <el-tab-pane label="数据明细" name="table" lazy>
          <div class="result-detail-pane">
            <MessageTable v-if="hasResult" :message="message" :columns="message.result!.columns" :rows="message.result!.rows" />
          </div>
        </el-tab-pane>
        <el-tab-pane v-if="message.sqlQuery" label="SQL" name="sql" lazy>
          <div class="result-detail-pane">
            <pre class="result-detail-sql">{{ message.sqlQuery }}</pre>
          </div>
        </el-tab-pane>
        <el-tab-pane v-if="message.summary" label="总结" name="summary" lazy>
          <div class="result-detail-pane result-detail-summary-text markdown-body" v-html="renderedSummary"></div>
        </el-tab-pane>
      </el-tabs>
    </el-dialog>

    <el-dialog
      v-model="metricDraftDrawerVisible"
      title="保存为指标草稿"
      width="min(760px, calc(100vw - 32px))"
      destroy-on-close
      class="metric-draft-dialog"
    >
      <div v-if="metricDraftLoading" class="metric-draft-loading">
        <el-icon class="is-loading"><Loading /></el-icon>
        <span>正在识别可沉淀指标...</span>
      </div>
      <section v-else-if="metricDraftDatasetMissing" class="metric-draft-empty-dataset">
        <div class="metric-draft-empty-icon">
          <el-icon><DocumentAdd /></el-icon>
        </div>
        <div>
          <span>缺少基础数据集</span>
          <strong>当前数据源下没有可绑定的同源数据集</strong>
          <p>{{ metricDraftDatasetError || "请先创建基础数据集，再回到探索结果保存为指标草稿。" }}</p>
        </div>
        <button type="button" class="metric-draft-create-dataset" @click="openDatasetBuilderForMetric">
          创建基础数据集
        </button>
      </section>
      <template v-else>
        <section class="metric-draft-hero">
          <div>
            <span>保存为指标草稿</span>
            <strong>{{ metricDraftForm.name || "待识别指标" }}</strong>
            <small class="metric-draft-dataset">绑定数据集：{{ metricDraftDatasetLabel }}</small>
            <p>保存后会进入指标草稿 / 待认证状态，TOP N、时间窗口等临时分析条件保留在来源证据中。</p>
          </div>
          <el-tag size="small" type="warning" effect="plain">草稿 / 待认证</el-tag>
        </section>

        <section class="metric-draft-checklist">
          <div class="metric-draft-checklist-head">
            <span>草稿完整度</span>
            <strong>{{ metricDraftCompletedCount }}/{{ metricDraftCompletionItems.length }}</strong>
          </div>
          <div class="metric-draft-checklist-items">
            <span
              v-for="item in metricDraftCompletionItems"
              :key="item.label"
              :class="{ 'is-done': item.done }"
            >
              <el-icon><CircleCheck /></el-icon>
              {{ item.label }}
            </span>
          </div>
        </section>

        <div v-if="metricDraftWarnings.length" class="metric-draft-warnings">
          <el-alert
            v-for="warning in metricDraftWarnings"
            :key="warning"
            :title="warning"
            type="warning"
            show-icon
            :closable="false"
          />
        </div>
        <el-form label-position="top" class="metric-draft-form">
          <el-form-item label="指标名称" required>
            <el-input v-model="metricDraftForm.name" maxlength="128" />
          </el-form-item>
          <el-form-item label="业务定义" required>
            <el-input v-model="metricDraftForm.definition" type="textarea" :rows="3" />
          </el-form-item>
          <el-form-item label="绑定数据集" required>
            <el-input :model-value="metricDraftDatasetLabel" disabled />
          </el-form-item>
          <el-row :gutter="12">
            <el-col :xs="24" :sm="12">
              <el-form-item label="指标列">
                <el-select v-model="metricDraftForm.selected_metric_column" style="width: 100%" clearable>
                  <el-option v-for="column in metricDraftColumns" :key="column" :label="column" :value="column" />
                </el-select>
              </el-form-item>
            </el-col>
            <el-col :xs="24" :sm="12">
              <el-form-item label="单位">
                <el-input v-model="metricDraftForm.unit" placeholder="次、元、%" />
              </el-form-item>
            </el-col>
          </el-row>
          <el-form-item label="计算公式" required>
            <el-input v-model="metricDraftForm.formula" />
            <div class="metric-field-hint">建议只保留稳定聚合公式，例如 COUNT(*)、SUM(amount)，不要把 TOP N 或临时时间窗口写入指标公式。</div>
          </el-form-item>
          <el-form-item label="推荐维度">
            <el-select v-model="metricDraftForm.dimensions" multiple clearable collapse-tags style="width: 100%">
              <el-option v-for="column in metricDraftDimensionColumns" :key="column" :label="column" :value="column" />
            </el-select>
          </el-form-item>
          <el-form-item label="时间字段">
            <el-select v-model="metricDraftForm.time_column" style="width: 100%" clearable>
              <el-option v-for="column in metricDraftColumns" :key="column" :label="column" :value="column" />
            </el-select>
          </el-form-item>
        </el-form>

        <section v-if="metricDraftResponse" class="metric-draft-source">
          <div class="metric-draft-source-title">
            <span>来源证据</span>
            <el-tag size="small" type="warning" effect="plain">草稿 / 待认证</el-tag>
          </div>
          <div class="metric-draft-source-grid">
            <span>原始问题</span>
            <strong>{{ metricDraftResponse.source.source_question || props.message.sourceQuestion || props.message.content }}</strong>
            <span>查询历史</span>
            <strong>#{{ metricDraftResponse.source.source_query_history_id }}</strong>
            <span>绑定数据集</span>
            <strong>{{ metricDraftDatasetLabel }}</strong>
            <span>结果行数</span>
            <strong>{{ metricDraftResponse.validation.row_count || 0 }}</strong>
            <span>校验状态</span>
            <strong>{{ metricDraftResponse.validation.message || metricDraftResponse.validation.validation_status || "待校验" }}</strong>
            <span>识别方式</span>
            <strong>{{ metricDraftResponse.llm_enhanced ? "大模型增强" : "规则识别" }}</strong>
          </div>
          <el-collapse class="metric-draft-evidence">
            <el-collapse-item title="查看来源 SQL" name="sql">
              <pre>{{ metricDraftResponse.source.source_sql }}</pre>
            </el-collapse-item>
          </el-collapse>
        </section>
      </template>
      <template #footer>
        <el-button @click="metricDraftDrawerVisible = false">取消</el-button>
        <el-button v-if="metricDraftDatasetMissing" type="primary" @click="openDatasetBuilderForMetric">
          创建基础数据集
        </el-button>
        <el-button v-else type="primary" :loading="metricDraftSaving" :disabled="metricDraftLoading" @click="saveMetricDraft">
          保存指标草稿
        </el-button>
      </template>
    </el-dialog>

    <DatasetCenter
      v-if="datasetBuilderVisible"
      embedded
      auto-create
      :preferred-datasource-id="metricDraftDatasourceId"
      @saved="handleMetricDatasetCreated"
      @closed="datasetBuilderVisible = false"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, reactive, ref, watch, type Component } from "vue"
import axios from "axios"
import { useRouter } from "vue-router"
import { ElMessage } from "element-plus"
import {
  Aim,
  CircleCheck,
  Compass,
  DataAnalysis,
  DocumentAdd,
  FullScreen,
  Loading,
  MagicStick,
  Tickets,
  TrendCharts,
  WarningFilled,
} from "@element-plus/icons-vue"
import { marked } from "marked"
import {
  useQueryStore,
  type AgenticRefinementAction,
  type AgentTraceStep,
  type ChatMessage,
  type DrillContext,
} from "@/store/query"
import { useAuthStore } from "@/store/auth"
import { useDatasourceStore } from "@/store/datasource"
import DatasetCenter from "@/views/DatasetCenter.vue"
import MessageChart from "./MessageChart.vue"
import MessageTable from "./MessageTable.vue"

const props = defineProps<{
  message: ChatMessage
  compactResult?: boolean
}>()

const emit = defineEmits<{
  (event: "use-refinement", question: string): void
  (event: "open-result", tab: ResultDetailTab): void
}>()

interface AssignableUser {
  id: number
  username: string
  role: string
  role_label: string
  department: string
}

interface AssignableDept {
  department: string
  users: AssignableUser[]
}

const queryStore = useQueryStore()
const authStore = useAuthStore()
const datasourceStore = useDatasourceStore()
const router = useRouter()
const actionDialogVisible = ref(false)
const agentNotesDialogVisible = ref(false)
const agentTraceDialogVisible = ref(false)
const attributionDialogVisible = ref(false)
const actionSaving = ref(false)
const actionAssignableLoading = ref(false)
const actionAssignableUsers = ref<AssignableDept[]>([])
const metricDraftDrawerVisible = ref(false)
const metricDraftLoading = ref(false)
const metricDraftSaving = ref(false)
const metricDraftResponse = ref<MetricDraftResponse | null>(null)
const metricDraftWarnings = ref<string[]>([])
const metricDraftDatasetMissing = ref(false)
const metricDraftDatasetError = ref("")
const datasetBuilderVisible = ref(false)
const metricDraftForm = reactive({
  dataset_id: null as number | null,
  name: "",
  definition: "",
  formula: "",
  unit: "",
  selected_metric_column: "",
  dimensions: [] as string[],
  time_column: "",
})

const actionForm = reactive({
  title: "",
  description: "",
  priority: "medium",
  due_date: "",
  owner_id: null as number | null,
  linked_metric_id: null as number | null,
})
const attributionLoading = ref(false)
const attributionResult = ref<AttributionResponse | null>(null)
const attributionPrecheckLoading = ref(false)
const attributionPrecheckResult = ref<AnomalyPrecheckResponse | null>(null)
const attributionPrecheckKey = ref("")
const analysisResultPanels = ref<string[]>([])

interface AttributionResponse {
  metric_column: string | null
  summary: string
  confidence: string
  llm_enhanced?: boolean
  llm_model?: string | null
  drivers: Array<{
    dimension: string
    value: string
    contribution: number
    share: number
    impact: string
  }>
  recommendations: string[]
}

interface AnomalyPrecheckResponse {
  status: "anomaly" | "normal" | "insufficient"
  has_anomaly: boolean
  metric_column: string | null
  time_column?: string | null
  anomaly_count: number
  summary: string
  severity: "info" | "success" | "warning" | "danger"
  confidence: string
  recommended_action: "anomaly_attribution" | "contribution_analysis" | "refine_query"
  action_label: string
  llm_enhanced?: boolean
  llm_model?: string | null
  anomalies: Array<{
    type: string
    title: string
    description: string
    severity: string
    metric_column?: string
    value?: string
    score?: number
  }>
}

interface MetricDraftResponse {
  candidate: {
    name?: string
    definition?: string
    formula?: string
    unit?: string | null
    metric_column?: string | null
    dimensions?: string[]
    time_column?: string | null
  }
  source: {
    source_query_history_id: number
    source_dataset_id?: number | null
    source_dataset_name?: string | null
    source_sql?: string
    source_question?: string
    source_metric_column?: string | null
    dataset_binding?: {
      dataset_id: number
      dataset_name: string
      datasource_id: number
      auto_recommended: boolean
    }
  }
  validation: {
    row_count?: number
    validation_status?: string
    message?: string
  }
  warnings: string[]
  llm_enhanced: boolean
  llm_model?: string | null
}

const hasResult = computed(() => {
  return props.message.result && 
         props.message.result.rows && 
         props.message.result.rows.length > 0
})

const agentAssumptions = computed(() => props.message.agentNotes?.assumptions || [])
const agentRiskFlags = computed(() => props.message.agentNotes?.risk_flags || [])
const agentRefinementActions = computed<AgenticRefinementAction[]>(() => props.message.agentNotes?.suggested_refinements || [])
const assumptionRefinementSelection = ref<string[]>([])
const assumptionRefinementDrafts = ref<Record<string, string>>({})
const customAssumptionClarification = ref("")
const assumptionRefinementSubmitting = ref(false)
const hasAgentNotes = computed(() =>
  Boolean(agentAssumptions.value.length || agentRiskFlags.value.length || agentRefinementActions.value.length)
)
const agentAssumptionCount = computed(() => Math.max(agentAssumptions.value.length, 1))
const agentConfidenceText = computed(() => {
  const confidence = props.message.agentNotes?.confidence || "medium"
  const labels: Record<string, string> = {
    high: "口径较明确，可直接查看结果",
    medium: "口径存在轻微不确定，可按需调整",
    low: "口径不确定性较高，建议查看假设",
  }
  return labels[confidence] || "可查看假设并继续调整"
})
const assumptionRefinementKey = (action: AgenticRefinementAction, index: number) =>
  `${index}-${action.label || "澄清"}-${action.question || ""}`
const assumptionRefinementItems = computed(() =>
  agentRefinementActions.value.map((action, index) => ({
    key: assumptionRefinementKey(action, index),
    label: action.label || `澄清 ${index + 1}`,
    question: action.question || "",
  }))
)
const selectedAssumptionRefinements = computed(() =>
  assumptionRefinementItems.value
    .filter(item => assumptionRefinementSelection.value.includes(item.key))
    .map(item => (assumptionRefinementDrafts.value[item.key] || item.question).trim())
    .filter(Boolean)
)
const assumptionBatchQuestion = computed(() => {
  const custom = customAssumptionClarification.value.trim()
  const lines = [...selectedAssumptionRefinements.value, ...(custom ? [custom] : [])]
  if (!lines.length) return ""
  const question = props.message.sourceQuestion || props.message.content || "上一个问题"
  return [
    `基于上一个问题「${question}」，补充澄清如下：`,
    ...lines.map((line, index) => `${index + 1}. ${line}`),
  ].join("\n")
})

const emptyDiagnosticChecks = computed(() => props.message.emptyDiagnostics?.checks || [])
const emptyDiagnosticActions = computed<AgenticRefinementAction[]>(() => props.message.emptyDiagnostics?.suggested_actions || [])
const hasEmptyDiagnostics = computed(() =>
  props.message.status === "success" &&
  !hasResult.value &&
  Boolean(emptyDiagnosticChecks.value.length || emptyDiagnosticActions.value.length)
)

const resultRowCount = computed(() => props.message.result?.rows?.length || 0)
const resultColumnCount = computed(() => props.message.result?.columns?.length || 0)
type ResultDetailTab = "chart" | "table" | "sql" | "summary"
const resultDetailVisible = ref(false)
const resultDetailTab = ref<ResultDetailTab>("chart")
const resultQuestionText = computed(() => props.message.sourceQuestion || props.message.content || "本次问数结果")
const showAssistantContent = computed(() =>
  Boolean(props.message.content && !(props.compactResult && props.message.summary))
)
const showInlineResultPreview = computed(() => hasResult.value)
const showResultQuickActions = computed(() =>
  props.message.role === "assistant" &&
  props.message.status !== "sending" &&
  Boolean(hasResult.value || hasAgentNotes.value || agentTraceSteps.value.length || canCreateAction.value || props.message.historyId)
)

const openResultDetail = (tab: ResultDetailTab = "chart") => {
  if (props.compactResult) {
    emit("open-result", tab)
    return
  }
  resultDetailTab.value = tab
  resultDetailVisible.value = true
}

const openResultFromSummary = () => {
  if (!props.compactResult || !hasResult.value) return
  const tab: ResultDetailTab = "chart"
  emit("open-result", tab)
}

const prepareAssumptionRefinementDrafts = () => {
  const nextDrafts: Record<string, string> = {}
  const nextSelection: string[] = []
  assumptionRefinementItems.value.forEach(item => {
    nextDrafts[item.key] = assumptionRefinementDrafts.value[item.key] || item.question
    nextSelection.push(item.key)
  })
  assumptionRefinementDrafts.value = nextDrafts
  assumptionRefinementSelection.value = nextSelection
  customAssumptionClarification.value = ""
}

const openAgentNotesDialog = () => {
  prepareAssumptionRefinementDrafts()
  agentNotesDialogVisible.value = true
}

const selectAllAssumptionRefinements = () => {
  assumptionRefinementSelection.value = assumptionRefinementItems.value.map(item => item.key)
}

const clearAssumptionRefinements = () => {
  assumptionRefinementSelection.value = []
}

const runAssumptionBatchRefinement = async () => {
  const question = assumptionBatchQuestion.value.trim()
  if (!question) {
    ElMessage.warning("请选择或填写需要澄清的内容")
    return
  }
  assumptionRefinementSubmitting.value = true
  agentNotesDialogVisible.value = false
  try {
    await queryStore.ask(question, props.message.mode || "business", undefined, props.message.historyId)
  } finally {
    assumptionRefinementSubmitting.value = false
  }
}

const openAgentTraceDialog = () => {
  agentTraceDialogVisible.value = true
  if (agentTraceSteps.value.length) {
    agentTracePanelOpen.value = ["agent-trace"]
    agentTracePanelTouched.value = true
    traceStepperTouched.value = false
    activeTraceStepIndex.value = latestTraceIndex.value
  }
}

const analysisStatusText = computed(() => {
  if (attributionLoading.value) return attributionPanelTitle.value === "贡献分析" ? "正在分析贡献构成" : "正在分析异常归因"
  if (attributionPrecheckLoading.value) return "正在预检异常"
  if (metricDraftLoading.value) return "正在识别指标草稿"
  if (attributionResult.value) return `已生成${attributionPanelTitle.value}`
  if (props.message.fromHistory) return "历史结果已加载，可按需分析"
  if (attributionPrecheckResult.value?.status === "anomaly") return `发现 ${attributionPrecheckResult.value.anomaly_count || 1} 个异常候选`
  if (attributionPrecheckResult.value?.status === "normal") return "未发现明显异常"
  if (attributionPrecheckResult.value?.status === "insufficient") return "数据不足以判断异常"
  return "结果已生成，正在准备分析"
})

const precheckStatusText = computed(() => {
  if (attributionPrecheckLoading.value) return "智能预检中"
  if (attributionPrecheckResult.value?.status === "anomaly") return "发现异常候选"
  if (attributionPrecheckResult.value?.status === "normal") return "未发现明显异常"
  if (attributionPrecheckResult.value?.status === "insufficient") return "数据不足"
  return "等待预检"
})

const precheckStatusType = computed(() => {
  if (attributionPrecheckResult.value?.status === "anomaly") return "warning"
  if (attributionPrecheckResult.value?.status === "normal") return "success"
  if (attributionPrecheckResult.value?.status === "insufficient") return "info"
  return attributionPrecheckLoading.value ? "info" : "info"
})

const attributionAnalysisMode = computed(() =>
  attributionPrecheckResult.value?.recommended_action === "contribution_analysis" ? "contribution_analysis" : "anomaly_attribution"
)

const attributionPanelTitle = computed(() =>
  attributionAnalysisMode.value === "contribution_analysis" ? "贡献分析" : "异常归因"
)

const attributionActionLabel = computed(() => {
  if (attributionPrecheckLoading.value) return "预检中"
  if (attributionPrecheckResult.value?.action_label) return attributionPrecheckResult.value.action_label
  return "异常归因"
})

const attributionActionDescription = computed(() => {
  if (attributionPrecheckLoading.value) return "图表已可查看，正在后台判断是否存在异常"
  if (attributionPrecheckResult.value?.status === "anomaly") return "针对异常候选定位主要驱动因素"
  if (attributionPrecheckResult.value?.status === "normal") return "未发现明显异常，解释主要贡献构成"
  if (attributionPrecheckResult.value?.status === "insufficient") return "需要更多时间点、数值指标或对比维度"
  return "定位主要驱动因素和可跟进方向"
})

const attributionActionDisabled = computed(() =>
  attributionLoading.value ||
  attributionPrecheckLoading.value ||
  attributionPrecheckResult.value?.recommended_action === "refine_query"
)

const metricDraftColumns = computed(() => props.message.result?.columns || [])
const metricDraftDimensionColumns = computed(() =>
  metricDraftColumns.value.filter(column => column !== metricDraftForm.selected_metric_column)
)

const metricDraftCompletionItems = computed(() => [
  { label: "数据集", done: Boolean(metricDraftForm.dataset_id) },
  { label: "名称", done: Boolean(metricDraftForm.name.trim()) },
  { label: "定义", done: Boolean(metricDraftForm.definition.trim()) },
  { label: "公式", done: Boolean(metricDraftForm.formula.trim()) },
  { label: "指标列", done: Boolean(metricDraftForm.selected_metric_column) },
  { label: "维度", done: metricDraftForm.dimensions.length > 0 },
  { label: "时间字段", done: Boolean(metricDraftForm.time_column) },
])

const metricDraftCompletedCount = computed(() =>
  metricDraftCompletionItems.value.filter(item => item.done).length
)

const metricDraftDatasetLabel = computed(() => {
  const source = metricDraftResponse.value?.source
  return source?.source_dataset_name || source?.dataset_binding?.dataset_name || "未绑定数据集"
})

const metricDraftDatasourceId = computed(() =>
  metricDraftResponse.value?.source.dataset_binding?.datasource_id ||
  props.message.datasourceId ||
  queryStore.selectedDatasourceId ||
  datasourceStore.currentId ||
  null
)

const currentUserRoleLabel = computed(() => {
  const role = authStore.profile?.role || ""
  const map: Record<string, string> = {
    user: "普通用户",
    dept_admin: "部门管理员",
    department_admin: "部门管理员",
    org_admin: "组织管理员",
    super_admin: "超级管理员",
  }
  return map[role] || role || "用户"
})

const actionAssignableTree = computed(() => {
  const groups = actionAssignableUsers.value.length
    ? actionAssignableUsers.value
    : authStore.profile
      ? [{
          department: "我的账号",
          users: [{
            id: authStore.profile.id,
            username: authStore.profile.username,
            role: authStore.profile.role,
            role_label: currentUserRoleLabel.value,
            department: "我的账号",
          }],
        }]
      : []

  return groups.map(dept => ({
    value: `dept:${dept.department}`,
    label: dept.department,
    disabled: true,
    children: dept.users.map(user => ({
      value: user.id,
      label: `${user.username}（${user.role_label || user.role}）`,
      disabled: false,
    })),
  }))
})

// 渲染 Markdown
const renderedSummary = computed(() => {
  if (!props.message.summary) return ""
  return marked(props.message.summary, { breaks: true })
})

const canCreateAction = computed(() =>
  props.message.role === "assistant" &&
  props.message.status === "success" &&
  Boolean(props.message.historyId || props.message.summary || props.message.result?.rows?.length)
)

const attributionEnhancementLabel = computed(() =>
  attributionResult.value?.llm_enhanced ? "大模型增强" : ""
)

const attributionDriverCountText = computed(() => `${attributionResult.value?.drivers?.length || 0} 个驱动因素`)

const attributionModelLabel = computed(() => {
  const model = attributionResult.value?.llm_model
  return model ? `模型 ${model}` : "规则识别"
})

const attributionConfidenceLabel = computed(() => {
  const confidence = attributionResult.value?.confidence || "medium"
  const labels: Record<string, string> = {
    high: "高置信度",
    medium: "中置信度",
    low: "低置信度",
  }
  return labels[confidence] || confidence
})

const attributionConfidenceType = computed(() => {
  const confidence = attributionResult.value?.confidence || "medium"
  const types: Record<string, "success" | "warning" | "info" | "danger"> = {
    high: "success",
    medium: "warning",
    low: "info",
  }
  return types[confidence] || "info"
})

const agentTracePanelOpen = ref<string[]>(props.message.status === "sending" || props.message.status === "error" ? ["agent-trace"] : [])
const agentTracePanelTouched = ref(false)
const traceStepperTouched = ref(false)
const activeTraceStepIndex = ref(0)
const agentTraceSteps = computed(() => props.message.agentTrace || [])
const latestTraceIndex = computed(() => agentTraceSteps.value.length - 1)
const latestTraceStep = computed((): AgentTraceStep | null => (
  latestTraceIndex.value >= 0 ? agentTraceSteps.value[latestTraceIndex.value] : null
))
const selectedTraceStepIndex = computed(() => {
  const total = agentTraceSteps.value.length
  if (!total) return -1
  if (activeTraceStepIndex.value < 0 || activeTraceStepIndex.value >= total) return total - 1
  return activeTraceStepIndex.value
})
const selectedTraceStep = computed((): AgentTraceStep | null => (
  selectedTraceStepIndex.value >= 0 ? agentTraceSteps.value[selectedTraceStepIndex.value] : null
))
const completedTraceCount = computed(() => agentTraceSteps.value.filter(item => item.status === "success").length)
const failedTraceCount = computed(() => agentTraceSteps.value.filter(item => item.status === "error").length)
const pendingTraceCount = computed(() => agentTraceSteps.value.filter(item => item.status === "pending").length)
const warningTraceCount = computed(() => agentTraceSteps.value.filter(item => item.status === "warning").length)

const traceProgressPercent = computed(() => {
  const total = agentTraceSteps.value.length
  if (!total) return 0
  if (failedTraceCount.value) return Math.max(8, Math.round((completedTraceCount.value / total) * 100))
  if (pendingTraceCount.value) return Math.max(8, Math.round(((completedTraceCount.value + 0.5) / total) * 100))
  return 100
})

const traceRunningText = computed(() => {
  if (failedTraceCount.value) return "需要处理"
  if (pendingTraceCount.value) return "执行中"
  if (warningTraceCount.value) return "有警告"
  if (agentTraceSteps.value.length) return "已完成"
  return "待开始"
})

const traceCurrentStatusClass = computed(() => (
  latestTraceStep.value ? `trace-dashboard--${latestTraceStep.value.status}` : "trace-dashboard--idle"
))

const traceSummary = computed(() => {
  const total = agentTraceSteps.value.length
  if (!total) return "0 步"
  if (failedTraceCount.value) return `${total} 步 · ${failedTraceCount.value} 个失败`
  if (pendingTraceCount.value) return `${total} 步 · 执行中`
  if (warningTraceCount.value) return `${total} 步 · 有警告`
  return `${total} 步 · 已完成`
})

const buildBreadcrumb = (context?: DrillContext): string[] => {
  if (!context) return []
  const previous = buildBreadcrumb(context.parentContext)
  return [
    ...previous,
    `${context.sourceLabel} = ${context.sourceValue}`,
    context.targetLabel,
  ]
}

const breadcrumbText = computed(() => buildBreadcrumb(props.message.drillContext).join(" -> "))

const goBackOneLevel = async () => {
  const drillContext = props.message.drillContext
  if (!drillContext?.parentQuestion) return
  await queryStore.ask(drillContext.parentQuestion, "business", drillContext.parentContext)
}

const riskFlagLabel = (flag: string) => {
  const labels: Record<string, string> = {
    question_ambiguous: "问题描述存在歧义",
    missing_time_range: "未指定时间范围",
    missing_metric: "未指定指标口径",
    missing_dimension: "未指定分析维度",
  }
  return labels[flag] || flag
}

const emitRefinement = (question: string) => {
  const refinedQuestion = question.trim()
  if (!refinedQuestion) return
  emit("use-refinement", refinedQuestion)
}

const traceStageLabel = (stage: string) => {
  const labels: Record<string, string> = {
    context: "上下文",
    value_probe: "值探测",
    plan: "规划",
    assumption: "假设",
    sql_generate: "生成",
    sql_fix: "修复",
    sql_execute_fix: "执行修复",
    sql_execute_fix_retry: "执行修复",
    execute: "执行",
    empty_diagnostics: "空结果诊断",
    chart_plan: "图表",
  }
  return labels[stage] || stage
}

const traceStageIcon = (stage: string) => {
  const icons: Record<string, Component> = {
    context: DataAnalysis,
    value_probe: Aim,
    plan: Compass,
    assumption: MagicStick,
    sql_generate: DocumentAdd,
    sql_fix: WarningFilled,
    sql_execute_fix: WarningFilled,
    sql_execute_fix_retry: WarningFilled,
    execute: CircleCheck,
    empty_diagnostics: WarningFilled,
    chart_plan: TrendCharts,
  }
  return icons[stage] || Compass
}

const traceStatusLabel = (status: string) => {
  const labels: Record<string, string> = {
    success: "已完成",
    warning: "有警告",
    error: "失败",
    pending: "执行中",
  }
  return labels[status] || status
}

const normalizeCollapseValue = (value: string | number | Array<string | number>) => {
  if (Array.isArray(value)) return value.map(String)
  return value ? [String(value)] : []
}

const handleTracePanelChange = (value: string | number | Array<string | number>) => {
  agentTracePanelTouched.value = true
  agentTracePanelOpen.value = normalizeCollapseValue(value)
}

const selectTraceStep = (index: number) => {
  if (index < 0 || index >= agentTraceSteps.value.length) return
  traceStepperTouched.value = true
  activeTraceStepIndex.value = index
}

const syncTraceCollapseState = () => {
  if (agentTraceSteps.value.length && (!traceStepperTouched.value || activeTraceStepIndex.value >= agentTraceSteps.value.length)) {
    activeTraceStepIndex.value = latestTraceIndex.value
  }
  if (props.message.status === "success" && agentTraceSteps.value.length && !agentTracePanelTouched.value) {
    agentTracePanelOpen.value = []
  }
  if ((props.message.status === "sending" || props.message.status === "error") && agentTraceSteps.value.length && !agentTracePanelTouched.value) {
    agentTracePanelOpen.value = ["agent-trace"]
  }
}

watch(
  () => [
    props.message.status,
    agentTraceSteps.value.length,
    agentTraceSteps.value.map(item => `${item.stage}:${item.status}:${item.message}`).join("|"),
  ],
  syncTraceCollapseState,
  { immediate: true }
)

watch(
  () => Boolean(attributionResult.value),
  () => {
    const nextPanels = new Set(analysisResultPanels.value)
    if (attributionResult.value) nextPanels.add("anomaly-attribution")
    analysisResultPanels.value = Array.from(nextPanels)
  }
)

watch(
  () => hasResult.value,
  (ready) => {
    if (ready && !props.message.fromHistory) void runAttributionPrecheck()
  },
  { immediate: true }
)

const formatTraceDetail = (detail: Record<string, unknown>) => {
  return JSON.stringify(detail, null, 2)
}

const fetchActionAssignableUsers = async () => {
  if (actionAssignableUsers.value.length || actionAssignableLoading.value) return
  actionAssignableLoading.value = true
  try {
    const response = await axios.get("/api/users/assignable")
    actionAssignableUsers.value = response.data || []
  } catch {
    ElMessage.warning("负责人列表加载失败，已保留当前登录用户作为默认负责人")
  } finally {
    actionAssignableLoading.value = false
  }
}

const openActionDialog = async () => {
  const question = props.message.sourceQuestion || "跟进分析结论"
  actionForm.title = question.length > 36 ? `${question.slice(0, 36)}...` : question
  actionForm.description = props.message.summary || props.message.content || "请根据本次问数结果安排后续跟进。"
  actionForm.priority = props.message.trustSignals?.some(signal => signal.quality_status === "error") ? "high" : "medium"
  actionForm.due_date = ""
  actionForm.owner_id = authStore.profile?.id || null
  actionForm.linked_metric_id = props.message.trustSignals?.[0]?.metric_id || null
  actionDialogVisible.value = true
  await fetchActionAssignableUsers()
}

const createActionItem = async () => {
  if (!actionForm.title.trim()) {
    ElMessage.warning("请输入行动项标题")
    return
  }
  actionSaving.value = true
  try {
    await axios.post("/api/action-items", {
      title: actionForm.title.trim(),
      description: actionForm.description || null,
      source_type: "query",
      source_id: props.message.historyId ? String(props.message.historyId) : props.message.id,
      source_payload: {
        question: props.message.sourceQuestion,
        summary: props.message.summary || props.message.content,
        sql_query: props.message.sqlQuery,
        row_count: props.message.result?.rows?.length || 0,
      },
      owner_id: actionForm.owner_id,
      priority: actionForm.priority,
      due_date: actionForm.due_date || null,
      linked_metric_id: actionForm.linked_metric_id,
    })
    ElMessage.success("行动项已创建")
    actionDialogVisible.value = false
    router.push("/action-items")
  } catch (error: any) {
    ElMessage.error(error.response?.data?.detail || "行动项创建失败")
  } finally {
    actionSaving.value = false
  }
}

const runAttributionPrecheck = async () => {
  if (!props.message.result || !hasResult.value || attributionPrecheckLoading.value) return
  const columns = props.message.result.columns || []
  const rows = props.message.result.rows || []
  const nextKey = `${props.message.id}:${columns.join("|")}:${rows.length}:${props.message.sqlQuery || ""}`
  if (attributionPrecheckKey.value === nextKey) return
  attributionPrecheckKey.value = nextKey
  attributionPrecheckLoading.value = true
  try {
    const res = await axios.post<AnomalyPrecheckResponse>("/api/insights/anomaly-precheck", {
      columns,
      rows,
      question: props.message.sourceQuestion || props.message.content,
      sql_query: props.message.sqlQuery,
    }, { suppressGlobalError: true } as any)
    attributionPrecheckResult.value = res.data
  } catch {
    attributionPrecheckResult.value = {
      status: "normal",
      has_anomaly: false,
      metric_column: null,
      time_column: null,
      anomaly_count: 0,
      anomalies: [],
      summary: "轻量预检暂不可用，可直接查看图表或手动做贡献分析。",
      severity: "info",
      confidence: "low",
      recommended_action: "contribution_analysis",
      action_label: "贡献分析",
      llm_enhanced: false,
      llm_model: null,
    }
  } finally {
    attributionPrecheckLoading.value = false
  }
}

const runAttribution = async () => {
  if (!props.message.result) return
  attributionLoading.value = true
  try {
    const res = await axios.post("/api/insights/anomaly-attribution", {
      columns: props.message.result.columns,
      rows: props.message.result.rows,
      question: props.message.sourceQuestion || props.message.content,
      sql_query: props.message.sqlQuery,
      metric_column: attributionPrecheckResult.value?.metric_column || null,
      analysis_mode: attributionAnalysisMode.value,
    })
    attributionResult.value = res.data
  } catch (error: any) {
    ElMessage.error(error.response?.data?.detail || `${attributionPanelTitle.value}生成失败`)
  } finally {
    attributionLoading.value = false
  }
}

const openAttributionDialog = async () => {
  if (!hasResult.value) return
  attributionDialogVisible.value = true
  if (!attributionResult.value && !attributionLoading.value && !attributionActionDisabled.value) {
    await runAttribution()
  }
}

const fillMetricDraftForm = (draft: MetricDraftResponse) => {
  const candidate = draft.candidate || {}
  metricDraftForm.dataset_id = draft.source.source_dataset_id || draft.source.dataset_binding?.dataset_id || null
  metricDraftForm.name = candidate.name || props.message.sourceQuestion?.slice(0, 64) || "探索沉淀指标"
  metricDraftForm.definition = candidate.definition || props.message.summary || "从探索模式问数结果沉淀的指标"
  metricDraftForm.formula = candidate.formula || ""
  metricDraftForm.unit = candidate.unit || ""
  metricDraftForm.selected_metric_column = candidate.metric_column || draft.source.source_metric_column || ""
  metricDraftForm.dimensions = [...(candidate.dimensions || [])]
  metricDraftForm.time_column = candidate.time_column || ""
}

const openMetricDraftDrawer = async () => {
  if (!props.message.historyId) {
    ElMessage.warning("当前结果缺少查询历史，无法保存指标")
    return
  }
  metricDraftDrawerVisible.value = true
  metricDraftLoading.value = true
  metricDraftResponse.value = null
  metricDraftWarnings.value = []
  metricDraftDatasetMissing.value = false
  metricDraftDatasetError.value = ""
  try {
    const res = await axios.post<MetricDraftResponse>("/api/metrics/from-query/draft", {
      query_history_id: props.message.historyId,
    }, { suppressGlobalError: true } as any)
    metricDraftResponse.value = res.data
    metricDraftWarnings.value = res.data.warnings || []
    fillMetricDraftForm(res.data)
  } catch (error: any) {
    const detail = error.response?.data?.detail || "指标草稿生成失败"
    const message = typeof detail === "string" ? detail : detail?.message || "指标草稿生成失败"
    if (message.includes("没有可绑定的同源数据集") || message.includes("先创建基础数据集")) {
      metricDraftDatasetMissing.value = true
      metricDraftDatasetError.value = message
      return
    }
    ElMessage.error(message)
    metricDraftDrawerVisible.value = false
  } finally {
    metricDraftLoading.value = false
  }
}

const saveMetricDraft = async () => {
  if (!props.message.historyId) return
  if (!metricDraftForm.dataset_id) {
    metricDraftDatasetMissing.value = true
    metricDraftDatasetError.value = "当前数据源下没有可绑定的同源数据集，请先创建基础数据集。"
    return
  }
  if (!metricDraftForm.name.trim() || !metricDraftForm.definition.trim() || !metricDraftForm.formula.trim()) {
    ElMessage.warning("请完善指标名称、定义和公式")
    return
  }
  metricDraftSaving.value = true
  try {
    await axios.post("/api/metrics/from-query", {
      query_history_id: props.message.historyId,
      dataset_id: metricDraftForm.dataset_id,
      name: metricDraftForm.name.trim(),
      definition: metricDraftForm.definition.trim(),
      formula: metricDraftForm.formula.trim(),
      unit: metricDraftForm.unit.trim() || null,
      selected_metric_column: metricDraftForm.selected_metric_column || null,
      selected_dimensions: metricDraftForm.dimensions,
      dimensions: metricDraftForm.dimensions,
      time_column: metricDraftForm.time_column || null,
      status: "draft",
      certification_status: "pending_review",
    })
    ElMessage.success("指标草稿已保存")
    metricDraftDrawerVisible.value = false
  } catch (error: any) {
    ElMessage.error(error.response?.data?.detail || "指标草稿保存失败")
  } finally {
    metricDraftSaving.value = false
  }
}

const openDatasetBuilderForMetric = () => {
  metricDraftDrawerVisible.value = false
  datasetBuilderVisible.value = true
}

const handleMetricDatasetCreated = async () => {
  datasetBuilderVisible.value = false
  if (!props.message.historyId) return
  await openMetricDraftDrawer()
}

const safePercentage = (value: number) => {
  const numericValue = Number(value)
  if (!Number.isFinite(numericValue)) return 0
  return Math.max(0, Math.min(Math.round(numericValue), 100))
}

const formatContribution = (value: number) => {
  const numericValue = Number(value)
  if (!Number.isFinite(numericValue)) return String(value)
  return new Intl.NumberFormat("zh-CN", { maximumFractionDigits: 2 }).format(numericValue)
}

const driverImpactLabel = (impact: string) => (impact === "negative" ? "负向" : "正向")

const driverImpactProgressStatus = (impact: string) => {
  return impact === "negative" ? "exception" : "success"
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

const formatTime = (date: Date) => {
  const d = new Date(date)
  return d.toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" })
}
</script>

<style scoped>
.chat-bubble {
  display: flex;
  gap: 12px;
  margin-bottom: 20px;
  max-width: 85%;
  animation: fadeInUp 0.3s ease-out;
}

@keyframes fadeInUp {
  from {
    opacity: 0;
    transform: translateY(10px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.chat-bubble--user {
  flex-direction: row-reverse;
  margin-left: auto;
}

.chat-bubble--assistant {
  flex-direction: row;
  margin-right: auto;
}

.chat-bubble--assistant.chat-bubble--with-result {
  width: min(100%, 980px);
  max-width: calc(100% - 6px);
}

.chat-avatar {
  flex-shrink: 0;
}

.avatar-user {
  background: #0f766e;
  color: #fff;
  font-weight: 600;
}

.avatar-assistant {
  background: #102033;
  color: #fff;
  font-weight: 600;
}

.chat-content {
  display: flex;
  flex-direction: column;
  gap: 10px;
  min-width: 0;
}

.chat-bubble--user .chat-content {
  align-items: flex-end;
}

.chat-bubble--assistant .chat-content {
  align-items: flex-start;
}

.chat-bubble--with-result .chat-content {
  flex: 1 1 auto;
  width: 100%;
}

.chat-bubble--with-result .assistant-content {
  width: 100%;
  min-width: 0;
}

.bubble-text {
  background: var(--app-surface-muted);
  padding: 14px 18px;
  border-radius: 16px;
  line-height: 1.7;
  word-break: break-word;
  white-space: pre-wrap;
  font-size: 14px;
}

.chat-bubble--user .bubble-text {
  background: var(--app-primary);
  color: #fff;
  border-bottom-right-radius: 6px;
  box-shadow: 0 4px 12px rgba(15, 118, 110, 0.18);
}

.chat-bubble--assistant .bubble-text {
  background: var(--app-surface);
  border: 1px solid var(--app-border-light);
  border-bottom-left-radius: 6px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.04);
}

.chat-loading {
  display: flex;
  flex-direction: column;
  align-items: stretch;
  gap: 12px;
  padding: 14px 18px;
  background: var(--app-surface);
  border: 1px solid var(--app-border-light);
  border-radius: 16px;
  color: var(--app-text-muted);
}

.chat-loading-line {
  display: flex;
  align-items: center;
  gap: 10px;
}

.chat-loading .el-icon {
  color: var(--app-primary);
}

.chat-error {
  display: flex;
  flex-direction: column;
  align-items: stretch;
  gap: 12px;
  padding: 14px 18px;
  background: #fef2f2;
  border: 1px solid #fecaca;
  border-radius: 16px;
  color: #ef4444;
}

.chat-error-line {
  display: flex;
  align-items: center;
  gap: 10px;
}

.chat-time {
  font-size: 11px;
  color: var(--app-text-light);
}

.assistant-content {
  display: flex;
  flex-direction: column;
  gap: 14px;
  width: 100%;
}

.drill-context {
  display: inline-flex;
  align-items: flex-start;
  gap: 8px;
  padding: 8px 12px;
  border-radius: 16px;
  background: #ecfdf5;
  color: #0f766e;
  font-size: 12px;
  border: 1px solid #b7e4d8;
}

.drill-context-label {
  font-weight: 600;
}

.drill-context-arrow {
  margin: 0 4px;
}

.drill-context-body {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.drill-back-btn {
  padding: 0;
}

.model-chip {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  border-radius: 999px;
  background: #f8fafc;
  border: 1px solid #dbe4f0;
  color: #334155;
  font-size: 12px;
}

.model-chip-label {
  color: #64748b;
  font-weight: 500;
}

.model-chip-value {
  font-family: "JetBrains Mono", "Fira Code", "Consolas", monospace;
  font-size: 12px;
  color: #0f172a;
}

.assumption-panel,
.empty-diagnostics-panel {
  width: 100%;
  padding: 12px;
  border: 1px solid #b7e4d8;
  border-radius: 12px;
  background: #f0fdfa;
}

.assumption-panel-head,
.empty-diagnostics-head {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr);
  gap: 10px;
  align-items: flex-start;
}

.assumption-icon,
.empty-diagnostics-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 30px;
  height: 30px;
  border-radius: 8px;
  color: #0f766e;
  background: #ccfbf1;
}

.assumption-panel-head strong,
.empty-diagnostics-head strong {
  display: block;
  color: #134e4a;
  font-size: 13px;
}

.assumption-panel-head span,
.empty-diagnostics-head span {
  display: block;
  margin-top: 3px;
  color: #475569;
  font-size: 12px;
  line-height: 1.5;
}

.assumption-list,
.assumption-risk-list,
.empty-check-list {
  display: grid;
  gap: 6px;
}

.assumption-list span,
.assumption-risk-list span,
.empty-check-list span {
  position: relative;
  padding-left: 14px;
  color: #334155;
  font-size: 12px;
  line-height: 1.5;
}

.assumption-list span::before,
.empty-check-list span::before {
  content: "";
  position: absolute;
  left: 1px;
  top: 8px;
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: #0f766e;
}

.assumption-risk-list {
  margin-top: 8px;
}

.assumption-risk-list span {
  color: #92400e;
}

.assumption-risk-list span::before {
  content: "";
  position: absolute;
  left: 0;
  top: 7px;
  width: 7px;
  height: 7px;
  border-radius: 2px;
  background: #f59e0b;
}

.refinement-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 10px;
}

.refinement-actions button {
  min-height: 32px;
  padding: 0 10px;
  border: 1px solid #99f6e4;
  border-radius: 999px;
  color: #0f766e;
  background: #ffffff;
  font-size: 12px;
  font-weight: 700;
  cursor: pointer;
  transition: transform 0.18s ease, box-shadow 0.18s ease, background 0.18s ease;
}

.refinement-actions button:hover {
  transform: translateY(-1px);
  background: #ccfbf1;
  box-shadow: 0 8px 18px rgba(15, 118, 110, 0.12);
}

.assumption-refinement-workbench {
  display: grid;
  gap: 10px;
  margin-top: 12px;
  padding: 12px;
  border: 1px solid #d7efe8;
  border-radius: 14px;
  background: #ffffff;
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.8);
}

.assumption-refinement-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.assumption-refinement-head strong {
  display: block;
  color: #0f172a;
  font-size: 13px;
}

.assumption-refinement-head span {
  display: block;
  margin-top: 3px;
  color: #64748b;
  font-size: 12px;
  line-height: 1.5;
}

.assumption-refinement-actions {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  flex-shrink: 0;
}

.assumption-refinement-actions button,
.agent-notes-secondary,
.agent-notes-primary {
  min-height: 34px;
  padding: 0 12px;
  border: 1px solid #b7e4d8;
  border-radius: 10px;
  font-size: 12px;
  font-weight: 800;
  cursor: pointer;
  transition: transform 0.18s ease, box-shadow 0.18s ease, background 0.18s ease, border-color 0.18s ease;
}

.assumption-refinement-actions button,
.agent-notes-secondary {
  color: #0f766e;
  background: #f8fffc;
}

.assumption-refinement-actions button:hover,
.agent-notes-secondary:hover {
  transform: translateY(-1px);
  border-color: #5eead4;
  background: #ecfdf5;
  box-shadow: 0 10px 20px rgba(15, 118, 110, 0.1);
}

.refinement-draft-item {
  display: grid;
  grid-template-columns: minmax(132px, 0.36fr) minmax(0, 1fr);
  gap: 12px;
  align-items: stretch;
  padding: 10px;
  border: 1px solid #dbe4f0;
  border-radius: 12px;
  background: #f8fafc;
  transition: border-color 0.18s ease, box-shadow 0.18s ease, background 0.18s ease;
}

.refinement-draft-editor.is-selected {
  border-color: #99f6e4;
  background: #f8fffc;
  box-shadow: 0 10px 24px rgba(15, 118, 110, 0.08);
}

.refinement-draft-check {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
  color: #0f172a;
  font-size: 12px;
  font-weight: 800;
  line-height: 1.45;
  cursor: pointer;
}

.refinement-draft-check input {
  width: 16px;
  height: 16px;
  margin: 0;
  flex: 0 0 auto;
  accent-color: #0f766e;
}

.refinement-draft-check span {
  min-width: 0;
  word-break: break-word;
}

.refinement-draft-textarea :deep(.el-textarea__inner),
.assumption-custom-field :deep(.el-textarea__inner) {
  min-height: 52px;
  border-color: #d7efe8;
  border-radius: 10px;
  color: #0f172a;
  font-size: 12px;
  line-height: 1.55;
  box-shadow: none;
}

.refinement-draft-textarea :deep(.el-textarea__inner:focus),
.assumption-custom-field :deep(.el-textarea__inner:focus) {
  border-color: #0f766e;
  box-shadow: 0 0 0 3px rgba(15, 118, 110, 0.12);
}

.assumption-custom-field,
.assumption-batch-preview {
  display: grid;
  gap: 6px;
}

.assumption-custom-field > span,
.assumption-batch-preview > span {
  color: #475569;
  font-size: 12px;
  font-weight: 800;
}

.assumption-batch-preview {
  padding: 10px;
  border: 1px dashed #99f6e4;
  border-radius: 12px;
  background: #f0fdfa;
}

.assumption-batch-preview pre {
  max-height: 150px;
  margin: 0;
  overflow: auto;
  color: #134e4a;
  font-family: inherit;
  font-size: 12px;
  line-height: 1.6;
  white-space: pre-wrap;
  word-break: break-word;
}

.agent-notes-footer {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}

.agent-notes-primary {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  border-color: #0f766e;
  color: #ffffff;
  background: #0f766e;
}

.agent-notes-primary:hover:not(:disabled) {
  transform: translateY(-1px);
  border-color: #115e59;
  background: #115e59;
  box-shadow: 0 12px 24px rgba(15, 118, 110, 0.22);
}

.agent-notes-primary:disabled {
  cursor: not-allowed;
  opacity: 0.55;
  box-shadow: none;
}

.empty-diagnostics-panel {
  display: grid;
  gap: 10px;
  border-color: #fde68a;
  background: #fffbeb;
}

.empty-diagnostics-icon {
  color: #92400e;
  background: #fef3c7;
}

.empty-diagnostics-head strong {
  color: #78350f;
}

.empty-actions button {
  border-color: #fde68a;
  color: #92400e;
}

.empty-actions button:hover {
  background: #fef3c7;
  box-shadow: 0 8px 18px rgba(146, 64, 14, 0.12);
}

.agent-trace-collapse {
  width: 100%;
  border: 1px solid #99f6e4;
  border-radius: 12px;
  background: #f0fdfa;
  overflow: hidden;
}

.agent-trace-collapse :deep(.el-collapse-item__header) {
  min-height: 46px;
  height: auto;
  padding: 0 12px;
  background: #f0fdfa;
  border-bottom: 0;
}

.agent-trace-collapse :deep(.el-collapse-item__wrap) {
  background: #f0fdfa;
  border-bottom: 0;
}

.agent-trace-collapse :deep(.el-collapse-item__content) {
  padding: 0 12px 12px;
}

.agent-trace-title {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  width: 100%;
  min-width: 0;
}

.agent-trace-title span {
  color: #0f766e;
  font-weight: 700;
}

.agent-trace-title small {
  color: #64748b;
  font-weight: 500;
  white-space: nowrap;
}

.agent-trace-compact {
  display: grid;
  gap: 8px;
  padding: 10px;
  margin-bottom: 8px;
  border: 1px solid #99f6e4;
  border-radius: 10px;
  background: #ffffff;
  box-shadow: 0 8px 18px rgba(15, 118, 110, 0.08);
}

.trace-summary-strip {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  align-items: center;
  gap: 10px;
  min-width: 0;
}

.trace-summary-main {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}

.trace-summary-main strong {
  min-width: 0;
  overflow: hidden;
  color: #0f172a;
  font-size: 13px;
  font-weight: 800;
  line-height: 1.35;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.trace-summary-chips {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 6px;
  flex-wrap: wrap;
}

.trace-summary-chip,
.trace-stage-pill,
.trace-step-index {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: 24px;
  padding: 0 8px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 800;
  line-height: 1;
  white-space: nowrap;
}

.trace-summary-chip {
  color: #475569;
  border: 1px solid #dbe4f0;
  background: #f8fafc;
}

.trace-summary-chip--status,
.trace-stage-pill {
  color: #0f766e;
  border: 1px solid #99f6e4;
  background: #ccfbf1;
}

.trace-summary-chip--warning {
  color: #92400e;
  border-color: #fde68a;
  background: #fffbeb;
}

.trace-summary-chip--error {
  color: #991b1b;
  border-color: #fecaca;
  background: #fff7f7;
}

.trace-stage-pill--soft {
  color: #0f766e;
  border-color: #ccfbf1;
  background: #f0fdfa;
}

.trace-step-index {
  min-width: 34px;
  color: #64748b;
  border: 1px solid #e2e8f0;
  background: #f8fafc;
  font-variant-numeric: tabular-nums;
}

.trace-progress-line {
  height: 4px;
  overflow: hidden;
  border-radius: 999px;
  background: #e2e8f0;
}

.trace-progress-line i {
  display: block;
  height: 100%;
  border-radius: inherit;
  background: linear-gradient(90deg, #0f766e 0%, #14b8a6 100%);
  transition: width 0.24s ease;
}

.trace-dashboard--pending .trace-summary-chip--status {
  color: #0e7490;
  border-color: #a5f3fc;
  background: #cffafe;
  animation: tracePulse 1.2s ease-in-out infinite;
}

.trace-dashboard--warning .trace-summary-chip--status {
  color: #92400e;
  border-color: #fde68a;
  background: #fef3c7;
}

.trace-dashboard--error .trace-summary-chip--status {
  color: #991b1b;
  border-color: #fecaca;
  background: #fee2e2;
}

@keyframes tracePulse {
  0%,
  100% {
    transform: scale(1);
    opacity: 0.86;
  }
  50% {
    transform: scale(1.03);
    opacity: 1;
  }
}

.trace-stepper {
  position: relative;
  display: grid;
  grid-auto-flow: column;
  grid-auto-columns: minmax(92px, 1fr);
  gap: 10px;
  min-width: 0;
  overflow-x: auto;
  padding: 10px 2px 4px;
  scrollbar-width: thin;
}

.trace-stepper-track {
  position: absolute;
  top: 32px;
  left: 46px;
  right: 46px;
  height: 3px;
  overflow: hidden;
  border-radius: 999px;
  background: #dbe4f0;
  pointer-events: none;
}

.trace-stepper-track i {
  display: block;
  height: 100%;
  border-radius: inherit;
  background: linear-gradient(90deg, #0f766e 0%, #14b8a6 100%);
  transition: width 0.24s ease;
}

.trace-stepper-node {
  position: relative;
  z-index: 1;
  min-width: 92px;
  display: grid;
  justify-items: center;
  gap: 5px;
  padding: 0;
  border: 0;
  background: transparent;
  color: #64748b;
  cursor: pointer;
  text-align: center;
  touch-action: manipulation;
}

.trace-stepper-node:focus-visible {
  outline: 3px solid rgba(15, 118, 110, 0.2);
  outline-offset: 3px;
  border-radius: 12px;
}

.trace-stepper-circle {
  position: relative;
  width: 46px;
  height: 46px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: 2px solid #ccfbf1;
  border-radius: 999px;
  background: #ffffff;
  box-shadow: 0 8px 18px rgba(15, 23, 42, 0.08);
  transition: transform 0.18s ease, border-color 0.18s ease, box-shadow 0.18s ease, background 0.18s ease;
}

.trace-stepper-icon {
  width: 22px;
  height: 22px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  color: #0f766e;
  font-size: 20px;
  line-height: 1;
  transition: color 0.18s ease, transform 0.18s ease;
}

.trace-stepper-icon :deep(svg) {
  width: 1em;
  height: 1em;
}

.trace-stepper-node--pending .trace-stepper-icon {
  color: #0891b2;
}

.trace-stepper-node--warning .trace-stepper-icon {
  color: #d97706;
}

.trace-stepper-node--error .trace-stepper-icon {
  color: #dc2626;
}

.trace-stepper-circle .trace-step-dot {
  position: absolute;
  right: 3px;
  bottom: 3px;
  margin-left: 0;
}

.trace-stepper-node:hover .trace-stepper-circle,
.trace-stepper-node--active .trace-stepper-circle {
  transform: translateY(-2px);
  border-color: #0f766e;
  background: #f0fdfa;
  box-shadow: 0 12px 24px rgba(15, 118, 110, 0.16);
}

.trace-stepper-node--pending .trace-stepper-circle {
  border-color: #a5f3fc;
}

.trace-stepper-node--warning .trace-stepper-circle {
  border-color: #fde68a;
  background: #fffbeb;
}

.trace-stepper-node--error .trace-stepper-circle {
  border-color: #fecaca;
  background: #fff7f7;
}

.trace-stepper-label {
  max-width: 96px;
  overflow: hidden;
  color: #0f172a;
  font-size: 12px;
  font-weight: 800;
  line-height: 1.25;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.trace-stepper-node small {
  color: #64748b;
  font-size: 11px;
  font-weight: 700;
}

.trace-stepper-node--active .trace-stepper-label,
.trace-stepper-node--active small {
  color: #0f766e;
}

.trace-selected-panel {
  display: grid;
  gap: 9px;
  min-width: 0;
  padding: 10px;
  border: 1px solid #dbe4f0;
  border-radius: 10px;
  background: #f8fafc;
}

.trace-selected-panel--success {
  border-color: #99f6e4;
  background: #f0fdfa;
}

.trace-selected-panel--pending {
  border-color: #a5f3fc;
  background: #ecfeff;
}

.trace-selected-panel--warning {
  border-color: #fde68a;
  background: #fffbeb;
}

.trace-selected-panel--error {
  border-color: #fecaca;
  background: #fff7f7;
}

.trace-selected-meta {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
}

.trace-step-dot {
  position: relative;
  z-index: 1;
  width: 9px;
  height: 9px;
  margin-left: 1px;
  border: 2px solid #ffffff;
  border-radius: 999px;
  background: #0f766e;
  box-shadow: 0 0 0 2px #ccfbf1;
}

.trace-step-dot--pending {
  background: #0891b2;
}

.trace-step-dot--warning {
  background: #d97706;
  box-shadow: 0 0 0 2px #fde68a;
}

.trace-step-dot--error {
  background: #dc2626;
  box-shadow: 0 0 0 2px #fecaca;
}

.trace-row-message {
  display: grid;
  gap: 2px;
  min-width: 0;
}

.trace-row-message strong {
  min-width: 0;
  overflow: hidden;
  color: #0f172a;
  font-size: 12px;
  font-weight: 700;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.trace-selected-panel .trace-row-message strong {
  white-space: normal;
}

.trace-detail {
  max-height: 220px;
  overflow: auto;
  margin: 0;
  padding: 10px;
  background: #0f172a;
  color: #dbeafe;
  font-family: "JetBrains Mono", "Fira Code", "Consolas", monospace;
  font-size: 11px;
  line-height: 1.55;
  white-space: pre-wrap;
  word-break: break-word;
}

.trace-detail-panel {
  border: 1px solid rgba(15, 23, 42, 0.08);
  border-radius: 8px;
}

.trust-panel {
  width: 100%;
  padding: 12px;
  border: 1px solid #c7d2fe;
  border-radius: 12px;
  background: #f8fafc;
}

.trust-panel-title {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: center;
  margin-bottom: 10px;
}

.trust-panel-title span {
  font-weight: 600;
  color: #1e3a8a;
}

.trust-panel-title small {
  color: #64748b;
}

.trust-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.trust-item {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 8px 12px;
  padding: 10px;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  background: #fff;
}

.trust-item-main {
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 0;
}

.trust-item-main strong {
  color: #0f172a;
}

.trust-item-main span,
.trust-item p {
  color: #64748b;
  font-size: 12px;
  line-height: 1.5;
}

.trust-tags {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 6px;
}

.trust-item p {
  grid-column: 1 / -1;
  margin: 0;
}

.summary-box {
  background: linear-gradient(135deg, #ecfdf5 0%, #d1fae5 100%);
  border: 1px solid #a7f3d0;
  border-radius: 12px;
  padding: 16px;
}

.summary-box--clickable {
  cursor: pointer;
  transition: transform 0.18s ease, border-color 0.18s ease, box-shadow 0.18s ease;
}

.summary-box--clickable:hover {
  transform: translateY(-1px);
  border-color: #0f766e;
  box-shadow: 0 12px 28px rgba(15, 118, 110, 0.12);
}

.summary-box--clickable:focus-visible {
  outline: 3px solid rgba(15, 118, 110, 0.22);
  outline-offset: 2px;
}

.summary-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-weight: 600;
  color: #059669;
  margin-bottom: 10px;
}

.summary-title small {
  margin-left: auto;
  color: #0f766e;
  font-size: 12px;
  font-weight: 800;
}

.summary-text {
  color: var(--app-text);
  line-height: 1.7;
}

.summary-text.markdown-body {
  font-size: 14px;
}

.summary-text.markdown-body :deep(h1),
.summary-text.markdown-body :deep(h2),
.summary-text.markdown-body :deep(h3) {
  margin: 14px 0 10px;
  font-weight: 600;
  color: var(--app-text);
}

.summary-text.markdown-body :deep(h1) { font-size: 18px; }
.summary-text.markdown-body :deep(h2) { font-size: 16px; }
.summary-text.markdown-body :deep(h3) { font-size: 15px; }

.summary-text.markdown-body :deep(p) {
  margin: 10px 0;
}

.summary-text.markdown-body :deep(ul),
.summary-text.markdown-body :deep(ol) {
  padding-left: 20px;
  margin: 10px 0;
}

.summary-text.markdown-body :deep(li) {
  margin: 6px 0;
}

.summary-text.markdown-body :deep(code) {
  background: rgba(0, 0, 0, 0.06);
  padding: 2px 6px;
  border-radius: 4px;
  font-family: "JetBrains Mono", "Fira Code", monospace;
  font-size: 13px;
}

.summary-text.markdown-body :deep(pre) {
  background: #1e1b4b;
  color: #e0e7ff;
  padding: 14px;
  border-radius: 8px;
  overflow-x: auto;
}

.summary-text.markdown-body :deep(pre code) {
  background: transparent;
  padding: 0;
}

.summary-text.markdown-body :deep(table) {
  width: 100%;
  border-collapse: collapse;
  margin: 14px 0;
}

.summary-text.markdown-body :deep(th),
.summary-text.markdown-body :deep(td) {
  border: 1px solid var(--app-border);
  padding: 10px 14px;
  text-align: left;
}

.summary-text.markdown-body :deep(th) {
  background: var(--app-surface-muted);
  font-weight: 600;
}

.summary-text.markdown-body :deep(strong) {
  font-weight: 600;
  color: var(--app-text);
}

.compact-result-actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
}

.compact-result-actions--loading,
.compact-result-actions--error {
  margin-top: 8px;
}

.result-mini-action-button {
  min-height: 32px;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 0 10px;
  border: 1px solid #dbe4f0;
  border-radius: 999px;
  background: #ffffff;
  color: #334155;
  font-size: 12px;
  font-weight: 800;
  cursor: pointer;
  touch-action: manipulation;
  transition: transform 0.16s ease, border-color 0.16s ease, background 0.16s ease, color 0.16s ease, box-shadow 0.16s ease;
}

.result-mini-action-button:hover:not(:disabled) {
  transform: translateY(-1px);
  border-color: #99f6e4;
  background: #f0fdfa;
  color: #0f766e;
  box-shadow: 0 8px 18px rgba(15, 118, 110, 0.1);
}

.result-mini-action-button:focus-visible {
  outline: 3px solid rgba(15, 118, 110, 0.22);
  outline-offset: 2px;
}

.result-mini-action-button:disabled {
  cursor: not-allowed;
  opacity: 0.62;
  transform: none;
}

.result-mini-action-button small {
  color: #64748b;
  font-weight: 700;
}

.result-mini-action--notes,
.result-mini-action--trace {
  border-color: #99f6e4;
  color: #0f766e;
  background: #f8fffd;
}

.result-mini-action--action {
  border-color: #c7d2fe;
  color: #3730a3;
  background: #f8f7ff;
}

.result-mini-action--attribution {
  border-color: #fde68a;
  color: #92400e;
  background: #fffdf5;
}

.result-mini-action-beta-badge {
  min-height: 18px;
  display: inline-flex;
  align-items: center;
  padding: 0 6px;
  border: 1px solid #fcd34d;
  border-radius: 999px;
  background: #fef3c7;
  color: #92400e;
  font-size: 10px;
  font-weight: 900;
  line-height: 1;
  letter-spacing: 0;
}

.result-mini-action--metric .metric-beta-badge {
  border-color: #fdba74;
  background: #ffedd5;
  color: #9a3412;
}

.result-mini-action--metric {
  border-color: #fed7aa;
  color: #9a3412;
  background: #fff7ed;
}

.modal-loading-state,
.modal-empty-state {
  display: grid;
  justify-items: center;
  gap: 10px;
  min-height: 160px;
  align-content: center;
  padding: 18px;
  color: #475569;
  text-align: center;
}

.modal-loading-state .el-icon {
  color: #0f766e;
  font-size: 22px;
}

.modal-empty-state strong {
  color: #0f172a;
  font-size: 15px;
}

.modal-empty-state p {
  max-width: 520px;
  margin: 0;
  color: #64748b;
  font-size: 13px;
  line-height: 1.6;
}

.attribution-panel-collapse {
  width: 100%;
  border: 1px solid #dbe4f0;
  border-radius: 12px;
  background: #fff;
  overflow: hidden;
}

.attribution-panel-collapse :deep(.el-collapse-item__header) {
  min-height: 48px;
  height: auto;
  padding: 0 14px;
  background: #fff;
  border-bottom: 1px solid #eef2f7;
}

.attribution-panel-collapse :deep(.el-collapse-item__content) {
  padding: 12px 14px 14px;
}

.attribution-collapse-title {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  width: 100%;
  min-width: 0;
}

.attribution-collapse-title > div {
  display: flex;
  align-items: baseline;
  gap: 8px;
  min-width: 0;
}

.attribution-collapse-title span {
  color: var(--app-text);
  font-weight: 700;
}

.attribution-collapse-title small {
  color: var(--app-text-muted);
  font-size: 12px;
}

.attribution-section {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.attribution-summary-card {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: flex-start;
  padding: 10px;
  border: 1px solid var(--app-border-light);
  border-radius: 8px;
  background: var(--app-surface-muted);
}

.attribution-summary-card > div {
  min-width: 0;
}

.attribution-summary-card span {
  display: block;
  color: var(--app-text);
  font-size: 12px;
  font-weight: 700;
}

.attribution-summary-card p {
  margin: 4px 0 0;
  color: var(--app-text-muted);
  font-size: 12px;
  line-height: 1.6;
}

.driver-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.driver-item strong {
  display: block;
  color: var(--app-text);
  font-size: 13px;
}

.driver-item span {
  margin: 4px 0 0;
  color: var(--app-text-muted);
  font-size: 12px;
  line-height: 1.5;
}

.attribution-overview {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 8px;
}

.attribution-overview div {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 10px;
  border: 1px solid var(--app-border-light);
  border-radius: 8px;
  background: #fff;
}

.attribution-overview span {
  color: var(--app-text-muted);
  font-size: 12px;
}

.attribution-overview strong {
  color: var(--app-text);
  font-size: 13px;
  word-break: break-word;
}

.driver-item {
  display: grid;
  grid-template-columns: minmax(0, 220px) minmax(160px, 1fr);
  gap: 12px;
  align-items: center;
  padding: 10px;
  border: 1px solid var(--app-border-light);
  border-radius: 8px;
  background: #fff;
}

.driver-main {
  min-width: 0;
}

.driver-progress {
  display: grid;
  gap: 4px;
}

.driver-progress small {
  color: var(--app-text-muted);
  font-size: 11px;
  text-align: right;
}

.recommendation-strip {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.recommendation-strip span {
  padding: 6px 10px;
  border-radius: 999px;
  background: #f8fafc;
  color: #475569;
  font-size: 12px;
  border: 1px solid #e2e8f0;
}

.metric-draft-loading {
  display: flex;
  align-items: center;
  gap: 10px;
  min-height: 120px;
  color: var(--app-text-muted);
}

.metric-draft-empty-dataset {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr);
  gap: 12px;
  padding: 16px;
  border: 1px solid #99f6e4;
  border-radius: 12px;
  background: #f0fdfa;
}

.metric-draft-empty-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 38px;
  height: 38px;
  border-radius: 10px;
  color: #0f766e;
  background: #ccfbf1;
}

.metric-draft-empty-dataset span {
  display: block;
  color: #0f766e;
  font-size: 12px;
  font-weight: 800;
}

.metric-draft-empty-dataset strong {
  display: block;
  margin-top: 4px;
  color: #0f172a;
  font-size: 15px;
}

.metric-draft-empty-dataset p {
  margin: 6px 0 0;
  color: #475569;
  font-size: 12px;
  line-height: 1.6;
}

.metric-draft-create-dataset {
  grid-column: 1 / -1;
  min-height: 40px;
  border: 0;
  border-radius: 10px;
  color: #ffffff;
  background: #0f766e;
  font-weight: 800;
  cursor: pointer;
  transition: transform 0.18s ease, box-shadow 0.18s ease, background 0.18s ease;
}

.metric-draft-create-dataset:hover {
  transform: translateY(-1px);
  background: #0d9488;
  box-shadow: 0 10px 22px rgba(15, 118, 110, 0.16);
}

.metric-draft-hero {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  padding: 14px;
  margin-bottom: 12px;
  border: 1px solid #fde68a;
  border-radius: 10px;
  background: #fffbeb;
}

.metric-draft-hero div {
  min-width: 0;
}

.metric-draft-hero span {
  display: block;
  color: #92400e;
  font-size: 12px;
  font-weight: 700;
}

.metric-draft-hero strong {
  display: block;
  margin-top: 4px;
  color: #0f172a;
  font-size: 16px;
  word-break: break-word;
}

.metric-draft-hero .metric-draft-dataset {
  display: block;
  margin-top: 5px;
  color: #0f766e;
  font-size: 12px;
  font-weight: 600;
}

.metric-draft-hero p {
  margin: 6px 0 0;
  color: #475569;
  font-size: 12px;
  line-height: 1.6;
}

.metric-draft-checklist {
  display: grid;
  gap: 10px;
  padding: 12px;
  margin-bottom: 12px;
  border: 1px solid var(--app-border-light);
  border-radius: 10px;
  background: #fff;
}

.metric-draft-checklist-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  color: var(--app-text);
  font-size: 13px;
  font-weight: 700;
}

.metric-draft-checklist-items {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.metric-draft-checklist-items span {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 5px 8px;
  border: 1px solid #e2e8f0;
  border-radius: 999px;
  color: #64748b;
  background: #f8fafc;
  font-size: 12px;
}

.metric-draft-checklist-items span.is-done {
  color: #047857;
  border-color: #a7f3d0;
  background: #ecfdf5;
}

.metric-draft-warnings {
  display: grid;
  gap: 8px;
  margin-bottom: 14px;
}

.metric-field-hint {
  margin-top: 6px;
  color: var(--app-text-muted);
  font-size: 12px;
  line-height: 1.5;
}

.metric-draft-source {
  margin-top: 8px;
  padding: 14px;
  border: 1px solid var(--app-border-light);
  border-radius: 8px;
  background: var(--app-surface-muted);
}

.metric-draft-source-title {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
}

.metric-draft-source-title span {
  color: var(--app-text);
  font-weight: 700;
}

.metric-draft-source-grid {
  display: grid;
  grid-template-columns: 88px minmax(0, 1fr);
  gap: 8px 12px;
  font-size: 13px;
}

.metric-draft-source-grid span {
  color: var(--app-text-muted);
}

.metric-draft-source-grid strong {
  min-width: 0;
  color: var(--app-text);
  word-break: break-word;
}

.metric-draft-evidence {
  margin-top: 12px;
  border-radius: 8px;
  overflow: hidden;
}

.metric-draft-evidence pre {
  margin: 0;
  padding: 12px;
  background: #0f172a;
  color: #dbeafe;
  font-family: "JetBrains Mono", "Fira Code", "Consolas", monospace;
  font-size: 12px;
  line-height: 1.6;
  white-space: pre-wrap;
  word-break: break-word;
}

.chart-container,
.table-container {
  background: var(--app-surface);
  border: 1px solid var(--app-border-light);
  border-radius: 12px;
  overflow: hidden;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.04);
}

.result-inline-panel {
  display: grid;
  width: 100%;
  min-width: 0;
}

.result-inline-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  padding: 9px 12px;
  border-bottom: 1px solid var(--app-border-light);
  background: #f8fafc;
}

.result-inline-toolbar span {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  color: #334155;
  font-size: 12px;
  font-weight: 800;
}

.result-inline-toolbar-actions {
  display: inline-flex;
  align-items: center;
  justify-content: flex-end;
  flex-wrap: wrap;
  gap: 4px;
}

.result-inline-toolbar :deep(.el-button) {
  color: #0f766e;
  font-weight: 800;
}

.result-inline-toolbar :deep(.el-button:hover) {
  color: #0d9488;
  background: #ccfbf1;
}

:global(.result-detail-dialog.el-dialog),
:global(.result-detail-dialog .el-dialog) {
  border-radius: 14px;
  overflow: hidden;
}

:global(.result-detail-dialog.el-dialog .el-dialog__header),
:global(.result-detail-dialog .el-dialog__header) {
  padding: 18px 20px 12px;
  margin: 0;
  border-bottom: 1px solid #eef2f7;
}

:global(.result-detail-dialog.el-dialog .el-dialog__title),
:global(.result-detail-dialog .el-dialog__title) {
  color: #0f172a;
  font-size: 16px;
  font-weight: 800;
}

:global(.result-detail-dialog.el-dialog .el-dialog__body),
:global(.result-detail-dialog .el-dialog__body) {
  padding: 16px 18px 18px;
}

.result-detail-summary {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 14px;
  padding: 14px;
  margin-bottom: 12px;
  border: 1px solid #ccfbf1;
  border-radius: 12px;
  background: #f0fdfa;
}

.result-detail-summary > div:first-child {
  display: grid;
  gap: 4px;
  min-width: 0;
}

.result-detail-summary span {
  color: #0f766e;
  font-size: 12px;
  font-weight: 800;
}

.result-detail-summary strong {
  color: #0f172a;
  font-size: 14px;
  line-height: 1.5;
  word-break: break-word;
}

.result-detail-metrics {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 6px;
}

.result-detail-metrics span {
  display: inline-flex;
  align-items: center;
  min-height: 26px;
  padding: 0 9px;
  border: 1px solid #99f6e4;
  border-radius: 999px;
  background: #ffffff;
  color: #475569;
  white-space: nowrap;
}

.result-detail-tabs {
  min-height: 460px;
}

.result-detail-tabs :deep(.el-tabs__item) {
  color: #64748b;
  font-weight: 700;
}

.result-detail-tabs :deep(.el-tabs__item.is-active) {
  color: #0f766e;
}

.result-detail-tabs :deep(.el-tabs__active-bar) {
  background: #0f766e;
}

.result-detail-pane {
  min-height: 420px;
  padding: 12px 0 0;
}

.result-detail-pane--chart {
  min-height: 460px;
}

.result-detail-sql {
  max-height: 520px;
  overflow: auto;
  margin: 0;
  padding: 14px;
  border-radius: 10px;
  background: #0f172a;
  color: #dbeafe;
  font-family: "JetBrains Mono", "Fira Code", "Consolas", monospace;
  font-size: 12px;
  line-height: 1.65;
  white-space: pre-wrap;
  word-break: break-word;
}

.result-detail-summary-text {
  max-height: 520px;
  overflow: auto;
  padding: 14px;
  border: 1px solid var(--app-border-light);
  border-radius: 10px;
  background: #ffffff;
}

.recommendations {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 10px;
}

.rec-label {
  font-size: 13px;
  color: var(--app-text-muted);
  font-weight: 500;
}

.recommendations :deep(.el-tag) {
  border-radius: 20px;
  padding: 4px 12px;
}

@media (max-width: 640px) {
  .result-detail-summary,
  .metric-draft-hero,
  .attribution-summary-card {
    align-items: stretch;
    flex-direction: column;
  }

  .refinement-draft-item {
    grid-template-columns: 1fr;
  }

  .assumption-refinement-head,
  .agent-notes-footer {
    align-items: stretch;
    flex-direction: column;
  }

  .assumption-refinement-actions,
  .agent-notes-secondary,
  .agent-notes-primary {
    width: 100%;
  }

  .result-detail-metrics {
    justify-content: flex-start;
  }

  .attribution-overview,
  .trace-summary-chips {
    grid-template-columns: 1fr;
  }

  .metric-draft-empty-dataset {
    grid-template-columns: 1fr;
  }

  .driver-item {
    grid-template-columns: 1fr;
  }
}
</style>
