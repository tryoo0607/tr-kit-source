# 분석 아티팩트 규격 — `[프로젝트] 구조 분석`

작성일: 2026-08-19 · 개정: 2026-08-19 (v2.6 — §6.7 SVG 라우팅·레이아웃 10규칙) · 상태: 확정 · 적용: `m-cmp` · `cloud-migrator` · `ai-mcmp`

> 여러 정부과제 프로젝트의 **구조 분석 아티팩트**를 한 시리즈로 통일하기 위한 규격. 제목·마스트헤드·섹션 골격·footer·디자인 토큰을 고정한다. 프로젝트 고유 내용(섹션 본문·도식)은 자유.

---

## 0. 왜 통일하나

같은 손이 만든 온보딩/구조 문서가 프로젝트마다 제목·톤·메타가 제각각이면, 갤러리에서 시리즈로 안 읽히고 매번 다시 디자인하게 된다. **골격을 고정하면 새 프로젝트는 내용만 채우면 된다.**

---

## 1. 제목 규칙 (필수)

```
[<프로젝트>] 구조 분석
```

- `[M-CMP] 구조 분석` · `[Cloud-Migrator] 구조 분석` · `[AI-MCMP] 구조 분석`
- 대괄호 프리픽스가 **갤러리에서 앞 이름만 다른 시리즈**로 세워준다.
- `<title>` 태그와 호스트별 발행 제목 모두 이 형식.
- 프로젝트 표기는 그 프로젝트가 스스로 쓰는 대소문자를 따른다(M-CMP·Cloud-Migrator·AI-MCMP).
- description(갤러리 부제): 한 문장으로 "무엇을 다루는 문서인지".
- favicon: 프로젝트 성격 이모지 1개, 재발행 간 **고정**.

---

## 2. 마스트헤드 (필수)

순서 고정: **eyebrow → h1 → 부제 → metabar**.

```html
<header class="masthead">
  <p class="eyebrow">&lt;플랫폼 성격 한 줄&gt;</p>
  <h1>[&lt;프로젝트&gt;] 구조 분석</h1>
  <p class="standfirst">&lt;2~3줄. 이 시스템이 무엇이고 이 문서가 무엇을 정리하는가&gt;</p>
  <div class="metabar">
    <div class="mi"><span class="mk">기준</span><span class="mv">&lt;날짜&gt;</span></div>
    <div class="mi"><span class="mk">근거</span><span class="mv">&lt;소스&gt;</span></div>
    <div class="mi"><span class="mk">범위</span><span class="mv">&lt;예: 아키텍처 · 데이터흐름 · 배포 · 코드 모듈&gt;</span></div>
    <details class="meta-note">
      <summary>근거 · 확신 없는 것</summary>
      <div class="mn-body">
        <p><b>근거</b> — &lt;무엇을 근거로 썼나&gt;</p>
        <p><b>확신 없는 것</b> — &lt;미확인·추정&gt;</p>
      </div>
    </details>
  </div>
</header>
```

- eyebrow: mono, `letter-spacing:.18em`, 대문자화, accent 색.
- 🔑 **metabar = 정보 한 판.** 위아래 hairline 프레임 안에 `기준·근거·범위`를 **라벨(위, mono 소문자 accent) + 값(아래)** 세로 정렬. 라벨은 **세 개로 고정**, 버전·커밋은 `근거` 값에 녹인다.
- 🔑 **`근거 · 확신 없는 것`은 metabar 안 접힌 `ⓘ` 토글**(`<details class="meta-note">`)로. footer 로 매 뷰 하단에 반복하지 않는다(멀티뷰에서 반복돼 거슬림). hover 아님 — 클릭 펼침(원격/터치에서 hover 는 안 뜸).

---

## 3. 섹션 골격 (권장 순서)

`h2` 는 `<span class="num">NN</span>` 를 앞에 단다. 번호는 **실제 순서를 뜻할 때만** 의미가 있으므로, 읽는 순서대로 01부터.

**각 섹션 = 사이드바의 한 뷰** (§6.5 멀티뷰). 골격은 **앞·중간·뒤**로 나뉜다.

