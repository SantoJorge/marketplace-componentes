from decimal import Decimal
from django.test import TestCase
from django.contrib.auth.models import User
from django.urls import reverse
from apps.accounts.models import Profile
from apps.catalog.models import Product, Category
from apps.orders.models import Cart, CartItem
from apps.orders.models import PurchaseOrder, PurchaseLine
from apps.accounts.models import SellerRequest

class MarketplaceTotalTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin=User.objects.create_user('admin_total',password='ClaveSegura987!')
        cls.seller=User.objects.create_user('seller_total',password='ClaveSegura987!')
        cls.buyer=User.objects.create_user('buyer_total',password='ClaveSegura987!')
        cls.buyer2=User.objects.create_user('buyer_otro',password='ClaveSegura987!')
        Profile.objects.create(user=cls.admin,role='ADMINISTRADOR')
        Profile.objects.create(user=cls.seller,role='VENDEDOR')
        Profile.objects.create(user=cls.buyer,role='COMPRADOR')
        Profile.objects.create(user=cls.buyer2,role='COMPRADOR')
        cls.cat=Category.objects.create(name='CPU total')
        cls.product=Product.objects.create(seller=cls.seller,category=cls.cat,name='Ryzen Test',brand='AMD',description='Procesador para pruebas',price='50.00',stock=8,approval_status='APROBADO')

    def test_public_catalog_shows_only_approved(self):
        response=self.client.get(reverse('catalog:tienda'))
        self.assertEqual(response.status_code,200)
        self.assertContains(response,'Ryzen Test')
        self.product.approval_status='PENDIENTE';self.product.save()
        self.assertNotContains(self.client.get(reverse('catalog:tienda')),'Ryzen Test')

    def test_buyer_cannot_enter_admin(self):
        self.client.force_login(self.buyer)
        self.assertEqual(self.client.get(reverse('management:usuarios')).status_code,403)

    def test_admin_cannot_change_superuser_or_self(self):
        self.client.force_login(self.admin)
        response=self.client.post(reverse('management:usuario_estado',args=[self.admin.pk]))
        self.assertEqual(response.status_code,403)
        self.admin.refresh_from_db();self.assertTrue(self.admin.is_active)

    def test_seller_may_not_edit_another_sellers_product(self):
        other=User.objects.create_user('otro_vendedor',password='ClaveSegura987!')
        Profile.objects.create(user=other,role='VENDEDOR')
        self.client.force_login(other)
        self.assertEqual(self.client.get(reverse('catalog:vendedor_producto_editar',args=[self.product.pk])).status_code,404)

    def test_checkout_creates_snapshot_and_decrements_stock(self):
        self.client.force_login(self.buyer)
        cart=Cart.objects.create(user=self.buyer)
        CartItem.objects.create(cart=cart,product=self.product,quantity=2)
        r=self.client.post(reverse('orders:checkout'),{
            'contact_name':'Comprador','contact_phone':'60000000','province':'Chiriquí',
            'address':'David, zona de prueba','comments':''})
        self.assertEqual(r.status_code,302)
        order=PurchaseOrder.objects.get(buyer=self.buyer)
        self.assertEqual(order.total,Decimal('100.00'))
        self.assertEqual(order.lines.count(),1)
        self.assertEqual(order.lines.first().seller_id,self.seller.pk)
        self.product.refresh_from_db();self.assertEqual(self.product.stock,6)
        self.assertFalse(cart.items.exists())
        self.client.force_login(self.buyer2)
        self.assertEqual(self.client.get(reverse('orders:pedido_detalle',args=[order.pk])).status_code,404)

    def test_cancel_restores_stock_once(self):
        self.client.force_login(self.buyer)
        order=PurchaseOrder.objects.create(buyer=self.buyer,contact_name='A',contact_phone='123',province='Panamá',address='Calle',total=Decimal('50'))
        PurchaseLine.objects.create(order=order,product=self.product,seller=self.seller,product_name='Ryzen Test',unit_price=50,quantity=1)
        self.product.stock=7;self.product.save(update_fields=['stock'])
        url=reverse('orders:cancelar_pedido',args=[order.pk])
        self.assertEqual(self.client.post(url).status_code,302)
        self.assertEqual(self.client.post(url).status_code,302)
        self.product.refresh_from_db();self.assertEqual(self.product.stock,8)

    def test_seller_request_admin_approval_and_role(self):
        self.client.force_login(self.buyer)
        self.client.post(reverse('accounts:ser_vendedor'),{
            'business_name':'Venta Test','business_description':'Hardware','business_phone':'60000000','location':'David'})
        req=SellerRequest.objects.get(user=self.buyer)
        self.assertEqual(req.status,'PENDIENTE')
        self.client.force_login(self.admin)
        resp=self.client.post(reverse('management:solicitud_resolver',args=[req.pk]),{'action':'approve'})
        self.assertEqual(resp.status_code,302)
        self.buyer.profile.refresh_from_db();self.assertEqual(self.buyer.profile.role,'VENDEDOR')
        self.assertTrue(hasattr(self.buyer,'seller_profile'))

    def test_mutations_are_not_get_requests(self):
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(reverse('management:producto_resolver',args=[self.product.pk])).status_code,405)

