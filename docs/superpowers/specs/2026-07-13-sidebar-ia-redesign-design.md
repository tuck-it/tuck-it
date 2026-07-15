# Sidebar IA redesign — design

Date: 2026-07-13
Repo: `tuckit` (public). Lives under `docs/superpowers/` — **local-only, never commit**
(per `docs-superpowers-local-only`).

Builds on the shipped sidebar visual redesign (v0.7.0). This is the *information
architecture* pass — what the destinations ARE, not how they look.

## Problem

The sidebar navigates by **object location** (Home / Attention / In Progress /
Roadmap / Activity / Areas — 6 destinations). Three of them (Home, Roadmap, In
Progress) all surface `building` slices; two (Attention, Triage) are both queues.
The user built tuckit *because* Confluence is too complex and even Linear is
overkill for a solo founder — but the current IA reproduces exactly the
"multiple overlapping for-me views" anti-pattern. Result: "I don't know where to
go to do what."

## Research basis (PM / SSOT tools, not to-do apps)

Competitive IA study of Linear·Shortcut·Height, Jira·Asana·ClickUp·Monday,
Notion·Coda·Airtable·Confluence, Basecamp·Trello·GitHub Projects·Productboard.
Five convergent principles:

1. **One item = source of truth; views are disposable.** Status is one field
   rendered as board/list/etc. Never make the same items three separate
   destinations. *(GitHub Projects, Productboard, Height, Linear Views)*
2. **Exactly ONE "what needs me now" surface.** Monday's single `My Work` works;
   Asana (Home/Inbox/My Tasks) and ClickUp (4 overlapping) are the documented
   anti-pattern. *(Monday vs Asana/ClickUp)*
3. **An intake queue, reusable for the AI agent.** Linear Triage / Basecamp Hey!
   hold incoming items awaiting acceptance. tuckit already has Triage +
   `Slice.source=agent`. *(Linear, Basecamp)*
4. **The product supplies structure; the user doesn't.** Confluence's fatal flaw
   = empty hierarchy + infinite nesting + no opinion → sprawl. tuckit's shallow,
   opinionated Area→Slice→Bite is a strength — keep it, add no nesting. *(Confluence,
   ClickUp anti-pattern; Basecamp/Trello positive)*
5. **Cap top-level count; open to a decision surface, not a file tree.** *(Basecamp
   ~6, Notion's opinionated Home over the page tree)*

## Naming decisions (locked)

- **Home · Inbox · Board · Areas.** Rationale, grounded in product register:
  - **Areas** kept (NOT renamed to Projects). This is the **PARA** distinction:
    a *Project* has an end; an *Area* is an ongoing responsibility maintained
    indefinitely (e.g. "Backend"). Things 3 uses "Areas" this exact way.
  - **Inbox** (not Triage): friendly, universal capture-dump meaning (Things).
    The "Inbox = notifications" collision is avoided because Activity moves to a
    bell/panel. Triage reads as clinical/dev-jargon.
  - **Board** (not Roadmap): tuckit has no dates; "Roadmap" implies a time axis
    and stakeholder communication. "Board" honestly names a status kanban.

## Scope

**IN (pure IA / tab restructure, reusing existing computed state):**
- Sidebar nav group reduced to **Home · Inbox · Board**; **Areas** section kept.
- **Home** repurposed to the single "now" surface (focus + attention strip).
- **Inbox** = the Triage view, relabeled; adds a `source` (human/agent) badge.
- **Board** = the Roadmap view, relabeled; absorbs the pipeline buckets Home used
  to show (planned / ideas / someday).
- **Activity** demoted from a nav tab to a bell icon → slide-over panel.
- Attention and In-Progress drop out of the nav (their content lives in Home).
- **Per-item activity thread** on each slice's detail (read-only; reuses
  `ActivityEvent` by target — no model change).

**OUT (explicitly deferred — separate specs):**
- **⌘K command palette** (research-recommended, but a new feature).
- **Agent accept/reject gate** on Inbox (a workflow feature; this pass only
  *displays* the `source` badge).
- **Comments** (a `Comment` model + write UI + MCP tool for human↔agent
  dialogue). The per-item thread is read-only this pass; comments are a separate
  future spec that would interleave into the same thread.
- **Dates / scheduling / someday-snooze.**
- **URL path & route-name renames** (`/triage/`→`/inbox/`, `/roadmap/`→`/board/`)
  — deferred to the deep-link project, which rewrites all routing anyway (see
  Deep-link coordination).

## The new IA — sidebar

