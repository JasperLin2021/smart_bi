<template>
  <div class="page data-pipelines-page etl-workbench">
    <section class="legacy-commandbar">
      <div class="legacy-commandbar__title">
        <p class="eyebrow">ENTERPRISE ETL</p>
        <h2>数据加工管道</h2>
        <span>在 BI 中完成抽取、清洗、转换、质量闸门、装载、调度、监控和血缘治理。</span>
      </div>
      <div class="legacy-commandbar__actions pipeline-action-toolbar">
        <el-input
          v-model="pipelineSearch"
          class="pipeline-search"
          clearable
          :prefix-icon="Search"
          placeholder="搜索管道 / 数据集"
        />
        <div class="toolbar-group" aria-label="管道维护操作">
          <el-tooltip content="刷新管道列表" placement="bottom">
            <el-button class="toolbar-button" circle :icon="Refresh" :loading="loading" aria-label="刷新管道列表" @click="loadAll" />
          </el-tooltip>
          <el-tooltip content="上线校验" placement="bottom">
            <el-button class="toolbar-button" circle :icon="CircleCheck" :loading="validating" :disabled="!selectedPipeline" aria-label="上线校验" @click="validateSelected" />
          </el-tooltip>
          <el-tooltip content="预览当前节点" placement="bottom">
            <el-button class="toolbar-button" circle :icon="View" :loading="previewing" :disabled="!selectedPipeline" aria-label="预览当前节点" @click="previewSelectedNode" />
          </el-tooltip>
          <el-tooltip content="保存流程配置" placement="bottom">
            <el-button class="toolbar-button" circle :icon="DocumentChecked" :loading="savingDag" :disabled="!selectedPipeline" aria-label="保存流程配置" @click="savePipelineDag" />
          </el-tooltip>
        </div>
        <div class="toolbar-group toolbar-group--primary" aria-label="运行操作">
          <el-button class="toolbar-button toolbar-button--primary" type="primary" :icon="VideoPlay" :loading="running" :disabled="!selectedPipeline" @click="runSelected()">运行</el-button>
          <el-button class="toolbar-button" type="warning" plain :icon="RefreshRight" :loading="running" :disabled="!selectedPipeline" @click="runBackfill">补数</el-button>
        </div>
        <el-button class="toolbar-button toolbar-button--new" type="primary" plain :icon="Plus" @click="openCreate">新建管道</el-button>
      </div>
    </section>

    <section class="pipeline-kpis">
      <div class="kpi-cell">
        <span>生产管道</span>
        <strong>{{ summaryStats.prod }}</strong>
      </div>
      <div class="kpi-cell">
        <span>运行中/已激活</span>
        <strong>{{ summaryStats.active }}</strong>
      </div>
      <div class="kpi-cell">
        <span>最近失败</span>
        <strong>{{ summaryStats.failed }}</strong>
      </div>
      <div class="kpi-cell">
        <span>SLA ≤ 2h</span>
        <strong>{{ summaryStats.tightSla }}</strong>
      </div>
    </section>

    <div class="page-tabbar etl-mode-tabs" role="tablist" aria-label="ETL 工作台视图">
      <button
        v-for="tab in workbenchTabs"
        :key="tab.value"
        type="button"
        class="page-tab"
        :class="{ 'is-active': activeWorkbenchTab === tab.value }"
        @click="activeWorkbenchTab = tab.value"
      >
        <el-icon><component :is="tab.icon" /></el-icon>
        {{ tab.label }}
      </button>
    </div>

    <section class="etl-shell etl-shell--composer">
      <aside class="etl-palette" aria-label="ETL 管道与节点组件">
        <div class="panel-title">
          <span>操作台</span>
          <small>拖拽组件到画板</small>
        </div>
        <div class="operator-console-note">
          <strong>{{ filteredPipelines.length }}</strong>
          <span>条管道资产</span>
        </div>
        <div class="status-filter">
          <button
            v-for="tab in statusTabs"
            :key="tab.value"
            type="button"
            :class="{ active: statusFilter === tab.value }"
            @click="statusFilter = tab.value"
          >
            {{ tab.label }} <span>{{ tab.count }}</span>
          </button>
        </div>
        <div class="pipeline-list">
          <button
            v-for="item in filteredPipelines"
            :key="item.id"
            type="button"
            class="pipeline-item"
            :class="{ active: selectedPipeline?.id === item.id }"
            @click="selectPipeline(item.id)"
          >
            <div class="pipeline-item__main">
              <strong>{{ item.name }}</strong>
              <span>{{ datasetName(item.dataset_id) }}</span>
            </div>
            <el-tag :type="pipelineStatusType(item)" size="small" effect="plain">
              {{ pipelineStatusLabel(item.status) }}
            </el-tag>
            <div class="pipeline-item__meta">
              <span>{{ environmentLabel(item.environment) }}</span>
              <span>{{ priorityLabel(item.priority) }}</span>
              <span>SLA {{ item.sla_minutes || 120 }}m</span>
            </div>
          </button>
          <el-empty v-if="!filteredPipelines.length" description="暂无符合条件的管道" :image-size="64" />
        </div>

        <div class="palette-section">
          <div class="panel-title">
            <span>数据源</span>
            <small>拖拽接入</small>
          </div>
          <button v-for="source in sourcePalette" :key="source.name" type="button" class="source-chip">
            <el-icon><component :is="source.icon" /></el-icon>
            {{ source.name }}
          </button>
        </div>

        <div class="palette-section">
          <div class="panel-title">
            <span>组件库</span>
            <small>来自算子目录</small>
          </div>
          <div class="operator-group" v-for="group in operatorGroups" :key="group.category">
            <div class="operator-group__title">{{ group.category }}</div>
            <div class="node-palette">
              <button
                v-for="node in group.nodes"
                :key="`${node.type}-${node.label}`"
                type="button"
                draggable="true"
                :title="node.description"
                @dragstart="onPaletteDragStart(node.type)"
                @click="addNode(node.type)"
              >
                <el-icon><component :is="node.icon" /></el-icon>
                <span>{{ node.label }}</span>
              </button>
            </div>
          </div>
        </div>
      </aside>

      <main class="etl-stage">
        <div class="pipeline-toolbar">
          <div>
            <h3>{{ selectedPipeline?.name || "选择一个数据加工管道" }}</h3>
            <span>
              {{ selectedPipeline ? `${flowNodes.length} 个节点 · ${flowEdges.length} 条依赖 · ${datasetName(selectedPipeline.dataset_id)}` : "DAG 将显示抽取、转换、质量闸门和装载链路" }}
            </span>
          </div>
          <div class="pipeline-toolbar__actions">
            <el-tag v-if="selectedPipeline" effect="plain">v{{ selectedPipeline.published_version || selectedPipeline.current_version || 0 }}</el-tag>
            <el-tag v-if="validation" :type="validationTagType" effect="plain">{{ validationStatusText }}</el-tag>
            <el-button size="small" :loading="publishingVersion" :disabled="!selectedPipeline" @click="publishSelectedVersion">发布版本</el-button>
          </div>
        </div>

        <section v-show="activeWorkbenchTab === 'design'" class="pipeline-canvas-panel">
          <div class="section-heading section-heading--canvas">
            <div>
              <span>流程设计</span>
              <small>抽取 -> 转换 -> 质量闸门 -> 装载</small>
            </div>
            <div class="canvas-commandbar" aria-label="画布操作">
              <el-input
                v-model="nodeSearch"
                class="node-search-input"
                clearable
                size="small"
                :prefix-icon="Search"
                placeholder="定位节点"
                @keyup.enter="locateSearchedNode"
              />
              <div class="toolbar-group toolbar-group--compact" aria-label="画布快捷操作">
                <el-tooltip content="定位节点" placement="bottom">
                  <el-button class="toolbar-button" size="small" circle :icon="Aim" :disabled="!selectedPipeline" aria-label="定位节点" @click="locateSearchedNode" />
                </el-tooltip>
                <el-tooltip content="撤销" placement="bottom">
                  <el-button class="toolbar-button" size="small" circle :icon="Back" :disabled="!dagUndoStack.length" aria-label="撤销" @click="undoDagChange" />
                </el-tooltip>
                <el-tooltip content="重做" placement="bottom">
                  <el-button class="toolbar-button" size="small" circle :icon="Right" :disabled="!dagRedoStack.length" aria-label="重做" @click="redoDagChange" />
                </el-tooltip>
                <el-tooltip content="复制节点" placement="bottom">
                  <el-button class="toolbar-button" size="small" circle :icon="CopyDocument" :disabled="!selectedNode" aria-label="复制节点" @click="copySelectedNode" />
                </el-tooltip>
                <el-tooltip content="粘贴节点" placement="bottom">
                  <el-button class="toolbar-button" size="small" circle :icon="DocumentCopy" :disabled="!copiedNode" aria-label="粘贴节点" @click="pasteCopiedNode" />
                </el-tooltip>
                <el-tooltip content="删除节点" placement="bottom">
                  <el-button class="toolbar-button" size="small" circle type="danger" plain :icon="Delete" :disabled="!selectedNode" aria-label="删除节点" @click="deleteSelectedNode" />
                </el-tooltip>
                <el-tooltip content="自动布局" placement="bottom">
                  <el-button class="toolbar-button" size="small" circle :icon="Rank" :disabled="!selectedPipeline" aria-label="自动布局" @click="autoLayoutDag" />
                </el-tooltip>
              </div>
              <el-button class="toolbar-button" size="small" :icon="MagicStick" :disabled="!selectedPipeline" @click="addTemplateNodes">套用模板</el-button>
            </div>
          </div>
          <div class="flow-wrap" @drop.prevent="onCanvasDrop" @dragover.prevent>
            <VueFlow
              v-if="selectedPipeline"
              :nodes="flowNodes"
              :edges="flowEdges"
              fit-view-on-init
              class="pipeline-flow"
              @connect="onConnect"
              @node-click="onNodeClick"
              @node-drag-stop="onNodeDragStop"
            >
              <template #node-etl-icon="{ data, selected, connectable }">
                <Handle type="target" :position="Position.Top" :connectable="connectable" />
                <div class="etl-canvas-node" :class="[`is-${data.status}`, { 'is-selected': selected }]">
                  <span class="etl-canvas-node__icon" :class="`etl-canvas-node__icon--${data.tone}`" aria-hidden="true">
                    <span class="etl-canvas-node__glyph" :class="`etl-canvas-node__glyph--${data.iconKey}`">
                      <span />
                      <span />
                      <b v-if="data.iconKey === 'sql'">SQL</b>
                    </span>
                    <i class="etl-canvas-node__status" />
                  </span>
                  <span class="etl-canvas-node__title">{{ data.title }}</span>
                  <small>{{ data.caption }}</small>
                </div>
                <Handle type="source" :position="Position.Bottom" :connectable="connectable" />
              </template>
              <Background />
              <MiniMap />
              <Controls />
            </VueFlow>
            <el-empty v-else description="请选择或新建管道" />
          </div>
        </section>

        <section v-show="activeWorkbenchTab !== 'design'" class="etl-tab-surface">
          <div v-if="activeWorkbenchTab === 'preview'" class="tab-surface-grid">
            <div>
              <div class="section-heading">
                <div>
                  <span>预览数据</span>
                  <small>按当前选中节点执行到该节点，不刷新目标数据集。</small>
                </div>
                <div class="section-heading__actions">
                  <el-tag effect="plain">{{ inspectMode }}</el-tag>
                  <el-button size="small" :icon="View" :loading="previewing" :disabled="!selectedPipeline" @click="previewSelectedNode">刷新预览</el-button>
                  <el-button size="small" :loading="inspecting" :disabled="!selectedPipeline" @click="inspectSelectedNode">字段画像</el-button>
                </div>
              </div>
              <el-table :data="previewRows" size="small" height="356" empty-text="暂无预览数据">
                <el-table-column v-for="column in previewColumns" :key="column" :prop="column" :label="column" min-width="130" show-overflow-tooltip />
              </el-table>
            </div>
          </div>

          <div v-if="activeWorkbenchTab === 'schedule'" class="schedule-grid">
            <div class="section-heading">
              <div>
                <span>运行控制台</span>
                <small>运行模式、补数窗口与干跑校验</small>
              </div>
            </div>
            <div class="ops-grid">
              <div>
                <span>调度与SLA</span>
                <strong>{{ selectedPipeline ? runModeLabel(selectedPipeline.run_mode) : "-" }}</strong>
                <small>{{ selectedPipeline?.schedule_cron || "手动触发" }}</small>
              </div>
              <div>
                <span>执行时间</span>
                <strong>{{ selectedPipeline?.schedule_cron || "未配置" }}</strong>
                <small>{{ selectedPipeline?.environment ? environmentLabel(selectedPipeline.environment) : "环境" }}</small>
              </div>
              <div>
                <span>重试策略</span>
                <strong>{{ selectedPipeline?.retry_count ?? 2 }} 次</strong>
                <small>超时 {{ selectedPipeline?.timeout_minutes || 60 }} 分钟</small>
              </div>
              <div>
                <span>告警策略</span>
                <strong>{{ alertPolicyText }}</strong>
                <small>异常告警及时触达</small>
              </div>
            </div>
            <div class="console-form">
              <label>
                <span>补数窗口</span>
                <el-date-picker
                  v-model="runWindow"
                  type="datetimerange"
                  value-format="YYYY-MM-DDTHH:mm:ss"
                  start-placeholder="开始时间"
                  end-placeholder="结束时间"
                  :disabled="runForm.mode !== 'backfill'"
                />
              </label>
              <label>
                <span>运行原因</span>
                <el-input v-model="runForm.reason" type="textarea" :rows="2" placeholder="例：修复上游缺失订单后补跑" />
              </label>
              <el-checkbox v-model="runForm.dry_run">干跑：真实抽取和质量校验，但不刷新目标数据集</el-checkbox>
              <el-segmented v-model="runForm.mode" class="page-segmented-tabs run-mode-tabs" :options="runModeOptions" />
            </div>
          </div>

          <div v-if="activeWorkbenchTab === 'monitor'" class="monitor-grid">
            <div class="section-heading">
              <div>
                <span>运行历史</span>
                <small>最近运行状态、读写行数与错误行数。</small>
              </div>
            </div>
            <div class="run-health">
              <div class="run-health__score">
                <strong>{{ successRate }}%</strong>
                <span>运行成功率</span>
              </div>
              <div class="run-health__stats">
                <span>读取行数 <b>{{ lastRun?.records_read ?? 0 }}</b></span>
                <span>写入行数 <b>{{ lastRun?.records_written ?? 0 }}</b></span>
                <span>错误行数 <b>{{ lastRun?.records_failed ?? 0 }}</b></span>
              </div>
            </div>
            <el-table :data="runHistory" size="small" height="320" empty-text="暂无运行历史">
              <el-table-column label="状态" width="90">
                <template #default="{ row }">
                  <el-tag :type="row.status === 'success' ? 'success' : 'danger'" size="small" effect="plain">{{ runStatusLabel(row.status) }}</el-tag>
                </template>
              </el-table-column>
              <el-table-column label="模式" width="100">
                <template #default="{ row }">{{ runModeLabel(row.mode) }}</template>
              </el-table-column>
              <el-table-column prop="reason" label="原因" min-width="180" show-overflow-tooltip />
              <el-table-column label="读取 / 写入 / 失败" width="170">
                <template #default="{ row }">{{ row.records_read }} / {{ row.records_written }} / {{ row.records_failed }}</template>
              </el-table-column>
              <el-table-column label="窗口" min-width="210">
                <template #default="{ row }">{{ runWindowLabel(row) }}</template>
              </el-table-column>
            </el-table>
          </div>

          <div v-if="activeWorkbenchTab === 'lineage'" class="lineage-panel">
            <div class="section-heading">
              <div>
                <span>影响血缘</span>
                <small>展示源表、转换节点、质量闸门和目标数据集的影响链路。</small>
              </div>
              <el-button size="small" :icon="Share" :loading="lineageLoading" :disabled="!selectedPipeline" @click="loadLineage">刷新血缘</el-button>
            </div>
            <div class="lineage-summary">
              <div>
                <span>源表</span>
                <strong>{{ lineageSourceText }}</strong>
              </div>
              <div>
                <span>目标数据集</span>
                <strong>{{ lineage?.target?.dataset_name || (selectedPipeline ? datasetName(selectedPipeline.dataset_id) : "-") }}</strong>
              </div>
              <div>
                <span>节点数</span>
                <strong>{{ lineage?.nodes?.length || flowNodes.length }}</strong>
              </div>
              <div>
                <span>依赖数</span>
                <strong>{{ lineage?.edges?.length || flowEdges.length }}</strong>
              </div>
            </div>
          </div>
        </section>

        <section class="etl-bottom-panel">
          <el-tabs v-model="detailTab">
            <el-tab-pane label="数据预览" name="preview">
              <el-table :data="previewRows" size="small" height="220" empty-text="点击预览查看节点输出">
                <el-table-column v-for="column in previewColumns" :key="column" :prop="column" :label="column" min-width="130" show-overflow-tooltip />
              </el-table>
            </el-tab-pane>
            <el-tab-pane label="字段画像" name="inspect">
              <div class="inspect-panel">
                <div class="table-toolbar">
                  <div>
                    <strong>字段画像</strong>
                    <span>{{ selectedNode ? `${selectedNode.label || selectedNode.id} · ${inspectMode}` : "选择节点后查看 schema、空值率和样例值" }}</span>
                  </div>
                  <el-button size="small" :loading="inspecting" :disabled="!selectedPipeline" @click="inspectSelectedNode">刷新画像</el-button>
                </div>
                <el-table :data="inspectProfile" size="small" height="176" empty-text="暂无字段画像">
                  <el-table-column prop="name" label="字段" min-width="150" show-overflow-tooltip />
                  <el-table-column prop="type" label="类型" width="110" />
                  <el-table-column label="空值率" width="100">
                    <template #default="{ row }">{{ Math.round((row.null_ratio || 0) * 10000) / 100 }}%</template>
                  </el-table-column>
                  <el-table-column prop="unique_count" label="唯一值" width="100" />
                  <el-table-column label="样例值" min-width="220" show-overflow-tooltip>
                    <template #default="{ row }">{{ (row.sample_values || []).join(", ") }}</template>
                  </el-table-column>
                </el-table>
              </div>
            </el-tab-pane>
            <el-tab-pane label="上线检查" name="validation">
              <div class="validation-panel">
                <div class="validation-score">
                  <el-icon :class="validationIconClass">
                    <CircleCheck v-if="validation?.status === 'ready'" />
                    <Warning v-else />
                  </el-icon>
                  <div>
                    <strong>{{ validationStatusText }}</strong>
                    <span>{{ validation ? `${validation.critical_count} 个阻断项 · ${validation.warning_count} 个建议项` : "选择管道后自动检查 DAG、调度、SLA 和告警配置" }}</span>
                  </div>
                </div>
                <div class="diagnostic-list">
                  <div v-for="item in activeDiagnostics" :key="`${item.code}-${item.node_id || 'global'}`" class="diagnostic-item">
                    <el-tag :type="item.severity === 'critical' ? 'danger' : 'warning'" size="small" effect="plain">
                      {{ item.severity === "critical" ? "阻断" : "建议" }}
                    </el-tag>
                    <span>{{ item.message }}</span>
                  </div>
                  <el-empty v-if="validation && !activeDiagnostics.length" description="上线检查通过" :image-size="56" />
                </div>
              </div>
            </el-tab-pane>
            <el-tab-pane label="质量规则" name="quality">
              <div class="table-toolbar">
                <div>
                  <strong>质量闸门</strong>
                  <span>在装载前执行字段、行数、新鲜度和自定义 SQL 校验。</span>
                </div>
                <el-button v-if="selectedPipeline" size="small" :icon="Plus" @click="openRuleCreate">新增规则</el-button>
              </div>
              <el-table :data="qualityRules" size="small" height="220" empty-text="暂无质量规则">
                <el-table-column prop="name" label="规则" min-width="160" show-overflow-tooltip />
                <el-table-column label="类型" width="120">
                  <template #default="{ row }">{{ ruleTypeLabel(row.rule_type) }}</template>
                </el-table-column>
                <el-table-column prop="field" label="字段" width="150" show-overflow-tooltip />
                <el-table-column prop="threshold" label="阈值" width="130" show-overflow-tooltip />
                <el-table-column label="级别" width="90">
                  <template #default="{ row }">
                    <el-tag :type="row.severity === 'error' ? 'danger' : 'warning'" size="small" effect="plain">{{ severityLabel(row.severity) }}</el-tag>
                  </template>
                </el-table-column>
                <el-table-column label="状态" width="90">
                  <template #default="{ row }">
                    <el-tag :type="row.is_active ? 'success' : 'info'" size="small" effect="plain">{{ row.is_active ? "启用" : "停用" }}</el-tag>
                  </template>
                </el-table-column>
              </el-table>
            </el-tab-pane>
            <el-tab-pane label="执行日志" name="logs">
              <div class="node-log-list">
                <div v-for="node in latestNodeLogs" :key="node.node_id" class="node-log-item">
                  <el-tag :type="node.status === 'success' ? 'success' : node.status === 'warning' ? 'warning' : node.status === 'skipped' ? 'info' : 'danger'" size="small" effect="plain">
                    {{ node.status }}
                  </el-tag>
                  <strong>{{ node.label || node.node_id }}</strong>
                  <span>{{ node.rows_in ?? 0 }} -> {{ node.rows_out ?? 0 }} 行</span>
                  <small>{{ node.duration_ms ?? 0 }}ms</small>
                </div>
                <el-empty v-if="!latestNodeLogs.length" description="暂无节点执行日志" :image-size="56" />
              </div>
            </el-tab-pane>
          </el-tabs>
        </section>
      </main>
    </section>

    <el-drawer
      v-model="nodeDrawerVisible"
      class="node-config-drawer"
      size="min(520px, calc(100vw - 24px))"
      direction="rtl"
      :with-header="false"
    >
      <div class="node-config-panel node-config-panel--drawer" aria-label="节点配置">
        <div class="section-heading">
          <div>
            <span>节点配置</span>
            <small>{{ selectedNode ? `${nodeTypeLabel(selectedNode.type)} · ${selectedNode.label || selectedNode.id}` : "选择画布节点后配置" }}</small>
          </div>
          <div class="node-config-heading__actions">
            <el-tag v-if="selectedNode" :type="selectedNodeStatus === 'failed' || selectedNodeStatus === 'blocked' ? 'danger' : selectedNodeStatus === 'warning' ? 'warning' : 'success'" effect="plain">
              {{ selectedNodeStatusText }}
            </el-tag>
            <el-button v-if="selectedNode" size="small" :loading="inspecting" @click="inspectSelectedNode">Inspect</el-button>
            <el-button size="small" text @click="nodeDrawerVisible = false">收起</el-button>
          </div>
        </div>

        <el-empty v-if="!selectedNode" description="请选择一个节点" :image-size="72" />
        <div v-else class="node-config-form">
          <label>
            <span>节点名称</span>
            <el-input v-model="selectedNode.label" placeholder="节点名称" />
          </label>
          <div v-if="selectedNodeLog || selectedNodeDiagnostics.length" class="node-state-panel">
            <div>
              <span>最近状态</span>
              <strong>{{ selectedNodeStatusText }}</strong>
            </div>
            <small v-if="selectedNodeLog">{{ selectedNodeLog.rows_in ?? 0 }} -> {{ selectedNodeLog.rows_out ?? selectedNodeLog.records_written ?? 0 }} 行 · {{ selectedNodeLog.duration_ms ?? 0 }}ms</small>
            <small v-for="item in selectedNodeDiagnostics" :key="`${item.code}-${item.node_id}`">{{ item.message }}</small>
          </div>

          <template v-if="selectedNode.type === 'source' || selectedNode.type === 'extract'">
            <div class="config-group">
              <label>
                <span>源数据集</span>
                <el-select v-model="selectedNodeConfig.dataset_id" clearable filterable placeholder="默认使用管道目标数据集">
                  <el-option v-for="dataset in datasets" :key="dataset.id" :label="dataset.name" :value="dataset.id" />
                </el-select>
              </label>
              <label>
                <span>抽取模式</span>
                <el-select v-model="selectedNodeConfig.mode" placeholder="抽取模式">
                  <el-option label="全量" value="full" />
                  <el-option label="增量" value="incremental" />
                  <el-option label="补数窗口" value="backfill" />
                </el-select>
              </label>
              <label>
                <span>增量字段</span>
                <el-input v-model="selectedNodeConfig.incremental_key" placeholder="updated_at" />
              </label>
              <label>
                <span>批次大小</span>
                <el-input-number v-model="selectedNodeConfig.batch_size" :min="1" :max="50000" controls-position="right" />
              </label>
            </div>
          </template>

          <template v-else-if="selectedNode.type === 'metadata_extract'">
            <div class="config-group">
              <label>
                <span>数据源 ID</span>
                <el-input-number v-model="selectedNodeConfig.datasource_id" :min="1" controls-position="right" />
              </label>
              <label>
                <span>表名列表</span>
                <el-input v-model="metadataTablesText" placeholder="orders, order_items" />
              </label>
              <el-checkbox v-model="selectedNodeConfig.refresh_schema">刷新数据源元数据</el-checkbox>
              <el-checkbox v-model="selectedNodeConfig.write_to_catalog">同步数据目录</el-checkbox>
            </div>
          </template>

          <template v-else-if="selectedNode.type === 'join'">
            <div class="config-group">
              <label>
                <span>左上游节点</span>
                <el-select v-model="selectedNodeConfig.left_node_id" filterable placeholder="选择左表节点">
                  <el-option v-for="node in upstreamCandidates" :key="node.id" :label="node.label || node.id" :value="node.id" />
                </el-select>
              </label>
              <label>
                <span>右上游节点</span>
                <el-select v-model="selectedNodeConfig.right_node_id" filterable placeholder="选择右表节点">
                  <el-option v-for="node in upstreamCandidates" :key="node.id" :label="node.label || node.id" :value="node.id" />
                </el-select>
              </label>
              <div class="mapping-row">
                <el-input v-model="selectedNodeConfig.left_key" placeholder="左关联键" />
                <el-input v-model="selectedNodeConfig.right_key" placeholder="右关联键" />
              </div>
              <label>
                <span>连接方式</span>
                <el-select v-model="selectedNodeConfig.join_type">
                  <el-option label="INNER" value="inner" />
                  <el-option label="LEFT" value="left" />
                  <el-option label="RIGHT" value="right" />
                  <el-option label="FULL" value="outer" />
                </el-select>
              </label>
            </div>
          </template>

          <template v-else-if="selectedNode.type === 'union'">
            <div class="config-group">
              <label>
                <span>汇合模式</span>
                <el-select v-model="selectedNodeConfig.mode">
                  <el-option label="保留全部" value="all" />
                  <el-option label="按键去重" value="distinct" />
                </el-select>
              </label>
              <label>
                <span>去重键</span>
                <el-input v-model="unionKeysText" placeholder="order_id, region" />
              </label>
            </div>
          </template>

          <template v-else-if="selectedNode.type === 'transform'">
            <div class="config-group">
              <div class="config-title">
                <strong>字段映射</strong>
                <el-button size="small" text :icon="Plus" @click="appendListConfig('field_mapping', { source: '', target: '' })">添加</el-button>
              </div>
              <div v-for="(item, index) in listConfig('field_mapping')" :key="`mapping-${index}`" class="mapping-row">
                <el-input v-model="item.source" placeholder="源字段" />
                <el-input v-model="item.target" placeholder="目标字段" />
                <el-button text type="danger" @click="removeListConfig('field_mapping', index)">删除</el-button>
              </div>
            </div>

            <div class="config-group">
              <div class="config-title">
                <strong>类型转换</strong>
                <el-button size="small" text :icon="Plus" @click="appendListConfig('type_conversions', { field: '', type: 'string' })">添加</el-button>
              </div>
              <div v-for="(item, index) in listConfig('type_conversions')" :key="`type-${index}`" class="mapping-row">
                <el-input v-model="item.field" placeholder="字段" />
                <el-select v-model="item.type" placeholder="类型">
                  <el-option label="STRING" value="string" />
                  <el-option label="BIGINT" value="integer" />
                  <el-option label="DECIMAL" value="decimal" />
                  <el-option label="TIMESTAMP" value="datetime" />
                </el-select>
                <el-button text type="danger" @click="removeListConfig('type_conversions', index)">删除</el-button>
              </div>
            </div>

            <div class="config-group">
              <div class="config-title">
                <strong>过滤条件</strong>
                <el-button size="small" text :icon="Plus" @click="appendListConfig('filters', { field: '', operator: '=', value: '' })">添加</el-button>
              </div>
              <div v-for="(item, index) in listConfig('filters')" :key="`filter-${index}`" class="filter-row">
                <el-input v-model="item.field" placeholder="字段" />
                <el-select v-model="item.operator" placeholder="操作符">
                  <el-option label="=" value="=" />
                  <el-option label=">=" value=">=" />
                  <el-option label="<=" value="<=" />
                  <el-option label="IN" value="in" />
                  <el-option label="NOT NULL" value="not_null" />
                </el-select>
                <el-input v-model="item.value" placeholder="值" />
                <el-button text type="danger" @click="removeListConfig('filters', index)">删除</el-button>
              </div>
            </div>

            <div class="config-group">
              <div class="config-title">
                <strong>派生列</strong>
                <el-button size="small" text :icon="Plus" @click="appendListConfig('derived_columns', { name: '', expression: '' })">添加</el-button>
              </div>
              <div v-for="(item, index) in listConfig('derived_columns')" :key="`derived-${index}`" class="mapping-row">
                <el-input v-model="item.name" placeholder="字段名" />
                <el-input v-model="item.expression" placeholder="表达式，如 amount - discount" />
                <el-button text type="danger" @click="removeListConfig('derived_columns', index)">删除</el-button>
              </div>
            </div>

            <div class="config-group">
              <div class="config-title">
                <strong>去重与聚合</strong>
              </div>
              <label>
                <span>去重键</span>
                <el-input v-model="dedupeKeysText" placeholder="order_id, user_id" />
              </label>
              <label>
                <span>聚合维度</span>
                <el-input v-model="aggregationGroupByText" placeholder="area, create_date" />
              </label>
              <div class="config-title">
                <strong>聚合指标</strong>
                <el-button size="small" text :icon="Plus" @click="appendAggregationMetric">添加</el-button>
              </div>
              <div v-for="(metric, index) in aggregationMetrics" :key="`metric-${index}`" class="filter-row">
                <el-input v-model="metric.field" placeholder="字段" />
                <el-select v-model="metric.function" placeholder="函数">
                  <el-option label="SUM" value="sum" />
                  <el-option label="AVG" value="avg" />
                  <el-option label="COUNT" value="count" />
                  <el-option label="MIN" value="min" />
                  <el-option label="MAX" value="max" />
                </el-select>
                <el-input v-model="metric.alias" placeholder="输出字段" />
                <el-button text type="danger" @click="removeAggregationMetric(index)">删除</el-button>
              </div>
            </div>
          </template>

          <template v-else-if="selectedNode.type === 'sql'">
            <div class="config-group">
              <label>
                <span>SQL 查询</span>
                <CodeMirrorSqlEditor
                  v-model="selectedNodeConfig.sql"
                  :datasource-id="selectedNodeConfig.datasource_id"
                  :rows="10"
                  :data-extensions="sqlEditorExtensions.join(',')"
                />
              </label>
              <label>
                <span>执行模式</span>
                <el-select v-model="selectedNodeConfig.execution_mode" placeholder="执行模式">
                  <el-option label="内存预览" value="in_memory" />
                  <el-option label="数据库下推" value="pushdown" />
                </el-select>
              </label>
              <label>
                <span>数据源 ID</span>
                <el-input-number v-model="selectedNodeConfig.datasource_id" :min="1" controls-position="right" />
              </label>
              <label>
                <span>物化目标表</span>
                <el-input v-model="selectedNodeConfig.target_table" placeholder="etl_sql_result" />
              </label>
            </div>
          </template>

          <template v-else-if="selectedNode.type === 'reverse_etl'">
            <div class="config-group">
              <label>
                <span>目标类型</span>
                <el-select v-model="selectedNodeConfig.target_type">
                  <el-option label="数据库" value="database" />
                </el-select>
              </label>
              <label>
                <span>业务系统数据源 ID</span>
                <el-input-number v-model="selectedNodeConfig.datasource_id" :min="1" controls-position="right" />
              </label>
              <label>
                <span>回写目标表</span>
                <el-input v-model="selectedNodeConfig.target_table" placeholder="crm_paid_orders" />
              </label>
              <label>
                <span>回写模式</span>
                <el-select v-model="selectedNodeConfig.mode">
                  <el-option label="追加写入" value="append" />
                  <el-option label="替换写入" value="replace" />
                  <el-option label="更新写入" value="upsert" />
                </el-select>
              </label>
              <label>
                <span>主键字段</span>
                <el-input v-model="selectedNodeConfig.primary_key" placeholder="crm_order_id" />
              </label>
              <label>
                <span>更新键</span>
                <el-input v-model="reverseEtlKeysText" placeholder="crm_order_id, tenant_id" />
              </label>
              <div class="config-title">
                <strong>回写字段映射</strong>
                <el-button size="small" text :icon="Plus" @click="appendListConfig('field_mapping', { source: '', target: '' })">添加</el-button>
              </div>
              <div v-for="(item, index) in listConfig('field_mapping')" :key="`reverse-map-${index}`" class="mapping-row">
                <el-input v-model="item.source" placeholder="分析字段" />
                <el-input v-model="item.target" placeholder="业务系统字段" />
                <el-button text type="danger" @click="removeListConfig('field_mapping', index)">删除</el-button>
              </div>
            </div>
          </template>

          <template v-else-if="selectedNode.type === 'quality'">
            <div class="config-group">
              <div class="config-title">
                <strong>质量规则</strong>
                <el-button size="small" text :icon="Plus" @click="openRuleCreate">新增规则</el-button>
              </div>
              <div v-for="rule in qualityRules" :key="rule.id" class="rule-chip">
                <span>{{ rule.name }}</span>
                <el-tag :type="rule.severity === 'error' ? 'danger' : 'warning'" size="small" effect="plain">{{ severityLabel(rule.severity) }}</el-tag>
              </div>
            </div>
          </template>

          <template v-else-if="selectedNode.type === 'load' || selectedNode.type === 'sink'">
            <div class="config-group">
              <label>
                <span>目标表</span>
                <el-input v-model="selectedNodeConfig.target_table" placeholder="etl_order_summary" />
              </label>
              <label>
                <span>装载模式</span>
                <el-select v-model="selectedNodeConfig.mode" placeholder="装载模式">
                  <el-option label="替换写入" value="replace" />
                  <el-option label="追加写入" value="append" />
                  <el-option label="仅刷新数据集" value="dataset_refresh" />
                </el-select>
              </label>
            </div>
          </template>

          <template v-else>
            <div class="config-group">
              <el-alert type="info" :closable="false" show-icon title="该节点使用默认配置运行。" />
            </div>
          </template>
        </div>
      </div>
    </el-drawer>

    <el-dialog v-model="dialogVisible" title="新建数据加工管道" width="min(860px, calc(100vw - 32px))" destroy-on-close>
      <el-form label-position="top" class="pipeline-form">
        <el-row :gutter="16">
          <el-col :xs="24" :md="12">
            <el-form-item label="管道名称">
              <el-input v-model="form.name" placeholder="例：Nova ERP 订单增量加工" />
            </el-form-item>
          </el-col>
          <el-col :xs="24" :md="12">
            <el-form-item label="目标数据集">
              <el-select v-model="form.dataset_id" filterable placeholder="选择数据集" style="width: 100%">
                <el-option v-for="dataset in datasets" :key="dataset.id" :label="dataset.name" :value="dataset.id" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="16">
          <el-col :xs="24" :md="8">
            <el-form-item label="运行环境">
              <el-select v-model="form.environment" style="width: 100%">
                <el-option label="生产环境" value="prod" />
                <el-option label="测试环境" value="test" />
                <el-option label="开发环境" value="dev" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :xs="24" :md="8">
            <el-form-item label="优先级">
              <el-select v-model="form.priority" style="width: 100%">
                <el-option label="关键" value="critical" />
                <el-option label="高" value="high" />
                <el-option label="中" value="medium" />
                <el-option label="低" value="low" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :xs="24" :md="8">
            <el-form-item label="运行模式">
              <el-select v-model="form.run_mode" style="width: 100%">
                <el-option label="定时调度" value="scheduled" />
                <el-option label="手动运行" value="manual" />
                <el-option label="增量运行" value="incremental" />
                <el-option label="全量运行" value="full" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="16">
          <el-col :xs="24" :md="8">
            <el-form-item label="Cron 调度">
              <el-input v-model="form.schedule_cron" placeholder="0 2 * * *" />
            </el-form-item>
          </el-col>
          <el-col :xs="24" :md="8">
            <el-form-item label="SLA 分钟">
              <el-input-number v-model="form.sla_minutes" :min="1" :max="1440" controls-position="right" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :xs="24" :md="8">
            <el-form-item label="超时分钟">
              <el-input-number v-model="form.timeout_minutes" :min="1" :max="720" controls-position="right" style="width: 100%" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="16">
          <el-col :xs="24" :md="8">
            <el-form-item label="失败重试">
              <el-input-number v-model="form.retry_count" :min="0" :max="10" controls-position="right" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :xs="24" :md="16">
            <el-form-item label="告警策略">
              <el-checkbox-group v-model="form.alert_channels">
                <el-checkbox label="wechat_work">企业微信</el-checkbox>
                <el-checkbox label="email">邮件</el-checkbox>
                <el-checkbox label="webhook">Webhook</el-checkbox>
              </el-checkbox-group>
              <el-checkbox v-model="form.alert_on_failure">失败时告警</el-checkbox>
            </el-form-item>
          </el-col>
        </el-row>
        <el-alert type="info" :closable="false" show-icon title="默认生成可执行 ETL 模板：抽取源数据 -> 字段标准化 -> 质量闸门 -> 写入目标数据集。" />
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="savePipeline">保存并检查</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="ruleDialogVisible" title="新增质量规则" width="min(640px, calc(100vw - 32px))" destroy-on-close>
      <el-form label-position="top">
        <el-form-item label="规则名称">
          <el-input v-model="ruleForm.name" placeholder="例：订单金额不能为空" />
        </el-form-item>
        <el-row :gutter="16">
          <el-col :xs="24" :md="12">
            <el-form-item label="规则类型">
              <el-select v-model="ruleForm.rule_type" style="width: 100%">
                <el-option label="非空" value="not_null" />
                <el-option label="唯一" value="unique" />
                <el-option label="范围" value="range" />
                <el-option label="正则" value="regex" />
                <el-option label="行数波动" value="row_count" />
                <el-option label="新鲜度" value="freshness" />
                <el-option label="自定义 SQL" value="custom_sql" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :xs="24" :md="12">
            <el-form-item label="字段">
              <el-select v-model="ruleForm.field" filterable allow-create clearable placeholder="选择或输入字段" style="width: 100%">
                <el-option v-for="field in selectedDatasetFields" :key="field" :label="field" :value="field" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="16">
          <el-col :xs="24" :md="12">
            <el-form-item label="操作符">
              <el-select v-model="ruleForm.operator" clearable placeholder="选择操作符" style="width: 100%">
                <el-option label="等于" value="eq" />
                <el-option label="大于等于" value="gte" />
                <el-option label="小于等于" value="lte" />
                <el-option label="匹配" value="match" />
                <el-option label="不超过" value="max" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :xs="24" :md="12">
            <el-form-item label="阈值 / 表达式">
              <el-input v-model="ruleForm.threshold" placeholder="例：0、^[A-Z]+$、select count(*) ..." />
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="严重级别">
          <el-radio-group v-model="ruleForm.severity">
            <el-radio-button label="error">阻断</el-radio-button>
            <el-radio-button label="warning">告警</el-radio-button>
          </el-radio-group>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="ruleDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="savingRule" @click="saveRule">保存规则</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, defineComponent, h, onMounted, reactive, ref, watch } from "vue"
