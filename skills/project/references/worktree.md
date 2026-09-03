# worktree 규약

한 repo에서 **병렬 작업**(기능 짜다 급한 버그) 시 `git worktree`로 같은 repo를 딴 폴더에 동시 체크아웃. stash/브랜치 전환의 컨텍스트 깨짐을 피한다.

## 레이아웃
`<repo>.worktrees/` 하나에 몰아넣기(점 프리픽스=메타 신호). 흩어진 형제 X.
```
~/projects/<project>/
├── _local-docs → ../_docs/<project>  # ← 단일 소스 (worktree마다 복제 X)
├── <repo>/                         # 메인
└── <repo>.worktrees/
    ├── <slug-a>/
    └── <slug-b>/
```
프로젝트 루트가 항상 `[_local-docs · 메인 · .worktrees]` 로 고정 → 몇 개가 생기든 깔끔.

## 생성 — base는 항상 물어봄 (default 금지)
worktree 딸 때 base 브랜치를 **임의로 정하지 말고 매번 확인**(AskUserQuestion):

| 상황 | 명령 |
|---|---|
| ① 새 작업 (보통) | `git worktree add ../<repo>.worktrees/<slug> -b <slug> origin/main` (fetch 후) |
| ② 특정 브랜치서 딴다 | `git worktree add … -b <slug> <base-branch>` |
| ③ 기존 브랜치 이어서 | `git worktree add … <existing-branch>` (`-b` 없음) |

## 이름 한 줄기
worktree 폴더·브랜치 = 작업 slug **그대로**:
```
slug "rules-dsl" → state/rules-dsl.md · exec/rules-dsl.md · 브랜치 rules-dsl · <repo>.worktrees/rules-dsl   <!-- audit-skip: slug 예시 -->
```
`grep <slug>` 하면 설계→실행→코드 관통. (멀티repo면 slug는 repo 네임스페이스 안에서)

## _local-docs 단일 소스
- worktree는 **코드 공간만** 새로 뚫음. 설계·로그는 **프로젝트 루트 _local-docs 하나**(복제 X).
- worktree cwd에서 작업 중이어도 **기록은 루트 `_local-docs`에**(`../../_local-docs/exec/…`). 훅은 `~/projects/_docs/<project>/`를 **계산**하므로 cwd가 어디든 같은 곳을 본다.
- **"_local-docs = 언제나 프로젝트 루트, repo 상대경로 아님"** — 이 규약이 load-bearing.
- 기록의 slug가 그대로 브랜치명이라 **어느 worktree였는지 따로 안 적어도 추적된다.**

## repo 안 공유 파일 — main에서만
worktree는 **브랜치를 나눌 뿐 같은 파일의 충돌은 막아주지 않는다.** 여러 worktree가 "repo 전체를 요약하는" 같은 파일을 고치면 머지 때 반드시 충돌한다.

| 성격 | 예 | 규칙 |
|---|---|---|
| 작업 **전용** (경로가 slug로 갈림) | `config/<대상>/` · `exec/<slug>.md` | worktree에서 자유롭게 |
| **공유** (전체 요약 단일 파일) | 인벤토리 · 구성도 · 목록 표 · 매니페스트 | ⚠️ **worktree에서 건드리지 않음** |

- **미루되 잊지 않는다** — 갱신거리는 "main 반영 대상"으로 적어두고 작업 **마지막 마일스톤에서 main에 한 번에** 반영. 그냥 "안 고친다"로 끝내면 갱신 자체가 유실된다.
- **공유 파일이 뭔지는 그 repo의 `AGENTS.md`가 정한다** (kit은 파일명을 갖지 않음). kit이 도메인별 파일명을 하드코딩하지 않는다.
- worktree 생성 시 그 목록을 확인해 알려준다.

## 정리 — 자동삭제 금지
기본은 **남긴다.** worktree엔 uncommitted/unpushed가 있을 수 있어 자동삭제 위험. 머지했다고 바로 지울 필요도 없음.

"정리" 시 각 worktree를 **3-가드** 통과할 때만 확인받고 제거:
| 가드 | 체크 | 실패 시 |
|---|---|---|
| ① 머지됨 | `git branch --merged <main>` 에 있나 | 미머지 → 경고, 안 지움 |
| ② 깨끗 | uncommitted 없음(`git status`) | dirty → 경고, 안 지움(remove도 거부) |
| ③ 푸시됨 | unpushed 커밋 없음 | unpushed → 경고 후 확인 |

통과 → 제안:
```bash
git worktree remove <repo>.worktrees/<slug>
git branch -d <slug>              # --merged라 -d로 안전삭제(미머지면 거부)
```
- **일괄 점검**: `git worktree list` 훑어 머지+클린인 것 모아 확인. `git worktree prune` = 폴더는 지웠는데 등록만 남은 유령 청소(안전).
- worktree 지워도 exec 이력은 _local-docs에 보존.

## 경계
- worktree 생성/정리 + **딸린 브랜치 생성(`-b`)·정리 삭제(`-d`)** = **project**(공간).
- 그 브랜치에 **커밋·머지·rebase·PR·네이밍전략** = **`git`**. project는 브랜치를 "낳기만", 키우는 건 code-*.
