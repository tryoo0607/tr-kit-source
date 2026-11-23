# 공식 도구 준비·확인

## 목적과 역할 경계

- 기존에 선택한 Context7 CLI·Playwright CLI/engine/Python·Semgrep·Trivy·Gitleaks를 명시한 새 prefix에 준비하고 결과를 검증한다. 외부 설치본을 kit 구성요소로 복제/동봉하거나 원문을 변형하지 않는다.
- 공식 npm·uv·release archive·Playwright browser 설치를 연결하는 자체 glue다. 새 runtime·scanner·브라우저를 구현하거나 agent 업무 절차를 대체하지 않는다.
- source 구현·계획 출력, 실제 취득/설치, env 적용, provider 등록, Git hook 활성화와 운영 배포는 각각 다른 상태다. 도구 부재나 일반 검사 요청을 설치 승인으로 취급하지 않는다.

## 입력과 전제

- 선택 group, kit source root, 신규 absolute prefix, 기존 Python과 development용 node/npm/uv 실행 경로를 받는다. prefix 부모는 존재해야 하며 prefix는 kit source 밖이어야 한다. 현재 작성한 설치 경로는 Linux x86_64/Python3.11 이상을 지원한다. Windows/macOS 지원을 추정하지 않는다.
- 버전 정본은 [개발 도구](../scripts/dev-tools.toml)·[Semgrep/Trivy](../scripts/security-tools.toml)·[Gitleaks](../scripts/secret-tools.toml)다. 현재 Python Playwright1.64.1과 Node 최소22.13.0은 기존 선택을 이관한 것이고 Python3.11 최소는 현재 자체 TOML 처리의 전제다. 호스트 runtime을 자동 업그레이드하지 않는다.
- 기존 prefix를 새 관리자가 자동 채택하거나 덮어쓰지 않는다. Gitleaks 구 receipt는 기존 비밀 검사기의 지원과 새 준비 관리기의 status 지원을 구분한다. status가 구 형식을 인식하지 못한다고 기존 설치를 삭제/재설치하지 않는다.

## 수행 방법과 절차

1. 사용자의 대상·설치/네트워크/파일 범위와 호스트 가드를 대조한다. source 작성 요청뿐이면 source/fixture만 검증한다.
2. source root에서 아래 CLI의 plan을 사용한다. plan은 pin과 명시 실행 파일을 읽고 hash를 계산하지만 설치 manager·버전 명령·네트워크를 실행하거나 prefix를 만들지 않는다.

   ```text
   python3 -B scripts/setup_dev_tools.py plan --prefix /absolute/new-tools --node /absolute/node --npm /absolute/npm --uv /absolute/uv
   python3 -B scripts/setup_git_guard.py plan --prefix /absolute/new-gitleaks
   ```

3. prefix·버전·공식 취득처·부수효과가 승인 범위와 맞으면 같은 인자의 action을 apply로 바꾸고 `--expect-plan <plan_id>`를 추가한다. 입력/source/prerequisite/pin이 바뀌면 거부한다. 같은 승인 범위 안에서 매 명령마다 새 사용자 승인을 받으라는 뜻이 아니다.
4. development는 공식 npm registry에 정확한 ctx7/CLI 버전을 요청하고 installed engine·Python 패키지 버전을 대조한다. npm lifecycle script는 실행하지 않으며 Python 설치는 공식 PyPI wheel만 사용한다. Chromium은 공식 installer가 해당 prefix에 설치한다. Trivy/Gitleaks archive는 고정한 공식 release URL과 SHA256, 단일 regular 실행 파일·실행 버전을 검사한다. Node/Python·OS 패키지·인증은 자동 설치하지 않는다.
5. `setup_dev_tools.py status --prefix /absolute/prefix` 또는 해당 Gitleaks CLI의 status로 receipt·pin·필수 artifact inventory/hash/target/mode를 확인한다. `ready`는 준비 상태이며 실제 검색·스캔·브라우저 동작 통과가 아니다. 전체 transitive runtime 무결성이나 package provenance 서명 검증을 완료한 것으로 확대하지 않는다. npm lock/Python freeze는 관측 snapshot이며 완전 고정된 재현 빌드 선언이 아니다.
6. 동작 검증은 [verify_dev_tools.py](../../../scripts/verify_dev_tools.py)에 prefix와 작업별 **새** evidence 경로를 명시한다.

   ```text
   python3 -B scripts/verify_dev_tools.py --prefix /absolute/prefix --evidence /absolute/new-evidence
   ```

   기본은 버전 확인이다. `--local`은 Gitleaks의 clean/합성 비밀 또는 Semgrep의 발견/정상 및 Python/CLI Playwright의 click·분리·screenshot을 시험한다. 임시 파일·브라우저·자기 session의 시작/종료를 포함하므로 실제 승인 범위를 대조한다. query/브라우저/스캔을 실제 실행하지 않았으면 버전 성공만 보고한다.
