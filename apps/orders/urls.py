from django.urls import path
from . import views


urlpatterns = [
    path("", views.ver_carrito, name="carrito"),
    path("agregar/<int:producto_id>/", views.agregar_al_carrito, name="agregar_al_carrito"),
    path("cantidad/<int:producto_id>/", views.cambiar_cantidad, name="cambiar_cantidad"),
    path("quitar/<int:producto_id>/", views.quitar_del_carrito, name="quitar_del_carrito"),
]
