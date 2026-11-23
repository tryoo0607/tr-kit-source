# 기존 시크릿 검사 사례와 개편 반영 대상

## 요청 범위와 현재 상태

사용자는 지정한 두 기존 Orca 세션에 구체 오류·버전·근거를 물어보고 현재 scratch 수정으로 해결됐는지 대조하도록 요청했다. 필요한 합성 격리 시험은 허용했지만 개편 전 플러그인 수정·배포를 요청한 것이 아니다. 이번에는 질의·코드 조회·합성 직접 시험·임시 검사 설정 시험만 수행했다. 기존 작업 재개·종료, live hook 변경·검사 해제·배포·push·Sites 호출은 수행하지 않았다.

최근 scratch 구현은 원문 복제 보호 검사다. commit-guard.py와 시크릿 검사기는 아직 이관하지 않았으며 아래 문제를 해결한 구현으로 간주하지 않는다. [현재 원문 보호 검사](20261117-upstream-guard-pre-post.md)와 별개다.

## 수신자와 버전 근거

| 세션 | 회신과 버전 범위 |
| --- | --- |
| dev01 ieo-study / Codex, tab 714e783b-8039-4cc8-b8de-a8cefc4c13d6 | 세션에 제시된 공통 0.7.13+codex.b0568e620f6a, private 0.7.14+codex.b1f950c9a494. 실제 실행 hook 경로와 동일한지는 미확인이라고 회신. 조회한 설치 소스와 실제 호출 버전을 동일시하지 않음 |
| inno-desktop ai-mcmp / Claude, tab a575067a-5e7d-457a-b52c-6f2a6c8dacb4 | 사용한 공통 tr-claude 0.7.13+claude.b0568e620f6a, cache 디렉토리명은 0.7.13-claude.b0568e620f6a. private 로드 여부 미확인. Git 등록 엔진은 별도 20261109-go-sum-63b106531102/5b6a50a9aa3208de이며 source hash가 0.7.7~0.7.10 사본과 같다는 수신자 확인. Gitleaks8.30.1. 플러그인 갱신만으로 독립 등록 엔진이 갱신됐다고 판단하지 않음 |

송신 당시 web-terminal ID는 CLI handle이 아니었으므로 공식 terminal list의 tabId와 대응한 live handle을 사용했다. 최초/후속 요청 receipt와 실제 응답을 구분했고 중복 재전송하지 않았다. 상세 식별자와 증거는 로컬 조사 기록에 둔다.

## 사례별 확인

| ID | 관측·재현 | 판정·남은 한계 |
| --- | --- | --- |
| SEC-01 go.sum | 수신자가 정상 checksum의 generic-api-key 탐지와 임시 설정 비교를 보고. 이 호스트에서도 기존 source hash a3dcff1867eeb5aceb7279888f3a3d2fe711d044e1a42316cbdbe130511275d2와 신뢰 검증된 Gitleaks8.30.1로 합성 checksum 1줄 통과, 2/12줄 탐지를 재현 | 오탐 재현. line 필드의 선행 LF는 직접 덤프한 사실이 아닌 정규식별 결과에서 도출한 추론. upstream 내부 slicing 소스·다른 엔진 버전·CRLF는 미검증 |
| SEC-02 Sites 결과 | Codex 수신자가 functions.exec 안의 sites_get_site 조회에서 고정 secret inspection 알림을 관측. 원 응답 필드·탐지 규칙·값이 공개되지 않았고 credential 발급 단계까지 실행됐는지도 미확인 | 결과 차단은 관측됨. 정탐/오탐/인증정보 전달 결함 판정은 미확인. get_site를 재호출하거나 원문·비밀을 수집하지 않음 |
| SEC-03 커밋 입력 | 수신자가 기록에서 회수한 multiline commit → rev-parse → status → playwright-cli -s=ieo-reader close를 기존 command_reason에 전달하면 blanket staging 거부가 재현됨. 단독 commit과 세미콜론 경계에서는 같은 거부 없음 | parser 오탐 재현. lexer에서 LF가 separator token으로 남지 않고 후속 -s=ieo-reader의 a가 commit 플래그 검사에 들어가는 코드 경로 확인. Git·Playwright 명령 자체는 실행하지 않음 |

