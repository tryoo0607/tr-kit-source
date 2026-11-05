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
4. 일반 세션 위임은 agent launch 또는 확인한 수신 핸들에 send하고, read로 그 요청의 실제 응답을 확인한다. 입력 접수와 완료를 구별하고 이미 시작한 작업을 다시 보내지 않는다. 응답 대기·진행 확인·같은 대화에 결과 반환만으로 orchestration을 선택하지 않는다. 호출자가 공식 작업 배정·완료 추적 기능을 명시적으로 요청했을 때만 같은 실행 파일의 `skills get orchestration`과 필요한 원격 placement guide를 적용한다. 해당 기능 실패를 일반 전달로 자동 전환하지 않는다. 실행 호스트·수신자·승인 범위를 검증하며 자체 위임기나 SSH 명령 대행으로 독립 작업자를 대체하지 않는다.
5. 동일 전달/실행의 재시도 식별자를 보존하고 응답 지연만으로 새 실행이나 재전송을 하지 않는다. 실제 ID/경로와 receipt, 턴 시작 여부와 미결을 반환한다.

### 프로젝트 소속 조회

소속 연결 요청에는 `project list --json`과 `repo list --json`을 같은 호스트에서 조회한다. `ok`와 실제 repo 경로를 확인하고 project의 `sourceRepoIds`를 repo의 `id`와 대응한다. repo가 반환한 `projectGroupId`는 그룹 소속 근거이며 폴더명은 근거가 아니다. 호스트 범위도 함께 반환하고 project/repo/group 식별자를 서로 바꿔 쓰지 않는다.

1.4.242의 공식 repo 출력에서 그룹 ID를 확인했지만 별도 그룹 목록 CLI는 확인하지 못했다. 그룹 이름·상위 관계가 필요한데 출력에 없으면 명시된 그룹 정보와 대조하거나 해당 정보 미확인으로 반환한다. 내부 DB·캐시를 런타임 연결 정본으로 삼거나 폴더명으로 보충하지 않는다. 새 버전에서 조회 명령이 추가됐는지는 해당 CLI의 guide/schema로 확인한다. 문서·assets 경로의 선택과 생성은 호출자에게 맡긴다.

## 제약과 주의점

guide의 Full Handoffs보다 호출자가 정한 같은 대화 재개/전체 인계/감독 위임 구분을 따른다. 전달 receipt는 입력 접수 근거이며 상대 작업 완료 근거가 아니다. 기록 내용은 document가 소유한다. 일반 조작에는 orchestration/computer-use/emulator를 추가하지 않는다. 명시적인 공식 추적 요청에만 orchestration guide를 적용하며 미지원 기능은 보류하고 알린다.

기동, 원격 입력, 종료/재시작, 공개 링크와 hook 실행은 승인 범위를 따른다. guide의 open 권고나 skill 로드만으로 실행하지 않는다. 런타임 접근 거부를 재기동으로 우회하지 않는다.

## 결과와 완료 판단

조회, 등록, 실행과 전달의 확인 범위를 구분해 반환한다. 전체 인계는 전달 증거를, 감독 위임의 상대 작업 완료는 요청된 별도 증거를 사용한다.
