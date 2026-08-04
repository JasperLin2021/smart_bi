<template>
  <div class="ac-page">
    <!-- ── Top Tab Bar ─────────────────────────────────────────────── -->
    <div class="page-tabbar ac-tabbar">
      <button
        v-for="t in visibleTabs"
        :key="t.key"
        class="page-tab ac-tab"
        :class="{ active: activeTab === t.key, 'is-active': activeTab === t.key }"
        @click="activeTab = t.key"
      >
        <el-icon><component :is="t.icon" /></el-icon>
        {{ t.label }}
        <span v-if="t.badge" class="page-tab-badge tab-badge">{{ t.badge }}</span>
      </button>
    </div>

    <!-- ══════════════════════════════════════════════════════════════ -->
    <!--  TAB: ROLES                                                   -->
    <!-- ══════════════════════════════════════════════════════════════ -->
    <div v-show="activeTab === 'roles'" class="tab-content">
      <div class="roles-layout">
        <!-- Left: role cards -->
        <div class="roles-sidebar">
          <div class="roles-sidebar-head">
            <div class="sidebar-label">角色库</div>
            <el-button v-if="canManageRoles" size="small" type="primary" :icon="Plus" @click="openRoleCreate">新建角色</el-button>
          </div>
          <div
            v-for="role in roles"
            :key="role.code"
            class="role-card"
            :class="{ active: selectedRole?.code === role.code, [`role-card--${role.code}`]: true }"
            @click="selectedRole = role"
          >
            <el-icon class="role-card-icon"><component :is="roleIcon(role.code)" /></el-icon>
            <div class="role-card-body">
              <div class="role-card-name">{{ role.name }}</div>
              <div class="role-card-meta">
                {{ role.is_builtin ? '内置角色' : (role.org_name || '自定义角色') }} · {{ userCountByRole(role.code) }} 人
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
              <el-tag size="small" effect="plain" :type="selectedRole.is_builtin ? 'info' : 'success'">
                {{ selectedRole.is_builtin ? '内置角色' : '自定义角色' }}
              </el-tag>
            </div>
            <div class="perm-detail-actions">
              <el-button
                v-if="isRoleEditable(selectedRole)"
                size="small"
                :icon="Edit"
                @click="openRoleEdit(selectedRole)"
              >
                编辑角色
              </el-button>
              <el-button
                v-if="isRoleEditable(selectedRole)"
                size="small"
                type="danger"
                :icon="Delete"
                @click="deleteRole(selectedRole)"
              >
                删除角色
              </el-button>
            </div>
          </div>
          <el-text type="info" size="small" style="margin-bottom:12px;display:block">
            内置角色只读；企业自定义角色可控制菜单、操作权限和数据范围。
          </el-text>

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
    <!--  TAB: ORGS / DEPARTMENTS                                      -->
    <!-- ══════════════════════════════════════════════════════════════ -->
    <div v-show="activeTab === 'orgs'" class="tab-content">
      <div class="toolbar">
        <div class="toolbar-left">
          <el-input v-model="orgSearch" placeholder="搜索企业 / 部门..." prefix-icon="Search" clearable style="width: 260px" />
        </div>
        <div class="toolbar-right">
          <el-button :icon="Refresh" @click="fetchOrgTree">刷新</el-button>
          <el-button v-if="canManageOrganizations" type="primary" :icon="Plus" @click="openOrgCreate">新增企业</el-button>
        </div>
      </div>

      <div class="enterprise-layout">
        <section class="enterprise-tree-panel">
          <div class="enterprise-panel-head">
            <div>
              <div class="enterprise-panel-title">企业 / 部门</div>
              <div class="enterprise-panel-sub">{{ organizationCount }} 个企业 · {{ deptCount }} 个部门</div>
            </div>
            <el-button
              v-if="selectedOrgNode && canManageDepartments"
              size="small"
              type="primary"
              :icon="Plus"
              @click="openDepartmentCreate(selectedOrgNode)"
            >
              新建下级部门
            </el-button>
          </div>

          <el-tree
            class="org-tree"
            :data="orgTreeData"
            :props="orgTreeProps"
            node-key="node_key"
            default-expand-all
            highlight-current
            :expand-on-click-node="false"
            @node-click="selectOrgNode"
          >
            <template #default="{ data }">
              <div class="org-tree-node" :class="`org-node--${data.type}`">
                <el-icon class="org-tree-icon">
                  <OfficeBuilding v-if="data.type === 'organization'" />
                  <Grid v-else />
                </el-icon>
                <span class="org-tree-label">{{ data.label }}</span>
                <span class="org-tree-meta">
                  {{ data.type === 'organization' ? `${data.department_count} 部门` : `${data.user_count} 人` }}
                </span>
              </div>
            </template>
          </el-tree>
        </section>

        <section class="enterprise-detail-panel">
          <template v-if="selectedOrgNode">
            <div class="enterprise-detail-head">
              <div class="enterprise-title-row">
                <div class="enterprise-avatar" :class="`enterprise-avatar--${selectedOrgNode.type}`">
                  <el-icon><OfficeBuilding v-if="selectedOrgNode.type === 'organization'" /><Grid v-else /></el-icon>
                </div>
                <div>
                  <div class="enterprise-name">{{ selectedOrgNode.name }}</div>
                  <div class="enterprise-path">{{ selectedNodePath }}</div>
                </div>
              </div>
              <div class="enterprise-actions">
                <el-button
                  v-if="canManageUsers"
                  size="small"
                  type="primary"
                  :icon="Plus"
                  @click="openCreateForOrgNode(selectedOrgNode)"
                >
                  新增成员
                </el-button>
                <el-button
                  v-if="canManageDepartments"
                  size="small"
                  :icon="Plus"
                  @click="openDepartmentCreate(selectedOrgNode)"
                >
                  新建下级部门
                </el-button>
                <template v-if="selectedOrgNode.type === 'department' && canManageDepartments">
                  <el-button size="small" :icon="Edit" @click="openDepartmentEdit(selectedOrgNode)">
                    重命名部门
                  </el-button>
                  <el-button size="small" type="danger" :icon="Delete" @click="deleteDepartment(selectedOrgNode)">
                    删除部门
                  </el-button>
                </template>
                <template v-else-if="canManageOrganizations">
                  <el-button size="small" :icon="Edit" @click="openOrgEdit(nodeToOrg(selectedOrgNode))">编辑企业</el-button>
                  <el-button size="small" type="danger" :icon="Delete" @click="deleteOrg(selectedOrgNode.id)">删除企业</el-button>
                </template>
              </div>
            </div>

            <div class="enterprise-metrics">
              <div class="enterprise-metric">
                <span class="metric-label">成员</span>
                <strong>{{ selectedOrgNode.user_count }}</strong>
              </div>
              <div class="enterprise-metric">
                <span class="metric-label">下级部门</span>
                <strong>{{ selectedOrgNode.department_count }}</strong>
              </div>
              <div class="enterprise-metric">
                <span class="metric-label">类型</span>
                <strong>{{ selectedOrgNode.type === 'organization' ? '企业' : '部门' }}</strong>
              </div>
            </div>

            <div class="enterprise-members">
              <div class="enterprise-section-head">
                <div>
                  <div class="enterprise-section-title">当前节点成员</div>
                  <div class="enterprise-section-sub">在企业或部门节点内直接维护成员账号、角色和个性化权限。</div>
                </div>
                <el-input
                  v-model="memberSearch"
                  placeholder="搜索成员"
                  prefix-icon="Search"
                  clearable
                  style="width: 220px"
                />
              </div>
              <el-table
                :data="selectedNodeUsersFiltered"
                stripe
                size="small"
                empty-text="暂无成员"
                @row-click="openDrawer"
              >
                <el-table-column label="用户" min-width="160">
                  <template #default="{ row }">
                    <div class="user-cell">
                      <div class="avatar" :class="`avatar--${row.role}`">{{ row.username.charAt(0).toUpperCase() }}</div>
                      <div>
                        <div class="cell-name">{{ row.username }}</div>
                        <div class="cell-sub">{{ roleLabel(row.role) }}</div>
                      </div>
                    </div>
                  </template>
                </el-table-column>
                <el-table-column label="部门" min-width="160">
                  <template #default="{ row }">{{ row.department || '未分配部门' }}</template>
                </el-table-column>
                <el-table-column label="权限" width="100">
                  <template #default="{ row }">
                    <el-tag v-if="row.permission_override_enabled" size="small" type="warning" effect="plain">个性化</el-tag>
                    <span v-else class="muted">角色默认</span>
                  </template>
                </el-table-column>
                <el-table-column label="操作" width="142" fixed="right">
                  <template #default="{ row }">
                    <el-button v-if="canManageUsers" size="small" text type="primary" :icon="Edit" @click.stop="openDrawer(row)">编辑</el-button>
                    <el-button v-if="canManageUsers" size="small" text type="danger" :icon="Delete" @click.stop="deleteUser(row.id)">删除</el-button>
                  </template>
                </el-table-column>
              </el-table>
            </div>
          </template>
          <el-empty v-else description="选择左侧企业或部门" :image-size="88" />
        </section>
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
              <el-select
                v-model="drawerForm.department_id"
                clearable
                filterable
                placeholder="选择部门"
                style="width:100%"
                @change="onDrawerDepartmentChange"
              >
                <el-option
                  v-for="dept in departmentOptionsForDrawerOrg"
                  :key="dept.id"
                  :label="dept.path"
                  :value="dept.id"
                >
                  <div class="dept-option">
                    <span>{{ dept.name }}</span>
                    <small>{{ dept.path }}</small>
                  </div>
                </el-option>
              </el-select>
            </el-form-item>
            <el-form-item v-if="isSuperAdmin" label="所属企业">
              <el-select v-model="drawerForm.org_id" clearable placeholder="选择企业" style="width:100%" @change="onDrawerOrgChange">
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
        <el-tab-pane v-if="drawerUser && canManageUserPermissions" label="权限配置" name="perms">
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

    <!-- ══════════════════════════════════════════════════════════════ -->
    <!--  DEPARTMENT DIALOG                                            -->
    <!-- ══════════════════════════════════════════════════════════════ -->
    <el-dialog
      v-model="departmentDialogVisible"
      :title="departmentIsEdit ? '重命名部门' : '新建下级部门'"
      width="460px"
      destroy-on-close
    >
      <el-form :model="departmentForm" label-width="92px">
        <el-form-item label="所属企业">
          <span class="readonly-line">{{ departmentDialogOrgName }}</span>
        </el-form-item>
        <el-form-item v-if="!departmentIsEdit" label="上级部门">
          <span class="readonly-line">{{ departmentDialogParentName }}</span>
        </el-form-item>
        <el-form-item label="部门名称" required>
          <el-input v-model="departmentForm.name" placeholder="如：销售运营部" />
        </el-form-item>
        <el-form-item label="排序">
          <el-input-number v-model="departmentForm.sort_order" :min="0" :max="999" style="width: 160px" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="departmentDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="savingDepartment" @click="saveDepartment">保存</el-button>
      </template>
    </el-dialog>

    <!-- ══════════════════════════════════════════════════════════════ -->
    <!--  ROLE DIALOG                                                  -->
    <!-- ══════════════════════════════════════════════════════════════ -->
    <el-dialog
      v-model="roleDialogVisible"
      :title="roleIsEdit ? '编辑角色' : '新建角色'"
      width="820px"
      destroy-on-close
      class="role-dialog"
    >
      <el-form :model="roleForm" label-width="92px" class="role-form">
        <div class="role-form-grid">
          <el-form-item label="角色编码" required>
            <el-input v-model="roleForm.code" :disabled="roleIsEdit" placeholder="sales_analyst" />
          </el-form-item>
          <el-form-item label="角色名称" required>
            <el-input v-model="roleForm.name" placeholder="销售分析师" />
          </el-form-item>
          <el-form-item v-if="isSuperAdmin" label="所属企业">
            <el-select v-model="roleForm.org_id" clearable placeholder="全局角色" style="width:100%">
              <el-option v-for="org in organizations" :key="org.id" :label="org.name" :value="org.id" />
            </el-select>
          </el-form-item>
          <el-form-item label="数据范围">
            <el-select v-model="roleForm.data_scope" style="width:100%">
              <el-option label="仅本人" value="owner" />
              <el-option label="本企业" value="org" />
              <el-option v-if="isSuperAdmin" label="全局" value="all" />
            </el-select>
          </el-form-item>
        </div>
        <el-form-item label="说明">
          <el-input v-model="roleForm.description" type="textarea" :rows="2" placeholder="描述该角色适用的岗位或授权边界" />
        </el-form-item>

        <el-tabs v-model="roleFormTab" class="role-perm-tabs">
          <el-tab-pane label="菜单权限" name="menu">
            <div class="override-grid">
              <div v-for="group in menuGroups" :key="group.group" class="perm-group">
                <div class="perm-group-label">{{ group.group }}</div>
                <div class="perm-items">
                  <label v-for="perm in group.permissions" :key="perm.code" class="perm-item override">
                    <el-checkbox v-model="roleForm.menu_permissions[perm.code]" />
                    <span class="perm-name">{{ perm.name }}</span>
                  </label>
                </div>
              </div>
            </div>
          </el-tab-pane>
          <el-tab-pane label="操作权限" name="action">
            <div class="override-grid">
              <div v-for="group in actionGroups" :key="group.group" class="perm-group">
                <div class="perm-group-label">{{ group.group }}</div>
                <div class="perm-items">
                  <label v-for="perm in group.permissions" :key="perm.code" class="perm-item override">
                    <el-checkbox v-model="roleForm.action_permissions[perm.code]" />
                    <span class="perm-name">{{ perm.name }}</span>
                  </label>
                </div>
              </div>
            </div>
          </el-tab-pane>
        </el-tabs>
      </el-form>
      <template #footer>
        <el-button @click="roleDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="savingRole" @click="saveRole">保存</el-button>
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
  User, OfficeBuilding, Grid, Setting,
  Refresh, Plus, Edit, Delete, Check, Close,
} from "@element-plus/icons-vue"

