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

from django import forms
from django.contrib.auth import get_user_model
from django.db import transaction
from apps.accounts.models import Profile, SellerProfile, SellerRequest
User = get_user_model()

class StyledForm:
    def style(self):
        for field in self.fields.values():
            field.widget.attrs.setdefault('class', 'mc-input')


#modificado en fase 3.2
class SellerRequestForm(StyledForm, forms.ModelForm):

    class Meta:
        model = SellerRequest
        fields = [
            "business_name",
            "business_description",
            "business_phone",
            "location",
        ]

        labels = {
            "business_name": "Nombre comercial (opcional)",
            "business_description": "Descripción de tu actividad",
            "business_phone": "Teléfono de contacto",
            "location": "Ubicación",
        }

        widgets = {
            "business_description": forms.Textarea(
                attrs={
                    "rows": 4,
                    "placeholder": (
                        "Cuéntanos qué componentes vendes "
                        "y cuál es tu experiencia."
                    ),
                }
            ),
            "business_name": forms.TextInput(
                attrs={
                    "placeholder": "Nombre de tu negocio",
                }
            ),
            "business_phone": forms.TextInput(
                attrs={
                    "placeholder": "+507 6000-0000",
                    "autocomplete": "tel",
                }
            ),
            "location": forms.TextInput(
                attrs={
                    "placeholder": "Ej: David, Chiriquí",
                }
            ),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields["business_name"].required = False
        self.fields["business_description"].required = True
        self.fields["business_phone"].required = True
        self.fields["location"].required = True

        if user is not None and not self.is_bound:
            self.initial.setdefault(
                "business_name",
                user.get_full_name() or user.username,
            )

            try:
                profile = user.profile
            except Profile.DoesNotExist:
                profile = None

            if profile is not None:
                self.initial.setdefault(
                    "business_phone",
                    profile.phone or "",
                )
                self.initial.setdefault(
                    "location",
                    profile.province or "",
                )

        self.style()



class BusinessForm(StyledForm, forms.ModelForm):
    class Meta:
        model = SellerProfile
        fields = ['business_name','business_description','business_phone','location']
        labels = {'business_name':'Nombre del negocio','business_description':'Descripción','business_phone':'Teléfono comercial','location':'Ubicación'}
        widgets={'business_description': forms.Textarea(attrs={'rows':4})}
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs); self.style()


class PersonalForm(StyledForm, forms.Form):
    first_name=forms.CharField(label='Nombre',max_length=150)
    last_name=forms.CharField(label='Apellido',max_length=150)
    email=forms.EmailField(label='Correo',max_length=254)
    phone=forms.CharField(label='Teléfono',max_length=20,required=False)
    province=forms.ChoiceField(label='Provincia', choices=PROVINCIAS_PANAMA,required=False)
    def __init__(self,*args,user,**kwargs):
        self.user=user
        profile,_=Profile.objects.get_or_create(user=user)
        self.profile=profile
        if not args and 'initial' not in kwargs:
            kwargs['initial']={'first_name':user.first_name,'last_name':user.last_name,'email':user.email,'phone':profile.phone,'province':profile.province}
        super().__init__(*args,**kwargs)
        prev=profile.province
        if prev and prev not in dict(PROVINCIAS_PANAMA): self.fields['province'].choices=[*PROVINCIAS_PANAMA,(prev,prev)]
        self.style()
    def clean_email(self):
        email=self.cleaned_data['email'].strip().lower()
        if User.objects.filter(email__iexact=email).exclude(pk=self.user.pk).exists():
            raise forms.ValidationError('Este correo ya está registrado.')
        return email
    @transaction.atomic
    def save(self):
        u=self.user
        u.first_name=self.cleaned_data['first_name'].strip()
        u.last_name=self.cleaned_data['last_name'].strip()
        u.email=self.cleaned_data['email']
        u.save(update_fields=['first_name','last_name','email'])
        self.profile.phone=self.cleaned_data['phone'].strip()
        self.profile.province=self.cleaned_data['province']
        self.profile.save(update_fields=['phone','province'])
