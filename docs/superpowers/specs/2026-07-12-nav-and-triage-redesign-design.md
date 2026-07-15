# 내비게이션 재설계 & Inbox→Triage — 설계 문서

- **작성일**: 2026-07-12
- **상태**: 설계 확정, 구현 대기
- **대상 repo**: `tuckit` (public, BSL 1.1)
- **범위**: 웹 대시보드의 사이드바 IA 전면 재설계 + 캡처 통 개명(Inbox→Triage) + Home 상태 대시보드 + 활동 로그 + 캡처 UX 수정

> 용어: 영어 라벨/식별자는 그대로, 설명은 한국어. UI 노출 문자열은 최종적으로 전부 영어로 간다(사용자 방침).

---

## 1. 배경 / 문제

tuckit의 정체성은 **"제품 상태·로드맵·미뤄둔 일의 단일 진실 공급원(single source of truth), 사람(웹)과 AI 에이전트(MCP)가 함께 읽고 쓰는 워크스페이스"** 다. 그런데 현재 사이드바는 이 정체성을 못 살린다.

현재 사이드바(위→아래): `홈 · 인박스(카운트) · 캡처(버튼) · Areas(동적 목록 + ＋Area) · 설정 · 다크모드 토글`.

확인된 문제:

1. **평평함** — 홈·인박스·캡처·Areas·설정이 위계/그룹 없이 한 줄로 나열돼 무엇이 주요 메뉴인지 안 보인다.
2. **"지금 상태가 어떤데?"가 사이드바에서 안 보인다** — 제품 상태 트래커인데 정작 내비게이션이 상태를 드러내지 않는다.
3. **"인박스" 네이밍 위화감** — Linear 등에서 "Inbox = 나에게 온 알림"으로 굳어져 있는데, tuckit의 인박스는 "내가 던져넣는 캡처 통"이라 방향이 반대로 읽힌다.
4. **캡처 UX 결함** — 캡처 후 성공 피드백(토스트)이 없고, Triage 페이지를 보고 있어도 새 항목이 목록에 즉시 반영되지 않아 새로고침이 필요하다. (`capture()` 뷰가 카운트 배지 OOB 스왑만 하기 때문.)

## 2. 목표 / 비목표

**목표**
- 사이드바를 3그룹으로 위계화하고, 상태 신호를 내비게이션에 상주시켜 "지금 상태"가 한눈에 보이게 한다.
- Linear/Jira/Confluence의 관례를 따른다.
- `Inbox`를 `Triage`로 개명(필드/서비스/URL/템플릿/테스트 전수).
- Home을 상태 대시보드(주의·로드맵·진행 중·최근 활동)로 확장한다.
- human/agent 구분이 드러나는 **활동 로그**를 도입한다.
- 캡처 피드백을 풀세트(토스트+카운트+라이브 행)로 고친다.

**비목표**
- 실제 "알림(notifications)" 기능은 만들지 않는다. (`Inbox`라는 이름을 미래 알림용으로 예약해두는 아이디어는 있었으나 이번 범위 아님 — YAGNI.)
- Areas/Slice/Bite의 도메인 모델 구조 자체는 바꾸지 않는다.
- 데이터 마이그레이션 호환(기존 사용자 데이터 보존)은 고려 대상 아님 — **현재 사용자 없음**. 단 Django 스키마 마이그레이션 파일은 필요.

## 3. 핵심 결정 요약

| 항목 | 결정 | 근거 |
|---|---|---|
| 캡처 통 이름 | **Triage** | Linear의 "Triage"(들어온 항목을 분류하는 대기 큐)와 의미가 정확히 일치. Inbox와 혼동 없음. "분류되면 큐에서 빠진다"는 동작이 이름과 일치. |
| 캡처 액션 | **Capture** 버튼 (⌘K) | 액션은 메뉴 줄이 아니라 눈에 띄는 기본 버튼으로 승격(Linear "New issue" / Jira "Create"). |
| IA 방향 | **하이브리드** | 강한 Home 대시보드 + 사이드바에 핵심 상태 렌즈 상주. Linear의 절제 + Jira의 현황감 절충. |
| 상태 라벨 | Home / Attention / In Progress / Roadmap / Triage / Areas / Settings | 전부 영어. |
| 활동 로그 | 신규 `ActivityEvent` 모델(제대로 된 로그) | human/agent 공유 워크스페이스에서 "누가 무엇을 했나"가 핵심 가치. |
| `is_inbox` 필드 | `is_triage`로 개명 | 이름 일관성. |

