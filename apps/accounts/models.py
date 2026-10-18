from django.conf import settings
from django.db import models
from django.contrib.auth.models import User


class Profile(models.Model):
    
    
    ROLE_CHOICES = [
        ("COMPRADOR", "Comprador"),
        ("VENDEDOR", "Vendedor"),
        ("ADMINISTRADOR", "Administrador"),
    ]

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="profile"
    )

    role = models.CharField(
        max_length=20,
        choices=ROLE_CHOICES,
        default="COMPRADOR"
    )

    phone = models.CharField(
        max_length=20,
        blank=True
    )

    province = models.CharField(
        max_length=100,
        blank=True
    )

    active = models.BooleanField(
        default=True
    )

    def __str__(self):
        return f"{self.user.username} - {self.role}"



class SellerProfile(models.Model):

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="seller_profile"
    )

    business_name = models.CharField(
        max_length=150
    )

    business_description = models.TextField(
        blank=True
    )

    business_phone = models.CharField(
        max_length=20,
        blank=True
    )

    location = models.CharField(
        max_length=200,
        blank=True
    )

    active = models.BooleanField(
        default=True
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    def __str__(self):
        return self.business_name


# Solicitud de vendedor (antes separada artificialmente de accounts).
class SellerRequest(models.Model):
    STATUSES = [('PENDIENTE', 'Pendiente'), ('APROBADA', 'Aprobada'), ('RECHAZADA', 'Rechazada')]
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='market_seller_request')
    business_name = models.CharField(max_length=150)
    business_description = models.TextField(blank=True)
    business_phone = models.CharField(max_length=20, blank=True)
    location = models.CharField(max_length=200, blank=True)
    status = models.CharField(max_length=12, choices=STATUSES, default='PENDIENTE')
    review_note = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.user.username}: {self.status}'