import axios from "axios"
import { ElButton, ElMessage, ElTooltip } from "element-plus"
import CodeMirrorSqlEditor from "@/components/SqlEditor.vue"
import {
  Aim,
  Back,
  CircleCheck,
  Connection,
  CopyDocument,
  DataAnalysis,
  Delete,
  DocumentChecked,
  DocumentCopy,
  Finished,
  FullScreen,
  Grid,
  Histogram,
  Link,
  MagicStick,
  Plus,
  Rank,
  Refresh,
  RefreshRight,
  Right,
  Search,
  Select,
  SetUp,
  Share,
  Tickets,
  UploadFilled,
  VideoPlay,
  View,
  Warning,
} from "@element-plus/icons-vue"
import { Handle, Position, VueFlow } from "@vue-flow/core"
import "@vue-flow/core/dist/style.css"
import "@vue-flow/core/dist/theme-default.css"

type RunMode = "manual" | "scheduled" | "incremental" | "full" | "backfill"
type DagNode = {
  id: string
  type: string
  label?: string
  position?: { x: number; y: number }
  config?: Record<string, any>
}
type DatasetItem = {
  id: number
  name: string
  datasource_id?: number
  fields_json?: { fields?: Array<string | Record<string, any>>; dimensions?: Array<string | Record<string, any>>; metrics?: Array<string | Record<string, any>> } | null
  semantic_model_json?: { dimensions?: Array<Record<string, any>>; measures?: Array<Record<string, any>> } | null
}
type Pipeline = {
  id: number
  name: string
  dataset_id: number
  dag_json: { nodes?: DagNode[]; edges?: Array<Record<string, any>> }
  schedule_cron?: string | null
  run_mode: RunMode
  status: string
  environment: "dev" | "test" | "prod"
  priority: "low" | "medium" | "high" | "critical"
  sla_minutes: number
  retry_count: number
  timeout_minutes: number
  alert_policy_json?: Record<string, any> | null
  current_version?: number
  published_version?: number
  last_run_status?: string | null
}
type QualityRule = {
  id: number
  name: string
  rule_type: string
  field?: string | null
  operator?: string | null
  threshold?: string | null
  severity: string
  is_active: boolean
}
type PipelineRun = {
  id: number
  mode: RunMode
  status: string
  reason?: string | null
  records_read: number
  records_written: number
  records_failed: number
  error_message?: string | null
  node_logs_json?: { summary?: Record<string, any>; nodes?: Array<Record<string, any>> } | null
}
type PipelineValidation = {
  status: "ready" | "warning" | "blocked"
  diagnostics: Array<{ severity: "critical" | "warning"; code: string; message: string; node_id?: string | null }>
  critical_count: number
  warning_count: number
  node_count: number
  edge_count: number
  schedule_cron?: string | null
  run_mode: string
  environment: string
  priority: string
  sla_minutes: number
  retry_count: number
  timeout_minutes: number
}
type PipelineLineage = {
  pipeline_id: number
  source: Record<string, any>
  target: Record<string, any>
  nodes: Array<Record<string, any>>
  edges: Array<Record<string, any>>
}
type OperatorDefinition = {
  type: string
  label: string
  category: string
  icon?: string
  description?: string
  input_ports?: string[]
  output_ports?: string[]
  default_config?: Record<string, any>
  config_schema?: Record<string, any>
}
type InspectFieldProfile = {
  name: string
  type: string
  nullable?: boolean
  null_count?: number
  null_ratio?: number
  unique_count?: number
  sample_values?: any[]
}