## 4. 사이드바 IA (섹션 1 확정)

```
tuck-it                  ▾   ← workspace switcher (기존 유지)
──────────────────────────
◆ Home                       ← 상태 대시보드
──────────────────────────
  ⚠ Attention          2     ← 주의 필요 뷰 (카운트 배지)
  ▶ In Progress        4     ← building/doing 뷰 (카운트 배지)
  ▤ Roadmap                  ← 상태별 보드
  📥 Triage            3     ← 캡처 통 (카운트 배지)
──────────────────────────
AREAS                    ＋   ← 사용자 생성 동적 목록 (기존 유지)
  # Billing
  # Onboarding
  # Infra
──────────────────────────
⚙ Settings   [ ＋ Capture ]  ← Capture는 ⌘K 기본 액션 버튼
```

**그룹 구조**
1. **고정 뷰**: Home + 상태 렌즈 4종(Attention / In Progress / Roadmap / Triage).
2. **Areas**: 사용자 생성 동적 목록 + `＋ Area` 인라인 추가(기존 유지).
3. **시스템**: Settings, 다크모드 토글(기존 유지).

**카운트 배지**: Attention / In Progress / Triage 옆에 활성 카운트. (기존 `inbox_count` 컨텍스트 프로세서를 일반화.)

**Capture 버튼**: 하단 고정 + ⌘K 단축키. 어느 페이지에서든 캡처 모달을 연다(기존 모달 재사용).

## 5. Home 대시보드 (섹션 2 확정)

카드 4종, 위→아래 = "지금 뭘 해야 하나 → 전체 그림 → 내가 하는 일 → 무슨 일이 있었나":

```
┌─ Home ────────────────────────────────────────────┐
│  ⚠ Attention (2)                        [ Triage → ]│
│  • "Payment-fail alert"  — Triage 9일 방치          │
│  • "Onboarding polish"   — building, 14일째 정체     │
├────────────────────────────────────────────────────┤
│  ▤ Roadmap                              [ 전체 → ]  │
│   Idea 5 │ Planned 3 │ ▓Building 4 │ Shipped 12     │
│   [██████░░░░░░░░░░░░░░░░  누적 바 ]                 │
├────────────────────────────────────────────────────┤
│  ▶ In Progress (4)                                 │
│  • Billing · "Paddle webhook 검증"      — building  │
│  • Onboarding · "이메일 인증 붙이기"     — doing      │
├────────────────────────────────────────────────────┤
│  🕒 Recent activity                                │
│  • 🤖 agent  ·  updated "웹훅 재시도"     · 2h 전    │
│  • 👤 you    ·  created "가격표 개편"     · 5h 전    │
│  • 🤖 agent  ·  shipped "로그인 리다이렉트" · 어제    │
└────────────────────────────────────────────────────┘
```

**카드별 데이터 출처**
- **Attention** — 기존 `attention_items(workspace)` 재사용(`state.py`). stale Triage(7일) + 정체된 building. `reason` 값만 `inbox_stale→triage_stale`로 개명.
- **Roadmap** — Slice를 `status`별 count. 신규 집계 함수 `roadmap_counts(ws)`. 카드 클릭 → `roadmap/` 페이지.
- **In Progress** — `status="building"` Slice + `status="doing"` Bite. 신규 `in_progress(ws)`.
- **Recent activity** — 신규 `ActivityEvent` 최신 N개(§6).

각 카드는 상단 N개만 요약하고 "전체 →" 링크로 해당 상태 렌즈 페이지(`attention/`, `roadmap/`, `in-progress/`, `triage/`)로 연결.

