from django.urls import path
from . import views


app_name = "catalog"


urlpatterns = [

    # Página pública principal
    path(
        "",
        views.inicio,
        name="inicio"
    ),

    # Catálogo público
    path(
        "catalogo/",
        views.catalogo,
        name="catalogo"
    ),

]