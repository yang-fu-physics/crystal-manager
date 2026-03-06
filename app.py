# -*- coding: utf-8 -*-
"""晶体材料样品管理系统 - Flask 主应用"""

import os
import sys
import uuid
import base64
import json
from flask import Flask, request, jsonify, render_template, send_from_directory, session, redirect, url_for
from functools import wraps

# 当前目录加入 sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config
import models

# 从上级目录导入元素摩尔质量表
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from molmass_data import elenmentsmasstable

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024  # 100MB max upload
app.secret_key = config.SECRET_KEY


# ============================================================
# 登录验证
# ============================================================

@app.before_request
def check_login():
    """所有请求前检查登录状态，白名单除外"""
    allowed = ['login_page', 'do_login', 'static']
    if request.endpoint in allowed:
        return
    if not session.get('logged_in'):
        if request.path.startswith('/api/'):
            return jsonify({'error': '未登录'}), 401
        return redirect(url_for('login_page'))


@app.route('/login')
def login_page():
    return render_template('login.html')


@app.route('/api/login', methods=['POST'])
def do_login():
    data = request.get_json()
    password = data.get('password', '') if data else ''
    if password == config.LOGIN_PASSWORD:
        session['logged_in'] = True
        return jsonify({'success': True})
    return jsonify({'error': '密码错误'}), 403


@app.route('/api/logout', methods=['POST'])
def do_logout():
    session.clear()
    return jsonify({'success': True})


# ============================================================
# 页面路由
# ============================================================

@app.route('/')
def index():
    return render_template('index.html')


# ============================================================
# 样品 API
# ============================================================

@app.route('/api/samples', methods=['GET'])
def list_samples():
    query = request.args.get('q', '').strip()
    samples = models.get_all_samples(query if query else None)
    return jsonify(samples)


@app.route('/api/samples', methods=['POST'])
def create_sample():
    data = request.get_json()
    if not data or not data.get('id'):
        return jsonify({'error': '样品编号不能为空'}), 400

    # 检查是否已存在
    existing = models.get_sample(data['id'])
    if existing:
        return jsonify({'error': f'样品编号 {data["id"]} 已存在'}), 409

    sample = models.create_sample(data)
    return jsonify(sample), 201


@app.route('/api/samples/<sample_id>', methods=['GET'])
def get_sample(sample_id):
    sample = models.get_sample(sample_id)
    if not sample:
        return jsonify({'error': '样品不存在'}), 404
    return jsonify(sample)


@app.route('/api/samples/<sample_id>', methods=['PUT'])
def update_sample(sample_id):
    data = request.get_json()
    if not data:
        return jsonify({'error': '无效数据'}), 400

    existing = models.get_sample(sample_id)
    if not existing:
        return jsonify({'error': '样品不存在'}), 404

    # 如果修改了 ID，检查新 ID 是否已存在
    new_id = data.get('id', sample_id)
    if new_id != sample_id:
        check = models.get_sample(new_id)
        if check:
            return jsonify({'error': f'样品编号 {new_id} 已存在'}), 409

    sample = models.update_sample(sample_id, data)
    return jsonify(sample)


@app.route('/api/samples/<sample_id>', methods=['DELETE'])
def delete_sample(sample_id):
    existing = models.get_sample(sample_id)
    if not existing:
        return jsonify({'error': '样品不存在'}), 404

    models.delete_sample(sample_id)
    return jsonify({'success': True})


# ============================================================
# 照片 API
# ============================================================

@app.route('/api/samples/<sample_id>/photos', methods=['POST'])
def upload_photo(sample_id):
    existing = models.get_sample(sample_id)
    if not existing:
        return jsonify({'error': '样品不存在'}), 404

    if 'file' not in request.files:
        return jsonify({'error': '未选择文件'}), 400

    files = request.files.getlist('file')
    uploaded = []
    for file in files:
        if file.filename:
            ext = os.path.splitext(file.filename)[1]
            safe_name = f"{uuid.uuid4().hex}{ext}"
            filepath = os.path.join(config.PHOTO_FOLDER, safe_name)
            file.save(filepath)
            photo_id = models.add_photo(sample_id, file.filename, filepath)
            uploaded.append({'id': photo_id, 'filename': file.filename, 'filepath': filepath})

    return jsonify(uploaded), 201


@app.route('/api/photos/<int:photo_id>', methods=['DELETE'])
def delete_photo(photo_id):
    models.delete_photo(photo_id)
    return jsonify({'success': True})


# ============================================================
# EDX API
# ============================================================

@app.route('/api/samples/<sample_id>/edx', methods=['POST'])
def upload_edx(sample_id):
    existing = models.get_sample(sample_id)
    if not existing:
        return jsonify({'error': '样品不存在'}), 404

    if 'file' not in request.files:
        return jsonify({'error': '未选择文件'}), 400

    files = request.files.getlist('file')
    uploaded = []
    for file in files:
        if file.filename:
            ext = os.path.splitext(file.filename)[1]
            safe_name = f"{uuid.uuid4().hex}{ext}"
            filepath = os.path.join(config.EDX_FOLDER, safe_name)
            file.save(filepath)
            edx_id = models.add_edx_image(sample_id, file.filename, filepath)
            uploaded.append({'id': edx_id, 'filename': file.filename, 'filepath': filepath})

    return jsonify(uploaded), 201


