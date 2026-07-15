# Home Dashboard Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the Home page into a scannable dashboard — a summary-cards row (counts + day-over-day deltas), a quiet needs-attention panel, a 3-column now-surface (Focus / Doing / Next+Later), and a calm recently-shipped strip — while strictly preserving the existing design system.

**Architecture:** A new `WorkspaceStatSnapshot` model records one row of counts per workspace per day. A `snapshot_today()` service upserts today's row on each Home load (lazy — no cron) and returns each metric's value plus a delta vs the most recent prior day. The `home` view feeds a `metrics` list to a redesigned `home.html` that reuses the existing `.board` column vocabulary and `_slice_row` partial. All CSS lands in `app.css` using existing tokens only.

**Tech Stack:** Django 5, pytest + pytest-django, Alpine.js + htmx (already in templates), static CSS token layers.

## Global Constraints

- **Repo:** `tuckit` (public OSS, BSL 1.1) — no billing/infra/pricing content. This feature is neutral product code and belongs here.
- **UI copy:** English only. No Korean in any template string.
- **Design system:** `var(--token)` only — never a literal hex or hardcoded radius. Radius via `--radius` (surfaces) / `--radius-small` (controls). Accent is teal `--blue`. No colored banners/bands.
- **CSS files:** edit `tuckit/web/static/web/app.css` only. Do NOT touch `tokens.brand.css`, `tokens.product.css`, or `base.css`.
- **Available tokens:** `--paper`, `--paper-deep`, `--surface`, `--line`, `--border`, `--ink`, `--ink-soft`, `--ink-faint`, `--muted`, `--blue`, `--radius`, `--radius-small`, `--mono`.
- **App label:** `core`. **Migrations dir:** `tuckit/core/migrations/`.
- **Run tests:** `uv run pytest` (settings module `tuckit.settings_test`, configured in `pytest.ini`).
- **Commit frequently** — one commit per task minimum.

---

### Task 1: `WorkspaceStatSnapshot` model + migration

**Files:**
- Modify: `tuckit/core/models/workspace.py` (append new model)
- Modify: `tuckit/core/models/__init__.py` (export it)
- Create: `tuckit/core/migrations/0011_workspacestatsnapshot.py` (generated)
- Test: `tests/test_models_workspace.py`

**Interfaces:**
- Produces: `WorkspaceStatSnapshot` with fields `workspace` (FK, `related_name="stat_snapshots"`), `date` (`DateField`), `building_ct`, `backlog_ct`, `shipped_week_ct`, `attention_ct` (all `IntegerField`, default 0). Unique on `(workspace, date)`.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_models_workspace.py`:

```python
def test_stat_snapshot_unique_per_workspace_per_day(db):
    from datetime import date
    from django.db import IntegrityError
    from tuckit.core.models import Org, Workspace, WorkspaceStatSnapshot
    org = Org.objects.create(name="Acme", slug="acme")
    ws = Workspace.objects.create(org=org, name="P", slug="p")
    d = date(2026, 7, 14)
    WorkspaceStatSnapshot.objects.create(workspace=ws, date=d, building_ct=3)
    with pytest.raises(IntegrityError):
        WorkspaceStatSnapshot.objects.create(workspace=ws, date=d, building_ct=9)
```

Ensure `import pytest` is present at the top of the file (it is in the existing test files; add if missing).

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_models_workspace.py::test_stat_snapshot_unique_per_workspace_per_day -v`
Expected: FAIL with `ImportError` / `cannot import name 'WorkspaceStatSnapshot'`.

- [ ] **Step 3: Add the model**

Append to `tuckit/core/models/workspace.py`:

```python
class WorkspaceStatSnapshot(models.Model):
    """One row of workspace counts per calendar day, written lazily on Home
    load. Powers the Home summary cards' day-over-day deltas — no scheduler."""
    workspace = models.ForeignKey(
        Workspace, on_delete=models.CASCADE, related_name="stat_snapshots"
    )
    date = models.DateField()
    building_ct = models.IntegerField(default=0)
    backlog_ct = models.IntegerField(default=0)
    shipped_week_ct = models.IntegerField(default=0)
    attention_ct = models.IntegerField(default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["workspace", "date"], name="uniq_ws_snapshot_per_day"
            ),
        ]
        indexes = [models.Index(fields=["workspace", "date"])]

    def __str__(self):
        return f"{self.workspace.slug} @ {self.date}"
```

