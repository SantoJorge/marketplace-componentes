
"""Autorización transversal del Marketplace Componentes."""

from functools import wraps

from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.shortcuts import render

from apps.accounts.models import Profile


def role(user):
    if not user.is_authenticated:
        return "PUBLICO"

    if not user.is_active:
        return "BLOQUEADO"

    if user.is_superuser:
        return "ADMINISTRADOR"

    try:
        profile = user.profile
        return profile.role if profile.active else "BLOQUEADO"
    except Profile.DoesNotExist:
        return "COMPRADOR"


def allowed(*roles):
    def decorate(view):
        @wraps(view)
        @login_required(login_url="accounts:login")
        def wrapper(request, *args, **kwargs):
            if role(request.user) not in roles:
                return HttpResponseForbidden(
                    "No tienes permiso para acceder a esta sección."
                )
            return view(request, *args, **kwargs)
        return wrapper
    return decorate


def screen(request, template, **context):
    current_role = role(request.user)

    context.setdefault("current_role", current_role)

    if current_role == "COMPRADOR":

        buyer_panel_views = {
            "accounts:perfil",
            ##"accounts:ser_vendedor", ELIMINADO FASE 3.1
            "orders:mis_pedidos",
            "orders:pedido_detalle",
        }

        match = request.resolver_match
        show_buyer_panel = bool(
            match and match.view_name in buyer_panel_views
        )

        context.setdefault("panel_mode", show_buyer_panel)

        if context["panel_mode"]:
            from apps.orders.models import PurchaseOrder

            context.setdefault(
                "buyer_orders_count",
                PurchaseOrder.objects.filter(
                    buyer=request.user
                ).count()
            )

    else:
        context.setdefault("panel_mode", True)

    if current_role == "ADMINISTRADOR":
        from apps.catalog.models import Product
        from apps.accounts.models import SellerRequest

        context.setdefault(
            "pending_products",
            Product.objects.filter(
                approval_status="PENDIENTE"
            ).count()
        )

        context.setdefault(
            "pending_requests",
            SellerRequest.objects.filter(
                status="PENDIENTE"
            ).count()
        )

    return render(request, template, context)
