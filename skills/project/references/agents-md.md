<!-- if:claude -->
# AGENTS.md / CLAUDE.md 배치

repo 루트에 **AGENTS.md(정본) + CLAUDE.md(얇은 래퍼)**.

## 각각
| | AGENTS.md | CLAUDE.md |
|---|---|---|
| 정체 | 크로스툴 표준 에이전트 지침(agents.md 규약) | Claude Code 전용 지침 |
| 읽는 주체 | 여러 AI 툴(Claude Code·Cursor 등) | Claude Code |
| 위치 | repo 루트 | repo 루트 (+ 글로벌·중첩) |
| 로드 | Claude Code가 읽음 | 매 세션 자동(hot) |

## 패턴 — AGENTS.md 정본 + CLAUDE.md = `@AGENTS.md`
```
<repo>/
├── AGENTS.md      # 정본: 빌드/테스트 명령·코드컨벤션·아키텍처·제약·gotcha (짧게!)
└── CLAUDE.md      # 내용 = @AGENTS.md  (한 줄)
```
- Claude Code는 `CLAUDE.md`를 매 세션 자동 로드. 안에 `@AGENTS.md` 적으면 AGENTS.md를 끌어와 로드.
- **지침은 AGENTS.md에 한 번만**, CLAUDE.md는 가리키기만(DRY). 유저 글로벌 `~/.claude/CLAUDE.md`="AGENTS.md"와 동일 패턴.

## AGENTS.md에 담는 것 (중요)
매 세션 로드(hot tier) → **짧고 고신호만.**
- **담기**: 빌드/테스트/린트 명령, 코드 스타일, 아키텍처 한눈, 핵심 제약, "절대 하지 마" 규칙.
- **안 담기**: 긴 절차(→skill), 상세 설계(→_local-docs), 탐색(→_local-docs).

## 구분
- **AGENTS.md vs _local-docs**: AGENTS.md="여기서 어떻게 일하나"(에이전트용·상시). _local-docs="설계·이력"(필요 시).
- **AGENTS.md vs memory**: repo에 넣어 공유·버전관리할 규칙→AGENTS.md. Claude 사적 recall→memory.

## 생성
`odin:init`(있으면)이 코드베이스 분석해 AGENTS.md 생성/개선 — **소프트의존**. 없으면 위 골격으로 직접.
<!-- /if -->
<!-- if:codex -->
# AGENTS.md 배치

codex는 `AGENTS.md`를 자동 로드한다. repo 루트에 `AGENTS.md` 하나면 된다 — CLAUDE.md 래퍼 불필요.
nested `AGENTS.md`/`AGENTS.override.md`로 하위 디렉토리 재정의 가능.
<!-- /if -->
