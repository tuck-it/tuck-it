# Onboarding: learn the primitives by hand — design

**Date:** 2026-07-15
**Repo:** `tuckit` (public core — ships to self-host AND cloud)
**Status:** design approved (brainstorm), spec for implementation
**Evolves:** `2026-07-13-first-run-onboarding-design.md` — reuses its `/welcome/`
flow, derived-state model, and design system, but **reorders the philosophy**
(see below).

## The shift from the 2026-07-13 spec

The earlier onboarding put the differentiated "aha" — **connect your AI agent** —
as step 1 (north star first), and left slice/bite creation to happen *as a
side effect of the agent working*. It also auto-created a throwaway `Default`
area at signup.

Two things were off:

1. **A `Default` area nobody asked for.** `create_workspace()` seeds both
   `Triage` and `Default` (`services/orgs.py:56`). `Default` is an empty shell
   the user never chose — clutter that also *steals the first real action*
   ("create an Area") from the newcomer.
2. **Understanding was being outsourced.** If the agent creates the first
   Area/Slice/Bite, the human never forms a mental model of the primitives.
   Per Karpathy: *you can outsource the work to an AI, but you cannot outsource
   the understanding.*

This spec resolves both by making the **human build the structure by hand
first** (Area → Slice → Bite, one at a time, with the concept explained at each
step), and only **then** hand the ongoing *work* to the agent. The two are not
alternatives — they are a **sequence**: understand first, delegate second.

This also matches how the category leaders actually onboard. Linear drops you
into the real workspace with a "get familiar" task checklist that teaches
through *doing*, and its activation moment is completing a real issue — not a
blocking wizard, not seeded demo data. Asana/Airtable lean on structured empty
states with one obvious next action. The anti-pattern (ClickUp) is a
configuration wall up front. We follow the Linear model: **an inline checklist
on the real dashboard.**

## Philosophy (confirmed)

- The tool works for the product, not the other way around (Linear). The manual
  creation must feel like *learning by doing*, never data-entry labor — each
  step is light, immediately shows why it is useful, and is skippable.
- Human builds Area → Slice → Bite by hand = forming understanding (cannot be
  outsourced). Connecting the agent = delegating the work.

## Key decisions (all confirmed)

- **Teaching surface:** inline "Get started" checklist on the real Home
  dashboard (Linear-style), **not** a dedicated step-by-step wizard (the pattern
  the leaders avoid) and **not** seeded sample data.
- **Four steps, in order:** ① create first Area → ② add first Slice → ③ break it
  into Bites → ④ connect your agent. This reorders the previous 3-step checklist
  and drops the old "Triage it into an area" step.
