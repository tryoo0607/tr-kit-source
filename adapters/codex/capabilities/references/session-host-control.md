# Codex 세션 제어

## 롤오버

```text
60% → state 정리 시작
75% → resume/fork가 아닌 새 독립 세션 안내 + pending origin 기록
새 session id → state 한 파일 단발 주입 + marker ack
```

새 세션은 사용자가 만든다. lifecycle hook은 새 session id와 같은 continuity key를 확인해 읽을 state 경로만 안내하며 이전 대화 전체를 자동으로 읽지 않는다.

## 무응답 세션

다른 Codex 세션에 임의 입력·종료 신호를 보내지 않는다. 사용자가 제공한 앱 상태와 실행 중인 프로세스를 읽기 전용으로 확인한다. 재시작·종료가 필요하면 정확한 대상과 작업 손실 가능성을 먼저 보고한다.
