
from .models import Categories, Favorite, Users

def cart_count(request):
    cart = request.session.get('cart', {})
    total_count = sum(item['quantity'] for item in cart.values()) if isinstance(cart, dict) else 0
    return {'cart_count': total_count}

def category_list(request):
    categories = Categories.objects.all().order_by('category_id')
    return {'categories': categories}

def login_context(request):
    user_id = request.session.get("user_id")
    login_status = Users.objects.filter(user_id=user_id)
    if not login_status:
        if "user_id" in request.session:
            del request.session["username"]
            del request.session["user_id"]
    return {
        'login_status': login_status,
        'user_id': request.session.get("user_id", None)
    }

def favorite_variants(request):
    user_id = request.session.get("user_id")
    if not user_id:
        return {'favorite_variants': []}
    
    try:
        user = Users.objects.get(user_id=user_id)
        favorites = Favorite.objects.filter(user=user).values_list('variant_id', flat=True)
        return {'favorite_variants': list(map(str, favorites))}
    except Users.DoesNotExist:
        return {'favorite_variants': []}
