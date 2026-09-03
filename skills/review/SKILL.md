---
name: review
description: 작성된 코드를 검수할 때 발동 — "리뷰/검토해줘", diff·PR·브랜치·파일 리뷰. 이미 쓴 것을 severity 순으로 지적·제안한다(post-write). 손대기 전 **파악**은 알아내기 profile, 버그 **재현**은 「정의」 소관.
---

# review

**작성된 코드**를 검수해 문제를 severity 순으로 짚고 개선을 제안한다. (이해=analyze와 구분: review는 post-write 평가)

## 대상
- 기본 = **현재 변경**(uncommitted / staged diff).
- 지정 시 = 브랜치 vs main diff · PR · 특정 파일/디렉토리.

## 차원 & 출력
- 리뷰 차원·severity·출력 형식 = `references/checklist.md`.
- 🔑 **이 repo에서 특히 볼 것**(`WATCHDOG.md`) · 상시 견제 옵션 = `references/priority.md`.
- 출력: **severity 순** `등급 | file:line | 문제 | 근거 | 제안`. 근거 없는 지적 금지.

## odin 소프트위임
- `odin:review` / `/code-review` 있으면 **그 워크플로 우선 활용**, 없으면 `references/checklist.md` 체크리스트로 fallback.

## 경계
- review = **지적·제안까지.** 수정 **적용**은 「수행」·사용자 몫.
- `git`이 **머지/PR 전 게이트**로 이 스킬을 소환(소프트위임).
- 리뷰 대상 코드에 **secret 발견** 시 즉시 blocker로 올림(commit 전 점검과 연계).
