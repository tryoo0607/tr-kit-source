# 운영 runtime 연결 보완

- 사용자 승인: 호스트별 원문 보호 대상·공식 provider 연결을 보완·검증한 뒤 배포 계속. dev01/nas-vm Codex, inno-desktop Claude만 대상이며 private는 앞 두 호스트만 설치한다.
- 구조: 제품별 native 시작/도구 hook → 공통 runtime_config → 명시 호스트 설정의 provider 선언·선택 검수 기록·upstream binding. 실제 검사는 기존 resolver/provider-review와 upstream guard가 소유한다. 설정은 kit source·기존 프로젝트 config.toml과 별도다.
- 기본 위치와 schema·실패 처리는 INSTALL.md가 소유한다. 셸 설정·실행기·역할·wiki 수집·백업 timer를 변경하지 않는다. 공식 설치본은 kit 밖 고정 호스트 경로에 관리 도구로 설치하며 기존 검수본과 원문·리소스를 대조한다.
- 보호 scope는 실제 kit source component만 명시한다. 다른 업무 프로젝트·새 worktree를 자동 편입하지 않는다. 등록 catalog에 없는 변형의 의미적 탐지는 보장하지 않는다.
- 검증: runtime 설정9개(양 제품 경로 전달·실제 guard 정상/원문 복제/범위 밖·잘못된 설정 등)와 공통 전체525개 회귀 통과. dev01 공식 설치본47개 리소스가 이전 검수 기준과 일치했다. 아래 운영 적용 전까지는 원격 설정·실제 운영 배포·신뢰 승인·새 운영 세션 검증이 진행 중이었다. 초기 구현 결과와 이후 적용 결과를 구분한다.
- 기계 검증과 모델의 선택·준수는 구분한다. 기존 실제 모델 보고 분량 위반·자동 업데이트 미지원 등 잔여 한계를 없어진 것으로 처리하지 않는다.

## 운영 적용 결과 — 2026-11-23

| 대상 | 실제 설치·초기 전달 | 실행 확인·한계 |
| --- | --- | --- |
| dev01 Codex 0.167.2 | 공통0.8.0·private0.8.1, 새 SessionStart의 runtime pointer·개인 지침·development 역할 확인 | 실제 모델의 `printf` 출력과 exit0 확인. 이번 새 세션에서 hook 실패 보고 없음 |
| nas-vm Codex 0.167.2 | 같은 공통/private, runtime pointer·개인 지침·control 역할 확인 | 읽기 전용 시험의 exec_command가 `bwrap: loopback: Failed RTM_NEWADDR: Operation not permitted`로 exit1. 명령 미실행이며 권한 확대·가드 우회로 재시험하지 않음 |
| inno-desktop Claude 2.1.330 | 공통0.8.0만 설치, native SessionStart 성공·새 runtime path 확인 | 실제 모델 Bash `printf` 출력과 성공 결과 확인. 이번 새 세션에서 hook 실패 보고 없음. Codex·private 배포 비대상 |

- 게시한 공통은 Codex `79b9eb379f6c9a6eedc3a1b5648de47e4759c5d8`, Claude `acc7ceaf02595587c859b3f74668e7b79c9b07e2`다. 검증한 source `49597935307457e12097485d023fa90a0ef8e1d6`과 main `14ae6f07da2734cd419f93ed070c792e9a974b3c`의 tree가 같다. Private0.8.1은 자체 source/게시 이력에서 별도 추적한다.
- 세 호스트 모두 kit 밖 공식 설치본47개와 검수 기록을 연결했다. 등록 원문 catalog42개, 실제 kit source component만 보호한다. 호스트별 자체 source gate와 hook 직접 입력에서 자체 내용 허용·등록 원문 거부·범위 밖 비편입을 확인했다. 이 callback 시험은 실제 파일을 쓰지 않았다.
- 새 private 기본 연결 파일은 기존 base와 별도로 관리한다. 이전 세션의 고정 가드·역할/자료 설정을 유지하며 공통 pin을 완화하지 않는다. 상세 계약은 개인 INSTALL.md가 소유한다.
- Codex 두 호스트에서 이번 공통5개·private5개 hook만 native UI 상세에서 개별 신뢰 승인했다. Trust all이나 신뢰 DB 편집은 하지 않았다. 기존 캐시 경로를 보존하고 사용자 세션을 재시작하지 않았다.
- Claude의 캐시에는 배포 파일 외 native `.in_use/<pid>` 표시2개가 관측됐다. 배포153파일 bytes는 전부 일치하며 표시 파일의 pid/procStart를 현재 사용자 소유 Claude 프로세스와 대조했다. 표시를 삭제하거나 원문/패키지를 바꾸지 않았다.
- 공통 최종525개 회귀와 실제 GitHub build, private129개 회귀가 통과했다. 기본 base+제품별 연결을 쓰는 격리 Codex/Claude native22사례도 통과했다. 합성 API·native callback·실제 모델의 범위를 합산하지 않는다.
- 초기 CI의 scanner 위치/부모 준비 실패, private 확인기의 잘못된 경로, Claude 확인기의 native 표시파일 혼동과 print 인자 전달 실패는 보존하고 확인 절차를 교정했다. 성공한 설치를 다시 실행하지 않았으며 원문·검사 기준·운영 역할을 완화하지 않았다.
- NAS의 별도 Orca 새 세션 시도는 기존 oh-my-zsh 업데이트 질문이 첫 입력을 소비해 agent 시작/요청 전달에 실패했다. 접수 응답 timeout 뒤 새 launch로 재전송하지 않고 실제 새 shell을 확인했다. 셸/실행기 설정은 변경하지 않았다.

원형 증거는 로컬 `/data/projects/_scratch/tr-kit-rollout-20261123/`와 각 호스트의 `~/.local/share/tr-kit/rollout-20261123/`에 둔다. raw 대화·debug·설정 사본을 source나 전송 후보에 넣지 않는다. 이 기록은 승인한 배포와 제한된 시작/명령 시험의 결과이며 전체62개 skill의 실제 업무·자연 발동·장기 압축·운영 자료 처리의 적합을 인증하지 않는다. 기존 Claude 분량 위반, BMAD 자동 갱신404 미지원, Claude의 시작 실패 안내가 세션 전체 차단을 보장하지 않는 한계는 유지한다. Timer·수집·worker·DB 활성화와 실제 인프라 적용은 수행하지 않았다.
