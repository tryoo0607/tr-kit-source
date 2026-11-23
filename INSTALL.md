# 패키지 검토·격리 설치·복귀

## 패키지 상태

- 소스 구조는 common/base·adapters·scripts를 유지한다. 외부 본문·runtime은 포함하지 않는다. native manifest는 제품이 지원하는 skill 경로를 직접 선택한다.
- `scripts/package.py build`는 명시 product/version/profile·catalog/scope/providers로 새 출력 하나를 만든다. source 밖 output과 모든 실제 입력·산출물을 scope에 등록해야 한다. `verify`는 현재 전체 파일/hash와 Gitleaks를 다시 검사한다. 자체 명세 일치는 서명·공식 출처 인증이 아니다.
- `review`: SessionStart를 통해 자체 공통 원칙을 전달하는 검토용. secret/upstream 가드의 native 등록은 포함하지 않는다. 운영용 보호가 준비됐다고 판단하지 않는다.
- `guarded`: 기존 secret/upstream hook을 제품별로 함께 등록한다. secret scanner는 기존 pin/receipt가 필요하다. upstream은 아래 호스트 runtime 연결에서 선택한 binding 파일의 정확한 `root`, `catalog`, `scope` canonical 절대 경로를 사용한다. binding 부재·오류는 Pre에서 명시 deny, Post에서 실패를 보고한다. 등록 전 실제 scope·scanner·native event/신뢰를 검증한다. review로 다시 만들기를 보호 우회로 사용하지 않는다.
- G4의 MCP template는 비활성 source 자료로 유지한다. runtime/data 경로·공식 출처/resources를 확인하지 않은 채 `.mcp.json`을 생성하거나 worker를 시작하지 않는다. 별도 G4/G7 준비와 native 연결 검증이 필요하다.

## 공식 설치·제거 수단

### 호스트 runtime 연결

- 제품별 기본 설정은 `~/.config/tr-kit/runtime-codex.json` 또는 `runtime-claude.json`이다. 명시한 `TR_KIT_RUNTIME_CONFIG`가 있으면 그 파일만 선택하며 오류 시 기본 파일로 대체하지 않는다. 기존 프로젝트 설정 `config.toml`과는 별개다.
- 설정은 현재 사용자 소유의 일반 파일이어야 하며 group/world 쓰기와 symlink를 허용하지 않는다. 모든 경로는 canonical 절대 경로다. 예시의 경로는 실제 공식 설치·검수 후 해당 호스트에 맞춰 정한다.

```json
{
  "schema_version": 1,
  "product": "codex",
  "providers": "/absolute/providers.json",
  "provider_reviews": {"sample": "/absolute/reviews/sample.json"},
  "upstream_binding": "/absolute/upstream-binding.json"
}
```

- SessionStart는 공통 원칙과 위 설정·provider 선언 위치만 전달한다. 전체 provider 본문·검수 기록을 주입하지 않는다. 선택한 provider는 기존 resolver/provider-review로 entry와 resource를 확인한다. 설정 파일 존재만으로 공식 설치·실행 성공을 주장하지 않는다.
- upstream hook은 명시한 `TR_KIT_UPSTREAM_BINDING`이 있으면 이를 우선하며, 없을 때만 runtime 설정의 `upstream_binding`을 사용한다. binding의 `root`, `catalog`, `scope`와 실제 scope에 등록한 kit component/artifact가 보호 대상이다. 새 worktree와 다른 프로젝트를 자동 등록하지 않는다. 잘못된 명시 binding을 다른 설정으로 대체하지 않는다.
- 설정이 없거나 잘못되면 시작 context는 not-ready, upstream Pre는 deny를 반환한다. 활성화 전에 실제 호스트 설정과 공식 provider, 대상 scope·scanner 및 제품별 callback을 검증한다. 셸 설정·실행기 수정이나 개인 자료 수집은 이 연결에 포함되지 않는다.

- Codex: [공식 패키징 문서](https://developers.openai.com/plugins/build/plugins)와 현재 `codex plugin --help`를 따른다. `plugin marketplace add <package>` 후 `plugin add tr-codex@tr-codex`; 제거는 `plugin remove tr-codex@tr-codex`와 해당 `plugin marketplace remove tr-codex`다. hook trust는 native UI에서 검토한다. 신뢰 DB 편집·Trust all 자동 수행은 하지 않는다.
- Claude: [공식 plugin CLI](https://code.claude.com/docs/en/plugins/cli-reference)의 `plugin marketplace add <package>`, `plugin install tr-claude@tr-claude --scope user`를 따른다. 제거 시 `plugin uninstall ... --scope user --keep-data`로 data 보존을 명시한다. marketplace 제거와 runtime/data 제거는 다르다.
- 설치/갱신한 파일·등록 상태, hook trust, 새 세션의 초기 지침·실제 native callback/차단과 공식 업무 실행은 별도로 확인한다. root CLAUDE.md/AGENTS.md 파일 존재를 초기 주입 근거로 사용하지 않는다.

## 이번 G5의 격리 실행기

`scripts/plugin-lifecycle.py`는 새 임시 prefix의 독립 home/제품 설정만 관리한다. 기존 사용자 home/config에 설치하는 기능이 아니다. `install/update/remove/rollback`의 기본 동작은 계획 출력이다. 현재 package/CLI/receipt 파일·hash만 조회하며 scanner·native CLI 실행이나 임시 파일 생성은 하지 않는다. 계획에는 비밀 검사가 미실행임을 표시한다. 실제 실행은 `--apply --expect-plan <plan_id>`로 한정하고, prefix 생성/설정 변경 전에 Gitleaks를 반드시 실행한다. 검사 실패를 정적 확인으로 대체하지 않는다.

- install: 새 prefix만 허용하고 native manager로 등록/설치한다. source 밖 검증된 package를 그대로 사용한다.
- update: 해당 prefix의 managed installed receipt와 새 package를 대조한다. 기존 package는 보존하고 제거→marketplace 교체→설치한다. native 캐시의 payload hash를 대조한다.
- rollback: 직전 보존 package를 다시 fresh 검사하고 공식 manager로 재설치한다. 기존 세션 context·외부 provider·실자료/worker를 복원했다는 뜻이 아니다.
- remove: 공식 manager로 plugin/marketplace만 제거하고, 같은 제품의 plugin list --json에서 대상 등록의 부재를 확인한다. 목록 부재/오류·알 수 없는 형식·대상 잔존은 완료로 보지 않는다. 제품이 보존한 version cache는 cache_retained로 별도 보고하며 강제 삭제하지 않는다. prefix의 기록·원래 package·개인 데이터·worker·timer를 삭제하지 않는다.
- 실패: 완료한 단계와 partial receipt를 남기며 성공으로 보고하지 않는다. partial 상태에서 같은 설치를 맹목 재전송하지 않는다. 관측과 native 상태에 따른 복귀 계획을 따로 검토한다. 조용한 자동 정리·force·개인 파일 덮어쓰기는 없다.

## 전송·CI와 운영 경계

`scripts/delivery.py`는 현재 package 검사 전용이며 push하지 않는다. CI도 검사 전용이며 배포 key·secret·SSH·원격 저장소 push가 없다. 운영 전송·기존 호스트 설정 변경과 전체 README 재작성은 이 단계에 포함하지 않는다. 기존 private의 common pin·native 통합은 별도 확인 대상이다.
