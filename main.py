import sqlite3
import os
import json
import uvicorn
import uuid
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field  # 💡 引入了 Field 用于更精准的结构化描述
from dotenv import load_dotenv
from zhipuai import ZhipuAI
from typing import Optional, List
from fastapi import Query
from models.user_model import UserProfile
from pydantic import Field
from fastapi.security import OAuth2PasswordRequestForm
from core.database import engine, get_db
from models.db_models import (
    Base,
    DBUser,
    DBUserProfile,
    DBChatMessage,
    DBRoadmap,
    DBInterview
)
from core.security import get_password_hash, verify_password, create_access_token, get_current_user, timedelta, ACCESS_TOKEN_EXPIRE_MINUTES
from sqlalchemy.orm import Session
from fastapi import Depends, HTTPException, status

# ==========================================
# 1. 基础配置与大模型初始化
# ==========================================
load_dotenv()
api_key = os.getenv("ZHIPUAI_API_KEY")
if not api_key:
    raise ValueError("❌ 找不到 API Key，请检查 .env 文件！")

client = ZhipuAI(api_key=api_key)


app = FastAPI(title="职业规划 Agent 后端 完整版")

app.add_middleware(
    CORSMiddleware,
# 开发阶段可以填 ["*"] 允许所有域名，部署上线时建议改成具体的前端地址（如 ["http://localhost:5173"]）
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- 定义带 Session 的请求体 ---
class ChatRequest(BaseModel):
    session_id: Optional[str] = None  # 前端传来的会话 ID，用来识别是谁在聊天
    message: str  # 用户发来的对话内容
    profile: Optional[UserProfile] = None  # 新增：允许前端在此处顺便传入用户的画像/简历数据


# --- 建立简单的内存数据库来存储聊天记录 ---
session_memory = {}

# 系统预设 Prompt（人设）
SYSTEM_PROMPT = "你是一个专业的职业规划专家。你有能力调用工具去数据库查询真实的岗位数据。请结合查询到的数据，给出专业、落地的建议。"

# 【重要】每次启动服务时，自动创建所有数据库表
Base.metadata.create_all(bind=engine)


# ==========================================
# 🔐 认证系统：注册与登录
# ==========================================
class UserRegister(BaseModel):
    username: str
    password: str


@app.post("/api/auth/register", summary="用户注册")
def register(user: UserRegister, db: Session = Depends(get_db)):
    # 检查用户名是否已存在
    db_user = db.query(DBUser).filter(DBUser.username == user.username).first()
    if db_user:
        raise HTTPException(status_code=400, detail="该用户名已被注册")

    # 密码加密并入库
    hashed_pwd = get_password_hash(user.password)
    new_user = DBUser(username=user.username, hashed_password=hashed_pwd)
    db.add(new_user)
    db.commit()
    return {"status": "success", "message": "注册成功"}


@app.post("/api/auth/login", summary="用户登录")
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    # 验证账号
    user = db.query(DBUser).filter(DBUser.username == form_data.username).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=400, detail="用户名或密码错误")

    # 签发 Token
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}


# ==========================================
# 2. 数据库查询工具（供 AI 调用 & 供 API 使用）
# ==========================================
def search_jobs_from_db(keyword: str):
    print(f"🔧 [系统日志] 正在执行数据库查询，关键词: {keyword}")
    conn = sqlite3.connect("data/career_project.db")
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    query = "SELECT title, location, salary_range, company FROM jobs WHERE title LIKE ? OR description LIKE ? LIMIT 5"
    cursor.execute(query, (f'%{keyword}%', f'%{keyword}%'))
    rows = cursor.fetchall()
    conn.close()

    result = [dict(row) for row in rows]
    print(f"🔧 [系统日志] 数据库返回了 {len(result)} 条数据")
    return result


# ==========================================
# 3. 工具说明书（供大模型识别）
# ==========================================
tools_description = [
    {
        "type": "function",
        "function": {
            "name": "search_jobs",
            "description": "当用户询问特定岗位、想找工作、或询问薪资时，调用此工具从数据库搜索真实的岗位信息。",
            "parameters": {
                "type": "object",
                "properties": {
                    "keyword": {
                        "type": "string",
                        "description": "提取用户想找的岗位关键词，例如：前端，Java，销售，产品经理"
                    }
                },
                "required": ["keyword"]
            }
        }
    }
]


