# -*- coding: utf-8 -*-
"""
迁移脚本：将旧的扁平文件结构迁移到按样品编号组织的新结构。

旧结构:
  uploads/photos/<uuid>.jpg
  uploads/edx/<uuid>.png
  uploads/data/<uuid>.dat
  uploads/others/<uuid>.xxx

新结构:
  uploads/<sample_id>/photos/<uuid>.jpg
  uploads/<sample_id>/edx/<uuid>.png
  uploads/<sample_id>/data/<uuid>.dat
  uploads/<sample_id>/others/<uuid>.xxx

数据库中的 filepath 字段也会同步更新。

使用方法:
  python migrate_storage.py [--dry-run]

  --dry-run: 仅打印将要移动的文件，不实际执行移动。
"""

import os
import sys
import shutil
import sqlite3

# 切换工作目录到脚本所在位置
os.chdir(os.path.dirname(os.path.abspath(__file__)))
import config


def sanitize(sample_id: str) -> str:
    return "".join(c if (c.isalnum() or c in '-_.') else '_' for c in sample_id)


def migrate_table(conn, table: str, subtype: str, dry_run: bool):
    rows = conn.execute(
        f"SELECT id, sample_id, filename, filepath FROM {table} ORDER BY id"
    ).fetchall()

    moved = 0
    skipped = 0

    for row in rows:
        file_id, sample_id, filename, old_path = (
            row['id'], row['sample_id'], row['filename'], row['filepath']
        )

        safe_id = sanitize(sample_id)
        new_dir = os.path.join(config.UPLOAD_FOLDER, safe_id, subtype)
        # Infer the filename part from old_path
        basename = os.path.basename(old_path)
        new_path = os.path.join(new_dir, basename)

        if old_path == new_path:
            skipped += 1
            continue

        if not os.path.exists(old_path):
            print(f"  [WARN] 文件不存在，跳过: {old_path}")
            skipped += 1
            continue

        print(f"  [MOVE] {old_path}\n"
              f"      -> {new_path}")

        if not dry_run:
            os.makedirs(new_dir, exist_ok=True)
            shutil.move(old_path, new_path)
            conn.execute(
                f"UPDATE {table} SET filepath = ? WHERE id = ?",
                (new_path, file_id)
            )
            moved += 1
        else:
            moved += 1

    print(f"  {table}: {moved} 个文件将被移动，{skipped} 个跳过")
    return moved


def main():
    dry_run = '--dry-run' in sys.argv

    if dry_run:
        print("=== DRY RUN 模式 — 不会实际移动文件 ===\n")
    else:
        print("=== 开始迁移文件结构 ===\n")

    conn = sqlite3.connect(config.DATABASE_PATH)
    conn.row_factory = sqlite3.Row

    total = 0
    total += migrate_table(conn, 'photos',      'photos', dry_run)
    total += migrate_table(conn, 'edx_images',  'edx',    dry_run)
    total += migrate_table(conn, 'data_files',  'data',   dry_run)

    # other_files 可能不存在于旧数据库
    try:
        total += migrate_table(conn, 'other_files', 'others', dry_run)
    except sqlite3.OperationalError:
        print("  other_files: 表不存在，跳过")

    if not dry_run:
        conn.commit()
        print(f"\n✅ 迁移完成，共移动 {total} 个文件。")
        print("提示: 旧的空目录（uploads/photos 等）可以手动删除。")
    else:
        print(f"\n☑  Dry run 结束，共 {total} 个文件需要移动。")
        print("若确认无误，去掉 --dry-run 参数再运行一次即可。")

    conn.close()


if __name__ == '__main__':
    main()
