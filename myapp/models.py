from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db.models import F
from datetime import datetime
from django.db.models import Max


# -------------------------------------------------------------------
# 1. 會員等級 (membership_levels)
# -------------------------------------------------------------------
class MembershipLevels(models.Model):
    level_id = models.AutoField(primary_key=True, verbose_name="會員等級編號")
    level_name = models.CharField(max_length=50, unique=True, verbose_name="會員等級名稱")
    min_spent = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="最低消費")
    discount_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0, verbose_name="折扣比率(%)")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="建立時間")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="更新時間")

    class Meta:
        db_table = "membership_levels"
        verbose_name = "會員等級"
        verbose_name_plural = "會員等級"

    def __str__(self):
        return f"{self.level_name}"


# -------------------------------------------------------------------
# 2. 會員表 (users)
# -------------------------------------------------------------------
GENDER_CHOICES = (
    ('男', '男'),
    ('女', '女'),
    ('其他', '其他'),
)

class Users(models.Model):
    user_id = models.AutoField(primary_key=True, verbose_name="會員編號")
    name = models.CharField(max_length=100, verbose_name="姓名")
    phone = models.CharField(max_length=20, unique=True, null=True, blank=True, verbose_name="電話")
    address = models.TextField(null=True, blank=True, verbose_name="地址")
    birthday = models.DateField(null=True, blank=True, verbose_name="生日")
    gender = models.CharField(max_length=10, choices=GENDER_CHOICES, null=True, blank=True, verbose_name="性別")
    # level_id 預設 1，在 Django 中可直接指定 default 的外鍵 (需注意該紀錄是否存在)
    level = models.ForeignKey(
        MembershipLevels,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        default=1,
        db_column='level_id',
        verbose_name="會員等級"
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="建立時間")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="更新時間")

    class Meta:
        db_table = "users"
        verbose_name = "會員"
        verbose_name_plural = "會員"

    def __str__(self):
        return f"{self.name}"


# -------------------------------------------------------------------
# 3. 會員帳號密碼 (auth_users)
# -------------------------------------------------------------------
class AuthUsers(models.Model):
    auth_id = models.AutoField(primary_key=True, verbose_name="會員帳號密碼編號")
    user = models.OneToOneField(
        Users,
        on_delete=models.CASCADE,
        db_column='user_id', 
        verbose_name="會員"
    )
    username = models.CharField(max_length=50, unique=True, verbose_name="會員名稱")
    email = models.EmailField(max_length=100, unique=True, verbose_name="電子郵件")
    password = models.CharField(max_length=255, verbose_name="密碼")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="建立時間")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="更新時間")

    class Meta:
        db_table = "auth_users"
        verbose_name = "會員帳號密碼"
        verbose_name_plural = "會員帳號密碼"

    def __str__(self):
        return self.username


# -------------------------------------------------------------------
# 4. 活動 (promotions)
# -------------------------------------------------------------------
PROMOTION_TYPE_CHOICES = (
    ('活動', '活動'),
    ('優惠券', '優惠券'),
)

DISCOUNT_TYPE_CHOICES = (
    ('百分比折扣', '百分比折扣'),
    ('固定金額折扣', '固定金額折扣'),
    ('贈品', '贈品'),
)

APPLY_METHOD_CHOICES = (
    ('自動套用', '自動套用'),
    ('優惠碼', '優惠碼'),
)

RECEIVE_METHOD_CHOICES = (
    ('先發放', '先發放'),
    ('自由輸入', '自由輸入'),
)

