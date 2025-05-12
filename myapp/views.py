
from django.http import HttpResponse
from django.http import JsonResponse
from myapp.models import *
import datetime #
from datetime import date
from datetime import datetime, timedelta
from django.utils.timezone import now
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
import json
from math import floor
from myapp.forms import OrderForm
from django.contrib import messages
from django.views.decorators.http import require_POST
from django.db.models import Sum
from django.template.loader import render_to_string
from django.core.mail import EmailMultiAlternatives
from django.core.mail import EmailMessage
from django.core.paginator import Paginator
from django.conf import settings
from django.shortcuts import render, redirect, get_object_or_404
from django.db.models import Q
from django.contrib.auth.hashers import make_password, check_password
import random
import string
import pytz


# 取得每個變體的第一張圖片
def get_product_image(variant):
    image = ProductImages.objects.filter(variant=variant).order_by('display_order').first()
    return image.image_name if image else 'default.png'

# 首頁
def homepage(request):
    login_status = request.session.get("username") is not None          # 檢查登入狀態

    user_id = request.session.get("user_id") if login_status else None  # 避免未登入時變數未定義

    # 取得每個活動的第一張圖片
    def get_promotion_image(promo):
        image = PromotionImages.objects.filter(promo=promo).order_by('display_order').first()
        return image.image_name if image else 'default.png'

    promo_items = []
    promos = Promotions.objects.filter(promo_id__lte=3)
    for promo in promos:
        promo_image_name = get_promotion_image(promo.promo_id)
        promo_items.append({"promo_image_name": promo_image_name})
    
    # 獲取所有用戶的推薦商品
    recommended_products = RecommendedProducts.objects.filter(recommended_for='所有用戶').select_related('variant__product')

    # 獲取熱門商品（熱銷商品）
    hot_products = RecommendedProducts.objects.filter(recommended_for='熱門商品').select_related('variant__product')

    # 準備推薦商品資料
    recommended_items = []
    for rp in recommended_products:
        variant = rp.variant
        product = variant.product
        image_name = get_product_image(variant)

        category_ids = list(
            ProductCategory.objects.filter(product=product)
            .values_list('category_id', flat=True)
        )

        stock_total = StockIn.objects.filter(variant=variant).aggregate(
            total=Sum('remaining_quantity')
        )['total'] or 0

        recommended_items.append({
            "variant_id": str(variant.variant_id),
            "product_id": product.product_id,
            "category_ids": category_ids,
            "product_name": product.name,
            "size": variant.size.size_value if variant.size else '',
            "package": variant.package.package_name,
            "price": variant.price,
            "image_name": image_name,
            "stock_total": stock_total,
        })

    # 準備熱銷商品資料
    hot_items = []
    for hp in hot_products:
        variant = hp.variant
        product = variant.product
        image_name = get_product_image(variant)

        category_ids = list(
            ProductCategory.objects.filter(product=product)
            .values_list('category_id', flat=True)
        )

        stock_total = StockIn.objects.filter(variant=variant).aggregate(
            total=Sum('remaining_quantity')
        )['total'] or 0

        hot_items.append({
            "variant_id": str(variant.variant_id),
            "product_id": product.product_id,
            "category_ids": category_ids,
            "product_name": product.name,
            "size": variant.size.size_value if variant.size else '',
            "package": variant.package.package_name,
            "price": variant.price,
            "image_name": image_name,
            "stock_total": stock_total,
        })

    return render(request, 'homepage.html', {
        'promo_items': promo_items,
        'recommended_items': recommended_items,
        'hot_items': hot_items,
    })

# 搜尋
def search(request):
    login_status = request.session.get("username") is not None  # 檢查登入狀態
    variants = ProductVariants.objects.select_related('product', 'size', 'package')

    sort = request.GET.get('sort')  #'price_asc'、'price_desc'、'latest'

    search = request.GET.get('search')
    if search is not None:
        search = search.strip()
        if search :
            keywords = search.split()
            q_objects = Q()

            for keyword in keywords:
                q_objects |= Q(product__name__icontains=keyword)
                q_objects |= Q(product__suitable_for__icontains=keyword)
                q_objects |= Q(size__size_value__icontains=keyword)
                q_objects |= Q(package__package_name__icontains=keyword)

            # 找到符合條件的產品
            variants = variants.filter(q_objects).distinct()

    else:
        variants = ProductVariants.objects.all()


    # 準備前端需要的欄位資訊
    product_list = []
    for variant in variants:
        product = variant.product
        image_name = get_product_image(variant)

        category_ids = list(
            ProductCategory.objects.filter(product=product)
            .values_list('category_id', flat=True)
        )

        stock_total = StockIn.objects.filter(variant=variant).aggregate(
            total=Sum('remaining_quantity')
        )['total'] or 0

        product_item = {
            "variant_id": str(variant.variant_id),
            "product_id": product.product_id,
            "category_ids": category_ids,
            "product_name": product.name,
            "size": variant.size.size_value if variant.size else '',
            "package": variant.package.package_name,
            "price": variant.price,
            "image_name": image_name,
            "created_at": variant.created_at,
            "stock_total": stock_total,
        }

        product_list.append(product_item)

        # 預設：根據 size (size_value) 由大到小排序
    product_list.sort(key=lambda x: x["size"], reverse=True)
    # print(product_list)

    # 排序邏輯
    if sort == 'price_asc':
        product_list.sort(key=lambda x: x['price'])
    elif sort == 'price_desc':
        product_list.sort(key=lambda x: x['price'], reverse=True)
    elif sort == 'latest':
        product_list.sort(key=lambda x: x['created_at'], reverse=True)

    # 分頁處理，每頁顯示 12 筆商品
    paginator = Paginator(product_list, 12)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    # 如果是 AJAX 請求，僅回傳部分 HTML
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        html = render_to_string("partials/search_list_items.html", {
            "page_obj": page_obj,
            "search": search,
            "selected_sort": sort
        }, request=request)
        return JsonResponse({"html": html})


    return render(request, "search.html", {
        "page_obj": page_obj,
        "search": search,
        "selected_sort": sort
    })


# 註冊會員
def register(request):
    # 檢查是否已經登入，若已登入則跳轉首頁
    if "username" in request.session:
        return redirect("/")
    
    if request.method == "POST":
        username = request.POST["username"]
        password = request.POST["password"]
        email = request.POST["email"]

        # 帳號長度檢查
        if len(username) < 5:
            message = "帳號長度至少 5 個字元"
            return render(request, "register.html", {"message": message})
        
        # 密碼長度檢查
        elif len(password) < 6 or len(password) > 12:
            message = "密碼長度須為 6-12 個字元"
            return render(request, "register.html", {"message": message, "username": username})
        
        elif AuthUsers.objects.filter(username=username).exists():
            message = "此帳號已被註冊"
            return render(request, "register.html", {"message": message})
        
        # 檢查 email 是否已經被註冊
        elif AuthUsers.objects.filter(email=email).exists():
            message = "此信箱已被註冊"
            return render(request, "register.html", {"message": message, "username": username})
        
        else:
            # 先創建 Users 並儲存
            user = Users.objects.create()

            # 創建 AuthUsers，並綁定 user_id
            auth_user = AuthUsers.objects.create(
                user=user,
                username=username,
                email=email,
                password=make_password(password)        # 加密密碼
            )

            # 設定本地時區（台灣）
            local_timezone = pytz.timezone("Asia/Taipei")

            # 找到會員優惠券的促銷活動
            try:
                promotion = Promotions.objects.get(promo_code="WELCOME100")

                # 獲取當前時間（使用 UTC 時間）
                utc_time = timezone.now()

                # 將 UTC 時間轉換為當地時間
                local_time = utc_time.astimezone(local_timezone)

                # 設定優惠券的有效期限（有效期 30 天）
                valid_from = local_time
                valid_until = (valid_from + timedelta(days=30)).replace(hour=23, minute=59, second=59)

                # 創建 UserPromotions 來綁定優惠券給新會員
                UserPromotions.objects.create(
                    user=user,
                    promo=promotion,
                    usage_count=0,  # 使用次數為 0
                    valid_from=valid_from,
                    valid_until=valid_until
                )
            except Promotions.DoesNotExist:
                pass    # 若找不到優惠券則跳過，不影響註冊流程

            # 會員註冊成功後寄送歡迎信
            html_content = f"""
            <html>
                <body style="background-color: rgb(252, 252, 240); width: 500px">
                <header style="background-color: rgb(165, 188, 201); text-align: center; padding: 2px">
                    <h2>CUI LIANG SHI</h2> 
                </header>
                <div style="padding-left: 10px;">
                    <p>您好，<b>{username}</b>：</p>
                    <p>感謝您加入 CUI LIANG SHI！我們已為您註冊成功 🎉</p>
                    <p>系統已發送迎新優惠券（WELCOME100）至您的帳戶，登入後即可查看與使用！</p>
                    <p>歡迎造訪我們的網站體驗輕奢保養的魅力。</p>
                </div>
                <hr style="border: none; border-top: 1px solid #DDD;">
                <footer style="font-size: 12px; color: #666; padding: 10px;">
                    <p>此信件由系統自動發送，請勿直接回覆。</p>
                    <p>如有任何問題，請聯繫 <a href="mailto:support@skincare.com">support@skincare.com</a>。</p>
                </footer>
                </body>
            </html>
            """
            email_message = EmailMessage(
                subject="歡迎加入 CUI LIANG SHI！",
                body=html_content,
                to=[email]
            )
            email_message.content_subtype = "html"
            email_message.send()

            # 讓使用者登入後直接跳轉到會員中心
            request.session["username"] = auth_user.username
            request.session["user_id"] = auth_user.user.user_id
            request.session["show_welcome_modal"] = True
            return redirect(f"/users/{user.user_id}/")    
    else:
        return render(request, "register.html")

# 會員中心
def users(request, id=None):
    username = request.session.get("username")      # 檢查使用者
    if not username:
        request.session["modal_message"] = "請先登入會員！"
        request.session["modal_type"] = "error"
        return redirect("/login/")                  # 未登入跳轉到登入頁

    user_id = request.session.get("user_id")

    # 取得 AuthUsers 資料
    auth_user = get_object_or_404(AuthUsers, username=username)

    # 確保登入者只能查看自己的會員中心
    if id is None or auth_user.user.user_id != id:
        return redirect(f"/users/{auth_user.user.user_id}/")  # 跳轉回自己的頁面

    user = auth_user.user  # 取得對應的 Users 資料

    # 歡迎提示彈窗
    show_modal = request.session.pop("show_welcome_modal", False)

    # 處理 modal 訊息
    modal_message = request.session.pop("modal_message", "")
    modal_type = request.session.pop("modal_type", "")  # 可為 success / error

    if request.method == "POST":
        # 更新會員個人資料
        user.name = request.POST["name"]
        user.gender = request.POST["gender"]

        # 避免生日存入空字串，並轉換成 datetime
        birthday_str = request.POST.get("birthday", "").strip()  # 取得生日欄位並去掉空白
        user.birthday = datetime.strptime(birthday_str, "%Y-%m-%d").date() if birthday_str else None

        phone = request.POST.get("phone", "").strip()

        # 檢查電話號碼是否已被其他會員使用
        if phone and Users.objects.filter(Q(phone=phone) & ~Q(user_id=user.user_id)).exists():
            modal_message = "此電話號碼已被其他會員使用，請使用其他號碼！"
            modal_type = "error"
        else:
            user.phone = phone
            user.address = request.POST["address"]
            user.save()
            modal_message = "資料更新成功！"
            modal_type = "success"

    # **將 GENDER_CHOICES 傳入模板**
    gender_choices = Users._meta.get_field("gender").choices

    return render(request, "users.html", {
        "user": user,
        "auth_user": auth_user,
        "show_modal": show_modal,
        "modal_message": modal_message,
        "modal_type": modal_type,
        "gender_choices": gender_choices,
    })

# 會員登入
def user_login(request):
    # 檢查是否已經登入，若已登入則跳轉首頁
    if "username" in request.session:
        return redirect("/")
    
    # 取出 modal 訊息（如果有）
    modal_message = request.session.pop("modal_message", "")
    modal_type = request.session.pop("modal_type", "")

    message = ""
    login_status = False

    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")

        try:
            auth_user = AuthUsers.objects.get(username=username)
            if check_password(password, auth_user.password):            # 驗證密碼
                request.session["username"] = auth_user.username        # 設置 session
                request.session["user_id"] = auth_user.user.user_id     # 存入 user_id
                # messages.success(request, f"{username}您好")
                login_status = True
                request.session["login_status"] = login_status
                return redirect("/")  # 登入成功後返回首頁
            else:
                message = "帳號或密碼錯誤!"
        except AuthUsers.DoesNotExist:
            message = "帳號或密碼錯誤!"

    return render(request, "login.html", {
        "modal_message": modal_message,
        "modal_type": modal_type,
        "message": message,
    })

# 會員登出
def user_logout(request):
    # if "username" in request.session:
    #     del request.session["username"]
    #     del request.session["user_id"]
    request.session.flush()  # 清空所有 session

    return redirect("/")  # 登出後返回首頁

# 檢查會員帳號
def check_username(request):
    username = request.GET.get("username", "").strip()
    is_available = not AuthUsers.objects.filter(username=username).exists()
    return JsonResponse({"available": is_available})

# 修改密碼
def edit(request):
    login_status = request.session.get("username") is not None  # 檢查登入狀態
    username = request.session.get("username")                  # 檢查使用者
    if not username:
        return redirect("/login/")                              # 未登入跳轉到登入頁
    
    user_id = request.session.get("user_id")

    # 取得 AuthUsers 資料
    auth_user = get_object_or_404(AuthUsers, username=username)
    # 取得對應的 Users 資料
    user = auth_user.user  

    if request.method == "POST":
        current_password = request.POST.get("current_password")
        new_password = request.POST.get("new_password")
        confirm_password = request.POST.get("confirm_password")

        # 驗證舊密碼
        if not check_password(current_password, auth_user.password):
            message = "舊密碼錯誤！"
        elif new_password != confirm_password:
            message = "新密碼與確認新密碼不符！"
        elif len(new_password) < 6 or len(new_password) > 12:
            message = "新密碼長度須為 6-12 個字元！"
        else:
            # 更新密碼
            auth_user.password = make_password(new_password)
            auth_user.save()
            request.session["modal_message"] = "密碼更新成功!"
            request.session["modal_type"] = "success"
            return redirect(f"/users/{user.user_id}/")
    
    return render(request, "edit.html", locals())

# 會員優惠券
def coupons(request):
    login_status = request.session.get("username") is not None  # 檢查登入狀態
    username = request.session.get("username")                  # 檢查使用者
    if not username:
        return redirect("/login/")                              # 未登入跳轉到登入頁

    user_id = request.session.get("user_id")

    tab = request.GET.get('tab', 'active')  # 預設為可使用
    print(tab)

    now = timezone.now()

    if tab == 'used':
        user_promotions = UserPromotions.objects.filter(
            user_id=user_id,
            promo_id=3,
            usage_count__gt=0
        )
    elif tab == 'expired':
        user_promotions = UserPromotions.objects.filter(
            user_id=user_id,
            promo_id=3,
            usage_count=0,
            valid_until__lt=now
        )
    else:  # 可使用
        user_promotions = UserPromotions.objects.filter(
            user_id=user_id,
            promo_id=3,
            usage_count=0
        ).filter(
            Q(valid_until__isnull=True) | Q(valid_until__gt=now)
        )

    # 取得活動的圖片
    images = PromotionImages.objects.filter(promo_id=3).order_by('display_order')

    # 取得第二張（index 1），若有的話
    coupon_image = images[1] if images.count() > 1 else None

    # return render(request, "coupons.html", locals())
    return render(request, "coupons.html", {
    'user_promotions': user_promotions,
    'tab': tab,
    'coupon_image': coupon_image,
    })

# 會員訂單查詢
def orders(request):
    login_status = request.session.get("username") is not None  # 檢查登入狀態
    username = request.session.get("username")                  # 檢查使用者
    if not username:
        return redirect("/login/")                              # 未登入跳轉到登入頁
    
    # 處理 modal 訊息
    modal_message = request.session.pop("modal_message", "")
    modal_type = request.session.pop("modal_type", "") 
    
    user_id = request.session.get("user_id")
    now = timezone.now()

    user_orders = Orders.objects.filter(user_id=user_id).order_by("-created_at")

    for order in user_orders:
        # 如果訂單狀態尚未取消或完成，並且建立時間在 12 小時內
        time_diff = now - order.created_at
        order.cancelable = (
            order.order_status in ["待付款", "已付款"]
            and time_diff <= timedelta(hours=12)
        )

    return render(request, "orders.html", locals())

@csrf_exempt
def cancel_order(request, order_number):
    login_status = request.session.get("username") is not None  # 檢查登入狀態
    username = request.session.get("username")                  # 檢查使用者
    if not username:
        return redirect("/login/")                              # 未登入跳轉到登入頁

    if request.method == "POST":
        order = get_object_or_404(Orders, order_number=order_number)

        order.order_status = "已取消"
        order.save()
        request.session["modal_message"] = "訂單已成功取消!"
        request.session["modal_type"] = "success"
        return redirect("/orders/")
        
    else:
        return redirect("/orders/")

# 訂單詳情
def details(request, number=None):
    login_status = request.session.get("username") is not None  # 檢查登入狀態
    username = request.session.get("username")                  # 檢查使用者
    if not username:
        return redirect("/login/")                              # 未登入跳轉到登入頁

    user_id = request.session.get("user_id")
    
    # 取得訂單，但限制只能查看自己的訂單
    order = get_object_or_404(Orders, order_number=number, user_id=user_id)

    # 取得該訂單的所有商品
    order_items = OrderItems.objects.filter(order=order)

    product_images = {
    item: ProductImages.objects.filter(variant=item.variant).order_by('display_order').first()
    for item in order_items
    }

    return render(request, "details.html", {
        "order": order,
        "order_items": order_items,
        "product_images": product_images,
        "promotions": order.promotion if hasattr(order, "promotion") else None
    })

# 會員追蹤清單
def favorites(request):
    login_status = request.session.get("username") is not None  # 檢查登入狀態
    username = request.session.get("username")                  # 檢查使用者
    if not username:
        return redirect("/login/")                              # 未登入跳轉到登入頁
    
    user_id = request.session.get("user_id")

    # 查詢該會員的追蹤清單
    favorite_qs = Favorite.objects.filter(user_id=user_id).select_related('variant__product', 'variant__size', 'variant__package')

    favorite_items = []
    for fav in favorite_qs:
        variant = fav.variant
        product = variant.product

        # 取圖
        image_name = get_product_image(variant)

        # 商品類別
        category_ids = list(
            ProductCategory.objects.filter(product=product)
            .values_list('category_id', flat=True)
        )

        # 查庫存
        stock_total = StockIn.objects.filter(variant=variant).aggregate(
            total=Sum('remaining_quantity')
        )['total'] or 0

        # 加入資料
        favorite_items.append({
            "variant_id": str(variant.variant_id),
            "product_id": product.product_id,
            "category_ids": category_ids,
            "product_name": product.name,
            "size": variant.size.size_value if variant.size else '',
            "package": variant.package.package_name if variant.package else '',
            "price": variant.price,
            "image_name": image_name,
            "stock_total": stock_total,
            "added_at": fav.added_at,
        })

    return render(request, "favorites.html", {
        "favorites": favorite_items})
		
# 刪除追蹤清單
def favorite_delete(request, favorite_id):
    if not request.session.get("user_id"):
        return redirect("/login/")

    try:
        favorite = Favorite.objects.get(variant_id=favorite_id, user_id=request.session.get("user_id"))
        favorite.delete()
    except Favorite.DoesNotExist:
        pass

    return redirect("/favorites/")
    
def generate_random_password(length=12):
    """生成 12 字元的隨機密碼"""
    characters = string.ascii_letters + string.digits
    return ''.join(random.choice(characters) for _ in range(length))

# 忘記密碼
def reset_password(request):
    if request.method == "POST":
        email = request.POST.get("email")

        # 無論信箱是否存在，都回傳相同訊息
        request.session["modal_message"] = "若該信箱有註冊，我們已寄出新密碼，請前往信箱查收。"
        request.session["modal_type"] = "info"

        try:
            auth_user = AuthUsers.objects.get(email=email)      # 查詢該 Email 是否存在
            new_password = generate_random_password()           # 生成隨機新密碼 
            auth_user.password = make_password(new_password)    # 加密並更新密碼
            auth_user.save()

            html_content = f"""
            <html>
                <body style="background-color: rgb(252, 252, 240); width: 500px">
                <header style="background-color: rgb(165, 188, 201); text-align: center; padding: 2px">
                    <h2>CUI LIANG SHI</h2> 
                </header>
                <div style="padding-left: 10px;">
                    <p>您好，<b>{auth_user.username}</b>：</p>
                    <p>我們已收到您的密碼重置請求，以下是您的新密碼：</p>
                    <p style="font-size: 18px; font-weight: bold; color: #333;">{new_password}</p>
                    <p>請使用此密碼登入您的帳戶，並在<span style="color: red;">登入後盡快修改密碼以確保安全。</span></p>
                </div>
                <hr style="border: none; border-top: 1px solid #DDD;">
                <footer style="font-size: 12px; color: #666; padding: 10px;">
                    <p>此信件由系統自動生成，請勿直接回覆。</p>
                    <p>如有疑問，請聯絡 <a href="mailto:support@skincare.com">support@skincare.com</a>。</p>
                </footer>
                </body>
            </html>
            """

            # 發送 HTML 格式的郵件
            email_message = EmailMessage(
                subject="您的新密碼",
                body=html_content,
                from_email="noreply@yourdomain.com",
                to=[email]
            )
            email_message.content_subtype = "html"  # 設置為 HTML 格式
            email_message.send()

            return redirect("/login/")  # 導回登入頁

        except AuthUsers.DoesNotExist:
            # pass  # 故意什麼都不做，避免洩漏帳號資訊
            return redirect("/login/")  # 導回登入頁

    return render(request, "password_reset.html")


def get_login_status(request):
    # login_status = request.session.get("login_status", False)
    login_status = request.session.get("username", None),
    user_id = request.session.get("user_id", None)
    return JsonResponse({
        'login_status': login_status,
        'user_id': user_id,
    })


def product_list(request):

    # 使用者目前點選的分類篩選條件
    category_id = request.GET.get('category')

    sort = request.GET.get('sort')  #'price_asc'、'price_desc'、'latest'

    products = Products.objects.filter(
        productcategory__category_id=category_id
    ).prefetch_related('productvariants_set__productimages_set')
    # print(products)

    product_list = []
    for product in products:
        for variant in product.productvariants_set.all():
            image = variant.productimages_set.first()

            if image:
                image_name = image.image_name
            else:
                image_name = "no_image.png"

            # 某個商品所屬的所有分類 ID 清單
            category_ids = list(
                ProductCategory.objects.filter(product=product)
                .values_list('category_id', flat=True)
            )

            stock_total = StockIn.objects.filter(variant=variant).aggregate(
                total=Sum('remaining_quantity')
            )['total'] or 0

            product_item = {
                "variant_id": str(variant.variant_id),
                "product_id": product.product_id,
                "category_ids": category_ids,
                "product_name": product.name,
                "size": variant.size.size_value,
                "package": variant.package.package_name,
                "price": variant.price,
                "image_name": image_name,
                "created_at": variant.created_at,  # for latest sort
                "stock_total": stock_total 
            }
            product_list.append(product_item)

    # 預設：根據 size (size_value) 由大到小排序
    product_list.sort(key=lambda x: x["size"], reverse=True)
    # print(product_list)

    # 排序邏輯
    if sort == 'price_asc':
        product_list.sort(key=lambda x: x['price'])
    elif sort == 'price_desc':
        product_list.sort(key=lambda x: x['price'], reverse=True)
    elif sort == 'latest':
        product_list.sort(key=lambda x: x['created_at'], reverse=True)

    # 分頁處理，每頁顯示 12 筆商品
    paginator = Paginator(product_list, 12)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    # 如果是 AJAX 請求，僅回傳部分 HTML
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        html = render_to_string("partials/product_list_items.html", {
            "page_obj": page_obj,
            "selected_category": category_id,
            "selected_sort": sort
        }, request=request)
        return JsonResponse({"html": html})


    return render(request, "product_list.html", {
        "page_obj": page_obj,
        "selected_category": category_id,
        "selected_sort": sort
    })


def product_detail(request):
    quantity_range = range(1, 16)  # 產生 1 到 15 的範圍

    variant_id = request.GET.get('variant', 0)

    # 一次 select_related 多個關聯，減少後續查詢
    variant = get_object_or_404(
        ProductVariants.objects.select_related(
            'product__supplier', 'size', 'package', 'fragrance', 'origin'
        ),
        variant_id=variant_id
    )

    # 取得該 variant 對應的 product
    product = variant.product

    # 查詢成分
    ingredients = ProductIngredients.objects.filter(
        productingredientsmap__product=product).values_list('ingredient_name', flat=True)
    # print(ingredients)

    # 查詢功效
    effectiveness = ProductEffectiveness.objects.filter(
        producteffectivenessmap__product=product).values_list('effectiveness_name', flat=True)
    # print(effectiveness)

    # 查詢圖片
    image = ProductImages.objects.filter(
        variant_id=variant_id).values_list('image_name', flat=True).first()
    # print(image)

    category_ids = list(
        ProductCategory.objects.filter(product=product)
        .values_list('category_id', flat=True)
    )

    # 主要分類（通常取第一個）
    main_category_id = category_ids[0] if category_ids else None

    category_name = None
    if main_category_id:
        category = Categories.objects.filter(category_id=main_category_id).first()
        category_name = category.category_name if category else None

    stock_total = StockIn.objects.filter(variant_id=variant_id).aggregate(
        total=Sum('remaining_quantity')
    )['total'] or 0

    context = {
        'product_name': variant.product.name,
        'variant_id': variant_id,
        'product_id': product.product_id,
        'category_ids': category_ids,
        "category_name": category_name,
        'price': variant.price,
        'size': variant.size.size_value if variant.size else None,
        'package': variant.package.package_name if variant.package else None,
        'description': variant.product.description,
        'long_description': variant.product.long_description,
        'fragrance': variant.fragrance.fragrance_name if variant.fragrance else None,
        'origin': variant.origin.origin_name if variant.origin else None,
        'shelf_life': variant.product.shelf_life,
        'suitable_for': variant.product.suitable_for,
        'usage_instructions': variant.product.usage_instructions,
        'supplier_name': variant.product.supplier.supplier_name if variant.product.supplier else None,
        'supplier_phone': variant.product.supplier.phone if variant.product.supplier else None,
        'supplier_address': variant.product.supplier.address if variant.product.supplier else None, 
        'stock_total': stock_total
    }
    # print(context)

    return render(request, 'product_detail.html', locals())


@require_POST
def toggle_favorite(request):
    user_id = request.session.get('user_id')
    if not user_id:
        return JsonResponse({'success': False, 'message': '請先登入'}, status=401)

    variant_id = request.POST.get('variant_id')
    try:
        user = Users.objects.get(user_id=user_id)
        variant = ProductVariants.objects.get(variant_id=variant_id)
    except (Users.DoesNotExist, ProductVariants.DoesNotExist):
        return JsonResponse({'success': False, 'message': '無效的商品'}, status=400)

    favorite, created = Favorite.objects.get_or_create(
        user=user, variant=variant)
    if not created:
        favorite.delete()
        return JsonResponse({'success': True, 'status': 'removed'})
    else:
        return JsonResponse({'success': True, 'status': 'added'})


def get_favorites(request):
    user_id = request.session.get("user_id")
    if not user_id:
        return JsonResponse({'favorite_variant_ids': []})

    try:
        user = Users.objects.get(user_id=user_id)
        favorite_ids = list(Favorite.objects.filter(
            user=user).values_list('variant_id', flat=True))
        return JsonResponse({'favorite_variant_ids': favorite_ids})
    except Users.DoesNotExist:
        return JsonResponse({'favorite_variant_ids': []})


def add_cart(request):
    # 判斷是否已經登入
    if not request.session.get('user_id'):
        return JsonResponse({'success': False, 'message': '請先登入會員！'}, status=401)

    if request.method == 'POST':
        variant_id = str(request.POST.get('variant'))
        product_id = int(request.POST.get('product_id'))
        # category_ids = list(map(int, request.POST.get('category_ids', '').split(',')))
        category_ids = request.POST.get('category_ids', '')
        category_ids = [int(cid)
                        for cid in category_ids.split(',') if cid.isdigit()]

        name = request.POST.get('name')
        size = request.POST.get('size')
        package = request.POST.get('package')
        price = int(request.POST.get('price', 0))
        image = request.POST.get('image_name')
        number = int(request.POST.get('number', 1))  # 預設為 1，若未傳入則設為 1

        # 取得目前購物車中該商品已加入的數量
        cart = request.session.get('cart', {})
        if not isinstance(cart, dict):
            cart = {}
        current_quantity_in_cart = cart.get(variant_id, {}).get('quantity', 0)

        # 查詢該商品在庫的總剩餘數量
        stock_total = StockIn.objects.filter(variant_id=variant_id).aggregate(
            total=Sum('remaining_quantity')
        )['total'] or 0

        # 如果超過庫存
        if current_quantity_in_cart + number > stock_total:
            return JsonResponse({
                'success': False,
                'message': '商品庫存不足，無法加入購物車！'
            }, status=400)

        if variant_id in cart:
            # 商品已存在，增加數量
            cart[variant_id]['quantity'] += number
            # 更新小計
            cart[variant_id]['subtotal'] = cart[variant_id]['price'] * \
                cart[variant_id]['quantity']
        else:
            # 新增商品
            cart[variant_id] = {
                'product_id': product_id,
                'category_ids': category_ids,
                'name': name,
                'size': size,
                'package': package,
                'price': price,
                'quantity': number,
                'subtotal': price * number,
                'image': image
            }

        # 更新購物車到 session
        request.session['cart'] = cart
        request.session.modified = True  # 標記 session 資料已修改

        # print(cart)  # 確認購物車內容
        # print("variant:", variant_id, "分類:", category_ids)

        return JsonResponse({
            'success': True,
            'message': f"{name} {size} 已加入購物車",
            # 傳回購物車商品數量
            'cart_count': sum(item['quantity'] for item in cart.values())
        })

    return JsonResponse({'success': False, 'message': '無效的請求'}, status=400)


def get_cart_count(request):
    cart = request.session.get('cart', {})
    count = sum(item['quantity']
                for item in cart.values()) if isinstance(cart, dict) else 0
    return JsonResponse({'cart_count': count})


def cart(request):

    # 判斷有無登入，沒有則導向登入頁面
    if not request.session.get('user_id'):
        messages.warning(request, "請先登入才能查看購物車")
        return redirect('/login/')

    # 如果購物車不存在，則取空字典，但不直接存入 session
    cart = request.session.get('cart', {})
    if not isinstance(cart, dict):
        cart = {}
        request.session['cart'] = cart
        request.session.modified = True

    # 如果沒有傳入 selected_keys，預設為「全部選取」
    selected_keys = list(cart.keys())

    total = sum(item['subtotal'] for item in cart.values())  # 直接用 sum 計算總價

    # 套用自動折扣與贈品
    auto_discount, auto_gift_list, auto_discount_list = apply_auto_promotions(
        request, cart, selected_keys)

    # 優惠碼相關資料從 session 中取出
    coupon_discount = int(request.session.get('coupon_discount', 0))
    coupon_discount_list = request.session.get('coupon_discount_list', [])
    coupon_gift_list = request.session.get('coupon_gift_list', [])

    # 合併折扣與贈品
    total_discount = auto_discount + coupon_discount
    all_gifts = auto_gift_list + coupon_gift_list
    active_promotions = auto_discount_list + coupon_discount_list

    # 最終金額
    final_total = max(0, total - total_discount)

    # 計算運費與最終金額
    shipping_cost = 0 if total >= 2500 else 100
    final_total = max(0, total - total_discount + shipping_cost)

    return render(request, "cart.html", {
        'cart': cart,
        'total': total,
        'discount': total_discount,
        'final_total': final_total,
        'shipping_cost': shipping_cost,
        'gifts': all_gifts,
        'active_promotions': active_promotions
    })


