import sqlite3
import os
import json
import re
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
import re  # 确保文件顶部有导入正则表达式模块
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
from models.db_models import DBJobStandardProfile
from pydantic import BaseModel, Field
from typing import List
from fastapi.responses import PlainTextResponse
from fastapi.responses import FileResponse
import shutil
from fastapi import UploadFile, File
from fastapi.staticfiles import StaticFiles
import time
import asyncio
from pathlib import Path
from fastapi import BackgroundTasks
import base64
import pdfplumber
from fastapi import UploadFile, File, Depends, HTTPException
from io import BytesIO
# ==========================================
# 1. 基础配置与大模型初始化
# ==========================================
load_dotenv()
api_key = os.getenv("ZHIPUAI_API_KEY")
if not api_key:
    raise ValueError("❌ 找不到 API Key，请检查 .env 文件！")

client = ZhipuAI(api_key=api_key)


app = FastAPI(title="职业规划 Agent 后端 完整版")
# 创建语音存储目录
AUDIO_DIR = "static/audio"
if not os.path.exists(AUDIO_DIR):
    os.makedirs(AUDIO_DIR, exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")


async def auto_cleanup_audio(interval_seconds: int = 86400):
    """
    后台清理任务：默认每24小时运行一次，删除存活超过24小时的音频文件
    """
    while True:
        print("🧹 [系统任务] 正在扫描过期语音文件...")
        now = time.time()
        audio_path = Path(AUDIO_DIR)

        if audio_path.exists():
            count = 0
            for file in audio_path.glob("*.mp3"):
                # 获取文件最后修改时间，如果早于 24 小时前，则删除
                if now - file.stat().st_mtime > 86400:
                    try:
                        file.unlink()
                        count += 1
                    except Exception as e:
                        print(f"❌ 删除文件 {file.name} 失败: {e}")
            print(f"✅ 清理完成，共删除 {count} 个过期文件。")

        # 挂起任务，等待下一次巡逻
        await asyncio.sleep(interval_seconds)
# --- 2. 在项目启动时挂载该任务 ---
@app.on_event("startup")
async def startup_event():
    # 使用 create_task 让它在后台独立运行，不阻塞主程序
    asyncio.create_task(auto_cleanup_audio())


# ======= 完整替换 main.py 中的 CORSMiddleware 配置 =======
app.add_middleware(
    CORSMiddleware,
    # 明确指定允许访问后端的来源地址
    allow_origins=[
        # 1. 线上环境：允许部署在同一台服务器 3000 端口的前端访问
        "http://47.111.21.230:3000",

        # 2. 开发环境：允许前端同学在本地电脑调试（Next.js 默认端口）
        "http://localhost:3000",
        "http://127.0.0.1:3000",

        # 3. 兼容性：保留 Vite 等其他常用开发端口
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    # 必须为 True 才能支持前端发送 Authorization Header 或 Cookie
    allow_credentials=True,
    # 允许所有 HTTP 方法 (GET, POST, PUT, DELETE 等)
    allow_methods=["*"],
    # 允许所有请求头
    allow_headers=["*"],
)


# --- 定义带 Session 的请求体 ---
class ChatRequest(BaseModel):
    session_id: Optional[str] = None  # 前端传来的会话 ID，用来识别是谁在聊天
    message: str  # 用户发来的对话内容
    profile: Optional[UserProfile] = None  # 新增：允许前端在此处顺便传入用户的画像/简历数据
    graph_data: Optional[dict] = None  # ✨ 新增这个字段，用于存放脱壳后的JSON
# --- 2. 响应模型：核心是增加 graph_data 字段 ---
class ChatResponse(BaseModel):
    session_id: str
    reply: str                       # 这里只放“洗干净”后的纯文本回复
    graph_data: Optional[dict] = None  # ✨ 这里放剥离出来的 JSON 对象，前端直接拿这个画图
    blocks: List[dict] = []          # 保持结构兼容
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


def extract_graph_data_logic(full_text: str):
    """
    专门负责把 AI 话里的 [[GRAPH_START]] 及其内容抠出来
    """
    pattern = r"\[\[GRAPH_START\]\]([\s\S]*?)\[\[GRAPH_END\]\]"
    match = re.search(pattern, full_text)

    if match:
        json_str = match.group(1).strip()
        # 得到不含标签的纯文字回复
        clean_text = re.sub(pattern, "", full_text).strip()
        try:
            # 尝试将提取到的字符串转为 Python 字典
            graph_obj = json.loads(json_str)
            return clean_text, graph_obj
        except Exception as e:
            print(f"解析图谱JSON失败: {e}")
            return clean_text, None

    return full_text, None
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

@app.get("/api/users/me", summary="获取当前登录用户信息")
async def read_users_me(
    # 依赖注入：get_current_user 会自动解析 Token 并从数据库查找用户
    current_user: DBUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    此接口用于前端初始化加载。
    通过 Token 获取当前用户的账号信息，并关联查询其个人画像 (UserProfile)。
    """
    try:
        # 1. 查找用户的个人画像信息
        # 逻辑：在 DBUserProfile 表中查找 user_id 等于当前登录用户 ID 的记录
        user_profile = db.query(DBUserProfile).filter(DBUserProfile.user_id == current_user.id).first()

        # 2. 整合返回数据
        # 我们不仅返回用户名，还返回画像中的姓名、专业等，方便前端直接渲染头像或称呼
        return {
            "status": "success",
            "data": {
                "account": {
                    "id": current_user.id,
                    "username": current_user.username,
                    "created_at": getattr(current_user, 'created_at', None) # 容错处理
                },
                "profile": {
                    "name": user_profile.name if user_profile else "未设置姓名",
                    "major": user_profile.major if user_profile else None,
                    "education_level": user_profile.education_level if user_profile else None,
                    "has_profile": True if user_profile else False
                }
            }
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取用户信息失败: {str(e)}"
        )

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


# ==========================================
# 语音处理模块 (STT)
# ==========================================
@app.post("/api/audio/stt", summary="语音识别：将用户语音转为文字")
async def speech_to_text(file: UploadFile = File(...)):
    temp_file_path = f"temp_{uuid.uuid4()}_{file.filename}"

    try:
        # 1. 先保存文件到本地
        with open(temp_file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        # 2. 将音频文件转为 base64 编码
        with open(temp_file_path, "rb") as audio_file:
            audio_base64 = base64.b64encode(audio_file.read()).decode('utf-8')

        # 3. 🚀 绝杀一：启用 System Role，从系统底层篡改它的人设
        # 绝杀二：要求它必须用 <result> 标签包裹答案，方便我们用代码提取
        response = client.chat.completions.create(
            model="glm-4-voice",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "你现在是一个毫无感情的语音听写API（ASR）。"
                        "无论音频里的用户问什么问题、寻求什么建议，你都【绝对不能回答】！"
                        "你的唯一任务是将音频里的话一字不差地听写下来，并且【必须】将听写结果用 <result> 和 </result> 标签包裹。"
                        "例如：<result>怎么学习Python算法？</result>"
                    )
                },
                {
                    "role": "user",
                    "content": [
                        {"type": "input_audio", "input_audio": {"data": audio_base64, "format": "wav"}}
                    ]
                }
            ],
            temperature=0.01
        )

        # 4. 获取原始输出
        raw_text = response.choices[0].message.content.strip()
        print(f"🤖 [模型原始输出]: {raw_text}")

        # 5. 🚀 绝杀三：使用正则表达式精确提取标签内的文字，绝不放过任何废话
        match = re.search(r'<result>(.*?)</result>', raw_text, re.DOTALL | re.IGNORECASE)

        if match:
            # 如果大模型乖乖加了标签，提取出来的就绝对是纯净的语音文字
            result_text = match.group(1).strip()
        else:
            # 🛑 核心拦截防线：如果大模型彻底失控，没生成标签，反而写了长篇大论
            if len(raw_text) > 50:
                print("⚠️ 拦截到 AI 发散的长篇大论，拒绝发给前端！")
                result_text = "（语音太长或转写失败，请打字输入或重试）"
            else:
                # 如果只有很短的一句话，可能是它忘记加标签了，勉强采用
                result_text = raw_text.replace("好的，", "").replace("没问题，", "").strip()

        # 清理多余的引号
        result_text = result_text.strip('"').strip("'")
        print(f"✅ [提纯后的真实语音]: {result_text}")

        return {"text": result_text}

    except Exception as e:
        print(f"❌ 语音识别失败: {str(e)}")
        return {"error": str(e)}

    finally:
        # 6. 清理临时文件
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)

def calculate_and_save_profile(db: Session, user_id: int, profile_data: dict):
    """
    保留原有算法优化的核心逻辑：
    - 确定性加权计算得分
    - 数据持久化
    """
    db_profile = db.query(DBUserProfile).filter(DBUserProfile.user_id == user_id).first()
    if not db_profile:
        db_profile = DBUserProfile(user_id=user_id)
        db.add(db_profile)

    # 更新字段逻辑 (对照 user_model.py)
    # 采用 .get(key, old_value) 模式，防止 AI 漏掉字段导致原有数据被置空
    db_profile.name = profile_data.get("name", db_profile.name)
    db_profile.education_level = profile_data.get("education_level", db_profile.education_level)
    db_profile.major = profile_data.get("major", db_profile.major)
    db_profile.current_skills = json.dumps(
        profile_data.get("current_skills", json.loads(db_profile.current_skills or "[]")))
    db_profile.certificates = json.dumps(profile_data.get("certificates", json.loads(db_profile.certificates or "[]")))

    # --- 核心修复：仅针对 internship_experience 的 SQLite 绑定错误 ---
    exp_value = profile_data.get("internship_experience", db_profile.internship_experience)
    if isinstance(exp_value, (dict, list)):
        # 如果是字典/列表，转为字符串存入，防止 (sqlite3.ProgrammingError)
        db_profile.internship_experience = json.dumps(exp_value, ensure_ascii=False)
    else:
        # 如果是字符串或 None，保持原逻辑
        db_profile.internship_experience = exp_value

    # --- 你的算法优化部分：确定性逻辑计算 (完全保留，未做任何改动) ---
    try:
        skills = json.loads(db_profile.current_skills)
        certs = json.loads(db_profile.certificates)

        # 基础分 50 + 技能加分 + 证书加分
        score = 50 + (len(skills) * 3) + (len(certs) * 8)

        # 学历加权 (假设你的逻辑)
        if db_profile.education_level == "硕士":
            score += 15
        elif db_profile.education_level == "博士":
            score += 25

        db_profile.competitiveness_score = min(score, 100)  # 封顶 100
    except:
        db_profile.competitiveness_score = 60  # 兜底分

    db.commit()
    db.refresh(db_profile)
    return db_profile
@app.post("/api/user/profile/extract", response_model=ProfileIntakeResponse, summary="从简历/介绍中提取画像并持久化")
async def extract_profile_endpoint(
        request: ResumeExtractRequest,
        db: Session = Depends(get_db),  # 🔒 注入数据库会话
        current_user: DBUser = Depends(get_current_user)  # 🔒 获取当前登录用户
):
    """
    解析用户输入的简历内容，提取画像，并自动更新数据库中的用户信息。
    已升级：支持软素质、创新潜力及竞争力评分提取。
    """
    print(f"🔬 [系统日志] 正在为用户 {current_user.username} 解析简历内容...")

    # 1. 强化版系统指令：确保 AI 提取赛题要求的硬性指标
    system_instruction = (
        "你是一个资深的职业规划专家和高级HR。请从用户的自我介绍或简历文本中提取信息。\n"
        "必须严格返回 JSON 格式，且包含以下字段（若无则填'暂无'或空列表）：\n"
        "1. name: 姓名\n"
        "2. education_level: 学历（如：本科、硕士）\n"
        "3. major: 专业\n"
        "4. current_skills: 专业技能列表 (Array)\n"
        "5. certificates: 证书及奖项列表 (Array)\n"
        "6. soft_skills: 沟通能力、抗压性、团队协作等软素质标签 (Array)\n"
        "7. innovation_potential: 评价其学习能力和创新潜力 (String)\n"
        "8. competitiveness_score: 综合竞争力评分 0-100 (Integer)\n"
        "9. target_roles: 意向岗位 (Array)\n"
        "不要包含任何解释文字，直接输出 JSON。"
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

        # 3. 转化为 Pydantic 模型进行校验 (使用我们最新更新的 UserProfile)
        profile_obj = UserProfile(**profile_dict)
        # ============================================================
        # 🌟 算法优化：使用确定性逻辑计算竞争力得分 (不再纯靠 AI 瞎猜)
        # ============================================================
        base_score = 50
        # 1. 学历加权 (20分)
        if "硕士" in profile_obj.education_level or "博士" in profile_obj.education_level:
            base_score += 20
        elif "本科" in profile_obj.education_level:
            base_score += 10

        # 2. 技能加权 (最多20分)
        skill_bonus = min(len(profile_obj.current_skills) * 3, 20)
        base_score += skill_bonus

        # 3. 证书加权 (最多10分)
        cert_bonus = min(len(profile_obj.certificates) * 5, 10)
        base_score += cert_bonus

        # 综合得分 (限制在 0-100 之间)
        final_score = min(max(base_score, 0), 100)
        profile_obj.competitiveness_score = final_score
        # ============================================================
        # ============================================================
        # 🌟 核心：持久化逻辑（已适配新增字段）
        # ============================================================
        # 检查该用户是否已经有了画像记录
        db_profile = db.query(DBUserProfile).filter(DBUserProfile.user_id == current_user.id).first()

        # 准备要存入数据库的数据
        # 注意：这里假设你的 DBUserProfile 表已经添加了对应的列
        save_data = {
            "education_level": profile_obj.education_level,
            "major": profile_obj.major,
            "grade": profile_obj.grade,
            "location": profile_obj.location,
            # 序列化列表为 JSON 字符串，以便存入数据库的 Text/String 字段
            "target_roles": json.dumps(profile_obj.target_roles, ensure_ascii=False),
            "current_skills": json.dumps(profile_obj.current_skills, ensure_ascii=False),

            # --- 新增维度数据的持久化 ---
            "certificates": json.dumps(profile_obj.certificates, ensure_ascii=False),
            "interests": json.dumps(profile_obj.soft_skills, ensure_ascii=False),  # 将软素质暂存入 interests 或独立字段
            "competitiveness_score": profile_obj.competitiveness_score
        }

        if db_profile:
            print(f"📝 [系统日志] 更新用户 {current_user.username} 的现有画像")
            for key, value in save_data.items():
                if hasattr(db_profile, key):  # 自动检查数据库表是否有此列
                    setattr(db_profile, key, value)
        else:
            print(f"🆕 [系统日志] 为用户 {current_user.username} 创建新画像")
            db_profile = DBUserProfile(user_id=current_user.id, **save_data)
            db.add(db_profile)

        db.commit()
        db.refresh(db_profile)
        # ============================================================

        # 4. 构造返回结果
        # 判断标准：主要信息不为“暂无”且技能列表不为空
        is_complete = (
                profile_obj.major != "暂无" and
                len(profile_obj.current_skills) > 0 and
                profile_obj.competitiveness_score > 0
        )

        return ProfileIntakeResponse(
            profile=profile_obj,
            is_complete=is_complete,
            missing_fields=[] if is_complete else ["请补充更详细的获奖证书或软素质信息"],
            next_questions=[]
        )

    except Exception as e:
        db.rollback()
        print(f"❌ [系统日志] 简历提取失败: {e}")
        raise HTTPException(status_code=500, detail=f"解析失败: {str(e)}")


@app.post("/api/user/profile/upload-resume", summary="上传PDF简历构建画像", tags=["用户画像"])
async def upload_resume_pdf(
        file: UploadFile = File(...),
        db: Session = Depends(get_db),
        current_user: DBUser = Depends(get_current_user)
):
    # 1. 文件校验
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="请上传 PDF 格式文件")

    try:
        # 2. 提取文本
        contents = await file.read()
        resume_text = ""
        with pdfplumber.open(BytesIO(contents)) as pdf:
            for page in pdf.pages:
                resume_text += (page.extract_text() or "") + "\n"

        # 3. AI 结构化处理 (严格对照你的 UserProfile 模型字段)
        response = client.chat.completions.create(
            model="glm-4",
            messages=[
                {"role": "system", "content": """你是一个专业的简历解析专家。
                请从简历中提取信息并返回 JSON。
                必须包含：name, education_level, major, current_skills(数组), certificates(数组), internship_experience, target_roles(数组)。
                不要输出任何 Markdown 标记。"""},
                {"role": "user", "content": resume_text}
            ],
            response_format={"type": "json_object"}
        )

        raw_info = json.loads(response.choices[0].message.content)

        # 4. 调用上面抽取的“确定性算法与持久化逻辑”
        updated_profile = calculate_and_save_profile(db, current_user.id, raw_info)

        return {
            "status": "success",
            "message": "简历画像已更新",
            "data": raw_info  # 返回给前端展示
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"PDF解析失败: {str(e)}")


@app.post("/api/user/profile/sync-from-chat", summary="基于聊天记录手动更新画像", tags=["用户画像"])
async def sync_profile_from_chat(
        db: Session = Depends(get_db),
        current_user: DBUser = Depends(get_current_user)
):
    """
    手动触发接口：分析最近的聊天记录，从中提取新的技能或经历，更新画像。
    """
    # 1. 获取最近 20 条聊天记录
    history = db.query(DBChatMessage).filter(
        DBChatMessage.user_id == current_user.id
    ).order_by(DBChatMessage.id.desc()).limit(20).all()

    if not history:
        raise HTTPException(status_code=400, detail="暂无足够聊天记录进行分析")

    # 将记录反转为正序时间轴
    chat_context = "\n".join([f"{'用户' if msg.is_user else 'AI'}: {msg.content}" for msg in reversed(history)])

    # 2. 获取当前已有的画像数据 (作为 AI 参考的 Baseline)
    current_profile = db.query(DBUserProfile).filter(DBUserProfile.user_id == current_user.id).first()
    profile_snap = {
        "current_skills": json.loads(current_profile.current_skills or "[]"),
        "certificates": json.loads(current_profile.certificates or "[]"),
        "major": current_profile.major
    } if current_profile else {}

    # 3. 调用智谱 AI 进行“增量分析”
    try:
        response = client.chat.completions.create(
            model="glm-4",
            messages=[
                {"role": "system", "content": """你是一个资深的职业画像分析师。
                任务：根据用户近期的聊天记录，识别其提到的任何新技能、新证书或经历的变化。
                要求：参考其现有的画像，合并新发现的信息。
                必须返回 JSON，包含字段：current_skills(数组), certificates(数组), internship_experience(字符串)。
                严禁输出解释性文字，只输出 JSON。"""},
                {"role": "user", "content": f"现有画像：{json.dumps(profile_snap)}\n近期聊天记录：\n{chat_context}"}
            ],
            response_format={"type": "json_object"}
        )

        new_data = json.loads(response.choices[0].message.content)

        # 4. 调用持久化逻辑（包含得分算法）
        updated_db_profile = calculate_and_save_profile(db, current_user.id, new_data)

        return {
            "status": "success",
            "message": "画像已根据聊天记录同步更新",
            "new_score": updated_db_profile.competitiveness_score,
            "detected_updates": new_data
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"同步失败: {str(e)}")
# ==========================================
# 个人画像管理模块 - 补充回显接口
# ==========================================

@app.get("/api/profile/me", summary="获取当前登录用户的画像回显", response_model=UserProfile)
def get_my_profile(
        db: Session = Depends(get_db),
        current_user: DBUser = Depends(get_current_user)
):
    # 1. 查询数据库
    db_profile = db.query(DBUserProfile).filter(DBUserProfile.user_id == current_user.id).first()

    # 2. 🔴 关键修复：如果查不到数据，主动报错告知前端，而不是返回 None
    if not db_profile:
        # 这里返回 404，FastAPI 拦截后不会去校验 UserProfile 模型，从而避免报错
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="您尚未创建个人画像，请先前往完善资料"
        )

    # 3. 正常解析数据并返回
    try:
        return UserProfile(
            name=getattr(db_profile, 'name', "未设置"),
            education_level=db_profile.education_level,
            major=db_profile.major,
            grade=db_profile.grade,
            location=db_profile.location,
            # 增加对空字符串的判断，防止 json.loads 报错
            current_skills=json.loads(db_profile.current_skills) if (
                        db_profile.current_skills and db_profile.current_skills.strip()) else [],
            certificates=json.loads(db_profile.certificates) if (
                        db_profile.certificates and db_profile.certificates.strip()) else [],
            internship_experience=db_profile.internship_experience,
            soft_skills=json.loads(db_profile.soft_skills) if (
                        db_profile.soft_skills and db_profile.soft_skills.strip()) else [],
            target_roles=json.loads(db_profile.target_roles) if (
                        db_profile.target_roles and db_profile.target_roles.strip()) else [],
            interests=json.loads(db_profile.interests) if (
                        db_profile.interests and db_profile.interests.strip()) else []
        )
    except Exception as e:
        print(f"解析画像数据失败: {e}")
        raise HTTPException(status_code=500, detail="画像数据格式解析失败")
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

class GraphNode(BaseModel):
    id: str
    label: str
    type: str = "skill" # skill, role, requirement

class GraphLink(BaseModel):
    source: str
    target: str

class CareerGraphData(BaseModel):
    nodes: List[GraphNode]
    links: List[GraphLink]

# --- 新增：通用的 ResultBlock 模型 ---
class ResultBlock(BaseModel):
    type: str # 'text' | 'career_map' | 'gap_analysis' | 'action_plan'
    content: Optional[str] = None
    data: Optional[dict] = None # 用于承载图谱、雷达图等复杂数据


@app.post("/api/agent/chat", response_model=ChatResponse, summary="职业规划 AI 多轮对话（终极脱壳版）")
async def career_chat(
        request: ChatRequest,
        db: Session = Depends(get_db),
        current_user: DBUser = Depends(get_current_user)
):
    session_id = request.session_id or str(uuid.uuid4())

    # 1. 获取历史记录
    history = db.query(DBChatMessage).filter(
        DBChatMessage.user_id == current_user.id,
        DBChatMessage.session_id == session_id
    ).order_by(DBChatMessage.id.asc()).all()

    # 2. 构造 Prompt（强化对 JSON 格式的约束）
    # 2. 构造 Prompt（强化对 JSON 格式的约束与场景区分）
    system_instruction = (
        "你是一个专业的职业规划专家和严厉的技术面试官。\n"
        "【全局约束】任何情况下返回的结构化数据必须包裹在 [[GRAPH_START]] 和 [[GRAPH_END]] 之间，且严禁使用 ```json 标记。\n\n"

        "【场景1：职业图谱】如果用户要求'渲染大厂晋升图谱'，请返回如下格式：\n"
        "[[GRAPH_START]]\n"
        '{"type": "career_map", "levels": [{"id": "L1", "level": "P5", "title": "初级工程师", "status": "acquired", "salaryRange": "15k-20k", "coreSkills": [{"name": "Python", "isMastered": true}]}]}\n'
        "[[GRAPH_END]]\n\n"

        "【场景2：全真模拟面试】🚨 核心警告：当用户开启模拟面试时，绝对不许你自己把【提问】和【回答】全部模拟写出来！你只需要扮演考官简短地打个招呼，然后根据用户的技能池，生成 3-5 道循序渐进的面试题，并严格按照以下 JSON 格式输出，前端组件会自动接管用户的答题和打分流程：\n"
        "[[GRAPH_START]]\n"
        '{"type": "mock_interview", "role": "目标岗位", "questions": ["面试题1...", "面试题2...", "面试题3..."]}\n'
        "[[GRAPH_END]]"
    )

    messages = [{"role": "system", "content": system_instruction}]
    for h in history:
        messages.append({"role": h.role, "content": h.content})
    messages.append({"role": "user", "content": request.message})

    try:
        # 3. 调用大模型
        response = client.chat.completions.create(
            model="glm-4-flash",
            messages=messages,
            temperature=0.1  # 压低温度，确保 JSON 输出格式极其稳定
        )
        ai_reply = response.choices[0].message.content

        # ==========================================
        # 💡 核心防御逻辑：物理切割 + 后端脱壳
        # ==========================================
        final_graph_obj = None
        clean_reply = ai_reply

        # 检测标记是否存在
        if "[[GRAPH_START]]" in ai_reply and "[[GRAPH_END]]" in ai_reply:
            try:
                # 1. 物理切割：分为文字区和 JSON 区
                parts = ai_reply.split("[[GRAPH_START]]")
                before_text = parts[0]

                inner_content = parts[1].split("[[GRAPH_END]]")
                raw_json = inner_content[0]
                after_text = inner_content[1] if len(inner_content) > 1 else ""

                # 2. 合并干净的文字回复
                clean_reply = (before_text.strip() + "\n" + after_text.strip()).strip()

                # 3. 强力清洗 JSON 字符串并转为字典
                # 排除 AI 可能带出的 Markdown 符号
                clean_json_str = raw_json.replace("```json", "").replace("```", "").strip()
                final_graph_obj = json.loads(clean_json_str)

                print(f"✅ [后端脱壳] 图谱数据解析成功")
            except Exception as e:
                print(f"❌ [后端脱壳] 解析 JSON 失败: {e}")
                # 解析失败时，clean_reply 依然是切干净的文本，不会显示代码乱码

        # ==========================================

        # 4. 持久化存储（存入数据库的是干净的文本，不含 [[...]] 乱码）
        user_msg = DBChatMessage(user_id=current_user.id, session_id=session_id, role="user", content=request.message)
        ai_msg = DBChatMessage(user_id=current_user.id, session_id=session_id, role="assistant", content=clean_reply)
        db.add(user_msg)
        db.add(ai_msg)
        db.commit()

        # 5. 返回给前端
        return ChatResponse(
            session_id=session_id,
            reply=clean_reply,  # ✨ 前端对话框只显示这个，非常干净
            graph_data=final_graph_obj,  # ✨ 前端图谱组件直接用这个对象
            blocks=[]
        )

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"对话失败: {e}")
# ==========================================
# 🚀 10. [全新增] 岗位差距分析接口 (Phase 4)
# 对应 TDD 的 Gap Analysis 功能
# ==========================================



class GapDimension(BaseModel):
    score: int = Field(..., description="该维度的得分(0-100)")
    analysis: str = Field(..., description="详细的差距分析文字")
    suggestions: List[str] = Field(default=[], description="改进建议列表")


class FullGapAnalysisResponse(BaseModel):

    target_role: str
    overall_match_score: int
    # 四维对齐模型
    basic_matching: GapDimension  # 基础素质（学历、专业）
    skill_matching: GapDimension  # 专业技能（工具、语言）
    soft_skill_matching: GapDimension  # 职业素养（沟通、协作、抗压）
    potential_matching: GapDimension  # 发展潜力（创新、学习能力）
    immediate_next_steps: List[str] = Field(default=[], description="即刻行动建议")
    roadmap_preview: str = Field(..., description="简短的学习路径规划建议")

@app.post("/api/agent/gap-analysis", summary="四维差距分析", tags=["Agent核心逻辑"])
def gap_analysis_endpoint(
    target_role: str = Query(..., description="目标岗位名称"),
    db: Session = Depends(get_db),
    current_user: DBUser = Depends(get_current_user)
):
    # 1. 获取用户画像
    db_profile = db.query(DBUserProfile).filter(DBUserProfile.user_id == current_user.id).first()
    if not db_profile:
        raise HTTPException(status_code=404, detail="请先生成个人画像")

    # 2. 获取行业标准（模块1生成的表）
    from models.db_models import DBJobStandardProfile
    standard_job = db.query(DBJobStandardProfile).filter(
        DBJobStandardProfile.role_name.like(f"%{target_role}%")
    ).first()

    job_ref = f"技能要求: {standard_job.core_skills}, 素质要求: {standard_job.soft_skills}" if standard_job else "通用行业标准"

    # 3. 构造 Prompt，强制约束字段名
    system_instruction = (
        "你是一个职业对齐分析引擎。对比用户信息与岗位标准，进行四维量化分析。\n"
        "必须严格返回 JSON，不得包含 ```json 标签。\n"
        "JSON 字段名必须完全匹配：\n"
        "{\n"
        "  \"overall_match_score\": 85,\n"
        "  \"basic\": {\"score\": 80, \"analysis\": \"...\", \"suggestions\": []},\n"
        "  \"skill\": {\"score\": 75, \"analysis\": \"...\", \"suggestions\": []},\n"
        "  \"soft\": {\"score\": 90, \"analysis\": \"...\", \"suggestions\": []},\n"
        "  \"potential\": {\"score\": 85, \"analysis\": \"...\", \"suggestions\": []},\n"
        "  \"immediate_next_steps\": [\"步骤1\"],\n"
        "  \"roadmap_preview\": \"预览文字\"\n"
        "}"
    )

    # 1. 组装用户信息字典
    user_info = {
        "education": db_profile.education_level,
        "major": db_profile.major,
        "current_skills": db_profile.current_skills,
        "soft_skills": db_profile.interests,
        "competitiveness": db_profile.competitiveness_score
    }
    user_prompt = f"请对比以下信息进行打分：\n目标岗位：{target_role}\n行业标准：{job_ref}\n用户信息：{json.dumps(user_info, ensure_ascii=False)}"
    # 替换 gap_analysis_endpoint 内部的 try 块
    max_retries = 2  # 设置最大重试次数
    for attempt in range(max_retries):
        try:
            response = client.chat.completions.create(
                model="glm-4-flash",
                messages=[
                    {"role": "system", "content": system_instruction},
                    {"role": "user", "content": user_prompt}  # 🚨 现在这里有值了！
                ],
                temperature=0.2
            )

            ai_content = response.choices[0].message.content.strip()
            cleaned_json = ai_content.replace("```json", "").replace("```", "").strip()
            result_dict = json.loads(cleaned_json)

            return FullGapAnalysisResponse(
                target_role=target_role,
                overall_match_score=result_dict.get("overall_match_score", 60),  # 提供默认值防崩
                basic_matching=GapDimension(
                    **result_dict.get("basic", {"score": 60, "analysis": "数据生成中", "suggestions": []})),
                skill_matching=GapDimension(
                    **result_dict.get("skill", {"score": 60, "analysis": "数据生成中", "suggestions": []})),
                soft_skill_matching=GapDimension(
                    **result_dict.get("soft", {"score": 60, "analysis": "数据生成中", "suggestions": []})),
                potential_matching=GapDimension(
                    **result_dict.get("potential", {"score": 60, "analysis": "数据生成中", "suggestions": []})),
                immediate_next_steps=result_dict.get("immediate_next_steps", ["继续努力"]),
                roadmap_preview=result_dict.get("roadmap_preview", "生成中...")
            )

        except json.JSONDecodeError:
            print(f"⚠️ 第 {attempt + 1} 次 JSON 解析失败，准备重试...")
            if attempt == max_retries - 1:  # 如果最后一次还失败
                raise HTTPException(status_code=500, detail="大模型生成格式持续异常，请稍后再试")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"分析失败: {str(e)}")
# ==========================================
# 🚀 11.Phase 5: 学习路径规划接口 (Actionable Roadmap)
# ==========================================
# 1. 定义数据模型
# --- 模块 4 专用：升维后的路径规划模型 ---

class LearningMilestone(BaseModel):
    phase: str = Field(..., description="阶段名称（如：短期突破、中期深造、长期规划）")
    period: str = Field(..., description="预计耗时（如：1-2周、3个月）")
    focus_targets: List[str] = Field(..., description="该阶段的核心学习目标/知识点")
    recommended_resources: List[str] = Field(..., description="推荐的学习资源、书籍或实战动作")

class ActionableRoadmapResponse(BaseModel):
    target_role: str = Field(..., description="目标岗位")
    summary: str = Field(..., description="路径规划总览")
    milestones: List[LearningMilestone] = Field(..., description="分阶段执行路径")
    conclusion: str = Field(..., description="职业导师的寄语")


# ==========================================
# 模块 4：学习路径规划核心接口 (🔥 已升级：生成器-反馈器 对抗架构)
# ==========================================
@app.post("/api/agent/learning-path", response_model=ActionableRoadmapResponse,
          summary="生成进阶学习路径 (Actor-Critic架构)")
async def learning_path_endpoint(
        target_role: str = Query(..., description="目标岗位"),
        db: Session = Depends(get_db),
        current_user: DBUser = Depends(get_current_user)
):
    print(f"\n🔬 [系统日志] 正在为用户 {current_user.username} 启动【多智能体协同】生成学习路径...")

    # 1. 自动调取用户最新的画像
    db_profile = db.query(DBUserProfile).filter(DBUserProfile.user_id == current_user.id).first()
    if not db_profile:
        raise HTTPException(status_code=404, detail="未找到用户画像，请先上传简历并生成档案")

    user_context = {
        "user_major": db_profile.major,
        "current_skills": db_profile.current_skills,
        "certificates": db_profile.certificates,
        "target_role": target_role,
        "current_competitiveness": db_profile.competitiveness_score
    }

    try:
        # ====================================================
        # 🟢 第一阶段：生成器 (Generator) 起草初稿
        # ====================================================
        generator_instruction = (
            "你是一个起草员。请根据用户现状，快速生成一个职业路径规划初稿。\n"
            "必须返回严格 JSON：{\"summary\": \"...\", \"milestones\": [{\"phase\": \"...\", \"period\": \"...\", \"focus_targets\": [], \"recommended_resources\": []}], \"conclusion\": \"...\"}"
        )

        gen_response = client.chat.completions.create(
            model="glm-4-flash",
            messages=[
                {"role": "system", "content": generator_instruction},
                {"role": "user", "content": f"用户信息：{json.dumps(user_context, ensure_ascii=False)}"}
            ],
            temperature=0.5
        )
        draft_json_str = gen_response.choices[0].message.content.strip().replace("```json", "").replace("```", "")

        print(f"✅ [生成器] 初稿起草完毕，正在提交给反馈器(Critic)审查...")

        # ====================================================
        # 🔴 第二阶段：反馈器 (Critic) 审查并重构
        # ====================================================
        critic_instruction = (
            "你是一位极其严苛的职场导师和技术架构师（Critic）。"
            "你的任务是审查【起草员】生成的学习路径初稿。找出其中的空洞、过于宽泛、不切实际或缺乏深度的地方。\n"
            "请直接输出一份【打分评价】以及【深度重构后的终稿】。\n"
            "必须严格返回 JSON，结构如下：\n"
            "{\n"
            "  \"critic_score\": 75,\n"
            "  \"critic_comments\": \"批评意见，例如：太笼统，缺少具体的开源项目推荐...\",\n"
            "  \"revised_roadmap\": {\n"
            "    \"summary\": \"...\",\n"
            "    \"milestones\": [{\"phase\": \"...\", \"period\": \"...\", \"focus_targets\": [], \"recommended_resources\": []}],\n"
            "    \"conclusion\": \"...\"\n"
            "  }\n"
            "}"
        )

        critic_response = client.chat.completions.create(
            model="glm-4-flash",
            messages=[
                {"role": "system", "content": critic_instruction},
                {"role": "user",
                 "content": f"目标岗位：{target_role}\n用户真实能力基底：{json.dumps(user_context, ensure_ascii=False)}\n\n【生成器初稿】：{draft_json_str}"}
            ],
            temperature=0.3  # 降低温度，确保严谨性
        )

        critic_raw = critic_response.choices[0].message.content.strip().replace("```json", "").replace("```", "")
        critic_data = json.loads(critic_raw)

        # 打印终端日志，供演示时展示 AI 内部博弈过程
        print(f"🔥 [反馈器] 审核完成！打分: {critic_data.get('critic_score', 0)}/100")
        print(f"📝 [反馈器意见]: {critic_data.get('critic_comments', '无')}")
        print(f"✨ [系统] 已采用重构后的高质量规划路径返回给用户。")

        # ====================================================
        # 🔵 第三阶段：提取最终高价值数据返回
        # ====================================================
        final_roadmap = critic_data.get("revised_roadmap", {})

        return ActionableRoadmapResponse(
            target_role=target_role,
            summary=final_roadmap.get("summary", "职业提升路径图"),
            milestones=[LearningMilestone(**m) for m in final_roadmap.get("milestones", [])],
            conclusion=final_roadmap.get("conclusion", "经历严苛审查的路线图，请严格执行！")
        )

    except Exception as e:
        print(f"❌ 路径规划生成崩溃: {str(e)}")
        # 降级容错逻辑：如果反馈器 JSON 解析失败，至少保证前端不崩
        raise HTTPException(status_code=500, detail=f"多智能体协同生成失败: {str(e)}")

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
# --- 模块 5：针对性面试专用模型  ---
class TargetedInterviewQuestion(BaseModel):
    role: str
    difficulty: str = Field(..., description="难度系数：初级/中级/高级")
    question: str = Field(..., description="针对性生成的面试题")
    focus_topic: str = Field(..., description="本题考察的知识点（针对用户的弱点）")
    background_context: str = Field(..., description="出题背景（为什么针对性出这道题）")

class TargetedInterviewWithAudioResponse(BaseModel):
    question_data: TargetedInterviewQuestion
    audio_url: Optional[str] = None

# 通用面试题的单个条目模型
class GeneralQuestionItem(BaseModel):
    id: int
    topic: str
    question: str
    audio_url: Optional[str] = None

# 接口最终返回的模型
class GeneralInterviewResponse(BaseModel):
    role: str
    questions: List[GeneralQuestionItem]

def task_generate_tts(text: str, save_path: str):
    """
    具体的语音合成后台任务，由 BackgroundTasks 调用
    """
    try:
        print(f"🎙️ [后台任务] 正在合成面试题语音...")
        # 调用智谱语音合成接口
        tts_response = client.audio.speech.create(
            model="cogview-3", # 请确保你的 API 权限支持此模型名
            voice="charles",   # charles(成熟男声), lily(亲切女声)
            input=text
        )
        # 将流式数据保存为本地 mp3 文件
        tts_response.stream_to_file(save_path)
        print(f"✅ [后台任务] 语音文件已生成: {save_path}")
    except Exception as e:
        print(f"❌ [后台任务] 语音合成失败: {str(e)}")

# ==========================================
# 历史记录查询模块 (适配 db_models.py 结构)
# ==========================================

@app.get("/api/history/roadmaps", summary="获取历史职业规划记录", tags=["历史记录回显"])
def get_roadmap_history(
    db: Session = Depends(get_db),
    current_user: DBUser = Depends(get_current_user)
):
    """
    获取当前用户所有的职业规划记录。
    适配 DBRoadmap 模型：使用 user_id 过滤，解析 roadmap_json 字段。
    """
    # 1. 从数据库按 ID 倒序查询（最新的规划排在最前）
    history = db.query(DBRoadmap).filter(
        DBRoadmap.user_id == current_user.id
    ).order_by(DBRoadmap.id.desc()).all()

    results = []
    for item in history:
        raw_data = getattr(item, 'roadmap_json', None) or getattr(item, 'roadmap_detail', None)
        # 2. 解析存储在 Text 字段中的 JSON 字符串
        try:
            data_content = json.loads(item.roadmap_json) if (item.roadmap_json and item.roadmap_json.strip()) else {}
        except Exception:
            data_content = {"error": "数据解析失败"}

        results.append({
            "id": item.id,
            "role_name": getattr(item, 'role_name', "未知岗位"),
            # 返回完整的规划 JSON 给前端渲染路径图
            "roadmap_detail": data_content
        })

    return {
        "status": "success",
        "count": len(results),
        "data": results
    }

# --- 新增：获取面试题目接口 ---
@app.get("/api/interview/questions", response_model=GeneralInterviewResponse,
         summary="通用面试：多维度题目生成（带异步语音）")
async def get_general_questions(
        background_tasks: BackgroundTasks,  # 引入后台任务
        target_role: str = Query(..., description="目标岗位"),
        focus_topics: str = Query("基础知识, 实战经验", description="考察重点，用逗号分隔"),
        db: Session = Depends(get_db),
        current_user: DBUser = Depends(get_current_user)
):
    """
    生成一组（3-5道）针对目标岗位的通用面试题，并异步生成第一道题的语音。
    """
    print(f"📋 [系统日志] 正在为用户 {current_user.username} 生成通用练习题...")

    system_instruction = (
        f"你是一位资深的{target_role}主考官。请根据考察重点：[{focus_topics}]，生成3-5道面试题。\n"
        "要求：题目由浅入深，涵盖基础理论与场景应用。\n"
        "必须返回严格的 JSON 数组格式，每个对象包含：id(int), topic(str), question(str)。\n"
        "不要包含任何 Markdown 标签。"
    )

    try:
        # 1. 调用大模型生成一组题目
        response = client.chat.completions.create(
            model="glm-4-flash",
            messages=[{"role": "system", "content": system_instruction}],
            temperature=0.7
        )

        ai_raw = response.choices[0].message.content.strip().replace("```json", "").replace("```", "")
        raw_questions = json.loads(ai_raw)

        final_questions = []
        for index, item in enumerate(raw_questions):
            # 2. 为每一道题预设一个唯一的语音文件名
            audio_filename = f"gen_q_{uuid.uuid4()}.mp3"
            audio_save_path = os.path.join(AUDIO_DIR, audio_filename)

            # 3. 🔴 关键优化：将第一道题（或全部题）加入异步语音合成
            # 为了节省 API 流量和服务器空间，建议演示时仅自动生成第一道题的语音
            if index == 0:
                background_tasks.add_task(task_generate_tts, item["question"], audio_save_path)
                audio_link = f"/static/audio/{audio_filename}"
            else:
                # 其他题目可以设置成“点击后再生成”，或这里暂时给 None
                audio_link = None

            final_questions.append(GeneralQuestionItem(
                id=item.get("id", index + 1),
                topic=item.get("topic", "通用"),
                question=item.get("question", ""),
                audio_url=audio_link
            ))

        return GeneralInterviewResponse(
            role=target_role,
            questions=final_questions
        )

    except Exception as e:
        print(f"❌ 通用出题失败: {str(e)}")
        raise HTTPException(status_code=500, detail="面试题生成失败，请稍后重试")

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
@app.post("/api/report/export", summary="一键导出职业规划报告 (Markdown格式)")
async def export_report_endpoint(
    target_role: str = Query(..., description="目标岗位"),
    db: Session = Depends(get_db),
    current_user: DBUser = Depends(get_current_user)
):
    """
    一键导出用户的个人画像与目标岗位规划报告。
    返回 Markdown 格式的文本文件，前端可直接触发下载。
    """
    # 1. 获取用户画像
    db_profile = db.query(DBUserProfile).filter(DBUserProfile.user_id == current_user.id).first()
    if not db_profile:
        raise HTTPException(status_code=404, detail="请先生成个人档案")

    # 2. 组装 Markdown 报告内容
    report_content = f"""# 🏆 个人职业发展规划报告

## 👤 基本信息
* **姓名/用户**: {current_user.username}
* **学历**: {db_profile.education_level}
* **专业**: {db_profile.major}
* **竞争力综合评分**: {db_profile.competitiveness_score} / 100

## 🎯 目标岗位: {target_role}

## 🛠️ 当前技能储备
* **专业技能**: {db_profile.current_skills}
* **软素质**: {db_profile.interests}
* **相关证书**: {db_profile.certificates}

---

## 📈 专家评估建议
*(基于系统四维对齐分析)*
系统已为您生成了深度分析，您的核心优势在于基础素质与学习潜力。针对 `{target_role}` 岗位，建议重点弥补专业技能中的工具链实战经验。

## 🚀 执行路径 (Roadmap)
1. **近期 (1-2周)**: 针对性弥补核心技能缺失，完成至少一个相关实战 Demo。
2. **中期 (1-3月)**: 沉淀项目经验，获取相关行业证书。
3. **长期**: 参与开源项目或高质量实习，提升不可替代性。

---
*报告生成时间: 自动生成*
*由 AI Agent 智能职业教练提供支持*
"""

    # 3. 返回文件形式的响应
    return PlainTextResponse(
        content=report_content,
        media_type="text/markdown",
        headers={"Content-Disposition": f"attachment; filename=Career_Report_{current_user.username}.md"}
    )


# ==========================================
# 模块 5：针对性面试生成 (🔥 已升级：智能上下文压缩 Context Compression)
# ==========================================



# ==========================================
# 模块 5：针对性面试生成 (🔥 已升级：智能上下文压缩 + TTS 语音同步)
# ==========================================
def task_generate_tts(text: str, save_path: str):
    """
    具体的语音合成逻辑，将被放在后台执行
    """
    try:
        print(f"🎙️ [后台任务] 开始为新题目生成语音...")
        tts_response = client.audio.speech.create(
            model="cogview-3", # 确保模型名正确
            voice="charles",
            input=text
        )
        tts_response.stream_to_file(save_path)
        print(f"✅ [后台任务] 语音合成成功: {save_path}")
    except Exception as e:
        print(f"❌ [后台任务] 语音合成失败: {str(e)}")


@app.get("/api/interview/generate-targeted", response_model=TargetedInterviewWithAudioResponse,
         summary="生成弱点定向面试题（异步语音版）")
async def generate_targeted_question(
        background_tasks: BackgroundTasks,  # 注入后台任务组件
        target_role: str = Query(..., description="目标岗位"),
        db: Session = Depends(get_db),
        current_user: DBUser = Depends(get_current_user)
):
    print(f"\n🔬 [系统日志] 正在为用户 {current_user.username} 准备定向面试题...")
    db_profile = db.query(DBUserProfile).filter(DBUserProfile.user_id == current_user.id).first()

    # --- 1. 上下文记忆压缩 (逻辑保持不变) ---
    past_weaknesses = db.query(DBInterview).filter(
        DBInterview.user_id == current_user.id,
        DBInterview.score < 75
    ).order_by(DBInterview.id.desc()).limit(10).all()

    weakness_context = "用户目前是基础学习阶段，暂无明显的历史错误。"

    if past_weaknesses:
        if len(past_weaknesses) <= 3:
            suggestions = [f"- {w.improvement_suggestion}" for w in past_weaknesses]
            weakness_context = "用户的历史弱点如下：\n" + "\n".join(suggestions)
        else:
            print(f"🗜️ [上下文管理] 触发 LLM 记忆压缩机制...")
            raw_text = "\n".join([w.improvement_suggestion for w in past_weaknesses])
            compress_instruction = "你是一个记忆压缩引擎。请精准提取出核心的知识盲区，总结成一段100字以内的精简画像。"
            try:
                compress_response = client.chat.completions.create(
                    model="glm-4-flash",
                    messages=[
                        {"role": "system", "content": compress_instruction},
                        {"role": "user", "content": raw_text}
                    ],
                    temperature=0.3
                )
                weakness_context = compress_response.choices[0].message.content.strip()
            except Exception:
                weakness_context = "\n".join([w.improvement_suggestion for w in past_weaknesses[:3]])

    # --- 2. AI 出题 ---
    system_instruction = (
        f"你是一位严厉且专业的{target_role}主考官。请参考用户的【历史弱点报告】，出一道能击中其弱点的深度面试题。\n"
        "必须返回严格的 JSON 格式，不得包含 Markdown 标签（如 ```json）。"
    )

    user_context = {
        "target_role": target_role,
        "skills": db_profile.current_skills if db_profile else "基础开发",
        "weakness_report": weakness_context
    }

    try:
        response = client.chat.completions.create(
            model="glm-4-flash",
            messages=[
                {"role": "system", "content": system_instruction},
                {"role": "user", "content": f"请出题：{json.dumps(user_context, ensure_ascii=False)}"}
            ],
            temperature=0.8
        )

        ai_raw = response.choices[0].message.content.strip()
        cleaned_json = ai_raw.replace("```json", "").replace("```", "").strip()
        res_dict = json.loads(cleaned_json)

        # 构建题目 Pydantic 对象
        question_obj = TargetedInterviewQuestion(**res_dict)

        # --- 3. 异步触发语音合成 ---
        # 预设文件名和路径
        audio_filename = f"interview_{uuid.uuid4()}.mp3"
        audio_save_path = os.path.join(AUDIO_DIR, audio_filename)

        # 🔴 将耗时的语音合成任务加入后台队列，立即返回响应
        background_tasks.add_task(task_generate_tts, question_obj.question, audio_save_path)

        # 返回给前端题目数据和音频访问链接
        return TargetedInterviewWithAudioResponse(
            question_data=question_obj,
            audio_url=f"/static/audio/{audio_filename}"
        )

    except Exception as e:
        print(f"❌ 针对性出题失败: {str(e)}")
        # 兜底逻辑
        return TargetedInterviewWithAudioResponse(
            question_data=TargetedInterviewQuestion(
                role=target_role,
                difficulty="中级",
                question=f"请简述在{target_role}开发中，如何确保系统的可扩展性？",
                focus_topic="架构设计",
                background_context="系统暂忙，请先行阅读题目进行练习。"
            ),
            audio_url=None
        )

@app.get("/api/history/interviews", summary="获取历史面试记录", tags=["历史记录回显"])
def get_interview_history(
    db: Session = Depends(get_db),
    current_user: DBUser = Depends(get_current_user)
):
    """
    获取当前用户所有的模拟面试复盘记录。
    适配 DBInterview 模型：提取得分、评价、建议及参考答案。
    """
    history = db.query(DBInterview).filter(
        DBInterview.user_id == current_user.id
    ).order_by(DBInterview.id.desc()).all()

    results = []
    for item in history:
        results.append({
            "id": item.id,
            "question": item.question,
            "user_answer": item.user_answer,
            "score": item.score,
            "evaluation": item.evaluation, # 对应模型中的评价字段
            "improvement_suggestion": item.improvement_suggestion, # 改进建议
            "reference_answer": item.reference_answer # 参考答案
        })

    return {
        "status": "success",
        "count": len(results),
        "data": results
    }

if __name__ == "__main__":

    # host="0.0.0.0" 是关键，它告诉程序监听手机热点分配给你的所有 IP 地址
    # port=8000 是你约定的接口端口
    print("🚀 后端服务正在启动，请确保已连接手机热点...")
    uvicorn.run(app, host="0.0.0.0", port=8000)
