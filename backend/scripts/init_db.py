import pandas as pd
import sqlite3
import os


def init_database():
    # ==========================================
    # 1. 路径修正 (确保与 main.py 所在的 data 目录对齐)
    # ==========================================

    xls_path = 'data/jobs-data.xls'
    db_path = 'data/career_project.db'

    if not os.path.exists('data'):
        os.makedirs('data')

    if not os.path.exists(xls_path):
        print(f"❌ 找不到原始数据文件：{xls_path}，请确认原始 Excel 是否放在了 data 目录下")
        return

    print("🚀 正在读取企业原始数据...")
    try:
        # 兼容处理
        if xls_path.endswith('.xls'):
            df = pd.read_excel(xls_path, engine='xlrd')
        elif xls_path.endswith('.xlsx'):
            df = pd.read_excel(xls_path)
        else:
            df = pd.read_csv(xls_path, encoding='gbk')
    except Exception as e:
        print(f"❌ 读取文件失败: {e}")
        return

    print("🧹 正在进行数据清洗和字段标准化 (保留全部业务字段)...")

    # ==========================================
    # 2. 完整字段映射 (基于你原始逻辑，不做任何阉割)
    # ==========================================
    column_mapping = {
        '岗位名称': 'title',
        '地址': 'location',
        '薪资范围': 'salary_range',
        '公司名称': 'company',
        '所属行业': 'industry',
        '公司规模': 'company_size',
        '公司类型': 'company_type',
        '岗位编码': 'job_code',
        '岗位详情': 'description',
        '更新日期': 'update_date',
        '公司详情': 'company_detail'
    }

    # 仅映射 Excel 中确实存在的列
    df.rename(columns=column_mapping, inplace=True)

    # 保留所有已映射的英文列名
    final_columns = [v for k, v in column_mapping.items() if v in df.columns]


    # 如果你的 main.py 查询需要 'requirement' 字段，请确保这里也有
    if '岗位要求' in df.columns and 'requirement' not in df.columns:
        df.rename(columns={'岗位要求': 'requirement'}, inplace=True)
        final_columns.append('requirement')

    df = df[final_columns]

    print(f"📦 正在导入 {len(df)} 条数据到数据库...")

    # ==========================================
    # 3. 导入数据库 (修正目标表名为 jobs)
    # ==========================================
    conn = sqlite3.connect(db_path)

    # 这里必须存为 'jobs' 表，因为 main.py 里的 SQL 语句是 SELECT * FROM jobs
    df.to_sql('jobs', conn, if_exists='replace', index=False)

    conn.close()
    print(f"✅ 初始化完成！")
    print(f"📍 数据库位置: {os.path.abspath(db_path)}")
    print(f"📊 导入表名: jobs")


if __name__ == "__main__":
    init_database()