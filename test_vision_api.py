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
                        "This is a screenshot of EDX (Energy Dispersive X-ray) quantitative analysis from INCA software. "
                        "Please recognize the table data in the screenshot, including:\n"
                        "1. All element names (e.g. Fe, Te, Ta, etc., i.e. the column headers)\n"
                        "2. Result type (atomic percent or weight percent, check the 'Result Type' dropdown at the bottom)\n"
                        "3. The values for each spectrum (Spectrum 1, Spectrum 2...) for each element\n"
                        "4. The average row in the statistics section\n\n"
                        "Return ONLY a JSON object in the following format, without any other text or markdown markup:\n"
                        '{\n'
                        '  "elements": ["Fe", "Te", "Ta"],\n'
                        '  "result_type": "atomic_percent",\n'
                        '  "spectra": [\n'
                        '    {"label": "Spectrum 1", "values": [2.05, 64.26, 33.70]},\n'
                        '    {"label": "Spectrum 2", "values": [2.29, 63.86, 33.85]}\n'
                        '  ],\n'
                        '  "average": {"label": "Average", "values": [1.68, 64.21, 34.11]}\n'
                        '}\n\n'
                        "Notes:\n"
                        "- The elements array contains all element symbols, corresponding to the table columns\n"
                        "- result_type is either \"atomic_percent\" (atomic percent) or \"weight_percent\" (weight percent)\n"
                        "- Each item in the spectra array has values in the same order as elements\n"
                        "- average is the average row from the statistics section\n"
                        "- Preserve the decimal places as shown in the screenshot\n"
                        "- All labels must be in English (e.g. 'Spectrum 1', 'Average'), even if the screenshot is in another language"
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
            print(f"  {avg.get('label', 'Average')}: {avg.get('values', [])}")
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

