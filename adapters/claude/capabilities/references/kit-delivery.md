# Claude kit delivery

## 소유 경계

Claude kit의 배포 대상은 skills·commands·hooks가 든 plugin repository와 marketplace cache다. 별도 host binary, systemd user unit, 사용자 `settings.json`·statusline·session data는 배치하거나 덮어쓰지 않는다.

## 점검 순서

1. target repo와 생성물 diff를 확인한다.
2. plugin manifest version과 marketplace source를 확인한다.
3. cache에 설치된 version과 새 session의 skill·hook 반영 여부를 구분한다.
4. 실제 설치·재시작 전에 사용자 승인을 받는다.

## Plugin cache 갱신

```bash
claude plugin marketplace update tr-claude
claude plugin update tr-claude@tr-claude
claude plugin list
```

- plugin update는 repo 작업 트리를 직접 읽지 않고 cache 사본을 갱신한다.
- 내용이 바뀌었는데 manifest version이 같으면 update가 no-op일 수 있다.
- 새 skill·hook·description은 재시작 전 세션에 반영됐다고 보지 않는다.
- Remote Control에서 slash UI가 막히면 위 CLI를 사용한다.

## 설명서 발행

설명서의 수치가 generator 산출이면 손으로 고치지 않는다. 본문 변화 없이 version·개수만 달라진 경우 재발행하지 않고 다음 내용 변경에 합친다. 기존 페이지를 갱신할 때는 파일 경로·URL·favicon 식별자를 유지한다.
