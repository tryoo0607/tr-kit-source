# G5: 제품별 패키징·격리 설치/복귀·검사 전용 CI

## 요구와 범위

R-37. 사용자 “G5 ㄱㄱ”에 따라 scratch 공통의 자체 source 조립을 제품 native 패키징으로 연결하고 공식 manager를 이용한 설치·교체·제거·복귀 경로와 검사 전용 CI를 작성한다. 실제 시험은 별도 임시 prefix로 한정하며 기존 운영 설치본·개인 profile/자료·hook trust·worker/timer·원격 push/배포는 변경하지 않는다.

설치/검토 절차 정본은 [INSTALL](../../INSTALL.md), 구현은 기존 assemble과 새 package/plugin-lifecycle/delivery/ci-check다. source bundle interface는 유지하고 native 포장만 별도 분기로 추가한다. 배포를 위해 구 vendor 조립기를 가져오거나 외부 원문·runtime/resources를 동봉하지 않는다. Git commit이 없는 현재 source를 임의 commit SHA로 표현하지 않고 실제 source inventory hash를 기록한다.

## 실제 구조와 흐름

```text
source
  common/base
    ├─ instructions.md · skills/ · references/ · 기존 검사/연결 코드
    └─ scripts/plugin_runtime.py   초기 지침 · 명시 upstream binding relay
  adapters/{codex,claude}
    ├─ plugin.json.in             제품 native metadata/skills 경로
    └─ 기존 hooks/scripts/mcp     변경 없이 연결·검증에 재사용
  scripts
    ├─ assemble.py                기존 fresh 원문·inventory·Gitleaks 조립
    ├─ package.py                 native overlay · 현재 package 검사
    ├─ plugin-runtime.py          공통 runtime 진입
    ├─ plugin-lifecycle.py        정적 계획 · 격리 prefix의 공식 CLI 연결
    ├─ delivery.py                현재 전송 후보 검사만, push 없음
    └─ ci-check.py                scanner 명시 · 로컬 CI 동등 검사
  .github/workflows/verify.yml     PR/수동 검사만
  LICENSE · NOTICE · SECURITY.md · INSTALL.md

생성 marketplace
  제품별 marketplace.json
  plugins/tr-{product}
    ├─ 제품별 plugin.json manifest
    ├─ common/base · adapters · scripts · workflow.md (경로 유지)
    └─ hooks/hooks.json            SessionStart + 선택한 기존 guard 등록
  release.json · assembly.json     현재 파일/hash·출처 범위·미준비 상태

계획 → 실제 적용 전 필수 Gitleaks → 공식 CLI → native 캐시 byte 대조
  install → update → retained package rollback → remove/캐시 부재 대조
```

## 결정 근거와 경계

- 제품 manifest의 명시 skill 경로를 사용해 common/base의 상대 reference를 보존한다. top-level skills로 이동·복제해 참조를 깨뜨리지 않는다. Codex는 공식 문서에서 지원하는 compatibility manifest를 선택했다. marketplace·manifest는 기존 tr-codex/tr-claude identity를 유지한다.
- [Claude 공식 manifest 문서](https://code.claude.com/docs/en/plugins-reference)에 따라 plugin 루트 CLAUDE.md 파일은 자동 주입 근거로 보지 않는다. 기존 공통 지침 본문 하나를 SessionStart가 읽어 전달하고 절대 workflow 포인터를 준다. 본문을 임의 축약하거나 업무별 reference를 함께 일괄 주입하지 않는다. 실제 callback·trust·모델 수신은 별도 검증이다.
- review는 native 구조 검토용으로 초기 지침 hook만 있고 운영 보호 준비를 주장하지 않는다. guarded는 기존 secret/upstream renderer의 검증을 재사용해 병렬 검사 정의를 연결한다. 등록·정책 의미를 바꾸거나 기존 운영 가드를 review로 전환하지 않는다. binding 부재의 Pre 응답은 명시 deny다.
- 호스트별 scanner·upstream binding·공식 provider/resources와 G4 MCP 경로는 패키지의 설치 성공과 다르다. MCP template를 native 설정으로 자동 등록하거나 worker를 시작하지 않는다. source 출력에도 operational_ready=false를 유지한다.
- lifecycle은 공식 CLI로 임시 제품 설정을 관리한다. 제품 config/trust DB 편집·강제 옵션·auth 복사·데이터 삭제를 구현하지 않았다. partial 상태는 단계·로그와 함께 보존하고 같은 동작을 자동 재전송하지 않는다. 성공 후 이전 패키지 복귀와 실패 중간 상태의 수동 수습을 같은 보장으로 표시하지 않는다.
- 기존 Apache LICENSE는 유지하고 과거 skill 저작 lineage 고지를 보존했다. 새 패키지에 없는 bundled Claude-Mem 고지를 실제 동봉 사실로 기재하지 않는다. 외부 공식 설치본의 개별 고지/resources·사용 조건 검증은 G7이다.
- 구 CI의 main push→배포·key/SSH 연결을 복제하지 않는다. 새 CI는 read 권한의 PR/수동 검사이며 공식 pinned scanner는 runner 임시 경로에만 준비한다. 원격 workflow 실행·artifact 게시·운영 전송은 미실행이다.

## 보완과 미결

- 모델의 최초 계획 시험은 계획 자체가 scanner를 실행해 임시 파일을 만드는 점을 발견했다. 정적 plan과 apply 전 필수 검사를 분리해 범위를 보존했으며 검사 예외나 요청 조건 완화로 해결하지 않는다.
- 잘못된 native JSON 타입이 Python 오류로 끝나던 문제를 명시 deny/실패 응답으로 보완했다. native 제거도 exit0만으로 완료하지 않고 대상 캐시 부재를 확인한다. plan은 패키지·CLI·receipt와 자체 구현/검증 코드 hash에 연결한다.
- 실제 Codex CLI는 0.167.2를 사용하고 isolated 설정/cache만 조회·변경한다. Claude CLI는 현재 PATH에서 확인되지 않아 실제 manager·native callback 검증을 통과로 세지 않는다.
- private는 이전 common source bundle pin/interface에 의존한다. 이번 공통 패키징으로 pin을 조용히 갱신하지 않았다. native private 포장·공통+private 조합과 실제 초기 주입/가드·MCP 공식 실행은 G7 및 후속 통합 대상이다.

현재 실제 결과와 근거/제한은 [검증 기록](../verification.md)의 G5 절과 로컬 `_bmad-output/g5-packaging-20261118/`에 연결한다.
