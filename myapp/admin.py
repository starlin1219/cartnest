from django.contrib import admin
from myapp.models import *
from django.db.models import Sum
from django.contrib.admin import SimpleListFilter
from django.contrib import messages
from .utils import update_hot_products 


admin.site.site_header = "CUI LIANG SHI 後台管理"
admin.site.site_title = "網站後台"
admin.site.index_title = "會員與商品資料總覽"

class MembershipLevelsAdmin(admin.ModelAdmin):
    list_display = ('level_id', 'level_name', 'min_spent', 'discount_rate')
    ordering = ('level_id',)
    search_fields = ('level_id', 'level_name')
admin.site.register(MembershipLevels, MembershipLevelsAdmin)


# 編輯帳號的 Inline（OneToOne）
class AuthUsersInline(admin.StackedInline):
    model = AuthUsers
    can_delete = False
    verbose_name_plural = '帳號資訊'
    fk_name = 'user'

# 編輯優惠使用紀錄的 Inline（M:N 中介）
class UserPromotionsInline(admin.TabularInline):
    model = UserPromotions
    extra = 0
    verbose_name_plural = '使用優惠紀錄'
    autocomplete_fields = ['promo']
    readonly_fields = ['used_at']  # 若不想被編輯

# 主 admin：Users
@admin.register(Users)
class UsersAdmin(admin.ModelAdmin):
    list_display = ['user_id', 'name', 'gender', 'level', 'get_username','birthday', 'get_email', 'address', 'created_at', 'updated_at']
    search_fields = ['name', 'authusers__email', 'authusers__username']
    inlines = [AuthUsersInline, UserPromotionsInline]

    def get_email(self, obj):
        return obj.authusers.email if hasattr(obj, 'authusers') else "-"
    get_email.short_description = 'Email'

    def get_username(self, obj):
        return obj.authusers.username if hasattr(obj, 'authusers') else "-"
    get_username.short_description = '帳號'


class PromotionTargetVariantsInline(admin.TabularInline):
    model = PromotionTargetVariants
    extra = 0
    autocomplete_fields = ['variant']
    readonly_fields = ['product_display']

    def product_display(self, obj):
        if obj.variant:
            name = obj.variant.product.name
            size = obj.variant.size.size_value if obj.variant.size else ''
            package = obj.variant.package.package_name if obj.variant.package else ''
            parts = [name]
            if size:
                parts.append(size)
            if package:
                parts.append(package)
            return f"{parts[0]}（{'／'.join(parts[1:])}）"
        return '-'
    product_display.short_description = '商品資訊'


class PromotionTargetCategoriesInline(admin.TabularInline):
    model = PromotionTargetCategories
    extra = 0
    autocomplete_fields = ['category']


class PromotionImagesInline(admin.TabularInline):
    model = PromotionImages
    extra = 1

@admin.register(Promotions)
class PromotionsAdmin(admin.ModelAdmin):
    list_display = ['promo_id', 'promo_name', 'conditions', 'promotion_type', 'discount_type', 'discount_value', 'apply_method', 'promo_code', 'receive_method','minimum_spending', 'trigger_quantity', 'is_vip_only', 'usage_limit', 'per_user_limit', 'is_accumulative_discount', 'is_accumulative_gift', 'start_date', 'end_date']
    list_filter = ['promotion_type', 'discount_type', 'apply_method']
    search_fields = ['promo_name', 'promo_code']
    inlines = [
        PromotionTargetVariantsInline,
        PromotionTargetCategoriesInline,
        PromotionImagesInline
    ]


# 商品圖片 Inline（掛在 ProductVariants 下）
class ProductImagesInline(admin.TabularInline):
    model = ProductImages
    extra = 0

# 商品變體 Inline（掛在 Products 下）
class ProductVariantsInline(admin.StackedInline):
    model = ProductVariants
    extra = 0
    show_change_link = True  # 點可進入單獨編輯
    autocomplete_fields = ['package', 'size', 'fragrance', 'origin']

# 商品分類 M:N 顯示在 ProductAdmin
class ProductCategoryInline(admin.TabularInline):
    model = ProductCategory
    extra = 0
    autocomplete_fields = ['category']

