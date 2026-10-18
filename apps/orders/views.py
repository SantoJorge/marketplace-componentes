from django.views.decorators.http import require_POST
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



@require_POST
def add_to_cart(request, product_id):
    # El catalogo añade una unidad utilizando
    # la misma logica de la ficha de producto.
    return cart_add(request, pk=product_id)


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


@require_POST
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


@require_POST
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


@require_POST
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

# Funcionalidades integradas desde el módulo antiguo; conservan los modelos reales.
from decimal import Decimal
from django.contrib import messages
from django.contrib.auth import get_user_model, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordChangeForm
from django.db import transaction
from django.db.models import F, Q, Sum
from django.http import HttpResponseForbidden, HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST
from apps.accounts.models import Profile, SellerProfile, SellerRequest
from apps.accounts.permissions import role, allowed, screen
from apps.catalog.models import Category, Product
from apps.orders.models import Cart, CartItem, PurchaseOrder, PurchaseLine
User = get_user_model()

from apps.orders.forms import CheckoutForm


def get_market_cart(request):
    """Conserva carrito invitado durante login y evita perder sus artículos."""
    cart = get_or_create_cart(request)
    if not request.user.is_authenticated:
        request.session['mc_guest_cart_id'] = cart.pk
        return cart
    guest_id = request.session.pop('mc_guest_cart_id', None)
    if guest_id:
        guest = Cart.objects.filter(pk=guest_id, user__isnull=True).first()
        if guest and guest.pk != cart.pk:
            with transaction.atomic():
                for item in guest.items.select_related('product'):
                    current, _ = CartItem.objects.get_or_create(cart=cart, product=item.product,
                                                                 defaults={'quantity': 0})
                    current.quantity = min(item.product.stock, current.quantity + item.quantity)
                    if current.quantity > 0:
                        current.save(update_fields=['quantity','updated_at'])
                    else:
                        current.delete()
                guest.delete()
    return cart


##CODIGO ACTUALIZADO QUE PERMITIRA MENSAJE FLOTANTE


@require_POST
def cart_add(request, pk):
    from django.http import JsonResponse
    from django.utils.http import url_has_allowed_host_and_scheme
    from apps.catalog.views import available_products

    ajax = (
        request.headers.get("X-Requested-With")
        == "XMLHttpRequest"
    )

    def responder(correcto, mensaje, estado=200, cantidad_total=None):
        # JavaScript recibe JSON y no cambia de pagina.
        if ajax:
            datos = {
                "ok": correcto,
                "message": mensaje,
            }

            if cantidad_total is not None:
                datos["cart_count"] = cantidad_total

            return JsonResponse(datos, status=estado)

        # Alternativa cuando JavaScript esta desactivado.
        if correcto:
            messages.success(request, mensaje)
        else:
            messages.error(request, mensaje)

        anterior = request.META.get("HTTP_REFERER", "")

        if anterior and url_has_allowed_host_and_scheme(
            url=anterior,
            allowed_hosts={request.get_host()},
            require_https=request.is_secure(),
        ):
            return redirect(anterior)

        return redirect("catalog:catalogo")

    # Solo productos disponibles del catalogo publico.
    product = available_products().filter(pk=pk).first()

    if product is None:
        return responder(
            False,
            "Este producto no esta disponible.",
            404,
        )

    # Impedir comprar productos propios.
    if (
        request.user.is_authenticated
        and request.user.pk == product.seller_id
    ):
        return responder(
            False,
            "No puedes comprar tus propios productos.",
            403,
        )

    # Leer la cantidad.
    # Catalogo: 1 unidad por defecto.
    # Ficha: cantidad seleccionada por el usuario.
    try:
        cantidad = int(
            request.POST.get("quantity", "1")
        )
    except (TypeError, ValueError):
        return responder(
            False,
            "Cantidad invalida.",
            400,
        )

    if cantidad < 1 or cantidad > 100:
        return responder(
            False,
            "La cantidad debe estar entre 1 y 100.",
            400,
        )

    # Carrito existente de invitado o usuario.
    cart = get_market_cart(request)

    with transaction.atomic():

        item = (
            CartItem.objects
            .select_for_update()
            .filter(cart=cart, product=product)
            .first()
        )

        actual = item.quantity if item else 0

        if actual + cantidad > product.stock:
            return responder(
                False,
                "No hay suficientes unidades disponibles.",
                409,
            )

        if item is None:
            CartItem.objects.create(
                cart=cart,
                product=product,
                quantity=cantidad,
            )
        else:
            item.quantity = actual + cantidad
            item.save(
                update_fields=[
                    "quantity",
                    "updated_at",
                ]
            )

    total_unidades = (
        cart.items.aggregate(total=Sum("quantity"))["total"]
        or 0
    )

    return responder(
        True,
        "Producto añadido al carrito.",
        cantidad_total=total_unidades,
    )




#MODIFICADO FASE 2.3.2