const loading = ref(false)
const saving = ref(false)
const savingDag = ref(false)
const running = ref(false)
const validating = ref(false)
const previewing = ref(false)
const inspecting = ref(false)
const lineageLoading = ref(false)
const savingRule = ref(false)
const publishingVersion = ref(false)
const dialogVisible = ref(false)
const ruleDialogVisible = ref(false)
const nodeDrawerVisible = ref(false)
const selectedId = ref<number | null>(null)
const selectedNodeId = ref<string | null>(null)
const draggedNodeType = ref<string | null>(null)
const nodeSearch = ref("")
const pipelineSearch = ref("")
const statusFilter = ref("all")
const activeWorkbenchTab = ref("design")
const detailTab = ref("preview")
const pipelines = ref<Pipeline[]>([])
const datasets = ref<DatasetItem[]>([])
const operatorCatalog = ref<OperatorDefinition[]>([])
const qualityRules = ref<QualityRule[]>([])
const runHistory = ref<PipelineRun[]>([])
const validation = ref<PipelineValidation | null>(null)
const lineage = ref<PipelineLineage | null>(null)
const previewColumns = ref<string[]>([])
const previewRows = ref<Array<Record<string, any>>>([])
const previewLogs = ref<Record<string, any> | null>(null)
const inspectSchema = ref<InspectFieldProfile[]>([])
const inspectProfile = ref<InspectFieldProfile[]>([])
const inspectRows = ref<Array<Record<string, any>>>([])
const inspectMode = ref("in_memory")
const runWindow = ref<[string, string] | null>(null)
const dagUndoStack = ref<Array<{ nodes?: DagNode[]; edges?: Array<Record<string, any>> }>>([])
const dagRedoStack = ref<Array<{ nodes?: DagNode[]; edges?: Array<Record<string, any>> }>>([])
const copiedNode = ref<DagNode | null>(null)
const sqlEditorExtensions = ["sql", "schema-autocomplete", "read-only-select"]

const form = reactive({
  name: "",
  dataset_id: null as number | null,
  schedule_cron: "0 2 * * *",
  run_mode: "scheduled" as RunMode,
  environment: "prod" as "dev" | "test" | "prod",
  priority: "high" as "low" | "medium" | "high" | "critical",
  sla_minutes: 120,
  retry_count: 2,
  timeout_minutes: 60,
  alert_channels: ["wechat_work"] as string[],
  alert_on_failure: true,
})
const runForm = reactive({
  mode: "manual" as RunMode,
  reason: "界面手动运行",
  dry_run: false,
})
const ruleForm = reactive({
  name: "",
  rule_type: "not_null",
  field: "",
  operator: "",
  threshold: "",
  severity: "error",
  is_active: true,
})

const workbenchTabs = [
  { label: "流程设计", value: "design", icon: SetUp },
  { label: "预览数据", value: "preview", icon: View },
  { label: "调度", value: "schedule", icon: Tickets },
  { label: "监控", value: "monitor", icon: DataAnalysis },
  { label: "血缘", value: "lineage", icon: Share },
]
const runModeOptions = [
  { label: "手动", value: "manual" },
  { label: "增量", value: "incremental" },
  { label: "全量", value: "full" },
  { label: "补数", value: "backfill" },
]
const sourcePalette = [
  { name: "MySQL", icon: DataAnalysis },
  { name: "PostgreSQL", icon: DataAnalysis },
  { name: "Excel", icon: DocumentChecked },
  { name: "API", icon: Connection },
  { name: "Kafka", icon: Link },
]
const fallbackNodePalette = [
  { type: "extract", label: "抽取", icon: UploadFilled },
  { type: "metadata_extract", label: "元数据", icon: DocumentChecked },
  { type: "transform", label: "转换", icon: SetUp },
  { type: "join", label: "关联", icon: Link },
  { type: "union", label: "汇合", icon: Connection },
  { type: "sql", label: "SQL 算子", icon: DataAnalysis },
  { type: "transform", label: "聚合", icon: Histogram },
  { type: "quality", label: "校验", icon: Select },
  { type: "load", label: "加载", icon: Finished },
  { type: "reverse_etl", label: "反向 ETL", icon: RefreshRight },
  { type: "transform", label: "自定义", icon: Grid },
]
const calloutGroups = {
  left: [
    { index: 1, title: "向导式创建流程", copy: "分步引导，降低使用门槛；模板推荐，快速起步；流程配置清晰可见。", icon: SetUp },
    { index: 2, title: "拖拽式节点编排", copy: "拖拽连接，简单直观；自动布局，结构清晰；组件丰富，灵活扩展。", icon: Grid },
    { index: 3, title: "即时数据预览与字段映射", copy: "所见即所得的预览体验；智能映射，减少配置成本；类型转换与过滤可视化。", icon: View },
    { index: 4, title: "内联校验与错误提示", copy: "字段级校验状态可视；错误行定位与原因提示；保障数据质量与一致性。", icon: CircleCheck },
  ],
  right: [
    { index: 5, title: "调度、监控、告警一体化", copy: "统一调度配置；运行状态实时监控；异常告警及时触达。", icon: Tickets },
    { index: 6, title: "数据血缘与影响分析", copy: "全链路血缘可视化；影响分析、变更可控；支持追溯与审计。", icon: Share },
    { index: 7, title: "模板复用与权限控制", copy: "流程和节点模板复用；细粒度权限控制；保障数据与操作安全。", icon: Select },
    { index: 8, title: "与 BI 数据集无缝衔接", copy: "一键输出为 BI 数据集；自动同步字段与元数据；快速用于报表与分析。", icon: Histogram },
  ],
}
const featureBenefits = [
  { title: "提升效率", copy: "可视化编排，降低开发成本", icon: UploadFilled },
  { title: "保障质量", copy: "内联校验，数据质量可控", icon: Select },
  { title: "稳定可靠", copy: "调度监控一体化，异常可追溯", icon: Tickets },
  { title: "开放集成", copy: "丰富连接器，支持扩展", icon: Grid },
  { title: "业务赋能", copy: "与 BI 无缝衔接，驱动决策", icon: DataAnalysis },
]
const referenceFlowNodes = [
  { stageId: "source", nodeId: "extract", title: "数据源", subtitle: "订单数据", meta: "MySQL", icon: DataAnalysis, tone: "blue" },
  { stageId: "clean", nodeId: "transform", title: "清洗", subtitle: "去重去空值", meta: "标准化", icon: UploadFilled, tone: "teal" },
  { stageId: "transform", nodeId: "transform", title: "转换", subtitle: "字段映射", meta: "类型转换", icon: SetUp, tone: "indigo" },
  { stageId: "aggregate", nodeId: "transform", title: "聚合", subtitle: "按日汇总", meta: "统计聚合", icon: Histogram, tone: "purple" },
  { stageId: "quality", nodeId: "quality", title: "校验", subtitle: "规则校验", meta: "数据质量", icon: Select, tone: "orange" },
  { stageId: "load", nodeId: "load", title: "加载到数仓", subtitle: "DWS 层", meta: "fact_order_d", icon: Finished, tone: "cyan" },
]
const fieldMappingPreview = [
  { source: "order_id", target: "订单ID", type: "BIGINT" },
  { source: "user_id", target: "用户ID", type: "BIGINT" },
  { source: "amount", target: "订单金额", type: "DECIMAL(18,2)" },
  { source: "create_time", target: "下单时间", type: "TIMESTAMP" },
  { source: "status", target: "订单状态", type: "STRING" },
]
const referencePreviewColumns = ["订单ID", "用户ID", "订单金额", "下单时间", "订单状态", "校验状态"]
const referencePreviewRows = [
  { 订单ID: "1000001", 用户ID: "20001", 订单金额: "1,250.00", 下单时间: "2024-05-20 10:15:30", 订单状态: "PAID", 校验状态: "通过" },
  { 订单ID: "1000002", 用户ID: "20002", 订单金额: "299.90", 下单时间: "2024-05-20 10:16:12", 订单状态: "COMPLETE", 校验状态: "通过" },
  { 订单ID: "1000003", 用户ID: "20003", 订单金额: "880.00", 下单时间: "2024-05-20 10:18:05", 订单状态: "PAID", 校验状态: "通过" },
  { 订单ID: "1000004", 用户ID: "20004", 订单金额: "1,599.00", 下单时间: "2024-05-20 10:18:55", 订单状态: "CANCELLED", 校验状态: "警告" },
  { 订单ID: "1000005", 用户ID: "20005", 订单金额: "499.00", 下单时间: "2024-05-20 10:20:03", 订单状态: "PAID", 校验状态: "通过" },
]

