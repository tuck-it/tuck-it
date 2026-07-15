# Nav Redesign — Phase 3 Implementation Plan (Activity Log)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans. Steps use checkbox (`- [ ]`) syntax.
>
> **DO NOT COMMIT this plan or the spec.** `docs/superpowers/` is git-ignored and must never land in the public `tuckit` repo (see the "docs/superpowers local-only" policy). Keep these files untracked.

**Goal:** Record who (human vs agent) did what (created / status-changed / triaged / moved) to slices and bites, in a new `ActivityEvent` table written from the service layer, and surface it as a Home "Recent activity" card + a dedicated `/activity/` page with a sidebar Activity lens.

**Architecture:** New `ActivityEvent` model (soft references + denormalized label so the log survives target deletion). A `record_activity` helper called from inside the mutation services — the single chokepoint both web views and MCP tools funnel through. `actor` is threaded explicitly (matching the existing `source=` convention): web entrypoints use the `"human"` default, MCP tools pass `"agent"`. Read side: `recent_activity()` + a shared `_activity_row.html` partial used by both the Home card and the Activity page.

**Tech Stack:** Django 5 (new model + migration), server-rendered templates, uv + pytest.

## Global Constraints

- **Spec:** `docs/superpowers/specs/2026-07-12-nav-and-triage-redesign-design.md` §6 (activity log). This is Phase 3 = part **D** of §9.
- **Scope decisions (agreed):**
  - **UI = both:** a light Home "Recent activity" card AND a dedicated `/activity/` page + sidebar Activity lens item.
  - **Lifecycle events only:** record `created`, `status_changed` (with `shipped`/`dropped` sub-verbs), `triaged`, `moved`. Do **NOT** record edits (title/spec/body/tags changes) or reorders — those are noise.
- **Actor threading, explicit:** add an `actor: str = "human"` param to the mutating services `set_slice_status`, `update_slice`, `set_slice_area`, `set_bite_status`, `update_bite`. Creation uses the existing `source` as the actor (no new param on `create_slice`/`create_bite`). MCP tools pass `actor="agent"`; web views use the default. `set_slice_area` is only called from the web triage view (MCP has no such tool) so it stays human in practice, but still takes the param for symmetry.
- **Do NOT record on reorder** (`reorder_slice`/`reorder_bite`) — leave them untouched.
- **Every task ends green:** `uv run pytest -q` (baseline: **254 passed**) before each commit. Adding recording to the mutation services means existing tests now also write ActivityEvents — that's a harmless side table; no existing assertion should break.
- **App label:** `core`. New migration = **0006**, depends on `("core", "0005_rename_area_is_inbox_is_triage")`.
- **Reuse:** the Activity page and Home card share one `_activity_row.html`; the sidebar Activity item reuses the existing nav/badge patterns.
- **Aesthetic:** no emoji/pills — actor shown as muted text (`agent` / `you`), matching the app's flat, token-only styling.

---

## File Structure

**Task 1 — model + helper**
- Create: `tuckit/core/models/activity.py` (`ActivityEvent`), `tuckit/core/migrations/0006_activityevent.py`, `tuckit/core/services/activity.py` (`record_activity`, `status_verb`)
- Modify: `tuckit/core/models/__init__.py` (export `ActivityEvent`)
- Test: `tests/test_services_activity.py`

**Task 2 — instrument slice services**
- Modify: `tuckit/core/services/slices.py`
- Test: `tests/test_activity_slices.py`

**Task 3 — instrument bite services + MCP actor**
- Modify: `tuckit/core/services/bites.py`, `tuckit/core/mcp/server.py`
- Test: `tests/test_activity_bites.py`

**Task 4 — Home Recent-activity card**
- Modify: `tuckit/core/services/state.py` (`recent_activity`), `tuckit/web/views/pages.py` (home passes it), `tuckit/web/templates/web/home.html`, `tuckit/web/static/web/app.css`
- Create: `tuckit/web/templates/web/partials/_activity_row.html`
- Test: `tests/web/test_home.py`

**Task 5 — Activity page + sidebar lens**
- Modify: `tuckit/web/views/pages.py`, `tuckit/web/urls.py`, `tuckit/web/templates/web/partials/_sidebar.html`, `tuckit/web/templatetags/web_extras.py` (icon)
- Create: `tuckit/web/templates/web/activity.html`
- Test: `tests/web/test_lens_pages.py`

