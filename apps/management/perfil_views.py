"""Perfil del administrador: identidad vinculada a request.user."""

from django.contrib import messages
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordChangeForm
from django.db import transaction
from django.http import HttpResponseBadRequest, HttpResponseForbidden
from django.shortcuts import redirect, render
from django.views.decorators.cache import never_cache

from apps.accounts.models import Profile
from .perfil_forms import PerfilAdministradorForm


def _administrador_autorizado(user):
    if not user.is_authenticated or not user.is_active:
        return False
    if user.is_superuser:
        return True
    try:
        return user.profile.role == "ADMINISTRADOR" and user.profile.active
    except Profile.DoesNotExist:
        return False


@login_required(login_url="accounts:login")
@never_cache
def perfil_admin_view(request):
    if not _administrador_autorizado(request.user):
        return HttpResponseForbidden("Solo los administradores pueden acceder.")

    # Un superusuario creado mediante createsuperuser puede no tener Profile.
    if request.user.is_superuser:
        profile, _created = Profile.objects.get_or_create(
            user=request.user, defaults={"role": "ADMINISTRADOR"}
        )
    else:
        profile = request.user.profile

    perfil_form = PerfilAdministradorForm(user=request.user, profile=profile)
    password_form = PasswordChangeForm(user=request.user, prefix="seguridad")

    if request.method == "POST":
        action = request.POST.get("action")

        if action == "guardar_perfil":
            perfil_form = PerfilAdministradorForm(
                request.POST, user=request.user, profile=profile
            )
            if perfil_form.is_valid():
                perfil_form.save()
                messages.success(request, "Tu información se actualizó correctamente.")
                return redirect("management:perfil")
            messages.error(request, "Revisa los datos marcados en el formulario.")

        elif action == "cambiar_password":
            password_form = PasswordChangeForm(
                user=request.user, data=request.POST, prefix="seguridad"
            )
            for field in password_form.fields.values():
                field.widget.attrs["class"] = "profile-input"
            if password_form.is_valid():
                with transaction.atomic():
                    user = password_form.save()
                    update_session_auth_hash(request, user)
                messages.success(request, "Tu contraseña se cambió correctamente.")
                return redirect("management:perfil")
            messages.error(request, "No se pudo cambiar la contraseña. Revisa los campos.")
        else:
            return HttpResponseBadRequest("Operación no reconocida.")

    for field in password_form.fields.values():
        field.widget.attrs.update({"class": "profile-input", "autocomplete": "off"})

    nombre_completo = request.user.get_full_name().strip() or request.user.username
    iniciales = "".join(
        item[:1].upper()
        for item in (request.user.first_name, request.user.last_name)
        if item.strip()
    ) or request.user.username[:2].upper()

    return render(
        request,
        "management/perfil.html",
        {
            "perfil_form": perfil_form,
            "password_form": password_form,
            "profile": profile,
            "admin_nombre": nombre_completo,
            "admin_iniciales": iniciales,
            "cuenta_activa": request.user.is_active and profile.active,
        },
    )
