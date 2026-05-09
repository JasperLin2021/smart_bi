<template>
  <div class="dashboard-center-page">
    <div class="toolbar">
      <el-segmented v-model="statusFilter" :options="statusOptions" @change="fetchDashboards" />
      <div class="toolbar-actions">
        <el-button @click="openTemplateDialog">模板创建</el-button>
        <el-button type="primary" :icon="Plus" @click="openCreate">新建看板</el-button>
      </div>
    </div>

    <el-table
      v-loading="loading"
      :data="dashboards"
      class="dashboard-table"
      @row-click="preview"
    >
      <el-table-column prop="title" label="看板名称" min-width="180" />
      <el-table-column prop="description" label="描述" min-width="220" show-overflow-tooltip />
      <el-table-column label="状态" width="100">
        <template #default="{ row }">
          <el-tag :type="row.status === 'published' ? 'success' : 'info'" effect="plain">
            {{ row.status === 'published' ? '已发布' : '草稿' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="可见范围" width="120">
        <template #default="{ row }">{{ row.visibility === 'org' ? '组织内' : '仅自己' }}</template>
      </el-table-column>
      <el-table-column label="组件数" width="100">
        <template #default="{ row }">{{ componentCount(row) }}</template>
      </el-table-column>
      <el-table-column label="操作" width="270" fixed="right">
        <template #default="{ row }">
          <el-button text type="primary" @click.stop="openDesigner(row)">编辑</el-button>
          <el-button text @click.stop="preview(row)">预览</el-button>
          <el-button text @click.stop="openShare(row)">分享</el-button>
          <el-dropdown trigger="click" @click.stop>
            <el-button text @click.stop>更多</el-button>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item @click="edit(row)">重命名/描述</el-dropdown-item>
                <el-dropdown-item v-if="row.status !== 'published'" @click="publish(row)">发布</el-dropdown-item>
                <el-dropdown-item divided @click="remove(row)">
                  <span style="color:var(--el-color-danger)">删除</span>
                </el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </template>
      </el-table-column>
    </el-table>

    <el-dialog v-model="editorVisible" :title="editingId ? '编辑看板' : '新建看板'" width="560px">
      <el-form :model="form" label-width="88px">
        <el-form-item label="名称">
          <el-input v-model="form.title" maxlength="128" show-word-limit />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="form.description" type="textarea" :rows="3" />
        </el-form-item>
        <el-form-item label="可见范围">
          <el-radio-group v-model="form.visibility">
            <el-radio value="private">仅自己</el-radio>
            <el-radio value="org">组织内</el-radio>
          </el-radio-group>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editorVisible = false">取消</el-button>
        <el-button type="primary" @click="save" :loading="saving">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="templateVisible" title="从模板创建看板" width="720px">
      <el-table v-loading="templateLoading" :data="templates">
        <el-table-column prop="name" label="模板名称" width="180" />
        <el-table-column prop="description" label="适用场景" />
        <el-table-column label="操作" width="100">
          <template #default="{ row }">
            <el-button text type="primary" @click="createFromTemplate(row)">使用</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-dialog>

    <el-dialog v-model="shareVisible" title="看板分享与嵌入" width="620px">
      <el-tabs v-model="shareDialogTab" class="modal-tabs">
        <el-tab-pane label="分享设置" name="share">
          <div class="modal-tab-content">
            <el-form label-width="96px">
              <el-form-item label="公开链接">
                <el-switch v-model="sharePublic" />
              </el-form-item>
              <el-form-item label="协作用户">
                <el-input v-model="shareUserIdsText" placeholder="用户 ID，用逗号分隔" />
              </el-form-item>
              <el-form-item v-if="shareTarget?.share_token" label="访问地址">
                <el-input :model-value="shareLink" readonly />
              </el-form-item>
            </el-form>
            <div style="display:flex;justify-content:flex-end;gap:8px;margin-top:12px">
              <el-button @click="shareVisible = false">取消</el-button>
              <el-button type="primary" :loading="shareSaving" @click="saveShare">保存分享</el-button>
            </div>
          </div>
        </el-tab-pane>

        <el-tab-pane label="嵌入 SDK" name="embed">
          <div class="modal-tab-content">
            <div class="embed-create-form">
              <el-input v-model="embedTokenForm.label" placeholder="Token 名称（可选）" style="width:200px" />
              <el-input-number v-model="embedTokenForm.expires_days" :min="1" :max="3650" placeholder="有效天数" :controls="false" style="width:120px" />
              <el-button type="primary" :loading="embedTokenCreating" @click="createEmbedToken">生成 Token</el-button>
            </div>
            <el-table v-loading="embedTokenLoading" :data="embedTokens" size="small" style="margin-top:12px">
              <el-table-column prop="label" label="名称" min-width="120" />
              <el-table-column label="过期时间" width="130">
                <template #default="{ row }">{{ row.expires_at ? row.expires_at.slice(0,10) : '永不' }}</template>
              </el-table-column>
              <el-table-column label="操作" width="140">
                <template #default="{ row }">
                  <el-button text type="primary" size="small" @click="copyEmbedCode(row)">复制代码</el-button>
                  <el-button text type="danger" size="small" @click="deleteEmbedToken(row.id)">删除</el-button>
                </template>
              </el-table-column>
            </el-table>
            <div class="embed-hint">
              <p>在任意网页中嵌入此看板，引入 <code>/embed.js</code> 后调用 <code>SmartBI.embed()</code>。</p>
            </div>
          </div>
        </el-tab-pane>
      </el-tabs>
    </el-dialog>

    <el-drawer v-model="previewVisible" title="看板预览" size="82%" @close="onPreviewClose" @opened="() => window.dispatchEvent(new Event('resize'))" class="preview-drawer">
      <template v-if="selectedDashboard">
        <div class="preview-header">
          <div>
            <h3 class="preview-title">{{ selectedDashboard.title }}</h3>
            <p class="preview-description">{{ selectedDashboard.description || "暂无描述" }}</p>
          </div>
          <div class="preview-header-right">
            <el-tag effect="plain">{{ componentCount(selectedDashboard) }} 个组件</el-tag>
            <el-button v-if="previewFilters.length > 0" size="small" type="warning" plain @click="previewFilters = []">
              清除过滤 ({{ previewFilters.length }})
            </el-button>
            <el-dropdown trigger="click" @command="handleExport">
              <el-button size="small" :loading="exporting">
                导出 <el-icon class="el-icon--right"><ArrowDown /></el-icon>
              </el-button>
              <template #dropdown>
                <el-dropdown-menu>
                  <el-dropdown-item command="png">导出为 PNG</el-dropdown-item>
                  <el-dropdown-item command="pdf">导出为 PDF</el-dropdown-item>
                </el-dropdown-menu>
              </template>
            </el-dropdown>
            <el-button size="small" :type="showComments ? 'primary' : ''" @click="showComments = !showComments">
              评论 {{ comments.length > 0 ? `(${comments.length})` : '' }}
            </el-button>
          </div>
        </div>

        <div class="preview-body">
          <!-- 图表区域 -->
          <div class="preview-charts-area">
            <div v-if="previewFilters.length > 0" class="preview-crossfilter-bar">
              <el-tag
                v-for="f in previewFilters"
                :key="f.field"
                closable
                type="warning"
                effect="plain"
                @close="previewFilters = previewFilters.filter(x => x.field !== f.field)"
              >{{ f.field }} = {{ f.value }}</el-tag>
            </div>
            <el-empty v-if="componentCount(selectedDashboard) === 0" description="暂无组件" />
            <div v-else ref="previewGridRef" class="preview-grid">
              <div
                v-for="item in selectedDashboard.layout_json?.components || []"
                :key="item.id"
                class="preview-component"
                :style="componentStyle(item)"
              >
                <PinnedChartCard
                  :chart="chartForComponent(item)"
                  :active-filters="previewFilters"
                  @delete="noop"
                  @filter="handlePreviewFilter"
                />
              </div>
            </div>
          </div>

          <!-- 评论侧栏 -->
          <aside v-if="showComments" class="preview-comment-panel">
            <div class="comment-panel-header">
              <strong>协作评论</strong>
              <span class="comment-count">{{ comments.length }} 条</span>
            </div>
            <div class="comment-list" ref="commentListRef">
              <div v-for="c in comments" :key="c.id" class="comment-item">
                <div class="comment-meta">
                  <span class="comment-author">{{ c.username }}</span>
                  <span class="comment-time">{{ formatCommentTime(c.created_at) }}</span>
                  <el-button
                    v-if="c.user_id === currentUserId || isAdmin"
                    text
                    type="danger"
                    size="small"
                    class="comment-del"
                    @click="deleteComment(c.id)"
                  >删除</el-button>
                </div>
                <p class="comment-content">{{ c.content }}</p>
              </div>
              <div v-if="comments.length === 0" class="comment-empty">暂无评论，来说点什么吧</div>
            </div>
            <div class="comment-input-area">
              <el-input
                v-model="newComment"
                type="textarea"
                :rows="3"
                placeholder="写下你的评论..."
                maxlength="2000"
                show-word-limit
                @keydown.ctrl.enter="submitComment"
              />
              <el-button type="primary" size="small" :loading="commentSubmitting" @click="submitComment" style="margin-top:8px;width:100%">
                发送 (Ctrl+Enter)
              </el-button>
            </div>
          </aside>
        </div>
      </template>
    </el-drawer>

    <el-drawer v-model="designerVisible" :with-header="false" size="92%" class="designer-drawer" @opened="() => window.dispatchEvent(new Event('resize'))">
      <div v-if="designingDashboard" class="designer-shell">
        <aside class="designer-sidebar">
          <div class="sidebar-header">
            <div class="sidebar-header-top">
              <div class="sidebar-title-group">
                <h3>图表库</h3>
                <span class="sidebar-count">{{ pinnedCharts.length }}</span>
              </div>
              <div class="designer-panel-actions">
                <el-button size="small" @click="chartManagerVisible = true">管理</el-button>
                <el-button type="primary" size="small" :icon="Plus" @click="openChartCreator">新建</el-button>
              </div>
            </div>
            <el-input
              v-model="chartKeyword"
              placeholder="搜索图表…"
              clearable
              size="small"
              :prefix-icon="Search"
            />
          </div>

          <div class="chart-library">
            <div
              v-for="chart in filteredPinnedCharts"
              :key="chart.id"
              class="chart-library-item"
              draggable="true"
              @dragstart="startLibraryDrag(chart)"
            >
              <div class="lib-header">
                <el-icon class="lib-drag-icon"><Rank /></el-icon>
                <span class="lib-name">{{ chart.title }}</span>
              </div>
              <div class="lib-footer">
                <div class="lib-meta">
                  <el-tag size="small" effect="plain" round>{{ chartTypeLabel(chart.chart_type) }}</el-tag>
                  <span class="lib-rows">{{ chart.rows.length }} 行</span>
                </div>
                <div class="lib-acts">
                  <el-tooltip content="预览" placement="top">
                    <el-button size="small" text @click.stop="previewLibraryChart(chart)">
                      <el-icon><View /></el-icon>
                    </el-button>
                  </el-tooltip>
                  <el-button size="small" type="primary" @click.stop="addChartToCanvas(chart)">
                    <el-icon><Plus /></el-icon>添加
                  </el-button>
                </div>
              </div>
            </div>
            <el-empty v-if="!filteredPinnedCharts.length" description="暂无可用图表" :image-size="60">
              <el-button type="primary" size="small" @click="openChartCreator">新建图表</el-button>
            </el-empty>
          </div>
        </aside>

        <main class="designer-main">
          <header class="designer-topbar">
            <div>
              <h2>{{ designingDashboard.title }}</h2>
              <p>{{ designingDashboard.description || "拖拽左侧图表到画布，调整尺寸后保存" }}</p>
            </div>
            <div class="designer-actions">
              <el-button @click="designerVisible = false">关闭</el-button>
              <el-button type="primary" :loading="designerSaving" @click="saveDesigner">保存布局</el-button>
            </div>
          </header>

          <section class="designer-canvas-wrap">
            <div class="canvas-ruler">
              <span v-for="column in 12" :key="column">{{ column }}</span>
            </div>
            <div class="designer-canvas" @dragover.prevent @drop="dropOnCanvas">
              <div v-if="!designerComponents.length" class="canvas-empty">
                <el-icon><Plus /></el-icon>
                <span>拖入图表开始设计看板</span>
              </div>
              <div
                v-for="(component, index) in designerComponents"
                :key="component.id"
                class="canvas-component"
                :class="{ selected: selectedComponentId === component.id }"
                :style="componentStyle(component)"
                draggable="true"
                @click="selectComponent(component.id)"
                @dragstart="startComponentDrag(index)"
                @dragover.prevent
                @drop.stop="dropComponent(index)"
              >
                <div class="canvas-component-toolbar">
                  <el-icon class="drag-handle canvas-drag"><Rank /></el-icon>
                  <span class="component-title-text">{{ component.title }}</span>
                  <div class="component-actions">
                    <el-tag size="small" effect="plain" round>{{ chartTypeLabel(component.chart_type) }}</el-tag>
                    <el-tooltip content="上移" placement="top">
                      <el-button text size="small" :disabled="index === 0" @click.stop="moveComponent(index, -1)">
                        <el-icon><ArrowUp /></el-icon>
                      </el-button>
                    </el-tooltip>
                    <el-tooltip content="下移" placement="top">
                      <el-button text size="small" :disabled="index === designerComponents.length - 1" @click.stop="moveComponent(index, 1)">
                        <el-icon><ArrowDown /></el-icon>
                      </el-button>
                    </el-tooltip>
                    <el-tooltip content="移除" placement="top">
                      <el-button text size="small" type="danger" @click.stop="removeComponent(component.id)">
                        <el-icon><Delete /></el-icon>
                      </el-button>
                    </el-tooltip>
                  </div>
                </div>
                <PinnedChartCard :chart="designerChartDataMap[component.id]" @delete="removeComponent(component.id)" />
              </div>
            </div>
          </section>
        </main>

        <aside class="designer-properties">
          <div class="designer-panel-header">
            <div>
              <h3>属性</h3>
              <span>{{ selectedComponent ? "组件设置" : "未选择组件" }}</span>
            </div>
          </div>

          <template v-if="selectedComponent">
            <el-form label-position="top" class="property-form">
              <el-form-item label="标题">
                <el-input v-model="selectedComponent.title" maxlength="128" />
              </el-form-item>
              <el-form-item label="描述">
                <el-input v-model="selectedComponent.description" type="textarea" :rows="2" placeholder="可选" />
              </el-form-item>
              <el-divider style="margin: 4px 0" />
              <el-form-item label="图表类型">
                <el-select v-model="selectedComponent.chart_type" style="width: 100%">
                  <el-option v-for="o in chartTypeOptions" :key="o.value" :label="o.label" :value="o.value" />
                </el-select>
              </el-form-item>
              <el-form-item label="排序">
                <el-select v-model="selectedComponent.sort_order" style="width: 100%">
                  <el-option label="默认" value="none" />
                  <el-option label="降序" value="desc" />
                  <el-option label="升序" value="asc" />
                </el-select>
              </el-form-item>
              <el-divider style="margin: 4px 0" />
              <el-form-item label="宽度（列）">
                <div class="slider-with-val">
                  <el-slider v-model="selectedComponent.w" :min="3" :max="12" show-stops style="flex: 1" />
                  <span class="slider-val">{{ selectedComponent.w }}/12</span>
                </div>
              </el-form-item>
              <el-form-item label="高度">
                <div class="slider-with-val">
                  <el-slider v-model="selectedComponent.h" :min="2" :max="6" show-stops style="flex: 1" />
                  <span class="slider-val">{{ selectedComponent.h }}</span>
                </div>
              </el-form-item>
            </el-form>
          </template>
          <el-empty v-else description="点击画布中的组件编辑属性" :image-size="64" />
        </aside>
      </div>
    </el-drawer>

    <el-dialog
      v-model="chartCreatorVisible"
      :title="editingChartId ? '编辑图表' : '新建图表'"
      width="860px"
      append-to-body
      class="chart-creator-dialog"
    >
      <el-form :model="chartForm" label-position="top" class="chart-creator-form">
        <el-tabs v-model="chartDialogTab" class="modal-tabs">
          <el-tab-pane label="图表配置" name="config">
            <div class="modal-tab-content">
              <el-row :gutter="12">
                <el-col :xs="24" :sm="12">
                  <el-form-item label="标题">
                    <el-input v-model="chartForm.title" maxlength="128" />
                  </el-form-item>
                </el-col>
                <el-col :xs="24" :sm="12">
                  <el-form-item label="数据源">
                    <el-select v-model="chartForm.datasource_id" style="width: 100%">
                      <el-option v-for="datasource in datasourceStore.datasources" :key="datasource.id" :label="datasource.name" :value="datasource.id" />
                    </el-select>
                  </el-form-item>
                </el-col>
                <el-col :xs="24" :sm="12">
                  <el-form-item label="图表类型">
                    <el-select v-model="chartForm.chart_type" style="width: 100%">
                      <el-option v-for="option in chartTypeOptions" :key="option.value" :label="option.label" :value="option.value" />
                    </el-select>
                  </el-form-item>
                </el-col>
                <el-col :xs="24" :sm="12">
                  <el-form-item label="排序">
                    <el-select v-model="chartForm.sort_order" style="width: 100%">
                      <el-option label="默认" value="none" />
                      <el-option label="降序" value="desc" />
                      <el-option label="升序" value="asc" />
                    </el-select>
                  </el-form-item>
                </el-col>
              </el-row>
              <el-form-item label="描述">
                <el-input v-model="chartForm.description" type="textarea" :rows="2" />
              </el-form-item>
            </div>
          </el-tab-pane>

          <el-tab-pane label="数据查询" name="query">
            <div class="modal-tab-content">
              <el-form-item label="创建方式">
                <el-segmented v-model="chartCreateMode" :options="chartCreateModeOptions" />
              </el-form-item>
              <el-form-item v-if="chartCreateMode === 'nl'" label="问题">
                <el-input v-model="chartForm.question" type="textarea" :rows="3" placeholder="例如：统计每个月的销售额趋势" />
              </el-form-item>
              <el-form-item label="SQL">
                <SqlEditor v-model="chartForm.sql_query" :datasource-id="chartForm.datasource_id" :rows="6" />
              </el-form-item>
            </div>
          </el-tab-pane>

          <el-tab-pane label="预览" name="preview">
            <div class="modal-tab-content">
              <div v-if="chartPreviewResult && chartPreviewResult.rows.length" class="preview-ai-toolbar">
                <el-button size="small" plain @click="openForecastFromPreview">
                  <el-icon><TrendCharts /></el-icon> 预测分析
                </el-button>
                <el-button size="small" plain @click="openAiReportFromPreview">
                  <el-icon><MagicStick /></el-icon> AI 分析报告
                </el-button>
              </div>
              <section class="chart-preview-panel">
                <PinnedChartCard v-if="chartPreviewResult && chartPreviewResult.rows.length" :chart="chartPreviewCard" @delete="noop" />
                <el-empty v-else description="点击底部「预览」按钮生成图表" :image-size="72" />
              </section>
            </div>
          </el-tab-pane>
        </el-tabs>
      </el-form>
      <template #footer>
        <el-button @click="chartCreatorVisible = false">取消</el-button>
        <el-button :loading="chartPreviewLoading" @click="previewChartDraft">预览</el-button>
        <el-button type="primary" :loading="chartCreateLoading" @click="saveCreatedChart">
          {{ editingChartId ? '保存' : '保存并加入画布' }}
        </el-button>
      </template>
    </el-dialog>

    <!-- Chart library management modal -->
    <el-dialog
      v-model="chartManagerVisible"
      title="图表库管理"
      width="860px"
      append-to-body
    >
      <div class="chart-manager-bar">
        <el-input
          v-model="managerKeyword"
          placeholder="搜索图表…"
          clearable
          :prefix-icon="Search"
          style="width: 240px"
        />
        <el-button type="primary" :icon="Plus" @click="openChartCreator">新建图表</el-button>
      </div>
      <el-table :data="filteredManagerCharts" stripe style="width: 100%" :loading="chartLoading">
        <el-table-column prop="title" label="图表名称" min-width="200" show-overflow-tooltip />
        <el-table-column label="类型" width="90">
          <template #default="{ row }">
            <el-tag size="small" effect="plain">{{ chartTypeLabel(row.chart_type) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="数据行" width="80" align="center">
          <template #default="{ row }">
            <span :class="row.rows.length === 0 ? 'zero-rows' : ''">{{ row.rows.length }}</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="260" fixed="right">
          <template #default="{ row }">
            <el-button size="small" text @click="previewLibraryChart(row)">预览</el-button>
            <el-button size="small" text type="primary" @click="openChartEditor(row)">编辑</el-button>
            <el-button size="small" text type="primary" @click="openAiReportForChart(row.id, row.title)">AI分析</el-button>
            <el-button size="small" text type="danger" @click="deleteLibraryChart(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
      <template #footer>
        <el-button @click="chartManagerVisible = false">关闭</el-button>
      </template>
    </el-dialog>

    <el-dialog
      v-model="chartLibraryPreviewVisible"
      :title="chartLibraryPreviewChart?.title || '图表预览'"
      width="760px"
      append-to-body
      @opened="() => window.dispatchEvent(new Event('resize'))"
    >
      <div style="height: 340px; padding: 4px">
        <PinnedChartCard
          v-if="chartLibraryPreviewChart"
          :chart="chartLibraryPreviewChart"
          @delete="noop"
        />
      </div>
    </el-dialog>

    <ForecastPanel
      v-model="forecastVisible"
      :datasource-id="forecastChart?.datasource_id ?? null"
      :sql-query="forecastChart?.sql_query ?? ''"
      :chart-title="forecastChart?.title"
    />

    <AiReportDrawer
      v-model="aiReportVisible"
      :chart-id="aiReportProps.chartId"
      :title="aiReportProps.title"
      :datasource-id="aiReportProps.datasourceId"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, reactive, ref } from "vue"
import { useRoute } from "vue-router"
import axios from "axios"
import { ElMessage, ElMessageBox } from "element-plus"
import { Plus, Refresh, Search, ArrowDown, ArrowUp, TrendCharts, MagicStick, View, Edit, Delete, Rank } from "@element-plus/icons-vue"
import PinnedChartCard from "@/components/PinnedChartCard.vue"
import ForecastPanel from "@/components/ForecastPanel.vue"
import AiReportDrawer from "@/components/AiReportDrawer.vue"
import SqlEditor from "@/components/SqlEditor.vue"
import { useDatasourceStore } from "@/store/datasource"
import { useAuthStore } from "@/store/auth"

interface DashboardComponent {
  id: string
  pinned_chart_id: number
  title: string
  description?: string | null
  chart_type: string
  sort_order: string
  x: number
  y: number
  w: number
  h: number
}

interface DashboardLayout {
  components?: DashboardComponent[]
}

interface DashboardItem {
  id: number
  title: string
  description: string | null
  layout_json: DashboardLayout | null
  filters_json: Record<string, unknown> | null
  status: string
  visibility: string
  is_public: number
  share_token: string | null
  shared_user_ids: number[] | null
  version: number
}

interface PinnedChartData {
  id: number
  title: string
  description: string | null
  sql_query?: string
  datasource_id?: number | null
  chart_type: string
  sort_order: string
  columns: string[]
  rows: Array<Record<string, unknown>>
}

interface ChartPreviewResult {
  columns: string[]
  rows: Array<Record<string, unknown>>
}

interface DashboardTemplate {
  id: string
  name: string
  description: string
}

const datasourceStore = useDatasourceStore()
const route = useRoute()
const dashboards = ref<DashboardItem[]>([])
const pinnedCharts = ref<PinnedChartData[]>([])
const designerComponents = ref<DashboardComponent[]>([])
const loading = ref(false)
const saving = ref(false)
const chartLoading = ref(false)
const designerSaving = ref(false)
const chartPreviewLoading = ref(false)
const chartCreateLoading = ref(false)
const editorVisible = ref(false)
const previewVisible = ref(false)
const designerVisible = ref(false)
const authStore = useAuthStore()
const currentUserId = computed(() => authStore.profile?.id)
const isAdmin = computed(() => ["super_admin", "org_admin"].includes(authStore.profile?.role || ""))

// 导出
const previewGridRef = ref<HTMLElement | null>(null)
const exporting = ref(false)

const handleExport = async (format: "png" | "pdf") => {
  if (!previewGridRef.value) return
  exporting.value = true
  try {
    const html2canvas = (await import("html2canvas")).default
    const canvas = await html2canvas(previewGridRef.value, { scale: 1.5, useCORS: true, backgroundColor: "#fff" })
    const title = selectedDashboard.value?.title || "dashboard"
    if (format === "png") {
      const link = document.createElement("a")
      link.download = `${title}.png`
      link.href = canvas.toDataURL("image/png")
      link.click()
    } else {
      const { jsPDF } = await import("jspdf")
      const imgData = canvas.toDataURL("image/jpeg", 0.9)
      const pdf = new jsPDF({ orientation: canvas.width > canvas.height ? "l" : "p", unit: "px", format: [canvas.width, canvas.height] })
      pdf.addImage(imgData, "JPEG", 0, 0, canvas.width, canvas.height)
      pdf.save(`${title}.pdf`)
    }
    ElMessage.success(`已导出为 ${format.toUpperCase()}`)
  } catch (e) {
    ElMessage.error("导出失败")
  } finally {
    exporting.value = false
  }
}

// 评论
interface Comment { id: number; dashboard_id: number; user_id: number; username: string; content: string; created_at: string }
const showComments = ref(false)
const comments = ref<Comment[]>([])
const newComment = ref("")
const commentSubmitting = ref(false)
const commentListRef = ref<HTMLElement | null>(null)

const fetchComments = async (dashboardId: number) => {
  try {
    const res = await axios.get(`/api/dashboards/${dashboardId}/comments`)
    comments.value = res.data
  } catch { comments.value = [] }
}

const submitComment = async () => {
  const content = newComment.value.trim()
  if (!content || !selectedDashboard.value) return
  commentSubmitting.value = true
  try {
    await axios.post(`/api/dashboards/${selectedDashboard.value.id}/comments`, { content })
    newComment.value = ""
    await fetchComments(selectedDashboard.value.id)
    await nextTick()
    if (commentListRef.value) commentListRef.value.scrollTop = commentListRef.value.scrollHeight
  } catch { ElMessage.error("评论发送失败") }
  finally { commentSubmitting.value = false }
}

const deleteComment = async (commentId: number) => {
  if (!selectedDashboard.value) return
  await axios.delete(`/api/dashboards/${selectedDashboard.value.id}/comments/${commentId}`)
  comments.value = comments.value.filter(c => c.id !== commentId)
}

const formatCommentTime = (t: string) => {
  if (!t) return ""
  const d = new Date(t)
  return `${d.getMonth() + 1}/${d.getDate()} ${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`
}

const onPreviewClose = () => {
  previewFilters.value = []
  showComments.value = false
  comments.value = []
}

interface CrossFilter { field: string; value: any }
const previewFilters = ref<CrossFilter[]>([])

const handlePreviewFilter = (filter: CrossFilter) => {
  const existing = previewFilters.value.findIndex(f => f.field === filter.field)
  if (existing >= 0) {
    if (previewFilters.value[existing].value === filter.value) {
      previewFilters.value.splice(existing, 1)
    } else {
      previewFilters.value[existing] = filter
    }
  } else {
    previewFilters.value.push(filter)
  }
}
const chartCreatorVisible = ref(false)
const chartDialogTab = ref("config")
const editingChartId = ref<number | null>(null)
const chartLibraryPreviewVisible = ref(false)
const chartLibraryPreviewChart = ref<PinnedChartData | null>(null)
const chartManagerVisible = ref(false)
const managerKeyword = ref("")
const templateVisible = ref(false)
const templateLoading = ref(false)
const shareVisible = ref(false)
const selectedDashboard = ref<DashboardItem | null>(null)
const designingDashboard = ref<DashboardItem | null>(null)
const shareTarget = ref<DashboardItem | null>(null)
const selectedComponentId = ref("")
const draggedChartId = ref<number | null>(null)
const draggedComponentIndex = ref<number | null>(null)
const editingId = ref<number | null>(null)
const statusFilter = ref("all")
const chartKeyword = ref("")
const libraryChartType = ref("auto")
const chartCreateMode = ref("nl")
const chartPreviewResult = ref<ChartPreviewResult | null>(null)
const templates = ref<DashboardTemplate[]>([])
const sharePublic = ref(false)
const shareUserIdsText = ref("")
const shareSaving = ref(false)

// Forecast
const forecastVisible = ref(false)
const forecastChart = ref<{ datasource_id: number | null; sql_query: string; title: string } | null>(null)

// AI report
const aiReportVisible = ref(false)
const aiReportProps = ref<{ chartId: number | null; title: string; datasourceId: number | null }>({
  chartId: null, title: "", datasourceId: null,
})

// Embed tokens
interface EmbedToken { id: number; token: string; label: string | null; resource_type: string; resource_id: number; allowed_domains: string | null; expires_at: string | null; created_at: string }
const embedTokens = ref<EmbedToken[]>([])
const embedTokenForm = reactive({ label: "", expires_days: null as number | null })
const embedTokenLoading = ref(false)
const embedTokenCreating = ref(false)

const fetchEmbedTokens = async (dashboardId: number) => {
  embedTokenLoading.value = true
  try {
    const res = await axios.get("/api/embed/tokens")
    embedTokens.value = res.data.filter((t: EmbedToken) => t.resource_type === "dashboard" && t.resource_id === dashboardId)
  } catch { embedTokens.value = [] }
  finally { embedTokenLoading.value = false }
}

const createEmbedToken = async () => {
  if (!shareTarget.value) return
  embedTokenCreating.value = true
  try {
    await axios.post("/api/embed/tokens", {
      label: embedTokenForm.label || `${shareTarget.value.title} 嵌入`,
      resource_type: "dashboard",
      resource_id: shareTarget.value.id,
      expires_days: embedTokenForm.expires_days || null,
    })
    await fetchEmbedTokens(shareTarget.value.id)
    embedTokenForm.label = ""
    embedTokenForm.expires_days = null
    ElMessage.success("Embed Token 已创建")
  } catch { ElMessage.error("创建失败") }
  finally { embedTokenCreating.value = false }
}

const deleteEmbedToken = async (tokenId: number) => {
  await axios.delete(`/api/embed/tokens/${tokenId}`)
  embedTokens.value = embedTokens.value.filter(t => t.id !== tokenId)
}

const embedCode = (token: EmbedToken) => {
  const origin = window.location.origin
  return `<script src="${origin}/embed.js"><\/script>\n<div id="smart-bi-embed"></div>\n<script>\n  SmartBI.embed({ token: "${token.token}", target: "#smart-bi-embed", height: "500px" });\n<\/script>`
}

const copyEmbedCode = async (token: EmbedToken) => {
  try {
    await navigator.clipboard.writeText(embedCode(token))
    ElMessage.success("嵌入代码已复制")
  } catch { ElMessage.error("复制失败") }
}

const shareDialogTab = ref("share")

const statusOptions = [
  { label: "全部", value: "all" },
  { label: "已发布", value: "published" },
  { label: "草稿", value: "draft" },
]
const chartCreateModeOptions = [
  { label: "自然语言", value: "nl" },
  { label: "SQL", value: "sql" },
]
const chartTypeOptions = [
  { label: "指标卡", value: "kpi" },
  { label: "明细表", value: "table" },
  { label: "柱状图", value: "bar" },
  { label: "条形图", value: "horizontal_bar" },
  { label: "折线图", value: "line" },
  { label: "面积图", value: "area" },
  { label: "饼图", value: "pie" },
  { label: "环形图", value: "donut" },
  { label: "散点图", value: "scatter" },
  { label: "组合图", value: "combo" },
  { label: "漏斗图", value: "funnel" },
  { label: "仪表盘", value: "gauge" },
]

const form = reactive({
  title: "",
  description: "",
  visibility: "private",
})

const chartForm = reactive({
  title: "",
  description: "",
  question: "",
  sql_query: "",
  datasource_id: null as number | null,
  chart_type: "bar",
  sort_order: "desc",
})

const selectedComponent = computed(() =>
  designerComponents.value.find((component) => component.id === selectedComponentId.value) || null
)

const shareLink = computed(() => {
  if (!shareTarget.value?.share_token) return ""
  return `${window.location.origin}/api/dashboards/public/${shareTarget.value.share_token}`
})

const chartPreviewCard = computed<PinnedChartData>(() => ({
  id: 0,
  title: chartForm.title || "预览图表",
  description: chartForm.description || null,
  chart_type: chartForm.chart_type,
  sort_order: chartForm.sort_order,
  columns: chartPreviewResult.value?.columns || [],
  rows: chartPreviewResult.value?.rows || [],
}))

const filteredPinnedCharts = computed(() => {
  const keyword = chartKeyword.value.trim().toLowerCase()
  if (!keyword) return pinnedCharts.value
  return pinnedCharts.value.filter((chart) =>
    [chart.title, chart.description || ""].some((value) => value.toLowerCase().includes(keyword))
  )
})

const filteredManagerCharts = computed(() => {
  const keyword = managerKeyword.value.trim().toLowerCase()
  if (!keyword) return pinnedCharts.value
  return pinnedCharts.value.filter((chart) =>
    [chart.title, chart.description || ""].some((value) => value.toLowerCase().includes(keyword))
  )
})

const componentCount = (dashboard: DashboardItem) => dashboard.layout_json?.components?.length || 0

const componentStyle = (component: DashboardComponent) => ({
  gridColumn: `span ${Math.min(Math.max(component.w || 6, 3), 12)}`,
  minHeight: `${Math.min(Math.max(component.h || 3, 2), 6) * 96}px`,
})

const chartTypeLabel = (type: string) => {
  return chartTypeOptions.find((option) => option.value === type)?.label || type
}

const resolveLibraryChartType = (chart: PinnedChartData) => (
  libraryChartType.value === "auto" ? chart.chart_type : libraryChartType.value
)

const defaultComponentSize = (chartType: string) => {
  const sizes: Record<string, Pick<DashboardComponent, "w" | "h">> = {
    kpi: { w: 3, h: 2 },
    table: { w: 12, h: 4 },
    pie: { w: 4, h: 3 },
    donut: { w: 4, h: 3 },
    scatter: { w: 6, h: 4 },
    combo: { w: 8, h: 4 },
  }
  return sizes[chartType] || { w: 6, h: 3 }
}

const noop = () => {}

const apiErrorMessage = (error: unknown, fallback: string) => {
  if (axios.isAxiosError(error)) {
    const detail = error.response?.data?.detail
    if (typeof detail === "string") return detail
  }
  return fallback
}

const cloneComponents = (dashboard: DashboardItem): DashboardComponent[] =>
  (dashboard.layout_json?.components || []).map((component, index) => ({
    id: component.id || `component-${Date.now()}-${index}`,
    pinned_chart_id: component.pinned_chart_id,
    title: component.title,
    description: component.description || null,
    chart_type: component.chart_type || "bar",
    sort_order: component.sort_order || "desc",
    x: component.x || 0,
    y: component.y ?? index,
    w: component.w || 6,
    h: component.h || 3,
  }))

const chartForComponent = (component: DashboardComponent): PinnedChartData => {
  const chart = pinnedCharts.value.find((item) => item.id === component.pinned_chart_id)
  return {
    id: component.pinned_chart_id,
    title: component.title,
    description: component.description || chart?.description || null,
    chart_type: component.chart_type || chart?.chart_type || "bar",
    sort_order: component.sort_order || chart?.sort_order || "desc",
    columns: chart?.columns || [],
    rows: chart?.rows || [],
  }
}

// 画布专用稳定 chart 数据缓存：仅当 designerComponents / pinnedCharts 变化时重算，
// 选中状态切换不会影响此 computed，从而避免 PinnedChartCard 因 prop 引用变化而重绘 ECharts
const designerChartDataMap = computed<Record<string, PinnedChartData>>(() => {
  const map: Record<string, PinnedChartData> = {}
  for (const component of designerComponents.value) {
    const chart = pinnedCharts.value.find((item) => item.id === component.pinned_chart_id)
    map[component.id] = {
      id: component.pinned_chart_id,
      title: component.title,
      description: component.description || chart?.description || null,
      chart_type: component.chart_type || chart?.chart_type || "bar",
      sort_order: component.sort_order || chart?.sort_order || "desc",
      columns: chart?.columns || [],
      rows: chart?.rows || [],
    }
  }
  return map
})

const fetchDashboards = async () => {
  loading.value = true
  try {
    const response = await axios.get("/api/dashboards", {
      params: { status: statusFilter.value === "all" ? undefined : statusFilter.value },
    })
    dashboards.value = response.data.items
  } catch (error) {
    ElMessage.error("看板加载失败")
  } finally {
    loading.value = false
  }
}

const fetchPinnedCharts = async () => {
  chartLoading.value = true
  try {
    const response = await axios.get("/api/pinned-charts/with-data")
    pinnedCharts.value = response.data
  } catch (error) {
    ElMessage.error("图表库加载失败")
  } finally {
    chartLoading.value = false
  }
}

const fetchTemplates = async () => {
  templateLoading.value = true
  try {
    const response = await axios.get("/api/dashboard-templates")
    templates.value = response.data.items
  } catch (error) {
    ElMessage.error("模板加载失败")
  } finally {
    templateLoading.value = false
  }
}

const resetForm = () => {
  editingId.value = null
  form.title = ""
  form.description = ""
  form.visibility = "private"
}

const openCreate = () => {
  resetForm()
  editorVisible.value = true
}

const openTemplateDialog = async () => {
  templateVisible.value = true
  if (!templates.value.length) {
    await fetchTemplates()
  }
}

const createFromTemplate = async (template: DashboardTemplate) => {
  try {
    await axios.post(`/api/dashboard-templates/${template.id}/dashboards`, null, {
      params: { title: template.name },
    })
    templateVisible.value = false
    ElMessage.success("已从模板创建看板")
    await fetchDashboards()
  } catch (error) {
    ElMessage.error(apiErrorMessage(error, "模板创建失败"))
  }
}

const edit = (dashboard: DashboardItem) => {
  editingId.value = dashboard.id
  form.title = dashboard.title
  form.description = dashboard.description || ""
  form.visibility = dashboard.visibility
  editorVisible.value = true
}

const save = async () => {
  if (!form.title.trim()) {
    ElMessage.warning("请输入看板名称")
    return
  }
  saving.value = true
  try {
    const payload = {
      title: form.title.trim(),
      description: form.description || null,
      visibility: form.visibility,
      layout_json: editingId.value ? undefined : { components: [] },
      filters_json: editingId.value ? undefined : {},
    }
    if (editingId.value) {
      await axios.put(`/api/dashboards/${editingId.value}`, payload)
    } else {
      await axios.post("/api/dashboards", payload)
    }
    editorVisible.value = false
    await fetchDashboards()
  } catch (error) {
    ElMessage.error("看板保存失败")
  } finally {
    saving.value = false
  }
}

const publish = async (dashboard: DashboardItem) => {
  await axios.post(`/api/dashboards/${dashboard.id}/publish`)
  ElMessage.success("看板已发布")
  await fetchDashboards()
}

const openShare = (dashboard: DashboardItem) => {
  shareTarget.value = dashboard
  sharePublic.value = !!dashboard.is_public
  shareUserIdsText.value = (dashboard.shared_user_ids || []).join(", ")
  shareDialogTab.value = "share"
  shareVisible.value = true
  fetchEmbedTokens(dashboard.id)
}

const saveShare = async () => {
  if (!shareTarget.value) return
  shareSaving.value = true
  try {
    const sharedUserIds = shareUserIdsText.value
      .split(/[\n,，]/)
      .map((item) => Number(item.trim()))
      .filter((item) => Number.isFinite(item) && item > 0)
    const response = await axios.put(`/api/dashboards/${shareTarget.value.id}/share`, {
      is_public: sharePublic.value,
      shared_user_ids: sharedUserIds,
    })
    const index = dashboards.value.findIndex((dashboard) => dashboard.id === response.data.id)
    if (index !== -1) dashboards.value[index] = response.data
    shareTarget.value = response.data
    ElMessage.success("分享配置已保存")
  } catch (error) {
    ElMessage.error(apiErrorMessage(error, "分享配置保存失败"))
  } finally {
    shareSaving.value = false
  }
}

const remove = async (dashboard: DashboardItem) => {
  await ElMessageBox.confirm("确定要删除这个看板吗？", "提示", {
    confirmButtonText: "删除",
    cancelButtonText: "取消",
    type: "warning",
  })
  await axios.delete(`/api/dashboards/${dashboard.id}`)
  await fetchDashboards()
}

const preview = async (dashboard: DashboardItem) => {
  if (!pinnedCharts.value.length) await fetchPinnedCharts()
  selectedDashboard.value = dashboard
  previewVisible.value = true
  fetchComments(dashboard.id)
}

const openDesigner = async (dashboard: DashboardItem) => {
  if (!pinnedCharts.value.length) await fetchPinnedCharts()
  if (!datasourceStore.datasources.length) await datasourceStore.fetchDatasources().catch(() => undefined)
  designingDashboard.value = dashboard
  designerComponents.value = cloneComponents(dashboard)
  selectedComponentId.value = designerComponents.value[0]?.id || ""
  designerVisible.value = true
}

const openDashboardFromRouteQuery = async () => {
  const rawId = Array.isArray(route.query.dashboard_id)
    ? route.query.dashboard_id[0]
    : route.query.dashboard_id
  const dashboardId = Number(rawId)
  if (!Number.isFinite(dashboardId) || dashboardId <= 0) return

  let target = dashboards.value.find((dashboard) => dashboard.id === dashboardId) || null
  if (!target) {
    try {
      const response = await axios.get(`/api/dashboards/${dashboardId}`)
      target = response.data
    } catch {
      ElMessage.error("看板不存在或无权访问")
      return
    }
  }

  if (route.query.mode === "edit") {
    await openDesigner(target)
  } else {
    await preview(target)
  }
}

const startLibraryDrag = (chart: PinnedChartData) => {
  draggedChartId.value = chart.id
  draggedComponentIndex.value = null
}

const startComponentDrag = (index: number) => {
  draggedComponentIndex.value = index
  draggedChartId.value = null
}

const addChartToCanvas = (chart: PinnedChartData, chartTypeOverride?: string) => {
  const nextIndex = designerComponents.value.length
  const chartType = chartTypeOverride || resolveLibraryChartType(chart)
  const size = defaultComponentSize(chartType)
  const component: DashboardComponent = {
    id: `component-${chart.id}-${Date.now()}`,
    pinned_chart_id: chart.id,
    title: chart.title,
    description: chart.description,
    chart_type: chartType,
    sort_order: chart.sort_order,
    x: 0,
    y: nextIndex,
    w: size.w,
    h: size.h,
  }
  designerComponents.value.push(component)
  selectedComponentId.value = component.id
}

const resetChartForm = () => {
  editingChartId.value = null
  chartCreateMode.value = "nl"
  chartForm.title = ""
  chartForm.description = ""
  chartForm.question = ""
  chartForm.sql_query = ""
  chartForm.datasource_id = datasourceStore.currentId || datasourceStore.datasources[0]?.id || null
  chartForm.chart_type = libraryChartType.value === "auto" ? "bar" : libraryChartType.value
  chartForm.sort_order = "desc"
  chartPreviewResult.value = null
}

const ensureChartDatasource = async () => {
  if (!datasourceStore.datasources.length) {
    await datasourceStore.fetchDatasources()
  }
  if (!chartForm.datasource_id) {
    chartForm.datasource_id = datasourceStore.currentId || datasourceStore.datasources[0]?.id || null
  }
  return !!chartForm.datasource_id
}

const openChartCreator = async () => {
  try {
    if (!(await ensureChartDatasource())) {
      ElMessage.warning("请先配置数据源")
      return
    }
    resetChartForm()
    chartDialogTab.value = "config"
    chartCreatorVisible.value = true
  } catch (error) {
    ElMessage.error(apiErrorMessage(error, "数据源加载失败"))
  }
}

const previewLibraryChart = (chart: PinnedChartData) => {
  chartLibraryPreviewChart.value = chart
  chartLibraryPreviewVisible.value = true
}

const openChartEditor = async (chart: PinnedChartData) => {
  try {
    if (!datasourceStore.datasources.length) await datasourceStore.fetchDatasources().catch(() => undefined)
    editingChartId.value = chart.id
    chartCreateMode.value = "sql"
    chartForm.title = chart.title
    chartForm.description = chart.description || ""
    chartForm.question = ""
    chartForm.sql_query = chart.sql_query || ""
    chartForm.datasource_id = chart.datasource_id ?? datasourceStore.currentId ?? datasourceStore.datasources[0]?.id ?? null
    chartForm.chart_type = chart.chart_type
    chartForm.sort_order = chart.sort_order
    chartPreviewResult.value = chart.rows.length
      ? { columns: chart.columns, rows: chart.rows as Array<Record<string, unknown>> }
      : null
    chartDialogTab.value = "config"
    chartCreatorVisible.value = true
  } catch (error) {
    ElMessage.error(apiErrorMessage(error, "数据源加载失败"))
  }
}

const deleteLibraryChart = async (chart: PinnedChartData) => {
  const usedInCanvas = designerComponents.value.some(c => c.pinned_chart_id === chart.id)
  const msg = usedInCanvas
    ? `图表"${chart.title}"已在当前画布中使用，删除后画布中对应组件将无数据。确认删除？`
    : `确定删除图表"${chart.title}"？`
  try {
    await ElMessageBox.confirm(msg, "删除图表", {
      confirmButtonText: "删除",
      cancelButtonText: "取消",
      type: "warning",
    })
    await axios.delete(`/api/pinned-charts/${chart.id}`)
    await fetchPinnedCharts()
    ElMessage.success("图表已删除")
  } catch (e: any) {
    if (e !== "cancel") ElMessage.error(apiErrorMessage(e, "删除失败"))
  }
}

const generateChartFromQuestion = async () => {
  const question = chartForm.question.trim()
  if (!question) {
    ElMessage.warning("请输入问题")
    return false
  }
  if (!(await ensureChartDatasource())) {
    ElMessage.warning("请先配置数据源")
    return false
  }

  const response = await axios.post("/api/query/ask", {
    question,
    mode: "text2sql",
    datasource_id: chartForm.datasource_id,
  })
  chartForm.sql_query = response.data.sql_query || ""
  chartPreviewResult.value = response.data.result || { columns: [], rows: [] }
  if (!chartForm.title.trim()) {
    chartForm.title = question.slice(0, 64)
  }
  return true
}

const previewChartSql = async () => {
  const sql = chartForm.sql_query.trim()
  if (!sql) {
    ElMessage.warning("请输入 SQL")
    return false
  }
  if (!(await ensureChartDatasource())) {
    ElMessage.warning("请先配置数据源")
    return false
  }

  const response = await axios.post("/api/pinned-charts/preview", {
    sql_query: sql,
    datasource_id: chartForm.datasource_id,
  })
  chartPreviewResult.value = response.data
  return true
}

const previewChartDraft = async () => {
  chartPreviewLoading.value = true
  try {
    const ok = chartCreateMode.value === "nl"
      ? await generateChartFromQuestion()
      : await previewChartSql()
    if (ok) {
      chartDialogTab.value = "preview"
      if (chartPreviewResult.value && !chartPreviewResult.value.rows.length) {
        ElMessage.warning("查询成功，但没有返回数据")
      }
    }
    return ok
  } catch (error) {
    ElMessage.error(apiErrorMessage(error, "图表预览失败"))
    return false
  } finally {
    chartPreviewLoading.value = false
  }
}

const saveCreatedChart = async () => {
  if (!chartForm.title.trim()) {
    ElMessage.warning("请输入图表标题")
    return
  }
  if (!chartForm.sql_query.trim()) {
    const ok = await previewChartDraft()
    if (!ok || !chartForm.sql_query.trim()) return
  }
  if (!chartPreviewResult.value) {
    const ok = await previewChartDraft()
    if (!ok) return
  }

  chartCreateLoading.value = true
  try {
    if (editingChartId.value) {
      await axios.put(`/api/pinned-charts/${editingChartId.value}`, {
        title: chartForm.title.trim(),
        description: chartForm.description.trim() || null,
        sql_query: chartForm.sql_query.trim(),
        chart_type: chartForm.chart_type,
        sort_order: chartForm.sort_order,
      })
      await fetchPinnedCharts()
      chartCreatorVisible.value = false
      ElMessage.success("图表已更新")
    } else {
      const response = await axios.post("/api/pinned-charts", {
        title: chartForm.title.trim(),
        description: chartForm.description.trim() || null,
        sql_query: chartForm.sql_query.trim(),
        chart_type: chartForm.chart_type,
        sort_order: chartForm.sort_order,
        datasource_id: chartForm.datasource_id,
      })
      await fetchPinnedCharts()
      const createdChart = pinnedCharts.value.find((chart) => chart.id === response.data.id) || {
        id: response.data.id,
        title: response.data.title,
        description: response.data.description,
        chart_type: response.data.chart_type,
        sort_order: response.data.sort_order,
        columns: chartPreviewResult.value?.columns || [],
        rows: chartPreviewResult.value?.rows || [],
      }
      addChartToCanvas(createdChart, chartForm.chart_type)
      chartCreatorVisible.value = false
      ElMessage.success("图表已创建并加入画布")
    }
  } catch (error) {
    ElMessage.error(apiErrorMessage(error, editingChartId.value ? "图表更新失败" : "图表创建失败"))
  } finally {
    chartCreateLoading.value = false
  }
}

const dropOnCanvas = () => {
  if (!draggedChartId.value) return
  const chart = pinnedCharts.value.find((item) => item.id === draggedChartId.value)
  if (chart) addChartToCanvas(chart)
  draggedChartId.value = null
}

const dropComponent = (targetIndex: number) => {
  if (draggedComponentIndex.value === null || draggedComponentIndex.value === targetIndex) return
  const [component] = designerComponents.value.splice(draggedComponentIndex.value, 1)
  designerComponents.value.splice(targetIndex, 0, component)
  designerComponents.value = designerComponents.value.map((item, index) => ({ ...item, y: index }))
  draggedComponentIndex.value = null
}

const selectComponent = (id: string) => {
  selectedComponentId.value = id
}

const moveComponent = (index: number, direction: -1 | 1) => {
  const targetIndex = index + direction
  if (targetIndex < 0 || targetIndex >= designerComponents.value.length) return
  const next = [...designerComponents.value]
  const [component] = next.splice(index, 1)
  next.splice(targetIndex, 0, component)
  designerComponents.value = next.map((item, itemIndex) => ({ ...item, y: itemIndex }))
}

const removeComponent = (id: string | number) => {
  const componentId = String(id)
  designerComponents.value = designerComponents.value
    .filter((component) => component.id !== componentId)
    .map((component, index) => ({ ...component, y: index }))
  if (selectedComponentId.value === componentId) {
    selectedComponentId.value = designerComponents.value[0]?.id || ""
  }
}

const saveDesigner = async () => {
  if (!designingDashboard.value) return
  designerSaving.value = true
  try {
    const response = await axios.put(`/api/dashboards/${designingDashboard.value.id}`, {
      layout_json: { components: designerComponents.value },
      filters_json: designingDashboard.value.filters_json || {},
    })
    const index = dashboards.value.findIndex((dashboard) => dashboard.id === response.data.id)
    if (index !== -1) dashboards.value[index] = response.data
    designingDashboard.value = response.data
    ElMessage.success("布局已保存")
  } catch (error) {
    ElMessage.error("布局保存失败")
  } finally {
    designerSaving.value = false
  }
}

const openForecastFromPreview = () => {
  forecastChart.value = {
    datasource_id: chartForm.datasource_id,
    sql_query: chartForm.sql_query,
    title: chartForm.title,
  }
  forecastVisible.value = true
}

const openAiReportFromPreview = () => {
  aiReportProps.value = {
    chartId: null,
    title: chartForm.title,
    datasourceId: chartForm.datasource_id,
  }
  aiReportVisible.value = true
}

const openForecastForChart = (chart: PinnedChartData) => {
  forecastChart.value = {
    datasource_id: null,
    sql_query: "",
    title: chart.title,
  }
  forecastVisible.value = true
}

const openAiReportForChart = (chartId: number, title: string) => {
  aiReportProps.value = { chartId, title, datasourceId: null }
  aiReportVisible.value = true
}

onMounted(async () => {
  await Promise.all([
    fetchDashboards(),
    fetchPinnedCharts(),
    datasourceStore.fetchDatasources().catch(() => undefined),
  ])
  await openDashboardFromRouteQuery()
})
</script>

<style scoped>
.dashboard-center-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
}

.toolbar-actions {
  display: flex;
  align-items: center;
  gap: 10px;
}

.dashboard-table :deep(.el-table__row) {
  cursor: pointer;
}

.dashboard-table :deep(.el-table__row:hover > td) {
  background: rgba(15, 118, 110, 0.05) !important;
}

.preview-header,
.designer-topbar,
.designer-panel-header,
.canvas-component-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.preview-title {
  margin: 0 0 8px;
  font-size: 18px;
}

.preview-header-right {
  display: flex;
  align-items: center;
  gap: 10px;
}

.preview-crossfilter-bar {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
  padding: 8px 12px;
  background: rgba(217, 119, 6, 0.06);
  border: 1px solid rgba(217, 119, 6, 0.25);
  border-radius: var(--app-radius-sm);
  margin-bottom: 12px;
}

.preview-body {
  display: flex;
  gap: 16px;
  height: calc(100% - 80px);
  overflow: hidden;
}

.preview-charts-area {
  flex: 1;
  overflow-y: auto;
  min-width: 0;
}

.preview-comment-panel {
  width: 300px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  border: 1px solid var(--app-border);
  border-radius: var(--app-radius-sm);
  background: var(--app-surface);
  overflow: hidden;
}

.comment-panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 14px;
  border-bottom: 1px solid var(--app-border);
  font-size: 13px;
}

.comment-count {
  color: var(--app-text-muted);
  font-size: 12px;
}

.comment-list {
  flex: 1;
  overflow-y: auto;
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.comment-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.comment-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
}

.comment-author {
  font-weight: 600;
  color: var(--app-text);
}

.comment-time {
  color: var(--app-text-muted);
}

.comment-del {
  margin-left: auto;
  opacity: 0;
  transition: opacity 0.15s;
}

.comment-item:hover .comment-del {
  opacity: 1;
}

.comment-content {
  margin: 0;
  font-size: 13px;
  color: var(--app-text);
  line-height: 1.5;
  white-space: pre-wrap;
  word-break: break-word;
}

.comment-empty {
  text-align: center;
  color: var(--app-text-muted);
  font-size: 13px;
  padding: 24px 0;
}

.comment-input-area {
  padding: 12px;
  border-top: 1px solid var(--app-border);
}

.preview-description,
.designer-topbar p {
  margin: 0;
  color: var(--app-text-muted);
}

.preview-grid,
.designer-canvas {
  display: grid;
  grid-template-columns: repeat(12, minmax(0, 1fr));
  gap: 14px;
}

.preview-component,
.canvas-component {
  min-width: 0;
}

.designer-drawer :deep(.el-drawer__body) {
  padding: 0;
}

.designer-shell {
  display: grid;
  grid-template-columns: 300px minmax(0, 1fr) 260px;
  min-height: 100vh;
  background: var(--app-bg);
}

.designer-sidebar {
  display: flex;
  flex-direction: column;
  height: 100vh;
  overflow: hidden;
  background: var(--app-surface);
  border-right: 1px solid var(--app-border);
}

.sidebar-header {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 14px 14px 10px;
  border-bottom: 1px solid var(--app-border);
  flex-shrink: 0;
}

.sidebar-header-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.sidebar-title-group {
  display: flex;
  align-items: center;
  gap: 6px;
}

.sidebar-title-group h3 {
  margin: 0;
  font-size: 14px;
  font-weight: 600;
}

.sidebar-count {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 20px;
  height: 18px;
  padding: 0 5px;
  background: var(--app-border);
  border-radius: 9px;
  font-size: 11px;
  color: var(--app-text-muted);
  font-weight: 500;
}

.designer-properties {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 14px;
  background: var(--app-surface);
  border-left: 1px solid var(--app-border);
  height: 100vh;
  overflow-y: auto;
}

.designer-topbar h2 {
  margin: 0;
}

.designer-panel-actions {
  display: flex;
  align-items: center;
  gap: 4px;
}

.chart-library {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 5px;
  overflow-y: auto;
  min-height: 0;
  padding: 10px 12px 16px;
}

.chart-library-item {
  border: 1px solid var(--app-border);
  border-left: 3px solid transparent;
  border-radius: var(--app-radius-sm);
  background: var(--app-surface);
  cursor: grab;
  transition: border-color 0.15s, box-shadow 0.15s, background 0.15s;
}

.chart-library-item:hover {
  border-left-color: var(--app-primary);
  border-color: rgba(15, 118, 110, 0.3);
  background: rgba(15, 118, 110, 0.02);
  box-shadow: 0 1px 6px rgba(15, 118, 110, 0.1);
}

.lib-header {
  display: flex;
  align-items: flex-start;
  gap: 5px;
  padding: 9px 10px 7px 8px;
}

.lib-drag-icon {
  flex-shrink: 0;
  margin-top: 2px;
  color: var(--app-text-muted);
  opacity: 0.25;
  font-size: 13px;
  transition: opacity 0.15s;
  cursor: grab;
}

.chart-library-item:hover .lib-drag-icon {
  opacity: 0.5;
}

.lib-name {
  flex: 1;
  min-width: 0;
  font-size: 13px;
  font-weight: 600;
  color: var(--app-text);
  line-height: 1.45;
  word-break: break-all;
}

.lib-footer {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 5px 8px 7px 8px;
  border-top: 1px solid var(--app-border);
  background: rgba(0, 0, 0, 0.02);
}

.lib-meta {
  flex: 1;
  min-width: 0;
  display: flex;
  align-items: center;
  gap: 4px;
  overflow: hidden;
}

.lib-rows {
  font-size: 11px;
  color: var(--app-text-muted);
  white-space: nowrap;
  flex-shrink: 0;
}

.lib-acts {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  gap: 4px;
}

.lib-acts .el-button {
  margin-left: 0;
}

/* Keep drag-handle for canvas toolbar */
.drag-handle {
  color: var(--app-text-muted);
  opacity: 0.4;
  cursor: grab;
  flex-shrink: 0;
  font-size: 14px;
}

.chart-manager-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
}

