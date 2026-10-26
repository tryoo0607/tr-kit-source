---
name: worktrunk
description: Worktrunk CLI의 worktree 조회, 생성과 정리, 설정과 문제 해결을 수행한다. 프로젝트 배치는 project, 에이전트 실행은 session에 맡긴다.
license: upstream/LICENSE
metadata:
  tr-role: external-wrapper
---

# Worktrunk 연결

## 목적과 역할 경계

확인된 repo, 시작 ref, 브랜치, 경로와 승인 범위를 받아 CLI 조작을 수행한다. 호출자가 이미 판단한 입력은 재사용한다. 배치와 격리 필요는 project, 에이전트 실행은 session이 소유하며 tmux/Zellij와 Claude Agent 실행 절차를 이 skill에서 적용하지 않는다.

## 수행 방법과 절차

1. 해당 호스트의 CLI와 기존 공간을 확인한다. 같은 repo에서 브랜치 인자가 공간을 선택하며, 다른 repo 또는 현재 공간 기준 명령에는 실행 위치를 지정한다. 충분한 기존 지침과 조회 결과는 재사용한다.
2. 아래에서 요청에 필요한 공식 명령 자료만 읽는다. 원본 전체 안내인 upstream/GUIDE.md는 기본 로드하지 않는다. 설치 버전 도움말로 실제 지원을 확인한다.
3. 기존 공간이 있으면 재사용하고 요청된 조작만 수행한다. 시작 commit 부재, 경로 충돌이나 도구 부재는 해당 조작을 보류한다. 사용자 설정을 작업 공간 요청의 부수 효과로 바꾸지 않는다.
4. 실제 경로, Git 연결, 브랜치/시작 상태와 오류를 반환한다. 정리에서는 미반영 변경과 사용 중 세션, 브랜치 삭제 부수 효과를 확인한다. 추가 등록과 에이전트 실행을 자동 수행하지 않는다.

## 요청별 분기

| 요청 | 선택 조건 | 읽을 reference |
|---|---|---|
| 공간 조회 | 기존 결과로 부족함 | [list](upstream/reference/list.md)의 Columns, Worktree와 요청된 출력 옵션 |
| 공간 생성 또는 전환 | 해당 조작이 필요함 | [switch](upstream/reference/switch.md)의 Creating a branch, Creating worktrees, Command reference |
| 공간 정리 | 해당 조작이 필요함 | [remove](upstream/reference/remove.md)의 동작, 옵션과 실패 조건 |
| 경로 설정과 명령 설정 | 설정 확인/변경이 요청됨 | [config](upstream/reference/config.md)의 해당 설정 절 |
| hook 설정 또는 승인 오류 | 해당 요청이나 오류가 발생함 | [hook](upstream/reference/hook.md)의 관련 절과 설치 CLI 승인 도움말 |

## 제약과 주의점

외부 plugin hook은 등록하지 않는다. Worktrunk 내부 hook도 별도 채택과 실행 권한이 필요하다. 미채택이면 지원되는 --no-hooks로 건너뛰고 필요한 환경 준비의 미수행을 반환한다. 채택된 hook도 승인 오류를 --yes로 우회하지 않는다. 설정 변경과 의존성 설치는 승인 범위를 따르며 hook 권고만으로 실행하지 않는다.

## 결과와 완료 판단

실제 공간과 요청 조작의 성공/실패를 확인한다. shell 이동을 현재 에이전트 세션의 자동 이동으로 보거나 worktree 준비를 등록/에이전트 실행 완료로 표시하지 않는다.
