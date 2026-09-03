---
description: 병렬작업용 git worktree를 <repo>.worktrees/<slug> 에 생성 (base는 물어봄)
argument-hint: "<slug> (작업 이름, state/exec와 공유)"
---

`project` 스킬의 `references/worktree.md` 규약대로 worktree를 만든다.

slug: `$ARGUMENTS` — **작업 slug 그대로**(`state/<slug>.md`·`exec/<slug>.md`와 이름 공유). 없으면 함께 정한다.

## 절차
1. **repo 확인** — 현재 프로젝트의 메인 repo 위치 파악(`git rev-parse --show-toplevel`).
2. **base 브랜치 물어봄** (default 금지 — AskUserQuestion, 단일선택):
   - ① `origin/main` 기준 새 브랜치 (fetch 후) — 보통
   - ② 특정 base 브랜치 지정 → 새 브랜치
   - ③ 기존 브랜치 그대로 이어서 (`-b` 없음)
3. **생성**:
   ```bash
   cd <repo>
   git fetch origin                                  # ①일 때
   git worktree add ../<repo>.worktrees/<slug> -b <slug> <base>   # ③은 -b 없이 <existing>
   ```
4. **안내**
   - 작업은 worktree cwd에서 하되 **기록은 프로젝트 루트 `_local-docs`**(`../../_local-docs/state/<slug>.md`). slug가 곧 브랜치명이라 어느 worktree였는지 따로 안 적어도 추적된다.
   - **공유 파일 경고** — 그 repo `AGENTS.md`에서 "worktree에서 수정 금지"인 공유 파일(인벤토리·구성도·목록 표 등)을 확인해 알려준다. 없으면 생략.

## 경계
커밋·머지는 **하지 않는다**(`git` 소관). 이 커맨드는 "공간"만 만든다.
