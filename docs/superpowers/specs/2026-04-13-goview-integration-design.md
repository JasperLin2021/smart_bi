# GoView Integration Design

## Overview

Integrate GoView into the existing Smart BI system on branch `feature/goview-integration` with the smallest viable scope that still satisfies business needs:

- Reuse the current Smart BI login as the entry point.
- Provide a new "大屏中心" feature inside the existing Vue application.
- Support both GoView designer access and published dashboard viewing.
- Keep GoView deployed as an external service instead of pulling its code into this repository.
- Avoid introducing a full reverse-proxy platform in this iteration.

The first release should optimize for fast delivery, low repo churn, and clear permission boundaries.

## Goals

1. Add a GoView entry inside Smart BI navigation.
2. Let `org_admin` and `super_admin` access GoView design capabilities.
3. Let standard `user` accounts view published dashboards only.
4. Minimize repeated login prompts by introducing a Smart BI controlled access handshake.
5. Keep organization isolation enforced from Smart BI instead of trusting client input.

## Non-Goals

- Vendor or fork GoView source code into this repository.
- Build a full SSO protocol implementation for this iteration.
- Build a full FastAPI reverse proxy for every GoView endpoint.
- Rework unrelated BI routes, datasource flows, or dashboard logic.
- Model every GoView asset in the Smart BI database in this first pass.

## Current Context

### Frontend

The current frontend is a single Vue 3 + Vite application with:

- centralized route registration in `frontend/src/router/index.ts`
- shared chrome in `frontend/src/layouts/MainLayout.vue`
- JWT-backed auth state in `frontend/src/store/auth.ts`

That makes Smart BI the correct control plane for exposing a new GoView feature entry and applying role-aware routing.

### Backend

The current backend is a FastAPI API service with:

- JWT auth in `backend/app/api/auth.py`
- centralized permission helpers in `backend/app/core/permissions.py`
- no existing static sub-app mounting or reverse proxy layer in `backend/app/main.py`

This favors an API-driven integration layer over a deep infrastructure rewrite.

## Recommended Approach

Use a Smart BI controlled GoView launch flow:

1. User logs into Smart BI as usual.
2. Frontend opens a new `/goview` page inside the existing app shell.
3. The page requests launch metadata from a new backend integration endpoint.
4. The backend validates the current Smart BI user and derives:
   - allowed GoView modes
   - organization scope
   - target GoView URL
   - whether embedded viewing is allowed
   - any bridge token or one-time launch credential
5. The frontend renders GoView in an `iframe` when possible, with a fallback to opening a new browser tab.

This approach keeps Smart BI in control of access while avoiding the operational cost of a full HTTP proxy layer.

## Alternative Approaches Considered

### 1. Full Reverse Proxy Through FastAPI

Proxy all GoView traffic under the Smart BI domain and inject auth server-side.

Pros:

- Most seamless same-origin user experience.
- Maximum control over request authorization.

Cons:

- High complexity for static assets, uploads, websockets, cookies, and upgrade compatibility.
- Larger backend surface area and higher debugging cost.

This is not recommended for the first integration milestone.

### 2. Plain External Link Or Simple Iframe Without Backend Mediation

Just add a menu item pointing to GoView and let users log in there separately.

Pros:

- Lowest implementation effort.

Cons:

- Fails the "尽量免登录" requirement.
- Weak control over role-based design vs view behavior.
- Poor organization isolation guarantees.

This does not meet the approved direction.

## Permission Model

Extend the existing permission vocabulary with GoView-specific keys.

### Menu Permissions

Add:

- `goview.view`

This controls whether the "大屏中心" menu and `/goview` route are available.

### Action Permissions

Add:

- `goview.read`
- `goview.design`

`goview.read` allows published dashboard viewing.

`goview.design` allows access to GoView designer or dashboard management entry points.

### Default Role Mapping

#### `user`

- `goview.view = true`
- `goview.read = true`
- `goview.design = false`

#### `org_admin`

- `goview.view = true`
- `goview.read = true`
- `goview.design = true`

#### `super_admin`

- full GoView access

This fits the already approved requirement: admins can design, normal users can only view.

## Route And Page Design

Add frontend routes:

- `/big-screen-center`: Smart BI navigation entry for GoView.
- `/goview`: compatibility redirect to `/big-screen-center`.
- `/internal-big-screen-center`: hidden fallback for the earlier built-in prototype.

Add a new page:

