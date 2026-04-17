# -*- coding: utf-8 -*-
"""晶体材料样品管理系统 - Flask 主应用"""

import os
import sys
import uuid
import base64
import json
import time
from flask import Flask, request, jsonify, render_template, send_from_directory, session, redirect, url_for
from functools import wraps
from PIL import Image

# 当前目录加入 sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config
import models
import todo_integration
import backup as _backup_module

# 从上级目录导入元素摩尔质量表
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from molmass_data import elenmentsmasstable

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024  # 100MB max upload
app.secret_key = config.SECRET_KEY

# 配置日志输出
import logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(name)s] %(levelname)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
)

# ============================================================
# 登录验证
# ============================================================

@app.before_request
def check_login():
    """所有请求前检查登录状态，白名单除外"""
    allowed = ['login_page', 'do_login', 'static', 'auth_microsoft', 'auth_callback']
    if request.endpoint in allowed:
        return
    if not session.get('logged_in'):
        if request.path.startswith('/api/'):
            return jsonify({'error': '未登录'}), 401
        return redirect(url_for('login_page'))


@app.route('/login')
def login_page():
    return render_template('login.html')


# 登录失败记录: {ip: {'count': int, 'locked_until': float}}
_login_attempts = {}
LOGIN_MAX_FAILURES = 3
LOGIN_LOCK_SECONDS = 86400  # 24小时


@app.route('/api/login', methods=['POST'])
def do_login():
    ip = request.remote_addr or 'unknown'
    now = time.time()

    # 检查是否被锁定
    record = _login_attempts.get(ip, {})
    locked_until = record.get('locked_until', 0)
    if now < locked_until:
        remaining = int((locked_until - now) / 3600) + 1
        return jsonify({'error': f'登录已锁定，请 {remaining} 小时后重试'}), 429

    data = request.get_json()
    password = data.get('password', '') if data else ''

    if password == config.LOGIN_PASSWORD:
        _login_attempts.pop(ip, None)  # 登录成功清除记录
        session['logged_in'] = True
        return jsonify({'success': True})

    # 登录失败
    count = record.get('count', 0) + 1
    if count >= LOGIN_MAX_FAILURES:
        _login_attempts[ip] = {'count': count, 'locked_until': now + LOGIN_LOCK_SECONDS}
        return jsonify({'error': f'密码错误 {LOGIN_MAX_FAILURES} 次，IP 已被锁定 24 小时'}), 429

    _login_attempts[ip] = {'count': count, 'locked_until': 0}
    return jsonify({'error': f'密码错误，还剩 {LOGIN_MAX_FAILURES - count} 次机会'}), 403


@app.route('/api/logout', methods=['POST'])
def do_logout():
    session.clear()
    return jsonify({'success': True})


# ============================================================
# Microsoft To Do OAuth2 路由
# ============================================================

@app.route('/auth/microsoft')
def auth_microsoft():
    """开始 Microsoft OAuth2 授权流程"""
    if not todo_integration.is_configured():
        return jsonify({'error': '请先在 config.py 中配置 MS_CLIENT_ID 和 MS_CLIENT_SECRET'}), 400
    auth_url = todo_integration.get_auth_url()
    return redirect(auth_url)


@app.route('/auth/callback')
def auth_callback():
    """Microsoft OAuth2 回调"""
    code = request.args.get('code')
    error = request.args.get('error')

    if error:
        return f'<h3>授权失败</h3><p>{error}: {request.args.get("error_description", "")}</p><a href="/">返回</a>', 400

    if not code:
        return '<h3>授权失败</h3><p>未收到授权码</p><a href="/">返回</a>', 400

    success, err_msg = todo_integration.acquire_token_by_code(code)
    if success:
        return redirect('/')
    else:
        return f'<h3>授权失败</h3><p>{err_msg}</p><a href="/">返回</a>', 400


@app.route('/api/ms-status', methods=['GET'])
def ms_status():
    """返回 Microsoft To Do 连接状态"""
    return jsonify({
        'configured': todo_integration.is_configured(),
        'connected': todo_integration.is_connected(),
    })


@app.route('/api/ms-disconnect', methods=['POST'])
def ms_disconnect():
    """断开 Microsoft To Do 连接"""
    todo_integration.disconnect()
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

    # 新建样品时如果有结束时间，也同步到 To Do
    todo_synced = False
    todo_msg = ''
    sintering_end = data.get('sintering_end', '')
    if sintering_end:
        try:
            ok, msg = todo_integration.create_or_update_todo(data['id'], sintering_end, models, data.get('target_product', ''))
            todo_synced = ok
            todo_msg = msg
        except Exception as e:
            app.logger.error(f'同步 To Do 失败: {e}')
            todo_msg = str(e)

    result = dict(sample) if isinstance(sample, dict) else sample
    result['todo_synced'] = todo_synced
    result['todo_msg'] = todo_msg
    return jsonify(result), 201


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

    # 记录旧的 sintering_end 用于后续比较
    old_sintering_end = existing.get('sintering_end', '')

    sample = models.update_sample(sample_id, data)

    # 同步 Microsoft To Do（仅当结束时间有变化时）
    todo_synced = False
    todo_msg = ''
    new_sintering_end = data.get('sintering_end', '')
    if new_sintering_end and new_sintering_end != old_sintering_end:
        try:
            ok, msg = todo_integration.create_or_update_todo(new_id, new_sintering_end, models, data.get('target_product', ''))
            todo_synced = ok
            todo_msg = msg
        except Exception as e:
            app.logger.error(f'同步 To Do 失败: {e}')
            todo_msg = str(e)

    result = dict(sample) if isinstance(sample, dict) else sample
    result['todo_synced'] = todo_synced
    result['todo_msg'] = todo_msg
    return jsonify(result)


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

    folder = models.get_sample_subfolder(sample_id, 'photos')
    files = request.files.getlist('file')
    uploaded = []
    for file in files:
        if file.filename:
            ext = os.path.splitext(file.filename)[1]
            safe_name = f"{uuid.uuid4().hex}{ext}"
            filepath = os.path.join(folder, safe_name)
            file.save(filepath)
            photo_id = models.add_photo(sample_id, file.filename, filepath)
            _create_thumbnail(filepath)
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

    folder = models.get_sample_subfolder(sample_id, 'edx')
    files = request.files.getlist('file')
    uploaded = []
    for file in files:
        if file.filename:
            ext = os.path.splitext(file.filename)[1]
            safe_name = f"{uuid.uuid4().hex}{ext}"
            filepath = os.path.join(folder, safe_name)
            file.save(filepath)
            edx_id = models.add_edx_image(sample_id, file.filename, filepath)
            _create_thumbnail(filepath)
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

    folder = models.get_sample_subfolder(sample_id, 'data')
    files = request.files.getlist('file')
    uploaded = []
    for file in files:
        if file.filename:
            ext = os.path.splitext(file.filename)[1]
            safe_name = f"{uuid.uuid4().hex}{ext}"
            filepath = os.path.join(folder, safe_name)
            file.save(filepath)
            file_id = models.add_data_file(sample_id, file.filename, filepath)
            uploaded.append({'id': file_id, 'filename': file.filename, 'filepath': filepath})

    return jsonify(uploaded), 201


