import sqlite3
import os

# 1. 自动尝试多个可能的路径
possible_paths = [
    os.path.join("data", "career_project.db"),
    "career_project.db",
    "../data/career_project.db"
]

db_path = None
for path in possible_paths:
    if os.path.exists(path):
        db_path = path
        break

if not db_path:
    print("❌ 错误：在所有预设路径下都找不到数据库文件！")
    print(f"当前脚本运行目录是: {os.getcwd()}")
    print("请手动确认你的 .db 文件到底在哪个文件夹里。")
else:
    print(f"🔍 找到数据库文件: {os.path.abspath(db_path)}")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # 2. 先检查都有哪些表
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = [row[0] for row in cursor.fetchall()]
    print(f"📋 数据库中的表有: {tables}")

    target_table = "user_profiles"
    if target_table not in tables:
        print(f"❌ 警告：数据库中不存在 '{target_table}' 表。")
        print("请检查 db_models.py 中的 __tablename__ 是否写错，或者数据库是否为空。")
    else:
        # 3. 补全缺失的列
        new_columns = [
            ("certificates", "TEXT"),
            ("competitiveness_score", "INTEGER DEFAULT 0")
        ]

        for col_name, col_type in new_columns:
            try:
                cursor.execute(f"ALTER TABLE {target_table} ADD COLUMN {col_name} {col_type};")
                print(f"✅ 成功添加字段: {col_name}")
            except sqlite3.OperationalError as e:
                if "duplicate column name" in str(e):
                    print(f"ℹ️ 字段 {col_name} 已存在，跳过。")
                else:
                    print(f"❌ 添加 {col_name} 时出错: {e}")

    conn.commit()
    conn.close()
    print("✨ 修复流程结束。")