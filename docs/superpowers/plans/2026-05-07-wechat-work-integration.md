# WeChat Work Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Enterprise WeChat login, organization/department permission mapping, and unified WeChat message delivery for alerts, reports, action items, comments, dashboard sharing, and approval reminders.

**Architecture:** Keep Smart BI as the source of authorization truth. WeChat Work supplies external identity, corporation, department, and message transport data; local `User`, `Organization`, role templates, and permission override fields remain authoritative after mapping. Add focused integration models, a WeChat client wrapper, a dispatcher service, backend APIs, and a system-admin frontend page.

**Tech Stack:** FastAPI, SQLAlchemy, Alembic, httpx, Pydantic, Vue 3, Pinia, Element Plus, Node test runner, pytest.

---

## File Structure

- Create `backend/app/models/integration.py`: integration config, org binding, external identity, permission mapping, message delivery models.
- Modify `backend/app/db/base.py`: import integration models for metadata creation.
- Modify `backend/app/main.py`: import models and add legacy-safe `_ensure_column`/table creation only if needed by current startup pattern.
- Create `backend/alembic/versions/20260507_0016_wechat_work_integration.py`: migration for new tables and indexes.
- Create `backend/app/schemas/integration.py`: request/response schemas for config, bindings, mappings, and deliveries.
- Create `backend/app/core/wechat_work.py`: small WeChat Work API client and mockable interface.
- Create `backend/app/core/external_auth.py`: bind/create users and apply department mappings.
- Create `backend/app/core/message_dispatcher.py`: standard event model and WeChat delivery logic.
- Create `backend/app/api/integrations.py`: admin config, mapping, delivery, test message APIs.
- Modify `backend/app/api/auth.py`: WeChat login URL and callback endpoints.
- Modify `backend/app/api/routes.py`: register integration router.
- Modify `backend/app/core/alert_evaluator.py` and `backend/app/core/alert_scheduler.py`: route alert/report notifications through dispatcher while keeping existing robot behavior.
- Modify `backend/app/api/action_items.py`, `backend/app/api/comments.py`, `backend/app/api/dashboards.py`: emit message events.
- Modify `frontend/src/views/Login.vue`: add WeChat Work login button and callback error handling.
- Create `frontend/src/views/WechatWorkIntegration.vue`: system-admin management page.
- Modify `frontend/src/router/index.ts`: add route.
- Modify `frontend/src/layouts/MainLayout.vue`: add system-admin menu item.
- Create/modify tests:
  - `backend/tests/test_wechat_work_auth.py`
  - `backend/tests/test_wechat_work_mappings.py`
  - `backend/tests/test_message_dispatcher.py`
  - `backend/tests/test_wechat_work_api.py`
  - `frontend/tests/wechatWorkIntegration.test.mjs`

---

### Task 1: Data Models And Migrations

**Files:**
- Create: `backend/app/models/integration.py`
- Modify: `backend/app/db/base.py`
- Modify: `backend/app/main.py`
- Create: `backend/alembic/versions/20260507_0016_wechat_work_integration.py`
- Test: `backend/tests/test_wechat_work_mappings.py`

- [ ] **Step 1: Write the failing model test**

Add a test that imports the models, creates an `IntegrationConfig`, `ExternalOrgBinding`, `ExternalIdentity`, `ExternalPermissionMapping`, and `MessageDelivery`, then asserts unique provider/corp identity fields are present.

Run:

```bash
cd backend
uv run pytest tests/test_wechat_work_mappings.py -q
```

Expected: FAIL because `app.models.integration` does not exist.

- [ ] **Step 2: Add SQLAlchemy models**

Create `backend/app/models/integration.py` with:

