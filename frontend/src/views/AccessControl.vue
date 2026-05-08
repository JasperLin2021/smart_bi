<template>
  <div class="ac-page">
    <!-- ── Top Tab Bar ─────────────────────────────────────────────── -->
    <div class="ac-tabbar">
      <button
        v-for="t in visibleTabs"
        :key="t.key"
        class="ac-tab"
        :class="{ active: activeTab === t.key }"
        @click="activeTab = t.key"
      >
        <el-icon><component :is="t.icon" /></el-icon>
        {{ t.label }}
        <span v-if="t.badge" class="tab-badge">{{ t.badge }}</span>
      </button>
    </div>

    <!-- ══════════════════════════════════════════════════════════════ -->
    <!--  TAB: USERS                                                   -->
    <!-- ══════════════════════════════════════════════════════════════ -->
    <div v-show="activeTab === 'users'" class="tab-content">
      <!-- Stats -->
      <div class="stats-row">
        <div class="stat-card">
          <div class="stat-icon" style="background: linear-gradient(135deg,#0f766e,#2563eb)">
            <el-icon :size="20"><User /></el-icon>
          </div>
          <div>
            <div class="stat-val">{{ users.length }}</div>
            <div class="stat-lbl">总用户</div>
          </div>
        </div>
        <div class="stat-card">
          <div class="stat-icon" style="background: linear-gradient(135deg,#f59e0b,#d97706)">
            <el-icon :size="20"><UserFilled /></el-icon>
          </div>
          <div>
            <div class="stat-val">{{ adminCount }}</div>
            <div class="stat-lbl">管理员</div>
          </div>
        </div>
        <div class="stat-card">
          <div class="stat-icon" style="background: linear-gradient(135deg,#8b5cf6,#7c3aed)">
            <el-icon :size="20"><Grid /></el-icon>
          </div>
          <div>
            <div class="stat-val">{{ deptCount }}</div>
            <div class="stat-lbl">部门</div>
          </div>
        </div>
        <div class="stat-card">
          <div class="stat-icon" style="background: linear-gradient(135deg,#10b981,#059669)">
            <el-icon :size="20"><OfficeBuilding /></el-icon>
          </div>
          <div>
            <div class="stat-val">{{ organizations.length }}</div>
            <div class="stat-lbl">企业</div>
          </div>
        </div>
      </div>

      <!-- Toolbar -->
      <div class="toolbar">
        <div class="toolbar-left">
          <el-input
            v-model="userSearch"
            placeholder="搜索用户名..."
            prefix-icon="Search"
            clearable
            style="width: 220px"
          />
          <el-select v-model="roleFilter" placeholder="角色" clearable style="width: 140px">
            <el-option label="普通用户" value="user" />
            <el-option label="部门管理员" value="dept_admin" />
            <el-option label="企业管理员" value="org_admin" />
            <el-option label="超级管理员" value="super_admin" />
          </el-select>
          <el-select v-model="deptFilter" placeholder="部门" clearable style="width: 160px">
            <el-option v-for="d in allDepts" :key="d" :label="d" :value="d" />
          </el-select>
        </div>
        <div class="toolbar-right">
          <el-button :icon="Refresh" @click="fetchAll">刷新</el-button>
          <el-button type="primary" :icon="Plus" @click="openCreate">新增用户</el-button>
        </div>
      </div>

      <!-- Table -->
      <div class="table-wrap">
        <el-table
          :data="filteredUsers"
          stripe
          highlight-current-row
          @row-click="openDrawer"
          style="cursor: pointer"
        >
          <el-table-column label="用户" min-width="180">
            <template #default="{ row }">
              <div class="user-cell">
                <div class="avatar" :class="`avatar--${row.role}`">
                  {{ row.username.charAt(0).toUpperCase() }}
                </div>
                <div>
                  <div class="cell-name">{{ row.username }}</div>
                  <div class="cell-sub">{{ row.department || '—' }}</div>
                </div>
              </div>
            </template>
          </el-table-column>
          <el-table-column label="角色" width="140">
            <template #default="{ row }">
              <el-tag :type="roleTagType(row.role)" size="small" effect="light">
                {{ roleLabel(row.role) }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="所属企业" min-width="160">
            <template #default="{ row }">
              <span v-if="row.org_name" class="org-chip">
                <el-icon><OfficeBuilding /></el-icon>{{ row.org_name }}
              </span>
              <span v-else class="muted">—</span>
            </template>
          </el-table-column>
          <el-table-column label="权限" width="100">
            <template #default="{ row }">
              <el-tag
                v-if="row.permission_override_enabled"
                size="small"
                type="warning"
                effect="plain"
              >个性化</el-tag>
              <span v-else class="muted">角色默认</span>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="130" fixed="right" @click.stop>
            <template #default="{ row }">
              <el-button size="small" text type="primary" @click.stop="openDrawer(row)">
                <el-icon><Edit /></el-icon>编辑
              </el-button>
              <el-button size="small" text type="danger" @click.stop="deleteUser(row.id)">
                <el-icon><Delete /></el-icon>删除
              </el-button>
            </template>
          </el-table-column>
        </el-table>
      </div>
    </div>

    <!-- ══════════════════════════════════════════════════════════════ -->
    <!--  TAB: ROLES                                                   -->
    <!-- ══════════════════════════════════════════════════════════════ -->
    <div v-show="activeTab === 'roles'" class="tab-content">
      <div class="roles-layout">
        <!-- Left: role cards -->
        <div class="roles-sidebar">
          <div class="sidebar-label">系统角色</div>
          <div
            v-for="role in roles"
            :key="role.code"
            class="role-card"
            :class="{ active: selectedRole?.code === role.code, [`role-card--${role.code}`]: true }"
            @click="selectedRole = role"
          >
            <div class="role-card-icon">{{ roleIcon(role.code) }}</div>
            <div class="role-card-body">
              <div class="role-card-name">{{ role.name }}</div>
              <div class="role-card-meta">
                {{ userCountByRole(role.code) }} 人
              </div>
            </div>
            <el-icon v-if="selectedRole?.code === role.code" class="role-check"><Check /></el-icon>
          </div>
        </div>

        <!-- Right: permission tree -->
        <div class="perm-detail" v-if="selectedRole">
          <div class="perm-detail-header">
            <div class="perm-detail-title">
              <span class="role-pill" :class="`role-pill--${selectedRole.code}`">{{ selectedRole.name }}</span>
              <span>权限详情</span>
            </div>
            <el-text type="info" size="small">内置角色权限为系统默认，可在用户详情中为个别用户定制。</el-text>
          </div>

          <el-tabs v-model="permTab" class="perm-tabs">
            <el-tab-pane label="菜单权限" name="menu">
              <div class="perm-grid">
                <div v-for="group in menuGroups" :key="group.group" class="perm-group">
                  <div class="perm-group-label">{{ group.group }}</div>
                  <div class="perm-items">
                    <div
                      v-for="perm in group.permissions"
                      :key="perm.code"
                      class="perm-item"
                      :class="{ on: isEnabled(selectedRole, perm.code, 'menu') }"
                    >
                      <span class="perm-dot" />
                      <span class="perm-name">{{ perm.name }}</span>
                      <el-icon class="perm-icon">
                        <Check v-if="isEnabled(selectedRole, perm.code, 'menu')" />
                        <Close v-else />
                      </el-icon>
                    </div>
                  </div>
                </div>
              </div>
            </el-tab-pane>

            <el-tab-pane label="操作权限" name="action">
              <div class="perm-grid">
                <div v-for="group in actionGroups" :key="group.group" class="perm-group">
                  <div class="perm-group-label">{{ group.group }}</div>
                  <div class="perm-items">
                    <div
                      v-for="perm in group.permissions"
                      :key="perm.code"
                      class="perm-item"
                      :class="{ on: isEnabled(selectedRole, perm.code, 'action') }"
                    >
                      <span class="perm-dot" />
                      <span class="perm-name">{{ perm.name }}</span>
                      <el-icon class="perm-icon">
                        <Check v-if="isEnabled(selectedRole, perm.code, 'action')" />
                        <Close v-else />
                      </el-icon>
                    </div>
                  </div>
                </div>
              </div>
            </el-tab-pane>
          </el-tabs>
        </div>

        <div v-else class="perm-empty">
          <el-empty description="选择左侧角色查看权限" :image-size="80" />
        </div>
      </div>
    </div>

    <!-- ══════════════════════════════════════════════════════════════ -->
    <!--  TAB: ORGS (super_admin only)                                 -->
    <!-- ══════════════════════════════════════════════════════════════ -->
    <div v-show="activeTab === 'orgs'" class="tab-content">
      <div class="toolbar">
        <div class="toolbar-left">
          <el-input v-model="orgSearch" placeholder="搜索企业..." prefix-icon="Search" clearable style="width: 220px" />
        </div>
        <div class="toolbar-right">
          <el-button :icon="Refresh" @click="fetchOrgs">刷新</el-button>
          <el-button type="primary" :icon="Plus" @click="openOrgCreate">新增企业</el-button>
        </div>
      </div>

      <div class="table-wrap">
        <el-table :data="filteredOrgs" stripe>
          <el-table-column label="企业" min-width="220">
            <template #default="{ row }">
              <div class="user-cell">
                <div class="org-avatar-cell">{{ row.name.charAt(0) }}</div>
                <div>
                  <div class="cell-name">{{ row.name }}</div>
                  <div class="cell-sub">{{ row.slug }}</div>
                </div>
              </div>
            </template>
          </el-table-column>
          <el-table-column label="标识" width="160">
            <template #default="{ row }">
              <el-tag effect="plain" size="small">{{ row.slug }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="用户数" width="100">
            <template #default="{ row }">
              <span>{{ userCountByOrg(row.id) }}</span>
            </template>
          </el-table-column>
          <el-table-column label="创建时间" width="180">
            <template #default="{ row }">
              <span class="muted">{{ formatDate(row.created_at) }}</span>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="130" fixed="right">
            <template #default="{ row }">
              <el-button size="small" text type="primary" @click="openOrgEdit(row)">
                <el-icon><Edit /></el-icon>编辑
              </el-button>
              <el-button size="small" text type="danger" @click="deleteOrg(row.id)">
                <el-icon><Delete /></el-icon>删除
              </el-button>
            </template>
          </el-table-column>
        </el-table>
      </div>
    </div>

    <!-- ══════════════════════════════════════════════════════════════ -->
    <!--  USER EDIT DRAWER                                             -->
    <!-- ══════════════════════════════════════════════════════════════ -->
    <el-drawer
      v-model="drawerVisible"
      :title="drawerTitle"
      direction="rtl"
      size="480px"
      destroy-on-close
      class="user-drawer"
    >
      <template #header>
        <div class="drawer-header">
          <div v-if="drawerUser" class="drawer-avatar" :class="`avatar--${drawerForm.role}`">
            {{ (drawerForm.username || '?').charAt(0).toUpperCase() }}
          </div>
          <div>
            <div class="drawer-title">{{ drawerTitle }}</div>
            <div v-if="drawerUser" class="drawer-sub">
              <el-tag :type="roleTagType(drawerUser.role)" size="small">{{ roleLabel(drawerUser.role) }}</el-tag>
              <span class="muted" style="margin-left:8px;font-size:12px">{{ drawerUser.department || '未分配部门' }}</span>
            </div>
          </div>
        </div>
      </template>

      <el-tabs v-model="drawerTab" class="drawer-tabs">
        <!-- Basic info tab -->
        <el-tab-pane label="基本信息" name="info">
          <el-form :model="drawerForm" label-width="88px" class="drawer-form">
            <el-form-item label="用户名" required>
              <el-input v-model="drawerForm.username" placeholder="请输入用户名" />
            </el-form-item>
            <el-form-item label="密码" :required="!drawerUser">
              <el-input
                v-model="drawerForm.password"
                type="password"
                show-password
                :placeholder="drawerUser ? '留空则不修改密码' : '请输入密码'"
              />
            </el-form-item>
            <el-form-item label="角色" required>
              <el-select v-model="drawerForm.role" style="width:100%">
                <el-option
                  v-for="r in availableRoles"
                  :key="r.code"
                  :value="r.code"
                  :label="r.name"
                >
                  <div class="role-opt">
                    <el-tag :type="roleTagType(r.code)" size="small" effect="light">{{ r.name }}</el-tag>
                    <span class="role-opt-desc">{{ r.desc }}</span>
                  </div>
                </el-option>
              </el-select>
            </el-form-item>
            <el-form-item label="部门">
              <el-input v-model="drawerForm.department" placeholder="如：数据分析部" />
            </el-form-item>
            <el-form-item v-if="isSuperAdmin" label="所属企业">
              <el-select v-model="drawerForm.org_id" clearable placeholder="选择企业" style="width:100%">
                <el-option v-for="org in organizations" :key="org.id" :label="org.name" :value="org.id" />
              </el-select>
            </el-form-item>
          </el-form>

          <div class="drawer-footer">
            <el-button @click="drawerVisible = false">取消</el-button>
            <el-button type="primary" :loading="saving" @click="saveUser">保存</el-button>
          </div>
        </el-tab-pane>

        <!-- Permission override tab (only when editing) -->
        <el-tab-pane v-if="drawerUser" label="权限配置" name="perms">
          <div class="perm-override-header">
            <el-switch
              v-model="overrideEnabled"
              active-text="个性化权限已启用"
              inactive-text="使用角色默认权限"
              @change="onOverrideToggle"
            />
            <el-text type="info" size="small" style="margin-top:8px;display:block">
              启用后可为该用户单独定制权限，覆盖其角色模板。
            </el-text>
          </div>

          <template v-if="overrideEnabled">
            <el-tabs v-model="overrideTab" style="margin-top:12px">
              <el-tab-pane label="菜单权限" name="menu">
                <div class="override-grid">
                  <div v-for="group in menuGroups" :key="group.group" class="perm-group">
                    <div class="perm-group-label">{{ group.group }}</div>
                    <div class="perm-items">
                      <div
                        v-for="perm in group.permissions"
                        :key="perm.code"
                        class="perm-item override"
                      >
                        <el-checkbox v-model="overrideMenuPerms[perm.code]" @change="isDirty = true" />
                        <span class="perm-name">{{ perm.name }}</span>
                        <el-tag
                          v-if="overrideMenuPerms[perm.code] !== roleBasePerms.menu[perm.code]"
                          size="small"
                          type="warning"
                          effect="plain"
                        >已覆盖</el-tag>
                      </div>
                    </div>
                  </div>
                </div>
              </el-tab-pane>

              <el-tab-pane label="操作权限" name="action">
                <div class="override-grid">
                  <div v-for="group in actionGroups" :key="group.group" class="perm-group">
                    <div class="perm-group-label">{{ group.group }}</div>
                    <div class="perm-items">
                      <div
                        v-for="perm in group.permissions"
                        :key="perm.code"
                        class="perm-item override"
                      >
                        <el-checkbox v-model="overrideActionPerms[perm.code]" @change="isDirty = true" />
                        <span class="perm-name">{{ perm.name }}</span>
                        <el-tag
                          v-if="overrideActionPerms[perm.code] !== roleBasePerms.action[perm.code]"
                          size="small"
                          type="warning"
                          effect="plain"
                        >已覆盖</el-tag>
                      </div>
                    </div>
                  </div>
                </div>
              </el-tab-pane>
            </el-tabs>

            <div class="drawer-footer" v-if="isDirty">
              <el-text type="warning" size="small">有未保存的更改</el-text>
              <div style="display:flex;gap:8px">
                <el-button @click="resetOverride">重置</el-button>
                <el-button type="primary" :loading="savingPerms" @click="saveOverride">保存权限</el-button>
              </div>
            </div>
          </template>
        </el-tab-pane>
      </el-tabs>
    </el-drawer>

    <!-- ══════════════════════════════════════════════════════════════ -->
    <!--  ORG DIALOG                                                   -->
    <!-- ══════════════════════════════════════════════════════════════ -->
    <el-dialog v-model="orgDialogVisible" :title="orgIsEdit ? '编辑企业' : '新增企业'" width="440px" destroy-on-close>
      <el-form :model="orgForm" label-width="100px">
        <el-form-item label="企业名称" required>
          <el-input v-model="orgForm.name" placeholder="如：嘉盛半导体" />
        </el-form-item>
        <el-form-item label="标识 (slug)" required>
          <el-input v-model="orgForm.slug" placeholder="如：carsem（英文小写）" />
          <div class="form-tip">用于区分不同企业，建议英文小写字母</div>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="orgDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="savingOrg" @click="saveOrg">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref, type Component } from "vue"
import axios from "axios"
import { ElMessage, ElMessageBox } from "element-plus"
import { useAuthStore } from "@/store/auth"
import {
  User, UserFilled, OfficeBuilding, Grid, Setting,
  Refresh, Plus, Edit, Delete, Check, Close,
} from "@element-plus/icons-vue"

// ── Types ──────────────────────────────────────────────────────────────────────

interface UserItem {
  id: number
  username: string
  role: string
  role_label: string | null
  department: string | null
  org_id: number | null
  org_name: string | null
  permission_override_enabled: boolean
  menu_permissions: Record<string, boolean> | null
  action_permissions: Record<string, boolean> | null
}

interface OrgItem {
  id: number
  name: string
  slug: string
  created_at: string
}

interface PermItem { code: string; name: string }
interface PermGroup { type: string; group: string; permissions: PermItem[] }
interface RoleTemplate {
  code: string
  name: string
  is_builtin: boolean
  template: { menu_permissions: Record<string, boolean>; action_permissions: Record<string, boolean> }
}

// ── State ──────────────────────────────────────────────────────────────────────

const authStore = useAuthStore()
const isSuperAdmin = computed(() => authStore.profile?.role === "super_admin")

const activeTab = ref<"users" | "roles" | "orgs">("users")

// Users
const users = ref<UserItem[]>([])
const userSearch = ref("")
const roleFilter = ref("")
const deptFilter = ref("")

// Roles
const roles = ref<RoleTemplate[]>([])
const catalog = ref<PermGroup[]>([])
const selectedRole = ref<RoleTemplate | null>(null)
const permTab = ref("menu")

// Orgs
const organizations = ref<OrgItem[]>([])
const orgSearch = ref("")

// Drawer
const drawerVisible = ref(false)
const drawerTab = ref("info")
const drawerUser = ref<UserItem | null>(null)
const saving = ref(false)
const drawerForm = reactive({
  username: "",
  password: "",
  role: "user",
  department: "",
  org_id: null as number | null,
})

// Permission override
const overrideEnabled = ref(false)
const overrideMenuPerms = ref<Record<string, boolean>>({})
const overrideActionPerms = ref<Record<string, boolean>>({})
const roleBasePerms = ref<{ menu: Record<string, boolean>; action: Record<string, boolean> }>({ menu: {}, action: {} })
const overrideTab = ref("menu")
const isDirty = ref(false)
const savingPerms = ref(false)

// Org dialog
const orgDialogVisible = ref(false)
const orgIsEdit = ref(false)
const orgEditId = ref<number | null>(null)
const savingOrg = ref(false)
const orgForm = reactive({ name: "", slug: "" })

// ── Computed ───────────────────────────────────────────────────────────────────

const visibleTabs = computed(() => {
  const tabs: { key: string; label: string; icon: Component; badge?: number }[] = [
    { key: "users", label: "用户管理", icon: User, badge: users.value.length },
    { key: "roles", label: "角色与权限", icon: Setting },
  ]
  if (isSuperAdmin.value) {
    tabs.push({ key: "orgs", label: "企业管理", icon: OfficeBuilding, badge: organizations.value.length })
  }
  return tabs
})

const adminCount = computed(() => users.value.filter(u => u.role !== "user").length)
const deptCount = computed(() => new Set(users.value.map(u => u.department).filter(Boolean)).size)

const allDepts = computed(() => [...new Set(users.value.map(u => u.department).filter(Boolean))] as string[])

const filteredUsers = computed(() => {
  return users.value.filter(u => {
    const matchSearch = !userSearch.value || u.username.toLowerCase().includes(userSearch.value.toLowerCase())
    const matchRole = !roleFilter.value || u.role === roleFilter.value
    const matchDept = !deptFilter.value || u.department === deptFilter.value
    return matchSearch && matchRole && matchDept
  })
})

const filteredOrgs = computed(() => {
  if (!orgSearch.value) return organizations.value
  return organizations.value.filter(o => o.name.toLowerCase().includes(orgSearch.value.toLowerCase()) || o.slug.includes(orgSearch.value))
})

const menuGroups = computed(() => catalog.value.filter(g => g.type === "menu"))
const actionGroups = computed(() => catalog.value.filter(g => g.type === "action"))

const drawerTitle = computed(() => drawerUser.value ? `编辑 ${drawerUser.value.username}` : "新增用户")

const availableRoles = computed(() => {
  const all = [
    { code: "user", name: "普通用户", desc: "可查询数据、浏览 BI 资产" },
    { code: "dept_admin", name: "部门管理员", desc: "可管理本部门行动项和 BI 资产" },
    { code: "org_admin", name: "企业管理员", desc: "可管理本企业用户、数据源和全部 BI 资产" },
  ]
  if (isSuperAdmin.value) {
    all.push({ code: "super_admin", name: "超级管理员", desc: "拥有所有权限，跨企业管理" })
  }
  return all
})

// ── Helpers ────────────────────────────────────────────────────────────────────

const roleLabel = (role: string) => {
  const map: Record<string, string> = {
    user: "普通用户", dept_admin: "部门管理员",
    org_admin: "企业管理员", super_admin: "超级管理员",
  }
  return map[role] || role
}

const roleTagType = (role: string): "info" | "success" | "warning" | "danger" | "primary" => {
  const map: Record<string, "info" | "success" | "warning" | "danger" | "primary"> = {
    user: "info", dept_admin: "primary", org_admin: "warning", super_admin: "danger",
  }
  return map[role] || "info"
}

const roleIcon = (code: string) => {
  const icons: Record<string, string> = {
    user: "👤", dept_admin: "👥", org_admin: "🏢", super_admin: "⭐",
  }
  return icons[code] || "🔑"
}

const userCountByRole = (role: string) => users.value.filter(u => u.role === role).length
const userCountByOrg = (orgId: number) => users.value.filter(u => u.org_id === orgId).length

const isEnabled = (role: RoleTemplate, code: string, type: "menu" | "action") => {
  const key = type === "menu" ? "menu_permissions" : "action_permissions"
  return Boolean(role.template[key]?.[code])
}

const formatDate = (s: string) => {
  const d = new Date(s)
  return isNaN(d.getTime()) ? s : d.toLocaleDateString("zh-CN")
}

// ── Data fetching ──────────────────────────────────────────────────────────────

const fetchUsers = async () => {
  const { data } = await axios.get("/api/users")
  users.value = data
}

const fetchOrgs = async () => {
  if (isSuperAdmin.value) {
    const { data } = await axios.get("/api/organizations")
    organizations.value = data
  }
}

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

const fetchAll = async () => {
  await Promise.all([fetchUsers(), fetchOrgs(), fetchCatalog()])
}

// ── User drawer ────────────────────────────────────────────────────────────────

const openCreate = () => {
  drawerUser.value = null
  drawerTab.value = "info"
  drawerForm.username = ""
  drawerForm.password = ""
  drawerForm.role = "user"
  drawerForm.department = ""
  drawerForm.org_id = authStore.profile?.org_id || null
  drawerVisible.value = true
}

const openDrawer = async (row: UserItem) => {
  drawerUser.value = row
  drawerTab.value = "info"
  drawerForm.username = row.username
  drawerForm.password = ""
  drawerForm.role = row.role
  drawerForm.department = row.department || ""
  drawerForm.org_id = row.org_id
  drawerVisible.value = true

  // Load permission data
  try {
    const { data } = await axios.get(`/api/users/${row.id}`)
    overrideEnabled.value = data.permission_override_enabled || false
    const roleTemplate = roles.value.find(r => r.code === data.role)
    roleBasePerms.value = {
      menu: roleTemplate?.template.menu_permissions || {},
      action: roleTemplate?.template.action_permissions || {},
    }
    overrideMenuPerms.value = { ...roleBasePerms.value.menu, ...(data.menu_permissions || {}) }
    overrideActionPerms.value = { ...roleBasePerms.value.action, ...(data.action_permissions || {}) }
    isDirty.value = false
  } catch { /* ignore */ }
}

const saveUser = async () => {
  if (!drawerForm.username || (!drawerUser.value && !drawerForm.password)) {
    ElMessage.warning("请填写必填字段")
    return
  }
  saving.value = true
  try {
    const payload: Record<string, unknown> = {
      username: drawerForm.username,
      role: drawerForm.role,
      department: drawerForm.department || null,
      org_id: drawerForm.org_id,
    }
    if (drawerForm.password) payload.password = drawerForm.password

    if (drawerUser.value) {
      await axios.put(`/api/users/${drawerUser.value.id}`, payload)
      ElMessage.success("用户已更新")
    } else {
      await axios.post("/api/users", payload)
      ElMessage.success("用户已创建")
    }
    drawerVisible.value = false
    await fetchUsers()
  } catch (e: unknown) {
    const err = e as { response?: { data?: { detail?: string } } }
    ElMessage.error(err.response?.data?.detail || "保存失败")
  } finally {
    saving.value = false
  }
}

const deleteUser = async (id: number) => {
  try {
    await ElMessageBox.confirm("确定要删除此用户？", "提示", { type: "warning" })
    await axios.delete(`/api/users/${id}`)
    ElMessage.success("已删除")
    if (drawerVisible.value && drawerUser.value?.id === id) drawerVisible.value = false
    await fetchUsers()
  } catch { /* cancelled */ }
}

// ── Permission override ────────────────────────────────────────────────────────

const onOverrideToggle = async (val: boolean) => {
  if (!drawerUser.value) return
  try {
    await axios.put(`/api/users/${drawerUser.value.id}`, { permission_override_enabled: val })
  } catch {
    overrideEnabled.value = !val
    ElMessage.error("保存失败")
  }
}

const saveOverride = async () => {
  if (!drawerUser.value) return
  savingPerms.value = true
  try {
    await axios.put(`/api/users/${drawerUser.value.id}`, {
      permission_override_enabled: true,
      menu_permissions: overrideMenuPerms.value,
      action_permissions: overrideActionPerms.value,
    })
    isDirty.value = false
    ElMessage.success("权限已保存")
    await fetchUsers()
  } catch {
    ElMessage.error("保存失败")
  } finally {
    savingPerms.value = false
  }
}

const resetOverride = async () => {
  if (drawerUser.value) await openDrawer(drawerUser.value)
}

// ── Org CRUD ───────────────────────────────────────────────────────────────────

const openOrgCreate = () => {
  orgIsEdit.value = false
  orgEditId.value = null
  orgForm.name = ""
  orgForm.slug = ""
  orgDialogVisible.value = true
}

const openOrgEdit = (row: OrgItem) => {
  orgIsEdit.value = true
  orgEditId.value = row.id
  orgForm.name = row.name
  orgForm.slug = row.slug
  orgDialogVisible.value = true
}

const saveOrg = async () => {
  if (!orgForm.name || !orgForm.slug) { ElMessage.warning("请填写必填字段"); return }
  savingOrg.value = true
  try {
    if (orgIsEdit.value && orgEditId.value) {
      await axios.put(`/api/organizations/${orgEditId.value}`, orgForm)
      ElMessage.success("企业已更新")
    } else {
      await axios.post("/api/organizations", orgForm)
      ElMessage.success("企业已创建")
    }
    orgDialogVisible.value = false
    await fetchOrgs()
  } catch (e: unknown) {
    const err = e as { response?: { data?: { detail?: string } } }
    ElMessage.error(err.response?.data?.detail || "保存失败")
  } finally {
    savingOrg.value = false
  }
}

const deleteOrg = async (id: number) => {
  try {
    await ElMessageBox.confirm("确定删除此企业？删除后该企业下的用户将无法登录。", "提示", { type: "warning" })
    await axios.delete(`/api/organizations/${id}`)
    ElMessage.success("已删除")
    await Promise.all([fetchOrgs(), fetchUsers()])
  } catch { /* cancelled */ }
}

// ── Init ───────────────────────────────────────────────────────────────────────

onMounted(fetchAll)
</script>

<style scoped>
/* ── Page shell ─────────────────────────────────────────────────────────────── */
.ac-page {
  display: flex;
  flex-direction: column;
  gap: 0;
  height: 100%;
}

/* ── Tab bar ────────────────────────────────────────────────────────────────── */
.ac-tabbar {
  display: flex;
  gap: 4px;
  background: var(--app-surface);
  border: 1px solid var(--app-border);
  border-radius: 12px;
  padding: 6px;
  margin-bottom: 20px;
  width: fit-content;
}

.ac-tab {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 18px;
  border-radius: 8px;
  border: none;
  background: transparent;
  color: var(--app-text-muted);
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.18s;
  position: relative;
}

.ac-tab:hover {
  background: var(--el-fill-color-light);
  color: var(--app-text);
}

.ac-tab.active {
  background: var(--app-primary);
  color: #fff;
}

.tab-badge {
  background: rgba(255, 255, 255, 0.25);
  color: inherit;
  font-size: 11px;
  font-weight: 600;
  padding: 1px 6px;
  border-radius: 10px;
  margin-left: 2px;
}

.ac-tab.active .tab-badge {
  background: rgba(255,255,255,0.3);
}

/* ── Tab content ────────────────────────────────────────────────────────────── */
.tab-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 16px;
  min-height: 0;
}

/* ── Stats ──────────────────────────────────────────────────────────────────── */
.stats-row {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
}

.stat-card {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 16px 20px;
  background: var(--app-surface);
  border: 1px solid var(--app-border);
  border-radius: 12px;
}

.stat-icon {
  width: 44px;
  height: 44px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  flex-shrink: 0;
}

.stat-val {
  font-size: 26px;
  font-weight: 700;
  color: var(--app-text);
  line-height: 1;
}

.stat-lbl {
  font-size: 12px;
  color: var(--app-text-muted);
  margin-top: 3px;
}

/* ── Toolbar ────────────────────────────────────────────────────────────────── */
.toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
}