Then edit `tuckit/core/models/__init__.py`:

```python
from tuckit.core.models.workspace import ApiToken, Workspace, WorkspaceStatSnapshot
```

and add `"WorkspaceStatSnapshot"` to the `__all__` list.

- [ ] **Step 4: Generate the migration**

Run: `uv run python manage.py makemigrations core --name workspacestatsnapshot`
Expected: creates `tuckit/core/migrations/0011_workspacestatsnapshot.py` reporting `Create model WorkspaceStatSnapshot`.

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest tests/test_models_workspace.py::test_stat_snapshot_unique_per_workspace_per_day -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add tuckit/core/models/workspace.py tuckit/core/models/__init__.py tuckit/core/migrations/0011_workspacestatsnapshot.py tests/test_models_workspace.py
git commit -m "feat(core): add WorkspaceStatSnapshot model for Home metric deltas"
```

---

### Task 2: `snapshot_today` service

**Files:**
- Modify: `tuckit/core/services/state.py` (add function + import model)
- Test: `tests/test_services_state.py`

**Interfaces:**
- Consumes: `WorkspaceStatSnapshot`, `attention_items()` (same module), `Slice`.
- Produces: `snapshot_today(workspace) -> dict` returning keys `building`, `backlog`, `shipped_week`, `attention`, each `{"value": int, "delta": int | None}`. `delta` is `None` when there is no prior-day row.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_services_state.py` (the file already imports `create_area`, `create_slice`, `create_bite`, `timezone`, `timedelta`):

```python
def test_snapshot_today_first_day_has_no_deltas(workspace):
    from datetime import date
    from tuckit.core.services.state import snapshot_today
    from tuckit.core.models import WorkspaceStatSnapshot
    area = create_area(workspace, "Backend")
    create_slice(area, "A", status="building")
    create_slice(area, "B", status="planned")
    out = snapshot_today(workspace)
    assert out["building"] == {"value": 1, "delta": None}
    assert out["backlog"]["value"] == 1
    assert out["backlog"]["delta"] is None
    # exactly one row was written for today
    assert WorkspaceStatSnapshot.objects.filter(workspace=workspace).count() == 1


def test_snapshot_today_is_idempotent_per_day(workspace):
    from tuckit.core.services.state import snapshot_today
    from tuckit.core.models import WorkspaceStatSnapshot
    area = create_area(workspace, "Backend")
    create_slice(area, "A", status="building")
    snapshot_today(workspace)
    snapshot_today(workspace)
    assert WorkspaceStatSnapshot.objects.filter(workspace=workspace).count() == 1


def test_snapshot_today_delta_vs_prior_day(workspace):
    from datetime import timedelta as _td
    from django.utils import timezone as _tz
    from tuckit.core.services.state import snapshot_today
    from tuckit.core.models import WorkspaceStatSnapshot
    area = create_area(workspace, "Backend")
    create_slice(area, "A", status="building")
    # simulate yesterday's snapshot: 3 building
    yesterday = _tz.localdate() - _td(days=1)
    WorkspaceStatSnapshot.objects.create(
        workspace=workspace, date=yesterday, building_ct=3, backlog_ct=0,
        shipped_week_ct=0, attention_ct=0,
    )
    out = snapshot_today(workspace)
    assert out["building"] == {"value": 1, "delta": -2}  # 1 today vs 3 yesterday
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_services_state.py -k snapshot_today -v`
Expected: FAIL with `ImportError: cannot import name 'snapshot_today'`.

- [ ] **Step 3: Implement the service**

In `tuckit/core/services/state.py`, add the model to the existing model import line:

```python
from tuckit.core.models import Area, Bite, Slice, Workspace, WorkspaceStatSnapshot
```

Append this function (place it near `home_state`):

