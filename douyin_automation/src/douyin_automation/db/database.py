"""
数据库连接配置
支持通过环境变量 DATABASE_URL 切换 SQLite（开发）和 PostgreSQL（生产）
"""

import os

from sqlalchemy import create_engine, Engine
from sqlalchemy.orm import sessionmaker, Session

# ── 数据库 URL 配置 ────────────────────────────────────────────────────────────
# 优先读取环境变量 DATABASE_URL；未设置时默认使用 SQLite（存储在项目根目录）
_DEFAULT_SQLITE_URL = "sqlite:///./douyin_automation.db"
DATABASE_URL: str = os.getenv("DATABASE_URL", _DEFAULT_SQLITE_URL)

# ── 引擎创建 ──────────────────────────────────────────────────────────────────
def _create_engine(url: str) -> Engine:
    """
    根据数据库 URL 创建 SQLAlchemy 引擎。
    SQLite 需要额外设置 check_same_thread=False 以支持多线程访问。
    """
    if url.startswith("sqlite"):
        return create_engine(
            url,
            connect_args={"check_same_thread": False},
            echo=os.getenv("DB_ECHO", "false").lower() == "true",
        )
    # PostgreSQL 或其他数据库
    return create_engine(
        url,
        pool_pre_ping=True,   # 连接前检测连通性，避免使用失效连接
        echo=os.getenv("DB_ECHO", "false").lower() == "true",
    )


# 全局引擎实例
engine: Engine = _create_engine(DATABASE_URL)

# ── Session 工厂 ──────────────────────────────────────────────────────────────
# autocommit=False：需要显式提交事务
# autoflush=False：不自动刷新，由调用方控制
SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
)


def get_session() -> Session:
    """
    获取数据库会话。
    推荐配合 with 语句使用，确保会话在使用后被正确关闭：

        with get_session() as session:
            session.add(obj)
            session.commit()
    """
    return SessionLocal()


def get_db():
    """
    FastAPI 依赖注入用的数据库会话生成器。
    使用方式：

        @app.get("/items")
        def read_items(db: Session = Depends(get_db)):
            ...
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
