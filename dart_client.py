"""
DART OpenAPI 클라이언트
OpenDartReader 기반으로 데이터 수집
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
        """
        최근 정기보고서 목록
        kind: A=정기공시(사업/반기/분기 보고서)
        """
        end = datetime.today().strftime("%Y%m%d")
        start = (datetime.today().replace(year=datetime.today().year - 2)).strftime("%Y%m%d")
        reports = self.dart.list(stock_code, start=start, end=end, kind=kind)
        return reports.head(count) if reports is not None else pd.DataFrame()

    def get_latest_business_report(self, stock_code):
        """가장 최근 사업보고서 (연간)"""
        reports = self.get_recent_reports(stock_code, count=20)
        if reports.empty:
            return None
        # report_nm에 "사업보고서" 포함된 것 중 최신
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
        """
        재무제표 다년치
        fs_div: CFS=연결, OFS=별도
        반환: {연도: DataFrame}
        """
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

    def get_business_section(self, rcept_no):
        """
        보고서에서 '사업의 내용' 섹션 추출
        rcept_no: 접수번호
        """
        # 보고서 원문 다운로드 후 II. 사업의 내용 섹션 파싱
        try:
            content = self.dart.report(rcept_no, "사업의 내용")
            return content
        except Exception as e:
            print(f"[WARN] 사업의 내용 추출 실패: {e}")
            return None

    def get_shareholders(self, rcept_no):
        """최대주주 및 특수관계인 지분"""
        try:
            return self.dart.report(rcept_no, "최대주주현황")
        except Exception as e:
            print(f"[WARN] 최대주주 조회 실패: {e}")
            return None

    def get_executives(self, rcept_no):
        """임원 현황"""
        try:
            return self.dart.report(rcept_no, "임원현황")
        except Exception as e:
            print(f"[WARN] 임원현황 조회 실패: {e}")
            return None
