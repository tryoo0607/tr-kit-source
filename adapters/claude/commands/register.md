---
description: 이 세션의 응답 레지스터를 바꾼다 (default · brief · deep)
argument-hint: "default | brief | deep"
---

이 세션의 **응답 레지스터**를 `$ARGUMENTS` 로 바꾼다.

```sh
key="$(tmux display-message -p '#S' 2>/dev/null || echo default)"
d="${XDG_STATE_HOME:-$HOME/.local/state}/claude-remote/register"
mkdir -p "$d" && printf '%s' "$ARGUMENTS" > "$d/$key"
```

| 값 | 무엇 |
|---|---|
| `default` | 지금 것 — 단계 블록 · 알림 · 첨언 · 여백 전문 |
| `brief` | 표·결론 중심. 근거는 요청 시. **알림·첨언 블록은 유지** |
| `deep` | default + 근거·대안·번복 명시·미검증 분리 |

🔑 **세션별로 갈린다.** 키가 tmux 세션 이름이라 한 세션은 `brief`, 다른 세션은 `deep` 이 된다.
`/clear` 를 넘어 유지된다 — `session-end` 와 같은 키 규약이다.

## 인라인 `==tldr==` — 슬래시 없이

프롬프트 안에 **인라인 디렉티브**로도 된다(`inject-state.sh` 가 잡는다). 구분자(감싸개)는 `==` `--` 둘 다.

| 인라인 디렉티브 | 무엇 |
|---|---|
| `==tldr==` | **이 턴만** brief (세션 register 안 바꿈) |
| `==tldr on==` | 이 세션 register=`brief` (지속) |
| `==tldr off==` | 해제(`default`) |

🔑 **코드펜스·인라인 코드 안, 첫 줄이 아닌 곳은 무시** — 붙여넣은 코드 속 `--tldr--` 는 안 터진다.

### 형제 인라인 디렉티브 (register 와 직교)

`tldr` 는 **간결도**를 바꾸지만, 아래 둘은 **자세**를 바꾼다 — 같은 감싸개·같은 오탐방어, 각각 맨몸=이 턴 / `on`·`off`=지속.

| 인라인 디렉티브 | 무엇 | 별칭 |
|---|---|---|
| `==chat==` | **논의-우선** — 바로 편집·실행 말고 선택지 먼저 | `==논의==` |
| `==asap==` | **즉답** — 물어본 것만, 사족·격식 제거 | `==즉답==` |

**세 축은 독립**이다 — `tldr`(요약) · `chat`(논의) · `asap`(직답). 인라인 디렉티브를 새로 만들 땐 `kit/references/authoring.md` 참고.

값이 셋 중 하나가 아니면 훅이 **조용히 `default` 로 되돌린다.** 바꾼 뒤엔 유저에게 어느 레지스터가 됐는지 한 줄로 알린다.
