# Claude-Mem 공식 실행기 연결

## 적용 범위와 경계

- MCP 연결 준비·진단 또는 worker 시작·중단을 명시적으로 요청한 경우만 이 안내를 읽는다. 경험 검색은 기존 [mem-search](../skills/mem-search/SKILL.md)와 공식 검색 skill이 소유한다. 검색 실패를 설치·시작·자료 수집 승인으로 확대하지 않는다.
- `scripts/claude-mem.py`는 kit 자체 연결·수명 관리 코드다. 외부 서버·검색/DB 엔진·공식 loader를 복제하거나 수정하지 않는다. 공식 설치본의 MCP stdio entry를 직접 실행한다.
- source 기준은 Claude-Mem **15.2.1**, revision `d9b36b66dc68da92af9df238e4c4debab587ba62`다. [공식 package](https://github.com/thedotmack/claude-mem/blob/d9b36b66dc68da92af9df238e4c4debab587ba62/package.json), [worker](https://github.com/thedotmack/claude-mem/blob/d9b36b66dc68da92af9df238e4c4debab587ba62/src/services/worker-service.ts), [MCP 서버](https://github.com/thedotmack/claude-mem/blob/d9b36b66dc68da92af9df238e4c4debab587ba62/src/servers/mcp-server.ts)를 기준으로 한다. 다른 버전은 호환성을 검토한 뒤 지원한다.

## 입력과 사전 확인

- 명시 binding JSON 파일 하나를 사용한다. 기본 경로 탐색·호스트 설정 병합·원격 fallback은 없다.
- 새 실행용 필드: `schema_version: 2`, `providers`, `node`, `bun`, `data_dir`, `state_dir`, `port`, `profile: "manual-local-worker"`, `reviews`.
  - `reviews`는 `claude-mem-mcp`, `claude-mem-worker` 각각을 명시 [설치본 검수](provider-review.md) 기록의 canonical 절대 경로에 연결한다. plan에 기록 hash를 포함하고 start/MCP 실행 직전에 entry·설치 리소스·근거·제품 검수를 다시 대조한다. 미결·누락·drift는 data/state 생성과 외부 실행 전에 보류한다.
  - 기존 schema1은 plan/doctor/render·health와 소유 worker의 stop 검사를 유지하지만 새 start/MCP는 허용하지 않는다. schema 숫자만 바꾸거나 검수 상태를 자동 승인해 전환하지 않는다.
  - 파일·디렉토리·실행 파일 경로는 canonical 절대 경로다. data/state는 서로 분리하고 source/공식 설치본 밖의 기존 parent 아래에 둔다.
  - `providers`는 [공통 외부 연결](external-connection.md) 규격이다. `claude-mem-mcp`, `claude-mem-worker` 두 CLI entry를 같은 공식 설치본의 `scripts/mcp-server.cjs`, `scripts/worker-service.cjs`로 명시한다. 지원 제품·15.2.1·entry hash를 기록한다.
  - Node와 Bun은 명시 실행 파일을 선택한다. 지원 버전은 pin 파일의 Node engine·Bun minimum을 따른다. metadata 진단과 실제 runtime 버전 실행을 구분한다.
  - schema2에는 선택 `claude_bin` 디렉토리를 명시할 수 있다. 이 디렉토리의 공식 `claude` launcher가 가리키는 실행 파일을 hash로 묶고 실행 전 identity를 대조한다. 선택한 디렉토리만 격리 PATH에 추가하며 호스트 PATH·shell 설정·인증을 복사하지 않는다. 공식 npm의 launcher symlink는 실제 대상으로 해석해 확인한다. 이 입력은 Claude observer의 CLI 부재를 해결할 수 있지만 로그인·AI 작업 성공을 보장하지 않는다. Node/Bun의 기존 경로 계약은 유지한다.
  - `port`는 1024~65535 중 선택한 loopback 포트다. 기본 포트나 기존 worker를 자동 발견하지 않는다.
- entry hash·manifest 일치는 공식 배포 출처·전체 resource·실제 동작 인증이 아니다. 실행 전에 공식 설치 관리 수단·취득 revision/버전·의존 resource를 별도로 확인한다. 비교용 checkout·구 kit 동봉본을 실행 provider로 쓰지 않는다.

## 동작과 실제 효과

공통 명령 형식: `python3 <kit>/scripts/claude-mem.py <action> --root <kit> --binding <file> --product codex|claude`.

| action | 실행·변경 효과 | 결과와 경계 |
| --- | --- | --- |
| plan | binding·entry·manifest·runtime 파일 hash만 조회 | 실행 효과·connection_id·plan_id. 외부 실행·data/state 생성 없음 |
| doctor | plan과 같은 정적 확인 | `entry-pinned`는 실제 worker/MCP 준비 완료가 아님 |
| render | 제품별 native 설정 fragment를 stdout으로 출력 | native 파일 저장·등록·활성화 없음. 출력 저장은 승인된 위치에서 별도 수행 |
| health | 명시 loopback 포트의 `/api/health`와 `/api/readiness`, 소유 receipt·Linux process 확인 | ready/ warming/degraded/absent/unverified와 owned 구분. ready+owned만 exit 0. 서버 응답 원문을 출력하지 않음 |
| start | 검토한 `--expect-plan <plan_id>` 필요. 새 data/state와 marker·log·receipt 생성, 공식 worker `--daemon` 실행 | 초기화/DB migration·upstream background 작업이 생길 수 있다. exit 0만으로 성공 판단하지 않고 endpoint·PID/start tick/명령 hash·readiness 대조 |
| stop | 같은 plan 확인 필요. 소유한 worker만 공식 `stop` 실행 | upstream 종료 코드와 실제 process 종료·port 해제를 별도로 확인. 실패 시 강제 종료·다른 worker 정리 없음 |
| mcp | 선택 data/state·설정/로그 생성 가능, 공식 stdio server를 Node로 직접 exec | worker 자동 시작과 transcript watcher를 끈 manual profile. 검색만으로 worker 시작·기존 DB 인수·전체 대화 수집을 하지 않음 |

- 새 연결의 data/state는 자체 connection marker로 구분한다. marker 없는 기존 디렉토리·기존 worker를 자동 인수하지 않는다. 기존 DB 연결/자료 이관은 이 source 구현으로 완료되지 않았다.
- `claude_bin` 같은 실행 의존의 선택이 바뀌면 connection_id도 달라진다. 기존 data/state를 자동 인수하거나 marker를 덮어쓰지 말고 새 시험 연결을 사용하거나 승인된 데이터 전환 절차를 별도로 확인한다.
- `manual-local-worker`는 별도 연결의 autostart와 transcript watcher를 끄는 profile이다. 기존 호스트 profile을 편집하거나 Chroma/cloud/observer 설정을 임의로 바꾸지 않는다. 명시 worker 시작은 upstream의 DB/queue 처리·의존 기능을 실행할 수 있으므로 자료·연결·외부 접근 영향을 승인 범위에 포함한다.
- 원래 caller cwd를 유지해 project 문맥을 전달한다. worker 관리용 cwd는 선택 state다. 호스트의 credential/env 전체를 복사하지 않는다. 기능에 필요한 별도 인증·의존 자원이 없으면 미지원/미준비로 보고하고 자동으로 끌어오지 않는다.
- lifecycle은 Linux process metadata로 소유를 확인한다. receipt는 로컬 추적 증거이며 적대적 프로세스나 filesystem 변경을 막는 OS 보안 경계가 아니다. port 사전 확인과 실행 사이의 경쟁·upstream 자식 프로세스 동작까지 원자적으로 통제하지 않는다.
- 기동 실패 시 생성한 PID/receipt/log를 남기고 성공으로 보고하지 않는다. 자동 재시작·기존 PID 회수·임의 reset·데이터 삭제 기능은 없다.

## 제품별 등록과 미검증

- Codex는 [공식 MCP 설정](https://learn.chatgpt.com/docs/extend/mcp?surface=cli)의 TOML fragment를 생성한다. 생성값은 `enabled = false`이며 켜기 전 native 검증·승인 범위를 확인한다.
- Claude는 [공식 MCP 설정](https://code.claude.com/docs/en/mcp)의 `mcpServers` stdio JSON을 생성한다. 지원 근거 없는 `enabled` 필드를 넣지 않는다. `.in`은 미등록 source이며 실제 등록하면 MCP 연결이 시도된다. worker autostart false와 MCP 비활성화는 다르다.
- 이 source 단계의 합성 worker/MCP 시험은 연결 코드·입출력/실패 경계 검증이다. 공식 runtime 실동작·제품 native 등록/도구 노출·기존 개인 자료 검색·실제 background 효과의 검증을 대신하지 않는다. 그 상태는 docs/verification.md와 후속 G5/G7에서 구분한다.
