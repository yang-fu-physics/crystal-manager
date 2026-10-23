# -*- coding: utf-8 -*-
"""完整数据库（含聊天历史）+ 附件增量；恢复时从完整基线顺序重放。"""

from contextlib import closing, contextmanager
from pathlib import Path, PurePosixPath, PureWindowsPath
import json
import logging
import os
import shutil
import sqlite3
import tempfile
import threading
import time
import zipfile

import config

logger = logging.getLogger("crystal.backup")
MANIFEST_PATH = os.path.join(config.BACKUP_FOLDER, "manifest.json")
TIMESTAMP_FMT = "%Y-%m-%d_%H-%M-%S_%f"
_backup_mutex = threading.Lock()


@contextmanager
def _backup_guard():
    """串行化线程和命令行进程对同一恢复链的更新。"""
    with _backup_mutex:
        os.makedirs(config.BACKUP_FOLDER, exist_ok=True)
        with open(os.path.join(config.BACKUP_FOLDER, ".backup.lock"), "a+b") as lock:
            if os.name == "nt":
                import msvcrt
                if os.fstat(lock.fileno()).st_size == 0:
                    lock.write(b"0")
                    lock.flush()
                lock.seek(0)
                msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            try:
                yield
            finally:
                if os.name == "nt":
                    lock.seek(0)
                    msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    fcntl.flock(lock.fileno(), fcntl.LOCK_UN)


def _load_manifest():
    if not os.path.exists(MANIFEST_PATH):
        return {}
    with open(MANIFEST_PATH, encoding="utf-8") as stream:
        return json.load(stream)


def _save_manifest(manifest):
    temporary = MANIFEST_PATH + ".tmp"
    with open(temporary, "w", encoding="utf-8") as stream:
        json.dump(manifest, stream, ensure_ascii=False, indent=2)
    os.replace(temporary, MANIFEST_PATH)


def list_backups():
    if not os.path.isdir(config.BACKUP_FOLDER):
        return []
    return sorted(name for name in os.listdir(config.BACKUP_FOLDER)
                  if not name.startswith(".")
                  and os.path.isfile(os.path.join(config.BACKUP_FOLDER, name, "backup_info.json")))


def list_full_backups():
    if not os.path.isdir(config.FULL_BACKUP_FOLDER):
        return []
    return sorted(name for name in os.listdir(config.FULL_BACKUP_FOLDER)
                  if name.startswith("full_") and name.endswith(".zip")
                  and os.path.isfile(os.path.join(config.FULL_BACKUP_FOLDER, name)))


def _copy_database(source, destination):
    # 整库快照：样品、聊天会话/消息、确认及撤销状态均包含在内。
    with closing(sqlite3.connect(Path(source).resolve().as_uri() + "?mode=ro", uri=True)) as src:
        with closing(sqlite3.connect(destination)) as dst:
            with dst:
                src.backup(dst)


def _backup_files(destination, previous):
    current, copied = {}, []
    added = updated = 0
    root = Path(config.UPLOAD_FOLDER)
    for directory, _, filenames in os.walk(root):
        for name in filenames:
            source = Path(directory) / name
            relative = source.relative_to(root).as_posix()
            stat = source.stat()
            current[relative] = {"mtime_ns": stat.st_mtime_ns, "size": stat.st_size}
            if previous.get(relative) == current[relative]:
                continue
            target = Path(destination, "files", relative)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
            copied.append(relative)
            if relative in previous:
                updated += 1
            else:
                added += 1
    return current, copied, sorted(previous.keys() - current.keys()), added, updated


