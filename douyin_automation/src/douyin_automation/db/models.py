"""
数据库 ORM 模型定义
使用 SQLAlchemy 2.x 声明式风格定义四张核心表
"""

from datetime import datetime

from sqlalchemy import (
    TIMESTAMP,
    ForeignKey,
    Integer,
    Text,
    Float,
    String,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """所有 ORM 模型的基类"""
    pass


class Product(Base):
    """
    商品表：存储从抖音爬取的商品基本信息及综合评分
    """
    __tablename__ = "products"

    # 商品唯一标识（抖音平台商品ID）
    product_id: Mapped[str] = mapped_column(Text, primary_key=True)
    # 商品标题
    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    # 商品类目
    category: Mapped[str | None] = mapped_column(Text, nullable=True)
    # 综合评分（由商品分析器计算）
    composite_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    # 爬取时间
    crawled_at: Mapped[datetime | None] = mapped_column(TIMESTAMP, nullable=True)

    def __repr__(self) -> str:
        return f"<Product product_id={self.product_id!r} title={self.title!r}>"


class Material(Base):
    """
    素材表：存储商品关联的图片和视频素材下载记录
    """
    __tablename__ = "materials"

    # 自增主键
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # 关联商品ID（外键）
    product_id: Mapped[str | None] = mapped_column(
        Text, ForeignKey("products.product_id"), nullable=True
    )
    # 素材在本地文件系统的存储路径
    file_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    # 文件类型：'image' 或 'video'
    file_type: Mapped[str | None] = mapped_column(
        String(10), nullable=True, comment="文件类型：image | video"
    )
    # 文件内容哈希值（用于去重和完整性校验）
    file_hash: Mapped[str | None] = mapped_column(Text, nullable=True)
    # 下载完成时间
    downloaded_at: Mapped[datetime | None] = mapped_column(TIMESTAMP, nullable=True)

    def __repr__(self) -> str:
        return (
            f"<Material id={self.id} product_id={self.product_id!r} "
            f"file_type={self.file_type!r}>"
        )


class PublishLog(Base):
    """
    发布日志表：记录每次视频发布操作的结果
    """
    __tablename__ = "publish_logs"

    # 自增主键
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # 抖音平台返回的视频ID
    video_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    # 关联商品ID
    product_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    # 发布时间
    published_at: Mapped[datetime | None] = mapped_column(TIMESTAMP, nullable=True)
    # 挂载的商品链接
    product_link: Mapped[str | None] = mapped_column(Text, nullable=True)
    # 发布状态（对应 TaskStatus 枚举值）
    status: Mapped[str | None] = mapped_column(Text, nullable=True)

    def __repr__(self) -> str:
        return (
            f"<PublishLog id={self.id} video_id={self.video_id!r} "
            f"status={self.status!r}>"
        )


class TaskLog(Base):
    """
    任务执行日志表：记录每个模块每次执行的状态和耗时
    """
    __tablename__ = "task_logs"

    # 自增主键
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # 流水线运行ID（同一次完整流水线共享同一个 run_id）
    run_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    # 执行的模块名称（对应 ModuleType 枚举值）
    module: Mapped[str | None] = mapped_column(Text, nullable=True)
    # 执行状态（对应 TaskStatus 枚举值）
    status: Mapped[str | None] = mapped_column(Text, nullable=True)
    # 模块开始执行时间
    started_at: Mapped[datetime | None] = mapped_column(TIMESTAMP, nullable=True)
    # 模块执行完成时间
    finished_at: Mapped[datetime | None] = mapped_column(TIMESTAMP, nullable=True)
    # 错误信息（执行失败时记录）
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    def __repr__(self) -> str:
        return (
            f"<TaskLog id={self.id} run_id={self.run_id!r} "
            f"module={self.module!r} status={self.status!r}>"
        )
