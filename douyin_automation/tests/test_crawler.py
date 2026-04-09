"""
爬虫模块测试
包含属性测试（Hypothesis）和单元测试
"""

import logging
import threading
import time
from datetime import datetime
from unittest.mock import MagicMock, patch, PropertyMock

import httpx
import pytest
from hypothesis import given, settings, strategies as st

from douyin_automation.crawler.crawler import Crawler, RawVideo
from douyin_automation.crawler.rate_limiter import RateLimiter
from douyin_automation.models.domain import RawProduct


# ── 属性测试 ──────────────────────────────────────────────────────────────────

# Feature: douyin-ecommerce-automation, Property 3: 爬虫重试次数上限
# 对于任意导致错误的请求，实际重试次数不超过3次
@given(st.integers(min_value=1, max_value=10))
@settings(max_examples=100)
def test_retry_count_never_exceeds_max(fail_times):
    """
    属性3：对于任意导致错误的请求，实际重试次数不超过 max_retries 次。
    Validates: Requirements 1.5
    """
    # 使用极小的 retry_delay 避免测试等待
    crawler = Crawler(max_retries=3, retry_delay=0.0)

    # 记录实际调用次数
    call_count = 0

    def mock_get(url, **kwargs):
        nonlocal call_count
        call_count += 1
        # 模拟持续返回 429 限流响应
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 429
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "429 Too Many Requests",
            request=MagicMock(),
            response=mock_response,
        )
        return mock_response

    crawler._http_client.get = mock_get

    with pytest.raises((httpx.HTTPStatusError, Exception)):
        crawler._request_with_retry("https://example.com/api")

    # 实际调用次数 = 1次初始请求 + 最多 max_retries 次重试
    # 总调用次数不超过 max_retries + 1
    assert call_count <= crawler.max_retries + 1, (
        f"调用次数 {call_count} 超过了最大允许次数 {crawler.max_retries + 1}"
    )


# Feature: douyin-ecommerce-automation, Property 4: 请求频率控制
# 对于任意连续请求，60秒窗口内请求数不超过30次
@given(st.integers(min_value=1, max_value=50))
@settings(max_examples=50)
def test_rate_limiter_never_exceeds_limit(request_count):
    """
    属性4：对于任意连续请求，任意60秒窗口内请求数不超过30次。
    Validates: Requirements 1.6
    """
    # 使用极小的窗口时间，避免测试等待，但保持逻辑正确性
    # 将窗口设为0.1秒，max_requests=5，快速验证限速逻辑
    limiter = RateLimiter(max_requests=5, window_seconds=0.1)

    # 快速发出 request_count 次请求（不实际等待超过0.1秒）
    # 通过 patch time.sleep 来避免真实等待
    with patch("time.sleep"):
        for _ in range(min(request_count, 10)):
            limiter.acquire()

    # 验证：在任意时间窗口内，请求数不超过 max_requests
    # 由于我们 patch 了 sleep，时间戳可能集中，但逻辑上限速器应该控制
    # 这里验证 get_request_count 不超过 max_requests
    count = limiter.get_request_count(window_seconds=0.1)
    assert count <= limiter.max_requests, (
        f"窗口内请求数 {count} 超过了限制 {limiter.max_requests}"
    )


# ── 单元测试 ──────────────────────────────────────────────────────────────────