.toolbar-left, .toolbar-right {
  display: flex;
  align-items: center;
  gap: 10px;
}

/* ── Table wrap ─────────────────────────────────────────────────────────────── */
.table-wrap {
  background: var(--app-surface);
  border: 1px solid var(--app-border);
  border-radius: 12px;
  overflow: hidden;
  flex: 1;
}

/* ── User cell ──────────────────────────────────────────────────────────────── */
.user-cell {
  display: flex;
  align-items: center;
  gap: 10px;
}

.avatar {
  width: 34px;
  height: 34px;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 700;
  font-size: 14px;
  color: #fff;
  flex-shrink: 0;
}

.avatar--user       { background: #94a3b8; }
.avatar--dept_admin { background: #3b82f6; }
.avatar--org_admin  { background: #f59e0b; }
.avatar--super_admin{ background: linear-gradient(135deg,#f59e0b,#ef4444); }

.org-avatar-cell {
  width: 34px;
  height: 34px;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 700;
  font-size: 16px;
  color: #fff;
  flex-shrink: 0;
  background: linear-gradient(135deg,#10b981,#059669);
}

.cell-name { font-weight: 500; font-size: 14px; color: var(--app-text); }
.cell-sub  { font-size: 12px; color: var(--app-text-muted); margin-top: 1px; }

.org-chip {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  color: var(--app-text);
  font-size: 13px;
}

.muted { color: var(--app-text-muted); font-size: 13px; }

/* ── Roles layout ───────────────────────────────────────────────────────────── */
.roles-layout {
  display: flex;
  gap: 24px;
  flex: 1;
  min-height: 0;
}

.roles-sidebar {
  width: 210px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.sidebar-label {
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.8px;
  text-transform: uppercase;
  color: var(--app-text-muted);
  padding: 0 4px;
  margin-bottom: 4px;
}

.role-card {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 14px;
  border-radius: 10px;
  border: 1.5px solid transparent;
  cursor: pointer;
  transition: all 0.16s;
  background: var(--app-surface);
}

.role-card:hover { background: var(--el-fill-color-light); }
.role-card.active {
  background: var(--el-color-primary-light-9);
  border-color: var(--el-color-primary-light-5);
}

.role-card--super_admin.active { background: #fef3c7; border-color: #fbbf24; }
.role-card--org_admin.active   { background: #dbeafe; border-color: #93c5fd; }
.role-card--dept_admin.active  { background: #d1fae5; border-color: #6ee7b7; }
.role-card--user.active        { background: #f3f4f6; border-color: #d1d5db; }

.role-card-icon { font-size: 22px; }
.role-card-body { flex: 1; min-width: 0; }
.role-card-name { font-weight: 600; font-size: 14px; }
.role-card-meta { font-size: 12px; color: var(--app-text-muted); }
.role-check { color: var(--app-primary); font-size: 16px; }

/* ── Permission detail ──────────────────────────────────────────────────────── */
.perm-detail {
  flex: 1;
  min-width: 0;
  background: var(--app-surface);
  border: 1px solid var(--app-border);
  border-radius: 12px;
  padding: 20px 24px;
  display: flex;
  flex-direction: column;
  overflow: auto;
}

.perm-detail-header {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  margin-bottom: 16px;
  flex-wrap: wrap;
  gap: 8px;
}

.perm-detail-title {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 15px;
  font-weight: 600;
}

.role-pill {
  padding: 3px 10px;
  border-radius: 6px;
  font-size: 12px;
  font-weight: 600;
}

.role-pill--super_admin { background: #fef3c7; color: #92400e; }
.role-pill--org_admin   { background: #dbeafe; color: #1e40af; }
.role-pill--dept_admin  { background: #d1fae5; color: #065f46; }
.role-pill--user        { background: #f3f4f6; color: #374151; }

.perm-empty { flex: 1; display: flex; align-items: center; justify-content: center; }

.perm-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: 16px;
  padding-top: 8px;
}

.perm-group { display: flex; flex-direction: column; gap: 4px; }

.perm-group-label {
  font-size: 11px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.6px;
  color: var(--app-text-muted);
  border-left: 3px solid var(--el-color-primary-light-5);
  padding-left: 7px;
  margin-bottom: 4px;
}

.perm-items { display: flex; flex-direction: column; gap: 2px; }

.perm-item {
  display: flex;
  align-items: center;
  gap: 7px;
  padding: 5px 6px;
  border-radius: 6px;
  font-size: 13px;
  transition: background 0.12s;
}

.perm-item:not(.on):not(.override) { opacity: 0.45; }
.perm-item.on { background: rgba(16, 185, 129, 0.07); }

.perm-item.override { opacity: 1; }
.perm-item.override:hover { background: var(--el-fill-color-light); }

.perm-dot {
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: #d1d5db;
  flex-shrink: 0;
}

.perm-item.on .perm-dot { background: #10b981; }

.perm-name { flex: 1; }

.perm-icon { font-size: 13px; flex-shrink: 0; color: #10b981; }
.perm-item:not(.on) .perm-icon { color: #d1d5db; }

/* ── Drawer ─────────────────────────────────────────────────────────────────── */
.drawer-header {
  display: flex;
  align-items: center;
  gap: 14px;
}

.drawer-avatar {
  width: 44px;
  height: 44px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 700;
  font-size: 18px;
  color: #fff;
  flex-shrink: 0;
}

.drawer-title { font-size: 15px; font-weight: 600; }
.drawer-sub { margin-top: 3px; display: flex; align-items: center; }

.drawer-form { padding-top: 8px; }

.drawer-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding-top: 20px;
  margin-top: 12px;
  border-top: 1px solid var(--app-border);
}

.perm-override-header {
  padding: 14px 16px;
  background: var(--el-fill-color-lighter);
  border-radius: 8px;
  margin-bottom: 4px;
}

.override-grid {
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding-top: 8px;
}

/* ── Role option in select ──────────────────────────────────────────────────── */
.role-opt { display: flex; align-items: center; gap: 10px; }
.role-opt-desc { font-size: 12px; color: var(--app-text-muted); }

/* ── Misc ───────────────────────────────────────────────────────────────────── */
.form-tip { font-size: 12px; color: var(--app-text-muted); margin-top: 4px; }

.perm-tabs { flex: 1; }

/* deep: remove el-drawer default padding so drawer tabs fill cleanly */
:deep(.user-drawer .el-drawer__body) {
  padding: 0 20px 20px;
  overflow-y: auto;
}

:deep(.user-drawer .el-drawer__header) {
  padding: 18px 20px 14px;
  margin-bottom: 0;
  border-bottom: 1px solid var(--app-border);
}

:deep(.drawer-tabs .el-tabs__header) {
  margin: 0 0 16px;
}
</style>
