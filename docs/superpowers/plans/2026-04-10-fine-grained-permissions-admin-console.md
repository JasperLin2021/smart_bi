# Fine-Grained Permissions And Admin Console Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add fine-grained permission control for menus, actions, and data scope, then replace the split organization/user pages with a single tree-based admin console.

**Architecture:** Keep `User.role` as the base preset role, add user-level permission override fields, and centralize permission resolution in backend helpers. Expose effective permission data through auth/admin APIs and consume it in a merged frontend admin console with a left tree and right detail editor.

**Tech Stack:** FastAPI, SQLAlchemy, Pydantic, Vue 3, Pinia, Element Plus, pytest

---

### Task 1: Define Permission Model And Tests

**Files:**
- Modify: `backend/app/core/permissions.py`
- Modify: `backend/app/models/user.py`
- Modify: `backend/app/schemas/user.py`
- Test: `backend/tests/test_permissions.py`

- [ ] **Step 1: Write the failing permission-resolution tests**

```python
def test_resolve_permissions_from_role_defaults():
    ...

def test_user_overrides_replace_role_defaults():
    ...

def test_super_admin_always_gets_full_access():
    ...
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && DATABASE_URL='sqlite:///./smartbi.db' .venv/bin/pytest tests/test_permissions.py -q`
Expected: FAIL because resolver helpers and new user fields do not exist yet.

- [ ] **Step 3: Add user permission fields and resolver helpers**

Implement minimal support for:

- `data_scope`
- `permission_override_enabled`
- JSON-backed `menu_permissions`
- JSON-backed `action_permissions`
- role template lookup
- effective permission merge

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && DATABASE_URL='sqlite:///./smartbi.db' .venv/bin/pytest tests/test_permissions.py -q`
Expected: PASS

- [ ] **Step 5: Refactor helper names and constants**

Keep permission keys centralized and readable.

- [ ] **Step 6: Commit**

```bash
git add backend/app/core/permissions.py backend/app/models/user.py backend/app/schemas/user.py backend/tests/test_permissions.py
git commit -m "feat: add fine-grained permission model"
```

### Task 2: Expose Effective Permissions In Auth Profile

**Files:**
- Modify: `backend/app/schemas/auth.py`
- Modify: `backend/app/api/auth.py`
- Test: `backend/tests/test_auth_profile_permissions.py`

- [ ] **Step 1: Write the failing auth profile test**

```python
def test_me_returns_effective_permissions_and_scope(client, db_session):
    ...
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && DATABASE_URL='sqlite:///./smartbi.db' .venv/bin/pytest tests/test_auth_profile_permissions.py -q`
Expected: FAIL because `/api/auth/me` does not return permission payload.

- [ ] **Step 3: Update auth schema and endpoint**

Return:

- `data_scope`
- `permission_override_enabled`
- `menu_permissions`
- `action_permissions`

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && DATABASE_URL='sqlite:///./smartbi.db' .venv/bin/pytest tests/test_auth_profile_permissions.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/schemas/auth.py backend/app/api/auth.py backend/tests/test_auth_profile_permissions.py
git commit -m "feat: expose effective permissions in auth profile"
```

### Task 3: Add Startup Migration For User Permission Fields

**Files:**
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_startup_permission_migrations.py`

- [ ] **Step 1: Write the failing startup migration test**

```python
def test_startup_adds_permission_columns_for_existing_users():
    ...
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && DATABASE_URL='sqlite:///./smartbi.db' .venv/bin/pytest tests/test_startup_permission_migrations.py -q`
Expected: FAIL because startup does not add the new columns yet.

- [ ] **Step 3: Add lightweight startup migrations**

Ensure missing `users` columns are added and existing users receive default scope values by role.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && DATABASE_URL='sqlite:///./smartbi.db' .venv/bin/pytest tests/test_startup_permission_migrations.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/main.py backend/tests/test_startup_permission_migrations.py
git commit -m "feat: migrate user permission fields on startup"
```

### Task 4: Refactor User APIs For Scope And Overrides

**Files:**
- Modify: `backend/app/api/users.py`
- Modify: `backend/app/schemas/user.py`
- Test: `backend/tests/test_user_permissions_api.py`

- [ ] **Step 1: Write the failing user API tests**

```python
def test_super_admin_can_set_user_overrides(client, db_session):
    ...

def test_org_admin_cannot_grant_all_scope_or_platform_permissions(client, db_session):
    ...
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && DATABASE_URL='sqlite:///./smartbi.db' .venv/bin/pytest tests/test_user_permissions_api.py -q`
Expected: FAIL because create/update payloads and policy checks are incomplete.

- [ ] **Step 3: Extend user schemas and endpoint validation**

Support editing:

- base role
- scope
- override toggle
- menu overrides
- action overrides

