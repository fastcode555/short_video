"""
文案分析器（Content_Analyzer）
负责从视频数据中提取文案、统计关键词/话题标签、识别标题模式，并导出 JSON。
"""

import json
import logging
import re
from collections import Counter
from datetime import datetime

import importlib.resources
import jieba

# 修复 jieba 0.42.1 在某些环境下 pkg_resources.resource_stream 失效的问题
# 通过显式指定词典路径来初始化
try:
    import pkg_resources as _pkg
    _pkg.resource_stream  # 测试是否可用
except (ImportError, AttributeError):
    import os as _os
    _jieba_dir = _os.path.dirname(jieba.__file__)
    _dict_path = _os.path.join(_jieba_dir, "dict.txt")
    jieba.initialize(_dict_path)

from douyin_automation.crawler.crawler import RawVideo
from douyin_automation.models.domain import (
    ContentAnalysis,
    HashtagStat,
    KeywordStat,
    PatternStat,
    VideoContent,
)

logger = logging.getLogger(__name__)

# 停用词集合
_STOPWORDS = frozenset(
    "的 了 是 在 我 你 他 她 它 们 这 那 有 和 与 或 但 而 也 都 就 不 很 太 真 好 大 小 多 少".split()
)

# 情感词列表
_SENTIMENT_WORDS = ["太", "真", "超", "巨", "绝", "爆", "香", "赞", "棒", "好吃", "好用", "推荐"]

# 数字列表模式：数字 + 量词（个、款、种、件、条、步、招、点、类、样）
_NUMERIC_LIST_PATTERN = re.compile(r"\d+\s*[个款种件条步招点类样]")

# 疑问句模式：含中文问号或英文问号
_QUESTION_PATTERN = re.compile(r"[？?]")