def cart_view(request):
    cart = get_market_cart(request)

    items = list(
        cart.items
        .select_related(
            "product",
            "product__seller",
            "product__category",
        )
        .order_by("pk")
    )

    total = sum(
        (item.subtotal for item in items),
        Decimal("0.00"),
    )

    cantidad_articulos = sum(
        item.quantity for item in items
    )

    return screen(
        request,
        "orders/carrito.html",
        items=items,
        total=total,
        cantidad_articulos=cantidad_articulos,
    )


@require_POST
def cart_clear(request):
    # Vaciar solamente el carrito
    # perteneciente al visitante o usuario actual.
    cart = get_market_cart(request)

    if cart.items.exists():
        cart.items.all().delete()
        messages.success(request, "Carrito vaciado.")
    else:
        messages.info(request, "El carrito ya está vacío.")

    return redirect("orders:cart_detail")



@require_POST
def cart_change(request,pk):
    cart=get_market_cart(request)
    item=get_object_or_404(CartItem,pk=pk,cart=cart)
    action=request.POST.get('action')
    if action=='delete': item.delete()
    elif action in ('plus','minus'):
        if action=='plus':
            if item.quantity<item.product.stock: item.quantity+=1
            else: messages.error(request,'Se alcanzó el stock disponible.')
        elif item.quantity>1: item.quantity-=1
        else: item.delete(); return redirect('orders:cart_detail')
        item.save(update_fields=['quantity','updated_at'])
    else: return HttpResponseBadRequest('Acción inválida.')
    return redirect('orders:cart_detail')



##MODIFICADO MODIFICADO FASE 2.4
@allowed('COMPRADOR', 'VENDEDOR', 'ADMINISTRADOR')
def checkout(request):
    from apps.catalog.views import available_products

    cart = get_market_cart(request)

    items = list(
        cart.items.select_related(
            "product",
            "product__seller",
            "product__category",
        ).order_by("pk")
    )

    if not items:
        messages.error(
            request,
            "Tu carrito está vacío."
        )
        return redirect("orders:cart_detail")

    # Datos iniciales del comprador.
    initial = {
        "contact_name": (
            request.user.get_full_name()
            or request.user.username
        )
    }

    try:
        initial.update(
            contact_phone=request.user.profile.phone,
            province=request.user.profile.province,
        )
    except Profile.DoesNotExist:
        pass

    form = CheckoutForm(
        request.POST if request.method == "POST" else None,
        initial=initial,
    )

    # Confirmar solo mediante POST y formulario válido.
    if request.method == "POST" and form.is_valid():

        try:
            with transaction.atomic():

                # Bloquear el carrito para evitar que
                # dos solicitudes lo confirmen a la vez.
                Cart.objects.select_for_update().get(
                    pk=cart.pk
                )

                # Consultar de nuevo los productos dentro
                # de la transacción.
                productos_carrito = list(
                    CartItem.objects
                    .select_for_update()
                    .filter(cart_id=cart.pk)
                    .select_related(
                        "product",
                        "product__seller",
                        "product__category",
                    )
                    .order_by("pk")
                )

                if not productos_carrito:
                    raise ValueError(
                        "El carrito ya fue procesado o está vacío."
                    )

                # Usar el mismo criterio del Catálogo.
                ids_disponibles = set(
                    available_products()
                    .filter(
                        pk__in=[
                            i.product_id
                            for i in productos_carrito
                        ]
                    )
                    .values_list("pk", flat=True)
                )

                total = Decimal("0.00")
                lineas = []

                for item in productos_carrito:
                    producto = item.product
                    cantidad = item.quantity

                    if producto.pk not in ids_disponibles:
                        raise ValueError(
                            f"{producto.name}: "
                            "producto no disponible."
                        )

                    # Regla de seguridad del INDEX.
                    if producto.seller_id == request.user.pk:
                        raise ValueError(
                            f"No puedes comprar tu propio "
                            f"producto: {producto.name}."
                        )

                    if cantidad < 1:
                        raise ValueError(
                            f"{producto.name}: cantidad inválida."
                        )

                    # Descontar stock solo si hay
                    # suficientes unidades disponibles.
                    actualizados = Product.objects.filter(
                        pk=producto.pk,
                        stock__gte=cantidad,
                        active=True,
                        approval_status="APROBADO",
                        category__active=True,
                        seller__is_active=True,
                    ).update(
                        stock=F("stock") - cantidad
                    )

                    if actualizados != 1:
                        raise ValueError(
                            f"{producto.name}: "
                            "stock insuficiente o producto "
                            "no disponible."
                        )

                    total += producto.price * cantidad

                    lineas.append(
                        (producto, cantidad)
                    )

                # Registrar la compra real.
                pedido = PurchaseOrder.objects.create(
                    buyer=request.user,
                    total=total,
                    **form.cleaned_data,
                )

                # Guardar productos, vendedor,
                # cantidad y precio de la compra.
                PurchaseLine.objects.bulk_create([
                    PurchaseLine(
                        order=pedido,
                        product=producto,
                        seller=producto.seller,
                        product_name=producto.name,
                        unit_price=producto.price,
                        quantity=cantidad,
                    )
                    for producto, cantidad in lineas
                ])

                # Vaciar solamente el carrito confirmado.
                CartItem.objects.filter(
                    cart_id=cart.pk
                ).delete()

        except ValueError as error:
            messages.error(request, str(error))
            return redirect("orders:cart_detail")

        messages.success(
            request,
            "Pedido registrado correctamente. "
            "El pago y la entrega se coordinan "
            "con el vendedor. No se ha cobrado nada."
        )

        return redirect(
            "orders:pedido_detalle",
            pk=pedido.pk,
        )

    # La pantalla de compra pertenece a la
    # experiencia pública, no al panel administrativo.
    total = sum(
        (i.subtotal for i in items),
        Decimal("0.00"),
    )

    cantidad_articulos = sum(
        i.quantity for i in items
    )

    return render(
        request,
        "orders/compra.html",
        {
            "form": form,
            "items": items,
            "total": total,
            "cantidad_articulos": cantidad_articulos,
        },
    )



