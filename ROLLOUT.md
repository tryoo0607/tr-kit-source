# Codex 적용과 문서 및 프로젝트 전환

## 범위와 순서

현재 저장소의 common, adapters, scripts가 정본이다. 이전 redesign의 현재 내용만 루트로 승격했으며 drafts와 이전 recipe, lifecycle, hook, Happy 배포는 포함하지 않는다. 설치된 이전 플러그인은 source 교체만으로 바뀌지 않는다.

1. source의 unit test, 외부 revision, Codex marketplace 조립과 모든 skill을 확인한다.
2. 기존 Codex plugin selector와 설치 source, 전역 AGENTS.md, 도구 PATH와 memory worker 상태를 조회한다. 복구할 원본과 변경 차이를 기록한다.
3. 기존 tr-codex marketplace의 갱신 또는 같은 이름의 로컬 조립본으로 검증한 plugin을 설치한다. canary 등 기존 별도 채널과의 중복 활성화를 피한다. tr-private 등 다른 플러그인은 유지한다. 이전 plugin의 전역 지침과 hook은 새 공통 지침에 자동 합치지 않는다.
4. 새 Codex 세션 하나에서 스킬 발견, 조사, 작은 구현과 검사, 기록 조회, 저장과 재개를 확인한다. 새 지침은 현재 세션에 자동 소급되지 않는다.
5. 일상 작업에 적용한 뒤 문서와 project를 한 대상씩 전환한다. Codex에서 검증한 공통 source를 나중에 Claude에 적용한다.

실제 host 교체는 설치 selector와 전역 지침 diff, 백업 위치 및 복구 명령을 확인한 뒤 수행한다. GitHub push와 원격 배포는 로컬 pilot과 별개다. 구버전 AGENTS.md가 이전 backbone이나 hook 경로를 가리키면 새 plugin만 설치해 전환 완료로 처리하지 않는다.

## adapter 목록의 의미

| 경로 | 소유 책임 |
|---|---|
| common/base/dependencies.toml | 공통 외부 skill과 revision |
| common/base/skills | 자체 skill과 공통 binding |
| adapters/codex/skills | document의 wiki 연결, creator 안내, wiki metadata 보정 |
| adapters/claude/skills | document의 wiki-manager 연결, creator 안내, wiki-manager metadata 보정 |
| adapters/*/dependencies.toml | 제품별 Wiki 원본 선택 |
| adapters/*/mcp.json | 제품별 plugin-root 변수와 MCP 실행 연결 |

adapter의 skills는 전체 목록이 아니다. 전체 포함 목록과 실제 파일 hash는 조립본의 assembly.json으로 확인한다. 공통 스킬을 양 adapter에 복제하지 않는다. 원본 procedure와 검사 형식, host runtime 검증을 구분한다.

## 문서 정돈 기준

| 자료 | 정본과 처리 | GitHub 공유 기준 |
|---|---|---|
| 소스 사용법, 공개 설계 및 기여 지침 | 해당 repo에 유지, 코드와 함께 검수 | repo의 공개 범위에 맞는 내용만 |
| 진행 중 요구와 계획, 검증 및 미결 | 기존 BMAD 작업 정본을 우선 사용 | 경로만으로 공개 여부를 결정하지 않음 |
| 작업 경험과 검색 | Claude-Mem의 관측과 원래 근거를 연결 | DB와 auth state를 repo에 복제하지 않음 |
| 재사용 지식 | 선택한 LLM Wiki의 source와 지식 페이지 | 소속과 공유 정책이 확인된 지식만 |
| 세션 인계 | 작업 정본 포인터, Wiki digest와 필요한 경험 | 독립 정본을 또 만들거나 전체 session을 무조건 공개하지 않음 |
| 기존 local-docs 기록 | 최초에는 기존 위치를 보존하고 새 기록에서 참조 | 정리와 원격 sync를 별도 작업으로 취급 |
| 로그, 영상, browser state, toolchain 및 cache | 필요한 원본만 지정된 비공개 자료 영역에 보존 | source와 공개 지식 repo에서 제외 |

Markdown이 local에 있다는 것과 GitHub에 비공개로 올라간다는 것은 다른 조건이다. Git remote, 현재 추적 파일과 과거 이력, 소속별 정책을 확인하기 전 sync를 켜지 않는다. secret은 문서나 Wiki로 이관하지 않는다.

한 정보의 정본은 하나로 두고 다른 도구에서는 원문 위치와 revision을 연결한다. 오래된 결정은 수정 이력과 대체 근거를 남긴다. BMAD 기록을 지식으로 합성한 뒤에도 원래 요구와 승인 사실은 유지한다. 기존 local-docs를 새 도구의 폴더 규격으로 일괄 변환하지 않는다.

## 기존 문서와 project 전환

먼저 코드 경로, Git remote 및 dirty 상태, worktree, Orca 등록, local-docs symlink, 문서 repo와 공유 범위를 조회한다. 이동이나 재등록 없이 현황표를 만든다.

각 항목을 유지, 참조 연결, 선택 이관, 보관으로 분류한다. 새 도구가 설치됐다는 이유로 코드와 문서 경로를 옮기지 않는다. group은 논리적 묶음이며 문서 상속이나 물리 이동을 뜻하지 않는다. 이미 준비된 workspace를 재사용한다.

작은 project 하나에서 기록 생성, 조회, 수정, 인계와 재개를 확인한 뒤 확장한다. 실제 이동이 필요하면 경로 매핑과 백업, worktree/Orca/symlink 검증 및 복구 순서를 그 작업에서 정한다. 원격 repo 생성이나 push는 별도 범위다.

## QMD 보류와 복구

QMD의 자동 index/embedding 갱신은 Codex pilot의 전제가 아니다. 타이머나 daemon을 정리할 때 실제 상태를 확인하고 대상 실행만 멈춘다. 기존 문서, index와 model 파일은 삭제 요청이 없는 한 보존한다.

다시 필요해지면 보존한 unit과 설정을 확인하고 해당 timer만 enable/start한다. index가 남아 있다고 최신이라고 가정하지 말고 선택한 collection의 갱신 시점과 소속부터 검증한다.

## 미검증 경계

CLI의 실제 실행과 package 검증은 model의 자연어 skill 선택, UI 미적 품질과 다르다. Claude-Mem은 명시 worker와 Bun, BMAD는 uv를 필요로 하며 hook 자동 수집은 이번 package에 등록하지 않는다. worker 부재를 빈 검색이나 저장 성공으로 보고하지 않는다. 호스트 toolchain, 새 세션 재개와 복구를 확인해야 실제 운영 전환 완료다.
