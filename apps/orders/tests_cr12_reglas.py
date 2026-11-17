from decimal import Decimal
from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import F
from django.test import TestCase
from apps.catalog.models import Product, Category
from apps.catalog.views import available_products

class ReglasCR12(TestCase):
    def setUp(self):
        self.seller = get_user_model().objects.create_user(username="vendedor_reglas_cr12")
        self.category = Category.objects.create(name="Categoria Reglas CR12", active=True)
        self.product = Product.objects.create(seller=self.seller, category=self.category, name="CPU Reglas CR12", description="Prueba", brand="Prueba", price=Decimal("42.00"), stock=1, approval_status="APROBADO", active=True)

    def intentar_compra(self):
        with transaction.atomic():
            if not available_products().filter(pk=self.product.pk).exists():
                return False
            return Product.objects.filter(pk=self.product.pk, stock__gte=1, active=True, approval_status="APROBADO").update(stock=F("stock") - 1) == 1

    def test_compra_valida(self):
        self.assertTrue(self.intentar_compra())
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 0)

    def test_categoria_inactiva(self):
        self.category.active = False
        self.category.save(update_fields=["active"])
        self.assertFalse(self.intentar_compra())
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 1)

    def test_vendedor_inactivo(self):
        self.seller.is_active = False
        self.seller.save(update_fields=["is_active"])
        self.assertFalse(self.intentar_compra())
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 1)

    def test_producto_inactivo(self):
        self.product.active = False
        self.product.save(update_fields=["active"])
        self.assertFalse(self.intentar_compra())

    def test_producto_no_aprobado(self):
        self.product.approval_status = "RECHAZADO"
        self.product.save(update_fields=["approval_status"])
        self.assertFalse(self.intentar_compra())

    def test_producto_agotado(self):
        self.product.stock = 0
        self.product.save(update_fields=["stock"])
        self.assertFalse(self.intentar_compra())
