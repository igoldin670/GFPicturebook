import json
from datetime import date
from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.db import IntegrityError, transaction
from django.utils import timezone
from .models import Album, AlbumPhoto, Favorite, Photo

@override_settings(SECURE_SSL_REDIRECT=False, ALLOWED_HOSTS=["testserver"])
class SecurityTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user("alex", password="long-test-password-only")
        self.client = Client(enforce_csrf_checks=True)
    def csrf(self):
        return self.client.get("/api/session/").json()["csrfToken"]
    def login(self, password="long-test-password-only"):
        return self.client.post("/api/login/", json.dumps({"username":"alex","password":password}), content_type="application/json", HTTP_X_CSRFTOKEN=self.csrf())
    def test_anonymous_cannot_read_library(self):
        self.assertEqual(self.client.get("/api/summary/").status_code, 401)
    def test_csrf_required_for_login(self):
        self.assertEqual(self.client.post("/api/login/", "{}", content_type="application/json").status_code, 403)
    def test_cross_origin_login_rejected(self):
        response = self.client.post("/api/login/", "{}", content_type="application/json", HTTP_X_CSRFTOKEN=self.csrf(), HTTP_ORIGIN="https://evil.example")
        self.assertEqual(response.status_code, 403)
    def test_login_logout_and_session_rotation(self):
        before = self.csrf()
        response = self.login()
        self.assertEqual(response.status_code, 200)
        self.assertNotEqual(before, response.json()["csrfToken"])
        self.assertTrue(response.cookies["sessionid"]["httponly"])
        self.assertEqual(self.client.get("/api/summary/").status_code, 200)
        self.assertEqual(self.client.post("/api/logout/").status_code, 403)
        self.assertEqual(self.client.post("/api/logout/", HTTP_X_CSRFTOKEN=response.json()["csrfToken"]).status_code, 200)
        self.assertEqual(self.client.get("/api/summary/").status_code, 401)
    def test_inactive_user_cannot_sign_in(self):
        self.user.is_active = False
        self.user.save()
        self.assertEqual(self.login().status_code, 401)
    def test_member_cannot_open_admin(self):
        self.login()
        self.assertEqual(self.client.get("/admin/").status_code, 302)
    def test_password_uses_argon2(self):
        self.assertTrue(self.user.password.startswith("argon2$"))
    def test_brute_force_lockout(self):
        for _ in range(5):
            response = self.login("wrong")
        self.assertEqual(response.status_code, 429)
        self.assertEqual(self.login().status_code, 429)
    def test_malformed_login(self):
        response = self.client.post("/api/login/", '[]', content_type="application/json", HTTP_X_CSRFTOKEN=self.csrf())
        self.assertEqual(response.status_code, 400)
    def test_no_public_photo_route(self):
        self.assertEqual(self.client.get("/photos/originals/example.jpg").status_code, 404)
    def test_private_response_headers(self):
        response = self.client.get("/api/session/")
        self.assertIn("no-store", response["Cache-Control"])
        self.assertIn("frame-ancestors 'none'", response["Content-Security-Policy"])
    @override_settings(SESSION_COOKIE_SECURE=True, CSRF_COOKIE_SECURE=True)
    def test_production_cookie_flags(self):
        response = self.login()
        self.assertTrue(response.cookies["sessionid"]["secure"])
        self.assertTrue(response.cookies["csrftoken"]["secure"])
    def test_shared_albums_individual_favorites_and_trash(self):
        photo = Photo.objects.create(original_filename="test.jpg",original_key="originals/uuid",sha256="a"*64,byte_size=100,mime_type="image/jpeg",display_date=date(2026,10,9),date_source="upload",uploaded_by=self.user,status="ready")
        for name in ["First date", "Us"]:
            album = Album.objects.create(name=name,created_by=self.user)
            AlbumPhoto.objects.create(album=album,photo=photo)
        Favorite.objects.create(user=self.user,photo=photo)
        self.login()
        self.assertEqual(self.client.get("/api/summary/").json(), {"photos":1,"albums":2,"favorites":1})
        other = get_user_model().objects.create_user("sam")
        self.client.force_login(other)
        self.assertEqual(self.client.get("/api/summary/").json()["favorites"], 0)
        with self.assertRaises(IntegrityError), transaction.atomic():
            Favorite.objects.create(user=self.user,photo=photo)
        photo.trashed_at = timezone.now()
        photo.save()
        self.client.force_login(self.user)
        self.assertEqual(self.client.get("/api/summary/").json()["favorites"], 0)
        self.assertEqual(Photo.objects.count(), 1)

    def test_csrf_errors_are_safe_json_for_the_frontend(self):
        response = self.client.post('/api/login/', '{}', content_type='application/json')
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.headers['Content-Type'], 'application/json')
        self.assertIn('Refresh', response.json()['error'])
    def test_deactivating_a_logged_in_member_revokes_private_api_access(self):
        self.login()
        self.user.is_active = False
        self.user.save()
        self.assertEqual(self.client.get('/api/summary/').status_code, 401)
        self.assertEqual(self.client.get('/api/photos/').status_code, 401)