| # | 성격 | 고정? |
|---|---|---|
| 01 | **개요** — 이 플랫폼이 뭔가 + 그 프로젝트의 **가장 중요한 함정** | 고정 |
| 02 | **용어·약어** — 두 벌 이름·개명·접두사 등 조회용 표 | 고정(작으면 개요에 흡수) |
| 03 | **컴포넌트 구조** — 컴포넌트 목록 표 + 계층도 + **모듈 배선도** | 고정 |
| 04 | **데이터흐름** — 요청/작업 한 건의 여정 (SVG) | 있으면 |
| 05~ | **프로젝트 고유** — 계약·실패·배포·모듈·성숙도 등 | **자유** |
| 끝 | **읽기 진입점** — 어디부터 읽나 | 고정 |

- **앞(개요·용어·컴포넌트·데이터흐름) + 뒤(읽기 진입점) = 공통 골격.** 중간(고유)만 프로젝트별로 채운다.
- 🔑 **01 개요의 "최대 함정"은 프로젝트마다 다르다** — 대개 이름·용어(M-CMP·Cloud-Migrator), AI-MCMP처럼 "선언 vs 실체"면 그걸 앞세운다.
- 🔑 **AI 접점·성숙도 같은 건 공통 골격이 아니다.** 필요한 프로젝트가 "고유(05~)"에 넣는다.
- 🔑 **nav 라벨 = h2 문구** (짧게 줄이더라도 앞부분 일치). 목차 클릭과 도착 제목이 어긋나지 않게.

---

## 4. 근거 · 확신 없는 것 (필수, metabar 안)

`근거` 와 `확신 없는 것` 두 항목은 **뺄 수 없다** — 이 시리즈는 "사실·근거·불확실 명시"가 값어치다.
단 **별도 footer 로 두지 않고 §2 metabar 의 `ⓘ` 토글**(`<details class="meta-note">`)에 담는다.
멀티뷰에서 footer 는 뷰마다 반복돼 거슬리므로, 문서당 **한 곳**(마스트헤드)에만 접어 둔다.

---

## 5. 디자인 토큰 (고정)

```css
:root{
  --ground:#f3f6f6; --surface:#ffffff; --surface-sunk:#e8eded;
  --line:#c9d3d4; --line-soft:#dde4e5;
  --ink:#16211f; --ink-mid:#3f504e; --ink-soft:#6b7c7a;
  --accent:#0b6f66; --accent-soft:#d5e8eb; --accent-ink:#0b555f;
  --warn:#8f5d10; --warn-soft:#f5e8cf;
  --crit:#94382c; --crit-soft:#f3ddd9;
  --ok:#2e6a44; --ok-soft:#d9ebdf;
  --mono:"IBM Plex Mono",ui-monospace,"SF Mono",Menlo,Consolas,monospace;
  --body:"IBM Plex Sans KR",-apple-system,"Apple SD Gothic Neo","Malgun Gothic",sans-serif;
}
```

- **본문 = sans-KR, 강조/코드/라벨/제목 = mono.** serif 본문 금지(한글 웹폰트 fallback 이 뷰어마다 제각각).
- 🔑 **`body { word-break: keep-all; overflow-wrap: break-word; }`** — 한글이 단어(공백) 단위로만 끊긴다. 없으면 "요청 한 / 건의" 처럼 단어 중간이 잘린다. 긴 코드 토큰은 `code { word-break: break-all; }`.
- accent = 틸 `#0b6f66` 공통. 프로젝트 구분이 꼭 필요하면 **accent 하나만** 바꾼다(나머지 토큰·구조는 손대지 않는다).
- 3-state 테마 필수: 바닥 `:root`(light) → `@media (prefers-color-scheme:dark) :root:not([data-theme="light"])` → `:root[data-theme="dark"]`. body 배경은 토큰으로 명시.
- 자체완결성을 위해 원격 웹폰트를 불러오지 않고 시스템 font stack을 사용한다.

---

## 6. 컴포넌트 세트

**필수**: 마스트헤드 · nav(좌측 sticky rail, 01~ 번호) · `h2 .num` · `.note`(기본/`.warn`/`.crit` — **색 3단**) · 표(`.tablewrap>table`) · footer.

**선택** (내용에 맞게):