class TestRateLimiter:
    """RateLimiter 单元测试"""

    def test_rate_limiter_allows_requests_within_limit(self):
        """30次以内的请求不被阻塞（在极短时间内完成）"""
        limiter = RateLimiter(max_requests=30, window_seconds=60.0)

        start = time.time()
        # 发出30次请求，应该不被阻塞
        for _ in range(30):
            limiter.acquire()
        elapsed = time.time() - start

        # 30次请求应在1秒内完成（无阻塞）
        assert elapsed < 1.0, f"30次请求耗时 {elapsed:.2f}s，超过预期（应 < 1s）"
        assert limiter.get_request_count() == 30

    def test_rate_limiter_blocks_when_limit_reached(self):
        """第31次请求会被阻塞（使用超时验证）"""
        limiter = RateLimiter(max_requests=30, window_seconds=60.0)

        # 先发出30次请求填满窗口
        for _ in range(30):
            limiter.acquire()

        # 第31次请求应该被阻塞
        # 使用线程 + 超时来验证阻塞行为
        acquired = threading.Event()

        def try_acquire():
            limiter.acquire()
            acquired.set()

        thread = threading.Thread(target=try_acquire, daemon=True)
        thread.start()

        # 等待0.2秒，第31次请求应该还在阻塞中
        acquired_within_timeout = acquired.wait(timeout=0.2)
        assert not acquired_within_timeout, "第31次请求应该被阻塞，但没有被阻塞"

        # 清理：不需要等待线程结束（daemon=True）

    def test_get_request_count_returns_correct_count(self):
        """get_request_count 返回正确的窗口内请求数"""
        limiter = RateLimiter(max_requests=30, window_seconds=60.0)

        assert limiter.get_request_count() == 0

        for i in range(5):
            limiter.acquire()

        assert limiter.get_request_count() == 5
        assert limiter.get_request_count(window_seconds=60.0) == 5


class TestCrawlerRetry:
    """Crawler 重试逻辑单元测试"""

    def test_crawler_retries_on_429(self):
        """遇到429时触发重试"""
        crawler = Crawler(max_retries=3, retry_delay=0.0)

        call_count = 0

        def mock_get(url, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                # 前两次返回429
                mock_resp = MagicMock(spec=httpx.Response)
                mock_resp.status_code = 429
                mock_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
                    "429", request=MagicMock(), response=mock_resp
                )
                return mock_resp
            else:
                # 第三次成功
                mock_resp = MagicMock(spec=httpx.Response)
                mock_resp.status_code = 200
                return mock_resp

        crawler._http_client.get = mock_get

        response = crawler._request_with_retry("https://example.com/api")
        assert response.status_code == 200
        # 应该调用了3次（2次失败 + 1次成功）
        assert call_count == 3

    def test_crawler_stops_after_max_retries(self):
        """超过最大重试次数后停止并记录日志"""
        crawler = Crawler(max_retries=3, retry_delay=0.0)

        call_count = 0

        def mock_get(url, **kwargs):
            nonlocal call_count
            call_count += 1
            mock_resp = MagicMock(spec=httpx.Response)
            mock_resp.status_code = 500
            mock_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
                "500 Internal Server Error",
                request=MagicMock(),
                response=mock_resp,
            )
            return mock_resp

        crawler._http_client.get = mock_get

        with pytest.raises(httpx.HTTPStatusError):
            crawler._request_with_retry("https://example.com/api")

        # 总调用次数 = 1次初始 + 3次重试 = 4次
        assert call_count == crawler.max_retries + 1

    def test_crawler_stops_after_max_retries_logs_error(self, caplog):
        """超过最大重试次数后记录错误日志"""
        crawler = Crawler(max_retries=2, retry_delay=0.0)

        def mock_get(url, **kwargs):
            mock_resp = MagicMock(spec=httpx.Response)
            mock_resp.status_code = 429
            mock_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
                "429", request=MagicMock(), response=mock_resp
            )
            return mock_resp

        crawler._http_client.get = mock_get

        with caplog.at_level(logging.ERROR, logger="douyin_automation.crawler.crawler"):
            with pytest.raises(httpx.HTTPStatusError):
                crawler._request_with_retry("https://example.com/api")

        # 应该有错误日志
        assert any("最大重试次数" in record.message for record in caplog.records)

    def test_retry_delay_between_retries(self):
        """重试间隔不少于配置的 retry_delay"""
        retry_delay = 0.05  # 50ms，足够测试但不会太慢
        crawler = Crawler(max_retries=2, retry_delay=retry_delay)

        call_times = []

        def mock_get(url, **kwargs):
            call_times.append(time.time())
            mock_resp = MagicMock(spec=httpx.Response)
            mock_resp.status_code = 500
            mock_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
                "500", request=MagicMock(), response=mock_resp
            )
            return mock_resp

        crawler._http_client.get = mock_get

        with pytest.raises(httpx.HTTPStatusError):
            crawler._request_with_retry("https://example.com/api")

        # 验证每次重试之间的间隔不少于 retry_delay
        assert len(call_times) >= 2
        for i in range(1, len(call_times)):
            interval = call_times[i] - call_times[i - 1]
            assert interval >= retry_delay * 0.9, (  # 允许10%误差
                f"第{i}次重试间隔 {interval:.3f}s 小于配置的 {retry_delay}s"
            )


