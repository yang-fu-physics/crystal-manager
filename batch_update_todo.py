# -*- coding: utf-8 -*-
"""批量更新所有有烧制结束时间的样品的 To Do 任务"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

import models
import todo_integration

def main():
    models.init_db()
    conn = models.get_db()
    rows = conn.execute(
        "SELECT id, sintering_end, target_product FROM samples WHERE sintering_end IS NOT NULL AND sintering_end != ''"
    ).fetchall()

    print(f"找到 {len(rows)} 个有烧制结束时间的样品")

    for row in rows:
        sample_id = row["id"]
        sintering_end = row["sintering_end"]
        target_product = row["target_product"] or ""
        ok, msg = todo_integration.create_or_update_todo(sample_id, sintering_end, models, target_product)
        print(f"  {sample_id}: {'OK' if ok else 'FAIL'} — {msg}")

if __name__ == "__main__":
    main()
