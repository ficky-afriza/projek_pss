from django.contrib import admin, messages

from .models import AccountProfile, Category, ContactMessage, Discount, Order, OrderItem, Product, ProductImage


class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 1


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("name", "category", "price", "stock")
    list_filter = ("category",)
    search_fields = ("name", "description")
    inlines = (ProductImageInline,)


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "total", "status", "created_at")
    list_filter = ("status", "payment_method", "created_at")
    search_fields = ("user__username", "address")
    readonly_fields = ("created_at", "updated_at", "status")
    actions = ("confirm_payment", "reject_payment")

    @admin.action(description="Konfirmasi pembayaran (bukti wajib)")
    def confirm_payment(self, request, queryset):
        eligible = queryset.filter(
            status__in=(Order.Status.WAITING, Order.Status.REJECTED)
        ).exclude(payment_proof="")
        updated = eligible.update(status=Order.Status.PAID)
        self.message_user(
            request,
            f"{updated} pembayaran dikonfirmasi.",
            level=messages.SUCCESS if updated else messages.WARNING,
        )

    @admin.action(description="Tolak pesanan yang dipilih")
    def reject_payment(self, request, queryset):
        updated = queryset.filter(
            status__in=(Order.Status.WAITING, Order.Status.REJECTED)
        ).update(status=Order.Status.REJECTED)
        self.message_user(
            request,
            f"{updated} pesanan ditolak.",
            level=messages.SUCCESS if updated else messages.WARNING,
        )


admin.site.register(Category)
admin.site.register(Discount)
admin.site.register(ContactMessage)
admin.site.register(OrderItem)
admin.site.register(AccountProfile)