class Promotions(models.Model):
    promo_id = models.AutoField(primary_key=True, verbose_name="活動編號")
    promo_name = models.CharField(max_length=255, verbose_name="活動名稱")
    promotion_type = models.CharField(max_length=10, choices=PROMOTION_TYPE_CHOICES, verbose_name="活動類型")
    discount_type = models.CharField(max_length=10, choices=DISCOUNT_TYPE_CHOICES, verbose_name="折扣類型")
    discount_value = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, verbose_name="折扣金額或折扣比率")
    
    # 新增條件欄位
    minimum_spending = models.IntegerField(null=True, blank=True, verbose_name="最低消費金額門檻")  # 最低消費金額門檻
    trigger_quantity = models.IntegerField(null=True, blank=True, verbose_name="需要達成的購買數量")  # 需要達成的購買數量
    
    conditions = models.TextField(verbose_name="活動描述")
    apply_method = models.CharField(max_length=10, choices=APPLY_METHOD_CHOICES, verbose_name="套用類型")
    promo_code = models.CharField(max_length=50, unique=True, null=True, blank=True, verbose_name="優惠碼")
    
    receive_method = models.CharField(max_length=10, choices=RECEIVE_METHOD_CHOICES, null=True, blank=True, verbose_name="優惠碼取得方式") # 會員是否需先擁有此優惠
    
    is_vip_only = models.BooleanField(default=False, verbose_name="是否為會員等級折扣")
    target_levels = models.ManyToManyField(MembershipLevels, blank=True, verbose_name="適用會員等級")

    usage_limit = models.IntegerField(null=True, blank=True, verbose_name="總使用次數限制")  # NULL 表示無限制
    per_user_limit = models.IntegerField(null=True, blank=True, verbose_name="每個會員限制使用次數")   # 每個會員限制使用次數, NULL 表示無限制
    is_accumulative_discount = models.BooleanField(default=False, verbose_name="是否允許累積折扣")  # 是否允許累積折扣
    is_accumulative_gift = models.BooleanField(default=False, verbose_name="是否允許累積贈品")      # 是否允許累積贈品
    
    start_date = models.DateTimeField(verbose_name="活動開始時間")
    end_date = models.DateTimeField(verbose_name="活動結束時間")

    class Meta:
        db_table = "promotions"
        verbose_name = "活動"
        verbose_name_plural = "活動"

    def __str__(self):
        return self.promo_name


# -------------------------------------------------------------------
# 5. 會員使用優惠 (user_promotions) - M:N 關聯
# -------------------------------------------------------------------
class UserPromotions(models.Model):
    user = models.ForeignKey(Users, on_delete=models.CASCADE, db_column='user_id', verbose_name="會員")
    promo = models.ForeignKey(Promotions, on_delete=models.CASCADE, db_column='promo_id', verbose_name="活動")
    used_at = models.DateTimeField(null=True, blank=True, verbose_name="最後使用時間")
    usage_count = models.IntegerField(default=0, verbose_name="使用次數")  # 使用次數
    # 新增以下欄位：
    valid_from = models.DateTimeField(null=True, blank=True, verbose_name="有效起始時間")
    valid_until = models.DateTimeField(null=True, blank=True, verbose_name="有效結束時間")

    class Meta:
        db_table = "user_promotions"
        unique_together = (('user', 'promo'),)
        verbose_name = "會員優惠"
        verbose_name_plural = "會員優惠"

    def __str__(self):
        return f"User {self.user.user_id} - Promo {self.promo.promo_id}"


# -------------------------------------------------------------------
# 6. 商品表 (products)
# -------------------------------------------------------------------
class Products(models.Model):
    product_id = models.AutoField(primary_key=True, verbose_name="商品編號")
    name = models.CharField(max_length=255, verbose_name="商品名稱")
    description = models.TextField(null=True, blank=True, verbose_name="商品描述(短)")
    long_description = models.TextField(null=True, blank=True, verbose_name="商品描述(長)")
    suitable_for = models.CharField(max_length=255, null=True, blank=True, verbose_name="適用於")   # 頭髮 / 臉部 / 身體等
    usage_instructions = models.TextField(null=True, blank=True, verbose_name="使用方式")
    shelf_life = models.IntegerField(null=True, blank=True, verbose_name="保存期限(月)")  # 以「月」為單位

    # 若商品無廠商 (或多家廠商)，可 on_delete=models.SET_NULL；看您實際需求
    supplier = models.ForeignKey(
        'Suppliers',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_column='supplier_id', 
        verbose_name="供應商"
    )

    created_at = models.DateTimeField(auto_now_add=True, verbose_name="建立時間")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="更新時間")

    class Meta:
        db_table = "products"
        verbose_name = "商品"
        verbose_name_plural = "商品"

    def __str__(self):
        return self.name


