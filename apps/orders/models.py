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

# Pedidos vinculados al comprador, al vendedor y al catÃ¡logo existentes.
class PurchaseOrder(models.Model):
    STATUSES = [('PENDIENTE_PAGO', 'Pendiente de pago'), ('PAGO_EN_REVISION', 'Pago en revision'), ('PAGADA', 'Pagada'), ('EN_PREPARACION', 'En preparacion'), ('LISTA_ENTREGA', 'Lista para entrega'), ('ENTREGADA', 'Entregada'), ('EN_DISPUTA', 'En disputa'), ('COMPLETADA', 'Completada'), ('CANCELADA', 'Cancelada')] + [('PENDIENTE', 'Pendiente legado'), ('EN_PROCESO', 'En proceso legado'), ('COMPLETADO', 'Completado legado'), ('CANCELADO', 'Cancelado legado')]
    buyer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='market_orders')
    status = models.CharField(max_length=20, choices=STATUSES, default='PENDIENTE')
    checkout_token = models.UUIDField(null=True, blank=True, unique=True, editable=False)
    contact_name = models.CharField(max_length=150)
    contact_phone = models.CharField(max_length=20)
    province = models.CharField(max_length=100)
    address = models.TextField()
    comments = models.TextField(blank=True)
    total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


    # CR-13: modalidad e instrucciones de entrega
    DELIVERY_CHOICES = [
        ("ENTREGA_ACORDADA", "Entrega acordada"),
        ("RETIRO", "Retiro"),
    ]

    delivery_method = models.CharField(
        max_length=20,
        choices=DELIVERY_CHOICES,
        default="ENTREGA_ACORDADA",
    )

    delivery_instructions = models.TextField(
        blank=True,
    )


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

class OrderStatusHistory(models.Model):
    order = models.ForeignKey(PurchaseOrder, on_delete=models.CASCADE, related_name="status_history")
    previous_status = models.CharField(max_length=20, blank=True)
    new_status = models.CharField(max_length=20)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    actor_role = models.CharField(max_length=20, blank=True)
    reason = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "id"]

class PaymentReceipt(models.Model):
    order = models.ForeignKey(PurchaseOrder, on_delete=models.PROTECT, related_name="receipts")
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="uploaded_receipts")
    file_name = models.CharField(max_length=255)
    mime_type = models.CharField(max_length=50)
    file_size = models.PositiveIntegerField()
    file_data = models.BinaryField()
    status = models.CharField(max_length=15, choices=[("PENDIENTE", "Pendiente"), ("APROBADO", "Aprobado"), ("RECHAZADO", "Rechazado")], default="PENDIENTE")
    observation = models.TextField(blank=True)
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="reviewed_receipts")
    uploaded_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)

class StockReservation(models.Model):
    line = models.OneToOneField(PurchaseLine, on_delete=models.PROTECT, related_name="stock_reservation")
    product = models.ForeignKey("catalog.Product", on_delete=models.PROTECT)
    quantity = models.PositiveIntegerField()
    status = models.CharField(max_length=12, choices=[("ACTIVA", "Activa"), ("LIBERADA", "Liberada"), ("CONSUMIDA", "Consumida"), ("VENCIDA", "Vencida")], default="ACTIVA")
    expires_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

class StockMovement(models.Model):
    product = models.ForeignKey("catalog.Product", on_delete=models.PROTECT, related_name="stock_movements")
    order = models.ForeignKey(PurchaseOrder, on_delete=models.PROTECT, null=True, blank=True)
    reservation = models.ForeignKey(StockReservation, on_delete=models.PROTECT, null=True, blank=True)
    movement_type = models.CharField(max_length=20)
    quantity_change = models.IntegerField()
    reason = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)



class Offer(models.Model):
    STATUSES = [
        ("PENDIENTE", "Pendiente del vendedor"),
        ("CONTRAOFERTA", "Contraoferta recibida"),
        ("ACEPTADA", "Oferta aceptada"),
        ("RECHAZADA", "Oferta rechazada"),
        ("VENCIDA", "Oferta vencida"),
        ("CONVERTIDA", "Convertida en compra"),
    ]

    product = models.ForeignKey(
        "catalog.Product",
        on_delete=models.PROTECT,
        related_name="offers",
    )

    buyer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="offers_sent",
    )

    seller = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="offers_received",
    )

    offered_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
    )

    counter_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
    )

    agreed_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
    )

    status = models.CharField(
        max_length=20,
        choices=STATUSES,
        default="PENDIENTE",
    )

    expires_at = models.DateTimeField()

    accepted_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    order = models.ForeignKey(
        "orders.PurchaseOrder",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="negotiated_offers",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Oferta #{self.pk} - Producto #{self.product_id}"


# ============================================================
# CR-14 - SISTEMA DE NOTIFICACIONES INTERNAS
# ============================================================

class Notification(models.Model):

    TYPES = [
        ("COMPRA_NUEVA", "Nueva compra"),
        ("PAGO_APROBADO", "Pago aprobado"),
        ("PAGO_RECHAZADO", "Pago rechazado"),
        ("ESTADO_PEDIDO", "Cambio de estado"),
        ("OFERTA_NUEVA", "Nueva oferta"),
        ("OFERTA_RESPUESTA", "Respuesta de oferta"),
        ("CANCELACION", "Cancelación"),
        ("DISPUTA", "Disputa"),
    ]

    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="market_notifications",
    )

    notification_type = models.CharField(
        max_length=25,
        choices=TYPES,
    )

    message = models.CharField(
        max_length=500,
    )

    order = models.ForeignKey(
        "orders.PurchaseOrder",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="notifications",
    )

    offer = models.ForeignKey(
        "orders.Offer",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="notifications",
    )

    event_key = models.CharField(
        max_length=150,
        unique=True,
        null=True,
        blank=True,
        editable=False,
    )

    is_read = models.BooleanField(
        default=False,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return (
            f"Notificación #{self.pk} "
            f"- Usuario #{self.recipient_id}"
        )




# ============================================================
# CR-15 - VALORACIONES Y RESENAS VERIFICADAS
# ============================================================

class ProductReview(models.Model):

    RATING_CHOICES = [
        (1, "1 estrella"),
        (2, "2 estrellas"),
        (3, "3 estrellas"),
        (4, "4 estrellas"),
        (5, "5 estrellas"),
    ]

    order_line = models.OneToOneField(
        "orders.PurchaseLine",
        on_delete=models.PROTECT,
        related_name="verified_review",
    )

    rating = models.PositiveSmallIntegerField(
        choices=RATING_CHOICES,
    )

    comment = models.TextField(
        max_length=2000,
        blank=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(
                    rating__gte=1,
                    rating__lte=5,
                ),
                name="cr15_rating_range",
            ),
        ]

    @property
    def product(self):
        return self.order_line.product

    @property
    def buyer(self):
        return self.order_line.order.buyer

    @property
    def is_verified(self):
        return (
            self.order_line.order.status == "COMPLETADA"
        )

    def __str__(self):
        return (
            f"Reseña #{self.pk} | "
            f"Producto #{self.order_line.product_id} | "
            f"{self.rating}/5"
        )
