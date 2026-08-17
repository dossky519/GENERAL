# 투자 리서치 어시스턴트 — 프로젝트 안내

이 저장소는 개인 투자자를 위한 **리서치 보조 시스템**입니다. Claude Code Skills로 구성되어 있으며, **매매 판단은 사용자가 직접 하고 AI는 리서치·정리·계산·모니터링만 합니다.**

## 구조
- `.claude/skills/investing-principles.md` — 모든 스킬이 공유하는 5원칙(헌법). 어떤 스킬을 실행하든 이 문서를 먼저 읽는다.
- `.claude/skills/company-decoder/` — 기업 해독기 (2층, 온디맨드): "이 회사 뭐 하는 회사야?"
- `.claude/skills/story-reader/` — 스토리 리더 (2층, 온디맨드): "요즘 이 회사 어때?"
- `.claude/skills/price-decoder/` — 가격 판독기 (2층, 온디맨드): "지금 사도 되나?" (역DCF)
- `.claude/skills/portfolio-cockpit/` — 포트폴리오 콕핏 (1.5층): 포트폴리오 종합 진단
- `.claude/skills/daily-brief/` — 일일 브리핑 (1층, 오케스트레이터): 매일 훑고 액션 신호 제시
- `.claude/skills/dashboard-refresh/` — 대시보드 갱신 (1층, 호출 시에만 실행)
- `data/portfolio.md` — 사용자가 수동으로 갱신하는 실제 보유 현황 (실시간 계좌 연동 없음). **`.gitignore` 처리되어 있어 로컬에만 존재** — 없으면 `data/portfolio.example.md` 형식을 참고해 사용자에게 입력을 요청한다.
- `data/watchlist.md` — 실제 관심 종목/테마. 마찬가지로 `.gitignore` 처리됨 — 형식은 `data/watchlist.example.md` 참고.
- `output/briefs/`, `output/cards/`, `output/dashboard.html` — 스킬 실행 결과. 계좌 성격의 데이터를 담을 수 있어 기본적으로 `.gitignore` 처리됨(폴더 구조만 git에 유지). 공유하고 싶은 결과만 사용자가 선택적으로 커밋한다.

## 절대 규칙
1. 출처 없는 숫자를 쓰지 않는다. 페이지 번호를 추측하지 않는다.
2. 모든 계산은 코드 실행으로 한다.
3. `[사실]`과 `[해석]`을 구분한다.
4. 매수/매도 신호를 말하지 않는다. "어디를 더 파야 하는지"만 제시한다.
5. 이 시스템의 결론은 투자 자문이 아니다 — 1차 스크리너일 뿐이다.

자세한 내용은 `README.md`와 각 스킬의 `SKILL.md`를 참고한다.
