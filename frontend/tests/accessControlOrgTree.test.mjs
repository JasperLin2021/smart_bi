import assert from "node:assert/strict"
import { existsSync, readFileSync } from "node:fs"
import { resolve } from "node:path"
import { test } from "node:test"

const root = resolve(import.meta.dirname, "..")
const read = (path) => readFileSync(resolve(root, path), "utf8")

test("enterprise management uses an organization and department tree", () => {
  const view = read("src/views/AccessControl.vue")

  assert.match(view, /activeTab\s*=\s*ref<"orgs"\s*\|\s*"roles">\("orgs"\)/)
  assert.match(view, /enterprise-tree-panel/)
  assert.match(view, /<el-tree/)
  assert.match(view, /orgTreeData/)
  assert.match(view, /\/api\/organizations\/tree/)
  assert.match(view, /新建下级部门/)
  assert.match(view, /重命名部门/)
  assert.match(view, /删除部门/)
  assert.match(view, /org-node--department/)
  assert.match(view, /department_count/)
  assert.doesNotMatch(view, /v-show="activeTab === 'orgs'"[\s\S]*?<el-table :data="filteredOrgs"/)
})

test("enterprise management absorbs standalone user management", () => {
  const router = read("src/router/index.ts")
  const view = read("src/views/AccessControl.vue")

  assert.match(router, /path:\s*"\/user-management",\s*redirect:\s*"\/access-control"/)
  assert.doesNotMatch(view, /key:\s*"users",\s*label:\s*"用户管理"/)
  assert.doesNotMatch(view, /v-show="activeTab === 'users'"/)
  assert.match(view, /key:\s*"orgs",\s*label:\s*"企业管理"/)
  assert.match(view, /新增成员/)
  assert.match(view, /openCreateForOrgNode/)
  assert.match(view, /selectedNodeUsersFiltered/)
  assert.match(view, /deleteUser\(row\.id\)/)
  assert.equal(existsSync(resolve(root, "src/views/UserManagement.vue")), false)
  assert.equal(existsSync(resolve(root, "src/views/OrgManagement.vue")), false)
  assert.equal(existsSync(resolve(root, "src/views/RoleManagement.vue")), false)
})

test("user drawer binds users to department entities instead of free text only", () => {
  const view = read("src/views/AccessControl.vue")

  assert.match(view, /department_id/)
  assert.match(view, /departmentOptionsForDrawerOrg/)
  assert.match(view, /placeholder="选择部门"/)
  assert.match(view, /\/api\/organizations\/\$\{orgId\}\/departments/)
  assert.doesNotMatch(view, /<el-input v-model="drawerForm\.department" placeholder="如：数据分析部" \/>/)
})
