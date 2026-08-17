# 보유 현황 (수동 갱신) — 예시 템플릿

이 파일은 형식 참고용 예시입니다. 실제 보유 현황은 `data/portfolio.md`(gitignore 처리됨, 로컬에만 존재)에 기록합니다.
`portfolio-cockpit`, `daily-brief`, `dashboard-refresh` 스킬은 `data/portfolio.md`를 읽습니다 — 그 파일이 없으면 먼저 사용자에게 입력을 요청합니다.

마지막 갱신일: YYYY-MM-DD

| 종목/티커 | 자산유형 | 통화 | 수량 | 평가금액 | 비고 |
|---|---|---|---|---|---|
| 예시: AAPL | 개별주 | USD | 0 | 0 | 예시 행 |
| 예시: SPY | 지수 ETF | USD | 0 | 0 | 예시 행 |
| 예시: GLD | 원자재 ETF | USD | 0 | 0 | 예시 행 |

<!-- 자산유형 값: 개별주 / 지수 ETF / 액티브 ETF(커버드콜 등) / 원자재 ETF / 채권 / 현금 -->
