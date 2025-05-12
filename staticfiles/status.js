
function checkLoginStatus() {
    $.ajax({
        url: GET_LOGIN_STATUS_URL,
        type: "GET",
        success: function (response) {
            const isLoggedIn = response.login_status;
            const userId = response.user_id;
            if ((isLoggedIn && $('.dropdown-toggle').length === 0) || (!isLoggedIn && $('.dropdown-toggle').length > 0)) {
                location.reload();
            }
        }
    });
}


function fetchCartCount() {
    $.ajax({
        url: GET_CART_COUNT_URL,
        type: "GET",
        success: function (response) {
            const count = response.cart_count || 0;
            const cartCount = $("#cart-count");
            if (count > 0) {
                cartCount.text(count).show();
            } else {
                cartCount.text('0').hide();
            }
        }
    });
}


function refreshFavoriteIcons() {
    $.ajax({
        url: GET_FAVORITES_URL,
        type: "GET",
        success: function (response) {
            if (!Array.isArray(response.favorite_variant_ids)) return;

            $('.favorite-icon').each(function () {
                const icon = $(this);
                const variantId = parseInt(icon.data('variant-id'));

                if (response.favorite_variant_ids.includes(variantId)) {
                    icon.removeClass('bi-heart').addClass('bi-heart-fill');
                } else {
                    icon.removeClass('bi-heart-fill').addClass('bi-heart');
                }
            });
        }
    });
}


