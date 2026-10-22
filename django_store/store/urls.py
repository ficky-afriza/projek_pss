from django.urls import path

from . import views


urlpatterns = [
    path("", views.home, name="home"),
    path("produk/<int:product_id>/", views.product_detail, name="product_detail"),
    path("register/", views.register, name="register"),
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),
    path("profile/", views.order_history, name="profile"),
    path("keranjang/", views.cart_view, name="cart"),
    path("keranjang/tambah/<int:product_id>/", views.cart_add, name="cart_add"),
    path("keranjang/perbarui/", views.cart_update, name="cart_update"),
    path("keranjang/hapus/<int:product_id>/", views.cart_remove, name="cart_remove"),
    path("keranjang/kosongkan/", views.cart_clear, name="cart_clear"),
    path("checkout/", views.checkout, name="checkout"),
    path("account/", views.account, name="account"),
    path("kelola-pesanan/", views.admin_orders, name="admin_orders"),
    path(
        "kelola-pesanan/<int:order_id>/<int:status>/",
        views.update_order_payment,
        name="update_order_payment",
    ),
    path("pesanan/", views.order_history, name="order_history"),
    path("pesanan/<int:order_id>/bukti/", views.upload_payment_proof, name="upload_payment_proof"),
    path("kontak/", views.contact, name="contact"),
    path("get-location", views.shipping_locations, name="shipping_locations"),
    path("get-cost", views.shipping_cost, name="shipping_cost"),
    path("api", views.api_transactions, name="api_transactions"),
    path("api/transaksi", views.orders_api, name="orders_api"),
    path("api/produk/", views.products_api, name="products_api"),
]
