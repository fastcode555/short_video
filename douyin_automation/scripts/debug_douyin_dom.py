"""
调试脚本：打印抖音搜索结果页的真实 DOM 结构
帮助找到正确的图片/视频选择器

用法：python3 scripts/debug_douyin_dom.py
前提：Chrome 已以调试模式运行（bash scripts/start_chrome.sh 第1步完成）
"""
import sys, os, time, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from playwright.sync_api import sync_playwright

PRODUCT_TITLE = "锋味派爆汁烤肠"

def main():
    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp("http://localhost:9222")
        context = browser.contexts[0]
        pages = context.pages
        for pg in pages[1:]:
            try: pg.close()
            except: pass
        page = context.pages[0]

        # 导航到搜索页
        search_url = f"https://www.douyin.com/search/{PRODUCT_TITLE}?type=product"
        print(f"导航到: {search_url}")
        page.goto(search_url, wait_until="networkidle", timeout=30000)

        # 等待内容渲染
        print("等待页面渲染...")
        time.sleep(5)

        # 滚动触发懒加载
        page.evaluate("window.scrollTo(0, 500)")
        time.sleep(2)

        # ── 1. 打印所有 img 标签 ──
        imgs = page.evaluate("""
            () => Array.from(document.querySelectorAll('img')).map(img => ({
                src: img.src,
                dataSrc: img.dataset.src || '',
                className: img.className.slice(0, 60),
                width: img.naturalWidth,
                height: img.naturalHeight,
            })).filter(i => i.src || i.dataSrc)
        """)
        print(f"\n=== 所有 img 标签 ({len(imgs)} 个) ===")
        for img in imgs:
            print(f"  [{img['width']}x{img['height']}] {img['src'][:80]}")
            if img['dataSrc']:
                print(f"    data-src: {img['dataSrc'][:80]}")
            print(f"    class: {img['className']}")

        # ── 2. 打印所有 video 标签 ──
        videos = page.evaluate("""
            () => Array.from(document.querySelectorAll('video')).map(v => ({
                src: v.src,
                poster: v.poster,
                className: v.className.slice(0, 60),
            }))
        """)
        print(f"\n=== 所有 video 标签 ({len(videos)} 个) ===")
        for v in videos:
            print(f"  src: {v['src'][:80]}")
            print(f"  poster: {v['poster'][:80]}")
            print(f"  class: {v['className']}")

        # ── 3. 打印页面上所有包含 http 的 src/href ──
        all_urls = page.evaluate("""
            () => {
                const urls = new Set();
                document.querySelectorAll('[src],[data-src],[poster],[href]').forEach(el => {
                    ['src','data-src','poster','href'].forEach(attr => {
                        const v = el.getAttribute(attr);
                        if (v && v.startsWith('http')) urls.add(v);
                    });
                });
                return [...urls];
            }
        """)
        print(f"\n=== 页面所有资源 URL ({len(all_urls)} 个) ===")
        for url in all_urls:
            print(f"  {url[:100]}")

        # ── 4. 打印页面 body 文本（前2000字）──
        body_text = page.inner_text("body")
        print(f"\n=== 页面文本（前2000字）===")
        print(body_text[:2000])

        # ── 5. 保存完整 HTML 供分析 ──
        html = page.content()
        out = "/tmp/douyin_search_debug.html"
        with open(out, "w", encoding="utf-8") as f:
            f.write(html)
        print(f"\n✅ 完整 HTML 已保存到 {out}")

        # ── 6. 打印当前页面 URL（确认是否跳转登录页）──
        print(f"\n当前 URL: {page.url}")

if __name__ == "__main__":
    main()
