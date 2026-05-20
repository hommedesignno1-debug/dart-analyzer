"""
재무제표 추출 및 정량 사전계산

카츠미 7대 체크리스트의 정량 지표와
불곰 1단계 재무 안전성 지표를
Python에서 미리 계산하여 Gemini에 전달.
이로써 Gemini의 자릿수 실수, 계산 누락을 방지.
"""
import pandas as pd
from typing import Dict, List, Optional


# DART 표준 계정과목 ID (XBRL 태그 기준)
ACCOUNT_TAGS = {
    "매출액": ["ifrs-full_Revenue", "ifrs_Revenue", "Revenue"],
    "영업이익": ["dart_OperatingIncomeLoss", "OperatingIncomeLoss"],
    "당기순이익": ["ifrs-full_ProfitLoss", "ProfitLoss"],
    "자산총계": ["ifrs-full_Assets", "Assets"],
    "부채총계": ["ifrs-full_Liabilities", "Liabilities"],
    "자본총계": ["ifrs-full_Equity", "Equity"],
    "유동자산": ["ifrs-full_CurrentAssets", "CurrentAssets"],
    "유동부채": ["ifrs-full_CurrentLiabilities", "CurrentLiabilities"],
    "매출채권": ["dart_ShortTermTradeReceivable", "TradeAndOtherCurrentReceivables"],
    "재고자산": ["ifrs-full_Inventories", "Inventories"],
    "영업현금흐름": ["ifrs-full_CashFlowsFromUsedInOperatingActivities"],
    "투자현금흐름": ["ifrs-full_CashFlowsFromUsedInInvestingActivities"],
    "재무현금흐름": ["ifrs-full_CashFlowsFromUsedInFinancingActivities"],
    "이자비용": ["ifrs-full_InterestExpense", "FinanceCosts"],
}


def extract_value(fs_df: pd.DataFrame, tag_candidates: List[str]) -> Optional[float]:
    """재무제표에서 특정 계정 값 추출"""
    if fs_df is None or fs_df.empty:
        return None
    for tag in tag_candidates:
        match = fs_df[fs_df["account_id"].str.contains(tag, case=False, na=False)]
        if not match.empty:
            try:
                # thstrm_amount = 당기금액
                val = match.iloc[0].get("thstrm_amount")
                if val and str(val).strip():
                    return float(str(val).replace(",", ""))
            except (ValueError, TypeError):
                continue
    return None


def parse_financial_data(fs_dict: Dict[int, pd.DataFrame]) -> Dict[int, Dict]:
    """다년치 재무제표를 표준화된 dict로 변환"""
    result = {}
    for year, fs in fs_dict.items():
        if fs is None or fs.empty:
            continue
        year_data = {}
        for name, tags in ACCOUNT_TAGS.items():
            year_data[name] = extract_value(fs, tags)
        result[year] = year_data
    return result


# =================================================================
# 카츠미 정량 지표
# =================================================================

def calc_katsuma_metrics(parsed: Dict[int, Dict]) -> Dict:
    """
    카츠미 7대 체크리스트의 정량 지표 계산
    """
    metrics = {}
    years = sorted(parsed.keys())

    for y in years:
        d = parsed[y]
        m = {}

        # 1. 영업CF ÷ 영업이익 (60~120%가 정상)
        if d.get("영업현금흐름") and d.get("영업이익") and d["영업이익"] != 0:
            m["영업CF_영업이익_비율"] = d["영업현금흐름"] / d["영업이익"] * 100
        else:
            m["영업CF_영업이익_비율"] = None

        # 2. 회수 개월 수 = 매출채권 ÷ (매출 ÷ 12)
        if d.get("매출채권") and d.get("매출액") and d["매출액"] != 0:
            m["회수개월수"] = d["매출채권"] / (d["매출액"] / 12)
        else:
            m["회수개월수"] = None

        # 3. 회계발생고 = 당기순이익 - 영업CF (높을수록 이익의 질 낮음)
        if d.get("당기순이익") and d.get("영업현금흐름"):
            m["회계발생고"] = d["당기순이익"] - d["영업현금흐름"]
            if d["당기순이익"] != 0:
                m["회계발생고_비율"] = m["회계발생고"] / abs(d["당기순이익"]) * 100
        else:
            m["회계발생고"] = None
            m["회계발생고_비율"] = None

        # 4. ROA = 당기순이익 ÷ 자산총계
        if d.get("당기순이익") and d.get("자산총계") and d["자산총계"] != 0:
            m["ROA"] = d["당기순이익"] / d["자산총계"] * 100
        else:
            m["ROA"] = None

        # 5. 운전자금 = 재고 + 매출채권 (외상구매대금/지불어음은 DART에서 분리 어려움)
        m["운전자금_단순"] = (d.get("재고자산") or 0) + (d.get("매출채권") or 0)

        # 6. 영업이익률
        if d.get("영업이익") and d.get("매출액") and d["매출액"] != 0:
            m["영업이익률"] = d["영업이익"] / d["매출액"] * 100
        else:
            m["영업이익률"] = None

        # 7. CF 패턴 (영업/투자/재무 부호)
        op_cf = d.get("영업현금흐름")
        inv_cf = d.get("투자현금흐름")
        fin_cf = d.get("재무현금흐름")
        if all(v is not None for v in [op_cf, inv_cf, fin_cf]):
            pattern = ""
            pattern += "+" if op_cf > 0 else "-"
            pattern += "+" if inv_cf > 0 else "-"
            pattern += "+" if fin_cf > 0 else "-"
            m["CF패턴"] = pattern
            m["CF패턴_해석"] = {
                "+--": "이상적 (영업창출+투자+부채상환)",
                "++-": "투자축소 (수확기)",
                "+-+": "성장기 (영업+투자확대+조달)",
                "-++": "위험 (영업부진+자산매각+조달)",
                "--+": "위험 (영업적자+투자+조달)",
                "---": "최악 (영업적자+투자+부채상환)",
            }.get(pattern, "혼합형")
        else:
            m["CF패턴"] = None

        metrics[y] = m

    return metrics


