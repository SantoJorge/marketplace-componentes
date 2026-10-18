
from django.urls import path
from . import views
from .perfil_views import perfil_admin_view

app_name = "management"

urlpatterns = [
    path("", views.admin_dashboard, name="dashboard"),
    path("perfil/", perfil_admin_view, name="perfil"),

    path("usuarios/", views.admin_users, name="usuarios"),
    path(
        "usuarios/<int:pk>/estado/",
        views.admin_user_toggle,
        name="usuario_estado",
    ),

    path("solicitudes/", views.admin_requests, name="solicitudes"),
    path(
        "solicitudes/<int:pk>/resolver/",
        views.admin_request_action,
        name="solicitud_resolver",
    ),

    path("productos/", views.admin_products, name="productos"),
    path(
        "productos/<int:pk>/resolver/",
        views.admin_product_action,
        name="producto_resolver",
    ),

    path(
        "productos/<int:pk>/eliminar/",
        views.admin_product_delete,
        name="producto_eliminar",

    ),


    path("categorias/", views.admin_categories, name="categorias"),
    path(
        "categorias/nueva/",
        views.admin_category_edit,
        name="categoria_nueva",
    ),
    path(
        "categorias/<int:pk>/",
        views.admin_category_edit,
        name="categoria_editar",
    ),


    path(
        "categorias/<int:pk>/estado/",
        views.admin_category_toggle,
    name="categoria_estado",
),


    path("pedidos/", views.admin_orders, name="pedidos"),
    path(
        "pedidos/<int:pk>/estado/",
        views.admin_pedido_estado,
        name="pedido_estado",
    ),
]
