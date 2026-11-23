
import os
import sys
from collections import Counter
from decimal import Decimal

# ============================================================
# MARKETPLACECOMPONENTES - FASE 10G.2
# CARGA CONTROLADA DE 150 PRODUCTOS DEMO
# ============================================================

BASE_PRINCIPAL = "marketplace_componentes"
BASE_DESARROLLO = "marketplace_componentes_dev"

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

# Seleccionar una BD de desarrollo sin modificar settings.py.
# No crea bases de datos ni altera los datos existentes.
base_alternativa = os.environ.get("MC_DEMO_DB_NAME", "").strip()

if base_alternativa:
    if base_alternativa != BASE_DESARROLLO:
        raise RuntimeError(
            "SEGURIDAD: MC_DEMO_DB_NAME no esta autorizada."
        )

    from django.conf import settings
    settings.DATABASES["default"]["NAME"] = BASE_DESARROLLO

import django
django.setup()

from django.db import connection, transaction
from django.utils import timezone
from apps.accounts.models import SellerProfile
from apps.catalog.models import Category, Product


# Identificador para evitar duplicaciones
ETIQUETA = "[DEMO-MC150-20261019]"

# Categoria | Marca | Modelo | Precio de prueba en USD

DATOS = """
Procesadores|AMD|Ryzen 5 5500|95
Procesadores|AMD|Ryzen 5 5600|125
Procesadores|AMD|Ryzen 5 5600G|135
Procesadores|AMD|Ryzen 5 5600X|145
Procesadores|AMD|Ryzen 7 5700X|185
Procesadores|AMD|Ryzen 7 5800X|205
Procesadores|AMD|Ryzen 5 7600|225
Procesadores|AMD|Ryzen 5 7600X|245
Procesadores|AMD|Ryzen 7 7700|285
Procesadores|AMD|Ryzen 7 7700X|305
Procesadores|AMD|Ryzen 7 7800X3D|385
Procesadores|AMD|Ryzen 9 7900|405
Procesadores|Intel|Core i3-12100F|110
Procesadores|Intel|Core i3-13100|150
Procesadores|Intel|Core i5-12400F|145
Procesadores|Intel|Core i5-13400F|215
Procesadores|Intel|Core i5-14400F|235
Procesadores|Intel|Core i5-14600K|330
Procesadores|Intel|Core i7-13700K|385
Procesadores|Intel|Core i7-14700K|445
Tarjetas gráficas|MSI|GeForce RTX 3050 VENTUS 2X 8G|220
Tarjetas gráficas|ASUS|Dual GeForce RTX 3060 12GB|315
Tarjetas gráficas|Gigabyte|GeForce RTX 3060 WINDFORCE OC 12G|310
Tarjetas gráficas|ZOTAC|Gaming GeForce RTX 4060 Twin Edge|315
Tarjetas gráficas|MSI|GeForce RTX 4060 VENTUS 2X BLACK 8G|320
Tarjetas gráficas|ASUS|Dual GeForce RTX 4060 OC 8GB|335
Tarjetas gráficas|Gigabyte|GeForce RTX 4060 Ti EAGLE 8G|420
Tarjetas gráficas|MSI|GeForce RTX 4060 Ti GAMING X 16G|485
Tarjetas gráficas|ASUS|Dual GeForce RTX 4070 12GB|590
Tarjetas gráficas|Gigabyte|GeForce RTX 4070 WINDFORCE OC 12G|605
Tarjetas gráficas|MSI|GeForce RTX 4070 SUPER VENTUS 2X 12G|665
Tarjetas gráficas|ZOTAC|Gaming GeForce RTX 4070 SUPER Twin Edge|670
Tarjetas gráficas|Gigabyte|GeForce RTX 4070 Ti SUPER GAMING OC 16G|885
Tarjetas gráficas|ASUS|TUF Gaming GeForce RTX 4080 SUPER 16GB|1190
Tarjetas gráficas|MSI|GeForce RTX 4090 GAMING X TRIO 24G|1790
Tarjetas gráficas|Sapphire|PULSE Radeon RX 6600 8GB|225
Tarjetas gráficas|XFX|Speedster SWFT 210 Radeon RX 7600 8GB|285
Tarjetas gráficas|ASRock|Challenger Radeon RX 7600 XT 16GB|350
Tarjetas gráficas|Sapphire|PULSE Radeon RX 7800 XT 16GB|545
Tarjetas gráficas|XFX|Speedster MERC 310 Radeon RX 7900 XTX 24GB|995
Memoria RAM|Kingston|FURY Beast 8GB DDR4 3200MHz|25
Memoria RAM|Kingston|FURY Beast 16GB DDR4 3200MHz|42
Memoria RAM|Kingston|FURY Beast 32GB DDR4 3200MHz|78
Memoria RAM|Kingston|FURY Beast 16GB DDR5 5600MHz|63
Memoria RAM|Kingston|FURY Beast 32GB DDR5 5600MHz|112
Memoria RAM|Corsair|Vengeance LPX 8GB DDR4 3200MHz|27
Memoria RAM|Corsair|Vengeance LPX 16GB DDR4 3200MHz|45
Memoria RAM|Corsair|Vengeance LPX 32GB DDR4 3200MHz|85
Memoria RAM|Corsair|Vengeance 32GB DDR5 6000MHz|125
Memoria RAM|Corsair|Vengeance RGB 32GB DDR5 6000MHz|140
Memoria RAM|G.Skill|Ripjaws V 16GB DDR4 3600MHz|44
Memoria RAM|G.Skill|Ripjaws V 32GB DDR4 3600MHz|83
Memoria RAM|G.Skill|Flare X5 32GB DDR5 6000MHz|118
Memoria RAM|G.Skill|Trident Z5 RGB 32GB DDR5 6000MHz|155
Memoria RAM|Crucial|Pro 16GB DDR4 3200MHz|43
Memoria RAM|Crucial|Pro 32GB DDR5 5600MHz|108
Memoria RAM|ADATA|XPG GAMMIX D35 16GB DDR4 3200MHz|40
Memoria RAM|ADATA|XPG LANCER 32GB DDR5 6000MHz|119
Memoria RAM|TEAMGROUP|T-FORCE DELTA RGB 32GB DDR5 6000MHz|134
Memoria RAM|Patriot|Viper Steel 16GB DDR4 3600MHz|46
Tarjetas madre|MSI|B550M PRO-VDH WIFI|115
Tarjetas madre|MSI|MAG B550 TOMAHAWK|160
Tarjetas madre|ASUS|PRIME B550M-A WIFI II|119
Tarjetas madre|Gigabyte|B550 AORUS ELITE V2|145
Tarjetas madre|ASRock|B550M Steel Legend|125
Tarjetas madre|MSI|PRO B650M-A WIFI|175
Tarjetas madre|MSI|MAG B650 TOMAHAWK WIFI|225
Tarjetas madre|ASUS|TUF GAMING B650-PLUS WIFI|230
Tarjetas madre|Gigabyte|B650 AORUS ELITE AX|235
Tarjetas madre|ASRock|B650M Pro RS WiFi|169
Tarjetas madre|MSI|PRO B760M-A WIFI DDR4|155
Tarjetas madre|ASUS|PRIME B760M-A D4|145
Tarjetas madre|Gigabyte|B760 GAMING X AX DDR4|177
Tarjetas madre|MSI|MAG Z790 TOMAHAWK WIFI|285
Tarjetas madre|ASUS|TUF GAMING Z790-PLUS WIFI|295
Almacenamiento|Kingston|NV2 500GB NVMe SSD|42
Almacenamiento|Kingston|NV2 1TB NVMe SSD|63
Almacenamiento|Kingston|NV2 2TB NVMe SSD|120
Almacenamiento|Kingston|KC3000 1TB NVMe SSD|98
Almacenamiento|Kingston|A400 480GB SATA SSD|38
Almacenamiento|Western Digital|Blue SN580 500GB NVMe SSD|48
Almacenamiento|Western Digital|Blue SN580 1TB NVMe SSD|72
Almacenamiento|Western Digital|Black SN770 1TB NVMe SSD|94
Almacenamiento|Western Digital|Black SN850X 2TB NVMe SSD|180
Almacenamiento|Samsung|870 EVO 500GB SATA SSD|59
Almacenamiento|Samsung|870 EVO 1TB SATA SSD|105
Almacenamiento|Samsung|980 PRO 1TB NVMe SSD|115
Almacenamiento|Samsung|990 PRO 2TB NVMe SSD|195
Almacenamiento|Crucial|P3 Plus 500GB NVMe SSD|49
Almacenamiento|Crucial|P3 Plus 1TB NVMe SSD|74
Almacenamiento|Crucial|P3 Plus 2TB NVMe SSD|135
Almacenamiento|Seagate|BarraCuda 1TB HDD 3.5in|51
Almacenamiento|Seagate|BarraCuda 2TB HDD 3.5in|72
Almacenamiento|Western Digital|Blue 2TB HDD 3.5in|75
Almacenamiento|Toshiba|P300 3TB HDD 3.5in|90
Fuentes de poder|Corsair|CX550 550W 80 PLUS Bronze|69
Fuentes de poder|Corsair|CX650 650W 80 PLUS Bronze|79
Fuentes de poder|Corsair|RM750e 750W 80 PLUS Gold|125
Fuentes de poder|Corsair|RM850x 850W 80 PLUS Gold|159
Fuentes de poder|Cooler Master|MWE Bronze 550 V2|65
Fuentes de poder|Cooler Master|MWE Gold 750 V2|115
Fuentes de poder|Thermaltake|Smart BX1 650W 80 PLUS Bronze|75
Fuentes de poder|Thermaltake|Toughpower GF A3 850W 80 PLUS Gold|132
Fuentes de poder|MSI|MAG A650BN 650W 80 PLUS Bronze|67
Fuentes de poder|MSI|MPG A850G PCIE5 850W 80 PLUS Gold|145
Fuentes de poder|EVGA|600 BR 600W 80 PLUS Bronze|69
Fuentes de poder|Seasonic|FOCUS GX-750 750W 80 PLUS Gold|134
Fuentes de poder|Seasonic|FOCUS GX-850 850W 80 PLUS Gold|154
Fuentes de poder|DeepCool|PK650D 650W 80 PLUS Bronze|70
Fuentes de poder|DeepCool|PX850G 850W 80 PLUS Gold|135
Gabinetes|NZXT|H5 Flow Mid Tower|105
Gabinetes|NZXT|H7 Flow Mid Tower|145
Gabinetes|Corsair|4000D Airflow Mid Tower|115
Gabinetes|Corsair|3000D Airflow Mid Tower|89
Gabinetes|Cooler Master|MasterBox Q300L Mini Tower|68
Gabinetes|Cooler Master|TD500 Mesh V2 Mid Tower|119
Gabinetes|Lian Li|LANCOOL 216 Mid Tower|118
Gabinetes|Lian Li|LANCOOL 205 Mesh Mid Tower|99
Gabinetes|Montech|X3 Mesh Mid Tower|76
Gabinetes|Phanteks|Eclipse G360A Mid Tower|107
Refrigeración para CPU|Noctua|NH-D15 Disipador CPU|115
Refrigeración para CPU|Noctua|NH-U12S Disipador CPU|76
Refrigeración para CPU|Noctua|NH-L9i Disipador CPU|55
Refrigeración para CPU|DeepCool|AK400 Disipador CPU|42
Refrigeración para CPU|DeepCool|AK620 Disipador CPU|76
Refrigeración para CPU|DeepCool|AG400 Disipador CPU|33
Refrigeración para CPU|DeepCool|LE500 Refrigeración Líquida 240mm|79
Refrigeración para CPU|Thermalright|Peerless Assassin 120 SE Disipador CPU|49
Refrigeración para CPU|Thermalright|Assassin X 120 Refined SE Disipador CPU|31
Refrigeración para CPU|Corsair|iCUE H100i ELITE Refrigeración Líquida 240mm|145
Refrigeración para CPU|Corsair|iCUE H150i ELITE Refrigeración Líquida 360mm|195
Refrigeración para CPU|ARCTIC|Freezer 36 Disipador CPU|37
Refrigeración para CPU|ARCTIC|Liquid Freezer III 240 Refrigeración Líquida|105
Refrigeración para CPU|Cooler Master|Hyper 212 Halo Disipador CPU|47
Refrigeración para CPU|Cooler Master|MasterLiquid ML240L V2 Refrigeración Líquida|88
Ventiladores y accesorios internos|ARCTIC|P12 PWM PST Ventilador 120mm|13
Ventiladores y accesorios internos|ARCTIC|P14 PWM PST Ventilador 140mm|16
Ventiladores y accesorios internos|Corsair|AF120 ELITE Ventilador 120mm|25
Ventiladores y accesorios internos|Corsair|AF140 ELITE Ventilador 140mm|31
Ventiladores y accesorios internos|Noctua|NF-A12x25 PWM Ventilador 120mm|37
Ventiladores y accesorios internos|Noctua|NF-P12 redux-1700 PWM Ventilador 120mm|20
Ventiladores y accesorios internos|Cooler Master|SickleFlow 120 ARGB Ventilador|19
Ventiladores y accesorios internos|Thermalright|TL-C12C-S Ventilador 120mm|12
Ventiladores y accesorios internos|DeepCool|FC120 Ventilador 120mm|21
Ventiladores y accesorios internos|be quiet!|Pure Wings 2 Ventilador 120mm|17
Ventiladores y accesorios internos|ARCTIC|MX-4 Pasta térmica 4g|11
Ventiladores y accesorios internos|ARCTIC|MX-6 Pasta térmica 4g|13
Ventiladores y accesorios internos|Noctua|NT-H1 Pasta térmica 3.5g|12
Ventiladores y accesorios internos|Thermal Grizzly|Kryonaut Pasta térmica 1g|14
Ventiladores y accesorios internos|Cooler Master|MasterGel Pro V2 Pasta térmica|12
"""


