---
name: career
description: 작업·성과를 커리어 기록으로 축적하거나 이력서·면접 재료로 정리할 때 사용한다. "업무 로그", "성과 정리", "이번 달 뭐 했지".
---

# career — 커리어 자산 축적·추출

작업의 **한 일·고민·해결·임팩트**를 **작업/성과 단위**로 쌓아 → 나중에 이력서·면접·성과평가 재료로. **방법론은 범용**(회사·개인 공통), **데이터는 개인 private**.

이 스킬은 방법론만 제공한다. 데이터 저장소는 plugin root의 `profile/setup.py get public.repositories.career`로 해석한다. 미설정이면 쓰기 전에 `profile-setup`으로 연결하며 경로나 remote를 추측하지 않는다.

## 철학 — 저마찰 2단 (raw → 정제)

무에서 이력서 문장을 쓰려면 부담돼서 안 쌓인다. 그래서 **두 단**:
```
한 일 (git·PR·plan·exec·구술)
   ↓ 날것으로 흘려 적기 (부담 0)
work-log/YYYY-MM.md   ← raw, 날짜순 append
   ↓ 필요할 때 정제 (증거링크 + 수치)
achievements/<slug>.md ← STAR/impact 단위, 이력서 재료
   ↓ 필터·재구성
이력서·면접 bullet (extract)
```

## 핵심 규칙
- **raw는 부담 0** — "오늘 뭐 했다" 한 줄이면 된다. 완결·수치 강요 안 함(그건 정제 때).
- **정제 단위 = 의미 있는 작업/성과 하나** (per-commit❌ 잘음 / per-project❌ 큼).
- **성과 중심**: 사유보다 결과·임팩트·내 역할. 수치화 가능하면 수치로(정제 때).
- ⚠️ **기밀 배제·일반화**: 회사 내부 코드명·미공개·고객데이터·독점 원문코드 안 넣음. 이식 가능한 기법·성과로 환원. **secret은 아예 안 넣는다**(→ `secrets` 스킬). 오픈소스·공개분은 평문 OK.

## 구조
```
<career-repository>/          # 사용자 소유, 평문
├─ work-log/YYYY-MM.md        # raw 날것 (저마찰 append)
├─ achievements/<slug>.md     # 정제 성과 (STAR/impact + 증거링크)
├─ resume/                    # master.md + variants/{role,platform}.md
├─ oss/                       # 공개 기여 (평문)
└─ skills-inventory.md        # 기술 인벤토리 → 각 근거 achievement backlink
```
- 참조해결: **로컬 → clone → 없으면 신설**(확인 후). repo 규약은 `git` 따름.
- git-crypt 없음(공개분·평문). 나중에 비공개 과제 생기면 그때 얹는다.

## 연산

| 명령 | 동작 |
|---|---|
| **log** | raw 한 줄을 `work-log/`에 append. 또는 **"이번 달/주 뭐 했지" → 로컬 git log 수확**(아래) |
| **promote** | work-log 항목 → `achievements/<slug>.md` 정제(증거·수치·역할 보강, 빠지면 물어봄) |
| **extract** | achievements에서 이력서·면접 재료 추림(STAR/XYZ bullet). 기술·기간·역할 필터 |
| **filter** | 기술스택·프로젝트·기간별 조회 |

### log — 로컬 git log 수확 (자동 초안)
"8월에 뭐 했지" 류엔 **회사 시스템 연동 없이** 노트북의 clone된 repo만 읽는다:
```
git -C <repo> log --author=<나> --since=<기간> --oneline
```
커밋을 기능/티켓 단위로 묶어 **work-log 초안 draft** → 유저가 다듬어 확정. GitLab MR API 연동은 **선택**(토큰 필요, 기본 안 함).

## 엔트리 스키마

**raw (work-log)** — 부담 0, 형식 느슨:
```
2026-08-24 · geodeonbar 룰엔진 캐싱. race → sync.Map 전환. PR #42
```

**정제 (achievements/<slug>.md)**:
```yaml
---
title:        # 작업 제목
date: 2026-08
role:         # 주도 | 공동 | 기여 | 리뷰 (정직하게 — 면접서 검증됨)
skills: [Go, ...]
tags: [backend, 성과-품질]
evidence: []  # commit/PR/문서 링크 (증거)
---
작업(WHAT):   무엇을 만들었/고쳤나
고민:         어려웠던 지점·트레이드오프
해결:         접근·근거 (기법 위주, 원문코드 X)
임팩트:       결과·수치(전/후) · 협업 규모
```
- **수치화 우선**: "느렸다"❌ → "p99 800ms→120ms"✅. 없으면 정성/추정 표기(날조 금지).

## extract — 이력서·면접 재료
- **XYZ**(bullet 렌더): "**X**를 **Y**만큼(수치) **Z**로 해냄" — 수치가 문법에 내장돼 강함.
- **STAR**(면접 서사): 고민→S/T · 해결→A · 임팩트→R.
- 필터: 지원 직무의 기술·역할에 맞는 achievement만 골라 재구성.
- ⚠️ **날조·과장 금지**: 근거(evidence) 있는 것만. 약하면 "정성/추정" 표기(proofread 정신).

## 커밋
저장 후 resolve된 career repository에 커밋(한 줄 Conventional). push는 유저 확인 후.

## 경계
- **재사용 지식** → `knowledge`. 개인 정서 기록은 이 skill의 범위가 아니다. 여기는 **성과·이력**만 다룬다.
- 상세 스키마·extract 형식 = `references/journaling.md`.
