---
name: kit
description: tr-kit 자체를 설치·점검·업데이트하거나 skill·component를 저작할 때 사용한다. "kit 업데이트", "스킬 만들어줘", "kit 점검".
---

# kit

이 kit 자체를 다룬다. 공통 source를 고치고 검증한 뒤 target별 생성물과 배포 채널에 반영하는 사이클을 관리한다.

## 먼저 — 무엇을 건드리나

| 일 | 읽을 곳 |
|---|---|
| 새 skill·component 저작 | `references/authoring.md` |
| 반복 산출물 형식 설계·검토 | `references/output-format.md` |
| source 조립·target 경계 | 현재 repo의 recipe·core·adapter 계약 |
| 설치·업데이트·캐시 점검 | 아래 target delivery capability |

## 공통 source 규칙

- 모든 target에서 같은 목적·판단·지식은 `core/`가 소유한다.
- 제품 도구·입출력·설치 방식은 `adapters/<target>/`이 소유한다.
- `recipes/<target>.toml`이 build-time 조립과 산출 경로의 정본이다.
- target adapter에 완성된 공통 skill 사본을 두지 않는다. 공통 본문과 named capability fragment를 합성한다.
- 생성된 `out/`은 직접 수정하지 않고 source를 고친 뒤 다시 빌드한다.

## 저작·검증 흐름

1. 기존 core·adapter·reference 중 재사용할 자리를 먼저 찾는다.
2. 공통 의미와 target 수단의 경계를 정한다.
3. 계약이나 실패 테스트를 먼저 추가한다.
4. source를 수정하고 양 target을 clean build한다.
5. skill validator·hook fixture·산출물 diff에서 의도된 변화만 확인한다.
6. 배포·설치·push 직전에 별도 확인을 받는다.

## Target delivery

{{slot:kit.delivery}}

## 점검

군살 점검은 report-first다. 깨진 링크, orphan reference, 유사 description, 생성물·설치본 drift를 보고하되 자동 삭제하거나 배포하지 않는다.

## 경계

| 일 | 어디 |
|---|---|
| OS/CLI 설치 목록 | 사용 환경의 package inventory 또는 project-local 문서 |
| repo 커밋·브랜치·병합 | `git` |
| local-docs 공간·마이그레이션 | `project` |
