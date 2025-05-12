from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
from datetime import timedelta

from .models import Orders, Users, MembershipLevels

@receiver(post_save, sender=Orders)
def upgrade_membership(sender, instance, **kwargs):
    if instance.order_status != '已完成':
        return

    user = instance.user
    one_year_ago = timezone.now() - timedelta(days=365)

    # 取得一年內所有已完成的訂單金額
    completed_orders = Orders.objects.filter(
        user=user,
        order_status='已完成',
        created_at__gte=one_year_ago
    )
    total_spent = sum(order.final_price for order in completed_orders)

    # 取得最適合的會員等級（總金額 >= min_spent，依 min_spent 遞減排序）
    new_level = MembershipLevels.objects.filter(
        min_spent__lte=total_spent
    ).order_by('-min_spent').first()

    if new_level and user.level != new_level:
        user.level = new_level
        user.save()