```python
def snapshot_today(workspace: Workspace) -> dict:
    """Upsert today's count row for `workspace` and return each metric's value
    plus its delta vs the most recent prior-day snapshot. Lazy — called on Home
    load, so history accrues without a scheduler. delta is None on the first day
    (no prior row) so the UI shows a value with no movement line."""
    today = timezone.localdate()
    building_ct = Slice.objects.filter(
        area__workspace=workspace, area__is_triage=False, status="building"
    ).count()
    backlog_ct = Slice.objects.filter(
        area__workspace=workspace, area__is_triage=False,
        status__in=["planned", "idea"],
    ).count()
    week_ago = timezone.now() - timedelta(days=7)
    shipped_week_ct = Slice.objects.filter(
        area__workspace=workspace, status="shipped", completed_at__gte=week_ago
    ).count()
    attention_ct = len(attention_items(workspace))

    WorkspaceStatSnapshot.objects.update_or_create(
        workspace=workspace,
        date=today,
        defaults={
            "building_ct": building_ct,
            "backlog_ct": backlog_ct,
            "shipped_week_ct": shipped_week_ct,
            "attention_ct": attention_ct,
        },
    )
    prior = (
        WorkspaceStatSnapshot.objects
        .filter(workspace=workspace, date__lt=today)
        .order_by("-date")
        .first()
    )

    def entry(value: int, field: str) -> dict:
        p = getattr(prior, field) if prior else None
        return {"value": value, "delta": None if p is None else value - p}

    return {
        "building": entry(building_ct, "building_ct"),
        "backlog": entry(backlog_ct, "backlog_ct"),
        "shipped_week": entry(shipped_week_ct, "shipped_week_ct"),
        "attention": entry(attention_ct, "attention_ct"),
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_services_state.py -k snapshot_today -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add tuckit/core/services/state.py tests/test_services_state.py
git commit -m "feat(core): add snapshot_today service for Home metric deltas"
```

---

### Task 3: View metrics + summary cards + header subtitle

Additive UI: inserts the cards row and swaps the header count for a subtitle. The single-column body below is untouched here, so existing structural tests stay green except the two header assertions updated in this task.

**Files:**
- Modify: `tuckit/web/views/pages.py` (`home` view)
- Create: `tuckit/web/templates/web/partials/_stat_cards.html`
- Modify: `tuckit/web/templates/web/home.html` (header + insert cards)
- Modify: `tuckit/web/static/web/app.css` (append card styles)
- Test: `tests/web/test_home.py`

**Interfaces:**
- Consumes: `snapshot_today()` from Task 2.
- Produces: `metrics` context var — a list of 4 dicts `{"label": str, "value": int, "delta": int|None, "abs": int|None, "dir": "up"|"down"|"flat"|None}`, in order Building, Backlog, Shipped this week, Needs attention. Rendered markup: `.stat-cards` > `.stat-card` (× n) each with `.stat-card-label`, `.stat-card-value`, optional `.stat-delta.stat-delta--{dir}`.

- [ ] **Step 1: Write the failing test**

Add to `tests/web/test_home.py`:

```python
@pytest.mark.django_db
def test_home_shows_summary_cards(client_local, workspace):
    from tuckit.core.services.areas import create_area
    from tuckit.core.services.slices import create_slice
    a = create_area(workspace, "Backend")
    create_slice(a, "Building one", status="building")
    body = client_local.get(f"/{workspace.org.slug}/{workspace.slug}/").content.decode()
    assert 'class="stat-cards"' in body
    assert "Building" in body and "Backlog" in body
    assert "Shipped this week" in body and "Needs attention" in body


@pytest.mark.django_db
def test_home_header_has_subtitle_not_count(client_local, workspace):
    body = client_local.get(f"/{workspace.org.slug}/{workspace.slug}/").content.decode()
    assert "Today's progress and what to focus on next" in body
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/web/test_home.py -k "summary_cards or subtitle" -v`
Expected: FAIL — `stat-cards` / subtitle text not in body.

- [ ] **Step 3: Wire metrics into the view**