- `frontend/src/views/GoViewCenter.vue`

### Page Responsibilities

The page should:

1. Request launch info from Smart BI backend on load.
2. Show the current mode:
   - view
   - design
3. Render a compact toolbar with:
   - mode switcher when both modes are available
   - open-in-new-window action
   - refresh action
4. Embed GoView in an `iframe` when permitted.
5. Fall back cleanly when embedded display is blocked.

### Sidebar Integration

Add a new sidebar item in the existing layout:

- label: `大屏中心`
- visibility: users with `goview.view`

This keeps navigation consistent with the current app shell.

## Backend API Design

Add a GoView integration router, for example:

- `GET /api/goview/launch`

Optional follow-up endpoints if needed:

- `GET /api/goview/health`
- `POST /api/goview/launch`

### Launch Response Shape

The launch endpoint should return a compact payload like:

```json
{
  "modes": ["view", "design"],
  "default_mode": "view",
  "embed": true,
  "title": "大屏中心",
  "organization": {
    "id": 2,
    "name": "Nexteer"
  },
  "targets": {
    "view": "https://goview.example.com/view?ticket=...",
    "design": "https://goview.example.com/design?ticket=..."
  }
}
```

The exact shape can be adjusted, but it should separate target URLs by mode and avoid requiring the frontend to infer authorization logic.

## Auth Bridge Strategy

The integration should follow this order of preference:

1. Preferred:
   Smart BI backend exchanges trusted server credentials with GoView and receives a short-lived access artifact for the current user session.

2. Acceptable fallback:
   Smart BI backend signs a short-lived launch token that a thin GoView-side bridge can verify.

3. Temporary emergency fallback:
   Redirect to GoView login when the bridge is unavailable.

The frontend should never be responsible for storing or constructing privileged GoView credentials on its own.

## Organization Isolation

Organization scope must be derived on the backend from the current Smart BI user.

Rules:

- `user` and `org_admin` may access only the current `org_id`.
- `super_admin` may access all organizations.
- The frontend must not pass raw organization authority for trust decisions.

If GoView supports project, workspace, or folder isolation, Smart BI should map each organization to a distinct GoView namespace. If GoView does not support this directly, Smart BI should at minimum restrict which entry URLs it issues.

## Failure Handling

### GoView Service Unavailable

- Backend returns a clear integration error.
- Frontend shows a recoverable empty state with retry.

### Embed Blocked

If `iframe` rendering fails due to GoView headers or browser policy:

- show an inline explanation
- keep the target URL available
- allow opening in a new tab

### Mode Not Allowed

If the requested mode is not permitted:

- backend returns `403`
- frontend falls back to the allowed default mode or shows a permission message

### Missing Dashboard Resource

Show an empty state instead of leaving a blank embedded frame.

## Testing Strategy

### Backend Tests

Add tests for:

- unauthenticated access rejection
- `user` receives view-only launch data
- `org_admin` receives view and design launch data
- `super_admin` receives unrestricted launch data
- service misconfiguration or upstream GoView failure returns a structured error

### Frontend Verification

Verify:

- sidebar visibility respects permissions
- `/goview` loads launch metadata correctly
- mode switcher respects allowed modes
- iframe fallback to new tab works
- permission errors produce readable UI feedback

## Implementation Notes

To keep the first diff small:

- add GoView permission keys to the existing permission constants and templates
- expose effective GoView capability through the existing auth/profile flow or a dedicated launch endpoint
- implement one new view and one new backend router
- keep GoView-specific configuration in environment settings rather than hardcoding URLs

Suggested environment variables:

- `GOVIEW_BASE_URL`
- `GOVIEW_EMBED_BASE_URL`
- `GOVIEW_BRIDGE_SECRET` or equivalent
- `GOVIEW_ENABLED`

Add `.env.example` updates if new settings are required.

## Rollout Plan

Phase 1:

- Add GoView menu and route
- Add launch endpoint
- Add view/design mode selection
- Add embed and new-tab fallback

Phase 2:

- Harden auth bridge
- Add organization-to-workspace mapping
- Add richer dashboard targeting and catalog UX

## Open Questions

These points affect implementation detail but do not block the approved design direction:

1. Which exact GoView authentication mechanism is available in the target deployment.
2. Whether GoView permits iframe embedding in the target environment.
3. Whether dashboard resources are already partitioned by organization in GoView.

The implementation should structure the integration layer so these answers can be plugged in without rewriting the frontend route or permission model.
