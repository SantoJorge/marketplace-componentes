"""Formulario para editar exclusivamente los datos de la sesión activa."""

from django import forms
from django.contrib.auth import get_user_model
from django.db import transaction

from apps.accounts.forms import PROVINCIAS_PANAMA

User = get_user_model()


class PerfilAdministradorForm(forms.Form):
    first_name = forms.CharField(label="Nombre", max_length=150)
    last_name = forms.CharField(label="Apellido", max_length=150)
    email = forms.EmailField(label="Correo electrónico", max_length=254)
    phone = forms.CharField(label="Teléfono", max_length=20, required=False)
    province = forms.ChoiceField(
        label="Provincia", required=False, choices=PROVINCIAS_PANAMA
    )

    def __init__(self, *args, user, profile, **kwargs):
        self.user = user
        self.profile = profile
        if not args and "initial" not in kwargs:
            kwargs["initial"] = {
                "first_name": user.first_name,
                "last_name": user.last_name,
                "email": user.email,
                "phone": profile.phone,
                "province": profile.province,
            }
        super().__init__(*args, **kwargs)

        # No perder datos antiguos de cuentas registradas antes de usar Panamá.
        existing = (profile.province or "").strip()
        known = {value for value, _label in PROVINCIAS_PANAMA}
        if existing and existing not in known:
            self.fields["province"].choices = [
                *PROVINCIAS_PANAMA,
                (existing, f"{existing} (registrada anteriormente)"),
            ]

        for field in self.fields.values():
            field.widget.attrs["class"] = "profile-input"

        self.fields["first_name"].widget.attrs["autocomplete"] = "given-name"
        self.fields["last_name"].widget.attrs["autocomplete"] = "family-name"
        self.fields["email"].widget.attrs["autocomplete"] = "email"
        self.fields["phone"].widget.attrs.update(
            {"autocomplete": "tel", "placeholder": "+507 6000-0000"}
        )

    def clean_first_name(self):
        value = self.cleaned_data["first_name"].strip()
        if not value:
            raise forms.ValidationError("Escribe tu nombre.")
        return value

    def clean_last_name(self):
        value = self.cleaned_data["last_name"].strip()
        if not value:
            raise forms.ValidationError("Escribe tu apellido.")
        return value

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if User.objects.filter(email__iexact=email).exclude(pk=self.user.pk).exists():
            raise forms.ValidationError("Este correo ya pertenece a otra cuenta.")
        return email

    @transaction.atomic
    def save(self):
        if not self.is_valid():
            raise ValueError("No puedes guardar un formulario inválido.")
        self.user.first_name = self.cleaned_data["first_name"]
        self.user.last_name = self.cleaned_data["last_name"]
        self.user.email = self.cleaned_data["email"]
        self.user.save(update_fields=["first_name", "last_name", "email"])

        self.profile.phone = self.cleaned_data["phone"].strip()
        self.profile.province = self.cleaned_data["province"]
        self.profile.save(update_fields=["phone", "province"])
        return self.user
