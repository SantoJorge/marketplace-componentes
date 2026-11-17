"""CR-12.8: locking de producto, categoría y vendedor durante checkout.

Ejecutar solo con --settings=config.settings_cr12_mysql_test.
Esta prueba usa la base efímera test_mc_cr12_isolada.
"""

from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
from decimal import Decimal
from threading import Event
from unittest.mock import patch
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.db import connection, connections
from django.test import Client, TransactionTestCase
from django.urls import reverse

from apps.catalog.models import Category, Product
from apps.orders.models import Cart, CartItem, PurchaseOrder, StockReservation
from apps.orders.stock_services import reserve_order_lines as reserva_real


class DisponibilidadConcurrenteCR12(TransactionTestCase):
    """Confirma que los cambios de disponibilidad respetan el checkout."""

    def setUp(self):
        if (
            connection.vendor != "mysql"
            or connection.settings_dict["NAME"] != "test_mc_cr12_isolada"
        ):
            raise RuntimeError("ALTO: las pruebas CR12 exigen MySQL aislado")

        User = get_user_model()
        self.seller = User.objects.create_user(username="cr12_disp_vendedor")
        self.buyer = User.objects.create_user(username="cr12_disp_comprador")
        self.category = Category.objects.create(name="Categoria Disponibilidad CR12", active=True)
        self.product = Product.objects.create(
            seller=self.seller,
            category=self.category,
            name="CPU Disponibilidad CR12",
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

    def _checkout(self):
        connections.close_all()
        try:
            client = Client()
            client.force_login(type(self.buyer).objects.get(pk=self.buyer.pk))
            response = client.post(self.url, self.payload)
            return response.status_code, response.get("Location", "")
        finally:
            connections.close_all()

    def _actualizar(self, modelo, pk, campo, inicio):
        connections.close_all()
        try:
            inicio.set()
            return modelo.objects.filter(pk=pk).update(**{campo: False})
        finally:
            connections.close_all()

    def _probar_bloqueo(self, modelo, pk, campo, etiqueta):
        reserva_alcanzada = Event()
        liberar_checkout = Event()
        inicio_actualizacion = Event()

        def reservar_y_pausar(pedido):
            reserva_real(pedido)
            reserva_alcanzada.set()
            if not liberar_checkout.wait(timeout=20):
                raise RuntimeError("CR12: no se libero la pausa de la prueba")

        with patch("apps.orders.stock_services.reserve_order_lines", side_effect=reservar_y_pausar):
            with ThreadPoolExecutor(max_workers=2) as pool:
                checkout_fut = pool.submit(self._checkout)
                try:
                    self.assertTrue(
                        reserva_alcanzada.wait(timeout=12),
                        "El checkout no alcanzo la reserva dentro de la transaccion",
                    )
                    actualizacion_fut = pool.submit(
                        self._actualizar, modelo, pk, campo, inicio_actualizacion
                    )
                    self.assertTrue(
                        inicio_actualizacion.wait(timeout=8),
                        "No se inicio la desactivacion concurrente",
                    )
                    # Sin el bloqueo adecuado, el UPDATE administrativo termina
                    # antes de que se confirme el checkout.
                    with self.assertRaises(
                        FutureTimeout,
                        msg=f"No se bloqueo la desactivacion de {etiqueta}",
                    ):
                        actualizacion_fut.result(timeout=0.5)
                finally:
                    liberar_checkout.set()
                status, destino = checkout_fut.result(timeout=20)
                actualizados = actualizacion_fut.result(timeout=20)

        self.assertEqual(actualizados, 1)
        pedido = PurchaseOrder.objects.get()
        self.assertEqual((status, destino), (302, reverse("orders:pedido_detalle", args=[pedido.pk])))
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 1)
        self.assertEqual(StockReservation.objects.count(), 1)
        self.assertEqual(CartItem.objects.filter(cart=self.cart).count(), 0)
        self.assertFalse(getattr(modelo.objects.get(pk=pk), campo))
        print(f"CR12 BLOQUEO {etiqueta}: pedido=1, reserva=1, stock=1, desactivacion posterior=OK")

    def test_categoria_no_se_desactiva_a_mitad_checkout(self):
        self._probar_bloqueo(Category, self.category.pk, "active", "categoria")

    def test_vendedor_no_se_desactiva_a_mitad_checkout(self):
        self._probar_bloqueo(type(self.seller), self.seller.pk, "is_active", "vendedor")

    def test_producto_no_se_desactiva_a_mitad_checkout(self):
        self._probar_bloqueo(Product, self.product.pk, "active", "producto")

    def _probar_desactivacion_previa(self, modelo, pk, campo):
        modelo.objects.filter(pk=pk).update(**{campo: False})
        status, destino = self._checkout()
        self.product.refresh_from_db()
        self.assertEqual((status, destino), (302, reverse("orders:cart_detail")))
        self.assertEqual(self.product.stock, 2)
        self.assertEqual(PurchaseOrder.objects.count(), 0)
        self.assertEqual(StockReservation.objects.count(), 0)
        self.assertEqual(CartItem.objects.filter(cart=self.cart).count(), 1)

    def test_categoria_inactiva_rechazada_por_checkout_http(self):
        self._probar_desactivacion_previa(Category, self.category.pk, "active")

    def test_vendedor_inactivo_rechazado_por_checkout_http(self):
        self._probar_desactivacion_previa(type(self.seller), self.seller.pk, "is_active")

    def test_producto_inactivo_rechazado_por_checkout_http(self):
        self._probar_desactivacion_previa(Product, self.product.pk, "active")
