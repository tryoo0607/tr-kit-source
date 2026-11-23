# Private native 연결을 위한 공통 패키지 인터페이스

## 요청과 범위

사용자가 앞서 남긴 private native 패키징·설치본 연결을 다음 작업으로 진행하도록 요청했다. scratch 공통/개인 source와 자체 생성물, 새 격리 prefix가 대상이다. 운영 설치·권한 확대·기존 호스트 설정·인증 복사·자료 수집·원격 배포는 하지 않았다. BMAD 자동 갱신404는 앞서 보류한 그대로다.

## 공통 변경

- `scripts/package.py`의 기존 공통 hook 작성은 유지하고, 자체 native envelope 생성을 `wrap_native_files`로 분리했다. 공통은 개인 패키지 이름·기능을 알 필요가 없다. 다른 kit은 자기 identity/hooks/요구를 전달한다.
- 실제 manager가 설치하는 payload 안에 `installation.json`을 생성한다. 제품·이름·버전·profile과 그 파일 자체를 제외한 전체 파일 명세를 담는다. 자기 서명이나 공식 출처 인증을 뜻하지 않는다.
- `scripts/assemble.py`는 승인된 자체 작성 코드가 renderer callback을 전달할 수 있다. JSON 설정이나 외부 plugin을 자동 실행하는 기능은 아니다. 기존 fresh source/산출물 검사·범위 확인·비밀 검사·변경 감지는 그대로 수행한다.
- `scripts/plugin-lifecycle.py`는 caller가 명시한 identity를 검증해 기존 설치/갱신/복귀/제거를 재사용한다. 기본 공통 identity는 유지하며 private 진입점은 자기 이름을 고정한다. 새 격리 prefix 요구·plan hash·CLI/package 재검사·partial 보존·data 유지·신뢰 승인 분리는 유지한다.

Source 배치와 native 생성물의 위치를 구분한다.

```text
공통 source/scripts/
├─ assemble.py             수정: 자체 renderer 연결
├─ package.py              수정: envelope·payload 명세
└─ plugin-lifecycle.py     수정: 명시 identity·제거 확인

각 native plugin payload/
├─ installation.json       생성: payload 전체 명세
├─ .codex-plugin/ 또는 .claude-plugin/
├─ hooks/hooks.json
└─ common/base/ 및 scripts/
```

## Private와의 연결

개인 구현 정본은 별도 scratch tr-kit-private의 common_links/private_runtime/native-context와 scripts/package-private.py·plugin-lifecycle.py, docs/decisions/20261120-native-private.md다. 공통 코드를 복사하지 않고 검증한 공통 implementation을 호출한다.

기존 source-bundle-v1 pin은 남기고 별도 native plugin-payload-v1 pin을 제품별로 추가했다. `kit.common_format=source|native`를 명시하며 기존 기본값은 source다. 형식 자동 탐색·다른 버전으로 대체·metadata 존재만으로 통과는 허용하지 않는다. pin·현재 전체 bytes·추가 파일·심볼릭 링크·제품/identity/profile을 대조한 뒤 공통 코드를 로드한다.

```text
개인 명시 설정 → 형식별 common 검증 → 공통 구현 호출
private 작성/설치 진입점 → 검증한 공통 조립·수명 관리 구현
SessionStart → 검증한 common context 함수(private 지침 읽기)
             → 기존 private 역할 안내 → 제품 context
```

