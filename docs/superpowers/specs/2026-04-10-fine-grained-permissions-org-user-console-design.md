# Fine-Grained Permissions And Org/User Console Design

## Overview

Refine the current 3-role model into a practical hybrid model:

- Keep preset roles as the default permission source.
- Allow per-user permission overrides through explicit checkbox-based grants.
- Support three control axes at the same time:
  - Menu visibility
  - Action-level authorization
  - Data scope filtering

At the same time, replace the separate "用户管理" and "企业管理" pages with a single organization-and-user console that uses a left-side tree and a right-side detail editor.

## Goals

1. Preserve the current `user` / `org_admin` / `super_admin` role semantics.
2. Make authorization checks explicit and reusable instead of scattering `role == ...` branches across endpoints.
3. Support preset roles with user-level overrides.
4. Support data scopes:
   - `all`
   - `org`
   - `owner`
5. Unify organization and user management into one page that can scale later to departments, datasource grants, and more refined policies.

## Non-Goals

- Full many-to-many RBAC with separate role tables and permission tables.
- Department hierarchy in this iteration.
- Datasource-specific allowlists in this iteration.
- Reworking unrelated navigation or business flows.

## Current Problems

### Permission Model Is Too Coarse

Current backend authorization is mostly based on three role checks in `backend/app/core/permissions.py` and endpoint-local branching. That works for broad tenancy boundaries, but it cannot express:

- A user who can view user management but cannot delete users.
- An org admin who can manage alerts but not LLM settings.
- A user who can edit only their own resources, while another role peer can edit all org resources.

### Frontend Management UX Is Split

`frontend/src/views/UserManagement.vue` and `frontend/src/views/OrgManagement.vue` are separated even though the operator is managing the same tenancy structure. This causes duplicated list/detail flow and leaves no obvious place for permission editing.

## Recommended Approach

Use a hybrid authorization design:

1. `User.role` remains the base role.
2. Add a per-user permission profile that stores override state.
3. Introduce a central permission resolver that computes effective permissions from:
   - preset role template
   - explicit user overrides
   - data scope
4. Migrate backend endpoints and frontend route/menu checks to use the resolved permission set.

This keeps the data model simple enough for the current project while still supporting flexible grants.

## Permission Model

### Base Roles

The system keeps these preset roles:

| Role | Purpose | Default scope |
|------|---------|---------------|
| `user` | Standard business user | `owner` or narrow org-level defaults where needed |
| `org_admin` | Tenant operator | `org` |
| `super_admin` | Platform operator | `all` |

### Permission Categories

Permissions are grouped into three buckets.

#### 1. Menu Permissions

Menu permissions control page visibility and route entry.

Suggested menu keys:

- `dashboard.view`
- `smart_query.view`
- `datasource.view`
- `metric.view`
- `alert.view`
- `admin_console.view`
- `llm_settings.view`

`admin_console.view` replaces the old split-page visibility for users and organizations.

#### 2. Action Permissions

Action permissions control what the user may do inside a feature.

Suggested action keys for this iteration:

- `organization.read`
- `organization.create`
- `organization.update`
- `organization.delete`
- `user.read`
- `user.create`
- `user.update`
- `user.delete`
- `user.permission.update`
- `datasource.read`
- `datasource.create`
- `datasource.update`
- `datasource.delete`
- `metric.read`
- `metric.create`
- `metric.update`
- `metric.delete`
- `alert.read`
- `alert.create`
- `alert.update`
- `alert.delete`
- `llm_settings.read`
- `llm_settings.update`

The set should live centrally in backend code so both defaults and UI rendering use the same vocabulary.

#### 3. Data Scope

Use one scope value per user for resource filtering:

- `all`: all tenants and all owned data
- `org`: resources within the current organization
- `owner`: only resources created by or assigned to the current user

For resources that do not yet have an ownership field, `owner` should degrade safely:

- if ownership is known, filter by owner
- if ownership is not modeled yet, deny mutating operations and only allow explicitly safe reads

## Storage Model

### User Table Changes

Extend `users` with fields that can represent override state without creating a full RBAC schema:

- `data_scope VARCHAR(16)` with values `all | org | owner`
- `menu_permissions TEXT` storing JSON
- `action_permissions TEXT` storing JSON
- `permission_override_enabled BOOLEAN`

The JSON payload should store explicit allow/deny decisions only, not the whole effective matrix. Effective permissions are computed at runtime.

Example shape:

```json
{
  "dashboard.view": true,
  "llm_settings.view": false
}
```

This is enough for the current codebase and SQLite deployment.

## Effective Permission Resolution

Add a resolver in `backend/app/core/permissions.py` with responsibilities:

1. Load preset permissions by role.
2. Merge in explicit user overrides.
3. Return a normalized permission object.
4. Provide helpers such as:
   - `require_menu(user, "admin_console.view")`
   - `require_action(user, "user.update")`
   - `can_access_org(user, org_id)`
   - `apply_scope_filter(query, model, user, owner_field=..., org_field=...)`

### Merge Rules

1. Start from preset role permissions.
2. Apply explicit user overrides on top.
3. `super_admin` always resolves to full access unless future product direction explicitly changes this.

This keeps preset roles understandable while still allowing exceptions.

## Preset Role Templates

### `user`

- Menus:
  - `dashboard.view`
  - `smart_query.view`
  - `datasource.view`
  - `metric.view`
  - `alert.view`
- Actions:
  - read access to normal business resources
  - limited create/update where already allowed by product policy
- Scope:
  - default `owner`

### `org_admin`

- Menus:
  - all business menus
  - `admin_console.view`
- Actions:
  - full user management inside own org
  - full org-scoped business resource management
  - no platform-wide organization deletion or LLM global admin by default
