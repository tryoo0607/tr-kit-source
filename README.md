# tr-kit-source

BMAD를 중심으로 개발, 조사, 검증, 지식과 인계를 연결하는 Codex 및 Claude용 플러그인 소스다.

이전 redesign의 현재 구현을 저장소 루트로 승격했다. drafts와 이전 core/shared/recipe 기반 구현은 현재 source와 배포 입력에서 제거했다. 기존 설치본과 운영 데이터는 source 교체만으로 바뀌지 않는다.

## 소스 구조

| 경로 | 책임 |
|---|---|
| common/base | 공통 지침, 자체 skill, 외부 의존 선언과 공통 binding |
| adapters/codex | Codex의 Wiki 선택, metadata와 MCP 경로 차이 |
| adapters/claude | Claude의 Wiki 선택, metadata와 MCP 경로 차이 |
| scripts | 외부 source 확보, 조립, 패키징과 실행 검증 |
| sources.toml | 공개 upstream URL. 정확한 commit은 dependencies.toml |
| tests | 현재 source의 조립, 검수와 도구 설정 테스트 |
| out | 생성물. 직접 편집하거나 커밋하지 않음 |

adapter의 skills 폴더는 전체 skill 목록이 아니라 제품별 보정만 담는다. BMAD와 개발 지원 skill 대부분은 common에서 포함한다. Codex와 Claude의 전체 포함 결과는 assembly.json으로 확인한다.

## 포함 기능

- BMAD: 조사, 요구, 설계, 구현과 검증.
- document, Claude-Mem, LLM Wiki: 작업 정본, 경험과 지식의 연결.
- Context7: 버전별 문서 조회.
- Semgrep 및 Trivy: 코드, 패키지, 이미지와 IaC 검사.
- frontend-design, diagram-design, Playwright: 화면 제작, 시각화와 브라우저 검증.
- project, Worktrunk, Orca: 코드 공간과 workspace 연결.
- session, profile-setup, skill-authoring: 인계와 호스트 운영, 설정 및 저작.

skill을 포함한 것과 실행 도구 설치, worker 가동 및 자동 hook 수집은 다르다. 새 package에는 plugin hook을 자동 등록하지 않는다.

## 준비와 빌드

Python 3.12 이상, Git과 PyYAML이 필요하다. 외부 checkout은 cache에 두고 정확한 revision과 clean 상태를 검사한다. build는 원격 source를 자동 취득하지 않는다.

```bash
python3 -m pip install 'PyYAML==6.0.3'
python3 scripts/fetch_sources.py
python3 -m unittest discover -s tests -p 'test_*.py'
./build.sh codex --output out/codex
```

기본 source cache는 .cache/upstreams다. 기존 cache를 재사용하려면 fetch의 --cache와 build의 TR_KIT_SOURCE_CACHE에 같은 경로를 명시한다. 다른 revision이나 dirty checkout은 자동 reset하지 않는다.

Codex 결과는 기존 tr-codex marketplace와 plugins/tr-codex payload를 포함한다. 설치 selector는 tr-codex@tr-codex다. 기능 버전은 VERSION, 제품별 suffix는 source commit에서 가져오므로 같은 커밋의 재배포는 같은 결과를 만든다. 기존 출력은 덮지 않으므로 다시 빌드할 때 새 output 경로를 지정한다.

Claude도 기존 tr-claude marketplace와 plugins/tr-claude payload를 만든다. 로컬 Claude 호스트 적용은 Codex 검증 이후에 한다.

```bash
./build.sh claude --output out/claude-check
```

## 설치와 실행 검증

```bash
./install.sh codex out/codex
```

기본은 native 설치 명령만 보여주는 dry-run이다. --apply는 marketplace 등록과 plugin 설치를 실행한다. 기존 plugin, 전역 AGENTS.md와 toolchain 경로의 전환은 먼저 [적용 및 정리 기준](ROLLOUT.md)으로 변경 범위와 복구안을 확인한다. 현재 세션은 새 설치를 자동으로 다시 읽지 않는다.

선택적 개발 도구는 scripts/setup_dev_tools.py --prefix NEW_DIRECTORY --uv /path/to/uv로 격리 설치한다. 도구 버전은 common/base/scripts/dev-tools.toml이 소유한다. env.sh는 선택한 shell에서 명시 적용하며 전역 설정을 자동 수정하지 않는다. BMAD의 uv와 Claude-Mem의 Bun 및 worker는 별도 실행 전제다.

실제 도구 검증은 scripts/verify_dev_tools.py --plugin PLUGIN_ROOT --toolchain TOOLCHAIN_ROOT, 기록 연결은 scripts/verify_records.py로 실행한다. Context7 실조회는 --network-context7을 명시한다. 두 검증기는 모델 호출과 자동 skill 선택을 시험하지 않는다.

## 배포와 데이터 경계

.github/workflows/build.yml은 PR의 필수 검사 이름 build를 유지하며 두 제품의 테스트·조립·skill 검수와 임시 clone 배포 dry-run을 수행한다. main push는 같은 검증을 통과한 생성물을 기존 tryoo0607/tr-codex와 tryoo0607/tr-claude 저장소에 일반 커밋/push한다. delivery.yml은 같은 흐름을 재사용하는 수동 배포 진입점이다. source 저장소에는 원본을, 두 배포 저장소에는 생성물만 둔다. 별도 tr-redesign 배포 저장소나 plugin은 만들지 않는다.

기존 Actions secret 이름 TR_CODEX_DEPLOY_KEY와 TR_CLAUDE_DEPLOY_KEY를 재사용한다. 각 key는 해당 배포 저장소의 쓰기 권한이 필요하며 main 보호 정책도 자동 push를 허용해야 한다. 값이나 권한을 자동 변경하지 않는다. 두 제품을 모두 준비한 뒤 순서대로 push하므로 두 번째 push가 실패하면 부분 반영될 수 있다. 문제를 수정하고 같은 source commit의 workflow를 재실행하면 이미 반영된 제품은 no-op으로 처리한다. release.json에 source revision과 전체 생성물 hash를 기록한다.

로컬에서 원격을 변경하지 않고 배포 차이를 확인하려면 두 제품을 out/codex와 out/claude에 빌드한 다음 아래를 실행한다. CLONE_ROOT는 존재하지 않는 새 경로여야 한다.

```bash
python3 scripts/delivery.py --built-root out --clone-root /tmp/tr-kit-delivery-check --source-revision SOURCE_COMMIT_SHA
```

기존 문서와 project는 자동 이동하지 않는다. 로컬/GitHub 문서 정본, 공유 및 이관 기준과 QMD 보류 정책은 ROLLOUT.md를 따른다.

공통 자체 소스의 라이선스는 LICENSE를 따른다. 외부 skill과 runtime은 각 upstream의 라이선스를 보존하며, 저장소 전체를 단일 라이선스의 외부 코드로 취급하지 않는다.
