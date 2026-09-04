# Codex 세션 제어

## 롤오버

```text
60% → state 정리 시작
75% → state 마무리 + "이제 /clear 하셔도 됩니다" 안내 + pending origin 기록
/clear 뒤 새 session id → state 한 파일 단발 주입 + marker ack
```

`/clear`는 사용자가 실행한다. lifecycle hook은 Happy session ID 또는 격리된 tmux pane key가 같은 경우에만 새 session id를 clear 후속 context로 인정한다. continuity key를 확인하지 못하면 자동 pickup하지 않는다. auto-compact는 같은 thread의 압축 재개이며 독립 세션으로 표시하지 않는다.

## Plugin runtime 갱신

Happy/Codex에서는 `scripts/happy_runtime_refresh.py inventory`로 root session과 busy/idle을 먼저 확인한다. `refresh <session>=<pid>`는 plan만 출력하고, 사용자 승인 뒤 같은 명령에 `--apply`를 붙여 실행한다. helper는 현재 세션·busy·stale PID를 거부하고 `SIGTERM` 뒤 `happy resume <Happy session ID>`만 사용하며 새 root PID와 `tr-codex:*` skill 수를 확인한다. batch도 canary 성공 후 다시 계산한 명시 session 목록만 받는다.

## 무응답 세션

다른 Codex 세션에 임의 입력·종료 신호를 보내지 않는다. 사용자가 제공한 앱 상태와 실행 중인 프로세스를 읽기 전용으로 확인한다. 재시작·종료가 필요하면 정확한 대상과 작업 손실 가능성을 먼저 보고한다.
