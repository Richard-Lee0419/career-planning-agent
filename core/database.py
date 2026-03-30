# core/database.py
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base
from sqlalchemy.orm import sessionmaker
import os
#数据库连接引擎!!
# 获取当前项目根目录，并定位到 data 文件夹下的数据库文件
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "data", "career_project.db")

# SQLite 连接 URL
SQLALCHEMY_DATABASE_URL = f"sqlite:///{DB_PATH}"

# 创建数据库引擎 (connect_args={"check_same_thread": False} 是 SQLite 在 FastAPI 中特有的配置)
engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)

# 创建会话工厂，用于每次请求时与数据库对话
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 创建 ORM 基类，后面的数据模型都要继承它
Base = declarative_base()

# 依赖项：用于在每次 API 请求时获取数据库连接，请求结束自动关闭
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()