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

from django.conf import settings

# Pedidos vinculados al comprador, al vendedor y al catálogo existentes.
class PurchaseOrder(models.Model):
    STATUSES = [('PENDIENTE', 'Pendiente'), ('EN_PROCESO', 'En proceso'), ('COMPLETADO', 'Completado'), ('CANCELADO', 'Cancelado')]
    buyer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='market_orders')
    status = models.CharField(max_length=15, choices=STATUSES, default='PENDIENTE')
    contact_name = models.CharField(max_length=150)
    contact_phone = models.CharField(max_length=20)
    province = models.CharField(max_length=100)
    address = models.TextField()
    comments = models.TextField(blank=True)
    total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'Pedido #{self.pk}'


class PurchaseLine(models.Model):
    STATUSES = [('PENDIENTE', 'Pendiente'), ('PREPARANDO', 'Preparando'), ('ENVIADO', 'Enviado'), ('ENTREGADO', 'Entregado')]
    order = models.ForeignKey(PurchaseOrder, on_delete=models.CASCADE, related_name='lines')
    product = models.ForeignKey('catalog.Product', on_delete=models.PROTECT)
    seller = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='market_sale_lines')
    product_name = models.CharField(max_length=150)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    quantity = models.PositiveIntegerField()
    status = models.CharField(max_length=12, choices=STATUSES, default='PENDIENTE')

    @property
    def subtotal(self):
        return self.unit_price * self.quantity

    class Meta:
        ordering = ['pk']
