---
name: running-instrumented-tests-with-androidjunit4
description: AndroidJUnit4 테스트 runner·source set·관련 의존성 구성을 공식 기능에 연결한다. runner 구성과 ADB 실행·기기 데이터 초기화를 구분한다.
metadata:
  tr-role: external-wrapper
---

# running-instrumented-tests-with-androidjunit4

## 목적과 역할 경계

- AndroidJUnit4 테스트 runner·source set·관련 의존성 구성을 공식 기능에 연결한다. runner 구성과 ADB 실행·기기 데이터 초기화를 구분한다.
- 공식 기능의 절차·예제·reference를 복제하거나 치환하지 않는 자체 연결이다. 다른 Android 담당은 아래 공통 기준의 요청별 분기에서 실제 필요한 경우만 선택한다.

## 입력과 전제

- 모듈/source set·실제 runner/annotation import·기존 의존 버전·오류·선택한 Orchestrator 여부와 허용 변경.
- 실제 제품·kit root·프로젝트 cwd·명시 provider 선언과 기존 공식 설치 근거를 받는다. 제공된 자료로 충분하면 SDK/기기/호스트 설정 탐색을 추가하지 않는다.

## 수행 방법과 절차

1. [Android 공통 작업 기준](../../references/android-work.md)의 입력·범위·버전·실행/결과 조건을 현재 요청에 적용한다. 해당 기준은 이 skill을 사용하는 동안 필수이며 전역 자동 주입을 뜻하지 않는다.
2. 아래 공통 외부 연결로 선택한 공식 entry 하나를 확인하고 공식 SKILL.md에 진입한다. 필요한 reference는 공식 skill 자신의 root에서 해석한다. 미선택 이웃 skill을 한꺼번에 읽지 않는다.
3. 공통 기준과 실제 공식 절차가 충돌하면 영향받는 실행을 보류하고 설명한다. 원문 편집·사본 실행·필수 단계의 묵시적 생략·자동 공급자 대체로 충돌을 없애지 않는다. 이미 승인된 독립 작업은 계속한다.
4. 실제 산출물/결과를 아래 기대 결과·원래 요청·보존 조건과 대조한다. 분석·작성·빌드·host/device 테스트를 서로 다른 상태로 보고한다.

## 연계와 의존

| 대상 | 전달 입력·필요 결과 | 필수 여부·부재 처리 |
| --- | --- | --- |
| provider `running-instrumented-tests-with-androidjunit4` · 종류 skill. [공통 외부 연결](../../references/external-connection.md) | 위 입력. 필요한 결과: 실제 설정/버전 근거·runner/테스트 클래스 구분·최소 수정·빌드/실행 검증 또는 미실행 | 공식 수행에 필수. 부재·pin drift·필수 reference 부재는 영향받는 수행을 보류. 제공 자료의 자체 분석은 가능 범위만 보고하고 공식 실행 완료로 표시하지 않음 |

## 결과와 완료 판단

- 실제 설정/버전 근거·runner/테스트 클래스 구분·최소 수정·빌드/실행 검증 또는 미실행. 실제 사용한 공식 기능·확인 버전/출처·승인과의 충돌·남은 제약을 반환한다.
- entry/형식/정적 검토·지침 모델 시험을 Android 빌드나 실기기 성공으로 보고하지 않는다.
