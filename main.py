import sqlite3
import os
import json
import uuid
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv
from zhipuai import ZhipuAI
from typing import Optional

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
    message: str


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