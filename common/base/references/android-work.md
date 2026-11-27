# Android·Wear OS 작업 범위와 검증

Android 전문 연결을 선택한 경우 공통 입력·범위·실행·완료 기준을 적용한다. 공식 기술 절차는 선택한 공식 설치본이 소유한다. BMAD 구현 과정에서 Android 전문 기능을 선택할 때도 이 기준을 사용하며 일반 개발 요청에는 로드하지 않는다.

## 입력과 전제

- 실제 프로젝트·모듈/source set·현재 구조/DI·version catalog/Gradle 설정·오류/로그와 요청을 먼저 확인한다. 이미 제공된 자료·승인은 재사용한다. 분석만 요청됐으면 실제 SDK/기기/패키지 탐색을 추가하지 않는다.
- 원문 예제·최신 버전·기존 작업의 선택과 현재 프로젝트의 pin/요구를 구분한다. 최신 버전 확인은 업그레이드 승인이 아니다. version을 알아내기 위해 의존성을 자동 resolve/download하지 않는다.
- 공식 설치본의 사용 가능성과 실제 실행 환경은 별도로 확인한다. 원문 대조용 checkout이나 구 kit의 동봉·치환본을 공식 실행 외부 연결로 등록하지 않는다.

## 수행 방법과 절차

### 요청·공식 절차·승인 범위

- 기존 구조·DI·테스트 스택·pin을 현재 근거로 사용한다. 모듈·domain/use-case 계층·Hilt·LiveData 전환·Horologist 이전·도구 버전 변경을 전문 skill을 읽었다는 이유로 수행하지 않는다. 필요성이 확인되면 영향과 대안을 제시하고 기존 승인 범위와 대조한다.
- 필요한 공식 기능 하나와 실제 요청에 맞는 절차를 적용한다. 원문의 필수 설치/업그레이드/기기 변경이나 미제공 reference가 요청과 충돌하면 해당 수행을 보류한다. 사용자의 범위·기존 pin은 작업 입력으로 전달하며 원문을 고치거나 필수 절차를 몰래 생략해 공식 workflow를 완료했다고 주장하지 않는다.
- 다른 기능과의 연결은 선택과 수행을 구분한다. BMAD build가 구현·검증의 작업 정본을 소유하며 전문 skill은 그 입력/결과를 보조한다. 전문 skill 부재를 BMAD를 생략하거나 공식 작업 완료를 꾸미는 근거로 쓰지 않는다.
- 버전/API가 불명확하거나 예제가 맞지 않으면 [ext-find-docs](../skills/ext-find-docs/SKILL.md)에 정확한 library·pin·질문을 전달해 허용된 공식 문서/소스를 확인한다. 기존 근거가 충분하면 재조회하지 않는다. 확인하지 못한 API/의존 버전을 호환된다고 보고하거나 예제 import를 강제로 복사하지 않는다.

### 실행과 데이터 변경

- 테스트 종류·예상 대상/개수·실제 프로젝트 명령·환경을 확인하고 승인한 동작만 실행한다. SDK·emulator·앱/APK·의존성·MCP/새 서비스를 자동 설치하지 않는다. 실행 환경 부재는 미실행이며 자동 설치의 근거가 아니다.
- 실제 기기 실행은 명시 serial·app/test package·runner·선택할 테스트와 승인한 영향을 확인한다. 여러 기기 중 첫 장치를 고르지 않는다. 무선 연결/포트 노출도 테스트 실행 승인에 포함됐는지 확인한다.
- clearPackageData/pm clear·앱 설치/초기화·animation 등 기기 설정 변경은 별도 효과다. 필요한 범위가 승인됐으면 진행하되 변경 전 값과 복원 가능한 항목의 복원 결과를 확인한다. 데이터 초기화가 원상 복원 가능하다고 약속하지 않는다. 승인 밖 효과는 그 동작만 보류한다.

### 결과 해석

- shell 종료 상태·명령 실행·빌드 성공·테스트 성공을 분리한다. 기존 runner/parser의 실제 결과를 확인하고 예상한 테스트가 실행됐는지, 출력이 완결됐는지, 실패/runner 오류·누락·skip·0건 여부를 대조한다. 한 줄 성공 문구·실패 문자열 부재·종료 코드만으로 성공을 판단하지 않는다.
- 원문 예제의 단순 grep/CI 조각을 프로젝트의 검증된 결과 parser로 간주하지 않는다. 기존 parser가 없거나 결과가 불완전하면 캡처/정적 관측과 미검증을 보고한다. 자체 parser·새 CI gate 작성은 해당 요구가 있을 때 별도로 다룬다.
- 제공 로그 분석은 실제 재실행과 다르다. unknown/부분 실행·모든 테스트 skip·0건을 전체 통과로 보고하지 않으며, failure/runner 오류가 확인되면 실행 환경 문제와 테스트 실패를 구분한다. 결과 해석 충돌은 원문 변경 대신 원문 위치·실제 근거·미결로 남긴다.

## 요청별 분기

같은 요청은 위에서부터 처음 일치하는 하나를 선택한다. 별도 대상/동작은 각각 선택한다. 테스트 체계 전체의 필수 순서가 아니며 선택하지 않은 skill을 기본 로드하지 않는다.

| 요청 | 선택 조건 | 읽을 reference |
| --- | --- | --- |
| Android 구조·DI 설계/검토 | 모듈/레이어/상태/DI 판단이 요청됨 | [ext-android-architecture](../skills/ext-android-architecture/SKILL.md) |
| Wear Compose 화면·컴포넌트·이전 | 해당 Wear 작업이 요청됨 | [ext-wear-compose-m3](../skills/ext-wear-compose-m3/SKILL.md) |
| 테스트 전략·기반 선택 | 테스트 종류·도구/인프라 전략이 요청됨 | [ext-testing-setup](../skills/ext-testing-setup/SKILL.md) |
| Compose 테스트 골격 | 해당 테스트 클래스·상태·rule·검증 흐름이 요청됨 | [ext-structuring-a-compose-test](../skills/ext-structuring-a-compose-test/SKILL.md) |
| instrumented runner 구성 | source set/runner/import/의존 연결 문제가 요청됨 | [ext-running-instrumented-tests-with-androidjunit4](../skills/ext-running-instrumented-tests-with-androidjunit4/SKILL.md) |
| ADB 테스트 실행·출력 판정 | 기존 runner를 통한 해당 실행/출력 분석이 요청됨 | [ext-running-instrumented-tests-via-adb](../skills/ext-running-instrumented-tests-via-adb/SKILL.md) |

이미 이 기준에서 선택한 wrapper에 진입했으면 그 wrapper가 다시 링크하는 공통 기준은 읽은 결과를 재사용한다. 분기표를 다시 평가해 같은 wrapper를 재귀 호출하지 않는다.

## 결과와 완료 판단

- 현재 프로젝트 근거·확인한 공식 기능/버전·요구/보존 조건과의 차이·선택한 작업·실제 산출물/관측·실패/미실행을 연결한다.
- 정적 검토·공식 지침 읽기·모델 시험·빌드·host 테스트·instrumented/실기기 검증·복원은 별도 상태다. 한 층위의 통과를 다른 층위나 다른 제품의 통과로 확대하지 않는다.
