from django import forms
from apps.accounts.forms import StyledForm
from apps.catalog.models import Category, Product


class ProductForm(StyledForm, forms.ModelForm):
    class Meta:
        model = Product
        fields = ['name','description','category','brand','model','price','stock','condition','image','location','active']
        labels={'name':'Nombre','description':'Descripción','category':'Categoría','brand':'Marca','model':'Modelo','price':'Precio (USD)','stock':'Unidades disponibles','condition':'Condición','image':'Fotografía','location':'Ubicación','active':'Visible tras aprobación'}
        widgets={'description':forms.Textarea(attrs={'rows':4}), 'image':forms.ClearableFileInput(attrs={'accept':'image/*'})}
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.fields['category'].queryset=Category.objects.filter(active=True)
        self.style()


class CategoryForm(StyledForm, forms.ModelForm):
    class Meta:
        model=Category
        fields=['name','icon','active']
        labels={'name':'Nombre','icon':'Emoji/icono','active':'Categoría activa'}
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs); self.style()

