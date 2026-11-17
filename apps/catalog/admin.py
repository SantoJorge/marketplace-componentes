from django.contrib import admin

# Register your models here.

from .models import ProductTechnicalSpec
@admin.register(ProductTechnicalSpec)
class ProductTechnicalSpecAdmin(admin.ModelAdmin):
    list_display = ('product','component_type','socket','ram_type')
    search_fields = ('product__name','socket','ram_type')
