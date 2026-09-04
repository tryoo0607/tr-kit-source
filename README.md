# tr-kit-source

[![build](https://github.com/tryoo0607/tr-kit-source/actions/workflows/build.yml/badge.svg)](https://github.com/tryoo0607/tr-kit-source/actions/workflows/build.yml)
[![release](https://img.shields.io/github/v/release/tryoo0607/tr-kit-source)](https://github.com/tryoo0607/tr-kit-source/releases/latest)

Claude Code와 Codex용 개발 워크플로 kit를 하나의 공통 소스에서 정적으로 조립하고 배포한다.

- **공통 관리**: 업무 의미와 판단은 한 번만 정의한다.
- **target 분리**: 제품별 형식과 기능 연결만 adapter에 둔다.
- **정적 산출**: build가 target이 고정된 완성 저장소를 만든다.

## 한눈에 보기

```mermaid
%%{init: {"flowchart": {"curve": "linear", "nodeSpacing": 42}}}%%
flowchart LR
    Core["공통 Core + Contracts<br/>의미 · 정책 · capability 정의"]
    Adapter["Target Adapter<br/>Claude/Codex별 기능 구현"]
    Recipe["Recipe<br/>조합 대상 · 산출 경로 선택"]
    Build["Build<br/>계약 검증 · 정적 합성"]
    Output["완성 Target 저장소<br/>tr-claude · tr-codex"]

    Core --> Adapter --> Recipe --> Build --> Output
```

- **관계**: core와 adapter는 별도 제품이 아니라 `tr-kit-source` 안의 정적 조립 입력이다.
- **선택 시점**: recipe가 build 시점에 공통 정본과 target adapter를 결합한다.
- **runtime**: 설치 후에는 adapter 탐색, target 선택, source 재조립을 하지 않는다.

## 디렉터리 책임

| 경로 | 맡는 것 | 맡지 않는 것 |
|---|---|---|
| `core/` | 공통 lifecycle·profile 엔진, capability 계약, 조합이 필요한 공통 skill | Claude/Codex raw payload와 제품별 출력 형식 |
| `shared/` | 두 target에 동일하게 들어가는 정책·백본·공통 runtime | target별 분기 |
| `skills/` | target 차이 없이 그대로 배포할 완성형 공통 skill | capability fragment 조립 |
| `adapters/<target>/` | hook 입출력, manifest, capability fragment 등 target 전용 수단 | 공통 업무 의미와 판단 규칙 |
| `recipes/` | 공통 소스와 target adapter를 어떤 경로로 조립할지 정의하는 실행 계획 | 업무 규칙 본문 |
| `glossary/` | `AGENTS.md`·`CLAUDE.md`처럼 의미가 같은 target별 명칭 값 | 행동이 다른 기능 분기 |
| `packaging/<target>/` | 배포 저장소 root의 marketplace metadata와 README | plugin payload 내부 구현 |
| `agents-doc/` | target 이름으로 변환되는 공통 agent 진입 문서 | 제품별 hook 구현 |
| `tools/` | recipe 검증, 정적 합성, delivery 검증·배포 | runtime target 선택 |
| `tests/` | 조립 계약, 공개 경계, lifecycle과 delivery 회귀 | 운영 데이터 |

## 조립 방식

| 종류 | 공통 정본 | target 입력 | 결과 |
|---|---|---|---|
| 그대로 공유 | `shared/`, `skills/` | 없음 | 두 target에 동일한 파일 |
| skill capability | `core/skills/<skill>/SKILL.md` | `adapters/<target>/capabilities/` | slot이 모두 채워진 완성 `SKILL.md` |
| lifecycle hook | `core/lifecycle/decision.py` | `adapters/<target>/hooks/` | 공통 event→result 판단 + target raw payload·렌더링 |
| repository packaging | 공통 payload와 `LICENSE` | `packaging/<target>/` | 설치 가능한 완전한 저장소 tree |

- **계약의 역할**: `core/contracts/capabilities.toml`은 필수 slot과 fragment 형식만 검사하며 산출물에는 포함되지 않는다.
- **실패 조건**: source 누락, 산출 경로 충돌, 미치환 token·guard·slot이 있으면 build를 중단한다.

## 생성되는 저장소

| target | 로컬 snapshot | 공개 배포 저장소 | 릴리스 |
|---|---|---|---|
| Claude Code | `out/claude/` | [`tr-claude`](https://github.com/tryoo0607/tr-claude) | [`v0.5.3`](https://github.com/tryoo0607/tr-claude/releases/tag/v0.5.3) |
| Codex | `out/codex/` | [`tr-codex`](https://github.com/tryoo0607/tr-codex) | [`v0.5.3`](https://github.com/tryoo0607/tr-codex/releases/tag/v0.5.3) |

- **소유권**: 두 배포 저장소는 사람이 payload를 직접 관리하는 별도 source가 아니다.
- **생성 방식**: `tr-kit-source`가 repository 전체 tree를 만드는 managed-root mirror다.
- **설치 안내**: 각 배포 저장소의 README를 따른다.

## 빌드와 검증

```sh
./build.sh            # claude와 codex 모두 생성
./build.sh claude     # 하나만 생성

python3 -m unittest discover -s tests -p 'test_*.py'
bash tests/hooks/lifecycle-smoke.sh
```

원격을 수정하지 않는 target 통합 dry-run:

```sh
python3 -m tools.delivery \
  --repo claude=/path/to/tr-claude \
  --repo codex=/path/to/tr-codex
```

- **적용 위치**: 실제 작업 checkout이 아니라 깨끗한 disposable clone만 변경한다.
- **검증 항목**: repository, marker, symlink, 소유 경계와 두 번째 적용의 멱등성을 확인한다.
- **push 정책**: 변경이 있을 때만 normal fast-forward push를 수행하며 force push는 사용하지 않는다.

## recipe 계약

- 기본 빌드는 `recipes/*.toml`에서 `_`로 시작하지 않는 모든 target을 찾는다.
- `_base.toml`의 공통 artifact와 target recipe의 artifact·composition을 합친다.
- composition은 공통 문서의 `{{slot:<capability>}}`를 recipe가 선택한 adapter fragment로 채운다.
- `_schema.toml`이 허용 key·scope·generator를 정의하고 build가 이를 직접 검증한다.
- `recipes/*.yaml`처럼 지원하지 않는 recipe가 남아 조용히 무시되는 것도 실패한다.
- 공식 target은 모두 `managed-root`이며 source output이 배포 저장소 전체의 정본이다.

## 변경 이력과 기여

- [`CHANGELOG.md`](CHANGELOG.md): 모든 공개 버전을 한 파일 안의 버전별 section으로 관리한다.
- [GitHub Releases](https://github.com/tryoo0607/tr-kit-source/releases): 특정 버전의 배포 시점과 release note를 관리한다.
- [`CONTRIBUTING.md`](CONTRIBUTING.md): 변경 제안과 검증 절차.
- [`SECURITY.md`](SECURITY.md): 취약점 제보 절차.

## 라이선스

[Apache License 2.0](LICENSE)