## 6. 활동 로그 (섹션 2 확정)

### 6.1 배경 — 왜 서비스 계층에 심는가

모든 쓰기가 **서비스 계층 한 곳으로 수렴**함을 코드로 확인:
- 웹 뷰(`capture.py`, `mutations.py`, `board.py`, `slices.py`)와 MCP 툴(`mcp/server.py`)이 **동일하게** `services/slices.py`·`bites.py`·`areas.py`의 함수를 호출한다.
- 따라서 이벤트 기록을 서비스 mutation 함수 안에 심으면 웹·에이전트 양쪽을 한 번에 커버, 누락 위험이 낮다.
- 이미 `create_slice`/`create_bite`는 `source="human"|"agent"`를 받는다(웹=human, MCP=agent). actor 신호가 절반은 존재.

### 6.2 모델 `ActivityEvent`

```python
class ActivityEvent(models.Model):
    ACTOR_CHOICES = [("human", "Human"), ("agent", "Agent")]
    VERB_CHOICES = [
        ("created", "created"),
        ("status_changed", "status changed"),
        ("triaged", "triaged"),          # Triage → 실제 Area로 이동(분류)
        ("moved", "moved"),              # Area 간 이동(Triage 무관)
        ("edited", "edited"),            # title/spec/body 수정
        ("shipped", "shipped"),          # status_changed의 특수 케이스 표기용(선택)
        ("dropped", "dropped"),
    ]
    TARGET_CHOICES = [("slice", "Slice"), ("bite", "Bite"), ("area", "Area")]

    workspace    = models.ForeignKey(Workspace, on_delete=models.CASCADE, related_name="activity")
    actor        = models.CharField(max_length=10, choices=ACTOR_CHOICES)
    verb         = models.CharField(max_length=20, choices=VERB_CHOICES)
    target_type  = models.CharField(max_length=10, choices=TARGET_CHOICES)
    target_id    = models.IntegerField()              # soft ref (대상 삭제돼도 로그 유지)
    target_label = models.CharField(max_length=300)   # 제목 스냅샷(비정규화)
    from_value   = models.CharField(max_length=50, blank=True, default="")  # 예: 이전 status
    to_value     = models.CharField(max_length=50, blank=True, default="")  # 예: 새 status
    created_at   = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["workspace", "-created_at"])]
```

**설계 근거**
- `GenericForeignKey`(contenttypes) 대신 `target_type` + `target_id` + `target_label` 스냅샷을 쓴다: 가볍고, 대상이 삭제/드롭돼도 로그가 남는다.
- `from_value`/`to_value`로 상태 전이("planned → building")를 표현한다.

### 6.3 기록 방식

- 신규 `tuckit/core/services/activity.py`에 헬퍼:
  ```python
  def record_activity(workspace, *, actor, verb, target, from_value="", to_value=""):
      # target: Slice|Bite|Area → target_type/target_id/target_label 도출
      ...
  ```
- **actor 전달** — mutation 서비스 함수에 `actor: str = "human"` 파라미터를 추가(생성은 기존 `source`가 곧 actor). 각 함수는 DB 쓰기 뒤 `record_activity(...)` 호출.
  - 대상 서비스: `create_slice`, `set_slice_status`, `set_slice_area`, `update_slice`, `create_bite`, `set_bite_status`, `update_bite`.
  - **웹 진입점**은 `actor="human"`(기본값), **MCP 툴**은 `actor="agent"`를 넘긴다. 기존 `source=` 관례와 대칭이며 명시적이다. (대안이던 contextvar 암묵 전달은 이 코드베이스의 명시적 관례와 안 맞아 채택하지 않음.)
- **verb 매핑**
  - `create_*` → `created`
  - `set_slice_status`/`update_slice(status=...)`/`set_bite_status`/`update_bite(status=...)` → `status_changed`(`from_value`/`to_value` 채움; `to="shipped"`면 `shipped`, `to="dropped"`면 `dropped`로 세분 가능)
  - `set_slice_area` → 대상 area가 Triage에서 벗어나면 `triaged`, 그 외 Area 간 이동은 `moved`
  - `update_slice`/`update_bite`의 title/spec/body 변경 → `edited`