# ==========================================
# 4. 供前端直接调用的岗位列表接口
# ==========================================
@app.get("/api/jobs", summary="获取所有岗位列表（纯数据接口）")
def get_all_jobs(skip: int = 0, limit: int = 20):
    print("🌐 [系统日志] 收到前端的岗位列表请求")
    conn = sqlite3.connect("data/career_project.db")
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    query = "SELECT title, location, salary_range, company FROM jobs LIMIT ? OFFSET ?"
    cursor.execute(query, (limit, skip))
    rows = cursor.fetchall()
    conn.close()

    result = [dict(row) for row in rows]
    return {
        "status": "success",
        "data": result,
        "total_returned": len(result)
    }


# ==========================================
# 5. 核心：支持记忆与规范输出的 AI 聊天接口
# ==========================================
@app.post("/api/chat")
async def chat_endpoint(request: ChatRequest):
    user_input = request.message
    session_id = request.session_id if request.session_id else f"sess_{uuid.uuid4().hex[:8]}"

    if session_id not in session_memory:
        session_memory[session_id] = [
            {"role": "system", "content": SYSTEM_PROMPT}
        ]

    session_memory[session_id].append({"role": "user", "content": user_input})
    print(f"🧠 [系统日志] 收到消息。当前会话 {session_id} 的记忆长度：{len(session_memory[session_id])} 条")

    response = client.chat.completions.create(
        model="glm-4-flash",
        messages=session_memory[session_id],
        tools=tools_description,
    )

    ai_message = response.choices[0].message
    blocks = []  # 准备发给前端的积木块

    if ai_message.tool_calls:
        print("🤖 [系统日志] 大模型决定调用工具！")
        tool_call = ai_message.tool_calls[0]
        args = json.loads(tool_call.function.arguments)
        search_keyword = args.get("keyword")

        job_data = search_jobs_from_db(search_keyword)

        session_memory[session_id].append(ai_message.model_dump())
        session_memory[session_id].append({
            "role": "tool",
            "content": json.dumps(job_data, ensure_ascii=False),
            "tool_call_id": tool_call.id
        })

        second_response = client.chat.completions.create(
            model="glm-4-flash",
            messages=session_memory[session_id]
        )
        final_reply = second_response.choices[0].message.content

        session_memory[session_id].append({"role": "assistant", "content": final_reply})

        blocks.append({"type": "text", "content": final_reply})
        if job_data:
            blocks.append({"type": "career_recommendations", "items": job_data})

    else:
        print("🤖 [系统日志] 直接回答。")
        final_reply = ai_message.content
        session_memory[session_id].append({"role": "assistant", "content": final_reply})
        blocks.append({"type": "text", "content": final_reply})

    return {
        "sessionId": session_id,
        "role": "assistant",
        "blocks": blocks
    }


# ==========================================
# 6. 高级多条件岗位搜索接口
# ==========================================
@app.get("/api/jobs/search", summary="高级岗位搜索接口")
def search_jobs_api(
        keyword: Optional[str] = Query(None, description="搜索关键词，如：Java, 前端"),
        location: Optional[str] = Query(None, description="工作地点，如：北京, 上海"),
        limit: int = Query(20, description="返回的最大条数")
):
    print(f"🔍 [系统日志] 收到高级搜索请求: keyword={keyword}, location={location}")
    conn = sqlite3.connect("data/career_project.db")
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    query = "SELECT title, location, salary_range, company FROM jobs WHERE 1=1"
    params = []

    if keyword:
        query += " AND (title LIKE ? OR description LIKE ?)"
        params.extend([f"%{keyword}%", f"%{keyword}%"])

    if location:
        query += " AND location LIKE ?"
        params.append(f"%{location}%")

    query += " LIMIT ?"
    params.append(limit)

    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()

    result = [dict(row) for row in rows]
    return {
        "status": "success",
        "data": result,
        "total_returned": len(result)
    }


