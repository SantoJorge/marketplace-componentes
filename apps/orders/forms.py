
from django import forms
from apps.accounts.forms import PROVINCIAS_PANAMA, StyledForm


class CheckoutForm(StyledForm, forms.Form):

    # ========================================================
    # DATOS DEL COMPRADOR
    # ========================================================

    contact_name = forms.CharField(
        label="Nombre de quien recibe",
        max_length=150,
    )

    contact_phone = forms.CharField(
        label="Teléfono de contacto",
        max_length=20,
    )

    province = forms.ChoiceField(
        label="Provincia",
        choices=PROVINCIAS_PANAMA,
    )

    address = forms.CharField(
        label="Dirección o punto de entrega/retiro",
        widget=forms.Textarea(
            attrs={"rows": 3}
        ),
    )

    comments = forms.CharField(
        label="Comentarios",
        required=False,
        widget=forms.Textarea(
            attrs={"rows": 2}
        ),
    )

    # ========================================================
    # CR-13: ENTREGA O RETIRO
    # ========================================================

    delivery_method = forms.ChoiceField(
        label="Modalidad de entrega",
        choices=[
            ("ENTREGA_ACORDADA", "Entrega acordada"),
            ("RETIRO", "Retiro en punto acordado"),
        ],
        required=False,
        initial="ENTREGA_ACORDADA",
    )

    delivery_instructions = forms.CharField(
        label="Instrucciones de entrega o retiro",
        max_length=1000,
        required=False,
        widget=forms.Textarea(
            attrs={
                "rows": 3,
                "placeholder": (
                    "Indica horario, referencia, "
                    "punto de encuentro u otras instrucciones."
                ),
            }
        ),
    )

    # ========================================================
    # ESTILO DEL FORMULARIO
    # ========================================================

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.style()

    # ========================================================
    # VALIDACION DE MODALIDAD
    # ========================================================

    def clean_delivery_method(self):
        return (
            self.cleaned_data.get("delivery_method")
            or "ENTREGA_ACORDADA"
        )
