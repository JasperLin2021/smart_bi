<template>
  <div class="scheduled-reports">
    <!-- Toolbar -->
    <div class="toolbar">
      <div class="toolbar-left">
        <el-select
          v-model="filterDatasourceId"
          placeholder="全部数据源"
          clearable
          style="width: 200px"
          @change="fetchReports"
        >
          <el-option
            v-for="ds in datasourceStore.datasources"
            :key="ds.id"
            :label="ds.name"
            :value="ds.id"
          />
        </el-select>
      </div>
      <el-button type="primary" :icon="Plus" @click="openCreate">新建定时报告</el-button>
    </div>

    <!-- List -->
    <el-table :data="reports" v-loading="loading" stripe border style="margin-top: 16px">
      <el-table-column prop="name" label="报告名称" min-width="160" />
      <el-table-column label="问题" min-width="220" show-overflow-tooltip>
        <template #default="{ row }">{{ row.question }}</template>
      </el-table-column>
      <el-table-column label="定时规则" min-width="150">
        <template #default="{ row }">
          <el-tag size="small" type="info">{{ row.cron_expression }}</el-tag>
          <div style="font-size:11px; color:#999; margin-top:2px">{{ describeCron(row.cron_expression) }}</div>
        </template>
      </el-table-column>
      <el-table-column label="通知方式" min-width="160">
        <template #default="{ row }">
          <el-tag v-if="row.notify_email" size="small" type="success" style="margin-right:4px">邮件</el-tag>
          <el-tag v-if="row.notify_wechat" size="small" type="warning" style="margin-right:4px">企微</el-tag>
          <el-tag v-if="row.notify_dingtalk" size="small" type="danger">钉钉</el-tag>
          <span v-if="!row.notify_email && !row.notify_wechat && !row.notify_dingtalk" style="color:#999; font-size:12px">未设置</span>
        </template>
      </el-table-column>
      <el-table-column label="最近执行" min-width="150">
        <template #default="{ row }">
          <span v-if="row.last_run_at">{{ formatDate(row.last_run_at) }}</span>
          <span v-else style="color:#999; font-size:12px">从未执行</span>
        </template>
      </el-table-column>
      <el-table-column label="状态" width="90">
        <template #default="{ row }">
          <el-switch
            :model-value="row.is_active"
            @change="(val: boolean) => toggleActive(row, val)"
          />
        </template>
      </el-table-column>
      <el-table-column label="操作" width="170" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" :icon="CaretRight" @click="runNow(row)" :loading="runningId === row.id">立即执行</el-button>
          <el-button link type="primary" :icon="Edit" @click="openEdit(row)">编辑</el-button>
          <el-button link type="danger" :icon="Delete" @click="handleDelete(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <!-- Dialog -->
    <el-dialog
      v-model="dialogVisible"
      :title="editingId ? '编辑定时报告' : '新建定时报告'"
      width="680px"
      destroy-on-close
    >
      <el-form ref="formRef" :model="form" :rules="rules" label-width="110px" label-position="left">
        <el-form-item label="报告名称" prop="name">
          <el-input v-model="form.name" placeholder="例：每日销售汇报" />
        </el-form-item>

        <el-form-item label="数据源" prop="datasource_id">
          <el-select v-model="form.datasource_id" placeholder="选择数据源" style="width: 100%">
            <el-option
              v-for="ds in datasourceStore.datasources"
              :key="ds.id"
              :label="ds.name"
              :value="ds.id"
            />
          </el-select>
        </el-form-item>

        <el-form-item label="查询问题" prop="question">
          <el-input
            v-model="form.question"
            type="textarea"
            :rows="3"
            placeholder="例：统计今日各产线异常数量，按数量降序排列"
          />
        </el-form-item>

        <el-form-item label="Cron 表达式" prop="cron_expression">
          <el-input v-model="form.cron_expression" placeholder="0 9 * * 1-5" style="width: 200px" />
          <span style="margin-left: 10px; color: #666; font-size: 13px">
            {{ describeCron(form.cron_expression) }}
          </span>
        </el-form-item>

        <el-form-item label="">
          <div class="cron-presets">
            <span style="color:#999; font-size:12px; margin-right:8px">快捷选择：</span>
            <el-tag
              v-for="p in cronPresets"
              :key="p.value"
              class="cron-preset-tag"
              size="small"
              effect="plain"
              @click="form.cron_expression = p.value"
            >{{ p.label }}</el-tag>
          </div>
        </el-form-item>

        <el-form-item label="通知方式">
          <div class="notify-group">
            <el-checkbox v-model="form.notify_email">邮件</el-checkbox>
            <el-checkbox v-model="form.notify_wechat">企业微信</el-checkbox>
            <el-checkbox v-model="form.notify_dingtalk">钉钉</el-checkbox>
          </div>
        </el-form-item>

        <el-form-item label="邮件收件人" v-if="form.notify_email">
          <el-input
            v-model="form.email_recipients"
            placeholder="多个地址用英文逗号分隔：a@x.com, b@x.com"
          />
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="handleSave">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from "vue"
import { ElMessage, ElMessageBox, type FormInstance, type FormRules } from "element-plus"
import { Plus, Edit, Delete, CaretRight } from "@element-plus/icons-vue"
import axios from "axios"
import { useDatasourceStore } from "@/store/datasource"

