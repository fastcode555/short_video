"""
商品分析器测试
包含属性测试（Hypothesis）和单元测试
"""

import math
from datetime import datetime

import pytest
from hypothesis import given, settings, strategies as st

from douyin_automation.analyzer.product_analyzer import ProductAnalyzer
from douyin_automation.models.domain import (
    ProductMetrics,
    RawProduct,
    ScoredProduct,
    TrendingProduct,
)

# 全局分析器实例（无状态，可复用）
analyzer = ProductAnalyzer()


# ── 辅助工厂函数 ──────────────────────────────────────────────────────────────

def make_raw_product(
    product_id: str = "prod_001",
    title: str = "测试商品",
    category: str = "美妆",
    price: float = 99.0,
    sales_count: int = 1000,
    likes: int = 500,
    comments: int = 100,
    shares: int = 50,
) -> RawProduct:
    """创建测试用 RawProduct"""
    return RawProduct(
        product_id=product_id,
        title=title,
        category=category,
        price=price,
        sales_count=sales_count,
        likes=likes,
        comments=comments,
        shares=shares,
        crawled_at=datetime.now(),
    )


def make_scored_product(
    product_id: str = "prod_001",
    category: str = "美妆",
    composite_score: float = 50.0,
    sales_growth_rate: float = 0.5,
    engagement_score: float = 50.0,
) -> ScoredProduct:
    """创建测试用 ScoredProduct"""
    raw = make_raw_product(product_id=product_id, category=category)
    metrics = ProductMetrics(
        product_id=product_id,
        sales_growth_rate=sales_growth_rate,
        engagement_score=engagement_score,
        composite_score=composite_score,
    )
    return ScoredProduct(product=raw, metrics=metrics)


# ── Hypothesis 策略 ───────────────────────────────────────────────────────────

# 类目列表（固定集合，便于测试类目过滤完整性）
CATEGORIES = ["美妆", "服饰", "食品", "数码", "珠宝"]

# ScoredProduct 生成策略
scored_product_strategy = st.builds(
    make_scored_product,
    product_id=st.text(
        alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd")),
        min_size=1,
        max_size=20,
    ),
    category=st.sampled_from(CATEGORIES),
    composite_score=st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False),
    sales_growth_rate=st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
    engagement_score=st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False),
)

# TrendingProduct 生成策略
trending_product_strategy = st.builds(
    TrendingProduct,
    product_id=st.text(
        alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd")),
        min_size=1,
        max_size=20,
    ),
    title=st.text(min_size=1, max_size=50),
    category=st.sampled_from(CATEGORIES),
    composite_score=st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False),
    rank=st.integers(min_value=1, max_value=100),
)


# ── 属性测试 ──────────────────────────────────────────────────────────────────

# Feature: douyin-ecommerce-automation, Property 1: 商品筛选数量与排序正确性
@given(st.lists(scored_product_strategy, min_size=1, max_size=50))
@settings(max_examples=100)
def test_trending_product_count_and_order(scored_products):
    """
    属性1：对于任意非空商品评分列表，筛选出的爆款候选数量等于总数的前20%（向上取整），
    且筛选结果按综合评分严格降序排列，所有入选商品的评分均 >= 所有未入选商品的评分。
    Validates: Requirements 1.2, 1.3
    """
    result = analyzer.get_trending_products(scored_products, top_percent=0.2)

    # 验证数量：ceil(len * 0.2)，最少 1 个
    expected_count = max(1, math.ceil(len(scored_products) * 0.2))
    assert len(result) == expected_count, (
        f"筛选数量 {len(result)} != 期望 {expected_count}（总数 {len(scored_products)}）"
    )

    # 验证降序排列
    scores = [p.composite_score for p in result]
    assert scores == sorted(scores, reverse=True), (
        f"筛选结果未按综合评分降序排列：{scores}"
    )

    # 验证所有入选商品评分 >= 所有未入选商品评分
    if len(result) < len(scored_products):
        result_ids = {p.product_id for p in result}
        min_selected = min(p.composite_score for p in result)
        non_selected_scores = [
            sp.metrics.composite_score
            for sp in scored_products
            if sp.product.product_id not in result_ids
        ]
        if non_selected_scores:
            max_non_selected = max(non_selected_scores)
            assert min_selected >= max_non_selected, (
                f"入选最低分 {min_selected:.2f} < 未入选最高分 {max_non_selected:.2f}"
            )


