"""
DART OpenAPI 클라이언트 (v0.2.1 수정)
- report() 메서드에 bsns_year 인자 추가
"""
import OpenDartReader
import pandas as pd
from datetime import datetime
from config import DART_API_KEY, YEARS_TO_FETCH


class DartClient:
    def __init__(self, api_key=None):
        self.dart = OpenDartReader(api_key or DART_API_KEY)

    def get_company_info(self, stock_code):
        """기업 기본정보"""
        return self.dart.company(stock_code)

    def get_recent_reports(self, stock_code, kind="A", count=10):
        """최근 정기보고서 목록"""
        end = datetime.today().strftime("%Y%m%d")
        start = (datetime.today().replace(year=datetime.today().year - 2)).strftime("%Y%m%d")
        reports = self.dart.list(stock_code, start=start, end=end, kind=kind)
        return reports.head(count) if reports is not None else pd.DataFrame()

    def get_latest_business_report(self, stock_code):
        """가장 최근 사업보고서"""
        reports = self.get_recent_reports(stock_code, count=20)
        if reports.empty:
            return None
        biz = reports[reports["report_nm"].str.contains("사업보고서", na=False)]
        return biz.iloc[0] if not biz.empty else None

    def get_latest_quarterly_report(self, stock_code):
        """가장 최근 분기/반기 보고서"""
        reports = self.get_recent_reports(stock_code, count=20)
        if reports.empty:
            return None
        q = reports[reports["report_nm"].str.contains("분기보고서|반기보고서", na=False)]
        return q.iloc[0] if not q.empty else None

    def get_financial_statements(self, stock_code, years=YEARS_TO_FETCH, fs_div="CFS"):
        """재무제표 다년치"""
        current_year = datetime.today().year
        result = {}
        for y in range(current_year - years, current_year):
            try:
                fs = self.dart.finstate_all(stock_code, y, fs_div=fs_div)
                if fs is not None and not fs.empty:
                    result[y] = fs
            except Exception as e:
                print(f"[WARN] {y}년 {fs_div} 재무제표 조회 실패: {e}")
        return result

    def _get_business_year_from_report(self, report_row):
        """보고서 row에서 사업연도 추출 (rcept_dt 기준)"""
        try:
            rcept_dt = str(report_row.get("rcept_dt", ""))
            if len(rcept_dt) >= 4:
                # 접수일 기준 전년도가 사업연도 (사업보고서는 보통 3월 제출)
                return int(rcept_dt[:4]) - 1
        except Exception:
            pass
        return datetime.today().year - 1

    def get_business_section(self, stock_code, biz_report_row):
        """사업의 내용 추출 (stock_code + bsns_year 필요)"""
        if biz_report_row is None:
            return None
        bsns_year = self._get_business_year_from_report(biz_report_row)
        try:
            return self.dart.report(stock_code, "사업의 내용", bsns_year)
        except Exception as e:
            print(f"[WARN] 사업의 내용 추출 실패 ({bsns_year}): {e}")
            try:
                return self.dart.report(stock_code, "사업의 내용", bsns_year - 1)
            except Exception as e2:
                print(f"[WARN] 사업의 내용 재시도 실패 ({bsns_year-1}): {e2}")
                return None

    def get_shareholders(self, stock_code, biz_report_row):
        """최대주주 현황"""
        if biz_report_row is None:
            return None
        bsns_year = self._get_business_year_from_report(biz_report_row)
        try:
            return self.dart.report(stock_code, "최대주주", bsns_year)
        except Exception as e:
            print(f"[WARN] 최대주주 조회 실패 ({bsns_year}): {e}")
            return None

    def get_executives(self, stock_code, biz_report_row):
        """임원 현황"""
        if biz_report_row is None:
            return None
        bsns_year = self._get_business_year_from_report(biz_report_row)
        try:
            return self.dart.report(stock_code, "임원", bsns_year)
        except Exception as e:
            print(f"[WARN] 임원현황 조회 실패 ({bsns_year}): {e}")
            return None
