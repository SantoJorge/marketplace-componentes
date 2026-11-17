"""CR-12: regresion del flujo administrativo de pedidos historicos.

Ejecutar exclusivamente con:
    python manage.py test apps.orders.tests_cr12_legacy_admin --settings=config.settings_cr12_mysql_test --noinput
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase

from apps.catalog.models import Category, Product
from apps.orders.models import PurchaseLine, PurchaseOrder
from apps.orders.services import OrderStateError, allowed_order_targets, transition_order


class LegacyAdminTransitionsCR12(TestCase):
    def setUp(self):
        if (
            connection.vendor != "mysql"
            or connection.settings_dict["NAME"] != "test_mc_cr12_isolada"
        ):
            raise RuntimeError("ALTO: esta prueba requiere MySQL aislado CR12")

        U = get_user_model()
        self.admin = U.objects.create_superuser(
            username="cr12_legacy_admin", email="admin-cr12@test.invalid", password="test"
        )
        self.buyer = U.objects.create_user(username="cr12_legacy_buyer")
        self.seller = U.objects.create_user(username="cr12_legacy_seller")
        category = Category.objects.create(name="Categoria Legacy CR12", active=True)
        self.product = Product.objects.create(
            seller=self.seller,
            category=category,
            name="CPU Legacy CR12",
            description="Prueba",
            brand="Test",
            price=Decimal("20.00"),
            stock=3,
            approval_status="APROBADO",
            active=True,
        )
        self.order = PurchaseOrder.objects.create(
            buyer=self.buyer,
            status="PENDIENTE",
            contact_name="Legacy CR12",
            contact_phone="60000000",
            province="Chiriquí",
            address="Prueba",
            total=Decimal("40.00"),
        )
        self.line = PurchaseLine.objects.create(
            order=self.order,
            product=self.product,
            seller=self.seller,
            product_name=self.product.name,
            unit_price=self.product.price,
            quantity=2,
            status="PENDIENTE",
        )

    def test_admin_ve_transiciones_legacy(self):
        opciones = dict(allowed_order_targets(self.order, self.admin))
        self.assertIn("EN_PROCESO", opciones)
        self.assertIn("CANCELADO", opciones)

    def test_pendiente_pasa_a_en_proceso(self):
        transition_order(self.order.pk, "EN_PROCESO", self.admin)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, "EN_PROCESO")

    def test_en_proceso_pasa_a_completado_con_entrega(self):
        self.order.status = "EN_PROCESO"
        self.order.save(update_fields=["status"])
        self.line.status = "ENTREGADO"
        self.line.save(update_fields=["status"])
        transition_order(self.order.pk, "COMPLETADO", self.admin)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, "COMPLETADO")

    def test_cancelado_legacy_restituye_stock_una_vez(self):
        transition_order(self.order.pk, "CANCELADO", self.admin)
        self.order.refresh_from_db()
        self.product.refresh_from_db()
        self.assertEqual(self.order.status, "CANCELADO")
        self.assertEqual(self.product.stock, 5)
        with self.assertRaises(OrderStateError):
            transition_order(self.order.pk, "CANCELADO", self.admin)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 5)