---

## Task 1: `ActivityEvent` model + migration + `record_activity`

**Files:** Create `models/activity.py`, `migrations/0006_activityevent.py`, `services/activity.py`; modify `models/__init__.py`; test `tests/test_services_activity.py`.

**Interfaces produced:**
- `ActivityEvent` model (fields per spec §6.2).
- `record_activity(workspace, *, actor, verb, target, from_value="", to_value="")` — derives `target_type`/`target_id`/`target_label` from `target` (a Slice/Bite/Area) and inserts a row.
- `status_verb(to_status) -> str` — `"shipped"`/`"dropped"` for those targets, else `"status_changed"`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_services_activity.py`:
```python
import pytest
from tuckit.core.models import ActivityEvent, Org, Workspace
from tuckit.core.services.areas import create_area
from tuckit.core.services.slices import create_slice
from tuckit.core.services.activity import record_activity, status_verb


def _ws(slug="w"):
    org = Org.objects.create(name="Acme", slug=f"acme-{slug}")
    return Workspace.objects.create(org=org, name="W", slug=slug)


@pytest.mark.django_db
def test_record_activity_derives_target_fields():
    ws = _ws()
    a = create_area(ws, "Backend")
    s = create_slice(a, "결제 도입", status="idea")
    ActivityEvent.objects.all().delete()  # ignore the create_slice event from Task 2
    record_activity(ws, actor="agent", verb="status_changed", target=s, from_value="idea", to_value="building")
    e = ActivityEvent.objects.get()
    assert e.workspace_id == ws.id
    assert e.actor == "agent" and e.verb == "status_changed"
    assert e.target_type == "slice" and e.target_id == s.id
    assert e.target_label == "결제 도입"
    assert e.from_value == "idea" and e.to_value == "building"


@pytest.mark.django_db
def test_record_activity_survives_target_deletion():
    ws = _ws("w2")
    a = create_area(ws, "Backend")
    s = create_slice(a, "삭제될 것")
    ActivityEvent.objects.all().delete()
    record_activity(ws, actor="human", verb="created", target=s)
    s.delete()
    e = ActivityEvent.objects.get()   # log row still there
    assert e.target_label == "삭제될 것" and e.target_id is not None


def test_status_verb_maps_terminal_states():
    assert status_verb("shipped") == "shipped"
    assert status_verb("dropped") == "dropped"
    assert status_verb("building") == "status_changed"
    assert status_verb("done") == "status_changed"
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/test_services_activity.py -v`
Expected: FAIL (`ImportError: cannot import name 'ActivityEvent'`).

- [ ] **Step 3: Create the model**

Create `tuckit/core/models/activity.py`:
```python
from django.db import models

from tuckit.core.models.workspace import Workspace


class ActivityEvent(models.Model):
    ACTOR_CHOICES = [("human", "Human"), ("agent", "Agent")]
    VERB_CHOICES = [
        ("created", "created"),
        ("status_changed", "status changed"),
        ("triaged", "triaged"),
        ("moved", "moved"),
        ("shipped", "shipped"),
        ("dropped", "dropped"),
    ]
    TARGET_CHOICES = [("slice", "Slice"), ("bite", "Bite"), ("area", "Area")]

    workspace = models.ForeignKey(Workspace, on_delete=models.CASCADE, related_name="activity")
    actor = models.CharField(max_length=10, choices=ACTOR_CHOICES)
    verb = models.CharField(max_length=20, choices=VERB_CHOICES)
    target_type = models.CharField(max_length=10, choices=TARGET_CHOICES)
    target_id = models.IntegerField()
    target_label = models.CharField(max_length=300)
    from_value = models.CharField(max_length=50, blank=True, default="")
    to_value = models.CharField(max_length=50, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["workspace", "-created_at"])]

    def __str__(self):
        return f"{self.actor} {self.verb} {self.target_type}:{self.target_id}"
