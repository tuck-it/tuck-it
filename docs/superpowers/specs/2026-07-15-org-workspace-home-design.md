# Org/Workspace Home & Overview — Design

**Date:** 2026-07-15
**Status:** Approved (brainstorm) → ready for implementation plan
**Scope:** tuckit (public OSS core). No cloud/billing changes.

> Local-only spec. Per workspace convention, `docs/superpowers/` stays **untracked** — do not commit to the public repo.

---

## 1. Problem

tuckit's data hierarchy is **Org → Workspace → Area → Slice → Bite**. Org is the
membership + billing boundary; workspace access is **derived** (any `OrgMember`
can open every workspace in that org — there is no `WorkspaceMember`). Org roles
(`owner`/`admin`/`member`) are the only roles.

Despite orgs being the real membership boundary, **the org is a second-class
citizen in the UI**:

- You never *pick* an org — you pick a workspace and the org tags along.
- No page enumerates "all my orgs and the workspaces inside each." The switcher
  popover lists workspaces across orgs but renders orgs as non-clickable gray
  headers. Account settings lists orgs but shows only a workspace **count**, not
  the workspaces. Org settings lists one org's workspaces but only from inside
  `settings/<org>/`, reached via a workspace → settings → "Manage →" detour.
- `workspace_create` exists as a view but **no button anywhere triggers it**.
- There is no org landing, no breadcrumb above the switcher label.

**Guiding principle (from the requester):** nothing about org/workspace
understanding or control should be *implicit*. Detail-oriented developers who
can't fully see and control their resources disengage. Every org and workspace a
user belongs to must be visible and reachable as a first-class place.

## 2. Goal

Make the **org a first-class destination** and give users one place to *see and
control* everything they belong to. Achieve this primarily by **re-surfacing
existing capabilities** as first-class pages, not by adding new capabilities.

## 3. Non-goals (YAGNI)

- **No change to the access model.** Keep derived workspace access; do **not**
  add `WorkspaceMember`, per-workspace roles, workspace archiving, or org
  ownership transfer. Those are separate, larger decisions.
- No cloud/billing/plan UI (lives in tuckit-cloud).
- No new member/permission mechanics — only re-exposure of what exists.

## 4. Why this shape (comparison rationale)

tuckit matches the **scope → projects** family (Linear/GitHub/Vercel: one
membership boundary containing lightweight sub-units), *not* the independent-
tenant family (Slack/Notion). So the right patterns are: a persistent scope
switcher **+** a durable org landing page that lists its workspaces **+** a
breadcrumb — rather than a far-left workspace-icon rail. Org = GitHub org /
Vercel team; workspace = repo / project.

## 5. Surfaces

### 5.1 Org Home — **NEW** — route `/<org_slug>/`

The centerpiece. Layout = "B's information × C's arrangement": everything visible
on one page, organized into a two-pane rail. Nothing hidden behind links.

**Top bar:** breadcrumb (`내 org / <Org>`), role badge, `rename`, (no separate
"⚙ 설정" — org home absorbs settings; see §6).

**Left rail (~260px, panel background) — reference & control:**
- Org identity block: name, `workspaces N · members M`.
- **Members** block: full list (avatar dot, name, role). Inline role change
  (admin/owner) and remove, gated by permissions. `초대` (invite) button.
  When the list is long, show top ~5 + "전체 보기" (collapse), so the page
  doesn't grow unbounded.
- **Danger zone**: delete organization (owner only, existing guards).

**Right pane (wide) — the primary "go somewhere":**
- **Workspaces** grid of cards: name + light meta (e.g. slice/area counts) +
  `열기 →` (→ `/<org>/<ws>/`). Trailing dashed `＋ 새 워크스페이스` tile.

**Data:** resolve `org` from `org_slug` in-view (like `settings_org` does today —
**no TenantMiddleware change**); membership check → 404 for non-members. Reuse
`accessible_workspaces`/org services and existing member/invite partials
(`_member_row.html`, `_member_manage_modal.html`, `_invite_row.html`).

**Permissions:** member sees everything read-only where appropriate; role edit /
remove / invite / delete follow existing `is_org_admin`/`is_org_owner` guards.

### 5.2 Account Overview — **MODIFY** — route `settings/account` (existing)

Redesign `settings_account` into a **nested tree** ("everything I belong to"):
- Account header (email) + `＋ 새 조직`.
- One card per org: header (name, role badge, member count, `org 홈 →`) and a
  body that **enumerates the org's workspaces as chips** (each `열기 →`), plus a
  `＋ 새 워크스페이스` chip. `member`-role orgs show `조직 나가기`.
- Replaces today's count-only display. Reuse `list_user_orgs` +
  `accessible_workspaces` (group workspaces by org).

### 5.3 Workspace Switcher — **MODIFY** — `_workspace_switcher.html`

- Org group headers become **clickable → org home** (`org 홈 →` affordance on
  hover). Workspaces still click straight through to the workspace.
- Footer gains: **"내 모든 org 보기"** (→ account overview) and
  **"＋ 새 워크스페이스"**.
