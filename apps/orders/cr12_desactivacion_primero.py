"""CR-12.9: administración toma el bloqueo antes del checkout.

Ejecutar SOLO con --settings=config.settings_cr12_mysql_test.
Usa la base temporal test_mc_cr12_isolada.
"""

from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
from decimal import Decimal
from threading import Event
from unittest.mock import patch
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.db import connection, connections, transaction
from django.test import Client, TransactionTestCase
from django.urls import reverse

from apps.catalog.models import Category, Product
from apps.orders.models import Cart, CartItem, PurchaseLine, PurchaseOrder, StockReservation
from apps.orders.views import get_market_cart as obtener_carrito_real


class DesactivacionPrimeroCR12(TransactionTestCase):
    """Rechaza la compra si la desactivación se confirma antes de tomar los bloqueos."""

    def setUp(self):
        if (
            connection.vendor != "mysql"
            or connection.settings_dict["NAME"] != "test_mc_cr12_isolada"
        ):
            raise RuntimeError("ALTO: solo base MySQL temporal CR12")

        User = get_user_model()
        self.seller = User.objects.create_user(username="cr12_inverso_seller")
        self.buyer = User.objects.create_user(username="cr12_inverso_buyer")
        self.category = Category.objects.create(name="Categoria Inversa CR12", active=True)
        self.product = Product.objects.create(
            seller=self.seller,
            category=self.category,
            name="CPU Inversa CR12",
            description="Prueba",
            brand="Prueba",
            price=Decimal("42.00"),
            stock=2,
            approval_status="APROBADO",
            active=True,
        )
        self.cart = Cart.objects.create(user=self.buyer)
        CartItem.objects.create(cart=self.cart, product=self.product, quantity=1)
        self.url = reverse("orders:checkout")
        self.payload = {
            "contact_name": "Comprador CR12",
            "contact_phone": "60000000",
            "province": "Chiriquí",
            "address": "Prueba",
            "checkout_token": str(uuid4()),
        }

    def _probar_desactivacion_primero(self, modelo, pk, campo, etiqueta):
        desactivada_sin_commit = Event()
        permitir_commit = Event()
        checkout_llego_al_carrito = Event()

        def desactivar():
            connections.close_all()
            try:
                with transaction.atomic():
                    objeto = modelo.objects.select_for_update().get(pk=pk)
                    setattr(objeto, campo, False)
                    objeto.save(update_fields=[campo])
                    desactivada_sin_commit.set()
                    if not permitir_commit.wait(timeout=20):
                        raise RuntimeError("CR12: no se autorizo el commit de desactivacion")
                return True
            finally:
                connections.close_all()

        def observar_carrito(request):
            cart = obtener_carrito_real(request)
            checkout_llego_al_carrito.set()
            return cart

        def realizar_checkout():
            connections.close_all()
            try:
                client = Client()
                client.force_login(type(self.buyer).objects.get(pk=self.buyer.pk))
                response = client.post(self.url, self.payload)
                return response.status_code, response.get("Location", "")
            finally:
                connections.close_all()

        with patch("apps.orders.views.get_market_cart", side_effect=observar_carrito):
            with ThreadPoolExecutor(max_workers=2) as pool:
                admin_future = pool.submit(desactivar)
                try:
                    self.assertTrue(
                        desactivada_sin_commit.wait(timeout=12),
                        f"No se obtuvo el bloqueo de {etiqueta}",
                    )
                    checkout_future = pool.submit(realizar_checkout)
                    self.assertTrue(
                        checkout_llego_al_carrito.wait(timeout=12),
                        "El checkout no alcanzo la lectura del carrito",
                    )
                    with self.assertRaises(
                        FutureTimeout,
                        msg=f"El checkout no espero al commit de {etiqueta}",
                    ):
                        checkout_future.result(timeout=0.5)
                finally:
                    permitir_commit.set()
                self.assertTrue(admin_future.result(timeout=20))
                estado, destino = checkout_future.result(timeout=20)

        self.product.refresh_from_db()
        self.assertFalse(getattr(modelo.objects.get(pk=pk), campo))
        self.assertEqual((estado, destino), (302, reverse("orders:cart_detail")))
        self.assertEqual(self.product.stock, 2)
        self.assertEqual(PurchaseOrder.objects.count(), 0)
        self.assertEqual(PurchaseLine.objects.count(), 0)
        self.assertEqual(StockReservation.objects.count(), 0)
        self.assertEqual(CartItem.objects.filter(cart=self.cart).count(), 1)
        print(f"CR12 DESACTIVACION PRIMERO {etiqueta}: compra rechazada, stock=2, pedidos=0, reservas=0")

    def test_categoria_desactivada_antes_del_bloqueo_checkout(self):
        self._probar_desactivacion_primero(Category, self.category.pk, "active", "categoria")

    def test_producto_desactivado_antes_del_bloqueo_checkout(self):
        self._probar_desactivacion_primero(Product, self.product.pk, "active", "producto")

    def test_vendedor_desactivado_antes_del_bloqueo_checkout(self):
        self._probar_desactivacion_primero(type(self.seller), self.seller.pk, "is_active", "vendedor")