```python
from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from app.db.base_class import Base

class IntegrationConfig(Base):
    __tablename__ = "integration_configs"
    id = Column(Integer, primary_key=True, index=True)
    provider = Column(String(32), nullable=False, index=True)
    name = Column(String(128), nullable=False)
    enabled = Column(Boolean, default=False, nullable=False)
    corp_id = Column(String(128), nullable=True, index=True)
    agent_id = Column(String(128), nullable=True)
    app_secret = Column(String(512), nullable=True)
    callback_url = Column(String(512), nullable=True)
    robot_webhook_url = Column(String(512), nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

class ExternalOrgBinding(Base):
    __tablename__ = "external_org_bindings"
    __table_args__ = (UniqueConstraint("provider", "external_corp_id", name="uq_external_org_provider_corp"),)
    id = Column(Integer, primary_key=True, index=True)
    provider = Column(String(32), nullable=False, index=True)
    external_corp_id = Column(String(128), nullable=False, index=True)
    org_id = Column(Integer, ForeignKey("organizations.id"), nullable=False, index=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

class ExternalIdentity(Base):
    __tablename__ = "external_identities"
    __table_args__ = (UniqueConstraint("provider", "external_corp_id", "external_user_id", name="uq_external_identity"),)
    id = Column(Integer, primary_key=True, index=True)
    provider = Column(String(32), nullable=False, index=True)
    external_corp_id = Column(String(128), nullable=False, index=True)
    external_user_id = Column(String(128), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    display_name = Column(String(128), nullable=True)
    email = Column(String(256), nullable=True)
    mobile = Column(String(64), nullable=True)
    department_ids_json = Column(Text, nullable=True)
    last_login_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

class ExternalPermissionMapping(Base):
    __tablename__ = "external_permission_mappings"
    id = Column(Integer, primary_key=True, index=True)
    provider = Column(String(32), nullable=False, index=True)
    external_corp_id = Column(String(128), nullable=False, index=True)
    external_department_id = Column(String(128), nullable=False, index=True)
    org_id = Column(Integer, ForeignKey("organizations.id"), nullable=False, index=True)
    role = Column(String(32), default="user", nullable=False)
    data_scope = Column(String(32), nullable=True)
    menu_permissions = Column(Text, nullable=True)
    action_permissions = Column(Text, nullable=True)
    priority = Column(Integer, default=100, nullable=False)
    enabled = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

class MessageDelivery(Base):
    __tablename__ = "message_deliveries"
    id = Column(Integer, primary_key=True, index=True)
    provider = Column(String(32), nullable=False, index=True)
    channel = Column(String(32), nullable=False, index=True)
    event_type = Column(String(64), nullable=False, index=True)
    recipient_user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    recipient_external_user_id = Column(String(128), nullable=True)
    org_id = Column(Integer, nullable=True, index=True)
    title = Column(String(256), nullable=False)
    content = Column(Text, nullable=False)
    link_url = Column(String(512), nullable=True)
    status = Column(String(32), default="pending", nullable=False, index=True)
    error_message = Column(Text, nullable=True)
    retry_count = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime, server_default=func.now())
    sent_at = Column(DateTime, nullable=True)
```

- [ ] **Step 3: Register models and migration**

Import the models in `backend/app/db/base.py` and `backend/app/main.py`. Add Alembic migration creating the same tables with `checkfirst` style matching existing migrations.

- [ ] **Step 4: Run tests**

Run:

```bash
cd backend
uv run pytest tests/test_wechat_work_mappings.py -q
```

Expected: PASS.

---

### Task 2: Schemas And Admin Integration API

**Files:**
- Create: `backend/app/schemas/integration.py`
- Create: `backend/app/api/integrations.py`
- Modify: `backend/app/api/routes.py`
- Test: `backend/tests/test_wechat_work_api.py`

- [ ] **Step 1: Write failing API tests**

Test that a super admin can save/read WeChat config, secret is not returned, org bindings can be listed/created/deleted, and permission mappings reject `super_admin`.

Run:

```bash
cd backend
uv run pytest tests/test_wechat_work_api.py -q
```

Expected: FAIL because `/api/integrations/wechat-work/config` does not exist.

- [ ] **Step 2: Add schemas**

Create config, binding, mapping, and delivery schemas. Use `app_secret_set: bool` on output and `app_secret: str | None` on update.

- [ ] **Step 3: Add router**

Create `router = APIRouter(prefix="/integrations/wechat-work", tags=["integrations"])`.

Implement:

- `GET /config`
- `PUT /config`
- `GET /org-bindings`
- `POST /org-bindings`
- `DELETE /org-bindings/{binding_id}`
- `GET /permission-mappings`
- `POST /permission-mappings`
- `PUT /permission-mappings/{mapping_id}`
- `DELETE /permission-mappings/{mapping_id}`
- `GET /message-deliveries`

Guard all endpoints with `require_super_admin(current_user)`.

- [ ] **Step 4: Register router**

Modify `backend/app/api/routes.py`:

```python
from app.api.integrations import router as integrations_router
api_router.include_router(integrations_router)
```

- [ ] **Step 5: Run tests**

Run:

```bash
cd backend
uv run pytest tests/test_wechat_work_api.py -q
```

Expected: PASS.

---

### Task 3: WeChat Work Client

**Files:**
- Create: `backend/app/core/wechat_work.py`
- Test: `backend/tests/test_wechat_work_auth.py`

- [ ] **Step 1: Write failing client tests**

Test URL generation, token response parsing, user identity parsing, and app message payload construction using a fake `httpx` transport or monkeypatch.

Run:

```bash
cd backend
uv run pytest tests/test_wechat_work_auth.py -q
```

Expected: FAIL because `WechatWorkClient` does not exist.

