import pandas as pd
import psycopg2
import re
from datetime import datetime
#本文件将企业提供的数据导入到本地的数据库中(暂时无用)
# ==============================
# 1 读取Excel
# ==============================

file_path = "jobs-data.xls"

df = pd.read_excel(file_path,engine='xlrd')

print("Excel读取成功")

# ==============================
# 2 数据清洗
# ==============================

# 删除空行
df = df.dropna(how="all")

# 删除重复
df = df.drop_duplicates()

# 去除字符串空格
for col in df.columns:
    if df[col].dtype == "object":
        df[col] = df[col].str.strip()

# 处理日期格式：将"5 月 19 日"或"2025 年 07 月 28 日"转换为"2026-05-19"
def convert_chinese_date(date_str):
    """将中文日期格式转换为标准格式"""
    
    if pd.isna(date_str) or not date_str:
        return None
    
    date_str = str(date_str).strip()
    
    # 匹配"X 年 Y 月 Z 日"格式（允许有空格或无空格）
    match_year = re.match(r'(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日', date_str)
    if match_year:
        year = int(match_year.group(1))
        month = int(match_year.group(2))
        day = int(match_year.group(3))
        return f"{year}-{month:02d}-{day:02d}"
    
    # 匹配"X 月 Y 日"格式（允许有空格或无空格）
    match = re.match(r'(\d{1,2})\s*月\s*(\d{1,2})\s*日', date_str)
    if match:
        month = int(match.group(1))
        day = int(match.group(2))
        year = datetime.now().year  # 使用当前年份
        return f"{year}-{month:02d}-{day:02d}"
    
    # 尝试匹配其他常见日期格式
    # 例如：2026-05-19, 2026/05/19, 2026-05-19 00:28:20 等
    try:
        # 如果包含时间部分，只提取日期
        if ' ' in date_str:
            # 处理 "2025-07-27 00:28:20" 格式
            dt = datetime.strptime(date_str, '%Y-%m-%d %H:%M:%S')
            return dt.strftime('%Y-%m-%d')
        else:
            # 处理 "2025-07-27" 格式
            dt = datetime.strptime(date_str, '%Y-%m-%d')
            return dt.strftime('%Y-%m-%d')
    except ValueError:
        pass
    
    # 如果无法解析，直接返回日期部分（如果是 datetime 对象）
    if isinstance(date_str, pd.Timestamp):
        return date_str.strftime('%Y-%m-%d')
    
    # 最后手段：如果看起来像日期，尝试提取前 10 个字符
    if len(date_str) >= 10 and date_str[4] == '-' and date_str[7] == '-':
        return date_str[:10]  # 返回 "YYYY-MM-DD" 部分
    
    # 如果无法解析，返回原始值
    print(f"警告：无法解析的日期格式：'{date_str}'")
    return date_str

if '更新日期' in df.columns:
    df['更新日期'] = df['更新日期'].apply(convert_chinese_date)
    print("更新日期列已转换")
    # 显示前几个转换后的日期用于验证
    print("示例日期转换结果:", df['更新日期'].head(3).tolist())

print("数据清洗完成")

# ==============================
# 3 连接数据库
# ==============================

conn = psycopg2.connect(
    host="localhost",
    database="My_Project_jobs",
    user="postgres",
    password="314159",
    port="5432"
)

cursor = conn.cursor()

print("数据库连接成功")

# ==============================
# 4 导入公司数据
# ==============================

company_map = {}

for index, row in df.iterrows():

    company_name = row["公司名称"]
    industry = row["所属行业"]
    company_size = row["公司规模"]
    company_type = row["公司类型"]
    company_description = row["公司详情"]

    # 公司去重
    if company_name not in company_map:

        cursor.execute(
            """
            INSERT INTO companies
            (company_name, industry, company_size, company_type, company_description)
            VALUES (%s,%s,%s,%s,%s)
            RETURNING id
            """,
            (company_name, industry, company_size, company_type, company_description)
        )

        company_id = cursor.fetchone()[0]

        company_map[company_name] = company_id

conn.commit()

print("公司数据导入完成")

# ==============================
# 5 导入岗位数据
# ==============================

for index, row in df.iterrows():

    job_code = row["岗位编码"]
    job_name = row["岗位名称"]
    location = row["地址"]
    salary = row["薪资范围"]
    job_desc = row["岗位详情"]
    update_date = row["更新日期"]
    source_url = row["岗位来源地址"]

    company_id = company_map[row["公司名称"]]



conn.commit()

print("岗位数据导入完成")

# ==============================
# 6 关闭数据库
# ==============================

cursor.close()
conn.close()

print("全部数据导入完成")