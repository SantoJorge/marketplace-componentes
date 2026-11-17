"""CR-08: comprobacion basica de componentes, sin afirmar compatibilidad total."""
import re
from django.contrib import messages
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from apps.accounts.permissions import allowed, screen
from .models import Product, ProductTechnicalSpec


CATEGORY_KINDS = {
    "procesadores": "CPU",
    "tarjetas madre": "PLACA",
    "memoria ram": "RAM",
}


def normalize_socket(value):
    return re.sub(r"[^A-Z0-9]", "", str(value or "").upper())


def normalize_ddr(value):
    match = re.search(r"DDR[2-6]", str(value or "").upper())
    return match.group(0) if match else ""


def spec(product, field):
    if product is None:
        return ""
    technical = getattr(product, "technical_spec", None)
    return getattr(technical, field, "") if technical else ""


def evaluate(cpu, board, ram):
    """Basic socket/DDR check; incomplete selections retain INDEX warnings."""
    cpu_socket = normalize_socket(spec(cpu, "socket"))
    board_socket = normalize_socket(spec(board, "socket"))
    board_ddr = normalize_ddr(spec(board, "ram_type"))
    ram_ddr = normalize_ddr(spec(ram, "ram_type"))
    if not cpu or not board:
        socket_status = "SIN DATOS"
        cpu_message = "Selecciona CPU y placa madre para comparar."
    elif not cpu_socket or not board_socket:
        socket_status = "SIN DATOS"
        cpu_message = "Faltan datos de socket en uno o ambos productos."
    elif cpu_socket == board_socket:
        socket_status = "COMPATIBLE"
        cpu_message = "CPU y placa madre son compatibles (socket " + cpu_socket + ")."
    else:
        socket_status = "INCOMPATIBLE"
        cpu_message = "Sockets distintos: CPU " + cpu_socket + " vs. placa " + board_socket + "."
    if not ram or not board:
        ram_status = "SIN DATOS"
        ram_message = "Selecciona RAM y placa madre para comparar."
    elif not board_ddr or not ram_ddr:
        ram_status = "SIN DATOS"
        ram_message = "Faltan datos del tipo de memoria en uno o ambos productos."
    elif board_ddr == ram_ddr:
        ram_status = "COMPATIBLE"
        ram_message = "RAM y placa madre son compatibles (" + ram_ddr + ")."
    else:
        ram_status = "INCOMPATIBLE"
        ram_message = "Tipos de memoria distintos: RAM " + ram_ddr + " vs. placa " + board_ddr + "."
    general = (
        "INCOMPATIBLE" if "INCOMPATIBLE" in (socket_status, ram_status) else
        "DATOS INSUFICIENTES" if "SIN DATOS" in (socket_status, ram_status) else
        "COMPATIBLE"
    )
    return {
        "general": general, "socket": socket_status, "ram": ram_status,
        "cpu_socket": cpu_socket, "board_socket": board_socket,
        "board_ddr": board_ddr, "ram_ddr": ram_ddr,
        "cpu_message": cpu_message, "ram_message": ram_message,
    }


def comparador(request):
    products = Product.objects.filter(
        approval_status="APROBADO", active=True, stock__gt=0,
        category__active=True, seller__is_active=True,
    ).select_related("technical_spec")
    groups = {
        "cpu": products.filter(category__name__iexact="Procesadores").order_by("name"),
        "placa": products.filter(category__name__iexact="Tarjetas madre").order_by("name"),
        "ram": products.filter(category__name__iexact="Memoria RAM").order_by("name"),
    }
    selected_ids = {k: request.GET.get(k, "") for k in groups}
    chosen = {
        k: q.filter(pk=int(selected_ids[k])).first() if selected_ids[k].isdecimal() else None
        for k, q in groups.items()
    }
    template_name = ("catalog/_compatibilidad_inline.html" if request.GET.get("fragment") == "1" else "catalog/compatibilidad.html")
    return render(request, template_name, {
        "groups": groups,
        "selected_ids": selected_ids,
        "result": evaluate(chosen["cpu"], chosen["placa"], chosen["ram"]) if (request.GET.get("check") == "1" or any(selected_ids.values())) else None,
    })


@allowed("VENDEDOR")
def editar_especificacion(request, pk):
    product = get_object_or_404(
        Product.objects.select_related("category", "technical_spec"),
        pk=pk, seller=request.user,
    )
    kind = CATEGORY_KINDS.get(product.category.name.strip().casefold())
    if kind is None:
        messages.error(request, "Esta categoria no admite fichas CPU/placa/RAM.")
        return redirect("catalog:vendedor_productos")
    technical = getattr(product, "technical_spec", None)
    if request.method == "POST":
        socket = normalize_socket(request.POST.get("socket", ""))
        ddr = normalize_ddr(request.POST.get("ram_type", ""))
        if kind in ("CPU", "PLACA") and (not socket or len(socket) > 50):
            messages.error(request, "Indica un socket valido (ej.: AM4 o LGA1700).")
        elif kind in ("PLACA", "RAM") and not ddr:
            messages.error(request, "Indica un tipo de memoria DDR valido.")
        else:
            with transaction.atomic():
                ProductTechnicalSpec.objects.update_or_create(
                    product=product,
                    defaults={
                        "component_type": kind,
                        "socket": socket if kind != "RAM" else "",
                        "ram_type": ddr if kind != "CPU" else "",
                    },
                )
                Product.objects.filter(pk=product.pk).update(approval_status="PENDIENTE")
            messages.success(request, "Ficha guardada. Pendiente de aprobacion administrativa.")
            return redirect("catalog:vendedor_productos")
    return screen(request, "catalog/especificacion.html",
                  product=product, kind=kind, technical=technical)
