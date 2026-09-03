---
name: knowledge
description: 조사·PoC·디버깅에서 얻은 재사용 가능한 지식을 Markdown repository에 축적·조회할 때 발동 — "이거 지식으로 남겨", "전에 알아낸 것 찾아줘", "내 지식 베이스에 저장". index와 상대 링크를 직접 순회하는 LLM-wiki 방식.
---

# knowledge — 개인 지식 베이스

이 스킬은 방법론만 제공한다. 저장소는 plugin root의 `profile/setup.py get public.repositories.knowledge`로 해석한다. 미설정이면 읽기·쓰기 전에 `profile-setup`으로 연결하며 경로나 remote를 추측하지 않는다.

**철학 = LLM-wiki**: 임베딩·벡터DB 없이 마크다운 + `index.md` + 상대경로 링크를 **직접 순회**. 수백~수천 노트까진 index+grep+MOC로 충분.

## 경계 — 여기에 넣나?

*"이 지식을 이 프로젝트 밖에서도 꺼낼까?"*
- **예**(재사용·조사결론·PoC결과·개념) → knowledge repository. 프로젝트에선 **링크만**.
- **아니오**(그 프로젝트 내부 결정·작업) → 프로젝트 docs. **중복 금지**(갱신 갈림).

## 구조

```
<knowledge-repository>/
├─ index.md                  # 루트 라우터(자동생성)
├─ llm-agent/  infra/  os-env/  dev/  hobby/   # 도메인(폴더마다 index.md=MOC)
└─ inbox/                    # 미분류 → 쌓이면 새 도메인 승격
```
- 도메인=폴더 / 성숙도=frontmatter `status: seed|evergreen|archived`(폴더 아님, 제자리 숙성).
- 폴더는 고정 아님 — inbox가 다음 도메인의 씨앗.

## 쓰기

**발동**: ① 자연어("이거 지식으로 남겨") · ④ **자동 제안**.
- **A. 내용 신호**(주): 대화 중 **재사용 앎**이 생긴 순간(조사결론·PoC결과·디버깅 원인·개념 설명)에 **한 줄로 제안** — 예: `💡 이거 dev에 남길까?`. 턴 경계에 안 묶는다(턴이 지저분해도 됨). 같은 건 1회만, 무시 가능.
- **B. sweep**(안전망): 롤오버 준비 알림·세션끝·"이번 세션 지식 훑어줘" 때 놓친 후보를 **몰아서** 제안.

**속도 2단**:
- **빠른 캡처** → `inbox/<slug>.md` 최소 frontmatter(title·summary·status: seed). 마찰 0.
- **정식 노트** → 도메인 폴더. 자기완결(evergreen 지향) + 링크 + 태그.

**노트 스키마** (`_template.md` 복사):
```yaml
---
title:      # 제목
summary:    # 한 줄 요약(index·검색 미리보기)
tags: []
links: []   # 관련 노트 상대경로
status: seed   # seed | evergreen | archived
created: YYYY-MM-DD
updated: YYYY-MM-DD
# review:      # (선택) dive 스킬의 SRS 대상일 때만 — {next, interval, score}
---
```
링크는 **상대경로 마크다운**(`[..](../dev/x.md)`). `[[wikilink]]` 금지.
`review:` 필드는 `dive` 스킬(간격반복 복습)이 관리한다 — 일반 노트엔 없어도 된다.

## 읽기

질문이 지식 조회면 **직접 순회**한다(임베딩 X):
1. 루트 `index.md` → 해당 도메인 MOC(`<domain>/index.md`)
2. 후보 좁힌 뒤 노트 파일 **직접 read**. 정확 검색은 `grep -rn` 병행.
3. 못 찾으면 `inbox/`도 훑는다.

명시 소환("지식 베이스에서 X 찾아")도 같은 순서.

## 정리 (index 자동)

- 노트 저장·수정 시 **그 폴더 `index.md`(MOC)를 재생성** — 폴더 내 노트의 `title`+`summary`를 표로. 루트 `index.md`는 도메인 목록.
- **손으로 index 안 쓴다**(local-docs 자동화 사상). frontmatter가 정본.

## inbox 승격

`inbox/`에 **유사 태그가 임계(≈5개) 이상** 쌓이면 *"이거 새 도메인(`<name>/`)으로 뺄까?"* **제안**(최종결정=사람). 승격 시 폴더 생성 + 노트 이동 + 링크 갱신.

## 커밋

지식 저장 후 resolve된 knowledge repository에 커밋(한 줄 Conventional). push는 유저 확인 후.
