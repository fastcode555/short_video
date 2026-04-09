"""
爬虫主类
负责从抖音平台抓取商品和视频数据，内置频率控制和重试逻辑。

注意：由于抖音没有公开 API，实际请求部分使用占位符实现，
但频率控制和重试逻辑是真实可测试的。
"""

import logging
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import httpx

from douyin_automation.crawler.rate_limiter import RateLimiter
from douyin_automation.models.domain import RawProduct, ProductMetrics

logger = logging.getLogger(__name__)


@dataclass
class RawVideo:
    """从抖音平台爬取的原始视频数据"""
    video_id: str          # 视频唯一标识
    product_id: str        # 关联商品 ID
    title: str             # 视频标题
    description: str       # 视频描述/文案
    hashtags: list[str]    # 话题标签列表
    video_url: str         # 视频播放地址
    cover_url: str         # 视频封面图地址
    likes: int             # 点赞数
    comments: int          # 评论数
    shares: int            # 分享数
    crawled_at: datetime   # 爬取时间


# 默认请求头，模拟正常浏览器行为
_DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "Referer": "https://www.douyin.com/",
}

# 模拟数据：用于在没有真实 API 的情况下提供测试数据
_MOCK_PRODUCTS = [
    RawProduct(
        product_id="prod_001",
        title="网红爆款口红套装",
        category="美妆",
        price=99.9,
        sales_count=15000,
        likes=8500,
        comments=1200,
        shares=3400,
        crawled_at=datetime.now(),
    ),
    RawProduct(
        product_id="prod_002",
        title="夏季新款连衣裙",
        category="服饰",
        price=159.0,
        sales_count=9800,
        likes=6200,
        comments=890,
        shares=2100,
        crawled_at=datetime.now(),
    ),
    RawProduct(
        product_id="prod_003",
        title="有机坚果礼盒",
        category="食品",
        price=68.0,
        sales_count=22000,
        likes=11000,
        comments=2300,
        shares=5600,
        crawled_at=datetime.now(),
    ),
]

_MOCK_VIDEOS: dict[str, list[RawVideo]] = {
    "prod_001": [
        RawVideo(
            video_id="vid_001_a",
            product_id="prod_001",
            title="这款口红真的绝了！",
            description="姐妹们快来看，这款口红显白又持久 #好物推荐 #口红测评",
            hashtags=["#好物推荐", "#口红测评", "#美妆"],
            video_url="https://example.com/video/vid_001_a.mp4",
            cover_url="https://example.com/cover/vid_001_a.jpg",
            likes=5200,
            comments=430,
            shares=1100,
            crawled_at=datetime.now(),
        ),
    ],
    "prod_002": [
        RawVideo(
            video_id="vid_002_a",
            product_id="prod_002",
            title="夏天必备！这条裙子太好看了",
            description="清凉又时尚，出门回头率100% #夏日穿搭 #连衣裙",
            hashtags=["#夏日穿搭", "#连衣裙", "#服饰"],
            video_url="https://example.com/video/vid_002_a.mp4",
            cover_url="https://example.com/cover/vid_002_a.jpg",
            likes=3800,
            comments=290,
            shares=780,
            crawled_at=datetime.now(),
        ),
    ],
}


