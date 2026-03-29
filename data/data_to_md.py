import pandas as pd
from tabulate import tabulate
#本文件将企业提供的数据转换成Markdown文件
# Excel文件路径
file_path = "jobs-data.xls"

# 读取Excel
df = pd.read_excel(file_path)

# 数据清洗

# 删除空行
df = df.dropna(how="all")

# 删除重复数据
df = df.drop_duplicates()

# 去除字符串空格
df = df.apply(lambda col: col.map(lambda x: x.strip() if isinstance(x, str) else x))

# 选择需要字段
columns_needed = [
    "岗位名称","地址","薪资范围","公司名称","所属行业","公司规模", "公司类型","岗位编码",	"岗位详情",	"更新日期",	"公司详情",
"岗位来源地址"
]
df = df[columns_needed]

# 转换为Markdown
markdown_table = tabulate(
    df,
    headers="keys",
    tablefmt="github",
    showindex=False
)

# 保存Markdown文件
with open("jobs-data.md", "w", encoding="utf-8") as f:
    f.write(markdown_table)

print("转换完成，已生成 jobs-data.md")