# Semgrep

## 입력과 전제

repo 루트와 검사할 경로, 고정한 로컬 rule 파일을 확인한다. `semgrep --version`을 배포 manifest와 대조하고 실행 파일이 없거나 버전이 다르면 설치 담당으로 돌려준다. Community Edition은 함수나 파일 경계를 넘는 분석에 한계가 있다.

격리 toolchain을 사용하는 환경에서는 setup이 제공한 `env.sh`를 해당 shell에서 명시 적용한다. 그 설정은 Semgrep settings와 log를 toolchain의 state로 분리한다. 읽기 전용 홈 경로 오류를 더 강한 권한이나 전역 설정 변경으로 우회하지 않는다.

## 수행 방법과 절차

1. 검사 경로와 rule 파일을 명시한다. 규칙이 없으면 기존 프로젝트 설정부터 찾고 외부 ruleset의 출처와 사용 조건을 확인한다. 원격 Registry 조회와 결과 업로드는 별개이며 `semgrep ci`나 로그인을 대신 실행하지 않는다.
2. repo 루트에서 실행한다. 결과 파일은 기존 파일을 덮지 않는 작업별 경로로 정한다.

   ```bash
   semgrep scan --config /absolute/path/rules.yaml --metrics off --error --json --output /absolute/path/results.json src/
   ```

3. 종료 코드만으로 판단하지 말고 JSON의 `results`, `errors`, `paths`를 확인한다. `--error`에서 발견 사항은 종료 코드 1일 수 있다. 실행 실패나 parse 오류, timeout과 제외 파일이 있으면 검사 범위의 한계로 보고한다.
4. 실제 입력과 실행 경로를 대조해 발견 사항을 판단한다. 자동 억제하거나 취약 코드를 실행해 재현하지 않는다. 수정 후 같은 규칙과 대상 범위로 다시 검사한다.

## 제약과 주의점

엔진, 규칙, Security Skills는 서로 다른 배포물이며 라이선스도 별도다. 이 skill은 Security Skills나 상용 엔진의 기능을 포함했다고 주장하지 않는다. CLI가 로컬 검사를 한다고 해서 Registry 요청이나 metrics 동작까지 오프라인이라고 가정하지 않는다.

공식 조작 기준: https://docs.semgrep.dev/running-rules 및 https://docs.semgrep.dev/metrics .
