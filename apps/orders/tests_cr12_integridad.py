from decimal import Decimal
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase
from django.urls import reverse
from apps.catalog.models import Category, Product
from apps.orders.models import Cart, CartItem, PurchaseOrder, PurchaseLine, StockReservation

class IntegridadCR12(TestCase):
    def setUp(self):
        if connection.vendor != "mysql" or connection.settings_dict["NAME"] != "test_mc_cr12_isolada":
            raise RuntimeError("ALTO: solo MySQL temporal CR12")
        U = get_user_model()
        self.buyer = U.objects.create_user(username="cr12_integridad_buyer")
        seller = U.objects.create_user(username="cr12_integridad_seller")
        category = Category.objects.create(name="Categoria Integridad CR12", active=True)
        self.product = Product.objects.create(seller=seller, category=category, name="CPU Integridad CR12", description="Prueba", brand="Prueba", price=Decimal("42.00"), stock=2, approval_status="APROBADO", active=True)
        self.cart = Cart.objects.create(user=self.buyer)
        CartItem.objects.create(cart=self.cart, product=self.product, quantity=1)
        self.client.force_login(self.buyer)
        self.url = reverse("orders:checkout")
        self.data = {"contact_name": "Comprador CR12", "contact_phone": "60000000", "province": "Chiriquí", "address": "Direccion de prueba"}

    def test_post_repetido_mismo_carrito(self):
        first = self.client.post(self.url, self.data)
        self.assertEqual(first.status_code, 302)
        pedido = PurchaseOrder.objects.get(buyer=self.buyer)
        self.assertEqual(first["Location"], reverse("orders:pedido_detalle", args=[pedido.pk]))
        second = self.client.post(self.url, self.data)
        self.assertEqual(second.status_code, 302)
        self.assertEqual(second["Location"], reverse("orders:cart_detail"))
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 1)
        self.assertEqual(PurchaseOrder.objects.count(), 1)
        self.assertEqual(PurchaseLine.objects.count(), 1)
        self.assertEqual(StockReservation.objects.filter(status="ACTIVA").count(), 1)
        self.assertEqual(CartItem.objects.filter(cart=self.cart).count(), 0)

    def test_fallo_reserva_revierte_transaccion(self):
        with patch("apps.orders.stock_services.reserve_order_lines", side_effect=RuntimeError("fallo simulado CR12")):
            with self.assertRaises(RuntimeError):
                self.client.post(self.url, self.data)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 2)
        self.assertEqual(PurchaseOrder.objects.count(), 0)
        self.assertEqual(PurchaseLine.objects.count(), 0)
        self.assertEqual(StockReservation.objects.count(), 0)
        self.assertEqual(CartItem.objects.filter(cart=self.cart).count(), 1)