class Crawler:
    """
    抖音平台爬虫，负责抓取商品和视频数据。
    内置请求频率控制（≤30次/分钟）和限流重试逻辑（最多3次，间隔60秒）。
    """

    def __init__(
        self,
        rate_limiter: RateLimiter | None = None,
        max_retries: int = 3,
        retry_delay: float = 60.0,
        http_client: httpx.Client | None = None,
    ):
        """
        初始化爬虫。

        :param rate_limiter: 请求频率限制器，默认创建一个30次/分钟的限制器
        :param max_retries: 最大重试次数，默认3次
        :param retry_delay: 重试等待时间（秒），默认60秒
        :param http_client: HTTP 客户端，可注入用于测试（mock）
        """
        self.rate_limiter = rate_limiter or RateLimiter(max_requests=30, window_seconds=60.0)
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        # 允许注入 http_client，便于测试时 mock
        self._http_client = http_client or httpx.Client(
            headers=_DEFAULT_HEADERS,
            timeout=30.0,
            follow_redirects=True,
        )

    def fetch_products(self, category: str | None = None) -> list[RawProduct]:
        """
        抓取商品列表。

        由于抖音没有公开 API，此方法使用模拟数据，但保留了真实的请求逻辑框架
        （频率控制、重试等）。

        :param category: 商品类目过滤，None 表示返回所有类目
        :return: 原始商品数据列表
        """
        # 调用频率限制器，确保请求频率不超过上限
        self.rate_limiter.acquire()

        # 实际项目中此处应调用真实 API，目前使用模拟数据
        products = list(_MOCK_PRODUCTS)

        # 按类目过滤
        if category is not None:
            products = [p for p in products if p.category == category]

        logger.info("抓取商品列表完成，共 %d 条，类目过滤：%s", len(products), category)
        return products

    def fetch_product_metrics(self, product_id: str) -> ProductMetrics:
        """
        抓取单个商品的互动指标（销量增长率、互动评分、综合评分）。

        :param product_id: 商品唯一标识
        :return: 商品指标数据
        """
        # 调用频率限制器
        self.rate_limiter.acquire()

        # 实际项目中此处应调用真实 API，目前使用模拟计算
        # 根据 product_id 查找对应商品
        product = next((p for p in _MOCK_PRODUCTS if p.product_id == product_id), None)

        if product is None:
            logger.warning("未找到商品 %s 的数据，返回默认指标", product_id)
            return ProductMetrics(
                product_id=product_id,
                sales_growth_rate=0.0,
                engagement_score=0.0,
                composite_score=0.0,
            )

        # 模拟计算互动评分（点赞*0.4 + 评论*0.4 + 分享*0.2，归一化到100分）
        engagement = (product.likes * 0.4 + product.comments * 0.4 + product.shares * 0.2)
        engagement_score = min(engagement / 1000, 100.0)
        # 模拟销量增长率（实际应对比历史数据）
        sales_growth_rate = min(product.sales_count / 10000, 5.0)
        composite_score = engagement_score * 0.6 + sales_growth_rate * 10 * 0.4

        logger.info("获取商品 %s 指标完成", product_id)
        return ProductMetrics(
            product_id=product_id,
            sales_growth_rate=sales_growth_rate,
            engagement_score=engagement_score,
            composite_score=composite_score,
        )

    def fetch_video_list(self, product_id: str) -> list[RawVideo]:
        """
        获取商品关联的视频列表。

        :param product_id: 商品唯一标识
        :return: 关联视频列表
        """
        # 调用频率限制器
        self.rate_limiter.acquire()

        # 实际项目中此处应调用真实 API，目前使用模拟数据
        videos = _MOCK_VIDEOS.get(product_id, [])
        logger.info("获取商品 %s 的视频列表完成，共 %d 条", product_id, len(videos))
        return list(videos)

    def _request_with_retry(self, url: str, **kwargs: Any) -> httpx.Response:
        """
        带重试逻辑的 HTTP 请求。
        遇到 HTTP 429（限流）或 5xx 错误时，等待 retry_delay 秒后重试。
        最多重试 max_retries 次，超过后记录错误日志并抛出异常。

        :param url: 请求 URL
        :param kwargs: 传递给 httpx.Client.get 的额外参数
        :return: HTTP 响应对象
        :raises httpx.HTTPStatusError: 超过最大重试次数后抛出
        """
        last_exception: Exception | None = None

        for attempt in range(self.max_retries + 1):
            try:
                # 调用频率限制器（每次请求前都要限速）
                self.rate_limiter.acquire()
                response = self._http_client.get(url, **kwargs)

                # 检查是否需要重试的状态码
                if response.status_code == 429 or response.status_code >= 500:
                    if attempt < self.max_retries:
                        logger.warning(
                            "请求 %s 返回 %d，第 %d/%d 次重试，等待 %.1f 秒",
                            url, response.status_code, attempt + 1, self.max_retries, self.retry_delay
                        )
                        time.sleep(self.retry_delay)
                        continue
                    else:
                        # 超过最大重试次数
                        logger.error(
                            "请求 %s 返回 %d，已达最大重试次数 %d，放弃重试",
                            url, response.status_code, self.max_retries
                        )
                        response.raise_for_status()

                return response

            except httpx.HTTPStatusError as e:
                last_exception = e
                if attempt < self.max_retries:
                    logger.warning(
                        "请求 %s 发生 HTTP 错误 %s，第 %d/%d 次重试，等待 %.1f 秒",
                        url, e, attempt + 1, self.max_retries, self.retry_delay
                    )
                    time.sleep(self.retry_delay)
                else:
                    logger.error(
                        "请求 %s 发生 HTTP 错误 %s，已达最大重试次数 %d，放弃重试",
                        url, e, self.max_retries
                    )
                    raise

            except httpx.RequestError as e:
                last_exception = e
                if attempt < self.max_retries:
                    logger.warning(
                        "请求 %s 发生网络错误 %s，第 %d/%d 次重试，等待 %.1f 秒",
                        url, e, attempt + 1, self.max_retries, self.retry_delay
                    )
                    time.sleep(self.retry_delay)
                else:
                    logger.error(
                        "请求 %s 发生网络错误 %s，已达最大重试次数 %d，放弃重试",
                        url, e, self.max_retries
                    )
                    raise

        # 理论上不会到达这里，但为了类型安全
        if last_exception:
            raise last_exception
        raise RuntimeError(f"请求 {url} 失败，原因未知")