.zero-rows {
  color: var(--el-color-warning);
}

.designer-main {
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.designer-topbar {
  padding: 14px 18px;
  background: var(--app-surface);
  border-bottom: 1px solid var(--app-border);
}

.designer-actions {
  display: flex;
  gap: 10px;
}

.designer-canvas-wrap {
  padding: 14px 18px 20px;
  overflow: auto;
}

.canvas-ruler {
  display: grid;
  grid-template-columns: repeat(12, minmax(0, 1fr));
  gap: 14px;
  margin-bottom: 8px;
  color: var(--app-text-muted);
  font-size: 12px;
  text-align: center;
}

.designer-canvas {
  position: relative;
  min-height: calc(100vh - 130px);
  padding: 16px;
  border: 1px dashed #b7c5d3;
  border-radius: var(--app-radius);
  background:
    linear-gradient(#ffffff, #ffffff) padding-box,
    repeating-linear-gradient(
      90deg,
      rgba(15, 118, 110, 0.05) 0,
      rgba(15, 118, 110, 0.05) 1px,
      transparent 1px,
      transparent calc((100% - 154px) / 12 + 14px)
    );
  align-content: start;
}

.canvas-empty {
  grid-column: 1 / -1;
  min-height: 280px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  color: var(--app-text-muted);
  border: 1px dashed var(--app-border);
  border-radius: var(--app-radius);
  background: rgba(255, 255, 255, 0.7);
}

.canvas-component {
  padding: 8px;
  border: 1px solid transparent;
  border-radius: var(--app-radius);
  background: var(--app-surface);
  cursor: grab;
  transition: border-color 0.2s, box-shadow 0.2s;
}

.canvas-component :deep(.el-card__header) {
  display: none;
}

.canvas-component :deep(.pinned-chart-card) {
  border: none;
  box-shadow: none;
}

.canvas-component :deep(.el-card__body) {
  padding: 8px;
}

.canvas-component.selected {
  border-color: var(--app-primary);
  box-shadow: 0 0 0 3px rgba(15, 118, 110, 0.14);
}

.canvas-component-toolbar {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 4px 2px 8px;
}

.canvas-drag {
  font-size: 14px;
  flex-shrink: 0;
}

.component-title-text {
  flex: 1;
  min-width: 0;
  font-size: 13px;
  font-weight: 600;
  color: var(--app-text);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.component-actions {
  display: flex;
  align-items: center;
  gap: 2px;
  flex-shrink: 0;
}

.property-form {
  width: 100%;
}

.chart-creator-form {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.chart-preview-panel {
  min-height: 260px;
  padding: 10px;
  border: 1px solid var(--app-border);
  border-radius: var(--app-radius);
  background: var(--app-surface-muted);
}

.preview-ai-toolbar {
  display: flex;
  gap: 8px;
  margin-bottom: 10px;
}

.slider-with-val {
  display: flex;
  align-items: center;
  gap: 10px;
  width: 100%;
}

.slider-val {
  font-size: 12px;
  color: var(--app-text-muted);
  min-width: 32px;
  text-align: right;
}

.embed-create-form {
  display: flex;
  gap: 8px;
  align-items: center;
  flex-wrap: wrap;
  margin-bottom: 8px;
}

.embed-hint {
  margin-top: 12px;
  padding: 10px 12px;
  background: var(--app-surface-muted);
  border-radius: var(--app-radius-sm);
  font-size: 12px;
  color: var(--app-text-muted);
}

.embed-hint code {
  background: var(--app-border);
  padding: 1px 4px;
  border-radius: 3px;
  font-family: monospace;
}

@media (max-width: 1120px) {
  .designer-shell {
    grid-template-columns: 240px minmax(0, 1fr);
  }

  .designer-properties {
    grid-column: 1 / -1;
    min-height: auto;
    border-left: 0;
    border-top: 1px solid var(--app-border);
  }
}

@media (max-width: 760px) {
  .designer-shell {
    grid-template-columns: 1fr;
  }

  .designer-sidebar {
    border-right: 0;
    border-bottom: 1px solid var(--app-border);
  }

  .designer-topbar {
    align-items: flex-start;
    flex-direction: column;
  }

  .preview-grid,
  .designer-canvas {
    grid-template-columns: 1fr;
  }

  .preview-component,
  .canvas-component {
    grid-column: 1 / -1 !important;
  }

  .canvas-ruler {
    display: none;
  }
}
</style>