def campo_tiempo(modelo, nombre):
    campo = modelo._meta.get_field(nombre)

    return not (
        campo.auto_now
        or campo.auto_now_add
        or campo.has_default()
    )


def cargar_productos():

    # ========================================================
    # VALIDACIONES DE SEGURIDAD
    # ========================================================

    argumentos_desconocidos = [
        arg for arg in sys.argv[1:] if arg != "--apply"
    ]

    if argumentos_desconocidos:
        raise RuntimeError(
            "Argumentos no reconocidos: "
            + ", ".join(argumentos_desconocidos)
        )

    aplicar = "--apply" in sys.argv[1:]
    nombre_base = str(connection.settings_dict.get("NAME", ""))

    if connection.vendor != "mysql":
        raise RuntimeError(
            "SEGURIDAD: La base de datos no es MySQL."
        )

    if nombre_base not in {
        BASE_PRINCIPAL,
        BASE_DESARROLLO,
    }:
        raise RuntimeError(
            "SEGURIDAD: Base MySQL no autorizada."
        )

    # Prohibir escrituras en la base principal.
    if aplicar and nombre_base != BASE_DESARROLLO:
        raise RuntimeError(
            "SEGURIDAD: Prohibido insertar productos DEMO "
            "en la base principal."
        )

    # Exigir autorizacion adicional para cualquier carga.
    if aplicar and os.environ.get("MC_AUTORIZAR_DEMO") != "SI":
        raise RuntimeError(
            "SEGURIDAD: Falta MC_AUTORIZAR_DEMO=SI "
            "para cargar datos DEMO."
        )

    # ========================================================
    # VALIDACION DEL CATALOGO
    # ========================================================

    productos = []

    for numero, linea in enumerate(
        DATOS.strip().splitlines(), 1
    ):

        partes = [p.strip() for p in linea.split("|")]

        if len(partes) != 4:
            raise ValueError(
                f"Linea {numero}: formato incorrecto"
            )

        categoria, marca, modelo, precio = partes

        productos.append(
            (categoria, marca, modelo, Decimal(precio))
        )

    if len(productos) != 150:
        raise RuntimeError(
            "El catalogo no contiene exactamente 150 productos."
        )

    unicos = {(p[1], p[2]) for p in productos}

    if len(unicos) != 150:
        raise RuntimeError(
            "Existen productos duplicados en el catalogo."
        )

    # ========================================================
    # VALIDACION DE VENDEDORES
    # ========================================================

    vendedores = list(
        SellerProfile.objects.select_related("user")
        .filter(
            user__username__in=("ana", "carlos"),
            active=True,
            user__profile__active=True,
            user__profile__role="VENDEDOR",
            user__is_active=True,
        )
        .order_by("user__username")
    )

    if {v.user.username for v in vendedores} != {
        "ana", "carlos"
    }:
        raise RuntimeError(
            "Ana y Carlos deben ser vendedores activos."
        )

    # ========================================================
    # MODO PREVISUALIZACION - NO MODIFICA MYSQL
    # ========================================================

    if not aplicar:

        print("\nMODO PREVISUALIZACION")
        print("No se modificara ninguna tabla.")
        print("BASE:", nombre_base)
        print("PRODUCTOS EXISTENTES:", Product.objects.count())
        print("VENDEDORES:", [v.user.username for v in vendedores])
        print("PRODUCTOS NUEVOS: 150")
        print("ANA: 75")
        print("CARLOS: 75")

        print("\nDISTRIBUCION POR CATEGORIA:")

        for categoria, total in Counter(
            p[0] for p in productos
        ).items():
            print(categoria, ":", total)

        existentes = set(
            Category.objects.filter(
                name__in={p[0] for p in productos}
            ).values_list("name", flat=True)
        )

        faltantes = {p[0] for p in productos} - existentes

        print("\nCATEGORIAS POR CREAR:")
        print(sorted(faltantes))
        print("\nPREVISUALIZACION FINALIZADA.")
        return

    # ========================================================
    # PREPARACION DE IMPORTACION
    # ========================================================

    antes = Product.objects.count()
    creados = 0
    omitidos = 0
    por_vendedor = Counter()
    categorias_nuevas = []
    ahora = timezone.now()

    # Impide dos importaciones simultaneas mediante
    # un bloqueo de sesion de MySQL.
    bloqueo = "MC150_DEMO_DEV_IMPORT"
    obtenido = False

    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT GET_LOCK(%s, 10)",
                [bloqueo]
            )
            obtenido = cursor.fetchone()[0] == 1

        if not obtenido:
            raise RuntimeError(
                "No fue posible bloquear la importacion DEMO."
            )

        # Una transaccion protege toda la carga.
        with transaction.atomic():

            categorias = {}

            iconos = {
                "Tarjetas madre": "▣",
                "Fuentes de poder": "⚡",
                "Gabinetes": "▤",
                "Refrigeración para CPU": "❄",
                "Ventiladores y accesorios internos": "✦",
            }

            # =================================================
            # CREAR O RECUPERAR CATEGORIAS
            # =================================================

            for nombre in dict.fromkeys(
                p[0] for p in productos
            ):

                defaults = {
                    "icon": iconos.get(nombre, "⚙"),
                    "active": True,
                }

                if campo_tiempo(Category, "created_at"):
                    defaults["created_at"] = ahora

                categoria, nueva = Category.objects.get_or_create(
                    name=nombre,
                    defaults=defaults
                )

                if nueva:
                    categorias_nuevas.append(nombre)

                elif not categoria.active:
                    raise RuntimeError(
                        f"Categoria inactiva: {nombre}"
                    )

                categorias[nombre] = categoria

            # =================================================
            # INSERTAR PRODUCTOS SIN DUPLICAR
            # =================================================

            for indice, datos_producto in enumerate(productos):

                nombre_categoria, marca, modelo, precio = datos_producto

                perfil = vendedores[indice % 2]
                vendedor = perfil.user

                nombre_producto = f"{marca} {modelo}"

                ya_existe = Product.objects.filter(
                    seller=vendedor,
                    name=nombre_producto,
                    description__contains=ETIQUETA
                ).exists()

                if ya_existe:
                    omitidos += 1
                    continue

                condicion = "NUEVO"

                if indice % 13 == 0:
                    condicion = "REACONDICIONADO"

                elif indice % 9 == 0:
                    condicion = "USADO"

                descripcion = (
                    f"{ETIQUETA} "
                    f"Componente de demostracion: {nombre_producto}. "
                    "Precio, condicion y existencias simuladas "
                    "para pruebas de MarketplaceComponentes. "
                    "Verificar compatibilidad y especificaciones "
                    "antes de una venta real."
                )

                nuevo_producto = {
                    "seller": vendedor,
                    "category": categorias[nombre_categoria],
                    "name": nombre_producto,
                    "description": descripcion,
                    "brand": marca,
                    "model": modelo,
                    "price": precio,
                    "stock": 3 + (indice % 13),
                    "condition": condicion,
                    "location": perfil.location or "Panamá",
                    "approval_status": "APROBADO",
                    "active": True,
                }

                if campo_tiempo(Product, "created_at"):
                    nuevo_producto["created_at"] = ahora

                if campo_tiempo(Product, "updated_at"):
                    nuevo_producto["updated_at"] = ahora

                Product.objects.create(**nuevo_producto)

                creados += 1
                por_vendedor[vendedor.username] += 1

    finally:
        if obtenido:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT RELEASE_LOCK(%s)",
                    [bloqueo]
                )

    # ========================================================
    # RESULTADO FINAL
    # ========================================================

    despues = Product.objects.count()

    total_demo = Product.objects.filter(
        description__contains=ETIQUETA
    ).count()

    print("\n================================")
    print("RESULTADO DE IMPORTACION MYSQL")
    print("================================")
    print("BASE:", connection.settings_dict["NAME"])
    print("PRODUCTOS ANTES:", antes)
    print("PRODUCTOS INSERTADOS:", creados)
    print("PRODUCTOS OMITIDOS:", omitidos)
    print("PRODUCTOS DEMO:", total_demo)
    print("PRODUCTOS TOTALES:", despues)
    print("NUEVOS POR VENDEDOR:", dict(por_vendedor))
    print("CATEGORIAS CREADAS:", categorias_nuevas)

    if total_demo == 150:
        print("\nOK: LOS 150 PRODUCTOS ESTAN REGISTRADOS.")
    else:
        print("\nAVISO: REVISAR TOTAL DE PRODUCTOS DEMO.")


if __name__ == "__main__":
    cargar_productos()
