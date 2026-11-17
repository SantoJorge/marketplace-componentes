"""CR-09: expire reservas de pedidos sin comprobante, por orden completa.

Por defecto es SIMULACION. Para modificar usar --apply, y ejecutar en horario
programado desde el sistema operativo si se desea expiracion automatica.
"""
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from apps.orders.models import PurchaseOrder, OrderStatusHistory, StockReservation
from apps.orders.stock_services import release_order_stock, StockIntegrityError


class Command(BaseCommand):
    help = "Simula o expira reservas vencidas de pedidos pendientes de pago."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true", help="Ejecutar cambios (sin esto, simulación)")
        parser.add_argument("--database", default="default")

    def handle(self, *args, **opts):
        alias = opts["database"]
        if alias != "default":
            raise CommandError("Configura la base destino en settings antes de ejecutar.")
        now = timezone.now()
        ids = list(StockReservation.objects.filter(
            status="ACTIVA", expires_at__lte=now,
            line__order__status="PENDIENTE_PAGO",
        ).values_list("line__order_id", flat=True).distinct())
        self.stdout.write(f"Pedidos candidatos: {len(ids)}. Modo: {'APLICAR' if opts['apply'] else 'SIMULACION'}")
        if not opts["apply"]:
            return
        processed = skipped = 0
        for oid in ids:
            try:
                with transaction.atomic():
                    order = PurchaseOrder.objects.select_for_update().get(pk=oid)
                    if order.status != "PENDIENTE_PAGO":
                        skipped += 1
                        continue
                    if order.receipts.filter(status__in=("PENDIENTE", "APROBADO")).exists():
                        skipped += 1
                        continue
                    lines = list(order.lines.select_for_update().all())
                    if not lines or any(line.status != "PENDIENTE" for line in lines):
                        skipped += 1
                        continue
                    active = list(StockReservation.objects.select_for_update().filter(line__order=order))
                    if len(active) != len(lines) or any(
                        r.status != "ACTIVA" or r.expires_at > now for r in active
                    ):
                        skipped += 1
                        continue
                    release_order_stock(order, expired=True)
                    order.status = "CANCELADA"
                    order.save(update_fields=["status", "updated_at"])
                    OrderStatusHistory.objects.create(
                        order=order, previous_status="PENDIENTE_PAGO",
                        new_status="CANCELADA", actor=None, actor_role="SISTEMA",
                        reason="Reserva vencida sin comprobante de pago",
                    )
                    processed += 1
            except (StockIntegrityError, PurchaseOrder.DoesNotExist) as exc:
                self.stderr.write(f"Pedido {oid}: {exc}")
                skipped += 1
        self.stdout.write(self.style.SUCCESS(f"Cancelados: {processed}; omitidos: {skipped}"))
