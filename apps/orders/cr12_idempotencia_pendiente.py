"""Prueba roja CR12: ejecutar solamente de forma explicita."""
from decimal import Decimal
from uuid import uuid4
from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase
from django.urls import reverse
from apps.catalog.models import Category, Product
from apps.orders.models import Cart, CartItem, PurchaseOrder, StockReservation

class IdempotenciaPendienteCR12(TestCase):
    def test_repetir_mismo_token_no_crea_otra_compra(self):
        if connection.vendor != "mysql" or connection.settings_dict["NAME"] != "test_mc_cr12_isolada":
            raise RuntimeError("ALTO: solo se permite la base CR12 aislada")
        U = get_user_model()
        buyer = U.objects.create_user(username="cr12_idem_buyer")
        seller = U.objects.create_user(username="cr12_idem_seller")
        cat = Category.objects.create(name="Categoria Idem CR12", active=True)
        product = Product.objects.create(seller=seller, category=cat, name="CPU Idem CR12", description="Prueba", brand="Prueba", price=Decimal("42.00"), stock=3, approval_status="APROBADO", active=True)
        cart = Cart.objects.create(user=buyer)
        CartItem.objects.create(cart=cart, product=product, quantity=1)
        self.client.force_login(buyer)
        token = str(uuid4())
        payload = {"contact_name": "Comprador CR12", "contact_phone": "60000000", "province": "Chiriquí", "address": "Prueba", "checkout_token": token}
        url = reverse("orders:checkout")
        first = self.client.post(url, payload)
        self.assertEqual(first.status_code, 302)
        order = PurchaseOrder.objects.get(buyer=buyer)
        self.assertEqual(first["Location"], reverse("orders:pedido_detalle", args=[order.pk]))
        CartItem.objects.create(cart=cart, product=product, quantity=1)
        second = self.client.post(url, payload)
        product.refresh_from_db()
        print("CR12 CLAVE REPETIDA: stock=", product.stock, "pedidos=", PurchaseOrder.objects.count(), "reservas=", StockReservation.objects.count())
        self.assertEqual(second.status_code, 302)
        self.assertEqual(second["Location"], reverse("orders:pedido_detalle", args=[order.pk]))
        self.assertEqual(PurchaseOrder.objects.count(), 1)
        self.assertEqual(StockReservation.objects.count(), 1)
        self.assertEqual(product.stock, 2)
