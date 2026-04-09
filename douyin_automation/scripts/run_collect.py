"""
演示采集脚本：使用榜单商品 + 公开可访问的示例图片 URL 运行 MaterialCollector
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from douyin_automation.collector.material_collector import MaterialCollector
from douyin_automation.models.domain import TrendingProduct

# 基于商品销售榜 Top5 构造商品列表
products = [
    TrendingProduct(product_id="prod_001", title="美赞臣液体钙5桶儿童有机钙", category="母婴", composite_score=95.0, rank=1),
    TrendingProduct(product_id="prod_002", title="锋味派爆汁烤肠三盒24根", category="食品", composite_score=90.0, rank=2),
    TrendingProduct(product_id="prod_003", title="喵际足金999.9财富金条", category="黄金珠宝", composite_score=85.0, rank=3),
    TrendingProduct(product_id="prod_004", title="领丰金零花钱攒金豆豆足金", category="黄金珠宝", composite_score=80.0, rank=4),
    TrendingProduct(product_id="prod_005", title="佐川新款修容方框磁吸眼镜", category="眼镜", composite_score=75.0, rank=5),
]

# 使用 Picsum Photos（公开免费图片服务）作为示例图片 URL
image_urls_map = {
    "prod_001": [
        "https://picsum.photos/seed/prod001a/400/400",
        "https://picsum.photos/seed/prod001b/400/400",
        "https://picsum.photos/seed/prod001c/400/400",
    ],
    "prod_002": [
        "https://picsum.photos/seed/prod002a/400/400",
        "https://picsum.photos/seed/prod002b/400/400",
        "https://picsum.photos/seed/prod002c/400/400",
    ],
    "prod_003": [
        "https://picsum.photos/seed/prod003a/400/400",
        "https://picsum.photos/seed/prod003b/400/400",
        "https://picsum.photos/seed/prod003c/400/400",
    ],
    "prod_004": [
        "https://picsum.photos/seed/prod004a/400/400",
        "https://picsum.photos/seed/prod004b/400/400",
        "https://picsum.photos/seed/prod004c/400/400",
    ],
    "prod_005": [
        "https://picsum.photos/seed/prod005a/400/400",
        "https://picsum.photos/seed/prod005b/400/400",
        "https://picsum.photos/seed/prod005c/400/400",
        # 故意加一条无效 URL 演示失败处理
        "https://invalid.example.com/no_such_image.jpg",
    ],
}

collector = MaterialCollector(base_dir="data/materials")
print("开始采集素材...\n")
reports = collector.collect_materials(products, image_urls_map=image_urls_map)

print("\n" + "=" * 60)
print("采集报告汇总")
print("=" * 60)
total_success = 0
total_failure = 0
for r in reports:
    product = next(p for p in products if p.product_id == r.product_id)
    print(f"\n商品: {product.title}")
    print(f"  product_id : {r.product_id}")
    print(f"  成功: {r.success_count}  失败: {r.failure_count}")
    if r.failures:
        for f in r.failures:
            print(f"  ✗ 失败原因: {f.error_reason}")
            print(f"    URL: {f.url}")
    total_success += r.success_count
    total_failure += r.failure_count

print(f"\n总计：成功 {total_success} 个，失败 {total_failure} 个")
