"""Pruebas aisladas de CR-09; no deben ejecutarse contra la base real."""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import transaction
from django.test import TestCase, override_settings
from django.utils import timezone

from apps.catalog.models import Category, Product
from .models import PurchaseOrder, PurchaseLine, StockMovement, StockReservation
from .stock_services import (
    StockIntegrityError, reserve_order_lines, release_order_stock,
    consume_shipped_line,
)


class ReservationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        U = get_user_model()
        cls.buyer = U.objects.create_user(username="cr09_buyer", password="pass")
        cls.seller = U.objects.create_user(username="cr09_seller", password="pass")
        cls.cat = Category.objects.create(name="Procesadores", active=True)
        cls.product = Product.objects.create(
            seller=cls.seller, category=cls.cat, name="CPU CR09", description="CPU",
            brand="Prueba", price=Decimal("42.00"), stock=8,
            approval_status="APROBADO", active=True,
        )

    def order(self):
        order = PurchaseOrder.objects.create(
            buyer=self.buyer, status="PENDIENTE_PAGO", contact_name="Test",
            contact_phone="60000000", province="Chiriqui", address="Prueba",
            total=Decimal("84.00"),
        )
        line = PurchaseLine.objects.create(
            order=order, product=self.product, seller=self.seller,
            product_name=self.product.name, unit_price=self.product.price,
            quantity=2,
        )
        Product.objects.filter(pk=self.product.pk).update(stock=6)  # checkout ya descontó
        return order, line

    def test_reserve_does_not_discount_twice(self):
        order, line = self.order()
        with transaction.atomic():
            reserve_order_lines(order)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 6)
        self.assertEqual(line.stock_reservation.status, "ACTIVA")
        self.assertEqual(StockMovement.objects.get(order=order).quantity_change, -2)

    def test_release_once_and_audit(self):
        order, line = self.order()
        with transaction.atomic():
            reserve_order_lines(order)
            release_order_stock(order)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 8)
        self.assertEqual(StockReservation.objects.get(line=line).status, "LIBERADA")
        with self.assertRaises(StockIntegrityError):
            with transaction.atomic():
                release_order_stock(order)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 8)

    def test_consumption_does_not_discount_again(self):
        order, line = self.order()
        with transaction.atomic():
            reserve_order_lines(order)
            consume_shipped_line(line)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 6)
        self.assertEqual(StockReservation.objects.get(line=line).status, "CONSUMIDA")
        self.assertTrue(StockMovement.objects.filter(order=order, movement_type="CONSUMO", quantity_change=0).exists())

    def test_prevents_partial_reservation_restore(self):
        order, line = self.order()
        second = PurchaseLine.objects.create(
            order=order, product=self.product, seller=self.seller,
            product_name=self.product.name, unit_price=self.product.price,
            quantity=1,
        )
        with transaction.atomic():
            StockReservation.objects.create(
                line=line, product=self.product, quantity=2,
                expires_at=timezone.now(), status="ACTIVA",
            )
        with self.assertRaises(StockIntegrityError):
            with transaction.atomic():
                release_order_stock(order)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 6)
