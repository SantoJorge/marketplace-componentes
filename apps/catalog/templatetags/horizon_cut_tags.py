from django import template
from apps.catalog.horizon_cut import cut_name, cut_storage

register = template.Library()

@register.simple_tag
def horizon_cut_url(product):
    name = cut_name(product)
    if not name:
        return ''
    storage = cut_storage()
    try:
        return storage.url(name) if storage.exists(name) else ''
    except (OSError, ValueError):
        return ''
