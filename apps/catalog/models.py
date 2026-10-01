from django.db import models
from django.contrib.auth.models import User

##INCLUIDO EN FASE 2.2

class Category(models.Model):

    name = models.CharField(
        max_length=100,
        unique=True
    )

    icon = models.CharField(
        max_length=20,
        blank=True
    )

    active = models.BooleanField(
        default=True
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Product(models.Model):

    CONDITION_CHOICES = [
        ("NUEVO", "Nuevo"),
        ("USADO", "Usado"),
        ("REACONDICIONADO", "Reacondicionado"),
    ]

    APPROVAL_CHOICES = [
        ("PENDIENTE", "Pendiente"),
        ("APROBADO", "Aprobado"),
        ("RECHAZADO", "Rechazado"),
    ]

    seller = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="products"
    )

    category = models.ForeignKey(
        Category,
        on_delete=models.PROTECT,
        related_name="products"
    )

    name = models.CharField(
        max_length=150
    )

    description = models.TextField()

    brand = models.CharField(
        max_length=100
    )

    model = models.CharField(
        max_length=100,
        blank=True
    )

    price = models.DecimalField(
        max_digits=10,
        decimal_places=2
    )

    stock = models.PositiveIntegerField(
        default=0
    )

    condition = models.CharField(
        max_length=20,
        choices=CONDITION_CHOICES,
        default="NUEVO"
    )

    image = models.ImageField(
        upload_to="products/",
        blank=True,
        null=True
    )

    location = models.CharField(
        max_length=200,
        blank=True
    )

    approval_status = models.CharField(
        max_length=20,
        choices=APPROVAL_CHOICES,
        default="PENDIENTE"
    )

    active = models.BooleanField(
        default=True
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    updated_at = models.DateTimeField(
        auto_now=True
    )

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.name