공식 제품의 패키징/관리자/입력·출력 계약을 재사용한다. [Claude dependency 기능](https://code.claude.com/docs/en/plugins/dependencies)은 설치·활성/버전 제약을 관리하지만 파일별 pin을 대신하지 않으며 자동 의존 설치 효과가 있다. 이번 연결은 별도 설치를 명시하고 이를 자동 설치 기능으로 바꾸지 않았다.

## Native에서 확인한 차이와 보완

Codex0.167.2와 Claude Code2.1.329의 공식 manager로 공통·private를 같은 제품 설정에 설치했다. 두 제품 모두 개인9개 skill을 실제 발견했다. 공통 지침·개인 지침·역할 안내가 전달됐고 큰 지침 본문은 각각1회였음을 실제 요청에서 확인했다. 토큰 비용 측정은 아니다. Codex10개 hook은 native UI로 개별 검토·승인했다. trust DB 편집·우회 옵션은 사용하지 않았다.

Claude의 local marketplace 실행 root는 cache가 아닌 release 폴더였다. 실제 init metadata/context의 경로와 검증한 payload bytes를 대조했으며 cache 파일 일치를 실행 경로 증거로 대신하지 않았다.

공통 연결 실패에서 Codex는 모델 요청 전 turn을 멈췄다. Claude는 [공식 SessionStart 계약](https://code.claude.com/docs/en/hooks#sessionstart-decision-control)이 context-only이며 실제로도 세션 전체를 막지 않았다. private 시작 실패에 사용자 warning과 모델 context를 추가해 준비 실패·private 작업 보류를 전달했다. 실제 공통 의존 호출의 pin 거부와 이 자연어 안내를 구분하며, 전체 private 실행을 기계적으로 차단하는 장치로 주장하지 않는다.

## 제거 확인 보완

최초 Claude 제거 명령2개는 성공했고 실제 설치 목록에서도 private가 사라졌지만, 이전 버전 cache 때문에 기존 검사기가 partial을 남겼다. 이를 보존했고 같은 partial 동작을 자동 재전송하지 않았다.

cache 존재는 등록 상태를 증명하지 않으므로 제거 후 `plugin list --json`을 읽어 대상 id 부재를 검증하도록 보완했다. plan에 이 확인 명령도 표시한다. query 실패·알 수 없는 JSON·대상 잔존은 여전히 실패다. 보존 cache는 `cache_retained`로 따로 보고하며 강제 삭제하지 않는다. [공식 Claude uninstall](https://code.claude.com/docs/en/plugins/cli-reference#plugin-uninstall)의 data 보존도 유지한다. 등록 해제가 기존 세션 맥락·데이터·모든 cache 삭제를 뜻하지 않는다.

새 prefix에서 최종 패키지로 설치·제거를 다시 시험해 양 제품 모두 removed와 공통 보존을 확인했다. Codex는 cache 미잔존, Claude는 cache 보존이었다. 앞선 버전 간 갱신·rollback도 실제 manager에서 확인했다.

## 검증과 현재 산출물

아래 source 수는 `assembly.json`을 제외한 inventory 파일 수이며, native 수는 `assembly.json`을 포함한 marketplace 전체 파일 수다.

- 공통 전체516개·private115개 시험 성공. 공통은 명시한 실제 Gitleaks를 포함했고 생략은 없다. Native 등록/metadata/admission/미검증 코드 실행 방지·설정 변경·제거 확인을 검사했다.
- 공통은 제품별150파일 source/155파일 native, private는53파일 source/58파일 native다. 원문 보호·비밀 검사·실제 파일 명세를 대조했고 공통 구현/scanner는 private payload에 없다. 역할 정책 hash는95c375…8d21로 유지된다.
- Native callback18사례: 양 제품의 정상2·입력/복제 차단4, source 연결1, 합성 비밀 출력 대체1, 공통 부재1. 합성 API 응답이므로 실제 모델 행동과 구분한다.
- 실제 Codex 새 세션에서 명시한 개편본 skill로 native document 연결과 공통 부재 보류를 확인했다. 기본 loader만 검사한 경우 전체 doctor를 실행했다고 세지 않는다. Claude 실제 모델·자연 발동·압축/재개·MCP native 등록·실자료·운영 배포는 남아 있다.

Callback 시험 pair 이후 제거 확인만 보완했다. 그 코드와 distribution 안내가 바뀌어 common/private pin을 다시 계산했다. 최종 pair의 직접 context·실제 설치/제거와 전체 회귀를 별도 확인했으며, 변경되지 않은 hook/context 구현의 앞선 native 증거와 구분한다. 동일 작성자의 kit/hook/연결 감사이며 독립 전문 감사나 전체 운영 적합 판정은 아니다.

최종 pair는 `/data/projects/_scratch/tr-kit-private-native-validation-20261120/`의 common-final-{source,native}-<product>, private-paired-{source,native}-<product>다. 공통516개 log는 `_bmad-output/private-native-20261120/common-ci-final/`, private115개·원래 실패/수정 전 callback·최종 callback18개·native inventory·수명 관리·새 모델 기록은 위 격리 경로에 보존했다. 개인 설정과 상세 입력/출력은 배포물에 포함하지 않는다.

## 추가 검증: 실제 Claude의 시작 실패 응답

사용자가 세션 전체 차단보다 연결 실패를 알리고 private 작업의 확인을 요청하는 응답이면 충분하다고 설명한 뒤, 권장한 정상·실패 비교 시험을 요청했다. 위의 실제 Claude 모델 미실행 항목 중 이 좁은 응답 범위만 후속 확인했다. 구현·pin·패키지·역할 정책은 변경하지 않았다.

dev01 Claude에는 인증이 없어, 기존 session/Orca 연결로 inno-desktop의 로그인된 Claude Code2.1.327을 사용했다. 인증을 복사하지 않았고 운영 plugin manager 등록·설정을 변경하지 않았다. `--plugin-dir`로 검증한 common/private payload를 임시 경로에서 로드하고 전체207파일 bytes를 전후 대조했다. 앞선 합성 시험의2.1.329와 이번 실제 제품 버전을 구분한다. 실제 응답 metadata의 모델은 `claude-opus-5-5`다.

동일한 중립 질문을 서로 독립적인 새 세션2개에 전달했다. 정상 설정은 명시 native common root, 실패 설정은 존재하지 않는 common root를 가리킨다. 추가 도구 실행 없이 시작 안내를 바탕으로 진행 가능 여부·확인 사항을 답하도록 했으며, 정답이나 기존 결론을 프롬프트에 넣지 않았다. 공식 restricted 모드·빈 도구 목록·빈 명시 MCP 설정을 사용했고 hook을 끄거나 권한을 우회하지 않았다. 자체 두 plugin 외 제품 builtin plugin도 로드됐다.

| 사례 | 실제 관측·판정 |
| --- | --- |
| 정상 연결 | 두 SessionStart 응답 성공. 공통/개인 지침과 development 역할을 인지하고 자료·범위·가드 실행 결과는 미확인으로 구분. 준비 완료 전체를 주장하지 않음 |
| 공통 연결 실패 | 자체 hook이 not ready 안내를 출력. 실제 모델이 private 작업을 진행할 수 없는 상태라고 답하고 선택 설정·공통 pin·역할 확인과 새 세션 재확인을 제시. 다른 설치본·고정 가드로 우회하지 않겠다는 응답 확인 |
| 별도 발견 | 실패 답변에 “사용자 쪽 설정 문제일 가능성이 높다”는 근거 없는 가능성 추정이 붙음. 추론 표시가 있어도 근거 충족으로 판정하지 않음. 두 답변 모두 요청보다 장황함. 아직 교정하지 않음 |

각 조건1회이며 두 세션 모두 정상 종료했고 도구 노출/호출은0개다. 따라서 **실패 인지·확인 요청·보류 의사 표현**의 목표를 관측한 것이며, 도구가 주어진 상황에서 실제 보류·우회 방지를 검증한 결과는 아니다. 일반적인 사실/추론 준수, 자연 발동·전체 private 업무·압축/재개·MCP 등록·운영 배포도 완료로 확대하지 않는다.

초기 터미널 입력 전송은 완료를 확인하지 못해 중단했다. 임시 Tailscale 직접 전송도 timeout으로 실패해 서버를 종료했고, 기존 Orca PTY로 전달한 파일의 hash를 확인한 뒤 모델 시험을 시작했다. 이 준비 실패는 kit/hook·모델 실패와 구분한다. 새로 만든 시험 terminal3개는 모두 종료·PTY 중단을 확인했다.

로컬 상세 증거는 위 검증 경로의 `claude-real-startup-model/`에 있다. `assessment.json`에 판정·한계, `remote-evidence/`에 실제 hook/모델 출력과 동일 질문, 실패 입력과 정상 입력을 구분해 보존했다. 원격 임시 fixture와 로그는 inno-desktop의 승인한 scratch 경로에만 남겼다. 코드 변경이 없어 기존516/115개 회귀·조립을 재실행한 것으로 세지 않는다.