# -------------------------------------------------------------------
# 7. 商品規格變體 (product_variants)
# -------------------------------------------------------------------
class ProductVariants(models.Model):
    variant_id = models.AutoField(primary_key=True, verbose_name="商品規格變體編號")
    product = models.ForeignKey(Products, on_delete=models.CASCADE, db_column='product_id', verbose_name="商品名稱")
    package = models.ForeignKey('PackageTypes', on_delete=models.CASCADE, db_column='package_id', verbose_name="包裝類型")
    size = models.ForeignKey('ProductSizes', on_delete=models.CASCADE, db_column='size_id', null=True, blank=True, verbose_name="商品容量")
    fragrance = models.ForeignKey('ProductFragrances', on_delete=models.CASCADE, db_column='fragrance_id', null=True, blank=True, verbose_name="香氣")
    origin = models.ForeignKey('ProductOrigins', on_delete=models.CASCADE, db_column='origin_id', verbose_name="產地")
    price = models.IntegerField(verbose_name="價格")
    is_gift = models.BooleanField(default=False, verbose_name="是否為贈品")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="建立時間")

    class Meta:
        db_table = "product_variants"
        verbose_name = "商品和規格"
        verbose_name_plural = "商品和規格"

    def __str__(self):
        # return f"Variant {self.variant_id} of {self.product}"
        return f"({self.variant_id}){self.product}{self.size}{self.package}"
        

# -------------------------------------------------------------------
# 8. 分類 (categories & product_category - M:N 關聯)
# -------------------------------------------------------------------
class Categories(models.Model):
    category_id = models.AutoField(primary_key=True, verbose_name="商品分類編號")
    category_name = models.CharField(max_length=100, unique=True, verbose_name="商品分類名稱")

    class Meta:
        db_table = "categories"
        verbose_name = "分類"
        verbose_name_plural = "分類"

    def __str__(self):
        return self.category_name


class ProductCategory(models.Model):
    product = models.ForeignKey(Products, on_delete=models.CASCADE, db_column='product_id', verbose_name="商品名稱")
    category = models.ForeignKey(Categories, on_delete=models.CASCADE, db_column='category_id', verbose_name="商品分類")

    class Meta:
        db_table = "product_category"
        unique_together = (('product', 'category'),)
        verbose_name = "商品分類"
        verbose_name_plural = "商品分類"

    def __str__(self):
        return f"{self.product} -> {self.category}"


# -------------------------------------------------------------------
# 4-1. 支援「特定商品達成數量門檻」 (PromotionTargetVariants)
# -------------------------------------------------------------------

class PromotionTargetVariants(models.Model):
    promo = models.ForeignKey(Promotions, on_delete=models.CASCADE, db_column='promo_id', verbose_name="活動")
    variant = models.ForeignKey(ProductVariants, on_delete=models.CASCADE, db_column='variant_id', verbose_name="商品")

    class Meta:
        db_table = "promotion_target_variants"
        unique_together = (('promo', 'variant'),)
        verbose_name = "活動限定商品"
        verbose_name_plural = "活動限定商品"

    def __str__(self):
        return f"Promo {self.promo.promo_id} 限定商品 {self.variant.variant_id}"



# -------------------------------------------------------------------
# 4-2. 支援「特定分類達成數量門檻」 (PromotionTargetCategories)
# -------------------------------------------------------------------