- [ ] **Step 2: Implement client**

Create:

```python
WECHAT_WORK_PROVIDER = "wechat_work"

class WechatWorkClient:
    def __init__(self, corp_id: str, agent_id: str, app_secret: str, callback_url: str): ...
    def build_login_url(self, state: str) -> str: ...
    def get_access_token(self) -> str: ...
    def get_user_id_by_code(self, code: str) -> str: ...
    def get_user(self, access_token: str, user_id: str) -> WechatWorkUser: ...
    def send_textcard(self, access_token: str, to_user: str, title: str, content: str, url: str | None = None) -> None: ...
```

Keep endpoint URLs as constants, use `httpx.Client(timeout=10)`, and raise `ValueError` with upstream `errmsg` on non-zero `errcode`.

- [ ] **Step 3: Run tests**

Run:

```bash
cd backend
uv run pytest tests/test_wechat_work_auth.py -q
```

Expected: PASS.

---

### Task 4: WeChat Login And Permission Mapping

**Files:**
- Create: `backend/app/core/external_auth.py`
- Modify: `backend/app/api/auth.py`
- Test: `backend/tests/test_wechat_work_auth.py`
- Test: `backend/tests/test_wechat_work_mappings.py`

- [ ] **Step 1: Write failing login tests**

Cover:

- no config returns 400 for login URL.
- unbound `corp_id` rejects callback.
- first login creates local user with role `user`.
- department mapping applies `org_admin` and permission overrides.
- mapping to `super_admin` is ignored or rejected.

- [ ] **Step 2: Implement external auth helper**

Create functions:

```python
def upsert_wechat_work_user(db: Session, *, corp_id: str, external_user: WechatWorkUser) -> User:
    ...

def apply_external_department_mapping(db: Session, user: User, *, corp_id: str, department_ids: list[str]) -> None:
    ...
```

Use `get_role_permission_template()` for defaults and `_dump_permissions()` compatible JSON encoding. Generate a random unusable password with `get_password_hash(secrets.token_urlsafe(32))`.

- [ ] **Step 3: Add auth endpoints**

In `backend/app/api/auth.py`, add:

- `GET /wechat-work/login-url`
- `GET /wechat-work/callback`

Callback should generate the local JWT and return a redirect to `/login?wechat_token=<token>` or a tiny HTML page that posts the token to the frontend. Prefer redirect with token only if same-origin deployment is guaranteed; otherwise return HTML that writes token to `localStorage` and navigates to `/dashboard`.

- [ ] **Step 4: Run tests**

Run:

```bash
cd backend
uv run pytest tests/test_wechat_work_auth.py tests/test_wechat_work_mappings.py -q
```

Expected: PASS.

---

### Task 5: Unified Message Dispatcher

**Files:**
- Create: `backend/app/core/message_dispatcher.py`
- Modify: `backend/app/core/alert_notifier.py`
- Test: `backend/tests/test_message_dispatcher.py`

- [ ] **Step 1: Write failing dispatcher tests**

Cover:

- delivery without external identity is marked `failed`.
- successful app message writes `success` and `sent_at`.
- WeChat client exception writes `failed` and `error_message`.
- `approval.requested` event can be dispatched even though no full approval module exists.

- [ ] **Step 2: Implement standard event model**

Create:

```python
class MessageEvent(BaseModel):
    event_type: str
    org_id: int | None = None
    recipient_user_ids: list[int] = []
    title: str
    content: str
    link_url: str | None = None
```

Supported event types:

- `alert.triggered`
- `scheduled_report.generated`
- `action_item.assigned`
- `action_item.status_changed`
- `dashboard.comment.created`
- `dashboard.shared`
- `approval.requested`

- [ ] **Step 3: Implement dispatch**

`dispatch_message_event(db, event, client_factory=None)` should:

1. Find enabled WeChat integration config.
2. Resolve recipients to `ExternalIdentity`.
3. Create `MessageDelivery` rows.
4. Send WeChat app message.
5. Update delivery status.
6. Never raise to caller for per-recipient delivery failures.

- [ ] **Step 4: Run tests**

Run:

```bash
cd backend
uv run pytest tests/test_message_dispatcher.py -q
```

Expected: PASS.

---

### Task 6: Wire Business Events

**Files:**
- Modify: `backend/app/core/alert_evaluator.py`
- Modify: `backend/app/core/alert_scheduler.py`
- Modify: `backend/app/api/action_items.py`
- Modify: `backend/app/api/comments.py`
- Modify: `backend/app/api/dashboards.py`
- Test: `backend/tests/test_message_dispatcher.py`
- Existing tests: action item, dashboard, alert/report tests.

- [ ] **Step 1: Add failing event hook tests**

Test that:

