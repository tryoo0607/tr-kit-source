# G4: 공식 Claude-Mem MCP·worker 연결

## 요구와 범위

R-36. 사용자 “다음 G4 ㄱㄱ”에 따라 scratch source에 실행기 연결·수명 관리·health 판정을 작성하고 격리 검수한다. 공식 서버/DB 엔진 동봉·치환, 운영 설치·기존 개인 DB 연결·조회/수집, native 등록·commit/push/배포는 포함하지 않는다.

기존 dependencies가 선택한 Claude-Mem revision `d9b36b66dc68da92af9df238e4c4debab587ba62`의 package/plugin 버전은 15.2.1이다. 현재 main의 16.0.0으로 임의 업데이트하지 않았다. 공식 source와 제품 MCP 문서를 확인했고 실제 공식 설치본 실행 검증과 구분한다. 업무 기준 본문은 [연결 안내](../../common/base/references/claude-mem.md)가 소유한다.

## 변경 전후 구조

```text
변경 전
  mem-search / document → 공식 skill·native MCP 필요
  MCP·worker 실행 연결 없음

변경 후
  mem-search / document
    ├─ 기존 경험 검색 → 공식 mem-search skill / native MCP
    └─ 명시 준비·진단·수명 관리 요청 → 공통 references/claude-mem.md
          └─ scripts/claude-mem.py (자체 CLI)
               └─ common/base/scripts/claude_mem.py + claude-mem.toml
                    ├─ 기존 provider_links / toolchain helper 재사용
                    ├─ plan / doctor / health / start / stop
                    ├─ mcp → 외부 공식 mcp-server.cjs 직접 exec
                    └─ render → 제품별 adapter template → stdout
                         ├─ adapters/codex/mcp/claude-mem.toml.in
                         └─ adapters/claude/mcp/claude-mem.json.in

별도 host-local binding (source·배포물 밖)
  공식 entry·runtime 경로/pin + data/state + loopback port
    ├─ 외부 공식 설치본 scripts/{mcp-server,worker-service}.cjs
    ├─ 선택 data (기존 DB 자동 인수 없음)
    └─ 선택 controller state (marker / receipt / log / lock)
```

source 조립은 해당 제품의 `.in` template도 원래 상대경로로 보존한다. `.mcp.json` 또는 사용자 config로 자동 변환·등록하지 않는다. Codex fragment는 비활성이고 Claude fragment에는 근거 없는 enabled 필드를 넣지 않는다. 양 제품 MCP의 자동 연결과 worker autostart는 서로 다른 동작이다.

## 선택 이유와 한계

- 구 `records.py`의 bundled `mem-mcp/mem-worker` 대신 공식 stdio entry와 worker `--daemon`/`stop`에 연결한다. 검색 순서·tool schema·DB 엔진은 공식 기능 소유로 유지한다. 일반 BMAD/Wiki doctor를 하나의 새 records 실행기로 합치지 않는다.
- 공식 start/stop의 exit 0만으로 준비·중단 완료를 판단할 수 없어 health/readiness와 실제 PID·시작 tick·명령/port를 대조한다. 모르는 기존 worker를 인수하거나 중단하지 않는다.
- upstream `--daemon`은 DB 초기화/이전·queue/background 실행을 할 수 있다. manual profile의 autostart/transcript watcher 비활성화만으로 worker 실행 전체가 읽기 전용이 되지 않는다. 이 단계에서는 합성 프로세스로만 자체 연결 코드를 시험했다.
- entry pin·manifest는 전체 공식 출처·dependency closure·운영 ABI 검증이 아니다. 기존 설치/DB 이관·실제 제품 등록·공식 process supervision과 native 전체 조합은 G5/G7에 남긴다. OS 원자적 격리나 receipt의 보안 인증을 주장하지 않는다.
- 초기 시험에서 interpreter exec 전후 command hash가 바뀌어 정상 기동을 소유 실패로 보는 오류를 확인했다. 새로 시작한 같은 PID/시작 tick에 한해 준비 중 identity를 갱신하고 running 이후 drift는 거부하도록 보완했다. 초기6개 실패와 보완 후 결과를 구분한다.

## 검증 연결

[검증 기록](../verification.md)의 G4 절에서 source/합성 process·stdio/새 모델 사용/제품 native/운영 상태를 구분한다. 상세 로그·fixture·source/기존 파일 hash 대조는 로컬 `_bmad-output/g4-claude-mem-20261118/`에 보관한다. private의 common pin을 조용히 갱신하거나 이 source 작업을 통합 설치 완료로 바꾸지 않는다.