```
[Org · Workspace ▾]          ← existing popover switcher (unchanged)

  Home            ← landing: today's focus + attention strip
  Inbox    (3)    ← was Triage: capture/agent intake
  Board           ← was Roadmap: idea→planned→building→shipped kanban
  ──────────
  Areas                       ← unchanged section (PARA "ongoing")
   Default
   + Area
  ──────────
  ⚙ Settings   🔔 Activity   ☀ theme     ← utility row (Activity now a bell)
  [ + Capture              C ]
```

6 object tabs → **3 surfaces + Areas**.

## Surface specs

### Home (`web:home`, `pages.home`, `home.html`) — the ONE "now" surface
Merges today's In-Progress + Attention into the landing. Shows, top to bottom:
- **Attention strip** — stale/stalled items (`home_state["attention"]` =
  `attention_items(ws)`: triage sitting >7d + building stalled >7d). A signal row,
  not a tab.
- **Focus ("지금 집중")** — `building` slices **and** `doing` bites. Powered by
  `in_progress_state(ws)` (returns `{slices, bites}`). `pages.home` passes this in
  addition to `home_state`.
- **Recently shipped** — `home_state["shipped"]` (a few, newest first) for a sense
  of progress.
- Onboarding get-started block preserved for new workspaces.
- **Removed from Home:** the `planned` / `ideas` / `someday` buckets — these now
  live on Board (kills the Home↔Roadmap overlap).

### Inbox (`web:triage`, `capture.triage_list`, `triage.html`) — intake
Behaviorally unchanged: captured slices land here; each row assigns **status +
Area** to leave the inbox (existing `capture.triage` POST). Additions:
- Sidebar label "Inbox" (route name stays `web:triage` — see coordination).
- Each row shows a **`source` badge** (`human` / `agent`) so agent-created items
  are visibly "proposed to you." No accept/reject gate this pass.
- Count badge unchanged (`triage_count`).

### Board (`web:roadmap`, `pages.roadmap`, `roadmap.html`) — the pipeline
The single pipeline view. `roadmap_state(ws)` already groups all non-triage,
non-dropped slices into `idea / planned / building / shipped`. Absorbs Home's old
planned/ideas buckets. `someday`-tagged slices appear in their status column
(no special lane this pass). Sidebar label "Board" (route name stays
`web:roadmap`).

### Areas (unchanged)
The `Areas` sidebar section, `_area_nav.html`, area detail (`slices.area_view`),
and slice detail (with Bites) are all unchanged. PARA "ongoing responsibility"
semantics preserved.

### Activity → slide-over panel (`web:activity` retained)
- Remove Activity from the nav group.
- Add a **🔔 bell** button to the utility row that toggles an Alpine slide-over
  panel. On first open the panel htmx-GETs an activity partial from `web:activity`
  (a new `?panel=1`/`HX-Request` branch returning just the event list, not the
  full page) and swaps it into the drawer. Primary use: reviewing what the AI
  agent did.
- Keep `web:activity` as both the panel's content source and a full-page fallback
  (unchanged when requested normally).

### Per-item activity thread (Linear-style)
Each slice's detail shows its own activity as a chronological thread at the
bottom — the Linear pattern (system events read like a comment feed), making
activity **contextual** where it's most useful. Complements (does not replace)
the global Activity panel: per-item = "context for this item", global bell =
"cross-item sweep, esp. agent oversight".
- **Read-only this pass** (no comment authoring). A real `Comment` model +
  write UI + MCP tool (human↔agent dialogue) is a compelling but separate future
  spec — see Out of scope.
- **No model change:** `ActivityEvent` already carries `target_type` +
  `target_id`. A slice's thread = its own events **plus** its bites' events,
  oldest-first: `slice_activity(slice_)` filters
  `Q(target_type="slice", target_id=slice.id) | Q(target_type="bite", target_id__in=<slice bite ids>)`
  within the slice's workspace, `order_by("created_at")`.
- Surface: `web/panel.py::slice_panel_context` adds `activity`; `_slice_panel.html`
  renders a thread (reusing `_activity_row.html`) below `panel-meta`. Because
  `slice_detail.html` just includes `_slice_panel.html`, this covers both the
  slide-over panel and the full page.

### Utility row / Capture / switcher
- Utility row gains the bell: **Settings · Activity(bell) · theme**. (No ⌘K icon
  — the palette is out of scope; a dead control would mislead.)
- Capture button and the workspace switcher popover are unchanged.

## No model changes

**Zero model/schema changes, zero migrations.** Every surface reuses existing
services and fields:
- Home: `in_progress_state`, `attention_items`, `home_state` (all exist).
- Inbox: `list_slices(triage)`; `Slice.source` already exists (badge only).
- Board: `roadmap_state` (exists).
- Activity panel: `recent_activity` / `workspace.activity` (exists).
- Per-item thread: `ActivityEvent.target_type`/`target_id` (exist) via a new
  read-only query helper `slice_activity`. No new field, no migration.
