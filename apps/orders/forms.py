from django import forms
from apps.accounts.forms import PROVINCIAS_PANAMA, StyledForm


class CheckoutForm(StyledForm, forms.Form):
    contact_name=forms.CharField(label='Nombre de quien recibe', max_length=150)
    contact_phone=forms.CharField(label='Teléfono de contacto',max_length=20)
    province=forms.ChoiceField(label='Provincia',choices=PROVINCIAS_PANAMA)
    address=forms.CharField(label='Dirección de entrega / coordinación',widget=forms.Textarea(attrs={'rows':3}))
    comments=forms.CharField(label='Comentarios',required=False,widget=forms.Textarea(attrs={'rows':2}))
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs); self.style()

