"""
商品分析器
对爬取的商品数据进行评分和排序，输出爆款候选列表。
"""

import logging
import math

from douyin_automation.models.domain import (
    ProductMetrics,
    RawProduct,
    ScoredProduct,
    TrendingProduct,
)

logger = logging.getLogger(__name__)


class ProductAnalyzer:
    """
    商品分析器：对商品列表进行综合评分，筛选爆款候选，支持按类目过滤。
    """

    def score_products(self, products: list[RawProduct]) -> list[ScoredProduct]:
        """
        对商品列表进行评分，返回带评分的商品列表。

        综合评分 = 互动评分 * 0.6 + 销量评分 * 0.4

        互动评分计算（归一化到 0-100）：
          engagement = likes * 0.4 + comments * 0.4 + shares * 0.2
          engagement_score = min(engagement / max_engagement * 100, 100)

        销量评分（归一化到 0-100）：
          sales_score = min(sales_count / max_sales * 100, 100)

        销量增长率（由排名倒推，排名越靠前增长率越高）：
          sales_growth_rate = (total - rank + 1) / total（归一化到 0-1）

        :param products: 原始商品列表
        :return: 带评分的商品列表
        """
        if not products:
            return []

        total = len(products)

        # 计算每个商品的互动值
        engagements = [
            p.likes * 0.4 + p.comments * 0.4 + p.shares * 0.2
            for p in products
        ]
        max_engagement = max(engagements) if engagements else 1.0
        # 避免除以零
        if max_engagement == 0:
            max_engagement = 1.0

        # 计算最大销量（避免除以零）
        max_sales = max((p.sales_count for p in products), default=1)
        if max_sales == 0:
            max_sales = 1

        scored = []
        for rank, (product, engagement) in enumerate(zip(products, engagements), start=1):
            # 互动评分（归一化到 0-100）
            engagement_score = min(engagement / max_engagement * 100.0, 100.0)

            # 销量评分（归一化到 0-100）
            sales_score = min(product.sales_count / max_sales * 100.0, 100.0)

            # 综合评分
            composite_score = engagement_score * 0.6 + sales_score * 0.4

            # 销量增长率（由排名倒推）
            sales_growth_rate = (total - rank + 1) / total

            metrics = ProductMetrics(
                product_id=product.product_id,
                sales_growth_rate=sales_growth_rate,
                engagement_score=engagement_score,
                composite_score=composite_score,
            )
            scored.append(ScoredProduct(product=product, metrics=metrics))

        logger.info("完成 %d 个商品的评分计算", len(scored))
        return scored

    def get_trending_products(
        self,
        products: list[ScoredProduct],
        top_percent: float = 0.2,
    ) -> list[TrendingProduct]:
        """
        筛选评分前 top_percent 的商品，按综合评分降序排列。

        数量 = ceil(len(products) * top_percent)，最少 1 个。
        空列表输入返回空列表。

        :param products: 带评分的商品列表
        :param top_percent: 筛选比例，默认 0.2（前 20%）
        :return: 爆款候选商品列表（TrendingProduct），按综合评分降序
        """
        if not products:
            return []

        # 按综合评分降序排列
        sorted_products = sorted(
            products,
            key=lambda sp: sp.metrics.composite_score,
            reverse=True,
        )

        # 计算筛选数量（向上取整，最少 1 个）
        count = max(1, math.ceil(len(products) * top_percent))
        top_products = sorted_products[:count]

        # 转换为 TrendingProduct
        trending = []
        for rank, sp in enumerate(top_products, start=1):
            trending.append(
                TrendingProduct(
                    product_id=sp.product.product_id,
                    title=sp.product.title,
                    category=sp.product.category,
                    composite_score=sp.metrics.composite_score,
                    rank=rank,
                )
            )

        logger.info(
            "筛选爆款商品完成：共 %d 个（前 %.0f%%，总数 %d）",
            len(trending),
            top_percent * 100,
            len(products),
        )
        return trending

    def filter_by_category(
        self,
        products: list[TrendingProduct],
        category: str,
    ) -> list[TrendingProduct]:
        """
        按类目过滤爆款商品列表，大小写不敏感，支持部分匹配。

        :param products: 爆款商品列表
        :param category: 目标类目字符串
        :return: 过滤后的商品列表
        """
        category_lower = category.lower()
        result = [
            p for p in products
            if p.category.lower() == category_lower
        ]
        logger.info(
            "按类目 '%s' 过滤：%d → %d 个商品",
            category,
            len(products),
            len(result),
        )
        return result
