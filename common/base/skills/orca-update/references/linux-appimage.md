# Linux AppImage 업데이트

선택한 대상에서 AppImage와 systemd 서비스 사용이 확인된 경우에만 읽는다. 이 파일은 설치 변경을 다루며 대상 선택과 완료 기준은 본문이 소유한다.

## 입력과 전제

대상의 실제 AppImage 경로, architecture, 서비스 소유 사용자와 unit, ExecStart, 필요한 가드와 권한, 독립 관리 경로를 확인한다. `systemctl --user show <unit> --no-pager` 등 현재 OS가 지원하는 읽기 전용 조회를 사용한다. 서비스가 system scope이면 사용자 서비스 명령으로 바꾸지 않는다. AppImage 경로가 root 소유이면 일반 사용자 권한으로 교체할 수 있다고 가정하지 않는다.

버전별 동작은 선택한 설치본의 도움말과 [공식 설치 안내](https://www.onorca.dev/docs/install), [공식 서버 안내](https://www.onorca.dev/docs/remote-servers), [공식 릴리스](https://github.com/stablyai/orca/releases)에서 필요한 절만 확인한다. `serve --supervise`나 서비스 관리 명령이 최신 문서에 있다는 이유로 기존 unit을 자동 변경하지 않는다. 설치된 버전의 지원과 기존 Restart 정책을 대조한다.

## 수행 방법과 절차

1. 본문의 orca-cli 계약으로 실제 대상 shell을 확인한다. 기존 shell을 쓰면 idle 상태와 실제 호스트를 확인하며 에이전트 입력창에 명령을 보내지 않는다. 모든 시스템 조회에 pager를 끄고, 호스트 정책의 설치 및 서비스 변경 capability를 실행 전에 검사한다. 가드 DENY를 sudo나 다른 접속으로 우회하지 않는다.
2. 해당 architecture의 공식 release asset을 선택하고 release tag, asset URL과 제공된 digest를 고정한다. 임시 파일에 다운로드하고 파일 형식, architecture와 제공된 무결성 값을 확인한다. digest가 없으면 SHA256을 계산했다는 이유로 공급자 검증을 마쳤다고 하지 않는다. 현재 설치 정책이 요구하는 신뢰 근거를 확보하지 못하면 교체를 보류한다. 다운로드 스크립트를 받아 바로 shell로 실행하지 않는다.
3. 실제 AppImage와 같은 파일시스템에 새 후보를 준비하고 소유자와 실행 권한을 확인한다. 기존 AppImage의 hash와 보존 파일 경로를 기록한다. unit, profile, pairing, 계정과 작업 데이터는 기존 것을 유지한다. 교체와 서비스 재시작의 정확한 명령을 만들고 승인 범위와 대조한다.
4. Orca 자체를 재시작하므로 그 Orca가 소유한 terminal 안의 foreground 명령에 완료를 의존하지 않는다. 기존 SSH 관리 경로나 대상 OS의 독립 실행 수단을 사용한다. systemd transient unit을 쓰면 이번 실행 고유 unit 이름, journal 조회법, timeout과 최종 종료 상태 회수법을 먼저 확정한다. 실제 unit에서 쓸 PATH, 사용자, 작업 경로와 필요한 권한을 명시하고 비밀번호 입력에 의존하지 않는다. 독립 실행과 결과 회수가 가능한지 확인할 수 없으면 중단한다.
5. 이미 다운로드하고 검증한 파일만 교체한다. 서비스의 기존 감독 정책이 확인되지 않으면 설치 변경, 서비스 정지와 시작의 순서를 그 정책에 맞춰 정한다. 최종 경로 교체는 같은 파일시스템에서 원자적으로 수행하며 이전 파일은 보존한다. 독립 실행 기록에 각 단계와 최종 exit status를 남기고 인증정보는 남기지 않는다. 독립 unit 제출 응답 뒤에는 동일 작업 상태를 조회하고 명령을 새로 보내지 않는다.
6. 독립 실행 결과와 실제 서비스 상태를 회수한다. 성공 종료만으로 완료하지 않고 본문의 재접속, 목표 runtime 버전, workspace와 terminal probe 검증을 수행한다. 한 대상이 검증되기 전 다음 대상을 시작하지 않는다.

## 실패와 복구

다운로드, 검증, 교체와 재시작 중 어느 단계가 끝났는지 구분한다. 교체 전 실패는 기존 실행 파일을 보존한다. 교체 후 실패는 독립 실행 로그와 새 파일 hash, 서비스 ExecStart 및 실제 runtime을 먼저 확인한다. 명령을 실행했다는 기록만 있고 결과가 없으면 미확인이다.

자동 원복은 기존 데이터 형식 호환성과 사용자 승인 범위가 확인된 경우에만 수행한다. unit 재설치나 supervision 전환을 업데이트 실패의 자동 해결책으로 쓰지 않는다. 기존 pairing으로 복귀할 수 없는 경우 임의 재발급하지 않고 미결을 보고한다.