# Feature: douyin-ecommerce-automation, Property 2: 类目过滤完整性
@given(
    st.lists(trending_product_strategy, min_size=0, max_size=30),
    st.sampled_from(CATEGORIES),
)
@settings(max_examples=100)
def test_category_filter_completeness(products, category):
    """
    属性2：对于任意商品列表和任意类目字符串，按类目过滤后的结果中，
    每一个商品的类目字段均等于指定类目，且原列表中属于该类目的商品均出现在结果中（无遗漏）。
    Validates: Requirements 1.4
    """
    result = analyzer.filter_by_category(products, category)

    # 结果中每个商品类目都匹配（大小写不敏感）
    for p in result:
        assert p.category.lower() == category.lower(), (
            f"结果中商品类目 '{p.category}' != 目标类目 '{category}'"
        )

    # 原列表中属于该类目的商品都在结果中（无遗漏）
    expected = [p for p in products if p.category.lower() == category.lower()]
    assert len(result) == len(expected), (
        f"过滤结果数量 {len(result)} != 期望数量 {len(expected)}（类目：{category}）"
    )


# ── 单元测试 ──────────────────────────────────────────────────────────────────

class TestScoreProducts:
    """score_products 方法单元测试"""

    def test_score_products_returns_scored_products(self):
        """score_products 返回 ScoredProduct 列表，类型正确"""
        products = [
            make_raw_product("p1", sales_count=1000, likes=500, comments=100, shares=50),
            make_raw_product("p2", sales_count=2000, likes=800, comments=200, shares=100),
        ]
        result = analyzer.score_products(products)

        assert isinstance(result, list)
        assert len(result) == 2
        for sp in result:
            assert isinstance(sp, ScoredProduct)
            assert isinstance(sp.product, RawProduct)
            assert isinstance(sp.metrics, ProductMetrics)

    def test_composite_score_in_valid_range(self):
        """综合评分在 [0, 100] 范围内"""
        products = [
            make_raw_product("p1", sales_count=0, likes=0, comments=0, shares=0),
            make_raw_product("p2", sales_count=99999, likes=99999, comments=99999, shares=99999),
            make_raw_product("p3", sales_count=500, likes=250, comments=50, shares=25),
        ]
        result = analyzer.score_products(products)

        for sp in result:
            score = sp.metrics.composite_score
            assert 0.0 <= score <= 100.0, (
                f"商品 {sp.product.product_id} 综合评分 {score:.2f} 超出 [0, 100] 范围"
            )

    def test_score_products_empty_input(self):
        """空列表输入返回空列表"""
        result = analyzer.score_products([])
        assert result == []

    def test_score_products_single_product(self):
        """单个商品时综合评分为 100（归一化后最大值）"""
        products = [make_raw_product("p1", sales_count=1000, likes=500, comments=100, shares=50)]
        result = analyzer.score_products(products)

        assert len(result) == 1
        # 单个商品时，互动评分和销量评分均为 100，综合评分也为 100
        assert result[0].metrics.composite_score == pytest.approx(100.0)

    def test_score_products_all_zeros(self):
        """所有指标为 0 时，综合评分为 0"""
        products = [
            make_raw_product("p1", sales_count=0, likes=0, comments=0, shares=0),
            make_raw_product("p2", sales_count=0, likes=0, comments=0, shares=0),
        ]
        result = analyzer.score_products(products)

        for sp in result:
            assert sp.metrics.composite_score == pytest.approx(0.0)

    def test_higher_engagement_gets_higher_score(self):
        """互动数据更高的商品应获得更高的综合评分"""
        products = [
            make_raw_product("low", sales_count=100, likes=10, comments=5, shares=2),
            make_raw_product("high", sales_count=100, likes=1000, comments=500, shares=200),
        ]
        result = analyzer.score_products(products)

        scores = {sp.product.product_id: sp.metrics.composite_score for sp in result}
        assert scores["high"] > scores["low"], (
            f"高互动商品评分 {scores['high']:.2f} 应 > 低互动商品评分 {scores['low']:.2f}"
        )


