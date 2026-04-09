"""
文案分析器测试
包含单元测试和属性测试（Hypothesis）
"""

import json
from datetime import datetime

import pytest
from hypothesis import given, settings, strategies as st

from douyin_automation.content.content_analyzer import ContentAnalyzer
from douyin_automation.crawler.crawler import RawVideo
from douyin_automation.models.domain import (
    ContentAnalysis,
    HashtagStat,
    KeywordStat,
    PatternStat,
    VideoContent,
)

analyzer = ContentAnalyzer()

# ── 辅助工厂函数 ──────────────────────────────────────────────────────────────

def make_raw_video(
    video_id: str = "vid_001",
    product_id: str = "prod_001",
    title: str = "测试视频标题",
    description: str = "这是一段测试描述 #好物推荐",
    hashtags: list[str] | None = None,
) -> RawVideo:
    return RawVideo(
        video_id=video_id,
        product_id=product_id,
        title=title,
        description=description,
        hashtags=hashtags or [],
        video_url="https://example.com/video.mp4",
        cover_url="https://example.com/cover.jpg",
        likes=100,
        comments=10,
        shares=5,
        crawled_at=datetime.now(),
    )


def make_video_content(
    video_id: str = "vid_001",
    title: str = "测试标题",
    body: str = "测试正文",
    hashtags: list[str] | None = None,
) -> VideoContent:
    return VideoContent(
        video_id=video_id,
        title=title,
        body=body,
        hashtags=hashtags or [],
    )


def make_content_analysis(
    top_keywords: list[KeywordStat] | None = None,
    top_hashtags: list[HashtagStat] | None = None,
    title_patterns: list[PatternStat] | None = None,
    analyzed_at: datetime | None = None,
) -> ContentAnalysis:
    return ContentAnalysis(
        top_keywords=top_keywords or [],
        top_hashtags=top_hashtags or [],
        title_patterns=title_patterns or [],
        analyzed_at=analyzed_at or datetime(2024, 1, 1, 12, 0, 0),
    )


# ── Hypothesis 策略 ───────────────────────────────────────────────────────────

# 中文字符策略
chinese_text = st.text(
    alphabet=st.characters(
        whitelist_categories=("Lu", "Ll", "Nd", "Lo"),  # Lo 包含 CJK 汉字
        whitelist_characters="，。！？#好物推荐美妆服饰食品数码",
    ),
    min_size=0,
    max_size=50,
)

video_content_strategy = st.builds(
    make_video_content,
    video_id=st.text(alphabet="abcdefghijklmnopqrstuvwxyz0123456789_", min_size=1, max_size=20),
    title=st.text(min_size=1, max_size=60),
    body=st.text(min_size=0, max_size=200),
    hashtags=st.lists(
        st.text(alphabet="abcdefghijklmnopqrstuvwxyz0123456789_#好物推荐美妆", min_size=2, max_size=15),
        min_size=0,
        max_size=5,
    ),
)

keyword_stat_strategy = st.builds(
    KeywordStat,
    keyword=st.text(min_size=1, max_size=20),
    frequency=st.integers(min_value=1, max_value=1000),
)

hashtag_stat_strategy = st.builds(
    HashtagStat,
    hashtag=st.text(min_size=2, max_size=20),
    frequency=st.integers(min_value=1, max_value=1000),
)

pattern_stat_strategy = st.builds(
    PatternStat,
    pattern_type=st.sampled_from(["疑问句", "数字列表", "情感词", "其他"]),
    count=st.integers(min_value=0, max_value=100),
    percentage=st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False),
)

content_analysis_strategy = st.builds(
    make_content_analysis,
    top_keywords=st.lists(keyword_stat_strategy, min_size=0, max_size=20),
    top_hashtags=st.lists(hashtag_stat_strategy, min_size=0, max_size=10),
    title_patterns=st.lists(pattern_stat_strategy, min_size=0, max_size=4),
    analyzed_at=st.datetimes(min_value=datetime(2020, 1, 1), max_value=datetime(2030, 12, 31)),
)


# ── 属性测试 ──────────────────────────────────────────────────────────────────

