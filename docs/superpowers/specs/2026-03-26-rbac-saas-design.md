# SaaS RBAC Design Spec

## Overview

Transform Smart BI into a multi-tenant SaaS platform with 3-tier Role-Based Access Control (RBAC).

## Roles

| Role | Description | Scope |
|------|-------------|-------|
| `user` | 普通用户 | Own org datasources, own queries |
| `org_admin` | 企业管理员 | Own org users + datasources + query history |
| `super_admin` | 超级管理员 | All orgs, all users, all resources |

## Data Model

### New: Organization Table

```sql
CREATE TABLE organizations (
    id SERIAL PRIMARY KEY,
    name VARCHAR(128) NOT NULL,
    slug VARCHAR(64) UNIQUE NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);
```

### Modified: User Table

```sql
ALTER TABLE users ADD COLUMN org_id INTEGER REFERENCES organizations(id);
-- role already exists, values: "user" | "org_admin" | "super_admin"
-- super_admin has org_id = NULL
```

### Modified: DataSource Table

```sql
ALTER TABLE datasources ADD COLUMN org_id INTEGER REFERENCES organizations(id);
```

## Permission Matrix

| Resource | Action | user | org_admin | super_admin |
|----------|--------|------|-----------|-------------|
| DataSource | List | Own org | Own org | All |
| DataSource | Create/Edit/Delete | Own org | Own org | All |
| User | List | - | Own org | All |
| User | Create/Edit/Delete | - | Own org | All |
| Query | Execute | Own org DS | Own org DS | All |
| Query | View History | Own only | Own org | All |
| Organization | CRUD | - | - | All |
| LLM Settings | CRUD | - | - | All |

## API Changes

### New Endpoints

```
# Organization management (super_admin only)
GET    /api/organizations
POST   /api/organizations
PUT    /api/organizations/{id}
DELETE /api/organizations/{id}

# User management (org_admin + super_admin)
GET    /api/users
POST   /api/users
PUT    /api/users/{id}
DELETE /api/users/{id}
```

### Modified Endpoints

All existing endpoints add org-based filtering:

- `GET /api/datasources` - filter by `user.org_id`
- `GET /api/query/history` - filter by org for org_admin
- `POST /api/query` - validate datasource belongs to user's org

### Permission Dependencies

```python
# app/core/permissions.py

def require_role(allowed_roles: list[str]):
    """Decorator to check user role"""
    
def require_super_admin(user: User) -> User:
    """Raises 403 if not super_admin"""
    
def require_org_admin_or_above(user: User) -> User:
    """Raises 403 if role is 'user'"""
    
def check_org_access(user: User, org_id: int) -> bool:
    """Returns True if user can access this org's resources"""
```

## Seed Data

### Organizations

| id | name | slug |
|----|------|------|
| 1 | Nexteer | nexteer |
| 2 | 嘉盛半导体 | carsem |

### Users

| username | password | role | org_id |
|----------|----------|------|--------|
| admin | admin123 | super_admin | NULL |
| nexteer_admin | nexteer123 | org_admin | 1 |
| nexteer | nexteer123 | user | 1 |
| carsem_admin | carsem123 | org_admin | 2 |
| carsem | carsem123 | user | 2 |

### Data Migration

- Existing Excel datasource → `org_id = 2` (Carsem)
- Existing users → `org_id = 1`, `role = "user"`

## Frontend Changes

### Navigation by Role

| Menu Item | user | org_admin | super_admin |
|-----------|------|-----------|-------------|
| 智能查询 | ✓ | ✓ | ✓ |
| Dashboard | ✓ | ✓ | ✓ |
| 数据源管理 | ✓ | ✓ | ✓ |
| 用户管理 | - | ✓ | ✓ |
| 企业管理 | - | - | ✓ |
| LLM设置 | - | - | ✓ |

### New Pages

1. `/users` - User management (org_admin+)
2. `/organizations` - Organization management (super_admin)

### Auth Store Updates

```typescript
interface UserProfile {
  id: number
  username: string
  role: 'user' | 'org_admin' | 'super_admin'
  org_id: number | null
  org_name: string | null
}
```

### Route Guards

- Add `meta.requiredRole` to routes
- Check in `router.beforeEach`
- Redirect unauthorized to `/dashboard`

## File Changes Summary

### Backend

| File | Change |
|------|--------|
| `models/organization.py` | NEW - Organization model |
| `models/user.py` | Add org_id FK |
| `models/datasource.py` | Add org_id FK |
| `schemas/organization.py` | NEW - Pydantic schemas |
| `schemas/user.py` | NEW - User CRUD schemas |
| `schemas/auth.py` | Update UserProfile |
| `api/organization.py` | NEW - Org CRUD endpoints |
| `api/users.py` | NEW - User CRUD endpoints |
| `api/datasource.py` | Add org filtering |
| `api/query.py` | Add org validation |
| `api/auth.py` | Return org info in profile |
| `core/permissions.py` | NEW - Permission utilities |
| `main.py` | Add migrations, seed data |

### Frontend

| File | Change |
|------|--------|
| `store/auth.ts` | Update UserProfile type |
| `router/index.ts` | Add route guards, new routes |
| `layouts/MainLayout.vue` | Conditional menu items |
| `views/UserManagement.vue` | NEW - User CRUD page |
| `views/OrgManagement.vue` | NEW - Org CRUD page |