- creating an action item emits `action_item.assigned` to owner.
- changing action item status emits `action_item.status_changed`.
- creating dashboard comment emits `dashboard.comment.created` to owner/shared users except author.
- sharing dashboard emits `dashboard.shared`.
- alert/report dispatch helpers call `dispatch_message_event`.

- [ ] **Step 2: Add non-blocking event hooks**

Call `dispatch_message_event()` after database commit. Wrap each call in `try/except Exception` and log errors so business writes are not rolled back by messaging failures.

- [ ] **Step 3: Preserve existing robot behavior**

For alerts and scheduled reports, keep existing `send_wechat_sync` robot path while adding app-message dispatch to mapped recipients when possible.

- [ ] **Step 4: Run focused tests**

Run:

```bash
cd backend
uv run pytest tests/test_message_dispatcher.py tests/test_action_items.py tests/test_dashboard_comments.py tests/test_scheduled_reports.py -q
```

Expected: PASS. If a named legacy test file does not exist, run the closest existing tests listed by `rg --files backend/tests`.

---

### Task 7: Frontend Login And Admin Page

**Files:**
- Modify: `frontend/src/views/Login.vue`
- Create: `frontend/src/views/WechatWorkIntegration.vue`
- Modify: `frontend/src/router/index.ts`
- Modify: `frontend/src/layouts/MainLayout.vue`
- Test: `frontend/tests/wechatWorkIntegration.test.mjs`

- [ ] **Step 1: Write failing frontend tests**

Test source code expectations:

- login page calls `/api/auth/wechat-work/login-url`.
- router has `/wechat-work-integration`.
- system-admin menu has `企业微信集成`.
- config page calls `/api/integrations/wechat-work/config`, `/org-bindings`, `/permission-mappings`, `/message-deliveries`.
- page does not render the secret value, only secret-set placeholder.

Run:

```bash
cd frontend
node --test tests/wechatWorkIntegration.test.mjs
```

Expected: FAIL.

- [ ] **Step 2: Implement login button**

Add a secondary button under the password login form:

```vue
<el-button class="wechat-login-btn" size="large" @click="loginWithWechatWork">
  企业微信登录
</el-button>
```

The handler fetches `login_url` and sets `window.location.href`.

- [ ] **Step 3: Implement admin page**

Use existing `NotificationSettings.vue` patterns: cards, switches, forms, tables. Include tabs for basic config, org binding, permission mapping, message test, and delivery records.

- [ ] **Step 4: Wire route and menu**

Add:

```ts
{ path: "/wechat-work-integration", component: () => import("@/views/WechatWorkIntegration.vue"), meta: { requiredRole: ["super_admin"] } }
```

Add system-admin menu item with label `企业微信集成`.

- [ ] **Step 5: Run frontend tests**

Run:

```bash
cd frontend
node --test tests/wechatWorkIntegration.test.mjs
node --test tests/*.mjs
npm run build
```

Expected: PASS.

---

### Task 8: End-To-End Verification And Docs

**Files:**
- Modify: `.env.example`
- Modify: `README.md`
- Test: full backend and frontend suites.

- [ ] **Step 1: Add environment documentation**

Document:

- WeChat Work CorpID
- AgentID
- Secret
- Callback URL
- Trusted domain requirement
- How to bind `corp_id` to `Organization`
- How department mapping works

- [ ] **Step 2: Run full backend tests**

Run:

```bash
cd backend
uv run pytest -q
```

Expected: all tests pass.

- [ ] **Step 3: Run full frontend tests and build**

Run:

```bash
cd frontend
node --test tests/*.mjs
npm run build
```

Expected: all tests pass and Vite build exits 0. Existing Vite large chunk warnings are acceptable.

- [ ] **Step 4: Rebuild graphify after code changes**

Run:

```bash
/home/qqr/graphify/.venv/bin/python -c "from graphify.watch import _rebuild_code; from pathlib import Path; _rebuild_code(Path('.'))"
```

Expected: graph rebuild completes.

- [ ] **Step 5: Rebuild local services**

Run:

```bash
docker compose up -d --build backend frontend
docker compose ps
```

Expected: backend and frontend are up; frontend remains exposed on `localhost:16006`.

---

## Execution Notes

- Keep all WeChat HTTP calls behind `backend/app/core/wechat_work.py` so tests can mock the client.
- Do not add new dependencies unless tests show existing `httpx` is insufficient.
- Do not return secrets to the frontend.
- Do not auto-grant `super_admin` from external mappings.
- Dispatch messages after committing the primary business transaction.
- If working in the current dirty worktree, do not commit unless the user explicitly asks. The task checkboxes mention commits for agentic workflows, but this workspace currently has broad unrelated changes.