# Feature: douyin-ecommerce-automation, Property 9: 文案提取字段完整性
@given(
    st.text(min_size=1, max_size=60),  # title 非空
    st.text(min_size=0, max_size=200),  # body
    st.lists(st.text(min_size=2, max_size=20), min_size=0, max_size=5),  # hashtags
)
@settings(max_examples=100)
def test_property_9_extract_content_field_completeness(title, body, hashtags):
    """
    属性 9：对于任意包含有效文案的视频，提取结果必须同时包含 title、body、hashtags 三个字段，
    且 hashtags 为列表类型。
    Validates: Requirements 3.1
    """
    video = make_raw_video(title=title, description=body, hashtags=hashtags)
    result = analyzer.extract_content(video)

    # title 非空时必须返回 VideoContent（不为 None）
    assert result is not None
    assert hasattr(result, "title")
    assert hasattr(result, "body")
    assert hasattr(result, "hashtags")
    assert isinstance(result.hashtags, list)
    assert result.title == title.strip()
    assert result.body == body.strip()


# Feature: douyin-ecommerce-automation, Property 10: 关键词与话题标签统计排序
@given(st.lists(video_content_strategy, min_size=1, max_size=30))
@settings(max_examples=100)
def test_property_10_keywords_and_hashtags_order_and_length(contents):
    """
    属性 10：对于任意视频文案集合，输出的关键词列表长度不超过 20 且按频率降序排列；
    话题标签列表长度不超过 10 且按频率降序排列。
    Validates: Requirements 3.2, 3.3
    """
    keywords = analyzer.analyze_keywords(contents)
    hashtags = analyzer.analyze_hashtags(contents)

    # 关键词：≤20 且降序
    assert len(keywords) <= 20
    freqs = [k.frequency for k in keywords]
    assert freqs == sorted(freqs, reverse=True), f"关键词未降序：{freqs}"

    # 话题标签：≤10 且降序
    assert len(hashtags) <= 10
    hfreqs = [h.frequency for h in hashtags]
    assert hfreqs == sorted(hfreqs, reverse=True), f"话题标签未降序：{hfreqs}"


# Feature: douyin-ecommerce-automation, Property 11: 标题模式占比之和为100%
@given(st.lists(video_content_strategy, min_size=1, max_size=50))
@settings(max_examples=100)
def test_property_11_title_patterns_sum_to_100(contents):
    """
    属性 11：对于任意视频标题集合（非空），分析输出的所有模式占比之和等于 100%（±0.01%）。
    Validates: Requirements 3.4
    """
    patterns = analyzer.analyze_title_patterns(contents)

    assert len(patterns) > 0, "有视频时应返回非空模式列表"
    total_pct = sum(p.percentage for p in patterns)
    assert abs(total_pct - 100.0) <= 0.01, (
        f"模式占比之和 {total_pct:.4f}% 不等于 100%（误差超过 0.01%）"
    )


# Feature: douyin-ecommerce-automation, Property 12: 文案分析JSON往返序列化
@given(content_analysis_strategy)
@settings(max_examples=100)
def test_property_12_json_roundtrip(analysis):
    """
    属性 12：对于任意 ContentAnalysis 对象，将其序列化为 JSON 字符串后再反序列化，
    应得到与原对象等价的对象（所有字段值相等）。
    Validates: Requirements 3.6
    """
    json_str = analyzer.export_json(analysis)
    restored = ContentAnalyzer.from_json(json_str)

    # 关键词
    assert len(restored.top_keywords) == len(analysis.top_keywords)
    for orig, rest in zip(analysis.top_keywords, restored.top_keywords):
        assert rest.keyword == orig.keyword
        assert rest.frequency == orig.frequency

    # 话题标签
    assert len(restored.top_hashtags) == len(analysis.top_hashtags)
    for orig, rest in zip(analysis.top_hashtags, restored.top_hashtags):
        assert rest.hashtag == orig.hashtag
        assert rest.frequency == orig.frequency

    # 标题模式
    assert len(restored.title_patterns) == len(analysis.title_patterns)
    for orig, rest in zip(analysis.title_patterns, restored.title_patterns):
        assert rest.pattern_type == orig.pattern_type
        assert rest.count == orig.count
        assert rest.percentage == pytest.approx(orig.percentage, abs=1e-9)

    # analyzed_at（精确到微秒）
    assert restored.analyzed_at == analysis.analyzed_at


