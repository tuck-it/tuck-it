# First-run onboarding — design

**Date:** 2026-07-13
**Repo:** `tuckit` (public core — ships to self-host AND cloud)
**Status:** design approved (visual mockup signed off), spec for implementation
**Visual reference:** interactive mockup — https://claude.ai/code/artifact/38f5109a-41db-4819-ba94-20e50f986aa7

## Problem & emotional job-to-be-done

A brand-new tuckit account lands directly on an empty Home full of undefined jargon
(NEEDS YOU / NOW·NEXT·SOMEDAY / slices / Triage / Areas), with no guidance and no
sense of what the product is for. The UX review flagged this as a top-3 first-run
failure.

The real job is not "explain the features." It is to resolve the **anxiety of
delegating to an AI agent** — *"am I missing something my agent is doing?"* tuckit
already answers this: it is the single source of truth a human (web) and their AI
agent (MCP) share, and it **surfaces what needs you** (7-day stale/stalled rules) and
**logs who did what** (👤 you / 🤖 agent). Onboarding's job is to make a newcomer
*feel* that reassurance fast, and to reach the differentiated first win: **their agent
connected and writing into the same workspace.**

## North star & key decisions (all confirmed)

- **First win / north star:** connect your AI agent (the differentiated "aha").
- **Form:** a dedicated one-time first-run flow at `/welcome/` + a persistent Home
  "Get started" checklist.
- **Verify step:** live detection + celebration — poll for the agent's first write and
  celebrate it in-flow (not a manual "I did it" button).
- **Connect snippets:** Claude Code + generic MCP JSON.
- **No seeded sample content** — keep the north star pure; use rich, guiding empty
  states instead.
- **Copy:** English; lead with the emotional framing, not the feature.
- **Design:** editorial-grade but on the existing design system — paper material, single
  teal accent, light/dark; **human = sans (Onest), agent/code = mono (IBM Plex Mono)**
  to typographically encode the human/agent duality; a calm radar→check celebration beat.

## Goals

- A new user reaches "my agent is connected and writing here" (or deliberately skips)
  within the first session.
- The empty Home is never a dead end: it guides the next action.
- Ships to both self-host and cloud from public core; no billing/pricing copy.

## Non-goals (explicitly out of scope)

- The full **English-only sweep** of the app (12 templates + 4 services still carry
  Korean strings) — that remains a separate queued effort. This spec only rewrites the
  **empty-state copy** on the screens a newcomer hits (Home, Triage, Attention, In
  Progress, Roadmap), which happens to clean up their Korean/em-dash empty states.
- Seeded/sample slices.
- Onboarding for **invited** members joining an existing workspace (they skip the flow —
  the workspace is already set up).
- A "Ship your first slice" 4th checklist step (YAGNI for now).
- Real notifications, email, or a product tour/coachmarks.

## State model — one new field, everything else derived

Add exactly one persisted field; derive all progress from real data.

- **`Workspace.onboarding_dismissed`** (`BooleanField(default=False)`) + a Django
  migration. Controls only whether the Home "Get started" card is shown.
- Everything else is derived (no new state):
  - **Agent connected** — the workspace has ≥1 `ApiToken` (the user generated a key).
    (Truer signal `token.last_used_at is not null` / an agent-authored `ActivityEvent`
    exists is available and used for the *live celebration*; the checklist uses the
    simpler "token exists" so generating the key gives immediate momentum.)
  - **First slice captured** — the workspace has ≥1 `Slice`.
  - **Triaged into an area** — ≥1 `Slice` lives in a non-triage `Area`.
- **No per-user onboarding state.** Onboarding is workspace-scoped and triggered for the
  workspace **creator** at signup.

## Flow A — the dedicated `/welcome/` page

A standalone, full-screen, focused page (does **NOT** extend `web/base.html`'s sidebar
shell — this is a pre-work moment, like the auth screens). It loads the token chain
`tokens.brand → tokens.product → base.css → welcome.css` (new sheet), plus Alpine + HTMX
(already vendored). Three steps, driven by Alpine `x-data` step state; **"Skip setup" /
"Skip for now" is present on every step** and just navigates to Home (does NOT set
`onboarding_dismissed` — the checklist stays so the user can resume).

**Routing / trigger:**
- New URL `web:welcome` → `GET /welcome/` (a normal logged-in view;
  `LoginRequiredMiddleware` already protects it).
