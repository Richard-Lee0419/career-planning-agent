import pandas as pd
import sqlite3
import os


def init_database():
    # 1. 路径配置 (注意：因为脚本在 scripts 文件夹里，所以路径要退回上一级)
    # 如果你没建 scripts 文件夹，就把 '../data/jobs-data.xls' 改成 'data/jobs-data.xls'
    xls_path = '../data/jobs-data.xls'
    db_path = '../career_project.db'

    if not os.path.exists(xls_path):
        print(f"❌ 找不到原始数据文件：{xls_path}，请确认路径！")
        return

    print("🚀 正在读取企业原始数据...")
    try:
        # 尝试读取
        df = pd.read_excel(xls_path, engine='xlrd')
    except Exception:
        try:
            df = pd.read_csv(xls_path, encoding='gbk')
        except:
            df = pd.read_csv(xls_path, encoding='utf-8')

    print("🧹 正在进行数据清洗和字段标准化 (适配 TDD 规范)...")

    # 2. 核心改变：字段映射字典 (把中文表头翻译成标准的英文数据库字段)
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
        '公司详情': 'company_details',
        '岗位来源地址': 'source_url'
    }

    # 执行重命名操作
    df = df.rename(columns=column_mapping)

    # 3. 处理空值 (防止后端接口报错)
    # 把所有空着的地方，填上 "暂无"
    df = df.fillna("暂无")

    print("📦 正在生成标准化的 SQLite 数据库...")
    # 4. 存入数据库
    conn = sqlite3.connect(db_path)
    # index=False 意思是不要把 Excel 的 1,2,3,4 行号存进去
    df.to_sql('jobs', conn, if_exists='replace', index=False)
    conn.close()

    print(f"✅ 大功告成！符合开发文档规范的数据库已生成：{os.path.abspath(db_path)}")


if __name__ == "__main__":
    # 执行主函数
    init_database()