class TestGetTrendingProducts:
    """get_trending_products 方法单元测试"""

    def test_get_trending_products_empty_input(self):
        """空列表输入返回空列表"""
        result = analyzer.get_trending_products([])
        assert result == []

    def test_get_trending_products_single_item(self):
        """单个商品时返回 1 个（最少 1 个）"""
        products = [make_scored_product("p1", composite_score=80.0)]
        result = analyzer.get_trending_products(products, top_percent=0.2)

        assert len(result) == 1
        assert isinstance(result[0], TrendingProduct)

    def test_get_trending_products_correct_count(self):
        """筛选数量等于 ceil(total * top_percent)"""
        # 10 个商品，前 20% = ceil(10 * 0.2) = 2 个
        products = [make_scored_product(f"p{i}", composite_score=float(i)) for i in range(10)]
        result = analyzer.get_trending_products(products, top_percent=0.2)
        assert len(result) == 2

    def test_get_trending_products_sorted_descending(self):
        """筛选结果按综合评分降序排列"""
        products = [
            make_scored_product("p1", composite_score=30.0),
            make_scored_product("p2", composite_score=90.0),
            make_scored_product("p3", composite_score=60.0),
            make_scored_product("p4", composite_score=75.0),
            make_scored_product("p5", composite_score=45.0),
        ]
        result = analyzer.get_trending_products(products, top_percent=0.4)

        scores = [p.composite_score for p in result]
        assert scores == sorted(scores, reverse=True)

    def test_get_trending_products_rank_starts_from_1(self):
        """TrendingProduct 的 rank 从 1 开始"""
        products = [make_scored_product(f"p{i}", composite_score=float(i * 10)) for i in range(5)]
        result = analyzer.get_trending_products(products, top_percent=1.0)

        for i, tp in enumerate(result, start=1):
            assert tp.rank == i, f"第 {i} 个商品的 rank 应为 {i}，实际为 {tp.rank}"

    def test_get_trending_products_returns_trending_product_type(self):
        """返回值类型为 TrendingProduct"""
        products = [make_scored_product("p1", composite_score=80.0)]
        result = analyzer.get_trending_products(products)

        assert len(result) == 1
        tp = result[0]
        assert isinstance(tp, TrendingProduct)
        assert tp.product_id == "p1"
        assert tp.category == "美妆"
        assert isinstance(tp.composite_score, float)
        assert isinstance(tp.rank, int)


class TestFilterByCategory:
    """filter_by_category 方法单元测试"""

    def test_filter_by_category_no_match(self):
        """不存在的类目返回空列表"""
        products = [
            TrendingProduct("p1", "商品1", "美妆", 80.0, 1),
            TrendingProduct("p2", "商品2", "服饰", 70.0, 2),
        ]
        result = analyzer.filter_by_category(products, "不存在的类目")
        assert result == []

    def test_filter_by_category_exact_match(self):
        """精确类目匹配"""
        products = [
            TrendingProduct("p1", "商品1", "美妆", 80.0, 1),
            TrendingProduct("p2", "商品2", "服饰", 70.0, 2),
            TrendingProduct("p3", "商品3", "美妆", 60.0, 3),
        ]
        result = analyzer.filter_by_category(products, "美妆")

        assert len(result) == 2
        assert all(p.category == "美妆" for p in result)

    def test_filter_by_category_case_insensitive(self):
        """类目过滤大小写不敏感"""
        products = [
            TrendingProduct("p1", "商品1", "美妆", 80.0, 1),
            TrendingProduct("p2", "商品2", "服饰", 70.0, 2),
        ]
        # 大写输入
        result = analyzer.filter_by_category(products, "美妆")
        assert len(result) == 1

    def test_filter_by_category_empty_input(self):
        """空列表输入返回空列表"""
        result = analyzer.filter_by_category([], "美妆")
        assert result == []

    def test_filter_by_category_all_match(self):
        """所有商品都属于目标类目时全部返回"""
        products = [
            TrendingProduct("p1", "商品1", "食品", 80.0, 1),
            TrendingProduct("p2", "商品2", "食品", 70.0, 2),
            TrendingProduct("p3", "商品3", "食品", 60.0, 3),
        ]
        result = analyzer.filter_by_category(products, "食品")
        assert len(result) == 3


class TestScoreProductsWithRealData:
    """使用真实飞瓜数据测试评分"""

    def test_score_products_with_real_data(self):
        """
        用真实飞瓜数据测试评分：加载商品销售榜，验证评分结果合理。
        """
        import json
        from pathlib import Path

        from douyin_automation.crawler.feigua_crawler import FeiGuaCrawler

        # 加载真实数据文件
        data_file = Path("data/ranks/2026-03-25/商品销售榜.json")
        if not data_file.exists():
            pytest.skip("真实数据文件不存在，跳过测试")

        crawler = FeiGuaCrawler(data_dir="data/ranks")
        products = crawler.load_from_file(str(data_file))

        # 确保加载到了商品
        assert len(products) > 0, "应加载到至少 1 个商品"

        # 评分
        scored = analyzer.score_products(products)
        assert len(scored) == len(products)

        # 验证所有评分在合法范围内
        for sp in scored:
            assert 0.0 <= sp.metrics.composite_score <= 100.0
            assert 0.0 <= sp.metrics.engagement_score <= 100.0
            assert 0.0 <= sp.metrics.sales_growth_rate <= 1.0

        # 筛选爆款
        trending = analyzer.get_trending_products(scored, top_percent=0.2)
        expected_count = max(1, math.ceil(len(scored) * 0.2))
        assert len(trending) == expected_count

        # 验证排名从 1 开始
        assert trending[0].rank == 1

        # 验证降序排列
        scores = [t.composite_score for t in trending]
        assert scores == sorted(scores, reverse=True)
