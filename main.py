import sqlite3
import os
import json
import uuid
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv
from zhipuai import ZhipuAI
from typing import Optional, List
from fastapi import Query
from models.user_model import UserProfile
# ==========================================
# 1. 基础配置与大模型初始化
# ==========================================
load_dotenv()
api_key = os.getenv("ZHIPUAI_API_KEY")
if not api_key:
    raise ValueError("❌ 找不到 API Key，请检查 .env 文件！")

client = ZhipuAI(api_key=api_key)

app = FastAPI(title="职业规划 Agent 后端 - Phase 2")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- 定义带 Session 的请求体 ---
class ChatRequest(BaseModel):
    session_id: Optional[str] = None  # 前端传来的会话 ID，用来识别是谁在聊天
    message: str                      # 用户发来的对话内容
    profile: Optional[UserProfile] = None  # 新增：允许前端在此处顺便传入用户的画像/简历数据


# --- 建立简单的内存数据库来存储聊天记录 ---
session_memory = {}

# 系统预设 Prompt（人设）
SYSTEM_PROMPT = "你是一个专业的职业规划专家。你有能力调用工具去数据库查询真实的岗位数据。请结合查询到的数据，给出专业、落地的建议。"


# ==========================================
# 2. 数据库查询工具（供 AI 调用 & 供 API 使用）
# ==========================================
def search_jobs_from_db(keyword: str):
    print(f"🔧 [系统日志] 正在执行数据库查询，关键词: {keyword}")
    # ⚠️ 请确保 career_project.db 文件在项目根目录下
    conn = sqlite3.connect("career_project.db")
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
# 4. 新增：供前端直接调用的岗位列表接口
# ==========================================
@app.get("/api/jobs", summary="获取所有岗位列表（纯数据接口）")
def get_all_jobs(skip: int = 0, limit: int = 20):
    """
    供前端（FE）同学直接获取岗位列表的接口（支持分页）。
    """
    print("🌐 [系统日志] 收到前端的岗位列表请求")
    conn = sqlite3.connect("career_project.db")
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # 查出指定数量的岗位
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

    # 1. 处理会话 ID：如果没有传，就生成一个新的
    session_id = request.session_id if request.session_id else f"sess_{uuid.uuid4().hex[:8]}"

    # 2. 提取或初始化历史记忆
    if session_id not in session_memory:
        session_memory[session_id] = [
            {"role": "system", "content": SYSTEM_PROMPT}
        ]

    # 把用户的新话加进记忆里
    session_memory[session_id].append({"role": "user", "content": user_input})

    print(f"🧠 [系统日志] 收到消息。当前会话 {session_id} 的记忆长度：{len(session_memory[session_id])} 条")

    # 3. 带着所有记忆去问大模型
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

        # 执行查询
        job_data = search_jobs_from_db(search_keyword)

        # 把 AI 调工具的动作存入记忆
        session_memory[session_id].append(ai_message.model_dump())
        session_memory[session_id].append({
            "role": "tool",
            "content": json.dumps(job_data, ensure_ascii=False),
            "tool_call_id": tool_call.id
        })

        # 再次请求 AI 总结
        second_response = client.chat.completions.create(
            model="glm-4-flash",
            messages=session_memory[session_id]
        )
        final_reply = second_response.choices[0].message.content

        # 把最终回答存入记忆
        session_memory[session_id].append({"role": "assistant", "content": final_reply})

        # 组装返回给前端的 blocks 数组
        blocks.append({"type": "text", "content": final_reply})
        if job_data:
            blocks.append({"type": "career_recommendations", "items": job_data})

    else:
        print("🤖 [系统日志] 直接回答。")
        final_reply = ai_message.content
        session_memory[session_id].append({"role": "assistant", "content": final_reply})
        blocks.append({"type": "text", "content": final_reply})

    # 严格按照你们团队约定的格式返回
    return {
        "sessionId": session_id,
        "role": "assistant",
        "blocks": blocks
    }




# ==========================================
# 6. 新增：高级多条件岗位搜索接口
# ==========================================
@app.get("/api/jobs/search", summary="高级岗位搜索接口")
def search_jobs_api(
        keyword: Optional[str] = Query(None, description="搜索关键词，如：Java, 前端"),
        location: Optional[str] = Query(None, description="工作地点，如：北京, 上海"),
        limit: int = Query(20, description="返回的最大条数")
):
    """
    供前端使用的多条件过滤接口。
    前端可以通过传入 keyword 或 location 组合过滤岗位。
    """
    print(f"🔍 [系统日志] 收到高级搜索请求: keyword={keyword}, location={location}")
    conn = sqlite3.connect("career_project.db")
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # 动态构建 SQL 语句，防止 SQL 注入
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
# 7. 新增：岗位数据分析与统计接口
# ==========================================
@app.get("/api/jobs/stats", summary="岗位数据统计接口 (供图表渲染)")
def get_job_stats():
    """
    返回清洗后的统计数据。
    供前端直接将数据喂给 ECharts 等图表库，绘制“各城市岗位分布图”等。
    """
    print("📊 [系统日志] 收到岗位数据统计请求")
    conn = sqlite3.connect("career_project.db")
    cursor = conn.cursor()

    # 统计出现次数最多的前 5 个工作城市
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

    # 将数据格式化为前端图表最喜欢的 key-value 结构
    stats_data = [{"name": row[0], "value": row[1]} for row in rows]

    return {
        "status": "success",
        "chart_type": "pie",  # 提示前端适合画饼图
        "data": stats_data
    }


