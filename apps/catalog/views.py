from django.shortcuts import render

from .models import Product, Category


# ============================================================
# INICIO PÚBLICO
# ============================================================

def inicio(request):

    productos_destacados = (
        Product.objects
        .filter(
            approval_status="APROBADO",
            active=True,
            stock__gt=0
        )
        .select_related(
            "seller",
            "category"
        )
        .order_by("-created_at")[:4]
    )

    categorias = (
        Category.objects
        .filter(active=True)
        .order_by("name")
    )

    context = {
        "productos_destacados": productos_destacados,
        "categorias": categorias,
    }

    return render(
        request,
        "public/inicio.html",
        context
    )


# ============================================================
# CATÁLOGO PÚBLICO
# ============================================================

def catalogo(request):

    productos = (
        Product.objects
        .filter(
            approval_status="APROBADO",
            active=True,
            stock__gt=0
        )
        .select_related(
            "seller",
            "category"
        )
        .order_by("-created_at")
    )

    categorias = (
        Category.objects
        .filter(active=True)
        .order_by("name")
    )

    context = {
        "productos": productos,
        "categorias": categorias,
    }

    return render(
        request,
        "public/catalogo.html",
        context
    )