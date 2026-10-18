"""Pruebas de acceso y persistencia. Ejecutar: python manage.py test apps.management.test_perfil"""

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from apps.accounts.models import Profile

User = get_user_model()


class PerfilAdminTests(TestCase):
    def setUp(self):
        self.url = reverse("management:perfil")
        self.admin = User.objects.create_user(
            username="admin_prueba", password="ClaveSegura2026!",
            first_name="Admin", last_name="Local", email="admin@example.com"
        )
        self.profile = Profile.objects.create(
            user=self.admin, role="ADMINISTRADOR", active=True,
            phone="+507 6000-0000", province="Chiriquí"
        )
        self.otro = User.objects.create_user(
            username="comprador", password="Comprador2026!", email="otro@example.com"
        )
        Profile.objects.create(user=self.otro, role="COMPRADOR", active=True)

    def test_requiere_sesion(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)

    def test_comprador_no_puede_acceder(self):
        self.client.force_login(self.otro)
        self.assertEqual(self.client.get(self.url).status_code, 403)

    def test_muestra_datos_del_usuario_real(self):
        self.client.force_login(self.admin)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "admin@example.com")
        self.assertContains(response, "Chiriquí")

    def test_actualiza_solo_el_usuario_autenticado(self):
        self.client.force_login(self.admin)
        response = self.client.post(self.url, {
            "action": "guardar_perfil", "first_name": "María",
            "last_name": "Admin", "email": "nuevo@example.com",
            "phone": "+507 6123-4567", "province": "Panamá",
            "user_id": self.otro.pk, "role": "SUPERUSER",
        })
        self.assertRedirects(response, self.url)
        self.admin.refresh_from_db()
        self.profile.refresh_from_db()
        self.otro.refresh_from_db()
        self.assertEqual(self.admin.first_name, "María")
        self.assertEqual(self.admin.email, "nuevo@example.com")
        self.assertEqual(self.profile.province, "Panamá")
        self.assertEqual(self.otro.email, "otro@example.com")
        self.assertFalse(self.admin.is_superuser)
        self.assertEqual(self.profile.role, "ADMINISTRADOR")

    def test_rechaza_email_duplicado(self):
        self.client.force_login(self.admin)
        response = self.client.post(self.url, {
            "action": "guardar_perfil", "first_name": "Admin",
            "last_name": "Local", "email": "OTRO@example.com",
            "phone": "1234", "province": "Chiriquí"
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Este correo ya pertenece a otra cuenta")
        self.admin.refresh_from_db()
        self.assertEqual(self.admin.email, "admin@example.com")

    def test_cambia_password_y_mantiene_sesion(self):
        self.client.force_login(self.admin)
        response = self.client.post(self.url, {
            "action": "cambiar_password",
            "seguridad-old_password": "ClaveSegura2026!",
            "seguridad-new_password1": "ClaveNueva2026!!",
            "seguridad-new_password2": "ClaveNueva2026!!",
        })
        self.assertRedirects(response, self.url)
        self.admin.refresh_from_db()
        self.assertTrue(self.admin.check_password("ClaveNueva2026!!"))
        self.assertEqual(self.client.get(self.url).status_code, 200)

    def test_password_incorrecto_no_actualiza(self):
        self.client.force_login(self.admin)
        response = self.client.post(self.url, {
            "action": "cambiar_password",
            "seguridad-old_password": "mal",
            "seguridad-new_password1": "ClaveNueva2026!!",
            "seguridad-new_password2": "ClaveNueva2026!!",
        })
        self.assertEqual(response.status_code, 200)
        self.admin.refresh_from_db()
        self.assertTrue(self.admin.check_password("ClaveSegura2026!"))

    def test_superusuario_sin_perfil(self):
        admin = User.objects.create_superuser(
            username="root_sin_perfil", email="root@example.com", password="Root2026!!"
        )
        self.client.force_login(admin)
        self.assertEqual(self.client.get(self.url).status_code, 200)
        self.assertTrue(Profile.objects.filter(user=admin).exists())

    def test_post_csrf_protegido(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.admin)
        response = client.post(self.url, {"action": "guardar_perfil"})
        self.assertEqual(response.status_code, 403)