- **Each step expands to a detailed concept card** (definition · example · why
  it's useful · CTA). Concept clarity is a first-class requirement — a newcomer
  may not know what Area/Slice/Bite mean.
- **No more auto-`Default` area.** A fresh workspace has only `Triage`; the first
  real Area is the one the user creates in step ①.
- **First-run entry:** keep the one-screen `/welcome/` intro hero (sets the
  "why"), then land on the **real Home dashboard** with the checklist as the
  hero. The agent-connect screen becomes the destination of checklist step ④,
  not a forced step 1.
- **Non-blocking & skippable:** the existing `onboarding_dismissed` dismiss and
  "Skip" affordances stay.
- **Copy:** English (matches existing `welcome.html` / `_get_started.html`).

## Concept card copy (the crux)

Each card: *definition · example · why useful · CTA*. Verbatim copy below
(English UI to match existing screens; refine wording during implementation but
keep the four-part shape and the plain-language definitions).

### ① Area — *A long-lived domain of responsibility.*
> An Area is a part of your product that keeps needing work — it never gets
> "done," it's a **home** for work. Everything you capture lives in one, so
> nothing floats around unowned.
>
> *Examples: `Backend`, `Marketing`, `Mobile`. (`Triage` is the one built-in
> Area — the inbox for anything not yet sorted.)*
>
> `[ + Create your first Area ]`

### ② Slice — *One chunk of product work.*
> A Slice is a single idea, feature, or fix. It moves through a status:
> **idea → planned → building → shipped**. Drop a raw idea as a Slice in seconds
> (`idea` = "do this next session") and flesh out the spec later.
>
> *Examples: "Retry failed webhooks", "Redesign the login screen".*
>
> `[ + Add a Slice to <the Area you just made> ]`

### ③ Bite — *One implementation step of a Slice.*
> Bites break a Slice into concrete to-dos: **todo → doing → done**. They turn a
> Slice into a checklist you — or your agent — knock out one at a time. When
> every Bite is done, the Slice ships.
>
> *Example: under "Retry failed webhooks" → "Add exponential backoff",
> "Cap retries at 5".*
>
> `[ + Break your Slice into Bites ]`

### ④ Connect your agent — *Now hand off the work.*
> You just built the structure by hand — so you **understand** it. From here
> your AI agent reads and writes these same Areas, Slices, and Bites over MCP.
> It does the work; nothing it does slips past you.
>
> `[ Connect your agent → ]`  (deep-links to the `/welcome/` connect step)

Step ④ voices the philosophy explicitly: you built it, so you understand it —
now the agent fills it in.

## State model — 4-signal derived state, no new flags

Redefine `OnboardingState` in `core/services/onboarding.py` from the current
`(connected, captured, triaged)` to **four derived signals, computed by query**
(idempotent — a user who already has data is auto-checked):

| Field | Done when |
|-------|-----------|
| `has_area` | a **non-triage** `Area` exists in the workspace |
| `has_slice` | any `Slice` exists in the workspace |
| `has_bite` | any `Bite` exists in the workspace |
| `connected` | the workspace has ≥1 `ApiToken` |

- `completed` = count of the four; `done` = all four.
- **No new persisted field.** The only onboarding state on the model remains the
  existing `Workspace.onboarding_dismissed` (controls card visibility).
- Onboarding is workspace-scoped, for the creator; invited members skip it.

## Remove the auto-`Default` area

- Delete `create_area(ws, "Default")` at `services/orgs.py:56`.
  `create_workspace()` keeps `get_or_create_triage(ws)` only.
- Consequence: a fresh workspace (self-service signup **and** `bootstrap` local
  dev, which routes through `create_workspace`) has exactly one Area, `Triage`.
- **Fix fallout:** audit `bootstrap` and the test suite for anything that assumes
  a `Default` area exists and update those assertions. (`bootstrap` names the
  *workspace* "Default"; that is unrelated to the area and stays.)
- Between signup and step ①, the workspace legitimately has only `Triage`. That
  empty Home is the intended nudge ("👋 Create your first Area to get started") —
  a guiding empty state with one obvious action. A user in a hurry can still
  quick-capture a Slice into `Triage`.

## First-run entry flow

```
signup (register_view)
   → /welcome/  (intro hero only: "why tuckit")   ← button: "Set up your workspace →"
   → Home dashboard  (Get started checklist is the hero; workspace has only Triage)
        ① create Area  ② add Slice  ③ add Bite  ④ connect agent → /welcome/ connect step
```

- `register_view` continues to redirect to `web:welcome` (unchanged), but
  `welcome.html`'s intro CTA changes from "Connect your agent →" to
  **"Set up your workspace →"**, navigating to Home instead of forcing the
  connect step.
- `welcome.html` **keeps** its connect + live-celebrate sections; they are now
  reached via checklist step ④ (deep-link to the connect step, e.g. a
  `?step=connect` / hash that sets the Alpine step state). The live agent
  detection + celebration mechanism is unchanged from the 2026-07-13 spec.
- Invite flows still redirect to `web:home` (unchanged).

## Flow B — the 4-step "Get started" checklist

Redesign `web/templates/web/partials/_get_started.html` (styled in `app.css`),
pinned at the top of Home while incomplete.

- **Visibility:** show iff `not workspace.onboarding_dismissed AND not
  onboarding.done`.
- **Four steps**, each rendered checked / open / gated:
  1. **Create your first Area** — done when `has_area`. CTA creates an Area
     (inline row or the existing create-area modal).
  2. **Add your first Slice** — done when `has_slice`. CTA creates a Slice inside
     the Area just made (or Triage). Gated until `has_area`.
  3. **Break it into Bites** — done when `has_bite`. CTA adds a Bite to that
     Slice. Gated until `has_slice`.
  4. **Connect your agent** — done when `connected`. CTA → `/welcome/` connect
     step.
- **Expand for the concept card** (§ Concept card copy). Collapsed = one line;
  expanded = definition + example + why + CTA. Sensible default: the first
  incomplete step is expanded.
- **Sequential gating:** a step whose prerequisite is unmet renders greyed with
  "Complete the step above first." (Slices need an Area, Bites need a Slice —
  enforced by the FK chain anyway; the gating is a UX cue, not new validation.)
- **Progress + Dismiss:** "N of 4 done" and a "Dismiss" control →
  `onboarding_dismissed=True` (hides permanently).
- When ①–③ are done, surface a small "🎉 You've got the structure — now let your
  agent do the work" to emphasize step ④ (the handoff).
- Steps still auto-complete from real data (e.g. if the agent writes first, or
  the user created things before opening the card).

## Design & boundaries

- Reuse the existing design system: `var(--token)` only, no literal hex / no
  hardcoded radius, single teal accent, full light/dark, human = sans / agent &
  code = mono. Checklist + concept-card styles live in `app.css` (app-shell
  component); `welcome.css` only gains the intro-CTA label change.
- `prefers-reduced-motion` respected; visible focus; keyboard operable; no
  horizontal overflow at 320px.
- Public/private boundary intact — all generic product onboarding; no
  billing/pricing copy. MCP endpoint, tokens, activity are already core.
- Don't change MCP/API behavior, tenant isolation, activity/actor threading, or
  invite-flow redirects.
- `docs/superpowers/` stays untracked — spec not committed to public `tuckit`.

## Testing strategy

- `create_workspace()` / `register` now yields exactly one Area (`Triage`), no
  `Default`; update any test/bootstrap assuming `Default`.
- `OnboardingState` four-signal derivations: fresh workspace → all false; after a
  non-triage Area → `has_area`; after a Slice → `has_slice`; after a Bite →
  `has_bite`; after an `ApiToken` → `connected`; all four → `done`.
- Checklist visibility: shown when not dismissed and not done; hidden when
  dismissed or done.
- Sequential gating: Slice/Bite steps render gated until their prerequisite
  exists.
- `register_view` still redirects to `/welcome/`; invite flows still redirect to
  `web:home` (unchanged).
- `welcome.html` intro CTA navigates to Home; the connect step is reachable via
  step ④'s deep link; live celebration path unchanged.
- Empty Home (only Triage, nothing else) renders the guiding "Create your first
  Area" state, not a dead end.
- Full `uv run pytest` green; design-system drift test still passes.

## Definition of done

- A newly-registered user lands on the intro, then a real Home whose "Get
  started" checklist walks them through creating their **own** first Area, then a
  Slice, then Bites — each with a plain-language concept explanation — and
  finally to connecting their agent.
- No `Default` area is ever created; the first non-triage Area is one the user
  chose.
- The checklist auto-completes from real data, gates steps in order, and can be
  dismissed.
- Light/dark + mobile composed; token-only CSS; all tests green; boundary
  intact.
```