const selectedPipeline = computed(() => pipelines.value.find((item) => item.id === selectedId.value) || pipelines.value[0] || null)
const selectedNode = computed<DagNode | null>(() => {
  const nodes = selectedPipeline.value?.dag_json?.nodes || []
  return nodes.find((node) => String(node.id) === selectedNodeId.value) || nodes[0] || null
})
const selectedNodeConfig = computed<Record<string, any>>(() => {
  if (!selectedNode.value) return {}
  selectedNode.value.config ||= {}
  return selectedNode.value.config
})
const iconRegistry: Record<string, any> = {
  CircleCheck,
  Connection,
  DataAnalysis,
  DocumentChecked,
  Finished,
  Grid,
  Histogram,
  Link,
  RefreshRight,
  Select,
  SetUp,
  UploadFilled,
}
const operatorIcon = (name?: string) => iconRegistry[name || ""] || Grid
const nodeIconKey = (type: string) => ({
  source: "source",
  extract: "extract",
  metadata_extract: "metadata",
  transform: "transform",
  join: "join",
  union: "union",
  sql: "sql",
  quality: "quality",
  load: "load",
  sink: "load",
  reverse_etl: "reverse",
}[type] || "task")
const nodeTone = (type: string) => ({
  source: "blue",
  extract: "blue",
  metadata_extract: "indigo",
  transform: "teal",
  join: "violet",
  union: "cyan",
  sql: "slate",
  quality: "amber",
  load: "emerald",
  sink: "emerald",
  reverse_etl: "rose",
}[type] || "teal")
const nodePalette = computed(() => {
  if (!operatorCatalog.value.length) return fallbackNodePalette
  return operatorCatalog.value.map((operator) => ({
    type: operator.type,
    label: operator.label,
    category: operator.category,
    description: operator.description,
    icon: operatorIcon(operator.icon),
    default_config: operator.default_config || {},
  }))
})
const operatorGroups = computed(() => {
  const groups = new Map<string, Array<Record<string, any>>>()
  for (const node of nodePalette.value) {
    const category = node.category || "其他"
    groups.set(category, [...(groups.get(category) || []), node])
  }
  return Array.from(groups, ([category, nodes]) => ({ category, nodes }))
})
const filteredPipelines = computed(() => {
  const keyword = pipelineSearch.value.trim().toLowerCase()
  return pipelines.value.filter((item) => {
    const matchesStatus = statusFilter.value === "all" || item.status === statusFilter.value || item.last_run_status === statusFilter.value
    const matchesKeyword = !keyword || `${item.name} ${datasetName(item.dataset_id)}`.toLowerCase().includes(keyword)
    return matchesStatus && matchesKeyword
  })
})
const statusTabs = computed(() => [
  { label: "全部", value: "all", count: pipelines.value.length },
  { label: "激活", value: "active", count: pipelines.value.filter((item) => item.status === "active").length },
  { label: "草稿", value: "draft", count: pipelines.value.filter((item) => item.status === "draft").length },
  { label: "失败", value: "failed", count: pipelines.value.filter((item) => item.last_run_status === "failed").length },
])
const summaryStats = computed(() => ({
  prod: pipelines.value.filter((item) => item.environment === "prod").length,
  active: pipelines.value.filter((item) => item.status === "active").length,
  failed: pipelines.value.filter((item) => item.last_run_status === "failed").length,
  tightSla: pipelines.value.filter((item) => (item.sla_minutes || 120) <= 120).length,
}))
const lastRun = computed(() => runHistory.value[0] || null)
const latestNodeLogs = computed(() => previewLogs.value?.nodes || lastRun.value?.node_logs_json?.nodes || [])
const activeDiagnostics = computed(() => validation.value?.diagnostics || [])
const selectedNodeLog = computed(() => latestNodeLogs.value.find((item: any) => String(item.node_id) === String(selectedNode.value?.id)) || null)
const selectedNodeDiagnostics = computed(() => activeDiagnostics.value.filter((item) => String(item.node_id || "") === String(selectedNode.value?.id || "")))
const selectedNodeStatus = computed(() => {
  if (!selectedNode.value) return "empty"
  if (selectedNodeLog.value?.status) return String(selectedNodeLog.value.status)
  if (selectedNodeDiagnostics.value.some((item) => item.severity === "critical")) return "blocked"
  if (selectedNodeDiagnostics.value.length) return "warning"
  const config = selectedNode.value.config || {}
  if (selectedNode.value.type === "sql" && !String(config.sql || "").trim()) return "blocked"
  if (selectedNode.value.type === "reverse_etl" && !String(config.target_table || "").trim()) return "blocked"
  return "configured"
})
const selectedNodeStatusText = computed(() => {
  const labels: Record<string, string> = {
    empty: "未选择",
    configured: "已配置",
    success: "预览成功",
    failed: "运行失败",
    warning: "需要关注",
    blocked: "缺少配置",
    skipped: "已跳过",
  }
  return labels[selectedNodeStatus.value] || selectedNodeStatus.value
})
const validationStatusText = computed(() => {
  if (!validation.value) return "等待上线检查"
  if (validation.value.status === "ready") return "上线检查通过"
  if (validation.value.status === "blocked") return "存在阻断项"
  return "存在优化建议"
})
const validationTagType = computed(() => {
  if (!validation.value) return "info"
  if (validation.value.status === "ready") return "success"
  if (validation.value.status === "blocked") return "danger"
  return "warning"
})
const validationIconClass = computed(() => `validation-icon validation-icon--${validation.value?.status || "empty"}`)
const selectedDatasetFields = computed(() => {
  const dataset = datasets.value.find((item) => item.id === selectedPipeline.value?.dataset_id)
  if (!dataset) return []
  const names = new Set<string>()
  const collect = (items?: Array<string | Record<string, any>>) => {
    for (const item of items || []) {
      if (typeof item === "string") names.add(item.split(".").pop() || item)
      else if (item?.name) names.add(String(item.name).split(".").pop() || String(item.name))
    }
  }
  collect(dataset.fields_json?.fields)
  collect(dataset.fields_json?.dimensions)
  collect(dataset.fields_json?.metrics)
  collect(dataset.semantic_model_json?.dimensions)
  collect(dataset.semantic_model_json?.measures)
  return Array.from(names)
})
const upstreamCandidates = computed(() => {
  const nodes = selectedPipeline.value?.dag_json?.nodes || []
  return nodes.filter((node) => String(node.id) !== String(selectedNode.value?.id))
})
const nodeStatusFor = (node: DagNode) => {
  const log = latestNodeLogs.value.find((item: any) => String(item.node_id) === String(node.id))
  if (log?.status) return String(log.status)
  const diagnostics = activeDiagnostics.value.filter((item) => String(item.node_id || "") === String(node.id))
  if (diagnostics.some((item) => item.severity === "critical")) return "blocked"
  if (diagnostics.length) return "warning"
  const config = node.config || {}
  if (node.type === "sql" && !String(config.sql || "").trim()) return "blocked"
  if (node.type === "reverse_etl" && !String(config.target_table || "").trim()) return "blocked"
  return "configured"
}
const flowNodes = computed(() => {
  const runNodeLogs = latestNodeLogs.value
  const nodes = selectedPipeline.value?.dag_json?.nodes || []
  return nodes.map((node, index) => {
    const log = runNodeLogs.find((item: any) => String(item.node_id) === String(node.id))
    const status = nodeStatusFor(node)
    const typeLabel = nodeTypeLabel(String(node.type || "task"))
    const title = String(node.label || node.id)
    const rowsText = log ? `${log.rows_out ?? log.records_written ?? 0} 行` : ""
    const statusText = nodeStatusText(status)
    return {
      id: String(node.id),
      type: "etl-icon",
      label: title,
      position: node.position || { x: 72 + (index % 4) * 190, y: 72 + Math.floor(index / 4) * 118 },
      sourcePosition: Position.Bottom,
      targetPosition: Position.Top,
      data: {
        type: node.type || "task",
        iconKey: nodeIconKey(String(node.type || "task")),
        tone: nodeTone(String(node.type || "task")),
        title,
        caption: `${typeLabel} · ${rowsText || statusText}`,
        status,
        statusText,
      },
      ariaLabel: `${typeLabel} ${title} ${statusText}`,
      class: `etl-node etl-node--${node.type || "task"} ${selectedNodeId.value === String(node.id) ? "is-selected" : ""} is-${status}`,
    }
  })
})
const flowEdges = computed(() => {
  const edges = selectedPipeline.value?.dag_json?.edges || []
  return edges.map((edge, index) => ({
    id: `edge-${index}`,
    source: String(edge.source),
    target: String(edge.target),
    animated: selectedPipeline.value?.status === "active",
  }))
})
const aggregationConfig = computed(() => {
  selectedNodeConfig.value.aggregations ||= { group_by: [], metrics: [] }
  selectedNodeConfig.value.aggregations.group_by ||= []
  selectedNodeConfig.value.aggregations.metrics ||= []
  return selectedNodeConfig.value.aggregations
})
const aggregationMetrics = computed<Array<Record<string, any>>>(() => aggregationConfig.value.metrics)
const aggregationGroupByText = computed({
  get: () => (aggregationConfig.value.group_by || []).join(", "),
  set: (value: string) => {
    aggregationConfig.value.group_by = splitCsv(value)
  },
})
const dedupeKeysText = computed({
  get: () => ((selectedNodeConfig.value.dedupe?.keys || []) as string[]).join(", "),
  set: (value: string) => {
    selectedNodeConfig.value.dedupe ||= { keep: "first" }
    selectedNodeConfig.value.dedupe.keys = splitCsv(value)
  },
})
const metadataTablesText = computed({
  get: () => ((selectedNodeConfig.value.tables || []) as string[]).join(", "),
  set: (value: string) => {
    selectedNodeConfig.value.tables = splitCsv(value)
  },
})
const unionKeysText = computed({
  get: () => ((selectedNodeConfig.value.keys || []) as string[]).join(", "),
  set: (value: string) => {
    selectedNodeConfig.value.keys = splitCsv(value)
  },
})
const reverseEtlKeysText = computed({
  get: () => ((selectedNodeConfig.value.upsert_keys || []) as string[]).join(", "),
  set: (value: string) => {
    selectedNodeConfig.value.upsert_keys = splitCsv(value)
  },
})
const alertPolicyText = computed(() => {
  const policy = selectedPipeline.value?.alert_policy_json || {}
  if (!policy.on_failure) return "未开启"
  const channels = Array.isArray(policy.channels) ? policy.channels : []
  return channels.length ? channels.join(", ") : "失败告警"
})
const successRate = computed(() => {
  if (!runHistory.value.length) return 100
  const success = runHistory.value.filter((item) => item.status === "success").length
  return Math.round((success / runHistory.value.length) * 100)
})
const lineageSourceText = computed(() => {
  const sources = lineage.value?.source?.sources
  if (Array.isArray(sources) && sources.length) return `${sources.length} 个来源`
  return lineage.value?.source?.table || "-"
})
const previewDisplayColumns = computed(() => previewColumns.value.length ? previewColumns.value.slice(0, 6) : referencePreviewColumns)
const previewDisplayRows = computed(() => previewRows.value.length ? previewRows.value.slice(0, 5) : referencePreviewRows)

const cloneDag = (dag?: { nodes?: DagNode[]; edges?: Array<Record<string, any>> }) => JSON.parse(JSON.stringify(dag || { nodes: [], edges: [] }))
const recordDagSnapshot = () => {
  if (!selectedPipeline.value) return
  dagUndoStack.value.push(cloneDag(selectedPipeline.value.dag_json))
  if (dagUndoStack.value.length > 50) dagUndoStack.value.shift()
  dagRedoStack.value = []
}
const replaceDagSnapshot = (snapshot: { nodes?: DagNode[]; edges?: Array<Record<string, any>> }) => {
  if (!selectedPipeline.value) return
  selectedPipeline.value.dag_json = cloneDag(snapshot)
  selectedNodeId.value = selectedPipeline.value.dag_json.nodes?.[0]?.id || null
}
const splitCsv = (value: string) => value.split(",").map((item) => item.trim()).filter(Boolean)
const datasetName = (id: number) => datasets.value.find((item) => item.id === id)?.name || `数据集 #${id}`
const defaultDag = () => ({
  nodes: [
    { id: "extract", type: "extract", label: "抽取源数据", position: { x: 80, y: 120 }, config: { connector: "database", incremental_key: "updated_at" } },
    {
      id: "transform",
      type: "transform",
      label: "标准化转换",
      position: { x: 300, y: 120 },
      config: {
        field_mapping: [],
        type_conversions: [],
        filters: [],
        derived_columns: [],
        dedupe: { keys: [], keep: "first" },
        aggregations: { group_by: [], metrics: [] },
      },
    },
    { id: "quality", type: "quality", label: "质量闸门", position: { x: 520, y: 120 }, config: { fail_fast: true } },
    { id: "load", type: "load", label: "写入目标数据集", position: { x: 740, y: 120 }, config: { mode: "dataset_refresh", target_table: "" } },
  ],
  edges: [
    { source: "extract", target: "transform" },
    { source: "transform", target: "quality" },
    { source: "quality", target: "load" },
  ],
})

const environmentLabel = (value?: string) => ({ prod: "生产", test: "测试", dev: "开发" }[value || "prod"] || "生产")
const priorityLabel = (value?: string) => ({ critical: "关键", high: "高优先级", medium: "中优先级", low: "低优先级" }[value || "medium"] || "中优先级")
const pipelineStatusLabel = (value: string) => ({ draft: "草稿", active: "激活", paused: "暂停", archived: "归档" }[value] || value)
const pipelineStatusType = (item: Pipeline) => item.last_run_status === "failed" ? "danger" : item.status === "active" ? "success" : item.status === "paused" ? "warning" : "info"
const runStatusLabel = (value: string) => ({ success: "成功", failed: "失败", running: "运行中" }[value] || value)
const runModeLabel = (value: string) => ({ manual: "手动", scheduled: "调度", incremental: "增量", full: "全量", backfill: "补数" }[value] || value)
const ruleTypeLabel = (value: string) => ({ not_null: "非空", unique: "唯一", range: "范围", regex: "正则", row_count: "行数波动", freshness: "新鲜度", custom_sql: "自定义 SQL" }[value] || value)
const severityLabel = (value: string) => ({ error: "阻断", warning: "告警" }[value] || value)
const nodeStatusText = (value: string) => ({ configured: "已配置", success: "成功", failed: "失败", warning: "建议", blocked: "缺配置", skipped: "跳过" }[value] || value)
const nodeTypeLabel = (value: string) => ({ source: "源", extract: "抽取", metadata_extract: "元数据", transform: "转换", join: "关联", union: "汇合", sql: "SQL 算子", quality: "质检", load: "装载", sink: "目标", reverse_etl: "反向 ETL" }[value] || "任务")
const runWindowLabel = (run: PipelineRun) => {
  const window = run.node_logs_json?.summary?.run_window
  if (!window?.start && !window?.end) return "-"
  return `${window.start || "-"} 至 ${window.end || "-"}`
}