In `tuckit/web/views/pages.py`, add `snapshot_today` to the import from `tuckit.core.services.state`, then in `home()` build `metrics` before `return render(...)`:

```python
    metrics = []
    if ws:
        snap = snapshot_today(ws)
        _defs = [
            ("Building", "building"),
            ("Backlog", "backlog"),
            ("Shipped this week", "shipped_week"),
            ("Needs attention", "attention"),
        ]
        for label, key in _defs:
            d = snap[key]["delta"]
            metrics.append({
                "label": label,
                "value": snap[key]["value"],
                "delta": d,
                "abs": abs(d) if d is not None else None,
                "dir": None if d is None else ("up" if d > 0 else "down" if d < 0 else "flat"),
            })
```

Add `"metrics": metrics,` to the render context dict.

- [ ] **Step 4: Create the cards partial**

Create `tuckit/web/templates/web/partials/_stat_cards.html`:

```django
{% if metrics %}
<div class="stat-cards">
  {% for m in metrics %}
    <div class="stat-card">
      <span class="stat-card-label">{{ m.label }}</span>
      <span class="stat-card-value">{{ m.value }}</span>
      {% if m.dir %}
        <span class="stat-delta stat-delta--{{ m.dir }}">
          {% if m.dir == "up" %}&uarr; {{ m.abs }}{% elif m.dir == "down" %}&darr; {{ m.abs }}{% else %}0{% endif %} since yesterday
        </span>
      {% endif %}
    </div>
  {% endfor %}
</div>
{% endif %}
```

- [ ] **Step 5: Edit the header + insert cards in `home.html`**

Replace the current header block (lines 4–12):

```django
  <header class="page-head">
    <div class="page-head-l">
      <h1 class="page-title">Home</h1>
      {% if workspace %}<span class="page-count">{{ building_ct }} building · {{ queued_ct }} backlog</span>{% endif %}
    </div>
    <button class="button button-small" type="button"
            x-on:click="cap = true; $nextTick(() => $refs.captureInput && $refs.captureInput.focus())">
      {% icon "plus" %}<span>Capture</span></button>
  </header>
```

with:

```django
  <header class="page-head">
    <div class="page-head-l">
      <h1 class="page-title">Home</h1>
      {% if workspace %}<span class="page-count">Today's progress and what to focus on next</span>{% endif %}
    </div>
    <button class="button button-small" type="button"
            x-on:click="cap = true; $nextTick(() => $refs.captureInput && $refs.captureInput.focus())">
      {% icon "plus" %}<span>Capture</span></button>
  </header>

  {% include "web/partials/_stat_cards.html" %}
```

- [ ] **Step 6: Append card CSS to `app.css`**

```css
/* Home summary metrics — at-a-glance counts with day-over-day movement. */
.stat-cards {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
  margin-top: 20px;
}
.stat-card {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 14px 16px;
  background: var(--paper);
  border: 1px solid var(--line);
  border-radius: var(--radius);
}
.stat-card-label { font-size: 12px; color: var(--ink-faint); }
.stat-card-value {
  font-size: 28px; font-weight: 600; line-height: 1.1;
  color: var(--ink); font-variant-numeric: tabular-nums;
}
.stat-delta { font-size: 11px; color: var(--ink-faint); font-variant-numeric: tabular-nums; }
.stat-delta--up { color: var(--blue); }
.stat-delta--down { color: var(--ink-soft); }
.stat-delta--flat { color: var(--ink-faint); }

@media (max-width: 860px) {
  .stat-cards { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}
```

- [ ] **Step 7: Update the two header-count assertions in existing tests**

In `tests/web/test_home.py`, `test_home_has_heading_and_capture` currently asserts old labels. Leave its `needs_you`/`now`/`doing` assertions for now (Task 4 revisits them) — this task only guarantees the subtitle and cards. No edit needed here yet; the new tests from Step 1 cover this task.

- [ ] **Step 8: Run the cards/subtitle tests**

Run: `uv run pytest tests/web/test_home.py -k "summary_cards or subtitle" -v`
Expected: PASS.

- [ ] **Step 9: Commit**

