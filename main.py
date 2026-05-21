"""
DART 분석기 메인 진입점 (v0.2.1)
"""
import sys
import argparse
import time
import json
from datetime import datetime
from pathlib import Path

from config import REPORTS_DIR, ENABLED_MODULES, GEMINI_DELAY
from dart_client import DartClient
from extractors.financial import (
    parse_financial_data,
    calc_katsuma_metrics,
    calc_bulgom_safety,
    calc_growth_rates,
)
from extractors.business import parse_business_content, summarize_for_prompt
from analyzers.gemini_caller import GeminiCaller
from utils.report_builder import build_report, save_report
from utils.email_sender import send_report_email, extract_summary_from_report

from prompts.basic import BASIC_PROMPT
from prompts.tenbagger import TENBAGGER_PROMPT
from prompts.swing import SWING_PROMPT
from prompts.longterm import LONGTERM_PROMPT
from prompts.bulgom import BULGOM_PROMPT
from prompts.katsuma import KATSUMA_PROMPT
from prompts.scenario import SCENARIO_PROMPT
from prompts.final import FINAL_PROMPT


# ============================================================
# 1. 데이터 수집
# ============================================================
def collect_all_data(stock_code: str) -> dict:
    print(f"\n[1단계] DART 데이터 수집: {stock_code}")
    dart = DartClient()

    print("  → 기업 정보")
    company = dart.get_company_info(stock_code)

    print("  → 최근 사업/분기 보고서")
    biz_report = dart.get_latest_business_report(stock_code)
    q_report = dart.get_latest_quarterly_report(stock_code)

    print("  → 재무제표 5년 (연결)")
    fs_cfs = dart.get_financial_statements(stock_code, fs_div="CFS")
    print("  → 재무제표 5년 (별도)")
    fs_ofs = dart.get_financial_statements(stock_code, fs_div="OFS")

    business_content = None
    shareholders = None
    executives = None
    if biz_report is not None:
        print("  → 사업의 내용")
        business_content = dart.get_business_section(stock_code, biz_report)
        print("  → 최대주주 현황")
        shareholders = dart.get_shareholders(stock_code, biz_report)
        print("  → 임원 현황")
        executives = dart.get_executives(stock_code, biz_report)

    return {
        "company": company,
        "biz_report": biz_report,
        "q_report": q_report,
        "fs_consolidated": fs_cfs,
        "fs_separate": fs_ofs,
        "business_content": business_content,
        "shareholders": shareholders,
        "executives": executives,
    }


# ============================================================
# 2. 정량 사전계산
# ============================================================
def precompute_metrics(raw_data: dict) -> dict:
    print(f"\n[2단계] 정량 지표 사전계산")
    fs = raw_data["fs_consolidated"] or raw_data["fs_separate"]
    parsed = parse_financial_data(fs)

    print("  → 카츠미 지표")
    katsuma = calc_katsuma_metrics(parsed)
    print("  → 불곰 안전성")
    bulgom = calc_bulgom_safety(parsed)
    print("  → 성장률")
    growth = calc_growth_rates(parsed)

    print("  → 사업의 내용 파싱")
    business_parsed = parse_business_content(raw_data.get("business_content"))
    business_summary = summarize_for_prompt(business_parsed, max_chars=5000)

    return {
        "parsed": parsed,
        "katsuma": katsuma,
        "bulgom": bulgom,
        "growth": growth,
        "business_parsed": business_parsed,
        "business_summary": business_summary,
    }


# ============================================================
# 3. Gemini 분석
# ============================================================
def format_financial_table(parsed: dict) -> str:
    years = sorted(parsed.keys())
    if not years:
        return "재무 데이터 없음"
    rows = ["| 항목 | " + " | ".join(str(y) for y in years) + " |"]
    rows.append("|" + "------|" * (len(years) + 1))
    items = ["매출액", "영업이익", "당기순이익", "자산총계", "부채총계", "자본총계", "영업현금흐름"]
    for item in items:
        row = f"| {item} | "
        for y in years:
            val = parsed[y].get(item)
            row += f"{val:,.0f} | " if val else "- | "
        rows.append(row.rstrip())
    return "\n".join(rows)


