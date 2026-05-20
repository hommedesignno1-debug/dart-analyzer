"""
Gmail SMTP 이메일 발송
기존 네이버 파이프라인과 동일한 방식 (앱 비밀번호 사용)

환경변수:
- GMAIL_USER: 발신/수신 이메일 (hommedesign.no1@gmail.com)
- GMAIL_APP_PASSWORD: Gmail 앱 비밀번호
"""
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from pathlib import Path


def send_report_email(
    stock_code: str,
    company_name: str,
    summary: str,
    full_report_path: Path,
    recipient: str = None,
):
    """
    분석 리포트를 이메일로 발송
    - 본문: 핵심 요약 (종합점수, 매수/매도 액션)
    - 첨부: 전체 Markdown 리포트
    """
    sender = os.environ.get("GMAIL_USER", "hommedesign.no1@gmail.com")
    password = os.environ.get("GMAIL_APP_PASSWORD")
    to = recipient or sender

    if not password:
        print("[ERROR] GMAIL_APP_PASSWORD 환경변수 없음")
        return False

    msg = MIMEMultipart()
    msg["From"] = sender
    msg["To"] = to
    msg["Subject"] = f"[DART 분석] {company_name} ({stock_code}) - {Path(full_report_path).stem}"

    # 본문 (HTML 형식)
    body = f"""
<h2>📊 {company_name} ({stock_code}) DART 종합 분석</h2>
<hr>
<h3>핵심 요약</h3>
<pre style="background:#f5f5f5;padding:15px;border-radius:5px;font-family:'D2Coding',monospace;">
{summary}
</pre>
<p><b>상세 리포트는 첨부파일을 참고해 주세요.</b></p>
<p style="color:#888;font-size:12px;">자동 생성 - DART Analyzer</p>
"""
    msg.attach(MIMEText(body, "html", "utf-8"))

    # 첨부파일
    if full_report_path and Path(full_report_path).exists():
        with open(full_report_path, "rb") as f:
            attach = MIMEBase("application", "octet-stream")
            attach.set_payload(f.read())
        encoders.encode_base64(attach)
        attach.add_header(
            "Content-Disposition",
            f"attachment; filename={Path(full_report_path).name}",
        )
        msg.attach(attach)

    # 전송
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(sender, password)
            server.sendmail(sender, to, msg.as_string())
        print(f"✅ 이메일 발송 완료: {to}")
        return True
    except Exception as e:
        print(f"[ERROR] 이메일 발송 실패: {e}")
        return False


def extract_summary_from_report(report_text: str, max_lines: int = 30) -> str:
    """리포트에서 종합 점수표 + 최종 액션 부분만 추출"""
    lines = report_text.split("\n")

    # "종합 점수표" 또는 "최종 액션" 섹션 찾기
    summary_start = None
    for i, line in enumerate(lines):
        if "종합 점수표" in line or "최종 액션" in line or "최종 결론" in line:
            summary_start = i
            break

    if summary_start is not None:
        return "\n".join(lines[summary_start:summary_start + max_lines])
    else:
        # 첫 30줄 반환
        return "\n".join(lines[:max_lines])
