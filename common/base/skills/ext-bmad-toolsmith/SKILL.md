---
name: ext-bmad-toolsmith
description: Smithy 또는 BMAD skill·agent·module의 제작/개선 요청에 연결한다. kit 자체 저작 기준은 plugin-authoring을 유지한다.
metadata:
  tr-role: external-wrapper
---

# ext-bmad-toolsmith

## 목적과 역할 경계

- Smithy 또는 BMAD skill·agent·module의 제작/개선 요청에 연결한다. kit 자체 저작 기준은 plugin-authoring을 유지한다.
- 이 파일은 자체 연결이다. 공식 절차·template·runtime을 포함하거나 재작성하지 않는다.

## 입력과 전제

- 저작 대상·역할·보존 요구·공식 기능 범위와 승인.
- 현재 제품·실제 프로젝트 cwd·kit root와 명시 외부 연결 선언을 확인한다. 이미 확인한 요구·설치 근거는 재사용한다.

## 수행 방법과 절차

- [BMAD 공통 연결](../ext-bmad/references/connection.md)을 적용해 아래 ID의 공식 설치본으로 진입한다. 공통 절차와 조건에 맞는 추가 절만 읽는다.
- 공식 기능이 만든 산출물과 실제 결과를 아래 필요한 결과·원래 요구와 대조한다. 지침 참조·렌더·실제 실행·완료를 구분한다.

## 연계와 의존

| 대상 | 전달 입력·필요 결과 | 필수 여부·부재 처리 |
| --- | --- | --- |
| 외부 연결 `bmad-toolsmith` · 종류 `skill` | 위 입력. 필요한 결과: 저작 산출물과 지원 도구·검증, kit 원문 보호와의 충돌/미지원 | 해당 공식 수행에 필수. 부재·미지원·pin drift는 수행 보류. 원문 복제·동명 wrapper·다른 공급자로 대체하지 않음 |

## 결과와 완료 판단

- 저작 산출물과 지원 도구·검증, kit 원문 보호와의 충돌/미지원. 적용한 실제 공식 기능·검증 범위·미결을 함께 반환한다.
- 공식 기능 부재 상태의 계획·입력 확인을 실제 외부 수행 완료로 보고하지 않는다.
