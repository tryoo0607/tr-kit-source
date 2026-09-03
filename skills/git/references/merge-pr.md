# 머지 · rebase · PR

## 히스토리 = 선형 지향
갈래 없는 한 줄 이력을 목표로.

### 최신화 (작업 중 main이 앞서갈 때)
- **미공유 로컬 브랜치** → `git rebase main` (내 커밋을 main 끝에 재배치, 직선).
- ⚠️ **이미 push된 공유 브랜치 → rebase 금지** (히스토리 재작성 위험) → `git merge main`으로 받음.

### 통합 (브랜치 → main)
- **리모트/PR** → **squash merge**(작업 커밋들을 1개로 압축, main 직선).
- **로컬 솔로** → **fast-forward**(`git merge --ff-only`, 직선 유지).
- 어느 경우든 **안전하게 main에 합치고** 브랜치 삭제(정리는 project).

## PR
**repo 기존 컨벤션 우선.**
1. `.github/PULL_REQUEST_TEMPLATE.md`(또는 `PULL_REQUEST_TEMPLATE/`) 있으면 **그 양식 따름**.
2. 없으면 **과거 PR 선례** 참고(제목·본문 구조).
3. 그것도 없으면 **기본양식**:
   ```markdown
   제목: <커밋과 동일 = 한 줄 Conventional>

   ## 배경     # _local-docs plan의 배경/계기 재사용
   ## 변경     # 무엇을 바꿨나
   ## 테스트   # 어떻게 검증
   ## 관련     # plan/exec·issue·이슈# 링크
   ```
- 제목은 **항상 커밋 컨벤션**(`commit.md`).
- 리뷰 코멘트·검수는 **`review` 소프트위임**.

## 안전 (main 보호)
- **main force-push 금지.** 보호된 브랜치 직접 push 지양.
- 머지 전 **테스트 통과 + (요청 시) 리뷰**.
- rebase는 미공유 브랜치에만. 공유된 것 건드리면 협업자 히스토리 깨짐.
- 되돌릴 땐 `git revert`(공유 이력) vs `reset`(로컬만) 구분.

## 소프트의존
odin `atomic-commit`·`git-branchless` 있으면 활용, 없으면 위 규약. pre-commit 훅 있으면 존중(걸리면 고쳐 재커밋).
