"""
Gemini API 호출 래퍼
- 재시도 로직
- Rate limit 회피
- 토큰 사용량 로깅
"""
import time
from google import genai
from config import GEMINI_API_KEY, GEMINI_MODEL, GEMINI_RETRY, GEMINI_DELAY


class GeminiCaller:
    def __init__(self, api_key=None, model=None):
        self.client = genai.Client(api_key=api_key or GEMINI_API_KEY)
        self.model = model or GEMINI_MODEL
        self.total_calls = 0
        self.total_input_chars = 0
        self.total_output_chars = 0

    def call(self, prompt: str, label: str = "") -> str:
        """단일 호출 (재시도 포함)"""
        self.total_calls += 1
        self.total_input_chars += len(prompt)

        for attempt in range(GEMINI_RETRY + 1):
            try:
                response = self.client.models.generate_content(
                    model=self.model,
                    contents=prompt,
                )
                text = response.text or ""
                self.total_output_chars += len(text)
                if label:
                    print(f"    ✓ {label}: {len(text)}자 응답")
                return text
            except Exception as e:
                print(f"    ⚠ {label} 시도 {attempt+1}/{GEMINI_RETRY+1} 실패: {e}")
                if attempt < GEMINI_RETRY:
                    time.sleep(GEMINI_DELAY * (attempt + 1))
                else:
                    return f"[ERROR] Gemini 호출 실패: {e}"

    def call_with_delay(self, prompt: str, label: str = "") -> str:
        """호출 + rate limit 회피용 대기"""
        result = self.call(prompt, label)
        time.sleep(GEMINI_DELAY)
        return result

    def stats(self) -> dict:
        return {
            "total_calls": self.total_calls,
            "total_input_chars": self.total_input_chars,
            "total_output_chars": self.total_output_chars,
        }
