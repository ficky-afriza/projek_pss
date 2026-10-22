from decimal import Decimal


def cart(request):
    items = request.session.get("cart", {})
    total = sum(
        (Decimal(str(item["price"])) - Decimal(str(item.get("discount", "0"))))
        * int(item["quantity"])
        for item in items.values()
    )
    return {"cart_count": sum(int(item["quantity"]) for item in items.values()), "cart_total": total}
