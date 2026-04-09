"""
获取飞瓜所有榜单的 URL
通过点击侧边栏展开各榜单分类
"""
import time
from playwright.sync_api import sync_playwright

# 已知的飞瓜榜单路由（从页面文本分析得出）
RANK_PAGES = [
    # 商品榜
    ("商品销售榜",   "https://dy.feigua.cn/app/#/product-rank/index?tab=product"),
    ("新品销售榜",   "https://dy.feigua.cn/app/#/product-rank/index?tab=newProduct"),
    ("商品搜索榜",   "https://dy.feigua.cn/app/#/product-rank/index?tab=search"),
    ("商品热词榜",   "https://dy.feigua.cn/app/#/product-rank/index?tab=hotWord"),
    ("SPU销售榜",    "https://dy.feigua.cn/app/#/spu-rank/index"),
    # 达人榜
    ("带货达人榜",   "https://dy.feigua.cn/app/#/product-blogger-rank?tab=productBlogger&type=1"),
    ("直播带货达人榜","https://dy.feigua.cn/app/#/product-blogger-rank?tab=productBlogger&type=2"),
    ("视频带货达人榜","https://dy.feigua.cn/app/#/product-blogger-rank?tab=productBlogger&type=3"),
    ("涨粉排行榜",   "https://dy.feigua.cn/app/#/bloggerrank/growingUpRank"),
    ("行业排行榜",   "https://dy.feigua.cn/app/#/bloggerrank/industryRank"),
    # 视频榜
    ("热门视频榜",   "https://dy.feigua.cn/app/#/video/library/all?period=24&sort=1"),
    ("带货视频榜",   "https://dy.feigua.cn/app/#/video-rank/index?tab=sellVideo"),
    ("种草视频榜",   "https://dy.feigua.cn/app/#/video-rank/index?tab=grassVideo"),
    ("热门话题榜",   "https://dy.feigua.cn/app/#/hot-list-rank/index"),
    # 直播榜
    ("实时直播热榜", "https://dy.feigua.cn/app/#/live-broadcast-rank"),
    ("直播人气榜",   "https://dy.feigua.cn/app/#/live-rank/index?tab=popularity"),
    ("直播热度榜",   "https://dy.feigua.cn/app/#/live-rank/index?tab=hot"),
    # 品牌榜
    ("品牌销售榜",   "https://dy.feigua.cn/app/#/brand-rank/index?tab=sales"),
    ("品牌自营榜",   "https://dy.feigua.cn/app/#/brand-rank/index?tab=self"),
    ("达人推广榜",   "https://dy.feigua.cn/app/#/brand-rank/index?tab=kol"),
    # 小店榜
    ("小店销售榜",   "https://dy.feigua.cn/app/#/shop-rank/index?tab=sales"),
    ("官方店销售榜", "https://dy.feigua.cn/app/#/shop-rank/index?tab=official"),
]


def probe_pages():
    """访问每个榜单页面，确认哪些可以正常加载"""
    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp("http://localhost:9222")
        context = browser.contexts[0]
        page = context.pages[0]

        accessible = []
        for name, url in RANK_PAGES:
            page.evaluate(f"window.location.hash = '{url.split('#')[1]}'")
            time.sleep(3)

            content = page.inner_text("body")
            # 检查是否有实际数据（包含排名数字 01）
            has_data = "01" in content and "数据若加载过久" not in content
            status = "✅" if has_data else "⚠️ "
            print(f"{status} {name:20s} {url}")
            if has_data:
                accessible.append((name, url))

        return accessible


if __name__ == "__main__":
    print("探测各榜单页面可访问性...\n")
    accessible = probe_pages()
    print(f"\n共 {len(accessible)} 个榜单可正常访问")
