from django.db import models
from django.contrib.auth.models import User

from apps.catalog.models import Product


class Cart(models.Model):

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="cart",
        null=True,
        blank=True
    )

    session_key = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        unique=True
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    updated_at = models.DateTimeField(
        auto_now=True
    )

    def __str__(self):

        if self.user:
            return f"Carrito de {self.user.username}"

        return f"Carrito invitado {self.session_key}"

    @property
    def total(self):

        return sum(
            item.subtotal
            for item in self.items.all()
        )


class CartItem(models.Model):

    cart = models.ForeignKey(
        Cart,
        on_delete=models.CASCADE,
        related_name="items"
    )

    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="cart_items"
    )

    quantity = models.PositiveIntegerField(
        default=1
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    updated_at = models.DateTimeField(
        auto_now=True
    )

    class Meta:

        unique_together = (
            "cart",
            "product",
        )

    def __str__(self):

        return (
            f"{self.product.name} "
            f"x {self.quantity}"
        )

    @property
    def subtotal(self):

        return (
            self.product.price *
            self.quantity
        )