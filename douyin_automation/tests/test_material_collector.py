"""
素材采集器测试
包含属性测试（Hypothesis）和单元测试
"""

import hashlib
import os
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from hypothesis import given, settings, strategies as st

from douyin_automation.collector.material_collector import MaterialCollector
from douyin_automation.models.domain import (
    CollectionReport,
    DownloadResult,
    TrendingProduct,
)

# ── 辅助工厂 ──────────────────────────────────────────────────────────────────

def make_product(product_id: str = "prod_001") -> TrendingProduct:
    return TrendingProduct(
        product_id=product_id,
        title="测试商品",
        category="美妆",
        composite_score=80.0,
        rank=1,
    )


def make_success_result(url: str, product_id: str, file_path: str) -> DownloadResult:
    return DownloadResult(
        url=url,
        product_id=product_id,
        file_path=file_path,
        success=True,
        error_reason=None,
        file_hash="abc123",
    )


def make_failure_result(url: str, product_id: str, reason: str) -> DownloadResult:
    return DownloadResult(
        url=url,
        product_id=product_id,
        file_path=None,
        success=False,
        error_reason=reason,
        file_hash=None,
    )


# ── Hypothesis 策略 ───────────────────────────────────────────────────────────

# 合法 product_id 策略（字母数字，非空）
product_id_strategy = st.text(
    alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd")),
    min_size=1,
    max_size=20,
)

# URL 策略（简单 http URL）
url_strategy = st.from_regex(
    r"https?://[a-z0-9]{3,10}\.[a-z]{2,4}/[a-z0-9_]{1,20}\.(jpg|mp4)",
    fullmatch=True,
)

# DownloadResult 策略（成功或失败）
download_result_strategy = st.one_of(
    st.builds(
        DownloadResult,
        url=url_strategy,
        product_id=product_id_strategy,
        file_path=st.just("/tmp/some_file.jpg"),
        success=st.just(True),
        error_reason=st.none(),
        file_hash=st.just("deadbeef"),
    ),
    st.builds(
        DownloadResult,
        url=url_strategy,
        product_id=product_id_strategy,
        file_path=st.none(),
        success=st.just(False),
        error_reason=st.text(min_size=1, max_size=50),
        file_hash=st.none(),
    ),
)


# ── 属性测试 ──────────────────────────────────────────────────────────────────

# Feature: douyin-ecommerce-automation, Property 5: 素材采集完整性与报告一致性
@given(st.lists(download_result_strategy, min_size=0, max_size=30))
@settings(max_examples=100)
def test_collection_report_consistency(results: list[DownloadResult]):
    """
    属性5：对于任意下载结果列表，CollectionReport 中的
    success_count + failure_count == 总尝试数，且每条失败记录均包含失败原因。
    Validates: Requirements 2.3, 2.4
    """
    from datetime import datetime

    successes = [r for r in results if r.success]
    failures = [r for r in results if not r.success]

    report = CollectionReport(
        product_id="test_pid",
        success_count=len(successes),
        failure_count=len(failures),
        failures=failures,
        generated_at=datetime.now(),
    )

    # 一致性：成功 + 失败 == 总数
    assert report.success_count + report.failure_count == len(results), (
        f"success_count({report.success_count}) + failure_count({report.failure_count}) "
        f"!= total({len(results)})"
    )

    # 每条失败记录必须包含失败原因
    for failure in report.failures:
        assert failure.error_reason is not None and failure.error_reason != "", (
            f"失败记录缺少失败原因：{failure}"
        )

    # failure_count 与 failures 列表长度一致
    assert report.failure_count == len(report.failures)


# Feature: douyin-ecommerce-automation, Property 6: 素材存储路径包含商品ID
@given(
    product_id=product_id_strategy,
    url=url_strategy,
)
@settings(max_examples=100)
def test_storage_path_contains_product_id(product_id: str, url: str):
    """
    属性6：对于任意成功下载的素材文件，其存储路径中包含对应商品的 product_id 作为目录层级。
    Validates: Requirements 2.2
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        collector = MaterialCollector(base_dir=tmpdir)

        # 模拟成功下载：直接调用 _product_dir 并构造路径
        product_dir = collector._product_dir(product_id)
        url_hash = collector._url_hash(url)
        file_path = product_dir / f"{url_hash}.jpg"

        # 验证路径中包含 product_id 作为目录层级
        path_parts = Path(str(file_path)).parts
        assert product_id in path_parts, (
            f"存储路径 {file_path} 中不包含 product_id '{product_id}' 作为目录层级"
        )

        # 验证 product_id 是路径中的一个目录（不仅仅是文件名的一部分）
        parent_parts = Path(str(file_path)).parent.parts
        assert product_id in parent_parts, (
            f"product_id '{product_id}' 不是存储路径的目录层级"
        )


# Feature: douyin-ecommerce-automation, Property 7: 素材去重幂等性
@given(
    urls=st.lists(url_strategy, min_size=1, max_size=20),
)
@settings(max_examples=100)
def test_deduplication_idempotency(urls: list[str]):
    """
    属性7：对于任意已下载的素材 URL，再次触发 deduplicate 时，
    这些 URL 不会出现在返回列表中（幂等性）。
    Validates: Requirements 2.5
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        collector = MaterialCollector(base_dir=tmpdir)

        # 第一次去重：所有 URL 都是新的
        first_pass = collector.deduplicate(urls)
        # 去重后不含重复（批次内去重）
        assert len(first_pass) == len(set(urls)), (
            f"第一次去重后应无重复：{len(first_pass)} != {len(set(urls))}"
        )

        # 模拟已下载：将所有 URL 标记为已下载
        for url in first_pass:
            collector._mark_downloaded(url)

        # 第二次去重：所有 URL 都已下载，应返回空列表
        second_pass = collector.deduplicate(urls)
        assert second_pass == [], (
            f"已下载的 URL 再次去重应返回空列表，实际返回：{second_pass}"
        )

        # 幂等性：多次调用结果一致
        third_pass = collector.deduplicate(urls)
        assert third_pass == second_pass, "多次调用 deduplicate 结果应一致（幂等）"