def update_cart_item(request, key, quantity):
    cart = request.session.get('cart', {})
    if not isinstance(cart, dict):
        cart = {}

    if key in cart:

        try:
            # 查詢商品的剩餘庫存
            stock_total = StockIn.objects.filter(variant_id=key).aggregate(
                total=Sum('remaining_quantity')
            )['total'] or 0

            # 如果超過庫存，不允許更新
            if quantity > stock_total:
                return JsonResponse({
                    'success': False,
                    'message': '商品庫存不足，無法更新數量！',
                    'stock_limit': stock_total
                }, status=400)

            # 更新數量和小計
            cart[key]['quantity'] = quantity
            cart[key]['subtotal'] = cart[key]['price'] * quantity
            request.session['cart'] = cart
            request.session.modified = True

            return JsonResponse({
                'success': True,
                'subtotal': cart[key]['subtotal'],
                'cart_count': sum(item['quantity'] for item in cart.values()),
            })

        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)}, status=500)

    return JsonResponse({'success': False})


def remove_cart_item(request, key):
    cart = request.session.get('cart', {})
    if not isinstance(cart, dict):
        cart = {}

    if key in cart:
        del cart[key]
        request.session['cart'] = cart
        request.session.modified = True

        cart_count = sum(item['quantity'] for item in cart.values())
        total = sum(item['subtotal'] for item in cart.values())

        return JsonResponse({
            'success': True,
            'cart_count': cart_count,
        })

    return JsonResponse({'success': False})

# 計算總金額（僅計算選取的商品）
def calculate_total(cart, selected_keys):
    total = sum(item['subtotal']
                for key, item in cart.items() if key in selected_keys)
    return total


def apply_coupon(request):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': '無效的請求'})

    coupon_code = request.POST.get('coupon_code', '').strip()
    selected_keys = json.loads(request.POST.get('selected_keys', '[]'))
    cart = request.session.get('cart', {})
    user_id = request.session.get('user_id')

    if not coupon_code:
        return JsonResponse({'success': False, 'message': '請輸入優惠碼'})

    # 檢查優惠碼是否存在於 promotions 表中
    try:
        promo = Promotions.objects.get(promo_code=coupon_code)
    except Promotions.DoesNotExist:
        return JsonResponse({'success': False, 'message': '優惠碼不存在'})

    current_time = now()

    # 活動時間檢查
    if not (promo.start_date <= current_time <= promo.end_date):
        return JsonResponse({'success': False, 'message': '此優惠碼已超出活動期間，無法使用'})

    user_promo = None
    if promo.receive_method == '先發放':
        try:
            # 檢查會員是否擁有此優惠碼
            user_promo = UserPromotions.objects.get(
                user_id=user_id, promo=promo)
            if user_promo.valid_from and user_promo.valid_until:
                if not (user_promo.valid_from <= current_time <= user_promo.valid_until):
                    return JsonResponse({'success': False, 'message': '此優惠碼已過期或尚未生效'})
        except UserPromotions.DoesNotExist:
            return JsonResponse({'success': False, 'message': '您尚未獲得此優惠碼'})

    elif promo.receive_method == '自由輸入':
        user_promo, _ = UserPromotions.objects.get_or_create(
            user_id=user_id,
            promo=promo,
            defaults={
                'valid_from': promo.start_date,
                'valid_until': promo.end_date,
                'usage_count': 0
            }
        )

    # 使用次數限制：活動總次數與每位會員次數
    if promo.usage_limit is not None:
        used_total = UserPromotions.objects.filter(promo=promo).aggregate(
            Sum('usage_count'))['usage_count__sum'] or 0
        if used_total >= promo.usage_limit:
            return JsonResponse({'success': False, 'message': '此優惠碼已達總使用上限'})

    if promo.per_user_limit is not None and user_promo:
        if user_promo.usage_count >= promo.per_user_limit:
            return JsonResponse({'success': False, 'message': '您已達優惠碼使用上限'})

    # 計算符合優惠活動條件的商品數量與金額
    promo_targets = list(PromotionTargetVariants.objects.filter(
        promo=promo).values_list('variant_id', flat=True))
    promo_categories = list(PromotionTargetCategories.objects.filter(
        promo=promo).values_list('category_id', flat=True))

    total_quantity = 0
    total = 0
    for key in selected_keys:
        item = cart.get(key)
        if not item:
            continue
        variant_id = int(key)
        category_ids = item.get('category_ids', [])

        is_qualified = (
            (promo_targets and variant_id in promo_targets) or
            (promo_categories and set(category_ids) & set(promo_categories)) or
            (not promo_targets and not promo_categories)
        )

        if is_qualified:
            total_quantity += item['quantity']
            total += item['subtotal']

    if promo.trigger_quantity and total_quantity < promo.trigger_quantity:
        return JsonResponse({'success': False, 'message': f'未達使用條件，最低購買數量需達 {promo.trigger_quantity} 件'})

    if promo.minimum_spending and total < promo.minimum_spending:
        return JsonResponse({'success': False, 'message': f'未達使用條件，最低消費金額需達 {promo.minimum_spending:.0f} 元'})

    # 折扣計算
    coupon_discount = 0
    coupon_discount_list = []

    if promo.discount_type == '固定金額折扣':
        times = floor(
            total / promo.minimum_spending) if promo.is_accumulative_discount else 1
        coupon_discount = int(times * promo.discount_value)
    elif promo.discount_type == '百分比折扣':
        times = floor(
            total / promo.minimum_spending) if promo.is_accumulative_discount else 1
        rate = (100 - promo.discount_value) / 100
        coupon_discount = int(total - (total * (rate ** times)))

    if coupon_discount > 0:
        coupon_discount_list.append({
            'promo_id': promo.promo_id,
            'promo_name': promo.promo_name,
            'conditions': promo.conditions,
            'discount': coupon_discount
        })

    # 贈品處理
    coupon_gift_list = []
    if promo.discount_type == '贈品':
        promo_gifts = PromotionGifts.objects.filter(promo=promo)
        for gift in promo_gifts:
            times = floor(
                total / promo.minimum_spending) if promo.is_accumulative_gift else 1
            quantity = int(gift.gift_quantity) * times

            stock_total = StockIn.objects.filter(variant_id=gift.variant.variant_id).aggregate(
                total=Sum('remaining_quantity')
            )['total'] or 0

            if stock_total < quantity:
                return JsonResponse({'success': False, 'message': '贈品庫存不足，無法套用此優惠碼'})

            coupon_gift_list.append({
                'promo_id': promo.promo_id,
                'promo_name': promo.promo_name,
                'conditions': promo.conditions,
                'variant_id': gift.variant.variant_id,
                'product_name': gift.variant.product.name,
                'size': gift.variant.size.size_value if gift.variant.size else '',
                'package': gift.variant.package.package_name if gift.variant.package else '',
                'quantity': quantity,
                'source': 'coupon'
            })

    # 儲存優惠資訊至 session
    request.session['promo_code'] = promo.promo_code
    request.session['coupon_discount'] = coupon_discount
    request.session['coupon_discount_list'] = coupon_discount_list
    request.session['coupon_gift_list'] = coupon_gift_list
    request.session.modified = True

    return JsonResponse({'success': True, 'message': '優惠碼已套用'})


@require_POST
def cancel_coupon(request):
    request.session.pop('promo_code', None)
    request.session['coupon_discount'] = 0
    request.session['coupon_discount_list'] = []
    request.session['coupon_gift_list'] = []
    request.session.modified = True

    return JsonResponse({'success': True})


# 定義自動套用活動的邏輯
def apply_auto_promotions(request, cart, selected_keys):

    user_id = request.session.get('user_id')
    total = sum(item['subtotal']
                for key, item in cart.items() if key in selected_keys)

    auto_discount = 0
    auto_discount_list = []
    auto_gift_list = []

    now_time = now()
    member_level = None

    # 查詢會員等級（如有登入）
    if user_id:
        try:
            user = Users.objects.select_related('level').get(user_id=user_id)
            member_level = user.level
        except Users.DoesNotExist:
            pass

    # 查詢自動套用活動（一般 + VIP）
    auto_promos = Promotions.objects.filter(
        start_date__lte=now_time,
        end_date__gte=now_time,
        apply_method='自動套用',
        is_vip_only=False
    )

    vip_promos = Promotions.objects.none()
    if member_level:
        vip_promos = Promotions.objects.filter(
            start_date__lte=now_time,
            end_date__gte=now_time,
            apply_method='自動套用',
            is_vip_only=True,
            target_levels=member_level
        )

    all_auto_promos = list(auto_promos) + list(vip_promos)

    for promo in all_auto_promos:
        # 活動總使用次數限制
        if promo.usage_limit is not None:
            used_count = UserPromotions.objects.filter(promo=promo).aggregate(
                models.Sum('usage_count'))['usage_count__sum'] or 0
            if used_count >= promo.usage_limit:
                continue

        # 單一會員使用次數限制
        if user_id and promo.per_user_limit is not None:
            user_used_count = UserPromotions.objects.filter(
                user_id=user_id, promo=promo).aggregate(Sum('usage_count'))['usage_count__sum'] or 0
            if user_used_count >= promo.per_user_limit:
                continue

        # 取得活動指定商品與分類
        promo_targets = list(PromotionTargetVariants.objects.filter(
            promo=promo).values_list('variant_id', flat=True))
        promo_categories = list(PromotionTargetCategories.objects.filter(
            promo=promo).values_list('category_id', flat=True))

        # 計算符合活動條件的商品數量
        total_quantity = 0
        for key in selected_keys:
            item = cart[key]
            variant_id = int(key)
            category_ids = item.get('category_ids', [])
            category_ids = [int(cid) for cid in category_ids]  # 確保是 int

            if promo_targets and variant_id in promo_targets:
                total_quantity += item['quantity']
            elif promo_categories and set(category_ids) & set(promo_categories):
                total_quantity += item['quantity']
            elif not promo_targets and not promo_categories:
                # 活動未設定指定商品或分類，視為全商品皆適用
                total_quantity += item['quantity']

        # 檢查數量與金額門檻
        if promo.trigger_quantity and total_quantity < promo.trigger_quantity:
            continue

        if promo.minimum_spending and total < promo.minimum_spending:
            continue

        # 折扣與贈品邏輯
        if promo.discount_type == '固定金額折扣':
            if promo.is_accumulative_discount:
                if promo.minimum_spending and promo.minimum_spending > 0:
                    times = floor(total / promo.minimum_spending)
                elif promo.trigger_quantity and total_quantity >= promo.trigger_quantity:
                    times = floor(total_quantity / promo.trigger_quantity)
                else:
                    times = 1
            else:
                times = 1

            discount = int(times * promo.discount_value)
            auto_discount += discount
            auto_discount_list.append({
                'promo_id': promo.promo_id,
                'promo_name': promo.promo_name,
                'conditions': promo.conditions,
                'discount': discount
            })

        elif promo.discount_type == '百分比折扣':
            if promo.is_accumulative_discount:
                if promo.minimum_spending and promo.minimum_spending > 0:
                    times = floor(total / promo.minimum_spending)
                elif promo.trigger_quantity and total_quantity >= promo.trigger_quantity:
                    times = floor(total_quantity / promo.trigger_quantity)
                else:
                    times = 1
            else:
                times = 1

            rate = (100 - promo.discount_value) / 100
            discount = int(total - (total * (rate ** times)))
            auto_discount += discount
            auto_discount_list.append({
                'promo_id': promo.promo_id,
                'promo_name': promo.promo_name,
                'conditions': promo.conditions,
                'discount': discount
            })

        elif promo.discount_type == '贈品':
            promo_gifts = PromotionGifts.objects.filter(promo=promo)
            for gift in promo_gifts:
                # 累贈邏輯：可依照 trigger_quantity 或 minimum_spending 判斷
                if promo.is_accumulative_gift:
                    if promo.trigger_quantity and total_quantity >= promo.trigger_quantity:
                        times = floor(total_quantity / promo.trigger_quantity)
                    elif promo.minimum_spending and promo.minimum_spending > 0 and total >= promo.minimum_spending:
                        times = floor(total / promo.minimum_spending)
                    else:
                        times = 0
                else:
                    times = 1 if (
                        (promo.trigger_quantity and total_quantity >= promo.trigger_quantity) or
                        (promo.minimum_spending and promo.minimum_spending >
                        0 and total >= promo.minimum_spending)
                    ) else 0

                expected_quantity = int(gift.gift_quantity) * times

                stock_total = StockIn.objects.filter(variant_id=gift.variant.variant_id).aggregate(
                    total=Sum('remaining_quantity')
                )['total'] or 0
                actual_quantity = min(expected_quantity, stock_total)

                if actual_quantity > 0:
                    auto_gift_list.append({
                        'promo_id': promo.promo_id,
                        'promo_name': promo.promo_name,
                        'conditions': promo.conditions,
                        'variant_id': gift.variant.variant_id,
                        'product_name': gift.variant.product.name,
                        'size': gift.variant.size.size_value if gift.variant.size else '',
                        'package': gift.variant.package.package_name if gift.variant.package else '',
                        'quantity': actual_quantity,
                        'source': 'auto'
                    })

    # 更新 session
    request.session['auto_discount'] = int(auto_discount)
    request.session['auto_discount_list'] = auto_discount_list
    request.session['auto_gift_list'] = auto_gift_list
    request.session.modified = True

    return auto_discount, auto_gift_list, auto_discount_list


def update_cart_summary(request):
    if request.method == 'POST':
        selected_keys = json.loads(request.POST.get('selected_keys', '[]'))
        cart = request.session.get('cart', {})

        # 只計算選取商品的總金額
        total = sum(
            item['subtotal'] for key, item in cart.items() if key in selected_keys
        )

        # 套用自動折扣與贈品
        auto_discount, auto_gift_list, auto_discount_list = apply_auto_promotions(
            request, cart, selected_keys)

        # 優惠碼資訊（若存在）
        coupon_discount = int(request.session.get('coupon_discount', 0))
        coupon_discount_list = request.session.get('coupon_discount_list', [])
        coupon_gift_list = request.session.get('coupon_gift_list', [])

        # 合併折扣與贈品（前端顯示用）
        all_discounts = auto_discount_list + coupon_discount_list
        all_gifts = auto_gift_list + coupon_gift_list

        # 運費與最終金額
        shipping_cost = 0 if total >= 2500 else 100
        final_total = max(0, total - auto_discount -
                        coupon_discount + shipping_cost)

        return JsonResponse({
            'total': total,
            'discount': auto_discount + coupon_discount,
            'final_total': final_total,
            'shipping_cost': shipping_cost,
            'active_promotions': all_discounts,
            'gifts': all_gifts
        })


def save_selected_items(request):
    if request.method == 'POST':
        selected_keys = json.loads(request.POST.get('selected_keys', '[]'))
        request.session['selected_keys'] = selected_keys
        request.session['allow_check_order'] = True  # 只在「結帳按鈕點擊」時才設定
        request.session.modified = True
        return JsonResponse({'success': True})
    return JsonResponse({'success': False})


def check_order(request):
    cart = request.session.get('cart', {})  
    if not isinstance(cart, dict):
        cart = {}

    selected_keys = request.session.get('selected_keys')
    allow_check_order = request.session.pop('allow_check_order', False)  # pop 完就失效

    # 若無選擇任何商品，導回購物車
    if not selected_keys or not allow_check_order:
        messages.warning(request, "請先在購物車中選擇商品再進入訂單確認")
        return redirect('cart')

    selected_items = {
        key: item for key, item in cart.items() if key in selected_keys
    }

    total = sum(item['subtotal'] for item in selected_items.values())
    shipping_cost = 0 if total >= 2500 else 100

    # 自動/優惠碼 折扣、贈品
    auto_discount = int(request.session.get('auto_discount', 0))
    coupon_discount = int(request.session.get('coupon_discount', 0))
    final_total = max(0, total - auto_discount -
                    coupon_discount + shipping_cost)

    gifts = request.session.get(
        'auto_gift_list', []) + request.session.get('coupon_gift_list', [])
    active_promotions = request.session.get(
        'auto_discount_list', []) + request.session.get('coupon_discount_list', [])
    coupon_code = request.session.get('promo_code', '')

    user_id = request.session.get('user_id')
    user = Users.objects.get(pk=user_id)
    auth_user = AuthUsers.objects.get(user=user)

    # 建立表單，設定 initial 預設值
    form = OrderForm(initial={
        'name': user.name,
        'phone': user.phone,
        'email': auth_user.email,
    })

    return render(request, 'check_order.html', {
        'selected_items': selected_items,
        'total': total,
        'shipping_cost': shipping_cost,
        'discount': auto_discount + coupon_discount,
        'final_total': final_total,
        'gifts': gifts,
        'active_promotions': active_promotions,
        'coupon_code': coupon_code,
        'form': form,
    })


def batch_deduct_stock(items, is_gift=False, strict=True, simulate=False):
    """
    批次扣除庫存（主商品或贈品）

    參數：
        items (list): 商品或贈品清單，結構需含 variant_id 與 quantity
        is_gift (bool): 是否為贈品，會影響錯誤訊息顯示
        strict (bool): 是否強制完全滿足數量，若為 False，則自動調整為可購買數量
            嚴格模式（strict=True）：數量不足就中止。
            寬鬆模式（strict=False）：自動調整實際扣除數量，並顯示提示訊息（主商品 or 贈品）。
        simulate (bool): 是否僅模擬檢查，不實際扣庫存

    回傳：
        (bool, str, list): 是否成功、錯誤訊息、實際扣除數量清單（含 variant_id, actual_qty）
    """
    adjusted_items = []

    for item in items:
        variant_id = item.get('variant_id')
        requested_qty = item.get('quantity', 0)
        actual_deducted = 0

        if not variant_id or requested_qty <= 0:
            continue

        remaining_qty = requested_qty
        stock_ins = StockIn.objects.filter(
            variant_id=variant_id,
            remaining_quantity__gt=0
        ).order_by('expiration_date', 'received_date')

        for stock in stock_ins:
            if remaining_qty <= 0:
                break
            deduct_qty = min(stock.remaining_quantity, remaining_qty)
            if not simulate:
                stock.remaining_quantity -= deduct_qty
                stock.save()
            actual_deducted += deduct_qty
            remaining_qty -= deduct_qty

        if remaining_qty > 0:
            if strict:
                try:
                    variant = ProductVariants.objects.select_related('product').get(variant_id=variant_id)
                    product_name = f"{variant.product.name} {variant.size} {variant.package}"
                except ProductVariants.DoesNotExist:
                    product_name = f"ID {variant_id}"
                label = "贈品" if is_gift else "商品"
                return False, f"{label}「{product_name}」庫存不足", []
            else:
                adjusted_items.append({
                    'variant_id': variant_id,
                    'actual_quantity': actual_deducted,
                    'requested_quantity': requested_qty,
                })
        else:
            adjusted_items.append({
                'variant_id': variant_id,
                'actual_quantity': requested_qty,
                'requested_quantity': requested_qty,
            })

    return True, "", adjusted_items


def order_completed(request):
    if request.method == "POST":
        form = OrderForm(request.POST)
        if form.is_valid():
            cart = request.session.get("cart", {})
            selected_keys = request.session.get("selected_keys", [])
            user_id = request.session.get("user_id")
            user = Users.objects.get(user_id=user_id)

            if not selected_keys:
                # 沒有選取商品
                return redirect("cart")
            
            # 檢查自動套用優惠
            # 比對是否與 check_order 當下不同
            def serialize_discounts(lst):
                return sorted([(d['promo_id'], d['discount']) for d in lst])

            def serialize_gifts(lst):
                return sorted([(g['variant_id'], g['quantity']) for g in lst])
            
            # step 1. 先複製原本的 session
            old_auto_discount = int(request.session.get('auto_discount', 0))
            old_auto_discount_list = request.session.get('auto_discount_list', [])
            old_auto_gift_list = request.session.get('auto_gift_list', [])

            # step 2. 呼叫（會更新 session）
            apply_auto_promotions(request, cart, selected_keys)

            # step 3. 再從 session 拿出新值
            new_auto_discount = int(request.session.get('auto_discount', 0))
            new_auto_discount_list = request.session.get('auto_discount_list', [])
            new_auto_gift_list = request.session.get('auto_gift_list', [])

            # step 4. 比對差異
            if (
                new_auto_discount != old_auto_discount or
                serialize_discounts(new_auto_discount_list) != serialize_discounts(old_auto_discount_list) or
                serialize_gifts(new_auto_gift_list) != serialize_gifts(old_auto_gift_list)
            ):
                messages.warning(request, "活動優惠內容已有變更或失效，請重新確認訂單")
                return redirect('cart')

            # 優惠碼驗證
            promo_code = request.session.get('promo_code')
            user_promo = None
            promo = None
            created = False

            if promo_code:
                try:
                    promo = Promotions.objects.get(promo_code=promo_code)
                    now = timezone.now()

                    # 時間範圍檢查
                    if promo.start_date > now or promo.end_date < now:
                        messages.warning(request, '優惠碼已過期，無法使用。')
                        return redirect('cart')

                    # 檢查全站使用次數限制
                    if promo.usage_limit is not None:
                        total_used = OrderAppliedPromotions.objects.filter(promo=promo).count()
                        if total_used >= promo.usage_limit:
                            messages.warning(request, '此優惠碼已達使用上限，無法完成訂單。')
                            return redirect('cart')

                    # 檢查會員是否持有
                    if promo.receive_method == '先發放':
                        try:
                            user_promo = UserPromotions.objects.get(
                                user=user, promo=promo)
                            if user_promo.valid_from and user_promo.valid_until:
                                if not (user_promo.valid_from <= now <= user_promo.valid_until):
                                    messages.warning(request, '此優惠碼已過期或尚未生效。')
                                    return redirect('cart')
                        except UserPromotions.DoesNotExist:
                            messages.warning(request, '您尚未獲得此優惠碼。')
                            return redirect('cart')
                    else:
                        user_promo, created = UserPromotions.objects.get_or_create(
                            user=user,
                            promo=promo,
                            defaults={
                                'usage_count': 1,
                                'used_at': timezone.now(),
                                'valid_from': promo.start_date,
                                'valid_until': promo.end_date
                            }
                        )

                    # 檢查每人使用次數限制
                    if not created and promo.per_user_limit and user_promo.usage_count >= promo.per_user_limit:
                        messages.warning(request, '此優惠碼已達使用上限，無法完成訂單。')
                        return redirect('cart')

                except Promotions.DoesNotExist:
                    promo_code = None
                    user_promo = None
                    created = False

            # 檢查主商品庫存（模擬）
            main_items = [{'variant_id': int(key), 'quantity': cart[key]['quantity']} for key in selected_keys]
            stock_ok, stock_msg, main_adjusted = batch_deduct_stock(main_items, is_gift=False, strict=True, simulate=True)
            if not stock_ok:
                messages.error(request, stock_msg)
                return redirect('cart')

            # 更新 cart 中數量、準備提示訊息
            adjusted_messages = []
            for adj in main_adjusted:
                if adj['actual_quantity'] < adj['requested_quantity']:
                    variant = ProductVariants.objects.select_related('product').get(variant_id=adj['variant_id'])
                    name = f"{variant.product.name} {variant.size} {variant.package}"
                    adjusted_messages.append(f"商品「{name}」數量不足，已自動調整為 {adj['actual_quantity']} 件")
                    cart[str(adj['variant_id'])]['quantity'] = adj['actual_quantity']

            if adjusted_messages:
                request.session['cart'] = cart
                messages.warning(request, "、".join(adjusted_messages))

            # 檢查贈品庫存（允許自動調整）
            for gift_type in ['auto_gift_list', 'coupon_gift_list']:
                gift_items = request.session.get(gift_type, [])
                stock_ok, stock_msg, gift_adjusted = batch_deduct_stock(gift_items, is_gift=True, strict=True, simulate=True)
                if not stock_ok:
                    messages.error(request, stock_msg)
                    return redirect('cart')
                for adj in gift_adjusted:
                    if adj['actual_quantity'] < adj['requested_quantity']:
                        messages.warning(request, f"贈品「{adj.get('product_name', 'ID ' + str(adj['variant_id']))}」數量不足，已自動調整為 {adj['actual_quantity']} 件")

            # 計算價格
            total_price = 0
            for key in selected_keys:
                item = cart[key]
                total_price += item['price'] * item['quantity']

            coupon_discount = int(request.session.get('coupon_discount', 0))
            total_discount =  new_auto_discount + coupon_discount

            shipping = 0 if total_price >= 2500 else 100
            final_price = total_price - total_discount + shipping

            # 收件地址組合
            full_address = f"{form.cleaned_data['city']}{form.cleaned_data['district']}{form.cleaned_data['detail_address']}"

            # 建立訂單
            order = Orders.objects.create(
                user=user,
                recipient_name=form.cleaned_data['name'],
                recipient_phone=form.cleaned_data['phone'],
                recipient_email=form.cleaned_data['email'],
                shipping_method=form.cleaned_data['ship_by'],
                shipping_address=full_address,
                payment_method=form.cleaned_data['payment'],
                total_price=total_price,
                discount_amount=total_discount,
                shipping_fee=shipping,
                final_price=final_price,
            )
            order.save()  # 自動生成 order_number

            # 建立訂單商品明細並實際扣庫存
            _, _, main_adjusted = batch_deduct_stock(main_items, is_gift=False, strict=False, simulate=False)
            for adj in main_adjusted:
                OrderItems.objects.create(
                    order=order,
                    variant_id=adj['variant_id'],
                    quantity=adj['actual_quantity'],
                    price=cart[str(adj['variant_id'])]['price'],
                    subtotal=cart[str(adj['variant_id'])]['price'] * adj['actual_quantity']
                )
            
            # 贈品扣庫存（活動與優惠碼）
            for gift_type in ['auto_gift_list', 'coupon_gift_list']: # 取出贈品清單
                gift_items = request.session.get(gift_type, [])
                batch_deduct_stock(gift_items, is_gift=True, strict=True, simulate=False)

            for promo_data in request.session.get('auto_discount_list', []):
                try:
                    promo_obj = Promotions.objects.get(promo_id=promo_data['promo_id'])  
                    OrderAppliedPromotions.objects.create(
                        order=order,
                        promo=promo_obj,
                        source='auto',
                        discount_amount=promo_data['discount']
                    )
                except Promotions.DoesNotExist:
                    continue

            for promo_data in request.session.get('coupon_discount_list', []):
                try:
                    promo_obj = Promotions.objects.get(promo_id=promo_data['promo_id'])
                    OrderAppliedPromotions.objects.create(
                        order=order,
                        promo=promo_obj,
                        source='coupon',
                        discount_amount=promo_data['discount']
                    )
                except Promotions.DoesNotExist:
                    continue  # 若找不到就略過，避免錯誤中斷整個訂單流程

            # 儲存自動套用贈品
            for gift_data in request.session.get('auto_gift_list', []):
                variant_id = gift_data.get('variant_id')
                if not variant_id:
                    continue  # 如果沒有 variant_id，略過

                try:
                    variant = ProductVariants.objects.get(
                        variant_id=variant_id)
                    promo = Promotions.objects.get(
                        promo_name=gift_data['promo_name'])

                    OrderAppliedPromotions.objects.create(
                        order=order,
                        promo=promo,
                        source='auto',
                        gift_variant=variant,
                        gift_quantity=gift_data['quantity']
                    )

                except (ProductVariants.DoesNotExist, Promotions.DoesNotExist):
                    continue  # 查不到就略過

            # 儲存優惠碼贈品
            for gift_data in request.session.get('coupon_gift_list', []):
                variant_id = gift_data.get('variant_id')
                if not variant_id:
                    continue

                try:
                    variant = ProductVariants.objects.get(
                        variant_id=variant_id)
                    promo = Promotions.objects.get(
                        promo_name=gift_data['promo_name'])

                    OrderAppliedPromotions.objects.create(
                        order=order,
                        promo=promo,
                        source='coupon',
                        gift_variant=variant,
                        gift_quantity=gift_data['quantity']
                    )

                except (ProductVariants.DoesNotExist, Promotions.DoesNotExist):
                    continue

            if promo_code and promo and user_promo and not created:
                user_promo.usage_count += 1
                user_promo.used_at = timezone.now()
                user_promo.save()

            # 清空購物車中已結帳的項目
            for key in selected_keys:
                cart.pop(key)
            request.session['cart'] = cart
            request.session['selected_keys'] = []

            request.session.pop('coupon_discount', None)
            request.session.pop('auto_discount', None)
            request.session.pop('coupon_discount_list', None)
            request.session.pop('auto_discount_list', None)
            request.session.pop('coupon_gift_list', None)
            request.session.pop('auto_gift_list', None)
            request.session.pop('promo_code', None)
            request.session.modified = True

            # 建立成功後寄送 Email 通知
            subject = "CUI LIANG SHI 訂單成立通知"
            from_email = settings.DEFAULT_FROM_EMAIL
            to_email = [form.cleaned_data['email']]

            context = {
                'name': user.name,
                'order_number': order.order_number
            }

            html_content = render_to_string(
                'emails/order_confirmation_email.html', context)

            email = EmailMultiAlternatives(subject, "", from_email, to_email)
            email.attach_alternative(
                html_content, "text/html")  # 如果 HTML 沒被支援，顯示純文字
            email.send()

            return render(request, "order_completed.html", {
                "order_number": order.order_number
            })

        else:
            # 表單驗證失敗：重新導回確認頁面，並顯示錯誤訊息
            messages.error(request, "請確認您填寫的資訊正確無誤。")

            # 重建畫面資料
            cart = request.session.get("cart", {})
            selected_keys = request.session.get("selected_keys", [])
            selected_items = {key: item for key,
                            item in cart.items() if key in selected_keys}
            total = sum(item['subtotal'] for item in selected_items.values())
            shipping_cost = 0 if total >= 2500 else 100
            auto_discount = int(request.session.get('auto_discount', 0))
            coupon_discount = int(request.session.get('coupon_discount', 0))
            final_total = max(0, total - auto_discount -
                            coupon_discount + shipping_cost)
            gifts = request.session.get(
                'auto_gift_list', []) + request.session.get('coupon_gift_list', [])
            active_promotions = request.session.get(
                'auto_discount_list', []) + request.session.get('coupon_discount_list', [])
            coupon_code = request.session.get('promo_code', '')

            return render(request, "check_order.html", {
                'selected_items': selected_items,
                'total': total,
                'shipping_cost': shipping_cost,
                'discount': auto_discount + coupon_discount,
                'final_total': final_total,
                'gifts': gifts,
                'active_promotions': active_promotions,
                'coupon_code': coupon_code,
                'form': form,
            })

    return redirect("cart")