@app.route('/api/edx/<int:edx_id>/recognize', methods=['POST'])
def recognize_edx(edx_id):
    """调用 GPT Vision API 识别 EDX 谱图"""
    from openai import OpenAI
    conn = models.get_db()
    row = conn.execute("SELECT * FROM edx_images WHERE id = ?", (edx_id,)).fetchone()
    conn.close()

    if not row:
        return jsonify({'error': 'EDX 图片不存在'}), 404

    filepath = row['filepath']
    if not os.path.exists(filepath):
        return jsonify({'error': '文件不存在'}), 404

    # 读取图片并 base64 编码
    with open(filepath, 'rb') as f:
        image_data = base64.b64encode(f.read()).decode('utf-8')

    ext = os.path.splitext(filepath)[1].lower()
    mime_map = {'.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg',
                '.bmp': 'image/bmp', '.tif': 'image/tiff', '.tiff': 'image/tiff'}
    mime = mime_map.get(ext, 'image/png')

    try:
        client = OpenAI(api_key=config.OPENAI_API_KEY, base_url=config.OPENAI_BASE_URL)
        response = client.chat.completions.create(
            model=config.OPENAI_MODEL,
            messages=[
                {
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
                            "image_url": {
                                "url": f"data:{mime};base64,{image_data}"
                            }
                        }
                    ]
                }
            ],
            max_tokens=1000
        )

        result_text = response.choices[0].message.content.strip()
        # 尝试解析 JSON
        # 去除可能的 markdown 包裹
        if result_text.startswith('```'):
            lines = result_text.split('\n')
            result_text = '\n'.join(lines[1:-1] if lines[-1].strip() == '```' else lines[1:])
            result_text = result_text.strip()

        recognized_data = json.loads(result_text)
        models.update_edx_recognized_data(edx_id, recognized_data)
        return jsonify({'recognized_data': recognized_data})

    except json.JSONDecodeError:
        # GPT 返回的不是有效 JSON，原样返回让前端处理
        return jsonify({'error': '识别结果格式异常', 'raw': result_text}), 422
    except Exception as e:
        return jsonify({'error': f'GPT API 调用失败: {str(e)}'}), 500


@app.route('/api/edx/<int:edx_id>', methods=['DELETE'])
def delete_edx(edx_id):
    models.delete_edx_image(edx_id)
    return jsonify({'success': True})


# ============================================================
# 数据文件 API
# ============================================================

@app.route('/api/samples/<sample_id>/datafiles', methods=['POST'])
def upload_data_file(sample_id):
    existing = models.get_sample(sample_id)
    if not existing:
        return jsonify({'error': '样品不存在'}), 404

    if 'file' not in request.files:
        return jsonify({'error': '未选择文件'}), 400

    files = request.files.getlist('file')
    uploaded = []
    for file in files:
        if file.filename:
            ext = os.path.splitext(file.filename)[1]
            safe_name = f"{uuid.uuid4().hex}{ext}"
            filepath = os.path.join(config.DATA_FOLDER, safe_name)
            file.save(filepath)
            file_id = models.add_data_file(sample_id, file.filename, filepath)
            uploaded.append({'id': file_id, 'filename': file.filename, 'filepath': filepath})

    return jsonify(uploaded), 201


@app.route('/api/datafiles/<int:file_id>', methods=['DELETE'])
def delete_data_file(file_id):
    models.delete_data_file(file_id)
    return jsonify({'success': True})


# ============================================================
# 元素质量计算 API
# ============================================================

@app.route('/api/calculate_mass', methods=['POST'])
def calculate_mass():
    """
    根据元素比例和某一元素的质量，计算其他元素的实际称量质量
    请求体:
    {
        "elements": [{"element": "Fe", "ratio": 1}, {"element": "La", "ratio": 2}, ...],
        "reference_element": "Fe",
        "reference_mass": 0.5
    }
    """
    data = request.get_json()
    if not data:
        return jsonify({'error': '无效数据'}), 400

    elements = data.get('elements', [])
    ref_element = data.get('reference_element', '')
    ref_mass = data.get('reference_mass', 0)

    if not elements or not ref_element or not ref_mass:
        return jsonify({'error': '请填写完整的元素比例和参考元素质量'}), 400

    # 验证参考元素在列表中
    ref_item = None
    for item in elements:
        if item['element'] == ref_element:
            ref_item = item
            break

    if ref_item is None:
        return jsonify({'error': f'参考元素 {ref_element} 不在元素列表中'}), 400

    # 获取摩尔质量
    ref_molar_mass = elenmentsmasstable.get(ref_element)
    if ref_molar_mass is None:
        return jsonify({'error': f'未知元素: {ref_element}'}), 400

    ref_ratio = ref_item['ratio']
    results = []

    for item in elements:
        el = item['element']
        ratio = item['ratio']
        molar_mass = elenmentsmasstable.get(el)

        if molar_mass is None:
            return jsonify({'error': f'未知元素: {el}'}), 400

        if el == ref_element:
            mass = ref_mass
        else:
            # m_B = m_A × (r_B / r_A) × (M_B / M_A)
            mass = ref_mass * (ratio / ref_ratio) * (molar_mass / ref_molar_mass)

        results.append({
            'element': el,
            'ratio': ratio,
            'molar_mass': round(molar_mass, 4),
            'mass': round(mass, 6)
        })

    return jsonify({'results': results})


@app.route('/api/elements', methods=['GET'])
def get_elements():
    """返回所有可用元素列表（带摩尔质量）"""
    return jsonify(elenmentsmasstable)


# ============================================================
# 静态文件服务 (上传的文件)
# ============================================================

@app.route('/uploads/<path:filename>')
def serve_upload(filename):
    return send_from_directory(config.UPLOAD_FOLDER, filename)


# ============================================================
# 启动
# ============================================================

if __name__ == '__main__':
    models.init_db()
    port = getattr(config, 'APP_PORT', 5000)
    print("=" * 50)
    print("晶体材料样品管理系统")
    print(f"访问地址: http://127.0.0.1:{port}")
    print("=" * 50)
    app.run(debug=True, host='0.0.0.0', port=port)
