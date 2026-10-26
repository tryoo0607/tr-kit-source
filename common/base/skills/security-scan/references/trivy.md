# Trivy

## 입력과 전제

`trivy --version`과 대상 이미지 digest 또는 경로를 확인한다. 배포 manifest의 실행 버전을 사용하고 DB 및 checks의 갱신 시점을 확인한다. 클러스터 접근과 원격 repo 검사는 별도 요청 범위이며 로컬 검사 대신 자동 실행하지 않는다.

## 수행 방법과 절차

1. 변경 대상에 필요한 검사만 고른다. 코드 자체의 취약 패턴은 Semgrep, lockfile과 패키지는 `fs --scanners vuln`, IaC는 `config`, 이미지는 `image --scanners vuln`을 사용한다. secret 검사는 요청 범위에 포함될 때 추가한다.
2. 결과는 작업별 새 JSON 경로로 저장한다. 예시는 실행 위치와 출력 경로를 실제 작업에 맞게 바꾼다.

   ```bash
   trivy fs --scanners vuln --format json --output /absolute/path/packages.json /absolute/project
   trivy config --format json --output /absolute/path/iac.json /absolute/project/infra
   trivy image --scanners vuln --format json --output /absolute/path/image.json image@sha256:digest
   ```

3. 기본 종료 코드 0은 취약점 부재를 뜻하지 않는다. JSON의 scanner별 결과와 오류를 확인한다. CI에서 탐지 시 실패가 필요할 때만 severity 기준과 `--exit-code 1`을 명시한다.
4. DB 다운로드 실패, 지원하지 않는 manifest, lockfile 부재와 제외 범위를 표시한다. `--skip-db-update`로 실패를 숨기지 않으며 오프라인 검사는 확보한 DB의 시점을 보고한다.

## 제약과 주의점

image 등 fs backend를 쓰는 scan cache는 BoltDB 잠금 때문에 한 process만 접근할 수 있다. 같은 cache를 사용하는 검사는 직렬화하거나 검증한 별도 cache를 사용한다. filesystem 및 SBOM의 기본 memory cache와 구분한다. DB 갱신도 동시에 중복 실행하지 않는다. 서버, Redis나 Docker daemon 권한을 검사 중 자동 추가하지 않는다.

공식 조작 기준: https://trivy.dev/docs/latest/configuration/ 및 https://trivy.dev/docs/latest/configuration/cache/ .
