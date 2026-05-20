"""
사업의 내용 HTML 파싱

DART의 정기보고서는 II. 사업의 내용 섹션이 가장 풍부한 정보를 담고 있다.
이 섹션을 추출하여 Gemini에 적절히 분할 전달.
"""
from bs4 import BeautifulSoup
import re


def parse_business_content(html_text: str) -> dict:
    """
    사업의 내용 HTML을 구조화된 dict로 변환
    """
    if not html_text:
        return {"raw": "", "sections": {}}

    soup = BeautifulSoup(html_text, "lxml")

    # 텍스트 추출
    text = soup.get_text(separator="\n", strip=True)

    # 섹션 분리 (1. 사업의 개요 / 2. 주요 제품 및 서비스 / 3. 원재료 및 생산설비 등)
    sections = {}
    section_patterns = [
        ("사업의 개요", r"1\.\s*사업의\s*개요"),
        ("주요 제품 및 서비스", r"2\.\s*주요\s*제품.*?서비스"),
        ("원재료 및 생산설비", r"3\.\s*원재료.*?생산설비"),
        ("매출 및 수주상황", r"4\.\s*매출.*?수주"),
        ("위험관리 및 파생거래", r"5\.\s*위험관리"),
        ("주요계약 및 연구개발활동", r"6\.\s*주요계약.*?연구개발"),
        ("기타 참고사항", r"7\.\s*기타\s*참고"),
    ]

    # 가장 단순한 접근: 각 섹션 헤더 위치 찾고 그 사이 텍스트 추출
    positions = []
    for name, pattern in section_patterns:
        match = re.search(pattern, text)
        if match:
            positions.append((match.start(), name))

    positions.sort()
    for i, (start, name) in enumerate(positions):
        end = positions[i+1][0] if i+1 < len(positions) else len(text)
        sections[name] = text[start:end].strip()

    return {
        "raw": text,
        "sections": sections,
        "length": len(text),
    }


def summarize_for_prompt(parsed: dict, max_chars: int = 5000) -> str:
    """
    Gemini 프롬프트용 요약 (토큰 절약)
    핵심 섹션 우선, 나머지는 잘라냄
    """
    if not parsed or not parsed.get("sections"):
        return parsed.get("raw", "")[:max_chars]

    priority_sections = [
        "사업의 개요",
        "주요 제품 및 서비스",
        "매출 및 수주상황",
        "원재료 및 생산설비",
    ]

    parts = []
    remaining = max_chars
    for name in priority_sections:
        if name in parsed["sections"] and remaining > 0:
            content = parsed["sections"][name]
            allocated = min(len(content), remaining // (len(priority_sections) - parts.__len__()))
            parts.append(f"### {name}\n{content[:allocated]}")
            remaining -= allocated

    return "\n\n".join(parts)


def extract_customers(parsed: dict) -> list:
    """주요 고객사 추출 시도"""
    text = parsed.get("raw", "")
    # 패턴: "삼성전자", "SK하이닉스" 등 대문자/한글 회사명
    # 간단한 휴리스틱이므로 100% 정확하지 않음
    customers = re.findall(r"(?:주요\s*거래처|주요\s*고객사|매출처)[\s:：]*([^\n]{5,200})", text)
    return customers[:5]