def format_katsuma_table(katsuma: dict) -> str:
    years = sorted(katsuma.keys())
    if not years:
        return "데이터 없음"
    rows = ["| 연도 | 영업CF/영업이익 | 회수개월수 | 회계발생고비율 | ROA | 영업이익률 | CF패턴 |"]
    rows.append("|------|---|---|---|---|---|---|")
    for y in years:
        m = katsuma[y]
        rows.append(
            f"| {y} | "
            f"{m.get('영업CF_영업이익_비율', 0):.1f}% | "
            f"{m.get('회수개월수', 0):.2f}개월 | "
            f"{m.get('회계발생고_비율', 0):.1f}% | "
            f"{m.get('ROA', 0):.2f}% | "
            f"{m.get('영업이익률', 0):.2f}% | "
            f"{m.get('CF패턴', '-')} |"
        )
    return "\n".join(rows)


def format_bulgom_table(bulgom: dict) -> str:
    rows = ["| 항목 | 기준 | 실제값 | 통과 |"]
    rows.append("|------|------|--------|------|")
    for name, check in bulgom.get("checks", {}).items():
        val = check.get("value", check.get("values", "-"))
        pass_mark = "✅" if check.get("pass") else "❌"
        rows.append(f"| {name} | {check.get('기준', '-')} | {val} | {pass_mark} |")
    rows.append(f"\n**판정**: {bulgom.get('판정', '-')} ({bulgom.get('passed_count', 0)}/{bulgom.get('total', 6)})")
    return "\n".join(rows)


def format_growth_table(growth: dict) -> str:
    rows = ["**YoY**"]
    for y, items in growth.get("YoY", {}).items():
        rows.append(f"- {y}: " + ", ".join(f"{k} {v}%" for k, v in items.items()))
    rows.append("\n**CAGR**")
    for k, v in growth.get("CAGR", {}).items():
        rows.append(f"- {k}: {v}%")
    return "\n".join(rows)


def run_ai_analyses(raw_data: dict, metrics: dict) -> dict:
    print(f"\n[3단계] Gemini 영역별 분석 (7개 순차)")
    gemini = GeminiCaller()

    company_info = raw_data.get("company", {})
    company_name = company_info.get("corp_name", "?") if isinstance(company_info, dict) else "?"
    sector = company_info.get("induty_code", "?") if isinstance(company_info, dict) else "?"
    stock_code = company_info.get("stock_code", "?") if isinstance(company_info, dict) else "?"

    common_vars = {
        "company_name": company_name,
        "stock_code": stock_code,
        "sector": sector,
        "financial_summary_table": format_financial_table(metrics["parsed"]),
        "katsuma_metrics_table": format_katsuma_table(metrics["katsuma"]),
        "bulgom_safety_table": format_bulgom_table(metrics["bulgom"]),
        "growth_table": format_growth_table(metrics["growth"]),
        "business_summary": metrics["business_summary"],
        "notes_excerpt": "주석 추출 미구현",
        "current_price": "TBD (네이버 연동 시)",
        "market_cap": "TBD",
        "valuation_metrics": "PBR/PER TBD",
        "industry_band": "업종 밴드 TBD",
        "dividend_history": "배당 이력 TBD",
        "governance_info": str(raw_data.get("shareholders", "지배구조 정보 없음"))[:1000],
        "price_action": "TBD (네이버 연동 시)",
        "volume_trend": "TBD",
        "chart_data": "TBD",
        "supply_data": "TBD",
        "recent_news": "TBD",
    }

    results = {}
    modules = [
        ("basic", BASIC_PROMPT, "기본 분석"),
        ("tenbagger", TENBAGGER_PROMPT, "텐배거"),
        ("swing", SWING_PROMPT, "단타/스윙"),
        ("longterm", LONGTERM_PROMPT, "장기투자"),
        ("bulgom", BULGOM_PROMPT, "불곰식 6단계"),
        ("katsuma", KATSUMA_PROMPT, "카츠미 7대"),
    ]

    for key, template, name in modules:
        if not ENABLED_MODULES.get(key):
            print(f"  ⏭  {name}: 비활성")
            continue
        print(f"  ▶ {name} 실행")
        prompt = template.format(**common_vars)
        results[key] = gemini.call_with_delay(prompt, label=name)

    if ENABLED_MODULES.get("scenario"):
        print("  ▶ 상승 시나리오 (조건부)")
        prior = "\n\n".join([
            f"### {k}\n{v[:800]}" for k, v in results.items()
        ])
        scenario_vars = {**common_vars, "prior_analyses_summary": prior}
        results["scenario"] = gemini.call_with_delay(
            SCENARIO_PROMPT.format(**scenario_vars), label="시나리오"
        )

    if ENABLED_MODULES.get("final"):
        print("  ▶ 최종 종합판정")
        final_vars = {
            **common_vars,
            "basic_result": results.get("basic", "")[:2000],
            "tenbagger_result": results.get("tenbagger", "")[:1500],
            "swing_result": results.get("swing", "")[:1500],
            "longterm_result": results.get("longterm", "")[:1500],
            "bulgom_result": results.get("bulgom", "")[:1500],
            "katsuma_result": results.get("katsuma", "")[:2000],
            "scenario_result": results.get("scenario", "")[:1500],
        }
        results["final"] = gemini.call_with_delay(
            FINAL_PROMPT.format(**final_vars), label="최종"
        )

    print(f"\n  📊 Gemini 통계: {gemini.stats()}")
    return results


