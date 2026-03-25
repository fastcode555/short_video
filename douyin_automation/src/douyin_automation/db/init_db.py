"""
数据库初始化脚本
执行此脚本将根据 ORM 模型定义创建所有数据库表（若表已存在则跳过）。

使用方式：
    python -m douyin_automation.db.init_db
    # 或直接运行：
    python src/douyin_automation/db/init_db.py
"""

import logging

from douyin_automation.db.database import DATABASE_URL, engine
from douyin_automation.db.models import Base

# 配置日志输出
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def init_db() -> None:
    """
    创建所有在 Base.metadata 中注册的数据库表。
    使用 checkfirst=True（由 create_all 默认行为保证），已存在的表不会被重建。
    """
    logger.info("正在连接数据库：%s", DATABASE_URL)
    logger.info("开始初始化数据库表...")

    # create_all 会自动跳过已存在的表，安全可重复执行
    Base.metadata.create_all(bind=engine)

    # 列出已创建的表名，方便确认
    table_names = list(Base.metadata.tables.keys())
    logger.info("数据库初始化完成，已创建/确认以下表：%s", table_names)


if __name__ == "__main__":
    init_db()
