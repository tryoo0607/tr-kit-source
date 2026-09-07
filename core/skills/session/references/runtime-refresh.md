# 실행 중 세션의 plugin runtime 갱신

Plugin 설치가 끝난 뒤 이미 실행 중인 세션에 새 skill·hook을 반영하는 절차다. 설치·marketplace·cache 자체는 `kit`에서 먼저 끝낸다.

## 공통 계약

1. 현재 설치 version과 적용 기준 시각을 확인한다.
2. 사용자에게 보이는 root session 기준으로 inventory를 만든다. 하위 agent·app-server PID를 별도 세션으로 세지 않는다.
3. 현재 작업 세션, busy, 상태 불명, 이미 새 runtime으로 시작한 세션은 제외한다.
4. idle 세션 하나를 canary로 선택하고 정확한 session ID·현재 PID·재개 방식을 보고한다.
5. 승인 후 canary만 갱신하고 동일 session identity·새 root PID·plugin skill·hook pickup을 검증한다.
6. canary가 통과하면 나머지 대상 목록을 다시 계산해 승인된 batch만 순차 갱신한다.
7. 실패하면 강제 종료로 넘어가지 않고 해당 세션을 보류한다.

## 안전 경계

- inventory와 plan이 기본이며 실제 종료·재시작에는 명시 승인이 필요하다.
- root PID와 현재 session ID를 함께 검증해 오래된 plan으로 다른 프로세스를 종료하지 않는다.
- 정상 종료만 사용한다. 제한 시간 안에 종료되지 않으면 자동 `SIGKILL`하지 않는다.
- 세션 제목·대화·underlying thread identity를 보존하는 host 기능만 사용한다.
- 비밀 필드가 섞인 session store 전체를 출력하지 않는다.

## Happy host 복구 (`TEMPORARY_HAPPY_COMPAT`)

PolyGarden 전환 전 임시 host 지원은 source checkout의 `install.sh happy-host`가 소유한다.
기본은 dry-run이며 `--apply`에서만 `~/.local/bin/happy-cycle`과 systemd user unit을
복사하고 daemon·snapshot timer를 enable한다. `--dest` staging은 systemd 상태를 바꾸지 않는다.
서버 주소·plugin directory 같은 머신별 값은 installer가 덮지 않는 `~/.config/happy/env`에
두며 daemon과 restore worker가 함께 읽는다.

- `happy-cycle snapshot`: 실제 process environment의 Happy session ID까지 일치하는 root만 원자적으로 저장한다.
- `happy-cycle restore`: snapshot에서 현재 죽은 session만 같은 ID와 cwd로 재개한다.
- `happy-cycle cycle`: snapshot 뒤 확인을 받고 정확한 PID만 정상 종료하고 daemon을 재기동한 다음 detached user unit에서 복원한다. 비대화형 실행은 `--yes`도 명시해야 한다.
- 모든 변경 명령은 기본 plan-only이며 `--apply`가 필요하다. `SIGKILL`과 전체 process-name kill은 사용하지 않는다.
- 주기 snapshot은 활성 세션이 0개이거나 cycle lock이 잡힌 동안 기존 복구 좌표를 덮지 않는다.
- daemon은 부팅 시 자동 시작하지만 개별 session의 부팅 자동 restore는 하지 않는다. 필요할 때 사용자가 `happy-cycle restore --apply`를 실행한다.
- 로그인 전 자동 시작에는 user linger가 필요하다. installer는 상태를 표시하고 명시 `--enable-linger`에서만 변경한다.

## 완료 조건

- canary와 batch 각각에서 기존 사용자 session identity가 유지된다.
- root PID는 교체되고 새 runtime의 plugin version·skill·hook이 관찰된다.
- busy·현재 세션·상태 불명 세션은 건드리지 않았음이 결과에 남는다.