class TestCrawlerFetch:
    """Crawler 数据抓取单元测试"""

    def test_crawler_fetch_products_returns_raw_products(self):
        """fetch_products 返回 RawProduct 列表"""
        crawler = Crawler()
        products = crawler.fetch_products()

        assert isinstance(products, list)
        assert len(products) > 0
        for product in products:
            assert isinstance(product, RawProduct)
            assert product.product_id
            assert product.title
            assert product.category
            assert isinstance(product.sales_count, int)
            assert isinstance(product.likes, int)
            assert isinstance(product.comments, int)
            assert isinstance(product.shares, int)
            assert isinstance(product.crawled_at, datetime)

    def test_crawler_fetch_products_with_category_filter(self):
        """fetch_products 支持按类目过滤"""
        crawler = Crawler()

        beauty_products = crawler.fetch_products(category="美妆")
        assert all(p.category == "美妆" for p in beauty_products)

        food_products = crawler.fetch_products(category="食品")
        assert all(p.category == "食品" for p in food_products)

        # 不存在的类目返回空列表
        empty = crawler.fetch_products(category="不存在的类目")
        assert empty == []

    def test_crawler_fetch_video_list_returns_raw_videos(self):
        """fetch_video_list 返回 RawVideo 列表"""
        crawler = Crawler()
        videos = crawler.fetch_video_list("prod_001")

        assert isinstance(videos, list)
        assert len(videos) > 0
        for video in videos:
            assert isinstance(video, RawVideo)
            assert video.video_id
            assert video.product_id == "prod_001"
            assert video.title
            assert isinstance(video.hashtags, list)
            assert isinstance(video.likes, int)
            assert isinstance(video.comments, int)
            assert isinstance(video.shares, int)
            assert isinstance(video.crawled_at, datetime)

    def test_crawler_fetch_video_list_empty_for_unknown_product(self):
        """未知商品 ID 返回空视频列表"""
        crawler = Crawler()
        videos = crawler.fetch_video_list("unknown_product_id")
        assert videos == []

    def test_crawler_fetch_product_metrics(self):
        """fetch_product_metrics 返回 ProductMetrics"""
        from douyin_automation.models.domain import ProductMetrics
        crawler = Crawler()
        metrics = crawler.fetch_product_metrics("prod_001")

        assert isinstance(metrics, ProductMetrics)
        assert metrics.product_id == "prod_001"
        assert isinstance(metrics.sales_growth_rate, float)
        assert isinstance(metrics.engagement_score, float)
        assert isinstance(metrics.composite_score, float)

    def test_crawler_uses_rate_limiter(self):
        """fetch_products 调用时会触发频率限制器"""
        mock_limiter = MagicMock(spec=RateLimiter)
        crawler = Crawler(rate_limiter=mock_limiter)

        crawler.fetch_products()

        # 确认 acquire 被调用了一次
        mock_limiter.acquire.assert_called_once()

    def test_crawler_fetch_video_list_uses_rate_limiter(self):
        """fetch_video_list 调用时会触发频率限制器"""
        mock_limiter = MagicMock(spec=RateLimiter)
        crawler = Crawler(rate_limiter=mock_limiter)

        crawler.fetch_video_list("prod_001")

        mock_limiter.acquire.assert_called_once()