# 功效 Inline
class ProductEffectivenessMapInline(admin.TabularInline):
    model = ProductEffectivenessMap
    extra = 0
    autocomplete_fields = ['effectiveness']

# 成分 Inline
class ProductIngredientsMapInline(admin.TabularInline):
    model = ProductIngredientsMap
    extra = 0
    autocomplete_fields = ['ingredient']

# 主商品 Admin 設定
@admin.register(Products)
class ProductAdmin(admin.ModelAdmin):
    list_display = ['product_id', 'name', 'suitable_for', 'shelf_life', 'supplier', 'created_at', 'updated_at']
    search_fields = ['name']
    inlines = [
        ProductCategoryInline,
        ProductEffectivenessMapInline,
        ProductIngredientsMapInline,
        ProductVariantsInline,
    ]
    autocomplete_fields = ['supplier']

# 商品變體 Admin 設定
@admin.register(ProductVariants)
class ProductVariantsAdmin(admin.ModelAdmin):
    list_display = ['variant_id', 'product', 'package', 'size', 'fragrance', 'origin', 'price', 'is_gift', 'created_at']
    search_fields = ['product__name', 'package__package_name', 'size__size_value']
    inlines = [ProductImagesInline]
    autocomplete_fields = ['product', 'package', 'size', 'fragrance', 'origin']


class CategoriesAdmin(admin.ModelAdmin):
    list_display = ('category_id', 'category_name')
    ordering = ('category_id', )
    search_fields = ('category_name',)
admin.site.register(Categories, CategoriesAdmin)

class PackageTypesAdmin(admin.ModelAdmin):
    list_display = ('package_id', 'package_name')
    ordering = ('package_id',)
    search_fields = ('package_name',)
admin.site.register(PackageTypes, PackageTypesAdmin)

class ProductSizesAdmin(admin.ModelAdmin):
    list_display = ('size_id', 'size_value')
    ordering = ('size_id',)
    search_fields = ('size_value',)
admin.site.register(ProductSizes, ProductSizesAdmin)

class ProductFragrancesAdmin(admin.ModelAdmin):
    list_display = ('fragrance_id', 'fragrance_name')
    ordering = ('fragrance_id',)
    search_fields = ('fragrance_name',)
admin.site.register(ProductFragrances, ProductFragrancesAdmin)

class ProductOriginsAdmin(admin.ModelAdmin):
    list_display = ('origin_id', 'origin_name')
    ordering = ('origin_id',)
    search_fields = ('origin_name',)
admin.site.register(ProductOrigins, ProductOriginsAdmin)

class ProductEffectivenessAdmin(admin.ModelAdmin):
    list_display = ('effectiveness_id', 'effectiveness_name')
    ordering = ('effectiveness_id',)
    search_fields = ('effectiveness_name',)
admin.site.register(ProductEffectiveness, ProductEffectivenessAdmin)

class ProductIngredientsAdmin(admin.ModelAdmin):
    list_display = ('ingredient_id', 'ingredient_name')
    ordering = ('ingredient_id',)
    search_fields = ('ingredient_name',)
admin.site.register(ProductIngredients, ProductIngredientsAdmin)

class ProductImagesAdmin(admin.ModelAdmin):
    list_display = ('image_id', 'variant', 'image_name', 'display_order')
    ordering = ('image_id',)
    search_fields = ('variant__product__name', 'image_name')
admin.site.register(ProductImages, ProductImagesAdmin)


# 訂單項目 Inline
class OrderItemsInline(admin.TabularInline):
    model = OrderItems
    extra = 0
    can_delete = False
    readonly_fields = ['product_name', 'variant', 'quantity', 'price', 'subtotal']
    fields = ['product_name', 'quantity', 'price', 'subtotal']

    def product_name(self, obj):
        name = obj.variant.product.name
        size = obj.variant.size.size_value if obj.variant.size else ''
        package = obj.variant.package.package_name
        # 依你喜好調整格式，例如：商品名稱（200ml／1入）
        parts = [name]
        if size:
            parts.append(size)
        if package:
            parts.append(package)
        return f"{parts[0]}（{'／'.join(parts[1:])}）" if len(parts) > 1 else parts[0]

    product_name.short_description = '商品名稱'

