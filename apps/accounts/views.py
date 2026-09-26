from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout

from .forms import RegisterForm
from .models import Profile


def register_view(request):

    if request.user.is_authenticated:
        return redirect("catalog:inicio")

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

            return redirect("catalog:inicio")

    else:

        form = RegisterForm()

    return render(
        request,
        "accounts/registro.html",
        {
            "form": form
        }
    )


def login_view(request):

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

            next_url = request.GET.get("next")

            if next_url:
                return redirect(next_url)

            return redirect_by_role(user)

        error = "Usuario o contraseña incorrectos."

    return render(
        request,
        "accounts/login.html",
        {
            "error": error
        }
    )


def logout_view(request):

    logout(request)

    return redirect("catalog:inicio")


def redirect_by_role(user):

    if user.is_superuser:
        return redirect("management:dashboard")

    try:
        role = user.profile.role
    except Profile.DoesNotExist:
        role = "COMPRADOR"

    if role == "ADMINISTRADOR":
        return redirect("management:dashboard")

    if role == "VENDEDOR":
        return redirect("catalog:inicio")

    return redirect("catalog:inicio")