# ==========================================
# 8:智能简历/画像录入接口
# ==========================================

# 1. 定义简历提取的请求载荷
class ResumeExtractRequest(BaseModel):
    session_id: Optional[str] = None  # 可选的会话 ID
    text_content: str  # 用户粘贴的简历文本或自我介绍


# 2. 定义符合 TDD 10.1 节要求的返回数据结构
class ProfileIntakeResponse(BaseModel):
    profile: UserProfile  # 结构化用户画像补全
    missing_fields: List[str]  # 缺失字段列表
    next_questions: List[str]  # 下一轮建议提问


@app.post("/api/user/profile/extract", response_model=ProfileIntakeResponse, summary="智能简历提取接口")
async def extract_profile_endpoint(request: ResumeExtractRequest):
    """
    对应 TDD 10.1 的 profile_intake_skill。
    输入：自然语言用户描述（简历或自我介绍）
    输出：提取出的结构化画像 + 缺失字段 + 追问建议
    """
    print("📝 [系统日志] 收到简历提取请求")

    # 3. 构造系统提示词，强制要求 AI 提取信息并输出 JSON 格式
    system_instruction = (
        "你是一个专业的简历解析助手。请从用户的自我介绍或简历文本中，提取结构化信息，"
        "并严格按照 JSON 格式返回。JSON 包含以下字段：\n"
        "- education_level (字符串或 null)\n"
        "- major (字符串或 null)\n"
        "- grade (字符串或 null)\n"
        "- location (字符串或 null)\n"
        "- target_roles (字符串数组)\n"
        "- current_skills (字符串数组)\n"
        "- interests (字符串数组)\n"
        "如果文本中完全没有提及某项，请填 null 或空数组。不要返回 JSON 以外的任何多余解释文字！"
    )

    # 4. 调用 GLM-4 提取简历中的有效实体信息
    ai_response = client.chat.completions.create(
        model="glm-4-flash",  # 沿用你项目中使用的模型
        messages=[
            {"role": "system", "content": system_instruction},
            {"role": "user", "content": f"请提取以下文本中的画像信息：\n{request.text_content}"}
        ],
        temperature=0.1  # 调低温度，保证提取的客观严谨性
    )

    ai_content = ai_response.choices[0].message.content

    # 5. 解析大模型返回的 JSON 并装填进 UserProfile
    try:
        # 去除 AI 有时会自动包裹的 ```json 代码块
        cleaned_json = ai_content.strip()
        if cleaned_json.startswith("```json"):
            cleaned_json = cleaned_json[7:]
        if cleaned_json.endswith("```"):
            cleaned_json = cleaned_json[:-3]
        cleaned_json = cleaned_json.strip()

        extracted_data = json.loads(cleaned_json)
        profile = UserProfile(**extracted_data)
    except Exception as e:
        print(f"❌ [系统日志] 解析 AI 返回的 JSON 失败: {e}。原始内容: {ai_content}")
        # 降级处理：解析失败则返回空画像
        profile = UserProfile()

    # 6. 检查缺失字段（对应 TDD 10.1 要求的输出）
    missing_fields = []
    if not profile.education_level: missing_fields.append("学历")
    if not profile.major: missing_fields.append("专业")
    if not profile.grade: missing_fields.append("年级")
    if not profile.location: missing_fields.append("期望工作地点")
    if not profile.target_roles: missing_fields.append("目标岗位")
    if not profile.current_skills: missing_fields.append("当前掌握的技能")

    # 7. 动态生成下一轮建议提问（对应 TDD 10.1 要求的输出）
    next_questions = []
    if "专业" in missing_fields:
        next_questions.append("请问你的大学专业是什么呢？")
    elif "当前掌握的技能" in missing_fields:
        next_questions.append("你目前比较熟悉或者掌握了哪些专业技能？（比如：Python，Excel 等）")
    elif "目标岗位" in missing_fields:
        next_questions.append("你毕业后比较想往哪个具体的岗位或职业方向发展？")
    else:
        next_questions.append("太棒了！你的基本画像已经非常完整，现在我们可以开始进行职业推荐或差距分析了。")

    # 8. 严格按照 TDD 协议格式返回
    return ProfileIntakeResponse(
        profile=profile,
        missing_fields=missing_fields,
        next_questions=next_questions
    )