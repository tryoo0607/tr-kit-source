# INTEGRATIONS — 외부 통합 레지스트리

kit이 기대는 **외부 skill·플러그인·프로젝트**를 한곳에 목록화한다. "이거 어떻게 들여왔더라"를 다시 안 헤매게, **통합 모드**와 상태를 명시한다. OS/CLI 패키지 목록은 이 레지스트리의 범위가 아니다.

> **왜 필요**: odin 소프트의존이 6+ 스킬에 인라인으로 흩어져 있고 중앙 목록이 없었다. 외부를 들일 때마다 모드(소프트의존/install/포팅…)를 매번 새로 판단하던 걸 여기서 표준화·조회한다.

## 통합 모드 (닫힌 목록)
| 모드 | 뜻 | 하드의존? |
|---|---|---|
| **소프트의존** | 있으면 우선 활용, 없으면 자체 fallback (표준 문구) | ❌ |
| **install** | 마켓/패키지로 설치해 병존(`/k-skill:*` 등 네임스페이스). tr-*가 라우터로 감쌈 | ❌ |
| **포팅** | 외부 **개념/행동만** 뽑아 내 kit에 재구현 (런타임 안 가져옴) | ❌ |
| **발췌 차용** | 텍스트 자산(프롬프트·정의)을 발췌해 tr 브랜드로 재작성 (라이선스 확인) | ❌ |
| **참고만** | 설계 레퍼런스로만 봄, 코드/자산 안 들임 | ❌ |

> 규율: **하드의존·자동설치 금지**. 전부 없어도 kit이 죽지 않아야 함.

## 레지스트리

| 외부 | 무엇 | 모드 | 상태 | 어디서/근거 |
|---|---|---|---|---|
| **odin** (플러그인) | 코딩 방법론·리뷰·fix·병렬 + **test**(adversarial·purge)·**방법론 실행**(test/type/contract/proof/validation-driven) 스킬군 | 소프트의존 | ✅ 사용중 | `deps`·`review`·`test`·`ci`·`session`·`architecture` 인라인 |
| **oh-my-pi** (`can1357/oh-my-pi`) | **Advisor(Watchdog)** = 훈수/코칭(성급완료·이탈 견제, nit/concern/blocker) | 포팅 | ✅ 포팅완료 | `review`의 `references/priority.md` + 백본 `ask-n.md` 렌즈(reviewer + devil's advocate)·severity·WATCHDOG.md·온디맨드 리뷰 + 옵션 Stop hook(경량, 기본 off). 라이브 스티어링만 미채택(비용) |
| **wshobson/agents · VoltAgent · atournayre/claude-personas** | 역할 페르소나 프롬프트(architect·security·perf·reviewer·tester·devil's advocate) | 발췌 차용 | ✅ 반영 | 개념 참고해 `multi-agent/references/personas.md` **원본 작성**(복제 아님). persona 셋·advisor 공유 |
| **hex/claude-council · richiethomas/claude-devils-advocate** | 중재자 수렴·라운드상한·조기종료 패턴 | 참고만 | ✅ 반영 | `multi-agent/references/council.md` 설계 벤치마크(라운드상한+조기종료) |
| **MetaGPT · CrewAI · AutoGen** | 표준 역할셋·`max_round`·GroupChatManager 수렴 | 참고만 | 📖 참고 | persona/council 설계 레퍼런스(런타임 하드의존 X) |

> 상태: ✅ 사용중 · 🔄 도입/이식예정 · 📖 참고. 진행되면 갱신.

## 규약
- 외부를 **새로 들이면 여기 등록**(모드·상태·어디서). 새 스킬을 만들 때 `kit`의 저작 체크리스트가 확인한다.
- 각 스킬 본문의 인라인 소프트의존(표준 문구)은 유지 — 여기는 **중앙 조회·모드 관리**용(인라인과 상보).
- 이력은 git이 갖는다. 공개 release 변화만 `CHANGELOG.md`에 롤업한다.
