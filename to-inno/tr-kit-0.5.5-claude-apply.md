# tr-kit 0.5.5 — 회사 Claude 적용 인계

## 목적

`tr-claude` 0.5.5를 회사 머신에 적용한다. NAS에는 설치하지 않는다. 실행 전 현재 세션과 systemd 상태를 읽기 전용으로 확인하고, 재시작이 필요한 단계는 사용자에게 대상과 영향을 보고한 뒤 진행한다.

## 이번 결정

- `tr-kit-source`에 legacy `setup/bin`, systemd unit, `dotclaude` 배치 계층을 이관하지 않았다.
- `claude-remote`, `claude-auth-check`, `claude-skillflow`, `local-docs-backup`은 앞으로 사용하지 않으므로 plugin의 호출·운영 문서 의존을 제거했다.
- local-docs는 `~/projects/_docs/`를 포함하는 Git 저장소의 일반 commit·push 흐름으로 관리한다. 별도 backup binary·cron을 설치하지 않는다.
- `dotclaude`의 settings·statusline·alias·session data는 사용자 로컬 상태이므로 plugin이 덮어쓰거나 회수하지 않는다.
- Happy 관련 patch·launcher·daemon은 PolyGarden 전환 전까지만 기존 회사 머신 상태로 유지한다. kit에 영구 host 계층이나 stable plugin pointer를 추가하지 않았다.

## 적용 전 확인

1. `claude plugin list`에서 현재 marketplace 이름, enabled 상태, 설치 version을 확인한다.
2. `systemctl --user status happy-daemon.service`와 unit/drop-in 경로를 확인한다.
3. `~/.local/bin` 및 `~/.config/systemd/user`에서 legacy `tr-claude/setup`을 가리키는 link를 목록으로만 확인한다.
4. legacy clone은 아직 pull·삭제하지 않는다. Happy 전환 전 link와 unit이 끊길 수 있다.

## plugin 적용

1. marketplace를 갱신하고 `tr-claude@tr-claude`를 0.5.5로 update한다.
2. `claude plugin list`와 cache manifest에서 installed/enabled/version `0.5.5`를 확인한다.
3. 일반 Claude CLI 세션은 `/reload-plugins`를 우선 사용한다. 실패한 세션만 idle 여부를 확인한 뒤 정상 restart/resume한다.

## Happy 임시 적용

Happy Agent SDK host는 marketplace 경로를 자동 해석하지 않는다. 현재 Happy patch가 SDK의 local plugin option을 받는 동안에만 아래 임시 우회를 사용한다.

1. 설치 cache에서 실제 `tr-claude` 0.5.5 plugin directory를 확인한다. 경로를 추측하지 않는다.
2. legacy unit 본문을 수정하지 말고 `happy-daemon.service`의 systemd user drop-in에서 다음을 설정한다.

   ```ini
   [Service]
   Environment=HAPPY_PLUGIN_DIRS=<확인한 0.5.5 plugin directory>
   Environment=HAPPY_SETTING_SOURCES=user,project,local
   ```

3. 변경 diff와 영향받는 Happy 세션을 사용자에게 보고한다.
4. 승인 후에만 `daemon-reload`와 Happy daemon restart를 수행한다.
5. 기존 Happy/Claude 세션은 idle 상태를 확인해 순차 restart/resume하고, skill·hook이 0.5.5에서 로드됐는지 canary 한 건으로 먼저 확인한다.

## 0.5.5 canary

- 읽기 전용 명령의 `2>/dev/null`이 change marker를 만들지 않는다.
- 실제 파일 redirection은 여전히 change marker를 만든다.
- Codex 설치는 이 회사 Claude 적용 범위 밖이다.

## PolyGarden 전환 후 정리

1. Happy 세션 종료와 daemon disable을 먼저 확인한다.
2. Happy systemd drop-in과 Happy 전용 link·unit을 제거한다.
3. 더 이상 쓰지 않는 legacy bin link를 제거한다. 사용자 settings·statusline·session data는 건드리지 않는다.
4. 끊어진 link와 실행 중 unit이 없음을 확인한 뒤에만 legacy clone 삭제를 별도로 승인받는다.

## 금지

- legacy clone을 먼저 pull하거나 삭제하지 않는다.
- `settings.json`, statusline, alias, session data를 plugin 설치 과정에서 덮어쓰지 않는다.
- `Permissions shown in terminal only...` 배너를 tr-kit 문제로 수정하지 않는다.
- Happy 임시 우회를 일반 host 배치 기능으로 확장하지 않는다.
