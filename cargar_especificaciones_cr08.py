
"""
MarketplaceComponentes
CR08 - Carga de especificaciones del catalogo demo.

No modifica productos, precios, stock ni aprobaciones.
No sobrescribe especificaciones existentes.
"""

import re

from collections import Counter
from django.db import connection, transaction
from apps.catalog.models import Product, ProductTechnicalSpec


CPU_AM4 = {
    "AMD Ryzen 5 5500",
    "AMD Ryzen 5 5600",
    "AMD Ryzen 5 5600G",
    "AMD Ryzen 5 5600X",
    "AMD Ryzen 7 5700X",
    "AMD Ryzen 7 5800X",
}

CPU_AM5 = {
    "AMD Ryzen 5 7600",
    "AMD Ryzen 5 7600X",
    "AMD Ryzen 7 7700",
    "AMD Ryzen 7 7700X",
    "AMD Ryzen 7 7800X3D",
    "AMD Ryzen 9 7900",
}

CPU_INTEL = {
    "Intel Core i3-12100F",
    "Intel Core i3-13100",
    "Intel Core i5-12400F",
    "Intel Core i5-13400F",
    "Intel Core i5-14400F",
    "Intel Core i5-14600K",
    "Intel Core i7-13700K",
    "Intel Core i7-14700K",
}


PLACAS = {
    "ASRock B550M Steel Legend": ("AM4", "DDR4"),
    "ASUS PRIME B550M-A WIFI II": ("AM4", "DDR4"),
    "Gigabyte B550 AORUS ELITE V2": ("AM4", "DDR4"),
    "MSI B550M PRO-VDH WIFI": ("AM4", "DDR4"),
    "MSI MAG B550 TOMAHAWK": ("AM4", "DDR4"),

    "ASRock B650M Pro RS WiFi": ("AM5", "DDR5"),
    "ASUS TUF GAMING B650-PLUS WIFI": ("AM5", "DDR5"),
    "Gigabyte B650 AORUS ELITE AX": ("AM5", "DDR5"),
    "MSI MAG B650 TOMAHAWK WIFI": ("AM5", "DDR5"),
    "MSI PRO B650M-A WIFI": ("AM5", "DDR5"),

    "ASUS PRIME B760M-A D4": ("LGA1700", "DDR4"),
    "Gigabyte B760 GAMING X AX DDR4": ("LGA1700", "DDR4"),
    "MSI PRO B760M-A WIFI DDR4": ("LGA1700", "DDR4"),

    "MSI MAG Z790 TOMAHAWK WIFI": ("LGA1700", "DDR5"),
    "ASUS TUF GAMING Z790-PLUS WIFI": ("LGA1700", "DDR5"),
}


def clasificar(producto):

    nombre = producto.name.strip()
    categoria = producto.category.name.strip().casefold()

    if categoria == "procesadores":

        if nombre in CPU_AM4:
            return "CPU", "AM4", ""

        if nombre in CPU_AM5:
            return "CPU", "AM5", ""

        if nombre in CPU_INTEL:
            return "CPU", "LGA1700", ""

    elif categoria == "tarjetas madre":

        if nombre in PLACAS:
            socket, ddr = PLACAS[nombre]
            return "PLACA", socket, ddr

    elif categoria == "memoria ram":

        coincidencias = set(
            re.findall(r"DDR[2-6]", nombre.upper())
        )

        if len(coincidencias) == 1:
            return "RAM", "", coincidencias.pop()

    return None


def cargar(aplicar=False):

    connection.ensure_connection()

    motor = connection.vendor
    base = connection.settings_dict["NAME"]

    print("=" * 65)
    print("MARKETPLACE - ESPECIFICACIONES CR08")
    print("MOTOR:", motor)
    print("BASE:", base)
    print("MODO:", "APLICAR" if aplicar else "SIMULACION")
    print("=" * 65)

    if motor != "mysql" or base != "marketplace_componentes":
        raise RuntimeError(
            "ALTO: base de datos no autorizada."
        )

    contador = Counter()

    with transaction.atomic():

        productos = Product.objects.filter(
            category__name__in=[
                "Procesadores",
                "Tarjetas madre",
                "Memoria RAM",
            ]
        ).select_related("category").order_by("pk")

        if aplicar:
            productos = productos.select_for_update()

        for producto in productos:

            datos = clasificar(producto)

            if datos is None:
                contador["SIN_CLASIFICAR"] += 1
                print("REVISAR:", producto.pk, producto.name)
                continue

            tipo, socket, ddr = datos

            defaults = {
                "component_type": tipo,
                "socket": socket,
                "ram_type": ddr,
            }

            existente = ProductTechnicalSpec.objects.filter(
                product=producto
            ).first()

            if existente:

                actual = (
                    existente.component_type,
                    existente.socket,
                    existente.ram_type,
                )

                if actual == datos:
                    contador["EXISTENTES"] += 1
                else:
                    contador["CONFLICTOS"] += 1
                    print("CONFLICTO:", producto.name)

                continue

            if aplicar:

                ficha, creada = (
                    ProductTechnicalSpec.objects.get_or_create(
                        product=producto,
                        defaults=defaults,
                    )
                )

                if not creada:
                    raise RuntimeError(
                        "Cambio concurrente detectado. Operacion cancelada."
                    )

            contador["NUEVAS"] += 1
            contador[tipo] += 1

            print(
                f"{producto.pk:03d} | "
                f"{tipo:5s} | "
                f"{socket or '-':8s} | "
                f"{ddr or '-':5s} | "
                f"{producto.name}"
            )

        if aplicar and contador["CONFLICTOS"]:
            raise RuntimeError(
                "Conflictos detectados. Se revierten las inserciones."
            )

    print("=" * 65)
    print("RESUMEN")
    print("CPU:", contador["CPU"])
    print("PLACAS:", contador["PLACA"])
    print("RAM:", contador["RAM"])
    print("FICHAS NUEVAS:", contador["NUEVAS"])
    print("FICHAS EXISTENTES:", contador["EXISTENTES"])
    print("CONFLICTOS:", contador["CONFLICTOS"])
    print("SIN CLASIFICAR:", contador["SIN_CLASIFICAR"])
    print("TOTAL EN BD:", ProductTechnicalSpec.objects.count())
    print("TOTAL PRODUCTOS:", Product.objects.count())
    print("=" * 65)
    print("CARGA COMPLETADA" if aplicar else "SIMULACION COMPLETADA")
