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
            has_electric INTEGER DEFAULT 0,
            has_magnetic INTEGER DEFAULT 0,
            has_xrd INTEGER DEFAULT 0,
            has_edx INTEGER DEFAULT 0,
            growth_process TEXT DEFAULT '',
            element_ratios TEXT DEFAULT '[]',
            actual_masses TEXT DEFAULT '[]',
            notes TEXT DEFAULT '',
            results TEXT DEFAULT '',
            sintering_start TEXT DEFAULT '',
            sintering_duration REAL DEFAULT NULL,
            sintering_end TEXT DEFAULT '',
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

        CREATE TABLE IF NOT EXISTS xrd_images (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sample_id TEXT NOT NULL,
            filename TEXT NOT NULL,
            filepath TEXT NOT NULL,
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

    # Dynamic migration for has_electric and has_magnetic
    try:
        cursor.execute("SELECT has_electric FROM samples LIMIT 1")
    except sqlite3.OperationalError:
        cursor.execute("ALTER TABLE samples ADD COLUMN has_electric INTEGER DEFAULT 0")
        cursor.execute("ALTER TABLE samples ADD COLUMN has_magnetic INTEGER DEFAULT 0")

    # Dynamic migration for has_xrd and has_edx
    try:
        cursor.execute("SELECT has_xrd FROM samples LIMIT 1")
    except sqlite3.OperationalError:
        cursor.execute("ALTER TABLE samples ADD COLUMN has_xrd INTEGER DEFAULT 0")
        cursor.execute("ALTER TABLE samples ADD COLUMN has_edx INTEGER DEFAULT 0")

    # Dynamic migration for sintering time fields
    try:
        cursor.execute("SELECT sintering_start FROM samples LIMIT 1")
    except sqlite3.OperationalError:
        cursor.execute("ALTER TABLE samples ADD COLUMN sintering_start TEXT DEFAULT ''")
        cursor.execute("ALTER TABLE samples ADD COLUMN sintering_duration REAL DEFAULT NULL")
        cursor.execute("ALTER TABLE samples ADD COLUMN sintering_end TEXT DEFAULT ''")

    # todo_tasks 表: 记录 sample_id ↔ Microsoft To Do task_id 映射
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS todo_tasks (
            sample_id TEXT PRIMARY KEY,
            task_id TEXT NOT NULL,
            sintering_end TEXT,
            updated_at TEXT
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
    # 有烧制时间用烧制时间，没有则用创建时间，统一降序排列
    ORDER_CLAUSE = "ORDER BY COALESCE(NULLIF(sintering_start, ''), created_at) DESC, created_at DESC"
    conn = get_db()
    try:
        if query:
            q = f"%{query}%"
            rows = conn.execute(
                f"""SELECT s.*, 
                    EXISTS(SELECT 1 FROM xrd_images x WHERE x.sample_id = s.id) as has_xrd_images,
                    EXISTS(SELECT 1 FROM edx_images e WHERE e.sample_id = s.id) as has_edx_images
                   FROM samples s
                   WHERE s.id LIKE ? OR s.target_product LIKE ? OR s.notes LIKE ? OR s.results LIKE ? OR s.growth_process LIKE ?
                   {ORDER_CLAUSE.replace('sintering_start', 's.sintering_start').replace('created_at', 's.created_at')}""",
                (q, q, q, q, q)
            ).fetchall()
        else:
            rows = conn.execute(f"""SELECT s.*,
                    EXISTS(SELECT 1 FROM xrd_images x WHERE x.sample_id = s.id) as has_xrd_images,
                    EXISTS(SELECT 1 FROM edx_images e WHERE e.sample_id = s.id) as has_edx_images
                   FROM samples s {ORDER_CLAUSE.replace('sintering_start', 's.sintering_start').replace('created_at', 's.created_at')}""").fetchall()
    finally:
        conn.close()
        
    samples = []
    for r in rows:
        d = sample_to_dict(r)
        d['has_xrd'] = 1 if (d.get('has_xrd') or d.get('has_xrd_images')) else 0
        d['has_edx'] = 1 if (d.get('has_edx') or d.get('has_edx_images')) else 0
        samples.append(d)
    return samples


def get_sample(sample_id):
    """获取单个样品详情（含附件列表）"""
    conn = get_db()
    try:
        row = conn.execute("SELECT * FROM samples WHERE id = ?", (sample_id,)).fetchone()
        if row is None:
            return None

        sample = sample_to_dict(row)

        # 附件列表
        sample['photos'] = [dict(r) for r in
                            conn.execute("SELECT * FROM photos WHERE sample_id = ? ORDER BY id", (sample_id,)).fetchall()]
        sample['edx_images'] = [dict(r) for r in
                                conn.execute("SELECT * FROM edx_images WHERE sample_id = ? ORDER BY id",
                                             (sample_id,)).fetchall()]
        sample['xrd_images'] = [dict(r) for r in
                                conn.execute("SELECT * FROM xrd_images WHERE sample_id = ? ORDER BY id",
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
    finally:
        conn.close()
    return sample


def create_sample(data):
    """新建样品"""
    now = datetime.now().isoformat()
    conn = get_db()
    try:
        conn.execute(
            """INSERT INTO samples (id, target_product, is_successful, has_electric, has_magnetic, has_xrd, has_edx, growth_process,
               element_ratios, actual_masses, notes, results,
               sintering_start, sintering_duration, sintering_end,
               created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                data['id'],
                data.get('target_product', ''),
                data.get('status', 2),
                data.get('has_electric', 0),
                data.get('has_magnetic', 0),
                data.get('has_xrd', 0),
                data.get('has_edx', 0),
                data.get('growth_process', ''),
                json.dumps(data.get('element_ratios', []), ensure_ascii=False),
                json.dumps(data.get('actual_masses', []), ensure_ascii=False),
                data.get('notes', ''),
                data.get('results', ''),
                data.get('sintering_start', ''),
                data.get('sintering_duration', None),
                data.get('sintering_end', ''),
                now, now
            )
        )
        conn.commit()
    finally:
        conn.close()
    return get_sample(data['id'])


def update_sample(sample_id, data):
    """更新样品"""
    now = datetime.now().isoformat()
    conn = get_db()

    # 如果 id 被修改了，需要更新关联表
    new_id = data.get('id', sample_id)

    try:
        if new_id != sample_id:
            conn.commit() # ensure no active transaction
            conn.execute("PRAGMA foreign_keys = OFF")
            conn.execute("BEGIN TRANSACTION")
            
            conn.execute(
                """UPDATE samples SET id=?, target_product=?, is_successful=?, has_electric=?, has_magnetic=?, has_xrd=?, has_edx=?, growth_process=?,
                   element_ratios=?, actual_masses=?, notes=?, results=?,
                   sintering_start=?, sintering_duration=?, sintering_end=?,
                   updated_at=?
                   WHERE id=?""",
                (new_id, data.get('target_product', ''), data.get('status', 2), data.get('has_electric', 0), data.get('has_magnetic', 0), data.get('has_xrd', 0), data.get('has_edx', 0), data.get('growth_process', ''), json.dumps(data.get('element_ratios', []), ensure_ascii=False), json.dumps(data.get('actual_masses', []), ensure_ascii=False), data.get('notes', ''), data.get('results', ''), data.get('sintering_start', ''), data.get('sintering_duration', None), data.get('sintering_end', ''), now, sample_id)
            )
            
            for table in ['photos', 'edx_images', 'xrd_images', 'data_files', 'other_files', 'todo_tasks']:
                try:
                    conn.execute(f"UPDATE {table} SET sample_id=? WHERE sample_id=?", (new_id, sample_id))
                except sqlite3.OperationalError:
                    pass # just in case a table doesn't exist or misses the column
            
            # rename upload folder and update filepaths
            old_safe_id = "".join(c if (c.isalnum() or c in '-_.') else '_' for c in sample_id)
            new_safe_id = "".join(c if (c.isalnum() or c in '-_.') else '_' for c in new_id)
            old_folder = os.path.join(config.UPLOAD_FOLDER, old_safe_id)
            new_folder = os.path.join(config.UPLOAD_FOLDER, new_safe_id)
            if os.path.exists(old_folder) and old_folder != new_folder:
                # avoid collision
                if not os.path.exists(new_folder):
                    os.rename(old_folder, new_folder)
            
            # Update filepaths in DB to point to the new folder
            old_folder_norm = os.path.normpath(old_folder)
            new_folder_norm = os.path.normpath(new_folder)
            for table in ['photos', 'edx_images', 'xrd_images', 'data_files', 'other_files']:
                try:
                    rows = conn.execute(f"SELECT id, filepath FROM {table} WHERE sample_id=?", (new_id,)).fetchall()
                    for r in rows:
                        old_fp = r['filepath']
                        if old_fp:
                            old_fp_norm = os.path.normpath(old_fp)
                            if old_fp_norm.startswith(old_folder_norm):
                                rel_path = old_fp_norm[len(old_folder_norm):].lstrip(os.sep)
                                new_fp = os.path.join(new_folder_norm, rel_path)
                                conn.execute(f"UPDATE {table} SET filepath=? WHERE id=?", (new_fp, r['id']))
                except sqlite3.OperationalError:
                    pass
            
            conn.commit()
            conn.execute("PRAGMA foreign_keys = ON")
        else:
            conn.execute(
                """UPDATE samples SET id=?, target_product=?, is_successful=?, has_electric=?, has_magnetic=?, has_xrd=?, has_edx=?, growth_process=?,
                   element_ratios=?, actual_masses=?, notes=?, results=?,
                   sintering_start=?, sintering_duration=?, sintering_end=?,
                   updated_at=?
                   WHERE id=?""",
                (new_id, data.get('target_product', ''), data.get('status', 2), data.get('has_electric', 0), data.get('has_magnetic', 0), data.get('has_xrd', 0), data.get('has_edx', 0), data.get('growth_process', ''), json.dumps(data.get('element_ratios', []), ensure_ascii=False), json.dumps(data.get('actual_masses', []), ensure_ascii=False), data.get('notes', ''), data.get('results', ''), data.get('sintering_start', ''), data.get('sintering_duration', None), data.get('sintering_end', ''), now, sample_id)
            )
            conn.commit()
    finally:
        conn.close()
    return get_sample(new_id)


def delete_sample(sample_id):
    """删除样品及其所有附件"""
    conn = get_db()

    try:
        # 获取附件路径以便删除文件
        photos = conn.execute("SELECT filepath FROM photos WHERE sample_id = ?", (sample_id,)).fetchall()
        edx_imgs = conn.execute("SELECT filepath FROM edx_images WHERE sample_id = ?", (sample_id,)).fetchall()
        xrd_imgs = conn.execute("SELECT filepath FROM xrd_images WHERE sample_id = ?", (sample_id,)).fetchall()
        data_files = conn.execute("SELECT filepath FROM data_files WHERE sample_id = ?", (sample_id,)).fetchall()
        other_files = conn.execute("SELECT filepath FROM other_files WHERE sample_id = ?", (sample_id,)).fetchall()

        # 删除数据库记录
        conn.execute("DELETE FROM samples WHERE id = ?", (sample_id,))
        conn.commit()
    finally:
        conn.close()

    # 删除文件 —— 先尝试删除整个样品文件夹
    safe_id = "".join(c if (c.isalnum() or c in '-_.') else '_' for c in sample_id)
    sample_folder = os.path.join(config.UPLOAD_FOLDER, safe_id)
    if os.path.isdir(sample_folder):
        shutil.rmtree(sample_folder, ignore_errors=True)
    else:
        # Fallback: delete individual files (legacy flat structure)
        for row in list(photos) + list(edx_imgs) + list(xrd_imgs) + list(data_files) + list(other_files):
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
    try:
        cursor = conn.execute(
            "INSERT INTO photos (sample_id, filename, filepath, uploaded_at) VALUES (?, ?, ?, ?)",
            (sample_id, filename, filepath, now)
        )
        photo_id = cursor.lastrowid
        conn.commit()
    finally:
        conn.close()
    return photo_id


def delete_photo(photo_id):
    conn = get_db()
    try:
        row = conn.execute("SELECT filepath FROM photos WHERE id = ?", (photo_id,)).fetchone()
        if row and os.path.exists(row['filepath']):
            os.remove(row['filepath'])
            # Also try to remove thumbnail
            dir_name = os.path.dirname(row['filepath'])
            base_name = os.path.basename(row['filepath'])
            thumb_path = os.path.join(dir_name, f"thumb_{base_name}")
            if os.path.exists(thumb_path):
                os.remove(thumb_path)
        conn.execute("DELETE FROM photos WHERE id = ?", (photo_id,))
        conn.commit()
    finally:
        conn.close()


def add_edx_image(sample_id, filename, filepath):
    now = datetime.now().isoformat()
    conn = get_db()
    try:
        cursor = conn.execute(
            "INSERT INTO edx_images (sample_id, filename, filepath, uploaded_at) VALUES (?, ?, ?, ?)",
            (sample_id, filename, filepath, now)
        )
        edx_id = cursor.lastrowid
        conn.commit()
    finally:
        conn.close()
    return edx_id


def update_edx_recognized_data(edx_id, data):
    conn = get_db()
    try:
        conn.execute(
            "UPDATE edx_images SET recognized_data = ? WHERE id = ?",
            (json.dumps(data, ensure_ascii=False), edx_id)
        )
        conn.commit()
    finally:
        conn.close()


def delete_edx_image(edx_id):
    conn = get_db()
    try:
        row = conn.execute("SELECT filepath FROM edx_images WHERE id = ?", (edx_id,)).fetchone()
        if row and os.path.exists(row['filepath']):
            os.remove(row['filepath'])
            # Also try to remove thumbnail
            dir_name = os.path.dirname(row['filepath'])
            base_name = os.path.basename(row['filepath'])
            thumb_path = os.path.join(dir_name, f"thumb_{base_name}")
            if os.path.exists(thumb_path):
                os.remove(thumb_path)
        conn.execute("DELETE FROM edx_images WHERE id = ?", (edx_id,))
        conn.commit()
    finally:
        conn.close()


def add_xrd_image(sample_id, filename, filepath):
    now = datetime.now().isoformat()
    conn = get_db()
    try:
        cursor = conn.execute(
            "INSERT INTO xrd_images (sample_id, filename, filepath, uploaded_at) VALUES (?, ?, ?, ?)",
            (sample_id, filename, filepath, now)
        )
        xrd_id = cursor.lastrowid
        conn.commit()
    finally:
        conn.close()
    return xrd_id


def delete_xrd_image(xrd_id):
    conn = get_db()
    try:
        row = conn.execute("SELECT filepath FROM xrd_images WHERE id = ?", (xrd_id,)).fetchone()
        if row and os.path.exists(row['filepath']):
            os.remove(row['filepath'])
            # Also try to remove thumbnail
            dir_name = os.path.dirname(row['filepath'])
            base_name = os.path.basename(row['filepath'])
            thumb_path = os.path.join(dir_name, f"thumb_{base_name}")
            if os.path.exists(thumb_path):
                os.remove(thumb_path)
        conn.execute("DELETE FROM xrd_images WHERE id = ?", (xrd_id,))
        conn.commit()
    finally:
        conn.close()


def add_data_file(sample_id, filename, filepath):
    now = datetime.now().isoformat()
    conn = get_db()
    try:
        cursor = conn.execute(
            "INSERT INTO data_files (sample_id, filename, filepath, uploaded_at) VALUES (?, ?, ?, ?)",
            (sample_id, filename, filepath, now)
        )
        file_id = cursor.lastrowid
        conn.commit()
    finally:
        conn.close()
    return file_id


def delete_data_file(file_id):
    conn = get_db()
    try:
        row = conn.execute("SELECT filepath FROM data_files WHERE id = ?", (file_id,)).fetchone()
        if row and os.path.exists(row['filepath']):
            os.remove(row['filepath'])
        conn.execute("DELETE FROM data_files WHERE id = ?", (file_id,))
        conn.commit()
    finally:
        conn.close()


def add_other_file(sample_id, filename, filepath):
    now = datetime.now().isoformat()
    conn = get_db()
    try:
        cursor = conn.execute(
            "INSERT INTO other_files (sample_id, filename, filepath, uploaded_at) VALUES (?, ?, ?, ?)",
            (sample_id, filename, filepath, now)
        )
        file_id = cursor.lastrowid
        conn.commit()
    finally:
        conn.close()
    return file_id


def delete_other_file(file_id):
    conn = get_db()
    try:
        row = conn.execute("SELECT filepath FROM other_files WHERE id = ?", (file_id,)).fetchone()
        if row and os.path.exists(row['filepath']):
            os.remove(row['filepath'])
        conn.execute("DELETE FROM other_files WHERE id = ?", (file_id,))
        conn.commit()
    finally:
        conn.close()


# ============================================================
# To Do 任务映射 (todo_tasks 表)
# ============================================================

def get_todo_task(sample_id):
    """获取样品关联的 To Do 任务记录"""
    conn = get_db()
    try:
        row = conn.execute("SELECT * FROM todo_tasks WHERE sample_id = ?", (sample_id,)).fetchone()
        if row:
            return dict(row)
    finally:
        conn.close()
    return None


def upsert_todo_task(sample_id, task_id, sintering_end):
    """插入或更新 To Do 任务映射"""
    now = datetime.now().isoformat()
    conn = get_db()
    try:
        conn.execute(
            """INSERT INTO todo_tasks (sample_id, task_id, sintering_end, updated_at)
               VALUES (?, ?, ?, ?)
               ON CONFLICT(sample_id) DO UPDATE SET
                   task_id = excluded.task_id,
                   sintering_end = excluded.sintering_end,
                   updated_at = excluded.updated_at""",
            (sample_id, task_id, sintering_end, now)
        )
        conn.commit()
    finally:
        conn.close()


def delete_todo_task(sample_id):
    """删除 To Do 任务映射"""
    conn = get_db()
    try:
        conn.execute("DELETE FROM todo_tasks WHERE sample_id = ?", (sample_id,))
        conn.commit()
    finally:
        conn.close()

