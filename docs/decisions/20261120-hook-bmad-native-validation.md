# Hook 오탐 보완·공식 BMAD 갱신·native 연결 검증

## 요구와 범위

사용자의 후속 진행 요청과 “공식 수정본으로 채택·검증” 승인을 적용했다. 기존 운영 kit을 수정·배포하는 작업이 아니라 scratch 개편본 보완과 격리 검증이다. 실제 인증·개인 자료·운영 설정·기존 세션은 사용하지 않았다.

## 자체 hook 보완

`common/base/scripts/secret_guard.py`가 quoted Python stdin 본문의 `set(...)`를 shell `set`으로 읽는 오탐을 보완했다. 명시적인 `python/python3 [지원 flag] - <<'구분자'`와 double-quoted 구분자 형식만 검사 내부에서 Python `-c` 입력으로 표현한다. 실제 도구 입력·명령·Python 원문은 변경하지 않는다. 불명확한 header는 기존 검사 대상으로 유지한다.

원래 입력 전체의 Gitleaks 검사를 유지하며, Python의 환경·인증 파일 출력과 뒤따르는 shell 명령도 검사한다. 리터럴 subprocess/os.system/os.popen 자식 호출은 같은 공통 검사에 연결하고 shell 문자열과 argv를 구분한다. 동적 변수·별칭·임의 interpreter·완전한 실행 경로를 해석하는 기능은 아니다. 함수 정의·분기 내부의 알려진 리터럴 호출까지 보수적으로 검사하므로 실제 도달 가능성을 증명하거나 모든 오탐·우회를 해결했다고 주장하지 않는다. 최대32개 검사 경계를 넘으면 통과가 아니라 보류한다.

배치·정책·adapter·hook 등록의 변경은 없다.

```text
제품 PreToolUse → 기존 제품 adapter → 공통 입력 검사
  → 좁은 Python/shell 구분 → 기존 명령·출력 금지 판별
  → 원래 입력 전체 Gitleaks 검사 → 제품 결과
```

`tests/test_secret_revision.py`에 양 제품·Bash/exec_command·정상 set/문자열·환경/파일 출력·tail·자식 호출·원문 보존·불명확 header·상한 회귀를 추가했다. 전체511개 시험이 성공했다. 그중 실제 scanner 전용6개는 기본 실행에서 생략됐으며, 해당6개는 실제 Gitleaks8.30.1로 별도 실행해 모두 성공했다. 동일 작성자가 hook 저작/감사 기준에 코드·원래 요구·직접/adapter·native 증거를 대조했으며 독립 전문 감사와 구분한다.

## 공식 BMAD 선택