| 컴포넌트 | 쓰임 |
|---|---|
| `.stack` + `.layer` | 계층 다이어그램 (위→아래, "무엇이 무엇 위에") |
| 인라인 `<svg>` 배선도 | **모듈 배선도 (누가 누구를 부르나) — 계층도와 별개로 중요** |
| `.bars` | 수량 비교 막대 (액션 수·컨테이너 수 등) |
| `.flow` + `.step` | 단계 스트립 (01·02·03…) |
| `.cards` + `.card` | repo/모듈 카드 |
| `.tree` | 디렉토리·라우팅 트리 (mono, `white-space:pre`) |
| `.chip` (+`.chip.key`) | 인라인 배지 — 버전·상태·"신규" 표식 |
| `sup.fnref` + `.footnotes` | **출처 각주** — 검증 가능한 수치·주장에 붙인다 |
| 인라인 `<svg>` (+`figure`/`figcaption` 또는 `.tablewrap`) | **모든 도식 — 계층·시퀀스·배선·토폴로지** |

- 🔑 **도식은 인라인 SVG로 통일한다 (v1.2). mermaid 는 쓰지 않는다.**
  이유: mermaid 는 색이 **테마 토큰에 안 물려** 다크모드에서 도식만 밝게 뜨고, 배치·강조를 못 고른다.
  SVG 는 `fill="var(--accent)"` 로 3-state 테마에 그대로 물리고, 배치·라벨·강조를 완전히 통제한다.
- **SVG 색은 반드시 토큰으로.** 하드코딩 hex 금지 — `fill="var(--ink)"`·`stroke="var(--line)"` 식.
  (마커 화살표 fill 도 토큰.) 참조 구현: Cloud-Migrator·M-CMP 아티팩트의 SVG.
- `figure`+`figcaption`(캡션 필요 시) 또는 `.tablewrap`(스크롤 박스)로 감싸고 `min-width` 를 준다.
  페이지 body 는 가로 스크롤 금지, 넓은 도식은 컨테이너 안에서만 스크롤.
- 텍스트가 많은 계층/막대 비교는 CSS 컴포넌트(`.stack`·`.bars`·`.flow`)로 대체 가능(이미 토큰 기반).

🔑 **컴포넌트 구조 뷰는 세 가지를 함께 둔다 (권장)**: ① 컴포넌트 **목록 표**(무엇이 있나) · ② **계층도**(무엇이 무엇 위에) · ③ **모듈 배선도**(무엇이 무엇을 호출/연결하나). 계층도와 배선도는 **다른 그림**이다 — 계층은 상하 적층, 배선은 호출·의존 관계(허브·역방향 연결 포함). 배선도는 인라인 SVG로, 토큰 색·화살표 마커로 그린다(참조: M-CMP 컴포넌트 뷰).

**선택 토큰 (v1.1, 추가)** — 하드코딩 대신 써도 된다(안 써도 규격 위반 아님):
```css
--s1:.25rem; --s2:.5rem; --s3:.75rem; --s4:1rem; --s5:1.5rem; --s6:2rem; --s7:3rem; --s8:4rem;
--measure:70ch;          /* 본문 최대폭 */
--plate:var(--surface); --plate-rule:var(--line);  /* 도식 액자 */
```

---

## 6.5 멀티뷰 (사이드바 = 뷰 전환)

한 페이지 스크롤이 아니라 **사이드바를 누르면 그 섹션만 보이는** 단일 아티팩트 앱이다.
(별도 아티팩트로 쪼개지 않는다 — 항상 한 URL.)

- **레이아웃**: 마스트헤드(전 뷰 공통) 위, 그 아래 `nav`(좌측 sticky) + `main`(뷰 하나). footer 도 공통.
- **동작**: `nav a[data-view="<id>"]` 클릭 → 같은 id `<section>` 만 표시, 나머지 hide. 활성 nav 강조.
- **상태**: URL 해시(`#flow`)로 유지 → 새로고침·뒤로가기·링크 공유 됨.
- 🔑 **뷰 전환 시 스크롤 위치 유지** — `scrollTo(0,0)` 쓰지 않는다(매번 최상단 제목으로 튀는 것 방지).
- **CSS**: `main > section { display:none } main > section.is-active { display:block }`.
- ⚠️ **footer 는 `grid-column: 2`(콘텐츠 열)로.** `1 / -1`(전체 폭)이면 짧은 뷰에서 footer 가 위로 올라와 sticky nav(열 1)와 **겹친다**. masthead 만 `1 / -1`.
- 🔑 **뷰가 많으면 nav 를 Part 로 묶는다** — `<li class="navpart">라벨</li>` 헤더를 그룹 앞에 둔다.
  표준 4묶음: **들어가기**(개요·용어) · **구조**(컴포넌트·데이터흐름) · **깊이**(프로젝트 고유) · **참고**(읽기 진입점).
  `nav .navpart { font-family:var(--mono); font-size:10px; letter-spacing:.14em; text-transform:uppercase; color:var(--ink-soft); margin:18px 0 4px; }`
