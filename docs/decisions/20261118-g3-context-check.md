# G3: 선언 읽기량 측정기 이관

2026-11-18. R-35의 scratch source 구현·검수다. 기존 own skill-authoring context_check·루트 wrapper·cases·5개 시험과 현행 plugin-authoring 기준을 대조해 이관했다. 외부 원문/CLI/runtime을 복제하지 않는다. 사용 기준은 shared/reading-flow.md가 소유한다.

## 실제 배치

```text
common/base/
  scripts/context_check.py
  skills/plugin-authoring/references/shared/reading-flow.md
scripts/
  context_check.py
  context-cases.json
tests/
  test_context_check.py
```

```text
명시 before/after roots·읽기 cases·발견 scope → CLI → 공통 측정
공통 측정 → full SKILL/선택 ATX 절·source hash·metadata·canonical 중복
          → 미측정/비대상 범위 별도 표시 → JSON stdout
measure-only → 수치 대조만, 증가해도 측정 성공
기존 비교 → chars/중복·발견 metadata 비증가 판정
입력/파일/절/metadata/dependency 오류 → unavailable, 성공/0측정과 구분
```

## 보존과 수정

- 기존 full SKILL·reference 절·discovery name/description·중복·unmeasured·이유 있는 증가 허용과 비증가 비교를 유지했다. CLI 기본 비교 의미를 조용히 없애지 않았으며 측정만 필요한 호출은 `--measure-only`로 구분한다. 입력한 allowance/이유는 승인 증거가 아니며 모든 저작에 새 비증가 의무를 적용하지 않는다.
- source의 common/base/skills와 기존 flat skills를 지원한다. 둘 다 있거나 scope가 충돌하면 명시 선택을 요구하고, 부재/empty entry를 0비용 성공으로 처리하지 않는다. 명시한 catalog의 문자 합계이며 제품의 실제 discovery/injection 관측이 아니다.
- 같은 canonical 파일의 반복·alias·전체/절 겹침을 센다. 다른 파일의 비슷한 내용은 자동 중복 판정하지 않는다. `exact_repeat_chars`와 전체 `duplicate_chars`를 구분하며 실제 read 내용은 출력하지 않고 위치·문자 수·hash를 남긴다.
- raw UTF-8 Unicode 문자와 원래 CRLF를 보존한다. metadata는 YAML 해석값이다. 초기 multiline YAML fixture에서 마지막 개행을 누락해1자가 적게 집계된 문제를 수정하고 재검증했다. YAML 오류에 원문 snippet을 출력하지 않는다.
- 절 파서는 ATX/fenced code 부분 지원이며 완전한 Markdown renderer가 아니다. 미지원 형식은 전체 파일 또는 별도 확인 범위로 다룬다. 명시되지 않은 읽기를 추론하거나 외부 provider를 복사해 측정하지 않는다.

## 관측과 한계

전용26개, 관련 조립 회귀를 포함한52개 직접 시험이 통과했다. G2 source bundle과 현재 source의 대표5개 부분 경로를 측정했다. metadata는 양쪽53개/5249자로 같고, 저작 경로는14888→17153(+2265), 나머지4개 경로는 동일했다. 새 안내가 늘어 legacy 비교는 exit1/미통과, raw 측정은 exit0/성공이다. 이를 숨기려고 문구를 줄이거나 allowance를 추가하지 않았다. 미측정 공식 지침·CLI 출력·작업 데이터·환경 주입이 있어 전체 컨텍스트 비용의 비교가 아니다.

새 Codex 세션은 정상 A와 after 파일이 없는 B를 각각 실행했다. A는 측정·부분 겹침·metadata를 보고하고, B는 exit2/미확인으로 남겨 누락을0자로 계산하지 않았다. fixture/source hash 변경은0이다. 이 결과는 명시 지침 사용1회 관측이며 자연 발동·실제 전체 읽기·token·Claude·압축 후 행동 시험이 아니다.

동일 작성자가 plugin-authoring의 kit/skill 저작·감사·shared 흐름/행동 기준과 공식 system skill-creator로 검수했다. 실제 모델 결과를 단순 지침 설명·tool exit0과 구분했고 다른 요청/제품/전체 kit로 확대하지 않는다. 운영 설치·배포·private pin은 변경하지 않았다. 상세 로그/원형 결과는 로컬 _bmad-output에 두고 docs에는 관측 요약만 연결한다.

ATX와 fence 경계는 [CommonMark 0.31.2](https://spec.commonmark.org/0.31.2/)의 해당 개념을 참고했다. 규격 전체 준수나 Markdown 렌더 동작을 인증하지 않는다.