def _write_full_backup():
    """调用者持有备份锁；同时为后续增量发布新的基线。"""
    os.makedirs(config.FULL_BACKUP_FOLDER, exist_ok=True)
    timestamp = config.get_local_now().strftime(TIMESTAMP_FMT)
    name = f"full_{timestamp}.zip"
    target = Path(config.FULL_BACKUP_FOLDER, name)
    if target.exists():
        raise FileExistsError(f"完整备份已存在: {name}")
    files = {}
    with tempfile.TemporaryDirectory(prefix=".full-", dir=config.FULL_BACKUP_FOLDER) as temporary:
        database = Path(temporary, "db.sqlite")
        _copy_database(config.DATABASE_PATH, database)
        archive = Path(temporary, name)
        with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as output:
            output.write(database, "db.sqlite")
            root = Path(config.UPLOAD_FOLDER)
            for directory, _, filenames in os.walk(root):
                for filename in filenames:
                    source = Path(directory, filename)
                    relative = source.relative_to(root).as_posix()
                    stat = source.stat()
                    files[relative] = {"mtime_ns": stat.st_mtime_ns, "size": stat.st_size}
                    output.write(source, "uploads/" + relative)
            output.writestr("backup_info.json", json.dumps({
                "format_version": 2, "kind": "full", "timestamp": timestamp, "files": files,
            }, ensure_ascii=False))
        _save_manifest({"format_version": 2, "base_full": name, "last_incremental": None, "files": files})
        os.replace(archive, target)
    _prune_old_full_backups()
    logger.info("完整备份完成: %s（含所有数据库表及上传文件）", name)
    return str(target)


def run_full_backup():
    with _backup_guard():
        return _write_full_backup()


def run_backup():
    with _backup_guard():
        manifest = _load_manifest()
        if manifest.get("format_version") != 2 or manifest["base_full"] not in list_full_backups():
            # 首次使用或升级旧格式时，先建立可验证的完整基线。
            _write_full_backup()
            manifest = _load_manifest()
        if manifest["last_incremental"] is not None:
            get_restore_plan(manifest["last_incremental"], manifest["base_full"])
        timestamp = config.get_local_now().strftime(TIMESTAMP_FMT)
        target = Path(config.BACKUP_FOLDER, timestamp)
        if target.exists():
            raise FileExistsError(f"增量备份已存在: {timestamp}")
        with tempfile.TemporaryDirectory(prefix=".incremental-", dir=config.BACKUP_FOLDER) as temporary:
            _copy_database(config.DATABASE_PATH, Path(temporary, "db.sqlite"))
            files, copied, deleted, added, updated = _backup_files(temporary, manifest["files"])
            info = {
                "format_version": 2, "kind": "incremental", "timestamp": timestamp,
                "base_full": manifest["base_full"], "previous_incremental": manifest["last_incremental"],
                "db_size_bytes": Path(temporary, "db.sqlite").stat().st_size,
                "files_added": added, "files_updated": updated, "files": copied, "deleted_files": deleted,
            }
            with open(Path(temporary, "backup_info.json"), "w", encoding="utf-8") as stream:
                json.dump(info, stream, ensure_ascii=False, indent=2)
            _save_manifest({**manifest, "last_incremental": timestamp, "files": files})
            os.replace(temporary, target)
        _prune_old_backups()
        logger.info("增量备份完成: %s（新增 %s，修改 %s，删除 %s）", timestamp, added, updated, len(deleted))
        return str(target)


def _prune_old_backups():
    backups = list_backups()
    excess = max(0, len(backups) - config.BACKUP_KEEP_COUNT)
    full = list_full_backups()
    # 保留仍被完整基线依赖的增量，不能为满足数量限制拆断恢复链。
    removable = [timestamp for timestamp in backups if full and
                 (timestamp < full[0][5:-4] or
                  (timestamp == full[0][5:-4] and _incremental_info(timestamp).get("base_full") != full[0]))]
    for timestamp in removable[:excess]:
        target = Path(config.BACKUP_FOLDER, timestamp).resolve()
        if not target.is_relative_to(Path(config.BACKUP_FOLDER).resolve()):
            raise ValueError("增量备份目录越界")
        shutil.rmtree(target)
        logger.info("已删除旧增量备份: %s", timestamp)
    if excess > len(removable):
        logger.warning("增量保留数暂超限制：仍需保留完整恢复链")


def _prune_old_full_backups():
    backups = list_full_backups()
    if config.FULL_BACKUP_KEEP_COUNT < 1:
        raise ValueError("至少需要保留一份完整备份")
    for name in backups[:max(0, len(backups) - config.FULL_BACKUP_KEEP_COUNT)]:
        Path(config.FULL_BACKUP_FOLDER, name).unlink()
        logger.info("已删除旧完整备份: %s", name)


