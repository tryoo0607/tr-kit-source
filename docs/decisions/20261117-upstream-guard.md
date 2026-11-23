# 외부 원문 보호 hook 초안

> 상태 구분: 이 문서는 90개 시험을 수행한 이전 구현의 설계·한계 기록이다. 후속 대화에서 채택한 사전·사후 검사 방향과 현재 수정 제안은 [대상·사전·사후 연결](20261117-upstream-guard-pre-post.md)에 둔다. 특히 아래 유사성 자동 보류·미지원 명령 보류는 현재 코드의 과거 설계이며 최신 채택 방향으로 재사용하지 않는다. 후속 scratch 코드는 새 사전·사후 설계로 변경됐으며 이 문서의 과거 판정을 현재 동작으로 재사용하지 않는다.

## 근거와 이번 범위

2026-11-17 사용자는 기록한 합의에 따라 scratch에서 보호 hook의 설계·작성·반복 검사·감사 진행을 요청했다. 원칙 근거는 기존 `_bmad-output/kit-principles-discussion-20261113.md`의 5절 wrapping과 6~11절 적용 범위·hook 저작 기준이다. 해당 원문 정본을 옮기거나 대체하지 않는다.

이번 구현은 아래 판단을 구체화한 작성자 초안이다. 운영 설치·활성화, 기존 hook 변경, 실제 외부 원본 등록이나 private 기능 이관의 완료·승인으로 확대하지 않는다.

## 정의·범위·허용·경계·미결

| 항목 | 이번 구현 |
| --- | --- |
| 정의 | 명시적으로 등록한 외부 원본의 fingerprint·경로와, 예정 파일 내용·대상을 대조하는 프로젝트용 검사 |
| 범위 | 호출에 명시한 kit root 및 그 kit에 등록한 원본 파일. 다른 사용자 프로젝트에 전역으로 켜는 규칙이 아님 |
| 허용 | 자체 내용에서 등록 원본과의 충돌이 없으면 이 검사에서 결정하지 않음. 공식 설치본 Read는 비대상. 제품 권한·역할·다른 보안 검사는 별도 유지 |
| 경계 | 원문 전체 복제·동봉과 등록 원본 수정은 차단. 정규화·조각 흔적은 검사 불가로 보류. 일반 작업 승인이 원칙 해제·검사 우회를 허용하지 않음 |
| 미결 | 등록하지 않은 원본과 임의 재서술의 출처, 지원하지 않는 shell의 효과, 실제 제품 이벤트·trust·조합·호출 경로 완전성 |

## 책임과 식별

- 공통 검사: `common/base/scripts/upstream_guard.py`. 경로 canonicalize, 등록 파일과 pin 검증, 복제·조각 대조, 결과 우선순위·제품을 바꾸지 않는 최소 응답 계약.
- 제품 adapter: `adapters/<product>/scripts/upstream_guard.py`. Codex의 patch·도구 cwd, Claude의 Write/Edit/Bash를 각각 처리한다. 예측 patch를 실제로 실행하거나 원본 파일을 수정하지 않는다.
- 공통 실행기: `common/base/scripts/run_upstream_guard.sh`. Linux의 `/usr/bin/python3`, GNU `/usr/bin/timeout`을 사용한다. child 시작 실패·오류·2초 deadline, 응답 검증의 1초 deadline에서 exit 2로 종료한다. 출력은 검증 후 다시 직렬화한다.
- 등록 초안: `adapters/<product>/hooks/upstream-guard.json.in`. 실제 제품이 읽는 설정 파일이 아니며 `@@SHELL_COMMAND@@` placeholder가 남아 있다. template의 `.*`를 사용자 전역 등록으로 사용하지 않는다.
- 등록 renderer: `scripts/render-upstream-hook.py`. 명시 경로에서 argv를 만들고 shell 인자 인용과 JSON 직렬화를 분리한다. template의 검토하지 않은 추가 이벤트·필드를 자동 수용하지 않는다. 결과를 stdout에 반환하며 실제 제품 설정·trust·활성화는 변경하지 않는다.
- catalog 작성: `scripts/upstream-catalog.py`. 명시한 파일만 읽고 새로운 파일에 hash·길이·원본 위치를 기록한다. 자동 host 탐색·원문 저장·기존 catalog 덮어쓰기·hook 등록은 하지 않는다. 실제 경로가 포함되므로 실제 host catalog는 로컬 설정으로 관리해야 한다.

## 검사와 실패 계약