class PromotionTargetCategories(models.Model):
    promo = models.ForeignKey(Promotions, on_delete=models.CASCADE, db_column='promo_id', verbose_name="活動")
    category = models.ForeignKey(Categories, on_delete=models.CASCADE, db_column='category_id', verbose_name="分類")

    class Meta:
        db_table = "promotion_target_categories"
        unique_together = (('promo', 'category'),)
        verbose_name = "活動限定分類"
        verbose_name_plural = "活動限定分類"

    def __str__(self):
        return f"Promo {self.promo.promo_id} 限定分類 {self.category.category_name}"

# -------------------------------------------------------------------
# 9. 各種選項 (PackageTypes, ProductSizes, ProductFragrances, ProductOrigins)
# -------------------------------------------------------------------
class PackageTypes(models.Model):
    package_id = models.AutoField(primary_key=True, verbose_name="包裝類型編號")
    package_name = models.CharField(max_length=50, unique=True, verbose_name="包裝類型")

    class Meta:
        db_table = "package_types"
        verbose_name = "包裝類型"
        verbose_name_plural = "包裝類型"

    def __str__(self):
        return self.package_name


class ProductSizes(models.Model):
    size_id = models.AutoField(primary_key=True, verbose_name="商品容量編號")
    size_value = models.CharField(max_length=50, unique=True, verbose_name="容量")

    class Meta:
        db_table = "product_sizes"
        verbose_name = "商品容量"
        verbose_name_plural = "商品容量"

    def __str__(self):
        return self.size_value


class ProductFragrances(models.Model):
    fragrance_id = models.AutoField(primary_key=True, verbose_name="商品香味編號")
    fragrance_name = models.CharField(max_length=100, unique=True, verbose_name="香味")

    class Meta:
        db_table = "product_fragrances"
        verbose_name = "商品香味"
        verbose_name_plural = "商品香味"

    def __str__(self):
        return self.fragrance_name


class ProductOrigins(models.Model):
    origin_id = models.AutoField(primary_key=True, verbose_name="商品產地編號")
    origin_name = models.CharField(max_length=100, unique=True, verbose_name="產地")

    class Meta:
        db_table = "product_origins"
        verbose_name = "商品產地"
        verbose_name_plural = "商品產地"

    def __str__(self):
        return self.origin_name


# -------------------------------------------------------------------
# 10. 功效 (product_effectiveness) & product_effectiveness_map (M:N)
# -------------------------------------------------------------------
class ProductEffectiveness(models.Model):
    effectiveness_id = models.AutoField(primary_key=True, verbose_name="商品功效編號")
    effectiveness_name = models.CharField(max_length=50, unique=True, verbose_name="功效")

    class Meta:
        db_table = "product_effectiveness"
        verbose_name = "功效"
        verbose_name_plural = "功效"

    def __str__(self):
        return self.effectiveness_name


class ProductEffectivenessMap(models.Model):
    product = models.ForeignKey(Products, on_delete=models.CASCADE, db_column='product_id', verbose_name="商品")
    effectiveness = models.ForeignKey(ProductEffectiveness, on_delete=models.CASCADE, db_column='effectiveness_id', verbose_name="功效")

    class Meta:
        db_table = "product_effectiveness_map"
        unique_together = (('product', 'effectiveness'),)
        verbose_name = "商品功效"
        verbose_name_plural = "商品功效"

    def __str__(self):
        return f"{self.product} - {self.effectiveness}"


# -------------------------------------------------------------------
# 11. 成分 (product_ingredients) & product_ingredients_map (M:N)
# -------------------------------------------------------------------
class ProductIngredients(models.Model):
    ingredient_id = models.AutoField(primary_key=True, verbose_name="商品成分編號")
    ingredient_name = models.CharField(max_length=100, unique=True, verbose_name="成分")

    class Meta:
        db_table = "product_ingredients"
        verbose_name = "成分"
        verbose_name_plural = "成分"

    def __str__(self):
        return self.ingredient_name


