# products/utils.py

from django.db.models import Sum
from myapp.models import OrderItems, ProductVariants, RecommendedProducts

def update_hot_products(top_n=6):
    # 統計每個變體的銷售量
    top_variants = (
        OrderItems.objects
        .values('variant')
        .annotate(total_sold=Sum('quantity'))
        .order_by('-total_sold')[:top_n]
    )

    # 若尚無訂單，預設最新商品當熱門
    if not top_variants:
        fallback_variants = ProductVariants.objects.order_by('-created_at')[:top_n]
    else:
        fallback_variants = [
            ProductVariants.objects.get(pk=item['variant']) for item in top_variants
        ]

    # 清除舊資料
    RecommendedProducts.objects.filter(recommended_for='熱門商品').delete()

    # 建立新資料
    for variant in fallback_variants:
        RecommendedProducts.objects.create(
            variant=variant,
            recommended_for='熱門商品'
        )