class VistasIntegradasTests(TestCase):
    """Comprueba que cada panel carga con la plantilla/base existentes."""
    @classmethod
    def setUpTestData(cls):
        cls.adm = User.objects.create_user("adm_vistas", password="ClaveSegura987!")
        cls.seller = User.objects.create_user("vendedor_vistas", password="ClaveSegura987!")
        cls.buyer = User.objects.create_user("comprador_vistas", password="ClaveSegura987!")
        for u, r in [(cls.adm, 'ADMINISTRADOR'), (cls.seller, 'VENDEDOR'), (cls.buyer, 'COMPRADOR')]:
            Profile.objects.create(user=u, role=r)
        cls.cat = Category.objects.create(name="Computadoras")
        cls.producto = Product.objects.create(seller=cls.seller, category=cls.cat, name='SSD 1TB', brand='Equipo', description='Prueba', price='25.00', stock=4, approval_status='APROBADO')

    def test_publico_y_catalogo(self):
        for name in ['catalog:inicio', 'catalog:catalogo', 'catalog:tienda']:
            with self.subTest(name=name):
                self.assertEqual(self.client.get(reverse(name)).status_code, 200)
        self.assertEqual(self.client.get(reverse('catalog:producto', args=[self.producto.pk])).status_code,200)

    def test_todas_las_secciones_administrativas(self):
        self.client.force_login(self.adm)
        for name in ['management:dashboard', 'management:perfil','management:usuarios','management:solicitudes','management:productos','management:categorias','management:pedidos','management:categoria_nueva']:
            with self.subTest(name=name):
                self.assertEqual(self.client.get(reverse(name)).status_code,200)

    def test_todas_las_secciones_vendedor(self):
        self.client.force_login(self.seller)
        for name in ['catalog:vendedor_dashboard', 'catalog:vendedor_productos', 'catalog:vendedor_producto_nuevo', 'orders:vendedor_ventas','accounts:perfil','accounts:negocio']:
            with self.subTest(name=name):
                self.assertEqual(self.client.get(reverse(name)).status_code,200)

    def test_todas_las_secciones_comprador(self):
        self.client.force_login(self.buyer)
        for name in ['orders:cart_detail','orders:mis_pedidos','accounts:perfil','accounts:ser_vendedor']:
            with self.subTest(name=name):
                self.assertEqual(self.client.get(reverse(name)).status_code,200)

    def test_no_permite_mutar_carrito_por_get(self):
        self.assertEqual(self.client.get(reverse('orders:add_to_cart',args=[self.producto.pk])).status_code,405)
