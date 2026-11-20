
# ============================================================
# CR-11 - PRUEBAS FUNCIONALES DE NEGOCIACION
# ============================================================

from datetime import timedelta
from decimal import Decimal
from uuid import uuid4

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import Profile
from apps.catalog.models import Category, Product
from apps.orders.models import (
    Cart, CartItem, Offer, PurchaseOrder
)
from apps.orders.services import (
    OfferError,
    cr11_crear_oferta,
    cr11_responder_vendedor,
    cr11_responder_comprador,
)


class CR11OffersTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.buyer = User.objects.create_user(
            username="cr11_buyer",
            password="Test12345!"
        )
        cls.seller = User.objects.create_user(
            username="cr11_seller",
            password="Test12345!"
        )
        cls.other = User.objects.create_user(
            username="cr11_other",
            password="Test12345!"
        )

        for usuario in (cls.seller, cls.other):
            Profile.objects.update_or_create(
                user=usuario,
                defaults={
                    "role": "VENDEDOR",
                    "active": True,
                }
            )

        cls.category = Category.objects.create(
            name="Componentes CR11",
            active=True,
        )

        cls.product = Product.objects.create(
            seller=cls.seller,
            category=cls.category,
            name="Procesador usado CR11",
            description="Producto de prueba",
            brand="Marca de prueba",
            price=Decimal("100.00"),
            stock=3,
            condition="USADO",
            approval_status="APROBADO",
            active=True,
        )

    def crear(self):
        return cr11_crear_oferta(
            self.product.pk,
            self.buyer,
            "80.00",
        )

    def test_crear_oferta_no_descuenta_stock(self):
        oferta = self.crear()

        self.assertEqual(oferta.status, "PENDIENTE")
        self.assertEqual(
            oferta.offered_price, Decimal("80.00")
        )

        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 3)

    def test_no_permite_ofertar_producto_nuevo(self):
        self.product.condition = "NUEVO"
        self.product.save(update_fields=["condition"])

        with self.assertRaises(OfferError):
            self.crear()

    def test_prohibe_ofertas_duplicadas_y_propias(self):
        self.crear()

        with self.assertRaises(OfferError):
            self.crear()

        with self.assertRaises(OfferError):
            cr11_crear_oferta(
                self.product.pk, self.seller, "70.00"
            )

    def test_vendedor_acepta_y_rechaza(self):
        oferta = self.crear()

        with self.assertRaises(OfferError):
            cr11_responder_vendedor(
                oferta.pk, self.other, "ACEPTAR"
            )

        cr11_responder_vendedor(
            oferta.pk, self.seller, "ACEPTAR"
        )
        oferta.refresh_from_db()

        self.assertEqual(oferta.status, "ACEPTADA")
        self.assertEqual(
            oferta.agreed_price, Decimal("80.00")
        )

        with self.assertRaises(OfferError):
            cr11_responder_vendedor(
                oferta.pk, self.seller, "RECHAZAR"
            )

    def test_contraoferta_y_aceptacion(self):
        oferta = self.crear()

        cr11_responder_vendedor(
            oferta.pk, self.seller,
            "CONTRAOFERTAR", "90.00"
        )

        oferta.refresh_from_db()
        self.assertEqual(oferta.status, "CONTRAOFERTA")

        cr11_responder_comprador(
            oferta.pk, self.buyer, "ACEPTAR"
        )

        oferta.refresh_from_db()
        self.assertEqual(oferta.status, "ACEPTADA")
        self.assertEqual(
            oferta.agreed_price, Decimal("90.00")
        )

    def test_oferta_vencida_no_puede_aceptarse(self):
        oferta = self.crear()
        oferta.expires_at = (
            timezone.now() - timedelta(minutes=1)
        )
        oferta.save(update_fields=["expires_at"])

        with self.assertRaises(OfferError):
            cr11_responder_vendedor(
                oferta.pk, self.seller, "ACEPTAR"
            )

    def test_checkout_usa_acuerdo_solo_una_vez(self):
        oferta = self.crear()

        cr11_responder_vendedor(
            oferta.pk, self.seller, "ACEPTAR"
        )

        carrito = Cart.objects.create(user=self.buyer)
        CartItem.objects.create(
            cart=carrito,
            product=self.product,
            quantity=1,
        )

        self.client.force_login(self.buyer)

        url = reverse("orders:checkout")

        respuesta = self.client.get(url)
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(
            respuesta.context["total"],
            Decimal("80.00"),
        )

        datos = {
            "contact_name": "Comprador CR11",
            "contact_phone": "60000000",
            "province": "Chiriquí",
            "address": "Direccion de prueba",
            "comments": "",
            "checkout_token": str(uuid4()),
        }

        respuesta = self.client.post(url, datos)
        self.assertEqual(respuesta.status_code, 302)

        pedido = PurchaseOrder.objects.get(
            buyer=self.buyer
        )

        self.assertEqual(
            pedido.total, Decimal("80.00")
        )
        self.assertEqual(
            pedido.lines.get().unit_price,
            Decimal("80.00"),
        )

        oferta.refresh_from_db()
        self.assertEqual(oferta.status, "CONVERTIDA")
        self.assertEqual(oferta.order_id, pedido.pk)

        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 2)

        # Segunda compra: el acuerdo ya fue utilizado.
        CartItem.objects.create(
            cart=carrito,
            product=self.product,
            quantity=1,
        )

        datos["checkout_token"] = str(uuid4())
        respuesta = self.client.post(url, datos)

        self.assertEqual(respuesta.status_code, 302)

        pedidos = PurchaseOrder.objects.filter(
            buyer=self.buyer
        ).order_by("pk")

        self.assertEqual(pedidos.count(), 2)
        self.assertEqual(
            pedidos.last().total,
            Decimal("100.00"),
        )

        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 1)



    def test_cr13_entrega_y_retiro(self):
        from uuid import uuid4
        from django.urls import reverse
        from apps.orders.models import Cart, CartItem, PurchaseOrder

        self.client.force_login(self.buyer)

        carrito = Cart.objects.create(user=self.buyer)
        checkout_url = reverse("orders:checkout")

        modalidades = [
            ("RETIRO", "Recoger jueves a las 10 am"),
            ("ENTREGA_ACORDADA", "Entregar viernes a las 3 pm"),
        ]

        for metodo, instrucciones in modalidades:
            CartItem.objects.create(
                cart=carrito,
                product=self.product,
                quantity=1,
            )

            datos = {
                "contact_name": "Comprador CR13",
                "contact_phone": "60000000",
                "province": "Chiriquí",
                "address": "Punto de encuentro de prueba",
                "comments": "",
                "delivery_method": metodo,
                "delivery_instructions": instrucciones,
                "checkout_token": str(uuid4()),
            }

            respuesta = self.client.post(checkout_url, datos)

            self.assertEqual(respuesta.status_code, 302)

            pedido = (
                PurchaseOrder.objects
                .filter(buyer=self.buyer)
                .order_by("-pk")
                .first()
            )

            self.assertIsNotNone(pedido)
            self.assertEqual(pedido.delivery_method, metodo)
            self.assertEqual(
                pedido.delivery_instructions,
                instrucciones,
            )

            detalle = self.client.get(
                reverse("orders:pedido_detalle", args=[pedido.pk])
            )

            self.assertContains(detalle, instrucciones)

        self.assertEqual(
            PurchaseOrder.objects.filter(
                buyer=self.buyer
            ).count(),
            2,
        )

        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 1)
