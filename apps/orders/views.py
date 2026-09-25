from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.catalog.models import Producto


def ver_carrito(request):
    carrito = request.session.get("carrito", {})
    productos = Producto.objects.filter(id__in=carrito.keys(), activo=True)

    articulos = []
    total = 0

    for producto in productos:
        cantidad = carrito.get(str(producto.id), 0)
        subtotal = producto.precio * cantidad
        total += subtotal
        articulos.append({
            "producto": producto,
            "cantidad": cantidad,
            "subtotal": subtotal,
        })

    return render(request, "orders/carrito.html", {
        "articulos": articulos,
        "total": total,
    })


@require_POST
def agregar_al_carrito(request, producto_id):
    producto = get_object_or_404(Producto, id=producto_id, activo=True)
    carrito = request.session.get("carrito", {})
    clave = str(producto.id)
    carrito[clave] = carrito.get(clave, 0) + 1
    request.session["carrito"] = carrito
    return redirect("carrito")


@require_POST
def cambiar_cantidad(request, producto_id):
    carrito = request.session.get("carrito", {})
    clave = str(producto_id)

    if clave in carrito:
        try:
            cantidad = int(request.POST.get("cantidad", 1))
        except ValueError:
            cantidad = 1

        if cantidad <= 0:
            carrito.pop(clave)
        else:
            carrito[clave] = cantidad

    request.session["carrito"] = carrito
    return redirect("carrito")


@require_POST
def quitar_del_carrito(request, producto_id):
    carrito = request.session.get("carrito", {})
    carrito.pop(str(producto_id), None)
    request.session["carrito"] = carrito
    return redirect("carrito")
