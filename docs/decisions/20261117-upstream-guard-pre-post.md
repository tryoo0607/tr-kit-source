# 원문 보호 검사의 대상과 사전·사후 연결

## 상태와 근거

2026-11-17 사용자는 사전 검사·실제 결과 검사 조합과 적용 대상 우선 판별에 동의하고, 제시한 유지·제거·수정 계획대로 구현·반복 검수 진행을 승인했다. 격리·OS 쓰기 통제는 제외한다. 이번 작업은 scratch의 자체 코드·합성 시험이며 운영 설치·활성화·배포와 기존 skill 이관은 포함하지 않는다.

이전 90개 시험과 감사는 [이전 설계 기록](20261117-upstream-guard.md)에 남긴다. 현재 구현의 시험·감사 상태는 [검증 요약](../verification.md)에서 별도로 확인한다.

## 채택한 기준

- 공식 설치본 참조·호출과 kit 구성요소로 원문을 복제·동봉하거나 원문·사본을 변형하는 행위를 구분한다. 후자의 금지는 유지한다.
- 먼저 적용 대상을 판별한다. 확인 가능한 원본 변경·kit 쓰기·명시 복사는 사전 검사한다. 대상 변경의 필수 검사 실패와 확인된 위반은 구분해서 해당 변경을 보류한다.
- 일반 shell·MCP의 효과를 해석하지 못한다는 이유만으로 일괄 차단하지 않는다. `deferred`는 사전 미검사이며 안전 확인·실행 승인도 아니다.
- 조각·유사성에 따른 자동 차단·보류는 제거했다. 이번 구현에 보조 유사성 검사도 추가하지 않는다.
- 등록 원문 전체와 같은 bytes 또는 그 전체가 후보에 포함된 관측만 내용 일치로 차단한다. 이 관측을 행위·저작자·출처의 증명으로 확대하지 않는다. no-match도 미등록 원문·재서술의 적법성 인증이 아니다.
- 사후 검사는 이미 실행된 효과를 막거나 복구하지 않는다. 실제 현재 파일의 검사와 조립·전송 직전의 새 필수 검사를 구분한다.
- 기존 승인 범위는 재승인 없이 진행한다. 추가 범위만 정리·보고 후 확인하며 기존 비밀·역할·제품 권한 검사를 대체하지 않는다.

## 대상 선언과 식별

catalog는 명시적으로 선택한 공식 파일의 canonical 경로·SHA256·길이만 보관한다. format 2이며 원문·유사성 metadata를 동봉하지 않는다. 기존 format 1을 자동 변환하거나 변경된 원문을 자동 재등록하지 않는다. 원본은 보호 kit 밖에 있어야 하고 현재 bytes와 pin이 다르면 검사를 완료하지 못한다.

검사 scope는 다음 형태의 명시 JSON이다. 예시는 설정 형식이며 실호스트에 등록한 값이 아니다.

```json
{"version":1,"components":["common/base","adapters","scripts"],"artifacts":["/absolute/expanded-output"]}
```

- components는 kit root 상대 경로 1~64개, artifacts는 절대 경로의 확장된 산출물 디렉토리 0~64개다. 파일명·Gitignore·untracked 여부로 자동 제외하지 않는다.
- 실제 구성·조립 입력에서 목록을 만들고 누락 여부를 확인하는 책임은 호출 측에 있다. scanner는 목록의 완전성을 증명하지 않는다.
- Pre는 선언한 파일 참조의 실제 변경 대상을 함께 판별하지만, 참조 대상이 곧 배포물의 승인된 원본으로 등록됐다고 보지는 않는다. 실제 포함 검사에서 등록 밖 참조를 불완전으로 처리하는 기준은 유지한다.
- 공식 파일로의 symlink는 원문 동봉과 구별되는 참조로 기록한다. 등록 밖으로 나가는 참조와 디렉토리 symlink는 불완전 검사로 처리한다. symlink 자체 제거와 원본 referent 삭제도 구분한다.
- 한 파일 1MB, 등록 원문 합계 1MB/256개, 실제 목록 4096노드/16MB 상한이다. 상한 초과·특수 파일·인식한 압축 형식은 검사 불가이며 통과로 바꾸지 않는다. 범용 압축·인코딩 해석기는 아니다.
- 구성 내부와 산출물 루트 자체의 디렉토리 symlink를 검사 불가로 처리한다. 경로 조상은 canonical 위치로 정규화하며 모든 조상 링크의 이력을 검사하는 정책은 아니다.

## 이벤트와 실패 처리

| 시점 | 현재 책임 |
| --- | --- |
| PreToolUse | 구조화된 파일 변경·등록 원본 변경·지원하는 명시 복사를 검사. block/unavailable만 deny, 불명확한 일반 실행은 deferred 안내. allow를 반환하지 않음 |
| PostToolUse | 알려진 읽기 전용 도구는 제외. 그 외 호출 뒤 선언된 현재 구성과 존재하는 산출물·원본 pin 검사. 실패·위반은 추가 문맥으로 보고하며 이미 실행된 효과를 취소하지 않음 |
| Claude PostToolUseFailure | 실패한 실행이 일부 변경을 남기는 경우도 동일한 실제 파일 검사에 연결 |
| assembly gate | 모든 선언 구성 입력을 새로 검사. 실패 시 exit 2이며 호출자는 조립을 진행하지 않아야 함 |
| transfer gate | 구성과 선언한 실제 산출물 디렉토리 전체를 새로 검사. 산출물 미선언·부재·불완전이면 exit 2이며 호출자는 전송을 진행하지 않아야 함 |

