<template>
  <div class="role-mgmt-page">
    <!-- Header -->
    <div class="page-header">
      <div class="page-header-left">
        <h2>权限管理</h2>
        <span class="page-subtitle">配置角色权限矩阵与用户权限覆盖</span>
      </div>
      <div class="page-header-actions">
        <el-radio-group v-model="activeView" size="small">
          <el-radio-button label="roles">角色模板</el-radio-button>
          <el-radio-button label="users">用户覆盖</el-radio-button>
        </el-radio-group>
      </div>
    </div>

    <!-- Role Template View -->
    <div v-if="activeView === 'roles'" class="view-panel">
      <div class="split-layout">
        <!-- Left: Role list -->
        <div class="role-sidebar">
          <div class="sidebar-title">系统角色</div>
          <div
            v-for="role in roles"
            :key="role.code"
            class="role-item"
            :class="{ active: selectedRole?.code === role.code }"
            @click="selectedRole = role"
          >
            <div class="role-item-icon" :class="`role-icon--${role.code}`">
              {{ roleIcon(role.code) }}
            </div>
            <div class="role-item-body">
              <div class="role-item-name">{{ role.name }}</div>
              <div class="role-item-code">{{ role.code }}</div>
            </div>
            <el-tag size="small" type="info" effect="plain">内置</el-tag>
          </div>
        </div>

        <!-- Right: Permission tree for selected role -->
        <div class="perm-panel" v-if="selectedRole">
          <div class="perm-panel-header">
            <span class="perm-panel-title">
              <span class="role-badge" :class="`role-badge--${selectedRole.code}`">{{ selectedRole.name }}</span>
              权限详情
            </span>
            <el-text type="info" size="small">内置角色权限为系统默认，通过"用户覆盖"可为个别用户定制。</el-text>
          </div>

          <el-tabs v-model="permTab" class="perm-tabs">
            <el-tab-pane label="菜单权限" name="menu">
              <div class="perm-tree">
                <div v-for="group in menuGroups" :key="group.group" class="perm-group">
                  <div class="perm-group-title">{{ group.group }}</div>
                  <div class="perm-items">
                    <div
                      v-for="perm in group.permissions"
                      :key="perm.code"
                      class="perm-item"
                      :class="{ enabled: isEnabled(selectedRole, perm.code, 'menu') }"
                    >
                      <el-icon class="perm-status-icon">
                        <Check v-if="isEnabled(selectedRole, perm.code, 'menu')" />
                        <Close v-else />
                      </el-icon>
                      <span class="perm-name">{{ perm.name }}</span>
                      <code class="perm-code">{{ perm.code }}</code>
                    </div>
                  </div>
                </div>
              </div>
            </el-tab-pane>

            <el-tab-pane label="操作权限" name="action">
              <div class="perm-tree">
                <div v-for="group in actionGroups" :key="group.group" class="perm-group">
                  <div class="perm-group-title">{{ group.group }}</div>
                  <div class="perm-items">
                    <div
                      v-for="perm in group.permissions"
                      :key="perm.code"
                      class="perm-item"
                      :class="{ enabled: isEnabled(selectedRole, perm.code, 'action') }"
                    >
                      <el-icon class="perm-status-icon">
                        <Check v-if="isEnabled(selectedRole, perm.code, 'action')" />
                        <Close v-else />
                      </el-icon>
                      <span class="perm-name">{{ perm.name }}</span>
                      <code class="perm-code">{{ perm.code }}</code>
                    </div>
                  </div>
                </div>
              </div>
            </el-tab-pane>
          </el-tabs>
        </div>

        <div v-else class="perm-empty">
          <el-empty description="请选择左侧角色查看权限" :image-size="80" />
        </div>
      </div>
    </div>

    <!-- User Override View -->
    <div v-if="activeView === 'users'" class="view-panel">
      <div class="user-override-header">
        <el-select v-model="selectedUserId" placeholder="选择用户" filterable clearable style="width: 280px" @change="onUserSelect">
          <el-option-group v-for="dept in usersByDept" :key="dept.department" :label="dept.department">
            <el-option
              v-for="u in dept.users"
              :key="u.id"
              :value="u.id"
              :label="`${u.username}（${u.role_label}）`"
            />
          </el-option-group>
        </el-select>
        <el-text type="info" size="small" style="margin-left: 12px">仅 super_admin 可为超级管理员配置，企业管理员可为本企业用户配置。</el-text>
      </div>

      <div v-if="editingUser" class="user-override-panel">
        <div class="user-override-meta">
          <el-descriptions :column="3" size="small" border>
            <el-descriptions-item label="用户名">{{ editingUser.username }}</el-descriptions-item>
            <el-descriptions-item label="角色">
              <el-tag :type="roleTagType(editingUser.role)" size="small">{{ editingUser.role_label || editingUser.role }}</el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="部门">{{ editingUser.department || '未分配' }}</el-descriptions-item>
          </el-descriptions>
        </div>

        <div class="override-toggle-row">
          <el-switch
            v-model="overrideEnabled"
            active-text="已启用个人权限覆盖"
            inactive-text="使用角色默认权限"
            @change="onOverrideToggle"
          />
          <el-text type="info" size="small" style="margin-left: 16px">
            启用后可为该用户单独调整权限，覆盖其角色模板。
          </el-text>
        </div>

        <el-tabs v-if="overrideEnabled" v-model="overrideTab" class="perm-tabs">
          <el-tab-pane label="菜单权限" name="menu">
            <div class="perm-tree editable">
              <div v-for="group in menuGroups" :key="group.group" class="perm-group">
                <div class="perm-group-title">{{ group.group }}</div>
                <div class="perm-items">
                  <div v-for="perm in group.permissions" :key="perm.code" class="perm-item editable">
                    <el-checkbox
                      v-model="overrideMenuPerms[perm.code]"
                      @change="markDirty"
                    />
                    <span class="perm-name">{{ perm.name }}</span>
                    <code class="perm-code">{{ perm.code }}</code>
                    <el-tag v-if="overrideMenuPerms[perm.code] !== roleBasePerms.menu[perm.code]" size="small" type="warning" effect="plain">已覆盖</el-tag>
                  </div>
                </div>
              </div>
            </div>
          </el-tab-pane>

          <el-tab-pane label="操作权限" name="action">
            <div class="perm-tree editable">
              <div v-for="group in actionGroups" :key="group.group" class="perm-group">
                <div class="perm-group-title">{{ group.group }}</div>
                <div class="perm-items">
                  <div v-for="perm in group.permissions" :key="perm.code" class="perm-item editable">
                    <el-checkbox
                      v-model="overrideActionPerms[perm.code]"
                      @change="markDirty"
                    />
                    <span class="perm-name">{{ perm.name }}</span>
                    <code class="perm-code">{{ perm.code }}</code>
                    <el-tag v-if="overrideActionPerms[perm.code] !== roleBasePerms.action[perm.code]" size="small" type="warning" effect="plain">已覆盖</el-tag>
                  </div>
                </div>
              </div>
            </div>
          </el-tab-pane>
        </el-tabs>

        <div v-if="overrideEnabled && isDirty" class="save-bar">
          <el-button type="primary" :loading="saving" @click="saveOverride">保存权限配置</el-button>
          <el-button @click="resetOverride">重置</el-button>
          <el-text type="warning" size="small">有未保存的更改</el-text>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, onMounted } from "vue"
