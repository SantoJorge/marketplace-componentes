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

from . import payment_views
urlpatterns += [
    path('pedidos/<int:pk>/comprobante/', payment_views.subir_comprobante, name='subir_comprobante'),
    path('pedidos/<int:pk>/comprobante/<int:receipt_id>/revisar/', payment_views.revisar_comprobante, name='revisar_comprobante'),
    path('pedidos/<int:pk>/comprobante/<int:receipt_id>/descargar/', payment_views.descargar_comprobante, name='descargar_comprobante'),
]
urlpatterns += [path("pedidos/<int:pk>/estado/", views.buyer_order_status, name="pedido_estado")]



# ============================================================
# CR-11 - OFERTAS Y CONTRAOFERTAS
# ============================================================

urlpatterns += [
    path(
        "ofertas/enviadas/",
        views.offers_sent,
        name="ofertas_enviadas",
    ),
    path(
        "ofertas/recibidas/",
        views.offers_received,
        name="ofertas_recibidas",
    ),
    path(
        "ofertas/producto/<int:product_id>/crear/",
        views.offer_create,
        name="crear_oferta",
    ),
    path(
        "ofertas/<int:offer_id>/vendedor/responder/",
        views.offer_seller_reply,
        name="responder_oferta_vendedor",
    ),
    path(
        "ofertas/<int:offer_id>/comprador/responder/",
        views.offer_buyer_reply,
        name="responder_oferta_comprador",
    ),
]



# ============================================================
# CR-14 - RUTAS DE NOTIFICACIONES
# ============================================================

urlpatterns += [
    path(
        "notificaciones/",
        views.notifications_list,
        name="mis_notificaciones",
    ),
    path(
        "notificaciones/<int:pk>/leida/",
        views.notification_mark_read,
        name="notificacion_marcar_leida",
    ),
    path(
        "notificaciones/marcar-todas/",
        views.notification_mark_all_read,
        name="notificaciones_marcar_todas",
    ),
]