정상 Post는 `{}`로 추가 문맥을 넣지 않는다. 실패 Post의 안내는 상태·미완료를 알리며 대화 원문이나 원 실행 명령을 저장하지 않는다. Pre 실행기 시작 실패·timeout·잘못된 응답은 exit 2, Post의 같은 실패는 검사 불가 안내다. 두 이벤트의 의미를 섞지 않는다.

Write/Edit는 두 adapter에서 공통 후보 검사로 연결한다. MultiEdit/NotebookEdit는 알려진 구조화 변경 이름으로 대상 경로부터 확인한다. 등록 원본이면 차단, 대상 밖이면 비대상 판정, kit 대상이면 후보 재구성 미지원으로 unavailable을 반환한다. 이 도구들의 후보 재구성 지원이나 실제 제품 payload 검증 완료를 주장하지 않는다. 일반 shell/MCP의 deferred와 구분한다.

## 실제 파일 검사와 후속 연결

- catalog 지문은 실제 해석한 동일 bytes에서 만든다. 두 번의 새 파일 목록·내용 지문을 비교하고 읽는 중 관측한 변경, 선언·원본 pin 변경을 검사 불가로 처리한다. 원자적 OS snapshot이나 과거 모든 순간의 무변경 증명은 아니다.
- 결과에는 phase, 실제 대상, 목록·내용·선언 지문과 누락 산출물을 연결한다. 원문 내용·명령·대화는 결과에 넣지 않는다.
- 과거 통과 영수증이나 callback 성공을 재사용하지 않는다. Post가 없거나 실패해도 조립·전송의 새 전체 검사가 필수다. 정상 현재 상태를 새로 확인하면 과거 검사 실패를 계속 누적하지 않는다.
- Git diff로 ignored·untracked 파일을 누락하지 않는다. 여러 세션의 변경을 특정 호출의 행위로 단정하지 않는다.
- 검사 CLI는 자체 조립·전송기를 구현하지 않는다. 현재 시험용 호출자에서 실패 시 다음 단계 미실행을 검증했다. **새 kit의 실제 조립·전송 진입점은 아직 없으므로 운영 전송 전체에 필수 gate가 연결됐다고 판단하지 않는다.** 불투명한 명령 안의 직접 전송은 Post보다 먼저 실행될 수 있다.

## 현재 물리적 배치

```text
common/base/scripts/
├── upstream_guard.py
├── upstream_artifacts.py
└── run_upstream_guard.sh
adapters/
├── codex/
│   ├── scripts/upstream_guard.py
│   └── hooks/upstream-guard.json.in
└── claude/
    ├── scripts/upstream_guard.py
    └── hooks/upstream-guard.json.in
scripts/
├── upstream-catalog.py
├── render-upstream-hook.py
└── check-upstream-artifacts.py
tests/
├── test_upstream_guard.py
└── test_upstream_lifecycle.py
```

## 실행 흐름

```text
Pre 입력 → 실행기 → 제품 adapter → 공통 대상·후보 검사 → 이벤트별 응답
실행 후 Post 입력 → 실행기 → adapter → 공통 현재 파일 검사 → 문제만 안내
조립/전송 호출자 → 새 gate 검사 → 성공일 때만 해당 후속 작업
```

등록 renderer는 제품·root·catalog·scope를 명시 입력받아 이벤트별 JSON을 stdout에 출력할 뿐 설치하지 않는다. 실행기 인자는 PRODUCT ROOT CATALOG SCOPE EVENT의 5개다. Codex Pre matcher는 Bash|exec_command|apply_patch|Write|Edit|MultiEdit|NotebookEdit, Claude는 Bash|Write|Edit|MultiEdit|NotebookEdit이며 Post는 전체 matcher 후 내부 읽기 전용 분기를 적용한다.

## 검증 경계와 후속

직접 시험·합성 payload, 독립 모델의 정적 감사, 제품 native callback·신뢰·차단·조합은 서로 다른 증거다. 실제 제품 연결 실험은 후순위다. template는 비활성이며 설치본·trust DB·역할·운영 hook을 변경하지 않는다.

공식 반환 계약 참고: [Codex hooks](https://learn.chatgpt.com/docs/hooks), [Claude hooks](https://code.claude.com/docs/en/hooks). 문서 계약 확인은 native 효과의 실행 증거가 아니다. Claude template의 Pre onFailure:block은 지원 버전 확인이 별도로 필요하다.

남은 한계: 미등록 원문·부분 복제·재서술·가려진 실행/전송·선언 누락·정책/코드 변조·경합을 전부 통제하지 않는다. 격리/OS 쓰기 통제는 사용자와 정한 이번 범위에 포함하지 않는다. 이 구현으로 wrapping 금지 전체가 기계적으로 보장된다고 보고하지 않는다.
