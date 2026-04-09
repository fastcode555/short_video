"""
真实素材采集脚本
流程：
  1. 从飞瓜商品销售榜读取 Top N 商品
  2. 用 ProductAnalyzer 筛选爆款（前20%）
  3. 对每个爆款商品，通过 Playwright 在抖音搜索商品名
  4. 抓取商品详情页的图片、视频封面、文案
  5. 用 MaterialCollector 下载并保存素材
  6. 打印采集报告，打开素材目录

用法：
  python3 scripts/collect_real_materials.py [--top N] [--category 类目]

前提：
  Chrome 已以调试模式启动（bash scripts/start_chrome.sh）
  并已登录飞瓜和抖音
"""

import argparse
import asyncio
import json
import logging
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from douyin_automation.analyzer.product_analyzer import ProductAnalyzer
from douyin_automation.collector.material_collector import MaterialCollector
from douyin_automation.crawler.feigua_crawler import FeiGuaCrawler
from douyin_automation.models.domain import TrendingProduct

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("collect_real_materials")


# ── 抖音商品详情抓取 ──────────────────────────────────────────────────────────

def fetch_douyin_product_detail(page, product_title: str) -> dict:
    """
    在抖音搜索商品名，抓取视频封面图（作为商品素材）和文案。

    策略：
    - 搜索页 type=general，等待 networkidle + 滚动触发懒加载
    - 封面图：class 含 fnWBjiik 的 img，域名 p3-pc-sign.douyinpic.com
    - 文案：从页面文本提取视频描述和话题标签
    """
    result = {"image_urls": [], "video_urls": [], "cover_urls": [], "description": ""}

    try:
        search_url = f"https://www.douyin.com/search/{product_title}?type=general"
        logger.info("搜索商品: %s", product_title)
        page.goto(search_url, wait_until="domcontentloaded", timeout=30000)

        # 等待视频封面图出现（class fnWBjiik 是抖音搜索结果封面的固定 class）
        try:
            page.wait_for_selector("img.fnWBjiik", timeout=10000)
        except Exception:
            pass  # 超时也继续，尽量抓
        time.sleep(2)

        # 滚动触发懒加载
        page.evaluate("window.scrollTo(0, 800)")
        time.sleep(1)
        page.evaluate("window.scrollTo(0, 1600)")
        time.sleep(1)

        # 抓取视频封面图：douyinpic.com 域名下的 img，尺寸 >= 200px
        images = page.evaluate("""
            () => {
                const urls = [];
                document.querySelectorAll('img').forEach(img => {
                    const src = img.src || '';
                    if (src.includes('douyinpic.com') &&
                        img.naturalWidth >= 200 &&
                        img.naturalHeight >= 200) {
                        urls.push(src);
                    }
                });
                return [...new Set(urls)].slice(0, 9);
            }
        """)
        result["image_urls"] = images or []

        # 抓取视频 poster（如果有视频在播放）
        covers = page.evaluate("""
            () => {
                const urls = [];
                document.querySelectorAll('video[poster]').forEach(v => {
                    if (v.poster && v.poster.startsWith('http')) urls.push(v.poster);
                });
                return [...new Set(urls)].slice(0, 3);
            }
        """)
        result["cover_urls"] = covers or []

        # 从页面文本提取文案（视频描述 + 话题标签）
        body_text = page.inner_text("body")
        lines = [l.strip() for l in body_text.split("\n") if l.strip()]
        # 找含话题标签的行作为文案
        captions = []
        for line in lines:
            if "#" in line and len(line) > 10:
                captions.append(line)
            if len(captions) >= 5:
                break
        result["description"] = "\n".join(captions)

        logger.info(
            "商品 [%s] 抓取完成：封面图 %d 张，视频 %d 个",
            product_title,
            len(result["image_urls"]) + len(result["cover_urls"]),
            len(result["video_urls"]),
        )

    except Exception as e:
        logger.warning("抓取商品 [%s] 详情失败: %s", product_title, e)

    return result


def fetch_all_product_details(products: list[TrendingProduct]) -> tuple[dict, dict]:
    """
    用 Playwright 连接已登录的 Chrome，批量抓取商品详情。
    返回 (image_urls_map, video_urls_map)
    """
    from playwright.sync_api import sync_playwright

    image_urls_map: dict[str, list[str]] = {}
    video_urls_map: dict[str, list[str]] = {}

    with sync_playwright() as p:
        try:
            browser = p.chromium.connect_over_cdp("http://localhost:9222")
        except Exception as e:
            logger.error("无法连接 Chrome 调试端口 9222: %s", e)
            logger.error("请先运行: bash scripts/start_chrome.sh")
            return image_urls_map, video_urls_map

        context = browser.contexts[0]
        # 关闭多余 tab，只保留一个
        pages = context.pages
        for pg in pages[1:]:
            try:
                pg.close()
            except Exception:
                pass
        page = context.pages[0]

        for product in products:
            detail = fetch_douyin_product_detail(page, product.title)

            # 合并图片：主图 + 封面图
            all_images = detail["image_urls"] + detail["cover_urls"]
            # 去重
            seen = set()
            unique_images = []
            for url in all_images:
                if url not in seen:
                    seen.add(url)
                    unique_images.append(url)

            image_urls_map[product.product_id] = unique_images[:6]  # 最多6张
            video_urls_map[product.product_id] = detail["video_urls"][:2]  # 最多2个

            # 保存文案到商品素材目录（与图片放在一起）
            desc_dir = Path("data/materials") / product.product_id
            desc_dir.mkdir(parents=True, exist_ok=True)
            desc_file = desc_dir / "description.json"
            with open(desc_file, "w", encoding="utf-8") as f:
                json.dump({
                    "product_id": product.product_id,
                    "title": product.title,
                    "description": detail["description"],
                    "crawled_at": datetime.now().isoformat(),
                }, f, ensure_ascii=False, indent=2)

            time.sleep(1.5)  # 避免请求过快

    return image_urls_map, video_urls_map


