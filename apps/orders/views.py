from django.shortcuts import (
    render,
    redirect,
    get_object_or_404
)

from apps.catalog.models import Product

from .models import (
    Cart,
    CartItem,
)


def get_or_create_cart(request):

    if request.user.is_authenticated:

        cart, created = Cart.objects.get_or_create(
            user=request.user
        )

        return cart


    if not request.session.session_key:

        request.session.create()


    cart, created = Cart.objects.get_or_create(
        session_key=request.session.session_key
    )

    return cart


def cart_detail(request):

    cart = get_or_create_cart(request)

    items = (
        cart.items
        .select_related(
            "product",
            "product__seller",
            "product__category"
        )
        .all()
    )

    context = {
        "cart": cart,
        "items": items,
    }

    return render(
        request,
        "orders/carrito.html",
        context
    )


def add_to_cart(request, product_id):

    product = get_object_or_404(
        Product,
        id=product_id,
        approval_status="APROBADO",
        active=True
    )

    if product.stock <= 0:

        return redirect(
            "catalog:catalogo"
        )


    cart = get_or_create_cart(request)


    item, created = (
        CartItem.objects.get_or_create(
            cart=cart,
            product=product,
            defaults={
                "quantity": 1
            }
        )
    )


    if not created:

        if item.quantity < product.stock:

            item.quantity += 1
            item.save()


    return redirect(
        "orders:cart_detail"
    )


def increase_quantity(request, item_id):

    cart = get_or_create_cart(request)

    item = get_object_or_404(
        CartItem,
        id=item_id,
        cart=cart
    )


    if item.quantity < item.product.stock:

        item.quantity += 1
        item.save()


    return redirect(
        "orders:cart_detail"
    )


def decrease_quantity(request, item_id):

    cart = get_or_create_cart(request)

    item = get_object_or_404(
        CartItem,
        id=item_id,
        cart=cart
    )


    if item.quantity > 1:

        item.quantity -= 1
        item.save()

    else:

        item.delete()


    return redirect(
        "orders:cart_detail"
    )


def remove_from_cart(request, item_id):

    cart = get_or_create_cart(request)

    item = get_object_or_404(
        CartItem,
        id=item_id,
        cart=cart
    )

    item.delete()

    return redirect(
        "orders:cart_detail"
    )