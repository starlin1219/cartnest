"""
URL configuration for cartnest project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from django.contrib import admin
from django.urls import path, include
from myapp import views

urlpatterns = [
    path("admin/", admin.site.urls),
    
    path('', views.homepage, name='home'),
    path('search/', views.search, name='search'),
    path('register/', views.register),
    path('login/', views.user_login),
    path('logout/', views.user_logout),     # 登出後會回首頁
    path('users/<int:id>/', views.users),
    path('users/edit/', views.edit),        # 修改會員密碼
    path('coupons/', views.coupons),
    path('orders/', views.orders, name='orders'),
    path('orders/<str:order_number>/cancel/', views.cancel_order, name='cancel_order'),
    path('orders/<str:number>/', views.details),
    path('favorites/', views.favorites),    # 追蹤清單
    path("favorites/delete/<int:favorite_id>/", views.favorite_delete, name="favorite_delete"),     # 刪除追蹤清單

    path("check_username/", views.check_username),
    path("newpassword/", views.reset_password),

    path('get_login_status/', views.get_login_status, name='get_login_status'),

    path("product_list/", views.product_list, name='product_list'),
    path("product_detail/", views.product_detail, name='product_detail'),

    path('toggle_favorite/', views.toggle_favorite, name='toggle_favorite'),
    path('get_favorites/', views.get_favorites, name='get_favorites'),

    path("add_cart/", views.add_cart, name='add_cart'),
    path('get_cart_count/', views.get_cart_count, name='get_cart_count'),
    path("cart/", views.cart, name='cart'),
    path('remove_cart_item/<str:key>/', views.remove_cart_item, name='remove_cart_item'),
    path('update_cart_item/<str:key>/<int:quantity>/', views.update_cart_item, name='update_cart_item'),
    path("apply_coupon/", views.apply_coupon, name='apply_coupon'),
    path('cancel_coupon/', views.cancel_coupon, name='cancel_coupon'),
    path('update_cart_summary/', views.update_cart_summary, name='update_cart_summary'),

    path('save_selected_items/', views.save_selected_items, name='save_selected_items'),
    path("check_order/", views.check_order, name='check_order'),
    path("order_completed/", views.order_completed, name='order_completed'),
    
    # 測試用
    path("add_data/", views.add_data),
]