# ============================================================
# 4. 리포트 생성 + 이메일
# ============================================================
def finalize(stock_code: str, raw_data: dict, metrics: dict, ai_results: dict, send_email: bool):
    print(f"\n[4단계] 리포트 생성 및 발송")

    company_info = raw_data.get("company", {})
    company_name = company_info.get("corp_name", stock_code) if isinstance(company_info, dict) else stock_code
    sector = company_info.get("induty_code", "?") if isinstance(company_info, dict) else "?"

    content = build_report(stock_code, company_name, sector, raw_data, metrics, ai_results)
    filepath = save_report(content, stock_code, REPORTS_DIR)
    print(f"  → 저장: {filepath}")

    if send_email:
        summary = extract_summary_from_report(content)
        send_report_email(stock_code, company_name, summary, filepath)

    return filepath


# ============================================================
# 진입점
# ============================================================
def analyze_single(stock_code: str, skip_scenario: bool, send_email: bool):
    if skip_scenario:
        ENABLED_MODULES["scenario"] = False

    start = time.time()
    print(f"\n🔍 종목코드: {stock_code}")
    print(f"⏱  시작: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    try:
        raw = collect_all_data(stock_code)
        metrics = precompute_metrics(raw)
        ai_results = run_ai_analyses(raw, metrics)
        filepath = finalize(stock_code, raw, metrics, ai_results, send_email)

        elapsed = time.time() - start
        print(f"\n✅ 완료! 소요시간: {elapsed:.1f}초")
        print(f"📄 리포트: {filepath}")
        return filepath
    except Exception as e:
        print(f"\n❌ 분석 실패: {e}")
        import traceback
        traceback.print_exc()
        return None


def analyze_watchlist(send_email: bool):
    watchlist_path = Path(__file__).parent / "watchlist.csv"
    if not watchlist_path.exists():
        print(f"❌ {watchlist_path} 없음")
        return

    import csv
    with open(watchlist_path, encoding="utf-8") as f:
        reader = csv.reader(f)
        codes = [row[0].strip() for row in reader if row and row[0].strip() and not row[0].startswith("#")]

    print(f"📋 일괄 분석: {len(codes)}개 종목")
    for i, code in enumerate(codes, 1):
        print(f"\n{'='*60}")
        print(f"[{i}/{len(codes)}] {code}")
        print(f"{'='*60}")
        analyze_single(code, skip_scenario=False, send_email=send_email)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("stock_code", nargs="?", help="종목코드 (예: 005930)")
    parser.add_argument("--skip-scenario", action="store_true")
    parser.add_argument("--no-email", action="store_true", help="이메일 발송 안 함")
    parser.add_argument("--watchlist", action="store_true", help="watchlist.csv 일괄 처리")
    args = parser.parse_args()

    send_email = not args.no_email

    if args.watchlist:
        analyze_watchlist(send_email)
    elif args.stock_code:
        analyze_single(args.stock_code, args.skip_scenario, send_email)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
