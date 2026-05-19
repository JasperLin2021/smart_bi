<template>
  <div class="chat-bubble" :class="[`chat-bubble--${message.role}`, { 'chat-bubble--error': message.status === 'error' }]">
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
        <el-collapse v-model="agentTracePanelOpen" class="agent-trace-collapse" v-if="message.agentTrace?.length" @change="handleTracePanelChange">
          <el-collapse-item name="agent-trace">
            <template #title>
              <div class="agent-trace-title">
                <span>探索模式执行过程</span>
                <small>{{ traceSummary }}</small>
              </div>
            </template>
            <div class="trace-current-card" v-if="latestTraceStep" :class="`trace-current-card--${latestTraceStep.status}`">
              <div class="trace-current-head">
                <el-tag size="small" :type="traceStatusType(latestTraceStep.status)" effect="plain">
                  {{ traceStageLabel(latestTraceStep.stage) }}
                </el-tag>
                <div class="trace-step-main trace-current-main">
                  <span>{{ latestTraceStep.message }}</span>
                  <small>最新 · {{ traceStatusLabel(latestTraceStep.status) }}</small>
                </div>
              </div>
              <el-collapse v-model="traceDetailOpen" class="trace-detail-collapse" v-if="latestTraceStep.detail">
                <el-collapse-item :name="traceStepName(latestTraceStep, latestTraceIndex)" title="查看详情">
                  <pre class="trace-detail">{{ formatTraceDetail(latestTraceStep.detail) }}</pre>
                </el-collapse-item>
              </el-collapse>
            </div>
            <el-collapse v-if="historicalTraceSteps.length" v-model="traceHistoryOpen" class="trace-history-collapse">
              <el-collapse-item name="trace-history">
                <template #title>
                  <div class="trace-history-title">
                    <span>历史步骤</span>
                    <small>{{ historicalTraceSteps.length }} 步已折叠</small>
                  </div>
                </template>
                <div class="trace-list trace-list--history">
                  <div
                    v-for="step in historicalTraceSteps"
                    :key="`${step.item.stage}-${step.item.message}-${step.index}`"
                    class="trace-step"
                    :class="`trace-step--${step.item.status}`"
                  >
                    <el-tag size="small" :type="traceStatusType(step.item.status)" effect="plain">
                      {{ traceStageLabel(step.item.stage) }}
                    </el-tag>
                    <div class="trace-step-main">
                      <span>{{ step.item.message }}</span>
                      <small>{{ traceStatusLabel(step.item.status) }}</small>
                    </div>
                    <el-collapse v-model="traceDetailOpen" class="trace-detail-collapse" v-if="step.item.detail">
                      <el-collapse-item :name="traceStepName(step.item, step.index)" title="查看详情">
                        <pre class="trace-detail">{{ formatTraceDetail(step.item.detail) }}</pre>
                      </el-collapse-item>
                    </el-collapse>
                  </div>
                </div>
              </el-collapse-item>
            </el-collapse>
          </el-collapse-item>
        </el-collapse>
      </div>
      
      <!-- 错误状态 -->
      <div v-else-if="message.status === 'error'" class="chat-error">
        <div class="chat-error-line">
          <el-icon><WarningFilled /></el-icon>
          <span>{{ message.error || '请求失败，请重试' }}</span>
        </div>
        <el-collapse v-model="agentTracePanelOpen" class="agent-trace-collapse" v-if="message.agentTrace?.length" @change="handleTracePanelChange">
          <el-collapse-item name="agent-trace">
            <template #title>
              <div class="agent-trace-title">
                <span>探索模式执行过程</span>
                <small>{{ traceSummary }}</small>
              </div>
            </template>
            <div class="trace-current-card" v-if="latestTraceStep" :class="`trace-current-card--${latestTraceStep.status}`">
              <div class="trace-current-head">
                <el-tag size="small" :type="traceStatusType(latestTraceStep.status)" effect="plain">
                  {{ traceStageLabel(latestTraceStep.stage) }}
                </el-tag>
                <div class="trace-step-main trace-current-main">
                  <span>{{ latestTraceStep.message }}</span>
                  <small>最新 · {{ traceStatusLabel(latestTraceStep.status) }}</small>
                </div>
              </div>
              <el-collapse v-model="traceDetailOpen" class="trace-detail-collapse" v-if="latestTraceStep.detail">
                <el-collapse-item :name="traceStepName(latestTraceStep, latestTraceIndex)" title="查看详情">
                  <pre class="trace-detail">{{ formatTraceDetail(latestTraceStep.detail) }}</pre>
                </el-collapse-item>
              </el-collapse>
            </div>
            <el-collapse v-if="historicalTraceSteps.length" v-model="traceHistoryOpen" class="trace-history-collapse">
              <el-collapse-item name="trace-history">
                <template #title>
                  <div class="trace-history-title">
                    <span>历史步骤</span>
                    <small>{{ historicalTraceSteps.length }} 步已折叠</small>
                  </div>
                </template>
                <div class="trace-list trace-list--history">
                  <div
                    v-for="step in historicalTraceSteps"
                    :key="`${step.item.stage}-${step.item.message}-${step.index}`"
                    class="trace-step"
                    :class="`trace-step--${step.item.status}`"
                  >
                    <el-tag size="small" :type="traceStatusType(step.item.status)" effect="plain">
                      {{ traceStageLabel(step.item.stage) }}
                    </el-tag>
                    <div class="trace-step-main">
                      <span>{{ step.item.message }}</span>
                      <small>{{ traceStatusLabel(step.item.status) }}</small>
                    </div>
                    <el-collapse v-model="traceDetailOpen" class="trace-detail-collapse" v-if="step.item.detail">
                      <el-collapse-item :name="traceStepName(step.item, step.index)" title="查看详情">
                        <pre class="trace-detail">{{ formatTraceDetail(step.item.detail) }}</pre>
                      </el-collapse-item>
                    </el-collapse>
                  </div>
                </div>
              </el-collapse-item>
            </el-collapse>
          </el-collapse-item>
        </el-collapse>
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
          <div v-if="message.content" class="bubble-text">
            {{ message.content }}
          </div>

          <div v-if="message.llmModel" class="model-chip">
            <span class="model-chip-label">实际模型</span>
            <code class="model-chip-value">{{ message.llmModel }}</code>
          </div>

          <div v-if="hasAgentNotes" class="assumption-panel">
            <div class="assumption-panel-head">
              <div class="assumption-icon">
                <el-icon><MagicStick /></el-icon>
              </div>
              <div>
                <strong>已按 {{ agentAssumptionCount }} 个默认假设完成查询</strong>
                <span>{{ agentConfidenceText }}</span>
              </div>
            </div>
            <el-collapse v-model="agentNotesPanelOpen" class="assumption-collapse">
              <el-collapse-item name="agent-notes" title="查看假设与可调整项">
                <div v-if="agentAssumptions.length" class="assumption-list">
                  <span v-for="item in agentAssumptions" :key="item">{{ item }}</span>
                </div>
                <div v-if="agentRiskFlags.length" class="assumption-risk-list">
                  <span v-for="item in agentRiskFlags" :key="item">{{ riskFlagLabel(item) }}</span>
                </div>
                <div v-if="agentRefinementActions.length" class="refinement-actions">
                  <button
                    v-for="action in agentRefinementActions"
                    :key="`${action.label}-${action.question}`"
                    type="button"
                    @click="runRefinement(action.question)"
                  >
                    {{ action.label }}
                  </button>
                </div>
              </el-collapse-item>
            </el-collapse>
          </div>

          <el-collapse v-model="agentTracePanelOpen" class="agent-trace-collapse" v-if="message.agentTrace?.length" @change="handleTracePanelChange">
            <el-collapse-item name="agent-trace">
              <template #title>
                <div class="agent-trace-title">
                  <span>探索模式执行过程</span>
                  <small>{{ traceSummary }}</small>
                </div>
              </template>
              <div class="trace-current-card" v-if="latestTraceStep" :class="`trace-current-card--${latestTraceStep.status}`">
                <div class="trace-current-head">
                  <el-tag size="small" :type="traceStatusType(latestTraceStep.status)" effect="plain">
                    {{ traceStageLabel(latestTraceStep.stage) }}
                  </el-tag>
                  <div class="trace-step-main trace-current-main">
                    <span>{{ latestTraceStep.message }}</span>
                    <small>最新 · {{ traceStatusLabel(latestTraceStep.status) }}</small>
                  </div>
                </div>
                <el-collapse v-model="traceDetailOpen" class="trace-detail-collapse" v-if="latestTraceStep.detail">
                  <el-collapse-item :name="traceStepName(latestTraceStep, latestTraceIndex)" title="查看详情">
                    <pre class="trace-detail">{{ formatTraceDetail(latestTraceStep.detail) }}</pre>
                  </el-collapse-item>
                </el-collapse>
              </div>
              <el-collapse v-if="historicalTraceSteps.length" v-model="traceHistoryOpen" class="trace-history-collapse">
                <el-collapse-item name="trace-history">
                  <template #title>
                    <div class="trace-history-title">
                      <span>历史步骤</span>
                      <small>{{ historicalTraceSteps.length }} 步已折叠</small>
                    </div>
                  </template>
                  <div class="trace-list trace-list--history">
                    <div
                      v-for="step in historicalTraceSteps"
                      :key="`${step.item.stage}-${step.item.message}-${step.index}`"
                      class="trace-step"
                      :class="`trace-step--${step.item.status}`"
                    >
                      <el-tag size="small" :type="traceStatusType(step.item.status)" effect="plain">
                        {{ traceStageLabel(step.item.stage) }}
                      </el-tag>
                      <div class="trace-step-main">
                        <span>{{ step.item.message }}</span>
                        <small>{{ traceStatusLabel(step.item.status) }}</small>
                      </div>
                      <el-collapse v-model="traceDetailOpen" class="trace-detail-collapse" v-if="step.item.detail">
                        <el-collapse-item :name="traceStepName(step.item, step.index)" title="查看详情">
                          <pre class="trace-detail">{{ formatTraceDetail(step.item.detail) }}</pre>
                        </el-collapse-item>
                      </el-collapse>
                    </div>
                  </div>
                </el-collapse-item>
              </el-collapse>
            </el-collapse-item>
          </el-collapse>

          <div v-if="message.trustSignals?.length" class="trust-panel">
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
          
          <!-- SQL 查询 (可折叠) -->
          <el-collapse v-if="message.sqlQuery" class="sql-collapse">
            <el-collapse-item title="技术细节 / SQL 查询语句" name="sql">
              <pre class="sql-code">{{ message.sqlQuery }}</pre>
            </el-collapse-item>
          </el-collapse>
          
          <!-- 分析总结 -->
          <div v-if="message.summary && message.summary !== message.content" class="summary-box">
            <div class="summary-title">
              <el-icon><DataAnalysis /></el-icon>
              <span>分析总结</span>
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
                @click="runRefinement(action.question)"
              >
                {{ action.label }}
              </button>
            </div>
          </div>

          <div v-if="canCreateAction" class="decision-action-bar">
            <div>
              <strong>生成行动项</strong>
              <span>把这次分析结论交给责任人跟踪处理</span>
            </div>
            <el-button size="small" type="primary" plain :icon="Tickets" @click="openActionDialog">
              创建
            </el-button>
          </div>

          <div v-if="hasResult" class="analysis-action-card">
            <div class="analysis-action-header">
              <div>
                <strong>结果操作</strong>
                <span>{{ analysisMetaText }}</span>
              </div>
              <el-tag size="small" type="info" effect="plain">{{ analysisStatusText }}</el-tag>
            </div>
            <div class="analysis-action-groups">
              <section class="analysis-action-group">
                <div class="analysis-group-label">
                  <el-icon><MagicStick /></el-icon>
                  <span>智能分析</span>
                </div>
                <div class="analysis-buttons">
                  <el-button size="small" type="primary" plain :loading="insightLoading" :icon="DataAnalysis" @click="runAutoInsights">
                    自动洞察
                  </el-button>
                  <el-button size="small" plain :loading="attributionLoading" :icon="Aim" @click="runAttribution">
                    异常归因
                  </el-button>
                </div>
              </section>
              <section v-if="props.message.historyId" class="analysis-action-group">
                <div class="analysis-group-label">
                  <el-icon><CollectionTag /></el-icon>
                  <span>沉淀资产</span>
                </div>
                <div class="analysis-buttons">
                  <el-button size="small" plain :loading="metricDraftLoading" :icon="DocumentAdd" @click="openMetricDraftDrawer">
                    保存为指标
                  </el-button>
                  <el-button size="small" plain :icon="CollectionTag" @click="openInsightDialog">
                    保存为洞察
                  </el-button>
                </div>
              </section>
            </div>
          </div>

          <el-collapse v-if="insightResult || attributionResult" v-model="analysisResultPanels" class="insight-panel-collapse">
            <el-collapse-item v-if="insightResult" name="auto-insights">
              <template #title>
                <div class="insight-collapse-title">
                  <div>
                    <span>自动洞察</span>
                    <small>{{ insightCountText }}</small>
                  </div>
                  <el-tag v-if="insightEnhancementLabel" size="small" type="success" effect="plain">
                    {{ insightEnhancementLabel }}
                  </el-tag>
                </div>
              </template>
              <section class="insight-section">
                <div class="insight-summary-card">
                  <div>
                    <span>摘要</span>
                    <p>{{ insightResult.summary }}</p>
                  </div>
                  <el-tag size="small" effect="plain">{{ insightModelLabel }}</el-tag>
                </div>
                <div v-if="insightResult.insights.length" class="insight-list">
                  <div v-for="item in insightResult.insights" :key="`${item.type}-${item.title}`" class="insight-item">
                    <el-tag size="small" :type="insightTagType(item.severity)" effect="light">{{ insightSeverityLabel(item.severity) }}</el-tag>
                    <div>
                      <strong>{{ item.title }}</strong>
                      <p>{{ item.description }}</p>
                    </div>
                  </div>
                </div>
                <el-empty v-else description="暂未发现显著洞察" :image-size="56" />
              </section>
            </el-collapse-item>
            <el-collapse-item v-if="attributionResult" name="anomaly-attribution">
              <template #title>
                <div class="insight-collapse-title">
                  <div>
                    <span>异常归因</span>
                    <small>{{ attributionDriverCountText }}</small>
                  </div>
                  <el-tag v-if="attributionEnhancementLabel" size="small" type="success" effect="plain">
                    {{ attributionEnhancementLabel }}
                  </el-tag>
                </div>
              </template>
              <section class="insight-section">
                <div class="insight-summary-card">
                  <div>
                    <span>归因结论</span>
                    <p>{{ attributionResult.summary }}</p>
                  </div>
                  <el-tag size="small" :type="attributionConfidenceType" effect="plain">
                    {{ attributionConfidenceLabel }}
                  </el-tag>
                </div>
                <div class="attribution-overview">
                  <div>
                    <span>归因指标</span>
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
            </el-collapse-item>
          </el-collapse>
          
          <!-- 查询结果图表 -->
          <div v-if="hasResult" class="chart-container">
            <MessageChart 
              :message="message"
              :columns="message.result!.columns" 
              :rows="message.result!.rows" 
              :sql-query="message.sqlQuery"
              :chart-spec="message.chartSpec"
            />
          </div>
          
          <!-- 查询结果表格 -->
          <div v-if="hasResult" class="table-container">
            <MessageTable :message="message" :columns="message.result!.columns" :rows="message.result!.rows" />
          </div>
          
          <!-- 推荐标签 -->
          <div v-if="message.recommendations?.length" class="recommendations">
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
      width="min(560px, calc(100vw - 32px))"
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
        <el-form-item label="负责人 ID">
          <el-input-number v-model="actionForm.owner_id" :min="1" style="width: 180px" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="actionDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="actionSaving" @click="createActionItem">创建行动项</el-button>
      </template>
    </el-dialog>

    <!-- Save as insight dialog -->
    <el-dialog
      v-model="saveInsightDialogVisible"
      title="保存为洞察"
      width="min(520px, calc(100vw - 32px))"
      destroy-on-close
      class="save-insight-dialog"
    >
      <div class="save-insight-intro">
        <el-icon><CollectionTag /></el-icon>
        <div>
          <strong>把本次分析沉淀为洞察</strong>
          <span>洞察将保存到查询洞察列表，保留问题、SQL、图表和结果上下文，方便复盘或继续生成行动项。</span>
        </div>
      </div>
      <el-form label-position="top" @submit.prevent>
        <el-form-item label="洞察标题" required>
          <el-input v-model="insightTitle" maxlength="100" show-word-limit placeholder="为这条查询结果起个有意义的名字" />
        </el-form-item>
        <el-form-item label="来源摘要">
          <el-input :model-value="insightSourceSummary" type="textarea" :rows="3" disabled />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="saveInsightDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="savingInsight" :disabled="!insightTitle.trim()" @click="doSaveInsight">保存洞察</el-button>
      </template>
    </el-dialog>

    <el-drawer
      v-model="metricDraftDrawerVisible"
      title="保存为指标草稿"
      size="min(560px, 100vw)"
      destroy-on-close
      class="metric-draft-drawer"
    >
      <div v-if="metricDraftLoading" class="metric-draft-loading">
        <el-icon class="is-loading"><Loading /></el-icon>
        <span>正在识别可沉淀指标...</span>
      </div>
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
        <el-button type="primary" :loading="metricDraftSaving" :disabled="metricDraftLoading" @click="saveMetricDraft">
          保存指标草稿
        </el-button>
      </template>
    </el-drawer>
  </div>
