<template>
  <div class="datalink-page">
    <!-- 左侧连接列表 -->
    <aside class="dl-sidebar">
      <div class="dl-sidebar__header">
        <div>
          <span class="dl-sidebar__title">连接器接入</span>
          <small class="dl-sidebar__subtitle">外部业务系统同步入口</small>
        </div>
        <el-button type="primary" size="small" :icon="Plus" @click="openCreateLink">新建连接</el-button>
      </div>
      <div class="dl-sidebar__search">
        <el-input v-model="linkKeyword" :prefix-icon="Search" placeholder="搜索连接" size="small" clearable />
      </div>
      <div class="dl-sidebar__list">
        <div
          v-for="link in filteredLinks"
          :key="link.id"
          class="dl-link-item"
          :class="{ 'is-active': selectedLink?.id === link.id }"
          @click="selectLink(link)"
        >
          <div class="dl-link-item__icon" :class="`icon-${link.connector_type}`">
            {{ connectorLabel(link.connector_type).charAt(0) }}
          </div>
          <div class="dl-link-item__body">
            <div class="dl-link-item__name">{{ link.name }}</div>
            <div class="dl-link-item__meta">
              <span class="dl-link-item__type">{{ connectorLabel(link.connector_type) }}</span>
              <el-tag
                :type="statusTagType(link.status)"
                size="small"
                class="dl-link-item__status"
              >{{ statusLabel(link.status) }}</el-tag>
            </div>
          </div>
          <el-dropdown trigger="click" @command="handleLinkCmd($event, link)" @click.stop>
            <el-icon class="dl-link-item__more"><MoreFilled /></el-icon>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="test">测试连接</el-dropdown-item>
                <el-dropdown-item command="edit">编辑</el-dropdown-item>
                <el-dropdown-item command="delete" divided>删除</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
        <div v-if="!filteredLinks.length" class="dl-empty-hint">暂无连接，点击"新建连接"开始</div>
      </div>
    </aside>

    <!-- 右侧主区域 -->
    <main class="dl-main">
      <!-- 未选中连接 -->
      <div v-if="!selectedLink" class="dl-welcome">
        <el-icon class="dl-welcome__icon"><Connection /></el-icon>
        <div class="dl-welcome__title">选择或新建一个数据连接</div>
        <div class="dl-welcome__desc">
          连接器接入负责把外部系统数据拉进平台，支持 ERP、WMS、CRM、SaaS API 等业务系统同步到目标数据库。
        </div>
        <el-button type="primary" :icon="Plus" @click="openCreateLink">新建连接</el-button>
      </div>

      <template v-else>
        <!-- 连接头部 -->
        <div class="dl-main__header">
          <div class="dl-main__header-left">
            <div class="dl-conn-badge" :class="`badge-${selectedLink.connector_type}`">
              {{ connectorLabel(selectedLink.connector_type) }}
            </div>
            <div>
              <h2 class="dl-main__title">{{ selectedLink.name }}</h2>
              <div class="dl-main__subtitle">
                <el-tag :type="statusTagType(selectedLink.status)" size="small">{{ statusLabel(selectedLink.status) }}</el-tag>
                <span v-if="selectedLink.last_test_at" class="dl-main__last-test">
                  上次测试：{{ fmtDate(selectedLink.last_test_at) }}
                </span>
              </div>
            </div>
          </div>
          <div class="dl-main__header-right">
            <el-button :loading="testing" @click="testLink">测试连接</el-button>
            <el-button type="primary" :icon="Plus" @click="openCreateTask">新建同步任务</el-button>
          </div>
        </div>

        <!-- 任务列表 -->
        <div class="dl-tasks">
          <div class="dl-tasks__toolbar">
            <el-input v-model="taskKeyword" :prefix-icon="Search" placeholder="搜索任务" size="small" clearable style="width:220px" />
            <span class="dl-tasks__count">{{ filteredTasks.length }} 个任务</span>
          </div>

          <el-table :data="filteredTasks" v-loading="tasksLoading" class="dl-table" empty-text="暂无同步任务" row-key="id">
            <el-table-column label="任务名称" prop="name" min-width="160">
              <template #default="{ row }">
                <div class="dl-task-name">{{ row.name }}</div>
                <div class="dl-task-obj">{{ objectLabel(row.source_object) }}</div>
              </template>
            </el-table-column>
            <el-table-column label="同步模式" width="90">
              <template #default="{ row }">
                <el-tag size="small" :type="row.sync_mode === 'incremental' ? 'success' : 'info'">
                  {{ row.sync_mode === 'incremental' ? '增量' : '全量' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="目标表" prop="target_table" min-width="140">
              <template #default="{ row }">
                <el-text type="info" size="small">{{ row.target_table || '(自动)' }}</el-text>
              </template>
            </el-table-column>
            <el-table-column label="调度周期" min-width="120">
              <template #default="{ row }">
                <el-text size="small">{{ describeCron(row.cron_expression) }}</el-text>
              </template>
            </el-table-column>
            <el-table-column label="上次执行" min-width="160">
              <template #default="{ row }">
                <div v-if="row.last_run_at">
                  <el-tag :type="runStatusType(row.last_run_status)" size="small">
                    {{ runStatusLabel(row.last_run_status) }}
                  </el-tag>
                  <div class="dl-task-runmeta">
                    {{ fmtDate(row.last_run_at) }}
                    <span v-if="row.last_run_records != null"> · {{ row.last_run_records }} 条</span>
                  </div>
                </div>
                <el-text v-else type="info" size="small">从未执行</el-text>
              </template>
            </el-table-column>
            <el-table-column label="状态" width="72">
              <template #default="{ row }">
                <el-switch
                  :model-value="row.is_active"
                  @change="toggleTask(row, $event)"
                  size="small"
                />
              </template>
            </el-table-column>
            <el-table-column label="操作" width="140" fixed="right">
              <template #default="{ row }">
                <el-button
                  size="small"
                  :loading="runningTaskId === row.id"
                  @click="runTask(row)"
                >立即同步</el-button>
                <el-dropdown trigger="click" @command="handleTaskCmd($event, row)">
                  <el-button size="small" :icon="MoreFilled" style="margin-left:4px" />
                  <template #dropdown>
                    <el-dropdown-menu>
                      <el-dropdown-item command="logs">执行历史</el-dropdown-item>
                      <el-dropdown-item command="edit">编辑</el-dropdown-item>
                      <el-dropdown-item command="delete" divided>删除</el-dropdown-item>
                    </el-dropdown-menu>
                  </template>
                </el-dropdown>
              </template>
            </el-table-column>
          </el-table>
        </div>
      </template>
    </main>

    <!-- ── 新建/编辑连接 Dialog ── -->
    <el-dialog
      v-model="linkDialogVisible"
      :title="editingLink ? '编辑连接' : '新建数据连接'"
      width="560px"
      destroy-on-close
    >
      <el-form ref="linkFormRef" :model="linkForm" :rules="linkRules" label-position="top">
        <el-form-item label="连接名称" prop="name">
          <el-input v-model="linkForm.name" placeholder="例：聚水潭-主账号" />
        </el-form-item>
        <el-form-item label="连接器类型" prop="connector_type">
          <el-select v-model="linkForm.connector_type" placeholder="选择系统类型" style="width:100%" @change="onConnectorChange">
            <el-option v-for="c in connectorTypes" :key="c.type" :label="c.label" :value="c.type" />
          </el-select>
        </el-form-item>

        <!-- 聚水潭凭据 -->
        <template v-if="linkForm.connector_type === 'jushuitan'">
          <el-form-item label="App Key" prop="config.app_key">
            <el-input v-model="linkForm.config.app_key" placeholder="聚水潭开放平台 App Key" />
          </el-form-item>
          <el-form-item label="App Secret" prop="config.app_secret">
            <el-input v-model="linkForm.config.app_secret" type="password" show-password placeholder="App Secret" />
          </el-form-item>
          <el-form-item label="Access Token" prop="config.access_token">
            <el-input v-model="linkForm.config.access_token" type="password" show-password placeholder="授权 Access Token" />
          </el-form-item>
        </template>

        <!-- 易仓凭据 -->
        <template v-if="linkForm.connector_type === 'yicang'">
          <el-form-item label="Client ID" prop="config.client_id">
            <el-input v-model="linkForm.config.client_id" placeholder="易仓开放平台 Client ID" />
          </el-form-item>
          <el-form-item label="Client Secret" prop="config.client_secret">
            <el-input v-model="linkForm.config.client_secret" type="password" show-password placeholder="Client Secret" />
          </el-form-item>
        </template>

        <!-- 纷享销客凭据 -->
        <template v-if="linkForm.connector_type === 'fenxiang'">
          <el-form-item label="Corp ID" prop="config.corp_id">
            <el-input v-model="linkForm.config.corp_id" placeholder="企业 Corp ID" />
          </el-form-item>
          <el-form-item label="App ID" prop="config.app_id">
            <el-input v-model="linkForm.config.app_id" placeholder="应用 App ID" />
          </el-form-item>
          <el-form-item label="App Secret" prop="config.app_secret">
            <el-input v-model="linkForm.config.app_secret" type="password" show-password placeholder="App Secret" />
          </el-form-item>
          <el-form-item label="Permanent Code" prop="config.permanent_code">
            <el-input v-model="linkForm.config.permanent_code" type="password" show-password placeholder="永久授权码" />
          </el-form-item>
        </template>
      </el-form>
      <template #footer>
        <el-button @click="linkDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="savingLink" @click="saveLink">保存</el-button>
      </template>
    </el-dialog>

    <!-- ── 新建/编辑任务 Dialog ── -->
    <el-dialog
      v-model="taskDialogVisible"
      :title="editingTask ? '编辑同步任务' : '新建同步任务'"
      width="640px"
      destroy-on-close
    >
      <el-form ref="taskFormRef" :model="taskForm" :rules="taskRules" label-position="top">
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="任务名称" prop="name">
              <el-input v-model="taskForm.name" placeholder="例：同步订单数据" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="同步对象" prop="source_object">
              <el-select v-model="taskForm.source_object" placeholder="选择数据对象" style="width:100%" @change="onObjectChange">
                <el-option
                  v-for="obj in availableObjects"
                  :key="obj.name"
                  :label="obj.label"
                  :value="obj.name"
                >
                  <span>{{ obj.label }}</span>
                  <el-text type="info" size="small" style="margin-left:6px">{{ obj.description }}</el-text>
                </el-option>
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>

        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="同步模式">
              <el-radio-group v-model="taskForm.sync_mode" @change="onSyncModeChange">
                <el-radio value="full">全量</el-radio>
                <el-radio
                  value="incremental"
                  :disabled="!selectedObjectMeta?.supports_incremental"
                >增量</el-radio>
              </el-radio-group>
              <el-text v-if="!selectedObjectMeta?.supports_incremental" type="warning" size="small">
                该对象不支持增量同步
              </el-text>
            </el-form-item>
          </el-col>
          <el-col v-if="taskForm.sync_mode === 'incremental'" :span="12">
            <el-form-item label="增量字段">
              <el-input v-model="taskForm.incremental_field" :placeholder="selectedObjectMeta?.incremental_field || ''" disabled />
            </el-form-item>
          </el-col>
        </el-row>

        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="目标数据源">
              <el-select v-model="taskForm.target_datasource_id" placeholder="选择写入数据源" clearable style="width:100%">
                <el-option v-for="ds in datasources" :key="ds.id" :label="ds.name" :value="ds.id" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="目标表名">
              <el-input v-model="taskForm.target_table" :placeholder="autoTableName" />
            </el-form-item>
          </el-col>
        </el-row>

        <el-form-item label="调度周期">
          <el-select v-model="taskForm.cron_expression" style="width:100%">
            <el-option label="每天凌晨 2 点" value="0 2 * * *" />
            <el-option label="每天早上 8 点" value="0 8 * * *" />
            <el-option label="每 6 小时" value="0 */6 * * *" />
            <el-option label="每小时" value="0 * * * *" />
            <el-option label="每周一早 9 点" value="0 9 * * 1" />
          </el-select>
        </el-form-item>

        <!-- 字段映射（若已选对象） -->
        <el-form-item v-if="selectedObjectMeta?.fields?.length" label="字段映射">
          <div class="dl-field-table">
            <div class="dl-field-table__head">
              <span>来源字段</span>
              <span>目标字段名</span>
              <span>类型</span>
            </div>
            <div v-for="(row, i) in taskForm.field_mapping" :key="i" class="dl-field-table__row">
              <span class="dl-field-src">{{ row.src_label }} <el-text type="info" size="small">({{ row.src }})</el-text></span>
              <el-input v-model="row.dst" size="small" />
              <el-tag size="small" class="dl-field-type">{{ row.type }}</el-tag>
            </div>
          </div>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="taskDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="savingTask" @click="saveTask">保存</el-button>
      </template>
    </el-dialog>

    <!-- ── 执行历史 Drawer ── -->
    <el-drawer v-model="logsDrawer" title="执行历史" size="600px" destroy-on-close>
      <div v-loading="logsLoading">
        <div v-for="log in taskLogs" :key="log.id" class="dl-log-item">
          <div class="dl-log-item__header">
            <el-tag :type="runStatusType(log.status)" size="small">{{ runStatusLabel(log.status) }}</el-tag>
            <span class="dl-log-item__time">{{ fmtDate(log.started_at) }}</span>
            <span v-if="log.finished_at" class="dl-log-item__duration">
              耗时 {{ elapsedSec(log.started_at, log.finished_at) }}s
            </span>
          </div>
          <div class="dl-log-item__stats">
            <span>读取 <strong>{{ log.records_read }}</strong></span>
            <span>写入 <strong>{{ log.records_written }}</strong></span>
            <span v-if="log.records_failed">失败 <strong>{{ log.records_failed }}</strong></span>
          </div>
          <el-alert v-if="log.error_message" :title="log.error_message" type="error" :closable="false" class="dl-log-item__err" />
        </div>
        <el-empty v-if="!taskLogs.length && !logsLoading" description="暂无执行记录" />
      </div>
    </el-drawer>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue"
import { ElMessage, ElMessageBox, type FormInstance } from "element-plus"
import { Connection, Plus, Search, MoreFilled } from "@element-plus/icons-vue"
import axios from "axios"

// ── state ──────────────────────────────────────────────────────────────────
const links = ref<any[]>([])
const selectedLink = ref<any>(null)
const linkKeyword = ref("")
const testing = ref(false)

const tasks = ref<any[]>([])
const tasksLoading = ref(false)
const taskKeyword = ref("")
const runningTaskId = ref<number | null>(null)

const connectorTypes = ref<any[]>([])
const availableObjects = ref<any[]>([])
const datasources = ref<any[]>([])

// dialogs
const linkDialogVisible = ref(false)
const editingLink = ref<any>(null)
const savingLink = ref(false)
const linkFormRef = ref<FormInstance>()

const taskDialogVisible = ref(false)
const editingTask = ref<any>(null)
const savingTask = ref(false)
const taskFormRef = ref<FormInstance>()

const logsDrawer = ref(false)
const logsLoading = ref(false)
const taskLogs = ref<any[]>([])

// ── forms ──────────────────────────────────────────────────────────────────
const defaultLinkForm = () => ({
  name: "",
  connector_type: "",
  config: {} as Record<string, string>,
})
const linkForm = reactive(defaultLinkForm())
const linkRules = {
  name: [{ required: true, message: "请输入连接名称", trigger: "blur" }],
  connector_type: [{ required: true, message: "请选择连接器", trigger: "change" }],
}

const defaultTaskForm = () => ({
  name: "",
  source_object: "",
  sync_mode: "full",
  incremental_field: "",
  target_datasource_id: null as number | null,
  target_table: "",
  cron_expression: "0 2 * * *",
  field_mapping: [] as Array<{ src: string; src_label: string; dst: string; type: string }>,
})
const taskForm = reactive(defaultTaskForm())
const taskRules = {
  name: [{ required: true, message: "请输入任务名称", trigger: "blur" }],
  source_object: [{ required: true, message: "请选择同步对象", trigger: "change" }],
}

// ── computed ───────────────────────────────────────────────────────────────
const filteredLinks = computed(() => {
  const kw = linkKeyword.value.toLowerCase()
  return links.value.filter(l =>
    !kw || l.name.toLowerCase().includes(kw) || connectorLabel(l.connector_type).includes(kw)
  )
})

const filteredTasks = computed(() => {
  const kw = taskKeyword.value.toLowerCase()
  return tasks.value.filter(t =>
    !kw || t.name.toLowerCase().includes(kw) || t.source_object.toLowerCase().includes(kw)
  )
})

const selectedObjectMeta = computed(() =>
  availableObjects.value.find(o => o.name === taskForm.source_object) || null
)

const autoTableName = computed(() => {
  if (!selectedLink.value || !taskForm.source_object) return "自动生成"
  return `dl_${selectedLink.value.connector_type}_${taskForm.source_object}`
})

// ── labels & utils ─────────────────────────────────────────────────────────
function connectorLabel(type: string) {
  return connectorTypes.value.find(c => c.type === type)?.label || type
}

function objectLabel(name: string) {
  return availableObjects.value.find(o => o.name === name)?.label || name
}

function statusLabel(s: string) {
  return { active: "已连接", inactive: "未连接", error: "连接失败" }[s] ?? s
}

function statusTagType(s: string) {
  return { active: "success", inactive: "info", error: "danger" }[s] ?? "info"
}

function runStatusLabel(s: string) {
  return ({ success: "成功", error: "失败", running: "同步中" }[s] ?? s) || "—"
}

function runStatusType(s: string) {
  return { success: "success", error: "danger", running: "warning" }[s] ?? "info"
}

function fmtDate(d: string) {
  return d ? new Date(d).toLocaleString("zh-CN", { month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit" }) : ""
}

function elapsedSec(start: string, end: string) {
  return Math.round((new Date(end).getTime() - new Date(start).getTime()) / 1000)
}

function describeCron(expr: string) {
  const map: Record<string, string> = {
    "0 2 * * *": "每天 02:00",
    "0 8 * * *": "每天 08:00",
    "0 */6 * * *": "每6小时",
    "0 * * * *": "每小时",
    "0 9 * * 1": "每周一 09:00",
  }
  return map[expr?.trim()] || expr || "—"
}

// ── data fetching ──────────────────────────────────────────────────────────
async function fetchLinks() {
  const { data } = await axios.get("/api/data-links")
  links.value = data
}

async function selectLink(link: any) {
  selectedLink.value = link
  taskKeyword.value = ""
  await fetchTasks()
  await fetchObjects()
}

async function fetchTasks() {
  if (!selectedLink.value) return
  tasksLoading.value = true
  try {
    const { data } = await axios.get(`/api/data-links/${selectedLink.value.id}/tasks`)
    tasks.value = data
  } finally {
    tasksLoading.value = false
  }
}

async function fetchObjects() {
  if (!selectedLink.value) return
  try {
    const { data } = await axios.get(`/api/data-links/${selectedLink.value.id}/objects`)
    availableObjects.value = data
  } catch {
    availableObjects.value = []
  }
}

async function fetchDatasources() {
  try {
    const { data } = await axios.get("/api/datasources")
    datasources.value = (data.items || data).filter((d: any) => d.source_type !== "excel")
  } catch { /* ignore */ }
}

async function fetchConnectorTypes() {
  try {
    const { data } = await axios.get("/api/data-links/connector-types")
    connectorTypes.value = data
  } catch { /* ignore */ }
}

// ── connection actions ─────────────────────────────────────────────────────
function openCreateLink() {
  editingLink.value = null
  Object.assign(linkForm, defaultLinkForm())
  linkDialogVisible.value = true
}

function openEditLink(link: any) {
  editingLink.value = link
  Object.assign(linkForm, {
    name: link.name,
    connector_type: link.connector_type,
    config: { ...(link.config_json || {}) },
  })
  linkDialogVisible.value = true
}

function onConnectorChange() {
  linkForm.config = {}
}

async function saveLink() {
  await linkFormRef.value?.validate()
  savingLink.value = true
  try {
    const payload = { name: linkForm.name, connector_type: linkForm.connector_type, config_json: linkForm.config }
    if (editingLink.value) {
      const { data } = await axios.put(`/api/data-links/${editingLink.value.id}`, payload)
      const idx = links.value.findIndex(l => l.id === editingLink.value.id)
      if (idx >= 0) links.value[idx] = data
      if (selectedLink.value?.id === data.id) selectedLink.value = data
    } else {
      const { data } = await axios.post("/api/data-links", payload)
      links.value.unshift(data)
    }
    ElMessage.success("保存成功")
    linkDialogVisible.value = false
  } finally {
    savingLink.value = false
  }
}

async function testLink() {
  testing.value = true
  try {
    const { data } = await axios.post(`/api/data-links/${selectedLink.value.id}/test`)
    if (data.ok) {
      ElMessage.success(`连接成功：${data.message}`)
      selectedLink.value.status = "active"
    } else {
      ElMessage.error(`连接失败：${data.message}`)
      selectedLink.value.status = "error"
    }
    // Refresh link in list
    const idx = links.value.findIndex(l => l.id === selectedLink.value.id)
    if (idx >= 0) {
      links.value[idx].status = selectedLink.value.status
      links.value[idx].last_test_at = new Date().toISOString()
    }
  } finally {
    testing.value = false
  }
}

async function handleLinkCmd(cmd: string, link: any) {
  if (cmd === "test") {
    selectedLink.value = link
    await testLink()
  } else if (cmd === "edit") {
    openEditLink(link)
  } else if (cmd === "delete") {
    await ElMessageBox.confirm(`确认删除连接「${link.name}」？其下所有任务也将删除。`, "删除确认", { type: "warning" })
    await axios.delete(`/api/data-links/${link.id}`)
    links.value = links.value.filter(l => l.id !== link.id)
    if (selectedLink.value?.id === link.id) selectedLink.value = null
    ElMessage.success("已删除")
  }
}

// ── task actions ───────────────────────────────────────────────────────────
function openCreateTask() {
  editingTask.value = null
  Object.assign(taskForm, defaultTaskForm())
  taskDialogVisible.value = true
}

function openEditTask(task: any) {
  editingTask.value = task
  const mapping = (task.field_mapping_json || []).map((m: any) => {
    const obj = availableObjects.value.find(o => o.name === task.source_object)
    const f = obj?.fields?.find((f: any) => f.name === m.src)
    return { src: m.src, src_label: f?.label || m.src, dst: m.dst, type: m.type || "string" }
  })
  Object.assign(taskForm, {
    name: task.name,
    source_object: task.source_object,
    sync_mode: task.sync_mode,
    incremental_field: task.incremental_field || "",
    target_datasource_id: task.target_datasource_id,
    target_table: task.target_table || "",
    cron_expression: task.cron_expression,
    field_mapping: mapping,
  })
  taskDialogVisible.value = true
}

function onObjectChange(name: string) {
  const meta = availableObjects.value.find(o => o.name === name)
  if (!meta) return
  taskForm.incremental_field = meta.incremental_field || ""
  if (taskForm.sync_mode === "incremental" && !meta.supports_incremental) {
    taskForm.sync_mode = "full"
  }
  // Auto-populate field mapping from object schema
  taskForm.field_mapping = (meta.fields || []).map((f: any) => ({
    src: f.name,
    src_label: f.label,
    dst: f.name.toLowerCase(),
    type: f.type,
  }))
}

function onSyncModeChange() {
  if (taskForm.sync_mode === "incremental") {
    taskForm.incremental_field = selectedObjectMeta.value?.incremental_field || ""
  }
}

async function saveTask() {
  await taskFormRef.value?.validate()
  savingTask.value = true
  try {
    const payload = {
      link_id: selectedLink.value.id,
      name: taskForm.name,
      source_object: taskForm.source_object,
      sync_mode: taskForm.sync_mode,
      incremental_field: taskForm.incremental_field || null,
      target_datasource_id: taskForm.target_datasource_id,
      target_table: taskForm.target_table || null,
      cron_expression: taskForm.cron_expression,
      is_active: true,
      field_mapping_json: taskForm.field_mapping.map(m => ({ src: m.src, dst: m.dst, type: m.type })),
    }
    if (editingTask.value) {
      const { data } = await axios.put(`/api/data-links/tasks/${editingTask.value.id}`, payload)
      const idx = tasks.value.findIndex(t => t.id === editingTask.value.id)
      if (idx >= 0) tasks.value[idx] = data
    } else {
      const { data } = await axios.post(`/api/data-links/${selectedLink.value.id}/tasks`, payload)
      tasks.value.unshift(data)
    }
    ElMessage.success("保存成功")
    taskDialogVisible.value = false
  } finally {
    savingTask.value = false
  }
}

async function runTask(task: any) {
  runningTaskId.value = task.id
  try {
    await axios.post(`/api/data-links/tasks/${task.id}/run`)
    ElMessage.success("同步任务已启动")
    setTimeout(fetchTasks, 2000)
  } finally {
    runningTaskId.value = null
  }
}

async function toggleTask(task: any, val: boolean) {
  await axios.put(`/api/data-links/tasks/${task.id}`, { is_active: val })
  task.is_active = val
}

async function openLogs(task: any) {
  logsDrawer.value = true
  logsLoading.value = true
  try {
    const { data } = await axios.get(`/api/data-links/tasks/${task.id}/logs`)
    taskLogs.value = data
  } finally {
    logsLoading.value = false
  }
}

async function handleTaskCmd(cmd: string, task: any) {
  if (cmd === "logs") {
    await openLogs(task)
  } else if (cmd === "edit") {
    openEditTask(task)
  } else if (cmd === "delete") {
    await ElMessageBox.confirm(`确认删除任务「${task.name}」？`, "删除确认", { type: "warning" })
    await axios.delete(`/api/data-links/tasks/${task.id}`)
    tasks.value = tasks.value.filter(t => t.id !== task.id)
    ElMessage.success("已删除")
  }
}

// ── lifecycle ─────────────────────────────────────────────────────────────
onMounted(() => {
  fetchLinks()
  fetchConnectorTypes()
  fetchDatasources()
})
</script>

<style scoped>
.datalink-page {
  display: flex;
  height: calc(100vh - 60px);
  background: var(--el-bg-color-page, #f5f7fa);
  overflow: hidden;
}

/* ── Sidebar ── */
.dl-sidebar {
  width: 260px;
  min-width: 220px;
  background: #fff;
  border-right: 1px solid var(--el-border-color-lighter);
  display: flex;
  flex-direction: column;
  flex-shrink: 0;
}
.dl-sidebar__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  padding: 16px 14px 10px;
}
.dl-sidebar__title { display: block; font-size: 14px; font-weight: 600; color: #1e293b; }
.dl-sidebar__subtitle { display: block; margin-top: 2px; color: #64748b; font-size: 12px; line-height: 1.2; }
.dl-sidebar__search { padding: 0 10px 10px; }
.dl-sidebar__list { flex: 1; overflow-y: auto; padding: 0 6px 12px; }

.dl-link-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 10px;
  border-radius: 8px;
  cursor: pointer;
  transition: background .15s;
  position: relative;
}
.dl-link-item:hover { background: #f1f5f9; }
.dl-link-item.is-active { background: #eff6ff; }
.dl-link-item__icon {
  width: 36px; height: 36px; border-radius: 8px;
  display: flex; align-items: center; justify-content: center;
  font-size: 16px; font-weight: 700; color: #fff; flex-shrink: 0;
}
.icon-jushuitan { background: linear-gradient(135deg,#f59e0b,#d97706); }
.icon-yicang    { background: linear-gradient(135deg,#3b82f6,#1d4ed8); }
.icon-fenxiang  { background: linear-gradient(135deg,#10b981,#059669); }

.dl-link-item__body { flex: 1; min-width: 0; }
.dl-link-item__name { font-size: 13px; font-weight: 500; color: #1e293b; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.dl-link-item__meta { display: flex; align-items: center; gap: 6px; margin-top: 2px; }
.dl-link-item__type { font-size: 11px; color: #94a3b8; }
.dl-link-item__more { color: #94a3b8; font-size: 16px; cursor: pointer; opacity: 0; transition: opacity .15s; }
.dl-link-item:hover .dl-link-item__more { opacity: 1; }
.dl-empty-hint { text-align: center; color: #94a3b8; font-size: 13px; padding: 24px 0; }

/* ── Main ── */
.dl-main {
  flex: 1;
  overflow: auto;
  display: flex;
  flex-direction: column;
}
.dl-welcome {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 16px;
  color: #64748b;
}
.dl-welcome__icon {
  width: 64px;
  height: 64px;
  border-radius: 16px;
  background: rgba(15, 118, 110, 0.08);
  color: var(--app-primary);
  font-size: 32px;
}
.dl-welcome__title { font-size: 20px; font-weight: 600; color: #1e293b; }
.dl-welcome__desc { font-size: 14px; max-width: 380px; text-align: center; }

.dl-main__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 20px 24px 16px;
  background: #fff;
  border-bottom: 1px solid var(--el-border-color-lighter);
  flex-shrink: 0;
}
.dl-main__header-left { display: flex; align-items: center; gap: 14px; }
.dl-conn-badge {
  width: 44px; height: 44px; border-radius: 10px;
  display: flex; align-items: center; justify-content: center;
  font-size: 13px; font-weight: 700; color: #fff;
}
.badge-jushuitan { background: linear-gradient(135deg,#f59e0b,#d97706); }
.badge-yicang    { background: linear-gradient(135deg,#3b82f6,#1d4ed8); }
.badge-fenxiang  { background: linear-gradient(135deg,#10b981,#059669); }

.dl-main__title { font-size: 18px; font-weight: 600; color: #1e293b; margin: 0 0 4px; }
.dl-main__subtitle { display: flex; align-items: center; gap: 8px; }
.dl-main__last-test { font-size: 12px; color: #94a3b8; }
.dl-main__header-right { display: flex; gap: 8px; }

/* ── Tasks ── */
.dl-tasks { padding: 16px 24px; }
.dl-tasks__toolbar { display: flex; align-items: center; gap: 12px; margin-bottom: 12px; }
.dl-tasks__count { font-size: 13px; color: #94a3b8; margin-left: auto; }
.dl-table { border-radius: 8px; }
.dl-task-name { font-size: 13px; font-weight: 500; color: #1e293b; }
.dl-task-obj { font-size: 12px; color: #94a3b8; margin-top: 2px; }
.dl-task-runmeta { font-size: 11px; color: #94a3b8; margin-top: 2px; }

/* ── Field mapping table ── */
.dl-field-table { border: 1px solid var(--el-border-color-lighter); border-radius: 6px; overflow: hidden; font-size: 13px; }
.dl-field-table__head {
  display: grid; grid-template-columns: 2fr 2fr 1fr;
  background: #f8fafc; padding: 6px 10px;
  font-weight: 600; color: #64748b; font-size: 12px;
}
.dl-field-table__row {
  display: grid; grid-template-columns: 2fr 2fr 1fr;
  align-items: center;
  padding: 5px 10px; border-top: 1px solid var(--el-border-color-lighter);
  gap: 8px;
}
.dl-field-src { font-size: 12px; color: #374151; }
.dl-field-type { align-self: center; }

/* ── Logs ── */
.dl-log-item {
  background: #f8fafc; border-radius: 8px; padding: 12px 14px; margin-bottom: 10px;
  border: 1px solid var(--el-border-color-lighter);
}
.dl-log-item__header { display: flex; align-items: center; gap: 8px; margin-bottom: 6px; }
.dl-log-item__time { font-size: 12px; color: #64748b; }
.dl-log-item__duration { font-size: 12px; color: #94a3b8; margin-left: auto; }
.dl-log-item__stats { display: flex; gap: 16px; font-size: 13px; color: #374151; }
.dl-log-item__err { margin-top: 8px; }
</style>