- 참조 구현(CSS+JS 그대로 복사): **M-CMP 아티팩트**.

```html
<nav><ol>
  <li><a href="#names" data-view="names"><span class="num">01</span>개요</a></li>
  ...
</ol></nav>
<main>
  <section id="names"> ... </section>
  ...
</main>
<script>
(function(){
  var V=[].slice.call(document.querySelectorAll('main > section'));
  var L=[].slice.call(document.querySelectorAll('nav a[data-view]'));
  function show(id){var ok=false;V.forEach(function(s){var on=s.id===id;s.classList.toggle('is-active',on);if(on)ok=true;});
    L.forEach(function(a){a.classList.toggle('is-current',a.getAttribute('data-view')===id);});return ok;}
  function sync(){var id=(location.hash||'').replace(/^#/,'');if(!id||!show(id))show(V[0].id);}
  L.forEach(function(a){a.addEventListener('click',function(e){e.preventDefault();var id=a.getAttribute('data-view');
    if((location.hash||'').replace(/^#/,'')===id)show(id);else location.hash=id;});});
  window.addEventListener('hashchange',sync);sync();
})();
</script>
```

---

## 6.6 출처 각주 (근거 링크)

이 시리즈의 값어치는 "사실·근거·불확실 명시"다. **검증 가능한 수치·주장에는 각주로 출처를 단다** —
독자가 "이거 어디서 봤나"를 클릭 한 번으로 확인하게.

- **무엇에 다나**: 개수(서브모듈 12·액션 857·서비스 62·인터페이스 25 등)·버전·"미러다"·"CSP에서 왔다" 같은 **원본 파일로 확인되는 주장**. 해석·의견엔 달지 않는다.
- **어디로**: 되도록 **줄 단위로 볼 수 있는 공개 파일 링크**(`github.com/.../blob/main/<file>`) 또는 디렉토리(`/tree/...`).
- **번호는 뷰 단위**: 각 뷰(섹션)마다 `[1]`부터. 뷰 하단에 `.footnotes` 목록. **각주와 그 참조는 같은 뷰 안에** 둔다(뷰 스위처라 다른 뷰의 앵커로 못 뛴다).
- 🔑 **양방향 링크**: 본문 번호 `[n]`↔각주가 서로 점프. 본문 `<a class="fnref" id="r-{뷰}-{n}" href="#f-{뷰}-{n}"><sup>[n]</sup></a>`, 각주 `<p><span id="f-{뷰}-{n}">[<a class="fnback" href="#r-{뷰}-{n}">n</a>]</span> …</p>`. id 는 `뷰id-번호` 로 유일하게.
- 🔑 **뷰 스위처 JS 는 뷰 id 가 아닌 해시를 무시해야 한다** — 각주 앵커(`#f-…`) 클릭 시 `sync()` 가 첫 뷰로 튀지 않게: `if(!id){show(first);return;} if(뷰중_존재)show(id);`(모르는 해시면 그냥 둠, 브라우저 네이티브 스크롤).
- ⚠️ **회사·내부 저장소는 링크하지 않는다.** 공개 repo만. 사내 자산 URL은 각주 대상 아님(반출).

```html
… 서브모듈 12개를 묶는다.<sup class="fnref">[1]</sup>
…
<div class="footnotes">
  <p>[1] 서브모듈 정의 — <a href="https://github.com/…/.gitmodules" target="_blank" rel="noopener">repo · .gitmodules</a></p>
</div>
```
```css
sup.fnref { font-family:var(--mono); font-size:10px; color:var(--accent-ink); font-weight:600; margin-left:1px; }
.footnotes { font-family:var(--mono); font-size:11px; line-height:1.7; color:var(--ink-soft); border-top:1px solid var(--line-soft); margin-top:24px; padding-top:12px; }
.footnotes p { margin:0 0 4px; max-width:none; }
.footnotes a { color:var(--accent-ink); word-break:break-all; }
```

