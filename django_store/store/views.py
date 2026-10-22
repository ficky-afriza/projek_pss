from decimal import Decimal
import json
import logging
import re
from secrets import compare_digest
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from urllib.error import HTTPError

from PIL import Image, UnidentifiedImageError
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from .forms import AccountForm, CheckoutForm, ContactForm, RegistrationForm
from .models import AccountProfile, Category, ContactMessage, Discount, Order, OrderItem, Product


logger = logging.getLogger(__name__)


class ShippingProviderError(Exception):
    def __init__(self, status_code, error_code=None):
        self.status_code = status_code
        self.error_code = error_code
        super().__init__(
            f"Shipping provider returned HTTP {status_code}"
            + (f" error {error_code}" if error_code else "")
        )


def current_discount():
    return Discount.objects.filter(date=timezone.localdate()).first()


def home(request):
    products = Product.objects.select_related("category").all()
    category_id = request.GET.get("category")
    if category_id and category_id.isdigit():
        products = products.filter(category_id=int(category_id))
    query = request.GET.get("q", "").strip()
    if query:
        products = products.filter(Q(name__icontains=query) | Q(description__icontains=query))
    page = Paginator(products, 12).get_page(request.GET.get("page"))
    discount = current_discount()
    for product in page.object_list:
        product.discounted_price = (
            max(product.price - discount.amount, Decimal("0")) if discount else product.price
        )
    return render(
        request,
        "store/home.html",
        {
            "products": page,
            "categories": Category.objects.all(),
            "selected_category": category_id,
            "query": query,
            "discount": discount,
        },
    )


def product_detail(request, product_id):
    product = get_object_or_404(
        Product.objects.select_related("category").prefetch_related("images"), pk=product_id
    )
    discount = current_discount()
    product.discounted_price = (
        max(product.price - discount.amount, Decimal("0")) if discount else product.price
    )
    return render(request, "store/product_detail.html", {"product": product, "discount": discount})


def register(request):
    if request.user.is_authenticated:
        messages.info(
            request,
            "Anda sudah masuk. Keluar dulu untuk membuat akun baru, atau admin dapat menambahkan user dari menu Admin.",
        )
        return redirect("home")
    form = RegistrationForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        login(request, user)
        messages.success(request, "Akun berhasil dibuat.")
        return redirect("home")
    return render(request, "store/form_page.html", {"form": form, "title": "Daftar akun"})


def login_view(request):
    if request.user.is_authenticated:
        return redirect("home")
    error = None
    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        user = authenticate(request, username=username, password=request.POST.get("password", ""))
        if user is not None:
            login(request, user)
            return redirect("home")
        error = "Username atau password salah."
    return render(request, "store/login.html", {"error": error})


@require_POST
def logout_view(request):
    logout(request)
    return redirect("home")


def _cart(request):
    return request.session.setdefault("cart", {})


@login_required
@require_POST
def cart_add(request, product_id):
    product = get_object_or_404(Product, pk=product_id)
    items = _cart(request)
    current_quantity = int(items.get(str(product_id), {}).get("quantity", 0))
    if current_quantity + 1 > product.stock:
        messages.error(request, "Jumlah produk melebihi stok yang tersedia.")
    else:
        discount = current_discount()
        items[str(product_id)] = {
            "name": product.name,
            "price": str(product.price),
            "quantity": current_quantity + 1,
            "discount": str(min(discount.amount, product.price) if discount else Decimal("0")),
            "image": product.image.name if product.image else "",
        }
        request.session.modified = True
        messages.success(request, "Produk berhasil ditambahkan ke keranjang.")
    return redirect(request.POST.get("next") or "home")


@login_required
def cart_view(request):
    products = Product.objects.in_bulk([int(key) for key in _cart(request) if key.isdigit()])
    lines, total = [], Decimal("0")
    discount_today = current_discount()
    for key, item in _cart(request).items():
        product = products.get(int(key)) if key.isdigit() else None
        if product is None:
            continue
        price = product.price
        discount = min(discount_today.amount, price) if discount_today else Decimal("0")
        quantity = int(item["quantity"])
        subtotal = (price - discount) * quantity
        total += subtotal
        lines.append({"product": product, "quantity": quantity, "subtotal": subtotal})
    return render(request, "store/cart.html", {"lines": lines, "total": total})


