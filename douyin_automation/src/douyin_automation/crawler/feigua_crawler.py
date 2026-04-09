"""
飞瓜数据爬虫
从本地已抓取的飞瓜榜单 JSON 文件中加载商品数据，转换为 RawProduct 列表。
支持通过 Playwright CDP 连接已登录的 Chrome 实时抓取（可选）。
"""

import json
import logging
import os
import re
from datetime import datetime
from pathlib import Path

from douyin_automation.models.domain import RawProduct

logger = logging.getLogger(__name__)


def parse_sales_count(value: str | None) -> int:
    """
    解析销量字段，支持多种格式，统一转换为整数（取范围中间值）。

    支持格式：
    - "10w-25w"   → 175000（中间值）
    - "1000-2500" → 1750（中间值）
    - "7500-1w"   → 8750（中间值）
    - "2.5w-5w"   → 37500（中间值）
    - "26.7w"     → 267000（单值）
    - "--" 或 None → 0

    :param value: 原始销量字符串
    :return: 整数销量
    """
    if value is None or value == "--" or value == "":
        return 0

    def to_int(s: str) -> int:
        """将单个数值字符串（可能含 w 后缀）转换为整数"""
        s = s.strip()
        if s.endswith("w"):
            # 去掉 w，乘以 10000
            return int(float(s[:-1]) * 10000)
        return int(float(s))

    # 匹配范围格式：如 "10w-25w"、"1000-2500"、"7500-1w"、"2.5w-5w"
    range_pattern = re.match(r"^([\d\.]+w?)\s*-\s*([\d\.]+w?)$", value.strip())
    if range_pattern:
        low = to_int(range_pattern.group(1))
        high = to_int(range_pattern.group(2))
        return (low + high) // 2

    # 匹配单值格式：如 "26.7w"、"1000"
    single_pattern = re.match(r"^([\d\.]+w?)$", value.strip())
    if single_pattern:
        return to_int(single_pattern.group(1))

    logger.warning("无法解析销量字段：%s，返回 0", value)
    return 0


