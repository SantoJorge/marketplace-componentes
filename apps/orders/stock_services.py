"""CR-09: reservas y auditoria de inventario.

Convencion existente del Marketplace: Product.stock = unidades DISPONIBLES.
El checkout ya hace stock = stock - quantity con una actualización condicional.
Crear una reserva SOLO registra ese descuento; no descuenta dos veces.
"""
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.db.models import F
from django.utils import timezone

from apps.catalog.models import Product
from .models import PurchaseLine, StockMovement, StockReservation
from .services import OrderStateError


class StockIntegrityError(OrderStateError):
    """El inventario requiere revisión antes de continuar."""


def _require_atomic():
    if not transaction.get_connection().in_atomic_block:
        raise StockIntegrityError("Operación de inventario fuera de una transacción.")


def reserve_order_lines(order):
    """Se invoca DESPUÉS del descuento en checkout y ANTES de confirmar la transacción."""
    _require_atomic()
    if order.status != "PENDIENTE_PAGO":
        raise StockIntegrityError("El pedido no admite una reserva inicial.")
    lines = list(PurchaseLine.objects.select_for_update().filter(order=order).order_by("pk"))
    if not lines:
        raise StockIntegrityError("No hay artículos que reservar.")
    if StockReservation.objects.filter(line__order=order).exists():
        raise StockIntegrityError("La reserva de este pedido ya fue registrada.")
    hours = int(getattr(settings, "MARKETPLACE_RESERVATION_HOURS", 48))
    if hours < 1 or hours > 720:
        raise StockIntegrityError("Configuración de duración de reservas inválida.")
    expires_at = timezone.now() + timedelta(hours=hours)
    for line in lines:
        if line.quantity < 1:
            raise StockIntegrityError("Cantidad de la línea inválida.")
        reservation = StockReservation.objects.create(
            line=line, product_id=line.product_id,
            quantity=line.quantity, status="ACTIVA", expires_at=expires_at,
        )
        StockMovement.objects.create(
            product_id=line.product_id, order=order, reservation=reservation,
            movement_type="RESERVA", quantity_change=-line.quantity,
            reason="Stock descontado una vez en checkout; reserva registrada",
        )


def release_order_stock(order, *, expired=False):
    """Devuelve stock exactamente una vez en cancelaciones (o expiración)."""
    _require_atomic()
    lines = list(PurchaseLine.objects.select_for_update().filter(order=order).order_by("pk"))
    if not lines:
        raise StockIntegrityError("Pedido sin líneas: no puede regularizarse automáticamente.")
    reservations = {
        res.line_id: res for res in StockReservation.objects.select_for_update()
        .filter(line__order=order).order_by("pk")
    }
    if reservations and len(reservations) != len(lines):
        raise StockIntegrityError("Reserva parcial. Requiere revisión administrativa.")
    if any(line.status in ("ENVIADO", "ENTREGADO") for line in lines):
        raise StockIntegrityError("Hay unidades enviadas. Requiere revisión administrativa.")
    for line in lines:
        reservation = reservations.get(line.pk)
        if reservation and reservation.status != "ACTIVA":
            raise StockIntegrityError("Reserva ya liberada o consumida. Se evita doble devolución.")
        if reservation and (reservation.product_id != line.product_id or reservation.quantity != line.quantity):
            raise StockIntegrityError("La reserva no coincide con la línea del pedido.")
    # Nunca devolver parcialmente: todas las validaciones pasan antes del primer UPDATE.
    for line in lines:
        reservation = reservations.get(line.pk)
        Product.objects.filter(pk=line.product_id).update(stock=F("stock") + line.quantity)
        movement_type = "EXPIRACION" if expired else "LIBERACION"
        StockMovement.objects.create(
            product_id=line.product_id, order=order, reservation=reservation,
            movement_type=movement_type, quantity_change=line.quantity,
            reason="Devolución de stock por vencimiento" if expired else "Devolución por cancelación",
        )
        if reservation:
            reservation.status = "VENCIDA" if expired else "LIBERADA"
            reservation.save(update_fields=["status", "updated_at"])


def consume_shipped_line(line):
    """Marca el stock reservado como enviado, sin descontarlo de nuevo."""
    _require_atomic()
    res = StockReservation.objects.select_for_update().filter(line=line).first()
    if res is None:  # Pedido anterior a la instalación de CR-09.
        return
    if res.status != "ACTIVA":
        raise StockIntegrityError("No se puede enviar una reserva liberada o consumida.")
    res.status = "CONSUMIDA"
    res.save(update_fields=["status", "updated_at"])
    StockMovement.objects.create(
        product_id=line.product_id, order_id=line.order_id, reservation=res,
        movement_type="CONSUMO", quantity_change=0,
        reason="Reserva consumida al enviar; stock ya descontado en checkout",
    )