@login_required
@require_POST
def cart_update(request):
    items = _cart(request)
    products = Product.objects.in_bulk([int(key) for key in items if key.isdigit()])
    try:
        for product_id, item in items.items():
            quantity = int(request.POST.get(f"quantity_{product_id}", ""))
            product = products.get(int(product_id))
            if quantity < 1 or product is None or quantity > product.stock:
                raise ValueError
            item["quantity"] = quantity
    except (TypeError, ValueError):
        messages.error(request, "Jumlah produk tidak valid atau melebihi stok.")
    else:
        request.session.modified = True
        messages.success(request, "Keranjang berhasil diperbarui.")
    return redirect("cart")


@login_required
@require_POST
def cart_remove(request, product_id):
    _cart(request).pop(str(product_id), None)
    request.session.modified = True
    return redirect("cart")


@login_required
@require_POST
def cart_clear(request):
    request.session["cart"] = {}
    return redirect("cart")


@login_required
def checkout(request):
    items = _cart(request)
    if not items:
        messages.info(request, "Keranjang masih kosong.")
        return redirect("cart")
    form = CheckoutForm(request.POST or None)
    products = Product.objects.in_bulk([int(key) for key in items if key.isdigit()])
    if len(products) != len(items) or any(not key.isdigit() for key in items):
        messages.error(request, "Ada produk di keranjang yang sudah tidak tersedia.")
        return redirect("cart")
    lines, subtotal = [], Decimal("0")
    discount_today = current_discount()
    for key, item in items.items():
        product = products.get(int(key)) if key.isdigit() else None
        if product is None:
            continue
        qty = int(item["quantity"])
        discount = min(discount_today.amount, product.price) if discount_today else Decimal("0")
        line_total = (product.price - discount) * qty
        lines.append((product, qty, discount, line_total))
        subtotal += line_total
    shipping_fee = Decimal(settings.SHIPPING_FEE)
    shipping_enabled = bool(settings.COST_API_KEY)
    shipping_error = None
    if request.method == "POST" and form.is_valid():
        if shipping_enabled:
            destination = request.POST.get("destination", "").strip()
            courier = request.POST.get("courier", "").strip().lower()
            selected_cost = request.POST.get("shipping_cost", "").strip()
            if (
                not destination.isdigit()
                or not re.fullmatch(r"[a-z][a-z0-9_-]{1,30}", courier)
                or not selected_cost.isdigit()
            ):
                shipping_error = "Pilih tujuan dan layanan ongkir yang valid."
            else:
                try:
                    options = _shipping_options(destination, courier, 1000)
                except ShippingProviderError as exc:
                    logger.warning("Shipping provider rejected checkout quote: HTTP %s", exc.status_code)
                    shipping_error = _shipping_error_message(
                        exc.status_code, exc.error_code
                    )
                except (OSError, ValueError, json.JSONDecodeError):
                    logger.exception("Shipping provider checkout request failed")
                    shipping_error = "Ongkir tidak dapat diverifikasi. Silakan coba lagi."
                else:
                    verified = next(
                        (
                            Decimal(str(option["cost"]))
                            for option in options
                            if isinstance(option, dict)
                            and str(option.get("cost", "")).isdigit()
                            and str(option["cost"]) == selected_cost
                        ),
                        None,
                    )
                    if verified is None:
                        shipping_error = "Tarif ongkir berubah. Muat ulang pilihan layanan."
                    else:
                        shipping_fee = verified

        if shipping_error:
            messages.error(request, shipping_error)
        else:
            with transaction.atomic():
                locked_products = {
                    product.pk: product
                    for product in Product.objects.select_for_update().filter(
                        pk__in=[line[0].pk for line in lines]
                    )
                }
                if any(
                    product.pk not in locked_products or qty > locked_products[product.pk].stock
                    for product, qty, _, _ in lines
                ):
                    messages.error(request, "Stok berubah. Perbarui keranjang dan coba lagi.")
                    return redirect("cart")
                locked_lines = []
                subtotal = Decimal("0")
                for product, quantity, _, _ in lines:
                    current_product = locked_products[product.pk]
                    discount = (
                        min(discount_today.amount, current_product.price)
                        if discount_today
                        else Decimal("0")
                    )
                    line_total = (current_product.price - discount) * quantity
                    subtotal += line_total
                    locked_lines.append((current_product, quantity, discount, line_total))
                order = Order.objects.create(
                    user=request.user,
                    total=subtotal + shipping_fee,
                    address=form.cleaned_data["address"],
                    shipping_fee=shipping_fee,
                    payment_method=form.cleaned_data["payment_method"],
                )
                for current_product, qty, discount, line_total in locked_lines:
                    OrderItem.objects.create(
                        order=order,
                        product=current_product,
                        product_name=current_product.name,
                        quantity=qty,
                        discount_per_item=discount,
                        unit_price=current_product.price,
                        subtotal=line_total,
                    )
                    current_product.stock -= qty
                    current_product.save(update_fields=["stock"])
            request.session["cart"] = {}
            messages.success(request, "Pesanan berhasil dibuat.")
            return redirect("order_history")
    return render(
        request,
        "store/checkout.html",
        {
            "form": form,
            "lines": lines,
            "subtotal": subtotal,
            "shipping_fee": shipping_fee,
            "total": subtotal + shipping_fee,
            "shipping_enabled": shipping_enabled,
            "location_url": "/get-location",
            "cost_url": "/get-cost",
            "selected_destination": request.POST.get("destination", ""),
            "selected_courier": request.POST.get("courier", "jne"),
            "selected_shipping_cost": request.POST.get("shipping_cost", ""),
        },
    )


