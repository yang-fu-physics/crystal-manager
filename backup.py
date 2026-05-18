# -*- coding: utf-8 -*-
"""
backup.py — 增量备份与恢复模块

备份结构:
  backups/
    manifest.json           ← 已备份文件的记录 {relative_path: mtime}
    2026-03-08_22-00-00/
      db.sqlite             ← 数据库完整快照 (SQLite Online Backup API)
      files/                ← 本次新增/变更的 uploads 文件
        CG-001/photos/xxx.jpg
        ...
      backup_info.json      ← 本次备份元信息 (时间、文件数)
    2026-03-09_22-00-00/
      ...

恢复逻辑:
  1. 选定目标备份时间点
  2. 恢复该目间点的 db.sqlite
  3. 按时间顺序合并所有 <= 目标时间的 files/ 目录，重建 uploads/
"""

import os
import json
import shutil
import sqlite3
import threading
import time
import zipfile
import logging
from datetime import datetime

import config

logger = logging.getLogger("crystal.backup")

# ---------- 内部常量 ----------
MANIFEST_PATH = os.path.join(config.BACKUP_FOLDER, "manifest.json")
TIMESTAMP_FMT = "%Y-%m-%d_%H-%M-%S"


# ============================================================
# 工具函数
# ============================================================

def _load_manifest() -> dict:
    """加载已备份文件清单 {相对路径: 修改时间}"""
    if os.path.exists(MANIFEST_PATH):
        with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def _save_manifest(manifest: dict):
    with open(MANIFEST_PATH, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)


def list_backups() -> list:
    """返回所有备份时间戳列表 (str, 升序)"""
    result = []
    for name in sorted(os.listdir(config.BACKUP_FOLDER)):
        info_path = os.path.join(config.BACKUP_FOLDER, name, "backup_info.json")
        if os.path.isdir(os.path.join(config.BACKUP_FOLDER, name)) and os.path.exists(info_path):
            result.append(name)
    return result


# ============================================================
# 备份
# ============================================================

def _backup_sqlite(dest_dir: str):
    """使用 SQLite Online Backup API 备份数据库（安全、热备份）"""
    dest_path = os.path.join(dest_dir, "db.sqlite")
    src_conn = sqlite3.connect(config.DATABASE_PATH)
    dst_conn = sqlite3.connect(dest_path)
    with dst_conn:
        src_conn.backup(dst_conn)
    dst_conn.close()
    src_conn.close()
    logger.debug(f"DB 已备份到 {dest_path}")


def _backup_files(dest_dir: str, manifest: dict) -> tuple[int, int]:
    """
    增量备份 uploads 目录中有变化的文件。
    返回 (新增文件数, 更新文件数)
    """
    files_dest = os.path.join(dest_dir, "files")
    added = updated = 0

    for root, _, filenames in os.walk(config.UPLOAD_FOLDER):
        for fname in filenames:
            abs_path = os.path.join(root, fname)
            rel_path = os.path.relpath(abs_path, config.UPLOAD_FOLDER)
            mtime = round(os.path.getmtime(abs_path), 3)

            if rel_path not in manifest:
                action = "new"
                added += 1
            elif manifest[rel_path] != mtime:
                action = "updated"
                updated += 1
            else:
                continue  # 未变化，跳过

            # 拷贝文件
            dest_path = os.path.join(files_dest, rel_path)
            os.makedirs(os.path.dirname(dest_path), exist_ok=True)
            shutil.copy2(abs_path, dest_path)
            manifest[rel_path] = mtime
            logger.debug(f"[{action}] {rel_path}")

    return added, updated