개발진의 [공식 수정 커밋867c546e](https://github.com/bmad-code-org/BMAD-METHOD/commit/867c546e625c4d1f0cfdd290a79dcc035a994586)를 채택했다. [이전 pin과의 비교](https://github.com/bmad-code-org/BMAD-METHOD/compare/61e01f82644c4bb533750cfa0d6d61ab61d2cc9b...867c546e625c4d1f0cfdd290a79dcc035a994586)는5커밋·6파일이며 YAML escaping 외에 build 설명·walkthrough 선택/절차가 달라진다. 이 차이를 설명하고 사용자가 채택한 뒤 설치했다. 원문을 자체 수정한 커밋이 아니다.

공식 Skills CLI1.9.0으로 별도 프로젝트에 양 제품31개씩 설치했다. metadata3개를 제외한 callable28개를 새 registry에 연결해 전체 callable47개씩이 됐다. 설치62묶음의 전체 원본 파일이 공식 고정 커밋 archive와 일치한다. 양 제품 BMAD 검수56개를 갱신·대조했고, 공식 setup과 retrospective renderer가 각각12131byte 지침을 정상 출력했다. 회고 업무 전체의 모델 행동 성공을 뜻하지 않는다.

고정 원문에 적힌 module update 경로3개는 현재 main에서 여전히404다. 공식 수정본 실행은 가능하지만 그 metadata를 이용한 자동 갱신은 미지원으로 남긴다. 최신 main의 대규모 구조 변경으로 조용히 전환하거나 원문의 update URL을 고치지 않았다.

대조 catalog46개 중 BMAD28개를 승인한 공식 설치본으로 연결했다. SKILL 본문 hash 변경은 build/build-auto/retrospective의3개다. 나머지18개 대조 원문과 기존 목록은 보존했다.

## 실제 native 검증

Codex0.167.2·Claude Code2.1.329 공식 실행기를 각각 별도 HOME/config/cache에서 사용했다. 공식 plugin manager로 공통154파일 native 패키지 설치·후속 갱신과 cache bytes 대조를 통과했다. 실계정 인증을 복사하지 않고 localhost 합성 API 응답만 사용했다. 이는 실제 제품의 hook callback 시험이며 실제 모델의 선택·추론·업무 수행 시험은 아니다.

Codex는 native UI에서 검토한 개별 hook만 승인했다. 갱신 뒤 공통5개가 modified, 기존 private5개는 trusted인 것을 공식 app-server hooks/list로 확인했다. 갱신된 공통5개도 native UI로 개별 재검토한 후 최종 후보에서 다시 시험했다. trust DB 직접 수정이나 hook trust 우회 옵션은 사용하지 않았다.

| 구성·사례 | 양 제품 관측 |
| --- | --- |
| 공통 단독: 정상 Python set·정상 marker | 실제 실행·예상 출력 |
| 공통 단독: 환경 전체 출력·일괄 stage·합성 비밀 입력·합성 외부 원문 복제 | 실제 PreToolUse 차단 응답. 복제 결과 없음 |
| 필수 upstream binding 없음·Gitleaks 실행 파일 없음 | 정상 명령도 필수 검사 불가로 차단; 허용으로 전환되지 않음 |
| 실행 중 생성한 합성 비밀 출력 | 다음 모델 요청에는 원문 대신 고정된 출력 차단 안내. 원 실행과 모든 native 내부 로그의 보호를 일반화하지 않음 |
| 공통+private hook: 위 정상/차단6개씩 | 양 제품 모두 기대 일치. 공통 지침과 development 역할/가드 경로가 같은 세션 입력에 전달됨 |

합계30사례의 최종 판정을 보존했다. private hook은 검증된48파일 source 묶음의 자체 template을 격리 native 설정에 연결했다. Codex capture는 비활성, Claude는 기존 SessionStart만 사용했다. 이 시험을 private 전체 native 플러그인 설치·발견·MCP·실제 수집·압축·권한 우회 불가능성 검증으로 확대하지 않는다.

## 재조립·pin과 최초 검사 오류

최종 공통은 제품별150파일 source/154파일 native, private는 제품별48파일 source다. 이전 공통 source 대비 배포 파일 변경은 secret_guard.py 하나이며 추가/삭제는 없다. 이를 대조해 private exact common pin만 갱신했다. 이전 공통 묶음 거부·새 묶음 허용과 역할 정책 hash 유지(95c375…8d21)를 확인했다. private106개 회귀가 통과했다.

첫 fresh 조립은 아직 생성되지 않은 두 번째 산출물을 한 scope에 미리 선언해 fail-closed 검사에서 거부됐다. 실패 출력/입력을 보존하고 산출물별 scope로 새 경로에서 재조립했다. 검사 구현·보호 범위를 완화하지 않았다. private 첫 회귀 실행은 필수 TR_PRIVATE_TEST_COMMON_ROOT 입력을 누락해 오류73개가 났고, 새 검증 공통 묶음을 명시한 재실행106개가 통과했다. 제품/구현 실패와 이 시험 입력 오류를 구분한다.

## 증거와 남은 단계

공통 로컬 기록은 `_bmad-output/official-provider-validation-20261120/`의 bmad-official-fix-*, catalog-bmad-adoption.json, hook-revision-test-results.json이다. 실제 설치/검수는 `/data/projects/_scratch/tr-kit-official-validation-20261120/`, native 입력·결과·UI 검토·새 조립물은 `/data/projects/_scratch/tr-kit-native-validation-20261120/`에 있다. 상세 합성 입력·출력은 배포물에 포함하지 않는다.

private의 common 계약은 여전히 source-bundle-v1만 수용한다. 공통 native 설치본에는 경로/manifest/hook 등 별도 파일이 있으므로 이를 조용히 raw source로 인정하지 않는다. **private native 패키징·설치본 연결 계약과 전체 제품 통합은 남아 있다.** 실제 모델의 새 kit 선택·업무 행동·압축/재개, 선택 MCP의 native 등록·개인 기능과 실자료 검증, 운영 배포도 완료하지 않았다. 이번 시험 프로세스와 localhost 서버는 종료했다.