const listConfig = (key: string) => {
  selectedNodeConfig.value[key] ||= []
  return selectedNodeConfig.value[key]
}
const appendListConfig = (key: string, value: Record<string, any>) => {
  listConfig(key).push({ ...value })
}
const removeListConfig = (key: string, index: number) => {
  listConfig(key).splice(index, 1)
}
const appendAggregationMetric = () => {
  aggregationConfig.value.metrics.push({ field: "", function: "sum", alias: "" })
}
const removeAggregationMetric = (index: number) => {
  aggregationConfig.value.metrics.splice(index, 1)
}
const onNodeClick = ({ node }: { node: { id: string } }) => {
  selectedNodeId.value = node.id
  nodeDrawerVisible.value = true
}
const onPaletteDragStart = (type: string) => {
  draggedNodeType.value = type
}
const onCanvasDrop = (event: DragEvent) => {
  if (!draggedNodeType.value || !selectedPipeline.value) return
  const target = event.currentTarget as HTMLElement | null
  const rect = target?.getBoundingClientRect()
  const position = rect
    ? { x: Math.max(24, event.clientX - rect.left - 75), y: Math.max(24, event.clientY - rect.top - 28) }
    : undefined
  addNode(draggedNodeType.value, position)
  draggedNodeType.value = null
}
const onConnect = (connection: any) => {
  if (!selectedPipeline.value || !connection?.source || !connection?.target) return
  selectedPipeline.value.dag_json ||= { nodes: [], edges: [] }
  selectedPipeline.value.dag_json.edges ||= []
  const exists = selectedPipeline.value.dag_json.edges.some((edge) => String(edge.source) === String(connection.source) && String(edge.target) === String(connection.target))
  if (!exists) {
    recordDagSnapshot()
    selectedPipeline.value.dag_json.edges.push({ source: String(connection.source), target: String(connection.target) })
  }
}
const onNodeDragStop = ({ node }: any) => {
  const dagNode = selectedPipeline.value?.dag_json?.nodes?.find((item) => String(item.id) === String(node?.id))
  if (dagNode && node?.position) {
    recordDagSnapshot()
    dagNode.position = { x: Number(node.position.x || 0), y: Number(node.position.y || 0) }
  }
}
const selectReferenceNode = (nodeId: string) => {
  selectedNodeId.value = nodeId
}
const selectPipeline = (id: number) => {
  selectedId.value = id
  nodeDrawerVisible.value = false
  const pipeline = pipelines.value.find((item) => item.id === id)
  selectedNodeId.value = pipeline?.dag_json?.nodes?.[0]?.id || null
  dagUndoStack.value = []
  dagRedoStack.value = []
}
const undoDagChange = () => {
  if (!selectedPipeline.value || !dagUndoStack.value.length) return
  dagRedoStack.value.push(cloneDag(selectedPipeline.value.dag_json))
  replaceDagSnapshot(dagUndoStack.value.pop()!)
}
const redoDagChange = () => {
  if (!selectedPipeline.value || !dagRedoStack.value.length) return
  dagUndoStack.value.push(cloneDag(selectedPipeline.value.dag_json))
  replaceDagSnapshot(dagRedoStack.value.pop()!)
}
const copySelectedNode = () => {
  if (!selectedNode.value) return
  copiedNode.value = cloneDag({ nodes: [selectedNode.value], edges: [] }).nodes?.[0] || null
  ElMessage.success("节点已复制")
}
const pasteCopiedNode = () => {
  if (!selectedPipeline.value || !copiedNode.value) return
  recordDagSnapshot()
  const index = (selectedPipeline.value.dag_json.nodes || []).length + 1
  const id = `${copiedNode.value.type}_${Date.now()}`
  const sourcePosition = copiedNode.value.position || { x: 80, y: 120 }
  const node = {
    ...cloneDag({ nodes: [copiedNode.value], edges: [] }).nodes[0],
    id,
    label: `${copiedNode.value.label || nodeTypeLabel(copiedNode.value.type)} 副本`,
    position: { x: sourcePosition.x + 40, y: sourcePosition.y + 40 + (index % 3) * 8 },
  }
  selectedPipeline.value.dag_json.nodes ||= []
  selectedPipeline.value.dag_json.nodes.push(node)
  selectedNodeId.value = id
  nodeDrawerVisible.value = true
}
const deleteSelectedNode = () => {
  if (!selectedPipeline.value || !selectedNode.value) return
  recordDagSnapshot()
  const nodeId = String(selectedNode.value.id)
  selectedPipeline.value.dag_json.nodes = (selectedPipeline.value.dag_json.nodes || []).filter((node) => String(node.id) !== nodeId)
  selectedPipeline.value.dag_json.edges = (selectedPipeline.value.dag_json.edges || []).filter((edge) => String(edge.source) !== nodeId && String(edge.target) !== nodeId)
  selectedNodeId.value = selectedPipeline.value.dag_json.nodes?.[0]?.id || null
  nodeDrawerVisible.value = false
}
const autoLayoutDag = () => {
  if (!selectedPipeline.value) return
  recordDagSnapshot()
  const nodes = selectedPipeline.value.dag_json.nodes || []
  nodes.forEach((node, index) => {
    node.position = { x: 90 + (index % 4) * 230, y: 96 + Math.floor(index / 4) * 150 }
  })
}
const fitCanvasView = () => {
  autoLayoutDag()
}
const locateSearchedNode = () => {
  const keyword = nodeSearch.value.trim().toLowerCase()
  if (!keyword || !selectedPipeline.value) return
  const target = (selectedPipeline.value.dag_json.nodes || []).find((node) => `${node.label || ""} ${node.id} ${node.type}`.toLowerCase().includes(keyword))
  if (!target) {
    ElMessage.warning("未找到匹配节点")
    return
  }
  selectedNodeId.value = String(target.id)
  nodeDrawerVisible.value = true
}
const addNode = (type: string, position?: { x: number; y: number }) => {
  if (!selectedPipeline.value) return
  recordDagSnapshot()
  selectedPipeline.value.dag_json ||= { nodes: [], edges: [] }
  selectedPipeline.value.dag_json.nodes ||= []
  selectedPipeline.value.dag_json.edges ||= []
  const index = selectedPipeline.value.dag_json.nodes.length + 1
  const id = `${type}_${Date.now()}`
  const previous = selectedPipeline.value.dag_json.nodes[selectedPipeline.value.dag_json.nodes.length - 1]
  selectedPipeline.value.dag_json.nodes.push({
    id,
    type,
    label: `${nodeTypeLabel(type)}节点 ${index}`,
    position: position || { x: 80 + (index - 1) * 190, y: 120 + Math.floor((index - 1) / 4) * 120 },
    config: defaultNodeConfig(type),
  })
  if (previous) selectedPipeline.value.dag_json.edges.push({ source: previous.id, target: id })
  selectedNodeId.value = id
  nodeDrawerVisible.value = true
}
const defaultNodeConfig = (type: string) => {
  const operatorDefault = operatorCatalog.value.find((operator) => operator.type === type)?.default_config
  if (operatorDefault) {
    const config = cloneDag({ nodes: [{ id: "config", type, config: operatorDefault }], edges: [] }).nodes[0].config || {}
    const datasourceId = datasets.value.find((item) => item.id === selectedPipeline.value?.dataset_id)?.datasource_id
    if (datasourceId && Object.prototype.hasOwnProperty.call(config, "datasource_id") && !config.datasource_id) config.datasource_id = datasourceId
    return config
  }
  if (type === "transform") return { field_mapping: [], type_conversions: [], filters: [], derived_columns: [], dedupe: { keys: [] }, aggregations: { group_by: [], metrics: [] } }
  if (type === "extract" || type === "source") return { mode: "full", incremental_key: "", batch_size: 5000 }
  if (type === "metadata_extract") {
    const datasourceId = datasets.value.find((item) => item.id === selectedPipeline.value?.dataset_id)?.datasource_id
    return { datasource_id: datasourceId, tables: [], refresh_schema: true, write_to_catalog: true }
  }
  if (type === "join") return { left_node_id: "", right_node_id: "", left_key: "", right_key: "", join_type: "inner" }
  if (type === "union") return { mode: "all", keys: [] }
  if (type === "sql") {
    const datasourceId = datasets.value.find((item) => item.id === selectedPipeline.value?.dataset_id)?.datasource_id
    return { execution_mode: "in_memory", sql: "SELECT * FROM input", datasource_id: datasourceId, target_table: "" }
  }
  if (type === "load" || type === "sink") return { mode: "dataset_refresh", target_table: "" }
  if (type === "reverse_etl") {
    const datasourceId = datasets.value.find((item) => item.id === selectedPipeline.value?.dataset_id)?.datasource_id
    return { target_type: "database", datasource_id: datasourceId, target_table: "", mode: "upsert", primary_key: "", upsert_keys: [], field_mapping: [] }
  }
  return {}
}
const addTemplateNodes = () => {
  if (!selectedPipeline.value) return
  recordDagSnapshot()
  selectedPipeline.value.dag_json = defaultDag()
  selectedNodeId.value = "extract"
  nodeDrawerVisible.value = false
}

const Background = defineComponent({
  name: "Background",
  setup: () => () => h("div", { class: "flow-background-grid", "aria-hidden": "true" }),
})
const Controls = defineComponent({
  name: "Controls",
  setup: () => () =>
    h("div", { class: "flow-controls", role: "toolbar", "aria-label": "画布视图控制" }, [
      h(ElTooltip, { content: "适配视图", placement: "top" }, {
        default: () => h(ElButton, { class: "flow-control-button", size: "small", icon: FullScreen, onClick: fitCanvasView, "aria-label": "适配视图" }, () => "适配"),
      }),
      h(ElTooltip, { content: "自动布局", placement: "top" }, {
        default: () => h(ElButton, { class: "flow-control-button", size: "small", icon: Rank, onClick: autoLayoutDag, "aria-label": "自动布局" }, () => "布局"),
      }),
    ]),
})
const MiniMap = defineComponent({
  name: "MiniMap",
  setup: () => () =>
    h("div", { class: "flow-minimap", "aria-label": "画布小地图" }, [
      h("span", "MiniMap"),
      ...flowNodes.value.slice(0, 12).map((node) =>
        h("i", {
          key: node.id,
          class: node.id === selectedNodeId.value ? "is-active" : "",
          style: {
            left: `${Math.min(86, Math.max(6, (Number(node.position?.x || 0) / 900) * 100))}%`,
            top: `${Math.min(78, Math.max(22, (Number(node.position?.y || 0) / 520) * 100))}%`,
          },
        }),
      ),
    ]),
})

const loadSelectedDetails = async () => {
  const current = selectedPipeline.value
  if (!current) {
    qualityRules.value = []
    runHistory.value = []
    validation.value = null
    lineage.value = null
    inspectSchema.value = []
    inspectProfile.value = []
    inspectRows.value = []
    return
  }
  try {
    const [ruleResp, runResp, validationResp] = await Promise.all([
      axios.get("/api/quality-rules", { params: { pipeline_id: current.id } }),
      axios.get(`/api/pipelines/${selectedPipeline.value.id}/runs`),
      axios.post(`/api/pipelines/${selectedPipeline.value.id}/validate`),
    ])
    if (selectedPipeline.value?.id !== current.id) return
    qualityRules.value = ruleResp.data || []
    runHistory.value = runResp.data || []
    validation.value = validationResp.data || null
    selectedNodeId.value = selectedPipeline.value?.dag_json?.nodes?.[0]?.id || null
    previewLogs.value = runHistory.value[0]?.node_logs_json || null
    inspectSchema.value = []
    inspectProfile.value = []
    inspectRows.value = []
  } catch (error: any) {
    ElMessage.error(error.response?.data?.detail || "管道详情加载失败")
  }
}

const loadAll = async () => {
  loading.value = true
  try {
    const [pipelineResp, datasetResp, operatorResp] = await Promise.all([
      axios.get("/api/pipelines"),
      axios.get("/api/datasets"),
      axios.get("/api/pipelines/operators"),
    ])
    pipelines.value = pipelineResp.data || []
    datasets.value = datasetResp.data.items || []
    operatorCatalog.value = operatorResp.data || []
    selectedId.value = pipelines.value.some((item) => item.id === selectedId.value) ? selectedId.value : pipelines.value[0]?.id || null
    await loadSelectedDetails()
  } catch (error: any) {
    ElMessage.error(error.response?.data?.detail || "数据加工管道加载失败")
  } finally {
    loading.value = false
  }
}

const validateSelected = async () => {
  if (!selectedPipeline.value) return
  validating.value = true
  try {
    const { data } = await axios.post(`/api/pipelines/${selectedPipeline.value.id}/validate`)
    validation.value = data
    ElMessage[data.status === "blocked" ? "warning" : "success"](data.status === "ready" ? "上线检查通过" : "上线检查已完成")
  } catch (error: any) {
    ElMessage.error(error.response?.data?.detail || "上线检查失败")
  } finally {
    validating.value = false
  }
}

const previewSelectedNode = async () => {
  if (!selectedPipeline.value) return
  previewing.value = true
  try {
    const { data } = await axios.post(`/api/pipelines/${selectedPipeline.value.id}/preview`, {
      node_id: selectedNode.value?.id,
      limit: 100,
      dag_json: selectedPipeline.value.dag_json,
    })
    previewColumns.value = data.columns || []
    previewRows.value = data.rows || []
    previewLogs.value = data.node_logs_json || null
    inspectSchema.value = data.schema || []
    inspectProfile.value = data.profile || []
    inspectRows.value = data.rows || []
    inspectMode.value = data.execution_mode || "in_memory"
    detailTab.value = "preview"
    activeWorkbenchTab.value = "preview"
  } catch (error: any) {
    ElMessage.error(error.response?.data?.detail || "节点预览失败")
  } finally {
    previewing.value = false
  }
}

const inspectSelectedNode = async () => {
  if (!selectedPipeline.value) return
  inspecting.value = true
  try {
    const { data } = await axios.post(`/api/pipelines/${selectedPipeline.value.id}/inspect`, {
      node_id: selectedNode.value?.id,
      limit: 100,
      dag_json: selectedPipeline.value.dag_json,
    })
    inspectSchema.value = data.schema || []
    inspectProfile.value = data.profile || []
    inspectRows.value = data.rows || []
    inspectMode.value = data.execution_mode || "in_memory"
    previewColumns.value = data.columns || previewColumns.value
    previewRows.value = data.rows || previewRows.value
    previewLogs.value = data.node_logs_json || previewLogs.value
    detailTab.value = "inspect"
  } catch (error: any) {
    ElMessage.error(error.response?.data?.detail || "字段画像加载失败")
  } finally {
    inspecting.value = false
  }
}

const loadLineage = async () => {
  if (!selectedPipeline.value) return
  lineageLoading.value = true
  try {
    const { data } = await axios.get(`/api/pipelines/${selectedPipeline.value.id}/lineage`)
    lineage.value = data
  } catch (error: any) {
    ElMessage.error(error.response?.data?.detail || "血缘加载失败")
  } finally {
    lineageLoading.value = false
  }
}

const savePipelineDag = async () => {
  if (!selectedPipeline.value) return false
  savingDag.value = true
  try {
    const { data } = await axios.put(`/api/pipelines/${selectedPipeline.value.id}`, {
      dag_json: selectedPipeline.value.dag_json,
    })
    const index = pipelines.value.findIndex((item) => item.id === data.id)
    if (index >= 0) pipelines.value[index] = data
    ElMessage.success("流程配置已保存")
    await validateSelected()
    return true
  } catch (error: any) {
    ElMessage.error(error.response?.data?.detail || "保存流程失败")
    return false
  } finally {
    savingDag.value = false
  }
}

