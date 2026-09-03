# E2E — 앱을 띄우는 테스트

`unit.md`와 **규율이 다르다.** 느리고 flaky하니 원칙이 따로 있다.

## E2E 규율 (유닛과 다른 점)

- **앱 구동이 먼저다** — dev 서버/빌드를 띄우고 대상 URL·디바이스를 지정한다. 안 떠 있으면 E2E 자체가 불가능하다.
- **flaky 억제** — auto-wait를 신뢰하고 **고정 `sleep` 금지** · retry 2~3 · 외부 API는 stub(HAR/mock) · 시드 고정.
- **안정 selector** — `role` / `data-testid` 우선. 텍스트 > CSS/xpath. **구조 의존은 깨지기 쉽다.**
- **격리** — 테스트간 독립 · 픽스처 시드 · 클린업. 순서 의존 금지.
- 🔑 **범위를 얇게** — 피라미드 상단이다. **핵심 사용자 흐름만**(로그인·결제·핵심 CRUD 등 골든 플로우 몇 개). 세부는 유닛/통합으로 내린다.
- **CI는 별도 레인** — 느리니 분리 · 헤드리스 · 병렬 샤딩 · 실패 아티팩트(스샷·비디오·trace) 수집.

## 도구 — 레이어당 주력 1개

repo에 이미 쓰는 게 있으면 **그걸** 따른다. 없을 때 기본:

| 스택 | 주력 | 대안 |
|---|---|---|
| **웹 프론트** | **Playwright** | Cypress |
| **모바일/Wear (Android)** | **Maestro** | Espresso · UIAutomator |
| **크로스플랫폼 모바일** | Appium | |
| **iOS** | XCUITest | Maestro |

> ⚠️ **같은 레이어에 도구 2개 금지** — 중복 유지비.

### Playwright (웹 기본)
크로스브라우저(Chromium/Firefox/WebKit) · auto-wait 내장 · **trace viewer**(실패 재현) · codegen.
셋업: `npm init playwright@latest` → `playwright.config.ts`(`baseURL` · `webServer`로 dev서버 자동기동).
selector: `getByRole` / `getByTestId` 우선. `page.locator('css')`는 최후.

**Cypress**는 DX·타임트래블이 좋지만 실행모델(브라우저 내)·멀티탭이 약점. repo가 이미 Cypress면 유지한다.

### Maestro (모바일/Wear 기본)
YAML flow(`tapOn`, `assertVisible`)로 **간단**하고 셋업이 가볍다. Wear·모바일 UI 흐름에 적합.
셋업: `maestro test flow.yaml` (에뮬/기기 연결).

**Espresso/UIAutomator**는 네이티브·정밀(Compose 포함) — 복잡한 상호작용이나 CI 통합이 깊을 때.
Compose UI는 `composeTestRule`(semantics matcher).

### Appium
Android+iOS 공유 시나리오. WebDriver 프로토콜. 무겁지만 커버가 넓다.