</template>

<script setup lang="ts">
import { computed, reactive, ref, watch } from "vue"
import axios from "axios"
import { useRouter } from "vue-router"
import { ElMessage } from "element-plus"
import {
  Aim,
  CircleCheck,
  CollectionTag,
  DataAnalysis,
  DocumentAdd,
  Loading,
  MagicStick,
  Tickets,
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
import MessageChart from "./MessageChart.vue"
import MessageTable from "./MessageTable.vue"

const props = defineProps<{
  message: ChatMessage
}>()

const queryStore = useQueryStore()
const authStore = useAuthStore()
const router = useRouter()
const actionDialogVisible = ref(false)
const actionSaving = ref(false)
const saveInsightDialogVisible = ref(false)
const insightTitle = ref("")
const savingInsight = ref(false)
const metricDraftDrawerVisible = ref(false)
const metricDraftLoading = ref(false)
const metricDraftSaving = ref(false)
const metricDraftResponse = ref<MetricDraftResponse | null>(null)
const metricDraftWarnings = ref<string[]>([])
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

const openInsightDialog = () => {
  insightTitle.value = insightTitle.value.trim() || defaultInsightTitle.value
  saveInsightDialogVisible.value = true
}

const doSaveInsight = async () => {
  if (!props.message.historyId) return
  if (!insightTitle.value.trim()) {
    ElMessage.warning("请输入洞察标题")
    return
  }
  savingInsight.value = true
  try {
    await axios.post("/api/query/save-insight", {
      history_id: props.message.historyId,
      title: insightTitle.value.trim(),
    })
    ElMessage.success("已保存为洞察")
    saveInsightDialogVisible.value = false
    insightTitle.value = ""
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || "保存失败")
  } finally {
    savingInsight.value = false
  }
}
const actionForm = reactive({
  title: "",
  description: "",
  priority: "medium",
  due_date: "",
  owner_id: null as number | null,
  linked_metric_id: null as number | null,
})
const insightLoading = ref(false)
const attributionLoading = ref(false)
const insightResult = ref<AutoInsightResponse | null>(null)
const attributionResult = ref<AttributionResponse | null>(null)
const analysisResultPanels = ref<string[]>([])