import axios from "axios"
import { ElMessage } from "element-plus"
import { Check, Close } from "@element-plus/icons-vue"

interface PermItem { code: string; name: string }
interface PermGroup { type: string; group: string; permissions: PermItem[] }
interface RoleTemplate {
  code: string
  name: string
  is_builtin: boolean
  template: { menu_permissions: Record<string, boolean>; action_permissions: Record<string, boolean> }
}
interface UserItem { id: number; username: string; role: string; role_label: string; department: string }
interface DeptGroup { department: string; users: UserItem[] }

const activeView = ref<"roles" | "users">("roles")
const permTab = ref("menu")
const overrideTab = ref("menu")
const roles = ref<RoleTemplate[]>([])
const catalog = ref<PermGroup[]>([])
const selectedRole = ref<RoleTemplate | null>(null)
const usersByDept = ref<DeptGroup[]>([])
const selectedUserId = ref<number | null>(null)
const editingUser = ref<UserItem | null>(null)
const overrideEnabled = ref(false)
const overrideMenuPerms = ref<Record<string, boolean>>({})
const overrideActionPerms = ref<Record<string, boolean>>({})
const roleBasePerms = ref<{ menu: Record<string, boolean>; action: Record<string, boolean> }>({ menu: {}, action: {} })
const isDirty = ref(false)
const saving = ref(false)

