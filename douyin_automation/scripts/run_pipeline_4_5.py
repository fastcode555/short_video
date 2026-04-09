"""
流水线演示：步骤 4（素材采集）→ 步骤 5（文案分析）
读取 data/materials/ 下已采集的商品素材和文案，运行 ContentAnalyzer，输出分析结果。

用法：python3 scripts/run_pipeline_4_5.py
"""
import json
import os
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from douyin_automation.content.content_analyzer import ContentAnalyzer
from douyin_automation.crawler.crawler import RawVideo
from douyin_automation.models.domain import ContentAnalysis

MATERIALS_DIR = Path("data/materials")
analyzer = ContentAnalyzer()


def load_videos_from_materials() -> list[RawVideo]:
    """从 data/materials/{product_id}/description.json 加载视频文案数据"""
    videos = []
    for product_dir in sorted(MATERIALS_DIR.iterdir()):
        if not product_dir.is_dir():
            continue
        desc_file = product_dir / "description.json"
        if not desc_file.exists():
            continue
        with open(desc_file, encoding="utf-8") as f:
            data = json.load(f)

        # 统计该商品目录下的图片数量
        images = list(product_dir.glob("*.jpg")) + list(product_dir.glob("*.png"))

        videos.append(RawVideo(
            video_id=data["product_id"],
            product_id=data["product_id"],
            title=data.get("title", ""),
            description=data.get("description", ""),
            hashtags=[],
            video_url="",
            cover_url="",
            likes=0,
            comments=0,
            shares=0,
            crawled_at=datetime.fromisoformat(data.get("crawled_at", datetime.now().isoformat())),
        ))
        print(f"  ✅ 加载商品: {data.get('title', '')[:40]}...")
        print(f"     product_id: {data['product_id']}  |  素材图片: {len(images)} 张")

    return videos


def print_separator(title: str = ""):
    width = 60
    if title:
        pad = (width - len(title) - 2) // 2
        print(f"\n{'─' * pad} {title} {'─' * pad}")
    else:
        print("─" * width)


def main():
    print("=" * 60)
    print("  流水线演示：步骤4（素材采集）→ 步骤5（文案分析）")
    print("=" * 60)

    # ── 步骤 4 输出：展示已采集的素材 ────────────────────────────────────────
    print_separator("步骤 4：已采集素材")
    if not MATERIALS_DIR.exists():
        print("❌ 未找到素材目录，请先运行采集脚本")
        sys.exit(1)

    videos = load_videos_from_materials()
    if not videos:
        print("❌ 未找到任何 description.json，请先运行采集脚本")
        sys.exit(1)

    total_images = sum(
        len(list((MATERIALS_DIR / v.product_id).glob("*.jpg")))
        for v in videos
    )
    print(f"\n  共 {len(videos)} 个商品，{total_images} 张素材图片")

    # ── 步骤 5：文案分析 ──────────────────────────────────────────────────────
    print_separator("步骤 5：文案分析")

    # 5.1 提取文案
    contents = []
    missing = []
    for video in videos:
        content = analyzer.extract_content(video)
        if content:
            contents.append(content)
        else:
            missing.append(video.video_id)

    print(f"\n  提取文案：{len(contents)} 个成功，{len(missing)} 个文案缺失")
    if missing:
        for m in missing:
            print(f"    ⚠️  {m}：文案缺失")

    if not contents:
        print("❌ 无可分析的文案")
        sys.exit(1)

    # 5.2 关键词分析
    keywords = analyzer.analyze_keywords(contents)
    print_separator("高频关键词 Top 20")
    for i, kw in enumerate(keywords, 1):
        bar = "█" * min(kw.frequency, 30)
        print(f"  {i:2d}. {kw.keyword:<12} {bar} ({kw.frequency})")

    # 5.3 话题标签分析
    hashtags = analyzer.analyze_hashtags(contents)
    print_separator("高频话题标签 Top 10")
    for i, ht in enumerate(hashtags, 1):
        bar = "█" * min(ht.frequency, 30)
        print(f"  {i:2d}. {ht.hashtag:<20} {bar} ({ht.frequency})")

    # 5.4 标题模式分析
    patterns = analyzer.analyze_title_patterns(contents)
    print_separator("标题模式分布")
    for p in patterns:
        bar = "█" * int(p.percentage / 5)
        print(f"  {p.pattern_type:<8} {bar} {p.percentage:.1f}%  (命中 {p.count}/{len(contents)} 个)")

    # 5.5 导出 JSON
    analysis = ContentAnalysis(
        top_keywords=keywords,
        top_hashtags=hashtags,
        title_patterns=patterns,
        analyzed_at=datetime.now(),
    )
    json_str = analyzer.export_json(analysis)

    out_path = MATERIALS_DIR / "analysis_result.json"
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(json_str)

    print_separator("分析结果已保存")
    print(f"\n  📄 {out_path}")
    print(f"\n  JSON 预览（前500字）：")
    print(json_str[:500] + ("..." if len(json_str) > 500 else ""))

    print("\n" + "=" * 60)
    print("  ✅ 步骤 4→5 串联完成")
    print("=" * 60)


if __name__ == "__main__":
    main()
