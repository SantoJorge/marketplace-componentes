from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm


PROVINCIAS_PANAMA = [
    ("", "Seleccionar..."),
    ("Bocas del Toro", "Bocas del Toro"),
    ("Coclé", "Coclé"),
    ("Colón", "Colón"),
    ("Chiriquí", "Chiriquí"),
    ("Darién", "Darién"),
    ("Herrera", "Herrera"),
    ("Los Santos", "Los Santos"),
    ("Panamá", "Panamá"),
    ("Panamá Oeste", "Panamá Oeste"),
    ("Veraguas", "Veraguas"),
]


class RegisterForm(UserCreationForm):

    first_name = forms.CharField(
        label="Nombre",
        max_length=150,
        widget=forms.TextInput(
            attrs={
                "class": "input",
                "placeholder": "Juan",
                "autocomplete": "given-name",
            }
        )
    )

    last_name = forms.CharField(
        label="Apellido",
        max_length=150,
        widget=forms.TextInput(
            attrs={
                "class": "input",
                "placeholder": "Pérez",
                "autocomplete": "family-name",
            }
        )
    )

    username = forms.CharField(
        label="Nombre de usuario",
        max_length=150,
        widget=forms.TextInput(
            attrs={
                "class": "input",
                "placeholder": "juanperez",
                "autocomplete": "username",
            }
        )
    )

    email = forms.EmailField(
        label="Correo electrónico",
        widget=forms.EmailInput(
            attrs={
                "class": "input",
                "placeholder": "juan@correo.com",
                "autocomplete": "email",
            }
        )
    )

    phone = forms.CharField(
        label="Teléfono",
        max_length=20,
        required=False,
        widget=forms.TextInput(
            attrs={
                "class": "input",
                "placeholder": "+507 6000-0000",
                "autocomplete": "tel",
            }
        )
    )

    province = forms.ChoiceField(
        label="Provincia",
        required=False,
        choices=PROVINCIAS_PANAMA,
        widget=forms.Select(
            attrs={
                "class": "input"
            }
        )
    )

    password1 = forms.CharField(
        label="Contraseña",
        widget=forms.PasswordInput(
            attrs={
                "class": "input",
                "placeholder": "Mínimo 8 caracteres",
                "id": "reg-pass",
                "autocomplete": "new-password",
            }
        )
    )

    password2 = forms.CharField(
        label="Confirmar contraseña",
        widget=forms.PasswordInput(
            attrs={
                "class": "input",
                "placeholder": "Repite la contraseña",
                "id": "reg-pass2",
                "autocomplete": "new-password",
            }
        )
    )

    class Meta:

        model = User

        fields = [
            "first_name",
            "last_name",
            "username",
            "email",
            "phone",
            "province",
            "password1",
            "password2",
        ]

    def clean_email(self):

        email = self.cleaned_data.get("email", "").strip().lower()

        if User.objects.filter(email__iexact=email).exists():

            raise forms.ValidationError(
                "Ya existe una cuenta con este correo electrónico."
            )

        return email