# ── 单元测试 ──────────────────────────────────────────────────────────────────

class TestExtractContent:
    """extract_content 单元测试"""

    def test_returns_video_content_with_valid_input(self):
        video = make_raw_video(
            title="好物推荐",
            description="这款产品真的很好用 #好物推荐 #美妆",
            hashtags=["#好物推荐"],
        )
        result = analyzer.extract_content(video)
        assert result is not None
        assert result.video_id == "vid_001"
        assert result.title == "好物推荐"
        assert result.body == "这款产品真的很好用 #好物推荐 #美妆"
        assert isinstance(result.hashtags, list)

    def test_returns_none_when_both_title_and_body_empty(self):
        video = make_raw_video(title="", description="", hashtags=[])
        result = analyzer.extract_content(video)
        assert result is None

    def test_returns_none_when_title_and_body_whitespace_only(self):
        video = make_raw_video(title="   ", description="  ", hashtags=[])
        result = analyzer.extract_content(video)
        assert result is None

    def test_returns_content_when_only_title_present(self):
        video = make_raw_video(title="有标题", description="", hashtags=[])
        result = analyzer.extract_content(video)
        assert result is not None
        assert result.title == "有标题"
        assert result.body == ""

    def test_returns_content_when_only_body_present(self):
        video = make_raw_video(title="", description="有正文内容", hashtags=[])
        result = analyzer.extract_content(video)
        assert result is not None
        assert result.title == ""
        assert result.body == "有正文内容"

    def test_merges_hashtags_from_field_and_body(self):
        video = make_raw_video(
            title="测试",
            description="正文 #新标签 #好物推荐",
            hashtags=["#好物推荐", "#美妆"],
        )
        result = analyzer.extract_content(video)
        assert result is not None
        # #好物推荐 已在 hashtags 字段中，不重复；#新标签 从正文提取
        assert "#好物推荐" in result.hashtags
        assert "#美妆" in result.hashtags
        assert "#新标签" in result.hashtags
        # 不重复
        assert result.hashtags.count("#好物推荐") == 1


class TestAnalyzeKeywords:
    """analyze_keywords 单元测试"""

    def test_empty_contents_returns_empty(self):
        result = analyzer.analyze_keywords([])
        assert result == []

    def test_returns_at_most_20_keywords(self):
        # 构造大量不同词汇
        contents = [
            make_video_content(title=f"商品{i}推荐购买使用效果", body=f"产品{i}质量不错值得入手")
            for i in range(50)
        ]
        result = analyzer.analyze_keywords(contents)
        assert len(result) <= 20

    def test_keywords_sorted_descending(self):
        contents = [
            make_video_content(title="推荐推荐推荐好物", body="推荐好物好物"),
        ]
        result = analyzer.analyze_keywords(contents)
        freqs = [k.frequency for k in result]
        assert freqs == sorted(freqs, reverse=True)

    def test_filters_stopwords(self):
        contents = [
            make_video_content(title="的了是在我你他她它们这那有和与或但而也都就不很太真好大小多少")
        ]
        result = analyzer.analyze_keywords(contents)
        keywords = [k.keyword for k in result]
        for stopword in ["的", "了", "是", "在", "我", "你"]:
            assert stopword not in keywords

    def test_filters_single_char_words(self):
        contents = [make_video_content(title="好 大 小 多 少 推荐购买")]
        result = analyzer.analyze_keywords(contents)
        keywords = [k.keyword for k in result]
        for single in ["好", "大", "小", "多", "少"]:
            assert single not in keywords

    def test_filters_pure_numbers(self):
        contents = [make_video_content(title="2024年新款产品推荐", body="100件好物")]
        result = analyzer.analyze_keywords(contents)
        keywords = [k.keyword for k in result]
        assert "2024" not in keywords
        assert "100" not in keywords

    def test_real_data_example(self):
        contents = [
            make_video_content(
                title="【升级版美赞臣液体钙】5桶儿童有机钙锌骨胶原酪蛋白7重营养搭配",
                body="秋冬季抓住关键成长期，又给娃安排了，还是#美赞臣 大品牌的，一天一条，好喝又营养",
                hashtags=["#美赞臣", "#液体钙"],
            )
        ]
        result = analyzer.analyze_keywords(contents)
        assert len(result) <= 20
        assert all(isinstance(k, KeywordStat) for k in result)


