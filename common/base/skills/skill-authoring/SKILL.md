---
name: skill-authoring
description: 스킬 작성, 수정과 검수 요청에 저작 기준을 적용한다. 역할 분담, reference, 외부 연결과 컨텍스트 읽기량을 검토한다. 일반 코드 리뷰나 문서 교정에는 사용하지 않는다.
metadata:
  tr-role: policy
---

# skill-authoring

## 목적과 역할 경계

일반 저작 절차를 재사용하면서 자체 저작 규격을 적용한다. 저작 결과, 배포 조립, 설치와 실제 실행을 구분한다. 외부 skill 원본의 절차를 복사해 별도 관리하지 않는다.

## 입력과 전제

요청, 작성 또는 검토 대상, 산출 경로, 적용 환경과 최신 합의를 확인한다. 현재 재설계의 자체 source는 common/base/skills, 제품별 차이는 adapters/<product>의 대응 계층이 소유한다. 보존본을 현재 실행 지침으로 자동 적용하지 않는다.

## 요청별 분기

| 요청 | 선택 조건 | 읽을 reference |
|---|---|---|
| 일반 skill 작성, 수정, 검토 | skill-creator 사용 가능 (배포본: ../skill-creator/SKILL.md) | [외부 creator 사용](references/creator.md) |
| 일반 skill 작성, 수정, 검토 | 그 외 | [기본 저작](references/basic.md) |
| reference 작성, 수정, 분리 검토 | 해당 요청이 포함됨 | [reference 기준](references/reference-authoring.md) |
| 스킬 호출 흐름과 컨텍스트 비용 검수 | 해당 검수가 요청됨 | [읽기량과 흐름 검수](references/context-review.md) |
| 외부 skill 선택, include 선언, 제품 연결 또는 조립 검토 | 해당 요청이 포함됨 | [include와 제품 연결](references/include.md) |
| creator 원본 확인, revision 갱신 또는 제품 변환 검토 | 해당 요청이 포함됨 | [include와 제품 연결](references/include.md) |
| 저작 후 설치 또는 업데이트도 요청됨 | 해당 요청이 포함됨 | [설치 연결](references/delivery.md) |

작성, 수정, 검토에는 [자체 기준](references/local-rules.md)을 공통 적용한다. 같은 요청의 행은 위에서부터 평가하고 처음 일치한 하나만 선택한다. 다른 추가 요청이 포함되면 그 요청에서도 한 행을 선택한다. 사용 가능은 대상 SKILL.md의 존재, 접근 가능, 사용 허용을 뜻하며 본문 로드나 실행으로 판정하지 않는다. 판정이 불명확하면 필요한 확인만 수행하고 금지된 경로를 읽지 않는다. 그 외는 앞선 조건이 성립하지 않을 때만 선택한다.

일반 저작 중 reference를 추가하거나 재구성할 때만 reference 기준을 추가 적용한다. 외부 의존성 선언이나 제품별 연결을 바꿀 때만 include 분기를 추가 적용한다. 처음 선택한 일반 저작 경로로 이 조건부 검사를 생략하지 않으며 reference 본문이나 명령을 단순 수정하는 데 모든 조립 지침을 기본 로드하지 않는다.

읽는 파일/절이나 skill 연결 흐름을 바꿨거나 컨텍스트 비용 검수를 요청받으면 [읽기량과 흐름 검수](references/context-review.md)를 추가 적용한다. 일반 검수에서 형식이나 표현만 바뀌었다면 전후 실행 평가까지 기본 수행하지 않는다.

선택하지 않은 reference는 읽지 않는다. 실행 중 실패는 자동 대체 조건이 아니며 이미 발생한 변경과 실패 원인을 확인한다. 상세 연결 계약은 실제 사용하는 reference의 연계와 의존을 따른다.

## 결과와 완료 판단

변경 경로, 적용한 규격, 실제 읽은 원본과 검증 범위, 미결을 전달한다. 대표 요청과 가까운 비대상 요청, 대상 부재와 실패 상황에서 지침을 대조한다. 형식 검사와 조립 성공을 자동 발동, 설치 완료나 독립 환경 실행 성공으로 보고하지 않는다.