class ContentAnalyzer:
    """
    文案分析器：提取视频文案、统计关键词/话题标签、识别标题模式、导出 JSON。
    """

    # ── 5.1 extract_content ──────────────────────────────────────────────────

    def extract_content(self, video: RawVideo) -> VideoContent | None:
        """
        从 RawVideo 对象提取标题、正文文案及全部话题标签。
        文案（title + description）均为空时返回 None 并记录日志。

        需求 3.1, 3.5
        """
        title = (video.title or "").strip()
        body = (video.description or "").strip()

        if not title and not body:
            logger.warning("视频 %s 文案缺失（title 和 description 均为空）", video.video_id)
            return None

        # 合并 hashtags 字段与正文中提取的话题标签，去重保序
        hashtags = list(video.hashtags or [])
        body_tags = re.findall(r"#\S+", body)
        seen = set(hashtags)
        for tag in body_tags:
            if tag not in seen:
                hashtags.append(tag)
                seen.add(tag)

        return VideoContent(
            video_id=video.video_id,
            title=title,
            body=body,
            hashtags=hashtags,
        )

    # ── 5.2 analyze_keywords ─────────────────────────────────────────────────

    def analyze_keywords(self, contents: list[VideoContent]) -> list[KeywordStat]:
        """
        统计关键词频率，输出前 20 个（降序）。
        使用 jieba 分词，过滤停用词、单字词和纯数字。

        需求 3.2
        """
        counter: Counter = Counter()
        for content in contents:
            text = content.title + " " + content.body
            words = jieba.cut(text)
            for word in words:
                word = word.strip()
                if (
                    len(word) >= 2
                    and not word.isdigit()
                    and word not in _STOPWORDS
                ):
                    counter[word] += 1

        top = counter.most_common(20)
        return [KeywordStat(keyword=kw, frequency=freq) for kw, freq in top]

    # ── 5.3 analyze_hashtags ─────────────────────────────────────────────────

    def analyze_hashtags(self, contents: list[VideoContent]) -> list[HashtagStat]:
        """
        统计话题标签频率，输出前 10 个（降序）。
        话题标签来源：VideoContent.hashtags 字段 + 正文中 # 开头的词。

        需求 3.3
        """
        counter: Counter = Counter()
        for content in contents:
            # 来自 hashtags 字段
            for tag in content.hashtags:
                tag = tag.strip()
                if tag.startswith("#") and len(tag) > 1:
                    counter[tag] += 1
            # 来自正文中的 #标签
            body_tags = re.findall(r"#\S+", content.body)
            for tag in body_tags:
                counter[tag] += 1

        top = counter.most_common(10)
        return [HashtagStat(hashtag=tag, frequency=freq) for tag, freq in top]

    # ── 5.4 analyze_title_patterns ───────────────────────────────────────────

    def analyze_title_patterns(self, contents: list[VideoContent]) -> list[PatternStat]:
        """
        识别标题模式并计算占比。
        模式：疑问句、数字列表、情感词。
        所有模式占比之和 = 100%（有视频时）；无视频时返回空列表。

        需求 3.4，属性 11
        """
        total = len(contents)
        if total == 0:
            return []

        question_count = 0
        numeric_count = 0
        sentiment_count = 0

        for content in contents:
            title = content.title
            if _QUESTION_PATTERN.search(title):
                question_count += 1
            if _NUMERIC_LIST_PATTERN.search(title):
                numeric_count += 1
            if any(word in title for word in _SENTIMENT_WORDS):
                sentiment_count += 1

        # 每个视频可能同时命中多个模式，"其他"补足到 100%
        # 用"命中任意模式"的视频数计算"其他"
        other_count = 0
        for content in contents:
            title = content.title
            has_question = bool(_QUESTION_PATTERN.search(title))
            has_numeric = bool(_NUMERIC_LIST_PATTERN.search(title))
            has_sentiment = any(word in title for word in _SENTIMENT_WORDS)
            if not (has_question or has_numeric or has_sentiment):
                other_count += 1

        # 计算各模式占比（基于视频总数）
        def pct(count: int) -> float:
            return round(count / total * 100, 4)

        patterns = [
            PatternStat(pattern_type="疑问句", count=question_count, percentage=pct(question_count)),
            PatternStat(pattern_type="数字列表", count=numeric_count, percentage=pct(numeric_count)),
            PatternStat(pattern_type="情感词", count=sentiment_count, percentage=pct(sentiment_count)),
            PatternStat(pattern_type="其他", count=other_count, percentage=pct(other_count)),
        ]

        # 修正浮点误差，使占比之和精确等于 100%
        raw_sum = sum(p.percentage for p in patterns)
        if raw_sum != 100.0:
            diff = round(100.0 - raw_sum, 4)
            # 将差值加到最大占比的模式上
            max_idx = max(range(len(patterns)), key=lambda i: patterns[i].percentage)
            patterns[max_idx] = PatternStat(
                pattern_type=patterns[max_idx].pattern_type,
                count=patterns[max_idx].count,
                percentage=round(patterns[max_idx].percentage + diff, 4),
            )

        return patterns

    # ── 5.5 export_json ──────────────────────────────────────────────────────

    def export_json(self, analysis: ContentAnalysis) -> str:
        """
        将 ContentAnalysis 序列化为 JSON 字符串。
        datetime 使用 ISO 格式字符串。

        需求 3.6，属性 12
        """
        data = {
            "top_keywords": [
                {"keyword": ks.keyword, "frequency": ks.frequency}
                for ks in analysis.top_keywords
            ],
            "top_hashtags": [
                {"hashtag": hs.hashtag, "frequency": hs.frequency}
                for hs in analysis.top_hashtags
            ],
            "title_patterns": [
                {
                    "pattern_type": ps.pattern_type,
                    "count": ps.count,
                    "percentage": ps.percentage,
                }
                for ps in analysis.title_patterns
            ],
            "analyzed_at": analysis.analyzed_at.isoformat(),
        }
        return json.dumps(data, ensure_ascii=False, indent=2)

    @staticmethod
    def from_json(json_str: str) -> ContentAnalysis:
        """
        从 JSON 字符串反序列化为 ContentAnalysis 对象。
        用于往返序列化验证（属性 12）。
        """
        data = json.loads(json_str)
        return ContentAnalysis(
            top_keywords=[
                KeywordStat(keyword=item["keyword"], frequency=item["frequency"])
                for item in data["top_keywords"]
            ],
            top_hashtags=[
                HashtagStat(hashtag=item["hashtag"], frequency=item["frequency"])
                for item in data["top_hashtags"]
            ],
            title_patterns=[
                PatternStat(
                    pattern_type=item["pattern_type"],
                    count=item["count"],
                    percentage=item["percentage"],
                )
                for item in data["title_patterns"]
            ],
            analyzed_at=datetime.fromisoformat(data["analyzed_at"]),
        )
