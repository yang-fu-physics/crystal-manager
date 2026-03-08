# -*- coding: utf-8 -*-
"""
restore_backup.py — 交互式备份恢复命令行工具

使用方法:
  python restore_backup.py                # 列出所有备份并交互式选择
  python restore_backup.py list           # 仅列出备份
  python restore_backup.py <timestamp>    # 直接恢复到指定时间点
  python restore_backup.py backup         # 立即执行一次备份

示例:
  python restore_backup.py 2026-03-08_22-00-00
"""

import sys
import os

# 切换到脚本目录，使 config 可以被正确导入
os.chdir(os.path.dirname(os.path.abspath(__file__)))

import backup
import config


def cmd_list():
    backups = backup.list_backups()
    if not backups:
        print("暂无备份。")
        return
    print(f"共 {len(backups)} 个备份（最多保留 {config.BACKUP_KEEP_COUNT} 个）:\n")
    for i, ts in enumerate(reversed(backups), 1):
        info_path = os.path.join(config.BACKUP_FOLDER, ts, "backup_info.json")
        extra = ""
        if os.path.exists(info_path):
            import json
            with open(info_path) as f:
                info = json.load(f)
            db_mb = info.get("db_size_bytes", 0) / 1024 / 1024
            added = info.get("files_added", 0)
            updated = info.get("files_updated", 0)
            extra = f"  DB: {db_mb:.2f} MB  新增文件: {added}  更新文件: {updated}"
        print(f"  [{i:2d}] {ts}{extra}")
    print()


def cmd_restore(timestamp: str):
    print(f"\n⚠️  即将恢复到备份时间点: {timestamp}")
    print(f"   数据库: {config.DATABASE_PATH}")
    print(f"   文件目录: {config.UPLOAD_FOLDER}")
    confirm = input("\n确认恢复? 这将覆盖当前数据 [y/N]: ").strip().lower()
    if confirm != 'y':
        print("已取消。")
        return

    print("\n正在恢复，请稍候...")
    try:
        backup.restore_backup(timestamp)
        print(f"\n✅ 恢复完成！已还原到: {timestamp}")
        print("请重启应用以使更改生效。")
    except Exception as e:
        print(f"\n❌ 恢复失败: {e}")
        sys.exit(1)


def cmd_backup_now():
    print("正在执行即时备份...")
    try:
        dest = backup.run_backup()
        print(f"✅ 备份成功: {dest}")
    except Exception as e:
        print(f"❌ 备份失败: {e}")
        sys.exit(1)


def main():
    args = sys.argv[1:]

    if not args:
        # 交互式模式
        cmd_list()
        backups = backup.list_backups()
        if not backups:
            return
        choice = input("输入编号或时间戳以恢复 (直接回车取消): ").strip()
        if not choice:
            return
        # 支持输入编号 (列表从新到旧，编号从1开始)
        if choice.isdigit():
            idx = int(choice) - 1
            ordered = list(reversed(backups))
            if 0 <= idx < len(ordered):
                timestamp = ordered[idx]
            else:
                print("编号超出范围。")
                return
        else:
            timestamp = choice
        cmd_restore(timestamp)

    elif args[0] == "list":
        cmd_list()

    elif args[0] == "backup":
        cmd_backup_now()

    elif args[0] in ("--help", "-h"):
        print(__doc__)

    else:
        cmd_restore(args[0])


if __name__ == "__main__":
    main()