# =================================================================
# 불곰 정량 지표
# =================================================================

def calc_bulgom_safety(parsed: Dict[int, Dict]) -> Dict:
    """
    불곰 1단계 재무 안전성 6개 항목 자동 판정
    """
    years = sorted(parsed.keys())
    recent_3 = years[-3:] if len(years) >= 3 else years

    result = {
        "checks": {},
        "passed_count": 0,
        "yearly_metrics": {},
    }

    # 1. 부채비율 100% 이하 (최근 연도 기준)
    latest = parsed[years[-1]] if years else {}
    if latest.get("부채총계") and latest.get("자본총계") and latest["자본총계"] != 0:
        debt_ratio = latest["부채총계"] / latest["자본총계"] * 100
        result["checks"]["부채비율_100이하"] = {
            "value": round(debt_ratio, 1),
            "pass": debt_ratio <= 100,
            "기준": "100% 이하"
        }

    # 2. 유동비율 150% 이상
    if latest.get("유동자산") and latest.get("유동부채") and latest["유동부채"] != 0:
        current_ratio = latest["유동자산"] / latest["유동부채"] * 100
        result["checks"]["유동비율_150이상"] = {
            "value": round(current_ratio, 1),
            "pass": current_ratio >= 150,
            "기준": "150% 이상"
        }

    # 3. 영업이익 3년 연속 흑자
    op_profits = [parsed[y].get("영업이익") for y in recent_3]
    op_positive = all(v is not None and v > 0 for v in op_profits)
    result["checks"]["영업이익_3년흑자"] = {
        "values": op_profits,
        "pass": op_positive,
        "기준": "최근 3년 연속 흑자"
    }

    # 4. 당기순이익 3년 연속 흑자
    net_profits = [parsed[y].get("당기순이익") for y in recent_3]
    net_positive = all(v is not None and v > 0 for v in net_profits)
    result["checks"]["순이익_3년흑자"] = {
        "values": net_profits,
        "pass": net_positive,
        "기준": "최근 3년 연속 흑자"
    }

    # 5. 이자보상배율 3배 이상 (영업이익 ÷ 이자비용)
    if latest.get("영업이익") and latest.get("이자비용") and latest["이자비용"] != 0:
        icr = latest["영업이익"] / abs(latest["이자비용"])
        result["checks"]["이자보상배율_3배이상"] = {
            "value": round(icr, 2),
            "pass": icr >= 3,
            "기준": "3배 이상"
        }

    # 6. 영업현금흐름 3년 연속 플러스
    op_cfs = [parsed[y].get("영업현금흐름") for y in recent_3]
    cf_positive = all(v is not None and v > 0 for v in op_cfs)
    result["checks"]["영업CF_3년플러스"] = {
        "values": op_cfs,
        "pass": cf_positive,
        "기준": "3년 연속 플러스"
    }

    # 통과 개수
    result["passed_count"] = sum(1 for c in result["checks"].values() if c.get("pass"))
    result["total"] = len(result["checks"])

    # 판정
    if result["passed_count"] >= 6:
        result["판정"] = "재무 안전성 합격"
    elif result["passed_count"] >= 4:
        result["판정"] = "조건부 통과 - 주의 필요"
    else:
        result["판정"] = "재무 안전성 미달 - 불곰식 기준 탈락"

    return result


# =================================================================
# 성장률 계산 (Part1 기본분석용)
# =================================================================

def calc_growth_rates(parsed: Dict[int, Dict]) -> Dict:
    """YoY 증감율 및 CAGR"""
    years = sorted(parsed.keys())
    result = {"YoY": {}, "CAGR": {}}

    for i in range(1, len(years)):
        y, prev = years[i], years[i-1]
        yoy = {}
        for metric in ["매출액", "영업이익", "당기순이익"]:
            cur, prv = parsed[y].get(metric), parsed[prev].get(metric)
            if cur and prv and prv != 0:
                yoy[metric] = round((cur - prv) / abs(prv) * 100, 1)
        result["YoY"][y] = yoy

    # CAGR (시작년 vs 최종년)
    if len(years) >= 2:
        first, last = years[0], years[-1]
        n = last - first
        for metric in ["매출액", "영업이익", "당기순이익"]:
            start, end = parsed[first].get(metric), parsed[last].get(metric)
            if start and end and start > 0 and end > 0 and n > 0:
                cagr = ((end / start) ** (1/n) - 1) * 100
                result["CAGR"][metric] = round(cagr, 1)

    return result