const menuGroups = computed(() => catalog.value.filter(g => g.type === "menu"))
const actionGroups = computed(() => catalog.value.filter(g => g.type === "action"))

const isEnabled = (role: RoleTemplate, code: string, type: "menu" | "action") => {
  const key = type === "menu" ? "menu_permissions" : "action_permissions"
  return Boolean(role.template[key]?.[code])
}

const roleIcon = (code: string) => {
  const icons: Record<string, string> = {
    user: "👤", dept_admin: "👥", org_admin: "🏢", super_admin: "⭐"
  }
  return icons[code] || "🔑"
}

const roleTagType = (role: string) => {
  const t: Record<string, string> = { super_admin: "danger", org_admin: "warning", dept_admin: "primary", user: "info" }
  return (t[role] || "info") as "danger" | "warning" | "primary" | "info"
}

const markDirty = () => { isDirty.value = true }

const fetchCatalog = async () => {
  try {
    const { data } = await axios.get("/api/users/permissions/catalog")
    catalog.value = data.catalog
    roles.value = data.roles
    if (roles.value.length) selectedRole.value = roles.value[0]
  } catch {
    ElMessage.error("权限目录加载失败")
  }
}

const fetchUsers = async () => {
  try {
    const { data } = await axios.get("/api/users/assignable")
    usersByDept.value = data
  } catch { /* ignore */ }
}

const onUserSelect = async (id: number | null) => {
  if (!id) { editingUser.value = null; return }
  for (const dept of usersByDept.value) {
    const u = dept.users.find(u => u.id === id)
    if (u) { editingUser.value = u; break }
  }
  // Load user's current permission config
  try {
    const { data } = await axios.get(`/api/users/${id}`)
    overrideEnabled.value = data.permission_override_enabled || false
    // Load role base perms
    const role = roles.value.find(r => r.code === data.role)
    roleBasePerms.value = {
      menu: role?.template.menu_permissions || {},
      action: role?.template.action_permissions || {},
    }
    // Merge role base with user overrides
    overrideMenuPerms.value = { ...roleBasePerms.value.menu, ...(data.menu_permissions || {}) }
    overrideActionPerms.value = { ...roleBasePerms.value.action, ...(data.action_permissions || {}) }
    isDirty.value = false
  } catch { /* ignore */ }
}

const onOverrideToggle = async (val: boolean) => {
  if (!editingUser.value) return
  try {
    await axios.put(`/api/users/${editingUser.value.id}`, {
      permission_override_enabled: val,
    })
    isDirty.value = false
  } catch {
    overrideEnabled.value = !val
    ElMessage.error("保存失败")
  }
}

const saveOverride = async () => {
  if (!editingUser.value) return
  saving.value = true
  try {
    await axios.put(`/api/users/${editingUser.value.id}`, {
      permission_override_enabled: true,
      menu_permissions: overrideMenuPerms.value,
      action_permissions: overrideActionPerms.value,
    })
    isDirty.value = false
    ElMessage.success("权限已保存")
  } catch {
    ElMessage.error("保存失败")
  } finally {
    saving.value = false
  }
}

const resetOverride = async () => {
  if (!editingUser.value) return
  await onUserSelect(editingUser.value.id)
}

onMounted(async () => {
  await Promise.all([fetchCatalog(), fetchUsers()])
})
</script>

