# `_local-docs` 스키마 — v2

작업 기록이 사는 곳의 구조와 각 파일의 형식. **버전 이력은 맨 아래.**

## 위치 — 실파일은 중첩 repo 밖

```
~/projects/
├─ .git/                          meta-repo (local-docs.git)
├─ .gitignore                     /*  +  !/_docs/
├─ _docs/<project>/               🔑 실파일 — ✅ 추적됨 (작고 텍스트)
├─ _assets/<project>/             ⛔ 무시됨 — 크고 바이너리 (아래)
└─ <project>/
    └─ _local-docs → ../_docs/<project>    심링크 (.gitignore로 제외)
```

**왜:** `git add -f`는 **중첩된 git repo 안의 파일을 에러 없이 무시한다.** 프로젝트 안에 실파일을 두면 그 프로젝트가 repo인 순간 백업이 조용히 끊긴다.

> 🔑 **심링크는 정본이 아니다.** 훅·시각화는 `_docs/<name>/`을 **계산**해 접근한다 — 심링크가 깨져도 시스템은 멈추지 않고, 사람이 `ls`로 못 볼 뿐이다.

### `_assets/` — `_docs/`의 형제

`.gitignore`가 `/*`로 다 무시하고 `!/_docs/`만 예외라, **`_assets/`는 규칙을 더 안 만들어도 자동으로 무시된다.** 구조는 `_docs/`와 같게(`_assets/<project>/`) 가져간다.

| | 어디 | 예 |
|---|---|---|
| 문서에 딸린 도식 | `_docs/<project>/wiki/design/<주제>/assets/` | png·svg·mmd (수백 KB) |
| 🔑 대용량 원본 | **`_assets/<project>/`** | 로그 덤프 · 화면 녹화 · 데이터셋 |

**경계는 숫자가 아니라 질문이다** — ***"이게 git 이력에 영원히 남아도 되나?"*** 도식 300KB는 남아도 된다. 로그 덤프 500MB는 안 된다. 한번 커밋되면 되돌릴 수 없다.

> `out/<slug>/`도 `_docs/` 안이라 같은 판단을 받는다 — 보고서는 여기, 그 보고서가 참조하는 원본 덤프는 `_assets/`.

## 구조 — LLM Wiki + 작업 생명주기

```
_docs/<project>/
├─ README.md          👤🤖  안정적인 목적·경계 + | 스키마 | v2 |
├─ index.md           👤🤖  Wiki + active state 라우터(자동생성)
├─ log.md             🤖    ingest·synthesize·migrate 이력
├─ sources/           🤖    외부 근거 record·payload manifest
├─ wiki/              👤🤖  현재 project 지식
│  ├─ decisions.md    🤖    작업을 넘는 결정 (D-nnn)
│  ├─ design/         👤🤖  작업을 넘는 설계
│  └─ index.md        👤🤖  자동생성 MOC
├─ state/<slug>.md    🤖    진행 중 ← 훅이 매 턴 주입
├─ exec/<slug>.md     🤖    완료 기록 ← 자기확장이 grep. 항상 단일 파일
├─ out/<slug>/        👤    산출물 — 형식 자유
└─ cases/             🤖    검증 케이스 원장
```

`sources/`와 `wiki/`의 공통 schema·ingest·query·lint는 plugin root `core/llm-wiki/`가 정본이다.
project Wiki만 `work_refs`로 `state/`·`exec/` 근거를 연결할 수 있다. 모든 exec를 Wiki로
복제하지 않고 여러 작업에서 재사용할 구조·결정·운영 지식만 합성한다.

🔑 `state/`, `exec/`, `cases/`, `out/`는 v1 경로를 유지한다. lifecycle hook과 Stop 기록
가드가 이 위치를 직접 계산하기 때문이다.

`INBOX.md`를 사용할 경우 configured handoff repository가 있으면 그곳을 단일 입구로 삼고,
없으면 프로젝트 local-docs에 둘 수 있다. 정제해서 실제 작업이 되면 이 트리(`state`·`exec`·`wiki/decisions.md`)로 내린다.

