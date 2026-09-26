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