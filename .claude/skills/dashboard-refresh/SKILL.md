---
name: dashboard-refresh
description: 대시보드 갱신. "갱신해줘", "대시보드 업데이트", "dashboard refresh" 한마디로 트리거되는 반자동 스킬. 매일 자동 실행되지 않고 호출될 때만 동작한다(불필요한 API 사용을 피하기 위함). 최신 가격·환율·뉴스를 웹검색으로 받아 daily-brief 결과와 HTML 대시보드를 함께 갱신하고, 로컬 서버로 렌더링을 실측 검증한 뒤 발행한다.
---

# 대시보드 갱신 (Dashboard Refresh)

시작하기 전에 `.claude/skills/investing-principles.md`를 반드시 먼저 읽는다.

## 트리거 원칙
자동 스케줄 실행이 아니라 사용자가 명시적으로 호출할 때만 동작한다. 구독 한도 안에서 쓰기 위한 의도적 설계이므로, 스스로 주기적/자동 실행을 제안하지 않는다.

## 프로세스
1. `daily-brief` 스킬의 프로세스를 실행해 최신 브리핑을 생성/갱신한다 (`output/briefs/YYYY-MM-DD.md`).
2. `data/portfolio.md`, `data/watchlist.md`를 읽어 최신 보유·관심 현황을 반영한다.
3. `output/dashboard.html`을 갱신한다 — 정적 HTML로 브리핑 요약, 포트폴리오 요약(가능하면 `portfolio-cockpit` 결과 재사용), 액션 신호를 렌더링한다.
4. **렌더링 검증** — HTML을 재생성한 뒤, 로컬 서버(`python3 -m http.server` 등)로 띄워서 실제로 깨짐이 없는지 확인한다. 특히 다음을 확인한다.
   - 레이아웃 붕괴 여부
   - 가로 스크롤 발생 여부 (없어야 정상)
   - 표/카드가 잘리지 않는지
5. 검증 후 문제가 없으면 완료로 보고한다. 문제가 있으면 수정 후 다시 검증한다(재검증 없이 완료로 보고하지 않는다).

## 출력
- 갱신된 `output/briefs/YYYY-MM-DD.md`
- 갱신된 `output/dashboard.html`
- 검증 결과 요약(무엇을 확인했는지, 문제가 있었는지)

## 금지사항
- 검증 없이 "갱신 완료"라고 보고하지 않는다.
- 자동/주기적 실행을 스스로 제안하지 않는다 — 항상 호출 시에만 동작.