```bash
git add tuckit/web/views/pages.py tuckit/web/templates/web/partials/_stat_cards.html tuckit/web/templates/web/home.html tuckit/web/static/web/app.css tests/web/test_home.py
git commit -m "feat(web): add Home summary cards with day-over-day deltas"
```

---

### Task 4: Three-column now-surface (Focus / Doing / Next+Later)

Replaces the single-column `now` → `doing` → `next` → `later` stack with a 3-column grid reusing the `.board-col` vocabulary. Updates the existing tests that asserted the old single-column labels.

**Files:**
- Modify: `tuckit/web/templates/web/home.html` (replace the four middle sections)
- Modify: `tuckit/web/static/web/app.css` (append column styles)
- Test: `tests/web/test_home.py`

**Interfaces:**
- Consumes: `state.building`, `in_progress.bites`, `state.planned`, `state.ideas`, `state.someday`, `later_ct` (all already in context); `_slice_row.html`, `_status_dot.html`.
- Produces: `.home-cols` grid with three `.board-col` sections — labels (lowercase text, CSS-uppercased) `focus`, `doing`, `next`, `later`. Column counts via `.board-col-count`. Focus/Next/Later carry a `.home-col-more` "View all →" link when non-empty. Doing empty state renders a `.home-col-empty` with a Capture CTA button.

- [ ] **Step 1: Update the failing/soon-broken tests first**

Replace these tests in `tests/web/test_home.py` with the versions below (they assert the new column structure):

```python
@pytest.mark.django_db
def test_home_lists_building_and_attention(client_local, workspace):
    from tuckit.core.services.areas import create_area
    from tuckit.core.services.slices import create_slice
    backend = create_area(workspace, "Backend")
    create_slice(backend, "Payments work", status="building")
    body = client_local.get(f"/{workspace.org.slug}/{workspace.slug}/").content.decode()
    assert "Payments work" in body
    assert "<span>focus</span>" in body   # building slices now live in the Focus column


@pytest.mark.django_db
def test_home_has_heading_and_capture(client_local, workspace):
    body = client_local.get(f"/{workspace.org.slug}/{workspace.slug}/").content.decode()
    assert 'class="page-head"' in body
    assert "<span>needs_you</span>" in body
    assert "<span>focus</span>" in body and "<span>doing</span>" in body and "<span>next</span>" in body
    assert 'class="button button-small"' in body   # page-head Capture button


@pytest.mark.django_db
def test_home_active_headers_present(client_local, workspace):
    from tuckit.core.services.areas import create_area
    from tuckit.core.services.slices import create_slice
    from tuckit.core.services.bites import create_bite
    a = create_area(workspace, "Backend")
    s = create_slice(a, "Building slice", status="building")
    create_bite(s, "Doing bite", status="doing")
    body = client_local.get(f"/{workspace.org.slug}/{workspace.slug}/").content.decode()
    # needs_you stays a lead-styled group; Focus/Doing/Next are board-style columns.
    assert "group-label--lead" in body
    assert 'class="home-cols"' in body
    assert "<span>doing</span>" in body


@pytest.mark.django_db
def test_home_shows_doing_bites_and_planned_in_next(client_local, workspace):
    from tuckit.core.services.areas import create_area
    from tuckit.core.services.slices import create_slice
    from tuckit.core.services.bites import create_bite
    a = create_area(workspace, "Backend")
    s = create_slice(a, "Building slice", status="building")
    create_bite(s, "Active bite", status="doing")
    create_slice(a, "Planned next", status="planned")
    body = client_local.get(f"/{workspace.org.slug}/{workspace.slug}/").content.decode()
    assert "Active bite" in body           # doing bite in the Doing column
    assert "Planned next" in body          # planned slice in the Next column
    assert "<span>next</span>" in body
```

