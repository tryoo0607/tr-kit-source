# 운영 runtime 연결 보완

- 사용자 승인: 호스트별 원문 보호 대상·공식 provider 연결을 보완·검증한 뒤 배포 계속. dev01/nas-vm Codex, inno-desktop Claude만 대상이며 private는 앞 두 호스트만 설치한다.
- 구조: 제품별 native 시작/도구 hook → 공통 runtime_config → 명시 호스트 설정의 provider 선언·선택 검수 기록·upstream binding. 실제 검사는 기존 resolver/provider-review와 upstream guard가 소유한다. 설정은 kit source·기존 프로젝트 config.toml과 별도다.
- 기본 위치와 schema·실패 처리는 INSTALL.md가 소유한다. 셸 설정·실행기·역할·wiki 수집·백업 timer를 변경하지 않는다. 공식 설치본은 kit 밖 고정 호스트 경로에 관리 도구로 설치하며 기존 검수본과 원문·리소스를 대조한다.
- 보호 scope는 실제 kit source component만 명시한다. 다른 업무 프로젝트·새 worktree를 자동 편입하지 않는다. 등록 catalog에 없는 변형의 의미적 탐지는 보장하지 않는다.
- 검증: runtime 설정9개(양 제품 경로 전달·실제 guard 정상/원문 복제/범위 밖·잘못된 설정 등)와 공통 전체525개 회귀 통과. dev01 공식 설치본47개 리소스가 이전 검수 기준과 일치했다. 이 시점의 원격 설정·실제 운영 배포·신뢰 승인·새 운영 세션 검증은 진행 중이며 완료로 판정하지 않는다.
- 기계 검증과 모델의 선택·준수는 구분한다. 기존 실제 모델 보고 분량 위반·자동 업데이트 미지원 등 잔여 한계를 없어진 것으로 처리하지 않는다.