// ── Types ──────────────────────────────────────────────────────────────────────

interface UserItem {
  id: number
  username: string
  role: string
  role_label: string | null
  department_id: number | null
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
  created_at?: string
}

interface DepartmentItem {
  id: number
  name: string
  org_id: number
  parent_id: number | null
  sort_order: number
}

interface OrgTreeNode {
  id: number
  node_key: string
  type: "organization" | "department"
  name: string
  label: string
  org_id: number
  slug?: string
  parent_id: number | null
  sort_order: number
  user_count: number
  department_count: number
  children: OrgTreeNode[]
}

interface DepartmentOption extends DepartmentItem {
  path: string
}

interface PermItem { code: string; name: string }
interface PermGroup { type: string; group: string; permissions: PermItem[] }
interface RoleTemplate {
  id: number
  code: string
  name: string
  description?: string | null
  org_id?: number | null
  org_name?: string | null
  is_builtin: boolean
  data_scope?: string | null
  template: {
    data_scope?: string
    menu_permissions: Record<string, boolean>
    action_permissions: Record<string, boolean>
  }
  menu_permissions?: Record<string, boolean>
  action_permissions?: Record<string, boolean>
}

// ── State ──────────────────────────────────────────────────────────────────────

const authStore = useAuthStore()
const currentRole = computed(() => authStore.profile?.role || "")
const isSuperAdmin = computed(() => authStore.profile?.role === "super_admin")
const canManageEnterprise = computed(() => ["super_admin", "org_admin", "dept_admin"].includes(currentRole.value))
const canManageOrganizations = computed(() => currentRole.value === "super_admin")
const canManageDepartments = computed(() => ["super_admin", "org_admin"].includes(currentRole.value))
const canManageRoles = computed(() => ["super_admin", "org_admin"].includes(currentRole.value))
const canManageUsers = computed(() => ["super_admin", "org_admin", "dept_admin"].includes(currentRole.value))
const canManageUserPermissions = computed(() => ["super_admin", "org_admin"].includes(currentRole.value))