const publishSelectedVersion = async () => {
  if (!selectedPipeline.value) return
  publishingVersion.value = true
  try {
    const saved = await savePipelineDag()
    if (!saved) return
    const { data } = await axios.post(`/api/pipelines/${selectedPipeline.value.id}/versions/publish`)
    const index = pipelines.value.findIndex((item) => item.id === selectedPipeline.value?.id)
    if (index >= 0) {
      pipelines.value[index] = {
        ...pipelines.value[index],
        current_version: data.version,
        published_version: data.version,
        status: pipelines.value[index].status === "draft" ? "active" : pipelines.value[index].status,
      }
    }
    ElMessage.success(`管道版本 v${data.version} 已发布`)
  } catch (error: any) {
    ElMessage.error(error.response?.data?.detail || "发布版本失败")
  } finally {
    publishingVersion.value = false
  }
}

const openCreate = () => {
  form.name = ""
  form.dataset_id = datasets.value[0]?.id || null
  form.schedule_cron = "0 2 * * *"
  form.run_mode = "scheduled"
  form.environment = "prod"
  form.priority = "high"
  form.sla_minutes = 120
  form.retry_count = 2
  form.timeout_minutes = 60
  form.alert_channels = ["wechat_work"]
  form.alert_on_failure = true
  dialogVisible.value = true
}

const savePipeline = async () => {
  if (!form.name.trim() || !form.dataset_id) {
    ElMessage.warning("请填写管道名称并选择数据集")
    return
  }
  saving.value = true
  try {
    const { data } = await axios.post("/api/pipelines", {
      name: form.name,
      dataset_id: form.dataset_id,
      schedule_cron: form.schedule_cron,
      run_mode: form.run_mode,
      environment: form.environment,
      priority: form.priority,
      sla_minutes: form.sla_minutes,
      retry_count: form.retry_count,
      timeout_minutes: form.timeout_minutes,
      alert_policy_json: {
        channels: form.alert_channels,
        on_failure: form.alert_on_failure,
      },
      dag_json: defaultDag(),
    })
    ElMessage.success("数据加工管道已创建")
    dialogVisible.value = false
    await loadAll()
    selectedId.value = data.id
    await loadSelectedDetails()
  } catch (error: any) {
    ElMessage.error(error.response?.data?.detail || "保存失败")
  } finally {
    saving.value = false
  }
}

const runSelected = async (mode?: RunMode) => {
  if (!selectedPipeline.value) return
  const runMode = mode || runForm.mode
  running.value = true
  try {
    const [window_start, window_end] = runMode === "backfill" && runWindow.value ? runWindow.value : [null, null]
    const { data } = await axios.post(`/api/pipelines/${selectedPipeline.value.id}/run`, {
      mode: runMode,
      reason: runForm.reason || (runMode === "backfill" ? "界面触发补数" : "界面手动运行"),
      window_start,
      window_end,
      dry_run: runForm.dry_run,
    })
    runHistory.value = [data, ...runHistory.value.filter((item) => item.id !== data.id)]
    previewLogs.value = data.node_logs_json || null
    if (data.status === "failed") {
      ElMessage.error(data.error_message || "管道运行失败")
    } else {
      ElMessage.success(runMode === "backfill" ? "补数任务执行完成" : "管道运行完成")
    }
    await loadAll()
  } catch (error: any) {
    ElMessage.error(error.response?.data?.detail || "运行失败")
  } finally {
    running.value = false
  }
}

const runBackfill = () => {
  runForm.mode = "backfill"
  runForm.reason = runForm.reason || "界面触发补数"
  runSelected("backfill")
}

const openRuleCreate = () => {
  ruleForm.name = ""
  ruleForm.rule_type = "not_null"
  ruleForm.field = selectedDatasetFields.value[0] || ""
  ruleForm.operator = ""
  ruleForm.threshold = ""
  ruleForm.severity = "error"
  ruleForm.is_active = true
  ruleDialogVisible.value = true
}

const saveRule = async () => {
  if (!selectedPipeline.value || !ruleForm.name.trim()) {
    ElMessage.warning("请填写质量规则名称")
    return
  }
  savingRule.value = true
  try {
    await axios.post("/api/quality-rules", {
      ...ruleForm,
      pipeline_id: selectedPipeline.value.id,
      dataset_id: selectedPipeline.value.dataset_id,
    })
    ElMessage.success("质量规则已保存")
    ruleDialogVisible.value = false
    await loadSelectedDetails()
  } catch (error: any) {
    ElMessage.error(error.response?.data?.detail || "质量规则保存失败")
  } finally {
    savingRule.value = false
  }
}

watch(() => selectedPipeline.value?.id, () => {
  loadSelectedDetails()
})
watch(activeWorkbenchTab, (tab) => {
  if (tab === "lineage") loadLineage()
})

onMounted(loadAll)
</script>

<style scoped>
.etl-reference-page {
  --etl-blue: #1463f3;
  --etl-blue-dark: #08275c;
  --etl-ink: #071d46;
  --etl-muted: #5d6f8d;
  --etl-line: #b9d2ff;
  --etl-panel: #ffffff;
  --etl-soft: #f3f8ff;
  position: relative;
  box-sizing: border-box;
  gap: 14px;
  width: 100%;
  min-height: 0;
  padding: 14px;
  overflow: visible;
  background:
    linear-gradient(180deg, #f7fbff 0%, #eef6ff 52%, #f8fbff 100%);
  border: 1px solid #d7e6ff;
  border-radius: 12px;
}

.etl-reference-hero,
.etl-reference-frame,
.benefit-rail {
  width: min(100%, 1600px);
  margin-inline: auto;
}

.etl-reference-hero {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 18px;
}

.etl-reference-hero h1 {
  margin: 0;
  color: var(--etl-ink);
  font-size: 26px;
  line-height: 1.2;
  font-weight: 800;
  letter-spacing: 0;
}

.etl-reference-hero__proof {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  flex-wrap: wrap;
  gap: 10px;
  color: #4a5b77;
  font-size: 13px;
  font-weight: 600;
}

.etl-reference-hero__proof span {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.etl-reference-hero__proof span + span::before {
  content: "";
  width: 4px;
  height: 4px;
  border-radius: 999px;
  background: #9cb4d6;
}

.etl-reference-frame {
  display: grid;
  grid-template-columns: 170px minmax(0, 1fr) 170px;
  align-items: center;
  gap: 16px;
  height: clamp(620px, calc(100vh - 255px), 720px);
  min-height: 620px;
}

.etl-callout-grid {
  display: grid;
  align-content: space-between;
  gap: 20px;
  height: 100%;
}

.etl-callout {
  position: relative;
  min-height: 118px;
  padding: 14px 12px;
  border: 1px solid var(--etl-line);
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.86);
  box-shadow: 0 12px 30px rgba(13, 66, 155, 0.08);
}

.etl-callout::after {
  position: absolute;
  top: 50%;
  width: 20px;
  border-top: 2px dashed var(--etl-blue);
  content: "";
}

.etl-callout-grid--left .etl-callout::after {
  right: -20px;
}

.etl-callout-grid--right .etl-callout::after {
  left: -20px;
}

.etl-callout__head {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  color: var(--etl-blue);
}

.etl-callout__head b {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex: 0 0 25px;
  width: 25px;
  height: 25px;
  border-radius: 999px;
  background: var(--etl-blue);
  color: #fff;
  font-size: 15px;
  line-height: 1;
}

.etl-callout__head strong {
  font-size: 17px;
  line-height: 1.28;
  font-weight: 800;
}

.etl-callout__body {
  display: grid;
  grid-template-columns: 34px minmax(0, 1fr);
  gap: 10px;
  margin-top: 13px;
  color: var(--etl-muted);
}

.etl-callout__body .el-icon {
  color: var(--etl-blue);
  font-size: 31px;
}

.etl-callout__body p {
  margin: 0;
  font-size: 13px;
  line-height: 1.65;
}

.embedded-bi-shell {
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  height: 100%;
  min-height: 0;
  overflow: hidden;
  border: 1px solid #d7e6ff;
  border-radius: 10px;
  background: #fff;
  box-shadow: 0 22px 54px rgba(7, 36, 91, 0.16);
}

.smartbi-workbench {
  display: grid;
  grid-template-rows: auto auto minmax(0, 1fr) auto;
  min-width: 0;
  min-height: 0;
  background: #f7faff;
}

.smartbi-topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  min-height: 52px;
  padding: 8px 16px;
  border-bottom: 1px solid #e5edf7;
  background: #fff;
}

.smartbi-titlebar,
.smartbi-actions,
.reference-panel-title,
.reference-canvas-tools,
.reference-tool-group,
.reference-switch,
.config-card__title {
  display: flex;
  align-items: center;
  gap: 10px;
}

.smartbi-titlebar strong {
  color: #0b1e43;
  font-size: 18px;
}

.reference-pipeline-select {
  width: 220px;
}

.workbench-tabs {
  display: flex;
  gap: 28px;
  min-height: 40px;
  padding: 0 18px;
  border-bottom: 1px solid #e5edf7;
  background: #fff;
}

.workbench-tabs button {
  position: relative;
  min-height: 40px;
  border: 0;
  background: transparent;
  color: #263b60;
  font: inherit;
  font-size: 13px;
  font-weight: 700;
  cursor: pointer;
}

.workbench-tabs button.is-active {
  color: var(--etl-blue);
}

.workbench-tabs button.is-active::after {
  position: absolute;
  right: 0;
  bottom: 0;
  left: 0;
  height: 3px;
  border-radius: 3px 3px 0 0;
  background: var(--etl-blue);
  content: "";
}

.reference-workbench-body {
  display: grid;
  grid-template-columns: 130px minmax(0, 1fr) 254px;
  height: auto;
  min-height: 0;
  gap: 10px;
  padding: 10px;
  overflow: hidden;
}

.reference-source-panel,
.reference-config-panel,
.reference-data-preview,
.reference-run-monitor {
  min-width: 0;
  border: 1px solid #e3ecf7;
  border-radius: 7px;
  background: #fff;
  box-shadow: 0 8px 22px rgba(13, 55, 120, 0.06);
}

.reference-source-panel {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 11px;
}

.reference-panel-title {
  justify-content: space-between;
  min-height: 28px;
}

.reference-panel-title strong {
  color: #0d234a;
  font-size: 14px;
}

.reference-panel-title span,
.reference-panel-title small {
  color: #6e7f99;
  font-size: 12px;
}

.ref-source-card {
  display: flex;
  align-items: center;
  gap: 8px;
  min-height: 36px;
  padding: 0 10px;
  border: 1px solid #dce8f6;
  border-radius: 5px;
  background: #fff;
  color: #1f3354;
  font: inherit;
  font-size: 13px;
  font-weight: 700;
  cursor: pointer;
}

.ref-source-card .el-icon {
  color: var(--etl-blue);
}

.ref-canvas-drop {
  min-height: 54px;
  margin-top: auto;
  border: 1px dashed #93b8ff;
  border-radius: 6px;
  background: #f8fbff;
  color: #3b6fd6;
  font: inherit;
  font-size: 12px;
  font-weight: 700;
  cursor: pointer;
}

.reference-canvas-panel {
  min-width: 0;
  display: flex;
  flex-direction: column;
}

.reference-canvas-tools {
  justify-content: space-between;
  min-height: 35px;
  margin-bottom: 6px;
}

.reference-tool-group {
  min-height: 32px;
  padding: 0 8px;
  border: 1px solid #dfe8f5;
  border-radius: 6px;
  background: #fff;
}

.reference-tool-group span,
.reference-switch {
  color: #52647e;
  font-size: 12px;
  font-weight: 700;
}

.reference-switch {
  padding: 0 9px;
  border: 1px solid #dfe8f5;
  border-radius: 6px;
  background: #fff;
}

.reference-dag-canvas {
  position: relative;
  display: grid;
  align-content: space-between;
  flex: 1;
  min-height: 0;
  padding: 30px 12px 12px;
  overflow: hidden;
  border: 1px solid #e2ebf8;
  border-radius: 7px;
  background:
    radial-gradient(circle, rgba(41, 106, 231, 0.13) 1px, transparent 1.5px),
    #fbfdff;
  background-size: 14px 14px;
}

.dag-mainline {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 7px;
  justify-self: start;
  width: max-content;
  min-width: 0;
  margin-left: 20px;
  transform: scale(0.86);
  transform-origin: left center;
}

.reference-dag-node,
.reference-output-node {
  display: grid;
  justify-items: center;
  gap: 5px;
  width: 62px;
  min-height: 118px;
  padding: 10px 7px;
  border: 1.5px solid #6fa2ff;
  border-radius: 10px;
  background: #fff;
  color: #183059;
  font: inherit;
  text-align: center;
  cursor: pointer;
  box-shadow: 0 8px 18px rgba(30, 96, 203, 0.08);
}

.reference-dag-node .el-icon,
.reference-output-node .el-icon {
  font-size: 26px;
}

.reference-dag-node strong,
.reference-output-node strong {
  font-size: 13px;
  line-height: 1.2;
}

.reference-dag-node span,
.reference-dag-node small,
.reference-output-node span {
  color: #34496b;
  font-size: 11px;
  line-height: 1.35;
}

.reference-dag-node.is-selected {
  box-shadow: 0 0 0 4px rgba(20, 99, 243, 0.14), 0 8px 18px rgba(30, 96, 203, 0.08);
}

.reference-dag-node--blue .el-icon,
.reference-dag-node--indigo .el-icon {
  color: var(--etl-blue);
}

.reference-dag-node--teal .el-icon,
.reference-dag-node--cyan .el-icon {
  color: #0798aa;
}

.reference-dag-node--purple .el-icon {
  color: #6a4bd9;
}

.reference-dag-node--orange .el-icon {
  color: #f28c18;
}

.dag-arrow {
  width: 14px;
  height: 2px;
  background: #101828;
}

.dag-arrow::after {
  display: block;
  width: 0;
  height: 0;
  margin-top: -4px;
  margin-left: 12px;
  border-top: 5px solid transparent;
  border-bottom: 5px solid transparent;
  border-left: 7px solid #101828;
  content: "";
}

.dag-output-row {
  display: flex;
  justify-content: flex-end;
  padding-right: 4px;
}

.dag-output-connector {
  width: 2px;
  height: 62px;
  margin-top: -58px;
  margin-right: 27px;
  border-left: 2px solid #101828;
}

.reference-output-node {
  width: 156px;
  min-height: 64px;
  grid-template-columns: auto minmax(0, 1fr);
  justify-items: start;
  align-items: center;
  border-style: dashed;
  border-color: #5d94ff;
  color: var(--etl-blue);
  text-align: left;
}

.reference-output-node span {
  grid-column: 2;
  color: #4d5f7b;
}

.reference-node-toolbar {
  display: grid;
  grid-template-columns: repeat(6, minmax(0, 1fr));
  width: min(100%, 420px);
  margin-inline: auto;
  overflow: hidden;
  border: 1px solid #dbe7f5;
  border-radius: 6px;
  background: #fff;
}

.reference-node-toolbar button {
  display: grid;
  justify-items: center;
  gap: 3px;
  min-height: 44px;
  padding: 6px;
  border: 0;
  border-right: 1px solid #e1eaf6;
  background: #fff;
  color: #29405f;
  font: inherit;
  font-size: 11px;
  font-weight: 700;
  cursor: pointer;
}

.reference-node-toolbar button:last-child {
  border-right: 0;
}

.reference-node-toolbar .el-icon {
  color: var(--etl-blue);
  font-size: 18px;
}

.reference-config-panel {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 10px;
  overflow: hidden;
}

.config-card {
  display: grid;
  gap: 7px;
  padding-bottom: 8px;
  border-bottom: 1px solid #e7eef7;
}

.config-card:last-child {
  border-bottom: 0;
}

.config-card__title {
  justify-content: space-between;
  color: #102a54;
  font-size: 13px;
  font-weight: 800;
}

.field-map-table {
  overflow: hidden;
  border: 1px solid #e1eaf5;
  border-radius: 6px;
}

.field-map-head,
.field-map-row {
  display: grid;
  grid-template-columns: 1fr 1fr 1.1fr;
}

.field-map-head span,
.field-map-row span {
  min-width: 0;
  padding: 5px 7px;
  overflow: hidden;
  border-right: 1px solid #e1eaf5;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 11px;
}

.field-map-head span {
  background: #f4f8fd;
  color: #4c5f78;
  font-weight: 800;
}

.field-map-row span {
  color: #1f3354;
}

.field-map-head span:last-child,
.field-map-row span:last-child {
  border-right: 0;
}

.config-rule-line,
.schedule-setting {
  display: grid;
  grid-template-columns: minmax(74px, auto) minmax(0, 1fr) auto;
  align-items: center;
  gap: 6px;
  color: #60728b;
  font-size: 12px;
}