class ProductIngredientsMap(models.Model):
    product = models.ForeignKey(Products, on_delete=models.CASCADE, db_column='product_id', verbose_name="商品")
    ingredient = models.ForeignKey(ProductIngredients, on_delete=models.CASCADE, db_column='ingredient_id', verbose_name="成分")

    class Meta:
        db_table = "product_ingredients_map"
        unique_together = (('product', 'ingredient'),)
        verbose_name = "商品成分"
        verbose_name_plural = "商品成分"

    def __str__(self):
        return f"{self.product} - {self.ingredient}"


# -------------------------------------------------------------------
# 12. 商品圖片 (product_images)
#     多張圖片對應同一個 variant_id
# -------------------------------------------------------------------
class ProductImages(models.Model):
    image_id = models.AutoField(primary_key=True, verbose_name="商品圖片編號")
    variant = models.ForeignKey(ProductVariants, on_delete=models.CASCADE, db_column='variant_id', verbose_name="商品")
    image_name = models.CharField(max_length=50, verbose_name="圖片名稱")
    display_order = models.IntegerField(default=0, verbose_name="排列順序")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="建立時間")

    class Meta:
        db_table = "product_images"
        verbose_name = "商品圖片"
        verbose_name_plural = "商品圖片"

    def __str__(self):
        return f"Image {self.image_id} for Variant {self.variant_id}"


# -------------------------------------------------------------------
# 13. 活動圖片 (promotion_images)
# -------------------------------------------------------------------
class PromotionImages(models.Model):
    image_id = models.AutoField(primary_key=True, verbose_name="活動圖片編號")
    promo = models.ForeignKey(Promotions, on_delete=models.CASCADE, db_column='promo_id', verbose_name="活動")
    image_name = models.CharField(max_length=255, verbose_name="圖片名稱")
    display_order = models.IntegerField(default=0, verbose_name="排列順序")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="建立時間")

    class Meta:
        db_table = "promotion_images"
        verbose_name = "活動圖片"
        verbose_name_plural = "活動圖片"

    def __str__(self):
        return f"Promotion Image {self.image_id} for Promo {self.promo_id}"


# -------------------------------------------------------------------
# 14. 贈品表 (promotion_gifts) - M:N 關聯
# -------------------------------------------------------------------
class PromotionGifts(models.Model):
    promo = models.ForeignKey(Promotions, on_delete=models.CASCADE, db_column='promo_id', verbose_name="活動")
    variant = models.ForeignKey(ProductVariants, on_delete=models.CASCADE, db_column='variant_id', verbose_name="商品")
    gift_quantity = models.IntegerField(default=1, verbose_name="贈品數")

    class Meta:
        db_table = "promotion_gifts"
        unique_together = (('promo', 'variant'),)
        verbose_name = "活動贈品"
        verbose_name_plural = "活動贈品"

    def __str__(self):
        return f"{self.promo} => Gift: {self.variant} x {self.gift_quantity}"


# -------------------------------------------------------------------
# 15. 推薦商品表 (recommended_products)
# -------------------------------------------------------------------
RECOMMENDED_FOR_CHOICES = (
    ('所有用戶', '所有用戶'),
    ('特定會員', '特定會員'),
    ('熱門商品', '熱門商品'),
)

class RecommendedProducts(models.Model):
    recommendation_id = models.AutoField(primary_key=True, verbose_name="推薦商品編號")
    variant = models.ForeignKey(ProductVariants, on_delete=models.CASCADE, db_column='variant_id', verbose_name="商品")
    recommended_for = models.CharField(max_length=10, choices=RECOMMENDED_FOR_CHOICES, verbose_name="推薦對象")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="建立時間")

    class Meta:
        db_table = "recommended_products"
        verbose_name = "推薦商品"
        verbose_name_plural = "推薦商品"

    def __str__(self):
        return f"Recommended {self.variant} for {self.recommended_for}"


