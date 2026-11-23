# G2: 공식 도구 준비·검증 연결

2026-11-18. R-34의 scratch 구현·검수다. G1의 초기 발견/시험 실패는 해당 보완 후 재검증됐고, 운영/native 미실행과 구분한 상태에서 사용자가 G2를 요청했다. 이번에는 실제 새 도구 취득/설치·호스트 환경 적용·provider/hook·배포를 수행하지 않는다.

## 재사용과 보존

- 기존 자체 setup_dev_tools/setup_git_guard/verify_dev_tools의 명시 새 prefix·공식 npm/uv/release·고정 tuple·검증 fixture·고유 Playwright session 개념을 재사용했다. 외부 원문·browser·scanner를 source나 bundle에 넣지 않는다.
- 선택 버전을 갱신하지 않는다. 현재 dev pin에 누락됐던 기존 Node 최소22.13.0·Python Playwright1.64.1을 명시하고 자체 TOML runner는 Python3.11 이상을 요구한다. Node/Python/OS 의존 패키지를 자동 설치하는 경로는 없다.
- 새 prefix·실행 파일 hash·공식 취득 URL·pin·기대 효과를 plan으로 출력하고 apply는 reviewed plan_id와 현재 입력을 대조한다. plan 자체는 manager/version 명령·네트워크·prefix 생성을 하지 않는다.
- development는 dev-tools/security-tools만, Gitleaks-only는 secret-tools만 소비한다. Gitleaks가 중복돼 있다는 최초 목록 설명은 실제 세 파일 개별 대조에서 부정돼 문서를 정정했다. 존재하지 않은 중복을 코드에서 지웠다고 보고하지 않는다.

## 실제 배치

```text
common/base/
  references/toolchain.md
  scripts/
    toolchain.py
    toolchain_verify.py
    dev-tools.toml
    security-tools.toml
    secret-tools.toml
scripts/
  setup_dev_tools.py
  setup_git_guard.py
  verify_dev_tools.py
tests/
  test_toolchain.py
```

기존 제시안의 공통 모듈을 준비와 probe 두 파일로 나눠 설치/다운로드 책임과 관측/cleanup 책임을 분리했다. 같은 로직을 제품별로 복사하거나 새 상시 service/skill을 만들지는 않았다.

## 실행 흐름

```text
명시 group/prefix/실행 경로 → plan(입력 hash·공식 취득·효과 출력)
                          → 승인 범위·plan_id 대조 → apply
apply → 신규 prefix 배타 생성 → 공식 npm/uv/Chromium·release 단계
      → engine/Python 패키지/실행 버전·checksum → receipt ready
실패 → failed receipt/부분 prefix 보존 → 기존 경로 유지
     → 새 prefix를 명시한 새 계획(자동 재개/삭제/덮어쓰기 없음)
status → 현재 해당 group pin·필수 artifact inventory/hash/target/mode 대조
verify → ready 전제 → 버전 관측 → 선택 local/network probe
       → 자기 session만 close → 결과·미실행·오류·cleanup report
```

ready는 취득/설치 단계의 상태다. 기본 verify도 버전만 확인하며 local·Context7 공개 query·Trivy checks/DB 시험은 각각 명시적으로 선택한다. Context7 인증·정확 버전 부재나 Trivy DB 실패를 로그인·다른 버전·skip-update로 통과시키지 않는다. 외부 도구의 소유된 설치본·runtime을 자체로 재작성하지 않는다.

## 검증과 한계

시험은 합성 archive/manager/process fixture로 수행했다. checksum·잘못된 archive member·engine/버전 drift·빈 version·기존 prefix·입력/receipt 변경·부분 실패/새 prefix 회복·probe parse 오류·timeout/cleanup 등을 실제 자체 코드에 대조한다. Gitleaks receipt는 공통 검사기 계약과 연결해 검증한다. 합성 fixture의 checksum은 테스트용이며 공식 다운로드 검증 실적으로 계산하지 않는다.

새 준비기는 기존 prefix·legacy receipt를 자동 채택/변환하지 않는다. 실패 prefix 삭제/동일 위치 resume·운영 toolchain 교체는 지원 완료로 주장하지 않는다. npm lock/Python freeze와 entry/browser hash는 관측 snapshot이며 전체 transitive closure/서명 검증이나 OS 격리가 아니다. 환경 상속을 줄이고 config/cache/NETRC를 명시하지만 외부 도구의 모든 숨은 접근·통신 부재를 보장하지 않는다. HOME과 shell startup은 변경하지 않는다.

구 검증기의 bundled diagram self-check/export 호출은 가져오지 않았다. 공식 diagram provider를 연결해 검사할 책임은 G7의 외부 resources/제품 연결에 남기며 browser smoke 시험으로 대체 완료하지 않는다. 원문 동봉과 치환을 되살리는 근거가 아니다.

사용 기준은 common/base/references/toolchain.md가 소유하고 요구/구조/검증 문서는 위치·상태·결정 이유만 연결한다. 감사는 plugin-authoring의 kit/skill와 shared 기준 및 공식 system skill-creator를 적용하는 동일 작성자 대조다. 새 kit 전체/native/Claude/압축/운영 적합 판정과 구분한다. 이번 common 변경에 따른 private common pin 갱신도 후속 통합 단계에 남긴다.

공식 조작 근거: [npm install](https://docs.npmjs.com/cli/v11/commands/npm-install/), [uv CLI](https://docs.astral.sh/uv/reference/cli/), [Playwright Python browsers](https://playwright.dev/python/docs/browsers), [Gitleaks v8.30.1](https://github.com/gitleaks/gitleaks/blob/v8.30.1/README.md). 기존 선택 tuple과 query 구문은 이전 자체 준비/검증 source에서도 대조했으며 실제 해당 tuple의 새 취득·동작은 이번에 실행하지 않았다.