@login_required
def order_history(request):
    orders = Order.objects.filter(user=request.user).prefetch_related("items")
    return render(request, "store/orders.html", {"orders": orders})


@login_required
@require_GET
def admin_orders(request):
    if not request.user.is_staff:
        return HttpResponseForbidden("Halaman ini hanya dapat diakses admin.")
    orders = Order.objects.select_related("user").prefetch_related("items")
    status = request.GET.get("status", "0")
    if status in {"0", "1", "2"}:
        orders = orders.filter(status=int(status))
    else:
        status = "all"
    return render(
        request,
        "store/admin_orders.html",
        {
            "orders": orders,
            "selected_status": status,
            "waiting_count": Order.objects.filter(status=Order.Status.WAITING).count(),
            "paid_count": Order.objects.filter(status=Order.Status.PAID).count(),
            "rejected_count": Order.objects.filter(status=Order.Status.REJECTED).count(),
        },
    )


@login_required
@require_POST
def update_order_payment(request, order_id, status):
    if not request.user.is_staff:
        return HttpResponseForbidden("Aksi ini hanya dapat dilakukan admin.")
    if status not in (Order.Status.PAID, Order.Status.REJECTED):
        messages.error(request, "Status pembayaran tidak valid.")
        return redirect("admin_orders")

    with transaction.atomic():
        order = Order.objects.select_for_update().filter(pk=order_id).first()
        if order is None:
            messages.error(request, "Pesanan tidak ditemukan.")
        elif order.status == Order.Status.PAID:
            messages.error(request, "Pesanan ini sudah dikonfirmasi dibayar.")
        elif status == Order.Status.PAID and not order.payment_proof:
            messages.error(request, "Periksa bukti pembayaran sebelum mengonfirmasi pesanan.")
        else:
            order.status = status
            order.save(update_fields=["status", "updated_at"])
            if status == Order.Status.PAID:
                messages.success(request, f"Pembayaran pesanan #{order.pk} berhasil dikonfirmasi.")
            else:
                messages.success(request, f"Pesanan #{order.pk} ditolak.")
    return redirect("admin_orders")


@login_required
def account(request):
    profile, _ = AccountProfile.objects.get_or_create(user=request.user)
    form = AccountForm(
        request.POST or None,
        request.FILES or None,
        instance=request.user,
        initial={"avatar": profile.avatar},
    )
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Akun berhasil diperbarui.")
        return redirect("account")
    return render(
        request,
        "store/form_page.html",
        {"form": form, "title": "Pengaturan akun", "multipart": True},
    )


