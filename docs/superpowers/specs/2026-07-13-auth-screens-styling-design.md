# Auth screens styling — design

**Date:** 2026-07-13
**Repo:** `tuckit` (public core)
**Scope:** Visual styling of the three standalone authentication templates using the
existing shared design system. No behavior, routing, form-field, or service changes.

## Problem

The account/org/tenancy/invitation backbone is fully built and tested, and production
(`tuckit-cloud`, `REGISTRATION_OPEN=True`) already serves real signups. But the three
pre-app-shell auth templates are bare, unstyled standalone HTML that load none of the
design tokens:

- `tuckit/web/templates/registration/login.html`
- `tuckit/web/templates/registration/register.html`
- `tuckit/web/templates/registration/invite_accept.html`

They render `{{ form.as_p }}` / raw `<label><input>` with no `<head>` CSS, no theme,
no responsive layout. This makes the product "look unbuilt" at its first-impression
surface. This is Phase 5 (authentication) of `MIGRATION_PLAYBOOK.md`, done ahead of
earlier phases at the user's request because the auth screens are a self-contained,
low-risk vertical slice.

## Goals

- All three auth screens use the accepted design system (paper material, tokens, fonts,
  light/dark, focus, button/form primitives).
- Screens read as one system with the rest of the app, at 320px→desktop, in both themes.
- Copy unified to **English** (login was EN, register/invite were KO).

## Non-goals (explicitly out of scope)

- Password reset / change — **next step**, separate spec.
- Email verification, social login, account-profile editing.
- `REGISTRATION_OPEN` policy (whether self-host defaults open).
- Any app-internal (post-login) screen.
- Cloud billing/upgrade surfaces (`tuckit-cloud` inherits tokens later, Phase 6).

## Protected behavior (must NOT change)

Per `MIGRATION_PLAYBOOK.md`:
- URL names / route slugs (`web:login`, `web:register`, `web:invite_accept`, `web:logout`).
- Form field **names and order** (login form fields, register `email`/`org_name`/`slug`/
  `password`, invite `password`).
- `next` hidden field behavior on login.
- `REGISTRATION_OPEN` gating and the invite-bypass of it.
- View logic, service functions, tenant isolation.
- The invite screen's three-state conditional (`invalid` / authenticated join /
  anonymous signup, email locked).
- License/legal copy; public/private repo boundary (no billing/pricing copy in core).

## Approach

### Structure: keep standalone HTML, add the token chain

The auth templates deliberately do **not** extend `web/base.html` — pre-signup there is
no active workspace, so no sidebar/app shell. That stays. Each template gets a proper
`<head>`:

- `<meta charset>` + `<meta name="viewport" content="width=device-width, initial-scale=1">`
- The theme pre-paint `<script>` copied from `base.html` (reads `localStorage.theme`,
  sets `document.documentElement.dataset.theme` before first paint; absent a choice,
  brand tokens fall back to `prefers-color-scheme`).
- Stylesheet chain, in order: `tokens.brand.css` → `tokens.product.css` → `base.css`
  → **`auth.css`**.
- **Not** `app.css` — it is screen-component CSS that assumes the sidebar/app layout and
  is unnecessary here. Confirmed: all 11 post-login templates extend `web/base.html`
  which links all four sheets; auth is the only surface not on the chain.

No visible theme toggle on auth screens (nobody is logged in yet) — the pre-paint script
still honors a previously saved preference and system theme.

### New file: `tuckit/web/static/web/auth.css`

Auth-specific layout lives in its own sheet so `base.css` stays primitives-only and
`app.css` stays app-screen-only. Every value uses `var(--token)` — no literal hex, no
hardcoded radius (`--radius` for the card, `--radius-small` for controls).

Components:

- `.auth-shell` — `min-height: 100vh`, centers its card (flex/grid place-items center),
  page padding so the card never touches edges at 320px. Sits on `--paper` (base.css
  already paints `body` + the fixed paper-texture overlay).
- `.auth-card` — `max-width` ~380px, `width: 100%`, background `--paper-raised`, border
  `1px solid --line`, `border-radius: var(--radius)`, `box-shadow` from `--shadow`,
  internal padding.
- `.auth-brand` — the `tuckit` wordmark (text; no logo asset exists), quiet, above title.
- Title uses the `h1` primitive from base.css.
- `.auth-form` — vertical stack (gap) of field groups.
- `.auth-field` — `label` (block, small, `--ink-soft`) + `input` (full width, border
  `--line`, `border-radius: var(--radius-small)`, padding; focus border `--blue` comes
  from the base.css form primitive).
- Submit: full-width `.button .button-primary` (reused from base.css).
- `.auth-error` — error banner, `--warn` toned, shown on validation/server error.
- `.auth-alt` — secondary line / link row (e.g. locked-email note on invite). Muted.

Responsive: single column already; card `max-width` + `width:100%` + shell padding
handle 320/390/768+. No horizontal overflow.

### Per-screen markup (English copy)

**login.html** — title "Log in". Render the Django auth form fields with our markup
instead of `{{ form.as_p }}` — iterate the form (or render `username`/`password`
explicitly) so each field is an `.auth-field`; preserve field names exactly. Keep the
`next` hidden input. Non-field/auth errors → `.auth-error`. **No "forgot password?"
link** this pass (reset does not exist yet — no dead link; added when reset lands).
Small "Create an account" link only if `REGISTRATION_OPEN` — optional, low priority;
default omit to keep scope tight unless trivial.

**register.html** — title "Create your account". Fields in existing order: email,
organization name, organization slug, password (names `email`/`org_name`/`slug`/
`password` unchanged). `{{ error }}` → `.auth-error`. Preserve submitted `values` on
re-render.

**invite_accept.html** — same card. Three states preserved:
- `invalid` → heading "This invite link is no longer valid." + explanation.
- authenticated user → "Join {{ invitation.org.name }}" + single Join button.
- anonymous → "Join {{ invitation.org.name }}" + locked email note (`invitation.email`)
  + password field + Join button.
`{{ error }}` → `.auth-error`.

## States to verify (subset of playbook matrix)

light / dark / system theme · 320 / 390 / 768px · reduced motion · keyboard-only ·
visible focus · validation error · server error · long org name · no horizontal overflow.

## Testing

- Keep existing pytest green (`tests/web/` auth/register/invite tests).
- Existing tests assert behavior (status codes, redirects, gating) — styling shouldn't
  break them; run to confirm.
- If any test asserts on markup that changes, update it; add view tests only for changed
  conditional markup (error banner rendering, invite anonymous-vs-authenticated branch)
  if not already covered.
- The design-system drift test (`tests/web/test_design_system.py`) must still pass —
  `auth.css` is a new sheet, not a token file, so no drift impact; verify.
- Manual/production-like render of all three screens in both themes before done.

## Files touched

- **New:** `tuckit/web/static/web/auth.css`
- **Edit:** the three `registration/*.html` templates
- **Edit (done):** `.gitignore` — `docs/superpowers/` kept untracked (local-only per
  workspace memory; brainstorming specs are never committed to public `tuckit`).
- Possibly: a test file under `tests/web/` if conditional markup assertions need updating.

## Definition of done

- All three auth screens use only accepted tokens/primitives; no literal hex/radius leak.
- Light and dark have equivalent hierarchy; focus visible; keyboard operable.
- Mobile (320px) composed, no overflow.
- All existing tests pass; changed conditional markup covered.
- Copy is English and consistent.
- Public/private boundary intact (no billing copy).
