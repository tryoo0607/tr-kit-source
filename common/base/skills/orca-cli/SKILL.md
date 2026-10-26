---
name: orca-cli
description: Orca CLI로 repo 등록, 외부 worktree 인식과 기존 공간의 에이전트 실행/전달을 수행한다. 공간 정책은 project, 인계와 감독 판단은 session에 맡긴다.
license: upstream/LICENSE
metadata:
  tr-role: external-wrapper
---

# Orca 연결

## 목적과 역할 경계

호스트, 기존 공간 ID/경로, 요청 조작, 수신자/전달 내용과 승인 범위를 받아 실행한다. project/session이 제공한 판단은 재사용하고 다시 로드하지 않는다. 추가 공간은 project가 Worktrunk로 준비하며 Orca 신규 checkout으로 대체하지 않는다.

## 수행 방법과 절차

1. 실행 파일을 한 번 선택한다. ORCA_CLI_COMMAND가 있으면 그 값, 없고 ORCA_DEV_REPO_ROOT가 있는 개발 환경이면 orca-dev, 그 외 Linux의 Orca 밖에서는 orca-ide, 나머지는 orca다. Linux의 GNOME 화면 읽기 프로그램을 잘못 실행하지 않는다. 선택 파일이 실패하면 다른 실행 파일로 자동 전환하지 않는다.
2. 선택한 CLI의 `skills get orca-cli`로 버전 일치 guide를 조회하고 필요한 작업 절만 읽는다. 같은 호스트/버전의 기존 guide는 재사용한다. upstream/GUIDE.md는 원본 stub 보존용이며 기본 로드하지 않는다. CLI/guide 미지원이면 읽기 전용 도움말로 확인하고 미지원 조작은 보류한다.
3. 기존 공간 ID와 실제 경로/수신자를 확인한다. 등록과 외부 공간 인식은 해당 guide의 repo/worktree 조회 절차, 실행은 기존 공간의 agent launch, 전달은 정확한 수신 핸들 하나를 사용한다. 인식 실패를 worktree create로 해결하지 않는다.
4. 동일 전달/실행의 재시도 식별자를 보존하고 응답 지연만으로 새 실행이나 재전송을 하지 않는다. 실제 ID/경로와 receipt, 턴 시작 여부와 미결을 반환한다.

## 제약과 주의점

guide의 Full Handoffs보다 호출자가 정한 같은 대화 재개/전체 인계/감독 위임 구분을 따른다. 전달 receipt는 입력 접수 근거이며 상대 작업 완료 근거가 아니다. 기록 내용은 document가 소유한다. 일반 조작에 orchestration/computer-use/emulator를 추가하지 않으며 해당 기능이 필요하면 미지원 범위를 알린다.

기동, 원격 입력, 종료/재시작, 공개 링크와 hook 실행은 승인 범위를 따른다. guide의 open 권고나 skill 로드만으로 실행하지 않는다. 런타임 접근 거부를 재기동으로 우회하지 않는다.

## 결과와 완료 판단

조회, 등록, 실행과 전달의 확인 범위를 구분해 반환한다. 전체 인계는 전달 증거를, 감독 위임의 상대 작업 완료는 요청된 별도 증거를 사용한다.
