"""
素材采集器（Material_Collector）
负责下载商品图片和视频素材，校验完整性，去重，并生成采集报告。
"""

import asyncio
import hashlib
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

import httpx

from douyin_automation.models.domain import (
    CollectionReport,
    DownloadResult,
    TrendingProduct,
)

logger = logging.getLogger(__name__)

# 默认素材存储根目录
DEFAULT_BASE_DIR = "data/materials"

# 单文件最大重试次数（完整性校验失败时）
MAX_INTEGRITY_RETRIES = 3


class MaterialCollector:
    """
    素材采集器：下载商品图片和视频，按商品 ID 分类存储，
    支持去重、完整性校验和采集报告生成。
    """

    def __init__(self, base_dir: str = DEFAULT_BASE_DIR) -> None:
        self.base_dir = Path(base_dir)
        # 已下载 URL 的 SHA256 哈希集合，用于去重
        self._downloaded_url_hashes: set[str] = set()

    # ── 内部工具 ──────────────────────────────────────────────────────────────

    @staticmethod
    def _url_hash(url: str) -> str:
        """计算 URL 的 SHA256 哈希，用于去重键。"""
        return hashlib.sha256(url.encode()).hexdigest()

    @staticmethod
    def _file_sha256(file_path: Path) -> str:
        """计算本地文件的 SHA256 哈希值。"""
        h = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk)
        return h.hexdigest()

    def _product_dir(self, product_id: str) -> Path:
        """返回商品素材存储目录（base_dir / product_id），并确保目录存在。"""
        d = self.base_dir / product_id
        d.mkdir(parents=True, exist_ok=True)
        return d

    # ── 4.3 去重 ──────────────────────────────────────────────────────────────

    def deduplicate(self, urls: list[str]) -> list[str]:
        """
        对 URL 列表去重：返回尚未下载过的 URL 列表。
        已下载的 URL（基于 SHA256 哈希）会被过滤掉。
        """
        unique: list[str] = []
        seen_in_batch: set[str] = set()
        for url in urls:
            h = self._url_hash(url)
            if h not in self._downloaded_url_hashes and h not in seen_in_batch:
                unique.append(url)
                seen_in_batch.add(h)
        return unique

    def _mark_downloaded(self, url: str) -> None:
        """将 URL 标记为已下载。"""
        self._downloaded_url_hashes.add(self._url_hash(url))

    # ── 4.4 完整性校验 ────────────────────────────────────────────────────────

    def verify_file_integrity(
        self, file_path: str, expected_hash: Optional[str] = None
    ) -> bool:
        """
        校验文件完整性：
        1. 文件必须存在且大小 > 0。
        2. 若提供了 expected_hash，则与文件 SHA256 比对。
        返回 True 表示文件完整，False 表示不完整。
        """
        p = Path(file_path)
        if not p.exists() or p.stat().st_size == 0:
            return False
        if expected_hash is not None:
            actual = self._file_sha256(p)
            return actual == expected_hash
        return True

    # ── 4.1 / 4.2 下载方法 ───────────────────────────────────────────────────

    async def _download_file(
        self,
        url: str,
        product_id: str,
        file_type: str,
        suffix: str,
    ) -> DownloadResult:
        """
        通用异步下载方法：
        - 将文件存储到 base_dir / product_id / <url_hash><suffix>
        - 下载后计算 SHA256 并校验完整性
        - 若完整性校验失败，最多重试 MAX_INTEGRITY_RETRIES 次
        """
        url_hash = self._url_hash(url)
        product_dir = self._product_dir(product_id)
        file_path = product_dir / f"{url_hash}{suffix}"

        for attempt in range(1, MAX_INTEGRITY_RETRIES + 1):
            try:
                async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
                    response = await client.get(url)
                    response.raise_for_status()
                    file_path.write_bytes(response.content)

                # 校验完整性（仅检查大小 > 0，无预期哈希时）
                if not self.verify_file_integrity(str(file_path)):
                    if attempt < MAX_INTEGRITY_RETRIES:
                        logger.warning(
                            "文件完整性校验失败，第 %d 次重试：%s", attempt, url
                        )
                        continue
                    return DownloadResult(
                        url=url,
                        product_id=product_id,
                        file_path=None,
                        success=False,
                        error_reason="文件完整性校验失败（文件为空）",
                        file_hash=None,
                    )

                file_hash = self._file_sha256(file_path)
                self._mark_downloaded(url)
                logger.info("下载成功 [%s] -> %s", file_type, file_path)
                return DownloadResult(
                    url=url,
                    product_id=product_id,
                    file_path=str(file_path),
                    success=True,
                    error_reason=None,
                    file_hash=file_hash,
                )

            except httpx.HTTPStatusError as e:
                error_reason = f"HTTP 错误 {e.response.status_code}: {url}"
                logger.warning("下载失败 [%s]：%s", file_type, error_reason)
                return DownloadResult(
                    url=url,
                    product_id=product_id,
                    file_path=None,
                    success=False,
                    error_reason=error_reason,
                    file_hash=None,
                )
            except Exception as e:
                error_reason = f"下载异常：{type(e).__name__}: {e}"
                logger.warning("下载失败 [%s]：%s", file_type, error_reason)
                return DownloadResult(
                    url=url,
                    product_id=product_id,
                    file_path=None,
                    success=False,
                    error_reason=error_reason,
                    file_hash=None,
                )

        # 不应到达此处，但作为保底
        return DownloadResult(
            url=url,
            product_id=product_id,
            file_path=None,
            success=False,
            error_reason="超过最大重试次数",
            file_hash=None,
        )

    def download_image(self, url: str, product_id: str) -> DownloadResult:
        """同步包装：下载图片（.jpg）。"""
        return asyncio.run(self._download_file(url, product_id, "image", ".jpg"))

    def download_video(self, url: str, product_id: str) -> DownloadResult:
        """同步包装：下载视频（.mp4）。"""
        return asyncio.run(self._download_file(url, product_id, "video", ".mp4"))

    async def _download_all_concurrent(
        self,
        image_urls: list[str],
        video_urls: list[str],
        product_id: str,
    ) -> list[DownloadResult]:
        """并发下载所有图片和视频。"""
        tasks = [
            self._download_file(url, product_id, "image", ".jpg")
            for url in image_urls
        ] + [
            self._download_file(url, product_id, "video", ".mp4")
            for url in video_urls
        ]
        return list(await asyncio.gather(*tasks))

    # ── 4.5 / 4.6 主流程与报告 ───────────────────────────────────────────────

    def collect_materials(
        self,
        products: list[TrendingProduct],
        image_urls_map: Optional[dict[str, list[str]]] = None,
        video_urls_map: Optional[dict[str, list[str]]] = None,
    ) -> list[CollectionReport]:
        """
        主采集流程：
        - 对每个商品，并发下载其图片和视频素材
        - 不可访问的资源跳过并记录失败原因
        - 返回每个商品的 CollectionReport 列表

        参数：
            products: 爆款商品列表
            image_urls_map: {product_id: [image_url, ...]}，可选
            video_urls_map: {product_id: [video_url, ...]}，可选
        """
        image_urls_map = image_urls_map or {}
        video_urls_map = video_urls_map or {}

        reports: list[CollectionReport] = []

        for product in products:
            pid = product.product_id
            raw_image_urls = image_urls_map.get(pid, [])
            raw_video_urls = video_urls_map.get(pid, [])

            # 去重
            image_urls = self.deduplicate(raw_image_urls)
            video_urls = self.deduplicate(raw_video_urls)

            total = len(image_urls) + len(video_urls)
            if total == 0:
                reports.append(
                    CollectionReport(
                        product_id=pid,
                        success_count=0,
                        failure_count=0,
                        failures=[],
                        generated_at=datetime.now(),
                    )
                )
                continue

            # 并发下载
            results = asyncio.run(
                self._download_all_concurrent(image_urls, video_urls, pid)
            )

            successes = [r for r in results if r.success]
            failures = [r for r in results if not r.success]

            report = CollectionReport(
                product_id=pid,
                success_count=len(successes),
                failure_count=len(failures),
                failures=failures,
                generated_at=datetime.now(),
            )
            reports.append(report)
            logger.info(
                "商品 %s 采集完成：成功 %d，失败 %d",
                pid,
                report.success_count,
                report.failure_count,
            )

        return reports
