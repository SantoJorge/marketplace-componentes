"""Pruebas rojas CR-12.7.

Simulan errores MySQL durante la reserva, luego de descontar stock y crear el
pedido dentro de transaction.atomic(). Deben ejecutarse EXCLUSIVAMENTE en
la base temporal test_mc_cr12_isolada, nunca contra la base principal.

No simulan una contencion real entre conexiones; verifican la politica de
reintento y el rollback ante codigos de error concretos.
"""

from decimal import Decimal
from unittest.mock import patch
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.db import OperationalError, connection
from django.test import TransactionTestCase
from django.urls import reverse

from apps.catalog.models import Category, Product
from apps.orders import stock_services
from apps.orders.models import Cart, CartItem, PurchaseLine, PurchaseOrder, StockReservation


class RecuperacionErroresCR12(TransactionTestCase):
    def setUp(self):
        if (
            connection.vendor != "mysql"
            or connection.settings_dict["NAME"] != "test_mc_cr12_isolada"
        ):
            raise RuntimeError("ALTO: estas pruebas requieren MySQL aislado CR12")

        user_model = get_user_model()
        self.buyer = user_model.objects.create_user(username="cr12_deadlock_buyer")
        seller = user_model.objects.create_user(username="cr12_deadlock_seller")
        category = Category.objects.create(name="Categoria Deadlock CR12", active=True)
        self.product = Product.objects.create(
            seller=seller,
            category=category,
            name="CPU Deadlock CR12",
            description="Prueba",
            brand="Prueba",
            price=Decimal("42.00"),
            stock=2,
            approval_status="APROBADO",
            active=True,
        )
        self.cart = Cart.objects.create(user=self.buyer)
        CartItem.objects.create(cart=self.cart, product=self.product, quantity=1)
        self.client.force_login(self.buyer)
        self.url = reverse("orders:checkout")
        self.data = {
            "contact_name": "Comprador CR12",
            "contact_phone": "60000000",
            "province": "Chiriquí",
            "address": "Direccion de prueba",
            "checkout_token": str(uuid4()),
        }

    def _comprobar_compra_unica(self, response):
        self.assertEqual(response.status_code, 302)
        pedido = PurchaseOrder.objects.get(buyer=self.buyer)
        self.assertEqual(
            response["Location"],
            reverse("orders:pedido_detalle", args=[pedido.pk]),
        )
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 1)
        self.assertEqual(PurchaseOrder.objects.count(), 1)
        self.assertEqual(PurchaseLine.objects.count(), 1)
        self.assertEqual(StockReservation.objects.filter(status="ACTIVA").count(), 1)
        self.assertEqual(CartItem.objects.filter(cart=self.cart).count(), 0)

    def _comprobar_reintento_tras_fallo(self, mysql_errno):
        original = stock_services.reserve_order_lines
        llamadas = {"n": 0}

        def fallo_primero(pedido):
            llamadas["n"] += 1
            if llamadas["n"] == 1:
                raise OperationalError(mysql_errno, "Error MySQL simulado CR12")
            return original(pedido)

        with patch("apps.orders.stock_services.reserve_order_lines", side_effect=fallo_primero):
            response = self.client.post(self.url, self.data)

        self.assertEqual(llamadas["n"], 2, "Se esperaba exactamente un reintento")
        self._comprobar_compra_unica(response)

    def test_deadlock_1213_reintenta_transaccion_completa(self):
        self._comprobar_reintento_tras_fallo(1213)

    def test_timeout_1205_reintenta_transaccion_completa(self):
        self._comprobar_reintento_tras_fallo(1205)

    def test_deadlock_persistente_agota_tres_intentos_sin_compra(self):
        llamadas = {"n": 0}

        def fallo_siempre(_pedido):
            llamadas["n"] += 1
            raise OperationalError(1213, "Deadlock persistente simulado CR12")

        with patch("apps.orders.stock_services.reserve_order_lines", side_effect=fallo_siempre):
            response = self.client.post(self.url, self.data)

        self.assertEqual(llamadas["n"], 3, "El limite de reintentos debe ser tres")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], reverse("orders:cart_detail"))
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 2)
        self.assertEqual(PurchaseOrder.objects.count(), 0)
        self.assertEqual(PurchaseLine.objects.count(), 0)
        self.assertEqual(StockReservation.objects.count(), 0)
        self.assertEqual(CartItem.objects.filter(cart=self.cart).count(), 1)