<style scoped>
.role-mgmt-page { padding: 0; height: 100%; display: flex; flex-direction: column; gap: 16px; }
.page-header { display: flex; align-items: center; justify-content: space-between; }
.page-header-left h2 { margin: 0 0 2px; font-size: 18px; font-weight: 600; }
.page-subtitle { color: var(--el-text-color-secondary); font-size: 13px; }

.view-panel { flex: 1; background: var(--app-surface); border-radius: 12px; padding: 24px; }
.split-layout { display: flex; gap: 24px; height: 100%; }

.role-sidebar { width: 220px; flex-shrink: 0; display: flex; flex-direction: column; gap: 4px; }
.sidebar-title { font-size: 12px; color: var(--el-text-color-secondary); font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 8px; }

.role-item { display: flex; align-items: center; gap: 10px; padding: 10px 12px; border-radius: 8px; cursor: pointer; transition: background 0.15s; border: 1px solid transparent; }
.role-item:hover { background: var(--el-fill-color-light); }
.role-item.active { background: var(--el-color-primary-light-9); border-color: var(--el-color-primary-light-5); }
.role-item-icon { width: 32px; height: 32px; border-radius: 8px; display: flex; align-items: center; justify-content: center; font-size: 16px; background: var(--el-fill-color); }
.role-icon--super_admin { background: #fef3c7; }
.role-icon--org_admin  { background: #dbeafe; }
.role-icon--dept_admin { background: #d1fae5; }
.role-icon--user       { background: #f3f4f6; }
.role-item-name { font-weight: 500; font-size: 14px; }
.role-item-code { font-size: 11px; color: var(--el-text-color-secondary); font-family: monospace; }

.perm-panel { flex: 1; min-width: 0; }
.perm-panel-header { display: flex; align-items: baseline; justify-content: space-between; margin-bottom: 16px; }
.perm-panel-title { font-size: 15px; font-weight: 600; display: flex; align-items: center; gap: 8px; }
.role-badge { padding: 2px 8px; border-radius: 4px; font-size: 12px; }
.role-badge--super_admin { background: #fef3c7; color: #92400e; }
.role-badge--org_admin   { background: #dbeafe; color: #1e40af; }
.role-badge--dept_admin  { background: #d1fae5; color: #065f46; }
.role-badge--user        { background: #f3f4f6; color: #374151; }

.perm-empty { flex: 1; display: flex; align-items: center; justify-content: center; }
.perm-tabs { margin-top: 8px; }

.perm-tree { display: flex; flex-direction: column; gap: 16px; padding: 8px 0; }
.perm-group { }
.perm-group-title { font-size: 12px; font-weight: 600; color: var(--el-text-color-secondary); text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 6px; padding-left: 4px; border-left: 3px solid var(--el-color-primary-light-5); padding-left: 8px; }
.perm-items { display: flex; flex-direction: column; gap: 2px; }
.perm-item { display: flex; align-items: center; gap: 8px; padding: 5px 8px; border-radius: 6px; font-size: 13px; }
.perm-item.enabled { background: rgba(16, 185, 129, 0.05); }
.perm-item:not(.enabled) { opacity: 0.5; }
.perm-item.editable { opacity: 1; }
.perm-item.editable:not(.enabled) { opacity: 1; }
.perm-status-icon { font-size: 14px; flex-shrink: 0; color: #10b981; }
.perm-item:not(.enabled) .perm-status-icon { color: #d1d5db; }
.perm-name { flex: 1; }
.perm-code { font-size: 11px; color: var(--el-text-color-placeholder); font-family: monospace; }

/* User override view */
.user-override-header { display: flex; align-items: center; margin-bottom: 20px; }
.user-override-meta { margin-bottom: 16px; }
.override-toggle-row { display: flex; align-items: center; margin-bottom: 20px; padding: 12px 16px; background: var(--el-fill-color-light); border-radius: 8px; }
.perm-tree.editable .perm-item { padding: 6px 8px; }
.perm-tree.editable .perm-item:hover { background: var(--el-fill-color-light); }
.save-bar { display: flex; align-items: center; gap: 12px; padding: 12px 0; border-top: 1px solid var(--el-border-color-lighter); margin-top: 16px; }
</style>