- **`register_view` (self-service signup) redirects to `web:welcome`** instead of
  `web:home` (`tuckit/web/views/accounts.py:25`). This is the only redirect changed;
  invite flows (`accounts.py:41,48`) keep going to `web:home`.
- `/welcome/` is idempotent and re-reachable later via the Home checklist's "Connect
  your agent" CTA (links to `/welcome/#connect` or the connect step).

### Step 1 — Welcome (the emotional hero)

- Eyebrow: `WELCOME TO TUCKIT` (mono).
- Headline (sans, large): **"Nothing your agent does slips past you."**
- Lede: *You and your AI agent work in **one shared workspace**. Every idea, change, and
  shipped feature — written by you or by your agent — lands in the same place. tuckit
  keeps watch, so **nothing quietly rots**.*
- **Hero visual = a live-feeling activity stream that demonstrates the reassurance:** a
  small card titled `ACTIVITY · live` with 4 entries (🤖 agent created…, 👤 you shipped…,
  🤖 agent edited…), the last one surfaced with a pulsing warn-toned **"● NEEDS YOU · sat
  in triage 9 days"** chip. Entries stagger-in on load. Caption: *That last one? Nobody
  touched it for 9 days. **tuckit surfaced it for you** — that's the whole point.*
  - This hero content is **illustrative/static** (it dramatizes the value; it is not the
    user's real data — a brand-new account has none). Mark it clearly as example.
- CTA: primary "Connect your agent →" · secondary "Skip setup".

### Step 2 — Connect your agent (the centerpiece)

- Eyebrow `STEP 1 OF 2 · CONNECT`; headline "Point your agent at this workspace."; lede
  explains the agent reads/writes over **MCP**.
- **MCP endpoint** row (mono, copy button): value = `request.build_absolute_uri("/mcp")`
  (reuse the settings pattern, `settings.py:24`).
- **Workspace key** row: a **"Generate key"** button → POSTs to create a token via
  `generate_token(workspace, name="Agent (onboarding)")` (`services/tokens.py`), reveals
  the raw token **once** (mono, copy button). Reuses the existing one-time-reveal pattern
  from Settings → tokens. (Do not auto-create on page load — avoid orphan tokens on
  refresh.)
- **Tabs: Claude Code | MCP JSON** (mono), each a copyable code block:
  - Claude Code: `claude mcp add tuckit --transport http <mcp_url> --header "Authorization: Bearer <token>"`
  - MCP JSON: `{ "mcpServers": { "tuckit": { "url": "<mcp_url>", "headers": { "Authorization": "Bearer <token>" } } } }`
- **Live "listening" panel** (radar pulse): *"Listening for your agent… ask it to capture
  or create something."* — this is the poll host (see Live detection).
- CTAs: "← Back" · "Skip for now".

### Step 3 — Celebrate (live)

Reached automatically when the agent's first write is detected (or never, if they skip).

- A drawn check "seal", eyebrow `CONNECTED`, headline "Your agent just joined the
  workspace.", and a real activity entry line **`🤖 agent created "<actual slice
  title>"`** built from the detected `ActivityEvent.target_label`.
- Lede: *From now on you'll see everything it does here — and tuckit will flag anything
  that needs you.*
- CTA: primary "Go to your workspace →" (→ `web:home`).

### Live detection mechanism

- On Step 2 render, compute `baseline` = the current max `ActivityEvent.id` for the
  workspace (0 if none). Embed it in the poll URL.
- New endpoint `web:welcome_agent_check` → `GET /welcome/agent-activity?since=<id>`:
  - If an `ActivityEvent` with `actor="agent"` and `id > since` exists for the current
    workspace → return the **celebration fragment** (targets `#welcome-stage`,
    `hx-swap="innerHTML"`), which contains no polling element → polling stops.
  - Else → return `204 No Content` → HTMX keeps polling.
- The listening panel polls with `hx-get=".../agent-activity?since={{baseline}}"
  hx-trigger="load delay:3s, every 3s" hx-target="#welcome-stage" hx-swap="innerHTML"`.
- `actor="agent"` events are produced whenever the MCP tools mutate via the service layer
  (the activity log already threads `actor`), so any agent *write* trips it. Read-only
  agent calls won't (acceptable — the copy nudges a write; Skip covers non-writers).

## Flow B — Home "Get started" checklist

Lives **inside** the app shell (`home.html`, styled in `app.css`), pinned at the top of
Home while incomplete.

- **Visibility:** show iff `not workspace.onboarding_dismissed AND not all_steps_done`.
- **Three steps** (each derived; renders checked/greyed when done, with a CTA when open):
  1. **Connect your AI agent** — done when workspace has ≥1 `ApiToken`. CTA → `/welcome/`
     (connect step).
  2. **Capture your first slice** — done when workspace has ≥1 `Slice`. CTA → opens Quick
     Capture (⌘K / the capture modal).
  3. **Triage it into an area** — done when ≥1 `Slice` is in a non-triage `Area`. CTA →
     `web:triage`.
- A small progress bar ("N of 3 done") and a **"Dismiss"** control → sets
  `onboarding_dismissed=True` (hides the card permanently).
- As the connected agent works, steps 2 and 3 auto-complete — reinforcing the aha.
- When all three complete (or dismissed), the card disappears, leaving the real status
  dashboard.

Progress is computed by a new helper, e.g. `onboarding_state(workspace) -> {connected,
captured, triaged, done, count}` in `core/services/` (derived from `ApiToken` / `Slice` /
`Area` counts), exposed to Home via the existing context/view path.

## Rich empty states (bounded copy pass)

Replace the passive/mixed-language empty states on the newcomer's screens with short,
guiding English copy (this also removes the Korean in `in_progress.html` and the bare
`—` in `roadmap.html`). Scope is **empty-state blocks only** — not the broader sweep.

- **Home:** the checklist card is the first-run hero; the normal empty sections keep quiet
  copy beneath it.
- **Triage empty:** "Nothing to triage. Capture an idea (⌘K) — or let your agent add one."
- **Attention empty:** keep "Nothing needs your attention right now." (already good).
- **In Progress empty:** replace Korean with e.g. "Nothing in progress. Slices you move to
  *building* show up here."
- **Roadmap empty columns:** replace `—` with a faint one-liner per column where useful.

## Design & assets

- New `tuckit/web/static/web/welcome.css` — flow layout/components, `var(--token)` only
  (no literal hex, no hardcoded radius). Reuses base.css primitives, fonts, paper texture.
- Type roles: human/body = Onest (`--sans`), agent/code/labels = IBM Plex Mono (`--mono`)
  — both already self-hosted in base.css.
- Full light/dark via tokens; `prefers-reduced-motion` disables the stagger/radar/draw
  animations; visible focus; keyboard operable; no horizontal overflow at 320px.
- Home checklist card styles go in `app.css` (app-shell component).

## Protected behavior / boundaries

- Public/private boundary intact — all generic product onboarding; MCP endpoint, tokens,
  and activity are already core; **no billing/pricing copy**.
- Don't change MCP/API behavior, tenant isolation, the activity/actor threading, or the
  invite flows' redirects.
- `docs/superpowers/` stays untracked (gitignored) — spec/plan not committed to public
  `tuckit`.

## Testing strategy

- `register_view` (self-service, REGISTRATION_OPEN) now redirects to `/welcome/`; the two
  invite flows still redirect to `web:home` (assert unchanged).
- `GET /welcome/` renders 200 for a logged-in user; contains the token chain + `welcome.css`,
  not `app.css`; no sidebar.
- "Generate key" creates exactly one `ApiToken` and reveals a raw token once.
- `GET /welcome/agent-activity?since=N` → 204 when no agent event after N; returns the
  celebration fragment (with the real `target_label`) when an `actor="agent"`
  `ActivityEvent` with id > N exists.
- `onboarding_state` derivations: fresh workspace → all false; after token → connected;
  after slice → captured; after a slice in a non-triage area → triaged; all → done.
- Home checklist visibility: shown when not dismissed and not done; hidden when dismissed
  (`onboarding_dismissed=True`) or when all steps done.
- Empty-state copy tests where markup changed (Triage/In Progress at minimum).
- Full `uv run pytest` green; design-system drift test still passes (welcome.css is a new
  screen sheet, not a token file).

## Definition of done

- A newly-registered user is taken to `/welcome/`, can generate a key, copy a Claude
  Code / MCP JSON snippet, and — when their agent writes — sees the live celebration.
- Home shows the guiding "Get started" checklist that auto-completes from real activity
  and can be dismissed.
- Newcomer empty states guide rather than dead-end; no Korean/em-dash empty states on
  those screens.
- Light/dark + mobile composed; token-only CSS; all tests green; boundary intact.