Also delete the now-obsolete `test_home_active_headers_are_lead_styled` (replaced by `test_home_active_headers_present` above).

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/web/test_home.py -k "lists_building or heading_and_capture or active_headers_present or planned_in_next" -v`
Expected: FAIL — `home-cols` / `<span>focus</span>` not present.

- [ ] **Step 3: Replace the middle sections in `home.html`**

Delete the current `now` status-group include, the `doing` section, the `next` fold, and the `later` fold (in the current file, the block starting at `{% include "web/partials/_status_group.html" with label="now" ...%}` through the end of the `later` `{% endif %}` — i.e. everything between the `_get_started` include and the `recently_shipped` section). Replace with:

```django
  <div class="home-cols">
    {# Focus — building slices, with progress #}
    <section class="board-col">
      <div class="board-col-head">
        <span class="board-col-label"><span>focus</span></span>
        <span class="board-col-count">{{ state.building|length }}</span>
      </div>
      <div class="home-col-body">
        {% for slice in state.building %}
          {% include "web/partials/_slice_row.html" with show_area=True show_desc=True %}
        {% empty %}
          <div class="home-col-empty"><span>Nothing in focus yet. Move a slice to building.</span></div>
        {% endfor %}
      </div>
      {% if state.building %}<a class="home-col-more" href="{% wurl 'web:roadmap' %}?view=list&status=building">View all &rarr;</a>{% endif %}
    </section>

    {# Doing — bites actively in progress #}
    <section class="board-col">
      <div class="board-col-head">
        <span class="board-col-label"><span>doing</span></span>
        <span class="board-col-count">{{ in_progress.bites|length }}</span>
      </div>
      <div class="home-col-body">
        {% for bite in in_progress.bites %}
          <a class="slice-row" href="{% wurl 'web:slice' bite.slice.id %}"
             hx-get="{% wurl 'web:slice' bite.slice.id %}?panel=1" hx-target="#panel" hx-push-url="true">
            {% include "web/partials/_status_dot.html" with status=bite.status %}
            <span class="row-title">{{ bite.title }}</span>
            <span class="row-meta">{{ bite.slice.title }}</span>
          </a>
        {% empty %}
          <div class="home-col-empty">
            <span>No bites in progress.</span>
            <button class="button button-small" type="button"
                    x-on:click="cap = true; $nextTick(() => $refs.captureInput && $refs.captureInput.focus())">
              {% icon "plus" %}<span>Start something</span></button>
          </div>
        {% endfor %}
      </div>
    </section>

    {# Next + Later stacked #}
    <div class="home-col-stack">
      <section class="board-col">
        <div class="board-col-head">
          <span class="board-col-label"><span>next</span></span>
          <span class="board-col-count">{{ state.planned|length }}</span>
        </div>
        <div class="home-col-body">
          {% for slice in state.planned %}
            {% include "web/partials/_slice_row.html" with show_area=True %}
          {% empty %}
            <div class="home-col-empty"><span>No planned work queued.</span></div>
          {% endfor %}
        </div>
        {% if state.planned %}<a class="home-col-more" href="{% wurl 'web:roadmap' %}?view=list&status=planned">View all &rarr;</a>{% endif %}
      </section>

      <section class="board-col">
        <div class="board-col-head">
          <span class="board-col-label"><span>later</span></span>
          <span class="board-col-count">{{ later_ct }}</span>
        </div>
        <div class="home-col-body">
          {% for slice in state.ideas %}{% include "web/partials/_slice_row.html" with show_area=True %}{% endfor %}
          {% for slice in state.someday %}{% include "web/partials/_slice_row.html" with show_area=True %}{% endfor %}
          {% if not state.ideas and not state.someday %}
            <div class="home-col-empty"><span>Nothing parked for later.</span></div>
          {% endif %}
        </div>
        {% if state.ideas or state.someday %}<a class="home-col-more" href="{% wurl 'web:roadmap' %}?view=list&status=idea">View all &rarr;</a>{% endif %}
      </section>
    </div>
  </div>
```

Note: the `.board-col-label` wraps an inner `<span>` so tests can match `<span>focus</span>` while the label element keeps the board's mono/uppercase styling.

- [ ] **Step 4: Append column CSS to `app.css`**

```css
/* Home three-column now-surface — reuses the board's calm grid vocabulary. */
.home-cols {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
  align-items: start;
  margin-top: 20px;
  padding: 12px;
  background: var(--paper-deep);
  border: 1px solid var(--line);
  border-radius: var(--radius);
}
.home-col-stack { display: flex; flex-direction: column; gap: 12px; min-width: 0; }
.home-col-body {
  display: flex; flex-direction: column; gap: 6px;
  padding: 10px; min-height: 96px;
}
.home-col-empty {
  display: flex; flex-direction: column; align-items: center; gap: 10px;
  padding: 22px 12px; text-align: center; color: var(--ink-faint); font-size: 13px;
}
.home-col-more { display: inline-block; margin: 0 12px 12px; font-size: 12px; color: var(--ink-faint); }
.home-col-more:hover { color: var(--ink); }

@media (max-width: 860px) {
  .home-cols { grid-template-columns: 1fr; }
}
```

- [ ] **Step 5: Run the updated tests**

Run: `uv run pytest tests/web/test_home.py -k "lists_building or heading_and_capture or active_headers_present or planned_in_next" -v`
Expected: PASS.

- [ ] **Step 6: Run the full Home + progress-bar tests to catch regressions**

Run: `uv run pytest tests/web/test_home.py -v`
Expected: the shipped-related tests (`test_home_tail_contains_shipped_items`, `test_home_recently_shipped_caps_and_links`) may still FAIL — they are fixed in Task 5. All others PASS, including `test_home_building_row_shows_progress_bar`, `test_home_now_row_shows_spec_summary`, `test_slice_row_has_status_dot_and_arrow`, `test_home_attention_shows_reason_label`, `test_home_all_clear_when_no_attention`, `test_home_stale_building_slice_not_duplicated_in_now`, `test_home_omits_roadmap_strip_and_recent_activity`.

- [ ] **Step 7: Commit**

```bash
git add tuckit/web/templates/web/home.html tuckit/web/static/web/app.css tests/web/test_home.py
git commit -m "feat(web): rebuild Home now-surface as Focus/Doing/Next+Later columns"
```

---

### Task 5: Recently-shipped strip

Replaces the collapsed shipped fold with an always-visible calm strip of chips (no confetti).

**Files:**
- Modify: `tuckit/web/templates/web/home.html` (replace the archive section)
- Modify: `tuckit/web/static/web/app.css` (append strip styles)
- Test: `tests/web/test_home.py`

**Interfaces:**
- Consumes: `state.shipped`, `shipped_total`, `shipped_hidden` (already in context); `_status_dot.html`.
- Produces: `.shipped-strip` containing `.shipped-chip` links (status dot + title + `.chip-area`), and a `.home-col-more` "View all (N) →" link to `?view=list&status=shipped` when `shipped_hidden`. Section header shows `recently_shipped` label + `shipped_total` count.

- [ ] **Step 1: Update the shipped tests**

Replace these two tests in `tests/web/test_home.py`:

```python
@pytest.mark.django_db
def test_home_recently_shipped_strip_shows_items(client_local, workspace):
    from tuckit.core.services.areas import create_area
    from tuckit.core.services.slices import create_slice
    a = create_area(workspace, "Design")
    create_slice(a, "Shipped feature", status="shipped")
    body = client_local.get(f"/{workspace.org.slug}/{workspace.slug}/").content.decode()
    assert 'class="shipped-strip"' in body
    assert "Shipped feature" in body
    assert "<span>recently_shipped</span>" in body


@pytest.mark.django_db
def test_home_recently_shipped_caps_and_links(client_local, workspace):
    from tuckit.core.services.areas import create_area
    from tuckit.core.services.slices import create_slice
    workspace.shipped_board_mode = "count"
    workspace.shipped_board_limit = 1
    workspace.save(update_fields=["shipped_board_mode", "shipped_board_limit"])
    p = f"/{workspace.org.slug}/{workspace.slug}"
    a = create_area(workspace, "Design")
    create_slice(a, "shipped one", status="shipped")
    create_slice(a, "shipped two", status="shipped")
    body = client_local.get(f"{p}/").content.decode()
    assert "View all (2)" in body                 # true total in the overflow link
    assert "status=shipped" in body               # unified view-all link
```

Delete the obsolete `test_home_tail_contains_shipped_items` (the shipped fold / `tail-body` no longer exists on Home).

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/web/test_home.py -k "shipped_strip or caps_and_links" -v`
Expected: FAIL — `shipped-strip` not present.

- [ ] **Step 3: Replace the archive section in `home.html`**

Replace the entire `<section class="group group--archive" ...> ... </section>` block (the current shipped fold) with:

```django
  <section class="group group--archive">
    <div class="group-label muted"><span>recently_shipped</span><span class="group-count">{{ shipped_total }}</span></div>
    {% if state.shipped %}
      <div class="shipped-strip">
        {% for slice in state.shipped %}
          <a class="shipped-chip" href="{% wurl 'web:slice' slice.id %}"
             hx-get="{% wurl 'web:slice' slice.id %}?panel=1" hx-target="#panel" hx-push-url="true">
            {% include "web/partials/_status_dot.html" with status=slice.status %}
            <span>{{ slice.title }}</span>
            <span class="chip-area">{{ slice.area.name }}</span>
          </a>
        {% endfor %}
        {% if shipped_hidden %}
          <a class="home-col-more" href="{% wurl 'web:roadmap' %}?view=list&status=shipped">View all ({{ shipped_total }}) &rarr;</a>
        {% endif %}
      </div>
    {% else %}
      <div class="empty muted">Nothing shipped yet.</div>
    {% endif %}
  </section>
```

- [ ] **Step 4: Append strip CSS to `app.css`**

```css
/* Recently shipped — a calm always-visible strip (no celebratory chrome). */
.shipped-strip { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; margin-top: 8px; }
.shipped-chip {
  display: inline-flex; align-items: center; gap: 6px;
  padding: 5px 10px; background: var(--paper); border: 1px solid var(--line);
  border-radius: var(--radius-small); font-size: 13px; color: var(--ink);
}
.shipped-chip:hover { border-color: var(--border); }
.shipped-chip .chip-area { color: var(--ink-faint); font-size: 11px; }
```

- [ ] **Step 5: Run the shipped tests**

Run: `uv run pytest tests/web/test_home.py -k "shipped_strip or caps_and_links" -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add tuckit/web/templates/web/home.html tuckit/web/static/web/app.css tests/web/test_home.py
git commit -m "feat(web): replace Home shipped fold with a calm shipped strip"
```

---

### Task 6: Full-suite verification

**Files:**
- Test: entire suite

- [ ] **Step 1: Run the whole test suite**

Run: `uv run pytest -q`
Expected: all tests PASS. Pay attention to `tests/web/test_design_system.py` (design-token drift) and `tests/web/test_home.py`.

- [ ] **Step 2: If the design-system drift test fails**

That test compares the two `tokens.brand.css` copies. This plan does not edit brand tokens, so a failure means an accidental edit — revert any change under `tokens.brand.css` / `tokens.product.css` / `base.css`. Only `app.css` should have changed.

- [ ] **Step 3: Manual smoke (optional but recommended)**

Run: `uv run python manage.py migrate && uv run python manage.py runserver` and load `/<org>/<workspace>/`. Confirm: 4 summary cards, deltas absent on first load, three columns, shipped strip. Reload to confirm no duplicate snapshot rows and deltas appear only after a day boundary (deltas won't show same-day — expected).

- [ ] **Step 4: Commit any fixes**

```bash
git add -A
git commit -m "test: verify Home dashboard redesign suite passes"
```

---

## Notes for the implementer

- **Snapshot writes on GET** is intentional (lazy analytics). Keep it confined to `snapshot_today`; the view is a thin caller.
- **Deltas won't appear on the same day** you first load — there's no prior-day row yet. This is correct behavior, not a bug.
- **Do not** add sparklines, a Capture dropdown/overflow menu, confetti, a scheduled job, or new roadmap routes — all explicitly out of scope.
- **`later_ct`, `building_ct`, `queued_ct`** remain in the view context; `later_ct` is still used (Later column). Leaving `building_ct`/`queued_ct` is harmless — do not spend effort removing them.