**AI가 읽는 곳에 큰 바이너리를 섞지 않는다** — grep과 훅 주입이 오염된다.

## 산출물은 네 갈래

| 산출물 | 어디 |
|---|---|
| 작업 기록에 녹는 것 (결정·결과 요약) | `exec/<slug>.md` |
| repo에 커밋되는 것 (코드·config) | 프로젝트 repo — `_local-docs` 밖 |
| 외부로 나가는 것 (문서 시스템·MR·{{VIZ}}) | 외부. **`## 산출`에 링크 + 한 줄만** |
| 독립적으로 읽히는 문서 (보고서 등) | **`out/<slug>/`** |

---

## `state/<slug>.md`

```markdown
# console blank 설정 반영              ← 작업명 = slug

| profile | 고치기 |
| 단계 | **수행** (루프 2/3) |
| 임계 | 중간 (10분) |
| 갱신 | 2026-08-06 14:20 |

## 요구                                 ← 「정의」 산출
- [사람] 개발 서버의 console blank 설정을 config repo에 반영한다
- [AI] 기존 `console-dpms-idle.service` 형식을 따른다

## 결정                                 ← 「계획」 산출
| 결정 | 근거 | 버린 대안 |
|---|---|---|
| systemd unit으로 | 기존 방식과 일관 | cron — 상태 추적 안 됨 |

## 미결
- [ ] 재부팅 후 자동 시작 확인 필요

## 산출
- [설정 반영 보고서](../out/console-blank/report.md)

## 진행                                 ← 각 단계 `returns` 누적
### 수행 · 루프 1 (14:05)
- 결과: unit 파일 작성, ssh로 배치
- **가정**: `/etc/systemd/system` 경로 (확인 안 함)
- **확신 없음**: nouveau에서 fb0 blank가 먹는지
### [차용:만들기] 정의 (14:20)          ← 접두어. 중첩하지 않는다
### 수행 · 루프 2 (15:10)
```

**규칙:**
- 섹션이 **단계에 1:1** 대응한다 — 요구=정의 / 결정=계획 / 진행=각 단계 `returns`
- **`## 진행`은 시간순.** 차용은 접두어로 표시하고 헤딩을 중첩하지 않는다 (헤더 = 포함관계 / 진행 = 시간순)
- 서브에게 브리핑할 땐 **`## 요구` + `## 결정`만** 넘긴다
- 파일 하나 = 작업 하나. **멀티세션 동시성은 slug 분리가 해결한다**

## `exec/<slug>.md`

**state 스키마 그대로 + 결과·분류 태그·회고.** 변환이 아니라 **이동**이다 — 마무리 비용을 최소로.

```markdown
| 완료 | 2026-08-06 15:40 |
| 태그 | reuse · infrastructure |    ← 자기확장이 세는 것

## 회고
- 잘된 것 / 다시 하면 다르게 할 것
```

**분류 태그가 3건 쌓이면 넛지**한다 — *"비슷한 게 3건이다, 스킬로 만들까?"* (알림이지 게이트가 아니다)

## `wiki/decisions.md`

**작업을 넘는 결정**만. 작업 안의 결정은 `state`/`exec`의 `## 결정`에 있다.

형식은 `decision-log`(A표 + C ADR) 재사용. `D-nnn` 부여.

## `README.md`

안정적인 project 경계. **스키마 버전은 여기에 프로젝트당 한 번.** 현재 초점과 다음 작업은
`state/`와 생성 `index.md`가 정본이므로 README에 복제하지 않는다.

```markdown
# {{KIT_REPO}}

| 스키마 | v2 |
| 목적 | 이 기록 공간이 다루는 project 경계 |
| 저장소 | 선택: 대응 repository 또는 workspace |
```

## `index.md`와 `log.md`

- `index.md`는 LLM Wiki 내용과 active state 제목·단계·갱신만 보여주는 자동생성 라우터다.
- `log.md`는 `capture`, `ingest`, `synthesize`, `query`, `lint`, `migrate` 중 실제 지식
  유지보수 이력만 append한다. 읽기만 한 query는 강제하지 않는다.
