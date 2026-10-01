from django.contrib import admin
from django.urls import path, include

from django.conf import settings
from django.conf.urls.static import static


urlpatterns = [

    path(
        "admin/",
        admin.site.urls
    ),

    # Inicio + catálogo público
    path(
        "",
        include("apps.catalog.urls")
    ),

    ##AÑADIDO EN FASE 2.5 DE CONEXION CARRITO
    path(
    "",
    include("apps.orders.urls")
),

    # Login + registro
    path(
        "cuenta/",
        include("apps.accounts.urls")
    ),
    #FASE ADMINISTRATIVA
    path(
        "gestion/",
        include(("apps.management.urls", "management"),
        namespace="management")
     ),

]


if settings.DEBUG:

    urlpatterns += static(
        settings.MEDIA_URL,
        document_root=settings.MEDIA_ROOT
    )