```

- [ ] **Step 4: Export it**

In `tuckit/core/models/__init__.py`, add the import + `__all__` entry:
```python
from tuckit.core.models.activity import ActivityEvent
```
and add `"ActivityEvent"` to the `__all__` list.

- [ ] **Step 5: Create the migration**

Create `tuckit/core/migrations/0006_activityevent.py`:
```python
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0005_rename_area_is_inbox_is_triage"),
    ]

    operations = [
        migrations.CreateModel(
            name="ActivityEvent",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("actor", models.CharField(choices=[("human", "Human"), ("agent", "Agent")], max_length=10)),
                ("verb", models.CharField(choices=[("created", "created"), ("status_changed", "status changed"), ("triaged", "triaged"), ("moved", "moved"), ("shipped", "shipped"), ("dropped", "dropped")], max_length=20)),
                ("target_type", models.CharField(choices=[("slice", "Slice"), ("bite", "Bite"), ("area", "Area")], max_length=10)),
                ("target_id", models.IntegerField()),
                ("target_label", models.CharField(max_length=300)),
                ("from_value", models.CharField(blank=True, default="", max_length=50)),
                ("to_value", models.CharField(blank=True, default="", max_length=50)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("workspace", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="activity", to="core.workspace")),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.AddIndex(
            model_name="activityevent",
            index=models.Index(fields=["workspace", "-created_at"], name="core_activi_workspa_idx"),
        ),
    ]
```
Then run `uv run python manage.py makemigrations --check --dry-run` — expected `No changes detected`. If it reports a change, your hand-written migration doesn't match the model; reconcile (don't add a second migration). If the index auto-name differs, copy the name Django wants.

- [ ] **Step 6: Create `record_activity`**

Create `tuckit/core/services/activity.py`:
```python
from tuckit.core.models import ActivityEvent

_TARGET_TYPES = {"Slice": "slice", "Bite": "bite", "Area": "area"}


def record_activity(workspace, *, actor, verb, target, from_value="", to_value=""):
    """Append one immutable activity row. Denormalizes target label so the log
    survives the target being deleted/dropped."""
    label = getattr(target, "title", None) or getattr(target, "name", "")
    ActivityEvent.objects.create(
        workspace=workspace,
        actor=actor,
        verb=verb,
        target_type=_TARGET_TYPES[type(target).__name__],
        target_id=target.id,
        target_label=(label or "")[:300],
        from_value=from_value or "",
        to_value=to_value or "",
    )


def status_verb(to_status: str) -> str:
    """The verb to record for a status change — terminal states get their own."""
    return {"shipped": "shipped", "dropped": "dropped"}.get(to_status, "status_changed")
```

- [ ] **Step 7: Migrate + run tests**

Run: `uv run python manage.py migrate --run-syncdb 2>/dev/null; uv run pytest tests/test_services_activity.py -q`
Expected: PASS.

- [ ] **Step 8: Full suite + commit**

Run: `uv run pytest -q` → 258 passed (254 + 4).
```bash
git add tuckit/core/models/activity.py tuckit/core/models/__init__.py \
  tuckit/core/migrations/0006_activityevent.py tuckit/core/services/activity.py \
  tests/test_services_activity.py
git commit -m "feat(core): ActivityEvent model + record_activity helper"
```

---

## Task 2: Instrument slice services (create / status / area)

**Files:** Modify `tuckit/core/services/slices.py`; test `tests/test_activity_slices.py`.

**Interfaces:** `set_slice_status`, `update_slice`, `set_slice_area` gain `actor: str = "human"`. Each mutation records an `ActivityEvent`. `create_slice` records `created` with `actor=source`.

- [ ] **Step 1: Write failing tests**

Create `tests/test_activity_slices.py`:
```python
import pytest
from tuckit.core.models import ActivityEvent, Org, Workspace
from tuckit.core.services.areas import create_area, get_or_create_triage
from tuckit.core.services.slices import create_slice, set_slice_status, set_slice_area, update_slice


def _ws(slug="w"):
    org = Org.objects.create(name="Acme", slug=f"acme-{slug}")
    return Workspace.objects.create(org=org, name="W", slug=slug)


@pytest.mark.django_db
def test_create_slice_records_created_with_source_actor():
    ws = _ws()
    a = create_area(ws, "Backend")
    create_slice(a, "결제", status="idea", source="agent")
    e = ActivityEvent.objects.get(verb="created")
    assert e.actor == "agent" and e.target_type == "slice" and e.target_label == "결제"


@pytest.mark.django_db
def test_set_slice_status_records_transition():
    ws = _ws("w2")
    a = create_area(ws, "Backend")
    s = create_slice(a, "결제", status="planned")
    ActivityEvent.objects.all().delete()
    set_slice_status(s, "building", actor="agent")
    e = ActivityEvent.objects.get()
    assert e.verb == "status_changed" and e.actor == "agent"
    assert e.from_value == "planned" and e.to_value == "building"


@pytest.mark.django_db
def test_set_slice_status_shipped_uses_shipped_verb():
    ws = _ws("w3")
    a = create_area(ws, "Backend")
    s = create_slice(a, "결제", status="building")
    ActivityEvent.objects.all().delete()
    set_slice_status(s, "shipped")
    assert ActivityEvent.objects.get().verb == "shipped"


@pytest.mark.django_db
def test_set_slice_status_noop_records_nothing():
    ws = _ws("w4")
    a = create_area(ws, "Backend")
    s = create_slice(a, "결제", status="building")
    ActivityEvent.objects.all().delete()
    set_slice_status(s, "building")   # same status
    assert ActivityEvent.objects.count() == 0


@pytest.mark.django_db
def test_set_slice_area_records_triaged_when_leaving_triage():
    ws = _ws("w5")
    triage = get_or_create_triage(ws)
    backend = create_area(ws, "Backend")
    s = create_slice(triage, "옮길 것")
    ActivityEvent.objects.all().delete()
    set_slice_area(s, backend)
    e = ActivityEvent.objects.get()
    assert e.verb == "triaged" and e.to_value == "Backend"


@pytest.mark.django_db
def test_set_slice_area_records_moved_between_real_areas():
    ws = _ws("w6")
    a1 = create_area(ws, "A1")
    a2 = create_area(ws, "A2")
    s = create_slice(a1, "이동")
    ActivityEvent.objects.all().delete()
    set_slice_area(s, a2)
    assert ActivityEvent.objects.get().verb == "moved"


@pytest.mark.django_db
def test_update_slice_records_only_on_status_change():
    ws = _ws("w7")
    a = create_area(ws, "Backend")
    s = create_slice(a, "제목", status="idea")
    ActivityEvent.objects.all().delete()
    update_slice(s, title="새 제목")            # edit only -> no event
    assert ActivityEvent.objects.count() == 0
    update_slice(s, status="planned")           # status -> one event
    assert ActivityEvent.objects.get().verb == "status_changed"
```

- [ ] **Step 2: Run to verify they fail**

Run: `uv run pytest tests/test_activity_slices.py -v`
Expected: FAIL (no events recorded / `set_slice_status() got unexpected keyword 'actor'`).

- [ ] **Step 3: Instrument `slices.py`**

Add the import at the top of `tuckit/core/services/slices.py`:
```python
from tuckit.core.services.activity import record_activity, status_verb
```
In `create_slice`, before `return slice_` (after the `tags` block), add:
```python
    record_activity(area.workspace, actor=source, verb="created", target=slice_)
    return slice_
```
Replace `update_slice` with:
```python
def update_slice(
    slice_: Slice,
    *,
    title: str | None = None,
    spec: str | None = None,
    status: str | None = None,
    tags: list[str] | None = None,
    actor: str = "human",
) -> Slice:
    old_status = slice_.status
    if title is not None:
        slice_.title = title
    if spec is not None:
        slice_.spec = spec
    if status is not None:
        validate_choice(status, Slice.STATUS_CHOICES, "status")
        _apply_status(slice_, status)
    slice_.save()
    if tags is not None:
        slice_.tags.set(get_or_create_tags(slice_.area.workspace, tags))
    if status is not None and status != old_status:
        record_activity(
            slice_.area.workspace, actor=actor, verb=status_verb(status),
            target=slice_, from_value=old_status, to_value=status,
        )
    return slice_
```
Replace `set_slice_status` with:
```python
def set_slice_status(slice_: Slice, status: str, *, actor: str = "human") -> Slice:
    validate_choice(status, Slice.STATUS_CHOICES, "status")
    old_status = slice_.status
    _apply_status(slice_, status)
    slice_.save(update_fields=["status", "completed_at", "updated_at"])
    if status != old_status:
        record_activity(
            slice_.area.workspace, actor=actor, verb=status_verb(status),
            target=slice_, from_value=old_status, to_value=status,
        )
    return slice_
```
Replace `set_slice_area` with:
```python
def set_slice_area(
    slice_: Slice, area: Area, *, before: Slice | None = None, after: Slice | None = None,
    actor: str = "human",
) -> Slice:
    old_area = slice_.area
    slice_.area = area
    slice_.rank = rank_for(Slice, {"area": area}, before=before, after=after)
    slice_.save(update_fields=["area", "rank", "updated_at"])
    record_activity(
        area.workspace, actor=actor, verb="triaged" if old_area.is_triage else "moved",
        target=slice_, from_value=old_area.name, to_value=area.name,
    )
    return slice_
```
(Leave `reorder_slice` untouched — no recording.)

- [ ] **Step 4: Run tests to verify pass**

Run: `uv run pytest tests/test_activity_slices.py -q`
Expected: PASS.

- [ ] **Step 5: Full suite + commit**

Run: `uv run pytest -q` → 265 passed (258 + 7).
```bash
git add tuckit/core/services/slices.py tests/test_activity_slices.py
git commit -m "feat(core): record slice lifecycle activity (created/status/triaged/moved)"
```

---

## Task 3: Instrument bite services + thread actor through MCP

**Files:** Modify `tuckit/core/services/bites.py`, `tuckit/core/mcp/server.py`; test `tests/test_activity_bites.py`.

**Interfaces:** `set_bite_status`, `update_bite` gain `actor: str = "human"`; `create_bite` records `created` with `actor=source`. MCP tools pass `actor="agent"` to the slice+bite mutation services.

- [ ] **Step 1: Write failing tests**

Create `tests/test_activity_bites.py`:
```python
import pytest
from tuckit.core.models import ActivityEvent, Org, Workspace
from tuckit.core.services.areas import create_area
from tuckit.core.services.slices import create_slice
from tuckit.core.services.bites import create_bite, set_bite_status, update_bite


def _ws(slug="w"):
    org = Org.objects.create(name="Acme", slug=f"acme-{slug}")
    return Workspace.objects.create(org=org, name="W", slug=slug)


def _slice(ws):
    return create_slice(create_area(ws, "Backend"), "S", status="building")


@pytest.mark.django_db
def test_create_bite_records_created():
    ws = _ws()
    create_bite(_slice(ws), "구현", status="todo", source="agent")
    e = ActivityEvent.objects.get(verb="created", target_type="bite")
    assert e.actor == "agent" and e.target_label == "구현"


@pytest.mark.django_db
def test_set_bite_status_records_transition_with_actor():
    ws = _ws("w2")
    b = create_bite(_slice(ws), "구현", status="todo")
    ActivityEvent.objects.all().delete()
    set_bite_status(b, "doing", actor="human")
    e = ActivityEvent.objects.get()
    assert e.target_type == "bite" and e.verb == "status_changed"
    assert e.from_value == "todo" and e.to_value == "doing" and e.actor == "human"


@pytest.mark.django_db
def test_bite_status_noop_records_nothing():
    ws = _ws("w3")
    b = create_bite(_slice(ws), "구현", status="doing")
    ActivityEvent.objects.all().delete()
    set_bite_status(b, "doing")
    assert ActivityEvent.objects.count() == 0
```

- [ ] **Step 2: Run to verify they fail**

Run: `uv run pytest tests/test_activity_bites.py -v`
Expected: FAIL.

- [ ] **Step 3: Instrument `bites.py`**

Add the import at the top of `tuckit/core/services/bites.py`:
```python
from tuckit.core.services.activity import record_activity, status_verb
```
In `create_bite`, replace the `return` with recording:
```python
    b = Bite.objects.create(
        slice=slice_, title=title, body=body, status=status, rank=rank, source=source,
    )
    record_activity(slice_.area.workspace, actor=source, verb="created", target=b)
    return b
```
Replace `update_bite` with:
```python
def update_bite(
    bite: Bite,
    *,
    title: str | None = None,
    body: str | None = None,
    status: str | None = None,
    actor: str = "human",
) -> Bite:
    old_status = bite.status
    if title is not None:
        bite.title = title
    if body is not None:
        bite.body = body
    if status is not None:
        validate_choice(status, Bite.STATUS_CHOICES, "status")
        bite.status = status
    bite.save()
    if status is not None and status != old_status:
        record_activity(
            bite.slice.area.workspace, actor=actor, verb=status_verb(status),
            target=bite, from_value=old_status, to_value=status,
        )
    return bite
```
Replace `set_bite_status` with:
```python
def set_bite_status(bite: Bite, status: str, *, actor: str = "human") -> Bite:
    validate_choice(status, Bite.STATUS_CHOICES, "status")
    old_status = bite.status
    bite.status = status
    bite.save(update_fields=["status", "updated_at"])
    if status != old_status:
        record_activity(
            bite.slice.area.workspace, actor=actor, verb=status_verb(status),
            target=bite, from_value=old_status, to_value=status,
        )
    return bite
```
(Leave `reorder_bite` untouched.)

- [ ] **Step 4: Thread `actor="agent"` through MCP**

In `tuckit/core/mcp/server.py`, add `actor="agent"` to the four mutation call sites (create_slice/create_bite already pass `source="agent"` which is the created actor — leave those):
- line ~172 `_update_slice(s, title=title, spec=spec, status=status, tags=tags)` → add `, actor="agent"`
- line ~183 `_set_slice_status(_resolve_slice(workspace, slice_id), status)` → add `, actor="agent"`
- line ~250 `_update_bite(b, title=title, body=body, status=status)` → add `, actor="agent"`
- line ~261 `_set_bite_status(_resolve_bite(workspace, bite_id), status)` → add `, actor="agent"`

Exact edits:
```python
        return slice_dict(_update_slice(s, title=title, spec=spec, status=status, tags=tags, actor="agent"))
```
```python
        return slice_dict(_set_slice_status(_resolve_slice(workspace, slice_id), status, actor="agent"))
```
```python
        return bite_dict(_update_bite(b, title=title, body=body, status=status, actor="agent"))
```
```python
        return bite_dict(_set_bite_status(_resolve_bite(workspace, bite_id), status, actor="agent"))
```

- [ ] **Step 5: Add an MCP actor test**

Add to `tests/test_activity_bites.py` (verifies the agent path records `agent` end-to-end through a service call the way MCP invokes it):
```python
@pytest.mark.django_db
def test_agent_status_change_records_agent_actor():
    from tuckit.core.services.slices import set_slice_status
    ws = _ws("w4")
    s = _slice(ws)
    ActivityEvent.objects.all().delete()
    set_slice_status(s, "shipped", actor="agent")   # how MCP calls it
    assert ActivityEvent.objects.get().actor == "agent"
```

- [ ] **Step 6: Run tests + full suite + commit**

Run: `uv run pytest tests/test_activity_bites.py tests/test_mcp_e2e.py -q && uv run pytest -q`
Expected: PASS; full suite 269 passed (265 + 4).
```bash
git add tuckit/core/services/bites.py tuckit/core/mcp/server.py tests/test_activity_bites.py
git commit -m "feat(core): record bite activity + thread agent actor through MCP mutations"
```

---

## Task 4: Home "Recent activity" card

**Files:** Modify `state.py`, `pages.py`, `home.html`, `app.css`; create `_activity_row.html`; test `tests/web/test_home.py`.

**Interfaces:** `recent_activity(workspace, limit=8) -> list[ActivityEvent]`; `home` view passes `recent_activity`; shared partial `_activity_row.html`.

- [ ] **Step 1: Write failing test**

Add to `tests/web/test_home.py`:
```python
@pytest.mark.django_db
def test_home_shows_recent_activity(client_local, workspace):
    from tuckit.core.services.areas import create_area
    from tuckit.core.services.slices import create_slice, set_slice_status
    a = create_area(workspace, "Backend")
    s = create_slice(a, "웹훅 재시도", status="planned")
    set_slice_status(s, "building")
    body = client_local.get("/").content.decode()
    assert "Recent activity" in body
    assert "웹훅 재시도" in body
    assert "planned" in body and "building" in body   # the transition
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/web/test_home.py::test_home_shows_recent_activity -v`
Expected: FAIL (`Recent activity` not in body).

- [ ] **Step 3: Add `recent_activity`**

Append to `tuckit/core/services/state.py`:
```python
def recent_activity(workspace: Workspace, limit: int = 8) -> list:
    """The workspace's most recent activity events (newest first, capped)."""
    return list(workspace.activity.all()[:limit])
```
(`ActivityEvent.Meta.ordering = ["-created_at"]` gives newest-first; `related_name="activity"`.)

- [ ] **Step 4: Pass it from the home view**

In `tuckit/web/views/pages.py`, add the import and extend `home`:
```python
from tuckit.core.services.state import (
    home_state, attention_items, roadmap_state, in_progress_state, recent_activity,
)
```
```python
def home(request):
    ws = get_current_workspace(request)
    return render(request, "web/home.html", {
        "workspace": ws,
        "state": home_state(ws) if ws else {},
        "roadmap": roadmap_state(ws) if ws else {},
        "recent_activity": recent_activity(ws) if ws else [],
    })
```

- [ ] **Step 5: Create the shared activity row partial**

Create `tuckit/web/templates/web/partials/_activity_row.html`:
```html
<div class="activity-row">
  <span class="activity-actor{% if event.actor == 'agent' %} is-agent{% endif %}">{% if event.actor == 'agent' %}agent{% else %}you{% endif %}</span>
  <span class="activity-body">{{ event.get_verb_display }} <span class="activity-target">{{ event.target_label }}</span>{% if event.to_value %} <span class="muted">{{ event.from_value }} → {{ event.to_value }}</span>{% endif %}</span>
  <span class="activity-time muted">{{ event.created_at|timesince }}</span>
</div>
```

- [ ] **Step 6: Add the Home card**

In `tuckit/web/templates/web/home.html`, add before the closing `{% endblock %}` (after the tail section):
```html
  <section class="group">
    <div class="group-label">Recent activity</div>
    {% if recent_activity %}
      <div class="panel">
        {% for event in recent_activity %}{% include "web/partials/_activity_row.html" %}{% endfor %}
      </div>
    {% else %}
      <div class="empty muted">아직 활동이 없어요</div>
    {% endif %}
  </section>
```

- [ ] **Step 7: Add styles**

Append to `tuckit/web/static/web/app.css`:
```css
/* --- Activity feed (nav redesign, Phase 3) --- */
.activity-row {
  display: flex;
  align-items: baseline;
  gap: 10px;
  padding: 8px 12px;
  line-height: 1.5;
}
.activity-actor {
  flex: 0 0 auto;
  font-size: 12px;
  color: var(--muted);
  min-width: 40px;
}
.activity-actor.is-agent { color: var(--accent); }
.activity-body { flex: 1 1 auto; min-width: 0; }
.activity-target { color: var(--text); }
.activity-time { flex: 0 0 auto; font-size: 12px; }
```

- [ ] **Step 8: Run test + full suite + commit**

Run: `uv run pytest tests/web/test_home.py -q && uv run pytest -q`
Expected: PASS; full suite 270 passed.
```bash
git add tuckit/core/services/state.py tuckit/web/views/pages.py \
  tuckit/web/templates/web/home.html tuckit/web/templates/web/partials/_activity_row.html \
  tuckit/web/static/web/app.css tests/web/test_home.py
git commit -m "feat(web): Home Recent-activity card"
```

---

## Task 5: Activity page + sidebar Activity lens

**Files:** Modify `pages.py`, `urls.py`, `_sidebar.html`, `web_extras.py`; create `activity.html`; test `tests/web/test_lens_pages.py`.

**Interfaces:** URL `web:activity` (`/activity/`); `activity` view; sidebar Activity item; icon key `activity`.

- [ ] **Step 1: Write failing test**

Add to `tests/web/test_lens_pages.py`:
```python
@pytest.mark.django_db
def test_activity_page_lists_events(client_local, workspace):
    from tuckit.core.services.areas import create_area
    from tuckit.core.services.slices import create_slice, set_slice_status
    a = create_area(workspace, "Backend")
    s = create_slice(a, "로그인 리다이렉트", status="building")
    set_slice_status(s, "shipped")
    body = client_local.get("/activity/").content.decode()
    assert "로그인 리다이렉트" in body
    assert 'href="/activity/"' in body   # sidebar link present on the page shell


@pytest.mark.django_db
def test_sidebar_has_activity_lens(client_local, workspace):
    body = client_local.get("/").content.decode()
    assert ">Activity<" in body and 'href="/activity/"' in body
```

- [ ] **Step 2: Run to verify they fail**

Run: `uv run pytest tests/web/test_lens_pages.py -k activity -v`
Expected: FAIL (404 / NoReverseMatch / label absent).

- [ ] **Step 3: Add the view**

In `tuckit/web/views/pages.py`, add:
```python
def activity(request):
    ws = get_current_workspace(request)
    return render(request, "web/activity.html", {
        "events": recent_activity(ws, limit=100) if ws else [],
    })
```

- [ ] **Step 4: Add the route**

In `tuckit/web/urls.py`, after the `roadmap/` route (added in Phase 2), add:
```python
    path("activity/", pages.activity, name="activity"),
```

- [ ] **Step 5: Create `activity.html`**

`tuckit/web/templates/web/activity.html`:
```html
{% extends "web/base.html" %}
{% block main %}
  <div class="topbar"><h1 class="area-title">Activity</h1></div>
  <section class="group">
    {% if events %}
      <div class="panel">
        {% for event in events %}{% include "web/partials/_activity_row.html" %}{% endfor %}
      </div>
    {% else %}
      <div class="empty muted">아직 활동이 없어요</div>
    {% endif %}
  </section>
{% endblock %}
```

- [ ] **Step 6: Add the icon**

In `tuckit/web/templatetags/web_extras.py`, add to `_ICON_PATHS`:
```python
    "activity": '<path d="M3 12h4l3 8 4-16 3 8h4"/>',
```
(A distinct pulse line — note this differs from the `in-progress` glyph; keep both.)

- [ ] **Step 7: Add the sidebar item**

In `tuckit/web/templates/web/partials/_sidebar.html`, add an Activity nav link inside the `nav-group`, immediately after the Roadmap `<a>` and before the Triage `<a>`:
```html
    <a class="nav{% if request.resolver_match.url_name == 'activity' %} nav--active{% endif %}"
       href="{% url 'web:activity' %}">{% icon "activity" %}<span class="nav-label">Activity</span></a>
```

- [ ] **Step 8: Run tests + full suite + commit**

Run: `uv run pytest tests/web/test_lens_pages.py -q && uv run pytest -q`
Expected: PASS; full suite 272 passed.
```bash
git add tuckit/web/views/pages.py tuckit/web/urls.py tuckit/web/templates/web/activity.html \
  tuckit/web/templates/web/partials/_sidebar.html tuckit/web/templatetags/web_extras.py \
  tests/web/test_lens_pages.py
git commit -m "feat(web): Activity page + sidebar Activity lens"
```

---

## Self-Review

**Spec coverage (Phase 3 = spec §6 / part D):**
- `ActivityEvent` model with soft refs + denormalized label — Task 1 (matches §6.2 exactly).
- `record_activity` helper in a new `services/activity.py` — Task 1 (§6.3).
- Actor threaded explicitly through mutation services; MCP=agent, web=human default — Tasks 2-3 (§6.3).
- Lifecycle verbs only (created/status_changed/shipped/dropped/triaged/moved); edits + reorders excluded — Tasks 2-3 (agreed scope, narrower than §6.2's `edited`).
- Home "Recent activity" card — Task 4 (§6.4).
- Dedicated `/activity/` page + sidebar lens — Task 5 (§6.4's optional page, promoted per the agreed "both" decision).

**Placeholder scan:** none. Every step has concrete code or exact edits. The migration includes a `makemigrations --check` guard in case the hand-written index name differs from Django's autogenerator.

**Type/name consistency:** `record_activity(workspace, *, actor, verb, target, from_value, to_value)` and `status_verb(to_status)` signatures are used identically across Tasks 2-4. `actor` param added consistently to `set_slice_status`/`update_slice`/`set_slice_area`/`set_bite_status`/`update_bite`; `create_slice`/`create_bite` use `source` as actor (no new param). Verb strings (`created`/`status_changed`/`triaged`/`moved`/`shipped`/`dropped`) match the model's `VERB_CHOICES`. `recent_activity` return type (list of `ActivityEvent`) is consumed the same way by the Home card and the Activity page via the shared `_activity_row.html`.

**Side-effect check:** adding recording to the mutation services means the whole existing suite now writes ActivityEvents. This is a harmless append-only side table; no existing test asserts activity-table emptiness. The noop guards (`if status != old_status`) prevent spurious events. If any pre-existing test unexpectedly fails, it's a real coupling worth investigating, not something to paper over.

**Out of scope confirmed:** reorder services untouched; `set_slice_area` still web-only (MCP has no tool); edits (title/spec/body/tags) deliberately not recorded; no activity for Area create/rename/delete (roadmap-movement feed stays focused on slices+bites).
