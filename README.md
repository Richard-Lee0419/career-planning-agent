# Career Planning Agent - 后端核心基建 (v1.0)

本项目是为 5 人团队开发的职业规划智能体后端系统。目前已完成 Phase 1 的基础框架搭建、数据清洗以及本地数据库持久化工作。

## 🛠️ 项目当前进展
- **后端架构**：基于 FastAPI 搭建，支持异步接口调用。
- **本地存储**：已集成 SQLite 数据库 `career_project.db`，存储当前核心岗位数据。
- **数据处理**：实现了从原始企业数据到 Markdown 及本地数据库的自动化转换流程。

## 📂 目录结构与脚本说明

### 1. 核心应用目录
- `app/`: 存放 FastAPI 核心代码，包括 `main.py` 入口及后续的 API 路由。
- `data/`: 存放核心数据库 `career_project.db`。
- `scripts/`: 包含数据库初始化脚本（如 `init_db.py`）。

### 2. 数据处理与辅助脚本 (重点关注)
- **`data/data_to_md.py`**：
  - **功能**：将企业提供的原始数据转换为 Markdown 格式。
  - **用途**：生成的 `.md` 文件方便前端（FE）和 AI 队友直观查看数据结构和内容。
- **`data/import_jobs.py`**：
  - **状态**：**暂时停用（Reserved）**。
  - **说明**：该脚本用于将数据导入本地 `pgAdmin` (PostgreSQL) 数据库。目前项目处于初期阶段，统一使用更轻量、免安装的 SQLite。当后续数据量大幅增长需要迁移至生产级数据库时，才会启用此文件。**其他团队成员目前无需关注此文件**。
- **`data/test_db.py`**：
  - **状态**：**暂时停用（Reserved）**。
  - **说明**：用于测试 `pgAdmin` 数据库的连接情况。与 `import_jobs.py` 配合使用，目前仅作技术储备，**其他团队成员无需关注**。

## 🚀 团队快速开始指南

### 1. 环境准备
推荐使用 Python 3.10+ 环境。在 PyCharm 终端运行：
```bash
# 创建并激活虚拟环境
python -m venv .venv
.\.venv\Scripts\activate

# 安装基础依赖
pip install fastapi uvicorn sqlalchemy
