
from django.db import transaction
from django.db.models import F

from apps.accounts.permissions import role
from apps.catalog.models import Product
from .models import PurchaseOrder, PurchaseLine, OrderStatusHistory


# FASE 7.1 - CR-06
# Estados y transiciones de pedidos.
# Referencia funcional: INDEX Base 2.1.

TRANSITIONS = {
    "PENDIENTE_PAGO": {
        "PAGO_EN_REVISION": ("COMPRADOR", "ADMINISTRADOR"),
        "CANCELADA": ("COMPRADOR", "ADMINISTRADOR"),
    },
    "PAGO_EN_REVISION": {
        "PAGADA": ("ADMINISTRADOR",),
        "PENDIENTE_PAGO": ("ADMINISTRADOR",),
        "CANCELADA": ("ADMINISTRADOR",),
    },
    "PAGADA": {
        "EN_PREPARACION": ("VENDEDOR", "ADMINISTRADOR"),
        "EN_DISPUTA": ("COMPRADOR", "ADMINISTRADOR"),
        "CANCELADA": ("ADMINISTRADOR",),
    },
    "EN_PREPARACION": {
        "LISTA_ENTREGA": ("VENDEDOR", "ADMINISTRADOR"),
        "EN_DISPUTA": ("COMPRADOR", "ADMINISTRADOR"),
        "CANCELADA": ("ADMINISTRADOR",),
    },
    "LISTA_ENTREGA": {
        "ENTREGADA": ("VENDEDOR", "ADMINISTRADOR"),
        "EN_DISPUTA": ("COMPRADOR", "ADMINISTRADOR"),
    },
    "ENTREGADA": {
        "COMPLETADA": ("COMPRADOR", "ADMINISTRADOR"),
        "EN_DISPUTA": ("COMPRADOR", "ADMINISTRADOR"),
    },
    "EN_DISPUTA": {
        "COMPLETADA": ("ADMINISTRADOR",),
        "CANCELADA": ("ADMINISTRADOR",),
        "PAGADA": ("ADMINISTRADOR",),
    },
    "COMPLETADA": {},
    "CANCELADA": {},

    # Pedidos históricos, anteriores a CR-06.
    "PENDIENTE": {
        "EN_PROCESO": ("ADMINISTRADOR",),
        "CANCELADO": ("ADMINISTRADOR",),
        "CANCELADA": ("COMPRADOR",),
    },
    "EN_PROCESO": {
        "COMPLETADO": ("ADMINISTRADOR",),
    },
    "COMPLETADO": {},
    "CANCELADO": {},
}


LABELS = dict(PurchaseOrder.STATUSES)

SELLER_NEXT = {
    "PENDIENTE": "PREPARANDO",
    "PREPARANDO": "ENVIADO",
    "ENVIADO": "ENTREGADO",
}

FULFILLMENT_STATES = {
    "PAGADA",
    "EN_PREPARACION",
    "LISTA_ENTREGA",
}


class OrderStateError(ValueError):
    pass


def _lines(order):
    return list(order.lines.all())


def _has_receipt(order, statuses):
    # CR-07 incorporará el modelo de comprobantes.
    # Nunca se debe asumir que un pago fue aprobado.
    relation = getattr(order, "receipts", None)

    if relation is None:
        return False

    return relation.filter(status__in=statuses).exists()


def _validate(order, new_status, actor, reason=""):
    if (
        actor is None
        or not actor.is_authenticated
        or not actor.is_active
    ):
        raise OrderStateError("Necesitas una sesión activa.")

    current = order.status

    if new_status == current:
        raise OrderStateError(
            "La orden ya tiene ese estado."
        )

    user_role = role(actor)

    permitted = TRANSITIONS.get(current, {}).get(
        new_status, ()
    )

    if user_role not in permitted:
        raise OrderStateError(
            "Este cambio de estado no está permitido."
        )

    if (
        user_role == "COMPRADOR"
        and order.buyer_id != actor.pk
    ):
        raise OrderStateError(
            "No puedes modificar pedidos de otros compradores."
        )

    if (
        user_role == "VENDEDOR"
        and not order.lines.filter(
            seller_id=actor.pk
        ).exists()
    ):
        raise OrderStateError(
            "No tienes productos asociados a este pedido."
        )

    lines = _lines(order)

    if new_status == "PAGO_EN_REVISION":
        if not _has_receipt(
            order, ("PENDIENTE", "APROBADO")
        ):
            raise OrderStateError(
                "Primero debes adjuntar un comprobante de pago."
            )

    if new_status == "PAGADA":
        if current == "PAGO_EN_REVISION":
            if not _has_receipt(order, ("APROBADO",)):
                raise OrderStateError(
                    "El comprobante todavía no está aprobado."
                )

    if (
        current == "PAGO_EN_REVISION"
        and new_status == "PENDIENTE_PAGO"
        and _has_receipt(order, ("PENDIENTE", "APROBADO"))
    ):
        raise OrderStateError(
            "Primero debe rechazarse el comprobante."
        )

    if new_status in {
        "EN_PREPARACION",
        "LISTA_ENTREGA",
        "ENTREGADA",
        "COMPLETADA",
        "COMPLETADO",
    } and not lines:
        raise OrderStateError(
            "El pedido no tiene artículos."
        )

    if new_status == "LISTA_ENTREGA":
        if any(
            line.status not in ("ENVIADO", "ENTREGADO")
            for line in lines
        ):
            raise OrderStateError(
                "Todos los artículos deben estar enviados."
            )

    if new_status in ("ENTREGADA", "COMPLETADA", "COMPLETADO"):
        if any(
            line.status != "ENTREGADO"
            for line in lines
        ):
            raise OrderStateError(
                "Todos los artículos deben estar entregados."
            )

    if new_status in ("CANCELADA", "CANCELADO"):
        if any(
            line.status in ("ENVIADO", "ENTREGADO")
            for line in lines
        ):
            raise OrderStateError(
                "Hay artículos enviados o entregados. "
                "Se requiere revisión manual del inventario."
            )

        if current == "PENDIENTE":
            if any(
                line.status != "PENDIENTE"
                for line in lines
            ):
                raise OrderStateError(
                    "Este pedido antiguo ya inició preparación."
                )

    if new_status == "EN_DISPUTA":
        if not reason.strip():
            raise OrderStateError(
                "Debes indicar el motivo de la disputa."
            )

    if current == "EN_DISPUTA":
        if not reason.strip():
            raise OrderStateError(
                "La resolución requiere un motivo."
            )

        if new_status == "PAGADA":
            if any(
                line.status != "PENDIENTE"
                for line in lines
            ):
                raise OrderStateError(
                    "La entrega ya comenzó. "
                    "Se requiere una resolución individual."
                )

    if (
        new_status == "CANCELADA"
        and current not in ("PENDIENTE_PAGO", "PENDIENTE")
        and not reason.strip()
    ):
        raise OrderStateError(
            "Debes indicar el motivo de cancelación."
        )