#MODIFICADO EN FASE 3.1

@allowed("COMPRADOR", "VENDEDOR", "ADMINISTRADOR")
def my_orders(request):
    """
    Historial de compras del usuario autenticado.
    Carga los productos para calcular las unidades
    sin realizar consultas individuales por pedido.
    """

    orders = list(
        PurchaseOrder.objects
        .filter(buyer=request.user)
        .prefetch_related("lines")
        .order_by("-created_at", "-pk")
    )

    for order in orders:
        order.items_count = sum(
            line.quantity
            for line in order.lines.all()
        )

    return screen(
        request,
        "orders/pedidos.html",
        orders=orders,
        orders_count=len(orders),
    )



@allowed('COMPRADOR','VENDEDOR','ADMINISTRADOR')
def order_detail(request,pk):
    qs=PurchaseOrder.objects.select_related('buyer').prefetch_related('lines__seller')
    if role(request.user)!='ADMINISTRADOR': qs=qs.filter(buyer=request.user)
    order=get_object_or_404(qs,pk=pk)
    return screen(request,'orders/pedido_detalle.html',order=order)



@require_POST
@allowed('COMPRADOR','VENDEDOR','ADMINISTRADOR')
def cancel_order(request,pk):
    with transaction.atomic():
        order=get_object_or_404(PurchaseOrder.objects.select_for_update(),pk=pk,buyer=request.user)
        if order.status!='PENDIENTE' or order.lines.exclude(status='PENDIENTE').exists():
            messages.error(request,'Ya no puedes cancelar este pedido.')
            return redirect('orders:pedido_detalle',pk=pk)
        order.status='CANCELADO'; order.save(update_fields=['status','updated_at'])
        for item in order.lines.all():
            Product.objects.filter(pk=item.product_id).update(stock=F('stock')+item.quantity)
    messages.success(request,'Pedido cancelado y stock restablecido.')
    return redirect('orders:pedido_detalle',pk=pk)



@allowed('VENDEDOR')
def seller_sales(request):
    lines=PurchaseLine.objects.filter(seller=request.user).select_related('order','order__buyer','product')
    return screen(request,'orders/vendedor_ventas.html',lines=lines)



@require_POST
@allowed('VENDEDOR')
def seller_sale_status(request,pk):
    allowed_next={'PENDIENTE':'PREPARANDO','PREPARANDO':'ENVIADO','ENVIADO':'ENTREGADO'}
    with transaction.atomic():
        line=get_object_or_404(PurchaseLine.objects.select_for_update().select_related('order'),pk=pk,seller=request.user)
        order=PurchaseOrder.objects.select_for_update().get(pk=line.order_id)
        next_state=allowed_next.get(line.status)
        if not next_state or order.status=='CANCELADO':
            messages.error(request,'La venta no permite este cambio de estado.')
        else:
            line.status=next_state; line.save(update_fields=['status'])
            statuses=list(order.lines.values_list('status',flat=True))
            order.status='COMPLETADO' if statuses and all(s=='ENTREGADO' for s in statuses) else 'EN_PROCESO'
            order.save(update_fields=['status','updated_at'])
            messages.success(request,'Estado de venta actualizado.')
    return redirect('orders:vendedor_ventas')


# FASE 2.3.3 - CONTADOR DINAMICO DEL CARRITO
from django.views.decorators.http import require_GET


@require_GET
def cart_count(request):
    from django.http import JsonResponse

    # Reutilizar el carrito real del usuario o invitado.
    cart = get_market_cart(request)

    # Contar unidades, no productos diferentes.
    cantidad = (
        cart.items.aggregate(total=Sum("quantity"))["total"]
        or 0
    )

    response = JsonResponse({
        "count": cantidad
    })

    response["Cache-Control"] = "no-store"

    return response
