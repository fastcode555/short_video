"""
Celery 应用实例配置
定义任务队列、路由规则和重试策略
"""

import os

from celery import Celery

# ── 从环境变量读取 Broker 和 Backend 地址 ─────────────────────────────────────

# 消息代理地址，默认使用本地 Redis
CELERY_BROKER_URL = os.environ.get("CELERY_BROKER_URL", "redis://localhost:6379/0")

# 任务结果存储地址，默认使用本地 Redis
CELERY_RESULT_BACKEND = os.environ.get("CELERY_RESULT_BACKEND", "redis://localhost:6379/1")

# ── 创建 Celery 应用实例 ──────────────────────────────────────────────────────

celery_app = Celery(
    "douyin_automation",
    broker=CELERY_BROKER_URL,
    backend=CELERY_RESULT_BACKEND,
)

# ── 队列定义 ──────────────────────────────────────────────────────────────────

# 6 个模块各对应一个独立队列，实现故障隔离和独立扩缩容
TASK_QUEUES = [
    "crawler_queue",          # 爬虫模块队列
    "analyzer_queue",         # 商品分析模块队列
    "collector_queue",        # 素材采集模块队列
    "content_analyzer_queue", # 文案分析模块队列
    "generator_queue",        # 内容生成模块队列
    "publisher_queue",        # 发布模块队列
]

# ── 任务路由配置 ──────────────────────────────────────────────────────────────

# 按任务名称前缀将任务路由到对应队列
# 各模块任务命名约定：douyin_automation.<模块名>.<任务名>
TASK_ROUTES = {
    # 爬虫模块任务 → crawler_queue
    "douyin_automation.crawler.*": {"queue": "crawler_queue"},

    # 商品分析模块任务 → analyzer_queue
    "douyin_automation.analyzer.*": {"queue": "analyzer_queue"},

    # 素材采集模块任务 → collector_queue
    "douyin_automation.collector.*": {"queue": "collector_queue"},

    # 文案分析模块任务 → content_analyzer_queue
    "douyin_automation.content.*": {"queue": "content_analyzer_queue"},

    # 内容生成模块任务 → generator_queue
    "douyin_automation.generator.*": {"queue": "generator_queue"},

    # 发布模块任务 → publisher_queue
    "douyin_automation.publisher.*": {"queue": "publisher_queue"},
}

# ── Celery 配置 ───────────────────────────────────────────────────────────────

celery_app.conf.update(
    # 序列化配置：统一使用 JSON，避免 pickle 安全风险
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],

    # 任务路由：将任务分发到对应队列
    task_routes=TASK_ROUTES,

    # 默认重试策略：最多重试 3 次，每次间隔 60 秒
    task_max_retries=3,
    task_default_retry_delay=60,  # 单位：秒

    # 任务追踪：记录任务开始状态，便于监控
    task_track_started=True,

    # 延迟确认：任务执行完成后再 ACK，防止 Worker 崩溃导致任务丢失
    task_acks_late=True,

    # 时区配置
    timezone="Asia/Shanghai",
    enable_utc=True,
)