@login_required
@require_POST
def upload_payment_proof(request, order_id):
    order = get_object_or_404(Order, pk=order_id, user=request.user)
    uploaded = request.FILES.get("payment_proof")
    if order.status not in (Order.Status.WAITING, Order.Status.REJECTED):
        messages.error(request, "Pesanan ini tidak menerima bukti pembayaran.")
    elif not _is_valid_payment_image(uploaded):
        messages.error(request, "Bukti pembayaran harus berupa gambar JPG, PNG, atau WEBP maksimal 5 MB.")
    else:
        order.payment_proof = uploaded
        order.save(update_fields=["payment_proof", "updated_at"])
        messages.success(request, "Bukti pembayaran berhasil diunggah.")
    return redirect("order_history")


@login_required
def contact(request):
    form = ContactForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        message = form.save(commit=False)
        message.user = request.user
        message.save()
        messages.success(request, "Pesan berhasil dikirim.")
        return redirect("contact")
    return render(request, "store/form_page.html", {"form": form, "title": "Hubungi kami"})


@require_GET
def products_api(request):
    if not _api_key_authorized(request):
        return JsonResponse({"message": "Unauthorized."}, status=401)
    if _rate_limited(request, "api-products", 30):
        return JsonResponse({"message": "Rate limit exceeded.", "retry_after": 60}, status=429)
    products = Product.objects.select_related("category").all()
    return JsonResponse(
        {
            "data": [
                {
                    "id": product.pk,
                    "nama": product.name,
                    "harga": str(product.price),
                    "jumlah": product.stock,
                    "category": product.category.name if product.category else None,
                    "deskripsi": product.description,
                }
                for product in products
            ]
        }
    )


@require_GET
def orders_api(request):
    if not request.user.is_authenticated:
        return JsonResponse({"message": "Authentication required."}, status=401)
    if not request.user.is_staff:
        return JsonResponse({"message": "Forbidden."}, status=403)
    if _rate_limited(request, "dashboard-transactions", 10):
        return JsonResponse(
            {"message": "Terlalu sering memuat data transaksi. Silakan tunggu sebentar.", "retry_after": 60},
            status=429,
        )
    orders = Order.objects.select_related("user").all()
    status = request.GET.get("status")
    if status is not None:
        if status not in {"0", "1", "2"}:
            return JsonResponse({"message": "Filter status hanya menerima 0, 1, atau 2."}, status=422)
        orders = orders.filter(status=int(status))
    username = request.GET.get("username", "").strip()[:100]
    if username:
        orders = orders.filter(user__username__icontains=username)
    page = max(1, int(request.GET.get("page", "1")) if request.GET.get("page", "1").isdigit() else 1)
    raw_per_page = request.GET.get("perPage", "10")
    per_page = min(100, max(1, int(raw_per_page))) if raw_per_page.isdigit() else 10
    paginator = Paginator(orders, per_page)
    current_page = paginator.get_page(page)
    return JsonResponse(
        {
            "data": [
                {
                    "id": order.pk,
                    "username": order.user.username,
                    "total_harga": str(order.total),
                    "alamat": order.address,
                    "ongkir": str(order.shipping_fee),
                    "status": order.status,
                    "created_at": order.created_at.isoformat(),
                    "jumlah_item": sum(item.quantity for item in order.items.all()),
                }
                for order in current_page.object_list.prefetch_related("items")
            ],
            "pagination": {
                "page": current_page.number,
                "perPage": per_page,
                "total": paginator.count,
                "totalPages": paginator.num_pages,
            },
        }
    )