- Scope:
  - default `org`

### `super_admin`

- Menus:
  - all menus
- Actions:
  - all actions
- Scope:
  - `all`

## Backend API Changes

### Auth/Profile

Expand the auth profile response to include effective permission info needed by the frontend:

- `role`
- `org_id`
- `org_name`
- `data_scope`
- `menu_permissions`
- `action_permissions`
- `permission_override_enabled`

The frontend should not recompute permissions from role names alone.

### User APIs

Update user create/update/list/detail APIs so operators can manage:

- base role
- data scope
- permission override toggle
- explicit menu overrides
- explicit action overrides

Org admins may update users only inside their org and never elevate to `all` scope or platform-only permissions unless explicitly intended in policy.

### Organization APIs

Keep organization CRUD platform-scoped, but expose data required by the merged admin console, including child users per organization or a companion tree endpoint.

### New Admin Console Tree Endpoint

Add a dedicated endpoint that returns organization and user nodes in one payload, for example:

`GET /api/admin-console/tree`

Response shape:

```json
[
  {
    "type": "organization",
    "id": 2,
    "label": "嘉盛半导体",
    "slug": "carsem",
    "children": [
      {
        "type": "user",
        "id": 7,
        "label": "carsem_admin",
        "role": "org_admin"
      }
    ]
  }
]
```

This avoids two independent requests plus frontend-side tree merging.

## Authorization Refactor Strategy

Replace direct role checks in endpoints with intent-based checks.

Examples:

- `require_super_admin(current_user)` for platform-only operations stays valid where the action is truly platform-only.
- `require_org_admin_or_above(current_user)` should gradually be replaced by `require_action(current_user, "...")`.
- Query/data APIs should use scope-aware filtering instead of role-only branching.

This refactor should start with user and organization management, then extend to datasource, metrics, alerts, and other administrative surfaces.

## Frontend Console Design

### Page Structure

Create a single admin console page:

- Left side: organization/user tree
- Right side: detail panel

The selected node determines the right panel mode.

### Left Tree

Tree behavior:

- Root level: organizations
- Child level: users under each organization
- Optional synthetic group for global users if any remain without `org_id`
- Search by organization name or username
- Quick actions near the tree header:
  - create organization
  - create user under selected organization
  - refresh tree

### Right Detail Panel

#### When Organization Is Selected

Show:

- organization basic info
- child user summary
- create user action
- edit/delete organization actions where permitted

#### When User Is Selected

Show:

- username
- password reset
- base role
- organization
- data scope selector
- "use preset role only" toggle
- menu permission checkbox groups
- action permission checkbox groups

When overrides are disabled, the checkbox area should render the preset permissions as read-only or visually inherited.

### Route And Navigation

Replace separate routes for user and organization management with one admin console route. The sidebar label can be:

- `组织与用户`
- or `管理控制台`

Recommendation: `组织与用户`, because it is concrete and easy to discover.

## UI Permission Rules

The frontend should enforce permissions in three places:

1. Route access
2. Sidebar/menu rendering
3. Button and form-state rendering

The backend remains the source of truth. Frontend checks are only for UX.

## Data Scope Behavior

### `all`

- no org restriction
- all resources visible according to action rights

### `org`

- only current org resources visible
- all user/organization console operations limited to current org unless platform-only

### `owner`

- business resource views and mutations limited to owned records
- user/organization admin operations should normally be disabled unless separately granted

This means scope is not the only gate; action permission still decides whether the action is allowed at all.

## Migration Plan

### Database Migration

On startup, add missing user permission columns if absent. Keep the project's current lightweight migration style.

### Seed Defaults

For existing users:

- `super_admin` => `data_scope = all`
- `org_admin` => `data_scope = org`
- `user` => `data_scope = owner`
- permission override fields empty and disabled

This preserves current behavior before any per-user customization.

## Testing Strategy

### Backend

Add tests for:

- effective permission resolution from role-only users
- explicit allow/deny overrides
- data scope enforcement for `all`, `org`, `owner`
- org admin restrictions when editing users outside own org
- merged admin-console tree payload visibility

### Frontend

Add tests for:

- tree rendering from mixed organization/user payload
- right-panel switching by node type
- inherited permission display
- override-enabled editing state
- conditional button visibility from effective permissions

## File Impact Summary

### Backend

- Modify `backend/app/models/user.py`
- Modify `backend/app/schemas/user.py`
- Modify `backend/app/schemas/auth.py`
- Modify `backend/app/api/auth.py`
- Modify `backend/app/api/users.py`
- Modify `backend/app/api/organization.py`
- Modify `backend/app/core/permissions.py`
- Modify `backend/app/main.py`
- Add `backend/tests/...` for permission resolution and admin console APIs

### Frontend

- Modify `frontend/src/store/auth.ts`
- Modify `frontend/src/router/index.ts`
- Modify `frontend/src/layouts/MainLayout.vue`
- Replace `frontend/src/views/UserManagement.vue`
- Replace `frontend/src/views/OrgManagement.vue`
- Add a merged admin console view and related local components if needed

## Risks

1. Some business resources may not yet have a clear owner field, which weakens `owner` scope until the model is filled in.
2. If permission keys are not centralized, backend and frontend may drift.
3. A naive UI with too many checkboxes can become hard to operate; grouping and inherited-state presentation are necessary.

## Recommendation

Implement this in two passes:

1. Build the permission foundation and merge the management UI around user and organization administration first.
2. Extend the same permission resolver to datasource, metric, alert, and other admin surfaces after the foundation is stable.

This keeps the first delivery focused while establishing the model needed for finer control across the rest of the project.
