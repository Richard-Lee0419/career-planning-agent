# models/user_model.py
from pydantic import BaseModel
from typing import List, Optional
#新增用户画像模型!!
# 继承 Pydantic 的 BaseModel，用于在 FastAPI 中进行请求体的数据校验和 JSON 序列化
# 完全对应 TDD 文档 6.2 节中定义的 UserProfile 实体
class UserProfile(BaseModel):
    education_level: Optional[str] = None  # 学历（如：本科、硕士），默认为空
    major: Optional[str] = None           # 专业（如：软件工程、信息管理），默认为空
    grade: Optional[str] = None           # 年级（如：大三、研一），默认为空
    location: Optional[str] = None         # 期望工作地点（如：北京、上海），默认为空
    target_roles: List[str] = []           # 目标岗位列表（如：['前端工程师', '产品经理']），默认为空列表
    current_skills: List[str] = []         # 当前具备的技能列表（如：['Python', 'Vue']），默认为空列表
    interests: List[str] = []              # 兴趣爱好，默认为空列表