@app.route('/api/datafiles/<int:file_id>', methods=['DELETE'])
def delete_data_file(file_id):
    models.delete_data_file(file_id)
    return jsonify({'success': True})


# ============================================================
# 其他文件 API
# ============================================================

@app.route('/api/samples/<sample_id>/otherfiles', methods=['POST'])
def upload_other_file(sample_id):
    existing = models.get_sample(sample_id)
    if not existing:
        return jsonify({'error': '样品不存在'}), 404

    if 'file' not in request.files:
        return jsonify({'error': '未选择文件'}), 400

    folder = models.get_sample_subfolder(sample_id, 'others')
    files = request.files.getlist('file')
    uploaded = []
    for file in files:
        if file.filename:
            ext = os.path.splitext(file.filename)[1]
            safe_name = f"{uuid.uuid4().hex}{ext}"
            filepath = os.path.join(folder, safe_name)
            file.save(filepath)
            file_id = models.add_other_file(sample_id, file.filename, filepath)
            uploaded.append({'id': file_id, 'filename': file.filename, 'filepath': filepath})

    return jsonify(uploaded), 201


@app.route('/api/otherfiles/<int:file_id>', methods=['DELETE'])
def delete_other_file(file_id):
    models.delete_other_file(file_id)
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
            'mass': round(mass, 4)
        })

    return jsonify({'results': results})


@app.route('/api/elements', methods=['GET'])
def get_elements():
    """返回所有可用元素列表（带摩尔质量）"""
    return jsonify(elenmentsmasstable)


# ============================================================
# 静态文件服务 (上传的文件)
# ============================================================

def _create_thumbnail(filepath, max_size=(300, 300)):
    """生成缩略图，保存在同目录，前缀为 thumb_"""
    try:
        # Check if it's a valid image extension
        ext = os.path.splitext(filepath)[1].lower()
        if ext not in ['.jpg', '.jpeg', '.png', '.bmp', '.tif', '.tiff']:
            return

        img = Image.open(filepath)
        # Convert to RGB mode if necessary (e.g. RGBA for PNGs before saving as JPEG, or just to be safe)
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")
            
        img.thumbnail(max_size)
        
        dir_name = os.path.dirname(filepath)
        base_name = os.path.basename(filepath)
        thumb_path = os.path.join(dir_name, f"thumb_{base_name}")
        
        img.save(thumb_path)
    except Exception as e:
        app.logger.error(f"Failed to create thumbnail for {filepath}: {e}")

@app.route('/uploads/<path:filename>')
def serve_upload(filename):
    use_thumb = request.args.get('thumb') == '1'
    if use_thumb:
        parts = filename.split('/')
        if len(parts) > 0:
            thumb_filename = '/'.join(parts[:-1] + [f"thumb_{parts[-1]}"]) if len(parts) > 1 else f"thumb_{parts[0]}"
            
            # Check if thumb exists (need native path for OS check)
            full_thumb_path = os.path.join(config.UPLOAD_FOLDER, thumb_filename.replace('/', os.sep))
            if os.path.exists(full_thumb_path):
                # Send using POSIX path for Flask security
                return send_from_directory(config.UPLOAD_FOLDER, thumb_filename)
                
    return send_from_directory(config.UPLOAD_FOLDER, filename)


# ============================================================
# 启动
# ============================================================

if __name__ == '__main__':
    models.init_db()
    # 启动定时备份调度器
    _backup_module.start_scheduler()

    port = getattr(config, 'APP_PORT', 5000)

    # Windows 默认 IPV6_V6ONLY=1，需要 patch 才能让 '::' 同时监听 IPv4
    import socket as _socket
    _orig_bind = _socket.socket.bind

    def _dual_stack_bind(self, address):
        if self.family == _socket.AF_INET6:
            try:
                self.setsockopt(_socket.IPPROTO_IPV6, _socket.IPV6_V6ONLY, 0)
            except (AttributeError, OSError):
                pass
        return _orig_bind(self, address)

    _socket.socket.bind = _dual_stack_bind

    print("=" * 50)
    print("晶体材料样品管理系统")
    print(f"IPv4 访问: http://127.0.0.1:{port}")
    print(f"IPv6 访问: http://[::1]:{port}")
    print("=" * 50)
    app.run(debug=True, host='::', port=port)