class FeiGuaCrawler:
    """
    飞瓜数据爬虫。
    主要功能：从本地 JSON 文件加载已抓取的榜单数据，转换为 RawProduct 列表。
    可选功能：通过 Playwright CDP 连接已登录的 Chrome 实时抓取。
    """

    def __init__(self, data_dir: str = "data/ranks"):
        """
        初始化飞瓜爬虫。

        :param data_dir: 榜单数据根目录，默认为 data/ranks
        """
        self.data_dir = Path(data_dir)

    def _find_latest_date_dir(self) -> Path | None:
        """
        在 data_dir 下查找最新日期的子目录（格式 YYYY-MM-DD）。

        :return: 最新日期目录路径，若不存在则返回 None
        """
        if not self.data_dir.exists():
            logger.warning("数据目录不存在：%s", self.data_dir)
            return None

        # 找出所有符合日期格式的子目录
        date_dirs = []
        for entry in self.data_dir.iterdir():
            if entry.is_dir() and re.match(r"^\d{4}-\d{2}-\d{2}$", entry.name):
                date_dirs.append(entry)

        if not date_dirs:
            logger.warning("未找到任何日期目录：%s", self.data_dir)
            return None

        # 按目录名（日期字符串）降序排列，取最新
        date_dirs.sort(key=lambda d: d.name, reverse=True)
        return date_dirs[0]

    def load_from_file(self, file_path: str, category: str | None = None) -> list[RawProduct]:
        """
        从指定 JSON 文件加载商品数据，转换为 RawProduct 列表。

        :param file_path: JSON 文件路径
        :param category: 类目过滤（None 表示不过滤）
        :return: RawProduct 列表
        """
        path = Path(file_path)
        if not path.exists():
            logger.error("文件不存在：%s", file_path)
            return []

        with open(path, encoding="utf-8") as f:
            data = json.load(f)

        items = data.get("items", [])
        crawled_at = datetime.now()

        # 尝试从文件中解析日期
        date_str = data.get("date")
        if date_str:
            try:
                crawled_at = datetime.strptime(date_str, "%Y-%m-%d")
            except ValueError:
                pass

        products = []
        for item in items:
            # 跳过无效条目（name 为空或仅含数字的分页控件行）
            name = item.get("name", "").strip()
            if not name or re.match(r"^\d+$", name):
                continue

            rank = item.get("rank", 0)
            product_id = f"feigua_{rank:02d}_{re.sub(r'[^a-zA-Z0-9]', '', name[:10])}"

            # 解析销量
            sales_count = parse_sales_count(item.get("sales_count"))

            # 解析浏览量（作为 likes 的近似值，飞瓜数据无点赞数）
            views_raw = item.get("views")
            views = parse_sales_count(views_raw) if views_raw else 0

            # 解析带货达人数（作为 shares 的近似值）
            kol_count_raw = item.get("kol_count")
            kol_count = int(kol_count_raw) if kol_count_raw and kol_count_raw.isdigit() else 0

            # 解析直播数（作为 comments 的近似值）
            live_count_raw = item.get("live_count")
            live_count = int(live_count_raw) if live_count_raw and live_count_raw.isdigit() else 0

            # 从商品名称推断类目（飞瓜商品销售榜无类目字段，用关键词匹配）
            inferred_category = _infer_category(name)

            product = RawProduct(
                product_id=product_id,
                title=name,
                category=inferred_category,
                price=0.0,  # 飞瓜榜单无价格字段
                sales_count=sales_count,
                likes=views,       # 用浏览量近似
                comments=live_count,  # 用直播数近似
                shares=kol_count,  # 用达人数近似
                crawled_at=crawled_at,
            )
            products.append(product)

        # 按类目过滤
        if category is not None:
            products = [p for p in products if p.category == category]

        logger.info("从文件 %s 加载 %d 个商品（类目过滤：%s）", file_path, len(products), category)
        return products

    def fetch_products(self, category: str | None = None) -> list[RawProduct]:
        """
        读取最新日期目录下的商品销售榜 JSON，转换为 RawProduct 列表。

        :param category: 类目过滤（None 表示不过滤）
        :return: RawProduct 列表
        """
        latest_dir = self._find_latest_date_dir()
        if latest_dir is None:
            logger.warning("未找到榜单数据目录，返回空列表")
            return []

        rank_file = latest_dir / "商品销售榜.json"
        if not rank_file.exists():
            logger.warning("未找到商品销售榜文件：%s", rank_file)
            return []

        logger.info("加载最新榜单数据：%s", rank_file)
        return self.load_from_file(str(rank_file), category=category)


# 类目关键词映射表（用于从商品名称推断类目）
_CATEGORY_KEYWORDS: list[tuple[str, list[str]]] = [
    ("美妆", ["口红", "粉底", "眼影", "护肤", "面膜", "精华", "防晒", "美妆", "化妆", "香水", "眼霜", "乳液"]),
    ("服饰", ["连衣裙", "T恤", "裤子", "外套", "衬衫", "裙", "衣", "裤", "鞋", "包", "帽", "袜", "内衣"]),
    ("食品", ["零食", "坚果", "饼干", "糖果", "茶", "咖啡", "饮料", "食品", "烤肠", "火腿", "肉", "米", "面"]),
    ("数码", ["手机", "耳机", "平板", "电脑", "相机", "充电", "数码", "小米", "华为", "苹果", "iPhone"]),
    ("珠宝", ["黄金", "金条", "金豆", "足金", "珠宝", "钻石", "翡翠", "玉", "银", "铂金"]),
    ("运动", ["跑步", "健身", "瑜伽", "运动", "球", "钓鱼", "鱼竿", "户外", "登山", "骑行"]),
    ("家居", ["家居", "床", "沙发", "桌", "椅", "灯", "收纳", "清洁", "厨房", "卫浴"]),
    ("母婴", ["婴儿", "儿童", "宝宝", "奶粉", "尿布", "玩具", "童装", "孕妇", "钙", "营养"]),
    ("眼镜", ["眼镜", "镜架", "镜片", "太阳镜", "隐形眼镜"]),
]


def _infer_category(name: str) -> str:
    """
    根据商品名称关键词推断类目。

    :param name: 商品名称
    :return: 推断的类目字符串，无法匹配时返回 "其他"
    """
    for category, keywords in _CATEGORY_KEYWORDS:
        for kw in keywords:
            if kw in name:
                return category
    return "其他"