# Feature: douyin-ecommerce-automation, Property 8: 文件完整性校验与重下载
@given(
    content=st.binary(min_size=1, max_size=1024),
    tamper=st.booleans(),
)
@settings(max_examples=100)
def test_file_integrity_check(content: bytes, tamper: bool):
    """
    属性8：对于任意下载后的文件，若哈希值与预期不符，verify_file_integrity 返回 False；
    若哈希值匹配，返回 True。
    Validates: Requirements 2.6
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        collector = MaterialCollector(base_dir=tmpdir)

        # 写入文件
        file_path = Path(tmpdir) / "test_file.bin"
        file_path.write_bytes(content)

        # 计算正确哈希
        correct_hash = hashlib.sha256(content).hexdigest()

        if tamper:
            # 提供错误哈希：完整性校验应失败
            wrong_hash = "0" * 64  # 全零哈希，必然不匹配
            result = collector.verify_file_integrity(str(file_path), wrong_hash)
            assert result is False, (
                f"哈希不匹配时 verify_file_integrity 应返回 False"
            )
        else:
            # 提供正确哈希：完整性校验应通过
            result = collector.verify_file_integrity(str(file_path), correct_hash)
            assert result is True, (
                f"哈希匹配时 verify_file_integrity 应返回 True"
            )

        # 无预期哈希时，非空文件应通过
        result_no_hash = collector.verify_file_integrity(str(file_path), None)
        assert result_no_hash is True, (
            "无预期哈希时，非空文件应通过完整性校验"
        )


# ── 单元测试 ──────────────────────────────────────────────────────────────────

class TestDeduplicate:
    """deduplicate 方法单元测试"""

    def test_deduplicate_empty_list(self):
        """空列表返回空列表"""
        with tempfile.TemporaryDirectory() as tmpdir:
            collector = MaterialCollector(base_dir=tmpdir)
            assert collector.deduplicate([]) == []

    def test_deduplicate_removes_already_downloaded(self):
        """已下载的 URL 被过滤"""
        with tempfile.TemporaryDirectory() as tmpdir:
            collector = MaterialCollector(base_dir=tmpdir)
            url = "https://example.com/img.jpg"
            collector._mark_downloaded(url)
            result = collector.deduplicate([url])
            assert result == []

    def test_deduplicate_keeps_new_urls(self):
        """未下载的 URL 保留"""
        with tempfile.TemporaryDirectory() as tmpdir:
            collector = MaterialCollector(base_dir=tmpdir)
            urls = ["https://a.com/1.jpg", "https://b.com/2.jpg"]
            result = collector.deduplicate(urls)
            assert result == urls

    def test_deduplicate_removes_batch_duplicates(self):
        """同一批次内的重复 URL 只保留一个"""
        with tempfile.TemporaryDirectory() as tmpdir:
            collector = MaterialCollector(base_dir=tmpdir)
            url = "https://example.com/img.jpg"
            result = collector.deduplicate([url, url, url])
            assert result == [url]


class TestVerifyFileIntegrity:
    """verify_file_integrity 方法单元测试"""

    def test_nonexistent_file_returns_false(self):
        """不存在的文件返回 False"""
        collector = MaterialCollector()
        assert collector.verify_file_integrity("/nonexistent/path/file.jpg") is False

    def test_empty_file_returns_false(self):
        """空文件返回 False"""
        with tempfile.NamedTemporaryFile(delete=False) as f:
            path = f.name
        try:
            collector = MaterialCollector()
            assert collector.verify_file_integrity(path) is False
        finally:
            os.unlink(path)

    def test_valid_file_no_hash_returns_true(self):
        """有内容的文件，无预期哈希时返回 True"""
        with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as f:
            f.write(b"fake image data")
            path = f.name
        try:
            collector = MaterialCollector()
            assert collector.verify_file_integrity(path) is True
        finally:
            os.unlink(path)

    def test_valid_file_correct_hash_returns_true(self):
        """有内容的文件，哈希匹配时返回 True"""
        content = b"test content"
        expected_hash = hashlib.sha256(content).hexdigest()
        with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as f:
            f.write(content)
            path = f.name
        try:
            collector = MaterialCollector()
            assert collector.verify_file_integrity(path, expected_hash) is True
        finally:
            os.unlink(path)

    def test_valid_file_wrong_hash_returns_false(self):
        """有内容的文件，哈希不匹配时返回 False"""
        with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as f:
            f.write(b"test content")
            path = f.name
        try:
            collector = MaterialCollector()
            assert collector.verify_file_integrity(path, "wrong_hash") is False
        finally:
            os.unlink(path)


class TestProductDir:
    """_product_dir 方法单元测试"""

    def test_product_dir_contains_product_id(self):
        """存储目录路径包含 product_id"""
        with tempfile.TemporaryDirectory() as tmpdir:
            collector = MaterialCollector(base_dir=tmpdir)
            d = collector._product_dir("prod_123")
            assert "prod_123" in d.parts

    def test_product_dir_is_created(self):
        """调用后目录被创建"""
        with tempfile.TemporaryDirectory() as tmpdir:
            collector = MaterialCollector(base_dir=tmpdir)
            d = collector._product_dir("new_product")
            assert d.exists() and d.is_dir()


class TestCollectMaterials:
    """collect_materials 主流程单元测试"""

    def test_collect_materials_empty_products(self):
        """空商品列表返回空报告列表"""
        with tempfile.TemporaryDirectory() as tmpdir:
            collector = MaterialCollector(base_dir=tmpdir)
            reports = collector.collect_materials([])
            assert reports == []

    def test_collect_materials_no_urls(self):
        """商品无 URL 时返回空报告（成功/失败均为 0）"""
        with tempfile.TemporaryDirectory() as tmpdir:
            collector = MaterialCollector(base_dir=tmpdir)
            product = make_product("prod_001")
            reports = collector.collect_materials([product])
            assert len(reports) == 1
            assert reports[0].success_count == 0
            assert reports[0].failure_count == 0
            assert reports[0].product_id == "prod_001"

    def test_collect_materials_failed_download_recorded(self):
        """下载失败时记录在报告中"""
        with tempfile.TemporaryDirectory() as tmpdir:
            collector = MaterialCollector(base_dir=tmpdir)
            product = make_product("prod_fail")

            # 模拟 _download_file 抛出连接错误
            async def mock_download(url, product_id, file_type, suffix):
                return DownloadResult(
                    url=url,
                    product_id=product_id,
                    file_path=None,
                    success=False,
                    error_reason="连接超时",
                    file_hash=None,
                )

            with patch.object(collector, "_download_file", side_effect=mock_download):
                reports = collector.collect_materials(
                    [product],
                    image_urls_map={"prod_fail": ["https://example.com/img.jpg"]},
                )

            assert len(reports) == 1
            report = reports[0]
            assert report.failure_count == 1
            assert report.success_count == 0
            assert report.failures[0].error_reason == "连接超时"

    def test_collect_materials_success_download(self):
        """成功下载时记录在报告中"""
        with tempfile.TemporaryDirectory() as tmpdir:
            collector = MaterialCollector(base_dir=tmpdir)
            product = make_product("prod_ok")

            async def mock_download(url, product_id, file_type, suffix):
                fake_path = str(Path(tmpdir) / product_id / "file.jpg")
                return DownloadResult(
                    url=url,
                    product_id=product_id,
                    file_path=fake_path,
                    success=True,
                    error_reason=None,
                    file_hash="abc123",
                )

            with patch.object(collector, "_download_file", side_effect=mock_download):
                reports = collector.collect_materials(
                    [product],
                    image_urls_map={"prod_ok": ["https://example.com/img.jpg"]},
                    video_urls_map={"prod_ok": ["https://example.com/vid.mp4"]},
                )

            assert len(reports) == 1
            report = reports[0]
            assert report.success_count == 2
            assert report.failure_count == 0

    def test_collect_materials_report_consistency(self):
        """报告中 success_count + failure_count == 总尝试数"""
        with tempfile.TemporaryDirectory() as tmpdir:
            collector = MaterialCollector(base_dir=tmpdir)
            product = make_product("prod_mix")

            call_count = 0

            async def mock_download(url, product_id, file_type, suffix):
                nonlocal call_count
                call_count += 1
                # 奇数次成功，偶数次失败
                if call_count % 2 == 1:
                    return DownloadResult(
                        url=url, product_id=product_id,
                        file_path="/tmp/f.jpg", success=True,
                        error_reason=None, file_hash="abc",
                    )
                else:
                    return DownloadResult(
                        url=url, product_id=product_id,
                        file_path=None, success=False,
                        error_reason="失败", file_hash=None,
                    )

            image_urls = [f"https://example.com/img{i}.jpg" for i in range(3)]
            video_urls = [f"https://example.com/vid{i}.mp4" for i in range(2)]

            with patch.object(collector, "_download_file", side_effect=mock_download):
                reports = collector.collect_materials(
                    [product],
                    image_urls_map={"prod_mix": image_urls},
                    video_urls_map={"prod_mix": video_urls},
                )

            report = reports[0]
            total = len(image_urls) + len(video_urls)
            assert report.success_count + report.failure_count == total
