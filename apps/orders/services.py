
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

    # CR-12: conservar la devolucion de inventario.
    if new_status in ("CANCELADA", "CANCELADO"):
        from apps.orders.stock_services import release_order_stock

        # Los pedidos legacy sin lineas se podian cancelar sin restock.
        # Para pedidos con lineas, restituir en la misma transaccion.
        if new_status == "CANCELADA" or order.lines.exists():
            release_order_stock(order)

    order.status = new_status
    order.save(update_fields=["status", "updated_at"])

    historial = OrderStatusHistory.objects.create(
        order=order,
        previous_status=previous,
        new_status=new_status,
        actor=actor,
        actor_role=role(actor),
        reason=(reason or "").strip()[:2000],
    )

    # CR-14: identificar el acontecimiento.
    if previous == "PAGO_EN_REVISION" and new_status == "PAGADA":
        tipo = "PAGO_APROBADO"
    elif previous == "PAGO_EN_REVISION" and new_status == "PENDIENTE_PAGO":
        tipo = "PAGO_RECHAZADO"
    elif new_status in ("CANCELADA", "CANCELADO"):
        tipo = "CANCELACION"
    elif new_status == "EN_DISPUTA":
        tipo = "DISPUTA"
    else:
        tipo = "ESTADO_PEDIDO"

    # El comprador recibe todos los cambios relevantes.
    destinatarios = {order.buyer_id}

    # En cancelaciones y disputas tambien se informa a los vendedores.
    if tipo in ("CANCELACION", "DISPUTA"):
        destinatarios.update(
            order.lines.values_list(
                "seller_id", flat=True
            ).distinct()
        )

    estado_visible = LABELS.get(new_status, new_status)

    for destinatario_id in destinatarios:
        cr14_notificar(
            destinatario_id=destinatario_id,
            tipo=tipo,
            mensaje=(
                f"El pedido #{order.pk} ha cambiado "
                f"al estado: {estado_visible}."
            ),
            clave=(
                f"pedido:{order.pk}:"
                f"historial:{historial.pk}:"
                f"usuario:{destinatario_id}"
            ),
            pedido=order,
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
    historial = OrderStatusHistory.objects.create(
        order=order,
        previous_status="",
        new_status=order.status,
        actor=actor,
        actor_role=role(actor),
        reason="Pedido creado",
    )

    # CR-14: notificar una vez a cada vendedor del pedido.
    vendedores = (
        order.lines
        .values_list("seller_id", flat=True)
        .distinct()
    )

    for vendedor_id in vendedores:
        cr14_notificar(
            destinatario_id=vendedor_id,
            tipo="COMPRA_NUEVA",
            mensaje=f"Has recibido una nueva compra en el pedido #{order.pk}.",
            clave=f"pedido:{order.pk}:compra:vendedor:{vendedor_id}",
            pedido=order,
        )

    return historial



# ============================================================
# CR-11 - OFERTAS Y CONTRAOFERTAS
# ============================================================

from datetime import timedelta
from decimal import Decimal, InvalidOperation

from django.conf import settings
from django.utils import timezone

from .models import Offer


class OfferError(OrderStateError):
    pass


def _cr11_precio(valor):
    try:
        precio = Decimal(str(valor))
    except (InvalidOperation, ValueError, TypeError):
        raise OfferError("Introduce un precio valido.")

    if (
        not precio.is_finite()
        or precio <= 0
        or precio > Decimal("99999999.99")
        or precio != precio.quantize(Decimal("0.01"))
    ):
        raise OfferError("El precio debe ser positivo y tener maximo dos decimales.")

    return precio


def _cr11_vigencia():
    horas = int(getattr(settings, "MARKETPLACE_OFFER_HOURS", 48))

    if not 1 <= horas <= 720:
        raise OfferError("La vigencia configurada no es valida.")

    return timezone.now() + timedelta(hours=horas)


def _cr11_producto_disponible(producto):
    return (
        producto.condition == "USADO"
        and producto.active
        and producto.approval_status == "APROBADO"
        and producto.stock > 0
        and producto.category.active
        and producto.seller.is_active
    )


@transaction.atomic
def cr11_crear_oferta(product_id, comprador, monto):
    if (
        comprador is None
        or not comprador.is_authenticated
        or role(comprador) not in ("COMPRADOR", "VENDEDOR")
    ):
        raise OfferError("Necesitas una cuenta activa para ofertar.")

    try:
        producto = (
            Product.objects
            .select_related("seller", "category")
            .select_for_update()
            .get(pk=product_id)
        )
    except Product.DoesNotExist:
        raise OfferError("El producto no existe.")

    if not _cr11_producto_disponible(producto):
        raise OfferError("Este producto no admite ofertas.")

    if producto.seller_id == comprador.pk:
        raise OfferError("No puedes ofertar por tu propio producto.")

    precio = _cr11_precio(monto)
    ahora = timezone.now()

    if Offer.objects.filter(
        product=producto,
        buyer=comprador,
        status__in=("PENDIENTE", "CONTRAOFERTA", "ACEPTADA"),
        expires_at__gt=ahora,
    ).exists():
        raise OfferError("Ya tienes una negociacion vigente para este producto.")


    oferta = Offer.objects.create(
        product=producto,
        buyer=comprador,
        seller=producto.seller,
        offered_price=precio,
        expires_at=_cr11_vigencia(),
    )

    # CR-14: avisar al vendedor sobre la nueva oferta.
    cr14_notificar(
        destinatario_id=producto.seller_id,
        tipo="OFERTA_NUEVA",
        mensaje=(
            f"Has recibido una oferta de "
            f"${precio} por {producto.name}."
        ),
        clave=f"oferta:{oferta.pk}:creada",
        oferta=oferta,
    )

    return oferta



@transaction.atomic
def cr11_responder_vendedor(oferta_id, vendedor, accion, monto=None):
    try:
        oferta = (
            Offer.objects.select_for_update()
            .select_related("product", "product__category", "product__seller")
            .get(pk=oferta_id)
        )
    except Offer.DoesNotExist:
        raise OfferError("La oferta no existe.")

    if role(vendedor) != "VENDEDOR" or oferta.seller_id != vendedor.pk:
        raise OfferError("No tienes permiso para responder esta oferta.")

    if oferta.status != "PENDIENTE":
        raise OfferError("Esta oferta ya fue respondida.")

    if oferta.expires_at <= timezone.now():
        raise OfferError("La oferta ha vencido.")

    accion = str(accion).strip().upper()

    if accion not in ("ACEPTAR", "RECHAZAR", "CONTRAOFERTAR"):
        raise OfferError("Accion no permitida.")

    if accion != "RECHAZAR" and not _cr11_producto_disponible(oferta.product):
        raise OfferError("El producto ya no esta disponible.")

    campos = ["status", "updated_at"]

    if accion == "ACEPTAR":
        oferta.status = "ACEPTADA"
        oferta.agreed_price = oferta.offered_price
        oferta.accepted_at = timezone.now()
        oferta.expires_at = _cr11_vigencia()
        campos += ["agreed_price", "accepted_at", "expires_at"]

    elif accion == "RECHAZAR":
        oferta.status = "RECHAZADA"

    else:
        precio = _cr11_precio(monto)

        if precio == oferta.offered_price:
            raise OfferError("La contraoferta debe tener un precio diferente.")

        oferta.counter_price = precio
        oferta.status = "CONTRAOFERTA"
        oferta.expires_at = _cr11_vigencia()
        campos += ["counter_price", "expires_at"]


    oferta.save(update_fields=campos)

    # CR-14: avisar al comprador de la respuesta.
    cr14_notificar(
        destinatario_id=oferta.buyer_id,
        tipo="OFERTA_RESPUESTA",
        mensaje=(
            f"El vendedor ha respondido a tu oferta "
            f"#{oferta.pk}: {oferta.get_status_display()}."
        ),
        clave=f"oferta:{oferta.pk}:respuesta:vendedor",
        oferta=oferta,
    )

    return oferta



@transaction.atomic
def cr11_responder_comprador(oferta_id, comprador, accion):
    try:
        oferta = (
            Offer.objects.select_for_update()
            .select_related("product", "product__category", "product__seller")
            .get(pk=oferta_id)
        )
    except Offer.DoesNotExist:
        raise OfferError("La oferta no existe.")

    if (
        role(comprador) not in ("COMPRADOR", "VENDEDOR")
        or oferta.buyer_id != comprador.pk
    ):
        raise OfferError("No tienes permiso para responder esta contraoferta.")

    if oferta.status != "CONTRAOFERTA":
        raise OfferError("No existe una contraoferta pendiente.")

    if oferta.expires_at <= timezone.now():
        raise OfferError("La contraoferta ha vencido.")

    accion = str(accion).strip().upper()

    if accion not in ("ACEPTAR", "RECHAZAR"):
        raise OfferError("Accion no permitida.")

    campos = ["status", "updated_at"]

    if accion == "ACEPTAR":
        if not _cr11_producto_disponible(oferta.product):
            raise OfferError("El producto ya no esta disponible.")

        oferta.status = "ACEPTADA"
        oferta.agreed_price = oferta.counter_price
        oferta.accepted_at = timezone.now()
        oferta.expires_at = _cr11_vigencia()
        campos += ["agreed_price", "accepted_at", "expires_at"]

    else:
        oferta.status = "RECHAZADA"


    oferta.save(update_fields=campos)

    # CR-14: avisar al vendedor de la decision del comprador.
    cr14_notificar(
        destinatario_id=oferta.seller_id,
        tipo="OFERTA_RESPUESTA",
        mensaje=(
            f"El comprador ha respondido a tu contraoferta "
            f"#{oferta.pk}: {oferta.get_status_display()}."
        ),
        clave=f"oferta:{oferta.pk}:respuesta:comprador",
        oferta=oferta,
    )

    return oferta



def cr11_vencer_ofertas():
    return Offer.objects.filter(
        status__in=("PENDIENTE", "CONTRAOFERTA", "ACEPTADA"),
        expires_at__lte=timezone.now(),
    ).update(status="VENCIDA", updated_at=timezone.now())



# ============================================================
# CR-14 - NOTIFICACIONES INTERNAS
# ============================================================

from .models import Notification


def cr14_notificar(
    *,
    destinatario_id,
    tipo,
    mensaje,
    clave,
    pedido=None,
    oferta=None,
):
    """
    Registra una notificacion unica por evento y destinatario.

    Debe llamarse dentro de la transaccion que registra
    el evento principal.
    """

    if not destinatario_id:
        raise ValueError("Destinatario obligatorio.")

    if tipo not in dict(Notification.TYPES):
        raise ValueError("Tipo de notificacion invalido.")

    if not mensaje or len(mensaje) > 500:
        raise ValueError("Mensaje de notificacion invalido.")

    if not clave or len(clave) > 150:
        raise ValueError("Identificador de evento invalido.")

    notificacion, creada = Notification.objects.get_or_create(
        event_key=clave,
        defaults={
            "recipient_id": destinatario_id,
            "notification_type": tipo,
            "message": mensaje,
            "order": pedido,
            "offer": oferta,
        },
    )

    if (
        notificacion.recipient_id != destinatario_id
        and notificacion.notification_type != tipo
    ):
        pass

    if (
        notificacion.recipient_id != destinatario_id
        or notificacion.notification_type != tipo
    ):
        raise ValueError(
            "El identificador pertenece a otra notificacion."
        )

    return notificacion, creada




# ============================================================
# CR-15 - RESENAS DE COMPRAS VERIFICADAS
# ============================================================

from .models import ProductReview


class CR15ReviewError(ValueError):
    """Error de validacion de resenas verificadas."""
    pass


@transaction.atomic
def cr15_crear_resena(
    linea_id,
    comprador,
    estrellas,
    comentario="",
):
    """
    Permite crear una resena solamente cuando:
    - El usuario esta autenticado y activo.
    - La linea pertenece a una compra suya.
    - El pedido esta COMPLETADO.
    - La calificacion esta entre 1 y 5.
    - La linea todavia no tiene una resena.

    Se utilizan bloqueos para proteger la operacion
    frente a solicitudes concurrentes.
    """

    if (
        comprador is None
        or not comprador.is_authenticated
        or not comprador.is_active
    ):
        raise CR15ReviewError(
            "Debes iniciar sesion para valorar una compra."
        )

    if (
        not isinstance(estrellas, int)
        or isinstance(estrellas, bool)
        or not 1 <= estrellas <= 5
    ):
        raise CR15ReviewError(
            "Selecciona una calificacion de 1 a 5 estrellas."
        )

    if not isinstance(comentario, str):
        raise CR15ReviewError(
            "El comentario no es valido."
        )

    comentario = comentario.strip()

    if len(comentario) > 2000:
        raise CR15ReviewError(
            "El comentario no puede superar 2000 caracteres."
        )

    # Consultar la referencia antes de bloquear.
    referencia = (
        PurchaseLine.objects
        .filter(pk=linea_id)
        .values("order_id")
        .first()
    )

    if referencia is None:
        raise CR15ReviewError(
            "La linea de compra no existe."
        )

    # Respetar el orden de bloqueos: pedido y luego linea.
    pedido = (
        PurchaseOrder.objects
        .select_for_update()
        .get(pk=referencia["order_id"])
    )

    linea = (
        PurchaseLine.objects
        .select_for_update()
        .get(
            pk=linea_id,
            order_id=pedido.pk,
        )
    )

    if pedido.buyer_id != comprador.pk:
        raise CR15ReviewError(
            "No puedes valorar compras de otros usuarios."
        )

    if pedido.status != "COMPLETADA":
        raise CR15ReviewError(
            "Solo puedes valorar pedidos completados."
        )

    if linea.seller_id == comprador.pk:
        raise CR15ReviewError(
            "No puedes valorar tu propio producto."
        )

    if ProductReview.objects.filter(
        order_line_id=linea.pk
    ).exists():
        raise CR15ReviewError(
            "Este articulo ya fue valorado en esta compra."
        )

    resena = ProductReview.objects.create(
        order_line=linea,
        rating=estrellas,
        comment=comentario,
    )

    return resena