# ==========================================
# 7. 岗位数据分析与统计接口
# ==========================================
@app.get("/api/jobs/stats", summary="岗位数据统计接口 (供图表渲染)")
def get_job_stats():
    print("📊 [系统日志] 收到岗位数据统计请求")
    conn = sqlite3.connect("data/career_project.db")
    cursor = conn.cursor()

    cursor.execute("""
                   SELECT location, COUNT(*) as job_count
                   FROM jobs
                   WHERE location IS NOT NULL
                     AND location != ''
                   GROUP BY location
                   ORDER BY job_count DESC
                       LIMIT 5
                   """)
    rows = cursor.fetchall()
    conn.close()

    stats_data = [{"name": row[0], "value": row[1]} for row in rows]

    return {
        "status": "success",
        "chart_type": "pie",
        "data": stats_data
    }


# ==========================================
# 8. 智能简历/画像录入接口 (Phase 2)
# ==========================================
class ResumeExtractRequest(BaseModel):
    session_id: Optional[str] = None
    resume_text: str


class ProfileIntakeResponse(BaseModel):
    profile: UserProfile
    is_complete: bool
    missing_fields: List[str]
    next_questions: List[str] = []


@app.post("/api/user/profile/extract", response_model=ProfileIntakeResponse, summary="从简历/介绍中提取画像并持久化")
async def extract_profile_endpoint(
        request: ResumeExtractRequest,
        db: Session = Depends(get_db),  # 🔒 注入数据库会话
        current_user: DBUser = Depends(get_current_user)  # 🔒 获取当前登录用户
):
    """
    解析用户输入的简历内容，提取画像，并自动更新数据库中的用户信息。
    """
    print(f"🔬 [系统日志] 正在为用户 {current_user.username} 解析简历内容...")

    system_instruction = (
        "你是一个专业的 HR 助手。请从用户的简历或自我介绍中提取结构化信息。\n"
        "要求：严格返回 JSON，不得包含 ```json 标签。\n"
        "结构：{\"education_level\": \"...\", \"major\": \"...\", \"grade\": \"...\", \"location\": \"...\", "
        "\"target_roles\": [\"...\"], \"current_skills\": [\"...\"], \"interests\": [\"...\"]}"
    )

    try:
        # 1. 调用大模型解析
        response = client.chat.completions.create(
            model="glm-4-flash",
            messages=[
                {"role": "system", "content": system_instruction},
                {"role": "user", "content": request.resume_text}
            ],
            temperature=0.1
        )
        ai_content = response.choices[0].message.content.strip()

        # 2. 清洗并解析 JSON
        cleaned_json = ai_content.replace("```json", "").replace("```", "").strip()
        profile_dict = json.loads(cleaned_json)

        # 3. 转化为 Pydantic 模型进行校验
        # 注意：这里假设你原有的 UserProfile 模型能匹配 profile_dict 的结构
        profile_obj = UserProfile(**profile_dict)

        # ============================================================
        # 🌟 核心：持久化逻辑（新增/更新）
        # ============================================================
        # 检查该用户是否已经有了画像记录
        db_profile = db.query(DBUserProfile).filter(DBUserProfile.user_id == current_user.id).first()

        # 准备要存入数据库的数据（将列表序列化为 JSON 字符串）
        save_data = {
            "education_level": profile_obj.education_level,
            "major": profile_obj.major,
            "grade": profile_obj.grade,
            "location": profile_obj.location,
            "target_roles": json.dumps(profile_obj.target_roles, ensure_ascii=False),
            "current_skills": json.dumps(profile_obj.current_skills, ensure_ascii=False),
            "interests": json.dumps(profile_obj.interests, ensure_ascii=False)
        }

        if db_profile:
            # 如果已存在，则更新字段
            print(f"📝 [系统日志] 更新用户 {current_user.username} 的现有画像")
            for key, value in save_data.items():
                setattr(db_profile, key, value)
        else:
            # 如果不存在，则新建记录
            print(f"🆕 [系统日志] 为用户 {current_user.username} 创建新画像")
            db_profile = DBUserProfile(user_id=current_user.id, **save_data)
            db.add(db_profile)

        db.commit()
        db.refresh(db_profile)
        # ============================================================

        # 4. 构造返回结果
        # 检查信息是否完整（这里保持你原有的逻辑，比如判断 major 是否为 "未知"）
        is_complete = profile_obj.major != "未知" and len(profile_obj.current_skills) > 0

        return ProfileIntakeResponse(
            profile=profile_obj,
            is_complete=is_complete,
            missing_fields=[] if is_complete else ["请补充更详细的技能或专业信息"],
            next_questions = []
        )

    except Exception as e:
        db.rollback()
        print(f"❌ [系统日志] 简历提取失败: {e}")
        raise HTTPException(status_code=500, detail=f"解析失败: {str(e)}")