| 입력·결과 | 처리 |
| --- | --- |
| 등록 파일 전체의 byte 일치 또는 64byte 이상인 전체 원문을 후보 안에 포함 | 위반 확인·차단 |
| token 정규화 전체 일치, 연속 16token 또는 8token 이상인 원문 한 줄 일치 | 출처·변형 여부를 확정하지 않고 검사 불가·보류. 유사한 자체 문장이 보류될 수 있음 |
| 일치 없음 | 등록 corpus 대조에서 pass. 독창성·모든 출처·요구 의미 전체를 인증하는 결과가 아님 |
| 정책 부재·잘못된 값·원본 pin 변경·비정규 파일·범위/크기 한도·지원하지 않는 입력 | 검사 불가·보류. 자동 재시도·우회·필수 검사의 알림 전환 없음 |
| conclusively 다른 대상의 파일 쓰기·직접 cp | 비대상. catalog 검증이 불가능하면 등록 원본 수정 여부도 판단할 수 없어 보류될 수 있음 |

catalog는 최대 256개 명시 파일, 파일·합산 원본·입력은 각각 1,000,000byte 한도다. 원문은 외부 도구 설치본에 남고 catalog에는 fingerprint·경로·길이를 저장한다. 바이너리의 전체 byte 복제도 검사하지만 변형 바이너리와 짧은 부분 복제의 완전 탐지는 지원하지 않는다.

Claude Edit는 기존 파일의 변경 후 전체 내용을 대조한다. Codex patch는 Add·유일하게 고정되는 문맥의 Update·Move·Delete를 지원하며, labelled/모호한 hunk, 중복·충돌 경로, LF 외 줄 구분·끝나지 않은 기존 줄은 임의 예측하지 않는다. Update의 출발지와 Move 목적지를 범위 판정 전에 공통 원본 식별에 대조한다. 현재 shell 지원은 단순한 `cp SOURCE TARGET`과 `pwd`뿐이다. 제어문자·tilde·glob 등 지원하지 않는 입력은 인용 여부를 임의로 해석하지 않고 보류한다. 일반 Python·빌드·테스트·복합 shell·미지원 MCP도 보류되므로 현재 template를 활성화하면 일상 개발에 큰 간섭이 생긴다. 이 한계를 피하려고 알 수 없는 동작을 자동 허용하는 예외를 넣지 않았다.

root 밖의 기존 파일이 여러 hard link를 가지면 kit 파일의 별칭인지 확정할 수 없어 보류한다. 전수 파일 색인을 자동 생성해 범위를 추측하지 않는다. 등록 경로 자체의 삭제는 차단하지만, 별도 hard link를 제거하는 것은 다른 등록 경로의 원문 내용을 삭제하는 행위와 같지 않다. 내용 동봉이 아닌 삭제의 일반 승인 여부는 다른 권한 검사에 맡기며 이 hook이 허용하지 않는다.

실제 효과를 제품 입력에서 예측하는 보조 검사다. canonical 경로·현재 hard link는 확인하지만 경로·파일·환경의 동시 변경, code-mode의 실제 callback과 기존 실행 세션 등 모든 우회 경로를 통제하는 OS 경계가 아니다. 에이전트가 수정 가능한 code·catalog만으로 변조 불가능하다고 주장하지 않는다.

## 제품 계약 근거와 검증 경계

- [Codex 공식 hooks 문서](https://learn.chatgpt.com/docs/hooks): 도구별 PreToolUse 입력, deny 또는 exit 2 차단, trust 필요와 일부 hook 경로 제외를 확인했다. 현재 문서가 로컬 0.167.2에서 모두 동일함을 실행 증명한 것은 아니다.
- [Claude 공식 hooks 문서](https://code.claude.com/docs/en/hooks): Write/Edit 입력과 deny, exit 2, 병렬 hook을 확인했다. template의 `onFailure: block`은 문서상 2.1.295 이상 조건이며 이 호스트의 Claude native 시험은 수행하지 않았다.
- pass·비대상은 `{}`를 반환하고 `allow`로 다른 권한을 대신하지 않는다. 기존 비밀·전송 검사를 복제하지 않으며, 다른 hook의 선행 처리·마스킹 결과에 의존하지 않는다. 실제 함께 활성화된 조합은 미검증이다.
- 실행기 child 실패를 exit 2로 바꾸는 것과 제품이 신뢰하지 않은 hook을 건너뛰는 상황, 실행기 자체의 시작 실패·제품 timeout·경로 제외를 구분한다. 후자를 보완했다고 보고하지 않는다.

## 검수 판단

구현·반복 시험·감사 결과는 [verification.md](../verification.md)에 연결한다. 현재 운영 적합 판단은 보류한다. 특히 일반 shell 간섭과 native·trust·조합 검증을 해결하지 않고 ‘요구 전체를 강제하는 보호 장치’로 활성화하면 안 된다. 원칙을 낮추거나 독단적으로 미지원 입력을 허용하는 대신, 후속 범위·연결 설계에서 해결해야 한다.
