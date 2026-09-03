# 프로토타입 스니펫 (프레임·다화면·목데이터)

전부 **인라인·자체완결**(외부의존 X). 복사해 조립.

## 워치 프레임 (Wear OS 원형)
```html
<div style="width:396px;height:396px;border-radius:50%;overflow:hidden;
            background:#000;color:#fff;margin:2rem auto;
            box-shadow:0 0 0 12px #222,0 8px 30px rgba(0,0,0,.5);
            display:flex;align-items:center;justify-content:center">
  <div style="text-align:center;padding:2rem">
    <!-- 워치 화면. 작은 뷰포트·큰 터치타깃(≥48px)·중앙 정렬 -->
    <div style="font-size:2.5rem;font-weight:700">14:30</div>
    <div style="opacity:.7">거던 빌드 3개</div>
  </div>
</div>
```
> 워치 규율: 정보 최소·중앙·큰 글자·터치타깃 크게. 실기 = 396×396(원형)/방형도 있음.

## 모바일 프레임 (폰 베젤)
```html
<div style="width:390px;height:844px;border-radius:40px;overflow:hidden;
            background:#fff;margin:2rem auto;border:12px solid #111;
            box-shadow:0 10px 40px rgba(0,0,0,.3);position:relative">
  <div style="height:100%;overflow-y:auto">
    <!-- 모바일 화면 내용 -->
  </div>
</div>
```

## 다화면 (한 파일, 탭 전환)
```html
<nav style="display:flex;gap:.5rem;justify-content:center;margin:1rem">
  <button onclick="show('s1')">홈</button>
  <button onclick="show('s2')">상세</button>
</nav>
<section id="s1" class="screen">…홈…</section>
<section id="s2" class="screen" hidden>…상세…</section>
<script>
  function show(id){
    document.querySelectorAll('.screen').forEach(s=>s.hidden = s.id!==id);
  }
</script>
```
> 화면 여러 개를 한 목업에 담아 흐름을 보여줌. 프로토타입은 라우팅 대신 토글로 충분.

## 목데이터 패턴
```html
<script>
  const MOCK = [
    {name:'빌드 A', likes:42, tag:'딜러'},
    {name:'빌드 B', likes:17, tag:'탱커'},
  ];
  document.getElementById('list').innerHTML =
    MOCK.map(x=>`<li>${x.name} · ♥${x.likes} · ${x.tag}</li>`).join('');
</script>
```
> 실제 API 없이 그럴듯한 더미로. **"데이터 연결은 나중"** 명시. throwaway.

## 저충실도 와이어프레임
- 색·이미지 대신 회색 박스(`background:#ddd`)·플레이스홀더 텍스트.
- 레이아웃·흐름만 — 스타일 판단은 `odin:design` 단계로 미룸.
```html
<div style="background:#e5e5e5;border:1px dashed #999;padding:2rem;text-align:center;color:#666">
  [히어로 이미지]
</div>
```
