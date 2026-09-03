---
description: 끝난 worktree를 3-가드(머지·클린·푸시) 통과 시에만 확인받고 정리
argument-hint: "[slug] (생략 시 전체 점검)"
---

`project` 스킬의 `references/worktree.md` 정리 규약대로 worktree를 정리한다. **자동삭제 금지 — 가드 통과 + 확인 필수.**

대상: `$ARGUMENTS` (비면 `git worktree list` 전체 점검).

## 절차
1. **현황** — `git worktree list` 로 worktree·브랜치 나열.
2. **각 worktree 3-가드 검사** (읽기 전용):
   - ① 머지됨? `git branch --merged <main>` 에 포함
   - ② 깨끗? uncommitted 없음 (`git -C <worktree> status --porcelain`)
   - ③ 푸시됨? unpushed 커밋 없음
3. **판정**:
   - 셋 다 통과 → **제거 제안** (사용자 확인 후):
     ```bash
     git worktree remove <repo>.worktrees/<slug>
     git branch -d <slug>
     ```
   - 하나라도 실패 → **경고만, 안 지움** (미머지/dirty/unpushed 사유 표시).
4. **유령 청소** — `git worktree prune` (폴더 이미 없는 등록만 제거, 안전).

기록은 `_local-docs`에 남으니 worktree를 지워도 이력은 보존된다.
