"""CR12: concurrencia real en una base MySQL temporal."""
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from threading import Barrier
from django.contrib.auth import get_user_model
from django.db import connection, connections, transaction
from django.db.models import F
from django.test import TransactionTestCase
from apps.catalog.models import Category, Product
from apps.orders.models import PurchaseOrder, PurchaseLine, StockReservation
from apps.orders.stock_services import reserve_order_lines

class ConcurrenciaCR12(TransactionTestCase):
    def test_dos_compradores_ultima_unidad(self):
        nombre = str(connection.settings_dict["NAME"])
        if connection.vendor != "mysql" or not nombre.startswith("test_mc_cr12_"):
            raise RuntimeError("SEGURIDAD: prohibida la base principal")
        U = get_user_model()
        vendedor = U.objects.create_user(username="cr12_seller")
        compradores = [U.objects.create_user(username=f"cr12_buyer_{i}").pk for i in range(2)]
        categoria = Category.objects.create(name="Categoria CR12", active=True)
        producto = Product.objects.create(seller=vendedor, category=categoria, name="CPU CR12", description="Prueba", brand="Prueba", price=Decimal("42.00"), stock=1, approval_status="APROBADO", active=True)
        barrera = Barrier(2)
        def comprar(usuario_id):
            connections.close_all()
            try:
                barrera.wait(timeout=30)
                with transaction.atomic():
                    n = Product.objects.filter(pk=producto.pk, stock__gte=1, active=True, approval_status="APROBADO").update(stock=F("stock") - 1)
                    if n != 1:
                        return "SIN_STOCK", None
                    pedido = PurchaseOrder.objects.create(buyer_id=usuario_id, status="PENDIENTE_PAGO", contact_name="CR12", contact_phone="60000000", province="Chiriqui", address="Prueba", total=Decimal("42.00"))
                    PurchaseLine.objects.create(order=pedido, product=producto, seller=vendedor, product_name=producto.name, unit_price=producto.price, quantity=1)
                    reserve_order_lines(pedido)
                    return "CONFIRMADA", pedido.pk
            except Exception as error:
                return "ERROR", repr(error)
            finally:
                connections.close_all()
        with ThreadPoolExecutor(max_workers=2) as pool:
            resultados = list(pool.map(comprar, compradores))
        producto.refresh_from_db()
        conteos = Counter(estado for estado, detalle in resultados)
        print("\nCR12 resultados:", resultados, "stock:", producto.stock, "pedidos:", PurchaseOrder.objects.count(), "reservas:", StockReservation.objects.count())
        self.assertEqual(conteos["CONFIRMADA"], 1)
        self.assertEqual(conteos["SIN_STOCK"], 1)
        self.assertEqual(conteos["ERROR"], 0)
        self.assertEqual(producto.stock, 0)
        self.assertEqual(PurchaseOrder.objects.count(), 1)
        self.assertEqual(StockReservation.objects.filter(status="ACTIVA", quantity=1).count(), 1)
