# 🚀 职业规划 Agent 后端 (Career Planning Agent Backend) - 全链路版 v3.0

本项目是为 5 人团队开发的职业规划智能体后端系统。目前系统已完成从基础基建到 **Phase 6（核心业务逻辑全闭环）** 的迭代。系统基于 FastAPI 构建，由智谱 AI (GLM-4) 驱动，实现了从简历解析、岗位匹配、差距分析、路径规划到模拟面试的完整“AI 职业导师”业务流。

---

## 🌟 核心功能模块

### ✅ 阶段 1 & 2：基础基建与记忆化对话
* **🗄️ 基础框架与本地知识库**：基于 SQLite 搭建轻量级本地岗位数据库，完成数据清洗与导入。
* **🤖 智能简历提取 (Profile Intake)**：支持解析自然语言自我介绍，结构化提取学历、专业、技能等画像，并自动识别缺失信息进行智能追问。
* **💬 记忆化多轮对话**：通过 `session_id` 维护用户聊天上下文，支持与职业规划专家的连贯交流。
* **🛠️ AI 工具调用 (Function Calling)**：大模型可自主识别用户意图，调用本地数据库查询真实的薪资和岗位信息，杜绝 AI 幻觉。

### ✅ 阶段 3 & 4：精准诊断与匹配
* **🎯 智能职业推荐 (Career Match)**：基于结构化的用户画像，AI 自动推荐高度匹配的岗位，并给出匹配理由。
* **🔍 差距雷达分析 (Gap Analysis)**：将用户现状与目标岗位要求进行多维度对齐，精准指出在“专业技能”、“实战经验”等方面的差距程度（Gap Degree）。

### ✅ 阶段 5 & 6：落地执行与检验
* **🗺️ 学习路径规划 (Actionable Roadmap)**：承接差距分析结果，生成带有明确时间轴的分阶段学习计划，包含具体的行动项与学习资源推荐。
* **👔 严厉面试官对练 (Mock Interview)**：
  * **动态出题**：根据目标岗位和指定的考察重点，生成带有难度分级的专业面试题。
  * **智能打分**：对用户的回答进行深度点评，给出百分制评分、指出漏洞并附带满分参考答案。

---

## 📂 项目目录结构与脚本说明

```text
├── api/                  # API 路由层 (预留)
├── core/
│   └── database.py       # 数据库基础配置
├── data/                 # 数据存储与处理 (核心目录)
│   ├── data_to_md.py     # 功能：将原始数据转为 Markdown，方便团队直观查看数据结构
│   ├── import_jobs.py    # 状态：【暂时停用 (Reserved)】。用于导入 PostgreSQL (pgAdmin)
│   ├── test_db.py        # 状态：【暂时停用 (Reserved)】。用于测试 pgAdmin 连接，目前无需关注
│   ├── jobs-data.md      # 原始岗位数据说明
│   └── jobs-data.xls     # 原始岗位 Excel 原始表
├── models/               # 数据模型定义
│   ├── job_model.py      # 岗位数据模型
│   └── user_model.py     # 用户画像模型 (UserProfile)
├── scripts/
│   └── init_db.py        # 数据库初始化脚本
├── .env                  # 环境配置文件 (🚨 严禁提交至 GitHub，内含 API Key)
├── career_project.db     # 当前使用的本地 SQLite 数据库
├── main.py               # 项目主入口：包含 Phase 1-6 所有核心 API 接口逻辑
└── README.md             # 项目说明文档
## 🚀 团队快速开始指南

### 1. 环境准备
推荐使用 Python 3.10+ 环境。在 PyCharm 终端运行：
```bash
# 创建并激活虚拟环境
python -m venv .venv
.\.venv\Scripts\activate

# 安装基础依赖
pip install fastapi uvicorn sqlalchemy
#启动依赖
uvicorn main:app --reload
