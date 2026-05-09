<template>
  <div class="catalog-layout">

    <!-- ── Left: folder sidebar ── -->
    <aside class="folder-sidebar">
      <div class="folder-sidebar__head">
        <span class="folder-sidebar__title">文件夹</span>
        <div class="folder-sidebar__actions">
          <!-- Sort dropdown -->
          <el-dropdown trigger="click" @command="onFolderSort" size="small">
            <button class="icon-btn icon-btn--sm" :class="{ 'is-active': folderSort !== 'custom' }" title="排序">
              <el-icon><Sort /></el-icon>
            </button>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="custom" :class="{ 'is-checked': folderSort === 'custom' }">
                  <el-icon v-if="folderSort === 'custom'" style="color:var(--el-color-primary)"><Check /></el-icon>
                  <span style="margin-left:4px">默认排序</span>
                </el-dropdown-item>
                <el-dropdown-item command="name" :class="{ 'is-checked': folderSort === 'name' }">
                  <el-icon v-if="folderSort === 'name'" style="color:var(--el-color-primary)"><Check /></el-icon>
                  <span style="margin-left:4px">按名称排序</span>
                </el-dropdown-item>
                <el-dropdown-item command="created_at" :class="{ 'is-checked': folderSort === 'created_at' }">
                  <el-icon v-if="folderSort === 'created_at'" style="color:var(--el-color-primary)"><Check /></el-icon>
                  <span style="margin-left:4px">按创建时间排序</span>
                </el-dropdown-item>
                <el-dropdown-item v-if="isAdmin" divided command="edit_order">
                  <el-icon><Operation /></el-icon>
                  <span style="margin-left:4px">编辑默认排序…</span>
                </el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>

          <el-tooltip v-if="isAdmin" content="新建文件夹" placement="top" :show-after="600">
            <button class="icon-btn icon-btn--sm" @click="openAddCategory(null)">
              <el-icon><Plus /></el-icon>
            </button>
          </el-tooltip>
        </div>
      </div>

      <nav class="folder-nav">
        <!-- All assets -->
        <button
          class="folder-nav__item folder-nav__item--all"
          :class="{ 'is-active': selectedCategoryId === null }"
          @click="onCategoryClick(null)"
        >
          <el-icon class="folder-nav__icon"><Grid /></el-icon>
          <span class="folder-nav__label">全部资产</span>
          <span class="folder-nav__badge">{{ totalCount }}</span>
        </button>

        <div class="folder-nav__sep" />

        <!-- Folder tree (flattened) -->
        <template v-for="{ node, depth } in flattenedTree" :key="node.id">
          <button
            class="folder-nav__item"
            :class="{ 'is-active': selectedCategoryId === node.id }"
            :style="{ paddingLeft: `${10 + depth * 16}px` }"
            @click="onCategoryClick(node)"
          >
            <!-- expand toggle -->
            <button
              v-if="node.children?.length"
              class="folder-expand-btn"
              @click.stop="toggleExpand(node.id)"
            >{{ expandedIds.has(node.id) ? '▾' : '▸' }}</button>
            <span v-else class="folder-expand-placeholder" />

            <el-icon
              class="folder-nav__icon folder-icon"
              :class="{ 'folder-icon--open': selectedCategoryId === node.id }"
            >
              <component :is="selectedCategoryId === node.id ? FolderOpened : Folder" />
            </el-icon>
            <span class="folder-nav__label">{{ node.name }}</span>

            <span class="folder-nav__actions" @click.stop v-if="isAdmin">
              <el-tooltip content="子文件夹" placement="right" :show-after="600">
                <button class="icon-btn icon-btn--xs" @click="openAddCategory(node.id)">
                  <el-icon><Plus /></el-icon>
                </button>
              </el-tooltip>
              <el-tooltip content="重命名" placement="right" :show-after="600">
                <button class="icon-btn icon-btn--xs" @click="openRenameCategory(node)">
                  <el-icon><Edit /></el-icon>
                </button>
              </el-tooltip>
              <el-tooltip content="删除" placement="right" :show-after="600">
                <button class="icon-btn icon-btn--xs icon-btn--danger" @click="removeCategory(node.id)">
                  <el-icon><Delete /></el-icon>
                </button>
              </el-tooltip>
            </span>
          </button>
        </template>

        <p v-if="!categoryTree.length" class="folder-nav__empty">暂无文件夹</p>
      </nav>
    </aside>

    <!-- ── Edit default order dialog ── -->
    <el-dialog v-model="editOrderVisible" title="编辑默认排序" width="360px" :close-on-click-modal="false">
      <p class="edit-order-hint">拖拽文件夹以调整默认显示顺序（仅顶层）</p>
      <ul class="edit-order-list" @dragover.prevent>
        <li
          v-for="(cat, idx) in editOrderItems"
          :key="cat.id"
          class="edit-order-item"
          draggable="true"
          :class="{ 'is-drag-over': dragOverIndex === idx }"
          @dragstart="onDragStart(idx)"
          @dragenter.prevent="dragOverIndex = idx"
          @dragleave="dragOverIndex = null"
          @drop.prevent="onDrop(idx)"
          @dragend="dragOverIndex = null"
        >
          <el-icon class="drag-handle"><DCaret /></el-icon>
          <el-icon style="color:#f59e0b;margin:0 6px"><Folder /></el-icon>
          <span>{{ cat.name }}</span>
        </li>
      </ul>
      <template #footer>
        <el-button @click="editOrderVisible = false">取消</el-button>
        <el-button type="primary" @click="saveOrder" :loading="savingOrder">保存</el-button>
      </template>
    </el-dialog>

    <!-- ── Right: main content ── -->
    <main class="catalog-main">

      <!-- Breadcrumb + toolbar -->
      <div class="catalog-toolbar">
        <div class="catalog-toolbar__left">
          <el-breadcrumb separator="/">
            <el-breadcrumb-item @click="onCategoryClick(null)" class="bc-link">数据目录</el-breadcrumb-item>
            <el-breadcrumb-item v-if="selectedCategoryId !== null">
              {{ currentFolderName }}
            </el-breadcrumb-item>
          </el-breadcrumb>
          <span class="catalog-toolbar__count">{{ assets.length }} 项</span>
        </div>

        <div class="catalog-toolbar__right">

          <!-- Search + scope unified -->
          <div class="search-unified" :class="{ 'is-focused': searchFocused }">
            <button
              class="search-scope"
              :class="{ 'is-global': searchScope === 'global' }"
              @click.stop="searchScope = searchScope === 'folder' ? 'global' : 'folder'"
            >
              <el-icon><component :is="searchScope === 'folder' ? Folder : Grid" /></el-icon>
              <span>{{ searchScope === 'folder' ? '当前文件夹' : '全局搜索' }}</span>
              <el-icon class="search-scope__caret"><component :is="searchScope === 'folder' ? 'ArrowDown' : 'ArrowDown'" /></el-icon>
            </button>
            <span class="search-unified__sep" />
            <el-icon class="search-unified__prefix"><Search /></el-icon>
            <input
              v-model="keyword"
              class="search-unified__input"
              placeholder="搜索资产…"
              @keyup.enter="fetchAssets"
              @focus="searchFocused = true"
              @blur="searchFocused = false"
            />
            <button v-if="keyword" class="search-unified__clear" @click="keyword = ''; fetchAssets()">
              <el-icon><Close /></el-icon>
            </button>
          </div>

          <div class="toolbar-divider" />

          <!-- Type filter chips -->
          <div class="type-chips">
            <button
              v-for="t in typeOptions"
              :key="t.value"
              class="type-chip"
              :class="{ 'is-active': assetType === t.value }"
              :style="assetType === t.value ? { '--chip-color': t.color } : {}"
              @click="toggleType(t.value)"
            >{{ t.label }}</button>
          </div>

          <div class="toolbar-divider" />

          <!-- View toggle -->
          <div class="view-toggle">
            <button class="view-toggle__btn" :class="{ 'is-active': viewMode === 'card' }" @click="viewMode = 'card'" title="卡片视图">
              <el-icon><Grid /></el-icon>
            </button>
            <button class="view-toggle__btn" :class="{ 'is-active': viewMode === 'list' }" @click="viewMode = 'list'" title="列表视图">
              <el-icon><List /></el-icon>
            </button>
          </div>
        </div>
      </div>

      <!-- Loading skeleton -->
      <div v-if="loading" class="card-grid">
        <div v-for="i in 8" :key="i" class="asset-card asset-card--skeleton">
          <el-skeleton animated>
            <template #template>
              <div style="padding:16px">
                <el-skeleton-item variant="rect" style="height:6px;width:40%;border-radius:4px;margin-bottom:12px" />
                <el-skeleton-item variant="h3" style="width:70%;margin-bottom:8px" />
                <el-skeleton-item variant="text" style="width:90%;margin-bottom:4px" />
                <el-skeleton-item variant="text" style="width:60%" />
              </div>
            </template>
          </el-skeleton>
        </div>
      </div>

      <!-- Empty state -->
      <div v-else-if="!assets.length" class="catalog-empty">
        <el-icon class="catalog-empty__icon"><FolderOpened /></el-icon>
        <p class="catalog-empty__title">{{ selectedCategoryId ? '该文件夹暂无资产' : '暂无数据资产' }}</p>
        <p class="catalog-empty__sub">可通过发布数据集或指标自动同步资产到目录</p>
      </div>

      <!-- Card grid view -->
      <div v-else-if="viewMode === 'card'" class="card-grid">
        <article
          v-for="asset in assets"
          :key="asset.id"
          class="asset-card"
          @click="showDetail(asset)"
        >
          <div class="asset-card__header" :style="{ background: assetTypeGradient(asset.asset_type) }">
            <el-icon class="asset-card__type-icon">
              <component :is="assetTypeIcon(asset.asset_type)" />
            </el-icon>
            <div class="asset-card__badges">
              <span class="asset-card__status-dot" :class="`dot--${asset.status}`" />
              <span v-if="asset.asset_type === 'metric' && asset.metadata_json?.certification_status === 'certified'" class="cert-badge">✓ 已认证</span>
            </div>
          </div>
          <div class="asset-card__body">
            <h3 class="asset-card__name" :title="asset.name">{{ asset.name }}</h3>
            <p class="asset-card__desc">{{ asset.description || '暂无描述' }}</p>
            <div class="asset-card__tags">
              <span
                v-for="tag in (asset.tags || []).slice(0, 3)"
                :key="tag"
                class="asset-tag"
              >{{ tag }}</span>
            </div>
          </div>
          <div class="asset-card__footer">
            <span class="asset-card__type-label" :style="{ color: assetTypeColor(asset.asset_type) }">
              {{ assetTypeLabel(asset.asset_type) }}
            </span>
            <span class="asset-card__views">
              <el-icon style="font-size:11px"><View /></el-icon>
              {{ asset.view_count ?? 0 }}
            </span>
          </div>
        </article>
      </div>

      <!-- List view -->
      <el-table
        v-else
        :data="assets"
        class="asset-table"
        row-class-name="asset-table-row"
        @row-click="showDetail"
      >
        <el-table-column label="资产名称" min-width="200">
          <template #default="{ row }">
            <div class="list-name-cell">
              <span class="list-type-dot" :style="{ background: assetTypeColor(row.asset_type) }" />
              <span class="list-name">{{ row.name }}</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="类型" width="90">
          <template #default="{ row }">
            <el-tag size="small" effect="plain" :style="{ color: assetTypeColor(row.asset_type), borderColor: assetTypeColor(row.asset_type) }">
              {{ assetTypeLabel(row.asset_type) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="80">
          <template #default="{ row }">
            <el-tag :type="row.status === 'published' ? 'success' : 'info'" size="small" effect="plain">
              {{ statusLabel(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="description" label="描述" min-width="200" show-overflow-tooltip />
        <el-table-column label="标签" min-width="140">
          <template #default="{ row }">
            <el-space wrap>
              <el-tag v-for="tag in row.tags || []" :key="tag" size="small" effect="plain">{{ tag }}</el-tag>
            </el-space>
          </template>
        </el-table-column>
        <el-table-column label="浏览" width="70" align="center">
          <template #default="{ row }">
            <span class="muted-sm">{{ row.view_count ?? 0 }}</span>
          </template>
        </el-table-column>
      </el-table>
    </main>

    <!-- ── Detail Drawer ── -->
    <el-drawer
      v-model="detailVisible"
      size="500px"
      :with-header="false"
      @open="onDrawerOpen"
    >
      <template v-if="selectedAsset">
        <!-- Drawer hero -->
        <div class="drawer-hero" :style="{ background: assetTypeGradient(selectedAsset.asset_type) }">
          <div class="drawer-hero__icon">
            <el-icon>
              <component :is="assetTypeIcon(selectedAsset.asset_type)" />
            </el-icon>
          </div>
          <div class="drawer-hero__meta">
            <div class="drawer-hero__type">{{ assetTypeLabel(selectedAsset.asset_type) }}</div>
            <h2 class="drawer-hero__name">{{ selectedAsset.name }}</h2>
          </div>
          <div class="drawer-hero__actions">
            <el-button
              :type="subscribed ? 'warning' : 'default'"
              size="small"
              round
              @click="toggleSubscription"
            >
              <el-icon><component :is="subscribed ? BellFilled : Bell" /></el-icon>
              {{ subscribed ? '取消关注' : '关注' }}
            </el-button>
            <el-button
              v-if="selectedAsset.asset_type === 'dashboard' && selectedAsset.asset_id"
              type="primary" size="small" round
              @click="openDashboardPreview(selectedAsset.asset_id!)"
            >预览看板</el-button>
            <el-button
              v-if="selectedAsset.asset_type === 'dataset' && selectedAsset.asset_id"
              type="primary" size="small" round
              @click="router.push('/dataset-center')"
            >打开数据集</el-button>
          </div>
        </div>

        <!-- Status strip -->
        <div class="drawer-strip">
          <div class="strip-item">
            <span class="strip-label">状态</span>
            <el-tag :type="selectedAsset.status === 'published' ? 'success' : 'info'" size="small" effect="light">
              {{ statusLabel(selectedAsset.status) }}
            </el-tag>
          </div>
          <div class="strip-item">
            <span class="strip-label">文件夹</span>
            <el-select
              v-if="isAdmin"
              :model-value="selectedAsset.category_id"
              placeholder="未分类"
              clearable
              size="small"
              style="width:130px"
              @change="(v: number | null) => assignCategory(v)"
            >
              <el-option v-for="cat in flatCategories" :key="cat.id" :label="cat.name" :value="cat.id" />
            </el-select>
            <span v-else class="strip-value">{{ categoryName(selectedAsset.category_id) || '未分类' }}</span>
          </div>
          <div class="strip-item">
            <span class="strip-label">浏览</span>
            <span class="strip-value">{{ selectedAsset.view_count ?? 0 }} 次</span>
          </div>
          <div v-if="refCount !== null" class="strip-item strip-item--link" @click="activeTab = 'refs'">
            <span class="strip-label">引用</span>
            <span class="strip-value strip-value--primary">{{ refCount }} 处</span>
          </div>
        </div>

        <!-- Tabs -->
        <el-tabs v-model="activeTab" class="drawer-tabs">

          <!-- Info -->
          <el-tab-pane label="概览" name="info">
            <div class="drawer-section">
              <p class="drawer-desc">{{ selectedAsset.description || '暂无描述' }}</p>
              <div v-if="selectedAsset.tags?.length" class="drawer-tags">
                <span v-for="tag in selectedAsset.tags" :key="tag" class="asset-tag">{{ tag }}</span>
              </div>
            </div>

            <div v-if="selectedAsset.asset_type === 'metric'" class="trust-card">
              <div class="trust-card__head">
                <span class="trust-card__title">可信指标</span>
                <div class="trust-badges">
                  <el-tag :type="certTagType(selectedAsset.metadata_json?.certification_status)" size="small" effect="light">
                    {{ certLabel(selectedAsset.metadata_json?.certification_status) }}
                  </el-tag>
                  <el-tag :type="qualityTagType(selectedAsset.metadata_json?.quality_status)" size="small" effect="light">
                    {{ qualityLabel(selectedAsset.metadata_json?.quality_status) }}
                  </el-tag>
                </div>
              </div>
              <div class="trust-grid">
                <div class="trust-row"><span>负责人</span><span>{{ selectedAsset.metadata_json?.owner_name || '-' }}</span></div>
                <div class="trust-row"><span>口径版本</span><span>{{ selectedAsset.metadata_json?.caliber_version || 'v1' }}</span></div>
                <div class="trust-row"><span>认证人</span><span>{{ selectedAsset.metadata_json?.certified_by || '-' }}</span></div>
                <div class="trust-row"><span>数据更新</span><span>{{ formatDate(selectedAsset.metadata_json?.data_updated_at) }}</span></div>
                <div class="trust-row trust-row--full"><span>计算公式</span><span>{{ selectedAsset.metadata_json?.formula || '-' }}</span></div>
                <div v-if="selectedAsset.metadata_json?.quality_message" class="trust-row trust-row--full">
                  <span>质量说明</span><span>{{ selectedAsset.metadata_json.quality_message }}</span>
                </div>
              </div>
            </div>
          </el-tab-pane>

          <!-- Fields -->
          <el-tab-pane
            v-if="selectedAsset.asset_type === 'dataset' || selectedAsset.asset_type === 'table'"
            label="字段" name="fields"
          >
            <div v-loading="fieldsLoading" style="min-height:120px">
              <el-empty v-if="!fieldsLoading && !fields.length" description="暂无字段信息" :image-size="60" />
              <div v-else class="field-list">
                <div v-for="f in fields" :key="f.name" class="field-row">
                  <span class="field-name">{{ f.name }}</span>
                  <span class="field-type">{{ f.type }}</span>
                  <span class="field-desc">{{ f.description || '' }}</span>
                </div>
              </div>
            </div>
          </el-tab-pane>

          <!-- Preview -->
          <el-tab-pane
            v-if="selectedAsset.asset_type === 'dataset' || selectedAsset.asset_type === 'table'"
            label="预览" name="preview"
          >
            <div v-loading="previewLoading" style="min-height:120px">
              <el-empty v-if="!previewLoading && !previewColumns.length" description="暂无预览数据" :image-size="60" />
              <el-table v-else :data="previewRows" size="small" max-height="340" border style="width:100%">
                <el-table-column
                  v-for="col in previewColumns" :key="col"
                  :prop="col" :label="col" min-width="110" show-overflow-tooltip
                />
              </el-table>
            </div>
          </el-tab-pane>

          <!-- Lineage -->
          <el-tab-pane label="血缘" name="lineage">
            <div v-loading="lineageLoading" style="min-height:120px">
              <el-empty v-if="!lineageLoading && !lineageNodes.length" description="暂无血缘记录" :image-size="60" />
              <div v-else>
                <VueFlow
                  :nodes="flowNodes"
                  :edges="flowEdges"
                  :fit-view-on-init="true"
                  class="lineage-flow"
                >
                  <template #node-custom="{ data }">
                    <div :class="['flow-node', `flow-node--${data.asset_type}`]" @click="jumpToAsset(data.id)">
                      <div class="flow-node-type">{{ assetTypeLabel(data.asset_type) }}</div>
                      <div class="flow-node-name">{{ data.label }}</div>
                    </div>
                  </template>
                </VueFlow>
                <div v-if="isAdmin" class="lineage-add">
                  <el-button text size="small" @click="showAddLineage = true">+ 手动添加血缘</el-button>
                </div>
              </div>
            </div>
          </el-tab-pane>

          <!-- References -->
          <el-tab-pane label="被引用" name="refs">
            <div v-loading="refsLoading" style="min-height:120px">
              <el-empty v-if="!refsLoading && !refs.length" description="未被任何看板或大屏引用" :image-size="60" />
              <div v-else class="ref-list">
                <div v-for="r in refs" :key="r.id" class="ref-row">
                  <el-tag size="small" effect="plain">{{ r.type === 'dashboard' ? '看板' : '大屏' }}</el-tag>
                  <span class="ref-name">{{ r.name }}</span>
                  <el-button v-if="r.type === 'dashboard'" text type="primary" size="small" @click="openDashboardPreview(r.id)">预览</el-button>
                </div>
              </div>
            </div>
          </el-tab-pane>

        </el-tabs>
      </template>
    </el-drawer>

    <!-- ── New folder dialog ── -->
    <el-dialog v-model="categoryDialogVisible" :title="categoryDialogTitle" width="340px" align-center>
      <el-input
        v-model="categoryDialogName"
        placeholder="文件夹名称"
        :prefix-icon="Folder"
        autofocus
        @keyup.enter="submitCategory"
      />
      <template #footer>
        <el-button @click="categoryDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitCategory">确定</el-button>
      </template>
    </el-dialog>

    <!-- ── Add lineage dialog ── -->
    <el-dialog v-model="showAddLineage" title="手动添加血缘关系" width="400px" align-center>
      <el-form label-width="72px" style="margin-top:8px">
        <el-form-item label="上游资产">
          <el-select v-model="newLineage.source_id" filterable placeholder="选择上游资产" style="width:100%">
            <el-option v-for="a in assets" :key="a.id" :label="a.name" :value="a.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="下游资产">
          <el-select v-model="newLineage.target_id" filterable placeholder="选择下游资产" style="width:100%">
            <el-option v-for="a in assets" :key="a.id" :label="a.name" :value="a.id" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showAddLineage = false">取消</el-button>
        <el-button type="primary" @click="addLineage">确定</el-button>
      </template>
    </el-dialog>

    <!-- ── Dashboard preview dialog ── -->
    <el-dialog
      v-model="dashboardPreviewVisible"
      width="86vw"
      top="5vh"
      append-to-body
      destroy-on-close
      class="catalog-dashboard-preview-dialog"
      @opened="() => window.dispatchEvent(new Event('resize'))"
    >
      <template #header>
        <div class="dashboard-preview-head">
          <div class="dashboard-preview-title-group">
            <span class="dashboard-preview-eyebrow">看板预览</span>
            <h3>{{ dashboardPreview?.title || '看板预览' }}</h3>
            <p>{{ dashboardPreview?.description || '暂无描述' }}</p>
          </div>
          <div class="dashboard-preview-actions">
            <el-tag v-if="dashboardPreview" effect="plain">
              {{ dashboardComponentCount(dashboardPreview) }} 个组件
            </el-tag>
            <el-button
              v-if="dashboardPreview"
              type="primary"
              :icon="Edit"
              @click="openDashboardEditorFromPreview"
            >
              编辑
            </el-button>
          </div>
        </div>
      </template>

      <div v-loading="dashboardPreviewLoading" class="dashboard-preview-body">
        <el-empty
          v-if="!dashboardPreviewLoading && (!dashboardPreview || dashboardComponentCount(dashboardPreview) === 0)"
          description="该看板暂无组件"
          :image-size="72"
        />
        <div v-else class="catalog-preview-grid">
          <div
            v-for="item in dashboardPreview?.layout_json?.components || []"
            :key="item.id"
            class="catalog-preview-component"
            :style="dashboardComponentStyle(item)"
          >
            <PinnedChartCard
              :chart="chartForDashboardComponent(item)"
              @delete="noop"
            />
          </div>
        </div>
      </div>
    </el-dialog>

  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch, type Component } from "vue"
import { useRouter } from "vue-router"
import axios from "axios"
import { ElMessage, ElMessageBox } from "element-plus"
import {
  ArrowDown, Bell, BellFilled, Check, Close, DataAnalysis, DataBoard, DCaret,
  Delete, Edit, Files, Folder, FolderOpened, Grid, List, Monitor, Operation,
  Plus, Search, Sort, Tickets, View,
} from "@element-plus/icons-vue"
import { VueFlow, type Node as FlowNode, type Edge as FlowEdge, Position } from "@vue-flow/core"
import "@vue-flow/core/dist/style.css"
import "@vue-flow/core/dist/theme-default.css"
import { useAuthStore } from "@/store/auth"
import PinnedChartCard from "@/components/PinnedChartCard.vue"

interface DataAsset {
  id: number
  asset_type: string
  asset_id: number | null
  name: string
  description: string | null
  status: string
  tags: string[] | null
  metadata_json: Record<string, any> | null
  category_id: number | null
  view_count: number
}

interface Category {
  id: number
  name: string
  parent_id: number | null
  org_id: number | null
  children: Category[]
}

interface FieldInfo { name: string; type: string; description: string | null }
interface RefItem { type: string; name: string; id: number }
interface LineageNodeRaw { id: number; name: string; asset_type: string }
interface LineageEdgeRaw { source: number; target: number; rel_type: string }
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
interface DashboardItem {
  id: number
  title: string
  description: string | null
  layout_json: { components?: DashboardComponent[] } | null
  status: string
  visibility: string
}
interface PinnedChartData {
  id: number
  title: string
  description: string | null
  chart_type: string
  sort_order: string
  columns: string[]
  rows: Array<Record<string, any>>
}

const router = useRouter()
const authStore = useAuthStore()
const isAdmin = computed(() => ["org_admin", "super_admin"].includes(authStore.profile?.role || ""))

const assets = ref<DataAsset[]>([])
const totalCount = ref(0)
const loading = ref(false)
const keyword = ref("")
const assetType = ref("")
const statusFilter = ref("")
const selectedCategoryId = ref<number | null>(null)
const viewMode = ref<"card" | "list">("card")

const detailVisible = ref(false)
const selectedAsset = ref<DataAsset | null>(null)
const activeTab = ref("info")

const subscribed = ref(false)
const fields = ref<FieldInfo[]>([])
const fieldsLoading = ref(false)
const previewColumns = ref<string[]>([])
const previewRows = ref<Record<string, any>[]>([])
const previewLoading = ref(false)
const lineageNodes = ref<LineageNodeRaw[]>([])
const lineageEdges = ref<LineageEdgeRaw[]>([])
const lineageLoading = ref(false)
const refs = ref<RefItem[]>([])
const refsLoading = ref(false)
const refCount = ref<number | null>(null)
const dashboardPreviewVisible = ref(false)
const dashboardPreviewLoading = ref(false)
const dashboardPreview = ref<DashboardItem | null>(null)
const dashboardPreviewCharts = ref<PinnedChartData[]>([])

const searchScope = ref<"folder" | "global">("folder")
const searchFocused = ref(false)

const categoryTree = ref<Category[]>([])
const expandedIds = ref<Set<number>>(new Set())

const flatCategories = computed(() => {
  const flat: Category[] = []
  const walk = (nodes: Category[]) => nodes.forEach(n => { flat.push(n); walk(n.children) })
  walk(categoryTree.value)
  return flat
})

interface FlatNode { node: Category; depth: number }
const flattenedTree = computed<FlatNode[]>(() => {
  const result: FlatNode[] = []
  const walk = (nodes: Category[], depth: number) => {
    for (const n of nodes) {
      result.push({ node: n, depth })
      if (n.children?.length && expandedIds.value.has(n.id)) {
        walk(n.children, depth + 1)
      }
    }
  }
  walk(sortedCategoryTree.value, 0)
  return result
})

const toggleExpand = (id: number) => {
  const s = new Set(expandedIds.value)
  s.has(id) ? s.delete(id) : s.add(id)
  expandedIds.value = s
}

const currentFolderName = computed(() =>
  flatCategories.value.find(c => c.id === selectedCategoryId.value)?.name || ""
)

// ── folder sort ───────────────────────────────────────────────────────────────
const folderSort = ref<"custom" | "name" | "created_at">("custom")

const sortedCategoryTree = computed<Category[]>(() => {
  const sortChildren = (nodes: Category[]): Category[] => {
    const sorted = [...nodes]
    if (folderSort.value === "name") {
      sorted.sort((a, b) => a.name.localeCompare(b.name, "zh"))
    } else if (folderSort.value === "created_at") {
      sorted.sort((a, b) => (a as any).created_at > (b as any).created_at ? -1 : 1)
    }
    return sorted.map(n => ({ ...n, children: sortChildren(n.children) }))
  }
  return sortChildren(categoryTree.value)
})

const onFolderSort = (cmd: string) => {
  if (cmd === "edit_order") {
    editOrderItems.value = categoryTree.value.map(c => ({ ...c }))
    editOrderVisible.value = true
  } else {
    folderSort.value = cmd as any
  }
}

const editOrderVisible = ref(false)
const editOrderItems = ref<Category[]>([])
const dragFromIndex = ref<number | null>(null)
const dragOverIndex = ref<number | null>(null)
const savingOrder = ref(false)

const onDragStart = (idx: number) => { dragFromIndex.value = idx }
const onDrop = (toIdx: number) => {
  if (dragFromIndex.value === null || dragFromIndex.value === toIdx) return
  const items = [...editOrderItems.value]
  const [moved] = items.splice(dragFromIndex.value, 1)
  items.splice(toIdx, 0, moved)
  editOrderItems.value = items
  dragFromIndex.value = null
  dragOverIndex.value = null
}

const saveOrder = async () => {
  savingOrder.value = true
  try {
    const payload = editOrderItems.value.map((c, i) => ({ id: c.id, sort_order: i }))
    await axios.put("/api/catalog/categories/reorder", payload)
    await fetchCategories()
    editOrderVisible.value = false
    ElMessage.success("排序已保存")
  } catch {
    ElMessage.error("保存失败")
  } finally {
    savingOrder.value = false
  }
}

const categoryDialogVisible = ref(false)
const categoryDialogTitle = ref("新建文件夹")
const categoryDialogName = ref("")
const categoryDialogParentId = ref<number | null>(null)
const categoryEditId = ref<number | null>(null)

const showAddLineage = ref(false)
const newLineage = reactive({ source_id: null as number | null, target_id: null as number | null })

// ── type config ───────────────────────────────────────────────────────────────

const TYPE_CONFIG: Record<string, { color: string; gradient: string; icon: Component; label: string }> = {
  metric:    { color: "#3b82f6", gradient: "linear-gradient(135deg,#3b82f6,#6366f1)", icon: DataAnalysis, label: "指标" },
  dataset:   { color: "#10b981", gradient: "linear-gradient(135deg,#10b981,#059669)", icon: Files, label: "数据集" },
  table:     { color: "#64748b", gradient: "linear-gradient(135deg,#64748b,#475569)", icon: Tickets, label: "数据表" },
  dashboard: { color: "#f59e0b", gradient: "linear-gradient(135deg,#f59e0b,#d97706)", icon: DataBoard, label: "看板" },
  big_screen:{ color: "#8b5cf6", gradient: "linear-gradient(135deg,#8b5cf6,#7c3aed)", icon: Monitor, label: "大屏" },
}

const typeOptions = Object.entries(TYPE_CONFIG).map(([v, c]) => ({ value: v, label: c.label, color: c.color }))

const assetTypeLabel   = (t: string) => TYPE_CONFIG[t]?.label || t
const assetTypeColor   = (t: string) => TYPE_CONFIG[t]?.color || "#606266"
const assetTypeGradient= (t: string) => TYPE_CONFIG[t]?.gradient || "linear-gradient(135deg,#64748b,#475569)"
const assetTypeIcon    = (t: string) => TYPE_CONFIG[t]?.icon || Folder
const statusLabel      = (v: string) => ({ draft:"草稿", published:"已发布", archived:"已归档" }[v] || v)
const certLabel = (s?: string) =>
  ({ draft:"草稿", pending_review:"待审核", certified:"已认证", deprecated:"已废弃" }[s||""] || "未认证")
const certTagType = (s?: string): "success"|"warning"|"info"|"danger" =>
  (({ draft:"info", pending_review:"warning", certified:"success", deprecated:"danger" } as any)[s||""] || "info")
const qualityLabel = (s?: string) =>
  ({ unknown:"未知", normal:"正常", stale:"过期", error:"异常" }[s||""] || "未知")
const qualityTagType = (s?: string): "success"|"warning"|"info"|"danger" =>
  (({ unknown:"info", normal:"success", stale:"warning", error:"danger" } as any)[s||""] || "info")
const formatDate = (v?: string) => {
  if (!v) return "-"
  const d = new Date(v)
  return isNaN(d.getTime()) ? v : d.toLocaleString("zh-CN", { hour12: false })
}
const categoryName = (id?: number | null) => flatCategories.value.find(c => c.id === id)?.name || null

const toggleType = (val: string) => {
  assetType.value = assetType.value === val ? "" : val
  fetchAssets()
}

// ── Vue Flow ──────────────────────────────────────────────────────────────────

const flowNodes = computed<FlowNode[]>(() => {
  if (!lineageNodes.value.length) return []
  const total = lineageNodes.value.length
  return lineageNodes.value.map((n, i) => ({
    id: String(n.id),
    type: "custom",
    position: { x: (i - Math.floor(total / 2)) * 200 + 220, y: 80 },
    data: { label: n.name, asset_type: n.asset_type, id: n.id },
    sourcePosition: Position.Right,
    targetPosition: Position.Left,
  }))
})

const flowEdges = computed<FlowEdge[]>(() =>
  lineageEdges.value.map((e, i) => ({
    id: `e-${i}`,
    source: String(e.source),
    target: String(e.target),
    animated: true,
    label: e.rel_type === "derives_from" ? "派生自" : "被使用",
  }))
)

// ── fetch ─────────────────────────────────────────────────────────────────────

const fetchAssets = async () => {
  loading.value = true
  try {
    // When in a folder and scope is "folder", filter by category; global ignores folder
    const effectiveCategoryId =
      selectedCategoryId.value !== null && searchScope.value === "folder"
        ? selectedCategoryId.value
        : selectedCategoryId.value !== null && searchScope.value === "global"
          ? undefined
          : selectedCategoryId.value ?? undefined
    const { data } = await axios.get("/api/catalog/assets", {
      params: {
        q: keyword.value || undefined,
        asset_type: assetType.value || undefined,
        status: statusFilter.value || undefined,
        category_id: effectiveCategoryId,
      },
    })
    assets.value = data.items
    if (selectedCategoryId.value === null && !keyword.value && !assetType.value) {
      totalCount.value = data.items.length
    }
  } catch {
    ElMessage.error("数据目录加载失败")
  } finally {
    loading.value = false
  }
}

const fetchCategories = async () => {
  try {
    const { data } = await axios.get("/api/catalog/categories")
    categoryTree.value = data
    // Auto-expand all nodes that have children
    const allWithChildren = new Set<number>()
    const walk = (nodes: Category[]) => nodes.forEach(n => {
      if (n.children?.length) { allWithChildren.add(n.id); walk(n.children) }
    })
    walk(data)
    expandedIds.value = allWithChildren
  } catch { /* ignore */ }
}

const onCategoryClick = (node: Category | null) => {
  selectedCategoryId.value = node ? node.id : null
  searchScope.value = "folder"
  fetchAssets()
}

// ── detail drawer ─────────────────────────────────────────────────────────────

const showDetail = async (row: DataAsset) => {
  selectedAsset.value = row
  activeTab.value = "info"
  detailVisible.value = true
  refCount.value = null
  try { const { data } = await axios.get(`/api/catalog/assets/${row.id}/subscription`); subscribed.value = data.subscribed }
  catch { subscribed.value = false }
  try { const { data } = await axios.get(`/api/catalog/assets/${row.id}/references`); refCount.value = data.count }
  catch { /* ignore */ }
}

const onDrawerOpen = () => {}

watch(activeTab, async (tab) => {
  if (!selectedAsset.value) return
  const id = selectedAsset.value.id

  if (tab === "fields" && !fields.value.length) {
    fieldsLoading.value = true
    try { const { data } = await axios.get(`/api/catalog/assets/${id}/fields`); fields.value = data.columns }
    catch { ElMessage.error("字段信息加载失败") }
    finally { fieldsLoading.value = false }
  }
  if (tab === "preview" && !previewColumns.value.length) {
    previewLoading.value = true
    try { const { data } = await axios.get(`/api/catalog/assets/${id}/preview`); previewColumns.value = data.columns; previewRows.value = data.rows }
    catch { ElMessage.error("数据预览加载失败") }
    finally { previewLoading.value = false }
  }
  if (tab === "lineage" && !lineageNodes.value.length) {
    lineageLoading.value = true
    try { const { data } = await axios.get(`/api/catalog/assets/${id}/lineage`); lineageNodes.value = data.nodes; lineageEdges.value = data.edges }
    catch { ElMessage.error("血缘数据加载失败") }
    finally { lineageLoading.value = false }
  }
  if (tab === "refs" && !refs.value.length) {
    refsLoading.value = true
    try { const { data } = await axios.get(`/api/catalog/assets/${id}/references`); refs.value = data.references; refCount.value = data.count }
    catch { ElMessage.error("引用信息加载失败") }
    finally { refsLoading.value = false }
  }
})

watch(selectedAsset, () => {
  fields.value = []; previewColumns.value = []; previewRows.value = []
  lineageNodes.value = []; lineageEdges.value = []; refs.value = []
})

// ── subscription ──────────────────────────────────────────────────────────────

const toggleSubscription = async () => {
  if (!selectedAsset.value) return
  const id = selectedAsset.value.id
  try {
    if (subscribed.value) {
      await axios.delete(`/api/catalog/assets/${id}/subscribe`); subscribed.value = false; ElMessage.success("已取消关注")
    } else {
      await axios.post(`/api/catalog/assets/${id}/subscribe`); subscribed.value = true; ElMessage.success("已关注，资产变更时将通知您")
    }
  } catch { ElMessage.error("操作失败") }
}

// ── folder management ─────────────────────────────────────────────────────────

const openAddCategory = (parentId: number | null) => {
  categoryDialogTitle.value = parentId ? "新建子文件夹" : "新建文件夹"
  categoryDialogName.value = ""
  categoryDialogParentId.value = parentId
  categoryEditId.value = null
  categoryDialogVisible.value = true
}

const openRenameCategory = (cat: Category) => {
  categoryDialogTitle.value = "重命名文件夹"
  categoryDialogName.value = cat.name
  categoryDialogParentId.value = cat.parent_id
  categoryEditId.value = cat.id
  categoryDialogVisible.value = true
}

const submitCategory = async () => {
  if (!categoryDialogName.value.trim()) return
  try {
    if (categoryEditId.value) {
      await axios.put(`/api/catalog/categories/${categoryEditId.value}`, { name: categoryDialogName.value })
    } else {
      await axios.post("/api/catalog/categories", { name: categoryDialogName.value, parent_id: categoryDialogParentId.value })
    }
    await fetchCategories()
    categoryDialogVisible.value = false
  } catch { ElMessage.error("操作失败") }
}

const removeCategory = async (id: number) => {
  await ElMessageBox.confirm("删除后，文件夹内的资产将变为未分类，确认继续？", "删除文件夹", { type: "warning" })
  try {
    await axios.delete(`/api/catalog/categories/${id}`)
    await fetchCategories()
    if (selectedCategoryId.value === id) { selectedCategoryId.value = null; fetchAssets() }
  } catch { ElMessage.error("删除失败") }
}

const assignCategory = async (categoryId: number | null) => {
  if (!selectedAsset.value) return
  try {
    const { data } = await axios.put(`/api/catalog/assets/${selectedAsset.value.id}/category`, { category_id: categoryId })
    selectedAsset.value = data
    ElMessage.success("已更新文件夹")
  } catch { ElMessage.error("更新失败") }
}

// ── lineage ───────────────────────────────────────────────────────────────────

const jumpToAsset = async (assetId: number) => {
  const found = assets.value.find(a => a.id === assetId)
  if (found) await showDetail(found)
}

const addLineage = async () => {
  if (!newLineage.source_id || !newLineage.target_id) { ElMessage.warning("请选择上游和下游资产"); return }
  try {
    await axios.post("/api/catalog/lineage", { source_id: newLineage.source_id, target_id: newLineage.target_id })
    showAddLineage.value = false; newLineage.source_id = null; newLineage.target_id = null
    lineageNodes.value = []; lineageEdges.value = []
    activeTab.value = "info"; setTimeout(() => { activeTab.value = "lineage" }, 50)
    ElMessage.success("血缘关系已添加")
  } catch { ElMessage.error("添加失败") }
}

const noop = () => {}

const dashboardComponentCount = (dashboard: DashboardItem) => dashboard.layout_json?.components?.length || 0

const dashboardComponentStyle = (component: DashboardComponent) => ({
  gridColumn: `span ${Math.min(Math.max(component.w || 6, 3), 12)}`,
  minHeight: `${Math.min(Math.max(component.h || 3, 2), 6) * 96}px`,
})

const chartForDashboardComponent = (component: DashboardComponent): PinnedChartData => {
  const chart = dashboardPreviewCharts.value.find((item) => item.id === component.pinned_chart_id)
  return {
    id: component.pinned_chart_id,
    title: component.title || chart?.title || "未命名图表",
    description: component.description || chart?.description || null,
    chart_type: component.chart_type || chart?.chart_type || "bar",
    sort_order: component.sort_order || chart?.sort_order || "desc",
    columns: chart?.columns || [],
    rows: chart?.rows || [],
  }
}

const fetchDashboardPreviewCharts = async () => {
  if (dashboardPreviewCharts.value.length) return
  try {
    const { data } = await axios.get("/api/pinned-charts/with-data")
    dashboardPreviewCharts.value = data
  } catch {
    dashboardPreviewCharts.value = []
  }
}

const openDashboardPreview = async (id: number) => {
  dashboardPreviewVisible.value = true
  dashboardPreviewLoading.value = true
  try {
    const [{ data }] = await Promise.all([
      axios.get(`/api/dashboards/${id}`),
      fetchDashboardPreviewCharts(),
    ])
    dashboardPreview.value = data
  } catch {
    dashboardPreviewVisible.value = false
    ElMessage.error("看板预览加载失败")
  } finally {
    dashboardPreviewLoading.value = false
  }
}

const openDashboardEditorFromPreview = () => {
  if (!dashboardPreview.value) return
  dashboardPreviewVisible.value = false
  router.push({ path: "/dashboard-center", query: { dashboard_id: dashboardPreview.value.id, mode: "edit" } })
}

onMounted(async () => {
  await fetchCategories()
  await fetchAssets()
  if (!authStore.profile) await authStore.fetchProfile()
})
</script>

<style scoped>
/* ── Layout ── */
.catalog-layout {
  display: flex;
  height: 100%;
  overflow: hidden;
}

/* ── Folder Sidebar ── */
.folder-sidebar {
  width: 196px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  border-right: 1px solid var(--app-border);
  background: var(--app-bg-soft, #f8f9fa);
  overflow-y: auto;
}

.folder-sidebar__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 18px 14px 10px;
}

.folder-sidebar__title {
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: var(--app-text-muted);
}

.folder-sidebar__actions {
  display: flex;
  align-items: center;
  gap: 2px;
}

.icon-btn--sm {
  width: 24px;
  height: 24px;
  font-size: 13px;
}

.icon-btn.is-active {
  color: var(--el-color-primary);
  background: var(--el-color-primary-light-9);
}

.folder-nav {
  flex: 1;
  padding: 0 8px 16px;
  display: flex;
  flex-direction: column;
  gap: 1px;
}

.folder-nav__sep {
  height: 1px;
  background: var(--app-border);
  margin: 6px 4px 8px;
}

.folder-nav__item {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
  padding: 7px 8px;
  border-radius: 8px;
  border: none;
  background: transparent;
  cursor: pointer;
  font-size: 13px;
  color: var(--app-text);
  text-align: left;
  transition: background 0.12s;
  position: relative;
}

.folder-nav__item--all {
  margin-bottom: 2px;
  font-weight: 500;
}

.folder-nav__item--child {
  padding-left: 22px;
}

.folder-tree-group {
  display: contents;
}

.folder-expand-btn {
  flex-shrink: 0;
  width: 16px;
  height: 16px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 10px;
  background: transparent;
  border: none;
  cursor: pointer;
  color: var(--el-text-color-secondary);
  padding: 0;
  margin-right: 2px;
  border-radius: 3px;
  line-height: 1;
}
.folder-expand-btn:hover {
  background: var(--el-color-primary-light-8);
  color: var(--el-color-primary);
}

.folder-expand-placeholder {
  flex-shrink: 0;
  width: 16px;
  margin-right: 2px;
  display: inline-block;
}

.folder-nav__item:hover {
  background: var(--el-color-primary-light-9);
  color: var(--el-color-primary);
}

.folder-nav__item.is-active {
  background: var(--el-color-primary-light-8);
  color: var(--el-color-primary);
  font-weight: 600;
}

.folder-nav__item.is-active::after {
  content: '';
  position: absolute;
  left: 0; top: 6px; bottom: 6px;
  width: 3px;
  border-radius: 0 3px 3px 0;
  background: var(--el-color-primary);
}

.folder-nav__icon {
  flex-shrink: 0;
  font-size: 14px;
  color: inherit;
  opacity: 0.8;
  transition: color 0.12s;
}

.folder-nav__icon--sm { font-size: 12px; opacity: 0.6; }

.folder-icon { color: #f59e0b; opacity: 1; }
.folder-icon--open { color: #d97706; }

.folder-nav__label {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.folder-nav__badge {
  font-size: 11px;
  color: var(--app-text-muted);
  background: var(--app-border);
  padding: 1px 7px;
  border-radius: 20px;
  flex-shrink: 0;
}

.folder-nav__actions {
  display: none;
  align-items: center;
  gap: 0;
  flex-shrink: 0;
}

.folder-nav__item:hover .folder-nav__actions { display: flex; }

.folder-nav__empty {
  font-size: 12px;
  color: var(--app-text-muted);
  text-align: center;
  padding: 20px 0 8px;
}

/* ── Icon button ── */
.icon-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 26px; height: 26px;
  border-radius: 6px;
  border: none;
  background: transparent;
  cursor: pointer;
  color: var(--app-text-muted);
  transition: background 0.12s, color 0.12s;
}

.icon-btn:hover { background: var(--el-fill-color); color: var(--app-text); }
.icon-btn--xs { width: 20px; height: 20px; border-radius: 4px; }
.icon-btn--danger:hover { background: var(--el-color-danger-light-9); color: var(--el-color-danger); }

/* ── Main ── */
.catalog-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  min-width: 0;
}

/* ── Toolbar ── */
.catalog-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 14px 20px 12px;
  border-bottom: 1px solid var(--app-border);
  flex-wrap: wrap;
  flex-shrink: 0;
}

.catalog-toolbar__left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.bc-link { cursor: pointer; }
.bc-link:hover :deep(.el-breadcrumb__inner) { color: var(--el-color-primary) !important; }

.catalog-toolbar__count {
  font-size: 12px;
  color: var(--app-text-muted);
  padding: 2px 8px;
  background: var(--app-border);
  border-radius: 20px;
}

.catalog-toolbar__right {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

/* ── Search bar ── */
/* ── Unified search bar ── */
.search-unified {
  display: inline-flex;
  align-items: center;
  height: 32px;
  border: 1.5px solid var(--app-border);
  border-radius: 8px;
  background: var(--app-surface);
  transition: border-color 0.18s, box-shadow 0.18s;
  overflow: hidden;
}
.search-unified.is-focused {
  border-color: var(--el-color-primary);
  box-shadow: 0 0 0 2px var(--el-color-primary-light-8);
}

.search-scope {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 0 10px 0 10px;
  height: 100%;
  border: none;
  background: var(--el-fill-color-light);
  cursor: pointer;
  font-size: 12px;
  font-weight: 500;
  color: var(--app-text-muted);
  white-space: nowrap;
  transition: background 0.15s, color 0.15s;
  flex-shrink: 0;
  user-select: none;
}
.search-scope:hover {
  background: var(--el-color-primary-light-9);
  color: var(--el-color-primary);
}
.search-scope.is-global {
  color: var(--el-color-primary);
  background: var(--el-color-primary-light-9);
}
.search-scope .el-icon { font-size: 12px; }
.search-scope__caret { font-size: 9px; opacity: 0.5; }

.search-unified__sep {
  width: 1px;
  height: 16px;
  background: var(--app-border);
  flex-shrink: 0;
}

.search-unified__prefix {
  font-size: 14px;
  color: var(--app-text-muted);
  padding: 0 6px 0 8px;
  flex-shrink: 0;
}

.search-unified__input {
  flex: 1;
  width: 180px;
  border: none;
  outline: none;
  background: transparent;
  font-size: 13px;
  color: var(--app-text);
  padding: 0 4px 0 0;
  min-width: 0;
}
.search-unified__input::placeholder { color: var(--app-text-muted); }

.search-unified__clear {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  margin-right: 4px;
  border: none;
  background: transparent;
  cursor: pointer;
  color: var(--app-text-muted);
  border-radius: 4px;
  font-size: 12px;
  flex-shrink: 0;
}
.search-unified__clear:hover {
  background: var(--el-fill-color);
  color: var(--app-text);
}

/* ── Divider ── */
.toolbar-divider {
  width: 1px;
  height: 20px;
  background: var(--app-border);
  flex-shrink: 0;
}

/* ── Type chips ── */
.type-chips {
  display: flex;
  gap: 4px;
  flex-wrap: wrap;
}

.type-chip {
  padding: 3px 10px;
  border-radius: 20px;
  border: 1.5px solid var(--app-border);
  background: transparent;
  font-size: 12px;
  color: var(--app-text-muted);
  cursor: pointer;
  transition: all 0.15s;
  white-space: nowrap;
  font-weight: 500;
}
.type-chip:hover {
  border-color: var(--app-text-muted);
  color: var(--app-text);
}
.type-chip.is-active {
  background: var(--chip-color, var(--el-color-primary));
  border-color: var(--chip-color, var(--el-color-primary));
  color: #fff;
}

/* ── View toggle ── */
.view-toggle {
  display: flex;
  border: 1.5px solid var(--app-border);
  border-radius: 8px;
  overflow: hidden;
}

.view-toggle__btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 30px; height: 28px;
  border: none;
  background: transparent;
  cursor: pointer;
  color: var(--app-text-muted);
  transition: background 0.12s, color 0.12s;
  font-size: 14px;
}
.view-toggle__btn + .view-toggle__btn {
  border-left: 1.5px solid var(--app-border);
}
.view-toggle__btn.is-active {
  background: var(--el-color-primary-light-8);
  color: var(--el-color-primary);
}
.view-toggle__btn:hover:not(.is-active) {
  background: var(--el-fill-color);
  color: var(--app-text);
}

/* ── Card Grid ── */
.card-grid {
  flex: 1;
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: 16px;
  padding: 20px;
  overflow-y: auto;
  align-content: start;
}

.asset-card {
  border: 1px solid var(--app-border);
  border-radius: 12px;
  overflow: hidden;
  cursor: pointer;
  background: var(--app-bg);
  transition: box-shadow 0.18s, transform 0.18s;
  display: flex;
  flex-direction: column;
}

.asset-card:hover {
  box-shadow: 0 8px 24px rgba(0,0,0,0.1);
  transform: translateY(-2px);
}

.asset-card--skeleton {
  min-height: 160px;
  cursor: default;
}
.asset-card--skeleton:hover { transform: none; box-shadow: none; }

.asset-card__header {
  height: 56px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 14px;
  flex-shrink: 0;
}

.asset-card__type-icon {
  color: #fff;
  font-size: 24px;
  line-height: 1;
}

.asset-card__badges { display: flex; align-items: center; gap: 6px; }

.asset-card__status-dot {
  width: 7px; height: 7px;
  border-radius: 50%;
  background: rgba(255,255,255,0.5);
}

.dot--published { background: #4ade80; }
.dot--draft     { background: rgba(255,255,255,0.4); }
.dot--archived  { background: rgba(255,255,255,0.2); }

.cert-badge {
  font-size: 10px;
  background: rgba(255,255,255,0.2);
  color: #fff;
  padding: 2px 7px;
  border-radius: 20px;
  white-space: nowrap;
}

.asset-card__body {
  flex: 1;
  padding: 12px 14px 10px;
  display: flex;
  flex-direction: column;
  gap: 6px;
  min-height: 0;
}

.asset-card__name {
  font-size: 14px;
  font-weight: 600;
  color: var(--app-text);
  margin: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.asset-card__desc {
  font-size: 12px;
  color: var(--app-text-muted);
  margin: 0;
  line-height: 1.5;
  overflow: hidden;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
}

.asset-card__tags { display: flex; flex-wrap: wrap; gap: 4px; }

.asset-tag {
  font-size: 11px;
  padding: 1px 7px;
  border-radius: 20px;
  background: var(--el-fill-color-light);
  color: var(--app-text-muted);
  border: 1px solid var(--app-border);
}

.asset-card__footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 14px;
  border-top: 1px solid var(--app-border);
  flex-shrink: 0;
}

.asset-card__type-label {
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.03em;
}

.asset-card__views {
  display: flex;
  align-items: center;
  gap: 3px;
  font-size: 11px;
  color: var(--app-text-muted);
}

/* ── List view ── */
.asset-table { flex: 1; overflow-y: auto; margin: 0 20px 20px; }
:deep(.asset-table-row) { cursor: pointer; }

.list-name-cell { display: flex; align-items: center; gap: 8px; }
.list-type-dot { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }
.list-name { font-weight: 500; }
.muted-sm { font-size: 12px; color: var(--app-text-muted); }

/* ── Empty state ── */
.catalog-empty {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 10px;
  padding: 60px 20px;
  color: var(--app-text-muted);
}

.catalog-empty__icon { font-size: 56px; opacity: 0.25; }
.catalog-empty__title { font-size: 16px; font-weight: 600; color: var(--app-text); margin: 0; }
.catalog-empty__sub { font-size: 13px; margin: 0; }

/* ── Drawer Hero ── */
.drawer-hero {
  padding: 24px 24px 20px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.drawer-hero__icon {
  color: #fff;
  font-size: 36px;
  line-height: 1;
  margin-bottom: 4px;
}

.drawer-hero__meta { display: flex; flex-direction: column; gap: 2px; }

.drawer-hero__type {
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: rgba(255,255,255,0.7);
}

.drawer-hero__name {
  font-size: 20px;
  font-weight: 700;
  color: #fff;
  margin: 0;
  word-break: break-word;
}

.drawer-hero__actions { display: flex; gap: 8px; margin-top: 12px; flex-wrap: wrap; }

/* ── Status strip ── */
.drawer-strip {
  display: flex;
  gap: 0;
  border-bottom: 1px solid var(--app-border);
  padding: 0;
}

.strip-item {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  padding: 10px 8px;
  border-right: 1px solid var(--app-border);
  min-width: 0;
}

.strip-item:last-child { border-right: none; }
.strip-item--link { cursor: pointer; }
.strip-item--link:hover { background: var(--el-fill-color-light); }

.strip-label {
  font-size: 10px;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: var(--app-text-muted);
  font-weight: 600;
}

.strip-value { font-size: 13px; font-weight: 500; color: var(--app-text); }
.strip-value--primary { color: var(--el-color-primary); }

/* ── Drawer content ── */
.drawer-tabs { padding: 0 20px; }
:deep(.drawer-tabs .el-tabs__header) { margin-bottom: 0; }
:deep(.drawer-tabs .el-tabs__content) { padding-top: 16px; }

.drawer-section { margin-bottom: 16px; }

.drawer-desc {
  font-size: 13px;
  line-height: 1.7;
  color: var(--app-text);
  margin: 0 0 12px;
}

.drawer-tags { display: flex; flex-wrap: wrap; gap: 6px; }

/* ── Trust card ── */
.trust-card {
  border: 1px solid var(--app-border);
  border-radius: 10px;
  padding: 14px;
  background: var(--app-bg-soft, #f8f9fa);
}

.trust-card__head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.trust-card__title { font-size: 13px; font-weight: 600; }
.trust-badges { display: flex; gap: 6px; }

.trust-grid { display: flex; flex-direction: column; gap: 6px; }

.trust-row {
  display: grid;
  grid-template-columns: 72px 1fr;
  gap: 8px;
  font-size: 12px;
}

.trust-row span:first-child { color: var(--app-text-muted); }
.trust-row span:last-child { color: var(--app-text); }
.trust-row--full { grid-template-columns: 72px 1fr; }

/* ── Field list ── */
.field-list { display: flex; flex-direction: column; gap: 0; }

.field-row {
  display: grid;
  grid-template-columns: 1fr 80px 1fr;
  gap: 8px;
  padding: 8px 0;
  border-bottom: 1px solid var(--app-border);
  font-size: 12px;
  align-items: center;
}

.field-name { font-weight: 600; color: var(--app-text); font-family: monospace; }
.field-type {
  font-size: 11px;
  padding: 1px 7px;
  border-radius: 4px;
  background: var(--el-fill-color-light);
  color: var(--app-text-muted);
  text-align: center;
}
.field-desc { color: var(--app-text-muted); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }

/* ── Ref list ── */
.ref-list { display: flex; flex-direction: column; gap: 4px; }

.ref-row {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 10px;
  border-radius: 8px;
  border: 1px solid var(--app-border);
}

.ref-name { flex: 1; font-size: 13px; }

/* ── Lineage ── */
.lineage-flow {
  height: 280px;
  border: 1px solid var(--app-border);
  border-radius: 10px;
  overflow: hidden;
}

.lineage-add { text-align: right; margin-top: 8px; }

.flow-node {
  padding: 8px 14px;
  border-radius: 8px;
  cursor: pointer;
  font-size: 12px;
  text-align: center;
  min-width: 100px;
  border: 2px solid transparent;
  transition: border-color 0.15s, box-shadow 0.15s;
}

.flow-node:hover { border-color: var(--el-color-primary); box-shadow: 0 4px 12px rgba(0,0,0,0.1); }

.flow-node--metric    { background: #eff6ff; }
.flow-node--dataset   { background: #f0fdf4; }
.flow-node--table     { background: #f8fafc; }
.flow-node--dashboard { background: #fffbeb; }
.flow-node--big_screen{ background: #faf5ff; }

.flow-node-type { font-size: 10px; color: var(--app-text-muted); margin-bottom: 2px; }
.flow-node-name { font-weight: 600; color: var(--app-text); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 140px; }

/* ── Edit order dialog ── */
.edit-order-hint {
  font-size: 12px;
  color: var(--app-text-muted);
  margin: 0 0 12px;
}

.edit-order-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.edit-order-item {
  display: flex;
  align-items: center;
  padding: 8px 10px;
  border-radius: 8px;
  border: 1px solid var(--app-border);
  background: var(--app-surface);
  cursor: grab;
  font-size: 13px;
  color: var(--app-text);
  transition: background 0.15s, border-color 0.15s;
  user-select: none;
}
.edit-order-item:active { cursor: grabbing; }
.edit-order-item:hover { background: var(--el-color-primary-light-9); }
.edit-order-item.is-drag-over {
  border-color: var(--el-color-primary);
  background: var(--el-color-primary-light-8);
}

.drag-handle {
  color: var(--app-text-muted);
  margin-right: 8px;
  font-size: 16px;
  cursor: grab;
}

.catalog-dashboard-preview-dialog :deep(.el-dialog__body) {
  padding-top: 0;
}

.dashboard-preview-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  padding-right: 34px;
}

.dashboard-preview-title-group {
  min-width: 0;
}

.dashboard-preview-eyebrow {
  display: block;
  margin-bottom: 4px;
  color: var(--app-primary);
  font-size: 12px;
  font-weight: 700;
}

.dashboard-preview-title-group h3 {
  margin: 0;
  color: var(--app-text);
  font-size: 18px;
  line-height: 1.35;
}

.dashboard-preview-title-group p {
  margin: 4px 0 0;
  color: var(--app-text-muted);
  font-size: 13px;
  line-height: 1.5;
}

.dashboard-preview-actions {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-shrink: 0;
}

.dashboard-preview-body {
  min-height: 360px;
  max-height: calc(90vh - 108px);
  overflow-y: auto;
  padding: 2px 2px 8px;
}

.catalog-preview-grid {
  display: grid;
  grid-template-columns: repeat(12, minmax(0, 1fr));
  gap: 14px;
  align-items: stretch;
}

.catalog-preview-component {
  min-width: 0;
}

.catalog-dashboard-preview-dialog :deep(.card-actions) {
  display: none;
}

@media (max-width: 768px) {
  .catalog-layout {
    flex-direction: column;
    height: auto;
    min-height: 100%;
    overflow: visible;
  }

  .folder-sidebar {
    width: 100%;
    max-height: 190px;
    border-right: 0;
    border-bottom: 1px solid var(--app-border);
  }

  .folder-sidebar__head {
    padding: 12px 14px 8px;
  }

  .folder-nav {
    max-height: 128px;
    overflow-y: auto;
    padding-bottom: 10px;
  }

  .catalog-main {
    min-height: 0;
    overflow: visible;
  }

  .catalog-toolbar {
    align-items: stretch;
    gap: 10px;
    padding: 12px;
  }

  .catalog-toolbar__left,
  .catalog-toolbar__right {
    width: 100%;
    min-width: 0;
    flex-wrap: wrap;
  }

  .search-unified {
    width: 100%;
  }

  .search-unified__input {
    width: auto;
  }

  .toolbar-divider {
    display: none;
  }

  .type-chips {
    width: 100%;
  }

  .view-toggle {
    margin-left: auto;
  }

  .card-grid {
    grid-template-columns: 1fr;
    padding: 12px;
    overflow: visible;
  }

  .asset-table {
    margin: 0 12px 12px;
    overflow-x: auto;
  }

  .dashboard-preview-head {
    flex-direction: column;
    padding-right: 24px;
  }

  .dashboard-preview-actions {
    width: 100%;
    justify-content: space-between;
  }

  .catalog-preview-grid {
    grid-template-columns: 1fr;
  }

  .catalog-preview-component {
    grid-column: 1 / -1 !important;
  }
}
</style>
