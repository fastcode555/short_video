"""
飞瓜数据 - 热销商品榜单抓取
直接读取已渲染的页面内容，解析商品榜单
"""
import time
import json
import re
from playwright.sync_api import sync_playwright


def main():
    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp("http://localhost:9222")
        context = browser.contexts[0]

        # 关闭多余的 tab，只保留第一个
        pages = context.pages
        for pg in pages[1:]:
            try:
                pg.close()
            except Exception:
                pass

        page = context.pages[0]
        print(f"当前页面: {page.url}")

        # 如果不在商品榜单页，先导航过去
        if "product-rank" not in page.url:
            print("导航到商品销售榜...")
            page.goto(
                "https://dy.feigua.cn/app/#/product-rank/index?tab=product",
                wait_until="domcontentloaded",
                timeout=30000,
            )
            time.sleep(6)
        else:
            # 已在目标页，直接刷新确保数据最新
            print("刷新页面...")
            page.reload(wait_until="domcontentloaded", timeout=30000)
            time.sleep(6)

        # 读取页面文本
        content = page.inner_text("body")
        lines = [l.strip() for l in content.split("\n") if l.strip()]

        # 找到榜单起始位置（"01"）
        start_idx = None
        for i, line in enumerate(lines):
            if line == "01":
                start_idx = i
                break

        if start_idx is None:
            print("未找到榜单数据，页面内容：")
            for line in lines[:50]:
                print(f"  {line}")
            return

        # 解析商品数据
        products = []
        i = start_idx
        while i < len(lines):
            line = lines[i]
            if re.match(r"^(0[1-9]|[1-4][0-9]|50)$", line):
                rank = int(line)
                product = {"rank": rank}
                i += 1
                # 商品名称
                if i < len(lines):
                    product["title"] = lines[i]
                    i += 1
                # 后续字段
                fields = []
                while i < len(lines) and not re.match(r"^(0[1-9]|[1-4][0-9]|50)$", lines[i]):
                    fields.append(lines[i])
                    i += 1
                    if len(fields) > 15:
                        break
                # 先提取评分/好评率/佣金率等非数值字段
                data_fields = []
                for f in fields:
                    if f.startswith("评分"):
                        product["rating"] = f.replace("评分 ", "")
                    elif f.startswith("好评率"):
                        product["good_rate"] = f.replace("好评率 ", "")
                    elif f.startswith("佣金率"):
                        product["commission_rate"] = f.replace("佣金率 ", "")
                    elif f == "价格":
                        pass  # 跳过"价格"占位符
                    elif re.match(r"^[\d\.]+w?-[\d\.]+w?$", f) or re.match(r"^[\d\.]+w$", f) or f == "--":
                        # 数值字段：销售额、销量、浏览量
                        data_fields.append(f)
                    elif re.match(r"^\d+$", f):
                        # 纯数字：带货视频数、直播数、达人数
                        data_fields.append(f)

                # 按固定顺序赋值：销售额、销量、浏览量、带货视频、带货直播、带货达人
                if len(data_fields) >= 1:
                    product["sales_amount"] = data_fields[0]
                if len(data_fields) >= 2:
                    product["sales_count"] = data_fields[1] if data_fields[1] != "--" else "未知"
                if len(data_fields) >= 3:
                    product["views"] = data_fields[2] if data_fields[2] != "--" else "未知"
                if len(data_fields) >= 4:
                    product["video_count"] = data_fields[3]
                if len(data_fields) >= 5:
                    product["live_count"] = data_fields[4]
                if len(data_fields) >= 6:
                    product["kol_count"] = data_fields[5]
                products.append(product)
            else:
                i += 1

        # 打印结果
        print("\n" + "=" * 70)
        print(f"飞瓜数据 - 抖音商品销售日榜 2026-03-25  共 {len(products)} 条")
        print("=" * 70)
        for prod in products:
            print(f"\n【第{prod['rank']:02d}名】{prod['title']}")
            if prod.get("sales_amount"):
                print(f"  销售额:   {prod['sales_amount']}")
            if prod.get("sales_count"):
                print(f"  销量:     {prod['sales_count']}")
            if prod.get("views"):
                print(f"  浏览量:   {prod['views']}")
            if prod.get("video_count"):
                print(f"  带货视频: {prod['video_count']} 个")
            if prod.get("live_count"):
                print(f"  带货直播: {prod['live_count']} 场")
            if prod.get("kol_count"):
                print(f"  带货达人: {prod['kol_count']} 人")
            if prod.get("rating"):
                print(f"  评分:     {prod['rating']}")
            if prod.get("good_rate"):
                print(f"  好评率:   {prod['good_rate']}")
            if prod.get("commission_rate"):
                print(f"  佣金率:   {prod['commission_rate']}")

        # 保存 JSON
        out_path = "/tmp/feigua_hot_products.json"
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(products, f, ensure_ascii=False, indent=2)
        print(f"\n✅ 数据已保存到 {out_path}")


if __name__ == "__main__":
    main()