- **순수 reorder(`reorder_slice`/`reorder_bite`, rank만 변경)는 기록하지 않는다** — 노이즈.

### 6.4 노출

- Home "Recent activity" 카드: `workspace.activity` 최신 N개.
- (선택, Phase 3 후반) `activity/` 전체 타임라인 페이지. MVP에선 카드만으로 충분 → 우선 카드만.

## 7. 캡처 UX 풀세트 (섹션 3 확정)

`capture()` 뷰의 응답을 **OOB 스왑 3종**으로 바꾼다:

```
캡처 성공 응답 (out-of-band swaps):
  ├─ #toast          → "Captured ✓"      (항상 표시, 자동 소멸)
  ├─ #triage-count   → 배지 숫자          (항상 갱신, 기존 로직 일반화)
  └─ #triage-list    → 새 행 afterbegin   (Triage 페이지일 때만 landing;
                                           대상 컨테이너가 없으면 htmx가 무시)
```

- **핵심 트릭**: htmx OOB 스왑은 대상 id가 화면에 없으면 그냥 무시된다. 따라서 서버가 "지금 무슨 페이지인지" 몰라도, Triage 페이지를 보고 있으면 새 행이 즉시 뜨고 그 외 페이지에선 토스트만 뜬다.
- **토스트**: `base.html`에 고정 `#toast` 영역 신설. 기존 OOB 방식과 일관. 자동 소멸(Alpine/CSS).
- **연타 캡처 유지**: 모달은 열린 채 입력창 재포커스(기존 동작 유지).
- **빈 상태 처리**: Triage가 비어 "Triage clean" 플레이스홀더가 떠 있을 때 첫 행이 주입되면 플레이스홀더가 치워지도록 처리.

## 8. 기술 매핑 (섹션 4 확정) — 파일 단위

### A. `inbox → triage` 전수 개명 (기계적)
- **모델**: `tuckit/core/models/domain.py` `Area.is_inbox → is_triage`
- **마이그레이션**: `RenameField` 신규 마이그레이션
- **서비스**: `services/areas.py` — `INBOX_NAME → TRIAGE_NAME="Triage"`, `get_or_create_inbox → get_or_create_triage`; `services/orgs.py:2,43`(import·호출); `services/state.py:118-121`(필터 + `reason="inbox_stale" → "triage_stale"`)
- **웹**: `web/context_processors.py`(`inbox_count → triage_count`, `is_inbox` 필터, docstring); `tuckit/settings.py:64`(CP 경로); `web/templatetags/web_extras.py:18,33`(아이콘 키 + `reason` 분기)
- **URL 이름 충돌 해소**: `web/urls.py` — 현재 `name="triage"`가 분류 POST 액션(`slices/<id>/triage`)에 쓰임. → **페이지**를 `triage/` `name="triage"`로, **기존 액션**을 `name="slice_triage"`로 개명. 액션 URL 경로 자체(`slices/<id>/triage`)는 유지 가능.
- **뷰**: `web/views/capture.py` — `inbox()` → `triage_list()`, `get_or_create_inbox` 임포트/호출 갱신
- **템플릿**: `inbox.html→triage.html`; `partials/_inbox_row.html→_triage_row.html`; `partials/_inbox_count.html→_triage_count.html`; id `inbox-list→triage-list`, `inbox-count→triage-count`; class `inbox-row→triage-row`; `_sidebar.html:7-9` 라벨(`인박스→Triage`)·아이콘·active 이름
- **CSS**: `web/static/web/app.css`의 `.inbox-row` 등
- **테스트**: `test_services_orgs/areas/slices/state/accounts`, `test_bootstrap`, `web/test_home/test_capture_inbox/test_cross_workspace_access/test_shell/test_integration` 의 `is_inbox`/`get_or_create_inbox`/`inbox_stale`/`/inbox/`/`inbox-count` 문자열 갱신. (`test_capture_inbox.py`는 파일명도 `test_capture_triage.py`로 개명 권장.)