def run_backup() -> str:
    """
    执行一次备份，返回备份目录路径。
    可安全地在后台线程中调用。
    """
    ts = config.get_local_now().strftime(TIMESTAMP_FMT)
    dest_dir = os.path.join(config.BACKUP_FOLDER, ts)
    os.makedirs(dest_dir, exist_ok=True)

    logger.info(f"开始备份 → {dest_dir}")

    try:
        # 1. 备份数据库
        _backup_sqlite(dest_dir)

        # 2. 增量备份文件
        manifest = _load_manifest()
        added, updated = _backup_files(dest_dir, manifest)
        _save_manifest(manifest)

        # 3. 写备份信息
        info = {
            "timestamp": ts,
            "db_size_bytes": os.path.getsize(os.path.join(dest_dir, "db.sqlite")),
            "files_added": added,
            "files_updated": updated,
        }
        with open(os.path.join(dest_dir, "backup_info.json"), "w", encoding="utf-8") as f:
            json.dump(info, f, ensure_ascii=False, indent=2)

        logger.info(f"备份完成：新增 {added} 个文件，更新 {updated} 个文件")

        # 4. 清理旧备份
        _prune_old_backups()

        return dest_dir

    except Exception as e:
        logger.error(f"备份失败: {e}", exc_info=True)
        # 清理不完整的备份目录
        if os.path.isdir(dest_dir) and not os.listdir(dest_dir):
            os.rmdir(dest_dir)
        raise


def _prune_old_backups():
    """删除超出 BACKUP_KEEP_COUNT 的最旧备份"""
    backups = list_backups()
    excess = len(backups) - config.BACKUP_KEEP_COUNT
    for old_ts in backups[:excess]:
        old_dir = os.path.join(config.BACKUP_FOLDER, old_ts)
        shutil.rmtree(old_dir, ignore_errors=True)
        logger.info(f"已删除旧增量备份: {old_ts}")


# ============================================================
# 完整备份 (zip 压缩)
# ============================================================

def list_full_backups() -> list:
    """返回所有完整备份文件名列表 (升序)"""
    result = []
    if not os.path.isdir(config.FULL_BACKUP_FOLDER):
        return result
    for name in sorted(os.listdir(config.FULL_BACKUP_FOLDER)):
        if name.startswith("full_") and name.endswith(".zip"):
            result.append(name)
    return result


def run_full_backup() -> str:
    """
    执行一次完整备份，将数据库 + 整个 uploads 目录打包为 zip 文件。
    返回 zip 文件路径。
    """
    ts = config.get_local_now().strftime(TIMESTAMP_FMT)
    zip_name = f"full_{ts}.zip"
    zip_path = os.path.join(config.FULL_BACKUP_FOLDER, zip_name)

    logger.info(f"开始完整备份 → {zip_path}")

    try:
        # 先用 SQLite Backup API 导出一份安全的数据库快照到临时文件
        temp_db = os.path.join(config.FULL_BACKUP_FOLDER, f"_temp_{ts}.sqlite")
        src_conn = sqlite3.connect(config.DATABASE_PATH)
        dst_conn = sqlite3.connect(temp_db)
        with dst_conn:
            src_conn.backup(dst_conn)
        dst_conn.close()
        src_conn.close()

        # 创建 zip 文件
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
            # 添加数据库快照
            zf.write(temp_db, "db.sqlite")

            # 添加整个 uploads 目录
            if os.path.isdir(config.UPLOAD_FOLDER):
                for root, dirs, filenames in os.walk(config.UPLOAD_FOLDER):
                    for fname in filenames:
                        abs_path = os.path.join(root, fname)
                        arc_name = os.path.join(
                            "uploads",
                            os.path.relpath(abs_path, config.UPLOAD_FOLDER)
                        )
                        zf.write(abs_path, arc_name)

        # 删除临时数据库文件
        os.remove(temp_db)

        # 统计信息
        zip_size_mb = os.path.getsize(zip_path) / 1024 / 1024
        logger.info(f"完整备份完成：{zip_name} ({zip_size_mb:.1f} MB)")

        # 清理旧的完整备份
        _prune_old_full_backups()

        return zip_path

    except Exception as e:
        logger.error(f"完整备份失败: {e}", exc_info=True)
        # 清理不完整的文件
        for f in [zip_path, temp_db if 'temp_db' in dir() else None]:
            if f and os.path.exists(f):
                try:
                    os.remove(f)
                except OSError:
                    pass
        raise


