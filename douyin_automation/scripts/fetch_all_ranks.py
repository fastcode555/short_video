"""
飞瓜数据 - 全榜单批量抓取脚本
抓取所有可访问的榜单数据并保存为 JSON
"""
import time
import json
import re
import os
from datetime import datetime
from playwright.sync_api import sync_playwright

# 可访问的榜单列表
RANK_PAGES = [
    ("商品销售榜",    "product-rank/index?tab=product"),
    ("新品销售榜",    "product-rank/index?tab=newProduct"),
    ("商品搜索榜",    "product-rank/index?tab=search"),
    ("商品热词榜",    "product-rank/index?tab=hotWord"),
    ("带货达人榜",    "product-blogger-rank?tab=productBlogger&type=1"),
    ("直播带货达人榜","product-blogger-rank?tab=productBlogger&type=2"),
    ("视频带货达人榜","product-blogger-rank?tab=productBlogger&type=3"),
    ("热门话题榜",    "hot-list-rank/index"),
    ("实时直播热榜",  "live-broadcast-rank"),
    ("直播热度榜",    "live-rank/index?tab=hot"),
    ("品牌销售榜",    "brand-rank/index?tab=sales"),
    ("品牌自营榜",    "brand-rank/index?tab=self"),
    ("达人推广榜",    "brand-rank/index?tab=kol"),
    ("小店销售榜",    "shop-rank/index?tab=sales"),
    ("官方店销售榜",  "shop-rank/index?tab=official"),
]

BASE_URL = "https://dy.feigua.cn/app/#/"


def parse_rank_items(lines):
    """通用榜单解析：按排名数字分割，提取每条记录的所有字段"""
    items = []
    start_idx = None
    for i, line in enumerate(lines):
        if line == "01":
            start_idx = i
            break
    if start_idx is None:
        return items

    i = start_idx
    while i < len(lines):
        line = lines[i]
        if re.match(r"^(0[1-9]|[1-4][0-9]|50)$", line):
            rank = int(line)
            # 过滤掉分页控件产生的假排名（后面跟的是纯数字串）
            if i + 1 < len(lines) and re.match(r"^\d{5,}$", lines[i + 1]):
                i += 1
                continue

            item = {"rank": rank}
            i += 1

            # 名称行
            if i < len(lines):
                item["name"] = lines[i]
                i += 1

            # 后续字段
            fields = []
            while i < len(lines) and not re.match(r"^(0[1-9]|[1-4][0-9]|50)$", lines[i]):
                fields.append(lines[i])
                i += 1
                if len(fields) > 20:
                    break

            # 解析字段
            data_fields = []
            for f in fields:
                if f == "价格" or not f:
                    continue
                elif f.startswith("评分"):
                    item["rating"] = f.replace("评分 ", "")
                elif f.startswith("好评率"):
                    item["good_rate"] = f.replace("好评率 ", "")
                elif f.startswith("佣金率"):
                    item["commission_rate"] = f.replace("佣金率 ", "")
                elif f.startswith("粉丝"):
                    item["fans"] = f.replace("粉丝 ", "")
                elif re.match(r"^[\d\.]+w?-[\d\.]+w?$", f) or re.match(r"^[\d\.]+w$", f) or f == "--":
                    data_fields.append(f)
                elif re.match(r"^\d+$", f) and int(f) < 10000:
                    data_fields.append(f)

            # 按位置赋值（销售额/销量/浏览量/视频数/直播数/达人数）
            field_names = ["sales_amount", "sales_count", "views", "video_count", "live_count", "kol_count"]
            for idx, fname in enumerate(field_names):
                if idx < len(data_fields):
                    val = data_fields[idx]
                    item[fname] = None if val == "--" else val

            items.append(item)
        else:
            i += 1

    return items


def fetch_rank(page, name, hash_path):
    """抓取单个榜单"""
    url = BASE_URL + hash_path
    print(f"\n  → 抓取 [{name}]...")

    page.evaluate(f"window.location.hash = '/{hash_path}'")
    time.sleep(4)

    content = page.inner_text("body")
    if "数据若加载过久" in content:
        # 尝试刷新
        page.reload(wait_until="domcontentloaded", timeout=20000)
        time.sleep(5)
        content = page.inner_text("body")

    lines = [l.strip() for l in content.split("\n") if l.strip()]
    items = parse_rank_items(lines)
    print(f"     解析到 {len(items)} 条数据")
    return items


def main():
    today = datetime.now().strftime("%Y-%m-%d")
    output_dir = f"douyin_automation/data/ranks/{today}"
    os.makedirs(output_dir, exist_ok=True)

    all_data = {}

    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp("http://localhost:9222")
        context = browser.contexts[0]

        # 关闭多余 tab
        pages = context.pages
        for pg in pages[1:]:
            try:
                pg.close()
            except Exception:
                pass

        page = context.pages[0]
        print(f"开始批量抓取飞瓜榜单数据 ({today})")
        print(f"共 {len(RANK_PAGES)} 个榜单\n")

        for name, hash_path in RANK_PAGES:
            try:
                items = fetch_rank(page, name, hash_path)
                all_data[name] = items

                # 单独保存每个榜单
                safe_name = name.replace("/", "_")
                out_file = f"{output_dir}/{safe_name}.json"
                with open(out_file, "w", encoding="utf-8") as f:
                    json.dump({"name": name, "date": today, "items": items}, f, ensure_ascii=False, indent=2)

            except Exception as e:
                print(f"     ❌ 抓取失败: {e}")
                all_data[name] = []

    # 保存汇总文件
    summary_file = f"{output_dir}/all_ranks.json"
    with open(summary_file, "w", encoding="utf-8") as f:
        json.dump({"date": today, "ranks": all_data}, f, ensure_ascii=False, indent=2)

    # 打印汇总结果
    print("\n" + "=" * 70)
    print(f"抓取完成！数据保存至 {output_dir}/")
    print("=" * 70)
    total = 0
    for name, items in all_data.items():
        count = len(items)
        total += count
        status = "✅" if count > 0 else "⚠️ "
        print(f"  {status} {name:20s} {count:3d} 条")
    print(f"\n  合计 {total} 条数据")

    # 打印商品销售榜 TOP10
    if all_data.get("商品销售榜"):
        print("\n" + "=" * 70)
        print("商品销售榜 TOP 10")
        print("=" * 70)
        for item in all_data["商品销售榜"][:10]:
            print(f"\n  【第{item['rank']:02d}名】{item['name']}")
            if item.get("sales_amount"): print(f"    销售额: {item['sales_amount']}")
            if item.get("sales_count"):  print(f"    销量:   {item['sales_count']}")
            if item.get("views"):        print(f"    浏览量: {item['views']}")
            if item.get("kol_count"):    print(f"    带货达人: {item['kol_count']} 人")
            if item.get("good_rate"):    print(f"    好评率: {item['good_rate']}")


if __name__ == "__main__":
    main()