def _incremental_info(timestamp):
    with open(Path(config.BACKUP_FOLDER, timestamp, "backup_info.json"), encoding="utf-8") as stream:
        return json.load(stream)


def get_restore_plan(timestamp=None, full_backup=None):
    """预览完整基线与后续增量；缺失链或目标不可用时在修改数据前失败。"""
    full = list_full_backups()
    incremental = list_backups()
    if not full:
        raise ValueError("没有可用的完整备份，不能只用增量恢复")
    if full_backup is not None and full_backup not in full:
        raise ValueError(f"完整备份不存在: {full_backup}")
    if full_backup is not None:
        base_time = full_backup[5:-4]
        later_full = [name[5:-4] for name in full if name[5:-4] > base_time]
        limit = later_full[0] if later_full else None
        if timestamp is None:
            candidates = [value for value in incremental if value > base_time and (limit is None or value < limit)]
            timestamp = candidates[-1] if candidates else base_time
        if timestamp < base_time or (limit is not None and timestamp >= limit):
            raise ValueError("目标不属于所选完整备份的恢复链，请按目标时间自动选择基线")
    else:
        if timestamp is None:
            timestamp = max([name[5:-4] for name in full] + incremental)
        eligible = [name for name in full if name[5:-4] <= timestamp]
        if not eligible:
            raise ValueError("目标时间之前没有完整备份")
        full_backup = eligible[-1]
        base_time = full_backup[5:-4]
    if timestamp not in incremental and timestamp not in [name[5:-4] for name in full]:
        raise ValueError(f"备份时间点不存在: {timestamp}")
    selected = [value for value in incremental if value <= timestamp and
                (value > base_time or (value == base_time and _incremental_info(value).get("base_full") == full_backup))]
    previous = None
    legacy = False
    for value in selected:
        info = _incremental_info(value)
        if not Path(config.BACKUP_FOLDER, value, "db.sqlite").is_file():
            raise FileNotFoundError(f"增量数据库快照缺失: {value}")
        if info.get("format_version") == 2:
            if info["base_full"] != full_backup or info["previous_incremental"] != previous:
                raise ValueError(f"增量恢复链不完整或基线不匹配: {value}")
        else:
            legacy = True
        previous = value
    return {"full_backup": full_backup, "incrementals": selected, "timestamp": timestamp, "legacy": legacy}


def _relative_path(root, relative):
    """校验来自备份元数据/压缩包的相对路径。"""
    if not isinstance(relative, str) or PureWindowsPath(relative).drive:
        raise ValueError(f"备份路径无效: {relative!r}")
    path = PurePosixPath(relative.replace("\\", "/"))
    root = Path(root).resolve()
    target = root.joinpath(*path.parts).resolve()
    if path.is_absolute() or ".." in path.parts or target == root or not target.is_relative_to(root):
        raise ValueError(f"备份路径越界: {relative}")
    return target


