"""Derived showroom images. Originals are never changed."""
import hashlib
from django.conf import settings
from django.core.files.storage import FileSystemStorage


def cut_storage():
    return FileSystemStorage(location=settings.MEDIA_ROOT, base_url=settings.MEDIA_URL)


def cut_name(product):
    image = product.image
    if not image or not image.name:
        return None
    try:
        modified = image.storage.get_modified_time(image.name)
        size = image.storage.size(image.name)
    except (OSError, ValueError, NotImplementedError):
        return None
    signature = hashlib.sha256(f'v1|{image.name}|{modified.isoformat()}|{size}'.encode('utf-8')).hexdigest()[:24]
    return f'products/horizon_cut/product_{product.pk}_{signature}_cut.png'
