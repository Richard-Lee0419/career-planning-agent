# models/db_models.py
from sqlalchemy import Column, Integer, String, Text, ForeignKey
from sqlalchemy.orm import relationship
from core.database import Base




# 1. 用户表
class DBUser(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)  # 存加密后的密码
    chats = relationship("DBChatMessage", back_populates="user")
    # 关联关系
    profiles = relationship("DBUserProfile", back_populates="user")
    roadmaps = relationship("DBRoadmap", back_populates="user")
    interviews = relationship("DBInterview", back_populates="user")


# 2. 用户画像表
class DBUserProfile(Base):
    __tablename__ = "user_profiles"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    # --- 基础画像信息 ---
    name = Column(String, nullable=True)  # 刚才报错缺失的字段 1
    education_level = Column(String)
    major = Column(String)
    grade = Column(String)
    location = Column(String)

    # --- 核心竞争力与经历 ---
    target_roles = Column(Text)  # 存储 JSON 字符串
    current_skills = Column(Text)  # 存储 JSON 字符串
    interests = Column(Text)  # 存储 JSON 字符串
    certificates = Column(Text, nullable=True)  # 存储 JSON 字符串

    # --- 关键：补齐之前报错缺失的字段 ---
    internship_experience = Column(Text, nullable=True)  # 刚才报错缺失的字段 2
    soft_skills = Column(Text, nullable=True)  # 对应 user_model 中的软素质标签

    # --- 赛题评分项 ---
    competitiveness_score = Column(Integer, default=0)

    # 关联关系
    user = relationship("DBUser", back_populates="profiles")


# 3. 学习路径表
class DBRoadmap(Base):
    __tablename__ = "roadmaps"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    role_name = Column(String, nullable=True)
    roadmap_json = Column(Text)  # 存储路线图的 JSON 数据
    user = relationship("DBUser", back_populates="roadmaps")


# 4. 面试记录表
class DBInterview(Base):
    __tablename__ = "interviews"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    target_role = Column(String, nullable=False)
    question = Column(Text, nullable=False)
    user_answer = Column(Text)
    score = Column(Integer)
    evaluation = Column(Text)
    improvement_suggestion = Column(Text)
    reference_answer = Column(Text)

    user = relationship("DBUser", back_populates="interviews")
# models/db_models.py 补充部分
class DBChatMessage(Base):
    __tablename__ = "chat_messages"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    session_id = Column(String, index=True)
    role = Column(String)  # "user" 或 "assistant"
    content = Column(Text)
    timestamp = Column(String) # 可以记录时间

    user = relationship("DBUser", back_populates="chats")

# 5. 岗位标准画像表 (Node)
class DBJobStandardProfile(Base):
    __tablename__ = "job_standard_profiles"

    id = Column(Integer, primary_key=True, index=True)
    role_name = Column(String, unique=True, index=True) # 岗位名称 (如: Java后端开发)
    core_skills = Column(Text)       # 核心技能 (JSON字符串)
    soft_skills = Column(Text)       # 软素质要求 (JSON字符串)
    certifications = Column(Text)    # 常见证书要求 (JSON字符串)
    description = Column(Text)       # 岗位描述

# 6. 岗位关系图谱表 (Edge)
class DBJobRelation(Base):
    __tablename__ = "job_relations"

    id = Column(Integer, primary_key=True, index=True)
    source_role = Column(String, index=True) # 起始岗位
    target_role = Column(String, index=True) # 目标岗位
    relation_type = Column(String)           # 关系类型："promotion" (晋升) 或 "transfer" (平调换岗)
    weight = Column(Integer)                 # 关联度/重合度 (0-100)