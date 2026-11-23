---
name: wiki
description: 명시적으로 선택한 Wiki의 지식 조회·원본 수집·정리·갱신·점검을 공식 설치본에 연결한다. 일반 문서 작성·경험 검색과 구분하며 조회 요청으로 색인·수집·자동 주입을 켜지 않는다.
metadata:
  tr-role: external-wrapper
---

# wiki

## 목적과 역할 경계

- 명시 Wiki 업무에서 지식 조회와 관리 동작을 구분해 공식 기능에 연결한다. 모든 문서/URL을 기본 수집하지 않는다.
- 원본 보관·작업 정본·경험 검색은 document와 해당 담당이 소유한다. 기존 hub와 개인/프로젝트 자료의 권한을 유지한다.

## 입력과 전제

- 질문/동작·실제 제품·hub/topic 또는 기존 설정 포인터·자료 소속·공유 범위·저장 범위를 확인한다. 누락을 전체 home/서버 검색으로 보완하지 않는다.
- 제품이 명시되지 않으면 실제 현재 환경으로 확인하고 불명이면 해당 호출만 보류한다. 선택하지 않은 adapter를 읽거나 두 제품을 연속 실행하지 않는다.

## 수행 방법과 절차

1. 아래에서 실제 제품의 provider reference 하나를 읽는다. 공통 요구를 전달하고 공식 설치본 entry를 확인한 후 해당 공식 절차를 적용한다.
2. 질문·검색만 요청되면 read-only provider를 사용한다. 수집/compile/수정 등 요청은 관리 provider를 사용하되 추가 효과를 기존 승인과 대조한다. 조회가 실패했다는 이유로 관리 동작을 실행하지 않는다.
3. raw 원본·compiled 지식·관측·추론·미확인을 구분하고 source/시점/충돌을 보존한다. 조회·저장·지식화·검증은 별도 상태다.

## 연계와 의존

| 대상 | 전달 입력·필요 결과 | 필수 여부·부재 처리 |
| --- | --- | --- |
| Codex [provider](../../../../adapters/codex/skills/wiki/references/provider.md) | 위키 동작·hub/topic·승인 범위. 결과는 실제 source/경로·변경·조회 한계 | Codex에서 필수. provider 부재 시 해당 동작 미실행, 복제 runtime/다른 제품으로 자동 전환하지 않음 |
| Claude [provider](../../../../adapters/claude/skills/wiki/references/provider.md) | 동일 공통 입력·결과 | Claude에서 필수. 동일 부재 처리 |

## 제약과 주의점

- 자동 capture·feedback·초기 맥락 주입·private adapter 설정·설치·전송은 이 skill 선택으로 활성화되지 않는다.
- 회사 자료를 개인 hub/NAS로 보내지 않는다. 기존 저장소가 있다는 사실은 자료 반입·공유 승인 근거가 아니다.

## 결과와 완료 판단

- 실제 source와 조회 범위, 변경 요청의 반영 위치/검증, 미연결·stale·미실행을 구분한다. 공식 entry 확인을 실행 성공으로 확대하지 않는다.
