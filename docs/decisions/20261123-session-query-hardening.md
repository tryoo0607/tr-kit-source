# 세션 조회 제한과 같은 응답에 묶인 복원 증거

R-52의 승인 계획은 `_bmad-output/plan-session-query-hardening.md`다. 이번 변경은 격리 worktree의 공통 session helper·회귀 시험·계약 문서에 한정한다. 설치·배포·원격 실행·사용자 terminal 입력은 수행하지 않는다.

## 관측과 결정

- NAS Codex0.167.2의 기존 관측은 cold inventory 약60.01초(5초 측정 해상도), warm1.31초, 설치26개, stderr0바이트다. 원본은 로컬 `/data/projects/_scratch/tr-kit-session-rollout-20261123-ec2049b415/nas-diagnosis-summary.json`이다. 이 값은 모든 환경의 최대 지연·출력 크기 측정이 아니다.
- 원래 보안 재현은 exit0/stderr 경고의 부분 목록 수용(SQ-01), 마지막 설치 대기 중 나타난 같은 UUID의 중복 생성(SQ-02)이다. 원본은 `/data/projects/_scratch/tr-kit-query-security-20261123-9bab636a63/`의 report/probes다.
- 후속 round1/2 재현은 같은 pane에서 신원이 바뀌어도 과거 응답과 나중 화면 proof를 결합한 경우와 포화 stderr가 deadline을 막은 경우다. `/data/projects/_scratch/tr-kit-query-release-0.8.2-a230161ef5/review-round{1,2}*`의 원본은 수정하지 않는다.
- [설계 판단] 관측한 약60초의 여유를 두어 Codex의 정확한 `plugin list --json`만180초로 정한다. Claude inventory와 그 외 native 명령은15초다. 설치26개 같은 metadata에 충분한 여유를 두되 메모리를 제한하도록 stdout2,000,000바이트·stderr64,000바이트를 선택한다. stderr의 비어 있지 않은 내용은 전부 미확인으로 처리한다. 설치 JSON의 최대 크기를 실측했다는 의미는 아니다.

## 실제 흐름과 보존 계약

파일 배치와 역할은 유지한다. `runtime_refresh.py`가 두 helper의 native runner·status·guard를 소유하고, `session_restart.py`가 기존 durable batch·선택·복원 판단을 연결한다.

```text
native inventory → 시간/양 pipe 제한·진단 거부 → 설치 snapshot
명시 선택 → fresh 설치/full guard → /status
  → passive 응답 관측 → 최신 경계의 frame/stream 신원 동등성
  → 같은 frame의 cursor/화면 hash를 재관측으로 확인
부재 복원 → 선택 후보의 응답 증거 유지 → 마지막 설치 확인
  → fresh list/ps와 선택 pane proof 대조 → durable sending → create
  → create receipt 보존 → agent가 연 선택 Claude modal만 guarded cleanup
```

응답 대기에는 긴 설치 조회를 끼우지 않는다. 과거 status 뒤 새 startup/resume/다른 명령, 현재 신원 누락과 frame/stream 불일치는 미확인이다. 과거 delta나 status 뒤 새 baseline으로 proof를 대체하지 않는다. 새 명령·raw key마다 설치/full guard를 유지하며 작업 뒤 설치 drift 검사도 유지한다.

Claude 일반 status/prepare는 원 모달 proof를 guarded Esc 직전에 확인해 닫는다. 부재 증명에서만 agent가 선택 pane에 연 모달을 마지막 설치 조회와 passive 검증까지 유지한다. 생성/거부 결정 후 같은 runtime/self/설치/identity/상태와 정확한 원 proof로만 Esc를 한 번 보낸다. 변경·미확인 UI나 불명확한 key receipt는 수동 정리를 기록하고 이후 대상도 멈춘다. 닫힌 화면을 원 UUID의 proof로 쓰지 않는다.

진행은5초마다 phase/provider/경과초/제한초만 stderr에 보낸다. Linux FIFO/TTY는 독립 open-file description을 비차단으로 열어 한 번만 write하며 원 caller flags를 유지한다. full/closed/unwritable sink와 bounded write가 보장되지 않는 sink는 생략한다. queue/thread/비관리 process는 없다. stdout은 최종 JSON이다. native 자식은 DEVNULL stdin·별도 소유 group에서 실행하고 성공·실패 모두 그 group만 정리하며 leader 회수는 추가 최대2초다.

정확한 UUID/cwd/권한, self 제외, 명시 선택, 무재전송, 첫 실패 중단, durable receipt, refresh apply 시작5분 규칙과 만료 없는 restart batch는 유지한다. 미선택 pane의 screen은 읽지 않는다.

