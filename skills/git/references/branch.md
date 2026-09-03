# 브랜치 전략

**GitHub Flow** — task당 짧게 사는 feature 브랜치.

## 흐름
```
main(안정) ─┬─ <slug> 브랜치 따서 작업 ─┬─ main 머지 ─ 브랜치 삭제
            (= project worktree slug)
```
- task 하나 = feature 브랜치 하나. main은 항상 안정/배포가능 상태 유지.
- **project worktree와 1:1**: 브랜치명 = worktree 폴더 = plan/exec의 `NN-<slug>` (한 줄기). `grep <slug>`로 관통.
- 작업 끝 → main 머지 → 브랜치·worktree 정리(정리는 project 소관, `--merged` 가드).
- **사소한 변경**(오타·문서 한 줄)은 브랜치 없이 main 직접 커밋 허용.

## 네이밍
- 기본 = **slug 그대로**(`rules-dsl`). project가 worktree 만들 때 준 이름.
- `feat/…` 프리픽스는 선택(팀/repo 관례 있으면 따름).

## main 브랜치 이름
- **새 repo = `main`**(현 표준, {{KIT_REPO}}도 main).
- **기존 repo = 감지해서 따름**: `git symbolic-ref refs/remotes/origin/HEAD` 또는 `git branch` 확인. master면 master.
- 고정 가정 금지 — 항상 그 repo의 기본 브랜치를 확인.

## 안 하는 것 (경계)
- 브랜치 **생성/정리**는 project(`/project:worktree`·`cleanup`). code-git은 그 브랜치 **위에서 커밋·머지**.