- 과거 작업은 index에 모두 복제하지 않고 `rg`로 `exec/` 후보를 좁힌 뒤 직접 읽는다.

## `out/<slug>/`

**형식 자유.** 사람이 읽는 것이라 고정 스키마를 강요하지 않는다. `exec/<slug>.md`와 slug로 대응한다.

## ID

| 대상 | ID |
|---|---|
| 작업 | `slug` (파일명) |
| 결정 | `D-nnn` |
| 단계 실행 | **없음** — 시간순이면 충분 |
| 미결/이슈 | ⬜ 미정 — 시각화 툴 만들 때 기록부담 실측 후 결정 |

**ID는 "가리켜야 할 일이 있을 때만" 만든다.** 늘리면 기록 부담이 늘고, 기록 부담이 곧 기록이 안 남는 이유다.

---

## 버전 규율

| | |
|---|---|
| 표기 | `README.md`에 **프로젝트당 한 번** |
| 기본 전략 | **lazy** — 옛 버전을 읽고, **손댈 때 최신으로 갱신**. 섞여 있는 게 정상 |
| 마이그레이션이 필요한 경우 | **이름·위치·의미 변경**만 (내용 추가는 lazy로 충분) |

**파일마다 버전을 붙이지 않는다** — 그 줄은 99% 안 읽히는데 기록 부담은 매번 든다. 버전은 project README 한 곳에서 판별한다.

### 마이그레이션은 **공통 core + project 스킬** 둘로 나눈다

| | 무엇 | 왜 거기 |
|---|---|---|
| 🤖 `project/scripts/local_docs_migrate.py` | 한 project의 v2 디렉터리·README·index 생성과 legacy 후보 보고. 기본 dry-run | **멱등**이고 실제 배포되는 경로다 |
| 👤 `project` 스킬의 활동 | 기존 design·decision의 장기 Wiki 가치 판단과 schema 변환 | 스크립트가 못 한다 |

project별 opt-in이다. 28개 project를 한 번에 자동 순회하지 않는다. 그리고 🔑 **회사 머신에서 따로 돌려야 한다**(`_local-docs`는 push 금지 → 동기화가 없다) → **kit에 담겨 같이 깔리는** 위치여야 한다.

> 패턴은 `audit`과 같다 — `tools/kit-audit`이 검사하고 스킬이 해석한다.

## 버전 이력

### v2 (2026-09-04)

| v1 | v2 |
|---|---|
| `design/` | 검토 후 선별적으로 `wiki/design/`에 합성 |
| `decisions.md` | 검토 후 `wiki/decisions.md`에 합성 |
| README의 수동 현재 초점·다음 | 제거 — `state/`와 자동 index에서 계산 |
| project 지식 계층 없음 | 공통 `sources/`, `wiki/`, `index.md`, `log.md` 추가 |

`state/`, `exec/`, `cases/`, `out/`는 이동하지 않는다. 개인/NAS의 private backup push와
회사 local-only no-push 정책도 바뀌지 않는다.

### v1 (2026-08-06)

**깨지는 변경:**

| 옛 (v0) | 새 (v1) |
|---|---|
| `<project>/_local-docs/` 실파일 | 🔑 `~/projects/_docs/<project>/` + 심링크 |
| `plan/` | `design/` (**개명**) |
| `explore/` · `research/` | `exec/`(한 작업의 조사) 또는 `design/`(여러 작업에 걸친 배경) — **사람 판단** |
| `issues/` | `cases/` |
| `INDEX.md` | 🔻 **폐기** — 손으로 쓰는 인덱스는 안 갱신되면 거짓말을 한다. 목록은 시각화 툴이 자동 생성 |

**추가:** `state/` · `out/` · `decisions.md`

### v0

`README` + `explore`/`plan`/`exec` + `research`/`issues`(선택) + `INBOX` + `cases`.
프로젝트마다 실제 구조가 달랐다(실측 2026-08-06) — 규약이 L4라서 표류했다.
