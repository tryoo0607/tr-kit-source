---
name: git
description: commit, branch, merge, rebase, PR 등 Git workflow를 다룰 때 사용한다. "커밋해줘", "브랜치 따줘", "PR 만들어줘". worktree 공간 관리는 project가 담당한다.
---

# git

코드 변경을 git에 반영하는 **워크플로**를 다룬다. project 스킬이 만든 worktree/브랜치 "공간" 안에서 **커밋·머지·rebase·PR**를 담당(공간 vs 흐름 경계).

## 경계
- **project** = worktree·브랜치 **생성/정리**(공간). **code-git** = 그 안 **커밋·머지·흐름**.
- **commit 한 줄 규칙**(Conventional·트레일러 없음)은 플러그인 `{{AGENT_FILE}}`(hot)에 상주 → 여기선 **상세만** 확장.
- 릴리즈·태그·버전은 범위 밖 → 미정(필요해지면 신설).

## 언제 뭘 (메뉴판)
| 상황 | 참조 |
|---|---|
| 커밋(단위·type·메시지·언어) | `references/commit.md` |
| 브랜치 전략·네이밍·main 감지 | `references/branch.md` |
| 머지·rebase·PR·main 보호 | `references/merge-pr.md` |

## 핵심 요약
- **브랜치**: task당 short-lived feature 브랜치(= project worktree slug), main 머지 후 삭제. 사소한 건 main 직접.
- **히스토리**: 선형 지향. 미공유 로컬 브랜치는 rebase로 최신화, **이미 push된 공유 브랜치는 rebase 금지 → merge**.
- **PR**: repo 기존 컨벤션 우선(템플릿/선례), 없으면 기본양식. 제목=커밋 컨벤션.
- **안전**: main force-push 금지, 머지 전 테스트/리뷰(→ `review` 소프트위임).

## 소프트의존
- odin `atomic-commit`·`git-branchless` 등 있으면 활용, 없으면 여기 규약으로 fallback.
- pre-commit 훅은 **만들지 않고** 있으면 존중(걸리면 고쳐 재커밋).
