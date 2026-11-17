from decimal import Decimal
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.db import transaction
from django.urls import reverse
from django.core.files.uploadedfile import SimpleUploadedFile
from apps.accounts.models import Profile
from apps.catalog.models import Category, Product
from apps.orders.models import PurchaseOrder, PurchaseLine, StockReservation
from apps.orders.stock_services import reserve_order_lines
from apps.orders.services import advance_seller_line
class Fase7Integrada(TestCase):
    def test_pago_y_entrega(self):
        U=get_user_model(); b=U.objects.create_user(username="flow_b"); s=U.objects.create_user(username="flow_s"); a=U.objects.create_superuser(username="flow_a",email="flow@test.invalid")
        Profile.objects.create(user=s,role="VENDEDOR")
        c=Category.objects.create(name="Procesadores",active=True)
        p=Product.objects.create(seller=s,category=c,name="CPU prueba",description="Prueba",brand="Test",price=Decimal("20.00"),stock=8,approval_status="APROBADO",active=True)
        o=PurchaseOrder.objects.create(buyer=b,status="PENDIENTE_PAGO",contact_name="Test",contact_phone="60000000",province="Chiriquí",address="Prueba",total=Decimal("40.00"))
        line=PurchaseLine.objects.create(order=o,product=p,seller=s,product_name=p.name,unit_price=p.price,quantity=2)
        Product.objects.filter(pk=p.pk).update(stock=6)
        with transaction.atomic(): reserve_order_lines(o)
        self.client.force_login(b)
        f=SimpleUploadedFile("pago.png",b"\x89PNG\r\n\x1a\n"+b"0"*24,content_type="image/png")
        self.client.post(reverse("orders:subir_comprobante",args=[o.pk]),{"comprobante":f})
        o.refresh_from_db(); self.assertEqual(o.status,"PAGO_EN_REVISION")
        self.client.force_login(a)
        self.client.post(reverse("orders:revisar_comprobante",args=[o.pk,o.receipts.get().pk]),{"decision":"APROBADO"})
        o.refresh_from_db(); self.assertEqual(o.status,"PAGADA")
        for _ in range(3): advance_seller_line(line.pk,s)
        o.refresh_from_db(); self.assertEqual(o.status,"ENTREGADA")
        self.client.force_login(b)
        self.client.post(reverse("orders:pedido_estado",args=[o.pk]),{"status":"COMPLETADA"})
        o.refresh_from_db(); self.assertEqual(o.status,"COMPLETADA")
        self.assertEqual(Product.objects.get(pk=p.pk).stock,6)
        self.assertEqual(StockReservation.objects.get(line=line).status,"CONSUMIDA")
    def test_checkout_y_cancelacion(self):
        from apps.orders.models import Cart, CartItem
        U=get_user_model(); b=U.objects.create_user(username="checkout_b"); s=U.objects.create_user(username="checkout_s")
        c=Category.objects.create(name="Procesadores",active=True)
        p=Product.objects.create(seller=s,category=c,name="CPU checkout",description="Prueba",brand="Test",price=Decimal("20.00"),stock=8,approval_status="APROBADO",active=True)
        cart=Cart.objects.create(user=b); CartItem.objects.create(cart=cart,product=p,quantity=2)
        self.client.force_login(b)
        self.client.post(reverse("orders:checkout"),{"contact_name":"Prueba","contact_phone":"60000000","province":"Chiriquí","address":"Prueba"})
        o=PurchaseOrder.objects.get(buyer=b)
        self.assertEqual(o.status,"PENDIENTE_PAGO")
        p.refresh_from_db(); self.assertEqual(p.stock,6)
        self.assertEqual(StockReservation.objects.get(line__order=o).status,"ACTIVA")
        self.client.post(reverse("orders:pedido_estado",args=[o.pk]),{"status":"CANCELADA"})
        o.refresh_from_db(); self.assertEqual(o.status,"CANCELADA")
        p.refresh_from_db(); self.assertEqual(p.stock,8)
        self.assertEqual(StockReservation.objects.get(line__order=o).status,"LIBERADA")
    def test_disputa_y_resolucion(self):
        from apps.orders.services import transition_order
        from apps.orders.models import OrderStatusHistory
        U=get_user_model()
        b=U.objects.create_user(username="disputa_b")
        a=U.objects.create_superuser(username="disputa_admin",email="admin@test.invalid")
        o=PurchaseOrder.objects.create(buyer=b,status="PAGADA",contact_name="Test",contact_phone="60000000",province="Chiriqui",address="Prueba",total=Decimal("20.00"))
        self.client.force_login(b)
        url=reverse("orders:pedido_estado",args=[o.pk])
        self.client.post(url,{"status":"EN_DISPUTA","reason":""})
        o.refresh_from_db(); self.assertEqual(o.status,"PAGADA")
        self.client.post(url,{"status":"EN_DISPUTA","reason":"Pedido no recibido"})
        o.refresh_from_db(); self.assertEqual(o.status,"EN_DISPUTA")
        self.assertTrue(OrderStatusHistory.objects.filter(order=o,new_status="EN_DISPUTA").exists())
        transition_order(o.pk,"PAGADA",a,"Disputa resuelta")
        o.refresh_from_db(); self.assertEqual(o.status,"PAGADA")