const activeTab = ref<"orgs" | "roles">("orgs")

// Users
const users = ref<UserItem[]>([])

// Roles
const roles = ref<RoleTemplate[]>([])
const assignableRoles = ref<RoleTemplate[]>([])
const catalog = ref<PermGroup[]>([])
const selectedRole = ref<RoleTemplate | null>(null)
const permTab = ref("menu")

// Orgs
const organizations = ref<OrgItem[]>([])
const organizationTree = ref<OrgTreeNode[]>([])
const selectedOrgNode = ref<OrgTreeNode | null>(null)
const departmentCache = ref<Record<number, DepartmentItem[]>>({})
const orgSearch = ref("")
const memberSearch = ref("")
const orgTreeProps = { children: "children", label: "label" }

// Drawer
const drawerVisible = ref(false)
const drawerTab = ref("info")
const drawerUser = ref<UserItem | null>(null)
const saving = ref(false)
const drawerForm = reactive({
  username: "",
  password: "",
  role: "user",
  department_id: null as number | null,
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

// Department dialog
const departmentDialogVisible = ref(false)
const departmentIsEdit = ref(false)
const departmentEditId = ref<number | null>(null)
const departmentForm = reactive({
  org_id: null as number | null,
  parent_id: null as number | null,
  name: "",
  sort_order: 0,
})
const savingDepartment = ref(false)

// Role dialog
const roleDialogVisible = ref(false)
const roleIsEdit = ref(false)
const roleEditId = ref<number | null>(null)
const roleFormTab = ref("menu")
const savingRole = ref(false)
const roleForm = reactive({
  code: "",
  name: "",
  description: "",
  org_id: null as number | null,
  data_scope: "owner",
  menu_permissions: {} as Record<string, boolean>,
  action_permissions: {} as Record<string, boolean>,
})

// ── Computed ───────────────────────────────────────────────────────────────────

const visibleTabs = computed(() => {
  const tabs: { key: "orgs" | "roles"; label: string; icon: Component; badge?: number }[] = []
  if (canManageEnterprise.value) {
    tabs.push({ key: "orgs", label: "企业管理", icon: OfficeBuilding, badge: organizationCount.value })
  }
  if (canManageRoles.value) {
    tabs.push({ key: "roles", label: "角色与权限", icon: Setting })
  }
  return tabs
})

const deptCount = computed(() => departmentOptions.value.length)
const organizationCount = computed(() => organizationTree.value.length || organizations.value.length)

const orgTreeData = computed(() => filterOrgTree(organizationTree.value, orgSearch.value))

const menuGroups = computed(() => catalog.value.filter(g => g.type === "menu"))
const actionGroups = computed(() => catalog.value.filter(g => g.type === "action"))

const drawerTitle = computed(() => drawerUser.value ? `编辑 ${drawerUser.value.username}` : "新增用户")

const departmentOptions = computed(() => flattenDepartmentOptions(organizationTree.value))

const departmentOptionsForDrawerOrg = computed(() => {
  if (!drawerForm.org_id) return departmentOptions.value
  const cached = departmentCache.value[drawerForm.org_id]
  if (cached?.length) return flattenDepartmentRecords(cached, drawerForm.org_id)
  return departmentOptions.value.filter(dept => dept.org_id === drawerForm.org_id)
})

const selectedNodeUsers = computed(() => {
  const node = selectedOrgNode.value
  if (!node) return []
  if (node.type === "organization") return users.value.filter(user => user.org_id === node.id)
  return users.value.filter(user => user.department_id === node.id)
})

const selectedNodeUsersFiltered = computed(() => {
  const term = memberSearch.value.trim().toLowerCase()
  if (!term) return selectedNodeUsers.value
  return selectedNodeUsers.value.filter(user => {
    return [
      user.username,
      user.department || "",
      user.org_name || "",
      roleLabel(user.role),
    ].some(value => value.toLowerCase().includes(term))
  })
})

const selectedNodePath = computed(() => {
  const node = selectedOrgNode.value
  if (!node) return ""
  return findNodePath(organizationTree.value, node.node_key).join(" / ")
})

const departmentDialogOrgName = computed(() => {
  if (!departmentForm.org_id) return "未选择企业"
  return getOrgName(departmentForm.org_id)
})

const departmentDialogParentName = computed(() => {
  if (!departmentForm.parent_id) return "企业根部门"
  return findDepartmentOption(departmentForm.parent_id)?.path || "企业根部门"
})

const availableRoles = computed(() => {
  const source = assignableRoles.value.length ? assignableRoles.value : roles.value
  return source.map(role => ({
    code: role.code,
    name: role.name,
    desc: role.description || roleDefaultDesc(role.code),
  }))
})

// ── Helpers ────────────────────────────────────────────────────────────────────

const roleLabel = (role: string) => {
  const map: Record<string, string> = {
    user: "普通用户", dept_admin: "部门管理员",
    org_admin: "企业管理员", super_admin: "超级管理员",
  }
  return map[role] || role
}

const roleDefaultDesc = (role: string) => {
  const map: Record<string, string> = {
    user: "可查询数据、浏览 BI 资产",
    dept_admin: "可管理本部门成员和部门内数据工作",
    org_admin: "可管理本企业用户、角色、部门和 BI 资产",
    super_admin: "拥有所有权限，跨企业管理",
  }
  return map[role] || "企业自定义岗位权限"
}

const roleTagType = (role: string): "info" | "success" | "warning" | "danger" | "primary" => {
  const map: Record<string, "info" | "success" | "warning" | "danger" | "primary"> = {
    user: "info", dept_admin: "primary", org_admin: "warning", super_admin: "danger",
  }
  return map[role] || "info"
}

const roleIcon = (code: string): Component => {
  const icons: Record<string, Component> = {
    user: User,
    dept_admin: Grid,
    org_admin: OfficeBuilding,
    super_admin: Setting,
  }
  return icons[code] || Setting
}

const userCountByRole = (role: string) => users.value.filter(u => u.role === role).length
const userCountByOrg = (orgId: number) => users.value.filter(u => u.org_id === orgId).length

const isEnabled = (role: RoleTemplate, code: string, type: "menu" | "action") => {
  const key = type === "menu" ? "menu_permissions" : "action_permissions"
  return Boolean(role.template[key]?.[code])
}

const isRoleEditable = (role: RoleTemplate | null) => {
  return Boolean(role && canManageRoles.value && !role.is_builtin)
}

const seedPermissionMap = (type: "menu" | "action", source: Record<string, boolean> = {}) => {
  const groups = type === "menu" ? menuGroups.value : actionGroups.value
  const map: Record<string, boolean> = {}
  groups.forEach(group => {
    group.permissions.forEach(perm => {
      map[perm.code] = Boolean(source[perm.code])
    })
  })
  return map
}

const formatDate = (s: string) => {
  const d = new Date(s)
  return isNaN(d.getTime()) ? s : d.toLocaleDateString("zh-CN")
}

const getOrgName = (orgId: number) => {
  const fromTree = organizationTree.value.find(org => org.id === orgId)
  if (fromTree) return fromTree.name
  return organizations.value.find(org => org.id === orgId)?.name || `企业 #${orgId}`
}

const filterOrgTree = (nodes: OrgTreeNode[], keyword: string): OrgTreeNode[] => {
  const term = keyword.trim().toLowerCase()
  if (!term) return nodes
  return nodes
    .map(node => {
      const children = filterOrgTree(node.children || [], keyword)
      const selfMatch = node.name.toLowerCase().includes(term) || (node.slug || "").toLowerCase().includes(term)
      if (!selfMatch && children.length === 0) return null
      return { ...node, children }
    })
    .filter(Boolean) as OrgTreeNode[]
}

const flattenDepartmentOptions = (nodes: OrgTreeNode[]): DepartmentOption[] => {
  const options: DepartmentOption[] = []
  const walk = (node: OrgTreeNode, path: string[]) => {
    const nextPath = [...path, node.name]
    if (node.type === "department") {
      options.push({
        id: node.id,
        name: node.name,
        org_id: node.org_id,
        parent_id: node.parent_id,
        sort_order: node.sort_order,
        path: nextPath.join(" / "),
      })
    }
    node.children?.forEach(child => walk(child, nextPath))
  }
  nodes.forEach(org => org.children?.forEach(child => walk(child, [org.name])))
  return options
}

const flattenDepartmentRecords = (records: DepartmentItem[], orgId: number): DepartmentOption[] => {
  const byParent = new Map<number | null, DepartmentItem[]>()
  records.forEach(item => {
    const key = item.parent_id ?? null
    byParent.set(key, [...(byParent.get(key) || []), item])
  })
  byParent.forEach(siblings => siblings.sort((a, b) => (a.sort_order - b.sort_order) || (a.id - b.id)))
  const options: DepartmentOption[] = []
  const walk = (item: DepartmentItem, path: string[]) => {
    const nextPath = [...path, item.name]
    options.push({ ...item, path: nextPath.join(" / ") })
    ;(byParent.get(item.id) || []).forEach(child => walk(child, nextPath))
  }
  ;(byParent.get(null) || []).forEach(item => walk(item, [getOrgName(orgId)]))
  return options
}

const findDepartmentOption = (departmentId: number) => {
  return departmentOptions.value.find(dept => dept.id === departmentId)
}

const findNodePath = (nodes: OrgTreeNode[], nodeKey: string, path: string[] = []): string[] => {
  for (const node of nodes) {
    const nextPath = [...path, node.name]
    if (node.node_key === nodeKey) return nextPath
    const childPath = findNodePath(node.children || [], nodeKey, nextPath)
    if (childPath.length) return childPath
  }
  return []
}

const findOrgTreeNode = (nodeKey: string | null): OrgTreeNode | null => {
  if (!nodeKey) return null
  const stack = [...organizationTree.value]
  while (stack.length) {
    const node = stack.shift()
    if (!node) continue
    if (node.node_key === nodeKey) return node
    stack.push(...(node.children || []))
  }
  return null
}

const nodeToOrg = (node: OrgTreeNode): OrgItem => ({
  id: node.id,
  name: node.name,
  slug: node.slug || "",
})

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

const fetchOrgTree = async () => {
  if (!canManageEnterprise.value) return
  try {
    const previousKey = selectedOrgNode.value?.node_key || null
    const { data } = await axios.get("/api/organizations/tree")
    organizationTree.value = data
    if (!isSuperAdmin.value) {
      organizations.value = data.map((node: OrgTreeNode) => ({
        id: node.id,
        name: node.name,
        slug: node.slug || "",
      }))
    }
    selectedOrgNode.value = findOrgTreeNode(previousKey) || organizationTree.value[0] || null
  } catch {
    ElMessage.error("组织架构加载失败")
  }
}

const fetchDepartmentsForOrg = async (orgId: number) => {
  const { data } = await axios.get(`/api/organizations/${orgId}/departments`)
  departmentCache.value = { ...departmentCache.value, [orgId]: data }
}

const fetchRoles = async () => {
  if (!canManageRoles.value) return
  const { data } = await axios.get("/api/roles")
  roles.value = data
  if (selectedRole.value) {
    selectedRole.value = roles.value.find(role => role.code === selectedRole.value?.code && role.org_id === selectedRole.value?.org_id) || roles.value[0] || null
  } else {
    selectedRole.value = roles.value[0] || null
  }
}

const fetchAssignableRoles = async () => {
  try {
    const { data } = await axios.get("/api/roles/assignable")
    assignableRoles.value = data
  } catch {
    assignableRoles.value = roles.value.filter(role => role.code === "user")
  }
}

const fetchCatalog = async () => {
  try {
    const { data } = await axios.get("/api/users/permissions/catalog")
    catalog.value = data.catalog
    if (canManageRoles.value) {
      await fetchRoles()
    } else {
      roles.value = data.roles
      selectedRole.value = roles.value[0] || null
    }
    await fetchAssignableRoles()
  } catch {
    ElMessage.error("权限目录加载失败")
  }
}

const fetchAll = async () => {
  await Promise.all([fetchUsers(), fetchOrgs(), fetchOrgTree(), fetchCatalog()])
}

// ── User drawer ────────────────────────────────────────────────────────────────

const openCreateForOrgNode = (node: OrgTreeNode | null = selectedOrgNode.value) => {
  if (!canManageUsers.value) return
  drawerUser.value = null
  drawerTab.value = "info"
  drawerForm.username = ""
  drawerForm.password = ""
  drawerForm.role = "user"
  drawerForm.org_id = node
    ? (node.type === "organization" ? node.id : node.org_id)
    : authStore.profile?.org_id || null
  drawerForm.department_id = node?.type === "department" ? node.id : null
  if (drawerForm.org_id) fetchDepartmentsForOrg(drawerForm.org_id).catch(() => undefined)
  drawerVisible.value = true
}

const openDrawer = async (row: UserItem) => {
  drawerUser.value = row
  drawerTab.value = "info"
  drawerForm.username = row.username
  drawerForm.password = ""
  drawerForm.role = row.role
  drawerForm.department_id = row.department_id || null
  drawerForm.org_id = row.org_id
  if (drawerForm.org_id) fetchDepartmentsForOrg(drawerForm.org_id).catch(() => undefined)
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
      department_id: drawerForm.department_id || null,
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
    await Promise.all([fetchUsers(), fetchOrgTree()])
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
    await Promise.all([fetchUsers(), fetchOrgTree()])
  } catch { /* cancelled */ }
}

const onDrawerOrgChange = async () => {
  drawerForm.department_id = null
  if (drawerForm.org_id) {
    try {
      await fetchDepartmentsForOrg(drawerForm.org_id)
    } catch {
      ElMessage.error("部门列表加载失败")
    }
  }
}

const onDrawerDepartmentChange = () => {
  if (!drawerForm.department_id || drawerForm.org_id) return
  const department = findDepartmentOption(drawerForm.department_id)
  if (department) drawerForm.org_id = department.org_id
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

// ── Role CRUD ────────────────────────────────────────────────────────────────

const openRoleCreate = () => {
  roleIsEdit.value = false
  roleEditId.value = null
  roleForm.code = ""
  roleForm.name = ""
  roleForm.description = ""
  roleForm.org_id = isSuperAdmin.value ? null : (authStore.profile?.org_id || null)
  roleForm.data_scope = "owner"
  roleForm.menu_permissions = seedPermissionMap("menu")
  roleForm.action_permissions = seedPermissionMap("action")
  roleFormTab.value = "menu"
  roleDialogVisible.value = true
}

const openRoleEdit = (role: RoleTemplate) => {
  if (!isRoleEditable(role)) return
  roleIsEdit.value = true
  roleEditId.value = role.id
  roleForm.code = role.code
  roleForm.name = role.name
  roleForm.description = role.description || ""
  roleForm.org_id = role.org_id || null
  roleForm.data_scope = role.data_scope || role.template.data_scope || "owner"
  roleForm.menu_permissions = seedPermissionMap("menu", role.template.menu_permissions)
  roleForm.action_permissions = seedPermissionMap("action", role.template.action_permissions)
  roleFormTab.value = "menu"
  roleDialogVisible.value = true
}

const saveRole = async () => {
  if (!roleForm.code.trim() || !roleForm.name.trim()) {
    ElMessage.warning("请填写角色编码和名称")
    return
  }
  savingRole.value = true
  try {
    const payload = {
      code: roleForm.code.trim(),
      name: roleForm.name.trim(),
      description: roleForm.description.trim() || null,
      org_id: roleForm.org_id,
      data_scope: roleForm.data_scope,
      menu_permissions: roleForm.menu_permissions,
      action_permissions: roleForm.action_permissions,
    }
    if (roleIsEdit.value && roleEditId.value) {
      await axios.put(`/api/roles/${roleEditId.value}`, payload)
      ElMessage.success("角色已更新")
    } else {
      await axios.post("/api/roles", payload)
      ElMessage.success("角色已创建")
    }
    roleDialogVisible.value = false
    await Promise.all([fetchRoles(), fetchAssignableRoles()])
    selectedRole.value = roles.value.find(role => role.code === payload.code) || selectedRole.value
  } catch (e: unknown) {
    const err = e as { response?: { data?: { detail?: string } } }
    ElMessage.error(err.response?.data?.detail || "保存角色失败")
  } finally {
    savingRole.value = false
  }
}

const deleteRole = async (role: RoleTemplate) => {
  if (!isRoleEditable(role)) return
  try {
    await ElMessageBox.confirm(`确定删除角色「${role.name}」？已分配给用户的角色会被系统阻止删除。`, "删除角色", { type: "warning" })
    await axios.delete(`/api/roles/${role.id}`)
    ElMessage.success("角色已删除")
    await Promise.all([fetchRoles(), fetchAssignableRoles()])
  } catch { /* cancelled */ }
}

// ── Org CRUD ───────────────────────────────────────────────────────────────────

const selectOrgNode = (node: OrgTreeNode) => {
  selectedOrgNode.value = node
}

const openOrgCreate = () => {
  if (!canManageOrganizations.value) return
  orgIsEdit.value = false
  orgEditId.value = null
  orgForm.name = ""
  orgForm.slug = ""
  orgDialogVisible.value = true
}

const openOrgEdit = (row: OrgItem) => {
  if (!canManageOrganizations.value) return
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
    await Promise.all([fetchOrgs(), fetchOrgTree()])
  } catch (e: unknown) {
    const err = e as { response?: { data?: { detail?: string } } }
    ElMessage.error(err.response?.data?.detail || "保存失败")
  } finally {
    savingOrg.value = false
  }
}

const deleteOrg = async (id: number) => {
  if (!canManageOrganizations.value) return
  try {
    await ElMessageBox.confirm("确定删除此企业？删除后该企业下的用户将无法登录。", "提示", { type: "warning" })
    await axios.delete(`/api/organizations/${id}`)
    ElMessage.success("已删除")
    await Promise.all([fetchOrgs(), fetchUsers(), fetchOrgTree()])
  } catch { /* cancelled */ }
}

// ── Department CRUD ───────────────────────────────────────────────────────────

const openDepartmentCreate = (baseNode: OrgTreeNode | null) => {
  if (!canManageDepartments.value) {
    ElMessage.warning("无权维护部门")
    return
  }
  const node = baseNode || selectedOrgNode.value
  if (!node) {
    ElMessage.warning("请先选择企业或部门")
    return
  }
  departmentIsEdit.value = false
  departmentEditId.value = null
  departmentForm.org_id = node.type === "organization" ? node.id : node.org_id
  departmentForm.parent_id = node.type === "department" ? node.id : null
  departmentForm.name = ""
  departmentForm.sort_order = 0
  departmentDialogVisible.value = true
}

const openDepartmentEdit = (node: OrgTreeNode) => {
  if (!canManageDepartments.value) return
  if (node.type !== "department") return
  departmentIsEdit.value = true
  departmentEditId.value = node.id
  departmentForm.org_id = node.org_id
  departmentForm.parent_id = node.parent_id
  departmentForm.name = node.name
  departmentForm.sort_order = node.sort_order || 0
  departmentDialogVisible.value = true
}

const saveDepartment = async () => {
  if (!departmentForm.org_id || !departmentForm.name.trim()) {
    ElMessage.warning("请填写部门名称")
    return
  }
  savingDepartment.value = true
  try {
    if (departmentIsEdit.value && departmentEditId.value) {
      await axios.put(`/api/organizations/${departmentForm.org_id}/departments/${departmentEditId.value}`, {
        name: departmentForm.name,
        sort_order: departmentForm.sort_order,
      })
      ElMessage.success("部门已更新")
    } else {
      await axios.post(`/api/organizations/${departmentForm.org_id}/departments`, {
        name: departmentForm.name,
        parent_id: departmentForm.parent_id,
        sort_order: departmentForm.sort_order,
      })
      ElMessage.success("部门已创建")
    }
    departmentDialogVisible.value = false
    delete departmentCache.value[departmentForm.org_id]
    await fetchOrgTree()
  } catch (e: unknown) {
    const err = e as { response?: { data?: { detail?: string } } }
    ElMessage.error(err.response?.data?.detail || "保存失败")
  } finally {
    savingDepartment.value = false
  }
}

const deleteDepartment = async (node: OrgTreeNode) => {
  if (!canManageDepartments.value) return
  if (node.type !== "department") return
  try {
    await ElMessageBox.confirm(`确定删除部门「${node.name}」？如果仍有下级部门或用户，系统会阻止删除。`, "删除部门", { type: "warning" })
    await axios.delete(`/api/organizations/${node.org_id}/departments/${node.id}`)
    ElMessage.success("部门已删除")
    delete departmentCache.value[node.org_id]
    await Promise.all([fetchOrgTree(), fetchUsers()])
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
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
}

.stat-card {
  display: flex;
  align-items: center;
  gap: 14px;
  min-width: 0;
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

@media (max-width: 760px) {
  .stats-row {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .stat-card {
    padding: 12px;
    gap: 10px;
  }

  .stat-icon {
    width: 38px;
    height: 38px;
  }

  .stat-val {
    font-size: 22px;
  }

  .toolbar,
  .toolbar-left,
  .toolbar-right {
    align-items: stretch;
    flex-direction: column;
  }

  .toolbar-left :deep(.el-input),
  .toolbar-left :deep(.el-select),
  .toolbar-right .el-button {
    width: 100% !important;
  }

  .enterprise-layout {
    grid-template-columns: minmax(0, 1fr);
  }

  .enterprise-detail-head,
  .enterprise-panel-head,
  .enterprise-section-head {
    flex-direction: column;
    align-items: stretch;
  }

  .enterprise-section-head :deep(.el-input) {
    width: 100% !important;
  }

  .enterprise-actions {
    justify-content: flex-start;
  }

  .enterprise-metrics {
    grid-template-columns: minmax(0, 1fr);
  }
}

/* ── Table wrap ─────────────────────────────────────────────────────────────── */
.table-wrap {
  background: var(--app-surface);
  border: 1px solid var(--app-border);
  border-radius: 12px;
  overflow: hidden;
  flex: 1;
}

/* ── Enterprise tree ───────────────────────────────────────────────────────── */
.enterprise-layout {
  display: grid;
  grid-template-columns: minmax(280px, 360px) minmax(0, 1fr);
  gap: 16px;
  min-height: 0;
  flex: 1;
}

.enterprise-tree-panel,
.enterprise-detail-panel {
  min-width: 0;
  min-height: 0;
  background: var(--app-surface);
  border: 1px solid var(--app-border);
  border-radius: 12px;
}

.enterprise-tree-panel {
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.enterprise-panel-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 16px;
  border-bottom: 1px solid var(--app-border);
}

.enterprise-panel-title {
  font-size: 14px;
  font-weight: 700;
  color: var(--app-text);
}

.enterprise-panel-sub {
  margin-top: 2px;
  font-size: 12px;
  color: var(--app-text-muted);
}

.org-tree {
  flex: 1;
  padding: 10px;
  overflow: auto;
}

.org-tree-node {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
  min-width: 0;
  padding-right: 6px;
}

.org-tree-icon {
  color: var(--app-primary);
  flex-shrink: 0;
}

.org-node--department .org-tree-icon {
  color: #64748b;
}

.org-tree-label {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  flex: 1;
  min-width: 0;
  font-size: 13px;
}

.org-tree-meta {
  font-size: 11px;
  color: var(--app-text-muted);
  flex-shrink: 0;
}

.enterprise-detail-panel {
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding: 18px;
  overflow: auto;
}

.enterprise-detail-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 16px;
}

.enterprise-title-row {
  display: flex;
  align-items: center;
  gap: 12px;
  min-width: 0;
}

.enterprise-avatar {
  width: 42px;
  height: 42px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  flex-shrink: 0;
}

.enterprise-avatar--organization {
  background: linear-gradient(135deg,#0f766e,#2563eb);
}

.enterprise-avatar--department {
  background: linear-gradient(135deg,#475569,#0f766e);
}

.enterprise-name {
  font-size: 18px;
  font-weight: 700;
  color: var(--app-text);
}

.enterprise-path {
  margin-top: 3px;
  color: var(--app-text-muted);
  font-size: 12px;
}

.enterprise-actions {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 8px;
}

.enterprise-metrics {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
}

.enterprise-metric {
  border: 1px solid var(--app-border);
  border-radius: 10px;
  padding: 12px;
  background: var(--el-fill-color-lighter);
}

.enterprise-metric .metric-label {
  display: block;
  font-size: 12px;
  color: var(--app-text-muted);
  margin-bottom: 4px;
}

.enterprise-metric strong {
  color: var(--app-text);
  font-size: 18px;
}

.enterprise-members {
  display: flex;
  flex-direction: column;
  gap: 12px;
  min-height: 0;
}

.enterprise-section-head {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 12px;
}

.enterprise-section-title {
  font-size: 13px;
  font-weight: 700;
  color: var(--app-text);
}

.enterprise-section-sub {
  margin-top: 3px;
  color: var(--app-text-muted);
  font-size: 12px;
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

.roles-sidebar-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 6px;
}

.sidebar-label {
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.8px;
  text-transform: uppercase;
  color: var(--app-text-muted);
  padding: 0 4px;
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

.role-card-icon {
  width: 22px;
  font-size: 20px;
  color: var(--app-primary);
}
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

.perm-detail-actions {
  display: flex;
  align-items: center;
  gap: 8px;
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

.role-form-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0 14px;
}

.role-dialog :deep(.el-dialog__body) {
  padding-top: 12px;
}

.role-perm-tabs {
  margin-top: 8px;
}

@media (max-width: 760px) {
  .roles-layout {
    flex-direction: column;
  }

  .roles-sidebar {
    width: 100%;
  }

  .role-form-grid {
    grid-template-columns: minmax(0, 1fr);
  }
}

/* ── Role option in select ──────────────────────────────────────────────────── */
.role-opt { display: flex; align-items: center; gap: 10px; }
.role-opt-desc { font-size: 12px; color: var(--app-text-muted); }

.dept-option {
  display: flex;
  flex-direction: column;
  gap: 1px;
  line-height: 1.25;
}

.dept-option small {
  color: var(--app-text-muted);
  font-size: 11px;
}

/* ── Misc ───────────────────────────────────────────────────────────────────── */
.form-tip { font-size: 12px; color: var(--app-text-muted); margin-top: 4px; }
.readonly-line { color: var(--app-text); font-size: 13px; }

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
