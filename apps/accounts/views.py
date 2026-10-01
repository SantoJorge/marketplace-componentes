from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required

from .forms import RegisterForm
from .models import Profile


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

    return render(
        request,
        "accounts/registro.html",
        {
            "form": form
        }
    )


# ==========================================================
# INICIO DE SESIÓN
# ==========================================================

def login_view(request):

    # Si ya inició sesión, enviarlo según su rol
    if request.user.is_authenticated:
        return redirect_by_role(request.user)

    error = None

    if request.method == "POST":

        username = request.POST.get("username", "").strip()
        password = request.POST.get("password", "")

        user = authenticate(
            request,
            username=username,
            password=password
        )

        if user is not None:

            login(request, user)

            # IMPORTANTE:
            # Después del login siempre entra según su rol.
            return redirect_by_role(user)

        error = "Usuario o contraseña incorrectos."

    return render(
        request,
        "accounts/login.html",
        {
            "error": error
        }
    )


# ==========================================================
# CERRAR SESIÓN
# ==========================================================

def logout_view(request):

    logout(request)

    return redirect("catalog:inicio")


# ==========================================================
# REDIRECCIÓN SEGÚN ROL
# ==========================================================

def redirect_by_role(user):

    # ==========================
    # SUPERUSUARIO
    # ==========================
    if user.is_superuser:
        return redirect("management:dashboard")

    try:
        role = user.profile.role

    except Profile.DoesNotExist:
        role = "COMPRADOR"

    # ==========================
    # ADMINISTRADOR
    # ==========================
    if role == "ADMINISTRADOR":
        return redirect("management:dashboard")

    # ==========================
    # VENDEDOR
    # ==========================
    if role == "VENDEDOR":
        return redirect("accounts:vendedor_dashboard")

    # ==========================
    # COMPRADOR
    # ==========================
    return redirect("catalog:inicio")


# ==========================================================
# V1.1 - PANEL DEL VENDEDOR
# ==========================================================

@login_required
def vendedor_dashboard(request):

    # Un superusuario pertenece al panel administrativo
    if request.user.is_superuser:
        return redirect("management:dashboard")

    # Comprobar que el usuario tenga perfil
    try:
        role = request.user.profile.role

    except Profile.DoesNotExist:
        return redirect("catalog:inicio")

    # Bloquear acceso si no es vendedor
    if role != "VENDEDOR":
        return redirect_by_role(request.user)

    # Vendedor autorizado
    return render(
        request,
        "accounts/vendedor_dashboard.html"
    )