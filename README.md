# DART 종합 분석기 v0.2

DART 전자공시 기반 한국 주식 종합 분석.
**카츠미 7대 체크리스트 + 불곰식 6단계 + 텐배거/단타/장투 + 상승 시나리오** 통합.
GitHub Actions로 PC 없이 자동/수동 실행.

## 분석 모듈 (총 8개)

| # | 모듈 | 출처 | 비고 |
|---|------|------|------|
| 1 | 기본 분석 | Part1 | 10개 항목 (한 줄 정의 → 매수전략) |
| 2 | 텐배거 탐지 | Part2-1 | 3·5·10배 가능성 |
| 3 | 단타/스윙 | Part2-2 | 1주~3개월 |
| 4 | 장기투자 | Part2-3 | 3~10년 |
| 5 | 불곰식 6단계 | Part2-5 | 재무안전성+저PBR+안전마진 |
| 6 | 카츠미 7대 | Part3 | 이익의 질 검증 |
| 7 | 상승 시나리오 | Part4 (조건부) | 5단계 탑다운 |
| 8 | 최종 종합판정 | Part5 | 9개 점수표 + 실전 액션 |

## 정량 지표 자동계산 (Python 사전계산)

**Gemini가 계산 실수하지 않도록 Python에서 미리 산출:**

### 카츠미 지표
- 영업CF ÷ 영업이익 비율 (정상 60~120%)
- 회수개월수 (매출채권 ÷ 월매출, 1.5→2.5 급증 시 의심)
- 회계발생고 (당기순이익 − 영업CF)
- ROA 5년 추이
- CF 패턴 (+/−/− 등)
- 영업이익률

### 불곰 1단계 재무 안전성 (6개 자동 판정)
- 부채비율 100% 이하
- 유동비율 150% 이상
- 영업이익 3년 연속 흑자
- 당기순이익 3년 연속 흑자
- 이자보상배율 3배 이상
- 영업현금흐름 3년 플러스

## 설치 & 초기 설정

### 1) DART API 키 발급
- https://opendart.fss.or.kr → 인증키 신청
- 무료, 일 20,000건

### 2) GitHub Secrets 등록
레포 Settings → Secrets → Actions에서 추가:
- `DART_API_KEY`
- `GEMINI_API_KEY` (기존 사용 키 그대로)
- `GMAIL_USER` = `hommedesign.no1@gmail.com`
- `GMAIL_APP_PASSWORD` (기존 사용 키 그대로)

### 3) 로컬 테스트 (선택)
```bash
pip install -r requirements.txt
export DART_API_KEY="발급키"
export GEMINI_API_KEY="기존키"
export GMAIL_USER="hommedesign.no1@gmail.com"
export GMAIL_APP_PASSWORD="기존_앱비밀번호"
python main.py 005930
```

## 사용법

### A. 수동 실행 (GitHub Actions)
1. 레포 → Actions 탭
2. "DART 수동 분석" 선택
3. Run workflow 클릭
4. 종목코드 입력 (예: 005930) → Run
5. **2분 뒤 hommedesign.no1@gmail.com에 분석 리포트 도착**

**모바일에서 가능** — GitHub 앱이나 모바일 웹에서 동일하게 실행.

### B. 자동 스케줄
- `watchlist.csv`에 종목코드 추가
- 매일 아침 8시(KST) 자동 실행
- 분석 결과는 이메일 + 레포 `reports/` 폴더에 커밋

### C. 로컬 실행
```bash
python main.py 005930              # 단일 종목
python main.py --watchlist          # 일괄 처리
python main.py 005930 --no-email   # 이메일 없이
python main.py 005930 --skip-scenario
```

## 실행 흐름

```
[1] DART 데이터 수집 (~30초)
    ├─ 기업 정보
    ├─ 사업/분기 보고서
    ├─ 재무제표 5년 (연결+별도)
    ├─ 사업의 내용 전문
    └─ 지배구조 (최대주주, 임원)

[2] 정량 사전계산 (~1초)
    ├─ 카츠미 지표 6종
    ├─ 불곰 안전성 6종 자동 판정
    ├─ YoY/CAGR
    └─ 사업의 내용 파싱

[3] Gemini 분석 (~80초, 7~8회 순차 호출)
    ├─ 기본 분석
    ├─ 텐배거
    ├─ 단타/스윙
    ├─ 장기투자
    ├─ 불곰식 6단계 (정량값 주입)
    ├─ 카츠미 7대 (정량값 주입)
    ├─ 상승 시나리오 (조건부)
    └─ 최종 종합판정 (앞 결과 종합)

[4] Markdown 리포트 + 이메일 (~5초)
    ├─ reports/{종목코드}_{타임스탬프}.md 저장
    └─ Gmail로 본문 요약 + 첨부파일 발송
```

**총 소요시간: 약 2분**

## 파일 구조

```
dart_analyzer/
├── config.py                       # 환경설정, 모듈 토글
├── dart_client.py                  # DART API 래퍼
├── main.py                          # 진입점
├── requirements.txt
├── watchlist.csv                    # 자동 분석 대상
├── extractors/
│   ├── financial.py                # 카츠미/불곰 정량 자동계산
│   └── business.py                  # 사업의 내용 HTML 파싱
├── analyzers/
│   └── gemini_caller.py            # Gemini 호출 (재시도, rate limit)
├── prompts/                          # 8개 영역별 프롬프트
│   ├── basic.py
│   ├── tenbagger.py
│   ├── swing.py
│   ├── longterm.py
│   ├── bulgom.py
│   ├── katsuma.py
│   ├── scenario.py
│   └── final.py
├── utils/
│   ├── email_sender.py             # Gmail SMTP
│   └── report_builder.py            # Markdown 조립
├── reports/                          # 분석 리포트 출력
└── .github/workflows/
    ├── manual_analysis.yml         # 수동 실행
    └── scheduled_analysis.yml       # 자동 스케줄
```

## 비용 (예상)

- DART API: **무료** (일 20,000건 / 종목당 ~10건 사용)
- Gemini API: 종목당 7~8회 호출, flash 모델 = **거의 0원**
- GitHub Actions: 퍼블릭 레포 무료 / 프라이빗 월 2,000분 무료
  - 종목당 2분 = 한 달 1,000개 분석 가능

## 한계 및 향후 확장

**현재 v0.2 한계**
- 주가/시총/PER/PBR은 TBD (네이버 연동 시 추가)
- 단타/스윙 분석은 차트 데이터 부재로 불완전
- 사업의 내용 파싱은 휴리스틱 (회사별로 정확도 차이)

**v0.3 계획**
- 기존 네이버 파이프라인과 통합 (가격·수급 데이터 결합)
- 주석(Notes) 본문 파싱 추가 (충당금/특수관계자/우발부채)
- Google Sheets 자동 누적 (점수표 시계열 추적)