# 套用優惠 Inline
class OrderAppliedPromotionsInline(admin.TabularInline):
    model = OrderAppliedPromotions
    extra = 0
    can_delete = False
    readonly_fields = ['promo', 'source', 'discount_amount', 'gift_variant', 'gift_product_name', 'gift_quantity']
    fields = ['promo', 'source', 'discount_amount', 'gift_product_name', 'gift_quantity']

    def gift_product_name(self, obj):
        variant = obj.gift_variant
        if not variant:
            return "-"
        
        name = variant.product.name
        size = variant.size.size_value if variant.size else ''
        package = variant.package.package_name if variant.package else ''
        
        parts = [name]
        if size:
            parts.append(size)
        if package:
            parts.append(package)
        
        return f"{parts[0]}（{'／'.join(parts[1:])}）" if len(parts) > 1 else parts[0]

    gift_product_name.short_description = '贈品名稱'

@admin.register(Orders)
class OrdersAdmin(admin.ModelAdmin):
    list_display = ['order_number', 'user', 'recipient_name', 'recipient_phone', 'recipient_email', 'shipping_method', 'shipping_address', 'payment_method', 'total_price', 'discount_amount', 'shipping_fee', 'final_price', 'order_status', 'created_at', 'status_updated_at']
    list_filter = ['order_status', 'payment_method', 'shipping_method']
    search_fields = ['order_number', 'user__name', 'recipient_name']
    inlines = [OrderItemsInline, OrderAppliedPromotionsInline]
    readonly_fields = ['order_number', 'total_price', 'discount_amount', 'final_price', 'created_at', 'status_updated_at']



class SuppliersAdmin(admin.ModelAdmin):
    list_display = ('supplier_id', 'supplier_name', 'phone', 'address')
    ordering = ('supplier_id',)
    search_fields = ('supplier_name', 'phone', 'address')
admin.site.register(Suppliers, SuppliersAdmin)


class TotalRemainingFilter(SimpleListFilter):
    title = '同款總庫存'
    parameter_name = 'total_remaining_sum'

    def lookups(self, request, model_admin):
        return [
            ('<10', '少於 10'),
            ('10-50', '10 到 50'),
            ('>50', '大於 50'),
        ]

    def queryset(self, request, queryset):
        queryset = queryset.annotate(total_remaining_sum=Sum(
            'variant__stockin__remaining_quantity'
        ))
        val = self.value()
        if val == '<10':
            return queryset.filter(total_remaining_sum__lt=10)
        elif val == '10-50':
            return queryset.filter(total_remaining_sum__gte=10, total_remaining_sum__lte=50)
        elif val == '>50':
            return queryset.filter(total_remaining_sum__gt=50)
        return queryset


class StockInAdmin(admin.ModelAdmin):
    list_display = ('stock_in_id', 'variant', 'supplier', 'quantity', 'purchase_price', 'received_date', 'expiration_date', 'remaining_quantity', 'total_remaining_for_variant',)
    list_filter = (TotalRemainingFilter,'received_date', 'supplier')
    ordering = ('stock_in_id',)
    search_fields = ['dummy']

    def get_search_results(self, request, queryset, search_term):
        if search_term:
            queryset = queryset.filter(
                models.Q(variant__product__name__icontains=search_term) |
                models.Q(supplier__supplier_name__icontains=search_term)
            )
        return queryset, False

    # Annotate 每筆資料，加入該變體的總庫存
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.annotate(total_remaining_sum=Sum(
            'variant__stockin__remaining_quantity'
        ))

    # 自訂顯示欄位：該 variant 的所有 remaining_quantity 總和
    def total_remaining_for_variant(self, obj):
        total = StockIn.objects.filter(variant=obj.variant).aggregate(
            total=models.Sum('remaining_quantity')
        )['total']
        return total or 0

    total_remaining_for_variant.short_description = '商品總庫存'
admin.site.register(StockIn, StockInAdmin)


@admin.register(RecommendedProducts)
class RecommendedProductsAdmin(admin.ModelAdmin):
    list_display = ('variant', 'recommended_for', 'created_at')
    list_filter = ('recommended_for',)
    actions = ['update_hot_products_action']

    def update_hot_products_action(self, request, queryset):
        update_hot_products()
        self.message_user(request, "已成功更新最新熱門商品！", level=messages.SUCCESS)

    update_hot_products_action.short_description = "更新熱門商品"