.config-rule-line strong,
.schedule-setting span {
  color: #2c4264;
}

.schedule-setting {
  grid-template-columns: 88px minmax(0, 1fr);
  min-height: 27px;
  padding: 0 8px;
  border: 1px solid #e5edf7;
  border-radius: 5px;
  background: #fbfdff;
}

.reference-bottom-panels {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 214px;
  gap: 10px;
  height: 166px;
  padding: 0 10px 10px;
  overflow: hidden;
}

.reference-data-preview,
.reference-run-monitor {
  padding: 10px;
}

.reference-run-monitor {
  display: grid;
  gap: 8px;
}

.monitor-donut {
  display: grid;
  place-items: center;
  width: 62px;
  height: 62px;
  margin-inline: auto;
  border: 8px solid #17b26a;
  border-left-color: #dff4e9;
  border-radius: 50%;
  color: #102a54;
}

.monitor-donut strong {
  font-size: 17px;
  line-height: 1;
}

.monitor-donut span {
  font-size: 10px;
}

.monitor-metrics {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 5px;
}

.monitor-metrics span {
  display: grid;
  gap: 2px;
  color: #65768e;
  font-size: 10px;
}

.monitor-metrics b {
  color: #12284e;
  font-size: 12px;
}

.monitor-metrics span:last-child b {
  color: #e32626;
}

.benefit-rail {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 8px;
  min-height: 64px;
  padding: 12px 18px;
  border: 1px solid var(--etl-line);
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.86);
  box-shadow: 0 12px 30px rgba(13, 66, 155, 0.08);
}

.benefit-rail__item {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  min-width: 0;
}

.benefit-rail__item .el-icon {
  flex: 0 0 auto;
  color: #5e83cf;
  font-size: 27px;
}

.benefit-rail__item div {
  display: grid;
  gap: 2px;
  min-width: 0;
}

.benefit-rail__item strong {
  color: var(--etl-blue);
  font-size: 14px;
}

.benefit-rail__item span {
  overflow-wrap: anywhere;
  color: #5f718d;
  font-size: 12px;
}

@media (max-width: 1500px) {
  .etl-reference-frame {
    grid-template-columns: 152px minmax(0, 1fr) 152px;
  }

  .etl-callout {
    min-height: 112px;
    padding: 12px 10px;
  }

  .etl-callout__head strong {
    font-size: 15px;
  }

  .etl-callout__body p {
    font-size: 12px;
  }

  .reference-workbench-body {
    grid-template-columns: 116px minmax(0, 1fr) 224px;
  }

  .dag-mainline {
    justify-self: start;
    margin-left: 14px;
    transform: scale(0.74);
    transform-origin: left center;
  }
}

@media (max-width: 1320px) {
  .etl-reference-frame {
    grid-template-columns: 1fr;
    height: auto;
    min-height: 0;
  }

  .etl-callout-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
    order: 2;
  }

  .etl-callout::after {
    display: none;
  }

  .embedded-bi-shell {
    order: 1;
    min-height: 620px;
  }
}