class TestAnalyzeHashtags:
    """analyze_hashtags 单元测试"""

    def test_empty_contents_returns_empty(self):
        result = analyzer.analyze_hashtags([])
        assert result == []

    def test_returns_at_most_10_hashtags(self):
        contents = [
            make_video_content(
                body=f"#标签{i} #标签{i+1} #标签{i+2}",
                hashtags=[f"#标签{i}", f"#标签{i+1}"],
            )
            for i in range(20)
        ]
        result = analyzer.analyze_hashtags(contents)
        assert len(result) <= 10

    def test_hashtags_sorted_descending(self):
        contents = [
            make_video_content(hashtags=["#好物推荐", "#美妆"], body="#好物推荐 #好物推荐"),
            make_video_content(hashtags=["#好物推荐"], body=""),
        ]
        result = analyzer.analyze_hashtags(contents)
        freqs = [h.frequency for h in result]
        assert freqs == sorted(freqs, reverse=True)

    def test_extracts_hashtags_from_body(self):
        contents = [
            make_video_content(body="这款产品 #好物推荐 真的很好用 #美妆测评", hashtags=[])
        ]
        result = analyzer.analyze_hashtags(contents)
        tags = [h.hashtag for h in result]
        assert "#好物推荐" in tags
        assert "#美妆测评" in tags

    def test_counts_hashtags_from_both_field_and_body(self):
        contents = [
            make_video_content(hashtags=["#好物推荐"], body="#好物推荐 正文"),
        ]
        result = analyzer.analyze_hashtags(contents)
        # hashtags 字段 1 次 + body 1 次 = 2 次
        tag_map = {h.hashtag: h.frequency for h in result}
        assert tag_map.get("#好物推荐", 0) == 2


class TestAnalyzeTitlePatterns:
    """analyze_title_patterns 单元测试"""

    def test_empty_contents_returns_empty(self):
        result = analyzer.analyze_title_patterns([])
        assert result == []

    def test_sum_of_percentages_equals_100(self):
        contents = [
            make_video_content(title="这款产品怎么样？"),
            make_video_content(title="3个必买好物推荐"),
            make_video_content(title="这款真的太好用了"),
            make_video_content(title="普通标题没有特殊模式"),
        ]
        result = analyzer.analyze_title_patterns(contents)
        total = sum(p.percentage for p in result)
        assert abs(total - 100.0) <= 0.01

    def test_detects_question_pattern(self):
        contents = [make_video_content(title="这款产品好用吗？")]
        result = analyzer.analyze_title_patterns(contents)
        pattern_map = {p.pattern_type: p for p in result}
        assert pattern_map["疑问句"].count == 1

    def test_detects_numeric_list_pattern(self):
        contents = [make_video_content(title="5个必买好物推荐")]
        result = analyzer.analyze_title_patterns(contents)
        pattern_map = {p.pattern_type: p for p in result}
        assert pattern_map["数字列表"].count == 1

    def test_detects_sentiment_pattern(self):
        contents = [make_video_content(title="这款真的太好用了")]
        result = analyzer.analyze_title_patterns(contents)
        pattern_map = {p.pattern_type: p for p in result}
        assert pattern_map["情感词"].count >= 1

    def test_single_video_all_other_gives_100_percent(self):
        contents = [make_video_content(title="普通标题")]
        result = analyzer.analyze_title_patterns(contents)
        total = sum(p.percentage for p in result)
        assert abs(total - 100.0) <= 0.01
        pattern_map = {p.pattern_type: p for p in result}
        assert pattern_map["其他"].count == 1

    def test_all_patterns_present_in_result(self):
        contents = [make_video_content(title="测试")]
        result = analyzer.analyze_title_patterns(contents)
        pattern_types = {p.pattern_type for p in result}
        assert "疑问句" in pattern_types
        assert "数字列表" in pattern_types
        assert "情感词" in pattern_types
        assert "其他" in pattern_types