## 검증과 한계

실행 명령은 `python3 -B -m unittest discover -s tests -p 'test_session*.py' -v`이며158개가42.515초에 통과했다(skip0). `git diff --check`도 통과했다. 최신 결과와 source hash는 격리 worktree의 `_bmad-output/session-query-hardening-evidence/session-tests-round3-final.log` 및 `round3-summary.json`에 연결한다. 과거 round1/2 결과를 최종 source 검증으로 대체하지 않는다.

시험은 소유 transport/native CLI doubles와 실제 소유 subprocess를 사용한다. 15.2초 완료, timeout·양 출력 flood·잘못된 encoding/shape/중복·진단 sentinel redaction·group 정리·포화 stderr3회 반복과 FD/flags/thread 보존, whole apply 부분 inventory 거부, whole restore 마지막 조회 및 post-status 대기 신원 변경, stale stream/current frame·남은 과거 status 뒤 startup/다른 명령, Claude pre/post-Esc 변경을 실행한다. Codex와 Claude의 다중 선택 정상 restore는 실제 한 번 create와 나머지 already-running을 확인한다. 모달 유지·부분 실패 정리·changed UI 무입력·불명확 Esc 무재전송도 검사한다.

이는 소유 로컬 source 검증이다. 실제 native warm 조회, 전체 CI, 공통/private 패키지·pin과 commit은 root의 별도 범위이며 운영 반영·새 모델/native 이벤트·실제 reboot·플러그인 소비 검증으로 확대하지 않는다. Orca는 원자적 관측/compare-and-create API가 없어 마지막 passive 관측·로컬 기록·create 사이의 경합은 남는다. modal 정리 전에 UI가 달라지면 자동 입력을 중단하므로 수동 정리가 남을 수 있다.

## Root 후속 검증 — 최종 보완 뒤

- 마지막 독립 리뷰의 일반 prompt 경계·깊은 JSON 예외2건을 최소 수정하고 실제 재현·정상 보존3개 시험을 추가했다. 최종 전체 CI **627개, skip0**(session 161개 포함)가 통과했다. 앞의158개는 마지막 보완 전 관측이며 현재 전체 결과와 합산하지 않는다. 로그: `/tmp/tr-kit-query-hardening-ci-20261123-a230161ef5/tests.log`.
- 실제 dev01 Codex0.171.0 설치 목록 조회가56.403초에 observed(설치15개), 이어 재조회가1.139초에 observed였다. 캐시를 강제로 만료시키거나 CLI/설치를 갱신하지 않았다. 실제 pipe 진행 출력도 확인했다. 새 소유 Codex 창에서 현재 status·작업 경로·응답 proof와 설치 재조회 뒤 proof 일치를 확인하고 그 창만 close했다. 현재 요청 창은 유지했다. 실제 resume/reboot나 새 kit 소비 검증은 아니다.
- 세부 안전 metadata는 로컬 `/data/projects/_scratch/tr-kit-query-release-0.8.2-a230161ef5/final-code-validation.json`에 보존한다. dev01에 Claude CLI가 없어 이번 실제 상태 proof 검사는 Codex에 한정했다. Claude 모달·여러 선택 복원은 controlled transport 시험이며 실제 inno-desktop 검증과 구분한다. 새 패키지/pin·운영 적용 상태는 별도 후속이다.

## 배포물 준비 결과

공통 native0.8.2/private native0.8.3, source/native×양 제품8묶음을 새 출력에 준비했다. source 인터페이스에는 release version이 내장되지 않는다. 각 묶음의 현재 source byte·provider 선언·fresh 전송 가드·실제 Gitleaks와 private의 common pin4개를 대조했다. private129개 회귀도 통과했다. 최종 receipt는 `/data/projects/_scratch/tr-kit-query-release-0.8.2-a230161ef5/receipt.json`이다. inventory 항목 수는 common source153/native154, private source53/native54(제품별, 생성된 inventory 자체는 별도)이며 이전 묶음 대비 경로 추가·누락은 없다.

세 차례 독립 리뷰에서 발견한 보안·응답 결합·입력 경계/파서 오류는 실제 재현 또는 명시한 inspection 범위로 분류해 보완했다. 마지막 일반 prompt·깊은 JSON 수정은 root가 diff·추가3개 시험·전체627개·소유 native로 확인했으며, 최종 수정본에 대해 네 번째 독립 리뷰를 실행했다고 주장하지 않는다. 기존 게시물은 덮어쓰지 않았고 운영 배포·native 업데이트·실제 사용자 세션 재시작·새 kit 소비/재부팅은 실행하지 않았다.
