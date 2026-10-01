from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect


@login_required
def dashboard_view(request):

    # Seguridad extra:
    # solo superusuarios o administradores pueden entrar.
    is_admin = request.user.is_superuser

    if not is_admin:
        try:
            is_admin = request.user.profile.role == "ADMINISTRADOR"
        except Exception:
            is_admin = False

    if not is_admin:
        return redirect("catalog:inicio")

    context = {
        "admin_name": request.user.first_name or request.user.username,
        "admin_full_name": (
            request.user.get_full_name()
            or request.user.username
        ),
        "admin_username": request.user.username,
    }

    return render(
        request,
        "management/dashboard.html",
        context
    )