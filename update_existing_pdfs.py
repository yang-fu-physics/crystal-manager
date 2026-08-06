import sqlite3
import os
import config

db_path = config.DATABASE_PATH

def update_pdf_status():
    if not os.path.exists(db_path):
        print(f"未找到数据库文件 {db_path}！")
        return
        
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            SELECT DISTINCT sample_id 
            FROM other_files 
            WHERE LOWER(filename) LIKE '%.pdf' OR LOWER(filepath) LIKE '%.pdf'
        """)
        rows = cursor.fetchall()
        
        if not rows:
            print("没有发现任何带有 PDF 附件的样品。")
            conn.close()
            return
            
        updated_count = 0
        for row in rows:
            sample_id = row[0]
            cursor.execute("UPDATE samples SET has_pdf = 1 WHERE id = ?", (sample_id,))
            if cursor.rowcount > 0:
                updated_count += 1
                print(f"已更新样品 {sample_id} -> has_pdf 自动选中")
                
        conn.commit()
        print(f"\n✅ 更新完成！共扫描并更新了 {updated_count} 个带有 PDF 的样品。")
        
    except sqlite3.OperationalError as e:
        print(f"数据库操作错误 (请确认数据库是否已被新版本覆盖): {e}")
    except Exception as e:
        print(f"发生错误: {e}")
    finally:
        conn.close()

if __name__ == '__main__':
    update_pdf_status()
