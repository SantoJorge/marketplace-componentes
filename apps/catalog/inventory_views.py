"""CR-09: consulta de stock disponible y reservas por vendedor."""
from django.db.models import Sum
from apps.accounts.permissions import allowed, screen
from apps.catalog.models import Product
from apps.orders.models import StockReservation


@allowed("VENDEDOR")
def vendedor_inventario(request):
    products = list(Product.objects.filter(seller=request.user).order_by("name"))
    grouped = StockReservation.objects.filter(
        product__seller=request.user, status="ACTIVA",
    ).values("product_id").annotate(units=Sum("quantity"))
    reserved = {item["product_id"]: item["units"] for item in grouped}
    for product in products:
        product.reserved_cr09 = reserved.get(product.pk, 0)
        product.total_cr09 = product.stock + product.reserved_cr09
    return screen(request, "catalog/vendedor_inventario.html", products=products)