# ==========================================
# 🚀 9. [全新增] 职业匹配推荐接口 (Phase 3)
# 对应 TDD 10.2 节的要求：career_match_skill
# ==========================================

class CareerRecommendationItem(BaseModel):
    role_name: str = Field(..., description="推荐的职业/岗位名称")
    match_reason: str = Field(..., description="结合用户画像得出的推荐理由")
    confidence_score: int = Field(..., ge=0, le=100, description="匹配得分，0到100之间")


class CareerMatchResponse(BaseModel):
    recommendations: List[CareerRecommendationItem]


@app.post("/api/agent/chat", summary="职业规划 AI 多轮对话（持久化版）")
async def career_chat(
        request: ChatRequest,
        db: Session = Depends(get_db),
        current_user: DBUser = Depends(get_current_user)
):
    """
    通过 user_id 和 session_id 维护用户的多轮对话记忆，并实时保存。
    """
    session_id = request.session_id or str(uuid.uuid4())

    # 1. 从数据库加载历史记录（取代之前的全局 sessions 字典）
    history = db.query(DBChatMessage).filter(
        DBChatMessage.user_id == current_user.id,
        DBChatMessage.session_id == session_id
    ).order_by(DBChatMessage.id.asc()).all()

    # 构造给大模型的消息格式
    messages = [{"role": "system", "content": "你是一个专业的职业规划专家..."}]
    for h in history:
        messages.append({"role": h.role, "content": h.content})

    # 加入当前用户的提问
    messages.append({"role": "user", "content": request.message})

    try:
        # 2. 调用大模型
        response = client.chat.completions.create(
            model="glm-4-flash",
            messages=messages
        )
        ai_reply = response.choices[0].message.content

        # 3. 🌟 持久化：将本次对话存入数据库
        user_msg = DBChatMessage(user_id=current_user.id, session_id=session_id, role="user", content=request.message)
        ai_msg = DBChatMessage(user_id=current_user.id, session_id=session_id, role="assistant", content=ai_reply)

        db.add(user_msg)
        db.add(ai_msg)
        db.commit()

        return {"session_id": session_id, "reply": ai_reply}

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"对话失败: {e}")
# ==========================================
# 🚀 10. [全新增] 岗位差距分析接口 (Phase 4)
# 对应 TDD 的 Gap Analysis 功能
# ==========================================

class GapAnalysisRequest(BaseModel):
    profile: UserProfile
    target_role: str

class GapItem(BaseModel):
    dimension: str
    current_status: str
    required_status: str
    gap_degree: str  # 无差距/小差距/大差距
    suggestion: str

class GapAnalysisResponse(BaseModel):
    target_role: str
    overall_match_score: int
    core_strengths: List[str]
    gaps: List[GapItem]
    immediate_next_steps: List[str]