### B. 사이드바 재구조화
- `web/templates/web/partials/_sidebar.html` 재작성(3그룹, 상태 렌즈 4종, Capture 버튼, Areas 분리)
- `app.css`에 그룹 구분/섹션 헤더/카운트 배지 스타일
- 카운트 배지 partial 일반화: `_triage_count.html`을 참고해 `_nav_count.html`(라벨·값·id 파라미터화) 도입 검토

### C. 상태 렌즈 페이지 + Home 대시보드
- **신규 URL/뷰**: `attention/`(`pages.attention`), `in-progress/`(`pages.in_progress`), `roadmap/`(`pages.roadmap`)
- **서비스 집계**: `services/state.py`에 `roadmap_counts(ws)`, `in_progress(ws)` 신설(기존 `attention_items` 재사용)
- **템플릿**: `home.html`을 4카드 대시보드로 확장 + 각 렌즈 페이지 템플릿
- **컨텍스트 프로세서**: Attention/In Progress 카운트 배지용 값 노출(`triage_count` 옆에 `attention_count`, `in_progress_count`)

### D. 활동 로그
- 신규 모델 `ActivityEvent`(`domain.py` 또는 신규 `models/activity.py`) + 마이그레이션
- 신규 `services/activity.py`(`record_activity`)
- mutation 서비스에 `actor` 파라미터 추가 + `record_activity` 호출(`slices.py`, `bites.py`, 필요시 `areas.py`)
- MCP 툴(`mcp/server.py`)의 mutation 호출에 `actor="agent"` 전달
- 웹 뷰의 mutation 호출은 기본값(`"human"`) 사용
- Home "Recent activity" 카드 렌더

### E. 캡처 UX
- `web/views/capture.py` `capture()` — OOB 3종 응답으로 변경
- `web/templates/web/base.html` — `#toast` 영역 + htmx OOB 재삽입 관련 설정(기존 base.html:26 주석 참고: 삭제/빈 요소 스왑을 위해 opt-in 되어 있음)
- `_triage_row.html`(개명본) 재사용, 빈 상태 플레이스홀더 처리

## 9. 구현 단계(Phasing)

스펙은 전체를 담되 구현은 3단계로 분리:

- **Phase 1 — 체감 핵심**: A(개명) + B(사이드바) + E(캡처 UX). 사용자가 처음 원한 "메뉴 구조 + 네이밍 + 캡처 결함"이 여기서 해결.
- **Phase 2 — 상태 가시화**: C(상태 렌즈 페이지 + Home 대시보드; Recent activity 카드는 자리만).
- **Phase 3 — 활동 로그**: D(모델·기록·actor 스레딩·Recent activity 카드 채움). 가장 무겁고 독립적.

각 Phase는 독립 구현 계획(writing-plans) 대상. Phase 1 완료 시 앱이 정상 동작해야 함(Phase 2/3 없이도).

## 10. 테스트 전략

- **A(개명)**: 기존 테스트를 개명해 그대로 통과시키는 것이 회귀 방지. `RenameField` 마이그레이션 적용 후 전체 `uv run pytest` 그린.
- **B/E**: 캡처 응답에 `#toast`/`#triage-count`/`#triage-list` OOB가 포함되는지, Triage 페이지에서 캡처 시 새 행이 렌더되는지, 다른 페이지에선 토스트만 나오는지(컨테이너 부재) 검증.
- **C**: `roadmap_counts`/`in_progress` 집계 정확성, Home에 4카드 노출, 각 렌즈 페이지 200 응답.
- **D**: 웹 mutation → `actor="human"` 이벤트 생성, MCP mutation → `actor="agent"` 이벤트 생성, verb/from/to 매핑, reorder는 이벤트 미생성, 대상 삭제 후에도 `target_label` 보존.

## 11. 미해결 사항

- 없음. (활동 로그 전체 타임라인 페이지 `activity/`는 Phase 3 후반 선택 항목으로 남김 — MVP는 Home 카드만.)
