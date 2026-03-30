# Career Planning Agent - 后端核心基建 (v2.0)

# 🚀 职业规划 Agent 后端 (Career Planning Agent Backend)

本项目是为 5 人团队开发的职业规划智能体后端系统。目前已从 Phase 1（基础基建）迭代至 **Phase 2（核心业务逻辑接入）**。系统基于 FastAPI 与智谱 AI (GLM-4) 驱动，实现了简历智能解析、记忆化对话及真实的岗位数据检索。

---

## 🌟 核心功能 (Phase 2 成果)
* 🚀Phase 1 成果回顾 ：基础框架、SQLite 数据库搭建、数据清洗
* **🤖 智能简历提取 (Profile Intake)**：对应 TDD 10.1 节。支持解析自然语言自我介绍，结构化提取学历、专业、技能等画像，并自动识别缺失信息进行智能追问。
* **💬 记忆化多轮对话**：通过 `session_id` 维护用户聊天上下文，支持与职业规划专家的连贯交流。
* **🛠️ AI 工具调用 (Function Calling)**：大模型可自主识别用户意图，通过调用本地数据库工具获取真实岗位信息，避免 AI 幻觉。
* **📊 数据分析接口**：提供高级多条件岗位搜索及专为 ECharts 准备的城市分布统计接口（`/api/jobs/stats`）。

---

## 📂 项目目录结构与脚本说明

```text
├── api/                  # API 路由层 (预留)
├── core/
│   └── database.py       # 数据库基础配置
├── data/                 # 数据存储与处理 (核心目录)
│   ├── data_to_md.py     # 功能：将原始数据转为 Markdown，方便团队直观查看数据结构
│   ├── import_jobs.py    # 状态：【暂时停用 (Reserved)】。用于导入 PostgreSQL (pgAdmin)。目前阶段统一使用轻量级 SQLite，该脚本作为后续迁移的技术储备
│   ├── test_db.py        # 状态：【暂时停用 (Reserved)】。用于测试 pgAdmin 连接，目前无需关注
│   ├── jobs-data.md      # 原始岗位数据说明
│   └── jobs-data.xls     # 原始岗位 Excel 原始表
├── models/               # 数据模型定义
│   ├── job_model.py      # 岗位数据模型
│   └── user_model.py     # 用户画像模型 (UserProfile)
├── scripts/
│   └── init_db.py        # 数据库初始化脚本
├── .env                  # 环境配置文件 (存放 ZHIPUAI_API_KEY)
├── career_project.db     # 当前使用的本地 SQLite 数据库
└── main.py               # 项目主入口：包含 5 大核心 API 接口逻辑
## 🚀 团队快速开始指南

### 1. 环境准备
推荐使用 Python 3.10+ 环境。在 PyCharm 终端运行：
```bash
# 创建并激活虚拟环境
python -m venv .venv
.\.venv\Scripts\activate

# 安装基础依赖
pip install fastapi uvicorn sqlalchemy