def allowed_order_targets(order, actor):
    options = []

    for target in TRANSITIONS.get(order.status, {}):
        # El usuario introducirá el motivo al confirmar.
        needs_reason = (
            target == "EN_DISPUTA"
            or order.status == "EN_DISPUTA"
            or (
                target == "CANCELADA"
                and order.status not in (
                    "PENDIENTE_PAGO", "PENDIENTE"
                )
            )
        )

        reason = "Pendiente de indicar" if needs_reason else ""

        try:
            _validate(order, target, actor, reason)
        except OrderStateError:
            continue

        options.append((target, LABELS[target]))

    return options


def _apply_locked(order, new_status, actor, reason=""):
    _validate(order, new_status, actor, reason)

    previous = order.status

    if new_status in ("CANCELADA", "CANCELADO"):
        from apps.orders.stock_services import release_order_stock
        # Los pedidos legacy sin lineas se podian cancelar sin restock.
        # Para pedidos con lineas, restituir en la misma transaccion.
        if new_status == "CANCELADA" or order.lines.exists():
            release_order_stock(order)

    order.status = new_status
    order.save(update_fields=["status", "updated_at"])

    OrderStatusHistory.objects.create(
        order=order,
        previous_status=previous,
        new_status=new_status,
        actor=actor,
        actor_role=role(actor),
        reason=(reason or "").strip()[:2000],
    )

    return order


@transaction.atomic
def transition_order(order_id, new_status, actor, reason=""):
    order = PurchaseOrder.objects.select_for_update().get(
        pk=order_id
    )

    list(
        order.lines.select_for_update().order_by("pk")
    )

    return _apply_locked(
        order, new_status, actor, reason
    )


def can_advance_seller_line(line):
    return (
        line.status in SELLER_NEXT
        and line.order.status in FULFILLMENT_STATES
    )


@transaction.atomic
def advance_seller_line(line_id, actor):
    if (
        actor is None
        or not actor.is_authenticated
        or not actor.is_active
        or role(actor) != "VENDEDOR"
    ):
        raise OrderStateError(
            "Solo un vendedor activo puede actualizar sus ventas."
        )

    reference = PurchaseLine.objects.filter(
        pk=line_id,
        seller=actor,
    ).values("order_id").first()

    if not reference:
        raise OrderStateError(
            "La venta no existe o no te pertenece."
        )

    order = PurchaseOrder.objects.select_for_update().get(
        pk=reference["order_id"]
    )

    lines = list(
        order.lines.select_for_update().order_by("pk")
    )

    line = next(
        (item for item in lines if item.pk == line_id),
        None,
    )

    if (
        line is None
        or line.seller_id != actor.pk
        or not can_advance_seller_line(line)
    ):
        raise OrderStateError(
            "No puedes avanzar esta venta antes de aprobar el pago."
        )

    line.status = SELLER_NEXT[line.status]
    line.save(update_fields=["status"])
    if line.status == "ENVIADO":
        from apps.orders.stock_services import consume_shipped_line
        consume_shipped_line(line)

    if order.status == "PAGADA":
        _apply_locked(
            order,
            "EN_PREPARACION",
            actor,
            "El vendedor inició la preparación",
        )

    if order.status == "EN_PREPARACION":
        if all(
            item.status in ("ENVIADO", "ENTREGADO")
            for item in lines
        ):
            _apply_locked(
                order,
                "LISTA_ENTREGA",
                actor,
                "Todos los artículos fueron despachados",
            )

    if order.status == "LISTA_ENTREGA":
        if all(
            item.status == "ENTREGADO"
            for item in lines
        ):
            _apply_locked(
                order,
                "ENTREGADA",
                actor,
                "Todos los artículos fueron entregados",
            )

    return line, order


def record_order_created(order, actor):
    return OrderStatusHistory.objects.create(
        order=order,
        previous_status="",
        new_status=order.status,
        actor=actor,
        actor_role=role(actor),
        reason="Pedido creado",
    )
