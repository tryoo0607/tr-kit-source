Claude에서 컨텍스트 롤오버는 잔여 80k에 정리를 시작하고 잔여 50k에 `/clear`를 안내한다. `/clear`는 사용자가 실행하며 `session-check`와 `inject-state`가 최신 state 재주입을 연결한다.

원격 세션이 무응답이면 포화로 단정하기 전에 현재 host의 연결·모달 상태를 확인한다. `/clear`·plugin reload·세션 재시작의 상세는 `references/host-control.md`를 읽는다. 종료·재시작·`/clear`는 사용자의 명시적 지시 없이 실행하지 않는다.
