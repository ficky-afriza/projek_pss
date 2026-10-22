from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone


class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("name",)
        verbose_name_plural = "categories"

    def __str__(self):
        return self.name


class Product(models.Model):
    name = models.CharField(max_length=255, verbose_name="Nama")
    price = models.DecimalField(
        max_digits=12, decimal_places=2, validators=[MinValueValidator(0)]
    )
    stock = models.PositiveIntegerField(default=0, verbose_name="Stok")
    image = models.ImageField(upload_to="products/", blank=True)
    description = models.TextField(blank=True)
    category = models.ForeignKey(
        Category, on_delete=models.SET_NULL, null=True, blank=True, related_name="products"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("name",)

    def __str__(self):
        return self.name


class ProductImage(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="images")
    image = models.ImageField(upload_to="products/gallery/")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Foto {self.product.name}"


class Discount(models.Model):
    date = models.DateField(unique=True, verbose_name="Tanggal")
    amount = models.DecimalField(
        max_digits=12, decimal_places=2, validators=[MinValueValidator(0)]
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-date",)

    def __str__(self):
        return f"{self.date}: Rp{self.amount}"


class Order(models.Model):
    class Status(models.IntegerChoices):
        WAITING = 0, "Menunggu pembayaran"
        PAID = 1, "Dibayar"
        REJECTED = 2, "Ditolak"

    class PaymentMethod(models.TextChoices):
        BANK = "Transfer Bank", "Transfer Bank"
        COD = "COD", "COD"
        EWALLET = "E-Wallet", "E-Wallet"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="orders"
    )
    total = models.DecimalField(max_digits=14, decimal_places=2)
    address = models.TextField()
    shipping_fee = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    payment_method = models.CharField(
        max_length=50, choices=PaymentMethod.choices, default=PaymentMethod.BANK
    )
    payment_proof = models.ImageField(upload_to="payments/", blank=True)
    status = models.PositiveSmallIntegerField(choices=Status.choices, default=Status.WAITING)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self):
        return f"Pesanan #{self.pk} - {self.user}"


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(
        Product, on_delete=models.SET_NULL, null=True, related_name="order_items"
    )
    product_name = models.CharField(max_length=255)
    quantity = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    discount_per_item = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    unit_price = models.DecimalField(max_digits=12, decimal_places=2)
    subtotal = models.DecimalField(max_digits=14, decimal_places=2)

    def __str__(self):
        return f"{self.product_name} x {self.quantity}"


class ContactMessage(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="contact_messages"
    )
    subject = models.CharField(max_length=150)
    message = models.TextField()
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self):
        return self.subject


class AccountProfile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="store_profile"
    )
    avatar = models.ImageField(upload_to="profiles/", blank=True)

    def __str__(self):
        return f"Profil {self.user.username}"
