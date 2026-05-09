# -*- coding: utf-8 -*-
"""Test local Vision API with a real EDX image"""
import base64, time, json, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from openai import OpenAI

IMAGE_PATH = r"C:\Users\fuyang\Desktop\postdoc\python\crystal_manager\uploads\H002-M287\edx\019e22a2c4b740cb866dff8077ec6af9.jpg"
API_KEY = "pwd"
BASE_URL = "http://127.0.0.1:7861/v1/"
MODEL = "gemini-3.1-pro-preview"

print("=" * 50)
print(f"Model: {MODEL}")
print(f"Base URL: {BASE_URL}")
print(f"Image: {IMAGE_PATH}")
print("=" * 50)

# Read image
with open(IMAGE_PATH, 'rb') as f:
    raw = f.read()
image_data = base64.b64encode(raw).decode('utf-8')
print(f"\nImage size: {len(raw)} bytes")

# Call API
print(f"\nCalling Vision API...")
client = OpenAI(api_key=API_KEY, base_url=BASE_URL)
t0 = time.time()

try:
    response = client.chat.completions.create(
        model=MODEL,
        messages=[{
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": (
                        "请识别这张 EDX (Energy Dispersive X-ray) 能谱照片中的元素成分数据。"
                        "请仅返回一个 JSON 数组，格式如下，不要包含任何其他文字或 markdown 标记：\n"
                        '[{"element": "Fe", "weight_percent": 25.3, "atomic_percent": 12.1}, ...]'
                    )
                },
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/jpeg;base64,{image_data}"}
                }
            ]
        }],
        max_tokens=1000
    )
    elapsed = time.time() - t0
    print(f"[OK] Response in {elapsed:.1f}s")

    result_text = response.choices[0].message.content.strip()
    print(f"\nRaw AI response:\n{result_text}")

    # Parse JSON
    clean = result_text
    if clean.startswith('```'):
        lines = clean.split('\n')
        clean = '\n'.join(lines[1:-1] if lines[-1].strip() == '```' else lines[1:]).strip()

    data = json.loads(clean)
    print(f"\n[OK] Parsed {len(data)} elements:")
    for item in data:
        el = item.get('element', '?')
        wt = item.get('weight_percent', '?')
        at = item.get('atomic_percent', '?')
        print(f"  {el:>3s}: wt%={wt}, at%={at}")

except json.JSONDecodeError:
    print(f"\n[WARN] JSON parse failed, but API call succeeded")
except Exception as e:
    elapsed = time.time() - t0
    print(f"[FAIL] Error after {elapsed:.1f}s: {e}")
