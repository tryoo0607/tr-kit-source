# Claude 세션 제어

Claude 원격 세션의 상태 확인, `/clear`, plugin 갱신 경계에만 적용한다.

## 무응답 진단

원격에서 입력해도 답이 없으면 컨텍스트 포화로 단정하기 전에 현재 host UI에서 연결 상태와 모달 대기를 확인한다.

- 선택형 모달에서 Enter는 항목을 실행할 수 있으므로 공통 탈출키로 쓰지 않는다.
- 모달이 아니면 응답 지연·컨텍스트 포화·compact 실패를 다음 후보로 본다.
- kit은 별도 원격 세션 manager binary를 배치하거나 특정 host의 생성·부활 명령을 소유하지 않는다.

## 권한 모드

세션별 권한은 `CLAUDE_REMOTE_MODE`가 정한다. CLI 인수가 settings 기본값보다 우선하므로 실제 실행 인수를 확인한다. `bypassPermissions`는 분류기까지 건너뛰므로 사용자가 명시하지 않으면 선택하지 않는다.

## 롤오버

```text
잔여 80k → state 정리 시작
잔여 50k → 사용자에게 /clear 안내
/clear 후 → session-check + inject-state가 state 재주입
```

`/clear`, 종료, 재시작은 사용자의 명시적 행동이다. busy 세션과 작업 기록을 확인하지 않고 실행하지 않는다.

## Plugin runtime 갱신

Marketplace/cache 갱신 뒤 현재 Claude Code 세션은 `/reload-plugins`를 우선 사용한다. 여러 원격 세션은 각각의 idle 상태를 확인하고 사용자 승인 후 순차 reload한다. `/reload-plugins`가 없거나 실패한 세션만 현재 host가 제공하는 정상적인 restart/resume 경로로 넘긴다. Codex/Happy용 process helper를 Claude 세션에 사용하지 않는다.

### Happy Agent SDK 임시 우회 (`TEMPORARY_HAPPY_COMPAT`)

PolyGarden 전환 전까지 Happy daemon의 systemd 환경에 아래 두 값을 한 번 설정한다. 대화마다 주입하는 값이 아니다.

```ini
Environment=HAPPY_PLUGIN_DIRS=<현재 검증된 tr-claude plugin directory>
Environment=HAPPY_SETTING_SOURCES=user,project,local
```

daemon을 다시 시작한 뒤 기존 Claude 세션도 restart/resume해야 반영된다. Marketplace update는 이 경로를 자동 갱신하지 않으므로 남은 Happy 사용 기간에는 검증된 version을 고정하고, 꼭 올릴 때만 경로와 runtime을 함께 갱신한다. 이 절차는 Happy와 함께 제거하며 확장하지 않는다.
