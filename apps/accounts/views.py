
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth import (
    authenticate,
    get_user_model,
    login,
    logout,
    update_session_auth_hash,
)
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordChangeForm
from django.db import transaction
from django.db.models import F, Q, Sum
from django.http import HttpResponseBadRequest, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.accounts.permissions import allowed, role, screen
from apps.catalog.models import Category, Product
from apps.orders.models import Cart, CartItem, PurchaseLine, PurchaseOrder
from .forms import BusinessForm, PersonalForm, RegisterForm, SellerRequestForm
from .models import Profile, SellerProfile, SellerRequest

User = get_user_model()


# ==========================================================
# REGISTRO
# ==========================================================
def register_view(request):
    if request.user.is_authenticated:
        return redirect_by_role(request.user)

    if request.method == "POST":
        form = RegisterForm(request.POST)

        if form.is_valid():
            user = form.save(commit=False)
            user.first_name = form.cleaned_data["first_name"]
            user.last_name = form.cleaned_data["last_name"]
            user.email = form.cleaned_data["email"]
            user.save()

            Profile.objects.create(
                user=user,
                role="COMPRADOR",
                phone=form.cleaned_data["phone"],
                province=form.cleaned_data["province"],
            )

            login(request, user)
            return redirect_by_role(user)
    else:
        form = RegisterForm()

    return render(request, "accounts/registro.html", {"form": form})


# ==========================================================
# INICIO DE SESION
# ==========================================================
def login_view(request):
    if request.user.is_authenticated:
        return redirect_by_role(request.user)

    error = None

    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        password = request.POST.get("password", "")
        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)
            return redirect_by_role(user)

        error = "Usuario o contraseña incorrectos."

    return render(request, "accounts/login.html", {"error": error})


# ==========================================================
# CERRAR SESION
# ==========================================================
@require_POST
def logout_view(request):
    logout(request)
    return redirect("catalog:inicio")


# ==========================================================
# REDIRECCION SEGUN ROL
# ==========================================================
def redirect_by_role(user):
    if user.is_superuser:
        return redirect("management:dashboard")

    try:
        user_role = user.profile.role
    except Profile.DoesNotExist:
        user_role = "COMPRADOR"

    if user_role == "ADMINISTRADOR":
        return redirect("management:dashboard")

    if user_role == "VENDEDOR":
        return redirect("catalog:vendedor_dashboard")

    return redirect("catalog:inicio")


# ==========================================================
# PANEL DEL VENDEDOR EXISTENTE
# ==========================================================
@login_required
def vendedor_dashboard(request):
    if request.user.is_superuser:
        return redirect("management:dashboard")

    try:
        user_role = request.user.profile.role
    except Profile.DoesNotExist:
        return redirect("catalog:inicio")

    if user_role != "VENDEDOR":
        return redirect_by_role(request.user)

    return redirect("catalog:vendedor_dashboard")


# ==========================================================
# FASE 3.1 - MI PERFIL
# ==========================================================
@allowed("COMPRADOR", "VENDEDOR", "ADMINISTRADOR")
def personal_profile(request):
    current_role = role(request.user)

    if current_role == "ADMINISTRADOR":
        return redirect("management:perfil")

    action = request.POST.get("action", "")

    # GET: cargar los valores del usuario y del perfil.
    # POST personal: validar lo escrito por el usuario.
    if request.method == "POST" and action == "personal":
        form = PersonalForm(
            request.POST,
            user=request.user,
        )
    else:
        form = PersonalForm(
            user=request.user,
        )

    # Se mantiene la funcionalidad existente de cambio de contrasena.
    pwd = PasswordChangeForm(
        request.user,
        request.POST if request.method == "POST" and action == "password" else None,
    )

    for field in pwd.fields.values():
        field.widget.attrs["class"] = "mc-input"

    if request.method == "POST":
        if action == "personal" and form.is_valid():
            form.save()
            messages.success(request, "Datos personales actualizados.")
            return redirect("accounts:perfil")

        if action == "password" and pwd.is_valid():
            user = pwd.save()
            update_session_auth_hash(request, user)
            messages.success(request, "Contraseña actualizada.")
            return redirect("accounts:perfil")

    seller_request = None
    if current_role == "COMPRADOR":
        seller_request = SellerRequest.objects.filter(
            user=request.user,
        ).first()

    return screen(
        request,
        "accounts/perfil.html",
        form=form,
        pwd=pwd,
        seller_request=seller_request,
    )


# ==========================================================
# FASE 3.1 - QUIERO VENDER (MODAL, SIN SIDEBAR)
# ==========================================================
@allowed("COMPRADOR")
def request_seller(request):
    existing = SellerRequest.objects.filter(
        user=request.user,
    ).first()

    if existing and existing.status in ("PENDIENTE", "APROBADA"):
        return screen(
            request,
            "accounts/solicitar_vendedor.html",
            existing=existing,
            panel_mode=False,
        )

    form = SellerRequestForm(
        request.POST or None,
        instance=existing,
        user=request.user,
    )

    if request.method == "POST" and form.is_valid():
        obj = form.save(commit=False)
        obj.user = request.user
        obj.status = "PENDIENTE"
        obj.review_note = ""
        obj.reviewed_at = None
        obj.save()

        messages.success(request, "Solicitud enviada a administración.")
        return redirect("accounts:ser_vendedor")

    return screen(
        request,
        "accounts/solicitar_vendedor.html",
        form=form,
        existing=existing,
        panel_mode=False,
    )


# ==========================================================
# NEGOCIO DEL VENDEDOR EXISTENTE
# ==========================================================
@allowed("VENDEDOR")
def seller_business(request):
    business, _ = SellerProfile.objects.get_or_create(
        user=request.user,
        defaults={
            "business_name": request.user.get_full_name() or request.user.username,
        },
    )

    form = BusinessForm(
        request.POST or None,
        instance=business,
    )

    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Información comercial actualizada.")
        return redirect("accounts:negocio")

    return screen(
        request,
        "includes/formulario.html",
        form=form,
        title="Mi negocio",
        hint="Estos datos aparecen asociados a tu cuenta de vendedor.",
        back="catalog:vendedor_dashboard",
    )
