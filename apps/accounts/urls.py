from django.urls import path
from . import views
app_name = "accounts"
urlpatterns = [
    path("login/", views.login_view, name="login"),
    path("registro/", views.register_view, name="registro"),
    path("logout/", views.logout_view, name="logout"),
    path("perfil/", views.personal_profile, name="perfil"),
    path("ser-vendedor/", views.request_seller, name="ser_vendedor"),
    path("negocio/", views.seller_business, name="negocio"),
    path("vendedor/", views.vendedor_dashboard, name="vendedor_dashboard"),
]