## 6.7 SVG 도식 라우팅·레이아웃 규칙 (v2.6)

도식(특히 배선도)은 아래 10규칙을 따른다. 목적: 선이 뜻을 흐리지 않고, 좁은 화면에서도 읽히게.
참조 구현: **M-CMP 컴포넌트 구조 뷰의 모듈 배선도** — 우회·버스·stub·범례·반응형을 전부 적용한 견본.

1. **관통 금지** — 선이 무관한 노드를 뚫고 지나가지 않는다. 노드를 피해 우회.
2. **텍스트 가두기** — 노드 안 텍스트가 박스를 넘지 않게. 박스 폭 확대 / 폰트 축소 / 줄바꿈 중 택일.
3. **직각 라우팅** — 대각선 대신 직각(ㄱ자, orthogonal). 사선 최소화.
4. **fan → 버스** — 하나에서 여러 갈래는 **실제 분화 로직에만**. 그 외엔 세로 버스 한 줄에서 수평 분기.
5. **no-graze · 우회 우선** — 관통이 아니어도 **무관 노드 사이 좁은 틈으로 평행 주행 금지**(스쳐 지나가 전달하는 오해). ① **바깥 여백으로 우회가 1순위** > ② 넓은 전용 통로. ⛔ **노드 무리를 갈라 통로를 내지 마라** — 한 무리가 별개 그룹처럼 보인다.
6. **인코딩 범례** — 선 색/굵기/실선·점선, 노드 테두리/배경으로 의미를 구분하면 **범례 표를 도식에 동봉**(스와치+뜻).
7. **노드 stub** — 선은 노드에서 **수직으로 짧게 빠져나온 뒤 꺾는다**. 모서리에 붙어 평행 주행 금지, 꺾임이 모서리에서 바로 일어나지 않게.
8. **가로 제한 · 세로 자유** — `<svg width="100%" style="max-width:…;height:auto">` **반응형**. **가로 스크롤 금지**(`min-width` 고정폭 금물). 정보가 많으면 **세로로 길게** 편다(세로는 자유).
9. **크로싱 구간 여유** — 여러 선·라벨이 겹치는 구간(예: 서비스 밴드↔인프라 축 사이)은 **세로로 넉넉히 벌려** 몰리지 않게. 세로는 자유(R8)니 아끼지 않는다.
10. **라벨 간격** — 라벨을 선에 **딱 붙이지 않는다**(수평선 위/아래 ≥~16px). **라벨끼리도 겹치지 않게**(세로 ≥~20px). 두 선 사이 끼는 배치를 피하고 넓은 여백 쪽으로 뺀다.

---

## 7. 새 프로젝트 추가 절차

1. 이 규격의 `<style>` 블록을 복사 (m-cmp 또는 cloud-migrator 아티팩트가 참조 구현).
2. 마스트헤드 4요소 채우기.
3. 섹션 01·02·03 + 프로젝트 고유 + 읽기 진입점.
4. footer 의 `근거`·`확신 없는 것`.
5. 제목 = `[<프로젝트>] 구조 분석`, favicon 1개 고정.
6. target adapter가 정한 방식으로 표시하고, 지속 산출물의 경로·URL은 프로젝트 기록에 남긴다.

---

## 참조 구현

- 기존 `[M-CMP]`, `[Cloud-Migrator]`, `[AI-MCMP]` 구조 분석 산출물은 이 규격을 만든 근거다. 접근 가능한 환경에서는 기존 프로젝트 기록의 링크를 참조한다.

## 가정

- 본문 폰트를 sans-KR 로 정한 것은 한글 가독성·렌더 안정성 근거다. serif 톤을 원하면 Noto Serif KR 웹폰트를 명시적으로 링크해야 하며, 그 경우 이 규격을 개정한다.
- accent 공통 틸은 두 기존 아티팩트가 이미 틸(`#0f6f7d`/`#0b6f66`)이라 자연스러운 수렴점이라 골랐다.

## 확신 없는 것

- 프로젝트가 4개 이상으로 늘면 accent 공통 유지가 맞는지(구분 필요성 대두), 그때 재검토.
- 프로젝트 표기: `[M-CMP]` · `[Cloud-Migrator]` · `[AI-MCMP]` — 각 프로젝트 관용 대문자. favicon: 🐝(honeybee 계열) · 🗺️ · 🤖.
