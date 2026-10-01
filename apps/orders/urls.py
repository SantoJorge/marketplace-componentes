from django.urls import path

from . import views


app_name = "orders"


urlpatterns = [

    path(
        "carrito/",
        views.cart_detail,
        name="cart_detail"
    ),

    path(
        "carrito/agregar/<int:product_id>/",
        views.add_to_cart,
        name="add_to_cart"
    ),

    path(
        "carrito/aumentar/<int:item_id>/",
        views.increase_quantity,
        name="increase_quantity"
    ),

    path(
        "carrito/disminuir/<int:item_id>/",
        views.decrease_quantity,
        name="decrease_quantity"
    ),

    path(
        "carrito/eliminar/<int:item_id>/",
        views.remove_from_cart,
        name="remove_from_cart"
    ),

]