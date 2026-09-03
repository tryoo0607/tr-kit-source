# Claude 세션 제어

Claude 원격 세션의 생성·부활·막힘 해제와 `/clear` 동작에만 적용한다.

## 무응답 진단

원격에서 입력해도 답이 없으면 컨텍스트 포화로 단정하기 전에 모달 대기를 확인한다.

```bash
claude-remote status <name>
claude-remote unblock [name]
```

- `unblock`은 상태를 재확인한 뒤 막힌 세션에만 Esc를 보낸다.
- 선택형 모달에서 Enter는 항목을 실행할 수 있으므로 공통 탈출키로 쓰지 않는다.
- 모달이 아니면 응답 지연·컨텍스트 포화·compact 실패를 다음 후보로 본다.

## 생성·부활

```bash
claude-remote -d new <name>
claude-remote -d restart <name>
claude-remote machine
claude-remote machine <tag>
```

- `-d`는 세션만 올리고 붙지 않는다.
- 머신 태그는 사용자가 정한 값이다. 설정이 없으면 hostname 등으로 추측하지 않는다.
- 이미 이름이 붙은 대화를 resume해도 앱 표시명이 바뀐다고 가정하지 않는다.
- 반복 입력 표면을 줄여야 하면 `~/.config/claude-remote/aliases.sh`의 짧은 alias를 사용한다.

## 권한 모드

세션별 권한은 `CLAUDE_REMOTE_MODE`가 정한다. CLI 인수가 settings 기본값보다 우선하므로 실제 실행 인수를 확인한다. `bypassPermissions`는 분류기까지 건너뛰므로 사용자가 명시하지 않으면 선택하지 않는다.

## 롤오버

```text
잔여 80k → state 정리 시작
잔여 50k → 사용자에게 /clear 안내
/clear 후 → session-check + inject-state가 state 재주입
```

`/clear`, kill, 전체 cycle은 사용자의 명시적 행동이다. 부활 좌표와 busy 세션을 확인하지 않고 실행하지 않는다.

`claude-remote`가 없거나 심링크가 끊겼으면 임시 우회하지 않고 `kit`의 Claude delivery 절차로 넘긴다.
