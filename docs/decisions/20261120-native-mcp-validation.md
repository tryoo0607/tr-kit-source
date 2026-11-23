# Claude-Mem의 제품 native MCP 등록·연결 검증

## 요청과 범위

사용자가 다음 MCP 실제 등록·연결 검증에 “ㅇㅇ ㄱㄱ”로 진행을 요청했다. 기존에 공식 설치·직접 stdio 검증한 Claude-Mem15.2.1과 현재 검증한 공통 native payload를 재사용했다. 운영 설정·실제 개인 DB·인증 복사·원문 변형·자료 수집·Wiki capture·배포는 제외했다.

이번에는 kit 구현·adapter·hook·provider pin·private 역할을 수정하지 않았다. 격리 binding/config·새 data/state·시험 실행기·필수 runtime 준비와 결과 기록만 추가했다. 기존 공통516개/private115개 회귀를 이번에 재실행한 것으로 세지 않는다.

## 재사용한 연결과 실제 구성

- 공통 `scripts/claude-mem.py`와 `common/base/scripts/claude_mem.py`, 양 제품의 기존 MCP template을 그대로 사용했다. 제품 등록과 worker 실행은 별개라는 기존 계약을 유지했다.
- 공식 설치본은 기존 manager가 준비한 revision `d9b36b66dc68da92af9df238e4c4debab587ba62`다. entry·리소스·설치 근거·제품 검수 기록을 실행 전후 재확인했다. 외부 MCP 서버/worker를 kit 안에 복제하지 않았다.
- 공통 native0.0.0-private-link.20261120.2의 전체 payload bytes를 시험 전후 명세와 대조했다. Codex는 앞선 공식 manager의 cache, Claude는 local marketplace의 실제 release root를 사용했다.
- [OpenAI Docs MCP 설정](https://learn.chatgpt.com/docs/extend/mcp?surface=cli)과 [app-server](https://learn.chatgpt.com/docs/app-server), [Claude MCP 등록](https://code.claude.com/docs/en/mcp)의 공식 기능을 사용했다. 실제 Codex0.167.2의 생성 schema도 대조했다.

```text
Codex 격리 config.toml / Claude 세션 --mcp-config
  → 설치된 공통 native payload의 claude-mem.py mcp
  → 기존 provider·review·runtime·소유 연결 검사
  → 공식 Node MCP stdio 서버
  → 명시한 loopback worker (자동 시작 꺼짐)
  → 새 시험 DB / 공식 Chroma MCP·선택 Python runtime
```

Codex는 기존 격리 prefix에서 공식 `mcp add/list/remove`로 등록을 확인했다. app-server의 실제 `mcpServerStatus/list`·`mcpServer/tool/call`을 사용했고 모델 호출은 하지 않았다. Claude Code2.1.329는 기존 격리 공통 plugin을 로드하고 생성한 명시 MCP JSON을 세션에 연결했다. localhost의 합성 모델 응답이 도구를 선택했지만, 실제 제품·공식 MCP/worker·공통 hook은 그대로 실행했다. 합성 API를 실제 모델의 선택·업무 능력 증거로 세지 않는다.

## 초기 발견과 격리 환경 보완

처음 양 제품에서 MCP19개 도구와 호출 자체는 연결됐다. 그러나 검색 응답은 Chroma 의미 검색 실패·FTS5 키워드 대체를 알렸고 검색 이후 worker health도 degraded였다. 초기 ready를 의미 검색의 성공으로 확대하지 않았다.

실제 로그는 `No interpreter found for Python 3.13`과 Python downloads=never를 원인으로 남겼다. 기존 manual worker 환경의 자동 다운로드 금지를 끄거나 Chroma 기능을 비활성으로 바꾸지 않았다.

[uv 공식 관리 기능](https://docs.astral.sh/uv/guides/install-python/)으로 별도 시험 경로에 정확한 Python3.13.9를 준비했다. uv가 선택한 배포는 Astral python-build-standalone이며 CPython 자체가 제공한 바이너리라고 주장하지 않는다. 설치 명령에만 manual 다운로드 정책을 적용하고 `--no-bin`으로 전역 실행 링크 생성을 막았다. worker 환경은 계속 never다. 시험 controller의 `bin/python3.13`만 선택 설치본에 연결했다. 이는 시험 준비이며 운영 Python 준비·설치 절차를 인증한 결과가 아니다.

공식 worker가 사용하는 기존 명령 그대로 `chroma-mcp==0.2.6`·`chromadb==1.5.9`·`onnxruntime>=1.20`·`protobuf<7`·`pydantic<2.14`의 uvx 환경을 각 시험 cache에 준비했다. source pin이나 외부 원문을 고치지 않았다. Python·도구 identity와 실제 설치 결과는 로컬 증거에 보존했다. 전이 의존 전체를 별도 lock으로 동결한 검증은 아니다.

Claude 첫 실행은 `--allowedTools`가 뒤의 프롬프트를 값으로 읽는 시험 입력 오류였다. 별도 negative 첫 실행도 가변 인자 `--mcp-config`의 같은 문제였다. 모두 모델/서버 실행 전 오류로 보존하고 `--`로 인자를 구분한 새 실행과 분리했다. Python 첫 명시 설치는 never 정책에 거부돼 보존했고, 명시 설치만 허용하는 manual로 설치한 뒤 worker의 never를 유지했다. 검사 실패를 kit 결함이나 통과로 집계하지 않는다.

## 최종 실제 관측

| 검사 | Codex | Claude |
| --- | --- | --- |
| 공식 native MCP 연결·도구 발견 | connected·19개·15.2.1 | connected·19개 |
| worker 부재 시 search | MCP 오류 반환·자동 기동 없음 | MCP 오류 반환·자동 기동 없음 |
| 명시 시작 후 search/timeline/get_observations | 3호출 정상 반환 | 3호출 정상 반환 |
| 실제 Chroma 연결 | 공식 stdio 연결 성공 로그 | 공식 stdio 연결 성공 로그 |
| 빈 DB search 응답 | No results found, 대체 검색 경고 없음 | No results found, 대체 검색 경고 없음 |
| client 종료 후 worker | 같은 소유 worker·ready 유지 | 같은 소유 worker·ready 유지 |
| 공식 명시 stop·포트 해제 | stopped·absent/owned=false | stopped·absent/owned=false |
| 존재하지 않는 binding | native handshake 실패·도구0개 | native failed·도구0개 |

Claude의 실제 공통 hook 응답은 SessionStart1·PreToolUse4·PostToolUseFailure2·PostToolUse6개였고 비정상 종료는 없었다. worker 부재 검색의 MCP 오류와 hook 자체 실패를 구분했다. Codex의 직접 app-server 호출을 모델 turn의 hook 조합 시험으로 확대하지 않는다.

빈 DB와 조회 호출만 시험했다. 자료가 있는 검색의 정확도·순위·embedding 품질·관측 저장/AI observer·transcript 수집을 검증하지 않았다. get_observations의 빈 ID 목록 응답도 실제 자료 조회 성공으로 확대하지 않는다.

## 정리와 현재 상태

Codex 시험 등록을 공식 remove로 제거하고 native list가 비었음을 확인했다. 기존 격리 config의 TOML 의미도 이전과 같았다. Claude 등록은 세션의 명시 JSON뿐이었으며 세션 종료로 끝났다. 소유 worker stop 후 두 포트가 닫혔고 시험 경로/MCP entry에 해당하는 실행 프로세스 잔존은 없었다. 원문·공통 native payload·private 역할 hash는 유지됐다. 운영 설정·plugin 등록·trust·shell profile·서비스/timer·원격 서버를 변경하지 않았다.

증거 정본은 `/data/projects/_scratch/tr-kit-mcp-native-validation-20261120/`다. assessment.json·제품별 native-summary/status/events·invalid 판정·registration-cleanup·final-process-check와 runtime 준비 기록이 있다. 초기 의미 검색 degraded 결과와 인자 오류도 별도 보존했다. 상세 입력/출력·DB·cache는 배포물에 넣지 않는다.

이번 범위의 **native 등록·연결·빈 fixture 조회·실패 처리·수명 관리**는 확인했다. 실제 모델의 MCP 선택·자료 업무, 자연 발동·압축/재개, 선택 REA·Wiki 실수집, 운영 전 전체 감사·배포는 별도다. 이후 운영 준비에서는 이 시험의 Python/Chroma 전제를 실제 대상별로 명시 준비·검증해야 하며 native 패키지 설치만으로 충족됐다고 보지 않는다.