# -------------------------------------------------------------------
# 16. 訂單 (orders)
# -------------------------------------------------------------------
SHIPPING_METHOD_CHOICES = (
    ('宅配', '宅配'),
    ('超商取貨', '超商取貨'),
    ('郵寄', '郵寄'),
)

PAYMENT_METHOD_CHOICES = (
    ('信用卡', '信用卡'),
    ('ATM', 'ATM'),
    ('貨到付款', '貨到付款'),
    # 其他...
)

ORDER_STATUS_CHOICES = (
    ('待付款', '待付款'),
    ('已付款', '已付款'),
    ('已出貨', '已出貨'),
    ('已完成', '已完成'),
    ('已取消', '已取消'),
    ('退貨中', '退貨中'),
    ('已退貨', '已退貨'),
)

class Orders(models.Model):
    order_id = models.AutoField(primary_key=True, verbose_name="訂單編號")
    user = models.ForeignKey(Users, on_delete=models.CASCADE, db_column='user_id', verbose_name="會員")
    order_number = models.CharField(max_length=20, unique=True, blank=True, verbose_name="訂單號碼")  # 新增訂單號碼欄位
    
    # 收件人相關欄位
    recipient_name = models.CharField(max_length=100, verbose_name="收件人姓名")  # 收件人名稱
    recipient_phone = models.CharField(max_length=20, verbose_name="收件人電話")  # 收件人電話
    recipient_email = models.EmailField(null=True, blank=True, verbose_name="電子郵件") # Email
    
    shipping_method = models.CharField(
        max_length=20, 
        choices=SHIPPING_METHOD_CHOICES, 
        null=True, 
        blank=True,
        verbose_name="寄送方式"
    )
    shipping_address = models.TextField(verbose_name="寄送地址")
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHOD_CHOICES, null=True, blank=True, verbose_name="付款方式")
    total_price = models.IntegerField(default=0, verbose_name="商品總金額") # 商品總金額
    discount_amount = models.IntegerField(default=0, verbose_name="折扣金額") # 折扣金額
    shipping_fee = models.IntegerField(default=0, verbose_name="運費") # 運費
    final_price = models.IntegerField(default=0, verbose_name="最終應付金額") # 最終應付金額
    order_status = models.CharField(max_length=10, choices=ORDER_STATUS_CHOICES, default='待付款', verbose_name="訂單狀態")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="建立時間")
    status_updated_at = models.DateTimeField(auto_now=True, verbose_name="更新時間")

    class Meta:
        db_table = "orders"
        verbose_name = "訂單"
        verbose_name_plural = "訂單"

    def __str__(self):
        return f"Order {self.order_id} - User {self.user_id}"
        
    def save(self, *args, **kwargs):
        # 如果訂單號碼尚未生成，則生成
        if not self.order_number:
            self.generate_order_number()
        super().save(*args, **kwargs)

    # 更新:確保即使多筆訂單在同一分鐘內創建，流水號仍會遞增
    def generate_order_number(self):
        now = self.created_at or datetime.now()
        date_str = now.strftime("%Y%m%d%H%M")  # 訂單號碼的前綴（年月日時分）

        # 查詢當前分鐘內的最大訂單號
        last_order = Orders.objects.filter(order_number__startswith=date_str).aggregate(Max('order_number'))
        
        last_order_number = last_order["order_number__max"]

        if last_order_number:
            last_serial = int(last_order_number[-3:]) + 1
        else:
            last_serial = 1

        self.order_number = f"{date_str}{last_serial:03d}"    

# -------------------------------------------------------------------
# 16-1. 訂單優惠 (Order_applied_promotions)
# -------------------------------------------------------------------

