---
name: ext-diagram-design
description: 수치 비교·추세·분포·재무 차트와 간트·칸반·사용자 여정 등의 업무 시각화를 공식 기능에 연결한다. 일반 구조/흐름은 archify가 기본이며 도구·스타일을 명시한 선택은 유지한다.
metadata:
  tr-role: external-wrapper
---

# ext-diagram-design

## 목적과 역할 경계

- 확인한 데이터·단위·관계·독자·상세도와 요청 형식을 공식 업무 시각화 기능에 전달한다. 데이터·설계의 새로운 결론을 임의로 확정하지 않는다.
- 구조/흐름은 archify가 기본이다. 사용자가 diagram-design 또는 그 스타일을 명시하면 공식 지원 범위에서 해당 선택을 유지한다.

## 입력과 전제

- 원본 데이터와 기간·단위·누락/미확인, label·관계·독자·형식·저장 범위를 받는다. 하나의 문서에 여러 도표를 넣어도 각각의 의미·탐색을 보존하며 근거 없이 합치거나 생략하지 않는다.
- 원본 첫 사용의 style 선택과 project marker/profile 해석은 실제 공식 지침을 따른다. 다른 프로젝트의 과거 선택을 새 프로젝트의 승인으로 사용하지 않는다.

## 수행 방법과 절차

1. 아래 공통 연결로 공식 SKILL.md에 진입하고 선택한 유형과 조건에 맞는 export/import 자료만 적용한다. 전체 gallery·원본 구현을 기본 로드하지 않는다.
2. 설치본/style-guide 원문·사본의 복제·변형이 필요한 동작은 보류·보고한다. 설치 원문을 바꾸지 않고 읽는 공식 marker/profile 경로가 실제 지원될 때만 그 계약으로 연결한다. 자체 프로젝트 사본·새 profile을 임의 대안으로 만들지 않는다.
3. 웹 font·외부 리소스, 출력 파일, profile/cache 갱신과 browser 부수효과를 승인 범위와 대조한다. 오프라인 요청이면 원문이 지원하는 system-font 경로를 확인해 사용하며 지원하지 않으면 한계를 알린다.
4. 요청한 형식만 export한다. HTML/SVG 검사·PNG용 Python Playwright/Chromium·실제 화면 관측을 구분한다. Node playwright-cli 하나만으로 모든 exporter 의존성이 충족됐다고 보지 않는다. 원문 검사가 설치 범위에 없으면 미실행으로 보고하며 원문 script를 kit에 복제하지 않는다.

## 연계와 의존

| 대상 | 전달 입력·필요 결과 | 필수 여부·부재 처리 |
| --- | --- | --- |
| 외부 연결 `diagram-design` · 종류 skill. [공통 외부 연결](../../references/external-connection.md) | 확인 데이터/관계·단위·기간·독자·형식·style 선택·범위. 결과는 파일·검사·보존/생략·미결 | 공식 생성에 필수. 부재·style/의존 충돌은 해당 수행 보류. 원문 변경·사본·다른 도구로 대체하지 않음 |
| [ext-playwright-cli](../ext-playwright-cli/SKILL.md) | 필요 시 로컬 HTML/승인 preview·viewport·겹침/clipping 시나리오 | 선택 화면 검수. 실제 관측·오류·capture와 미검증 반환. PNG exporter를 대체하지 않음 |
| [artifact-publish](../artifact-publish/SKILL.md) | 완성본·제목·기존 URL·승인된 계정/공유 범위 | 게시 요청에만 적용. 부재 시 파일 보존·미게시 |

## 결과와 완료 판단

- 원본 데이터/관계와 대조한 결과, 병합·생략·미확인, 파일 위치와 검사·화면 검수·export의 실제 범위를 반환한다. style 질문·공식 gate를 생략한 상태를 전체 수행 완료로 보고하지 않는다.