@require_GET
def api_transactions(request):
    if not _api_key_authorized(request):
        return JsonResponse({"message": "Unauthorized."}, status=401)
    if _rate_limited(request, "api-transactions", 30):
        return JsonResponse({"message": "Rate limit exceeded.", "retry_after": 60}, status=429)
    status = request.GET.get("status")
    if status is not None and status not in {"0", "1", "2"}:
        return JsonResponse({"message": "Filter status hanya menerima 0, 1, atau 2."}, status=422)
    orders = Order.objects.select_related("user").prefetch_related("items")
    if status is not None:
        orders = orders.filter(status=int(status))
    username = request.GET.get("username", "").strip()[:100]
    if username:
        orders = orders.filter(user__username__icontains=username)
    page_number = _positive_query_int(request.GET.get("page"), default=1)
    per_page = min(100, max(1, _positive_query_int(request.GET.get("perPage"), default=10)))
    paginator = Paginator(orders, per_page)
    page = paginator.get_page(page_number)
    results = []
    for order in page.object_list:
        results.append(
            {
                "id": order.pk,
                "username": order.user.username,
                "total_harga": str(order.total),
                "alamat": order.address,
                "ongkir": str(order.shipping_fee),
                "metode_pembayaran": order.payment_method,
                "bukti_pembayaran": order.payment_proof.name or None,
                "status": order.status,
                "created_at": order.created_at.isoformat(),
                "updated_at": order.updated_at.isoformat(),
                "details": [
                    {
                        "transaction_id": order.pk,
                        "product_id": item.product_id,
                        "jumlah": item.quantity,
                        "diskon": str(item.discount_per_item),
                        "subtotal_harga": str(item.subtotal),
                    }
                    for item in order.items.all()
                ],
            }
        )
    return JsonResponse(
        {
            "status": {"code": 200, "description": "OK"},
            "results": results,
            "pagination": {
                "page": page.number,
                "perPage": per_page,
                "total": paginator.count,
                "totalPages": paginator.num_pages,
            },
        }
    )


@require_GET
def shipping_locations(request):
    search = request.GET.get("search", "").strip()[:100]
    if not search:
        return JsonResponse({"message": "Search wajib diisi."}, status=422)
    if _rate_limited(request, "shipping-location", 30):
        return JsonResponse({"message": "Terlalu sering mencari lokasi.", "retry_after": 60}, status=429)
    if not settings.COST_API_KEY:
        return JsonResponse({"message": "Layanan ongkir belum dikonfigurasi."}, status=503)
    query = urlencode({"search": search, "limit": 50})
    try:
        result = _shipping_request(
            f"https://rajaongkir.komerce.id/api/v1/destination/domestic-destination?{query}",
            method="GET",
        )
    except ShippingProviderError as exc:
        logger.warning("Shipping destination lookup failed: HTTP %s", exc.status_code)
        return JsonResponse(
            {"message": _shipping_error_message(exc.status_code, exc.error_code)}, status=502
        )
    except (OSError, ValueError, json.JSONDecodeError):
        logger.exception("Shipping destination lookup request failed")
        return JsonResponse({"message": "Layanan ongkir sedang tidak tersedia."}, status=502)
    locations = _extract_provider_list(result, ("data", "results", "items"))
    if locations is None:
        logger.error("Shipping provider returned an unexpected destination response")
        return JsonResponse({"message": "Layanan ongkir sedang tidak tersedia."}, status=502)
    return JsonResponse(locations, safe=False)


@require_GET
def shipping_cost(request):
    destination = request.GET.get("destination", "")
    weight = request.GET.get("weight", "1000")
    courier = request.GET.get("courier", "jne").lower()
    if not destination.isdigit():
        return JsonResponse({"message": "Destination ID wajib berupa angka."}, status=422)
    if not weight.isdigit() or not 1 <= int(weight) <= 50000:
        return JsonResponse({"message": "Berat harus antara 1 dan 50000 gram."}, status=422)
    if not re.fullmatch(r"[a-z][a-z0-9_-]{1,30}", courier):
        return JsonResponse({"message": "Kode kurir tidak valid."}, status=422)
    if _rate_limited(request, "shipping-cost", 20):
        return JsonResponse({"message": "Terlalu sering meminta ongkir. Coba lagi nanti."}, status=429)
    if not settings.COST_API_KEY:
        return JsonResponse({"message": "Layanan ongkir belum dikonfigurasi."}, status=503)
    try:
        options = _shipping_options(destination, courier, int(weight))
    except ShippingProviderError as exc:
        logger.warning("Shipping cost lookup failed: HTTP %s", exc.status_code)
        return JsonResponse(
            {"message": _shipping_error_message(exc.status_code, exc.error_code)}, status=502
        )
    except (OSError, ValueError, json.JSONDecodeError):
        logger.exception("Shipping cost lookup request failed")
        return JsonResponse({"message": "Layanan ongkir sedang tidak tersedia."}, status=502)
    return JsonResponse(options, safe=False)