@media (max-width: 980px) {
  .etl-reference-hero,
  .smartbi-topbar,
  .smartbi-titlebar,
  .smartbi-actions {
    align-items: stretch;
    flex-direction: column;
  }

  .etl-reference-hero h1 {
    font-size: 24px;
  }

  .embedded-bi-shell,
  .reference-workbench-body,
  .reference-bottom-panels {
    grid-template-columns: 1fr;
  }

  .dag-mainline {
    flex-wrap: wrap;
    transform: none;
  }

  .dag-arrow {
    display: none;
  }

  .reference-dag-node {
    width: 112px;
  }

  .benefit-rail {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 640px) {
  .etl-reference-page {
    padding: 8px 0;
  }

  .etl-callout-grid,
  .benefit-rail,
  .reference-node-toolbar,
  .monitor-metrics {
    grid-template-columns: 1fr;
  }

  .embedded-bi-shell,
  .benefit-rail,
  .etl-callout {
    border-radius: 8px;
  }

  .reference-pipeline-select,
  .smartbi-actions .el-button {
    width: 100%;
  }
}

.data-pipelines-page {
  gap: 12px;
}

.legacy-commandbar,
.pipeline-kpis,
.etl-palette,
.etl-stage,
.node-config-panel,
.pipeline-canvas-panel,
.etl-tab-surface,
.etl-bottom-panel {
  background: var(--app-surface);
  border: 1px solid var(--app-border);
  border-radius: var(--app-radius);
}

.legacy-commandbar {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 16px;
  padding: 16px;
}

.legacy-commandbar__title h2,
.pipeline-toolbar h3 {
  margin: 2px 0 6px;
  letter-spacing: 0;
}

.legacy-commandbar__title span,
.pipeline-toolbar span,
.section-heading small,
.pipeline-item span,
.kpi-cell span,
.ops-grid span,
.ops-grid small,
.validation-score span,
.node-log-item span,
.lineage-summary span,
.run-health span,
.config-title + label span,
.node-config-form label span {
  color: var(--app-text-muted);
}

.eyebrow {
  margin: 0;
  color: var(--app-primary);
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0;
}

.legacy-commandbar__actions,
.pipeline-toolbar,
.section-heading,
.validation-score,
.diagnostic-item,
.panel-title,
.config-title,
.node-log-item {
  display: flex;
  align-items: center;
  gap: 10px;
}

.legacy-commandbar__actions {
  justify-content: flex-end;
  flex-wrap: wrap;
}

.pipeline-action-toolbar {
  display: grid;
  grid-template-columns: minmax(220px, 270px) max-content max-content max-content;
  align-items: center;
  justify-content: end;
  gap: 8px;
}

.toolbar-group {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  min-height: 38px;
  padding: 3px;
  border: 1px solid var(--app-border-light);
  border-radius: var(--app-radius-sm);
  background: var(--app-surface-muted);
}

.toolbar-group--primary {
  background: #fff;
}

.toolbar-group :deep(.el-button + .el-button),
.flow-controls :deep(.el-button + .el-button) {
  margin-left: 0;
}

.toolbar-button,
.flow-control-button {
  min-height: 32px;
  border-radius: 6px;
  font-weight: 700;
}

.toolbar-button--new {
  white-space: nowrap;
}

.pipeline-toolbar__actions {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
  justify-content: flex-end;
}

.pipeline-search {
  width: 220px;
}

.pipeline-kpis {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
}

.kpi-cell {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 14px 16px;
  border-right: 1px solid var(--app-border-light);
}

.kpi-cell:last-child {
  border-right: none;
}

.kpi-cell strong {
  font-size: 22px;
  line-height: 1.1;
}

.etl-mode-tabs {
  width: 100%;
}

.etl-shell {
  display: grid;
  grid-template-columns: 320px minmax(0, 1fr);
  align-items: start;
  gap: 12px;
}

.etl-palette,
.etl-stage,
.node-config-panel {
  min-width: 0;
  padding: 12px;
}

.etl-palette {
  display: flex;
  position: sticky;
  top: 12px;
  max-height: calc(100vh - 24px);
  min-height: 660px;
  flex-direction: column;
  gap: 12px;
  overflow: auto;
}

.operator-console-note {
  display: flex;
  align-items: baseline;
  gap: 6px;
  min-height: 42px;
  padding: 10px 12px;
  border: 1px solid var(--app-border-light);
  border-radius: var(--app-radius-sm);
  background: linear-gradient(135deg, rgba(15, 118, 110, 0.08), rgba(37, 99, 235, 0.08));
}

.operator-console-note strong {
  color: var(--app-primary);
  font-size: 22px;
  line-height: 1;
}

.operator-console-note span {
  color: var(--app-text-muted);
  font-size: 13px;
  font-weight: 600;
}

.panel-title,
.section-heading,
.config-title,
.pipeline-toolbar {
  justify-content: space-between;
}

.panel-title {
  font-weight: 700;
}

.panel-title small {
  color: var(--app-text-muted);
  font-weight: 500;
}

.status-filter {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 6px;
}

.status-filter button,
.source-chip,
.node-palette button,
.pipeline-item {
  appearance: none;
  border: 1px solid var(--app-border);
  border-radius: var(--app-radius-sm);
  background: var(--app-surface);
  color: var(--app-text);
  cursor: pointer;
  font: inherit;
  line-height: 1.2;
  transition: border-color var(--app-transition), background var(--app-transition), box-shadow var(--app-transition);
}

.status-filter button {
  display: flex;
  align-items: center;
  justify-content: space-between;
  min-height: 34px;
  padding: 7px 9px;
  font-weight: 700;
}

.status-filter button:focus-visible,
.source-chip:focus-visible,
.node-palette button:focus-visible,
.pipeline-item:focus-visible {
  outline: none;
  border-color: var(--app-primary);
  box-shadow: 0 0 0 3px rgba(15, 118, 110, 0.14);
}

.status-filter button.active,
.pipeline-item.active,
.node-palette button:hover,
.source-chip:hover {
  border-color: var(--app-primary);
  background: rgba(15, 118, 110, 0.06);
}

.pipeline-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.pipeline-item {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 8px;
  width: 100%;
  padding: 12px;
  text-align: left;
}

.pipeline-item.active {
  box-shadow: inset 3px 0 0 var(--app-primary);
}

.pipeline-item__main {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: 4px;
}

.pipeline-item__main strong,
.pipeline-item__main span {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.pipeline-item__meta {
  display: flex;
  grid-column: 1 / -1;
  flex-wrap: wrap;
  gap: 6px;
}

.pipeline-item__meta span {
  padding: 2px 6px;
  border-radius: 999px;
  background: var(--app-surface-muted);
  color: var(--app-text-muted);
  font-size: 12px;
}

.palette-section {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.operator-group {
  display: grid;
  gap: 6px;
}

.operator-group__title {
  color: var(--app-text-muted);
  font-size: 12px;
  font-weight: 700;
}

.source-chip,
.node-palette button {
  display: inline-flex;
  align-items: center;
  justify-content: flex-start;
  gap: 8px;
  width: 100%;
  min-height: 40px;
  padding: 8px 10px;
  text-align: left;
}

.source-chip .el-icon,
.node-palette button .el-icon {
  flex: 0 0 auto;
}

.node-palette button span {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.node-palette {
  display: grid;
  grid-template-columns: 1fr;
  gap: 8px;
}

.etl-stage {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: 12px;
}

.pipeline-canvas-panel,
.etl-tab-surface,
.etl-bottom-panel {
  padding: 12px;
}

.section-heading {
  min-height: 36px;
  margin-bottom: 10px;
}

.section-heading--canvas {
  align-items: flex-start;
  gap: 12px;
}

.section-heading > div:first-child {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: 2px;
}

.section-heading__actions,
.canvas-commandbar {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  flex-wrap: wrap;
  gap: 8px;
}

.canvas-commandbar {
  flex: 1;
  min-width: min(100%, 560px);
}

.canvas-commandbar .toolbar-group {
  flex-wrap: nowrap;
}

.node-search-input {
  width: clamp(180px, 22vw, 260px);
}

.section-heading span,
.config-title strong {
  font-weight: 700;
}

.flow-wrap {
  position: relative;
  height: clamp(560px, calc(100vh - 420px), 760px);
  min-height: 520px;
  overflow: hidden;
  border: 1px solid var(--app-border-light);
  border-radius: var(--app-radius-sm);
  background:
    linear-gradient(rgba(15, 118, 110, 0.04) 1px, transparent 1px),
    linear-gradient(90deg, rgba(15, 118, 110, 0.04) 1px, transparent 1px),
    #f8fafc;
  background-size: 24px 24px;
}

.pipeline-flow {
  height: 100%;
}

.flow-background-grid {
  position: absolute;
  inset: 0;
  pointer-events: none;
  background-image:
    linear-gradient(rgba(15, 118, 110, 0.05) 1px, transparent 1px),
    linear-gradient(90deg, rgba(15, 118, 110, 0.05) 1px, transparent 1px);
  background-size: 24px 24px;
}

.flow-minimap {
  position: absolute;
  right: 14px;
  bottom: 14px;
  z-index: 4;
  width: 142px;
  height: 92px;
  border: 1px solid var(--app-border);
  border-radius: var(--app-radius-sm);
  background: rgba(255, 255, 255, 0.94);
  box-shadow: var(--app-shadow-soft);
}

.flow-minimap span {
  position: absolute;
  top: 6px;
  left: 8px;
  color: var(--app-text-muted);
  font-size: 11px;
  font-weight: 700;
}

.flow-minimap i {
  position: absolute;
  width: 18px;
  height: 10px;
  border-radius: 3px;
  background: rgba(15, 118, 110, 0.24);
}

.flow-minimap i.is-active {
  background: var(--app-primary);
}

.flow-controls {
  position: absolute;
  left: 14px;
  bottom: 14px;
  z-index: 4;
  display: inline-flex;
  gap: 6px;
  padding: 6px;
  overflow: visible;
  border: 1px solid var(--app-border);
  border-radius: var(--app-radius-sm);
  background: rgba(255, 255, 255, 0.96);
  box-shadow: var(--app-shadow-soft);
}

.pipeline-flow :deep(.vue-flow__node) {
  min-width: 112px;
  padding: 0;
  border: 0;
  background: transparent;
  color: var(--app-text);
  box-shadow: none;
}

.pipeline-flow :deep(.vue-flow__node-etl-icon) {
  width: 120px;
}

.pipeline-flow :deep(.vue-flow__handle) {
  width: 9px;
  height: 9px;
  border: 2px solid #fff;
  background: var(--app-primary);
  opacity: 0.88;
}

.pipeline-flow :deep(.vue-flow__handle-top) {
  top: -4px;
}

.pipeline-flow :deep(.vue-flow__handle-bottom) {
  bottom: -4px;
}

.etl-canvas-node {
  display: grid;
  justify-items: center;
  gap: 5px;
  width: 120px;
  min-height: 88px;
  color: var(--app-text);
  text-align: center;
  user-select: none;
}

.etl-canvas-node__icon {
  --node-accent: var(--app-primary);
  --node-accent-soft: rgba(15, 118, 110, 0.14);
  --node-accent-mid: rgba(15, 118, 110, 0.36);
  position: relative;
  display: grid;
  place-items: center;
  width: 50px;
  height: 50px;
  overflow: hidden;
  border: 1px solid rgba(148, 163, 184, 0.38);
  border-radius: 999px;
  background:
    radial-gradient(circle at 30% 24%, rgba(255, 255, 255, 0.96) 0 20%, transparent 36%),
    linear-gradient(145deg, #ffffff 0%, #f7fbff 56%, var(--node-accent-soft) 100%);
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.82),
    0 10px 22px rgba(15, 23, 42, 0.14);
  transition: border-color var(--app-transition), box-shadow var(--app-transition), transform var(--app-transition), background var(--app-transition);
}

.etl-canvas-node__icon::after {
  position: absolute;
  inset: 8px;
  border: 1px solid var(--node-accent-soft);
  border-radius: inherit;
  content: "";
}

.etl-canvas-node__icon--blue {
  --node-accent: #2563eb;
  --node-accent-soft: rgba(37, 99, 235, 0.15);
  --node-accent-mid: rgba(37, 99, 235, 0.42);
}

.etl-canvas-node__icon--indigo {
  --node-accent: #4f46e5;
  --node-accent-soft: rgba(79, 70, 229, 0.15);
  --node-accent-mid: rgba(79, 70, 229, 0.42);
}

.etl-canvas-node__icon--teal {
  --node-accent: #0f766e;
  --node-accent-soft: rgba(15, 118, 110, 0.15);
  --node-accent-mid: rgba(15, 118, 110, 0.42);
}

.etl-canvas-node__icon--violet {
  --node-accent: #7c3aed;
  --node-accent-soft: rgba(124, 58, 237, 0.15);
  --node-accent-mid: rgba(124, 58, 237, 0.42);
}

.etl-canvas-node__icon--cyan {
  --node-accent: #0891b2;
  --node-accent-soft: rgba(8, 145, 178, 0.15);
  --node-accent-mid: rgba(8, 145, 178, 0.42);
}

.etl-canvas-node__icon--slate {
  --node-accent: #334155;
  --node-accent-soft: rgba(51, 65, 85, 0.16);
  --node-accent-mid: rgba(51, 65, 85, 0.44);
}

.etl-canvas-node__icon--amber {
  --node-accent: #d97706;
  --node-accent-soft: rgba(217, 119, 6, 0.16);
  --node-accent-mid: rgba(217, 119, 6, 0.44);
}

.etl-canvas-node__icon--emerald {
  --node-accent: #059669;
  --node-accent-soft: rgba(5, 150, 105, 0.15);
  --node-accent-mid: rgba(5, 150, 105, 0.42);
}

.etl-canvas-node__icon--rose {
  --node-accent: #e11d48;
  --node-accent-soft: rgba(225, 29, 72, 0.15);
  --node-accent-mid: rgba(225, 29, 72, 0.42);
}

.etl-canvas-node__status {
  position: absolute;
  right: 2px;
  bottom: 3px;
  z-index: 3;
  width: 10px;
  height: 10px;
  border: 2px solid #fff;
  border-radius: 999px;
  background: var(--app-success);
}

.etl-canvas-node__glyph,
.etl-canvas-node__glyph::before,
.etl-canvas-node__glyph::after,
.etl-canvas-node__glyph span {
  position: absolute;
  box-sizing: border-box;
}

.etl-canvas-node__glyph {
  z-index: 2;
  width: 28px;
  height: 28px;
  color: var(--node-accent);
}

.etl-canvas-node__glyph::before,
.etl-canvas-node__glyph::after,
.etl-canvas-node__glyph span {
  content: "";
}

.etl-canvas-node__glyph b {
  position: absolute;
  inset: 7px 3px auto;
  color: var(--node-accent);
  font-size: 8px;
  font-weight: 900;
  letter-spacing: 0;
  line-height: 1;
}

.etl-canvas-node__glyph--source::before {
  top: 3px;
  left: 4px;
  width: 20px;
  height: 8px;
  border: 2px solid var(--node-accent);
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.72);
}

.etl-canvas-node__glyph--source span:first-child {
  top: 7px;
  left: 4px;
  width: 20px;
  height: 15px;
  border-right: 2px solid var(--node-accent);
  border-bottom: 2px solid var(--node-accent);
  border-left: 2px solid var(--node-accent);
  border-radius: 0 0 10px 10px;
  background: linear-gradient(180deg, var(--node-accent-soft), rgba(255, 255, 255, 0.36));
}

.etl-canvas-node__glyph--source::after {
  top: 14px;
  left: 8px;
  width: 12px;
  height: 2px;
  border-radius: 2px;
  background: var(--node-accent-mid);
  box-shadow: 0 4px 0 var(--node-accent-mid);
}

.etl-canvas-node__glyph--extract::before {
  top: 4px;
  left: 12px;
  width: 4px;
  height: 13px;
  border-radius: 999px;
  background: var(--node-accent);
}

.etl-canvas-node__glyph--extract::after {
  top: 13px;
  left: 7px;
  width: 14px;
  height: 14px;
  border-right: 4px solid var(--node-accent);
  border-bottom: 4px solid var(--node-accent);
  transform: rotate(45deg);
}

.etl-canvas-node__glyph--extract span:first-child {
  right: 3px;
  bottom: 2px;
  left: 3px;
  height: 5px;
  border: 2px solid var(--node-accent-mid);
  border-top: 0;
  border-radius: 0 0 7px 7px;
}

.etl-canvas-node__glyph--metadata::before {
  inset: 3px 6px 3px 5px;
  border: 2px solid var(--node-accent);
  border-radius: 5px;
  background: rgba(255, 255, 255, 0.58);
}

.etl-canvas-node__glyph--metadata::after {
  top: 7px;
  right: 7px;
  width: 7px;
  height: 7px;
  border-top: 2px solid var(--node-accent-mid);
  border-right: 2px solid var(--node-accent-mid);
}

.etl-canvas-node__glyph--metadata span:first-child {
  top: 12px;
  left: 9px;
  width: 3px;
  height: 3px;
  border-radius: 999px;
  background: var(--node-accent);
  box-shadow: 6px 0 0 var(--node-accent), 0 6px 0 var(--node-accent-mid), 6px 6px 0 var(--node-accent-mid);
}

.etl-canvas-node__glyph--transform::before,
.etl-canvas-node__glyph--transform::after {
  left: 4px;
  width: 20px;
  height: 4px;
  border-radius: 999px;
  background: var(--node-accent-mid);
}

.etl-canvas-node__glyph--transform::before {
  top: 8px;
}

.etl-canvas-node__glyph--transform::after {
  bottom: 8px;
}

.etl-canvas-node__glyph--transform span:first-child,
.etl-canvas-node__glyph--transform span:last-child {
  width: 9px;
  height: 9px;
  border: 2px solid #fff;
  border-radius: 999px;
  background: var(--node-accent);
  box-shadow: 0 2px 5px var(--node-accent-soft);
}

.etl-canvas-node__glyph--transform span:first-child {
  top: 5px;
  left: 7px;
}

.etl-canvas-node__glyph--transform span:last-child {
  right: 6px;
  bottom: 5px;
}

.etl-canvas-node__glyph--join::before,
.etl-canvas-node__glyph--join::after,
.etl-canvas-node__glyph--join span:first-child {
  width: 9px;
  height: 9px;
  border: 2px solid var(--node-accent);
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.7);
}

.etl-canvas-node__glyph--join::before {
  top: 5px;
  left: 4px;
}

.etl-canvas-node__glyph--join::after {
  bottom: 5px;
  left: 4px;
}

.etl-canvas-node__glyph--join span:first-child {
  top: 10px;
  right: 4px;
  background: var(--node-accent);
}

.etl-canvas-node__glyph--join span:last-child {
  top: 10px;
  left: 12px;
  width: 10px;
  height: 8px;
  border-top: 2px solid var(--node-accent-mid);
  border-bottom: 2px solid var(--node-accent-mid);
  transform: skewX(-22deg);
}

.etl-canvas-node__glyph--union::before,
.etl-canvas-node__glyph--union::after {
  top: 5px;
  width: 11px;
  height: 17px;
  border-top: 2px solid var(--node-accent);
  border-bottom: 2px solid var(--node-accent);
}

.etl-canvas-node__glyph--union::before {
  left: 5px;
  border-left: 2px solid var(--node-accent);
  border-radius: 8px 0 0 8px;
}

.etl-canvas-node__glyph--union::after {
  right: 5px;
  border-right: 2px solid var(--node-accent);
  border-radius: 0 8px 8px 0;
}

.etl-canvas-node__glyph--union span:first-child {
  top: 13px;
  left: 6px;
  width: 16px;
  height: 2px;
  border-radius: 2px;
  background: var(--node-accent);
}

.etl-canvas-node__glyph--sql::before,
.etl-canvas-node__glyph--sql::after {
  top: 5px;
  width: 6px;
  height: 18px;
  border: 2px solid var(--node-accent);
}

.etl-canvas-node__glyph--sql::before {
  left: 3px;
  border-right: 0;
  border-radius: 6px 0 0 6px;
}

.etl-canvas-node__glyph--sql::after {
  right: 3px;
  border-left: 0;
  border-radius: 0 6px 6px 0;
}

.etl-canvas-node__glyph--quality::before {
  top: 3px;
  left: 6px;
  width: 16px;
  height: 20px;
  border: 2px solid var(--node-accent);
  border-radius: 9px 9px 12px 12px;
  background: var(--node-accent-soft);
}

.etl-canvas-node__glyph--quality::after {
  top: 10px;
  left: 11px;
  width: 11px;
  height: 7px;
  border-bottom: 3px solid var(--node-accent);
  border-left: 3px solid var(--node-accent);
  transform: rotate(-45deg);
}

.etl-canvas-node__glyph--load::before {
  right: 4px;
  bottom: 3px;
  left: 4px;
  height: 12px;
  border: 2px solid var(--node-accent);
  border-radius: 4px 4px 8px 8px;
  background: var(--node-accent-soft);
}

.etl-canvas-node__glyph--load::after {
  top: 4px;
  left: 11px;
  width: 6px;
  height: 13px;
  border-radius: 999px;
  background: var(--node-accent);
}

.etl-canvas-node__glyph--load span:first-child {
  top: 4px;
  left: 7px;
  width: 14px;
  height: 14px;
  border-top: 4px solid var(--node-accent);
  border-left: 4px solid var(--node-accent);
  transform: rotate(45deg);
}

.etl-canvas-node__glyph--reverse::before {
  inset: 4px;
  border: 3px solid var(--node-accent-mid);
  border-right-color: var(--node-accent);
  border-bottom-color: var(--node-accent);
  border-radius: 999px;
  transform: rotate(-24deg);
}

.etl-canvas-node__glyph--reverse::after {
  top: 5px;
  right: 3px;
  width: 0;
  height: 0;
  border-top: 5px solid transparent;
  border-bottom: 5px solid transparent;
  border-left: 7px solid var(--node-accent);
  transform: rotate(24deg);
}

.etl-canvas-node__glyph--reverse span:first-child {
  bottom: 5px;
  left: 3px;
  width: 0;
  height: 0;
  border-top: 5px solid transparent;
  border-right: 7px solid var(--node-accent-mid);
  border-bottom: 5px solid transparent;
  transform: rotate(24deg);
}

.etl-canvas-node__glyph--task::before {
  inset: 5px;
  border: 2px solid var(--node-accent);
  border-radius: 6px;
  background:
    linear-gradient(var(--node-accent-soft) 0 0) 50% 50% / 2px 100% no-repeat,
    linear-gradient(90deg, var(--node-accent-soft) 0 0) 50% 50% / 100% 2px no-repeat;
}

.etl-canvas-node__title {
  display: -webkit-box;
  width: 116px;
  overflow: hidden;
  color: var(--app-text);
  font-size: 13px;
  font-weight: 700;
  line-height: 1.25;
  text-overflow: ellipsis;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
}

.etl-canvas-node small {
  width: 116px;
  overflow: hidden;
  color: var(--app-text-muted);
  font-size: 11px;
  font-weight: 600;
  line-height: 1.2;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.etl-canvas-node.is-selected .etl-canvas-node__icon,
.pipeline-flow :deep(.vue-flow__node.selected .etl-canvas-node__icon),
.pipeline-flow :deep(.vue-flow__node.is-selected .etl-canvas-node__icon) {
  border-color: var(--app-primary);
  box-shadow: 0 0 0 5px rgba(15, 118, 110, 0.14), 0 10px 22px rgba(15, 23, 42, 0.14);
  transform: translateY(-1px);
}

.etl-canvas-node.is-blocked .etl-canvas-node__icon,
.etl-canvas-node.is-failed .etl-canvas-node__icon {
  --node-accent: var(--app-danger);
  --node-accent-soft: rgba(220, 38, 38, 0.15);
  --node-accent-mid: rgba(220, 38, 38, 0.44);
  border-color: var(--app-danger);
}

.etl-canvas-node.is-blocked .etl-canvas-node__status,
.etl-canvas-node.is-failed .etl-canvas-node__status {
  background: var(--app-danger);
}

.etl-canvas-node.is-warning .etl-canvas-node__icon {
  --node-accent: var(--app-warning);
  --node-accent-soft: rgba(217, 119, 6, 0.16);
  --node-accent-mid: rgba(217, 119, 6, 0.44);
  border-color: var(--app-warning);
}

.etl-canvas-node.is-warning .etl-canvas-node__status {
  background: var(--app-warning);
}

.pipeline-flow :deep(.vue-flow__edge-path) {
  stroke: var(--app-primary);
  stroke-width: 2;
}

.tab-surface-grid,
.schedule-grid,
.monitor-grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  gap: 12px;
  min-height: 392px;
}

.ops-grid,
.lineage-summary {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 8px;
}

.ops-grid > div,
.lineage-summary > div {
  display: flex;
  min-height: 82px;
  flex-direction: column;
  gap: 4px;
  justify-content: center;
  padding: 10px;
  border: 1px solid var(--app-border-light);
  border-radius: var(--app-radius-sm);
  background: var(--app-surface-muted);
}

.ops-grid strong,
.lineage-summary strong {
  font-size: 16px;
}

.console-form,
.node-config-form,
.config-group {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.console-form label,
.node-config-form label {
  display: flex;
  flex-direction: column;
  gap: 6px;
  color: var(--app-text);
  font-size: 13px;
  font-weight: 600;
}

.console-form :deep(.el-date-editor) {
  width: 100%;
}

.run-mode-tabs {
  width: 100%;
}

.run-health {
  display: grid;
  grid-template-columns: 180px minmax(0, 1fr);
  gap: 12px;
  padding: 12px;
  border: 1px solid var(--app-border-light);
  border-radius: var(--app-radius-sm);
  background: var(--app-surface-muted);
}

.run-health__score {
  display: flex;
  flex-direction: column;
  justify-content: center;
}

.run-health__score strong {
  color: var(--app-success);
  font-size: 34px;
  line-height: 1;
}

.run-health__stats {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 8px;
}

.run-health__stats span {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 10px;
  border-radius: var(--app-radius-sm);
  background: #fff;
}

.validation-panel {
  display: grid;
  grid-template-columns: 280px minmax(0, 1fr);
  gap: 12px;
}

.inspect-panel {
  min-height: 220px;
}

.validation-score {
  align-items: flex-start;
  padding: 12px;
  border: 1px solid var(--app-border-light);
  border-radius: var(--app-radius-sm);
  background: var(--app-surface-muted);
}

.validation-score > div {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.validation-icon {
  font-size: 24px;
}

.validation-icon--ready {
  color: var(--app-success);
}

.validation-icon--blocked {
  color: var(--app-danger);
}

.validation-icon--warning,
.validation-icon--empty {
  color: var(--app-warning);
}

.diagnostic-list,
.node-log-list {
  display: flex;
  min-height: 72px;
  flex-direction: column;
  gap: 8px;
}

.diagnostic-item,
.node-log-item,
.rule-chip {
  justify-content: flex-start;
  min-height: 34px;
  padding: 8px 10px;
  border: 1px solid var(--app-border-light);
  border-radius: var(--app-radius-sm);
}

.node-log-item small {
  margin-left: auto;
  color: var(--app-text-muted);
}

.table-toolbar {
  display: flex;
  justify-content: space-between;
  margin-bottom: 10px;
}

.table-toolbar > div {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.node-config-panel {
  max-height: calc(100vh - 232px);
  overflow: auto;
}

.node-config-panel--drawer {
  max-height: none;
  padding: 0;
  border: 0;
  border-radius: 0;
}

.node-state-panel {
  display: grid;
  gap: 6px;
  padding: 10px;
  border: 1px solid var(--app-border-light);
  border-radius: var(--app-radius-sm);
  background: var(--app-surface-muted);
}

.node-state-panel > div {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.node-state-panel span,
.node-state-panel small {
  color: var(--app-text-muted);
}

.node-config-heading__actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

:deep(.node-config-drawer) {
  --el-drawer-padding-primary: 18px;
}

:deep(.node-config-drawer .el-drawer__body) {
  padding: 18px;
}

.mapping-row,
.filter-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1fr) auto;
  gap: 8px;
}

.filter-row {
  grid-template-columns: minmax(0, 1fr) 112px minmax(0, 1fr) auto;
}

.rule-chip {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.pipeline-form :deep(.el-form-item) {
  margin-bottom: 14px;
}

@media (max-width: 1280px) {
  .etl-shell {
    grid-template-columns: 280px minmax(0, 1fr);
  }

  .pipeline-action-toolbar {
    grid-template-columns: minmax(220px, 1fr) max-content;
  }
}

@media (max-width: 920px) {
  .etl-shell,
  .validation-panel,
  .run-health {
    grid-template-columns: 1fr;
  }

  .etl-palette {
    position: static;
    max-height: none;
    min-height: auto;
  }

  .flow-wrap {
    height: 520px;
    min-height: 460px;
  }

  .ops-grid,
  .lineage-summary,
  .pipeline-kpis,
  .run-health__stats {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 760px) {
  .legacy-commandbar,
  .legacy-commandbar__actions,
  .pipeline-toolbar,
  .section-heading--canvas,
  .mapping-row,
  .filter-row {
    align-items: stretch;
    grid-template-columns: 1fr;
    flex-direction: column;
  }

  .pipeline-action-toolbar {
    justify-content: stretch;
  }

  .pipeline-action-toolbar .toolbar-group,
  .pipeline-action-toolbar .toolbar-button--new {
    width: 100%;
  }

  .pipeline-action-toolbar .toolbar-group--primary .el-button {
    flex: 1;
  }

  .pipeline-action-toolbar .toolbar-group:not(.toolbar-group--primary) .el-button.is-circle {
    width: 32px;
  }

  .pipeline-search,
  .legacy-commandbar__actions .el-button {
    width: 100%;
  }

  .canvas-commandbar {
    align-items: stretch;
    min-width: 0;
  }

  .canvas-commandbar .toolbar-group {
    flex-wrap: wrap;
    justify-content: flex-start;
  }

  .node-search-input {
    width: 100%;
  }

  .kpi-cell {
    border-right: none;
    border-bottom: 1px solid var(--app-border-light);
  }

  .kpi-cell:last-child {
    border-bottom: none;
  }
}
</style>
