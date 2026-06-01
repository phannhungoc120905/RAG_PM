from pathlib import Path

import cv2
import httpx
import pytesseract

from config import settings

TESSERACT_CMD = r"E:\Tesseract-OCR\tesseract.exe"
IMAGE_PATH = Path(r"E:\PM_RAG\RAG_PM\img2.jpg")
OUTPUT_PATH = Path(r"E:\PM_RAG\RAG_PM\dich.txt")
LLM_URL = getattr(settings, "LLM_URL", "http://localhost:11434/api/generate")
LLM_MODEL = getattr(settings, "LLM_MODEL", "llama3.2:latest")

pytesseract.pytesseract.tesseract_cmd = TESSERACT_CMD

image = cv2.imread(str(IMAGE_PATH))
if image is None:
    raise FileNotFoundError(f"Khong doc duoc anh: {IMAGE_PATH}")

gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
blur = cv2.GaussianBlur(gray, (5, 5), 0)
_, thresh = cv2.threshold(
    blur,
    0,
    255,
    cv2.THRESH_BINARY + cv2.THRESH_OTSU,
)

text = pytesseract.image_to_string(thresh, lang="vie+eng")
print("===== OCR RAW =====")
print(text[:3000])
print("===================")

prompt = f"""
Bạn là công cụ hậu xử lý OCR.

YÊU CẦU BẮT BUỘC:

- Văn bản đầu vào là tiếng Việt.
- GIỮ NGUYÊN tiếng Việt có dấu.
- KHÔNG dịch.
- KHÔNG chuyển sang chữ in hoa.
- KHÔNG bỏ dấu tiếng Việt.
- KHÔNG viết lại câu.
- KHÔNG tóm tắt.
- Chỉ sửa các lỗi OCR rõ ràng.

Ví dụ các trường hợp sửa lỗi OCR:
'Hỗ Chí Minh' -> 'Hồ Chí Minh'
'Bide 1' -> 'Điều 1'
'Cla cứ' -> 'Căn cứ'

giữ nguyên văn bản sau khi đã sửa lỗi OCR, KHÔNG viết lại câu, KHÔNG tóm tắt, KHÔNG bỏ dấu tiếng Việt, không trả lời như đang chat với tôi, chỉ trả về chính xác văn bản đã được sửa lỗi OCR.

Nếu không chắc thì giữ nguyên.

Văn bản OCR:

{text}
"""

refined_text = text
try:
    with httpx.Client(timeout=120) as client:
        response = client.post(
            LLM_URL,
            json={
                "model": LLM_MODEL,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": 0,
                },
            },
        )
        response.raise_for_status()
        refined_text = response.json().get("response", "").strip() or text
except Exception as exc:
    print(f"LLM_UNAVAILABLE: {exc}")
    refined_text = text

print(refined_text)
OUTPUT_PATH.write_text(refined_text, encoding="utf-8")
