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
                        "这是一张 INCA 软件的 EDX (Energy Dispersive X-ray) 定量分析截图。"
                        "请识别截图中的表格数据，包括：\n"
                        "1. 所有元素名称（如 Fe, Te, Ta 等，即表头列名）\n"
                        "2. 结果类型（原子百分比 或 质量百分比，看截图底部的\"结果类型\"下拉框）\n"
                        "3. 每个谱图（谱图1、谱图2...）对应各元素的数值\n"
                        "4. 统计数据中的平均值行\n\n"
                        "请仅返回一个 JSON 对象，格式如下，不要包含任何其他文字或 markdown 标记：\n"
                        '{\n'
                        '  "elements": ["Fe", "Te", "Ta"],\n'
                        '  "result_type": "atomic_percent",\n'
                        '  "spectra": [\n'
                        '    {"label": "谱图1", "values": [2.05, 64.26, 33.70]},\n'
                        '    {"label": "谱图2", "values": [2.29, 63.86, 33.85]}\n'
                        '  ],\n'
                        '  "average": {"label": "平均值", "values": [1.68, 64.21, 34.11]}\n'
                        '}\n\n'
                        "说明：\n"
                        "- elements 数组包含所有元素符号，与表头列对应\n"
                        "- result_type 为 \"atomic_percent\"（原子百分比）或 \"weight_percent\"（质量百分比）\n"
                        "- spectra 数组中每项的 values 顺序与 elements 一一对应\n"
                        "- average 是统计数据中的平均值行\n"
                        "- 数值保留截图中显示的小数位数"
                    )
                },
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/jpeg;base64,{image_data}"}
                }
            ]
        }],
        max_tokens=2000
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

    if isinstance(data, dict) and 'elements' in data:
        print(f"\n[OK] INCA table format detected")
        print(f"  Elements: {data['elements']}")
        print(f"  Result type: {data.get('result_type', '?')}")
        for sp in data.get('spectra', []):
            print(f"  {sp['label']}: {sp['values']}")
        avg = data.get('average', {})
        if avg:
            print(f"  {avg.get('label', '平均值')}: {avg.get('values', [])}")
    else:
        print(f"\n[OK] Legacy format, {len(data)} elements:")
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

