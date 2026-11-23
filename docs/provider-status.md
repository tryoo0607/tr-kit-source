# 공식 외부 연결 현황

## 현재 근거의 범위 — 2026-11-23

공식 연결의11월20일 설치·원문/리소스 대조와 실행은 [공식 준비 기록](decisions/20261120-official-provider-validation.md)·[BMAD/hook 후속](decisions/20261120-hook-bmad-native-validation.md)에 있다. 이후 [private native](decisions/20261120-native-private-interface.md), [memory MCP](decisions/20261120-native-mcp-validation.md), [대표 모델/압축](decisions/20261120-real-work-compaction-validation.md)은 각각 다른 범위의 추가 관측이다. 오늘 새 공식 설치·업데이트/네트워크 조회·전 기능 실행을 한 결과가 아니다.

원문 BMAD 오류와 새 source Python stdin 오탐은 후속에서 보완했고 BMAD 자동 update404는 미지원으로 남겼다. 기존 운영 hook은 교체하지 않았으며 [보고 시험](decisions/20261120-reporting-approval-validation.md)의 기존 설치본 차단도 별도 발견이다. 후속5번에서 새 공통/private 묶음·pin·native 연결과 제품별47개 entry/resource의 현재 bytes를 재대조했다. 새 공식 업무 실행/업데이트는 아니며 전 기능 사용 가능 판정으로 확대하지 않는다. [현재 검증 요약](verification.md#현재-판정--2026-11-23)을 함께 읽는다.

## 공식 연결 검증 이력

아래 초기 검증·11월18일 표는 당시 결과로 보존한다. 그 안의 미설치/미실행과 원문 오류는 후속 보완 전의 관측이며 운영·전체 업무의 최신 실패나 성공으로 바꾸어 읽지 않는다.

### 2026-11-20 후속 보완 결과

- 승인한 개발진의 공식 BMAD867c546e를 별도 설치해 양 제품31개씩 원문 일치, retrospective 누락 해소·renderer 정상 출력을 확인했다. callable47개씩·BMAD 검수56개를 갱신했다. 원문 update metadata404는 남아 자동 갱신은 미지원이다.
- 새 source의 Python quoted stdin set(...) 오탐을 보완했다. 원래 입력 전체 scanner와 실제 금지 명령 검사는 유지한다. 운영 구 kit은 교체하지 않았다.
- 실제 Codex·Claude 실행기에서 합성 API 응답으로 hook 정상·차단·검사 불가·출력 차단·private hook 비간섭30사례를 확인했다. 실제 모델 행동·전체 private native 설치·실자료/압축·배포 성공과 구분한다.

### 2026-11-20 초기 격리 설치·호출 검증

[1번 검증 기록](decisions/20261120-official-provider-validation.md)에 실제 준비·호출·보완과 한계를 정리했다. 아래 11월18일 표는 당시 source 검수 상태다.

- 고정 commit의 skill41개씩(metadata3개 포함)을 양 제품 위치에 공식 관리 수단으로 설치하고 원문을 대조했다. BMAD retrospective 한 개는 원문 YAML 오류로 미설치다. 호출 entry46개씩/검수92개를 명시했다.
- 공식 Wiki/Claude-Mem의 양 제품 payload와 리소스가 manager의 고정 source와 일치한다. BMAD setup/help/build 렌더, 도구/브라우저·공개 docs/DB·memory worker/MCP·5개 Codex skill 사례를 실제 실행했다. native 발동·Claude 모델·실제 자료/SDK/기기·전체 업무 성공은 별도다.
- Sites 대조 입력은 후속 사용자 승인에 따라 현재 공식1.1.7 원문으로 채택했다. 기존 catalog를 보존하고 현재 schema2로 새 목록을 생성해 Codex/Claude 공통150파일·private48파일씩 fresh 조립했다. Sites 실행 provider의 버전 변경·실제 게시를 뜻하지 않는다. 기존1.1.6 원문과의 의미 비교는 미확인이다.
- Python heredoc `set(...)` 오탐은 새 source에도 남아 있다. 후속 hook/native 통합 검증의 보완 대상으로 기록했다.

### 2026-11-18 source 검수

이 표는 공식 문서의 설치/지원 설명과 이 작업에서 관측한 설치·실행을 구분한다. 기존 dependencies의 revision은 대조 기준이며 새 공식 설치를 완료했다는 뜻이 아니다. 아래 공식 경로를 확인한 사실로 해당 명령을 자동 실행하거나 최신 버전으로 바꾸지 않는다.

| 기능 묶음 | 공식 근거·관리 경로 | 이번 관측과 남은 검증 |
| --- | --- | --- |
| BMAD | [선택 revision README](https://github.com/bmad-code-org/BMAD-METHOD/blob/61e01f82644c4bb533750cfa0d6d61ab61d2cc9b/README.md)의 Skills CLI 또는 양 제품 공식 marketplace. V6 npm 경로와 V7 preview 경로는 다름 | 공식 관리 경로만 조회. bmad·모듈 metadata·knowledge/help·setup/renderer·uv/project `_bmad`를 함께 검수해야 함. 구 kit transformed skill/대조 checkout 미사용 |
| Archify | [선택 revision](https://github.com/tt-a1i/archify/blob/a4065941f12be7967436261d9934784e381d423c/README.md#installation-options)은 Codex/Claude 설치 위치와 renderer/validation 지원을 설명 | 외부 공식 entry·renderer/template/resource와 실제 브라우저 검증 미실행. 설명상의 지원을 실제 성공으로 세지 않음 |
| Diagram Design | [선택 revision](https://github.com/cathrynlavery/diagram-design/blob/10cfad6a7be7f734a92d3d628e5fa344685d4f01/README.md#install)의 Skills CLI 및 Claude marketplace | 양 제품 연결·공식 리소스·스타일/출력·선택 브라우저·네트워크 효과 검수 필요. 자동 업데이트 켜지 않음 |
| frontend-design/doc-coauthoring | [Anthropic 원 저장소](https://github.com/anthropics/skills/blob/dbd4588f9e1033efb41dad4bef2f7947c8993d44/README.md)의 Claude marketplace | 공식 entry와 개별 설치 범위/조건·리소스 확인 전. Codex 실행 호환은 해당 설치/제품 계약에서 별도 확인; kit 동봉으로 대체하지 않음 |
| README | [선택 revision](https://github.com/pekral/github-readme-generator/blob/d8bdac94d1a9488751d65e55e78eeabd47895bd0/README.md)의 Skills CLI와 양 제품 marketplace | 작성자는 Claude 행동 시험과 다른 제품의 포장 지원을 구분함. Codex 성공으로 확대하지 않음. 실제 설치/업무 시험은 미실행 |
| Android/Wear | [android/skills](https://github.com/android/skills/blob/bf68e2d66a992a1e6aeb7e9263293cc23fcbf475/README.md)의 Android CLI 또는 양 제품 marketplace | wear/testing entry·실제 SDK/기기·빌드와 행동 검증 미실행. agent/프로젝트 대상은 설치 시 명시 필요 |
| Android architecture | [GuillemRoca 원 저장소](https://github.com/GuillemRoca/agent-skills-android/blob/68fd141eec5ad2029ae8393e510dbe46dea48c36/README.md)의 Claude marketplace | 선택 원문은 commit 단위 버전, 다른 제품 설정은 원문 복사 방식도 제시함. 이를 kit 내 복제 허용으로 채택하지 않음. Codex 무변형 연결/지원 범위 미확인 |
| Android tests | [skydoves 원 저장소](https://github.com/skydoves/android-testing-skills/blob/8665ed59643c90eb1056a256a6ddec161aa1cfa1/README.md#installation)의 공식 script가 외부 source→평면 skill symlink 설치 | 비교용 checkout을 실행본으로 재사용하지 않음. 공식 관리 설치와 원문의 실제 root 기준 참조·Codex 지원 검증 필요. Google Android CLI의 관리 대상이라고 섞지 않음 |
| Wiki | [선택 revision](https://github.com/nvk/llm-wiki/blob/d60674ff785e5c6d35322657d7839a7c0bdd3ca7/README.md#install)의 Codex/Claude marketplace | 별도 read-only/query와 관리 entry·공식 helper·제품 resources 확인 필요. bundled session hook 수집은 별도 trust/허용 범위이며 설치/조회 승인으로 자동 수집하지 않음. private 자체 gate만 source 검수 |
| Claude-Mem | [15.2.1 source](https://github.com/thedotmack/claude-mem/tree/d9b36b66dc68da92af9df238e4c4debab587ba62)와 G4의 공식 MCP/worker 연결 | 합성 process/stdio와 자체 수명 관리 검수. 공식 runtime/resources·외부 background 효과·기존 DB·native 등록 미실행. schema2 검수 기록 전 실행 보류 |
| Context7 CLI | [npm 0.8.2](https://registry.npmjs.org/ctx7/0.8.2), 기존 명시 npm 설치와 lock | 실제 package10파일 전체가 공식 archive와 일치. 전이 의존·Node/실제 질문/native 연동 미검증; pending 유지 |
| Playwright CLI | [npm 0.1.22](https://registry.npmjs.org/@playwright/cli/0.1.22), 기존 명시 npm 설치와 lock | 실제 package16파일 전체가 공식 archive와 일치. engine·브라우저·실제 UI 시나리오/native 연동 미검증; pending 유지 |
| skill-creator / Sites | 현재 선언의 호스트 관리 system skill / 공식 plugin cache entry | G7에서는 새로 인증/설치하지 않음. 현재 entry pin과 개별 manager·전체 리소스·제품 native 수행 증거를 구분. Sites는 선언상 Codex만 지원하며 Claude 게시 경로로 대체하지 않음 |
| Worktrunk / Orca | 기존 선택 CLI/업무 연결의 공식 경로를 재사용 | worktrunk entry pin은 기존 선언에 있음. G7에서 release 설치 근거·Orca 실제 서버/세션·위임을 새로 실행 검증하지 않음 |

공통 53개 own skill의 존재·source 조립 성공은 위 공식 기능들이 모두 설치·실행 가능하다는 뜻이 아니다. provider별 검수 기록이 없으면 미확인으로 남긴다. source+private 조립과 제품 native 조합도 별도 상태다. 실행 도구의 정확한 검수 계약은 common/base/references/provider-review.md, 실제 시험 범위는 verification.md가 소유한다.