interface AutoInsightResponse {
  summary: string
  insights: Array<{
    type: string
    title: string
    description: string
    severity: string
  }>
  metadata: Record<string, unknown> & {
    llm_enhanced?: boolean
    llm_model?: string | null
  }
}

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

const agentNotesPanelOpen = ref<string[]>([])
const agentAssumptions = computed(() => props.message.agentNotes?.assumptions || [])
const agentRiskFlags = computed(() => props.message.agentNotes?.risk_flags || [])
const agentRefinementActions = computed<AgenticRefinementAction[]>(() => props.message.agentNotes?.suggested_refinements || [])
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

const emptyDiagnosticChecks = computed(() => props.message.emptyDiagnostics?.checks || [])
const emptyDiagnosticActions = computed<AgenticRefinementAction[]>(() => props.message.emptyDiagnostics?.suggested_actions || [])
const hasEmptyDiagnostics = computed(() =>
  props.message.status === "success" &&
  !hasResult.value &&
  Boolean(emptyDiagnosticChecks.value.length || emptyDiagnosticActions.value.length)
)

const resultRowCount = computed(() => props.message.result?.rows?.length || 0)
const resultColumnCount = computed(() => props.message.result?.columns?.length || 0)

const analysisMetaText = computed(() => `${resultRowCount.value} 行结果 · ${resultColumnCount.value} 个字段`)

