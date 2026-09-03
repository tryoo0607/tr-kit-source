---
name: profile-setup
description: tr-kit의 non-secret 로컬 연결을 설정·점검할 때 발동 — "career/knowledge 저장소 연결", "handoff 경로 설정", "dive 자동 제안 켜기", "profile.d doctor". read-only plan을 먼저 보여주고 승인된 managed profile만 변경한다.
---

# profile-setup

public skill이 사용하는 로컬 repo 경로와 선택 기능을 설정한다. plugin root의 `profile/setup.py`를 사용하며 source나 data repo에 실제 값을 쓰지 않는다.

## 절차

1. `profile/setup.py plan` 또는 필요한 key만 `plan --key <key>`로 점검한다.
2. 경로와 profile diff를 사용자에게 보여준다.
3. 사용자가 승인한 값만 `apply --yes --key <key> --set <key>=<value>`로 적용한다.
4. `doctor --required-by <skill>`로 해당 skill에 필요한 연결을 검증한다.

경로를 자동 추측하거나 repo를 clone·생성하지 않는다. 그런 변경이 필요하면 대상과 영향을 따로 설명하고 승인받는다.

## 경계

- `50-tr-kit.toml`만 관리한다. `90-local.toml`, unmanaged file, symlink는 수정하지 않는다.
- token·password·SSH key·IP·hostname과 개인 학습/상담 상태는 profile에 넣지 않는다.
- profile이 없어도 plugin 설치와 경로 비의존 skill은 정상 동작해야 한다.
