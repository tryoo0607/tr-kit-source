# Codex kit delivery

## 검증

생성된 plugin root에 `.codex-plugin/plugin.json`이 있어야 한다. manifest·skill·hook을 plugin validator로 검사하고 기존 오류와 이번 변경에서 생긴 오류를 구분한다.

## Local plugin 갱신

기존 marketplace entry가 현재 source를 가리키는지 먼저 확인한다. `marketplace.json`이나 Codex config를 손으로 고치지 않는다.

1. plugin-creator helper로 marketplace 이름을 읽는다.
2. `update_plugin_cachebuster.py <plugin-path>`로 기존 `+codex.*` suffix 하나만 교체한다.
3. `codex plugin add <plugin>@<marketplace>`로 재설치한다.
4. 새 thread에서 skill·hook을 확인한다.

기본 personal marketplace는 별도 `codex plugin marketplace add`가 필요 없다. 다른 marketplace 경로라면 설정 여부와 실제 local source를 먼저 확인하고, 이름을 추측하지 않는다.

Cachebuster는 기능 버전과 별개다. 반복 설치를 위해 숫자 version을 임의로 올리거나 suffix를 계속 이어 붙이지 않는다.

설치 cache 변경·재설치·새 thread 전환·외부 push는 현재 diff와 예상 영향을 먼저 보고하고 승인 후 수행한다.