def restore_backup(timestamp=None, target_upload_dir=None, target_db_path=None, *, full_backup=None):
    """先在临时目录还原完整备份及后续增量，验证后替换目标数据。应用必须先停止。"""
    with _backup_guard():
        plan = get_restore_plan(timestamp, full_backup)
        uploads = Path(config.UPLOAD_FOLDER if target_upload_dir is None else target_upload_dir).resolve()
        database = Path(config.DATABASE_PATH if target_db_path is None else target_db_path).resolve()
        backup_roots = [Path(config.BACKUP_FOLDER).resolve(), Path(config.FULL_BACKUP_FOLDER).resolve()]
        if (uploads == uploads.parent or database.is_relative_to(uploads)
                or any(root.is_relative_to(uploads) or uploads.is_relative_to(root) for root in backup_roots)
                or any(database.is_relative_to(root) for root in backup_roots)):
            raise ValueError("恢复目标不能覆盖数据库所在目录、文件系统根目录或备份目录")
        uploads.parent.mkdir(parents=True, exist_ok=True)
        database.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix=".crystal-restore-", dir=uploads.parent) as temporary:
            staged_uploads = Path(temporary, "uploads")
            staged_uploads.mkdir()
            staged_db = Path(temporary, "db.sqlite")
            with zipfile.ZipFile(Path(config.FULL_BACKUP_FOLDER, plan["full_backup"])) as archive:
                with archive.open("db.sqlite") as source, staged_db.open("wb") as output:
                    shutil.copyfileobj(source, output)
                members = [name for name in archive.namelist() if name.startswith("uploads/") and not name.endswith("/")]
                if "backup_info.json" in archive.namelist():
                    info = json.loads(archive.read("backup_info.json"))
                    if info.get("format_version") == 2 and set(info["files"]) != {name[8:] for name in members}:
                        raise ValueError("完整备份文件清单不一致")
                else:
                    plan["legacy"] = True
                for name in members:
                    target = _relative_path(staged_uploads, name[8:])
                    target.parent.mkdir(parents=True, exist_ok=True)
                    with archive.open(name) as source, target.open("wb") as output:
                        shutil.copyfileobj(source, output)
            for value in plan["incrementals"]:
                info = _incremental_info(value)
                source_root = Path(config.BACKUP_FOLDER, value, "files")
                if info.get("format_version") == 2:
                    for relative in info["deleted_files"]:
                        _relative_path(staged_uploads, relative).unlink(missing_ok=True)
                    paths = info["files"]
                else:
                    paths = [path.relative_to(source_root).as_posix() for path in source_root.rglob("*") if path.is_file()]
                for relative in paths:
                    source = _relative_path(source_root, relative)
                    target = _relative_path(staged_uploads, relative)
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(source, target)
                shutil.copy2(Path(config.BACKUP_FOLDER, value, "db.sqlite"), staged_db)
            with closing(sqlite3.connect(staged_db)) as connection:
                if connection.execute("PRAGMA quick_check").fetchall() != [("ok",)]:
                    raise ValueError("备份数据库完整性检查失败")
                connection.execute("SELECT 1 FROM samples LIMIT 0")
            # 临时目录与 uploads 同卷；保留原目录，数据库恢复失败时还原文件。
            old_uploads = Path(temporary, "previous-uploads")
            had_uploads = uploads.exists()
            if had_uploads:
                os.replace(uploads, old_uploads)
            installed = False
            try:
                os.replace(staged_uploads, uploads)
                installed = True
                _copy_database(staged_db, database)
            except (OSError, sqlite3.Error):
                if installed:
                    os.replace(uploads, Path(temporary, "failed-uploads"))
                if had_uploads:
                    os.replace(old_uploads, uploads)
                raise
        logger.info("恢复完成: %s + %s 份增量 → %s", plan["full_backup"], len(plan["incrementals"]), plan["timestamp"])
        return plan


def restore_full_backup(zip_name, target_upload_dir=None, target_db_path=None, timestamp=None):
    """恢复所选完整基线，并叠加同一恢复链中的后续增量。"""
    return restore_backup(timestamp, target_upload_dir, target_db_path, full_backup=zip_name)


_scheduler_thread = None
_stop_event = threading.Event()


def _scheduler_loop():
    # 同时到期时先完整、后增量，避免启动时并发重置恢复基线。
    next_full = next_incremental = time.monotonic()
    while not _stop_event.is_set():
        if time.monotonic() >= next_full:
            try:
                run_full_backup()
            except (OSError, sqlite3.Error, zipfile.BadZipFile, ValueError):
                logger.exception("定时完整备份失败")
            next_full = time.monotonic() + config.FULL_BACKUP_INTERVAL_HOURS * 3600
        if not _stop_event.is_set() and time.monotonic() >= next_incremental:
            try:
                run_backup()
            except (OSError, sqlite3.Error, zipfile.BadZipFile, ValueError):
                logger.exception("定时增量备份失败")
            next_incremental = time.monotonic() + config.BACKUP_INTERVAL_HOURS * 3600
        _stop_event.wait(max(0, min(next_full, next_incremental) - time.monotonic()))


def start_scheduler():
    global _scheduler_thread
    if not (_scheduler_thread and _scheduler_thread.is_alive()):
        _stop_event.clear()
        _scheduler_thread = threading.Thread(target=_scheduler_loop, name="BackupScheduler", daemon=True)
        _scheduler_thread.start()


def stop_scheduler():
    _stop_event.set()
