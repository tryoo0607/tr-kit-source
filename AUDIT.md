# kit-audit 검토안

현재 통합 kit-audit 스킬은 없다. 이 문서는 도입 범위 제안이며 새 스킬·실행기·원격 스캔을 활성화하지 않는다.

## 기존 감사와의 역할

skill-authoring과 연결된 skill-creator는 개별 skill의 역할·reference·외부 연결·제품 차이·읽기량을 검사한다. kit-audit를 도입한다면 그 검사를 복제하는 대신 전체 구성에서 누락·충돌·경계 위반·검증 공백이 있는지 취합하는 역할이 적합하다.

| 감사 범위 | 재사용할 정본·도구 | 필요한 결과 |
|---|---|---|
| README 자체 작성·감사 | github-readme-generator와 공통 binding | 공개·제안 명령의 구현 조건, 최종 설명과 근거의 정합성 |
| 요구와 실제 기능 | 최신 합의, README, 실제 source와 dependencies | 구현·합의·제안·미결의 차이 |
| 역할과 연결 | skill 본문·binding, skill-authoring | 중복 소유·빠진 필수 연결·의도치 않은 호출 |
| upstream과 제품 조립 | fetch/build/validate, assembly.json | 정확한 revision·license·제품별 파일과 링크 |
| 공통/private 경계 | 공통 경계 테스트, private pin과 검증기 | 개인 기능 유출 여부·pin 정합성; private 부재 허용 |
| 배포 출처와 무결성 | delivery.verify, release.json | 실제 source commit·payload hash·제품별 게시 결과 |
| 실행 도구와 기록 | verify_dev_tools.py, verify_records.py | 실행 전제·실제 실행·미설정·실패를 구분 |
| 호스트 활성화 | native CLI·hook trust·Git guard status와 receipt | 설치/활성/실행 중 세션 상태의 차이 |
| 데이터와 변경 범위 | 호스트 경로·공유 정책과 승인 | 회사/개인 경계, 원본·백업·외부 전송 범위 |

## 제안하는 수행 방식

1. 감사 대상 source·제품·호스트·변경 범위와 조회 권한을 확인한다. 기본은 source와 제공된 증거의 읽기 전용 검사다.
2. 변경이 영향을 주는 항목에 기존 검증을 연결하고, 이미 있는 같은 revision의 유효 결과를 재사용한다.
3. 발견 사항에 파일·관측·위험·권장 조치·미검증 범위를 붙인다. 차단 결함, 개선 제안, 환경 부재를 구분한다.
4. 수정·설치·실서버 실행·배포는 감사 결과와 분리한다. 감사 요청을 자동 수리나 권한 확대의 승인으로 취급하지 않는다.

결과에는 대상 revision·제품·환경, 실행/재사용한 검사, 발견 사항과 미결을 남긴다. 성공 판정은 검사 범위로 한정한다. 합성 모델의 도구 callback 검증을 실제 모델의 skill 선택·분석 품질 검증으로 바꾸어 표현하지 않는다.

## 스킬 도입 시 권장 경계

별도 kit-audit 스킬은 전체 감사 요청의 진입점으로, skill-authoring은 개별 저작·검수 정본으로 두는 안을 권장한다. 한 스킬로 합친다면 기존 분기에서 전체 kit 감사 요청을 구분해야 하며 모든 skill 수정에 호스트·배포 전수 감사를 강제하지 않아야 한다. 어느 안이든 기존 검증기를 부르는 얇은 연결로 시작하고 별도 검사 엔진·상태 DB·중복 체크리스트를 만들 필요는 없다.

이번에는 신규 스킬의 작성·배포까지 확정하지 않는다. 실제 반복 감사에서 필요한 입력과 출력이 확인되면 범위와 재사용 대상을 정해 구현한다.

## 현재 확인한 미결

- PTBMAF·Design Doc 방법론 전용 스킬은 현재 common/adapters 소스에서 확인되지 않았다. 이전 대화의 도입 완료 설명은 실제 source 근거와 맞지 않으므로 완료 항목에 포함하지 않는다.
- 최근 배포에서 nas-vm·inno-desktop Codex의 native 가드 차단은 관측됐지만 허용 명령은 bwrap 오류로 전체 실행 검증이 제한됐다. Git hook 검사와 Claude 검증 결과에 합쳐 성공으로 처리하지 않는다.
- Obsidian은 보류이며 현재 kit 구성에 필수로 추가하지 않는다. 프로젝트 wiki 운영 방식은 후속 논의 항목이며 자동 도입 의무가 아니다.
