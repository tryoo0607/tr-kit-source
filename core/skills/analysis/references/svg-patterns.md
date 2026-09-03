# SVG 도식 구현 패턴 — §6.7 규칙의 실제 코드

`spec.md` §6.7의 라우팅·레이아웃 규칙을 **복붙 가능한 SVG 조각**으로 옮긴 것. 노드 이름은 전부 placeholder(`NodeA`·`ServiceX`)다 — 참조구현에서 **기법만** 추렸다. 색은 항상 테마 토큰(`var(--…)`)이라 라이트/다크 자동 대응.

## 0. 컨테이너 — figure > plate > svg > figcaption

```html
<figure>
  <div class="plate">
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 784 940"
         width="100%" style="max-width:784px;height:auto;display:block;margin:0 auto"
         font-family="'IBM Plex Sans KR',sans-serif">…</svg>
  </div>
  <figcaption>기준: … (근거 한 줄)</figcaption>
</figure>
```

```css
figure svg { display:block; width:100%; height:auto; }   /* 반응형: 세로 자유, 가로 스크롤은 .plate가 */
figure .plate { overflow-x:auto; }
```

🔑 **`viewBox` + `width:100%` + `max-width:Wpx` + `height:auto`** 가 §6.7의 "반응형·가로 스크롤 금지·세로 자유"다.

## 1. 화살표 마커 — 관계 종류마다 색을 분리

```html
<defs>
  <marker id="ar-mid" markerWidth="9" markerHeight="9" refX="7.5" refY="3" orient="auto">
    <path d="M0,0 L8,3 L0,6 z" fill="var(--ink-mid)"/></marker>
  <marker id="ar-acc" … ><path … fill="var(--accent)"/></marker>   <!-- 주 흐름 -->
  <marker id="ar-soft" … ><path … fill="var(--ink-soft)"/></marker> <!-- 기동 순서 -->
</defs>
```

**기동 순서 · 데이터 흐름 · 주 호출**을 마커 색으로 구분한다(§05 "기동 순서와 호출 관계는 다르다"). fill도 토큰.

## 2. 노드(박스) — rect + text 3줄

```html
<rect x="40" y="100" width="212" height="66" rx="8"
      fill="var(--surface)" stroke="var(--accent)" stroke-width="2.5"/>
<text x="146" y="126" text-anchor="middle" font-size="13" font-weight="600" fill="var(--ink)">NodeA</text>
<text x="146" y="144" text-anchor="middle" font-size="11" fill="var(--ink-mid)">역할 한 줄</text>
<text x="146" y="160" text-anchor="middle" font-size="10" fill="var(--ink-soft)">:port · vX.Y</text>
```

- **허브/중심 노드** = 굵은 stroke 또는 좌측 accent 바: `<rect x=232 y=610 width=5 height=68 fill="var(--accent)"/>` 겹쳐 그림.
- **컨테이너 밖·가상 노드** = `stroke-dasharray="5 3"`.

## 3. 밴드 — 층을 묶는 큰 라운드 사각형

```html
<rect x="24" y="64" width="712" height="376" rx="10"
      fill="var(--accent-soft)" stroke="var(--accent)" stroke-width="1.5"/>
<text x="40" y="86" font-size="12.5" font-weight="600" fill="var(--accent-ink)">층 이름 (설명)</text>
```

층마다 배경 톤을 달리(`--accent-soft` / `--warn-soft` 신규 · `--surface-sunk` 하부). **계층도**가 이 밴드 적층으로 나온다.

## 4. 🔑 라우팅 — 직각 + 바깥 여백 우회

핵심은 **관통 금지**. 노드를 가로지르지 않게 **바깥 여백으로 빙 둘러** 재진입한다:

```html
<!-- NodeTop(우상단)에서 NodeHub(하단 중앙)로: 오른쪽 여백 x=760으로 나갔다가 내려와 진입 -->
<path d="M712 133 L760 133 L760 560 L384 560 L384 610"
      fill="none" stroke="var(--accent)" stroke-width="2.2" marker-end="url(#ar-acc)"/>
<text x="548" y="576" text-anchor="middle" font-size="10" fill="var(--accent-ink)">관계 라벨</text>
```

| §6.7 규칙 | 구현 |
|---|---|
| 사선 금지·직각 | `path`를 **수평·수직 세그먼트만**(`L`로 꺾기) |
| 관통 금지·우회 우선 | 노드 사이로 못 가면 **`max-x + 여백`(예 760)으로 나갔다 재진입** |
| fan → 버스 | 여러 선을 **공통 y(버스 라인)로 모아** 한 줄로 흐르게(`M146 166 L146 184 L604 184 L604 166`) |
| 노드 stub | 노드 경계에서 **짧게 떼고**(stub) 꺾기 시작 |
| 라벨 간격 | 선 중간에 `<text>`, 선과 안 겹치게 y 오프셋 |

## 5. 조립 순서

1. `viewBox`(전체 캔버스) 정하고 밴드부터 깔기(층).
2. 밴드 안에 노드 배치(그리드처럼 x·y 규칙적으로).
3. 마커 `defs` 정의(관계 색 수만큼).
4. 노드 사이 직선(가까우면) → 못 가면 바깥 우회 `path`.
5. 라벨·범례·figcaption.

> 계층도·배선도·데이터흐름은 **같은 조각으로 셋 다** 그린다 — 밴드 적층=계층도 / 우회 path=배선도 / 마커색 순차선=데이터흐름.
