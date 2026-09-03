---
description: 아이디어를 configured handoff repository의 INBOX에 한 줄로 캡처한다. 저장소가 없으면 local-docs에 둔다.
argument-hint: "<아이디어 텍스트>"
---

`$ARGUMENTS`를 검증·정제하지 않은 한 줄 아이디어로 캡처한다.

1. plugin root의 `profile/setup.py get public.repositories.handoffs`로 handoff repository를 해석한다.
2. 연결되어 있으면 그 repository의 `INBOX.md`에 append할 diff를 먼저 보여준다.
3. 연결이 없으면 현재 프로젝트 `_local-docs/INBOX.md`를 사용한다. 프로젝트도 판정할 수 없으면 저장 위치를 묻는다.
4. 파일 변경 승인과 원격 push 승인은 구분한다. push 요청이 없으면 로컬 기록까지만 한다.

캡처 단계에서는 중요도나 분류를 오래 고민하지 않는다. 조직·고객 자산은 개인 handoff repository에 기록하지 않는다.