- Keep the current-workspace header and `{% regroup … by org %}` structure.

### 5.4 Breadcrumb — **NEW** — app shell (base template)

Small component making the current level legible everywhere:
- In a workspace: `<Org> / <Workspace>` — `<Org>` → org home.
- On org home: `내 org / <Org>` — `내 org` → account overview.
- Explicit "one level up" from any point in the tree.

### 5.5 "＋ New Workspace" button — **NEW UI** for existing `workspace_create`

Surface the un-triggered `workspace_create` view in three places: org home grid,
account overview (per-org chip), switcher footer. No view change — UI only.

### 5.6 Reserved slug fix — **MODIFY** — `core/services/slugs.py`

Add `first-org` to `RESERVED_ORG_SLUGS` (currently missing; it's a literal route
so an org with that slug would be shadowed at its root). Closes the last
single-segment collision gap.

## 6. Removing the old org settings page

Org home absorbs org settings (members, invites, rename, delete are all inline).
Therefore:

- **Delete (no redirect stub):** `settings_org.org_settings` view, the
  `settings_org.html` template, and the `path("settings/<slug:org_slug>/", …,
  name="settings_org")` **GET** route.
- **Keep (reused as POST/mutation targets by org home):** `org_rename`,
  `org_member_role`, `org_member_remove`, `org_member_manage`, `org_delete`,
  `workspace_create`, `invite_create`, `invite_cancel`, `invite_manage`. These
  stay at their `settings/<org_slug>/…` paths (URL cosmetics don't matter for
  POST endpoints); their partials are reused inside org home.
- **Repoint references:** workspace-settings "Manage →" link, the settings
  scope-nav "Organization" tab, and any `{% url 'web:settings_org' %}` → org home
  (`/<org>/`). The settings scope-nav's Organization entry now points at org
  home (or is dropped in favor of the breadcrumb/switcher entry points).

## 7. Routing & collision safety

Adding a single-segment `<slug:org_slug>/` route is safe:

1. **Reserved-slug list already blocks the dangerous words** (`settings`,
   `login`, `logout`, `register`, `invite`, `cloud`, `account`, `api`, …). The
   list was clearly designed for a single-segment org namespace. Only gap:
   `first-org` (added in §5.6).
2. **Cloud is fully namespaced under `cloud/`** (`tuckit_cloud/urls.py`:
   `cloud/health`, `cloud/paddle/webhook`, `cloud/upgrade`,
   `cloud/billing/portal`, then `include("tuckit.urls")`), and `cloud` is
   reserved. **Local and SaaS both safe.**
3. **Order-based resolution:** place the org-root pattern after `auth_patterns`
   and `settings_patterns` so literal single-segment routes always win. Content
   routes are two-segment (`<org>/<ws>/`) so they never collide with the
   one-segment org root.

**URL placement:** append an org-root group to `urlpatterns` after
`settings_patterns` (before/after `app_patterns` is immaterial — different
segment counts). Example:
`path("<slug:org_slug>/", pages.org_home, name="org_home")`.

## 8. Data / services reuse

- `list_user_orgs`, `accessible_workspaces`, `is_org_admin`, `is_org_owner`,
  `_owner_count` (`core/services/orgs.py`) — all reused.
- Context processors `switchable_workspaces` / `current_workspace` unchanged
  (switcher still uses them).
- Existing partials for members/invites/org rows reused; new templates:
  `org_home.html` (+ small workspace-grid/rail partials), redesigned
  `settings_account.html`, a breadcrumb include, edits to
  `_workspace_switcher.html`.

## 9. Access model (unchanged) — restated

Org membership ⇒ access to all workspaces in the org. Everything above is
presentation/navigation over the existing model. No migrations expected beyond
none (the `first-org` reserved word is a code constant, not schema).

## 10. Testing

- **Routing:** org home resolves for members; 404 for non-members; reserved
  slugs (incl. `first-org`) still rejected at creation; literal routes still win
  over `<org_slug>/`; two-segment content routes unaffected.
- **Org home:** renders workspaces + members + danger zone; permission gating on
  role edit/remove/invite/delete; `＋ 새 워크스페이스` reaches `workspace_create`.
- **Account overview:** enumerates workspaces per org (not counts); create org /
  leave org / open workspace links resolve.
- **Switcher/breadcrumb:** org header → org home; footer → overview; breadcrumb
  "up" links resolve at each level.
- **Regression:** existing `settings_org`-named URL references are gone/repointed
  (no broken `{% url %}`); the design-system drift test still passes.
- Follow existing test layout under `tuckit/tests/` (incl. `tests/web/`).

## 11. Open items / risks

- **Member list length** on org home — mitigated by top-5 + "전체 보기".
- **Scope-nav shape** — with org settings gone, confirm the Account/Workspace
  scope-nav still makes sense (Organization tab → org home or removed). Minor;
  resolve during implementation.
- **Empty/first-run** — a user with zero orgs still hits `first-org`
  onboarding; account overview handles the "some orgs" case. Verify org home
  isn't reachable with no membership (404 covers it).
