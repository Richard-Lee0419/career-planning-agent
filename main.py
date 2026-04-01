import sqlite3
import os
import json
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
# ==========================================
# 1. 基础配置与大模型初始化
# ==========================================
load_dotenv()
api_key = os.getenv("ZHIPUAI_API_KEY")
if not api_key:
    raise ValueError("❌ 找不到 API Key，请检查 .env 文件！")

client = ZhipuAI(api_key=api_key)

# 💡 顺便把文档标题从 Phase 2 升为 Phase 3
app = FastAPI(title="职业规划 Agent 后端 - Phase 4")

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
    message: str  # 用户发来的对话内容
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
# 4. 供前端直接调用的岗位列表接口
# ==========================================
@app.get("/api/jobs", summary="获取所有岗位列表（纯数据接口）")
def get_all_jobs(skip: int = 0, limit: int = 20):
    print("🌐 [系统日志] 收到前端的岗位列表请求")
    conn = sqlite3.connect("career_project.db")
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
    conn = sqlite3.connect("career_project.db")
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
    conn = sqlite3.connect("career_project.db")
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
    text_content: str


class ProfileIntakeResponse(BaseModel):
    profile: UserProfile
    missing_fields: List[str]
    next_questions: List[str]


@app.post("/api/user/profile/extract", response_model=ProfileIntakeResponse, summary="智能简历提取接口")
async def extract_profile_endpoint(request: ResumeExtractRequest):
    print("📝 [系统日志] 收到简历提取请求")

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

    ai_response = client.chat.completions.create(
        model="glm-4-flash",
        messages=[
            {"role": "system", "content": system_instruction},
            {"role": "user", "content": f"请提取以下文本中的画像信息：\n{request.text_content}"}
        ],
        temperature=0.1
    )

    ai_content = ai_response.choices[0].message.content

    try:
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
        profile = UserProfile()

    missing_fields = []
    if not profile.education_level: missing_fields.append("学历")
    if not profile.major: missing_fields.append("专业")
    if not profile.grade: missing_fields.append("年级")
    if not profile.location: missing_fields.append("期望工作地点")
    if not profile.target_roles: missing_fields.append("目标岗位")
    if not profile.current_skills: missing_fields.append("当前掌握的技能")

    next_questions = []
    if "专业" in missing_fields:
        next_questions.append("请问你的大学专业是什么呢？")
    elif "当前掌握的技能" in missing_fields:
        next_questions.append("你目前比较熟悉或者掌握了哪些专业技能？（比如：Python，Excel 等）")
    elif "目标岗位" in missing_fields:
        next_questions.append("你毕业后比较想往哪个具体的岗位或职业方向发展？")
    else:
        next_questions.append("太棒了！你的基本画像已经非常完整，现在我们可以开始进行职业推荐或差距分析了。")

    return ProfileIntakeResponse(
        profile=profile,
        missing_fields=missing_fields,
        next_questions=next_questions
    )


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


