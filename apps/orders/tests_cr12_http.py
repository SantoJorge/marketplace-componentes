from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from threading import Barrier
from django.contrib.auth import get_user_model
from django.db import connection, connections
from django.test import Client, TransactionTestCase
from django.urls import reverse
from apps.catalog.models import Category, Product
from apps.orders.models import Cart, CartItem, PurchaseOrder, PurchaseLine, StockReservation

class CheckoutHTTPCR12(TransactionTestCase):
    def test_dos_compradores_http_ultima_unidad(self):
        if connection.vendor != "mysql" or str(connection.settings_dict["NAME"]) != "test_mc_cr12_isolada":
            raise RuntimeError("ALTO: solo se permite MySQL de pruebas CR12")
        U = get_user_model()
        seller = U.objects.create_user(username="cr12_http_seller")
        buyers = [U.objects.create_user(username=f"cr12_http_buyer_{i}") for i in range(2)]
        category = Category.objects.create(name="Categoria HTTP CR12", active=True)
        product = Product.objects.create(seller=seller, category=category, name="CPU HTTP CR12", description="Prueba", brand="Prueba", price=Decimal("42.00"), stock=1, approval_status="APROBADO", active=True)
        for buyer in buyers:
            cart = Cart.objects.create(user=buyer)
            CartItem.objects.create(cart=cart, product=product, quantity=1)
        gate = Barrier(2)
        data = {"contact_name": "Prueba", "contact_phone": "60000000", "province": "Chiriquí", "address": "Direccion de prueba"}
        def worker(buyer_id):
            connections.close_all()
            try:
                client = Client(raise_request_exception=False)
                client.force_login(U.objects.get(pk=buyer_id))
                gate.wait(timeout=30)
                response = client.post(reverse("orders:checkout"), data)
                return response.status_code, response.get("Location", "")
            except Exception as exc:
                return 0, repr(exc)
            finally:
                connections.close_all()
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(worker, [b.pk for b in buyers]))
        product.refresh_from_db()
        print("RESULTADOS HTTP CR12:", results)
        print("STOCK:", product.stock, "PEDIDOS:", PurchaseOrder.objects.count(), "RESERVAS:", StockReservation.objects.count())
        self.assertEqual(sorted(x[0] for x in results), [302, 302])
        self.assertEqual(PurchaseOrder.objects.count(), 1)
        self.assertEqual(PurchaseLine.objects.count(), 1)
        self.assertEqual(StockReservation.objects.filter(status="ACTIVA").count(), 1)
        self.assertEqual(product.stock, 0)
        order = PurchaseOrder.objects.get()
        self.assertCountEqual([x[1] for x in results], [reverse("orders:pedido_detalle", args=[order.pk]), reverse("orders:cart_detail")])
        self.assertEqual(CartItem.objects.count(), 1)
