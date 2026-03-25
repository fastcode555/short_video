# 数据模型模块：定义所有核心数据结构（dataclass）

from douyin_automation.models.domain import (
    # 枚举
    TaskStatus,
    ModuleType,
    # 商品相关
    RawProduct,
    ProductMetrics,
    ScoredProduct,
    TrendingProduct,
    # 素材相关
    DownloadResult,
    CollectionReport,
    # 文案分析相关
    VideoContent,
    KeywordStat,
    HashtagStat,
    PatternStat,
    ContentAnalysis,
    # 内容生成相关
    VideoScript,
    VideoCaption,
    # 发布相关
    PublishSchedule,
    UploadResult,
    AttachResult,
    PublishLog,
    # 调度相关
    PipelineConfig,
    PipelineRun,
)

__all__ = [
    # 枚举
    "TaskStatus",
    "ModuleType",
    # 商品相关
    "RawProduct",
    "ProductMetrics",
    "ScoredProduct",
    "TrendingProduct",
    # 素材相关
    "DownloadResult",
    "CollectionReport",
    # 文案分析相关
    "VideoContent",
    "KeywordStat",
    "HashtagStat",
    "PatternStat",
    "ContentAnalysis",
    # 内容生成相关
    "VideoScript",
    "VideoCaption",
    # 发布相关
    "PublishSchedule",
    "UploadResult",
    "AttachResult",
    "PublishLog",
    # 调度相关
    "PipelineConfig",
    "PipelineRun",
]
