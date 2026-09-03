# GitHub Actions — 양식·스니펫

`.github/workflows/<name>.yml`. 아래는 조립용 조각 — 프로젝트에 맞게 넣고 뺀다(비처방).

## 기본 골격
```yaml
name: ci
on:
  push:
    branches: [main]
  pull_request:
permissions:
  contents: read          # 최소권한. 배포 등 필요 시만 확장
concurrency:              # 같은 ref 중복 실행 취소(비용·시간 절약)
  group: ci-${{ github.ref }}
  cancel-in-progress: true
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      # ↓ 언어별 setup + lint/test
```

## 언어별 (setup + 캐시 내장)
**Go** (예: geodeonbar Echo)
```yaml
      - uses: actions/setup-go@v5
        with: { go-version-file: go.mod, cache: true }   # 모듈 캐시 자동
      - run: go vet ./...
      - run: go test ./... -race -cover
      - run: go build ./...
```
**Node**
```yaml
      - uses: actions/setup-node@v4
        with: { node-version-file: .nvmrc, cache: npm }
      - run: npm ci
      - run: npm run lint --if-present
      - run: npm test
```
**Python**
```yaml
      - uses: actions/setup-python@v5
        with: { python-version-file: .python-version, cache: pip }
      - run: pip install -r requirements.txt
      - run: ruff check . && pytest
```

## 스테이지 분리 (job 의존)
```yaml
jobs:
  lint:   { runs-on: ubuntu-latest, steps: [...] }
  test:   { needs: lint, ... }
  build:  { needs: test, ... }
  deploy: { needs: build, if: startsWith(github.ref, 'refs/tags/v'), ... }
```
- 순차 게이트는 `needs:`. 배포는 `if:`로 태그/브랜치 제한.

## 매트릭스 (필요 시만)
```yaml
    strategy:
      matrix: { go: ['1.22', '1.23'], os: [ubuntu-latest] }
    runs-on: ${{ matrix.os }}
```
과하면 지양 — 실제 지원 범위만.

## Secret (평문 금지)
```yaml
      - run: ./deploy.sh
        env:
          TOKEN: ${{ secrets.DEPLOY_TOKEN }}   # 이름만. 값은 GH Actions secrets에 등록
```
- 값 등록 = repo/org **Settings → Secrets and variables → Actions** (유저가, report-first 안내).
- ⚠️ PR from fork엔 secret 미노출(보안) — 필요 시 `pull_request_target` 신중히.
- repo **파일** secret(git-crypt)과 CI **secret**은 다른 층 — 혼동 금지.

## 배포 예 (태그 릴리스)
```yaml
  release:
    needs: build
    if: startsWith(github.ref, 'refs/tags/v')
    permissions: { contents: write }
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: softprops/action-gh-release@v2   # 액션 버전 고정
```

## 함정 (gotcha)
- **액션 버전 고정** — `@v4` 등 태그 고정(혹은 SHA). `@main` 금지(재현성·공급망).
- **최소권한** — `permissions:` 기본 read, 필요한 job만 write.
- **concurrency**로 중복 실행 취소(무료 분·시간 절약).
- **캐시 키**는 lockfile 기준(setup-* 내장 캐시 우선, 수동이면 `hashFiles`).
- 실패하면 **`odin:gh-fix-ci`** — 로그 기반 진단·수정.
