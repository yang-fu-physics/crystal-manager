# -*- coding: utf-8 -*-
"""晶体样品管理系统 - 数据库模型"""

import sqlite3
import json
import os
import shutil
from datetime import datetime
import config


def get_db():
    """获取数据库连接"""
    conn = sqlite3.connect(config.DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    """初始化数据库表"""
    conn = get_db()
    cursor = conn.cursor()

    cursor.executescript("""
        CREATE TABLE IF NOT EXISTS samples (
            id TEXT PRIMARY KEY,
            target_product TEXT DEFAULT '',
            is_successful INTEGER DEFAULT 2,
            growth_process TEXT DEFAULT '',
            element_ratios TEXT DEFAULT '[]',
            actual_masses TEXT DEFAULT '[]',
            notes TEXT DEFAULT '',
            results TEXT DEFAULT '',
            created_at TEXT,
            updated_at TEXT
        );

        CREATE TABLE IF NOT EXISTS photos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sample_id TEXT NOT NULL,
            filename TEXT NOT NULL,
            filepath TEXT NOT NULL,
            uploaded_at TEXT,
            FOREIGN KEY (sample_id) REFERENCES samples(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS edx_images (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sample_id TEXT NOT NULL,
            filename TEXT NOT NULL,
            filepath TEXT NOT NULL,
            recognized_data TEXT DEFAULT '[]',
            uploaded_at TEXT,
            FOREIGN KEY (sample_id) REFERENCES samples(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS data_files (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sample_id TEXT NOT NULL,
            filename TEXT NOT NULL,
            filepath TEXT NOT NULL,
            uploaded_at TEXT,
            FOREIGN KEY (sample_id) REFERENCES samples(id) ON DELETE CASCADE
        );

    """)

    # Dynamic migration for other_files (backwards compatibility)
    try:
        cursor.execute("SELECT 1 FROM other_files LIMIT 1")
    except sqlite3.OperationalError:
        cursor.execute("""
            CREATE TABLE other_files (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sample_id TEXT NOT NULL,
                filename TEXT NOT NULL,
                filepath TEXT NOT NULL,
                uploaded_at TEXT,
                FOREIGN KEY (sample_id) REFERENCES samples(id) ON DELETE CASCADE
            )
        """)

    conn.commit()
    conn.close()


def get_sample_subfolder(sample_id: str, subtype: str) -> str:
    """Return (and create) uploads/{sample_id}/{subtype}/ directory."""
    safe_id = "".join(c if (c.isalnum() or c in '-_.') else '_' for c in sample_id)
    folder = os.path.join(config.UPLOAD_FOLDER, safe_id, subtype)
    os.makedirs(folder, exist_ok=True)
    return folder


# ============================================================
# Sample CRUD
# ============================================================

def sample_to_dict(row):
    """将数据库行转为字典"""
    if row is None:
        return None
    d = dict(row)
    # 解析 JSON 字段
    for key in ['element_ratios', 'actual_masses']:
        if d.get(key):
            try:
                d[key] = json.loads(d[key])
            except (json.JSONDecodeError, TypeError):
                d[key] = []
        else:
            d[key] = []
    return d


def get_all_samples(query=None):
    """获取所有样品，支持搜索"""
    conn = get_db()
    if query:
        q = f"%{query}%"
        rows = conn.execute(
            """SELECT * FROM samples
               WHERE id LIKE ? OR target_product LIKE ? OR notes LIKE ? OR results LIKE ? OR growth_process LIKE ?
               ORDER BY created_at DESC""",
            (q, q, q, q, q)
        ).fetchall()
    else:
        rows = conn.execute("SELECT * FROM samples ORDER BY created_at DESC").fetchall()
    conn.close()
    return [sample_to_dict(r) for r in rows]


def get_sample(sample_id):
    """获取单个样品详情（含附件列表）"""
    conn = get_db()
    row = conn.execute("SELECT * FROM samples WHERE id = ?", (sample_id,)).fetchone()
    if row is None:
        conn.close()
        return None

    sample = sample_to_dict(row)

    # 附件列表
    sample['photos'] = [dict(r) for r in
                        conn.execute("SELECT * FROM photos WHERE sample_id = ? ORDER BY id", (sample_id,)).fetchall()]
    sample['edx_images'] = [dict(r) for r in
                            conn.execute("SELECT * FROM edx_images WHERE sample_id = ? ORDER BY id",
                                         (sample_id,)).fetchall()]
    for edx in sample['edx_images']:
        if edx.get('recognized_data'):
            try:
                edx['recognized_data'] = json.loads(edx['recognized_data'])
            except (json.JSONDecodeError, TypeError):
                edx['recognized_data'] = []
        else:
            edx['recognized_data'] = []

    sample['data_files'] = [dict(r) for r in
                            conn.execute("SELECT * FROM data_files WHERE sample_id = ? ORDER BY id",
                                         (sample_id,)).fetchall()]
    sample['other_files'] = [dict(r) for r in
                             conn.execute("SELECT * FROM other_files WHERE sample_id = ? ORDER BY id",
                                          (sample_id,)).fetchall()]
    conn.close()
    return sample


def create_sample(data):
    """新建样品"""
    now = datetime.now().isoformat()
    conn = get_db()
    conn.execute(
        """INSERT INTO samples (id, target_product, is_successful, growth_process,
           element_ratios, actual_masses, notes, results, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            data['id'],
            data.get('target_product', ''),
            data.get('status', 2),
            data.get('growth_process', ''),
            json.dumps(data.get('element_ratios', []), ensure_ascii=False),
            json.dumps(data.get('actual_masses', []), ensure_ascii=False),
            data.get('notes', ''),
            data.get('results', ''),
            now, now
        )
    )
    conn.commit()
    conn.close()
    return get_sample(data['id'])


def update_sample(sample_id, data):
    """更新样品"""
    now = datetime.now().isoformat()
    conn = get_db()

    # 如果 id 被修改了，需要更新关联表
    new_id = data.get('id', sample_id)

    conn.execute(
        """UPDATE samples SET id=?, target_product=?, is_successful=?, growth_process=?,
           element_ratios=?, actual_masses=?, notes=?, results=?, updated_at=?
           WHERE id=?""",
        (
            new_id,
            data.get('target_product', ''),
            data.get('status', 2),
            data.get('growth_process', ''),
            json.dumps(data.get('element_ratios', []), ensure_ascii=False),
            json.dumps(data.get('actual_masses', []), ensure_ascii=False),
            data.get('notes', ''),
            data.get('results', ''),
            now,
            sample_id
        )
    )
    conn.commit()
    conn.close()
    return get_sample(new_id)


def delete_sample(sample_id):
    """删除样品及其所有附件"""
    conn = get_db()

    # 获取附件路径以便删除文件
    photos = conn.execute("SELECT filepath FROM photos WHERE sample_id = ?", (sample_id,)).fetchall()
    edx_imgs = conn.execute("SELECT filepath FROM edx_images WHERE sample_id = ?", (sample_id,)).fetchall()
    data_files = conn.execute("SELECT filepath FROM data_files WHERE sample_id = ?", (sample_id,)).fetchall()
    other_files = conn.execute("SELECT filepath FROM other_files WHERE sample_id = ?", (sample_id,)).fetchall()

    # 删除数据库记录
    conn.execute("DELETE FROM samples WHERE id = ?", (sample_id,))
    conn.commit()
    conn.close()

    # 删除文件 —— 先尝试删除整个样品文件夹
    safe_id = "".join(c if (c.isalnum() or c in '-_.') else '_' for c in sample_id)
    sample_folder = os.path.join(config.UPLOAD_FOLDER, safe_id)
    if os.path.isdir(sample_folder):
        shutil.rmtree(sample_folder, ignore_errors=True)
    else:
        # Fallback: delete individual files (legacy flat structure)
        for row in list(photos) + list(edx_imgs) + list(data_files) + list(other_files):
            filepath = row['filepath']
            if os.path.exists(filepath):
                os.remove(filepath)

    return True


# ============================================================
# 附件操作
# ============================================================

def add_photo(sample_id, filename, filepath):
    now = datetime.now().isoformat()
    conn = get_db()
    cursor = conn.execute(
        "INSERT INTO photos (sample_id, filename, filepath, uploaded_at) VALUES (?, ?, ?, ?)",
        (sample_id, filename, filepath, now)
    )
    photo_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return photo_id


def delete_photo(photo_id):
    conn = get_db()
    row = conn.execute("SELECT filepath FROM photos WHERE id = ?", (photo_id,)).fetchone()
    if row and os.path.exists(row['filepath']):
        os.remove(row['filepath'])
    conn.execute("DELETE FROM photos WHERE id = ?", (photo_id,))
    conn.commit()
    conn.close()


def add_edx_image(sample_id, filename, filepath):
    now = datetime.now().isoformat()
    conn = get_db()
    cursor = conn.execute(
        "INSERT INTO edx_images (sample_id, filename, filepath, uploaded_at) VALUES (?, ?, ?, ?)",
        (sample_id, filename, filepath, now)
    )
    edx_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return edx_id


def update_edx_recognized_data(edx_id, data):
    conn = get_db()
    conn.execute(
        "UPDATE edx_images SET recognized_data = ? WHERE id = ?",
        (json.dumps(data, ensure_ascii=False), edx_id)
    )
    conn.commit()
    conn.close()


def delete_edx_image(edx_id):
    conn = get_db()
    row = conn.execute("SELECT filepath FROM edx_images WHERE id = ?", (edx_id,)).fetchone()
    if row and os.path.exists(row['filepath']):
        os.remove(row['filepath'])
    conn.execute("DELETE FROM edx_images WHERE id = ?", (edx_id,))
    conn.commit()
    conn.close()


def add_data_file(sample_id, filename, filepath):
    now = datetime.now().isoformat()
    conn = get_db()
    cursor = conn.execute(
        "INSERT INTO data_files (sample_id, filename, filepath, uploaded_at) VALUES (?, ?, ?, ?)",
        (sample_id, filename, filepath, now)
    )
    file_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return file_id


def delete_data_file(file_id):
    conn = get_db()
    row = conn.execute("SELECT filepath FROM data_files WHERE id = ?", (file_id,)).fetchone()
    if row and os.path.exists(row['filepath']):
        os.remove(row['filepath'])
    conn.execute("DELETE FROM data_files WHERE id = ?", (file_id,))
    conn.commit()
    conn.close()


def add_other_file(sample_id, filename, filepath):
    now = datetime.now().isoformat()
    conn = get_db()
    cursor = conn.execute(
        "INSERT INTO other_files (sample_id, filename, filepath, uploaded_at) VALUES (?, ?, ?, ?)",
        (sample_id, filename, filepath, now)
    )
    file_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return file_id


def delete_other_file(file_id):
    conn = get_db()
    row = conn.execute("SELECT filepath FROM other_files WHERE id = ?", (file_id,)).fetchone()
    if row and os.path.exists(row['filepath']):
        os.remove(row['filepath'])
    conn.execute("DELETE FROM other_files WHERE id = ?", (file_id,))
    conn.commit()
    conn.close()