def add_data(request):

    ##廠商列表 (suppliers)
    # 插入單筆資料
    Suppliers.objects.create(supplier_name="美美生技股份有限公司", phone="03-1231230", address="桃園市龜山區健康路1號")

    # 批量插入多筆資料
    suppliers_data = [
        Suppliers(supplier_name="自然美學國際股份有限公司", phone="02-4280338", address="台北市中山區民生東路290號"),
        Suppliers(supplier_name="綠色奇蹟國際股份有限公司", phone="02-3526505", address="台北市士林區和平東路190號"),
        Suppliers(supplier_name="極光護膚國際股份有限公司", phone="04-9237716", address="台中市信義區復興南路40號"),
        Suppliers(supplier_name="水潤之泉生技股份有限公司", phone="06-3581314", address="台南市士林區南京西路288號"),
        Suppliers(supplier_name="美麗密碼生技股份有限公司", phone="06-7713837", address="台南市信義區民生東路101號"),
        Suppliers(supplier_name="花漾之光生技股份有限公司", phone="04-5877746", address="台中市大安區中山路284號"),
        Suppliers(supplier_name="雪肌精選化妝品股份有限公司", phone="04-4830039", address="台中市大安區和平東路9號"),
        Suppliers(supplier_name="天然之選生技股份有限公司", phone="02-2680106", address="台北市中山區和平東路162號"),
        Suppliers(supplier_name="奢華美研國際股份有限公司", phone="06-1929109", address="台南市中山區復興南路238號"),
        Suppliers(supplier_name="精華時光化妝品股份有限公司", phone="07-1998789", address="高雄市士林區復興南路272號"),
    ]

    Suppliers.objects.bulk_create(suppliers_data)  # 批量插入


    ##會員等級 (membership_levels)
    membership_levels = [
        MembershipLevels(level_name="一般會員", min_spent=0, discount_rate=0),
        MembershipLevels(level_name="黃金會員", min_spent=5000, discount_rate=4),
        MembershipLevels(level_name="白金會員", min_spent=10000, discount_rate=8),
        MembershipLevels(level_name="鑽石會員", min_spent=20000, discount_rate=12),
    ]

    MembershipLevels.objects.bulk_create(membership_levels)


    ##商品表 (products)
    suppliers = {s.supplier_id: s for s in Suppliers.objects.all()}
    products = [
        Products(name="保濕洗面乳", description="● 深層保濕配方\n\n● 有效鎖住水分，使肌膚長效水潤", 
                long_description=
'''天然果萃 × 深層保濕 × 溫和潔淨

● 極致保濕，洗後不乾燥
    特別添加玻尿酸與神經醯胺，幫助肌膚維持水分平衡，潔淨後依然柔嫩水潤，適合所有膚質，特別是乾燥與敏感肌。

● 天然果萃精華，喚醒肌膚活力
    富含柑橘、蘋果、莓果萃取，蘊含維生素C與抗氧化成分，能溫和去除老廢角質，提升肌膚透亮感，讓每次洗臉都像果香SPA！

● 氨基酸溫和潔淨，敏感肌也安心
    採用氨基酸系界面活性劑，細緻泡沫能深入毛孔帶走污垢與油脂，同時溫和不刺激，維持肌膚天然屏障，讓潔面後的肌膚清爽不緊繃。

● 不含SLS / SLES、酒精、人工色素
    無添加刺激成分，降低敏感風險，給肌膚最純淨的呵護，每天享受安心洗臉體驗。

● 適合肌膚類型：
    乾性肌膚 / 敏感肌膚
    暗沉肌膚 / 需要溫和去角質者
    喜愛天然果香與清新感受的使用者

● 果香滿溢，洗出透亮水嫩肌！''',
                suitable_for="臉部", usage_instructions="取適量於掌心，加水搓揉起泡後，輕輕按摩全臉，再用溫水洗淨。",
                shelf_life=24, supplier=suppliers[1]),
        
        Products(name="控油洗面乳", description="● 獨特控油成分\n\n● 有效清潔多餘油脂，讓肌膚保持清爽",
                long_description=
'''深層潔淨 × 平衡控油 × 清爽水潤

● 綠茶精華 × 天然淨膚力
    嚴選天然綠茶萃取，富含兒茶素 (Catechin) 和 抗氧化因子，幫助對抗外界污染物，舒緩肌膚不適，讓肌膚保持健康清新狀態。

● 溫和控油，淨透毛孔
    特別添加鋅PCA與茶樹精油，有效調理皮脂分泌，減少多餘油脂堆積，預防粉刺與痘痘生成，讓肌膚時刻保持潔淨清爽。

● 氨基酸泡沫，溫和潔膚不緊繃
    使用氨基酸系界面活性劑，溫和帶走毛孔內的油脂與污垢，不傷害肌膚天然屏障，洗後清爽無負擔，不乾澀、不緊繃。

● 去油但不過度清潔，維持水油平衡
    搭配玻尿酸與甘油等保濕因子，在控油的同時維持肌膚水分，避免過度清潔導致肌膚乾燥出油惡性循環。

● 無SLS / SLES、無酒精、無人工香精
    減少刺激成分，溫和呵護肌膚，敏感肌也能安心使用。

● 適合肌膚類型：
    油性肌膚 / 混合肌膚
    容易長粉刺、痘痘肌膚
    想改善出油問題、追求清爽洗感的使用者

● 綠茶淨化 × 淨爽透亮，讓肌膚回歸清新平衡！''',
                suitable_for="臉部", usage_instructions="取適量於掌心，加水搓揉起泡後，輕輕按摩全臉，再用溫水洗淨。",
                shelf_life=24, supplier=suppliers[1]),
        
        Products(name="溫和洗面乳(敏感肌)", description="● 溫和不刺激\n\n● 特別適合敏感肌使用，減少過敏機率",
                long_description=
'''低敏配方 × 溫和潔淨 × 舒緩保濕

● 氨基酸潔膚，溫和不刺激
    採用氨基酸系界面活性劑，細緻柔軟的泡沫能夠溫和帶走污垢與多餘油脂，不破壞肌膚屏障，讓敏感肌也能享受安心潔面體驗。

● 添加神經醯胺，修護肌膚屏障
    特別添加神經醯胺 (Ceramide)，幫助修復並強化肌膚屏障，減少水分流失，提升肌膚保護力，維持水嫩柔軟感。

● 積雪草 & 燕麥萃取，舒緩敏感泛紅
    富含積雪草萃取 (CICA) 和燕麥萃取，有效舒緩乾燥、敏感與泛紅問題，幫助肌膚穩定，洗後不乾燥、不緊繃。

●️ pH5.5 弱酸性，維持肌膚健康平衡
    貼近肌膚天然酸鹼值，減少刺激，讓肌膚保持穩定狀態，敏感肌也能安心使用。

● 無SLS / SLES、無酒精、無香精、無皂基
    減少刺激性成分，不含可能引發過敏的添加物，給敏感肌最純粹的呵護。

● 適合肌膚類型：
    敏感肌膚 / 泛紅肌膚
    乾性肌膚 / 皮膚屏障受損者
    想尋找溫和無負擔洗面乳的使用者

● 溫和潔淨 × 舒緩保濕，洗出健康水潤肌！''',
                suitable_for="臉部", usage_instructions="取適量於掌心，加水搓揉起泡後，輕輕按摩全臉，再用溫水洗淨。",
                shelf_life=24, supplier=suppliers[1]),

        Products(name="去角質洗面乳", description="● 含有細緻去角質微粒\n\n● 幫助去除老廢角質，使肌膚更加光滑",
                long_description=
'''溫和去角質 × 深層潔淨 × 舒緩保濕

● 天然薰衣草精華，舒緩肌膚壓力
    嚴選法國薰衣草萃取，富含天然植萃舒緩成分，能幫助鎮靜肌膚，減少外界刺激造成的敏感，讓洗臉的同時感受療癒香氣，釋放一天疲勞。

● 果酸溫和代謝，改善粗糙與暗沉
    搭配溫和果酸 (AHA，如乳酸、甘醇酸)，輕柔去除老廢角質，改善暗沉與粗糙，讓肌膚更加細緻透亮，恢復光滑感。

● 極細柔珠去角質，溫和不刺激
    含有植物纖維柔珠，能夠溫和按摩肌膚，幫助去除毛孔中的污垢與多餘皮脂，不刮傷肌膚，洗後滑嫩不緊繃。

● 維生素B5 & 玻尿酸，洗後保濕不乾燥
    特別添加維生素B5 (泛醇) 與 玻尿酸，補充水分，防止洗臉後的乾燥感，讓肌膚維持柔嫩光澤。

● 無SLS / SLES、無酒精、無皂基、無塑膠微粒
    環保溫和配方，不含刺激性清潔劑與化學去角質成分，讓肌膚與環境都能安心。

● 適合肌膚類型：
    暗沉肌 / 需要溫和去角質者
    粗糙肌 / 想提升肌膚光滑度者
    喜愛薰衣草香氣、想要舒緩壓力的使用者

● 深層淨化 × 光滑透亮，讓肌膚重現細緻嫩感！''',
                suitable_for="臉部", usage_instructions="取適量於掌心，加水搓揉起泡後，輕輕按摩全臉，再用溫水洗淨。",
                shelf_life=24, supplier=suppliers[1]),

        Products(name="美白洗面乳", description="● 富含美白成分\n\n● 能提亮膚色，使肌膚更加均勻透亮",
                long_description=
'''花萃嫩白 × 深層潔淨 × 水潤透亮

● 玫瑰花萃 × 植萃嫩白能量
    嚴選大馬士革玫瑰萃取，富含天然抗氧化因子與維生素C，幫助提升肌膚光澤感，改善暗沉，洗出水嫩透亮肌。

● 煙酰胺 + 熊果素，美白淡斑雙重修護
    蘊含煙酰胺 (Vitamin B3) 與 熊果素 (Arbutin)，有效抑制黑色素生成，改善膚色不均，持續使用讓肌膚更亮白、透潤。

● 氨基酸溫和潔淨，洗後不乾燥
    採用氨基酸系界面活性劑，細緻泡沫能夠溫和帶走污垢與老廢角質，不破壞肌膚屏障，洗後水潤不緊繃。

● 玻尿酸 + 玫瑰精油，保濕滋養不乾澀
    搭配玻尿酸與玫瑰精油，潔面同時補充水分，維持肌膚彈潤感，洗後肌膚細緻水嫩，彷彿敷完保濕面膜。

● 無SLS / SLES、無酒精、無人工色素
    溫和無刺激，敏感肌也能安心使用，給肌膚最純淨的呵護。

● 適合肌膚類型：
    暗沉肌 / 需要美白提亮者
    乾燥肌 / 追求水潤透亮感者
    喜愛玫瑰香氛，想要奢華洗臉體驗的使用者

● 玫瑰花萃 × 透亮嫩白，讓肌膚綻放水光光采！''',
                suitable_for="臉部", usage_instructions="取適量於掌心，加水搓揉起泡後，輕輕按摩全臉，再用溫水洗淨。",
                shelf_life=24, supplier=suppliers[1]),

        Products(name="保濕洗髮乳", description="● 深層滋潤髮絲\n\n● 讓秀髮恢復彈性與光澤",
                long_description=
'''花漾滋養 × 深層補水 × 柔順亮澤

● 大馬士革玫瑰精華，髮絲奢華滋養
    嚴選大馬士革玫瑰萃取，富含天然抗氧化因子與保濕成分，溫和呵護髮絲，提升髮質彈性與光澤，洗後秀髮柔順飄逸。

● 玻尿酸 + 神經醯胺，極致補水保濕
    搭配玻尿酸與神經醯胺 (Ceramide)，深入髮絲補水鎖水，修復乾燥受損髮，長效維持髮絲水潤柔亮。        

● 氨基酸溫和潔淨，洗後不乾澀
    選用氨基酸系界面活性劑，細緻泡沫溫和潔淨頭皮與髮絲，帶走油脂與髒污的同時，保留秀髮天然水分，不刺激、不緊繃。

● 摩洛哥堅果油 + 玫瑰精油，修護滋養髮絲
    特別添加摩洛哥堅果油與玫瑰精油，深層滋養髮絲，幫助撫平毛躁，讓秀髮更柔順、輕盈，宛如剛做完護髮。

● 無SLS / SLES、無矽靈、無人工色素
    溫和無負擔，減少頭皮刺激，讓髮絲健康蓬鬆不扁塌，細軟髮與敏感頭皮都能安心使用。

● 適合髮質：
    乾燥髮 / 染燙受損髮
    髮絲毛躁 / 想要柔順水潤感者
    喜愛玫瑰香氣，追求奢華護髮體驗的使用者

● 玫瑰花漾 × 水潤柔順，讓秀髮散發迷人光澤！''',
                suitable_for="頭髮", usage_instructions="先將頭髮完全浸濕，取適量洗髮乳均勻塗抹，按摩後沖洗乾淨。",
                shelf_life=24, supplier=suppliers[9]),

        Products(name="控油洗髮乳", description="● 有效控油\n\n● 減少頭皮出油，保持髮絲清爽",
                long_description=
'''深層淨化 × 平衡控油 × 清爽蓬鬆

● 天然綠茶萃取，調理頭皮油脂
    嚴選綠茶精華，富含兒茶素 (Catechin) 與抗氧化因子，有效對抗外界污染，幫助調理頭皮油脂，讓頭皮保持清新潔淨，減少油膩感。

● 鋅PCA + 茶樹精油，持久控油不乾燥
    搭配鋅PCA與茶樹精油，溫和調理油脂分泌，減少頭皮出油並舒緩頭皮悶熱感，長時間維持頭皮清爽，告別油膩扁塌。

● 氨基酸溫和潔淨，洗後不緊繃
    使用氨基酸系界面活性劑，細緻泡沫能深入髮根帶走多餘油脂與污垢，同時不過度清潔，不傷害頭皮天然屏障，洗後清爽卻不乾澀。

● 無矽靈，蓬鬆輕盈不扁塌
    特別選用無矽靈配方，減少頭皮負擔，讓髮絲更輕盈蓬鬆，不易因殘留物造成毛囊堵塞，細軟髮也能輕鬆擁有豐盈感。

● 無SLS / SLES、無酒精、無人工香精
    溫和低刺激，不含刺激性清潔成分，適合敏感頭皮，長期使用更健康。

● 適合髮質：
    油性頭皮 / 容易出油者
    扁塌髮 / 需要蓬鬆感者
    想改善頭皮悶熱、長效清爽的使用者

● 綠茶淨化 × 控油調理，讓秀髮清爽蓬鬆一整天！''',
                suitable_for="頭髮", usage_instructions="先將頭髮完全浸濕，取適量洗髮乳均勻塗抹，按摩後沖洗乾淨。",
                shelf_life=24, supplier=suppliers[9]),

        Products(name="去屑洗髮乳", description="● 添加去屑因子\n\n● 有效緩解頭皮屑問題，保持潔淨",
                long_description=
'''草本淨化 × 溫和去屑 × 平衡控油

● 佛手柑精華 × 天然淨化力量
    嚴選佛手柑精油，富含天然抗菌與抗氧化因子，能幫助深層潔淨頭皮、減少油脂堆積，並舒緩頭皮不適，帶來清新透氣感。

● 鋅PCA + 水楊酸，雙效去屑控油
    鋅PCA：調節皮脂分泌，減少頭皮屑產生，長效維持頭皮潔淨健康。
    水楊酸 (Salicylic Acid, BHA)：溫和去角質，幫助去除老廢角質與多餘皮脂，防止頭皮屑形成，讓頭皮更清爽透氣。

● 茶樹精油 + 薄荷萃取，舒緩頭皮癢感
    富含茶樹精油與薄荷萃取，天然抗菌成分能幫助減少細菌滋生，舒緩頭皮發癢與不適感，讓頭皮長時間維持涼爽潔淨狀態。

● 無矽靈，頭皮無負擔，髮絲蓬鬆不扁塌
    不含矽靈，減少頭皮毛囊堵塞，洗後髮根更輕盈蓬鬆，細軟髮也能擁有豐盈感。

● 無SLS / SLES、無酒精、無人工香精
    溫和低刺激，不含刺激性界面活性劑，敏感頭皮也能安心使用，長期使用更健康。

● 適合髮質：
    頭皮屑困擾 / 容易發癢者
    油性頭皮 / 需長效控油者
    想舒緩頭皮並享受清新草本香氣的使用者

● 草本去屑 × 持久控油，讓頭皮清爽舒適無屑可擊！''',
                suitable_for="頭髮", usage_instructions="先將頭髮完全浸濕，取適量洗髮乳均勻塗抹，按摩後沖洗乾淨。",
                shelf_life=24, supplier=suppliers[9]),

        Products(name="護色洗髮乳", description="● 富含護色因子\n\n● 幫助染後髮色更持久亮麗",
                long_description=
'''植萃養護 × 鎖色亮澤 × 溫和潔淨

● 茉莉花萃取，極致滋養秀髮
    嚴選茉莉花精華，富含天然抗氧化成分，幫助舒緩染後受損髮絲，維持髮質柔順亮澤，讓染後秀髮持續閃耀迷人光采。

● 胺基酸溫和潔淨，鎖住染髮色彩
    採用氨基酸系界面活性劑，低泡溫和清潔，不破壞頭皮油水平衡，幫助減少染後褪色問題，讓髮色更持久、鮮明透亮。

● 摩洛哥堅果油 + 玻尿酸，雙重修護保濕
    摩洛哥堅果油 (Argan Oil)：深層滋養秀髮，撫平染後乾燥毛躁，讓髮絲更絲滑柔順。
    玻尿酸 (Hyaluronic Acid)：補充髮絲水分，避免乾澀，使秀髮維持水潤彈性，散發自然光澤。

● 維生素B5 + 神經醯胺，強韌髮絲不斷裂
    添加維生素B5 (泛醇) 與神經醯胺 (Ceramide)，強化髮絲結構，提升染後髮質韌性，減少分岔與斷裂，讓秀髮保持健康活力。

● 無SLS / SLES、無矽靈、無酒精、無人工色素
    溫和不刺激，減少對染後髮質與頭皮的負擔，長期使用更健康。

● 適合髮質：
    染燙受損髮 / 需護色者
    乾燥毛躁髮 / 需深層修護者
    喜愛茉莉花香，想要享受花漾洗護體驗的使用者

● 茉莉花漾 × 鎖色護髮，讓秀髮綻放光采亮麗！''',
                suitable_for="頭髮", usage_instructions="先將頭髮完全浸濕，取適量洗髮乳均勻塗抹，按摩後沖洗乾淨。",
                shelf_life=24, supplier=suppliers[9]),
                
        Products(name="深層修護洗髮乳", description="● 深層修護乾燥受損髮絲\n\n● 強化髮根健康",
                long_description=
'''濃密滋養 × 修護受損 × 絲滑亮澤

● 迷人麝香精華，奢華髮絲護理
    融合經典麝香精華，溫暖而細膩的香氣深層滲透髮絲，持久留香，為秀髮增添神秘魅力，打造奢華護理體驗。

● 水解角蛋白 + 神經醯胺，修護受損髮質
    水解角蛋白 (Hydrolyzed Keratin)：深入填補受損髮絲結構，強化髮質彈性，讓髮絲更健康強韌。
    神經醯胺 (Ceramide)：修復毛鱗片，減少染燙受損造成的乾燥與毛躁，讓秀髮絲滑柔順。

● 摩洛哥堅果油 + 玻尿酸，雙效滋養保濕
    摩洛哥堅果油 (Argan Oil)：豐富維生素E與脂肪酸，深層滋養乾燥髮絲，撫平毛躁，使髮絲更加順滑光澤。
    玻尿酸 (Hyaluronic Acid)：鎖住髮絲水分，避免乾燥，使頭髮維持水潤輕盈，不再暗淡無光。

● 氨基酸溫和潔淨，修護同時不傷頭皮
    採用氨基酸系界面活性劑，溫和清潔頭皮與髮絲，不帶走過多油脂，在修護髮質的同時維持頭皮健康，減少乾燥與刺激。

● 無SLS / SLES、無矽靈、無酒精、無人工色素
    溫和低刺激，避免對髮絲與頭皮造成額外負擔，長期使用更健康。

● 適合髮質：
    染燙受損髮 / 極乾燥髮質
    毛躁易打結 / 缺乏光澤髮質
    喜愛高級麝香香氛、追求奢華護髮體驗的使用者

● 麝香魅力 × 極致修護，讓秀髮散發絲滑光澤感！''',
                suitable_for="頭髮", usage_instructions="先將頭髮完全浸濕，取適量洗髮乳均勻塗抹，按摩後沖洗乾淨。",
                shelf_life=24, supplier=suppliers[9]),
        
        Products(name="保濕沐浴乳", description="● 含有深層保濕成分\n\n● 能夠滋潤肌膚並提供全天候水嫩感",
                long_description=
'''天然果萃 × 深層保濕 × 滋潤嫩膚

● 果香滿溢，喚醒身心活力
    嚴選天然水果萃取，融合蜜桃、莓果、柑橘等多種鮮果精華，綻放清新甜美果香，讓每次沐浴都像沉浸在多汁水果的香氣中，煥發活力與好心情！

● 玻尿酸 + 甘油，極致保濕鎖水
    玻尿酸 (Hyaluronic Acid)：高效補水，幫助肌膚維持水嫩彈性，告別乾燥緊繃。
    甘油 (Glycerin)：溫和保濕，提升肌膚鎖水力，讓肌膚洗後依然柔滑細緻。

● 氨基酸溫和潔淨，洗後不乾澀
    採用氨基酸系界面活性劑，泡沫細緻綿密，溫和潔淨肌膚，同時保留肌膚水分，洗後柔嫩不乾燥。

● 維生素C + 果酸溫和嫩膚，提升光澤感
    富含維生素C與果酸 (AHA)，幫助溫和去除老廢角質，改善暗沉，讓肌膚綻放透亮光澤，洗出滑嫩細膩肌！

● 無SLS / SLES、無酒精、無人工色素
    溫和低刺激，不含刺激性化學成分，敏感肌也能安心使用，給肌膚最純粹的果香呵護。

● 適合肌膚類型：
    乾燥肌 / 需要長效保濕者
    暗沉肌 / 追求透亮光滑感者
    喜愛清新水果香氛、希望沐浴同時享受芳香療癒的使用者

● 果香水潤 × 柔嫩光澤，喚醒肌膚鮮嫩彈潤感！''',
                suitable_for="身體", usage_instructions="取適量沐浴乳於沐浴球或掌心，搓揉起泡後塗抹全身，最後以溫水沖淨。",
                shelf_life=24, supplier=suppliers[6]),

        Products(name="溫和清潔沐浴乳", description="● 溫和配方，適合敏感肌\n\n● 清潔同時呵護肌膚屏障",
                long_description=
'''滋潤嫩膚 × 溫和潔淨 × 柔滑保濕

● 牛奶精華 × 深層滋養肌膚
    富含純淨牛奶萃取，富含天然乳蛋白與維生素，能有效補充肌膚養分，增強肌膚屏障，洗後柔嫩細緻，散發自然潤澤光感。

● 玻尿酸 + 神經醯胺，長效保濕鎖水
    玻尿酸 (Hyaluronic Acid)：高效補水，讓肌膚保持水潤彈性，洗後不乾燥、不緊繃。
    神經醯胺 (Ceramide)：修護肌膚屏障，幫助防止水分流失，讓肌膚更健康柔軟。

● 氨基酸溫和潔淨，敏感肌適用
    使用氨基酸系界面活性劑，泡沫細緻溫和，不破壞肌膚天然油脂，洗後清爽水嫩，不乾澀、不刺激，適合全家人使用。

● 牛奶 + 乳木果油，雙重滋養保護
    牛奶蛋白：有效修護乾燥肌膚，提升光澤度，洗出絲滑柔嫩肌。
    乳木果油 (Shea Butter)：深層滋養乾燥肌，形成天然保護膜，鎖住水分，讓肌膚長時間保持潤澤感。

● 無SLS / SLES、無酒精、無人工色素、無皂基
    低敏溫和配方，不含刺激性清潔成分，呵護肌膚屏障，敏感肌也能安心使用。

● 適合肌膚類型：
    乾燥肌 / 極需滋潤者
    敏感肌 / 兒童與全家適用
    想要溫和清潔、同時擁有牛奶絲滑嫩膚感的使用者

● 牛奶呵護 × 溫和潔膚，讓肌膚享受極致柔嫩體驗！''',
                suitable_for="身體", usage_instructions="取適量沐浴乳於沐浴球或掌心，搓揉起泡後塗抹全身，最後以溫水沖淨。",
                shelf_life=24, supplier=suppliers[6]),

        Products(name="抗痘沐浴乳", description="● 含抗菌成分\n\n● 有效清除油脂並減少痘痘生成",
                long_description=
'''淨化肌膚 × 舒緩抗痘 × 長效清爽

● 澳洲茶樹精油 × 天然抗菌淨膚
    嚴選澳洲茶樹精油 (Tea Tree Oil)，富含天然抗菌與消炎成分，有效調理肌膚油脂，減少背部與身體痘痘，帶來潔淨清爽感受。

● 水楊酸 (BHA) 深層淨化毛孔
    添加水楊酸 (Salicylic Acid)，溫和去除毛孔內的多餘皮脂與老廢角質，幫助減少毛孔堵塞，預防粉刺與痘痘生成，改善粗糙肌膚。

● 氨基酸溫和潔淨，控油不乾燥
    採用氨基酸系界面活性劑，泡沫綿密細緻，溫和帶走多餘油脂與污垢，同時保留肌膚必要水分，洗後不緊繃、不乾澀。

● 薄荷 + 積雪草萃取，舒緩痘痘不適
    薄荷萃取 (Menthol)：帶來沁涼舒爽感，幫助舒緩發炎與痘痘不適感。
    積雪草萃取 (Centella Asiatica, CICA)：修護肌膚，減少泛紅，穩定敏感與痘痘問題。
  
● 無SLS / SLES、無酒精、無人工色素
    溫和低刺激，不含刺激性清潔劑與化學成分，敏感肌與痘痘肌都能安心使用。

● 適合肌膚類型：
    容易長背部痘痘 / 粉刺的肌膚
    油性肌 / 易出汗、悶熱導致毛孔堵塞者
    想調理油脂、維持清爽淨膚感的使用者

● 茶樹抗痘 × 清爽調理，讓肌膚遠離痘痘困擾，恢復淨透光滑！''',
                suitable_for="身體", usage_instructions="取適量沐浴乳於沐浴球或掌心，搓揉起泡後塗抹全身，最後以溫水沖淨。",
                shelf_life=24, supplier=suppliers[6]),

        Products(name="控油沐浴乳", description="● 平衡肌膚油脂分泌\n\n● 保持肌膚潔淨無油感",
                long_description=
'''深層淨化 × 平衡控油 × 清爽透氣

● 綠茶精華 × 天然淨化力
    富含綠茶萃取 (Green Tea Extract)，蘊含豐富兒茶素 (Catechin) 與抗氧化因子，有效吸附多餘油脂、對抗環境污染，幫助肌膚恢復清新潔淨感，預防黏膩不適。

● 鋅PCA + 水楊酸 (BHA)，溫和控油調理
    鋅PCA：平衡皮脂分泌，減少多餘油脂堆積，幫助維持肌膚清爽不油膩。
    水楊酸 (Salicylic Acid, BHA)：溫和代謝老廢角質，深入毛孔清潔，預防油脂堵塞與粉刺生成。
  
● 氨基酸潔淨配方，洗後清爽不乾燥
    採用氨基酸系界面活性劑，泡沫細緻溫和，能夠帶走污垢與多餘皮脂，同時維持肌膚水分，不破壞天然屏障，洗後清新舒適，不乾澀。

● 茶樹精油 + 薄荷萃取，淨化舒緩肌膚
    茶樹精油 (Tea Tree Oil)：天然抗菌成分，幫助減少油脂分泌，舒緩肌膚悶熱感。
    薄荷萃取 (Menthol)：帶來清涼舒爽體驗，洗後肌膚透氣不悶熱，適合炎熱氣候與運動後使用。
  
● 無SLS / SLES、無酒精、無人工色素
    溫和低刺激配方，不含刺激性化學成分，讓敏感肌與油性肌膚都能安心使用，帶來最純淨的控油呵護。

● 適合肌膚類型：
    油性肌 / 容易出汗、黏膩不適者
    背部粉刺 / 需調理肌膚油脂者
    喜愛綠茶香氛、追求長效清爽的使用者

● 綠茶淨化 × 持久控油，讓肌膚享受全天候清爽透氣感！''',
                suitable_for="身體", usage_instructions="取適量沐浴乳於沐浴球或掌心，搓揉起泡後塗抹全身，最後以溫水沖淨。",
                shelf_life=24, supplier=suppliers[6]),

        Products(name="美白沐浴乳", description="● 富含美白因子\n\n● 有效提亮膚色，使肌膚更顯透亮",
                long_description=
'''花萃嫩白 × 深層潤澤 × 透亮水感肌

● 櫻花精華 × 植萃嫩白呵護
    嚴選日本櫻花萃取 (Sakura Extract)，富含天然抗氧化成分，幫助溫和淡化暗沉，使肌膚回復勻亮透嫩，綻放粉嫩光澤。

● 煙酰胺 + 熊果素，美白提亮雙重修護
    煙酰胺 (Niacinamide, 維生素B3)：抑制黑色素生成，改善膚色不均，讓肌膚更透亮柔嫩。
    熊果素 (Arbutin)：淡化暗沉，溫和提亮肌膚光澤，使肌膚白皙細緻。

● 玻尿酸 + 玫瑰精油，水嫩潤澤不乾燥
    玻尿酸 (Hyaluronic Acid)：高效補水，洗後肌膚保持彈潤透亮，減少乾燥緊繃感。
    玫瑰精油 (Rose Oil)：溫和滋養，讓肌膚光滑細緻，綻放迷人柔嫩感。
  
● 氨基酸溫和潔淨，洗後滑嫩不緊繃
    採用氨基酸系界面活性劑，泡沫細緻綿密，溫和帶走污垢與多餘油脂，洗後肌膚水潤細滑，宛如沐浴在櫻花雨中。

● 無SLS / SLES、無酒精、無人工色素
    溫和低刺激配方，不含刺激性化學成分，敏感肌也能安心使用，讓肌膚享受最純粹的櫻花呵護。

● 適合肌膚類型：
    暗沉肌 / 想提升透亮感者
    乾燥肌 / 需要保濕滋潤者
    喜愛淡雅櫻花香氣、追求日系溫柔感的使用者

● 櫻花美白 × 水嫩透亮，讓肌膚綻放粉嫩光采！''',
                suitable_for="身體", usage_instructions="取適量沐浴乳於沐浴球或掌心，搓揉起泡後塗抹全身，最後以溫水沖淨。",
                shelf_life=24, supplier=suppliers[6]),

        Products(name="保濕洗手慕斯", description="● 含天然保濕成分\n\n● 溫和清潔雙手並提供長效滋潤",
                long_description=
'''綿密泡沫 × 深層保濕 × 柔嫩雙手

● 茉莉花精華 × 溫和淨膚
    嚴選茉莉花萃取 (Jasmine Extract)，富含天然植萃精華，溫和潔淨雙手的同時，帶來優雅細膩的芳香，享受貴族般的呵護體驗。

● 細緻慕斯泡沫，溫和潔淨不殘留
    輕輕一按，即釋放豐盈綿密的泡沫，能深入手部細微紋理，帶走污垢與細菌，沖洗後不殘留，讓潔手過程更輕鬆愉悅。

● 玻尿酸 + 甘油，深層滋潤不乾澀
    玻尿酸 (Hyaluronic Acid)：高效鎖水，洗後雙手持續保濕，不乾燥、不緊繃。
    甘油 (Glycerin)：溫和修護手部肌膚，提升柔嫩度，使肌膚觸感更細緻。
  
● pH5.5 溫和配方，適合全家使用
    貼近肌膚天然酸鹼值，不破壞肌膚屏障，適合日常頻繁使用，讓每一次洗手都能保持滋潤與舒適。

● 無SLS / SLES、無酒精、無人工色素
    不含刺激性化學成分，降低敏感風險，敏感肌與兒童皆可安心使用。

● 適合手部需求：
    乾燥手部 / 需要長效保濕者
    經常洗手 / 需要溫和潔淨者
    喜愛清新茉莉香氛、享受優雅洗手體驗的使用者

● 茉莉綿密泡沫 × 深層保濕，讓雙手時刻水潤細緻！''',
                suitable_for="手部", usage_instructions="取適量於掌心，搓揉起泡後輕輕按摩，最後用清水洗淨。",
                shelf_life=36, supplier=suppliers[5]),

        Products(name="溫和洗手慕斯", description="● 低敏溫和配方\n\n● 適合頻繁洗手並呵護敏感肌膚",
                long_description=
'''舒緩淨膚 × 溫和潔淨 × 保濕呵護

● 薰衣草精華 × 天然植萃舒緩
    富含法國薰衣草萃取 (Lavender Extract)，天然舒緩鎮靜成分，幫助減少肌膚乾燥不適，帶來放鬆療癒的潔手體驗，讓每次洗手都如同享受芳香SPA。

● 綿密慕斯泡沫，深層清潔不刺激
    輕輕一按，即可釋放細緻豐盈的泡沫，溫和包覆手部肌膚，帶走污垢與細菌，沖洗後無殘留，讓雙手潔淨柔嫩。

● 玻尿酸 + 神經醯胺，長效保濕不乾澀
    玻尿酸 (Hyaluronic Acid)：深層補水，鎖住肌膚水分，洗後雙手不緊繃。
    神經醯胺 (Ceramide)：修護肌膚屏障，預防手部乾燥，維持柔嫩膚感。

● pH5.5 弱酸性溫和配方，全家適用
    貼近肌膚天然酸鹼值，適合頻繁洗手使用，維持手部肌膚健康，敏感肌與兒童也能安心使用。

● 無SLS / SLES、無酒精、無人工色素
    低敏無刺激，減少對手部肌膚的負擔，讓洗手更安心。

● 適合手部需求：
    乾燥手部 / 頻繁洗手者
    敏感肌 / 兒童適用
    喜愛薰衣草香氣，享受舒緩放鬆洗手體驗的使用者

● 薰衣草溫和洗手 × 滋潤舒緩，讓雙手潔淨水潤不乾澀！''',
                suitable_for="手部", usage_instructions="取適量於掌心，搓揉起泡後輕輕按摩，最後用清水洗淨。",
                shelf_life=36, supplier=suppliers[5]),

        Products(name="抗菌洗手慕斯", description="● 含抗菌成分\n\n● 有效抑制細菌滋生，保持雙手清潔健康",
                long_description=
'''天然抗菌 × 溫和潔淨 × 持久清新

● 佛手柑精油 × 天然淨化力
    嚴選佛手柑精油 (Bergamot Essential Oil)，富含天然抗菌因子，有效潔淨雙手、去除污垢與細菌，帶來清新柑橘香氛，洗後舒爽無負擔。

● 綿密泡沫，深層潔淨不殘留
    一按即出細緻慕斯泡沫，能深入指縫與紋理，溫和帶走手部髒污與油脂，沖洗快速不殘留，潔淨同時維持手部柔嫩感。

● 玻尿酸 + 維生素E，潔手同時保濕養護
    玻尿酸 (Hyaluronic Acid)：深層補水，洗後雙手保持水潤柔嫩，不乾澀。
    維生素E (Vitamin E)：滋養修護肌膚，防止手部乾燥粗糙，讓雙手長效潤澤細緻。

● pH5.5 溫和弱酸性，全家安心使用
    貼近肌膚天然酸鹼值，減少刺激，即使頻繁洗手也不會影響手部肌膚屏障，溫和保護雙手健康。

● 無SLS / SLES、無酒精、無人工色素
    不含刺激性化學成分，呵護雙手，不傷害肌膚天然屏障，敏感肌與兒童也可安心使用。

● 適合手部需求：
    需長效抗菌清潔 / 外出回家必備
    乾燥手部 / 頻繁洗手者
    喜愛清新柑橘香氛、希望洗手同時提振活力的使用者

● 佛手柑淨化 × 溫和抗菌，讓雙手潔淨清新不乾燥！''',
                suitable_for="手部", usage_instructions="取適量於掌心，搓揉起泡後輕輕按摩，最後用清水洗淨。",
                shelf_life=36, supplier=suppliers[5]),
                
        Products(name="全效保濕化妝水", description="● 富含玻尿酸與保濕因子\n\n● 深層補水，提升肌膚水嫩感",
                long_description=
'''多重補水 × 深層滋養 × 柔嫩透亮

● 天然果萃精華，喚醒水潤能量
    富含蜜桃、莓果、柑橘萃取，富含天然維生素C與抗氧化因子，能夠溫和修護肌膚，幫助提亮膚色，讓肌膚透現健康水光。

● 玻尿酸 + 神經醯胺，雙重深層補水鎖水
    玻尿酸 (Hyaluronic Acid)：瞬間補水，提升肌膚含水量，讓肌膚水潤飽滿。
    神經醯胺 (Ceramide)：強化肌膚屏障，減少水分流失，長效鎖水，維持彈嫩細緻感。
  
● 煙酰胺 + 維生素B5，養出細膩柔滑肌
    煙酰胺 (Niacinamide, 維生素B3)：提亮膚色，均勻膚質，改善暗沉與乾燥。
    維生素B5 (泛醇, Panthenol)：舒緩修護，增強肌膚保濕力，讓肌膚維持水嫩彈性。
  
● 溫和弱酸性 pH5.5，維持肌膚健康平衡
    貼近肌膚天然酸鹼值，幫助穩定膚況，適合每日使用，為後續保養做好最佳吸收準備。

● 無酒精、無香精、無人工色素、無礦物油
    低敏配方，減少刺激性成分，讓敏感肌也能安心使用，帶來最純淨的水潤呵護。

● 適合肌膚類型：
    乾燥肌 / 極需補水者
    暗沉肌 / 需要提亮均勻膚色者
    喜愛清新果香、希望日常保養同時享受療癒香氛的使用者

● 果萃保濕 × 細緻嫩膚，喚醒肌膚的水潤光澤感！''',
                suitable_for="臉部", usage_instructions="使用化妝棉或手掌取適量，輕拍於需要部位直至吸收。",
                shelf_life=24, supplier=suppliers[4]),

        Products(name="舒緩修護化妝水", description="● 添加舒緩成分\n\n● 有效修護肌膚屏障，減少敏感不適",
                long_description=
'''溫和修護 × 深層補水 × 強化屏障

● 積雪草 + 燕麥萃取，舒緩修護敏弱肌
    蘊含積雪草萃取 (Centella Asiatica, CICA) 和 燕麥萃取 (Oat Extract)，能幫助舒緩泛紅、減少乾燥不適，強化肌膚屏障，使敏感肌恢復穩定健康狀態。

● 玻尿酸 + 神經醯胺，雙效補水鎖水
    玻尿酸 (Hyaluronic Acid)：高效補水，迅速提升肌膚含水量，讓肌膚水潤透亮。
    神經醯胺 (Ceramide)：修復受損屏障，鎖住水分，減少乾燥脫屑與敏感不適。
  
● 維生素B5 + β-葡聚醣，提升肌膚防禦力
    維生素B5 (泛醇, Panthenol)：深層修護，強化肌膚保濕能力，舒緩乾燥、緊繃感。
    β-葡聚醣 (Beta-Glucan)：增強肌膚防護力，抵禦外界刺激，維持穩定膚況。
  
● pH5.5 弱酸性，維持肌膚健康平衡
    貼近肌膚天然酸鹼值，溫和呵護肌膚，不刺激、不致敏，幫助維持穩定健康膚況。

● 無酒精、無香精、無人工色素、無防腐劑
    低敏配方，不含刺激性成分，適合敏感肌、乾燥肌，讓肌膚在溫和舒緩中恢復水潤彈嫩。

● 適合肌膚類型：
    敏感肌 / 泛紅肌 / 乾燥不適肌
    肌膚屏障受損 / 需要修護保養者
    追求溫和修護、穩定膚況的使用者

● 舒緩修護 × 深層補水，讓肌膚重拾健康穩定狀態！''',
                suitable_for="臉部", usage_instructions="使用化妝棉或手掌取適量，輕拍於需要部位直至吸收。",
                shelf_life=24, supplier=suppliers[4]),

        Products(name="青春抗痘化妝水", description="● 含有抗菌成分\n\n● 幫助調理油脂，減少粉刺與痘痘生成",
                long_description=
'''控油調理 × 舒緩抗痘 × 收斂毛孔

● 茶樹精油 × 天然抗菌抗痘力
    富含澳洲茶樹精油 (Tea Tree Oil)，有效調理油脂分泌，淨化毛孔，減少粉刺與痘痘生成，讓肌膚恢復清爽潔淨狀態。

● 水楊酸 (BHA) + 積雪草，溫和去角質、舒緩痘肌
    水楊酸 (Salicylic Acid, BHA)：深入毛孔清潔多餘油脂與角質，幫助預防痘痘與粉刺形成。
    積雪草萃取 (Centella Asiatica, CICA)：舒緩鎮定肌膚，減少痘痘紅腫與敏感狀況。
  
● 鋅PCA + 金縷梅萃取，控油收斂毛孔
    鋅PCA：調節皮脂分泌，減少油光，讓肌膚長效維持清爽。
    金縷梅萃取 (Witch Hazel Extract)：收斂毛孔，平衡肌膚油脂與水分，改善毛孔粗大問題。
  
● pH5.5 弱酸性，溫和調理痘痘肌
    貼近肌膚天然酸鹼值，不刺激、不傷害肌膚屏障，讓敏感痘肌也能安心使用。

● 無酒精、無香精、無人工色素、無礦物油
    低敏無刺激，不含可能引發過敏的成分，讓肌膚得到最溫和有效的抗痘呵護。

● 適合肌膚類型：
    油性肌 / 混合肌 / 痘痘肌
    容易長粉刺 / 毛孔粗大者
    想調理油脂、改善痘痘問題的使用者

● 茶樹淨化 × 溫和抗痘，讓肌膚重回清爽淨透狀態！''',
                suitable_for="臉部", usage_instructions="使用化妝棉或手掌取適量，輕拍於需要部位直至吸收。",
                shelf_life=24, supplier=suppliers[4]),

        Products(name="控油平衡化妝水", description="● 有效控油成分\n\n● 平衡肌膚油脂，讓肌膚保持清爽透亮",
                long_description=
'''淨化調理 × 控油保濕 × 收斂毛孔

● 綠茶萃取 × 天然淨化控油
    富含綠茶萃取 (Green Tea Extract)，蘊含豐富兒茶素 (Catechin) 與抗氧化成分，能有效調理油脂分泌、對抗環境污染，幫助肌膚恢復潔淨平衡，減少出油與悶熱感。

● 鋅PCA + 金縷梅萃取，長效控油調理
    鋅PCA：調節皮脂分泌，減少油光，使肌膚清爽持久不泛油。
    金縷梅萃取 (Witch Hazel Extract)：幫助收斂毛孔，改善毛孔粗大問題，讓肌膚更細緻。
  
● 水楊酸 (BHA) + 積雪草萃取，舒緩肌膚並淨化毛孔
    水楊酸 (Salicylic Acid, BHA)：深入毛孔去除多餘油脂與老廢角質，幫助預防粉刺與痘痘生成。
    積雪草萃取 (Centella Asiatica, CICA)：舒緩肌膚，減少泛紅與敏感不適，強化肌膚屏障。
  
● pH5.5 弱酸性，維持肌膚水油平衡
    貼近肌膚天然酸鹼值，不刺激、不傷害肌膚屏障，讓肌膚時刻維持穩定狀態。

● 無酒精、無香精、無人工色素、無礦物油
    溫和低敏配方，不含刺激性成分，讓油性肌與混合肌都能安心使用，避免過度清潔導致肌膚乾燥或出油惡性循環。

● 適合肌膚類型：
    油性肌 / 容易出油、長時間油光者
    混合肌 / 需要平衡T字部位油脂者
    想改善毛孔粗大、調理油脂與保濕平衡的使用者

● 綠茶淨化 × 持久控油，讓肌膚時刻保持清爽細緻！''',
                suitable_for="臉部", usage_instructions="使用化妝棉或手掌取適量，輕拍於需要部位直至吸收。",
                shelf_life=24, supplier=suppliers[4]),

        Products(name="光采美白化妝水", description="● 富含美白因子，提亮膚色\n\n● 幫助打造均勻亮白肌膚",
                long_description=
'''透亮嫩白 × 深層補水 × 滋養修護

● 牛奶蛋白精華 × 滋養嫩白肌膚
    富含牛奶蛋白萃取 (Milk Protein Extract)，富含天然乳酸與維生素，能夠溫和代謝老廢角質、提升肌膚亮度，幫助肌膚展現細緻透亮的柔嫩光澤。

● 煙酰胺 + 熊果素，美白雙重修護
    煙酰胺 (Niacinamide, 維生素B3)：有效抑制黑色素生成，改善暗沉，使膚色更加均勻透亮。
    熊果素 (Arbutin)：淡化暗沉與色斑，提亮膚色，讓肌膚綻放水光光采。
  
● 玻尿酸 + 維生素B5，長效補水鎖水
    玻尿酸 (Hyaluronic Acid)：高效補水，提升肌膚水潤度，讓肌膚長時間保持細膩Q彈。
    維生素B5 (泛醇, Panthenol)：強化肌膚屏障，舒緩乾燥不適，讓肌膚維持柔嫩觸感。
  
● pH5.5 弱酸性，維持肌膚健康平衡
    貼近肌膚天然酸鹼值，幫助穩定膚況，不刺激、不致敏，適合每日使用，為後續保養做好最佳吸收準備。

● 無酒精、無香精、無人工色素、無礦物油
    低敏溫和配方，不含刺激性成分，讓敏感肌也能安心使用，帶來最純粹的亮白保濕呵護。

● 適合肌膚類型：
    暗沉肌 / 需要提升透亮度者
    乾燥肌 / 需要保濕鎖水者
    想改善肌膚粗糙、均勻膚色的使用者

● 牛奶嫩白 × 透亮潤澤，讓肌膚綻放細緻水光美肌！''',
                suitable_for="臉部", usage_instructions="使用化妝棉或手掌取適量，輕拍於需要部位直至吸收。",
                shelf_life=24, supplier=suppliers[4]),

        Products(name="全效保濕乳", description="● 含高濃度玻尿酸與保濕成分\n\n● 能深層滋潤並維持肌膚水潤",
                long_description=
'''多重補水 × 深層滋養 × 鎖水嫩膚

● 果萃精華 × 水潤能量喚醒肌膚
    蘊含蜜桃、莓果、柑橘萃取等天然果萃精華，富含維生素C與抗氧化因子，能夠提升肌膚保濕力、均勻膚色，帶來清新果香，讓肌膚散發自然透亮感。

● 玻尿酸 + 神經醯胺，長效鎖水補水
    玻尿酸 (Hyaluronic Acid)：深層補水，迅速滲透肌膚，提升含水量，使肌膚水潤飽滿。
    神經醯胺 (Ceramide)：強化肌膚屏障，防止水分流失，減少乾燥脫屑，維持肌膚健康光澤。
  
● 維生素B5 + 維生素E，雙重滋養修護
    維生素B5 (泛醇, Panthenol)：舒緩修護乾燥肌膚，增強肌膚彈性，減少粗糙不適。
    維生素E (Tocopherol)：強效抗氧化，提升肌膚防護力，讓肌膚長時間保持水嫩柔滑。
  
● 輕盈水感質地，吸收快速不黏膩
    絲滑乳液質地，一抹即融入肌膚，快速滲透，帶來全天候的清爽保濕感，適合各種膚質。

● 無酒精、無人工色素、無礦物油
    溫和低敏配方，不含刺激性成分，讓乾性肌、敏感肌也能安心使用，為肌膚帶來最純粹的水潤呵護。

● 適合肌膚類型：
    乾燥肌 / 需要長效保濕者
    暗沉肌 / 想提升肌膚亮澤感者
    喜愛清新果香，享受水潤透亮膚感的使用者

● 果香水潤 × 長效鎖水，讓肌膚時刻柔嫩透亮！''',
                suitable_for="臉部", usage_instructions="使用於化妝水與精華液後，取適量塗抹全臉。",
                shelf_life=24, supplier=suppliers[4]),

        Products(name="舒緩修護乳", description="● 添加舒緩修護因子\n\n● 有效減少肌膚敏感與泛紅問題",
                long_description=
'''深層修護 × 溫和舒緩 × 長效保濕

● 積雪草 + 燕麥萃取，舒緩鎮定敏弱肌
    富含積雪草萃取 (Centella Asiatica, CICA) 和 燕麥萃取 (Oat Extract)，有效舒緩泛紅、減少乾燥不適，修護受損肌膚，幫助肌膚恢復健康穩定狀態。

● 玻尿酸 + 神經醯胺，補水修護屏障
    玻尿酸 (Hyaluronic Acid)：深入補水，迅速提升肌膚水分含量，使肌膚柔嫩透亮。
    神經醯胺 (Ceramide)：強化肌膚屏障，減少水分流失，修護乾燥脆弱肌，增強保濕鎖水能力。
  
● 維生素B5 + β-葡聚醣，強化肌膚保護力
    維生素B5 (泛醇, Panthenol)：舒緩修護，幫助減少肌膚緊繃、乾燥與不適。
    β-葡聚醣 (Beta-Glucan)：增強肌膚防禦力，抵禦外界環境刺激，讓肌膚維持穩定健康狀態。
● 輕盈潤澤質地，溫和親膚不油膩
    細膩絲滑質地，快速吸收不黏膩，為肌膚帶來長效滋潤，適合敏感肌與乾燥肌日常修護使用。

● 無酒精、無香精、無人工色素、無礦物油
    低敏溫和配方，不含刺激性成分，讓敏感肌也能安心使用，全天候守護肌膚健康。

● 適合肌膚類型：
    敏感肌 / 泛紅肌 / 乾燥不適肌
    肌膚屏障受損 / 需要修護保養者
    想舒緩穩定膚況、提升肌膚防禦力的使用者

● 溫和修護 × 深層滋養，讓肌膚重拾健康穩定狀態！''',
                suitable_for="臉部", usage_instructions="使用於化妝水與精華液後，取適量塗抹全臉。",
                shelf_life=24, supplier=suppliers[4]),

        Products(name="青春抗痘乳", description="● 專為易長粉刺與痘痘肌設計\n\n● 幫助調理油脂分泌並減少粉刺",
                long_description=
'''淨化調理 × 舒緩抗痘 × 水油平衡

● 茶樹精油 × 天然抗菌淨膚力
    富含澳洲茶樹精油 (Tea Tree Oil)，具有強效抗菌與淨化作用，能夠調理皮脂分泌，幫助減少痘痘與粉刺，讓肌膚恢復潔淨清爽狀態。

● 水楊酸 (BHA) + 積雪草，深層清潔舒緩痘肌
    水楊酸 (Salicylic Acid, BHA)：深入毛孔溶解油脂與老廢角質，預防粉刺與痘痘生成，改善毛孔阻塞。
    積雪草萃取 (Centella Asiatica, CICA)：舒緩鎮定肌膚，減少痘痘發炎與紅腫問題，加速修護受損肌膚。
  
● 鋅PCA + 金縷梅萃取，調節油脂、收斂毛孔
    鋅PCA：控油保濕，平衡水油比例，減少油光產生，避免過度出油導致的痘痘問題。
    金縷梅萃取 (Witch Hazel Extract)：幫助收斂毛孔，改善毛孔粗大，使肌膚更加細緻光滑。
  
● 輕盈透氣質地，快速吸收不黏膩
    水感清爽配方，質地輕盈好推開，不會造成肌膚負擔，提供長效保濕與油水平衡效果。

● 無酒精、無香精、無人工色素、無礦物油
    溫和低敏配方，不含刺激性成分，讓油性肌與痘痘肌也能安心使用，不刺激、不致粉刺。

● 適合肌膚類型：
    油性肌 / 痘痘肌 / 粉刺肌
    容易出油、毛孔粗大者
    需要溫和調理、穩定膚況的使用者

● 茶樹控油 × 抗痘修護，讓肌膚回歸清爽淨透狀態！''',
                suitable_for="臉部", usage_instructions="使用於化妝水與精華液後，取適量塗抹全臉。",
                shelf_life=24, supplier=suppliers[4]),

        Products(name="控油平衡乳", description="● 有效控油\n\n● 減少肌膚油光，維持清爽感",
                long_description=
'''清爽控油 × 水油平衡 × 長效保濕

● 綠茶萃取 × 天然淨化力
    富含綠茶萃取 (Green Tea Extract)，蘊含兒茶素 (Catechin) 與強效抗氧化因子，幫助調理皮脂分泌，溫和控油，淨化毛孔，維持肌膚清爽透亮，告別油光與悶熱感。

● 鋅PCA + 金縷梅萃取，雙效控油收斂毛孔
    鋅PCA：調節油脂分泌，減少多餘皮脂，防止油光泛出，讓肌膚長效維持水油平衡。
    金縷梅萃取 (Witch Hazel Extract)：幫助收斂毛孔，改善毛孔粗大問題，使肌膚細緻平滑。
  
● 水楊酸 (BHA) + 積雪草萃取，舒緩調理肌膚
    水楊酸 (Salicylic Acid, BHA)：深入毛孔溶解油脂與老廢角質，幫助預防粉刺與痘痘生成，改善毛孔阻塞問題。
    積雪草萃取 (Centella Asiatica, CICA)：舒緩鎮定肌膚，減少發炎與泛紅，強化肌膚屏障，維持穩定膚況。
  
● 輕盈水感質地，吸收快速不黏膩
    獨特輕盈啫喱質地，好推開且迅速吸收，不會造成肌膚負擔，給予肌膚剛剛好的清爽滋潤感。

● 無酒精、無香精、無人工色素、無礦物油
    低敏溫和配方，不含刺激性成分，讓油性肌與混合肌安心使用，不阻塞毛孔、不造成粉刺生成。

● 適合肌膚類型：
    油性肌 / 混合肌 / T字部位易出油者
    容易毛孔粗大 / 需要調理油水平衡者
    想要控油但同時保持肌膚水潤感的使用者

● 綠茶淨化 × 溫和控油，讓肌膚時刻清爽透亮！''',
                suitable_for="臉部", usage_instructions="使用於化妝水與精華液後，取適量塗抹全臉。",
                shelf_life=24, supplier=suppliers[4]),

        Products(name="光采美白乳", description="● 富含美白精華\n\n● 幫助淡化色斑，提升肌膚透亮感",
                long_description=
'''嫩白透亮 × 深層滋養 × 長效保濕

● 牛奶蛋白精華 × 煥亮嫩白肌膚
    富含牛奶蛋白萃取 (Milk Protein Extract)，含有天然乳酸與豐富維生素，能溫和代謝老廢角質，提升肌膚亮度，讓肌膚透現細緻柔嫩光澤。

● 煙酰胺 + 熊果素，雙重提亮勻嫩膚色
    煙酰胺 (Niacinamide, 維生素B3)：有效抑制黑色素生成，均勻膚色，讓肌膚更加透亮柔滑。
    熊果素 (Arbutin)：淡化暗沉，提亮肌膚光澤，使肌膚呈現水嫩淨白感。
  
● 玻尿酸 + 神經醯胺，補水鎖水，長效保濕
    玻尿酸 (Hyaluronic Acid)：深層補水，迅速滲透肌膚，讓肌膚水嫩透亮不乾燥。
    神經醯胺 (Ceramide)：強化肌膚屏障，減少水分流失，修護乾燥肌膚，維持細緻光澤感。
  
● 維生素E + 維生素B5，修護滋養柔滑肌膚
    維生素E (Tocopherol)：強效抗氧化，提升肌膚防護力，預防暗沉與粗糙。
    維生素B5 (泛醇, Panthenol)：舒緩修護乾燥肌膚，增強肌膚彈性，減少細紋與粗糙。
  
● 輕盈絲滑質地，吸收快速不黏膩
    細膩柔滑的質地，一抹即融入肌膚，迅速吸收，帶來全天候的滋養保濕與透亮膚感。

● 無酒精、無香精、無人工色素、無礦物油
    低敏溫和配方，不含刺激性成分，讓乾性肌、敏感肌也能安心使用，持續煥亮肌膚。

● 適合肌膚類型：
    暗沉肌 / 想提升肌膚透亮感者
    乾燥肌 / 需要長效滋潤與嫩白修護者
    想均勻膚色、養出細緻光滑牛奶肌的使用者

● 牛奶嫩白 × 透亮潤澤，讓肌膚煥發絲滑水光感！''',
                suitable_for="臉部", usage_instructions="使用於化妝水與精華液後，取適量塗抹全臉，可搭配防曬使用。",
                shelf_life=24, supplier=suppliers[4]),

        Products(name="保濕護髮乳", description="● 深層滋潤髮絲\n\n● 防止乾燥與毛躁，使秀髮柔順亮澤",
                long_description=
'''深層滋養 × 柔順保濕 × 修護毛躁

● 茉莉花精華 × 髮絲奢華滋養
    嚴選茉莉花萃取 (Jasmine Extract)，富含天然抗氧化成分，能夠舒緩頭皮、提升髮絲柔順度，並帶來細膩優雅的花香，讓秀髮散發自然迷人魅力。

● 玻尿酸 + 摩洛哥堅果油，雙重補水鎖水
    玻尿酸 (Hyaluronic Acid)：深入髮絲補水，提升髮絲含水量，改善乾燥毛躁問題。
    摩洛哥堅果油 (Argan Oil)：豐富維生素E與必需脂肪酸，深層滋養，讓秀髮光澤滑順、不打結。
  
● 維生素B5 + 神經醯胺，強韌髮絲、減少斷裂
    維生素B5 (泛醇, Panthenol)：修護受損髮絲，提升髮絲彈性與柔軟度。
    神經醯胺 (Ceramide)：幫助修復髮絲毛鱗片，強化髮質，減少因乾燥造成的分岔與脆弱問題。
  
● 絲滑乳霜質地，輕盈不扁塌
    細膩乳霜質地，均勻包裹每根髮絲，吸收快速不厚重，讓秀髮柔順輕盈不扁塌，適合日常護理使用。

● 無矽靈、無SLS / SLES、無人工色素、無酒精
    溫和低敏配方，不含刺激性成分，讓細軟髮、乾燥受損髮安心使用，維持健康柔順髮質。

● 適合髮質：
    乾燥髮 / 受損髮 / 毛躁髮
    細軟髮 / 想要輕盈保濕不扁塌者
    喜愛茉莉花香，追求優雅護髮體驗的使用者

● 茉莉花漾 × 水潤柔順，讓秀髮綻放絲滑光澤！''',
                suitable_for="頭髮", usage_instructions="洗髮後取適量護髮乳，均勻塗抹於髮絲，停留3-5分鐘後沖洗。",
                shelf_life=36, supplier=suppliers[9]),

        Products(name="護色護髮乳", description="● 含護色因子\n\n● 有效延長染後髮色的亮麗持久度",
                long_description=
'''鎖色護理 × 深層滋養 × 絲滑光澤

● 奢華麝香精華 × 持久迷人髮香
    特選麝香精華 (Musk Extract)，讓秀髮散發細緻優雅的迷人氣息，洗後持久留香，為髮絲增添高貴神秘的魅力。

● 胺基酸護色科技，維持染後髮色亮澤
    胺基酸複合配方 (Amino Acid Complex)：溫和修護染後受損髮絲，幫助鎖住髮色，使色澤持久亮麗不易褪色。
    UV防護因子：有效抵禦紫外線傷害，減少陽光造成的髮色氧化與黯淡，讓染後髮色更加持久動人。
  
● 摩洛哥堅果油 + 玻尿酸，雙重滋養修護
    摩洛哥堅果油 (Argan Oil)：深入滲透髮絲，補充染後流失的營養，強化髮質，提升絲滑感。
    玻尿酸 (Hyaluronic Acid)：高效補水，鎖住髮絲水分，防止乾燥，使秀髮輕盈柔順不毛躁。
  
● 維生素B5 + 神經醯胺，強韌髮絲減少斷裂
    維生素B5 (泛醇, Panthenol)：修護髮絲結構，減少染燙造成的損傷，提升髮絲韌性。
    神經醯胺 (Ceramide)：填補髮絲毛鱗片空隙，修復受損髮質，讓秀髮更柔順有光澤。
  
● 絲滑乳霜質地，深層滋養不扁塌
    細膩乳霜質地，包覆每根髮絲，修護同時維持輕盈蓬鬆感，不易讓髮絲油膩或厚重。

● 無矽靈、無SLS / SLES、無人工色素、無酒精
    不含矽靈與刺激性成分，減少殘留與頭皮負擔，讓染燙受損髮也能安心使用。

● 適合髮質：
    染燙受損髮 / 需護色者
    乾燥髮 / 毛躁髮 / 易斷裂髮質
    喜愛麝香高級香氛，追求持久絲滑護髮體驗的使用者

● 麝香奢養 × 護色鎖水，讓秀髮煥發極致絲滑光澤！''',
                suitable_for="頭髮", usage_instructions="洗髮後取適量護髮乳，均勻塗抹於髮絲，停留3-5分鐘後沖洗。",
                shelf_life=36, supplier=suppliers[9]),

        Products(name="深層修護護髮乳", description="● 修護受損髮絲\n\n● 補充蛋白質並提升髮絲強韌度",
                long_description=
'''密集修護 × 柔順強韌 × 深層滋養

● 山茶花精華 × 極致修護受損髮絲
    富含日本山茶花油 (Camellia Oil)，蘊含豐富維生素與必需脂肪酸，深入髮絲核心補充流失的養分，修護染燙受損髮質，恢復柔順光澤。

● 水解角蛋白 + 神經醯胺，強化髮絲韌性
    水解角蛋白 (Hydrolyzed Keratin)：深入滲透髮芯，修補受損髮絲結構，增強髮質強韌度，減少斷裂與分岔。
    神經醯胺 (Ceramide)：填補髮絲毛鱗片縫隙，幫助強化髮質，讓髮絲柔順不毛躁，提升健康感。
  
● 玻尿酸 + 摩洛哥堅果油，雙重保濕修護
    玻尿酸 (Hyaluronic Acid)：深層補水，鎖住髮絲水分，使秀髮水潤柔軟。
    摩洛哥堅果油 (Argan Oil)：滋養受損髮質，恢復亮澤感，減少毛躁與乾燥問題。
  
● 維生素B5 + 乳木果油，滋潤修護乾枯髮絲
    維生素B5 (泛醇, Panthenol)：幫助秀髮維持彈性與柔軟度，減少染燙受損的粗糙感。
    乳木果油 (Shea Butter)：為極度乾燥髮絲提供深層滋養，強化保濕鎖水效果。
  
● 絲滑乳霜質地，輕盈柔順不厚重
    細膩的乳霜質地，能均勻包裹髮絲，補充流失的養分，使秀髮絲滑柔順，不易打結或扁塌。

● 無矽靈、無SLS / SLES、無人工色素、無酒精
    溫和配方，不含矽靈與刺激性成分，減少頭皮負擔，適合日常修護染燙受損髮質。

● 適合髮質：
    染燙受損髮 / 乾枯斷裂髮質
    毛躁髮 / 極需深層滋養修護者
    喜愛山茶花淡雅香氣，追求高級護髮體驗的使用者

● 山茶花奢養 × 深層修護，讓秀髮煥發絲滑柔亮光澤！''',
                suitable_for="頭髮", usage_instructions="洗髮後取適量護髮乳，均勻塗抹於髮絲，停留3-5分鐘後沖洗。",
                shelf_life=36, supplier=suppliers[9]),
                
        Products(name="全效保濕身體乳", description="● 含高濃度玻尿酸\n\n● 深層補水，持續保濕一整天",
                long_description=
'''深層滋養 × 長效保濕 × 柔嫩絲滑

● 奢華麝香精華 × 持久迷人香氣
    特選麝香精華 (Musk Extract)，溫暖細膩的高級香氛，融合柔和木質與淡雅花香，讓肌膚散發優雅性感魅力，宛如置身奢華香氛體驗。

● 玻尿酸 + 神經醯胺，雙效保濕鎖水
    玻尿酸 (Hyaluronic Acid)：深入滲透肌膚底層，瞬間補水，讓肌膚長效水潤彈嫩。
    神經醯胺 (Ceramide)：強化肌膚屏障，減少水分流失，修護乾燥粗糙，維持肌膚細緻柔滑。
  
● 乳木果油 + 摩洛哥堅果油，極致滋養修護
    乳木果油 (Shea Butter)：深層潤澤乾燥肌膚，提升保濕鎖水能力，使肌膚觸感柔軟細膩。
    摩洛哥堅果油 (Argan Oil)：富含維生素E與必需脂肪酸，幫助修復乾燥與受損肌膚，使肌膚恢復光澤感。
  
● 維生素E + 維生素B5，修護肌膚提升光澤
    維生素E (Tocopherol)：強效抗氧化，增強肌膚防禦力，讓肌膚更加健康透亮。
    維生素B5 (泛醇, Panthenol)：舒緩乾燥不適，維持肌膚彈性與潤澤感。
  
● 絲滑乳霜質地，快速吸收不黏膩
    輕盈細緻的乳霜質地，能夠迅速滲透肌膚，形成潤澤保護膜，讓肌膚長時間保持柔嫩潤澤，不油膩、不厚重。

● 無酒精、無人工色素、無礦物油
    溫和低敏配方，不含刺激性成分，適合日常保養，給予肌膚最純淨的保濕呵護。

● 適合肌膚類型：
    乾燥肌 / 需要深層滋養者
    想提升肌膚光澤感，維持彈嫩柔滑者
    喜愛持久奢華麝香香氛，追求高級護膚體驗的使用者

● 麝香奢養 × 深層保濕，讓肌膚綻放絲滑細膩光澤！''',
                suitable_for="身體", usage_instructions="沐浴後取適量身體乳，均勻塗抹於全身，使肌膚保持水潤不黏膩。",
                shelf_life=24, supplier=suppliers[10]),

        Products(name="舒緩修護身體乳", description="● 舒緩修護成分\n\n● 有效減少乾燥與敏感問題，強化肌膚屏障",
                long_description=
'''深層修護 × 長效保濕 × 舒緩敏弱肌

● 積雪草 + 燕麥萃取，舒緩鎮定敏感肌
    蘊含積雪草萃取 (Centella Asiatica, CICA) 和 燕麥萃取 (Oat Extract)，能有效舒緩肌膚泛紅、乾燥不適，強化肌膚屏障，幫助修護敏感與受損肌膚，使肌膚恢復健康穩定狀態。

● 玻尿酸 + 神經醯胺，補水修護屏障
    玻尿酸 (Hyaluronic Acid)：迅速補水，深入滲透肌膚底層，提升肌膚含水量，讓肌膚長效水潤彈嫩。
    神經醯胺 (Ceramide)：強化肌膚屏障，鎖住水分，減少乾燥與脫皮，維持肌膚細緻柔滑。
  
● 維生素B5 + β-葡聚醣，提升肌膚防禦力
    維生素B5 (泛醇, Panthenol)：深層修護乾燥肌膚，舒緩肌膚敏感與緊繃感，維持水潤舒適。
    β-葡聚醣 (Beta-Glucan)：強化肌膚防禦力，減少外界環境刺激對肌膚的影響，幫助維持健康膚況。
  
● 乳木果油 + 摩洛哥堅果油，深層滋養乾燥肌
    乳木果油 (Shea Butter)：溫和潤澤，為乾燥肌膚提供長效保濕與滋養，恢復肌膚柔嫩感。
    摩洛哥堅果油 (Argan Oil)：富含維生素E與必需脂肪酸，修護乾燥粗糙部位，使肌膚更加細緻滑嫩。
  
● 輕盈乳霜質地，快速吸收不黏膩
    細緻乳霜質地，輕盈好吸收，不厚重、不油膩，讓肌膚持續水潤舒適，適合日常全身保養。

● 無酒精、無香精、無人工色素、無礦物油
    溫和低敏配方，不含刺激性成分，特別適合乾燥肌、敏感肌與容易泛紅的肌膚，帶來最安心的修護保濕呵護。

● 適合肌膚類型：
    乾燥肌 / 敏感肌 / 泛紅肌
    肌膚屏障受損 / 需要修護與深層保濕者
    想舒緩肌膚不適、強化防禦力的使用者

● 舒緩修護 × 深層滋養，讓肌膚恢復細緻柔嫩的健康光采！''',
                suitable_for="身體", usage_instructions="沐浴後取適量身體乳，均勻塗抹於全身，輕輕按摩至吸收。",
                shelf_life=24, supplier=suppliers[10]),

        Products(name="青春抗痘身體乳", description="● 添加抗菌成分\n\n● 幫助抑制痘痘生成，改善肌膚油水平衡",
                long_description=
'''淨化調理 × 舒緩抗痘 × 持久清爽

● 茶樹精油 × 天然抗菌抗痘力
    嚴選澳洲茶樹精油 (Tea Tree Oil)，富含天然抗菌與淨膚因子，有效調理油脂分泌，幫助減少粉刺與背部痘痘，讓肌膚恢復清爽細緻，遠離痘痘困擾。

● 水楊酸 (BHA) + 鋅PCA，深層控油調理
    水楊酸 (Salicylic Acid, BHA)：深入毛孔溶解多餘油脂與老廢角質，防止毛孔堵塞，減少粉刺與痘痘生成。
    鋅PCA：平衡皮脂分泌，長時間維持肌膚清爽狀態，減少油光與悶熱感。
  
● 積雪草 + 尿囊素，舒緩修護肌膚
    積雪草萃取 (Centella Asiatica, CICA)：幫助舒緩紅腫與發炎，加速痘痘修護，使肌膚更穩定健康。
    尿囊素 (Allantoin)：溫和修護受損肌膚，幫助減少乾燥脫屑，讓肌膚更加柔嫩細緻。
  
● 薄荷萃取 + 金縷梅，清新舒爽不悶熱
    薄荷萃取 (Menthol)：帶來清涼舒適感，舒緩痘痘不適與油膩感，讓肌膚長時間保持透氣清新。
    金縷梅萃取 (Witch Hazel Extract)：有效收斂毛孔，減少油脂分泌，幫助肌膚細緻緊緻。
  
● 輕盈水感質地，清爽不黏膩
    輕盈的水潤配方，能迅速滲透肌膚，不會造成毛孔負擔，長效保濕同時維持清爽不黏膩的舒適感。

● 無酒精、無矽靈、無人工色素、無礦物油
    低敏溫和配方，不含刺激性成分，適合痘痘肌、油性肌與混合肌，幫助調理油脂，讓肌膚長期維持平衡健康。

● 適合肌膚類型：
    背部痘痘 / 粉刺肌 / 容易長痘的肌膚
    油性肌 / 容易悶熱、出油的肌膚
    需要舒緩痘痘不適、改善毛孔阻塞的使用者

● 茶樹淨化 × 舒緩抗痘，讓肌膚回歸淨透光滑！''',
                suitable_for="身體", usage_instructions="沐浴後取適量身體乳，均勻塗抹於全身，輕輕按摩至吸收。",
                shelf_life=24, supplier=suppliers[10]),

        Products(name="控油平衡身體乳", description="● 控油成分可有效調節皮脂\n\n● 讓肌膚保持清爽柔滑",
                long_description=
'''水油平衡 × 清爽保濕 × 持久控油

● 綠茶精華 × 天然淨化控油
    富含綠茶萃取 (Green Tea Extract)，蘊含豐富兒茶素 (Catechin) 與抗氧化成分，能有效調理油脂分泌、淨化毛孔，幫助肌膚恢復潔淨透亮，減少油膩與悶熱感。

● 鋅PCA + 金縷梅，長效控油調理
    鋅PCA：調節皮脂分泌，減少多餘油脂，防止油光泛出，讓肌膚長時間保持清爽水潤。
    金縷梅萃取 (Witch Hazel Extract)：幫助收斂毛孔，改善毛孔粗大，使肌膚更細緻平滑。
  
● 水楊酸 (BHA) + 積雪草，舒緩調理肌膚
    水楊酸 (Salicylic Acid, BHA)：溫和代謝老廢角質，清潔毛孔，預防粉刺與油脂堆積，讓肌膚更光滑細緻。
    積雪草萃取 (Centella Asiatica, CICA)：舒緩鎮定肌膚，減少泛紅與敏感，強化肌膚屏障，維持穩定膚況。
  
●薄荷萃取 + 維生素B5，舒爽保濕不黏膩
    薄荷萃取 (Menthol)：帶來清涼舒適感，幫助舒緩油性肌膚的不適，讓肌膚透氣不悶熱。
    維生素B5 (泛醇, Panthenol)：強化肌膚保濕力，減少乾燥脫皮，同時維持水油平衡。
  
● 輕盈水感質地，快速吸收不油膩
    輕盈水潤配方，質地清爽好吸收，提供肌膚剛剛好的滋潤，長效保濕但不黏膩，適合所有季節使用。

● 無酒精、無人工色素、無礦物油
    低敏溫和配方，不含刺激性成分，讓油性肌與混合肌安心使用，不阻塞毛孔、不造成粉刺生成。

● 適合肌膚類型：
    油性肌 / 容易出油、長時間油光者
    混合肌 / 需要平衡水油比例者
    想改善毛孔粗大、長效控油但同時保持肌膚水潤感的使用者

● 綠茶淨化 × 清爽控油，讓肌膚時刻保持細緻透亮！''',
                suitable_for="身體", usage_instructions="沐浴後取適量身體乳，均勻塗抹於全身，輕輕按摩至吸收。",
                shelf_life=24, supplier=suppliers[10]),

        Products(name="光采美白身體乳", description="● 富含維他命C美白精華\n\n● 幫助提亮膚色，使肌膚透亮光采",
                long_description=
'''透亮嫩白 × 深層滋養 × 長效保濕

● 牛奶蛋白精華 × 提亮柔嫩肌膚
    富含牛奶蛋白萃取 (Milk Protein Extract)，蘊含豐富的乳酸與維生素，能溫和去除老廢角質、提升肌膚亮度，讓肌膚散發絲滑透亮的牛奶光澤。

● 煙酰胺 + 熊果素，雙重美白修護
    煙酰胺 (Niacinamide, 維生素B3)：有效抑制黑色素生成，改善膚色不均，讓肌膚更加勻亮細緻。
    熊果素 (Arbutin)：淡化暗沉與色斑，提亮膚色，使肌膚恢復透亮光澤感。
  
● 玻尿酸 + 神經醯胺，深層保濕修護屏障
    玻尿酸 (Hyaluronic Acid)：迅速補水，提升肌膚含水量，讓肌膚水潤飽滿，長時間維持嫩滑觸感。
    神經醯胺 (Ceramide)：修護肌膚屏障，鎖住水分，防止乾燥脫皮，使肌膚細膩柔嫩。
  
● 乳木果油 + 維生素E，滋養修護乾燥肌
    乳木果油 (Shea Butter)：深層滋潤肌膚，增強鎖水能力，使肌膚更加絲滑柔軟。
    維生素E (Tocopherol)：強效抗氧化，提升肌膚防護力，減少暗沉與粗糙，讓肌膚維持細緻光澤。
  
● 絲滑乳霜質地，吸收迅速不黏膩
    輕盈柔滑的乳霜質地，一抹即融入肌膚，迅速吸收，帶來全天候的美白滋潤體驗。

● 無酒精、無人工色素、無礦物油
    低敏溫和配方，不含刺激性成分，讓乾性肌、暗沉肌與敏感肌都能安心使用，帶來最純粹的美白保濕呵護。

● 適合肌膚類型：
    暗沉肌 / 想提升肌膚透亮感者
    乾燥肌 / 需要長效滋潤與嫩白修護者
    想均勻膚色、養出細緻牛奶肌的使用者

● 牛奶嫩白 × 透亮潤澤，讓肌膚綻放絲滑牛奶光！''',
                suitable_for="身體", usage_instructions="取適量乳液於手掌，均勻塗抹於全身，建議搭配防曬產品使用。",
                shelf_life=24, supplier=suppliers[10]),

        Products(name="全能修護護手霜", description="● 多重修護配方\n\n● 能深層滋養雙手，減少乾燥與龜裂",
                long_description=
'''深層修護 × 長效保濕 × 舒緩嫩膚

● 法國薰衣草精華 × 舒緩修護雙手
    富含法國薰衣草萃取 (Lavender Extract)，具有天然舒緩與抗氧化功效，能夠幫助舒緩乾燥不適，使雙手恢復柔嫩細緻，並帶來放鬆療癒的芳香體驗。

● 玻尿酸 + 神經醯胺，強效保濕鎖水
    玻尿酸 (Hyaluronic Acid)：高效補水，深層滲透滋養乾燥肌膚，讓雙手維持水潤嫩滑。
    神經醯胺 (Ceramide)：修護受損肌膚屏障，減少水分流失，長效鎖水，預防乾燥龜裂。
  
● 乳木果油 + 摩洛哥堅果油，極致滋養修護
    乳木果油 (Shea Butter)：深層潤澤，提供長效保護，使手部肌膚柔嫩光滑。
    摩洛哥堅果油 (Argan Oil)：豐富維生素E與脂肪酸，修護乾燥粗糙，讓雙手重現健康亮澤。
  
● 維生素B5 + 維生素E，抗氧修護雙重呵護
    維生素B5 (泛醇, Panthenol)：舒緩乾燥與脫皮問題，提升肌膚修護能力。
    維生素E (Tocopherol)：強效抗氧化，增強肌膚防禦力，減少因環境刺激造成的乾燥與粗糙。
  
● 絲滑乳霜質地，快速吸收不黏膩
    柔滑細膩的乳霜質地，輕盈好推開，迅速吸收，提供全天候的深層滋潤與修護，讓雙手保持柔嫩不油膩。

● 無酒精、無人工色素、無礦物油
    低敏溫和配方，不含刺激性成分，適合乾燥肌、敏感肌與頻繁洗手後的日常修護。

● 適合手部需求：
    乾燥粗糙 / 經常接觸水、清潔劑者
    手部龜裂 / 需要深層修護與長效保濕者
    喜愛薰衣草香氛，享受舒緩放鬆護手體驗的使用者

● 薰衣草舒緩 × 全能修護，讓雙手時刻水潤細緻！''',
                suitable_for="手部", usage_instructions="取適量護手霜，均勻塗抹於雙手，輕輕按摩至完全吸收。",
                shelf_life=36, supplier=suppliers[2]),

        Products(name="保濕滋潤護手霜", description="● 高效保濕成分\n\n● 為雙手提供長效滋潤，避免乾燥粗糙",
                long_description=
'''奢華潤澤 × 深層保濕 × 柔嫩修護

● 大馬士革玫瑰精華 × 奢華潤澤呵護
    富含大馬士革玫瑰萃取 (Damask Rose Extract)，蘊含豐富抗氧化因子，能有效滋養乾燥雙手、提升肌膚彈性，並帶來淡雅高級玫瑰芳香，散發優雅魅力。

● 玻尿酸 + 神經醯胺，強效保濕鎖水
    玻尿酸 (Hyaluronic Acid)：深層補水，迅速滲透肌膚，讓雙手維持柔嫩水潤感。
    神經醯胺 (Ceramide)：強化肌膚屏障，防止水分流失，長效鎖水，預防乾燥龜裂。
  
● 乳木果油 + 摩洛哥堅果油，極致滋養修護
    乳木果油 (Shea Butter)：高效潤澤，修護乾燥粗糙，幫助肌膚恢復細緻柔滑。
    摩洛哥堅果油 (Argan Oil)：富含維生素E與必需脂肪酸，提供深層營養，讓雙手重現健康光澤。
  
● 維生素B5 + 維生素E，抗氧修護雙重呵護
    維生素B5 (泛醇, Panthenol)：舒緩乾燥與細紋，提升肌膚彈性，使雙手更加柔嫩細滑。
    維生素E (Tocopherol)：強效抗氧化，抵禦環境傷害，減少粗糙與乾裂問題，讓雙手維持年輕光采。
  
● 絲滑乳霜質地，快速吸收不黏膩
    輕盈絲滑的乳霜質地，能迅速吸收，形成保護膜，讓肌膚長效水潤柔嫩，同時不影響日常活動，輕鬆保持雙手潤澤細緻。

● 無酒精、無人工色素、無礦物油
    溫和低敏配方，不含刺激性成分，適合乾燥肌、敏感肌與頻繁洗手後的日常護理。

● 適合手部需求：
    乾燥粗糙 / 經常接觸水、清潔劑者
    手部細紋 / 需要深層修護與長效滋養者
    喜愛玫瑰香氛，追求優雅奢華護手體驗的使用者

● 玫瑰滋潤 × 柔嫩修護，讓雙手綻放水潤絲滑光澤！''',
                suitable_for="手部", usage_instructions="取適量護手霜，均勻塗抹於雙手，輕輕按摩至完全吸收。",
                shelf_life=36, supplier=suppliers[2]),

        Products(name="純淨水感護手霜", description="● 水潤輕盈質地，迅速吸收不黏膩\n\n● 讓雙手保持柔嫩舒適",
                long_description=
'''輕盈保濕 × 絲滑柔嫩 × 持久清新

● 奢華麝香精華 × 純淨細膩香氛
    特選麝香精華 (Musk Extract)，融合柔和木質與淡雅花香，讓雙手散發溫潤細膩的高級香氣，輕盈不厚重，帶來純淨優雅的護手體驗。

● 玻尿酸 + 神經醯胺，輕盈補水鎖水
    玻尿酸 (Hyaluronic Acid)：迅速補水，滲透肌膚深層，讓雙手保持水嫩柔滑，告別乾燥。
    神經醯胺 (Ceramide)：修護肌膚屏障，減少水分流失，提升手部柔軟度，維持全天候水感滋潤。
  
● 維生素B5 + 維生素E，修護與保護雙重呵護
    維生素B5 (泛醇, Panthenol)：舒緩乾燥不適，提升肌膚彈性，讓雙手更加細緻柔嫩。
    維生素E (Tocopherol)：強效抗氧化，幫助抵禦環境刺激，減少手部粗糙與乾裂問題。
  
● 輕盈水感質地，吸收迅速不黏膩
    獨特水潤凝霜配方，輕盈柔滑，快速滲透肌膚，補水同時維持透氣舒適感，不油膩、不厚重，適合日常使用。

● 無酒精、無人工色素、無礦物油
    溫和低敏配方，不含刺激性成分，適合所有膚質，給予雙手最純粹的水感保濕呵護。

● 適合手部需求：
    乾燥肌 / 需要輕盈長效保濕者
    手部容易出汗 / 喜歡無負擔水潤感者
    喜愛麝香香氛，追求高級輕盈護手體驗的使用者

● 麝香純淨 × 水感滋潤，讓雙手時刻清新柔嫩！''',
                suitable_for="手部", usage_instructions="取適量塗抹於手部，吸收迅速不油膩，適合日常保養使用。",
                shelf_life=36, supplier=suppliers[2]),

        Products(name="柔嫩美白護手霜", description="● 富含美白精華\n\n● 有效提亮膚色，使雙手更顯年輕細緻",
                long_description=
'''提亮嫩白 × 滋養保濕 × 清新柔滑

● 檸檬精華 × 天然透亮能量
    富含檸檬萃取 (Lemon Extract)，蘊含維生素C與天然果酸 (AHA)，能幫助溫和代謝老廢角質，提亮膚色，讓手部肌膚更加細緻透亮，重現柔嫩白皙感。

● 煙酰胺 + 熊果素，雙重美白修護
    煙酰胺 (Niacinamide, 維生素B3)：有效抑制黑色素生成，均勻膚色，使手部肌膚更加透亮細緻。
    熊果素 (Arbutin)：幫助淡化暗沉與色素沉澱，讓雙手恢復自然嫩白光澤。
  
● 玻尿酸 + 維生素E，保濕抗氧化雙重呵護
    玻尿酸 (Hyaluronic Acid)：深層補水，鎖住水分，讓雙手長效水潤，不乾燥。
    維生素E (Tocopherol)：強效抗氧化，抵禦環境刺激，減少乾燥粗糙，使肌膚更健康亮澤。
  
● 乳木果油 + 維生素B5，修護乾燥粗糙
    乳木果油 (Shea Butter)：深層滋養乾燥手部肌膚，減少粗糙感，使雙手更柔軟細滑。
    維生素B5 (泛醇, Panthenol)：舒緩乾燥不適，提升手部肌膚彈性與光澤度。
  
● 輕盈水潤質地，快速吸收不黏膩
    細膩柔滑的乳霜質地，輕盈好推開，能迅速滲透肌膚，讓雙手持久保濕嫩白，不影響日常使用。

● 無酒精、無人工色素、無礦物油
    溫和低敏配方，不含刺激性成分，適合所有膚質，特別適合乾燥與暗沉肌膚，帶來最純粹的嫩白滋潤呵護。

● 適合手部需求：
    手部暗沉 / 想提升手部透亮感者
    乾燥粗糙肌 / 需要長效滋養與修護者
    喜愛清新檸檬香氛，追求嫩白柔滑感的使用者

● 檸檬嫩白 × 水潤修護，讓雙手綻放自然透亮光采！''',
                suitable_for="手部", usage_instructions="取適量護手霜，均勻塗抹於雙手，輕輕按摩至完全吸收。",
                shelf_life=36, supplier=suppliers[2]), 

        Products(name="品牌購物袋", description="品牌購物袋，方便又時尚。",
            long_description="環保材質，結構堅固，適合日常使用。",
            suitable_for="日常使用", usage_instructions="直接使用即可",
            shelf_life=None, supplier=suppliers[2]),     
    ]

    # 批量插入資料
    Products.objects.bulk_create(products)
    

    ##包裝類型 (package_types)
    # 準備要插入的資料
    package_types = [
        PackageTypes(package_name="單入"),
        PackageTypes(package_name="兩入"),
        PackageTypes(package_name="三入"),
        PackageTypes(package_name="禮盒"),
    ]

    # 批量插入資料
    PackageTypes.objects.bulk_create(package_types)

     
    ##容量/重量 (product_sizes)
    # 準備要插入的資料
    product_sizes = [
        ProductSizes(size_value="50g"),
        ProductSizes(size_value="75g"),
        ProductSizes(size_value="120g"),
        ProductSizes(size_value="10mL"),
        ProductSizes(size_value="30mL"),
        ProductSizes(size_value="200mL"),
        ProductSizes(size_value="350mL"),
        ProductSizes(size_value="500mL"),
    ]

    # 批量插入資料
    ProductSizes.objects.bulk_create(product_sizes)


    ##香味 (product_fragrances)
    # 準備要插入的資料
    product_fragrances = [
        ProductFragrances(fragrance_name="無香味"),
        ProductFragrances(fragrance_name="玫瑰香"),
        ProductFragrances(fragrance_name="薰衣草香"),
        ProductFragrances(fragrance_name="佛手柑"),
        ProductFragrances(fragrance_name="麝香"),
        ProductFragrances(fragrance_name="茉莉香"),
        ProductFragrances(fragrance_name="茶樹"),
        ProductFragrances(fragrance_name="果香"),
        ProductFragrances(fragrance_name="山茶花香"),
        ProductFragrances(fragrance_name="綠茶"),
        ProductFragrances(fragrance_name="檸檬"),
        ProductFragrances(fragrance_name="櫻花香"),
        ProductFragrances(fragrance_name="牛奶香"),
    ]

    # 批量插入資料
    ProductFragrances.objects.bulk_create(product_fragrances)


    ##產地 (product_origins)
    # 準備要插入的資料
    product_origins = [
        ProductOrigins(origin_name="台灣"),
        ProductOrigins(origin_name="日本"),
        ProductOrigins(origin_name="韓國"),
        ProductOrigins(origin_name="美國"),
        ProductOrigins(origin_name="法國"),
        ProductOrigins(origin_name="英國"),
        ProductOrigins(origin_name="澳洲"),
        ProductOrigins(origin_name="德國"),
        ProductOrigins(origin_name="瑞士"),
        ProductOrigins(origin_name="西班牙"),
    ]

    # 批量插入資料
    ProductOrigins.objects.bulk_create(product_origins)


    ##功效 (product_effectiveness)
    # 準備要插入的資料
    product_effectiveness_list = [
        ProductEffectiveness(effectiveness_name="保濕"),
        ProductEffectiveness(effectiveness_name="控油"),
        ProductEffectiveness(effectiveness_name="抗痘"),
        ProductEffectiveness(effectiveness_name="舒緩"),
        ProductEffectiveness(effectiveness_name="美白"),
        ProductEffectiveness(effectiveness_name="清爽"),
        ProductEffectiveness(effectiveness_name="修護"),
        ProductEffectiveness(effectiveness_name="去角質"),
        ProductEffectiveness(effectiveness_name="抗菌"),
        ProductEffectiveness(effectiveness_name="護色"),
        ProductEffectiveness(effectiveness_name="去屑"),
    ]

    # 批量插入資料
    ProductEffectiveness.objects.bulk_create(product_effectiveness_list)



    ##商品與功效關聯 (product_effectiveness_map)
    # 確保外鍵的資料已存在
    products = {p.product_id: p for p in Products.objects.all()}
    effectiveness = {e.effectiveness_id: e for e in ProductEffectiveness.objects.all()}
    # 準備要插入的資料
    effectiveness_map_records = [
        ProductEffectivenessMap(product=products[1], effectiveness=effectiveness[1]),
        ProductEffectivenessMap(product=products[2], effectiveness=effectiveness[2]),
        ProductEffectivenessMap(product=products[3], effectiveness=effectiveness[4]),
        ProductEffectivenessMap(product=products[4], effectiveness=effectiveness[8]),
        ProductEffectivenessMap(product=products[5], effectiveness=effectiveness[5]),
        ProductEffectivenessMap(product=products[6], effectiveness=effectiveness[1]),
        ProductEffectivenessMap(product=products[7], effectiveness=effectiveness[2]),
        ProductEffectivenessMap(product=products[8], effectiveness=effectiveness[10]),
        ProductEffectivenessMap(product=products[9], effectiveness=effectiveness[9]),
        ProductEffectivenessMap(product=products[10], effectiveness=effectiveness[7]),
        ProductEffectivenessMap(product=products[11], effectiveness=effectiveness[1]),
        ProductEffectivenessMap(product=products[12], effectiveness=effectiveness[4]),
        ProductEffectivenessMap(product=products[13], effectiveness=effectiveness[3]),
        ProductEffectivenessMap(product=products[14], effectiveness=effectiveness[2]),
        ProductEffectivenessMap(product=products[15], effectiveness=effectiveness[5]),
        ProductEffectivenessMap(product=products[16], effectiveness=effectiveness[1]),
        ProductEffectivenessMap(product=products[17], effectiveness=effectiveness[4]),
        ProductEffectivenessMap(product=products[18], effectiveness=effectiveness[11]),
        ProductEffectivenessMap(product=products[19], effectiveness=effectiveness[1]),
        ProductEffectivenessMap(product=products[20], effectiveness=effectiveness[4]),
        ProductEffectivenessMap(product=products[20], effectiveness=effectiveness[7]),
        ProductEffectivenessMap(product=products[21], effectiveness=effectiveness[3]),
        ProductEffectivenessMap(product=products[22], effectiveness=effectiveness[2]),
        ProductEffectivenessMap(product=products[23], effectiveness=effectiveness[5]),
        ProductEffectivenessMap(product=products[24], effectiveness=effectiveness[1]),
        ProductEffectivenessMap(product=products[25], effectiveness=effectiveness[4]),
        ProductEffectivenessMap(product=products[25], effectiveness=effectiveness[7]),
        ProductEffectivenessMap(product=products[26], effectiveness=effectiveness[3]),
        ProductEffectivenessMap(product=products[27], effectiveness=effectiveness[2]),
        ProductEffectivenessMap(product=products[28], effectiveness=effectiveness[5]),
        ProductEffectivenessMap(product=products[29], effectiveness=effectiveness[1]),
        ProductEffectivenessMap(product=products[30], effectiveness=effectiveness[9]),
        ProductEffectivenessMap(product=products[31], effectiveness=effectiveness[7]),
        ProductEffectivenessMap(product=products[32], effectiveness=effectiveness[1]),
        ProductEffectivenessMap(product=products[33], effectiveness=effectiveness[4]),
        ProductEffectivenessMap(product=products[33], effectiveness=effectiveness[7]),
        ProductEffectivenessMap(product=products[34], effectiveness=effectiveness[3]),
        ProductEffectivenessMap(product=products[35], effectiveness=effectiveness[2]),
        ProductEffectivenessMap(product=products[36], effectiveness=effectiveness[5]),
        ProductEffectivenessMap(product=products[37], effectiveness=effectiveness[7]),
        ProductEffectivenessMap(product=products[38], effectiveness=effectiveness[1]),
        ProductEffectivenessMap(product=products[39], effectiveness=effectiveness[6]),
        ProductEffectivenessMap(product=products[40], effectiveness=effectiveness[5]),
    ]

    # 批量插入資料
    ProductEffectivenessMap.objects.bulk_create(effectiveness_map_records)



    ##成分 (product_ingredients)
    # 準備要插入的資料
    product_ingredients = [
        ProductIngredients(ingredient_name="水"),
        ProductIngredients(ingredient_name="玻尿酸"),
        ProductIngredients(ingredient_name="維他命B5"),
        ProductIngredients(ingredient_name="甘油"),
        ProductIngredients(ingredient_name="維他命C誘導體"),
        ProductIngredients(ingredient_name="熊果素"),
        ProductIngredients(ingredient_name="傳明酸"),
        ProductIngredients(ingredient_name="水楊酸"),
        ProductIngredients(ingredient_name="果酸"),
        ProductIngredients(ingredient_name="木瓜酵素"),
        ProductIngredients(ingredient_name="金縷梅萃取"),
        ProductIngredients(ingredient_name="積雪草萃取"),
        ProductIngredients(ingredient_name="洋甘菊萃取"),
        ProductIngredients(ingredient_name="燕麥萃取"),
        ProductIngredients(ingredient_name="神經醯胺"),
        ProductIngredients(ingredient_name="煙鹼醯胺"),
        ProductIngredients(ingredient_name="尿囊素"),
        ProductIngredients(ingredient_name="乳木果油"),
        ProductIngredients(ingredient_name="玫瑰果油"),
        ProductIngredients(ingredient_name="橄欖油"),
        ProductIngredients(ingredient_name="辣木油"),
        ProductIngredients(ingredient_name="紅石榴萃取"),
        ProductIngredients(ingredient_name="竹炭粉"),
        ProductIngredients(ingredient_name="燕麥粉"),
        ProductIngredients(ingredient_name="高嶺土"),
        ProductIngredients(ingredient_name="蘋果醋"),
        ProductIngredients(ingredient_name="葡萄籽油"),
        ProductIngredients(ingredient_name="蘆薈萃取"),
        ProductIngredients(ingredient_name="角蛋白"),
        ProductIngredients(ingredient_name="椰子油"),
        ProductIngredients(ingredient_name="水解蠶絲蛋白"),
        ProductIngredients(ingredient_name="水解小麥蛋白"),
        ProductIngredients(ingredient_name="水解膠原蛋白"),
        ProductIngredients(ingredient_name="胺基酸系界面活性劑"),
        ProductIngredients(ingredient_name="椰油基葡萄糖苷"),
        ProductIngredients(ingredient_name="月桂醯胺基"),
        ProductIngredients(ingredient_name="月見草油基表面活性劑"),
        ProductIngredients(ingredient_name="椰油酰胺丙基甜菜鹼"),
        ProductIngredients(ingredient_name="檸檬酸"),
        ProductIngredients(ingredient_name="玫瑰精油"),
        ProductIngredients(ingredient_name="薰衣草精油"),
        ProductIngredients(ingredient_name="佛手柑果皮精油"),
        ProductIngredients(ingredient_name="麝香酮"),
        ProductIngredients(ingredient_name="茉莉花精油"),
        ProductIngredients(ingredient_name="茶樹精油"),
        ProductIngredients(ingredient_name="果皮精油"),
        ProductIngredients(ingredient_name="山茶花萃取"),
        ProductIngredients(ingredient_name="綠茶萃取"),
        ProductIngredients(ingredient_name="檸檬精油"),
        ProductIngredients(ingredient_name="櫻花萃取"),
        ProductIngredients(ingredient_name="杏仁油"),
        ProductIngredients(ingredient_name="山嵛醇"),
        ProductIngredients(ingredient_name="甘油脂肪酸酯"),
        ProductIngredients(ingredient_name="蜂蠟"),
    ]

    # 批量插入資料
    ProductIngredients.objects.bulk_create(product_ingredients)


    ##商品與成分關聯 (product_ingredients_map)
    # 確保外鍵的資料已存在
    products = {p.product_id: p for p in Products.objects.all()}
    ingredients = {i.ingredient_id: i for i in ProductIngredients.objects.all()}
    # 準備要插入的資料
    ingredients_map_records = [
        ProductIngredientsMap(product=products[1], ingredient=ingredients[1]),
        ProductIngredientsMap(product=products[1], ingredient=ingredients[34]),
        ProductIngredientsMap(product=products[1], ingredient=ingredients[35]),
        ProductIngredientsMap(product=products[1], ingredient=ingredients[2]),
        ProductIngredientsMap(product=products[1], ingredient=ingredients[46]),
        ProductIngredientsMap(product=products[2], ingredient=ingredients[1]),
        ProductIngredientsMap(product=products[2], ingredient=ingredients[34]),
        ProductIngredientsMap(product=products[2], ingredient=ingredients[36]),
        ProductIngredientsMap(product=products[2], ingredient=ingredients[8]),
        ProductIngredientsMap(product=products[2], ingredient=ingredients[48]),
        ProductIngredientsMap(product=products[3], ingredient=ingredients[1]),
        ProductIngredientsMap(product=products[3], ingredient=ingredients[34]),
        ProductIngredientsMap(product=products[3], ingredient=ingredients[35]),
        ProductIngredientsMap(product=products[3], ingredient=ingredients[12]),
        ProductIngredientsMap(product=products[3], ingredient=ingredients[14]),
        ProductIngredientsMap(product=products[4], ingredient=ingredients[1]),
        ProductIngredientsMap(product=products[4], ingredient=ingredients[34]),
        ProductIngredientsMap(product=products[4], ingredient=ingredients[35]),
        ProductIngredientsMap(product=products[4], ingredient=ingredients[10]),
        ProductIngredientsMap(product=products[4], ingredient=ingredients[23]),
        ProductIngredientsMap(product=products[5], ingredient=ingredients[1]),
        ProductIngredientsMap(product=products[5], ingredient=ingredients[34]),
        ProductIngredientsMap(product=products[5], ingredient=ingredients[35]),
        ProductIngredientsMap(product=products[5], ingredient=ingredients[5]),
        ProductIngredientsMap(product=products[5], ingredient=ingredients[6]),
        ProductIngredientsMap(product=products[5], ingredient=ingredients[40]),
        ProductIngredientsMap(product=products[6], ingredient=ingredients[1]),
        ProductIngredientsMap(product=products[6], ingredient=ingredients[37]),
        ProductIngredientsMap(product=products[6], ingredient=ingredients[39]),
        ProductIngredientsMap(product=products[6], ingredient=ingredients[4]),
        ProductIngredientsMap(product=products[6], ingredient=ingredients[40]),
        ProductIngredientsMap(product=products[7], ingredient=ingredients[1]),
        ProductIngredientsMap(product=products[7], ingredient=ingredients[37]),
        ProductIngredientsMap(product=products[7], ingredient=ingredients[39]),
        ProductIngredientsMap(product=products[7], ingredient=ingredients[25]),
        ProductIngredientsMap(product=products[7], ingredient=ingredients[48]),
        ProductIngredientsMap(product=products[8], ingredient=ingredients[1]),
        ProductIngredientsMap(product=products[8], ingredient=ingredients[37]),
        ProductIngredientsMap(product=products[8], ingredient=ingredients[39]),
        ProductIngredientsMap(product=products[8], ingredient=ingredients[8]),
        ProductIngredientsMap(product=products[8], ingredient=ingredients[26]),
        ProductIngredientsMap(product=products[8], ingredient=ingredients[42]),
        ProductIngredientsMap(product=products[9], ingredient=ingredients[1]),
        ProductIngredientsMap(product=products[9], ingredient=ingredients[37]),
        ProductIngredientsMap(product=products[9], ingredient=ingredients[39]),
        ProductIngredientsMap(product=products[9], ingredient=ingredients[27]),
        ProductIngredientsMap(product=products[9], ingredient=ingredients[28]),
        ProductIngredientsMap(product=products[9], ingredient=ingredients[44]),
        ProductIngredientsMap(product=products[10], ingredient=ingredients[1]),
        ProductIngredientsMap(product=products[10], ingredient=ingredients[37]),
        ProductIngredientsMap(product=products[10], ingredient=ingredients[39]),
        ProductIngredientsMap(product=products[10], ingredient=ingredients[12]),
        ProductIngredientsMap(product=products[10], ingredient=ingredients[18]),
        ProductIngredientsMap(product=products[10], ingredient=ingredients[29]),
        ProductIngredientsMap(product=products[10], ingredient=ingredients[43]),
        ProductIngredientsMap(product=products[11], ingredient=ingredients[1]),
        ProductIngredientsMap(product=products[11], ingredient=ingredients[38]),
        ProductIngredientsMap(product=products[11], ingredient=ingredients[39]),
        ProductIngredientsMap(product=products[11], ingredient=ingredients[2]),
        ProductIngredientsMap(product=products[11], ingredient=ingredients[4]),
        ProductIngredientsMap(product=products[11], ingredient=ingredients[30]),
        ProductIngredientsMap(product=products[11], ingredient=ingredients[46]),
        ProductIngredientsMap(product=products[12], ingredient=ingredients[1]),
        ProductIngredientsMap(product=products[12], ingredient=ingredients[38]),
        ProductIngredientsMap(product=products[12], ingredient=ingredients[39]),
        ProductIngredientsMap(product=products[12], ingredient=ingredients[3]),
        ProductIngredientsMap(product=products[12], ingredient=ingredients[13]),
        ProductIngredientsMap(product=products[12], ingredient=ingredients[14]),
        ProductIngredientsMap(product=products[12], ingredient=ingredients[30]),
        ProductIngredientsMap(product=products[12], ingredient=ingredients[51]),
        ProductIngredientsMap(product=products[13], ingredient=ingredients[1]),
        ProductIngredientsMap(product=products[13], ingredient=ingredients[38]),
        ProductIngredientsMap(product=products[13], ingredient=ingredients[39]),
        ProductIngredientsMap(product=products[13], ingredient=ingredients[8]),
        ProductIngredientsMap(product=products[13], ingredient=ingredients[30]),
        ProductIngredientsMap(product=products[13], ingredient=ingredients[45]),
        ProductIngredientsMap(product=products[14], ingredient=ingredients[1]),
        ProductIngredientsMap(product=products[14], ingredient=ingredients[38]),
        ProductIngredientsMap(product=products[14], ingredient=ingredients[39]),
        ProductIngredientsMap(product=products[14], ingredient=ingredients[25]),
        ProductIngredientsMap(product=products[14], ingredient=ingredients[28]),
        ProductIngredientsMap(product=products[14], ingredient=ingredients[48]),
        ProductIngredientsMap(product=products[15], ingredient=ingredients[1]),
        ProductIngredientsMap(product=products[15], ingredient=ingredients[38]),
        ProductIngredientsMap(product=products[15], ingredient=ingredients[39]),
        ProductIngredientsMap(product=products[15], ingredient=ingredients[5]),
        ProductIngredientsMap(product=products[15], ingredient=ingredients[6]),
        ProductIngredientsMap(product=products[15], ingredient=ingredients[30]),
        ProductIngredientsMap(product=products[15], ingredient=ingredients[50]),
        ProductIngredientsMap(product=products[16], ingredient=ingredients[1]),
        ProductIngredientsMap(product=products[16], ingredient=ingredients[38]),
        ProductIngredientsMap(product=products[16], ingredient=ingredients[39]),
        ProductIngredientsMap(product=products[16], ingredient=ingredients[2]),
        ProductIngredientsMap(product=products[16], ingredient=ingredients[4]),
        ProductIngredientsMap(product=products[16], ingredient=ingredients[28]),
        ProductIngredientsMap(product=products[16], ingredient=ingredients[44]),
        ProductIngredientsMap(product=products[16], ingredient=ingredients[52]),
        ProductIngredientsMap(product=products[17], ingredient=ingredients[1]),
        ProductIngredientsMap(product=products[17], ingredient=ingredients[38]),
        ProductIngredientsMap(product=products[17], ingredient=ingredients[39]),
        ProductIngredientsMap(product=products[17], ingredient=ingredients[4]),
        ProductIngredientsMap(product=products[17], ingredient=ingredients[14]),
        ProductIngredientsMap(product=products[17], ingredient=ingredients[41]),
        ProductIngredientsMap(product=products[17], ingredient=ingredients[52]),
        ProductIngredientsMap(product=products[18], ingredient=ingredients[1]),
        ProductIngredientsMap(product=products[18], ingredient=ingredients[38]),
        ProductIngredientsMap(product=products[18], ingredient=ingredients[39]),
        ProductIngredientsMap(product=products[18], ingredient=ingredients[4]),
        ProductIngredientsMap(product=products[18], ingredient=ingredients[42]),
        ProductIngredientsMap(product=products[18], ingredient=ingredients[45]),
        ProductIngredientsMap(product=products[18], ingredient=ingredients[52]),
        ProductIngredientsMap(product=products[19], ingredient=ingredients[1]),
        ProductIngredientsMap(product=products[19], ingredient=ingredients[39]),
        ProductIngredientsMap(product=products[19], ingredient=ingredients[2]),
        ProductIngredientsMap(product=products[19], ingredient=ingredients[4]),
        ProductIngredientsMap(product=products[19], ingredient=ingredients[46]),
        ProductIngredientsMap(product=products[20], ingredient=ingredients[1]),
        ProductIngredientsMap(product=products[20], ingredient=ingredients[39]),
        ProductIngredientsMap(product=products[20], ingredient=ingredients[13]),
        ProductIngredientsMap(product=products[20], ingredient=ingredients[14]),
        ProductIngredientsMap(product=products[21], ingredient=ingredients[1]),
        ProductIngredientsMap(product=products[21], ingredient=ingredients[39]),
        ProductIngredientsMap(product=products[21], ingredient=ingredients[8]),
        ProductIngredientsMap(product=products[21], ingredient=ingredients[45]),
        ProductIngredientsMap(product=products[22], ingredient=ingredients[1]),
        ProductIngredientsMap(product=products[22], ingredient=ingredients[39]),
        ProductIngredientsMap(product=products[22], ingredient=ingredients[11]),
        ProductIngredientsMap(product=products[22], ingredient=ingredients[48]),
        ProductIngredientsMap(product=products[23], ingredient=ingredients[1]),
        ProductIngredientsMap(product=products[23], ingredient=ingredients[39]),
        ProductIngredientsMap(product=products[23], ingredient=ingredients[5]),
        ProductIngredientsMap(product=products[23], ingredient=ingredients[6]),
        ProductIngredientsMap(product=products[23], ingredient=ingredients[51]),
        ProductIngredientsMap(product=products[24], ingredient=ingredients[1]),
        ProductIngredientsMap(product=products[24], ingredient=ingredients[39]),
        ProductIngredientsMap(product=products[24], ingredient=ingredients[53]),
        ProductIngredientsMap(product=products[24], ingredient=ingredients[15]),
        ProductIngredientsMap(product=products[24], ingredient=ingredients[21]),
        ProductIngredientsMap(product=products[24], ingredient=ingredients[46]),
        ProductIngredientsMap(product=products[25], ingredient=ingredients[1]),
        ProductIngredientsMap(product=products[25], ingredient=ingredients[39]),
        ProductIngredientsMap(product=products[25], ingredient=ingredients[53]),
        ProductIngredientsMap(product=products[25], ingredient=ingredients[3]),
        ProductIngredientsMap(product=products[25], ingredient=ingredients[16]),
        ProductIngredientsMap(product=products[26], ingredient=ingredients[1]),
        ProductIngredientsMap(product=products[26], ingredient=ingredients[39]),
        ProductIngredientsMap(product=products[26], ingredient=ingredients[53]),
        ProductIngredientsMap(product=products[26], ingredient=ingredients[12]),
        ProductIngredientsMap(product=products[26], ingredient=ingredients[45]),
        ProductIngredientsMap(product=products[27], ingredient=ingredients[1]),
        ProductIngredientsMap(product=products[27], ingredient=ingredients[39]),
        ProductIngredientsMap(product=products[27], ingredient=ingredients[53]),
        ProductIngredientsMap(product=products[27], ingredient=ingredients[11]),
        ProductIngredientsMap(product=products[27], ingredient=ingredients[48]),
        ProductIngredientsMap(product=products[28], ingredient=ingredients[1]),
        ProductIngredientsMap(product=products[28], ingredient=ingredients[39]),
        ProductIngredientsMap(product=products[28], ingredient=ingredients[53]),
        ProductIngredientsMap(product=products[28], ingredient=ingredients[5]),
        ProductIngredientsMap(product=products[28], ingredient=ingredients[7]),
        ProductIngredientsMap(product=products[28], ingredient=ingredients[51]),
        ProductIngredientsMap(product=products[29], ingredient=ingredients[1]),
        ProductIngredientsMap(product=products[29], ingredient=ingredients[39]),
        ProductIngredientsMap(product=products[29], ingredient=ingredients[53]),
        ProductIngredientsMap(product=products[29], ingredient=ingredients[4]),
        ProductIngredientsMap(product=products[29], ingredient=ingredients[30]),
        ProductIngredientsMap(product=products[29], ingredient=ingredients[31]),
        ProductIngredientsMap(product=products[29], ingredient=ingredients[44]),
        ProductIngredientsMap(product=products[30], ingredient=ingredients[1]),
        ProductIngredientsMap(product=products[30], ingredient=ingredients[39]),
        ProductIngredientsMap(product=products[30], ingredient=ingredients[53]),
        ProductIngredientsMap(product=products[30], ingredient=ingredients[4]),
        ProductIngredientsMap(product=products[30], ingredient=ingredients[27]),
        ProductIngredientsMap(product=products[30], ingredient=ingredients[32]),
        ProductIngredientsMap(product=products[30], ingredient=ingredients[43]),
        ProductIngredientsMap(product=products[31], ingredient=ingredients[1]),
        ProductIngredientsMap(product=products[31], ingredient=ingredients[39]),
        ProductIngredientsMap(product=products[31], ingredient=ingredients[53]),
        ProductIngredientsMap(product=products[31], ingredient=ingredients[19]),
        ProductIngredientsMap(product=products[31], ingredient=ingredients[29]),
        ProductIngredientsMap(product=products[31], ingredient=ingredients[33]),
        ProductIngredientsMap(product=products[31], ingredient=ingredients[47]),
        ProductIngredientsMap(product=products[32], ingredient=ingredients[1]),
        ProductIngredientsMap(product=products[32], ingredient=ingredients[39]),
        ProductIngredientsMap(product=products[32], ingredient=ingredients[54]),
        ProductIngredientsMap(product=products[32], ingredient=ingredients[15]),
        ProductIngredientsMap(product=products[32], ingredient=ingredients[18]),
        ProductIngredientsMap(product=products[32], ingredient=ingredients[46]),
        ProductIngredientsMap(product=products[33], ingredient=ingredients[1]),
        ProductIngredientsMap(product=products[33], ingredient=ingredients[39]),
        ProductIngredientsMap(product=products[33], ingredient=ingredients[54]),
        ProductIngredientsMap(product=products[33], ingredient=ingredients[3]),
        ProductIngredientsMap(product=products[33], ingredient=ingredients[13]),
        ProductIngredientsMap(product=products[33], ingredient=ingredients[16]),
        ProductIngredientsMap(product=products[33], ingredient=ingredients[20]),
        ProductIngredientsMap(product=products[34], ingredient=ingredients[1]),
        ProductIngredientsMap(product=products[34], ingredient=ingredients[39]),
        ProductIngredientsMap(product=products[34], ingredient=ingredients[54]),
        ProductIngredientsMap(product=products[34], ingredient=ingredients[17]),
        ProductIngredientsMap(product=products[34], ingredient=ingredients[24]),
        ProductIngredientsMap(product=products[34], ingredient=ingredients[45]),
        ProductIngredientsMap(product=products[35], ingredient=ingredients[1]),
        ProductIngredientsMap(product=products[35], ingredient=ingredients[39]),
        ProductIngredientsMap(product=products[35], ingredient=ingredients[54]),
        ProductIngredientsMap(product=products[35], ingredient=ingredients[18]),
        ProductIngredientsMap(product=products[35], ingredient=ingredients[25]),
        ProductIngredientsMap(product=products[35], ingredient=ingredients[48]),
        ProductIngredientsMap(product=products[36], ingredient=ingredients[1]),
        ProductIngredientsMap(product=products[36], ingredient=ingredients[39]),
        ProductIngredientsMap(product=products[36], ingredient=ingredients[54]),
        ProductIngredientsMap(product=products[36], ingredient=ingredients[5]),
        ProductIngredientsMap(product=products[36], ingredient=ingredients[20]),
        ProductIngredientsMap(product=products[36], ingredient=ingredients[22]),
        ProductIngredientsMap(product=products[36], ingredient=ingredients[51]),
        ProductIngredientsMap(product=products[37], ingredient=ingredients[1]),
        ProductIngredientsMap(product=products[37], ingredient=ingredients[4]),
        ProductIngredientsMap(product=products[37], ingredient=ingredients[52]),
        ProductIngredientsMap(product=products[37], ingredient=ingredients[53]),
        ProductIngredientsMap(product=products[37], ingredient=ingredients[3]),
        ProductIngredientsMap(product=products[37], ingredient=ingredients[15]),
        ProductIngredientsMap(product=products[37], ingredient=ingredients[41]),
        ProductIngredientsMap(product=products[38], ingredient=ingredients[1]),
        ProductIngredientsMap(product=products[38], ingredient=ingredients[4]),
        ProductIngredientsMap(product=products[38], ingredient=ingredients[52]),
        ProductIngredientsMap(product=products[38], ingredient=ingredients[53]),
        ProductIngredientsMap(product=products[38], ingredient=ingredients[2]),
        ProductIngredientsMap(product=products[38], ingredient=ingredients[19]),
        ProductIngredientsMap(product=products[38], ingredient=ingredients[40]),
        ProductIngredientsMap(product=products[39], ingredient=ingredients[1]),
        ProductIngredientsMap(product=products[39], ingredient=ingredients[4]),
        ProductIngredientsMap(product=products[39], ingredient=ingredients[52]),
        ProductIngredientsMap(product=products[39], ingredient=ingredients[53]),
        ProductIngredientsMap(product=products[39], ingredient=ingredients[2]),
        ProductIngredientsMap(product=products[39], ingredient=ingredients[28]),
        ProductIngredientsMap(product=products[39], ingredient=ingredients[43]),
        ProductIngredientsMap(product=products[40], ingredient=ingredients[1]),
        ProductIngredientsMap(product=products[40], ingredient=ingredients[4]),
        ProductIngredientsMap(product=products[40], ingredient=ingredients[52]),
        ProductIngredientsMap(product=products[40], ingredient=ingredients[53]),
        ProductIngredientsMap(product=products[40], ingredient=ingredients[5]),
        ProductIngredientsMap(product=products[40], ingredient=ingredients[6]),
        ProductIngredientsMap(product=products[40], ingredient=ingredients[19]),
        ProductIngredientsMap(product=products[40], ingredient=ingredients[49]),
    ]

    # 批量插入資料
    ProductIngredientsMap.objects.bulk_create(ingredients_map_records)



    ##分類表
    # 準備要插入的資料
    categories = [
        Categories(category_name="臉部清潔"),
        Categories(category_name="頭髮清潔"),
        Categories(category_name="身體清潔"),
        Categories(category_name="手部清潔"),
        Categories(category_name="臉部保養"),
        Categories(category_name="頭髮保養"),
        Categories(category_name="身體保養"),
        Categories(category_name="手部保養"),
    ]

    # 批量插入資料
    Categories.objects.bulk_create(categories)


    ##商品分類對應表(product_category)
    # 先查詢所有必要的資料，建立字典
    products = {p.product_id: p for p in Products.objects.all()}
    categories = {c.category_id: c for c in Categories.objects.all()}

    # 準備要插入的關聯資料
    product_category_data = [
        ProductCategory(product=products[1], category=categories[1]),
        ProductCategory(product=products[2], category=categories[1]),
        ProductCategory(product=products[3], category=categories[1]),
        ProductCategory(product=products[4], category=categories[1]),
        ProductCategory(product=products[5], category=categories[1]),
        ProductCategory(product=products[6], category=categories[2]),
        ProductCategory(product=products[7], category=categories[2]),
        ProductCategory(product=products[8], category=categories[2]),
        ProductCategory(product=products[9], category=categories[2]),
        ProductCategory(product=products[10], category=categories[2]),
        ProductCategory(product=products[11], category=categories[3]),
        ProductCategory(product=products[12], category=categories[3]),
        ProductCategory(product=products[13], category=categories[3]),
        ProductCategory(product=products[14], category=categories[3]),
        ProductCategory(product=products[15], category=categories[3]),
        ProductCategory(product=products[16], category=categories[4]),
        ProductCategory(product=products[17], category=categories[4]),
        ProductCategory(product=products[18], category=categories[4]),
        ProductCategory(product=products[19], category=categories[5]),
        ProductCategory(product=products[20], category=categories[5]),
        ProductCategory(product=products[21], category=categories[5]),
        ProductCategory(product=products[22], category=categories[5]),
        ProductCategory(product=products[23], category=categories[5]),
        ProductCategory(product=products[24], category=categories[5]),
        ProductCategory(product=products[25], category=categories[5]),
        ProductCategory(product=products[26], category=categories[5]),
        ProductCategory(product=products[27], category=categories[5]),
        ProductCategory(product=products[28], category=categories[5]),
        ProductCategory(product=products[29], category=categories[6]),
        ProductCategory(product=products[30], category=categories[6]),
        ProductCategory(product=products[31], category=categories[6]),
        ProductCategory(product=products[32], category=categories[7]),
        ProductCategory(product=products[33], category=categories[7]),
        ProductCategory(product=products[34], category=categories[7]),
        ProductCategory(product=products[35], category=categories[7]),
        ProductCategory(product=products[36], category=categories[7]),
        ProductCategory(product=products[37], category=categories[8]),
        ProductCategory(product=products[38], category=categories[8]),
        ProductCategory(product=products[39], category=categories[8]),
        ProductCategory(product=products[40], category=categories[8]),
        
    ]

    ProductCategory.objects.bulk_create(product_category_data)



    ##product_variants (商品規格變體表)
    # 確保外鍵的資料已存在
    products = {p.product_id: p for p in Products.objects.all()}
    packages = {p.package_id: p for p in PackageTypes.objects.all()}
    sizes = {s.size_id: s for s in ProductSizes.objects.all()}
    fragrances = {f.fragrance_id: f for f in ProductFragrances.objects.all()}
    origins = {o.origin_id: o for o in ProductOrigins.objects.all()}
    # 準備要插入的資料
    product_variants = [
        ProductVariants(product=products[1], package=packages[1], size=sizes[3], fragrance=fragrances[8], origin=origins[1], price=350, is_gift=False),
        ProductVariants(product=products[1], package=packages[1], size=sizes[4], fragrance=fragrances[8], origin=origins[1], price=150, is_gift=True),
        ProductVariants(product=products[2], package=packages[1], size=sizes[3], fragrance=fragrances[10], origin=origins[1], price=350, is_gift=False),
        ProductVariants(product=products[2], package=packages[1], size=sizes[4], fragrance=fragrances[10], origin=origins[1], price=150, is_gift=True),
        ProductVariants(product=products[3], package=packages[1], size=sizes[3], fragrance=fragrances[1], origin=origins[1], price=350, is_gift=False),
        ProductVariants(product=products[3], package=packages[1], size=sizes[4], fragrance=fragrances[1], origin=origins[1], price=150, is_gift=True),
        ProductVariants(product=products[4], package=packages[1], size=sizes[3], fragrance=fragrances[3], origin=origins[1], price=350, is_gift=False),
        ProductVariants(product=products[4], package=packages[1], size=sizes[4], fragrance=fragrances[3], origin=origins[1], price=150, is_gift=True),
        ProductVariants(product=products[5], package=packages[1], size=sizes[3], fragrance=fragrances[2], origin=origins[1], price=350, is_gift=False),
        ProductVariants(product=products[5], package=packages[1], size=sizes[4], fragrance=fragrances[2], origin=origins[1], price=150, is_gift=True),
        ProductVariants(product=products[6], package=packages[1], size=sizes[8], fragrance=fragrances[2], origin=origins[1], price=499, is_gift=False),
        ProductVariants(product=products[6], package=packages[1], size=sizes[5], fragrance=fragrances[2], origin=origins[1], price=150, is_gift=True),
        ProductVariants(product=products[7], package=packages[1], size=sizes[8], fragrance=fragrances[10], origin=origins[1], price=499, is_gift=False),
        ProductVariants(product=products[7], package=packages[1], size=sizes[5], fragrance=fragrances[10], origin=origins[1], price=150, is_gift=True),
        ProductVariants(product=products[8], package=packages[1], size=sizes[8], fragrance=fragrances[4], origin=origins[1], price=499, is_gift=False),
        ProductVariants(product=products[8], package=packages[1], size=sizes[5], fragrance=fragrances[4], origin=origins[1], price=150, is_gift=True),
        ProductVariants(product=products[9], package=packages[1], size=sizes[8], fragrance=fragrances[6], origin=origins[1], price=499, is_gift=False),
        ProductVariants(product=products[9], package=packages[1], size=sizes[5], fragrance=fragrances[6], origin=origins[1], price=150, is_gift=True),
        ProductVariants(product=products[10], package=packages[1], size=sizes[8], fragrance=fragrances[5], origin=origins[1], price=499, is_gift=False),
        ProductVariants(product=products[10], package=packages[1], size=sizes[5], fragrance=fragrances[5], origin=origins[1], price=150, is_gift=True),
        ProductVariants(product=products[11], package=packages[1], size=sizes[8], fragrance=fragrances[8], origin=origins[1], price=499, is_gift=False),
        ProductVariants(product=products[11], package=packages[1], size=sizes[5], fragrance=fragrances[8], origin=origins[1], price=150, is_gift=True),
        ProductVariants(product=products[12], package=packages[1], size=sizes[8], fragrance=fragrances[13], origin=origins[1], price=499, is_gift=False),
        ProductVariants(product=products[12], package=packages[1], size=sizes[5], fragrance=fragrances[13], origin=origins[1], price=150, is_gift=True),
        ProductVariants(product=products[13], package=packages[1], size=sizes[8], fragrance=fragrances[7], origin=origins[1], price=499, is_gift=False),
        ProductVariants(product=products[13], package=packages[1], size=sizes[5], fragrance=fragrances[7], origin=origins[1], price=150, is_gift=True),
        ProductVariants(product=products[14], package=packages[1], size=sizes[8], fragrance=fragrances[4], origin=origins[1], price=499, is_gift=False),
        ProductVariants(product=products[14], package=packages[1], size=sizes[5], fragrance=fragrances[4], origin=origins[1], price=150, is_gift=True),
        ProductVariants(product=products[15], package=packages[1], size=sizes[8], fragrance=fragrances[12], origin=origins[1], price=499, is_gift=False),
        ProductVariants(product=products[15], package=packages[1], size=sizes[5], fragrance=fragrances[12], origin=origins[1], price=150, is_gift=True),
        ProductVariants(product=products[16], package=packages[1], size=sizes[6], fragrance=fragrances[6], origin=origins[1], price=320, is_gift=False),
        ProductVariants(product=products[16], package=packages[2], size=sizes[6], fragrance=fragrances[6], origin=origins[1], price=499, is_gift=False),
        ProductVariants(product=products[17], package=packages[1], size=sizes[6], fragrance=fragrances[3], origin=origins[1], price=320, is_gift=False),
        ProductVariants(product=products[17], package=packages[2], size=sizes[6], fragrance=fragrances[3], origin=origins[1], price=499, is_gift=False),
        ProductVariants(product=products[18], package=packages[1], size=sizes[6], fragrance=fragrances[4], origin=origins[1], price=320, is_gift=False),
        ProductVariants(product=products[18], package=packages[2], size=sizes[6], fragrance=fragrances[4], origin=origins[1], price=499, is_gift=False),
        ProductVariants(product=products[19], package=packages[1], size=sizes[6], fragrance=fragrances[8], origin=origins[2], price=450, is_gift=False),
        ProductVariants(product=products[19], package=packages[2], size=sizes[6], fragrance=fragrances[8], origin=origins[2], price=750, is_gift=False),
        ProductVariants(product=products[19], package=packages[1], size=sizes[5], fragrance=fragrances[8], origin=origins[2], price=150, is_gift=True),
        ProductVariants(product=products[20], package=packages[1], size=sizes[6], fragrance=fragrances[1], origin=origins[2], price=450, is_gift=False),
        ProductVariants(product=products[20], package=packages[2], size=sizes[6], fragrance=fragrances[1], origin=origins[2], price=750, is_gift=False),
        ProductVariants(product=products[20], package=packages[1], size=sizes[5], fragrance=fragrances[1], origin=origins[2], price=150, is_gift=True),
        ProductVariants(product=products[21], package=packages[1], size=sizes[6], fragrance=fragrances[7], origin=origins[2], price=450, is_gift=False),
        ProductVariants(product=products[21], package=packages[2], size=sizes[6], fragrance=fragrances[7], origin=origins[2], price=750, is_gift=False),
        ProductVariants(product=products[21], package=packages[1], size=sizes[5], fragrance=fragrances[7], origin=origins[2], price=150, is_gift=True),
        ProductVariants(product=products[22], package=packages[1], size=sizes[6], fragrance=fragrances[10], origin=origins[2], price=450, is_gift=False),
        ProductVariants(product=products[22], package=packages[2], size=sizes[6], fragrance=fragrances[10], origin=origins[2], price=750, is_gift=False),
        ProductVariants(product=products[22], package=packages[1], size=sizes[5], fragrance=fragrances[10], origin=origins[2], price=150, is_gift=True),
        ProductVariants(product=products[23], package=packages[1], size=sizes[6], fragrance=fragrances[13], origin=origins[2], price=450, is_gift=False),
        ProductVariants(product=products[23], package=packages[2], size=sizes[6], fragrance=fragrances[13], origin=origins[2], price=750, is_gift=False),
        ProductVariants(product=products[23], package=packages[1], size=sizes[5], fragrance=fragrances[13], origin=origins[2], price=150, is_gift=True),
        ProductVariants(product=products[24], package=packages[1], size=sizes[6], fragrance=fragrances[8], origin=origins[2], price=450, is_gift=False),
        ProductVariants(product=products[24], package=packages[2], size=sizes[6], fragrance=fragrances[8], origin=origins[2], price=750, is_gift=False),
        ProductVariants(product=products[24], package=packages[1], size=sizes[5], fragrance=fragrances[8], origin=origins[2], price=150, is_gift=True),
        ProductVariants(product=products[25], package=packages[1], size=sizes[6], fragrance=fragrances[1], origin=origins[2], price=450, is_gift=False),
        ProductVariants(product=products[25], package=packages[2], size=sizes[6], fragrance=fragrances[1], origin=origins[2], price=750, is_gift=False),
        ProductVariants(product=products[25], package=packages[1], size=sizes[5], fragrance=fragrances[1], origin=origins[2], price=150, is_gift=True),
        ProductVariants(product=products[26], package=packages[1], size=sizes[6], fragrance=fragrances[7], origin=origins[2], price=450, is_gift=False),
        ProductVariants(product=products[26], package=packages[2], size=sizes[6], fragrance=fragrances[7], origin=origins[2], price=750, is_gift=False),
        ProductVariants(product=products[26], package=packages[1], size=sizes[5], fragrance=fragrances[7], origin=origins[2], price=150, is_gift=True),
        ProductVariants(product=products[27], package=packages[1], size=sizes[6], fragrance=fragrances[10], origin=origins[2], price=450, is_gift=False),
        ProductVariants(product=products[27], package=packages[2], size=sizes[6], fragrance=fragrances[10], origin=origins[2], price=750, is_gift=False),
        ProductVariants(product=products[27], package=packages[1], size=sizes[5], fragrance=fragrances[10], origin=origins[2], price=150, is_gift=True),
        ProductVariants(product=products[28], package=packages[1], size=sizes[6], fragrance=fragrances[13], origin=origins[2], price=450, is_gift=False),
        ProductVariants(product=products[28], package=packages[2], size=sizes[6], fragrance=fragrances[13], origin=origins[2], price=750, is_gift=False),
        ProductVariants(product=products[28], package=packages[1], size=sizes[5], fragrance=fragrances[13], origin=origins[2], price=150, is_gift=True),
        ProductVariants(product=products[29], package=packages[1], size=sizes[7], fragrance=fragrances[6], origin=origins[1], price=550, is_gift=False),
        ProductVariants(product=products[29], package=packages[1], size=sizes[4], fragrance=fragrances[6], origin=origins[1], price=150, is_gift=True),
        ProductVariants(product=products[30], package=packages[1], size=sizes[7], fragrance=fragrances[5], origin=origins[1], price=550, is_gift=False),
        ProductVariants(product=products[30], package=packages[1], size=sizes[4], fragrance=fragrances[5], origin=origins[1], price=150, is_gift=True),
        ProductVariants(product=products[31], package=packages[1], size=sizes[7], fragrance=fragrances[9], origin=origins[1], price=550, is_gift=False),
        ProductVariants(product=products[31], package=packages[1], size=sizes[4], fragrance=fragrances[9], origin=origins[1], price=150, is_gift=True),
        ProductVariants(product=products[32], package=packages[1], size=sizes[7], fragrance=fragrances[8], origin=origins[5], price=580, is_gift=False),
        ProductVariants(product=products[32], package=packages[2], size=sizes[7], fragrance=fragrances[8], origin=origins[5], price=999, is_gift=False),
        ProductVariants(product=products[33], package=packages[1], size=sizes[7], fragrance=fragrances[1], origin=origins[5], price=580, is_gift=False),
        ProductVariants(product=products[33], package=packages[2], size=sizes[7], fragrance=fragrances[1], origin=origins[5], price=999, is_gift=False),
        ProductVariants(product=products[34], package=packages[1], size=sizes[7], fragrance=fragrances[7], origin=origins[5], price=580, is_gift=False),
        ProductVariants(product=products[34], package=packages[2], size=sizes[7], fragrance=fragrances[7], origin=origins[5], price=999, is_gift=False),
        ProductVariants(product=products[35], package=packages[1], size=sizes[7], fragrance=fragrances[10], origin=origins[5], price=580, is_gift=False),
        ProductVariants(product=products[35], package=packages[2], size=sizes[7], fragrance=fragrances[10], origin=origins[5], price=999, is_gift=False),
        ProductVariants(product=products[36], package=packages[1], size=sizes[7], fragrance=fragrances[13], origin=origins[5], price=580, is_gift=False),
        ProductVariants(product=products[36], package=packages[2], size=sizes[7], fragrance=fragrances[13], origin=origins[5], price=999, is_gift=False),
        ProductVariants(product=products[37], package=packages[1], size=sizes[2], fragrance=fragrances[3], origin=origins[7], price=699, is_gift=False),
        ProductVariants(product=products[37], package=packages[1], size=sizes[1], fragrance=fragrances[3], origin=origins[7], price=520, is_gift=False),
        ProductVariants(product=products[37], package=packages[2], size=sizes[1], fragrance=fragrances[3], origin=origins[7], price=899, is_gift=False),
        ProductVariants(product=products[37], package=packages[3], size=sizes[1], fragrance=fragrances[3], origin=origins[7], price=1199, is_gift=False),
        ProductVariants(product=products[38], package=packages[1], size=sizes[2], fragrance=fragrances[2], origin=origins[7], price=699, is_gift=False),
        ProductVariants(product=products[38], package=packages[1], size=sizes[1], fragrance=fragrances[2], origin=origins[7], price=520, is_gift=False),
        ProductVariants(product=products[38], package=packages[2], size=sizes[1], fragrance=fragrances[2], origin=origins[7], price=899, is_gift=False),
        ProductVariants(product=products[38], package=packages[3], size=sizes[1], fragrance=fragrances[2], origin=origins[7], price=1199, is_gift=False),
        ProductVariants(product=products[39], package=packages[1], size=sizes[2], fragrance=fragrances[5], origin=origins[7], price=699, is_gift=False),
        ProductVariants(product=products[39], package=packages[1], size=sizes[1], fragrance=fragrances[5], origin=origins[7], price=520, is_gift=False),
        ProductVariants(product=products[39], package=packages[2], size=sizes[1], fragrance=fragrances[5], origin=origins[7], price=899, is_gift=False),
        ProductVariants(product=products[39], package=packages[3], size=sizes[1], fragrance=fragrances[5], origin=origins[7], price=1199, is_gift=False),
        ProductVariants(product=products[40], package=packages[1], size=sizes[2], fragrance=fragrances[11], origin=origins[7], price=699, is_gift=False),
        ProductVariants(product=products[40], package=packages[1], size=sizes[1], fragrance=fragrances[11], origin=origins[7], price=520, is_gift=False),
        ProductVariants(product=products[40], package=packages[2], size=sizes[1], fragrance=fragrances[11], origin=origins[7], price=899, is_gift=False),
        ProductVariants(product=products[40], package=packages[3], size=sizes[1], fragrance=fragrances[11], origin=origins[7], price=1199, is_gift=False),   
        ProductVariants(product=products[41], package=packages[1], origin=origins[1], price=990, is_gift=True),   
    ]

    # 批量插入資料
    ProductVariants.objects.bulk_create(product_variants)


    ##商品圖片 (product_images)
    # 準備要插入的資料
    data = [
        ProductImages(variant_id=1, image_name='moisturizing_facialCleanser_120g.png'),
        ProductImages(variant_id=2, image_name='moisturizing_facialCleanser_10ml.png'),
        ProductImages(variant_id=3, image_name='oilControl_facialCleanserr_120g.png'),
        ProductImages(variant_id=4, image_name='oilControl_facialCleanser_10ml.png'),
        ProductImages(variant_id=5, image_name='gentle_facialCleanserr_120g.png'),
        ProductImages(variant_id=6, image_name='gentle_facialCleanser_10ml.png'),
        ProductImages(variant_id=7, image_name='exfoliating_facialCleanserr_120g.png'),
        ProductImages(variant_id=8, image_name='exfoliating_facialCleanser_10ml.png'),
        ProductImages(variant_id=9, image_name='whitening_facialCleanserr_120g.png'),
        ProductImages(variant_id=10, image_name='whitening_facialCleanser_10ml.png'),
        ProductImages(variant_id=11, image_name='moisturizing_shampoo_500ml.png'),
        ProductImages(variant_id=12, image_name='moisturizing_shampoo_30ml.png'),
        ProductImages(variant_id=13, image_name='oilControl_shampoo_500ml.png'),
        ProductImages(variant_id=14, image_name='oilControl_shampoo_30ml.png'),
        ProductImages(variant_id=15, image_name='antiDandruff_shampoo_500ml.png'),
        ProductImages(variant_id=16, image_name='antiDandruff_shampoo_30ml.png'),
        ProductImages(variant_id=17, image_name='colorSafe_shampoo_500ml.png'),
        ProductImages(variant_id=18, image_name='colorSafe_shampoo_30ml.png'),
        ProductImages(variant_id=19, image_name='repair_shampoo_500ml.png'),
        ProductImages(variant_id=20, image_name='repair_shampoo_30ml.png'),
        ProductImages(variant_id=21, image_name='moisturizing_bodyWash_500ml.png'),
        ProductImages(variant_id=22, image_name='moisturizing_bodyWash_30ml.png'),
        ProductImages(variant_id=23, image_name='soothing_bodyWash_500ml.png'),
        ProductImages(variant_id=24, image_name='soothing_bodyWash_30ml.png'),
        ProductImages(variant_id=25, image_name='antiAcne_bodyWash_500ml.png'),
        ProductImages(variant_id=26, image_name='antiAcne_bodyWash_30ml.png'),
        ProductImages(variant_id=27, image_name='oilControl_bodyWash_500ml.png'),
        ProductImages(variant_id=28, image_name='oilControl_bodyWash_30ml.png'),
        ProductImages(variant_id=29, image_name='whitening_bodyWash_500ml.png'),
        ProductImages(variant_id=30, image_name='whitening_bodyWash_30ml.png'),
        ProductImages(variant_id=31, image_name='moisturizing_handWashMousse_200ml.png'),
        ProductImages(variant_id=32, image_name='moisturizing_handWashMousse_200ml_x2.png'),
        ProductImages(variant_id=33, image_name='gentle_handWashMousse_200ml.png'),
        ProductImages(variant_id=34, image_name='gentle_handWashMousse_200ml_x2.png'),
        ProductImages(variant_id=35, image_name='antiBacterial_handWashMousse_200ml.png'),
        ProductImages(variant_id=36, image_name='antiBacterial_handWashMousse_200ml_x2.png'),
        ProductImages(variant_id=37, image_name='moisturizing_toner_200ml.png'),
        ProductImages(variant_id=38, image_name='moisturizing_toner_200ml_x2.png'),
        ProductImages(variant_id=39, image_name='moisturizing_toner_30ml.png'),
        ProductImages(variant_id=40, image_name='soothing_toner_200ml.png'),
        ProductImages(variant_id=41, image_name='soothing_toner_200ml_x2.png'),
        ProductImages(variant_id=42, image_name='soothing_toner_30ml.png'),
        ProductImages(variant_id=43, image_name='antiAcne_toner_200ml.png'),
        ProductImages(variant_id=44, image_name='antiAcne_toner_200ml_x2.png'),
        ProductImages(variant_id=45, image_name='antiAcne_toner_30ml.png'),
        ProductImages(variant_id=46, image_name='oilControl_toner_200ml.png'),
        ProductImages(variant_id=47, image_name='oilControl_toner_200ml_x2.png'),
        ProductImages(variant_id=48, image_name='oilControl_toner_30ml.png'),
        ProductImages(variant_id=49, image_name='whitening_toner_200ml.png'),
        ProductImages(variant_id=50, image_name='whitening_toner_200ml_x2.png'),
        ProductImages(variant_id=51, image_name='whitening_toner_30ml.png'),
        ProductImages(variant_id=52, image_name='moisturizing_lotion_200ml.png'),
        ProductImages(variant_id=53, image_name='moisturizing_lotion_200ml_x2.png'),
        ProductImages(variant_id=54, image_name='moisturizing_lotion_30ml.png'),
        ProductImages(variant_id=55, image_name='soothing_lotion_200ml.png'),
        ProductImages(variant_id=56, image_name='soothing_lotion_200ml_x2.png'),
        ProductImages(variant_id=57, image_name='soothing_lotion_30ml.png'),
        ProductImages(variant_id=58, image_name='antiAcne_lotion_200ml.png'),
        ProductImages(variant_id=59, image_name='antiAcne_lotion_200ml_x2.png'),
        ProductImages(variant_id=60, image_name='antiAcne_lotion_30ml.png'),
        ProductImages(variant_id=61, image_name='oilControl_lotion_200ml.png'),
        ProductImages(variant_id=62, image_name='oilControl_lotion_200ml_x2.png'),
        ProductImages(variant_id=63, image_name='oilControl_lotion_30ml.png'),
        ProductImages(variant_id=64, image_name='whitening_lotion_200ml.png'),
        ProductImages(variant_id=65, image_name='whitening_lotion_200ml_x2.png'),
        ProductImages(variant_id=66, image_name='whitening_lotion_30ml.png'),
        ProductImages(variant_id=67, image_name='moisturizing_conditioner_350ml.png'),
        ProductImages(variant_id=68, image_name='moisturizing_conditioner_10ml.png'),
        ProductImages(variant_id=69, image_name='colorSafe_conditioner_350ml.png'),
        ProductImages(variant_id=70, image_name='colorSafe_conditioner_10ml.png'),
        ProductImages(variant_id=71, image_name='repair_conditioner_350ml.png'),
        ProductImages(variant_id=72, image_name='repair_conditioner_10ml.png'),
        ProductImages(variant_id=73, image_name='moisturizing_bodyLotion_350ml.png'),
        ProductImages(variant_id=74, image_name='moisturizing_bodyLotion_350ml_x2.png'),
        ProductImages(variant_id=75, image_name='soothing_bodyLotion_350ml.png'),
        ProductImages(variant_id=76, image_name='soothing_bodyLotion_350ml_x2.png'),
        ProductImages(variant_id=77, image_name='antiAcne_bodyLotion_350ml.png'),
        ProductImages(variant_id=78, image_name='antiAcne_bodyLotion_350ml_x2.png'),
        ProductImages(variant_id=79, image_name='oilControl_bodyLotion_350ml.png'),
        ProductImages(variant_id=80, image_name='oilControl_bodyLotion_350ml_x2.png'),
        ProductImages(variant_id=81, image_name='whitening_bodyLotion_350ml.png'),
        ProductImages(variant_id=82, image_name='whitening_bodyLotion_350ml_x2.png'),
        ProductImages(variant_id=83, image_name='repair_handCream_75g.png'),
        ProductImages(variant_id=84, image_name='repair_handCream_50g.png'),
        ProductImages(variant_id=85, image_name='repair_handCream_50g_x2.png'),
        ProductImages(variant_id=86, image_name='repair_handCream_50g_x3.png'),
        ProductImages(variant_id=87, image_name='moisturizing_handCream_75g.png'),
        ProductImages(variant_id=88, image_name='moisturizing_handCream_50g.png'),
        ProductImages(variant_id=89, image_name='moisturizing_handCream_50g_x2.png'),
        ProductImages(variant_id=90, image_name='moisturizing_handCream_50g_x3.png'),
        ProductImages(variant_id=91, image_name='watery_handCream_75g.png'),
        ProductImages(variant_id=92, image_name='watery_handCream_50g.png'),
        ProductImages(variant_id=93, image_name='watery_handCream_50g_x2.png'),
        ProductImages(variant_id=94, image_name='watery_handCream_50g_x3.png'),
        ProductImages(variant_id=95, image_name='whitening_handCream_75g.png'),
        ProductImages(variant_id=96, image_name='whitening_handCream_50g.png'),
        ProductImages(variant_id=97, image_name='whitening_handCream_50g_x2.png'),
        ProductImages(variant_id=98, image_name='whitening_handCream_50g_x3.png'),
        ProductImages(variant_id=99, image_name='shopping_bag.png'),
    ]

    # 使用 bulk_create 一次性插入
    ProductImages.objects.bulk_create(data)



    ##活動 (promotions)    
    # 準備要插入的資料
    promotions = [
        Promotions(
            promo_name="開幕滿額贈品",
            promotion_type="活動",
            discount_type="贈品",
            discount_value=0,
            minimum_spending=1000,  # 最低消費金額為 1000
            trigger_quantity=None,
            conditions="單筆消費滿$1000送購物袋",
            apply_method="自動套用",
            promo_code=None,
            usage_limit=1000,
            per_user_limit=None,
            start_date=datetime(2025, 3, 15, 0, 0), 
            end_date=datetime(2035, 5, 15, 23, 59),
            is_accumulative_discount=False,
            is_accumulative_gift=True,
        ),
        Promotions(
            promo_name="母親節滿額折扣",
            promotion_type="活動",
            discount_type="百分比折扣",
            discount_value=10,
            minimum_spending=1000,  # 最低消費金額為 1000
            trigger_quantity=None,
            conditions="單筆消費滿$1000打九折",
            apply_method="自動套用",
            promo_code=None,
            usage_limit=None,  # 無限使用次數
            per_user_limit=None,
            start_date=datetime(2025, 3, 25, 0, 0),
            end_date=datetime(2035, 5, 11, 23, 59),
            is_accumulative_discount=False,
            is_accumulative_gift=False,
        ),
        Promotions(
            promo_name="新會員限定折扣",
            promotion_type="優惠券",
            discount_type="固定金額折扣",
            discount_value=100,
            minimum_spending=100,
            trigger_quantity=None,
            conditions="輸入優惠碼[WELCOME100]折100元",
            apply_method="優惠碼",
            promo_code="WELCOME100",
            receive_method = "先發放",
            usage_limit=5000,
            per_user_limit=1,
            start_date=datetime(2025, 1, 1, 0, 0),
            end_date=datetime(2035, 12, 31, 23, 59),
            is_accumulative_discount=False,
            is_accumulative_gift=False,
        ),
        Promotions(
            promo_name="新品試用活動",
            promotion_type="優惠券",
            discount_type="贈品",
            discount_value=0,
            minimum_spending=None,
            trigger_quantity=None,
            conditions="輸入優惠碼[TRIAL2025]贈送控油洗面乳10ml 2包",
            apply_method="優惠碼",
            promo_code="TRIAL2025",
            receive_method = "自由輸入",
            usage_limit=3000,
            per_user_limit=2,
            start_date=datetime(2025, 3, 28, 0, 0),
            end_date=datetime(2035, 5, 31, 23, 59),
            is_accumulative_discount=False,
            is_accumulative_gift=False,
        ),
    ]
    # 批量插入資料
    Promotions.objects.bulk_create(promotions)
    
    promotion5 = Promotions.objects.create(
        promo_name="身體清潔滿件贈品",
        promotion_type="活動",
        discount_type="贈品",
        discount_value=0,
        minimum_spending=None,
        trigger_quantity=3,
        conditions="購買身體清潔類商品滿3件送美白沐浴乳30mL",
        apply_method="自動套用",
        promo_code=None,
        receive_method=None,
        usage_limit=2000,
        per_user_limit=None,
        start_date=datetime(2025, 3, 31, 0, 0),
        end_date=datetime(2035, 5, 31, 23, 59),
        is_accumulative_discount=False,
        is_accumulative_gift=True,
    )

    promotion6 = Promotions.objects.create(
        promo_name="溫和洗手慕斯買2折10元",
        promotion_type="活動",
        discount_type="固定金額折扣",
        discount_value=10,
        minimum_spending=None,
        trigger_quantity=2,
        conditions="購買溫和洗手慕斯 2 件折 10 元",
        apply_method="自動套用",
        promo_code=None,
        receive_method=None,
        usage_limit=1000,
        per_user_limit=None,
        start_date=datetime(2025, 3, 31, 0, 0),
        end_date=datetime(2035, 5, 31, 23, 59),
        is_accumulative_discount=True,
        is_accumulative_gift=False,
    )
    
    # 抓出對應會員等級
    gold = MembershipLevels.objects.get(level_name="黃金會員")
    platinum = MembershipLevels.objects.get(level_name="白金會員")
    diamond = MembershipLevels.objects.get(level_name="鑽石會員")

    # 建立活動（單一折扣活動代表一個會員等級）
    gold_promo = Promotions.objects.create(
        promo_name="黃金會員專屬折扣",
        promotion_type="活動",
        discount_type="百分比折扣",
        discount_value=gold.discount_rate,  # 即 4 表示打 96 折
        minimum_spending=None,
        trigger_quantity=None,
        conditions="黃金會員全站享 96 折",
        apply_method="自動套用",
        is_vip_only=True,
        usage_limit=None,
        per_user_limit=None,
        is_accumulative_discount=False,
        is_accumulative_gift=False,
        start_date=datetime(2025, 1, 1, 0, 0),
        end_date=datetime(2035, 12, 31, 23, 59),
    )
    gold_promo.target_levels.add(gold)

    platinum_promo = Promotions.objects.create(
        promo_name="白金會員專屬折扣",
        promotion_type="活動",
        discount_type="百分比折扣",
        discount_value=platinum.discount_rate,  # 即 8 表示打 92 折
        minimum_spending=None,
        trigger_quantity=None,
        conditions="白金會員全站享 92 折",
        apply_method="自動套用",
        is_vip_only=True,
        usage_limit=None,
        per_user_limit=None,
        is_accumulative_discount=False,
        is_accumulative_gift=False,
        start_date=datetime(2025, 1, 1, 0, 0),
        end_date=datetime(2035, 12, 31, 23, 59),
    )
    platinum_promo.target_levels.add(platinum)

    diamond_promo = Promotions.objects.create(
        promo_name="鑽石會員專屬折扣",
        promotion_type="活動",
        discount_type="百分比折扣",
        discount_value=diamond.discount_rate,  # 即 12 表示打 88 折
        minimum_spending=None,
        trigger_quantity=None,
        conditions="鑽石會員全站享 88 折",
        apply_method="自動套用",
        is_vip_only=True,
        usage_limit=None,
        per_user_limit=None,
        is_accumulative_discount=False,
        is_accumulative_gift=False,
        start_date=datetime(2025, 1, 1, 0, 0),
        end_date=datetime(2035, 12, 31, 23, 59),
    )
    diamond_promo.target_levels.add(diamond)
    
    PromotionTargetCategories.objects.create(
        promo=promotion5,
        category_id=3  # 身體清潔分類為 category_id = 3
    )
    
    PromotionTargetVariants.objects.create(
        promo=promotion6,
        variant_id=33  # 溫和洗手慕斯的 variant_id = 33
    )
    
    ##活動圖片 (promotion_images)
    # 準備要插入的資料
    data = [
        PromotionImages(promo_id=1, image_name='event_01.png'),
        PromotionImages(promo_id=2, image_name='event_02.png'),
        PromotionImages(promo_id=3, image_name='event_03.png'),
        PromotionImages(promo_id=3, image_name='coupon_welcome.png', display_order=1),
    ]

    # 使用 bulk_create 一次性插入
    PromotionImages.objects.bulk_create(data)

    #贈品表 (promotion_gifts)
    # 取得「開幕滿額贈品」的活動
    opening_promo = Promotions.objects.get(promo_name="開幕滿額贈品")

    # 取得「新品試用活動」的優惠券活動
    trial_promo = Promotions.objects.get(promo_name="新品試用活動")
    
    # 取得「身體清潔滿件贈品」活動
    bodycare_promo = Promotions.objects.get(promo_name="身體清潔滿件贈品")

    # 插入贈品（需確保 variant_id 存在）
    gift_entries = [
        PromotionGifts(promo=opening_promo, variant_id=99, gift_quantity=1),  # 送購物袋 1 個
        PromotionGifts(promo=trial_promo, variant_id=4, gift_quantity=2),   # 送控油洗面乳 2 包
        PromotionGifts(promo=bodycare_promo, variant_id=30, gift_quantity=1), # 送美白沐浴乳30mL*1
    ]

    # 批量建立
    PromotionGifts.objects.bulk_create(gift_entries)


    ##進貨紀錄 (stock_in)
    # 確保外鍵的資料已存在
    variants = {v.variant_id: v for v in ProductVariants.objects.all()}
    suppliers = {s.supplier_id: s for s in Suppliers.objects.all()}
    # 準備要插入的資料
    stock_in_records = [
        StockIn(variant=variants[1], supplier=suppliers[1], quantity=50, purchase_price=100, received_date=date(2025, 3, 1), expiration_date=date(2027, 2, 28), remaining_quantity=50),
        StockIn(variant=variants[2], supplier=suppliers[1], quantity=50, purchase_price=10, received_date=date(2025, 3, 1), expiration_date=date(2027, 2, 28), remaining_quantity=50),
        StockIn(variant=variants[3], supplier=suppliers[1], quantity=50, purchase_price=100, received_date=date(2025, 3, 1), expiration_date=date(2027, 2, 28), remaining_quantity=50),
        StockIn(variant=variants[4], supplier=suppliers[1], quantity=50, purchase_price=10, received_date=date(2025, 3, 1), expiration_date=date(2027, 2, 28), remaining_quantity=50),
        StockIn(variant=variants[5], supplier=suppliers[1], quantity=50, purchase_price=100, received_date=date(2025, 3, 1), expiration_date=date(2027, 2, 28), remaining_quantity=50),
        StockIn(variant=variants[6], supplier=suppliers[1], quantity=50, purchase_price=10, received_date=date(2025, 3, 1), expiration_date=date(2027, 2, 28), remaining_quantity=50),
        StockIn(variant=variants[7], supplier=suppliers[1], quantity=50, purchase_price=100, received_date=date(2025, 3, 1), expiration_date=date(2027, 2, 28), remaining_quantity=50),
        StockIn(variant=variants[8], supplier=suppliers[1], quantity=50, purchase_price=10, received_date=date(2025, 3, 1), expiration_date=date(2027, 2, 28), remaining_quantity=50),
        StockIn(variant=variants[9], supplier=suppliers[1], quantity=50, purchase_price=100, received_date=date(2025, 3, 1), expiration_date=date(2027, 2, 28), remaining_quantity=50),
        StockIn(variant=variants[10], supplier=suppliers[1], quantity=50, purchase_price=10, received_date=date(2025, 3, 1), expiration_date=date(2027, 2, 28), remaining_quantity=50),
        StockIn(variant=variants[11], supplier=suppliers[9], quantity=50, purchase_price=200, received_date=date(2025, 3, 1), expiration_date=date(2027, 2, 28), remaining_quantity=50),
        StockIn(variant=variants[12], supplier=suppliers[9], quantity=50, purchase_price=10, received_date=date(2025, 3, 1), expiration_date=date(2027, 2, 28), remaining_quantity=50),
        StockIn(variant=variants[13], supplier=suppliers[9], quantity=50, purchase_price=200, received_date=date(2025, 3, 1), expiration_date=date(2027, 2, 28), remaining_quantity=50),
        StockIn(variant=variants[14], supplier=suppliers[9], quantity=50, purchase_price=10, received_date=date(2025, 3, 1), expiration_date=date(2027, 2, 28), remaining_quantity=50),
        StockIn(variant=variants[15], supplier=suppliers[9], quantity=50, purchase_price=200, received_date=date(2025, 3, 1), expiration_date=date(2027, 2, 28), remaining_quantity=50),
        StockIn(variant=variants[16], supplier=suppliers[9], quantity=50, purchase_price=10, received_date=date(2025, 3, 1), expiration_date=date(2027, 2, 28), remaining_quantity=50),
        StockIn(variant=variants[17], supplier=suppliers[9], quantity=50, purchase_price=200, received_date=date(2025, 3, 1), expiration_date=date(2027, 2, 28), remaining_quantity=50),
        StockIn(variant=variants[18], supplier=suppliers[9], quantity=50, purchase_price=10, received_date=date(2025, 3, 1), expiration_date=date(2027, 2, 28), remaining_quantity=50),
        StockIn(variant=variants[19], supplier=suppliers[9], quantity=50, purchase_price=200, received_date=date(2025, 3, 1), expiration_date=date(2027, 2, 28), remaining_quantity=50),
        StockIn(variant=variants[20], supplier=suppliers[9], quantity=50, purchase_price=10, received_date=date(2025, 3, 1), expiration_date=date(2027, 2, 28), remaining_quantity=50),
        StockIn(variant=variants[21], supplier=suppliers[6], quantity=50, purchase_price=200, received_date=date(2025, 3, 1), expiration_date=date(2027, 2, 28), remaining_quantity=50),
        StockIn(variant=variants[22], supplier=suppliers[6], quantity=50, purchase_price=10, received_date=date(2025, 3, 1), expiration_date=date(2027, 2, 28), remaining_quantity=50),
        StockIn(variant=variants[23], supplier=suppliers[6], quantity=50, purchase_price=200, received_date=date(2025, 3, 1), expiration_date=date(2027, 2, 28), remaining_quantity=50),
        StockIn(variant=variants[24], supplier=suppliers[6], quantity=50, purchase_price=10, received_date=date(2025, 3, 1), expiration_date=date(2027, 2, 28), remaining_quantity=50),
        StockIn(variant=variants[25], supplier=suppliers[6], quantity=50, purchase_price=200, received_date=date(2025, 3, 1), expiration_date=date(2027, 2, 28), remaining_quantity=50),
        StockIn(variant=variants[26], supplier=suppliers[6], quantity=50, purchase_price=10, received_date=date(2025, 3, 1), expiration_date=date(2027, 2, 28), remaining_quantity=50),
        StockIn(variant=variants[27], supplier=suppliers[6], quantity=50, purchase_price=200, received_date=date(2025, 3, 1), expiration_date=date(2027, 2, 28), remaining_quantity=50),
        StockIn(variant=variants[28], supplier=suppliers[6], quantity=50, purchase_price=10, received_date=date(2025, 3, 1), expiration_date=date(2027, 2, 28), remaining_quantity=50),
        StockIn(variant=variants[29], supplier=suppliers[6], quantity=50, purchase_price=200, received_date=date(2025, 3, 1), expiration_date=date(2027, 2, 28), remaining_quantity=50),
        StockIn(variant=variants[30], supplier=suppliers[6], quantity=50, purchase_price=10, received_date=date(2025, 3, 1), expiration_date=date(2027, 2, 28), remaining_quantity=50),
        StockIn(variant=variants[31], supplier=suppliers[5], quantity=50, purchase_price=100, received_date=date(2025, 3, 1), expiration_date=date(2028, 2, 28), remaining_quantity=50),
        StockIn(variant=variants[32], supplier=suppliers[5], quantity=50, purchase_price=200, received_date=date(2025, 3, 1), expiration_date=date(2028, 2, 28), remaining_quantity=50),
        StockIn(variant=variants[33], supplier=suppliers[5], quantity=50, purchase_price=100, received_date=date(2025, 3, 1), expiration_date=date(2028, 2, 28), remaining_quantity=50),
        StockIn(variant=variants[34], supplier=suppliers[5], quantity=50, purchase_price=200, received_date=date(2025, 3, 1), expiration_date=date(2028, 2, 28), remaining_quantity=50),
        StockIn(variant=variants[35], supplier=suppliers[5], quantity=50, purchase_price=100, received_date=date(2025, 3, 1), expiration_date=date(2028, 2, 28), remaining_quantity=50),
        StockIn(variant=variants[36], supplier=suppliers[5], quantity=50, purchase_price=200, received_date=date(2025, 3, 1), expiration_date=date(2028, 2, 28), remaining_quantity=50),
        StockIn(variant=variants[37], supplier=suppliers[4], quantity=50, purchase_price=200, received_date=date(2025, 3, 1), expiration_date=date(2027, 2, 28), remaining_quantity=50),
        StockIn(variant=variants[38], supplier=suppliers[4], quantity=50, purchase_price=400, received_date=date(2025, 3, 1), expiration_date=date(2027, 2, 28), remaining_quantity=50),
        StockIn(variant=variants[39], supplier=suppliers[4], quantity=50, purchase_price=10, received_date=date(2025, 3, 1), expiration_date=date(2027, 2, 28), remaining_quantity=50),
        StockIn(variant=variants[40], supplier=suppliers[4], quantity=50, purchase_price=200, received_date=date(2025, 3, 1), expiration_date=date(2027, 2, 28), remaining_quantity=50),
        StockIn(variant=variants[41], supplier=suppliers[4], quantity=50, purchase_price=400, received_date=date(2025, 3, 1), expiration_date=date(2027, 2, 28), remaining_quantity=50),
        StockIn(variant=variants[42], supplier=suppliers[4], quantity=50, purchase_price=10, received_date=date(2025, 3, 1), expiration_date=date(2027, 2, 28), remaining_quantity=50),
        StockIn(variant=variants[43], supplier=suppliers[4], quantity=50, purchase_price=200, received_date=date(2025, 3, 1), expiration_date=date(2027, 2, 28), remaining_quantity=50),
        StockIn(variant=variants[44], supplier=suppliers[4], quantity=50, purchase_price=400, received_date=date(2025, 3, 1), expiration_date=date(2027, 2, 28), remaining_quantity=50),
        StockIn(variant=variants[45], supplier=suppliers[4], quantity=50, purchase_price=10, received_date=date(2025, 3, 1), expiration_date=date(2027, 2, 28), remaining_quantity=50),
        StockIn(variant=variants[46], supplier=suppliers[4], quantity=50, purchase_price=200, received_date=date(2025, 3, 1), expiration_date=date(2027, 2, 28), remaining_quantity=50),
        StockIn(variant=variants[47], supplier=suppliers[4], quantity=50, purchase_price=400, received_date=date(2025, 3, 1), expiration_date=date(2027, 2, 28), remaining_quantity=50),
        StockIn(variant=variants[48], supplier=suppliers[4], quantity=50, purchase_price=10, received_date=date(2025, 3, 1), expiration_date=date(2027, 2, 28), remaining_quantity=50),
        StockIn(variant=variants[49], supplier=suppliers[4], quantity=50, purchase_price=200, received_date=date(2025, 3, 1), expiration_date=date(2027, 2, 28), remaining_quantity=50),
        StockIn(variant=variants[50], supplier=suppliers[4], quantity=50, purchase_price=400, received_date=date(2025, 3, 1), expiration_date=date(2027, 2, 28), remaining_quantity=50),
        StockIn(variant=variants[51], supplier=suppliers[4], quantity=50, purchase_price=10, received_date=date(2025, 3, 1), expiration_date=date(2027, 2, 28), remaining_quantity=50),
        StockIn(variant=variants[52], supplier=suppliers[4], quantity=50, purchase_price=200, received_date=date(2025, 3, 1), expiration_date=date(2027, 2, 28), remaining_quantity=50),
        StockIn(variant=variants[53], supplier=suppliers[4], quantity=50, purchase_price=400, received_date=date(2025, 3, 1), expiration_date=date(2027, 2, 28), remaining_quantity=50),
        StockIn(variant=variants[54], supplier=suppliers[4], quantity=50, purchase_price=10, received_date=date(2025, 3, 1), expiration_date=date(2027, 2, 28), remaining_quantity=50),
        StockIn(variant=variants[55], supplier=suppliers[4], quantity=50, purchase_price=200, received_date=date(2025, 3, 1), expiration_date=date(2027, 2, 28), remaining_quantity=50),
        StockIn(variant=variants[56], supplier=suppliers[4], quantity=50, purchase_price=400, received_date=date(2025, 3, 1), expiration_date=date(2027, 2, 28), remaining_quantity=50),
        StockIn(variant=variants[57], supplier=suppliers[4], quantity=50, purchase_price=10, received_date=date(2025, 3, 1), expiration_date=date(2027, 2, 28), remaining_quantity=50),
        StockIn(variant=variants[58], supplier=suppliers[4], quantity=50, purchase_price=200, received_date=date(2025, 3, 1), expiration_date=date(2027, 2, 28), remaining_quantity=50),
        StockIn(variant=variants[59], supplier=suppliers[4], quantity=50, purchase_price=400, received_date=date(2025, 3, 1), expiration_date=date(2027, 2, 28), remaining_quantity=50),
        StockIn(variant=variants[60], supplier=suppliers[4], quantity=50, purchase_price=10, received_date=date(2025, 3, 1), expiration_date=date(2027, 2, 28), remaining_quantity=50),
        StockIn(variant=variants[61], supplier=suppliers[4], quantity=50, purchase_price=200, received_date=date(2025, 3, 1), expiration_date=date(2027, 2, 28), remaining_quantity=50),
        StockIn(variant=variants[62], supplier=suppliers[4], quantity=50, purchase_price=400, received_date=date(2025, 3, 1), expiration_date=date(2027, 2, 28), remaining_quantity=50),
        StockIn(variant=variants[63], supplier=suppliers[4], quantity=50, purchase_price=10, received_date=date(2025, 3, 1), expiration_date=date(2027, 2, 28), remaining_quantity=50),
        StockIn(variant=variants[64], supplier=suppliers[4], quantity=50, purchase_price=200, received_date=date(2025, 3, 1), expiration_date=date(2027, 2, 28), remaining_quantity=50),
        StockIn(variant=variants[65], supplier=suppliers[4], quantity=50, purchase_price=400, received_date=date(2025, 3, 1), expiration_date=date(2027, 2, 28), remaining_quantity=50),
        StockIn(variant=variants[66], supplier=suppliers[4], quantity=50, purchase_price=10, received_date=date(2025, 3, 1), expiration_date=date(2027, 2, 28), remaining_quantity=50),
        StockIn(variant=variants[67], supplier=suppliers[9], quantity=50, purchase_price=250, received_date=date(2025, 3, 1), expiration_date=date(2027, 2, 28), remaining_quantity=50),
        StockIn(variant=variants[68], supplier=suppliers[9], quantity=50, purchase_price=10, received_date=date(2025, 3, 1), expiration_date=date(2027, 2, 28), remaining_quantity=50),
        StockIn(variant=variants[69], supplier=suppliers[9], quantity=50, purchase_price=250, received_date=date(2025, 3, 1), expiration_date=date(2027, 2, 28), remaining_quantity=50),
        StockIn(variant=variants[70], supplier=suppliers[9], quantity=50, purchase_price=10, received_date=date(2025, 3, 1), expiration_date=date(2027, 2, 28), remaining_quantity=50),
        StockIn(variant=variants[71], supplier=suppliers[9], quantity=50, purchase_price=250, received_date=date(2025, 3, 1), expiration_date=date(2027, 2, 28), remaining_quantity=50),
        StockIn(variant=variants[72], supplier=suppliers[9], quantity=50, purchase_price=10, received_date=date(2025, 3, 1), expiration_date=date(2027, 2, 28), remaining_quantity=50),
        StockIn(variant=variants[73], supplier=suppliers[10], quantity=50, purchase_price=250, received_date=date(2025, 3, 1), expiration_date=date(2027, 2, 28), remaining_quantity=50),
        StockIn(variant=variants[74], supplier=suppliers[10], quantity=50, purchase_price=500, received_date=date(2025, 3, 1), expiration_date=date(2027, 2, 28), remaining_quantity=50),
        StockIn(variant=variants[75], supplier=suppliers[10], quantity=50, purchase_price=250, received_date=date(2025, 3, 1), expiration_date=date(2027, 2, 28), remaining_quantity=50),
        StockIn(variant=variants[76], supplier=suppliers[10], quantity=50, purchase_price=500, received_date=date(2025, 3, 1), expiration_date=date(2027, 2, 28), remaining_quantity=50),
        StockIn(variant=variants[77], supplier=suppliers[10], quantity=50, purchase_price=250, received_date=date(2025, 3, 1), expiration_date=date(2027, 2, 28), remaining_quantity=50),
        StockIn(variant=variants[78], supplier=suppliers[10], quantity=50, purchase_price=500, received_date=date(2025, 3, 1), expiration_date=date(2027, 2, 28), remaining_quantity=50),
        StockIn(variant=variants[79], supplier=suppliers[10], quantity=50, purchase_price=250, received_date=date(2025, 3, 1), expiration_date=date(2027, 2, 28), remaining_quantity=50),
        StockIn(variant=variants[80], supplier=suppliers[10], quantity=50, purchase_price=500, received_date=date(2025, 3, 1), expiration_date=date(2027, 2, 28), remaining_quantity=50),
        StockIn(variant=variants[81], supplier=suppliers[10], quantity=50, purchase_price=250, received_date=date(2025, 3, 1), expiration_date=date(2027, 2, 28), remaining_quantity=50),
        StockIn(variant=variants[82], supplier=suppliers[10], quantity=50, purchase_price=500, received_date=date(2025, 3, 1), expiration_date=date(2027, 2, 28), remaining_quantity=50),
        StockIn(variant=variants[83], supplier=suppliers[2], quantity=50, purchase_price=400, received_date=date(2025, 3, 1), expiration_date=date(2028, 2, 28), remaining_quantity=50),
        StockIn(variant=variants[84], supplier=suppliers[2], quantity=50, purchase_price=250, received_date=date(2025, 3, 1), expiration_date=date(2028, 2, 28), remaining_quantity=50),
        StockIn(variant=variants[85], supplier=suppliers[2], quantity=50, purchase_price=500, received_date=date(2025, 3, 1), expiration_date=date(2028, 2, 28), remaining_quantity=50),
        StockIn(variant=variants[86], supplier=suppliers[2], quantity=50, purchase_price=750, received_date=date(2025, 3, 1), expiration_date=date(2028, 2, 28), remaining_quantity=50),
        StockIn(variant=variants[87], supplier=suppliers[2], quantity=50, purchase_price=400, received_date=date(2025, 3, 1), expiration_date=date(2028, 2, 28), remaining_quantity=50),
        StockIn(variant=variants[88], supplier=suppliers[2], quantity=50, purchase_price=250, received_date=date(2025, 3, 1), expiration_date=date(2028, 2, 28), remaining_quantity=50),
        StockIn(variant=variants[89], supplier=suppliers[2], quantity=50, purchase_price=500, received_date=date(2025, 3, 1), expiration_date=date(2028, 2, 28), remaining_quantity=50),
        StockIn(variant=variants[90], supplier=suppliers[2], quantity=50, purchase_price=750, received_date=date(2025, 3, 1), expiration_date=date(2028, 2, 28), remaining_quantity=50),
        StockIn(variant=variants[91], supplier=suppliers[2], quantity=50, purchase_price=400, received_date=date(2025, 3, 1), expiration_date=date(2028, 2, 28), remaining_quantity=50),
        StockIn(variant=variants[92], supplier=suppliers[2], quantity=50, purchase_price=250, received_date=date(2025, 3, 1), expiration_date=date(2028, 2, 28), remaining_quantity=50),
        StockIn(variant=variants[93], supplier=suppliers[2], quantity=50, purchase_price=500, received_date=date(2025, 3, 1), expiration_date=date(2028, 2, 28), remaining_quantity=50),
        StockIn(variant=variants[94], supplier=suppliers[2], quantity=50, purchase_price=750, received_date=date(2025, 3, 1), expiration_date=date(2028, 2, 28), remaining_quantity=50),
        StockIn(variant=variants[95], supplier=suppliers[2], quantity=50, purchase_price=400, received_date=date(2025, 3, 1), expiration_date=date(2028, 2, 28), remaining_quantity=50),
        StockIn(variant=variants[96], supplier=suppliers[2], quantity=50, purchase_price=250, received_date=date(2025, 3, 1), expiration_date=date(2028, 2, 28), remaining_quantity=50),
        StockIn(variant=variants[97], supplier=suppliers[2], quantity=50, purchase_price=500, received_date=date(2025, 3, 1), expiration_date=date(2028, 2, 28), remaining_quantity=50),
        StockIn(variant=variants[98], supplier=suppliers[2], quantity=50, purchase_price=750, received_date=date(2025, 3, 1), expiration_date=date(2028, 2, 28), remaining_quantity=50),
        StockIn(variant=variants[99], supplier=suppliers[3], quantity=50, purchase_price=150, received_date=date(2025, 3, 1), remaining_quantity=50),
        StockIn(variant=variants[1], supplier=suppliers[1], quantity=20, purchase_price=100, received_date=date(2025, 4, 1), expiration_date=date(2027, 3, 31), remaining_quantity=20),
        StockIn(variant=variants[2], supplier=suppliers[1], quantity=20, purchase_price=10, received_date=date(2025, 4, 1), expiration_date=date(2027, 3, 31), remaining_quantity=20),
        StockIn(variant=variants[3], supplier=suppliers[1], quantity=20, purchase_price=100, received_date=date(2025, 4, 1), expiration_date=date(2027, 3, 31), remaining_quantity=20),
        StockIn(variant=variants[4], supplier=suppliers[1], quantity=20, purchase_price=10, received_date=date(2025, 4, 1), expiration_date=date(2027, 3, 31), remaining_quantity=20),
        StockIn(variant=variants[5], supplier=suppliers[1], quantity=20, purchase_price=100, received_date=date(2025, 4, 1), expiration_date=date(2027, 3, 31), remaining_quantity=20),
        StockIn(variant=variants[6], supplier=suppliers[1], quantity=20, purchase_price=10, received_date=date(2025, 4, 1), expiration_date=date(2027, 3, 31), remaining_quantity=20),
        StockIn(variant=variants[7], supplier=suppliers[1], quantity=20, purchase_price=100, received_date=date(2025, 4, 1), expiration_date=date(2027, 3, 31), remaining_quantity=20),
        StockIn(variant=variants[8], supplier=suppliers[1], quantity=20, purchase_price=10, received_date=date(2025, 4, 1), expiration_date=date(2027, 3, 31), remaining_quantity=20),
        StockIn(variant=variants[9], supplier=suppliers[1], quantity=20, purchase_price=100, received_date=date(2025, 4, 1), expiration_date=date(2027, 3, 31), remaining_quantity=20),
        StockIn(variant=variants[10], supplier=suppliers[1], quantity=20, purchase_price=10, received_date=date(2025, 4, 1), expiration_date=date(2027, 3, 31), remaining_quantity=20),
        StockIn(variant=variants[11], supplier=suppliers[9], quantity=20, purchase_price=200, received_date=date(2025, 4, 1), expiration_date=date(2027, 3, 31), remaining_quantity=20),
        StockIn(variant=variants[12], supplier=suppliers[9], quantity=20, purchase_price=10, received_date=date(2025, 4, 1), expiration_date=date(2027, 3, 31), remaining_quantity=20),
        StockIn(variant=variants[13], supplier=suppliers[9], quantity=20, purchase_price=200, received_date=date(2025, 4, 1), expiration_date=date(2027, 3, 31), remaining_quantity=20),
        StockIn(variant=variants[14], supplier=suppliers[9], quantity=20, purchase_price=10, received_date=date(2025, 4, 1), expiration_date=date(2027, 3, 31), remaining_quantity=20),
        StockIn(variant=variants[15], supplier=suppliers[9], quantity=20, purchase_price=200, received_date=date(2025, 4, 1), expiration_date=date(2027, 3, 31), remaining_quantity=20),
        StockIn(variant=variants[16], supplier=suppliers[9], quantity=20, purchase_price=10, received_date=date(2025, 4, 1), expiration_date=date(2027, 3, 31), remaining_quantity=20),
        StockIn(variant=variants[17], supplier=suppliers[9], quantity=20, purchase_price=200, received_date=date(2025, 4, 1), expiration_date=date(2027, 3, 31), remaining_quantity=20),
        StockIn(variant=variants[18], supplier=suppliers[9], quantity=20, purchase_price=10, received_date=date(2025, 4, 1), expiration_date=date(2027, 3, 31), remaining_quantity=20),
        StockIn(variant=variants[19], supplier=suppliers[9], quantity=20, purchase_price=200, received_date=date(2025, 4, 1), expiration_date=date(2027, 3, 31), remaining_quantity=20),
        StockIn(variant=variants[20], supplier=suppliers[9], quantity=20, purchase_price=10, received_date=date(2025, 4, 1), expiration_date=date(2027, 3, 31), remaining_quantity=20),
        StockIn(variant=variants[21], supplier=suppliers[6], quantity=20, purchase_price=200, received_date=date(2025, 4, 1), expiration_date=date(2027, 3, 31), remaining_quantity=20),
        StockIn(variant=variants[22], supplier=suppliers[6], quantity=20, purchase_price=10, received_date=date(2025, 4, 1), expiration_date=date(2027, 3, 31), remaining_quantity=20),
        StockIn(variant=variants[23], supplier=suppliers[6], quantity=20, purchase_price=200, received_date=date(2025, 4, 1), expiration_date=date(2027, 3, 31), remaining_quantity=20),
        StockIn(variant=variants[24], supplier=suppliers[6], quantity=20, purchase_price=10, received_date=date(2025, 4, 1), expiration_date=date(2027, 3, 31), remaining_quantity=20),
        StockIn(variant=variants[25], supplier=suppliers[6], quantity=20, purchase_price=200, received_date=date(2025, 4, 1), expiration_date=date(2027, 3, 31), remaining_quantity=20),
        StockIn(variant=variants[26], supplier=suppliers[6], quantity=20, purchase_price=10, received_date=date(2025, 4, 1), expiration_date=date(2027, 3, 31), remaining_quantity=20),
        StockIn(variant=variants[27], supplier=suppliers[6], quantity=20, purchase_price=200, received_date=date(2025, 4, 1), expiration_date=date(2027, 3, 31), remaining_quantity=20),
        StockIn(variant=variants[28], supplier=suppliers[6], quantity=20, purchase_price=10, received_date=date(2025, 4, 1), expiration_date=date(2027, 3, 31), remaining_quantity=20),
        StockIn(variant=variants[29], supplier=suppliers[6], quantity=20, purchase_price=200, received_date=date(2025, 4, 1), expiration_date=date(2027, 3, 31), remaining_quantity=20),
        StockIn(variant=variants[30], supplier=suppliers[6], quantity=20, purchase_price=10, received_date=date(2025, 4, 1), expiration_date=date(2027, 3, 31), remaining_quantity=20),
        StockIn(variant=variants[31], supplier=suppliers[5], quantity=20, purchase_price=100, received_date=date(2025, 4, 1), expiration_date=date(2028, 3, 31), remaining_quantity=20),
        StockIn(variant=variants[32], supplier=suppliers[5], quantity=20, purchase_price=200, received_date=date(2025, 4, 1), expiration_date=date(2028, 3, 31), remaining_quantity=20),
        StockIn(variant=variants[33], supplier=suppliers[5], quantity=20, purchase_price=100, received_date=date(2025, 4, 1), expiration_date=date(2028, 3, 31), remaining_quantity=20),
        StockIn(variant=variants[34], supplier=suppliers[5], quantity=20, purchase_price=200, received_date=date(2025, 4, 1), expiration_date=date(2028, 3, 31), remaining_quantity=20),
        StockIn(variant=variants[35], supplier=suppliers[5], quantity=20, purchase_price=100, received_date=date(2025, 4, 1), expiration_date=date(2028, 3, 31), remaining_quantity=20),
        StockIn(variant=variants[36], supplier=suppliers[5], quantity=20, purchase_price=200, received_date=date(2025, 4, 1), expiration_date=date(2028, 3, 31), remaining_quantity=20),
        StockIn(variant=variants[37], supplier=suppliers[4], quantity=20, purchase_price=200, received_date=date(2025, 4, 1), expiration_date=date(2027, 3, 31), remaining_quantity=20),
        StockIn(variant=variants[38], supplier=suppliers[4], quantity=20, purchase_price=400, received_date=date(2025, 4, 1), expiration_date=date(2027, 3, 31), remaining_quantity=20),
        StockIn(variant=variants[39], supplier=suppliers[4], quantity=20, purchase_price=10, received_date=date(2025, 4, 1), expiration_date=date(2027, 3, 31), remaining_quantity=20),
        StockIn(variant=variants[40], supplier=suppliers[4], quantity=20, purchase_price=200, received_date=date(2025, 4, 1), expiration_date=date(2027, 3, 31), remaining_quantity=20),
        StockIn(variant=variants[41], supplier=suppliers[4], quantity=20, purchase_price=400, received_date=date(2025, 4, 1), expiration_date=date(2027, 3, 31), remaining_quantity=20),
        StockIn(variant=variants[42], supplier=suppliers[4], quantity=20, purchase_price=10, received_date=date(2025, 4, 1), expiration_date=date(2027, 3, 31), remaining_quantity=20),
        StockIn(variant=variants[43], supplier=suppliers[4], quantity=20, purchase_price=200, received_date=date(2025, 4, 1), expiration_date=date(2027, 3, 31), remaining_quantity=20),
        StockIn(variant=variants[44], supplier=suppliers[4], quantity=20, purchase_price=400, received_date=date(2025, 4, 1), expiration_date=date(2027, 3, 31), remaining_quantity=20),
        StockIn(variant=variants[45], supplier=suppliers[4], quantity=20, purchase_price=10, received_date=date(2025, 4, 1), expiration_date=date(2027, 3, 31), remaining_quantity=20),
        StockIn(variant=variants[46], supplier=suppliers[4], quantity=20, purchase_price=200, received_date=date(2025, 4, 1), expiration_date=date(2027, 3, 31), remaining_quantity=20),
        StockIn(variant=variants[47], supplier=suppliers[4], quantity=20, purchase_price=400, received_date=date(2025, 4, 1), expiration_date=date(2027, 3, 31), remaining_quantity=20),
        StockIn(variant=variants[48], supplier=suppliers[4], quantity=20, purchase_price=10, received_date=date(2025, 4, 1), expiration_date=date(2027, 3, 31), remaining_quantity=20),
        StockIn(variant=variants[49], supplier=suppliers[4], quantity=20, purchase_price=200, received_date=date(2025, 4, 1), expiration_date=date(2027, 3, 31), remaining_quantity=20),
        StockIn(variant=variants[50], supplier=suppliers[4], quantity=20, purchase_price=400, received_date=date(2025, 4, 1), expiration_date=date(2027, 3, 31), remaining_quantity=20),
        StockIn(variant=variants[51], supplier=suppliers[4], quantity=20, purchase_price=10, received_date=date(2025, 4, 1), expiration_date=date(2027, 3, 31), remaining_quantity=20),
        StockIn(variant=variants[52], supplier=suppliers[4], quantity=20, purchase_price=200, received_date=date(2025, 4, 1), expiration_date=date(2027, 3, 31), remaining_quantity=20),
        StockIn(variant=variants[53], supplier=suppliers[4], quantity=20, purchase_price=400, received_date=date(2025, 4, 1), expiration_date=date(2027, 3, 31), remaining_quantity=20),
        StockIn(variant=variants[54], supplier=suppliers[4], quantity=20, purchase_price=10, received_date=date(2025, 4, 1), expiration_date=date(2027, 3, 31), remaining_quantity=20),
        StockIn(variant=variants[55], supplier=suppliers[4], quantity=20, purchase_price=200, received_date=date(2025, 4, 1), expiration_date=date(2027, 3, 31), remaining_quantity=20),
        StockIn(variant=variants[56], supplier=suppliers[4], quantity=20, purchase_price=400, received_date=date(2025, 4, 1), expiration_date=date(2027, 3, 31), remaining_quantity=20),
        StockIn(variant=variants[57], supplier=suppliers[4], quantity=20, purchase_price=10, received_date=date(2025, 4, 1), expiration_date=date(2027, 3, 31), remaining_quantity=20),
        StockIn(variant=variants[58], supplier=suppliers[4], quantity=20, purchase_price=200, received_date=date(2025, 4, 1), expiration_date=date(2027, 3, 31), remaining_quantity=20),
        StockIn(variant=variants[59], supplier=suppliers[4], quantity=20, purchase_price=400, received_date=date(2025, 4, 1), expiration_date=date(2027, 3, 31), remaining_quantity=20),
        StockIn(variant=variants[60], supplier=suppliers[4], quantity=20, purchase_price=10, received_date=date(2025, 4, 1), expiration_date=date(2027, 3, 31), remaining_quantity=20),
        StockIn(variant=variants[61], supplier=suppliers[4], quantity=20, purchase_price=200, received_date=date(2025, 4, 1), expiration_date=date(2027, 3, 31), remaining_quantity=20),
        StockIn(variant=variants[62], supplier=suppliers[4], quantity=20, purchase_price=400, received_date=date(2025, 4, 1), expiration_date=date(2027, 3, 31), remaining_quantity=20),
        StockIn(variant=variants[63], supplier=suppliers[4], quantity=20, purchase_price=10, received_date=date(2025, 4, 1), expiration_date=date(2027, 3, 31), remaining_quantity=20),
        StockIn(variant=variants[64], supplier=suppliers[4], quantity=20, purchase_price=200, received_date=date(2025, 4, 1), expiration_date=date(2027, 3, 31), remaining_quantity=20),
        StockIn(variant=variants[65], supplier=suppliers[4], quantity=20, purchase_price=400, received_date=date(2025, 4, 1), expiration_date=date(2027, 3, 31), remaining_quantity=20),
        StockIn(variant=variants[66], supplier=suppliers[4], quantity=20, purchase_price=10, received_date=date(2025, 4, 1), expiration_date=date(2027, 3, 31), remaining_quantity=20),
        StockIn(variant=variants[67], supplier=suppliers[9], quantity=20, purchase_price=250, received_date=date(2025, 4, 1), expiration_date=date(2027, 3, 31), remaining_quantity=20),
        StockIn(variant=variants[68], supplier=suppliers[9], quantity=20, purchase_price=10, received_date=date(2025, 4, 1), expiration_date=date(2027, 3, 31), remaining_quantity=20),
        StockIn(variant=variants[69], supplier=suppliers[9], quantity=20, purchase_price=250, received_date=date(2025, 4, 1), expiration_date=date(2027, 3, 31), remaining_quantity=20),
        StockIn(variant=variants[70], supplier=suppliers[9], quantity=20, purchase_price=10, received_date=date(2025, 4, 1), expiration_date=date(2027, 3, 31), remaining_quantity=20),
        StockIn(variant=variants[71], supplier=suppliers[9], quantity=20, purchase_price=250, received_date=date(2025, 4, 1), expiration_date=date(2027, 3, 31), remaining_quantity=20),
        StockIn(variant=variants[72], supplier=suppliers[9], quantity=20, purchase_price=10, received_date=date(2025, 4, 1), expiration_date=date(2027, 3, 31), remaining_quantity=20),
        StockIn(variant=variants[73], supplier=suppliers[10], quantity=20, purchase_price=250, received_date=date(2025, 4, 1), expiration_date=date(2027, 3, 31), remaining_quantity=20),
        StockIn(variant=variants[74], supplier=suppliers[10], quantity=20, purchase_price=500, received_date=date(2025, 4, 1), expiration_date=date(2027, 3, 31), remaining_quantity=20),
        StockIn(variant=variants[75], supplier=suppliers[10], quantity=20, purchase_price=250, received_date=date(2025, 4, 1), expiration_date=date(2027, 3, 31), remaining_quantity=20),
        StockIn(variant=variants[76], supplier=suppliers[10], quantity=20, purchase_price=500, received_date=date(2025, 4, 1), expiration_date=date(2027, 3, 31), remaining_quantity=20),
        StockIn(variant=variants[77], supplier=suppliers[10], quantity=20, purchase_price=250, received_date=date(2025, 4, 1), expiration_date=date(2027, 3, 31), remaining_quantity=20),
        StockIn(variant=variants[78], supplier=suppliers[10], quantity=20, purchase_price=500, received_date=date(2025, 4, 1), expiration_date=date(2027, 3, 31), remaining_quantity=20),
        StockIn(variant=variants[79], supplier=suppliers[10], quantity=20, purchase_price=250, received_date=date(2025, 4, 1), expiration_date=date(2027, 3, 31), remaining_quantity=20),
        StockIn(variant=variants[80], supplier=suppliers[10], quantity=20, purchase_price=500, received_date=date(2025, 4, 1), expiration_date=date(2027, 3, 31), remaining_quantity=20),
        StockIn(variant=variants[81], supplier=suppliers[10], quantity=20, purchase_price=250, received_date=date(2025, 4, 1), expiration_date=date(2027, 3, 31), remaining_quantity=20),
        StockIn(variant=variants[82], supplier=suppliers[10], quantity=20, purchase_price=500, received_date=date(2025, 4, 1), expiration_date=date(2027, 3, 31), remaining_quantity=20),
        StockIn(variant=variants[83], supplier=suppliers[2], quantity=20, purchase_price=400, received_date=date(2025, 4, 1), expiration_date=date(2028, 3, 31), remaining_quantity=20),
        StockIn(variant=variants[84], supplier=suppliers[2], quantity=20, purchase_price=250, received_date=date(2025, 4, 1), expiration_date=date(2028, 3, 31), remaining_quantity=20),
        StockIn(variant=variants[85], supplier=suppliers[2], quantity=20, purchase_price=500, received_date=date(2025, 4, 1), expiration_date=date(2028, 3, 31), remaining_quantity=20),
        StockIn(variant=variants[86], supplier=suppliers[2], quantity=20, purchase_price=750, received_date=date(2025, 4, 1), expiration_date=date(2028, 3, 31), remaining_quantity=20),
        StockIn(variant=variants[87], supplier=suppliers[2], quantity=20, purchase_price=400, received_date=date(2025, 4, 1), expiration_date=date(2028, 3, 31), remaining_quantity=20),
        StockIn(variant=variants[88], supplier=suppliers[2], quantity=20, purchase_price=250, received_date=date(2025, 4, 1), expiration_date=date(2028, 3, 31), remaining_quantity=20),
        StockIn(variant=variants[89], supplier=suppliers[2], quantity=20, purchase_price=500, received_date=date(2025, 4, 1), expiration_date=date(2028, 3, 31), remaining_quantity=20),
        StockIn(variant=variants[90], supplier=suppliers[2], quantity=20, purchase_price=750, received_date=date(2025, 4, 1), expiration_date=date(2028, 3, 31), remaining_quantity=20),
        StockIn(variant=variants[91], supplier=suppliers[2], quantity=20, purchase_price=400, received_date=date(2025, 4, 1), expiration_date=date(2028, 3, 31), remaining_quantity=20),
        StockIn(variant=variants[92], supplier=suppliers[2], quantity=20, purchase_price=250, received_date=date(2025, 4, 1), expiration_date=date(2028, 3, 31), remaining_quantity=20),
        StockIn(variant=variants[93], supplier=suppliers[2], quantity=20, purchase_price=500, received_date=date(2025, 4, 1), expiration_date=date(2028, 3, 31), remaining_quantity=20),
        StockIn(variant=variants[94], supplier=suppliers[2], quantity=20, purchase_price=750, received_date=date(2025, 4, 1), expiration_date=date(2028, 3, 31), remaining_quantity=20),
        StockIn(variant=variants[95], supplier=suppliers[2], quantity=20, purchase_price=400, received_date=date(2025, 4, 1), expiration_date=date(2028, 3, 31), remaining_quantity=20),
        StockIn(variant=variants[96], supplier=suppliers[2], quantity=20, purchase_price=250, received_date=date(2025, 4, 1), expiration_date=date(2028, 3, 31), remaining_quantity=20),
        StockIn(variant=variants[97], supplier=suppliers[2], quantity=20, purchase_price=500, received_date=date(2025, 4, 1), expiration_date=date(2028, 3, 31), remaining_quantity=20),
        StockIn(variant=variants[98], supplier=suppliers[2], quantity=20, purchase_price=750, received_date=date(2025, 4, 1), expiration_date=date(2028, 3, 31), remaining_quantity=20),
        StockIn(variant=variants[99], supplier=suppliers[3], quantity=20, purchase_price=150, received_date=date(2025, 4, 1), remaining_quantity=20),
    ]

    # 批量插入資料
    StockIn.objects.bulk_create(stock_in_records)
    
    
    ##推薦商品表 (recommended_products)
    # 準備要插入的資料
    recommended = [
        RecommendedProducts(variant_id=7, recommended_for='所有用戶'),
        RecommendedProducts(variant_id=11, recommended_for='所有用戶'),
        RecommendedProducts(variant_id=27, recommended_for='所有用戶'),
        RecommendedProducts(variant_id=58, recommended_for='所有用戶'),
        RecommendedProducts(variant_id=73, recommended_for='所有用戶'),
        RecommendedProducts(variant_id=97, recommended_for='所有用戶'),
        RecommendedProducts(variant_id=3, recommended_for='熱門商品'),
        RecommendedProducts(variant_id=1, recommended_for='熱門商品'),
        RecommendedProducts(variant_id=11, recommended_for='熱門商品'),
        RecommendedProducts(variant_id=49, recommended_for='熱門商品'),
        RecommendedProducts(variant_id=71, recommended_for='熱門商品'),
        RecommendedProducts(variant_id=87, recommended_for='熱門商品'),
    ]
    # 使用 bulk_create 一次性插入
    RecommendedProducts.objects.bulk_create(recommended)


    return HttpResponse("add success")
