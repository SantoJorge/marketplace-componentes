from django.urls import path
from . import views
app_name = "orders"
urlpatterns = [
    path("carrito/", views.cart_view, name="cart_detail"),
    path("carrito/contador/", views.cart_count, name="cart_count"),
    path("carrito/agregar/<int:product_id>/", views.add_to_cart, name="add_to_cart"),
    path("carrito/aumentar/<int:item_id>/", views.increase_quantity, name="increase_quantity"),
    path("carrito/disminuir/<int:item_id>/", views.decrease_quantity, name="decrease_quantity"),
    path("carrito/eliminar/<int:item_id>/", views.remove_from_cart, name="remove_from_cart"),
    path("carrito/agregar-producto/<int:pk>/", views.cart_add, name="cart_add"),
    path("carrito/item/<int:pk>/", views.cart_change, name="cart_change"),
    path("carrito/vaciar/", views.cart_clear, name="cart_clear"),
    path("checkout/", views.checkout, name="checkout"),
    path("pedidos/", views.my_orders, name="mis_pedidos"),
    path("pedidos/<int:pk>/", views.order_detail, name="pedido_detalle"),
    path("pedidos/<int:pk>/cancelar/", views.cancel_order, name="cancelar_pedido"),
    path("vendedor/ventas/", views.seller_sales, name="vendedor_ventas"),
    path("vendedor/ventas/<int:pk>/estado/", views.seller_sale_status, name="vendedor_venta_estado"),
]
