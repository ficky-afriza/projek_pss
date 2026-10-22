from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .models import Category, Discount, Order, OrderItem, Product
from .views import ShippingProviderError


@override_settings(COST_API_KEY="")
class StoreFlowTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="pembeli", password="KataSandiAman123!"
        )
        self.category = Category.objects.create(name="Pakaian")
        self.product = Product.objects.create(
            name="Kaos", price=Decimal("50000.00"), stock=4, category=self.category
        )

    def test_catalog_filters_by_category(self):
        response = self.client.get(reverse("home"), {"category": self.category.pk})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Kaos")

    def test_registration_creates_and_logs_in_new_user(self):
        response = self.client.post(
            reverse("register"),
            {
                "username": "userbaru",
                "email": "userbaru@example.com",
                "password1": "KataSandiAmanBaru!873",
                "password2": "KataSandiAmanBaru!873",
            },
        )

        self.assertRedirects(response, reverse("home"))
        self.assertTrue(User.objects.filter(username="userbaru").exists())
        self.assertTrue(response.wsgi_request.user.is_authenticated)

    def test_registration_shows_validation_errors(self):
        response = self.client.post(
            reverse("register"),
            {
                "username": "ab",
                "email": "bukan-email",
                "password1": "123",
                "password2": "456",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Username harus terdiri dari minimal 5 karakter.")
        self.assertContains(response, "Masukkan alamat email yang valid.")
        self.assertContains(response, "Kata sandi")

    def test_logged_in_user_gets_explanation_when_opening_registration(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse("register"), follow=True)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Anda sudah masuk")

    def test_admin_order_page_is_staff_only(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("admin_orders"))
        self.assertEqual(response.status_code, 403)

        admin_user = User.objects.create_superuser(
            username="adminuser", email="admin@example.com", password="AdminPassword123!"
        )
        self.client.force_login(admin_user)
        response = self.client.get(reverse("admin_orders"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Konfirmasi pesanan")

    def test_admin_can_confirm_order_after_payment_proof_is_uploaded(self):
        admin_user = User.objects.create_superuser(
            username="adminuser", email="admin@example.com", password="AdminPassword123!"
        )
        order = Order.objects.create(
            user=self.user,
            total=Decimal("50000"),
            address="Alamat contoh",
            payment_method=Order.PaymentMethod.BANK,
            status=Order.Status.WAITING,
        )
        self.client.force_login(admin_user)

        response = self.client.post(
            reverse(
                "update_order_payment",
                args=[order.pk, Order.Status.PAID],
            )
        )
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.WAITING)
        self.assertRedirects(response, reverse("admin_orders"))

        order.payment_proof = "payments/bukti-transfer.png"
        order.save(update_fields=["payment_proof"])
        response = self.client.post(
            reverse(
                "update_order_payment",
                args=[order.pk, Order.Status.PAID],
            )
        )

        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.PAID)
        self.assertRedirects(response, reverse("admin_orders"))

    def test_cart_requires_login_and_adds_item(self):
        response = self.client.post(reverse("cart_add", args=[self.product.pk]))
        self.assertRedirects(response, f"{reverse('login')}?next={reverse('cart_add', args=[self.product.pk])}")

        self.client.login(username="pembeli", password="KataSandiAman123!")
        response = self.client.post(reverse("cart_add", args=[self.product.pk]))
        self.assertRedirects(response, reverse("home"))
        self.assertEqual(self.client.session["cart"][str(self.product.pk)]["quantity"], 1)

    def test_checkout_creates_order_and_decrements_stock(self):
        self.client.login(username="pembeli", password="KataSandiAman123!")
        self.client.post(reverse("cart_add", args=[self.product.pk]))

        response = self.client.post(
            reverse("checkout"),
            {"address": "Jl. Contoh nomor 1", "payment_method": Order.PaymentMethod.BANK},
        )

        self.assertRedirects(response, reverse("order_history"))
        order = Order.objects.get(user=self.user)
        self.assertEqual(order.total, Decimal("50000.00"))
        self.assertEqual(OrderItem.objects.get(order=order).quantity, 1)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 3)
        self.assertEqual(self.client.session["cart"], {})

    @override_settings(COST_API_KEY="provider-test-key")
    def test_checkout_shows_location_search_when_shipping_provider_is_configured(self):
        self.client.login(username="pembeli", password="KataSandiAman123!")
        self.client.post(reverse("cart_add", args=[self.product.pk]))

        response = self.client.get(reverse("checkout"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="location-search"')
        self.assertContains(response, 'id="location-results"')
        self.assertContains(response, 'id="shipping-service"')

    @override_settings(COST_API_KEY="provider-test-key")
    @patch("store.views._shipping_options", return_value=[{"service": "REG", "cost": 25000}])
    def test_checkout_verifies_and_saves_selected_shipping_cost(self, shipping_options):
        self.client.login(username="pembeli", password="KataSandiAman123!")
        self.client.post(reverse("cart_add", args=[self.product.pk]))

        response = self.client.post(
            reverse("checkout"),
            {
                "address": "Jl. Contoh nomor 1",
                "payment_method": Order.PaymentMethod.BANK,
                "destination": "12345",
                "courier": "jne",
                "shipping_cost": "25000",
            },
        )

        self.assertRedirects(response, reverse("order_history"))
        order = Order.objects.get(user=self.user)
        self.assertEqual(order.shipping_fee, Decimal("25000"))
        self.assertEqual(order.total, Decimal("75000"))
        shipping_options.assert_called_once_with("12345", "jne", 1000)

    @override_settings(COST_API_KEY="provider-test-key")
    @patch("store.views._shipping_options", return_value=[{"service": "REG", "cost": 25000}])
    def test_checkout_rejects_shipping_cost_not_returned_by_provider(self, shipping_options):
        self.client.login(username="pembeli", password="KataSandiAman123!")
        self.client.post(reverse("cart_add", args=[self.product.pk]))

        response = self.client.post(
            reverse("checkout"),
            {
                "address": "Jl. Contoh nomor 1",
                "payment_method": Order.PaymentMethod.BANK,
                "destination": "12345",
                "courier": "jne",
                "shipping_cost": "1",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(Order.objects.exists())
        self.assertContains(response, "Tarif ongkir berubah")
        shipping_options.assert_called_once_with("12345", "jne", 1000)

    def test_checkout_applies_current_discount(self):
        Discount.objects.create(date=timezone.localdate(), amount=Decimal("5000.00"))
        self.client.login(username="pembeli", password="KataSandiAman123!")
        self.client.post(reverse("cart_add", args=[self.product.pk]))

        self.client.post(
            reverse("checkout"),
            {"address": "Jl. Contoh nomor 1", "payment_method": Order.PaymentMethod.BANK},
        )

        order = Order.objects.get(user=self.user)
        self.assertEqual(order.total, Decimal("45000.00"))
        self.assertEqual(order.items.get().discount_per_item, Decimal("5000.00"))

    def test_checkout_rejects_out_of_stock_cart(self):
        self.client.login(username="pembeli", password="KataSandiAman123!")
        session = self.client.session
        session["cart"] = {
            str(self.product.pk): {
                "name": self.product.name,
                "price": str(self.product.price),
                "quantity": 5,
                "discount": "0",
                "image": "",
            }
        }
        session.save()

        response = self.client.post(
            reverse("checkout"),
            {"address": "Jl. Contoh nomor 1", "payment_method": Order.PaymentMethod.BANK},
        )

        self.assertRedirects(response, reverse("cart"))
        self.assertFalse(Order.objects.exists())

    @override_settings(API_KEY="test-secret")
    def test_transaction_api_requires_matching_api_key(self):
        response = self.client.get(reverse("api_transactions"))
        self.assertEqual(response.status_code, 401)

        response = self.client.get(
            reverse("api_transactions"), headers={"X-API-Key": "test-secret"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("results", response.json())

    def test_shipping_cost_validates_destination_before_provider_call(self):
        response = self.client.get(reverse("shipping_cost"), {"destination": "not-a-number"})
        self.assertEqual(response.status_code, 422)

    @override_settings(COST_API_KEY="provider-test-key")
    @patch(
        "store.views._shipping_request",
        return_value={
            "data": [
                {
                    "id": 12345,
                    "label": "Kelurahan Contoh, Kota Contoh",
                    "subdistrict_name": "Kelurahan Contoh",
                }
            ]
        },
    )
    def test_location_search_returns_selectable_provider_results(self, provider_request):
        response = self.client.get(reverse("shipping_locations"), {"search": "Contoh"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            [
                {
                    "id": 12345,
                    "label": "Kelurahan Contoh, Kota Contoh",
                    "subdistrict_name": "Kelurahan Contoh",
                }
            ],
        )
        provider_request.assert_called_once()

    @override_settings(COST_API_KEY="provider-test-key")
    @patch(
        "store.views._shipping_request",
        return_value={
            "data": {
                "results": [
                    {"destinationId": 12345, "label": "Kelurahan Contoh, Kota Contoh"}
                ]
            }
        },
    )
    def test_location_search_normalizes_nested_provider_response(self, provider_request):
        response = self.client.get(reverse("shipping_locations"), {"search": "Contoh"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            [{"destinationId": 12345, "label": "Kelurahan Contoh, Kota Contoh"}],
        )
        provider_request.assert_called_once()

    @override_settings(COST_API_KEY="provider-test-key")
    @patch("store.views._shipping_request", side_effect=ShippingProviderError(403, 1010))
    def test_location_search_reports_provider_auth_failure(self, provider_request):
        response = self.client.get(reverse("shipping_locations"), {"search": "Contoh"})

        self.assertEqual(response.status_code, 502)
        self.assertIn("Error 1010", response.json()["message"])
        self.assertIn("bukan menolak API key", response.json()["message"])
        provider_request.assert_called_once()

    @override_settings(COST_API_KEY="provider-test-key")
    @patch("store.views._shipping_options", return_value=[{"service": "REG", "cost": 25000}])
    def test_shipping_cost_endpoint_returns_provider_options(self, shipping_options):
        response = self.client.get(
            reverse("shipping_cost"),
            {"destination": "12345", "courier": "jne", "weight": "1000"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), [{"service": "REG", "cost": 25000}])
        shipping_options.assert_called_once_with("12345", "jne", 1000)
