
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



# ============================================================
# CR-15 - PRUEBAS DE RESENAS VERIFICADAS
# ============================================================

from apps.orders.models import PurchaseLine, ProductReview
from apps.orders.services import (
    CR15ReviewError,
    cr15_crear_resena,
)


class CR15ReviewTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.buyer = User.objects.create_user(
            username="cr15_buyer",
            password="Test12345!",
        )

        cls.seller = User.objects.create_user(
            username="cr15_seller",
            password="Test12345!",
        )

        cls.other = User.objects.create_user(
            username="cr15_other",
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
            name="Componentes CR15",
            active=True,
        )

        cls.product = Product.objects.create(
            seller=cls.seller,
            category=cls.category,
            name="Procesador CR15",
            description="Producto para pruebas",
            brand="Marca CR15",
            price=Decimal("100.00"),
            stock=3,
            condition="USADO",
            approval_status="APROBADO",
            active=True,
        )

        cls.order = PurchaseOrder.objects.create(
            buyer=cls.buyer,
            status="COMPLETADA",
            contact_name="Comprador CR15",
            contact_phone="60000000",
            province="Chiriquí",
            address="Direccion de prueba",
            total=Decimal("100.00"),
        )

        cls.line = PurchaseLine.objects.create(
            order=cls.order,
            product=cls.product,
            seller=cls.seller,
            product_name=cls.product.name,
            unit_price=Decimal("100.00"),
            quantity=1,
            status="ENTREGADO",
        )

    def test_comprador_verificado_puede_valorar(self):
        resena = cr15_crear_resena(
            self.line.pk,
            self.buyer,
            5,
            "Excelente producto",
        )

        self.assertEqual(resena.rating, 5)
        self.assertEqual(
            resena.comment,
            "Excelente producto",
        )
        self.assertEqual(
            resena.order_line_id,
            self.line.pk,
        )
        self.assertEqual(
            resena.buyer,
            self.buyer,
        )
        self.assertTrue(resena.is_verified)

        self.assertEqual(
            ProductReview.objects.count(),
            1,
        )

    def test_pedido_sin_completar_no_puede_valorarse(self):
        self.order.status = "ENTREGADA"
        self.order.save(update_fields=["status"])

        with self.assertRaises(CR15ReviewError):
            cr15_crear_resena(
                self.line.pk,
                self.buyer,
                5,
                "Pedido sin completar",
            )

        self.assertFalse(
            ProductReview.objects.exists()
        )

    def test_comprador_ajeno_no_puede_valorar(self):
        with self.assertRaises(CR15ReviewError):
            cr15_crear_resena(
                self.line.pk,
                self.other,
                4,
                "Compra de otra persona",
            )

        self.assertFalse(
            ProductReview.objects.exists()
        )

    def test_no_permite_resenas_duplicadas(self):
        primera = cr15_crear_resena(
            self.line.pk,
            self.buyer,
            5,
            "Primera valoracion",
        )

        with self.assertRaises(CR15ReviewError):
            cr15_crear_resena(
                self.line.pk,
                self.buyer,
                1,
                "Segunda valoracion",
            )

        self.assertEqual(
            ProductReview.objects.count(),
            1,
        )

        primera.refresh_from_db()
        self.assertEqual(primera.rating, 5)

    def test_rechaza_calificaciones_y_comentarios_invalidos(self):
        for estrellas in (0, 6, -1, True, "5"):
            with self.subTest(estrellas=estrellas):
                with self.assertRaises(CR15ReviewError):
                    cr15_crear_resena(
                        self.line.pk,
                        self.buyer,
                        estrellas,
                        "Prueba",
                    )

        with self.assertRaises(CR15ReviewError):
            cr15_crear_resena(
                self.line.pk,
                self.buyer,
                5,
                "A" * 2001,
            )

        self.assertEqual(
            ProductReview.objects.count(),
            0,
        )



    # ========================================================
    # CR-15 - PRUEBAS HTTP E INTERFAZ PUBLICA
    # ========================================================

    def test_http_publicar_y_mostrar_resena(self):
        self.client.force_login(self.buyer)

        url = reverse(
            "orders:resena_publicar",
            kwargs={"linea_id": self.line.pk},
        )

        respuesta = self.client.post(
            url,
            {
                "rating": "5",
                "comment": "Excelente procesador CR15 HTTP",
            },
        )

        self.assertEqual(respuesta.status_code, 302)

        resena = ProductReview.objects.get(
            order_line=self.line,
        )

        self.assertEqual(resena.rating, 5)
        self.assertEqual(
            resena.comment,
            "Excelente procesador CR15 HTTP",
        )

        # Las reseñas deben ser visibles públicamente.
        self.client.logout()

        respuesta = self.client.get(
            reverse(
                "catalog:producto",
                kwargs={"pk": self.product.pk},
            )
        )

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(
            respuesta,
            "Excelente procesador CR15 HTTP",
        )
        self.assertContains(
            respuesta,
            "Compra verificada",
        )
        self.assertContains(
            respuesta,
            "Valoraciones de compradores",
        )

    def test_http_bloquea_anonimos_y_compradores_ajenos(self):
        url = reverse(
            "orders:resena_publicar",
            kwargs={"linea_id": self.line.pk},
        )

        datos = {
            "rating": "4",
            "comment": "Intento no autorizado",
        }

        # Sin iniciar sesion.
        respuesta = self.client.post(url, datos)
        self.assertEqual(respuesta.status_code, 302)

        # Usuario que no compro el producto.
        self.client.force_login(self.other)

        respuesta = self.client.post(url, datos)
        self.assertEqual(respuesta.status_code, 302)

        self.assertFalse(
            ProductReview.objects.exists()
        )

        # Un GET no puede publicar una valoracion.
        self.client.force_login(self.buyer)

        respuesta = self.client.get(url)
        self.assertEqual(respuesta.status_code, 405)

        self.assertFalse(
            ProductReview.objects.exists()
        )

    def test_http_rechaza_pedido_incompleto_y_duplicados(self):
        self.client.force_login(self.buyer)

        url = reverse(
            "orders:resena_publicar",
            kwargs={"linea_id": self.line.pk},
        )

        self.order.status = "ENTREGADA"
        self.order.save(update_fields=["status"])

        datos = {
            "rating": "5",
            "comment": "Primera reseña HTTP",
        }

        respuesta = self.client.post(url, datos)
        self.assertEqual(respuesta.status_code, 302)

        self.assertEqual(
            ProductReview.objects.count(),
            0,
        )

        # El comprador completa el pedido.
        self.order.status = "COMPLETADA"
        self.order.save(update_fields=["status"])

        respuesta = self.client.post(url, datos)
        self.assertEqual(respuesta.status_code, 302)

        self.assertEqual(
            ProductReview.objects.count(),
            1,
        )

        # Intentar publicar otra vez.
        respuesta = self.client.post(
            url,
            {
                "rating": "1",
                "comment": "Intento duplicado",
            },
        )

        self.assertEqual(respuesta.status_code, 302)

        self.assertEqual(
            ProductReview.objects.count(),
            1,
        )

        resena = ProductReview.objects.get(
            order_line=self.line,
        )

        self.assertEqual(resena.rating, 5)
        self.assertEqual(
            resena.comment,
            "Primera reseña HTTP",
        )

    def test_formulario_solo_en_pedido_completado(self):
        self.client.force_login(self.buyer)

        url = reverse(
            "orders:pedido_detalle",
            kwargs={"pk": self.order.pk},
        )

        # Pedido completado: aparece el formulario.
        respuesta = self.client.get(url)

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(
            respuesta,
            'id="cr15-valoraciones"',
        )

        # Pedido sin completar: no aparece.
        self.order.status = "ENTREGADA"
        self.order.save(update_fields=["status"])

        respuesta = self.client.get(url)

        self.assertEqual(respuesta.status_code, 200)
        self.assertNotContains(
            respuesta,
            'id="cr15-valoraciones"',
        )

        # Pedido completado y valorado:
        # se muestra la reseña, no otro formulario.
        self.order.status = "COMPLETADA"
        self.order.save(update_fields=["status"])

        cr15_crear_resena(
            self.line.pk,
            self.buyer,
            4,
            "Producto recibido correctamente",
        )

        respuesta = self.client.get(url)

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(
            respuesta,
            "Ya valoraste este producto",
        )
        self.assertContains(
            respuesta,
            "Producto recibido correctamente",
        )

    def test_resena_no_aparece_en_otro_producto(self):
        otro_producto = Product.objects.create(
            seller=self.seller,
            category=self.category,
            name="Memoria RAM distinta CR15",
            description="Otro producto de prueba",
            brand="Marca CR15",
            price=Decimal("50.00"),
            stock=3,
            condition="USADO",
            approval_status="APROBADO",
            active=True,
        )

        cr15_crear_resena(
            self.line.pk,
            self.buyer,
            5,
            "Comentario exclusivo del procesador",
        )

        # La reseña aparece en el producto comprado.
        respuesta_original = self.client.get(
            reverse(
                "catalog:producto",
                kwargs={"pk": self.product.pk},
            )
        )

        self.assertContains(
            respuesta_original,
            "Comentario exclusivo del procesador",
        )

        # No debe contaminar la ficha de otro producto.
        respuesta_otro = self.client.get(
            reverse(
                "catalog:producto",
                kwargs={"pk": otro_producto.pk},
            )
        )

        self.assertEqual(
            respuesta_otro.status_code,
            200,
        )

        self.assertNotContains(
            respuesta_otro,
            "Comentario exclusivo del procesador",
        )

        self.assertContains(
            respuesta_otro,
            "Este producto todavía no tiene valoraciones",
        )
