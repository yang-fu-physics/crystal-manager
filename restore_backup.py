# -*- coding: utf-8 -*-
"""
restore_backup.py — 交互式备份恢复命令行工具

使用方法:
  python restore_backup.py                # 交互式选择恢复
  python restore_backup.py list           # 列出所有备份 (增量 + 完整)
  python restore_backup.py restore [timestamp]  # 完整备份 + 后续增量，默认最新时间点
  python restore_backup.py <timestamp>    # 同上，保留原命令形式
  python restore_backup.py backup         # 立即执行一次增量备份
  python restore_backup.py full-backup    # 立即执行一次完整备份 (zip)
  python restore_backup.py full-restore <zip_name> [timestamp]  # 指定完整基线及其后的增量

示例:
  python restore_backup.py 2026-03-08_22-00-00
  python restore_backup.py full-backup
  python restore_backup.py full-restore full_2026-03-08_22-00-00.zip
"""

import sys
import os
import sqlite3
import zipfile

# 切换到脚本目录，使 config 可以被正确导入
os.chdir(os.path.dirname(os.path.abspath(__file__)))

import backup
import config


def cmd_list():
    # 增量备份
    backups = backup.list_backups()
    print("=" * 60)
    print("增量备份")
    print("=" * 60)
    if not backups:
        print("  暂无增量备份。\n")
    else:
        print(f"  共 {len(backups)} 个增量备份（保留目标 {config.BACKUP_KEEP_COUNT} 个，完整恢复链优先）:\n")
        for i, ts in enumerate(reversed(backups), 1):
            info_path = os.path.join(config.BACKUP_FOLDER, ts, "backup_info.json")
            extra = ""
            if os.path.exists(info_path):
                import json
                with open(info_path, encoding="utf-8") as f:
                    info = json.load(f)
                db_mb = info.get("db_size_bytes", 0) / 1024 / 1024
                added = info.get("files_added", 0)
                updated = info.get("files_updated", 0)
                deleted = len(info.get("deleted_files", []))
                extra = f"  DB: {db_mb:.2f} MB  新增: {added}  更新: {updated}  删除: {deleted}"
            print(f"    [{i:2d}] {ts}{extra}")
        print()

    # 完整备份
    full_backups = backup.list_full_backups()
    print("=" * 60)
    print("完整备份 (zip)")
    print("=" * 60)
    if not full_backups:
        print("  暂无完整备份。\n")
    else:
        print(f"  共 {len(full_backups)} 个完整备份（最多保留 {config.FULL_BACKUP_KEEP_COUNT} 个）:\n")
        for i, name in enumerate(reversed(full_backups), 1):
            zip_path = os.path.join(config.FULL_BACKUP_FOLDER, name)
            size_mb = os.path.getsize(zip_path) / 1024 / 1024
            print(f"    [{i:2d}] {name}  ({size_mb:.1f} MB)")
        print()


def cmd_restore(timestamp=None, full_backup=None):
    try:
        plan = backup.get_restore_plan(timestamp, full_backup)
    except (OSError, ValueError) as error:
        print(f"无法生成恢复计划: {error}", file=sys.stderr)
        raise SystemExit(1) from error
    print(f"\n⚠️  即将恢复到: {plan['timestamp']}")
    print(f"   完整基线: {plan['full_backup']}")
    print(f"   后续增量: {len(plan['incrementals'])} 份，按以下顺序应用")
    for value in plan['incrementals']:
        print(f"     {value}")
    if plan['legacy']:
        print("   旧格式增量不含前序和删除记录，无法校验缺链或还原历史删除。")
    print(f"   数据库: {config.DATABASE_PATH}")
    print(f"   文件目录: {config.UPLOAD_FOLDER}")
    print("   请先停止应用。数据库含样品、聊天历史及操作状态；上传目录将完整重建。")
    confirm = input("\n确认恢复? 这将覆盖当前数据 [y/N]: ").strip().lower()
    if confirm != 'y':
        print("已取消。")
        return

    print("\n正在恢复，请稍候...")
    try:
        backup.restore_backup(plan['timestamp'], full_backup=plan['full_backup'])
        print(f"\n✅ 恢复完成！已还原到: {plan['timestamp']}")
        print("现在可以重新启动应用。")
    except (OSError, ValueError, sqlite3.Error, zipfile.BadZipFile) as e:
        print(f"\n❌ 恢复失败: {e}")
        sys.exit(1)


def cmd_backup_now():
    print("正在执行即时增量备份...")
    try:
        dest = backup.run_backup()
        print(f"✅ 增量备份成功: {dest}")
    except (OSError, ValueError, sqlite3.Error, zipfile.BadZipFile) as e:
        print(f"❌ 增量备份失败: {e}")
        sys.exit(1)


def cmd_full_backup_now():
    print("正在执行完整备份 (zip 压缩)，可能需要几分钟...")
    try:
        dest = backup.run_full_backup()
        size_mb = os.path.getsize(dest) / 1024 / 1024
        print(f"✅ 完整备份成功: {dest} ({size_mb:.1f} MB)")
    except (OSError, ValueError, sqlite3.Error, zipfile.BadZipFile) as e:
        print(f"❌ 完整备份失败: {e}")
        sys.exit(1)


def cmd_full_restore(zip_name: str, timestamp=None):
    cmd_restore(timestamp, full_backup=zip_name)


def main():
    args = sys.argv[1:]

    if not args:
        # 交互式模式
        cmd_list()

        print("操作选项:")
        print("  1) 恢复到时间点（自动完整基线 + 后续增量）")
        print("  2) 指定完整基线及其后增量恢复")
        print("  3) 立即执行增量备份")
        print("  4) 立即执行完整备份")
        print()
        choice = input("请选择操作 (1-4, 直接回车取消): ").strip()

        if choice == '1':
            timestamp = input("输入目标时间戳（回车恢复最新）: ").strip()
            cmd_restore(timestamp or None)

        elif choice == '2':
            full_backups = backup.list_full_backups()
            if not full_backups:
                print("暂无完整备份。")
                return
            fb_choice = input("输入编号或文件名: ").strip()
            if not fb_choice:
                return
            if fb_choice.isdigit():
                idx = int(fb_choice) - 1
                ordered = list(reversed(full_backups))
                if 0 <= idx < len(ordered):
                    zip_name = ordered[idx]
                else:
                    print("编号超出范围。")
                    return
            else:
                zip_name = fb_choice
            cmd_full_restore(zip_name)

        elif choice == '3':
            cmd_backup_now()

        elif choice == '4':
            cmd_full_backup_now()

        else:
            if choice:
                print("无效选择。")

    elif args[0] == "restore":
        cmd_restore(args[1] if len(args) > 1 else None)

    elif args[0] == "list":
        cmd_list()

    elif args[0] == "backup":
        cmd_backup_now()

    elif args[0] == "full-backup":
        cmd_full_backup_now()

    elif args[0] == "full-restore":
        if len(args) < 2:
            print("用法: python restore_backup.py full-restore <zip文件名> [目标时间戳]")
            print("例如: python restore_backup.py full-restore full_2026-03-08_22-00-00.zip")
            sys.exit(1)
        cmd_full_restore(args[1], args[2] if len(args) > 2 else None)

    elif args[0] in ("--help", "-h"):
        print(__doc__)

    else:
        cmd_restore(args[0])


if __name__ == "__main__":
    main()