class OrderAppliedPromotions(models.Model):
    order = models.ForeignKey(Orders, on_delete=models.CASCADE, verbose_name="訂單")
    promo = models.ForeignKey(Promotions, on_delete=models.CASCADE, verbose_name="活動")
    source = models.CharField(max_length=10, choices=[('auto', '自動套用'), ('coupon', '優惠碼')], verbose_name="優惠套用方式")
    
    # 折扣金額（非贈品活動可用）
    discount_amount = models.IntegerField(default=0, verbose_name="折扣金額")

    # 贈品資訊（可為 null）
    gift_variant = models.ForeignKey(ProductVariants, null=True, blank=True, on_delete=models.SET_NULL, verbose_name="贈品")
    gift_quantity = models.PositiveIntegerField(null=True, blank=True, verbose_name="贈品數量")

    class Meta:
        db_table = "order_applied_promotions"
        verbose_name = "訂單優惠"
        verbose_name_plural = "訂單優惠"
    

# -------------------------------------------------------------------
# 17. 訂單詳情 (order_items)
# -------------------------------------------------------------------
class OrderItems(models.Model):
    order_item_id = models.AutoField(primary_key=True, verbose_name="訂單詳情編號")
    order = models.ForeignKey(Orders, on_delete=models.CASCADE, db_column='order_id', verbose_name="訂單")
    variant = models.ForeignKey(ProductVariants, on_delete=models.CASCADE, db_column='variant_id', verbose_name="商品")
    quantity = models.IntegerField(verbose_name="數量")
    price = models.IntegerField(verbose_name="價格")
    subtotal = models.IntegerField(verbose_name="小計")

    class Meta:
        db_table = "order_items"
        verbose_name = "訂單詳情"
        verbose_name_plural = "訂單詳情"

    def __str__(self):
        return f"Item {self.order_item_id} (Order {self.order_id})"
           

# -------------------------------------------------------------------
# 18. 廠商列表 (suppliers)
# -------------------------------------------------------------------
class Suppliers(models.Model):
    supplier_id = models.AutoField(primary_key=True, verbose_name="供應商編號")
    supplier_name = models.CharField(max_length=255, unique=True, verbose_name="供應商名稱")
    phone = models.CharField(max_length=50, verbose_name="電話")
    address = models.TextField(verbose_name="地址")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="建立時間")

    class Meta:
        db_table = "suppliers"
        verbose_name = "供應商"
        verbose_name_plural = "供應商"

    def __str__(self):
        return self.supplier_name


# -------------------------------------------------------------------
# 19. 進貨紀錄 (stock_in)
# -------------------------------------------------------------------
class StockIn(models.Model):
    stock_in_id = models.AutoField(primary_key=True, verbose_name="進貨紀錄及庫存編號")
    variant = models.ForeignKey(ProductVariants, on_delete=models.CASCADE, db_column='variant_id', verbose_name="商品")
    supplier = models.ForeignKey(Suppliers, on_delete=models.CASCADE, db_column='supplier_id', verbose_name="廠商")
    quantity = models.IntegerField(verbose_name="進貨數量")
    purchase_price = models.IntegerField(verbose_name="進貨價格")
    received_date = models.DateTimeField(auto_now_add=True, verbose_name="進貨日期")
    expiration_date = models.DateField(null=True, blank=True, verbose_name="有效期限")
    remaining_quantity = models.IntegerField(verbose_name="該批次剩餘庫存數量")

    class Meta:
        db_table = "stock_in"
        verbose_name = "進貨紀錄及庫存"
        verbose_name_plural = "進貨紀錄及庫存"

    def __str__(self):
        return f"StockIn {self.stock_in_id} - Variant {self.variant_id}"