@app.post("/api/agent/gap-analysis", response_model=GapAnalysisResponse, summary="能力差距分析（自动调取档案）")
async def gap_analysis_endpoint(
        target_role: str = Query(..., description="目标岗位"),
        db: Session = Depends(get_db),
        current_user: DBUser = Depends(get_current_user)
):
    # 1. 从数据库获取该用户的画像
    db_profile = db.query(DBUserProfile).filter(DBUserProfile.user_id == current_user.id).first()
    if not db_profile:
        raise HTTPException(status_code=404, detail="请先通过 /api/user/profile/extract 接口上传简历生成画像")

    user_info = {
        "education": db_profile.education_level,
        "major": db_profile.major,
        "skills": db_profile.current_skills,
        "target_roles": db_profile.target_roles
    }

    # 【关键修改】：强化系统指令，确保字段名称与 GapAnalysisResponse 模型完全一致
    system_instruction = (
        "你是一个专业的职业规划与岗位匹配专家。\n"
        "请对比用户画像与目标岗位，给出一份结构化的 JSON 分析报告。\n"
        "要求：必须严格返回 JSON，不得包含 ```json 标签，不得有任何多余文字。\n"
        "JSON 结构必须包含以下字段：\n"
        "{\n"
        "  \"target_role\": \"岗位名称\",\n"
        "  \"overall_match_score\": 85,\n"
        "  \"core_strengths\": [\"优势1\", \"优势2\"],\n"
        "  \"gaps\": [\n"
        "    {\"dimension\": \"技能\", \"current_status\": \"掌握Python\", \"required_status\": \"精通C++\", \"gap_degree\": \"大差距\", \"suggestion\": \"学习C++\"}\n"
        "  ],\n"
        "  \"immediate_next_steps\": [\"具体行动1\"]\n"
        "}"
    )

    user_prompt = f"目标岗位：{target_role}\n用户现状：{json.dumps(user_info, ensure_ascii=False)}"

    try:
        response = client.chat.completions.create(
            model="glm-4-flash",
            messages=[
                {"role": "system", "content": system_instruction},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.2
        )

        ai_content = response.choices[0].message.content.strip()

        # 强化清洗逻辑：移除所有可能的 Markdown 干扰
        cleaned_json = ai_content.replace("```json", "").replace("```", "").strip()

        # 尝试解析
        result_dict = json.loads(cleaned_json)

        # 强制补充 target_role 以防 AI 漏掉
        if "target_role" not in result_dict:
            result_dict["target_role"] = target_role

        return GapAnalysisResponse(**result_dict)

    except json.JSONDecodeError as e:
        print(f"❌ JSON 解析失败，AI 返回内容为: {ai_content}")
        raise HTTPException(status_code=500, detail="AI 返回了非法的 JSON 格式，请重试")
    except Exception as e:
        print(f"❌ 能力差距分析发生崩溃: {str(e)}")
        raise HTTPException(status_code=500, detail=f"分析失败: {str(e)}")

# ==========================================
# 🚀 11.Phase 5: 学习路径规划接口 (Actionable Roadmap)
# ==========================================
# 1. 定义数据模型
class RoadmapPhase(BaseModel):
    time_period: str = Field(..., description="时间段，例如：第1-2周")
    focus: str = Field(..., description="本阶段学习焦点")
    action_items: List[str] = Field(..., description="具体行动项")
    learning_resources: List[str] = Field(..., description="推荐资源")


class LearningPathResponse(BaseModel):
    target_role: str
    overall_timeline: str
    roadmap: List[RoadmapPhase]


class LearningPathRequest(BaseModel):
    profile: UserProfile
    target_role: str
    gaps: List[GapItem]  # 这里引用你 Phase 4 定义的 GapItem


@app.post("/api/agent/learning-path", response_model=LearningPathResponse)
async def learning_path_endpoint(
        request: LearningPathRequest,
        db: Session = Depends(get_db),  # 🔒 注入数据库会话
        current_user: DBUser = Depends(get_current_user)  # 🔒 注入当前登录用户
):
    """
    基于用户画像和 Phase 4 的差距分析结果，生成详细的提升计划，并持久化到数据库。
    """
    print(f"🔬 [系统日志] 正在为用户 {current_user.username} 的 {request.target_role} 目标生成学习路径...")

    system_instruction = (
        "你是一个职业规划导师。请根据用户的现状和岗位差距，提供一份分阶段的学习路线图。\n"
        "要求：严格返回 JSON 格式，不得包含 ```json 标签或任何多余文字。\n"
        "必须严格符合以下 JSON 结构：\n"
        "{\n"
        "  \"target_role\": \"岗位名称\",\n"
        "  \"overall_timeline\": \"总耗时预估\",\n"
        "  \"roadmap\": [\n"
        "    {\"time_period\": \"...\", \"focus\": \"...\", \"action_items\": [\"...\"], \"learning_resources\": [\"...\"]}\n"
        "  ]\n"
        "}"
    )

    user_prompt = (
        f"目标岗位：{request.target_role}\n"
        f"用户画像：{request.profile.model_dump_json(exclude_none=True)}\n"
        f"存在差距：{json.dumps([g.model_dump() for g in request.gaps], ensure_ascii=False)}"
    )

    try:
        # 1. 调用大模型生成路径
        response = client.chat.completions.create(
            model="glm-4-flash",
            messages=[
                {"role": "system", "content": system_instruction},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.3
        )

        ai_content = response.choices[0].message.content.strip()

        # 2. 鲁棒性清洗 JSON (采用更简洁高效的替换方式)
        cleaned_json = ai_content.replace("```json", "").replace("```", "").strip()

        # 3. 解析为 Python 字典
        extracted_data = json.loads(cleaned_json)

        # 4. 验证并转化为 Pydantic 模型对象 (ai_result)
        ai_result = LearningPathResponse(**extracted_data)

        # ============================================================
        # 🌟 核心：数据库持久化逻辑
        # ============================================================

        # 将 roadmap 列表转化为 JSON 字符串存储到数据库的 Text 字段中
        # [item.model_dump() for item in ai_result.roadmap] 会把每个 RoadmapPhase 对象转回字典
        roadmap_json_str = json.dumps(
            [item.model_dump() for item in ai_result.roadmap],
            ensure_ascii=False
        )

        # 创建数据库记录
        new_path_record = DBRoadmap(
            user_id=current_user.id,  # 关键：绑定当前登录用户
            target_role=ai_result.target_role,
            overall_timeline=ai_result.overall_timeline,
            roadmap_detail=roadmap_json_str  # 存入序列化后的 JSON 字符串
        )

        db.add(new_path_record)  # 添加到事务
        db.commit()  # 提交到数据库
        db.refresh(new_path_record)  # 刷新以同步数据库生成的 ID

        print(f"✅ [系统日志] 学习路径已成功保存到数据库，记录ID: {new_path_record.id}")
        # ============================================================

        # 返回 AI 生成的结果给前端
        return ai_result

    except Exception as e:
        db.rollback()  # 如果存库出错，回滚数据库操作
        print(f"❌ [系统日志] 路径规划或持久化失败: {e}. 原始内容: {ai_content if 'ai_content' in locals() else 'N/A'}")

        # 降级处理：返回一个友好的错误提示结构，确保前端不挂掉
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"路径生成失败: {str(e)}"
        )


# ==========================================
# 🚀 12. [全新增] 模拟面试与打分系统 (Phase 6)
# ==========================================
# --- 新增：面试题目返回模型 ---
class InterviewQuestion(BaseModel):
    id: int
    question: str
    dimension: str  # 考察维度，如：技术深度、项目经验、应变能力

class InterviewQuestionsResponse(BaseModel):
    target_role: str
    questions: List[InterviewQuestion]

# --- 新增：获取面试题目接口 ---
@app.get("/api/interview/questions", response_model=InterviewQuestionsResponse, summary="获取定制化面试题")
async def get_interview_questions(
        target_role: str = Query(..., description="目标岗位"),
        current_user: DBUser = Depends(get_current_user)
):
    # 将逻辑分为“身份设定”和“具体任务”
    system_instruction = "你是一个资深的面试官，擅长根据岗位需求挖掘候选人的技术深度。"

    user_prompt = (
        f"请针对【{target_role}】这个岗位，生成3道高质量的面试题。\n"
        "要求：返回严格的 JSON 格式，包含以下字段：\n"
        "- target_role: 岗位名称\n"
        "- questions: 数组，每个元素包含 id (整数), question (字符串), dimension (考察维度)。\n"
        "注意：直接返回 JSON 字符串，不要包含 ```json 等 Markdown 标签。"
    )

    try:
        response = client.chat.completions.create(
            model="glm-4-flash",
            messages=[
                {"role": "system", "content": system_instruction},
                {"role": "user", "content": user_prompt}  # 添加 user 角色消息
            ],
            temperature=0.7
        )
        ai_content = response.choices[0].message.content.strip()

        # 鲁棒性清洗
        cleaned_json = ai_content.replace("```json", "").replace("```", "").strip()
        result_dict = json.loads(cleaned_json)

        # 补全可能缺失的字段
        if "target_role" not in result_dict:
            result_dict["target_role"] = target_role

        return InterviewQuestionsResponse(**result_dict)

    except Exception as e:
        print(f"❌ 生成题目失败: {e}")
        raise HTTPException(status_code=500, detail=f"生成题目失败: {str(e)}")

class MockInterviewRequest(BaseModel):
    target_role: str = Field(..., description="目标岗位，如：Python后端开发")
    focus_area: str = Field(..., description="本次面试的考察重点，如：数据库优化、或者项目实战")


class MockInterviewQuestion(BaseModel):
    question: str = Field(..., description="面试官提出的具体问题")
    difficulty: str = Field(..., description="难度级别：基础/进阶/困难")
    interview_tips: str = Field(..., description="给用户的隐藏提示或答题思路")

class MockAnswerRequest(BaseModel):
    target_role: str
    question: str = Field(..., description="刚才面试官提的问题")
    user_answer: str = Field(..., description="用户的回答内容")
    focus_area: Optional[str] = "综合能力"  # 👉 添加这一行，设为可选并给个默认值


class MockEvaluation(BaseModel):
    score: int = Field(..., description="回答评分 (0-100的整数)")
    evaluation: str = Field(..., description="资深面试官的详细点评")
    improvement_suggestion: str = Field(..., description="改进建议（指出缺漏点）")
    reference_answer: str = Field(..., description="满分标准参考答案")

@app.post("/api/agent/mock-interview/evaluate", response_model=MockEvaluation, summary="评估面试回答并持久化")
async def evaluate_interview_answer(
        request: MockAnswerRequest,
        db: Session = Depends(get_db),
        current_user: DBUser = Depends(get_current_user)
):
    # 1. 极其严厉的系统指令，强制 AI 锁死返回格式
    system_instruction = (
        "你是一个专业的 AI 面试官。现在请你对用户的面试回答进行【评分和点评】。\n"
        "注意：你必须返回一个且仅一个 JSON 对象，严禁包含任何 Markdown 标签（如 ```json）。\n"
        "JSON 必须严格包含以下字段，不得缺失：\n"
        "1. score: 0-100 的整数分数\n"
        "2. evaluation: 对回答的深度点评\n"
        "3. improvement_suggestion: 具体的改进建议\n"
        "4. reference_answer: 该题目的高分参考答案"
    )

    # 2. 构造 User Prompt，明确区分题目和回答
    user_prompt = (
        f"面试岗位：{request.target_role}\n"
        f"面试题目：{request.question}\n"
        f"候选人回答：{request.user_answer}\n"
        f"考察重点：{request.focus_area if hasattr(request, 'focus_area') else '综合素质'}\n"
        "请基于以上信息给出评分 JSON。"
    )

    try:
        response = client.chat.completions.create(
            model="glm-4-flash",
            messages=[
                {"role": "system", "content": system_instruction},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.1  # 降低随机性，确保格式稳定
        )
        ai_content = response.choices[0].message.content.strip()

        # 3. 强化清洗逻辑
        cleaned_json = ai_content.replace("```json", "").replace("```", "").strip()

        # 4. 解析并进行【字段兜底】
        try:
            result_dict = json.loads(cleaned_json)
        except json.JSONDecodeError:
            # 如果 AI 还是返回了带文字的内容，尝试用正则或简单切分提取（进阶处理）
            raise HTTPException(status_code=500, detail="AI 返回格式解析失败")

        # 核心修复：手动补齐 Pydantic 校验所需的必填字段，防止 500 错误
        result_dict["score"] = result_dict.get("score", 0)
        result_dict["evaluation"] = result_dict.get("evaluation", "无法生成点评")
        result_dict["improvement_suggestion"] = result_dict.get("improvement_suggestion", "无改进建议")
        result_dict["reference_answer"] = result_dict.get("reference_answer", "无参考答案")

        # 5. 持久化到数据库 (DBInterview)
        db_record = DBInterview(
            user_id=current_user.id,
            target_role=request.target_role,
            question=request.question,
            user_answer=request.user_answer,
            score=int(result_dict["score"]),  # 强制转成整数
            evaluation=result_dict["evaluation"],
            improvement_suggestion=result_dict["improvement_suggestion"],
            reference_answer=result_dict["reference_answer"]
        )
        db.add(db_record)
        db.commit()

        # 6. 返回结果
        return result_dict

    except Exception as e:
        print(f"❌ 评估流程失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"评估失败: {str(e)}")


if __name__ == "__main__":

    # host="0.0.0.0" 是关键，它告诉程序监听手机热点分配给你的所有 IP 地址
    # port=8000 是你约定的接口端口
    print("🚀 后端服务正在启动，请确保已连接手机热点...")
    uvicorn.run(app, host="0.0.0.0", port=8000)
