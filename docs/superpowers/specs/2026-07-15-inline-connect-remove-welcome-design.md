# Inline agent-connect in the checklist; remove /welcome/ — design

**Date:** 2026-07-15
**Repo:** `tuckit` (public core — ships to self-host AND cloud)
**Status:** design approved (brainstorm), spec for implementation
**Evolves:** `2026-07-15-onboarding-guided-primitives-design.md` (the 4-step
checklist) and supersedes the `/welcome/` flow from
`2026-07-13-first-run-onboarding-design.md`.

## Problem

The 4-step "Get started" checklist lives inline on Home, but its final step ④
("Connect your agent") links **out** to a separate, chrome-less full-screen page
`/welcome/`. That page:

- **Bounces the user out** of the in-app checklist for the last step (jarring
  context switch).
- **Duplicates** the token + MCP snippet that Settings → Agent access already
  provides.
- Carries a now-**vestigial intro narrative** (its step 0 "why tuckit" hero,
  whose CTA just goes to Home since a prior change).

Only two things on `/welcome/` are genuinely differentiated and worth keeping:
the **guided connect** (endpoint + one-time key + Claude Code / MCP JSON
snippets) and the **live "your agent just joined" celebration** (polls for the
agent's first write and celebrates it in-flow).

## Decision (confirmed)

**Fold the connect experience — including the live celebration — inline into
checklist step ④, and delete `/welcome/` entirely** (page, intro narrative,
styles, endpoints, tests). Settings → Agent access remains the ongoing
management surface (create/revoke tokens). Cleanup must be thorough: **no
orphaned template, CSS, JS, view, URL name, context var, or test** may remain.

## ④ completion semantics change (confirmed)

Today step ④ is "done" when a **token exists** (generating a key checks it).
With the live celebration inline, completion now means the **agent has actually
connected** — i.e. an agent-authored `ActivityEvent` exists. This aligns the
checkmark, the celebration, and the real "aha" into one moment (Linear's "close
the loop" principle). Generating a key is an intermediate action within ④, not
completion. A user who makes a key but never runs their agent leaves ④ open
(correct) — they can still dismiss the checklist.

`OnboardingState` splits the single `connected` signal into two derived signals:

| Field | Done when | Drives |
|-------|-----------|--------|
| `connected` (redefined) | an `ActivityEvent` with `actor="agent"` exists in the workspace | ④ done + checklist completion |
| `has_key` (new) | the workspace has ≥1 `ApiToken` | whether ④ shows "Generate key" vs "Listening…" |

`completed`/`done`/`current` continue to count the four **step** signals
(`has_area`, `has_slice`, `has_bite`, `connected`); `has_key` is an auxiliary
render hint, not a fifth step.

## Step ④ card — the three sub-states

Rendered inside the existing `<details>` concept card (reusing the same
philosophy copy: "You built the structure by hand — now hand off the work").

1. **No key yet** (`not has_key`): MCP endpoint (copyable) + **"Generate agent
   key"** button.
2. **Key made, agent not yet active** (`has_key and not connected`): the
   snippets area (from the generate response) + a live **"Listening for your
   agent…"** poller.
3. **Agent connected** (`connected`): ④ is checked; the card shows a compact
   **"🎉 Your agent just joined"** confirmation (from the celebrate fragment).

The one-time raw token is shown **only** in the generate response (matching
today's one-time-reveal). On a later Home reload with `has_key and not
connected`, the card shows the endpoint + "Listening…" + a "Generate another
key" affordance (no stale token echoed).

## Backend

Move the two welcome endpoints into the onboarding views, now **tenant-scoped**
under the workspace URL prefix `P = "<org>/<ws>/"` (so they use
`get_current_workspace`, not `resolve_fallback_workspace`):

- **`onboarding_connect_key`** (`POST {P}onboarding/connect-key`,
  `name="onboarding_connect_key"`): `generate_token(ws, "Agent (onboarding)")`
  → render `web/partials/_get_started_key.html` with `{mcp_url, raw_token,
  agent_baseline}` (endpoint + one-time token + Claude Code / MCP JSON snippets +
  the poller, which needs `agent_baseline` as its `since`).
- **`onboarding_agent_check`** (`GET {P}onboarding/agent-activity?since=<id>`,
  `name="onboarding_agent_check"`): if an `ActivityEvent` with `actor="agent"`
  and `id > since` exists → render `web/partials/_get_started_celebrate.html`
  (no polling element → polling stops); else render
  `web/partials/_get_started_listen.html` (the poller element itself, re-served
  → polling continues). **Both are HTTP 200 — do NOT use 204.** `base.html`
  globally opts htmx into swapping on 204 (`htmx.config.responseHandling …
  {code:"204", swap:true}`, base.html:42), so a 204 here would swap empty
  content and wipe the poller. The waiting response is therefore a real fragment
  that re-renders the poller (self-replacing via `hx-swap="outerHTML"`).

**Home view (`pages.py home`)** additionally passes, only needed by the ④ card:
- `mcp_url = request.build_absolute_uri("/mcp")`
- `agent_baseline = ActivityEvent.objects.filter(workspace=ws).order_by("-id").values_list("id", flat=True).first() or 0`
  (the poller's `since`, so only **new** agent events celebrate).

## Templates & CSS

- **`_get_started.html` step ④**: replace the `<a href="{% url 'web:welcome'
  %}?step=connect">` with a single **`#gs-connect`** container holding the
  three-state card. Its initial content is chosen server-side by signal:
  `not has_key` → endpoint + "Generate agent key" button; `has_key and not
  connected` → endpoint + the "Listening…" poller + "Generate another key";
  `connected` → the compact celebrate/done confirmation. The generate button
  (`hx-post="{% wurl 'web:onboarding_connect_key' %}" hx-target="#gs-connect"
  hx-swap="innerHTML"`) and the poller both swap into `#gs-connect`.
- **New `web/partials/_get_started_key.html`** (the generate response, swapped
  into `#gs-connect`): endpoint + one-time token + Claude Code / MCP JSON
  snippets, then `{% include "web/partials/_get_started_listen.html" %}` for the
  poller. Copy buttons use the in-repo inline pattern
  `x-on:click="navigator.clipboard.writeText(...)"` (Alpine) — **not** a global
  `wCopy()` helper.
- **New `web/partials/_get_started_listen.html`** — the self-replacing poller
  element (single source, included by both `_get_started.html` state 2 and
  `_get_started_key.html`):
  `<div id="gs-listen" hx-get="{% wurl 'web:onboarding_agent_check' %}?since={{ agent_baseline }}"
  hx-trigger="every 3s" hx-target="#gs-listen" hx-swap="outerHTML">…Listening for
  your agent…</div>`. The waiting response re-serves this element (keeps
  polling); the celebrate response replaces it (stops polling). It sits below the
  snippets, so the one-time token stays visible while waiting.
- **New `web/partials/_get_started_celebrate.html`**: compact inline "🎉 Your
  agent just joined" (adapted from `_welcome_celebrate.html`, checklist-styled).
- **CSS**: add the needed connect/snippet/celebrate styles to `app.css`
  (`.gs-connect*`, code block, copy row) using `var(--token)` only — no literal
  hex, no hardcoded radius. Do **not** reintroduce the `.w-*` classes.

## Removal — must be complete (no dead code)

Delete outright:
- `tuckit/web/views/welcome.py` (the whole module — `welcome`,
  `welcome_generate_key`, `welcome_agent_check` all gone; logic reborn in
  onboarding views).
- `tuckit/web/templates/web/welcome.html` (intro step 0 + connect step 1).
- `tuckit/web/templates/web/partials/_welcome_key.html`.
- `tuckit/web/templates/web/partials/_welcome_celebrate.html`.
- `tuckit/web/static/web/welcome.css`.

Edit:
- **`tuckit/web/urls.py`**: remove `path("welcome/", …)`, `welcome/key`,
  `welcome/agent-activity`, and the `welcome as welcome_views` import; add the
  two `onboarding_*` routes under `P`.
- **`tuckit/web/views/accounts.py`**: `register_view` → redirect to Home
  (`return redirect("web:home", org_slug=org.slug, ws_slug=ws.slug)`, using the
  `org, ws` from `register(...)`) instead of `web:welcome`. (The self-service
  signup already creates the org+workspace, so Home + the checklist is the
  landing.)
- **`landing_route` / `resolve_fallback_workspace`**: keep — still used by root,
  first_org, context processors. Only the `web:welcome` **target** disappears;
  no leaf points at it anymore.

Verify nothing dangles: after the change, `grep -rniI "welcome"` over
`tuckit/web` (templates, views, urls, static) and the tests must return **no
live reference** to the removed page/URLs/partials/css (only unrelated words
like "welcome" in prose copy, if any, are acceptable — there should be none in
code). This grep is part of the Definition of Done.

## Tests

- **Remove** `tests/web/test_welcome.py` entirely (the page is gone), including
  the intro-CTA and `?step=connect` deeplink tests added earlier.
- **`OnboardingState`** (`tests/test_services_onboarding.py`): `connected` now
  keyed to an agent `ActivityEvent` (not a token); add `has_key` (token) cases.
  A workspace with a token but no agent event → `has_key True, connected False,
  done False`. With an agent event → `connected True`.
- **New `tests/web/test_onboarding_connect.py`**:
  - `POST {P}onboarding/connect-key` creates exactly one `ApiToken` and the
    response contains the raw token once + the snippets.
  - `GET {P}onboarding/agent-activity?since=N` → the listen fragment (200,
    contains `id="gs-listen"` poller) when no agent event after N; the celebrate
    fragment (200, real `target_label`, no poller) when an `actor="agent"`
    `ActivityEvent` with id > N exists. (Never 204 — see base.html:42.)
  - Step ④ card states render by signal: no key → "Generate"; key & no agent →
    poller present (`onboarding/agent-activity` in body); agent event → ④ shown
    done / celebrate copy.
- **`tests/web/test_get_started.py`**: ④ no longer links to `/welcome/`;
  `has_key`/`connected` gating of the sub-states.
- **`register`**: self-service signup now redirects to `web:home` (assert), not
  `web:welcome`; invite flows unchanged.
- Full `uv run pytest` green; design-system drift test still passes (welcome.css
  removed; new styles are in app.css, not a token file).

## Boundaries

- Public/private boundary intact — all generic product onboarding; MCP endpoint,
  tokens, activity are already core; no billing/pricing copy.
- Don't change MCP/API behavior, tenant isolation, or the activity/actor
  threading (the poller relies on the existing `actor="agent"` events).
- `docs/superpowers/` stays untracked.

## Definition of done

- Checklist ④ connects the agent **inline** — generate key, copy Claude Code /
  MCP JSON, and see the live "🎉 your agent just joined" celebration — without
  ever leaving Home.
- ④ completes when the agent actually writes (agent `ActivityEvent`), not when a
  key is minted.
- `/welcome/` and its intro narrative are **completely gone**: no view,
  template, partial, css, URL, or test references remain (verified by grep).
- Self-service signup lands on Home; light/dark + mobile composed; token-only
  CSS; all tests green; boundary intact.
