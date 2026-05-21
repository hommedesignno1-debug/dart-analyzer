"""
DART 분석기 환경설정
"""
import os
from pathlib import Path

# ===== API 키 (환경변수 또는 .env에서 로드) =====
DART_API_KEY = os.environ.get("DART_API_KEY", "여기에_DART_API_KEY_입력")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "여기에_GEMINI_API_KEY_입력")

# ===== 분석 설정 =====
YEARS_TO_FETCH = 5              # 재무제표 과거 데이터 (카츠미 권장)
FETCH_BOTH_CONSOLIDATED = True  # 연결 + 별도 둘 다
GEMINI_MODEL = "gemini-2.5-flash"  # 기존 파이프라인과 동일

# ===== 경로 =====
BASE_DIR = Path(__file__).parent
REPORTS_DIR = BASE_DIR / "reports"
CACHE_DIR = BASE_DIR / "cache"
REPORTS_DIR.mkdir(exist_ok=True)
CACHE_DIR.mkdir(exist_ok=True)

# ===== Gemini 호출 설정 =====
GEMINI_TIMEOUT = 120     # 단일 호출 타임아웃 (초)
GEMINI_RETRY = 2         # 실패 시 재시도 횟수
GEMINI_DELAY = 1         # 호출 간 대기 (rate limit 회피)

# ===== 분석 모듈 활성화 =====
ENABLED_MODULES = {
    "basic": True,        # Part1 기본 분석
    "tenbagger": True,    # Part2-확장1 텐배거
    "swing": True,        # Part2-확장2 단타/스윙
    "longterm": True,     # Part2-확장3 장기투자
    "bulgom": True,       # Part2-확장5 불곰 6단계
    "katsuma": True,      # Part3 카츠미 7대 체크리스트
    "scenario": True,     # Part4 상승 시나리오 (조건부)
    "final": True,        # Part5 최종 종합판정
}
