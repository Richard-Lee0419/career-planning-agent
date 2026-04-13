# models/user_model.py
from pydantic import BaseModel, Field
from typing import List, Optional


# ==========================================
# 用户画像模型 (UserProfile)
# 对标“服务外包大赛”技术指标，包含软硬素质全维度分析
# ==========================================

class UserProfile(BaseModel):
    # --- 基础身份信息 ---
    name: Optional[str] = Field(None, description="用户姓名")
    education_level: Optional[str] = Field(None, description="学历（如：本科、硕士）")
    major: Optional[str] = Field(None, description="专业名称")
    grade: Optional[str] = Field(None, description="当前年级")
    location: Optional[str] = Field(None, description="期望工作/实习地点")

    # --- 核心竞争力指标 (赛题硬性要求) ---
    current_skills: List[str] = Field(default=[], description="已掌握的专业技能列表")
    certificates: List[str] = Field(default=[], description="持有的证书、奖项或荣誉")
    internship_experience: Optional[str] = Field(None, description="实习或项目实践经历简述")

    # --- 软素质维度 (赛题加分项：体现性格特质与工作能力) ---
    # 侧重性格特质、沟通能力与团队协作
    soft_skills: List[str] = Field(
        default=[],
        description="通用素质标签（如：沟通能力强、抗压性好、团队协作能力优秀）"
    )

    # 赛题要求的“创新能力”与“学习能力”评估
    innovation_potential: Optional[str] = Field(
        None,
        description="AI 评估的创新意识与自主学习潜力评价"
    )

    # --- 职业目标与量化评分 ---
    target_roles: List[str] = Field(default=[], description="目标岗位意向")
    interests: List[str] = Field(default=[], description="个人兴趣与职业倾向")

    # 赛题要求的“竞争力评分”，由 AI 根据简历背景自动算出
    competitiveness_score: int = Field(
        default=0,
        ge=0,
        le=100,
        description="综合竞争力评分 (0-100)"
    )

    class Config:
        # 允许代码中使用驼峰命名或增加示例数据
        json_schema_extra = {
            "example": {
                "name": "张同学",
                "education_level": "本科",
                "major": "软件工程",
                "current_skills": ["Python", "FastAPI", "SQL"],
                "soft_skills": ["沟通协调", "快速学习"],
                "competitiveness_score": 85
            }
        }