# ── 主流程 ────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="从飞瓜+抖音采集真实商品素材")
    parser.add_argument("--top", type=int, default=5, help="采集前 N 个爆款商品（默认5）")
    parser.add_argument("--category", type=str, default=None, help="按类目过滤（如：食品、美妆）")
    parser.add_argument("--data-dir", type=str, default="data/ranks", help="飞瓜榜单数据目录")
    args = parser.parse_args()

    print("=" * 60)
    print("抖音带货自动化 - 真实素材采集")
    print("=" * 60)

    # Step 1: 从飞瓜加载商品
    print(f"\n[1/4] 从飞瓜榜单加载商品数据...")
    crawler = FeiGuaCrawler(data_dir=args.data_dir)
    raw_products = crawler.fetch_products(category=args.category)
    if not raw_products:
        print("❌ 未找到商品数据，请确认飞瓜榜单文件存在")
        sys.exit(1)
    print(f"     加载 {len(raw_products)} 个商品")

    # Step 2: 分析筛选爆款
    print(f"\n[2/4] 分析筛选爆款商品（前20%）...")
    analyzer = ProductAnalyzer()
    scored = analyzer.score_products(raw_products)
    trending = analyzer.get_trending_products(scored, top_percent=0.2)

    # 限制采集数量
    trending = trending[:args.top]
    print(f"     筛选出 {len(trending)} 个爆款商品：")
    for p in trending:
        print(f"     [{p.rank}] {p.title[:30]}... (评分: {p.composite_score:.1f})")

    # Step 3: 从抖音抓取商品详情
    print(f"\n[3/4] 从抖音抓取商品详情（图片/视频/文案）...")
    print("     正在连接 Chrome 调试端口 9222...")
    image_urls_map, video_urls_map = fetch_all_product_details(trending)

    total_images = sum(len(v) for v in image_urls_map.values())
    total_videos = sum(len(v) for v in video_urls_map.values())
    print(f"     找到图片 URL: {total_images} 个，视频 URL: {total_videos} 个")

    if total_images == 0 and total_videos == 0:
        print("⚠️  未找到任何素材 URL，可能原因：")
        print("   - Chrome 未启动或未登录抖音")
        print("   - 请先运行: bash scripts/start_chrome.sh 并登录")
        sys.exit(1)

    print(f"     找到图片 URL: {total_images} 个，视频 URL: {total_videos} 个")

    # Step 4: 下载素材
    print(f"\n[4/4] 下载素材...")
    collector = MaterialCollector(base_dir="data/materials")
    reports = collector.collect_materials(
        trending,
        image_urls_map=image_urls_map,
        video_urls_map=video_urls_map,
    )

    # 打印报告
    print("\n" + "=" * 60)
    print("采集报告")
    print("=" * 60)
    total_success = 0
    total_failure = 0
    all_files = []

    for report in reports:
        product = next(p for p in trending if p.product_id == report.product_id)
        print(f"\n商品: {product.title[:40]}")
        print(f"  product_id: {report.product_id}")
        print(f"  成功: {report.success_count}  失败: {report.failure_count}")
        if report.failures:
            for f in report.failures:
                print(f"  ✗ {f.error_reason}")
        total_success += report.success_count
        total_failure += report.failure_count

    print(f"\n总计：成功 {total_success} 个，失败 {total_failure} 个")

    # 列出所有采集的文件
    materials_dir = Path("data/materials")
    if materials_dir.exists():
        print("\n" + "=" * 60)
        print("已采集文件列表")
        print("=" * 60)
        for f in sorted(materials_dir.rglob("*")):
            if f.is_file():
                size_kb = f.stat().st_size / 1024
                print(f"  {f}  ({size_kb:.1f} KB)")
                all_files.append(str(f))
        print(f"\n共 {len(all_files)} 个文件")

    # 打开文件夹
    print(f"\n📂 打开素材目录: {materials_dir.absolute()}")
    os.system(f"open '{materials_dir.absolute()}'")


if __name__ == "__main__":
    main()