@app.post("/api/agent/career-match", response_model=CareerMatchResponse, summary="基于画像的精准职业推荐")
async def career_match_endpoint(profile: UserProfile):
    """
    输入：前端传入的 UserProfile 画像
    输出：大模型分析推荐的 3 个职业方向，及理由、匹配度
    """
    print(f"🎯 [系统日志] 收到职业推荐请求，主要专业: {profile.major}")

    # 1. 构造强制 JSON 输出的 Prompt
    # ⚠️ 为了防止 AI 固步自封，Prompt 中加入了破圈发散的指令
    system_instruction = (
        "你是一个顶级的 AI 职业规划导师。请根据用户提供的结构化画像（如专业、技能、兴趣等），为TA推荐 3 个最合适或极具潜力的职业方向。\n"
        "你可以推荐 2 个完全符合TA专业背景的传统强势岗位，并推荐 1 个稍微跳出原有框架、但符合其潜力的'新兴/破圈'岗位，以发散思维。\n"
        "你必须严格按照 JSON 格式输出，JSON 格式必须包含一个名为 'recommendations' 的数组。\n"
        "数组中的每个对象必须包含以下字段：\n"
        "- 'role_name': (字符串) 岗位名称\n"
        "- 'match_reason': (字符串) 推荐理由，必须结合用户的专业、技能和兴趣进行客观严谨的分析\n"
        "- 'confidence_score': (整数) 匹配度得分，0到100之间\n"
        "不要输出任何 Markdown 标记（如 ```json），直接输出纯 JSON 字符串！"
    )

    user_profile_json = profile.model_dump_json(exclude_none=True)

    ai_content = ""
    try:
        # 2. 调用大模型进行推理分析
        response = client.chat.completions.create(
            model="glm-4-flash",
            messages=[
                {"role": "system", "content": system_instruction},
                {"role": "user", "content": f"这是用户的详细画像数据：\n{user_profile_json}"}
            ],
            temperature=0.3  # 稍微控制温度，防止它胡思乱想
        )

        ai_content = response.choices[0].message.content.strip()

        # 3. 清洗可能存在的 Markdown 标签
        if ai_content.startswith("```json"):
            ai_content = ai_content[7:]
        if ai_content.endswith("```"):
            ai_content = ai_content[:-3]
        ai_content = ai_content.strip()

        # 4. 解析并按 Pydantic 结构校验
        extracted_data = json.loads(ai_content)
        return CareerMatchResponse(**extracted_data)

    except Exception as e:
        print(f"❌ [系统日志] 生成职业推荐 JSON 失败: {e}。原始返回: {ai_content}")
        # 异常兜底策略
        fallback = CareerRecommendationItem(
            role_name="通用管培生 / 综合岗",
            match_reason="大模型暂未能按预期解析出具体行业方向，建议从不限专业的通用性岗位开启规划。",
            confidence_score=60
        )
        return CareerMatchResponse(recommendations=[fallback])


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