def restore_full_backup(zip_name: str, target_upload_dir: str = None, target_db_path: str = None):
    """
    从完整备份 zip 文件恢复。

    :param zip_name: zip 文件名，如 'full_2026-03-08_22-00-00.zip'
    :param target_upload_dir: 恢复到的 uploads 目录（默认 config.UPLOAD_FOLDER）
    :param target_db_path: 恢复到的 DB 路径（默认 config.DATABASE_PATH）
    """
    if target_upload_dir is None:
        target_upload_dir = config.UPLOAD_FOLDER
    if target_db_path is None:
        target_db_path = config.DATABASE_PATH

    zip_path = os.path.join(config.FULL_BACKUP_FOLDER, zip_name)
    if not os.path.exists(zip_path):
        available = list_full_backups()
        raise ValueError(f"完整备份不存在: {zip_name}\n可用备份: {available}")

    logger.info(f"正在从完整备份恢复: {zip_name}")

    with zipfile.ZipFile(zip_path, 'r') as zf:
        members = zf.namelist()

        # 1. 恢复数据库
        if "db.sqlite" not in members:
            raise FileNotFoundError(f"备份中缺少数据库文件: db.sqlite")

        # 解压到临时文件，再用 SQLite Backup API 安全恢复
        temp_db = target_db_path + ".restore_tmp"
        with zf.open("db.sqlite") as src, open(temp_db, 'wb') as dst:
            shutil.copyfileobj(src, dst)

        src_conn = sqlite3.connect(temp_db)
        dst_conn = sqlite3.connect(target_db_path)
        with dst_conn:
            src_conn.backup(dst_conn)
        dst_conn.close()
        src_conn.close()
        os.remove(temp_db)
        logger.info(f"数据库已恢复 → {target_db_path}")

        # 2. 恢复 uploads 文件
        upload_members = [m for m in members if m.startswith("uploads/") and not m.endswith("/")]
        for member in upload_members:
            rel_path = member[len("uploads/"):]  # 去掉 "uploads/" 前缀
            dst_path = os.path.join(target_upload_dir, rel_path)
            os.makedirs(os.path.dirname(dst_path), exist_ok=True)
            with zf.open(member) as src, open(dst_path, 'wb') as dst:
                shutil.copyfileobj(src, dst)

        logger.info(f"文件已恢复 ({len(upload_members)} 个文件) → {target_upload_dir}")

    logger.info(f"完整备份恢复完成: {zip_name}")


def _prune_old_full_backups():
    """删除超出 FULL_BACKUP_KEEP_COUNT 的最旧完整备份"""
    backups = list_full_backups()
    excess = len(backups) - config.FULL_BACKUP_KEEP_COUNT
    for old_name in backups[:excess]:
        old_path = os.path.join(config.FULL_BACKUP_FOLDER, old_name)
        try:
            os.remove(old_path)
            logger.info(f"已删除旧完整备份: {old_name}")
        except OSError as e:
            logger.error(f"删除完整备份失败: {old_name}: {e}")


# ============================================================
# 恢复
# ============================================================

