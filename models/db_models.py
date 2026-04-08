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

    education_level = Column(String)
    major = Column(String)
    grade = Column(String)
    location = Column(String)
    target_roles = Column(Text)  # 列表转为 JSON 字符串存储
    current_skills = Column(Text)  # 列表转为 JSON 字符串存储
    interests = Column(Text)  # 列表转为 JSON 字符串存储

    user = relationship("DBUser", back_populates="profiles")


# 3. 学习路径表
class DBRoadmap(Base):
    __tablename__ = "roadmaps"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    target_role = Column(String, nullable=False)
    overall_timeline = Column(String)
    roadmap_detail = Column(Text, nullable=False)  # 复杂的 JSON 数组转为字符串存储

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