@app.post("/api/agent/gap-analysis", response_model=GapAnalysisResponse, summary="岗位差距与行动计划分析")
async def gap_analysis_endpoint(request: GapAnalysisRequest):
    """
    输入：前端传入的 UserProfile 画像 + 用户选定的 Target Role
    输出：大模型化身资深HR，对比现状与目标，输出详细的差距卡片和行动指南
    """
    print(f"🔬 [系统日志] 开始执行差距分析，目标岗位: {request.target_role}")

    system_instruction = (
        "你是一个极其严谨、客观的互联网大厂资深 HR 兼职业导师。\n"
        "你需要对比【用户现状】与【目标岗位市场要求】之间的差距，提供一份诊断报告。\n"
        "请严格按 JSON 格式输出，切勿带有任何 ```json 等 Markdown 标记，必须完全符合以下结构：\n"
        "{\n"
        "  \"target_role\": \"(字符串)\",\n"
        "  \"overall_match_score\": (0-100的整数),\n"
        "  \"core_strengths\": [\"(字符串，优势1)\", \"(优势2)\"],\n"
        "  \"gaps\": [\n"
        "    {\n"
        "      \"dimension\": \"(字符串，如：硬技能/软技能/学历)\",\n"
        "      \"current_status\": \"(字符串)\",\n"
        "      \"required_status\": \"(字符串)\",\n"
        "      \"gap_degree\": \"(无差距/小差距/大差距)\",\n"
        "      \"suggestion\": \"(字符串，如何提升的建议)\"\n"
        "    }\n"
        "  ],\n"
        "  \"immediate_next_steps\": [\"(字符串，短期行动1)\", \"(行动2)\"]\n"
        "}"
    )

    user_data_str = request.profile.model_dump_json(exclude_none=True)
    user_prompt = f"目标岗位：{request.target_role}\n用户现状：{user_data_str}\n请帮TA进行残酷但具有建设性的差距分析。"

    # 【新增】将核心逻辑放入 try 块中
    try:
        response = client.chat.completions.create(
            model="glm-4-flash",
            messages=[
                {"role": "system", "content": system_instruction},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.1  # 降低温度，让 AI 严格按照格式输出，不瞎编
        )

        ai_content = response.choices[0].message.content.strip()

        # 【新增】把 AI 返回的东西打印到 PyCharm 的控制台，方便我们 Debug
        print(f"🤖 [系统日志] 大模型原始返回内容：\n{ai_content}")

        # 清洗可能存在的 Markdown 标记
        if ai_content.startswith("```json"):
            ai_content = ai_content[7:]
        if ai_content.endswith("```"):
            ai_content = ai_content[:-3]
        ai_content = ai_content.strip()

        extracted_data = json.loads(ai_content)

        # 返回成功数据
        return GapAnalysisResponse(**extracted_data)

    except json.JSONDecodeError as json_err:
        print(f"❌ [系统日志] 解析 AI 返回的 JSON 失败: {json_err}")
        return GapAnalysisResponse(
            target_role=request.target_role,
            overall_match_score=0,
            core_strengths=["系统解析失败"],
            gaps=[],
            immediate_next_steps=["AI 返回的数据不是合法的 JSON，请重新尝试生成。"]
        )
    except Exception as e:
        print(f"❌ [系统日志] 发生未知错误: {e}")
        return GapAnalysisResponse(
            target_role=request.target_role,
            overall_match_score=0,
            core_strengths=["系统未知错误"],
            gaps=[],
            immediate_next_steps=[f"错误详情: {str(e)}"]
        )

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


@app.post("/api/agent/learning-path", response_model=LearningPathResponse, summary="生成个性化学习路径")
async def learning_path_endpoint(request: LearningPathRequest):
    """
    基于用户画像和 Phase 4 的差距分析结果，生成详细的提升计划。
    """
    print(f"🔬 [系统日志] 正在为 {request.target_role} 生成学习路径...")

    system_instruction = (
        "你是一个职业规划导师。请根据用户的现状和岗位差距，提供一份分阶段的学习路线图。\n"
        "要求：严格返回 JSON 格式，不得包含 ```json 标签或任何多余文字。\n"
        "结构如下：\n"
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
        response = client.chat.completions.create(
            model="glm-4-flash",
            messages=[
                {"role": "system", "content": system_instruction},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.3
        )

        ai_content = response.choices[0].message.content.strip()

        # --- 鲁棒性处理：清洗 AI 返回的字符串 ---
        cleaned_json = ai_content
        if cleaned_json.startswith("```"):
            # 移除开头的 ```json 或 ```
            cleaned_json = cleaned_json.split("\n", 1)[-1] if "\n" in cleaned_json else cleaned_json
        if cleaned_json.endswith("```"):
            cleaned_json = cleaned_json.rsplit("```", 1)[0]
        cleaned_json = cleaned_json.strip()

        # 解析并返回
        extracted_data = json.loads(cleaned_json)
        return LearningPathResponse(**extracted_data)

    except Exception as e:
        print(f"❌ [系统日志] 路径规划失败: {e}. 原始内容: {ai_content}")
        # 降级处理：防止 500 错误，返回一个基础结构
        return LearningPathResponse(
            target_role=request.target_role,
            overall_timeline="分析中",
            roadmap=[
                RoadmapPhase(
                    time_period="短期",
                    focus="系统处理异常",
                    action_items=["请稍后重新尝试生成计划"],
                    learning_resources=[]
                )
            ]
        )


# ==========================================
# 🚀 12. [全新增] 模拟面试与打分系统 (Phase 6)
# ==========================================

class MockInterviewRequest(BaseModel):
    target_role: str = Field(..., description="目标岗位，如：Python后端开发")
    focus_area: str = Field(..., description="本次面试的考察重点，如：数据库优化、或者项目实战")


class MockInterviewQuestion(BaseModel):
    question: str = Field(..., description="面试官提出的具体问题")
    difficulty: str = Field(..., description="难度级别：基础/进阶/困难")
    interview_tips: str = Field(..., description="给用户的隐藏提示或答题思路")


@app.post("/api/agent/mock-interview/question", response_model=MockInterviewQuestion, summary="生成模拟面试题目")
async def generate_interview_question(request: MockInterviewRequest):
    """根据目标岗位和考点，生成一道专业的面试题"""
    print(f"🔬 [系统日志] 生成面试题，岗位: {request.target_role}, 考点: {request.focus_area}")

    system_instruction = (
        "你现在是互联网大厂的资深技术面试官。\n"
        "请根据用户提供的【目标岗位】和【考察重点】，生成一道极其专业的面试题。\n"
        "请严格返回 JSON 格式，切勿包含 ```json 等 Markdown 标记。\n"
        "必须严格符合结构：{\"question\": \"...\", \"difficulty\": \"...\", \"interview_tips\": \"...\"}"
    )
    prompt = f"目标岗位：{request.target_role}\n考察重点：{request.focus_area}"

    try:
        response = client.chat.completions.create(
            model="glm-4-flash",
            messages=[
                {"role": "system", "content": system_instruction},
                {"role": "user", "content": prompt}
            ],
            temperature=0.4
        )
        ai_content = response.choices[0].message.content.strip()

        # 鲁棒性清洗，防止 500 错误
        if ai_content.startswith("```"):
            ai_content = ai_content.split("\n", 1)[-1] if "\n" in ai_content else ai_content
        if ai_content.endswith("```"):
            ai_content = ai_content.rsplit("```", 1)[0]

        return MockInterviewQuestion(**json.loads(ai_content.strip()))
    except Exception as e:
        print(f"❌ [系统日志] 生成面试题出错: {e}")
        return MockInterviewQuestion(question="请简述你做过最有挑战性的项目？", difficulty="基础",
                                     interview_tips="结合 STAR 法则回答")


class MockAnswerRequest(BaseModel):
    target_role: str
    question: str = Field(..., description="刚才面试官提的问题")
    user_answer: str = Field(..., description="用户的回答内容")


class MockEvaluation(BaseModel):
    score: int = Field(..., description="回答评分 (0-100的整数)")
    evaluation: str = Field(..., description="资深面试官的详细点评")
    improvement_suggestion: str = Field(..., description="改进建议（指出缺漏点）")
    reference_answer: str = Field(..., description="满分标准参考答案")


@app.post("/api/agent/mock-interview/evaluate", response_model=MockEvaluation, summary="评估用户的面试回答")
async def evaluate_interview_answer(request: MockAnswerRequest):
    """评估用户的回答，给出得分和改进建议"""
    print(f"🔬 [系统日志] 评估面试回答，题目: {request.question}")

    system_instruction = (
        "你现在是互联网大厂的资深技术面试官。\n"
        "你需要对求职者的回答进行客观、严厉但有建设性的打分与点评，并给出满分参考答案。\n"
        "请严格返回 JSON 格式，切勿包含 ```json 等 Markdown 标记。\n"
        "必须严格符合结构：{\"score\": 85, \"evaluation\": \"...\", \"improvement_suggestion\": \"...\", \"reference_answer\": \"...\"}"
    )
    prompt = (
        f"面试岗位：{request.target_role}\n"
        f"面试题：{request.question}\n"
        f"求职者回答：{request.user_answer}\n"
        f"请给出评分、犀利点评以及满分参考答案。"
    )

    try:
        response = client.chat.completions.create(
            model="glm-4-flash",
            messages=[
                {"role": "system", "content": system_instruction},
                {"role": "user", "content": prompt}
            ],
            temperature=0.2  # 评估需要客观严谨，低温度
        )
        ai_content = response.choices[0].message.content.strip()

        # 鲁棒性清洗，防止 500 错误
        if ai_content.startswith("```"):
            ai_content = ai_content.split("\n", 1)[-1] if "\n" in ai_content else ai_content
        if ai_content.endswith("```"):
            ai_content = ai_content.rsplit("```", 1)[0]

        return MockEvaluation(**json.loads(ai_content.strip()))
    except Exception as e:
        print(f"❌ [系统日志] 评估面试回答出错: {e}")
        return MockEvaluation(score=60, evaluation="系统暂无法评分", improvement_suggestion="建议系统复习该考点",
                              reference_answer="暂无")