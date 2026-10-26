# include와 제품 연결

외부 skill을 배포 입력으로 선택하거나 제품별 연결과 조립을 작성, 검토할 때 사용한다. include는 build-time 배포 선택이며 runtime에서 skill 지침을 적용하는 연결과 구분한다.

## 입력과 전제

실제 조립 계약은 common/base/dependencies.toml과 scripts/build.py다. 원본의 출처, license, 정확한 revision, skill 경로와 의존 자료를 확인한다. 이 지침은 원격 취득이나 의존성 변경 실행을 자동 승인하지 않는다.

현재 외부 원본과 제품별 선택 경로는 common/base 및 adapters/<product>의 dependencies.toml을 정본으로 한다. BMAD, Claude-Mem과 Wiki의 런타임도 선언된 resources로 보존한다. 다른 호스트에서는 같은 commit의 checkout과 실제 source 위치를 확인한다. 조립 후 assembly.json의 revision과 license_files/resources, 실제 라이선스 및 지원 자료 보존을 확인한다. 배포 입력 누락은 runtime 대체 경로로 해결된 조립 성공이 아니다. Orca의 실제 guide는 설치 CLI에서 조회하므로 stub revision 고정만으로 runtime guide까지 고정됐다고 판단하지 않는다.

## 수행 방법과 절차

1. 외부 plugin 전체 대신 필요한 skill을 명시 선택한다. dependencies.toml의 schema_version=1과 skills 항목에 id, source, revision, path를 선언한다. source는 sources.toml의 repository alias이고 revision은 정확한 commit, id는 원본 name과 같아야 한다. scripts/fetch_sources.py로 명시 취득한 clean checkout을 사용한다. cache는 TR_KIT_SOURCE_CACHE 또는 source root의 .cache/upstreams이며 로컬 절대 경로를 공개 선언에 넣지 않는다. 조립기는 기존 절대 checkout 입력도 검증할 수 있지만 새 선언은 alias를 사용한다.
2. 함께 포함해야 하는 외부 skill은 선택 requires 배열에 명시한다. 자동 취득이나 전이 의존 추론을 기대하지 않는다. 폴더 밖 상대 참조, plugin 초기화와 공통 지원 자료는 원본을 검토해 누락을 확인한다. skill 폴더 밖의 라이선스는 license_files에 원본 checkout 기준 상대경로를 선언한다. 기존 출력 파일 충돌이나 누락은 조립 오류다.
   skill 밖의 실행 자료는 resources 배열의 source/target으로 선언한다. source는 같은 고정 checkout 기준, target은 출력 루트 기준 상대경로다. 경로 이탈과 symlink, 기존 파일 충돌은 거부한다. 자원을 복사한 것과 해당 hook을 등록한 것은 별개다.
3. 선택한 skill의 지원 파일과 내부 hook을 보존하고 외부 plugin 수준 hook은 등록하지 않는다. Claude 내부 hook 실행은 별도 검증한다. 현재 Codex 미변환 hook, plugin root 변수와 symlink 등 미지원 입력은 오류로 처리하며 조용히 제거하지 않는다.
4. 자체 wrapper를 진입점으로 쓸 때는 wrapped=true를 선언하고 common/base/skills/<id>/SKILL.md를 작성한다. 공식 원본과 라이선스는 배포 skill의 upstream/ 아래 보존하고 원본 SKILL.md는 GUIDE.md로 바꿔 중복 skill 발견을 막는다. wrapper에서 필요한 원본 reference로 바로 연결하고 GUIDE.md 전체를 기본 재로드하지 않는다. wrapped가 아니면 공식 원본 자체가 진입점이며 기존 skill과 충돌할 때 조립을 중단한다.
5. 공통 보정은 common/base/skills/<id>/bindings.toml, 제품별 호출/경로 차이는 adapters/<product>/skills/<id>/bindings.toml에 둔다. 공통 후 제품 binding을 적용한다. schema_version=1, 선택 runtime_note와 replacements의 file/old/new/count, 선택 target_skill/target_file을 사용한다. 예상 치환 횟수가 다르면 원본 drift로 검토한다. wrapper의 정책을 binding에도 복제하지 않는다.
6. 변환은 배포본 Markdown에만 적용한다. 원본 checkout과 실행 script를 고치지 않는다. sibling SKILL.md 링크는 지침을 읽어 적용하는 연결이며 native 호출이나 격리를 보장하지 않는다. script 경로는 실제 배포 자료 위치를 기준으로 해석하며 upstream 안의 도구를 wrapper 루트에 있다고 가정하지 않는다.
7. 각 제품을 새 출력 경로로 조립하고 assembly.json, 포함 목록과 변경 결과를 확인한다. bindings.toml은 배포하지 않는다. 현재 조립기는 공통과 adapter의 동일 출력 파일 충돌을 거부하며 임의의 Markdown 병합을 하지 않는다. 대응 계층 유지가 지원되지 않는 덮어쓰기를 허용하지 않는다. 같은 산출물을 다시 덮어쓰거나 검증을 설치와 혼동하지 않는다.
   공통/제품 scripts와 adapter mcp.json도 조립한다. MCP 등록 자료는 포함된 원본 런타임을 실행하므로 실제 프로세스로 initialize와 tools/list, 저장/조회를 확인한다. 호스트 설정을 쓰거나 plugin hook을 자동 활성화하지 않는다.

개발 도구의 실행 버전은 common/base/scripts/dev-tools.toml에 둔다. source의 scripts/setup_dev_tools.py는 명시한 새 prefix에 CLI와 browser를 설치하고 env.sh, npm lockfile과 Python freeze를 남긴다. 기존 prefix와 전역 설정은 덮지 않는다. 설치는 skill 조립과 별도로 승인된 범위에서 실행하고 필요한 shell에서만 env.sh를 명시 적용한다. Python Playwright의 browser와 Node CLI의 preview engine 조합은 scripts/verify_dev_tools.py로 실제 검사한다. 현재 자동 provision은 Linux x86_64를 지원하며 다른 환경에서 검증 완료로 취급하지 않는다. toolchain 생성, host plugin 활성화와 모델의 skill 선택은 별도 완료 조건이다.

조립 검수에서 표준 compatibility 필드 때문에 고정 creator validator가 거부하면 원본을 삭제/변형해 통과시키지 않는다. 이 repository의 scripts/validate.py에 배포 skill과 --creator 경로를 전달하면 해당 필드를 별도 검사하고 나머지는 임시 검사본으로 고정 validator에 전달한다. 원본과 배포본 metadata는 유지한다. 이 검사기는 Python/PyYAML이 필요하며 source에서 실행하는 검수 도구다. 제공되지 않는 환경에서는 해당 필드 수동 대조와 도구 미실행 범위를 구분한다.

## 제약과 주의점

자체 skill은 공통 source, 제품 의미 차이는 adapter에 둔다. 외부 저작 규칙을 자체 원본에 일괄 적용하려고 upstream을 재작성하지 않는다. requires는 배포 의존 선언이고 연계와 의존은 runtime 요청 계약이므로 서로 대신하지 않는다. 현재 외부 선택이 비어 있다는 이유만으로 creator 연결이나 제품 호환이 완료됐다고 판단하지 않는다.

## 결과와 완료 판단

선택 원본과 revision, 보존 자료, 제품별 변환, 조립 결과와 미지원 범위를 기록한다. 정적 조립, 호스트 등록, 실제 hook 실행과 model routing 검증을 구분한다.