Apply org-boundary restrictions for org admins.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && DATABASE_URL='sqlite:///./smartbi.db' .venv/bin/pytest tests/test_user_permissions_api.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/api/users.py backend/app/schemas/user.py backend/tests/test_user_permissions_api.py
git commit -m "feat: support user permission overrides"
```

### Task 5: Add Admin Console Tree API

**Files:**
- Modify: `backend/app/api/organization.py`
- Modify: `backend/app/api/routes.py`
- Test: `backend/tests/test_admin_console_tree.py`

- [ ] **Step 1: Write the failing admin tree tests**

```python
def test_super_admin_sees_all_orgs_and_users_in_tree(client, db_session):
    ...

def test_org_admin_sees_only_own_org_branch(client, db_session):
    ...
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && DATABASE_URL='sqlite:///./smartbi.db' .venv/bin/pytest tests/test_admin_console_tree.py -q`
Expected: FAIL because the tree endpoint does not exist yet.

- [ ] **Step 3: Implement tree endpoint**

Add a dedicated endpoint returning organization nodes with user children and enforce access through effective permissions plus scope.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && DATABASE_URL='sqlite:///./smartbi.db' .venv/bin/pytest tests/test_admin_console_tree.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/api/organization.py backend/app/api/routes.py backend/tests/test_admin_console_tree.py
git commit -m "feat: add admin console tree endpoint"
```

### Task 6: Update Frontend Auth Store And Route Guards

**Files:**
- Modify: `frontend/src/store/auth.ts`
- Modify: `frontend/src/router/index.ts`
- Modify: `frontend/src/layouts/MainLayout.vue`

- [ ] **Step 1: Write the failing frontend permission expectations**

If an existing frontend test setup is present, add route/menu tests there. Otherwise document the first verification target and create the minimal route/menu test scaffold needed for this feature.

- [ ] **Step 2: Run test to verify it fails**

Run the targeted frontend test command for the new route/menu checks.
Expected: FAIL because profile permissions are not yet used by routing and menu rendering.

- [ ] **Step 3: Extend frontend auth model**

Add:

- `data_scope`
- `permission_override_enabled`
- `menu_permissions`
- `action_permissions`
- convenience helpers like `hasMenuPermission()` and `hasActionPermission()`

- [ ] **Step 4: Replace role-only route guards and sidebar visibility**

Use effective menu permissions instead of direct `role` checks for the merged admin page and other gated routes.

- [ ] **Step 5: Run test to verify it passes**

Run the same targeted frontend tests and confirm PASS.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/store/auth.ts frontend/src/router/index.ts frontend/src/layouts/MainLayout.vue
git commit -m "feat: use effective permissions in frontend navigation"
```

### Task 7: Build The Merged Admin Console Page

**Files:**
- Add or Replace: `frontend/src/views/AdminConsole.vue`
- Modify: `frontend/src/router/index.ts`
- Remove or stop routing to: `frontend/src/views/UserManagement.vue`
- Remove or stop routing to: `frontend/src/views/OrgManagement.vue`

- [ ] **Step 1: Write the failing UI behavior tests**

Cover at least:

- organization/user tree rendering
- node selection switching the detail panel
- user editor showing role, scope, and override controls

- [ ] **Step 2: Run test to verify it fails**

Run the targeted frontend tests for the new admin console.
Expected: FAIL because the page and interactions do not exist yet.

- [ ] **Step 3: Implement the merged page**

Build:

- left organization/user tree
- right organization detail mode
- right user detail mode
- create/edit dialogs or inline forms
- permission checkbox groups with inherited-state display

- [ ] **Step 4: Update route and navigation labels**

Replace `/user-management` and `/org-management` with one route such as `/admin-console`.

- [ ] **Step 5: Run test to verify it passes**

Run the same targeted frontend tests and confirm PASS.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/views/AdminConsole.vue frontend/src/router/index.ts frontend/src/layouts/MainLayout.vue
git commit -m "feat: merge org and user management into admin console"
```

### Task 8: End-To-End Permission And UI Verification

**Files:**
- Modify: relevant backend/frontend files from earlier tasks only if defects are found
- Test: backend and frontend targeted suites

- [ ] **Step 1: Run backend targeted suites**

Run:

```bash
cd backend && DATABASE_URL='sqlite:///./smartbi.db' .venv/bin/pytest \
  tests/test_permissions.py \
  tests/test_auth_profile_permissions.py \
  tests/test_startup_permission_migrations.py \
  tests/test_user_permissions_api.py \
  tests/test_admin_console_tree.py -q
```

Expected: all PASS

- [ ] **Step 2: Run frontend targeted suite**

Run the frontend test command covering auth store, route guard, and admin console behaviors.
Expected: PASS

- [ ] **Step 3: Run app-level smoke verification**

Check:

- login as `admin`
- merged admin console loads
- tree renders org/user nodes
- user permission edits persist

- [ ] **Step 4: Rebuild graphify code graph**

Run:

```bash
python3 -c "from graphify.watch import _rebuild_code; from pathlib import Path; _rebuild_code(Path('.'))"
```

- [ ] **Step 5: Commit final fixes**

```bash
git add backend frontend graphify-out
git commit -m "feat: add fine-grained permissions and admin console"
```
