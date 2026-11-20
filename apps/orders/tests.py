
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
from django.db import transaction
from django.core.files.uploadedfile import SimpleUploadedFile

from apps.accounts.models import Profile
from apps.catalog.models import Category, Product
from apps.orders.models import (
    Cart,
    CartItem,
    Offer,
    PurchaseOrder,
    PaymentReceipt,
    Notification,
)
from apps.orders.services import (
    OfferError,
    cr11_crear_oferta,
    cr11_responder_vendedor,
    cr11_responder_comprador,
    cr14_notificar,
)


class CR11OffersTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.buyer = User.objects.create_user(
            username="cr11_buyer",
            password="Test12345!",
        )
        cls.seller = User.objects.create_user(
            username="cr11_seller",
            password="Test12345!",
        )
        cls.other = User.objects.create_user(
            username="cr11_other",
            password="Test12345!",
        )

        for usuario in (cls.seller, cls.other):
            Profile.objects.update_or_create(
                user=usuario,
                defaults={
                    "role": "VENDEDOR",
                    "active": True,
                },
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
            oferta.offered_price,
            Decimal("80.00"),
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
                self.product.pk,
                self.seller,
                "70.00",
            )

    def test_vendedor_acepta_y_rechaza(self):
        oferta = self.crear()

        with self.assertRaises(OfferError):
            cr11_responder_vendedor(
                oferta.pk,
                self.other,
                "ACEPTAR",
            )

        cr11_responder_vendedor(
            oferta.pk,
            self.seller,
            "ACEPTAR",
        )

        oferta.refresh_from_db()

        self.assertEqual(oferta.status, "ACEPTADA")
        self.assertEqual(
            oferta.agreed_price,
            Decimal("80.00"),
        )

        with self.assertRaises(OfferError):
            cr11_responder_vendedor(
                oferta.pk,
                self.seller,
                "RECHAZAR",
            )

    def test_contraoferta_y_aceptacion(self):
        oferta = self.crear()

        cr11_responder_vendedor(
            oferta.pk,
            self.seller,
            "CONTRAOFERTAR",
            "90.00",
        )

        oferta.refresh_from_db()
        self.assertEqual(oferta.status, "CONTRAOFERTA")

        cr11_responder_comprador(
            oferta.pk,
            self.buyer,
            "ACEPTAR",
        )

        oferta.refresh_from_db()

        self.assertEqual(oferta.status, "ACEPTADA")
        self.assertEqual(
            oferta.agreed_price,
            Decimal("90.00"),
        )

    def test_oferta_vencida_no_puede_aceptarse(self):
        oferta = self.crear()

        oferta.expires_at = (
            timezone.now() - timedelta(minutes=1)
        )
        oferta.save(update_fields=["expires_at"])

        with self.assertRaises(OfferError):
            cr11_responder_vendedor(
                oferta.pk,
                self.seller,
                "ACEPTAR",
            )

    def test_checkout_usa_acuerdo_solo_una_vez(self):
        oferta = self.crear()

        cr11_responder_vendedor(
            oferta.pk,
            self.seller,
            "ACEPTAR",
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
            buyer=self.buyer,
        )

        self.assertEqual(
            pedido.total,
            Decimal("80.00"),
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
            buyer=self.buyer,
        ).order_by("pk")

        self.assertEqual(pedidos.count(), 2)
        self.assertEqual(
            pedidos.last().total,
            Decimal("100.00"),
        )

        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 1)

    # ========================================================
    # CR-13 - ENTREGA ACORDADA Y RETIRO
    # ========================================================

    def test_cr13_entrega_y_retiro(self):
        self.client.force_login(self.buyer)

        carrito = Cart.objects.create(user=self.buyer)
        checkout_url = reverse("orders:checkout")

        modalidades = [
            ("RETIRO", "Recoger jueves a las 10 am"),
            (
                "ENTREGA_ACORDADA",
                "Entregar viernes a las 3 pm",
            ),
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

            respuesta = self.client.post(
                checkout_url,
                datos,
            )

            self.assertEqual(
                respuesta.status_code,
                302,
            )

            pedido = (
                PurchaseOrder.objects
                .filter(buyer=self.buyer)
                .order_by("-pk")
                .first()
            )

            self.assertIsNotNone(pedido)
            self.assertEqual(
                pedido.delivery_method,
                metodo,
            )
            self.assertEqual(
                pedido.delivery_instructions,
                instrucciones,
            )

            detalle = self.client.get(
                reverse(
                    "orders:pedido_detalle",
                    args=[pedido.pk],
                )
            )

            self.assertContains(
                detalle,
                instrucciones,
            )

        self.assertEqual(
            PurchaseOrder.objects.filter(
                buyer=self.buyer,
            ).count(),
            2,
        )

        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 1)


