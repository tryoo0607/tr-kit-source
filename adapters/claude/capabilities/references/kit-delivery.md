# Claude kit delivery

## 두 채널

| 채널 | 내용 | 반영 |
|---|---|---|
| plugin cache | skills·commands·hooks | marketplace refetch → plugin update → 세션 재시작 |
| 셸 설치본 | `setup/bin`·설정 seed/복사본 | `setup/tools/install.sh` |

한 기능이 양쪽에 걸리면 둘 다 확인한다. 한쪽만 갱신해도 오류 없이 옛 동작이 남을 수 있다.

## 점검 순서

1. target repo와 생성물 diff를 확인한다.
2. `tools/kit-doctor`가 있는 배포 repo에서는 bin 링크·PATH·설정 복사본·plugin cache commit을 확인한다.
3. 셸 채널 변경은 `setup/tools/install.sh`의 변경 범위를 보고한다.
4. plugin 변경은 manifest version과 marketplace source를 확인한다.
5. 실제 설치·재시작 전에 사용자 승인을 받는다.

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

## 셸 설치본

- 심링크는 repo를 따라가지만 복사된 config는 자동 추종하지 않는다.
- 사용자 소유 alias·permission은 자동 덮어쓰지 않는다.
- `install.sh --force`는 변경 대상을 확인하고 명시 승인 후에만 사용한다.
- `sessions.log` 같은 세션 데이터는 seed로 덮어쓰지 않는다.

## 설명서 발행

설명서의 수치가 generator 산출이면 손으로 고치지 않는다. 본문 변화 없이 version·개수만 달라진 경우 재발행하지 않고 다음 내용 변경에 합친다. 기존 페이지를 갱신할 때는 파일 경로·URL·favicon 식별자를 유지한다.