7. `--network-context7`은 명시한 공개 query fixture로 library·정확 버전 docs를 확인하고, `--network-trivy`는 공개 checks/CVE DB를 해당 evidence cache에 받으며 합성 IaC/lockfile을 검사한다. 둘 다 기본 비활성이다. 실프로젝트·회사 자료를 fixture 대신 전송하지 않는다. 인증/네트워크/정확 버전 부재는 실패·미실행으로 남기고 로그인·다른 버전·skip-update나 다른 scanner로 대체하지 않는다.

## 제약과 주의점

- 새 prefix만 배타 생성한다. 실패 prefix는 `failed` receipt와 함께 남기고 동일 경로를 덮어쓰기/자동 재개/자동 삭제하지 않는다. 복구는 기존 상태 보존 후 명시한 새 prefix로 새 계획을 만드는 방식이다. 기존 prefix 정리나 운영 연결 전환은 별도 범위를 확인한다.
- 자체 실행 환경은 registry/config·credential 관련 상속 값을 줄이고 npm config·netrc·cache·Semgrep settings/log·browser 위치를 명시한다. `HOME`을 바꾸지 않는다. 이것은 OS/네트워크 sandbox가 아니며 모든 외부 도구의 숨은 파일 접근·통신 부재를 보장하지 않는다.
- 생성한 env.sh는 명시 source용이다. shell startup/profile, 현재 agent 환경·Git 설정·hook·MCP·서비스를 자동 변경하지 않는다. 어떤 작업 환경에 실제 적용할지 확인한 후 연결한다.
- probe는 자신이 연 고유 Playwright session만 close한다. close-all/kill-all이나 기존 사용자 browser 정리는 하지 않는다. timeout과 scoped cleanup 실패를 보고하고 고아 process 부재를 증거 없이 보장하지 않는다.
- 실제 Chromium은 Unix socket 경로 길이 제한을 받을 수 있다. 긴 prefix에서 도구 설치가 성공해도 긴 evidence/tmp 때문에 실행이 실패할 수 있으므로, 시험 evidence는 `/var/tmp` 아래의 명시한 짧은 새 경로를 사용할 수 있다. 실패한 evidence는 보존한다. CLI의 file URL 제한을 끄지 않으며, 로컬 시험은 합성 HTML 하나만 응답하는 임시127.0.0.1 서버를 사용하고 해당 서버도 종료한다. 파일 디렉토리 공개·외부 bind·공개 게시를 하지 않는다.
- 공식 diagram 도구의 외부 self-check/export script는 이 kit에 동봉하지 않는다. 이전 검증기의 bundled diagram 호출은 공식 provider 연결 검증으로 별도 유지할 대상이며 이 준비기의 브라우저 시험으로 대체 완료하지 않는다.

## 결과와 완료 판단

- plan·ready/status·버전 관측·각 local/network probe의 성공/발견/오류·미실행·cleanup을 구분한다. source·mock protocol·실제 공식 도구 취득·실행은 다른 증거다.
- 로컬 receipt·외부 manager 출력·검증 report는 private 실행 증거다. source docs에는 필요한 버전/범위/결과와 한계만 남기며 원본 상태·로그를 자동 커밋/전송하지 않는다.
- 설치/업데이트 이후 실제 사용하는 provider/entry·버전·원문 변경과 제품별 연결 검수는 후속 통합 단계에서 수행한다. 준비기 성공만으로 모든 skill이 새 설치본을 쓰는 것으로 표시하지 않는다.
