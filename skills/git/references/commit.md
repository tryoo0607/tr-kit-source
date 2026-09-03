# 커밋 컨벤션 (상세)

hot 한 줄 규칙(플러그인 `{{AGENT_FILE}}`)의 확장. **한 줄 Conventional Commits 제목만, 본문·트레일러 없음.**

## 형식
```
type(scope): 설명
```
- **type·scope = 영문**(Conventional). **설명 = 기본 한글**(필요 시 영문).
- scope는 선택(모듈/영역). 예: `feat(rules): DSL 파서 추가`, `fix: 로그인 리다이렉트 오류`.
- 본문·기타 트레일러 **없음** — 제목 한 줄만.
- ⛔ **{{PRODUCT}} 자동 footer 전부 제거** — 아래 자동 트레일러를 **넣지 않는다.**
<!-- if:claude -->
  - `🤖 Generated with Claude Code`, `Co-Authored-By: Claude…`, `Claude-Session:…`
<!-- /if -->
<!-- if:codex -->
  - Codex가 자동으로 붙이는 트레일러(있으면)
<!-- /if -->
- **제목 길이**: ~50자 목표(넘으면 72 이내).
- **Breaking change**: `type!` 로 표기(`feat!: …`). footer 안 쓰므로 `!` 사용.
- 이슈 번호는 커밋에 안 붙이고 **PR 본문 `## 관련`** 에.

## 회사(tr-work) 오버레이 [scope 승리, §P8]
- **회사 repo/작업 커밋은 tr-work 플러그인의 `tc-commit` 양식을 우선 따른다**(있으면). 이 기본 컨벤션을 tr-work가 덮어씀. 소프트의존 — tr-work 미설치면 이 기본으로 fallback.

## 허용 type (이 목록만 사용 — 자족)
| type | 뜻 |
|---|---|
| feat | 기능 추가 |
| fix | 버그 수정 |
| docs | 문서만 변경 |
| refactor | 동작 불변 구조 개선 (버그·기능 아님) |
| test | 테스트 추가·수정 |
| chore | 잡무(빌드 외 설정·정리) |
| perf | 성능 개선(동작 불변, 더 빠름) |
| build | 빌드 시스템·의존성 |
| ci | CI 설정 |
| style | 포맷·세미콜론 등(로직 불변) |

> 참고(참고용 링크, 의존 아님): conventionalcommits.org. **허용 목록은 위 표가 정본.**

## atomic 규칙
- **한 커밋 = 한 논리 변경.** 기능과 리팩터를 한 커밋에 섞지 않는다.
- 큰 변경은 논리 단위로 쪼개 여러 커밋. 되돌리기·리뷰 쉬움.
- WIP·잡동사니 뭉텅이 커밋 금지.

## 언어
- 이 repo({{KIT_REPO}})·개인 프로젝트: 설명 한글 기본.
- 회사/영문 컨벤션 repo: 그 repo 관례 우선(선례 감지).

## 커밋 전 점검 (pre-commit gate) [행동 규칙]
커밋 직전 아래를 확인한다. (자동 훅 셋업은 미래 `secrets`/훅 스킬 — 지금은 행동 규칙 + repo에 훅 있으면 존중)
| 검사 | 내용 |
|---|---|
| **secret/자격증명** ⭐ | API key·token·password·`.env`·개인키 실수 커밋 차단 |
| **머지 충돌 마커** | `<<<<<<<` `=======` `>>>>>>>` 잔존 없나 |
| **디버그 잔재** | `console.log`·`print`·`breakpoint`·임시 `TODO/FIXME` |
| **대용량/바이너리** | 실수로 큰 파일·빌드산출물 staged 안 됐나 |
| **의도한 파일만 staged** | `git add .` 광범위 스테이징 주의 → `git status` 확인 |
| repo 린트/포맷 | 있으면 통과 후 커밋 |
- secret 의심 발견 시 **커밋 중단**하고 제거(경로/변수 참조로 대체). 이미 커밋됐으면 히스토리 정리까지 안내.