def _shipping_options(destination, courier, weight):
    result = _shipping_request(
        "https://rajaongkir.komerce.id/api/v1/calculate/domestic-cost",
        method="POST",
        data={
            "origin": settings.SHIPPING_ORIGIN,
            "destination": destination,
            "weight": weight,
            "courier": courier,
        },
    )
    if not isinstance(result.get("data"), list):
        raise ValueError("Shipping provider returned an invalid response")
    return result["data"]


def _extract_provider_list(payload, keys):
    current = payload
    for _ in range(3):
        if isinstance(current, list):
            return current
        if not isinstance(current, dict):
            return None
        next_value = next((current[key] for key in keys if key in current), None)
        if next_value is None:
            return None
        current = next_value
    return current if isinstance(current, list) else None


def _shipping_error_message(status_code, error_code=None):
    if error_code == 1010:
        return (
            "Cloudflare provider memblokir signature request aplikasi (Error 1010), bukan menolak API key. "
            "Mulai ulang server untuk memakai identitas client baru; jika masih terjadi, minta Komerce "
            "mengizinkan API client atau IP server."
        )
    if status_code == 403:
        return (
            "Provider menolak akses request (HTTP 403). API key dapat aktif, tetapi produk/izin "
            "atau IP server mungkin belum diizinkan. Minta Komerce memeriksa akses akun."
        )
    if status_code == 401:
        return "Provider menolak kunci ongkir (HTTP 401/403). Periksa COST_API_KEY di .env lalu mulai ulang server."
    if status_code == 422:
        return "Provider menolak format pencarian/lokasi (HTTP 422). Coba nama lokasi yang lebih spesifik."
    if status_code == 429:
        return "Provider sedang membatasi permintaan (HTTP 429). Tunggu sebentar lalu coba lagi."
    return f"Layanan ongkir menolak permintaan (HTTP {status_code}). Coba lagi nanti."


def _api_key_authorized(request):
    provided = request.headers.get("X-API-Key", "")
    return bool(
        settings.API_KEY
        and provided
        and compare_digest(settings.API_KEY.encode(), provided.encode())
    )


def _rate_limited(request, scope, limit):
    key = f"rate:{scope}:{request.META.get('REMOTE_ADDR', 'unknown')}"
    cache.add(key, 0, timeout=60)
    try:
        count = cache.incr(key)
    except ValueError:
        cache.set(key, 1, timeout=60)
        count = 1
    return count > limit


def _positive_query_int(value, default):
    try:
        return max(1, int(value))
    except (TypeError, ValueError):
        return default


def _shipping_request(url, method, data=None):
    encoded = urlencode(data).encode() if data is not None else None
    request = Request(
        url,
        data=encoded,
        method=method,
        headers={
            "accept": "application/json",
            "key": settings.COST_API_KEY,
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": "TokoFR-Django/1.0 (shipping API client)",
        },
    )
    try:
        with urlopen(request, timeout=10) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        body = exc.read(4096)
        error_code = None
        try:
            error_payload = json.loads(body.decode("utf-8", errors="replace"))
            if isinstance(error_payload, dict):
                error_code = error_payload.get("error_code")
        except json.JSONDecodeError:
            pass
        raise ShippingProviderError(exc.code, error_code) from exc
    if not isinstance(payload, dict):
        raise ValueError("Invalid shipping provider response")
    return payload


def _is_valid_payment_image(uploaded):
    if not uploaded or uploaded.size > 5 * 1024 * 1024:
        return False
    try:
        with Image.open(uploaded) as image:
            if image.format not in {"JPEG", "PNG", "WEBP"}:
                return False
            image.verify()
        uploaded.seek(0)
        with Image.open(uploaded) as image:
            return image.width <= 10000 and image.height <= 10000
    except (OSError, UnidentifiedImageError, ValueError, Image.DecompressionBombError):
        return False
    finally:
        uploaded.seek(0)
