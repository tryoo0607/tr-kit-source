# career 상세 — 수확·정제·추출

## log — raw 수확 (부담 0)
- **수동 append**: "오늘 뭐 했다" 한 줄을 `work-log/YYYY-MM.md` 최신 위로. 완결·수치 강요 X.
- **git log 수확** (회사 시스템 연동 없음 — 로컬 clone만):
  1. 대상 repo에서 `git -C <repo> log --author=<나> --since=<기간> --oneline` (여러 repo면 반복).
  2. 커밋을 **기능·티켓·브랜치 단위로 클러스터**링.
  3. 각 묶음을 "X 했음 (커밋 링크)" **초안**으로 draft → work-log에 넣기 전 유저가 다듬음.
  - GitLab MR은 선택(토큰 필요): MR 제목·설명·리뷰논의까지 증거로. 기본 비활성.

## promote — raw → 정제 (achievements)
work-log 항목이 "이력서에 쓸 만하다" 싶으면 승격:
1. **일반화**: 회사 기밀 특정정보(내부 코드명·미공개·고객데이터·독점 원문코드) 제거 → 이식 가능한 기법·성과로.
2. **보강 질문**: 로그가 못 아는 것 — 정량 수치, 내 역할(주도/공동/기여/리뷰), 비즈니스 임팩트 — 물어서 채움.
3. **증거 링크**: commit/PR/문서 URL을 `evidence`에.
4. `achievements/<slug>.md` 저장.

## 정제 스키마 (achievements)
```yaml
---
title:
date: YYYY-MM
role:          # 주도 | 공동 | 기여 | 리뷰
skills: []
tags: []       # 영역(backend/infra) + 성과유형(품질/성능/생산성/안정성)
evidence: []   # PR/commit/문서 링크
---
작업(WHAT): 무엇을 만들었/고쳤나 (기능·범위)
고민:       어려웠던 지점·제약·트레이드오프 (issue/plan에서)
해결:       접근·근거 (exec/PR에서). 기법 위주, 원문코드 X
임팩트:     결과·수치(전/후) · 협업 규모
```
- **수치화 우선**: "느렸다"❌ → "p99 800ms→120ms"✅. 모르면 물어보고, 끝내 없으면 정성/추정 표기.
- 역할은 정직하게(면접서 검증됨).

## extract — 이력서·면접 재료
- **XYZ** (bullet, Google/Bock): "**X**를 **Y**로 측정되게, **Z**로 해냄." 수치(Y)가 문법 슬롯이라 강함. 예: "알람 오탐을 30%↓, 룰엔진 캐싱으로."
- **STAR** (면접 서사): Situation·Task(고민)→Action(해결)→Result(임팩트).
- **필터**: 지원 직무 기술스택·역할에 맞는 achievement만 골라 재구성.
- ⚠️ **날조·과장 금지**: evidence 있는 것만. 근거 약하면 "정성/추정"으로 표기(proofread 정신).

## 저장 세부
- repo 전체 **평문**(공개·이식 가능분). secret은 애초에 안 넣음(→ `secrets` 스킬).
- `work-log/`는 월별 1파일(최신 위 append), `achievements/`는 성과별 1파일 → 이직·직무별 extract 쉬움.
- 나중에 비공개 과제가 생기면 그 경로만 git-crypt 지정(지금은 불요).

## 경계
- **history 갈래**(WHAT+임팩트) — 공통 이력 규율은 `kit`(git이 정본, 롤업만, append). 커리어는 **repo 밖 성격**이라 형식·추출을 이 스킬이 갖는다.