const datasourceStore = useDatasourceStore()

const loading = ref(false)
const saving = ref(false)
const reports = ref<any[]>([])
const filterDatasourceId = ref<number | null>(null)
const dialogVisible = ref(false)
const editingId = ref<number | null>(null)
const formRef = ref<FormInstance>()
const runningId = ref<number | null>(null)

const cronPresets = [
  { label: "工作日早9点", value: "0 9 * * 1-5" },
  { label: "每天早8点", value: "0 8 * * *" },
  { label: "每周一早9点", value: "0 9 * * 1" },
  { label: "每月1号早9点", value: "0 9 1 * *" },
  { label: "每小时", value: "0 * * * *" },
]

const defaultForm = () => ({
  name: "",
  datasource_id: datasourceStore.currentId ?? null as number | null,
  question: "",
  cron_expression: "0 9 * * 1-5",
  notify_email: false,
  notify_wechat: false,
  notify_dingtalk: false,
  email_recipients: "",
  is_active: true,
})

const form = reactive(defaultForm())

const rules: FormRules = {
  name: [{ required: true, message: "请输入报告名称", trigger: "blur" }],
  datasource_id: [{ required: true, message: "请选择数据源", trigger: "change" }],
  question: [{ required: true, message: "请输入查询问题", trigger: "blur" }],
  cron_expression: [{ required: true, message: "请输入 Cron 表达式", trigger: "blur" }],
}

function describeCron(expr: string): string {
  if (!expr) return ""
  const presetMap: Record<string, string> = {
    "0 9 * * 1-5": "工作日每天 09:00",
    "0 8 * * *": "每天 08:00",
    "0 9 * * 1": "每周一 09:00",
    "0 9 1 * *": "每月 1 号 09:00",
    "0 * * * *": "每小时整点",
  }
  return presetMap[expr.trim()] || "自定义"
}

function formatDate(dt: string): string {
  return new Date(dt).toLocaleString("zh-CN", {
    year: "numeric", month: "2-digit", day: "2-digit",
    hour: "2-digit", minute: "2-digit",
  })
}

async function fetchReports() {
  loading.value = true
  try {
    const params = filterDatasourceId.value ? { datasource_id: filterDatasourceId.value } : {}
    const { data } = await axios.get("/api/scheduled-reports", { params })
    reports.value = data.items
  } finally {
    loading.value = false
  }
}

function openCreate() {
  editingId.value = null
  Object.assign(form, defaultForm())
  dialogVisible.value = true
}

function openEdit(row: any) {
  editingId.value = row.id
  Object.assign(form, {
    name: row.name,
    datasource_id: row.datasource_id,
    question: row.question,
    cron_expression: row.cron_expression,
    notify_email: row.notify_email,
    notify_wechat: row.notify_wechat,
    notify_dingtalk: row.notify_dingtalk,
    email_recipients: row.email_recipients || "",
    is_active: row.is_active,
  })
  dialogVisible.value = true
}

async function handleSave() {
  if (!formRef.value) return
  await formRef.value.validate()
  saving.value = true
  try {
    if (editingId.value) {
      await axios.put(`/api/scheduled-reports/${editingId.value}`, { ...form })
      ElMessage.success("已更新")
    } else {
      await axios.post("/api/scheduled-reports", { ...form })
      ElMessage.success("已创建")
    }
    dialogVisible.value = false
    fetchReports()
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || "保存失败")
  } finally {
    saving.value = false
  }
}

async function handleDelete(row: any) {
  await ElMessageBox.confirm(`确认删除报告「${row.name}」？`, "删除确认", { type: "warning" })
  await axios.delete(`/api/scheduled-reports/${row.id}`)
  ElMessage.success("已删除")
  fetchReports()
}

async function toggleActive(row: any, val: boolean) {
  await axios.put(`/api/scheduled-reports/${row.id}`, { is_active: val })
  row.is_active = val
}

async function runNow(row: any) {
  runningId.value = row.id
  try {
    const { data } = await axios.post(`/api/scheduled-reports/${row.id}/run`)
    ElMessage.success(data.message || "已触发执行")
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || "触发失败")
  } finally {
    runningId.value = null
  }
}

onMounted(async () => {
  await datasourceStore.fetchDatasources()
  fetchReports()
})
</script>

<style scoped>
.scheduled-reports {
  padding: 0;
}
.toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.toolbar-left {
  display: flex;
  gap: 12px;
  align-items: center;
}
.notify-group {
  display: flex;
  gap: 20px;
}
.cron-presets {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  align-items: center;
}
.cron-preset-tag {
  cursor: pointer;
}
.cron-preset-tag:hover {
  background: #ecf5ff;
}
</style>
