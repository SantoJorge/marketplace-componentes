from django.urls import path
from . import views
app_name = "catalog"
urlpatterns = [
    path("", views.inicio, name="inicio"),
    path("catalogo/", views.catalogo, name="catalogo"),
    path("tienda/", views.shop, name="tienda"),
    path("tienda/producto/<int:pk>/", views.product_detail, name="producto"),
    path("vendedor/", views.seller_dashboard, name="vendedor_dashboard"),
    path("vendedor/productos/", views.seller_products, name="vendedor_productos"),
    path("vendedor/productos/nuevo/", views.seller_product_edit, name="vendedor_producto_nuevo"),
    path("vendedor/productos/<int:pk>/", views.seller_product_edit, name="vendedor_producto_editar"),
]