def restore_backup(timestamp: str, target_upload_dir: str = None, target_db_path: str = None):
    """
    恢复到指定时间点的备份。

    策略：
      - 将指定备份的 db.sqlite 覆盖当前数据库
      - 重建 uploads：按时间顺序将所有 <= timestamp 的 files/ 合并

    :param timestamp: 备份时间戳字符串，如 '2026-03-08_22-00-00'
    :param target_upload_dir: 恢复到的 uploads 目录（默认 config.UPLOAD_FOLDER）
    :param target_db_path: 恢复到的 DB 路径（默认 config.DATABASE_PATH）
    """
    if target_upload_dir is None:
        target_upload_dir = config.UPLOAD_FOLDER
    if target_db_path is None:
        target_db_path = config.DATABASE_PATH

    all_backups = list_backups()
    if timestamp not in all_backups:
        raise ValueError(f"备份不存在: {timestamp}\n可用备份: {all_backups}")

    backup_dir = os.path.join(config.BACKUP_FOLDER, timestamp)

    # 1. 恢复数据库
    db_backup = os.path.join(backup_dir, "db.sqlite")
    if not os.path.exists(db_backup):
        raise FileNotFoundError(f"数据库备份文件不存在: {db_backup}")

    logger.info(f"正在恢复数据库 → {target_db_path}")
    src_conn = sqlite3.connect(db_backup)
    dst_conn = sqlite3.connect(target_db_path)
    with dst_conn:
        src_conn.backup(dst_conn)
    dst_conn.close()
    src_conn.close()

    # 2. 重建 uploads/: 按时间顺序叠加所有 <= timestamp 的 files/
    logger.info(f"正在重建文件 → {target_upload_dir}")
    eligible = [b for b in all_backups if b <= timestamp]
    for bts in eligible:
        files_src = os.path.join(config.BACKUP_FOLDER, bts, "files")
        if not os.path.isdir(files_src):
            continue
        for root, _, filenames in os.walk(files_src):
            for fname in filenames:
                src_path = os.path.join(root, fname)
                rel = os.path.relpath(src_path, files_src)
                dst_path = os.path.join(target_upload_dir, rel)
                os.makedirs(os.path.dirname(dst_path), exist_ok=True)
                shutil.copy2(src_path, dst_path)

    logger.info(f"恢复完成 (时间点: {timestamp})")


# ============================================================
# 定时调度器
# ============================================================

_scheduler_thread: threading.Thread | None = None
_full_scheduler_thread: threading.Thread | None = None
_stop_event = threading.Event()


def _scheduler_loop():
    """ 增量备份调度循环 """
    interval_secs = config.BACKUP_INTERVAL_HOURS * 3600
    logger.info(f"增量备份调度器启动，间隔 {config.BACKUP_INTERVAL_HOURS} 小时")
    while not _stop_event.is_set():
        try:
            run_backup()
        except Exception:
            pass  # 错误已在 run_backup 中记录
        _stop_event.wait(timeout=interval_secs)
    logger.info("增量备份调度器已停止")


def _full_backup_scheduler_loop():
    """ 完整备份调度循环 """
    interval_secs = config.FULL_BACKUP_INTERVAL_HOURS * 3600
    logger.info(f"完整备份调度器启动，间隔 {config.FULL_BACKUP_INTERVAL_HOURS} 小时 ({config.FULL_BACKUP_INTERVAL_HOURS / 24:.0f} 天)")
    while not _stop_event.is_set():
        try:
            run_full_backup()
        except Exception:
            pass  # 错误已在 run_full_backup 中记录
        _stop_event.wait(timeout=interval_secs)
    logger.info("完整备份调度器已停止")


def _is_werkzeug_spawner() -> bool:
    """Flask debug 模式下检测是否在父进程 (spawner) 中"""
    import os as _os
    wrm = _os.environ.get('WERKZEUG_RUN_MAIN')
    return wrm is not None and wrm != 'true'


def start_scheduler():
    """在后台线程中启动定时备份调度器（幂等）"""
    global _scheduler_thread, _full_scheduler_thread

    if _is_werkzeug_spawner():
        return

    _stop_event.clear()

    # 增量备份调度器
    if not (_scheduler_thread and _scheduler_thread.is_alive()):
        _scheduler_thread = threading.Thread(
            target=_scheduler_loop,
            name="BackupScheduler",
            daemon=True,
        )
        _scheduler_thread.start()

    # 完整备份调度器
    if not (_full_scheduler_thread and _full_scheduler_thread.is_alive()):
        _full_scheduler_thread = threading.Thread(
            target=_full_backup_scheduler_loop,
            name="FullBackupScheduler",
            daemon=True,
        )
        _full_scheduler_thread.start()


def stop_scheduler():
    """停止所有定时备份调度器"""
    _stop_event.set()