# -------------------------------------------------------------------
# 20. 商品評價 (product_reviews)
#     一個會員對同一訂單內相同商品(variant) 僅能評價一次
# -------------------------------------------------------------------
class ProductReviews(models.Model):
    review_id = models.AutoField(primary_key=True, verbose_name="商品評價編號")
    order = models.ForeignKey(Orders, on_delete=models.CASCADE, db_column='order_id', verbose_name="訂單")
    user = models.ForeignKey(Users, on_delete=models.CASCADE, db_column='user_id', verbose_name="會員")
    variant = models.ForeignKey(ProductVariants, on_delete=models.CASCADE, db_column='variant_id', verbose_name="商品")
    # 可考慮加上 Validator：1~5
    rating = models.IntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)], verbose_name="評價")
    review_text = models.TextField(null=True, blank=True, verbose_name="評價內容")
    review_image = models.TextField(null=True, blank=True, verbose_name="圖片")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="建立時間")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="更新時間")

    class Meta:
        db_table = "product_reviews"
        unique_together = (('order', 'user', 'variant'),)
        verbose_name = "商品評價"
        verbose_name_plural = "商品評價"

    def __str__(self):
        return f"Review {self.review_id} by User {self.user_id}"


# -------------------------------------------------------------------
# 21. 意見回饋 (feedbacks)
# -------------------------------------------------------------------
FEEDBACK_CATEGORY_CHOICES = (
    ('網站問題', '網站問題'),
    ('商品問題', '商品問題'),
    ('配送問題', '配送問題'),
    ('客服問題', '客服問題'),
    ('其他', '其他'),
)

class Feedbacks(models.Model):
    feedback_id = models.AutoField(primary_key=True, verbose_name="意見回饋編號")
    user = models.ForeignKey(Users, on_delete=models.CASCADE, db_column='user_id', verbose_name="會員")
    feedback_category = models.CharField(max_length=10, choices=FEEDBACK_CATEGORY_CHOICES, default='其他', verbose_name="意見分類")
    feedback_text = models.TextField(verbose_name="回饋內容")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="建立時間")

    class Meta:
        db_table = "feedbacks"
        verbose_name = "意見回饋"
        verbose_name_plural = "意見回饋"

    def __str__(self):
        return f"Feedback {self.feedback_id} - {self.feedback_category}"


# -------------------------------------------------------------------
# 22. 公告訊息 (announcements)
# -------------------------------------------------------------------
ANNOUNCEMENT_TYPE_CHOICES = (
    ('系統公告', '系統公告'),
    ('促銷活動', '促銷活動'),
    ('政策變更', '政策變更'),
    ('其他', '其他'),
)

class Announcements(models.Model):
    announcement_id = models.AutoField(primary_key=True, verbose_name="公告訊息編號")
    announcement_type = models.CharField(max_length=10, choices=ANNOUNCEMENT_TYPE_CHOICES, default='系統公告', verbose_name="公告類型")
    title = models.CharField(max_length=255, verbose_name="標題")
    content = models.TextField(verbose_name="公告內容")
    start_date = models.DateTimeField(auto_now_add=True, verbose_name="開始時間")
    end_date = models.DateTimeField(null=True, blank=True, verbose_name="結束時間")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="建立時間")

    class Meta:
        db_table = "announcements"
        verbose_name = "公告訊息"
        verbose_name_plural = "公告訊息"

    def __str__(self):
        return self.title
    
# -------------------------------------------------------------------
# 22. 我的最愛 (Favorite)
# -------------------------------------------------------------------

class Favorite(models.Model):
    user = models.ForeignKey(Users, on_delete=models.CASCADE, verbose_name="商品追蹤編號")
    variant = models.ForeignKey(ProductVariants, on_delete=models.CASCADE, verbose_name="追蹤商品")
    added_at = models.DateTimeField(auto_now_add=True, verbose_name="追蹤日期")

    class Meta:
        db_table = "favorite"
        unique_together = ('user', 'variant')
        verbose_name = "我的最愛"
        verbose_name_plural = "我的最愛"

    def __str__(self):
        return f"{self.user} 收藏了 {self.variant}"
