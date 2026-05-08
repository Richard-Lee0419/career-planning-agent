# models/job_model.py
from sqlalchemy import Column, Integer, String, Text
from core.database import Base
#建立数据模型
class Job(Base):
    __tablename__ = "jobs"  # 这里必须和你 SQLite 数据库里的表名完全一致

    # 定义表的字段（请根据你之前清洗的 Excel 字段进行调整）
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    title = Column(String, index=True, comment="岗位名称")
    company = Column(String, index=True, comment="公司名称")
    salary = Column(String, comment="薪资范围")
    location = Column(String, comment="工作地点")
    description = Column(Text, comment="岗位职责与要求")
    # 注意：如果你的数据库里有其他字段，比如 requirements(要求), tags(标签)，请在这里继续添加