class TestExportJson:
    """export_json / from_json 单元测试"""

    def test_export_json_returns_valid_json(self):
        analysis = make_content_analysis()
        json_str = analyzer.export_json(analysis)
        data = json.loads(json_str)
        assert "top_keywords" in data
        assert "top_hashtags" in data
        assert "title_patterns" in data
        assert "analyzed_at" in data

    def test_export_json_datetime_as_iso_string(self):
        dt = datetime(2024, 3, 25, 22, 46, 28, 734527)
        analysis = make_content_analysis(analyzed_at=dt)
        json_str = analyzer.export_json(analysis)
        data = json.loads(json_str)
        assert data["analyzed_at"] == dt.isoformat()

    def test_roundtrip_preserves_keywords(self):
        keywords = [KeywordStat("推荐", 10), KeywordStat("好物", 5)]
        analysis = make_content_analysis(top_keywords=keywords)
        restored = ContentAnalyzer.from_json(analyzer.export_json(analysis))
        assert len(restored.top_keywords) == 2
        assert restored.top_keywords[0].keyword == "推荐"
        assert restored.top_keywords[0].frequency == 10

    def test_roundtrip_preserves_hashtags(self):
        hashtags = [HashtagStat("#好物推荐", 8), HashtagStat("#美妆", 3)]
        analysis = make_content_analysis(top_hashtags=hashtags)
        restored = ContentAnalyzer.from_json(analyzer.export_json(analysis))
        assert len(restored.top_hashtags) == 2
        assert restored.top_hashtags[0].hashtag == "#好物推荐"

    def test_roundtrip_preserves_patterns(self):
        patterns = [
            PatternStat("疑问句", 3, 30.0),
            PatternStat("情感词", 7, 70.0),
        ]
        analysis = make_content_analysis(title_patterns=patterns)
        restored = ContentAnalyzer.from_json(analyzer.export_json(analysis))
        assert len(restored.title_patterns) == 2
        assert restored.title_patterns[0].pattern_type == "疑问句"
        assert restored.title_patterns[0].percentage == pytest.approx(30.0)

    def test_roundtrip_preserves_analyzed_at(self):
        dt = datetime(2024, 3, 25, 22, 46, 28, 734527)
        analysis = make_content_analysis(analyzed_at=dt)
        restored = ContentAnalyzer.from_json(analyzer.export_json(analysis))
        assert restored.analyzed_at == dt

    def test_export_json_with_real_data(self):
        """使用真实样例数据测试完整流程"""
        video = make_raw_video(
            video_id="feigua_01_",
            title="【升级版美赞臣液体钙】5桶儿童有机钙锌骨胶原酪蛋白7重营养搭配",
            description=(
                "秋冬季抓住关键成长期，又给娃安排了，还是#美赞臣 大品牌的，"
                "一天一条，好喝又营养#液体钙 #美赞臣钙锌维生素 #宝妈推荐 #母婴好物\n"
                "有条件的家庭还是应该给孩子安排上！！！ #育儿 #美赞臣学优力液体钙"
            ),
            hashtags=["#美赞臣", "#液体钙"],
        )
        content = analyzer.extract_content(video)
        assert content is not None

        contents = [content]
        keywords = analyzer.analyze_keywords(contents)
        hashtags_result = analyzer.analyze_hashtags(contents)
        patterns = analyzer.analyze_title_patterns(contents)

        analysis = ContentAnalysis(
            top_keywords=keywords,
            top_hashtags=hashtags_result,
            title_patterns=patterns,
            analyzed_at=datetime(2024, 3, 25, 22, 46, 28),
        )

        json_str = analyzer.export_json(analysis)
        restored = ContentAnalyzer.from_json(json_str)

        assert len(restored.top_keywords) == len(keywords)
        assert len(restored.top_hashtags) == len(hashtags_result)
        assert restored.analyzed_at == analysis.analyzed_at
