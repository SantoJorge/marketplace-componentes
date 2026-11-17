from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from threading import Barrier
from uuid import uuid4
from django.contrib.auth import get_user_model
from django.db import connection, connections
from django.test import Client, TransactionTestCase
from django.urls import reverse
from apps.catalog.models import Category, Product
from apps.orders.models import Cart, CartItem, PurchaseOrder, PurchaseLine, StockReservation

class TokenConcurrenteCR12(TransactionTestCase):
    def test_dos_post_simultaneos_mismo_token(self):
        if connection.vendor != "mysql" or connection.settings_dict["NAME"] != "test_mc_cr12_isolada":
            raise RuntimeError("ALTO: se requiere MySQL aislado CR12")
        U = get_user_model()
        buyer = U.objects.create_user(username="cr12_token_buyer")
        seller = U.objects.create_user(username="cr12_token_seller")
        category = Category.objects.create(name="Categoria Token CR12", active=True)
        product = Product.objects.create(seller=seller, category=category, name="CPU Token CR12", description="Prueba", brand="Prueba", price=Decimal("42.00"), stock=2, approval_status="APROBADO", active=True)
        cart = Cart.objects.create(user=buyer)
        CartItem.objects.create(cart=cart, product=product, quantity=1)
        token = str(uuid4())
        data = {"contact_name":"Prueba CR12","contact_phone":"60000000","province":"Chiriquí","address":"Prueba","checkout_token":token}
        url = reverse("orders:checkout")
        gate = Barrier(2)

        def worker(_):
            connections.close_all()
            try:
                client = Client(raise_request_exception=False)
                client.force_login(U.objects.get(pk=buyer.pk))
                gate.wait(timeout=30)
                response = client.post(url, data)
                return response.status_code, response.get("Location", "")
            except Exception as exc:
                return 0, repr(exc)
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(worker, range(2)))
        product.refresh_from_db()
        print("CR12 TOKEN SIMULTANEO:", results)
        print("STOCK:", product.stock, "PEDIDOS:", PurchaseOrder.objects.count(), "RESERVAS:", StockReservation.objects.count())
        self.assertEqual(PurchaseOrder.objects.count(), 1)
        order = PurchaseOrder.objects.get()
        destination = reverse("orders:pedido_detalle", args=[order.pk])
        self.assertCountEqual(results, [(302, destination), (302, destination)])
        self.assertEqual(PurchaseLine.objects.count(), 1)
        self.assertEqual(StockReservation.objects.filter(status="ACTIVA").count(), 1)
        self.assertEqual(StockReservation.objects.count(), 1)
        self.assertEqual(product.stock, 1)
        self.assertEqual(CartItem.objects.filter(cart=cart).count(), 0)