# ============================================================
# CR-14 - PRUEBAS DE NOTIFICACIONES
# ============================================================

class CR14NotificationTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.buyer = User.objects.create_user(
            username="cr14_buyer",
            password="Test12345!",
        )

        cls.seller = User.objects.create_user(
            username="cr14_seller",
            password="Test12345!",
        )

        cls.other = User.objects.create_user(
            username="cr14_other",
            password="Test12345!",
        )

        Profile.objects.update_or_create(
            user=cls.seller,
            defaults={
                "role": "VENDEDOR",
                "active": True,
            },
        )

        cls.category = Category.objects.create(
            name="Componentes CR14",
            active=True,
        )

        cls.product = Product.objects.create(
            seller=cls.seller,
            category=cls.category,
            name="Procesador CR14",
            description="Producto de prueba",
            brand="Prueba",
            price=Decimal("100.00"),
            stock=3,
            condition="USADO",
            approval_status="APROBADO",
            active=True,
        )

    def crear_aviso(self, recipient, clave):
        return Notification.objects.create(
            recipient=recipient,
            notification_type="ESTADO_PEDIDO",
            message="Mensaje privado CR14",
            event_key=clave,
        )

    # ========================================================
    # CR-14 - OFERTAS Y CONTRAOFERTAS
    # ========================================================

    def test_oferta_y_contraoferta_notifican(self):
        oferta = cr11_crear_oferta(
            self.product.pk,
            self.buyer,
            "80.00",
        )

        inicial = Notification.objects.get(
            event_key=f"oferta:{oferta.pk}:creada",
        )

        self.assertEqual(
            inicial.recipient_id,
            self.seller.pk,
        )
        self.assertEqual(
            inicial.notification_type,
            "OFERTA_NUEVA",
        )

        cr11_responder_vendedor(
            oferta.pk,
            self.seller,
            "CONTRAOFERTAR",
            "90.00",
        )

        respuesta = Notification.objects.get(
            event_key=(
                f"oferta:{oferta.pk}:respuesta:vendedor"
            ),
        )

        self.assertEqual(
            respuesta.recipient_id,
            self.buyer.pk,
        )

        cr11_responder_comprador(
            oferta.pk,
            self.buyer,
            "ACEPTAR",
        )

        final = Notification.objects.get(
            event_key=(
                f"oferta:{oferta.pk}:respuesta:comprador"
            ),
        )

        self.assertEqual(
            final.recipient_id,
            self.seller.pk,
        )

        self.assertEqual(
            Notification.objects.count(),
            3,
        )

    # ========================================================
    # CR-14 - PREVENCION DE DUPLICADOS
    # ========================================================

    def test_evento_unico_no_duplica(self):
        datos = {
            "destinatario_id": self.buyer.pk,
            "tipo": "ESTADO_PEDIDO",
            "mensaje": "Prueba de evento unico",
            "clave": "cr14:evento:unico",
        }

        primero, creada = cr14_notificar(**datos)
        segundo, repetida = cr14_notificar(**datos)

        self.assertTrue(creada)
        self.assertFalse(repetida)

        self.assertEqual(
            primero.pk,
            segundo.pk,
        )
        self.assertEqual(
            Notification.objects.count(),
            1,
        )

        with self.assertRaises(ValueError):
            cr14_notificar(
                destinatario_id=self.other.pk,
                tipo="ESTADO_PEDIDO",
                mensaje="Intento ajeno",
                clave="cr14:evento:unico",
            )

    # ========================================================
    # CR-14 - ROLLBACK DE TRANSACCIONES
    # ========================================================

    def test_notificacion_revierte_con_transaccion(self):
        with self.assertRaises(RuntimeError):
            with transaction.atomic():
                cr14_notificar(
                    destinatario_id=self.buyer.pk,
                    tipo="ESTADO_PEDIDO",
                    mensaje="Operacion fallida",
                    clave="cr14:rollback",
                )

                raise RuntimeError("Revertir operacion")

        self.assertFalse(
            Notification.objects.filter(
                event_key="cr14:rollback",
            ).exists()
        )

    # ========================================================
    # CR-14 - AUTENTICACION Y PRIVACIDAD
    # ========================================================

    def test_autenticacion_y_privacidad(self):
        aviso = self.crear_aviso(
            self.seller,
            "cr14:privado",
        )

        lista = reverse(
            "orders:mis_notificaciones",
        )

        marcar = reverse(
            "orders:notificacion_marcar_leida",
            kwargs={"pk": aviso.pk},
        )

        self.assertEqual(
            self.client.get(lista).status_code,
            302,
        )

        self.client.force_login(self.buyer)

        respuesta = self.client.get(lista)

        self.assertEqual(
            respuesta.status_code,
            200,
        )

        self.assertNotContains(
            respuesta,
            "Mensaje privado CR14",
        )

        self.assertEqual(
            self.client.post(marcar).status_code,
            404,
        )

        aviso.refresh_from_db()
        self.assertFalse(aviso.is_read)

    # ========================================================
    # CR-14 - MARCAR UNA NOTIFICACION COMO LEIDA
    # ========================================================

    def test_marcar_como_leida_solo_por_post(self):
        aviso = self.crear_aviso(
            self.buyer,
            "cr14:lectura:individual",
        )

        ruta = reverse(
            "orders:notificacion_marcar_leida",
            kwargs={"pk": aviso.pk},
        )

        self.client.force_login(self.buyer)

        self.assertEqual(
            self.client.get(ruta).status_code,
            405,
        )

        self.assertEqual(
            self.client.post(ruta).status_code,
            302,
        )

        aviso.refresh_from_db()
        self.assertTrue(aviso.is_read)

    # ========================================================
    # CR-14 - MARCAR TODAS COMO LEIDAS
    # ========================================================

    def test_marcar_todas_respeta_propietario(self):
        self.crear_aviso(
            self.buyer,
            "cr14:todas:1",
        )

        self.crear_aviso(
            self.buyer,
            "cr14:todas:2",
        )

        ajeno = self.crear_aviso(
            self.seller,
            "cr14:todas:otro",
        )

        self.client.force_login(self.buyer)

        ruta = reverse(
            "orders:notificaciones_marcar_todas",
        )

        self.assertEqual(
            self.client.get(ruta).status_code,
            405,
        )

        self.assertEqual(
            self.client.post(ruta).status_code,
            302,
        )

        self.assertEqual(
            Notification.objects.filter(
                recipient=self.buyer,
                is_read=False,
            ).count(),
            0,
        )

        ajeno.refresh_from_db()
        self.assertFalse(ajeno.is_read)

    # ========================================================
    # CR-14 - CREAR PEDIDO REAL PARA PRUEBAS HTTP
    # ========================================================

    def _crear_pedido_cr14(self):
        self.client.force_login(self.buyer)

        carrito = Cart.objects.create(
            user=self.buyer,
        )

        CartItem.objects.create(
            cart=carrito,
            product=self.product,
            quantity=1,
        )

        datos = {
            "contact_name": "Comprador CR14",
            "contact_phone": "60000000",
            "province": "Chiriquí",
            "address": "Direccion de prueba CR14",
            "comments": "",
            "delivery_method": "RETIRO",
            "delivery_instructions": "Retiro de prueba",
            "checkout_token": str(uuid4()),
        }

        respuesta = self.client.post(
            reverse("orders:checkout"),
            datos,
        )

        self.assertEqual(
            respuesta.status_code,
            302,
        )

        pedido = PurchaseOrder.objects.get(
            buyer=self.buyer,
        )

        self.assertEqual(
            pedido.status,
            "PENDIENTE_PAGO",
        )

        return pedido

    # ========================================================
    # CR-14 - NOTIFICAR NUEVA COMPRA AL VENDEDOR
    # ========================================================

    def test_compra_notifica_al_vendedor(self):
        pedido = self._crear_pedido_cr14()

        avisos = Notification.objects.filter(
            order=pedido,
            recipient=self.seller,
            notification_type="COMPRA_NUEVA",
        )

        self.assertEqual(
            avisos.count(),
            1,
        )

        self.assertFalse(
            Notification.objects.filter(
                order=pedido,
                recipient=self.buyer,
                notification_type="COMPRA_NUEVA",
            ).exists()
        )

        self.assertEqual(
            avisos.first().event_key,
            (
                f"pedido:{pedido.pk}:compra:"
                f"vendedor:{self.seller.pk}"
            ),
        )

    # ========================================================
    # CR-14 - RECHAZO Y APROBACION DE COMPROBANTES
    # ========================================================

    def test_rechazo_y_aprobacion_pago_notifican(self):
        pedido = self._crear_pedido_cr14()

        admin = User.objects.create_superuser(
            username="cr14_admin",
            email="admin-cr14@example.com",
            password="Test12345!",
        )

        Profile.objects.update_or_create(
            user=admin,
            defaults={
                "role": "ADMINISTRADOR",
                "active": True,
            },
        )

        def subir_comprobante(nombre):
            self.client.force_login(self.buyer)

            archivo = SimpleUploadedFile(
                nombre,
                (
                    b"%PDF-1.4\n"
                    b"1 0 obj\n"
                    b"<<>>\n"
                    b"endobj\n"
                    b"%%EOF"
                ),
                content_type="application/pdf",
            )

            respuesta = self.client.post(
                reverse(
                    "orders:subir_comprobante",
                    kwargs={"pk": pedido.pk},
                ),
                {"comprobante": archivo},
            )

            self.assertEqual(
                respuesta.status_code,
                302,
            )

            pedido.refresh_from_db()

            self.assertEqual(
                pedido.status,
                "PAGO_EN_REVISION",
            )

            return (
                PaymentReceipt.objects
                .filter(order=pedido)
                .latest("pk")
            )

        def revisar_comprobante(
            comprobante,
            decision,
            motivo,
        ):
            self.client.force_login(admin)

            respuesta = self.client.post(
                reverse(
                    "orders:revisar_comprobante",
                    kwargs={
                        "pk": pedido.pk,
                        "receipt_id": comprobante.pk,
                    },
                ),
                {
                    "decision": decision,
                    "observation": motivo,
                },
            )

            self.assertEqual(
                respuesta.status_code,
                302,
            )

        # PRIMERA REVISION: PAGO RECHAZADO
        primero = subir_comprobante(
            "rechazado.pdf",
        )

        revisar_comprobante(
            primero,
            "RECHAZADO",
            "Comprobante no valido para la prueba",
        )

        pedido.refresh_from_db()

        self.assertEqual(
            pedido.status,
            "PENDIENTE_PAGO",
        )

        self.assertEqual(
            Notification.objects.filter(
                order=pedido,
                recipient=self.buyer,
                notification_type="PAGO_RECHAZADO",
            ).count(),
            1,
        )

        # SEGUNDA REVISION: PAGO APROBADO
        segundo = subir_comprobante(
            "aprobado.pdf",
        )

        revisar_comprobante(
            segundo,
            "APROBADO",
            "Pago verificado",
        )

        pedido.refresh_from_db()

        self.assertEqual(
            pedido.status,
            "PAGADA",
        )

        self.assertEqual(
            Notification.objects.filter(
                order=pedido,
                recipient=self.buyer,
                notification_type="PAGO_APROBADO",
            ).count(),
            1,
        )

        # Verificar que se conservan ambos eventos.
        self.assertEqual(
            Notification.objects.filter(
                order=pedido,
                recipient=self.buyer,
                notification_type__in=(
                    "PAGO_APROBADO",
                    "PAGO_RECHAZADO",
                ),
            ).count(),
            2,
        )
