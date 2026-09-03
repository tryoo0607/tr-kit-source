# 환경 종속 값

**스킬 본문에 IP·경로·계정·workspace id를 박지 않는다. 공개 기본값만 두고, 사용자 값은 runtime profile이나 도메인별 private 저장소로 분리한다.**

## 왜 이 파일인가

| | |
|---|---|
| 공개 기본값 | 모든 사용자에게 같은 값만 이곳에서 설명한다 |
| 사용자 값 | runtime profile이나 domain repository가 소유한다 |
| 스킬을 읽을 때 | 실제 값이 아니라 논리 key와 절차만 보인다 |

## 규약

- 스킬은 runtime profile의 논리 key나 도메인 저장소를 **참조**한다.
- **secret은 여기 두지 않는다** — repo 밖 또는 git-crypt. 여기엔 *"어디 있는지"*만.
- 사용자 값이 바뀌면 local profile이나 domain repository만 고치고, public skill은 건드리지 않는다.

---

## 값

공개 kit 자체가 필요로 하는 플랫폼 중립 기본값만 둔다. 개인 인프라 값과 현재 상태는 이 파일의 범위가 아니다.

### `paths`

| 키 | 값 |
|---|---|
| `paths.projects` | `~/projects` |
| `paths.docs` | `~/projects/_docs/<project>` — 작업 기록 실파일 |
| `paths.assets` | `~/projects/_assets/<project>` — 대용량 원본 |
| `paths.bin` | `~/.local/bin` — kit이 심링크를 까는 곳 |

> 실제 repo 경로는 runtime profile에 두고 source에 커밋하지 않는다.