코드 근거는 기존 source common/base/scripts/commit-guard.py의 scan(53행 이후), checksum_line(78행 부근), command_reason(211행 이후), output/protected_output(523행 이후)다. 첫 검토의 단순 commit·후속 status/show 사례는 재현되지 않았고, 정확한 수신 명령을 받은 뒤 SEC-03을 재현했다. 미재현을 해결 판정으로 바꾸지 않았다.

수신자의 숫자 정정: go.sum의 11건은 중립 파일명 blob1에 기본 설정만 사용한 수동 검사였고, guard와 같은 candidate 파일명·trusted 설정에서는 1행이 제외돼10건이었다. 실제 pre-push 발견 총수를11건이라고 단정하지 않는다. 합성3줄의 기본/trusted/선택 LF/필수 LF 설정 결과는3/2/0/1건이라는 회신이다.

## 임시 설정 시험과 한계

원본 source를 수정하지 않고 scan이 만든 임시 trusted.toml의 checksum regex 시작에만 선택 LF 대응을 적용했다. 합성12줄이 통과했고 같은 내용의 다른 파일명, h2 비정상 checksum, 추가한 비실재 합성 키는 계속 탐지됐다. 원문 파일 bytes·나머지 규칙·기본 rules 상속은 유지했다.

이는 수정 방향의 제한적 근거다. 이 정규식을 최종 채택·배포한 것이 아니며 CRLF·모듈/version 변형·같은 줄 오염·다른 키 규칙·native 제품·실제 Git pre-push의 충분한 회귀는 남아 있다. 첫 시험 harness가 allowlist가 없는 다른 파일에서도 정규식 교체를 요구해 오류가 났다. 이를 엔진 오류로 세지 않고 harness를 고친 뒤 재실행했다.

## 개편 시 반영할 검토·수용 항목

다음은 발견 사항에 따른 보완 제안과 시험 항목이며 아직 구현·최종 설계로 확정하지 않았다.

- SEC-01: 경로와 정상 checksum 형식의 결합을 보존한 채 LF·CRLF·첫/후속/빈줄·끝 개행·여러 버전 형식과 오염/키 삽입을 검사한다. go.sum 전체 제외나 generic-api-key 전체 해제는 해결 방법으로 삼지 않는다.
- SEC-02: 비밀 본문을 전달하지 않고도 탐지/검사 오류, 안전한 규칙 식별자·검사 단계·실제 엔진 식별 근거를 알 수 있는 진단 계약을 설계한다. Sites 응답은 정오탐을 먼저 확인하고 필요한 인증정보의 내부 전달과 모델/화면 공개를 구분한다. Sites 전체 허용이나 실제 시크릿의 무검사 전달로 해결하지 않는다.
- SEC-03: shell 경계와 인용 문자열·명령 옵션의 소유 관계를 검사한다. 보고된 multiline 명령, 세미콜론, 인용된 줄바꿈, 실제 commit -a/--all과 우회를 회귀에 함께 둔다. 특정 playwright 문자열 예외로 대체하지 않는다.
- 공통: 설치 버전·세션이 읽은 버전·native 유효 hook·Git 독립 엔진의 identity를 나누고 source/규칙/scanner를 시험 증거와 연결한다. 같은 결함이 양 제품 연결·Git 등록 경로에 다시 나타나는지 확인한다.

세 사례는 같은 시크릿 검사 기능군과 연관돼도 원인이 같다고 확인된 것은 아니다. 운영 설치·배포와 임시 우회 실행은 이번 조사로 승인·수행한 작업이 아니다.
