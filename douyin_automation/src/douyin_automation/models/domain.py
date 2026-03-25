"""
核心领域数据模型
使用 Python dataclass 定义系统中所有核心数据结构
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


# ── 枚举 ──────────────────────────────────────────────────────────────────────

class TaskStatus(Enum):
    """任务状态枚举"""
    PENDING = "pending"    # 等待执行
    RUNNING = "running"    # 执行中
    SUCCESS = "success"    # 执行成功
    FAILED = "failed"      # 执行失败
    SKIPPED = "skipped"    # 已跳过


class ModuleType(Enum):
    """模块类型枚举，对应流水线中的各个处理模块"""
    CRAWLER = "crawler"                        # 爬虫模块
    PRODUCT_ANALYZER = "product_analyzer"      # 商品分析模块
    MATERIAL_COLLECTOR = "material_collector"  # 素材采集模块
    CONTENT_ANALYZER = "content_analyzer"      # 文案分析模块
    CONTENT_GENERATOR = "content_generator"    # 内容生成模块
    PUBLISHER = "publisher"                    # 发布模块


# ── 商品相关 ──────────────────────────────────────────────────────────────────

@dataclass
class RawProduct:
    """从抖音平台爬取的原始商品数据"""
    product_id: str       # 商品唯一标识
    title: str            # 商品标题
    category: str         # 商品类目
    price: float          # 商品价格
    sales_count: int      # 销量
    likes: int            # 点赞数
    comments: int         # 评论数
    shares: int           # 分享数
    crawled_at: datetime  # 爬取时间


@dataclass
class ProductMetrics:
    """商品评分指标，由商品分析器计算得出"""
    product_id: str             # 商品唯一标识
    sales_growth_rate: float    # 销量增长率
    engagement_score: float     # 互动综合评分（点赞+评论+分享加权）
    composite_score: float      # 综合评分（用于排序筛选）


@dataclass
class ScoredProduct:
    """带评分的商品，包含原始数据和计算指标"""
    product: RawProduct      # 原始商品数据
    metrics: ProductMetrics  # 商品评分指标


@dataclass
class TrendingProduct:
    """爆款候选商品，经过筛选和排序后的精简数据"""
    product_id: str         # 商品唯一标识
    title: str              # 商品标题
    category: str           # 商品类目
    composite_score: float  # 综合评分
    rank: int               # 排名（从1开始）


# ── 素材相关 ──────────────────────────────────────────────────────────────────

@dataclass
class DownloadResult:
    """单个素材文件的下载结果"""
    url: str                       # 资源原始 URL
    product_id: str                # 所属商品 ID
    file_path: Optional[str]       # 本地存储路径（失败时为 None）
    success: bool                  # 是否下载成功
    error_reason: Optional[str]    # 失败原因（成功时为 None）
    file_hash: Optional[str]       # 文件 MD5/SHA256 哈希值（用于完整性校验）


@dataclass
class CollectionReport:
    """商品素材采集汇总报告"""
    product_id: str                  # 商品唯一标识
    success_count: int               # 成功下载数量
    failure_count: int               # 失败下载数量
    failures: list[DownloadResult]   # 失败记录列表（含失败原因）
    generated_at: datetime           # 报告生成时间


# ── 文案分析相关 ──────────────────────────────────────────────────────────────

@dataclass
class VideoContent:
    """从视频中提取的文案内容"""
    video_id: str          # 视频唯一标识
    title: str             # 视频标题
    body: str              # 视频正文/描述
    hashtags: list[str]    # 话题标签列表（如 ["#好物推荐", "#抖音带货"]）


@dataclass
class KeywordStat:
    """关键词频率统计"""
    keyword: str    # 关键词
    frequency: int  # 出现频次


@dataclass
class HashtagStat:
    """话题标签频率统计"""
    hashtag: str    # 话题标签（含 # 前缀）
    frequency: int  # 出现频次


@dataclass
class PatternStat:
    """标题模式统计（如疑问句、数字列表、情感词等）"""
    pattern_type: str   # 模式类型（如 "疑问句"、"数字列表"、"情感词"）
    count: int          # 出现次数
    percentage: float   # 占比（所有模式占比之和应为 100%）


@dataclass
class ContentAnalysis:
    """文案分析结果，包含关键词、话题标签和标题模式统计"""
    top_keywords: list[KeywordStat]      # 高频关键词列表（最多20个，按频率降序）
    top_hashtags: list[HashtagStat]      # 高频话题标签列表（最多10个，按频率降序）
    title_patterns: list[PatternStat]    # 标题模式分布
    analyzed_at: datetime                # 分析完成时间


# ── 内容生成相关 ──────────────────────────────────────────────────────────────

@dataclass
class VideoScript:
    """带货视频脚本，由内容生成器根据商品和文案分析结果生成"""
    product_id: str        # 对应商品 ID
    scenes: list[str]      # 分镜场景描述列表
    duration_seconds: int  # 视频时长（秒），范围 [15, 60]
    voiceover_text: str    # 配音文案


@dataclass
class VideoCaption:
    """视频发布文案（标题+正文+话题标签）"""
    title: str                        # 视频标题
    body: str                         # 视频正文描述
    hashtags: list[str]               # 话题标签列表
    has_forbidden_words: bool = False  # 是否包含违禁词（True 时需人工审核）


# ── 发布相关 ──────────────────────────────────────────────────────────────────

@dataclass
class PublishSchedule:
    """定时发布计划"""
    times: list[str]              # 发布时间列表（如 ["10:00", "18:00", "21:00"]）
    timezone: str = "Asia/Shanghai"  # 时区，默认上海时间


@dataclass
class UploadResult:
    """视频上传结果"""
    video_id: Optional[str]       # 上传成功后的视频 ID（失败时为 None）
    success: bool                 # 是否上传成功
    error_reason: Optional[str]   # 失败原因（成功时为 None）
    retry_count: int = 0          # 已重试次数


@dataclass
class AttachResult:
    """商品链接挂载结果"""
    video_id: str                  # 视频 ID
    product_id: str                # 商品 ID
    success: bool                  # 是否挂载成功
    error_reason: Optional[str]    # 失败原因（成功时为 None）


@dataclass
class PublishLog:
    """视频发布日志记录"""
    video_id: str          # 视频 ID
    published_at: datetime # 发布时间
    product_link: str      # 挂载的商品链接
    status: TaskStatus     # 发布状态


# ── 调度相关 ──────────────────────────────────────────────────────────────────

@dataclass
class PipelineConfig:
    """流水线运行配置"""
    category_filter: Optional[str]                    # 商品类目过滤（None 表示不过滤）
    manual_review: bool = False                        # 是否启用人工审核（在内容生成后暂停）
    forbidden_words: list[str] = field(default_factory=list)  # 违禁词列表
    publish_schedule: Optional[PublishSchedule] = None  # 定时发布计划（None 表示立即发布）
    alert_email: Optional[str] = None                  # 告警邮件地址
    alert_webhook: Optional[str] = None                # 告警 Webhook URL


@dataclass
class PipelineRun:
    """流水线单次运行实例，记录整体状态和各模块状态"""
    run_id: str                                    # 运行唯一标识
    started_at: datetime                           # 启动时间
    status: TaskStatus                             # 整体运行状态
    module_statuses: dict[ModuleType, TaskStatus]  # 各模块执行状态
    failure_counts: dict[ModuleType, int]          # 各模块失败次数（用于触发告警）
