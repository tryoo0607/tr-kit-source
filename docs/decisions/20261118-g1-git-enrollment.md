# G1: 명시 Git 등록과 예외 범위 강제

2026-11-18. R-32의 scratch 구현·검수 기록. 실제 운영 저장소 등록·배포는 하지 않는다. 후속 도입 구상은 R-33 및 migration-status.md에서 관리한다.

## 범위와 재사용

- 기존 자체 git-guard-install의 snapshot·original hook 보존·전후 검사·복귀 개념을 재사용한다. 새 secret_guard와 CLI를 연결하며 외부 Gitleaks는 공식 설치 경로/receipt/pin/hash를 검증해서 사용한다. 바이너리·외부 원문을 복제하지 않는다.
- plugin-authoring의 kit/hook 작성·감사, shared 구성·흐름·행동 시험 기준과 공식 system skill-creator를 적용한다. BMAD의 `_bmad` renderer는 scratch 또는 상위 디렉토리에 없고 공식 build workflow를 실행하지 않았다. kit 고유 연결 저작을 BMAD 실제 수행 완료로 표시하지 않는다.
- 등록 관리기는 명시 repo·신규 state·scanner를 받는다. plan은 파일을 쓰지 않고 공개 hash를 반환한다. CLI apply는 같은 입력과 reviewed plan_id를 요구하며 다른 계획이면 변경하지 않는다. 같은 승인 범위의 재승인 단계로 강제하는 장치가 아니다.
- 관리 상태는 worktree·Git directory·hooks 밖에 둔다. 자체 코드 사본과 정책만 보존한다. Python과 공식 scanner는 외부 의존이다. 기존 관리자/symlink/점유 backup/state는 거부하며 global/local Git 설정을 바꾸지 않는다.
- `_bmad-output/**` 예외는 실제로 선택한 `tr-local-docs` Git root와 정확한 디렉토리 suffix로 제한한다. 등록 CLI뿐 아니라 직접 정책 검사에도 적용한다. 이름은 신뢰/소유/공유 권한의 증명이 아니며 원격과 자료 공개 범위는 별도 확인 대상이다. 예외 파일도 비밀 검사는 계속한다.

## 예정 배치와 실행

```text
common/base/scripts/
  secret_guard.py             공통 정책·공식 scanner receipt 검증
  git_guard_install.py        등록·상태·복귀·hook 실행
scripts/
  git-guard-install.py        명시 CLI
  check-git-secrets.py        기존 index/outgoing 검사
tests/
  test_git_guard_install.py   임시 repo·로컬 bare remote 시험
```

```text
명시 repo/state/scanner → plan → 입력/plan_id 대조 → apply
Git pre-commit/pre-push → wrapper → 등록된 root일 때 공통 비밀·산출물 검사
                        → 기존 hook(있고 실행 가능할 때)
                        → 기존 hook 성공 후 공통 재검사(등록 root만)
status → receipt/설정/파일 대조 → 충돌 보고
rollback → 사전 대조 → 소유 변경 복귀(충돌이면 덮어쓰지 않음)
```

정상 runtime에서 shared hooks를 쓰는 다른 worktree는 새 정책에 자동 등록하지 않고 원래 hook 실행만 유지한다. runtime/Python/receipt 등 공유 의존이 깨진 경우 미등록 worktree까지 차단될 수 있으므로 공유 경로 변경 전에 그 영향을 확인해야 한다. pre-push argv와 stdin은 두 검사와 기존 hook에 그대로 전달한다. 기존 hook 실패는 유지하며 내용/실행 mode를 보존한다. 기존 hook이 staged 파일을 변경했으면 재검사로 차단하지만 변경 자체를 자동으로 되돌리지는 않는다.

## 실패·복구와 한계

신규 state와 hooks의 배타 lock으로 동일 관리기의 동시 변경을 제한한다. 의존 파일·backup을 먼저 쓰고 wrapper는 마지막에 활성화한다. write journal과 원래 bytes/mode를 남겨 부분 실패 시 소유 변경을 복귀한다. 사후 편집·설정 변경·symlink 충돌은 강제 덮어쓰지 않고 보고한다. 기존 hook 원문 snapshot을 포함한 receipt는 로컬 전용이다.

이 제어는 OS 쓰기 통제나 악의적 소유자의 우회 방지가 아니다. 다른 프로세스와 Git 실행 전체를 원자적으로 잠그지 않으며 전원 단절/강제 kill 순간의 완전 복구를 보장하지 않는다. 알려진 manager는 거부하지만 임의 hook의 자체 경로/파일명 의존까지 호환을 보장하지 않는다. 실제 Codex/Claude trust·native 이벤트와 운영 저장소 연결은 후속 통합 검증이다. 이번 변경으로 common source hash가 달라지므로 private common pin은 실제 통합 전 명시 갱신·재검증해야 하며 이번에 조용히 완화하지 않는다.

Git 공식 [githooks](https://git-scm.com/docs/githooks)·[core.hooksPath](https://git-scm.com/docs/git-config#Documentation/git-config.txt-corehooksPath)의 실행 위치·인자/stdin·비실행 hook·경로 규칙을 참고했다. 정적 설명과 임시 Git 직접 실행의 결과는 docs/verification.md에서 구분한다.