Migrations remain through core 0008. Forward-compatible with the deep-link
project (which adds slug validation independently).

## Deep-link coordination (in-flight, approved, code not started)

The deep-link project (`docs/superpowers/specs/2026-07-13-org-workspace-deeplink-slug-design.md`)
rewrites routing to `app.tuckit.dev/<org>/<workspace>/...` via a single urlconf +
`TenantMiddleware.process_view` + a `{% wurl %}` template tag, replacing session
tenancy. Interactions and the division of labor:

1. **Route names/paths stay put in THIS pass (label-only).** We change sidebar
   *labels* (Inbox, Board) and *which entries appear*, but NOT URL paths or route
   names (`web:triage`, `web:roadmap` remain; `nav--active` matching still works).
   The deep-link project is the single owner of URL structure. **Recommendation:**
   when deep-link Phase B rewrites paths, rename them there at zero extra cost:
   `/triage/`→`/inbox/`, `/roadmap/`→`/board/` (and route names to
   `web:inbox`/`web:board`). Add this to the deep-link spec's route table. Until
   then, a `/roadmap/` path labeled "Board" is an acceptable internal-only
   mismatch.
2. **`{% wurl %}` sweep — sequence matters.** This IA change edits `_sidebar.html`
   nav links (drops Attention/In-Progress/Activity from the group, adds the bell).
   - If **this IA lands first** (recommended): deep-link Phase B sweeps the *new*
     nav set into `{% wurl %}`. The deep-link plan's "links to convert" list must
     reflect Home/Inbox/Board + Capture + Settings + the Activity panel trigger.
   - If **deep-link lands first**: this IA must author the new sidebar links with
     `{% wurl %}`, not `{% url %}`.
3. **Switcher interaction.** The shipped popover switcher POSTs `web:switch_workspace`
   (session tenancy). Deep-link replaces session switching with path navigation
   (`/<org>/<other-ws>/...`). The switcher's *mechanism* is owned by the deep-link
   project; this IA does not touch it. Flagged so both efforts know the switcher
   is a shared touch-point in `_workspace_switcher.html`.
4. **Settings hub.** Deep-link makes Settings a root hub `/settings/<org>/<workspace>/`.
   The utility-row Settings link is swept by deep-link like any other link; no
   conflict here.

**Recommended order: ship this IA pass first, then deep-link Phase B** — deep-link
then sweeps a smaller, final nav surface, and renames the two paths as part of its
own routing rewrite.

## Files touched (this pass)

- `templates/web/partials/_sidebar.html` — nav group → Home/Inbox/Board; relabel;
  drop Attention/In-Progress/Activity from the group; add bell to utility row;
  Activity slide-over panel markup.
- `templates/web/home.html` — drop planned/ideas/someday buckets; add doing-bites
  to the focus section; keep attention strip + recently-shipped.
- `views/pages.py` — `home` passes `in_progress_state(ws)` alongside `home_state`.
- `templates/web/triage.html` — `source` badge per row (Inbox).
- `static/web/app.css` — Activity slide-over panel styles; `source` badge; minor
  Home layout; utility-row bell; per-item thread (all via `var(--token)`).
- `core/services/activity.py` — new `slice_activity(slice_)` read helper.
- `web/panel.py` — `slice_panel_context` adds `activity`.
- `templates/web/partials/_slice_panel.html` — activity thread section.
- (No `urls.py` path/name changes; no `models`, no migrations.)

## Out of scope / future (separate specs)

- ⌘K command palette (create/navigate/act; mirrors the MCP agent).
- Inbox agent accept/reject gate.
- Dates / scheduling / someday-snooze.
- URL path renames — folded into deep-link Phase B.

## Verification

- Sidebar shows exactly Home · Inbox · Board + Areas; Attention/In-Progress/Activity
  gone from the nav group; bell opens the Activity panel.
- Home renders focus (building slices + doing bites) + attention strip + recently
  shipped, and no longer shows planned/ideas/someday.
- Board shows the full idea→shipped pipeline (including what Home dropped).
- Inbox rows carry a human/agent source badge; assigning status+Area still removes
  the row.
- A slice's detail (panel + full page) shows an activity thread of its own +
  its bites' events, oldest-first.
- `tests/web` green (update `test_home_shell` nav-content assertions, add
  Home-focus, Inbox-badge, Activity-panel, and per-item-thread assertions). No
  new migrations.
- Light + dark visual check of Home, Inbox badge, and the Activity slide-over.