const analysisStatusText = computed(() => {
  if (insightLoading.value) return "正在生成自动洞察"
  if (attributionLoading.value) return "正在分析异常归因"
  if (insightResult.value && attributionResult.value) return "已完成洞察与归因"
  if (insightResult.value) return "已生成自动洞察"
  if (attributionResult.value) return "已生成异常归因"
  return "可继续分析或沉淀"
})

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

const defaultInsightTitle = computed(() => {
  const source = props.message.sourceQuestion || props.message.content || "查询洞察"
  return source.length > 80 ? `${source.slice(0, 80)}...` : source
})

const insightSourceSummary = computed(() => {
  const question = props.message.sourceQuestion || props.message.content || "未记录问题"
  const rowText = `${resultRowCount.value} 行结果`
  const summary = props.message.summary || "暂无分析总结"
  return `问题：${question}\n结果：${rowText}\n总结：${summary}`
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

const insightEnhancementLabel = computed(() =>
  insightResult.value?.metadata?.llm_enhanced ? "大模型增强" : ""
)

const attributionEnhancementLabel = computed(() =>
  attributionResult.value?.llm_enhanced ? "大模型增强" : ""
)

const insightCountText = computed(() => `${insightResult.value?.insights?.length || 0} 条洞察`)

const insightModelLabel = computed(() => {
  const model = insightResult.value?.metadata?.llm_model
  return model ? `模型 ${model}` : "规则识别"
})

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
const traceDetailOpen = ref<string[]>([])
const traceHistoryOpen = ref<string[]>([])
const agentTracePanelTouched = ref(false)
const agentTraceSteps = computed(() => props.message.agentTrace || [])
const latestTraceIndex = computed(() => agentTraceSteps.value.length - 1)
const latestTraceStep = computed((): AgentTraceStep | null => (
  latestTraceIndex.value >= 0 ? agentTraceSteps.value[latestTraceIndex.value] : null
))
const historicalTraceSteps = computed(() => (
  agentTraceSteps.value.slice(0, -1).map((item, index) => ({ item, index }))
))
const failedTraceCount = computed(() => agentTraceSteps.value.filter(item => item.status === "error").length)
const pendingTraceCount = computed(() => agentTraceSteps.value.filter(item => item.status === "pending").length)
const warningTraceCount = computed(() => agentTraceSteps.value.filter(item => item.status === "warning").length)

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

const runRefinement = async (question: string) => {
  const refinedQuestion = question.trim()
  if (!refinedQuestion || queryStore.loading) return
  await queryStore.ask(
    refinedQuestion,
    "agentic",
    undefined,
    props.message.historyId || null,
  )
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

const traceStatusType = (status: string) => {
  const types: Record<string, "success" | "warning" | "info" | "danger"> = {
    success: "success",
    warning: "warning",
    error: "danger",
    pending: "info",
  }
  return types[status] || "info"
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

const traceStepName = (item: AgentTraceStep, index: number) => {
  return `${index}-${item.stage}-${item.status}`
}

const normalizeCollapseValue = (value: string | number | Array<string | number>) => {
  if (Array.isArray(value)) return value.map(String)
  return value ? [String(value)] : []
}

const handleTracePanelChange = (value: string | number | Array<string | number>) => {
  agentTracePanelTouched.value = true
  agentTracePanelOpen.value = normalizeCollapseValue(value)
}

// 失败步骤自动展开，成功步骤保留折叠。
const defaultTraceDetailNames = () => {
  return agentTraceSteps.value
    .map((item, index) => (item.status === "error" && item.detail ? traceStepName(item, index) : ""))
    .filter(Boolean)
}

const syncTraceCollapseState = () => {
  const errorNames = defaultTraceDetailNames()
  if (errorNames.length) {
    traceDetailOpen.value = Array.from(new Set([...traceDetailOpen.value, ...errorNames]))
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
  () => [Boolean(insightResult.value), Boolean(attributionResult.value)],
  () => {
    const nextPanels = new Set(analysisResultPanels.value)
    if (insightResult.value) nextPanels.add("auto-insights")
    if (attributionResult.value) nextPanels.add("anomaly-attribution")
    analysisResultPanels.value = Array.from(nextPanels)
  }
)

const formatTraceDetail = (detail: Record<string, unknown>) => {
  return JSON.stringify(detail, null, 2)
}

const openActionDialog = () => {
  const question = props.message.sourceQuestion || "跟进分析结论"
  actionForm.title = question.length > 36 ? `${question.slice(0, 36)}...` : question
  actionForm.description = props.message.summary || props.message.content || "请根据本次问数结果安排后续跟进。"
  actionForm.priority = props.message.trustSignals?.some(signal => signal.quality_status === "error") ? "high" : "medium"
  actionForm.due_date = ""
  actionForm.owner_id = authStore.profile?.id || null
  actionForm.linked_metric_id = props.message.trustSignals?.[0]?.metric_id || null
  actionDialogVisible.value = true
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

const runAutoInsights = async () => {
  if (!props.message.result) return
  insightLoading.value = true
  try {
    const res = await axios.post("/api/insights/auto-insights", {
      columns: props.message.result.columns,
      rows: props.message.result.rows,
      question: props.message.sourceQuestion || props.message.content,
      sql_query: props.message.sqlQuery,
    })
    insightResult.value = res.data
  } catch (error: any) {
    ElMessage.error(error.response?.data?.detail || "自动洞察生成失败")
  } finally {
    insightLoading.value = false
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
    })
    attributionResult.value = res.data
  } catch (error: any) {
    ElMessage.error(error.response?.data?.detail || "异常归因生成失败")
  } finally {
    attributionLoading.value = false
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
  try {
    const res = await axios.post<MetricDraftResponse>("/api/metrics/from-query/draft", {
      query_history_id: props.message.historyId,
    })
    metricDraftResponse.value = res.data
    metricDraftWarnings.value = res.data.warnings || []
    fillMetricDraftForm(res.data)
  } catch (error: any) {
    ElMessage.error(error.response?.data?.detail || "指标草稿生成失败")
    metricDraftDrawerVisible.value = false
  } finally {
    metricDraftLoading.value = false
  }
}

const saveMetricDraft = async () => {
  if (!props.message.historyId) return
  if (!metricDraftForm.dataset_id) {
    ElMessage.warning("当前结果未绑定数据集，请先创建基础数据集")
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

const insightSeverityLabel = (severity: string) => {
  const labels: Record<string, string> = {
    success: "机会",
    warning: "关注",
    danger: "风险",
    info: "洞察",
  }
  return labels[severity] || "洞察"
}

const insightTagType = (severity: string) => {
  const types: Record<string, "success" | "warning" | "info" | "danger"> = {
    success: "success",
    warning: "warning",
    danger: "danger",
    info: "info",
  }
  return types[severity] || "info"
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
}

.chat-bubble--user .chat-content {
  align-items: flex-end;
}

.chat-bubble--assistant .chat-content {
  align-items: flex-start;
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

.sql-collapse {
  background: var(--app-surface);
  border-radius: 12px;
  border: 1px solid var(--app-border-light);
  overflow: hidden;
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

.assumption-collapse {
  margin-top: 8px;
  border: 0;
  background: transparent;
}

.assumption-collapse :deep(.el-collapse-item__header) {
  min-height: 34px;
  height: auto;
  padding: 0;
  border: 0;
  background: transparent;
  color: #0f766e;
  font-size: 12px;
  font-weight: 700;
}

.assumption-collapse :deep(.el-collapse-item__wrap) {
  border: 0;
  background: transparent;
}

.assumption-collapse :deep(.el-collapse-item__content) {
  padding: 4px 0 0;
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

.trace-current-card {
  display: grid;
  gap: 8px;
  padding: 10px;
  border: 1px solid #99f6e4;
  border-left: 3px solid #0f766e;
  border-radius: 10px;
  background: #ffffff;
  box-shadow: 0 8px 20px rgba(15, 118, 110, 0.08);
}

.trace-current-head {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr);
  align-items: start;
  gap: 8px 10px;
}

.trace-step-main.trace-current-main span {
  color: #0f172a;
  font-weight: 600;
  white-space: normal;
  word-break: break-word;
}

.trace-step-main.trace-current-main small {
  color: #0f766e;
}

.trace-current-card--error {
  border-color: #fecaca;
  border-left-color: #dc2626;
  box-shadow: 0 8px 20px rgba(220, 38, 38, 0.08);
}

.trace-current-card--warning {
  border-color: #fde68a;
  border-left-color: #d97706;
  box-shadow: 0 8px 20px rgba(217, 119, 6, 0.08);
}

.trace-current-card--pending {
  border-color: #99f6e4;
  border-left-color: #0891b2;
}

.trace-history-collapse {
  margin-top: 8px;
  border: 1px solid #ccfbf1;
  border-radius: 10px;
  background: rgba(255, 255, 255, 0.72);
  overflow: hidden;
}

.trace-history-collapse :deep(.el-collapse-item__header) {
  min-height: 38px;
  height: auto;
  padding: 0 10px;
  background: rgba(255, 255, 255, 0.72);
  border-bottom: 0;
}

.trace-history-collapse :deep(.el-collapse-item__wrap) {
  border-bottom: 0;
  background: rgba(255, 255, 255, 0.72);
}

.trace-history-collapse :deep(.el-collapse-item__content) {
  padding: 0 10px 10px;
}

.trace-history-title {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  width: 100%;
  min-width: 0;
}

.trace-history-title span {
  color: #0f766e;
  font-size: 12px;
  font-weight: 700;
}

.trace-history-title small {
  color: #64748b;
  font-size: 11px;
  font-weight: 500;
  white-space: nowrap;
}

.trace-list {
  display: grid;
  gap: 8px;
}

.trace-step {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr);
  align-items: start;
  gap: 8px 10px;
  padding: 8px 10px;
  border: 1px solid #dbe4f0;
  border-radius: 8px;
  background: #fff;
  color: #334155;
  font-size: 12px;
}

.trace-step-main {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}

.trace-step-main span {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.trace-step-main small {
  color: #64748b;
  font-size: 11px;
}

.trace-detail-collapse {
  grid-column: 1 / -1;
  border: 1px solid #dbe4f0;
  border-radius: 8px;
  overflow: hidden;
  background: #f8fafc;
}

.trace-detail-collapse :deep(.el-collapse-item__header) {
  min-height: 34px;
  height: auto;
  padding: 0 10px;
  background: #f8fafc;
  color: #475569;
  font-size: 12px;
  font-weight: 500;
}

.trace-detail-collapse :deep(.el-collapse-item__wrap) {
  border-bottom: 0;
}

.trace-detail-collapse :deep(.el-collapse-item__content) {
  padding: 0;
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

.trace-step--error {
  border-color: #fecaca;
  background: #fff7f7;
}

.trace-step--warning {
  border-color: #fde68a;
  background: #fffbeb;
}

.trace-step--pending {
  border-color: #bfdbfe;
  background: #f8fbff;
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

.sql-collapse :deep(.el-collapse-item__header) {
  padding: 0 16px;
  font-size: 13px;
  height: 44px;
  font-weight: 500;
  color: var(--app-text);
}

.sql-collapse :deep(.el-collapse-item__content) {
  padding: 0;
}

.sql-code {
  background: #1e1b4b;
  color: #e0e7ff;
  padding: 16px;
  border-radius: 0 0 12px 12px;
  font-family: "JetBrains Mono", "Fira Code", "Consolas", monospace;
  font-size: 13px;
  overflow-x: auto;
  margin: 0;
  white-space: pre-wrap;
  word-break: break-all;
  line-height: 1.6;
}

.summary-box {
  background: linear-gradient(135deg, #ecfdf5 0%, #d1fae5 100%);
  border: 1px solid #a7f3d0;
  border-radius: 12px;
  padding: 16px;
}

.summary-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-weight: 600;
  color: #059669;
  margin-bottom: 10px;
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

.decision-action-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 12px 14px;
  border: 1px solid var(--app-border-light);
  border-radius: 10px;
  background: var(--app-surface-muted);
}

.analysis-action-card {
  display: grid;
  gap: 12px;
  padding: 14px;
  border: 1px solid #bfdbfe;
  border-radius: 10px;
  background: #f8fbff;
}

.analysis-action-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.analysis-action-header > div {
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 0;
}

.analysis-action-header strong {
  color: #1e3a8a;
  font-size: 14px;
}

.analysis-action-header span {
  color: #475569;
  font-size: 12px;
}

.analysis-action-groups {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}

.analysis-action-group {
  display: grid;
  gap: 10px;
  padding: 10px;
  border: 1px solid #dbe4f0;
  border-radius: 8px;
  background: #fff;
}

.analysis-group-label {
  display: flex;
  align-items: center;
  gap: 6px;
  color: #334155;
  font-size: 12px;
  font-weight: 700;
}

.analysis-group-label .el-icon {
  color: #2563eb;
}

.analysis-buttons {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.insight-panel-collapse {
  width: 100%;
  border: 1px solid #dbe4f0;
  border-radius: 12px;
  background: #fff;
  overflow: hidden;
}

.insight-panel-collapse :deep(.el-collapse-item__header) {
  min-height: 48px;
  height: auto;
  padding: 0 14px;
  background: #fff;
  border-bottom: 1px solid #eef2f7;
}

.insight-panel-collapse :deep(.el-collapse-item__content) {
  padding: 12px 14px 14px;
}

.insight-collapse-title {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  width: 100%;
  min-width: 0;
}

.insight-collapse-title > div {
  display: flex;
  align-items: baseline;
  gap: 8px;
  min-width: 0;
}

.insight-collapse-title span {
  color: var(--app-text);
  font-weight: 700;
}

.insight-collapse-title small {
  color: var(--app-text-muted);
  font-size: 12px;
}

.insight-section {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.insight-summary-card {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: flex-start;
  padding: 10px;
  border: 1px solid var(--app-border-light);
  border-radius: 8px;
  background: var(--app-surface-muted);
}

.insight-summary-card > div {
  min-width: 0;
}

.insight-summary-card span {
  display: block;
  color: var(--app-text);
  font-size: 12px;
  font-weight: 700;
}

.insight-summary-card p {
  margin: 4px 0 0;
  color: var(--app-text-muted);
  font-size: 12px;
  line-height: 1.6;
}

.insight-list,
.driver-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.insight-item {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr);
  gap: 10px;
  padding: 10px;
  border: 1px solid var(--app-border-light);
  border-radius: 8px;
  background: #fff;
}

.insight-item strong,
.driver-item strong {
  display: block;
  color: var(--app-text);
  font-size: 13px;
}

.insight-item p,
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

.save-insight-intro {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr);
  gap: 10px;
  padding: 12px;
  margin-bottom: 14px;
  border: 1px solid #dbe4f0;
  border-radius: 8px;
  background: #f8fafc;
}

.save-insight-intro .el-icon {
  color: #2563eb;
  margin-top: 2px;
}

.save-insight-intro strong {
  display: block;
  color: var(--app-text);
  font-size: 14px;
  margin-bottom: 4px;
}

.save-insight-intro span {
  color: var(--app-text-muted);
  font-size: 12px;
  line-height: 1.6;
}

.metric-draft-loading {
  display: flex;
  align-items: center;
  gap: 10px;
  min-height: 120px;
  color: var(--app-text-muted);
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

.decision-action-bar div {
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 0;
}

.decision-action-bar strong {
  color: var(--app-text);
  font-size: 14px;
}

.decision-action-bar span {
  color: var(--app-text-muted);
  font-size: 12px;
}

.chart-container,
.table-container {
  background: var(--app-surface);
  border: 1px solid var(--app-border-light);
  border-radius: 12px;
  overflow: hidden;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.04);
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
  .decision-action-bar,
  .analysis-action-header,
  .metric-draft-hero,
  .insight-summary-card {
    align-items: stretch;
    flex-direction: column;
  }

  .analysis-action-groups,
  .attribution-overview {
    grid-template-columns: 1fr;
  }

  .analysis-buttons {
    flex-direction: column;
  }

  .analysis-buttons :deep(.el-button) {
    width: 100%;
    margin-left: 0;
  }

  .driver-item {
    grid-template-columns: 1fr;
  }
}
</style>
