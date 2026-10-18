
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.core.paginator import Paginator
from django.db.models import Count, F, Q, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from apps.accounts.models import Profile
from apps.accounts.permissions import allowed, role, screen
from apps.catalog.forms import ProductForm
from apps.catalog.models import Category, Product
from apps.orders.models import PurchaseLine, PurchaseOrder

User = get_user_model()


# ============================================================
# PRODUCTOS VISIBLES PARA EL PUBLICO
# ============================================================

def available_products():
    return (
        Product.objects.filter(
            approval_status="APROBADO",
            active=True,
            stock__gt=0,
            category__active=True,
            seller__is_active=True,
        )
        .select_related("seller", "category")
    )


# ============================================================
# HOME / INICIO PUBLICO
# Accesible para visitantes y todos los roles
# ============================================================

def inicio(request):

    disponibles = available_products().order_by(
        "-created_at", "-pk"
    )

    # Hasta diez categorias populares con cantidades reales
    categorias = (
        Category.objects.filter(active=True)
        .annotate(
            cantidad_productos=Count(
                "products",
                filter=Q(
                    products__approval_status="APROBADO",
                    products__active=True,
                    products__stock__gt=0,
                    products__seller__is_active=True,
                ),
            )
        )
        .order_by("-cantidad_productos", "name")[:10]
    )

    # Determinar el destino del boton Vender
    rol_actual = role(request.user)

    if rol_actual == "ADMINISTRADOR":
        vender_url = reverse("management:dashboard")
        vender_texto = "Ir a administración"

    elif rol_actual == "VENDEDOR":
        vender_url = reverse("catalog:vendedor_dashboard")
        vender_texto = "Mi panel de vendedor"

    elif rol_actual == "COMPRADOR":
        vender_url = reverse("accounts:ser_vendedor")
        vender_texto = "Quiero vender"

    else:
        vender_url = reverse("accounts:login")
        vender_texto = "Vender componentes"

    # Enviar informacion real a la plantilla
    context = {
        "productos_destacados": disponibles[:4],
        "productos_recientes": disponibles[:8],
        "categorias": categorias,

        "total_productos": disponibles.count(),

        "total_vendedores": Profile.objects.filter(
            role="VENDEDOR",
            active=True,
            user__is_active=True
        ).count(),

        "total_categorias": Category.objects.filter(
            active=True
        ).count(),

        "total_ordenes": PurchaseOrder.objects.count(),

        "vender_url": vender_url,
        "vender_texto": vender_texto,
    }

    return render(
        request,
        "public/inicio.html",
        context
    )


# ============================================================
# VALIDACION DE PRECIOS DEL CATALOGO
# ============================================================

def _precio_valido(texto):
    try:
        if not texto or len(texto) > 14:
            return None

        numero = Decimal(texto)

        if (
            numero.is_finite()
            and Decimal("0") <= numero
            <= Decimal("99999999.99")
        ):
            return numero

        return None

    except (ValueError, ArithmeticError):
        return None


# ============================================================
# CATALOGO PUBLICO
# Soporta enlaces de categorias enviados desde HOME
# ============================================================


def catalogo(request):
    from decimal import Decimal, InvalidOperation
    from urllib.parse import urlencode

    from django.core.paginator import Paginator
    from django.db.models import Q
    from django.shortcuts import redirect, render
    from django.urls import reverse

    from apps.catalog.models import Category, Product

    # ==========================================
    # 1. RECORDAR FILTROS ENTRE PAGINAS
    # ==========================================

    url_catalogo = reverse("catalog:catalogo")
    clave = "mc_catalogo_filtros"

    # Borrar los filtros cuando se pulse Limpiar
    if request.GET.get("limpiar") == "1":
        request.session.pop(clave, None)
        return redirect(url_catalogo)

    # Regresar desde HOME o desde otro menu
    if not request.GET:
        filtros_guardados = request.session.get(clave, "")

        if filtros_guardados:
            return redirect(
                f"{url_catalogo}?{filtros_guardados}"
            )

    # ==========================================
    # 2. LEER Y VALIDAR LOS FILTROS
    # ==========================================

    consulta = request.GET.get("q", "").strip()[:90]

    categoria = request.GET.get(
        "categoria", ""
    ).strip()[:20]

    if not categoria.isdecimal():
        categoria = ""

    marca = request.GET.get(
        "marca", ""
    ).strip()[:100]

    condicion = request.GET.get(
        "condicion", ""
    ).strip().upper()[:20]

    if condicion not in dict(Product.CONDITION_CHOICES):
        condicion = ""

    minimo = request.GET.get("min", "").strip()[:20]
    maximo = request.GET.get("max", "").strip()[:20]

    orden = request.GET.get(
        "orden", "recientes"
    ).strip()

    ordenes = {
        "recientes": ("-created_at", "-pk"),
        "precio_asc": ("price", "pk"),
        "precio_desc": ("-price", "-pk"),
    }

    if orden not in ordenes:
        orden = "recientes"

    # ==========================================
    # 3. PRODUCTOS DE LA BASE DE DATOS
    # ==========================================

    productos = available_products()

    if consulta:
        productos = productos.filter(
            Q(name__icontains=consulta)
            | Q(brand__icontains=consulta)
            | Q(model__icontains=consulta)
            | Q(description__icontains=consulta)
        )

    if categoria:
        productos = productos.filter(
            category_id=int(categoria)
        )

    if marca:
        productos = productos.filter(
            brand__iexact=marca
        )

    if condicion:
        productos = productos.filter(
            condition=condicion
        )

    def precio_valido(valor):
        if not valor:
            return None

        try:
            precio = Decimal(valor)
        except (InvalidOperation, ValueError):
            return None

        if (
            precio.is_finite()
            and Decimal("0") <= precio
            <= Decimal("99999999.99")
        ):
            return precio

        return None

    precio_min = precio_valido(minimo)
    precio_max = precio_valido(maximo)

    if precio_min is not None:
        productos = productos.filter(
            price__gte=precio_min
        )

    if precio_max is not None:
        productos = productos.filter(
            price__lte=precio_max
        )

    productos = productos.order_by(*ordenes[orden])

    # ==========================================
    # 4. GUARDAR LOS FILTROS SELECCIONADOS
    # ==========================================

    filtros = {}

    valores = {
        "q": consulta,
        "categoria": categoria,
        "marca": marca,
        "condicion": condicion,
        "min": minimo,
        "max": maximo,
        "orden": orden,
    }

    for nombre, valor in valores.items():
        if valor and not (
            nombre == "orden" and valor == "recientes"
        ):
            filtros[nombre] = valor

    filtros_url = urlencode(filtros)

    if request.GET:
        if filtros_url:
            request.session[clave] = filtros_url
        else:
            request.session.pop(clave, None)

    # ==========================================
    # 5. PAGINACION
    # ==========================================

    pagina = Paginator(
        productos, 12
    ).get_page(request.GET.get("page"))

    # ==========================================
    # 6. OPCIONES REALES DE FILTROS
    # ==========================================

    categorias = Category.objects.filter(
        active=True
    ).order_by("name")

    marcas = sorted(
        {
            valor
            for valor in available_products()
            .values_list("brand", flat=True)
            .distinct()
            if valor
        },
        key=str.casefold
    )

    # ==========================================
    # 7. ENVIAR INFORMACION AL HTML
    # ==========================================

    contexto = {
        "productos": pagina,
        "pagina": pagina,
        "total_resultados": pagina.paginator.count,
        "consulta": consulta,
        "categorias": categorias,
        "categoria_actual": categoria,
        "selected_category": categoria,
        "marcas": marcas,
        "selected_brand": marca,
        "condiciones": Product.CONDITION_CHOICES,
        "selected_condition": condicion,
        "precio_minimo": minimo,
        "precio_maximo": maximo,
        "orden": orden,
        "filtros_url": filtros_url,
    }

    return render(
        request,
        "public/catalogo.html",
        contexto
    )


# ============================================================
# TIENDA ORIGINAL - COMPATIBILIDAD
# ============================================================

def shop(request):

    products = available_products()

    q = request.GET.get("q", "").strip()[:90]
    category = request.GET.get("categoria", "")

    if q:
        products = products.filter(
            Q(name__icontains=q)
            | Q(brand__icontains=q)
            | Q(model__icontains=q)
            | Q(description__icontains=q)
        )

    if category.isdecimal():
        products = products.filter(
            category_id=int(category)
        )

    return screen(
        request,
        "catalog/tienda.html",
        products=products[:80],
        categories=Category.objects.filter(active=True),
        query=q,
        selected_category=category,
    )


# ============================================================
# DETALLE DE PRODUCTO ORIGINAL
# ============================================================

def product_detail(request, pk):

    return screen(
        request,
        "catalog/producto.html",
        product=get_object_or_404(
            available_products(),
            pk=pk
        ),
    )


# ============================================================
# FUNCIONES EXISTENTES DEL VENDEDOR
# Se mantienen para no afectar la fase Vendedor
# ============================================================


@allowed("VENDEDOR")
def seller_dashboard(request):
    """
    FASE 4.4 - DASHBOARD DEL VENDEDOR
    Replica las estadísticas del INDEX original
    utilizando los datos reales del marketplace.
    """

    # Productos pertenecientes al vendedor.
    mine = Product.objects.filter(
        seller=request.user
    )

    product_stats = mine.aggregate(
        total=Count("pk"),

        pending=Count(
            "pk",
            filter=Q(approval_status="PENDIENTE")
        ),

        approved=Count(
            "pk",
            filter=Q(approval_status="APROBADO")
        ),

        rejected=Count(
            "pk",
            filter=Q(approval_status="RECHAZADO")
        ),

        inactive=Count(
            "pk",
            filter=Q(active=False)
        ),

        units=Sum("stock"),
    )

    # Ventas reales del vendedor.
    # Los pedidos cancelados no cuentan.
    lines = PurchaseLine.objects.filter(
        seller=request.user
    ).exclude(
        order__status="CANCELADO"
    )

    sales_stats = lines.aggregate(
        sold_units=Sum("quantity"),

        revenue=Sum(
            F("quantity") * F("unit_price")
        ),
    )

    # Datos para la gráfica.
    # Se agrupan las unidades vendidas
    # por nombre de producto.
    chart_data = list(
        lines.values("product_name")
        .annotate(value=Sum("quantity"))
        .order_by("-value", "product_name")[:7]
    )

    return screen(
        request,
        "catalog/vendedor_dashboard.html",

        total_products=product_stats["total"] or 0,
        pending=product_stats["pending"] or 0,
        approved=product_stats["approved"] or 0,
        rejected=product_stats["rejected"] or 0,
        inactive=product_stats["inactive"] or 0,
        units=product_stats["units"] or 0,

        sold_units=sales_stats["sold_units"] or 0,
        revenue=sales_stats["revenue"] or Decimal("0.00"),

        chart_data=chart_data,
    )



@allowed("VENDEDOR")
def seller_products(request):
    """
    FASE 4.3 - Mis productos.

    Funcionalidades:
    - Listar publicaciones del vendedor autenticado.
    - Activar o desactivar productos.
    - Eliminar productos sin historial de ventas.
    - Conservar los productos vinculados a pedidos reales.
    """

    if request.method == "POST":

        action = request.POST.get("action", "")
        product_id = request.POST.get("product_id", "")

        # Validar la acción y el identificador recibido.
        if (
            action not in ("toggle", "delete")
            or not product_id.isdecimal()
        ):
            messages.error(
                request,
                "No se pudo procesar la acción solicitada."
            )
            return redirect("catalog:vendedor_productos")

        # Seguridad: el producto debe pertenecer
        # al vendedor que inició sesión.
        product = get_object_or_404(
            Product,
            pk=int(product_id),
            seller=request.user
        )

        # ACTIVAR / DESACTIVAR
        if action == "toggle":

            product.active = not product.active

            product.save(
                update_fields=["active", "updated_at"]
            )

            if product.active:
                messages.success(
                    request,
                    "Producto activado correctamente."
                )
            else:
                messages.success(
                    request,
                    "Producto desactivado correctamente."
                )

        # ELIMINAR
        elif action == "delete":

            # No eliminar registros que forman parte
            # del historial de compras y ventas.
            if PurchaseLine.objects.filter(
                product=product
            ).exists():

                messages.warning(
                    request,
                    "Este producto tiene ventas registradas "
                    "y no puede eliminarse. Puedes "
                    "desactivarlo para ocultarlo del catálogo."
                )

            else:
                from django.db.models.deletion import ProtectedError

                try:
                    product.delete()

                except ProtectedError:
                    messages.error(
                        request,
                        "No se pudo eliminar el producto "
                        "porque tiene registros relacionados."
                    )

                else:
                    messages.success(
                        request,
                        "Producto eliminado correctamente."
                    )

        return redirect("catalog:vendedor_productos")

    # GET: mostrar todos los productos del vendedor,
    # incluidos pendientes, rechazados e inactivos.
    products = (
        Product.objects
        .filter(seller=request.user)
        .select_related("category")
        .order_by("-created_at", "-pk")
    )

    return screen(
        request,
        "catalog/vendedor_productos.html",
        products=products,
    )


@allowed("VENDEDOR")
def seller_product_edit(request, pk=None):

    obj = (
        get_object_or_404(
            Product,
            pk=pk,
            seller=request.user
        )
        if pk else None
    )

    form = ProductForm(
        request.POST or None,
        request.FILES or None,
        instance=obj
    )

    if request.method == "POST" and form.is_valid():

        p = form.save(commit=False)
        p.seller = request.user
        p.approval_status = "PENDIENTE"
        p.save()

        messages.success(
            request,
            "Producto guardado y enviado a revisión."
        )

        return redirect(
            "catalog:vendedor_productos"
        )


    return screen(
        request,
        "catalog/vendedor_producto_form.html",

        form=form,
        title=(
            "Editar producto"
            if pk else "Publicar producto"
        ),
        hint=(
            "Cada edición requiere una nueva "
            "aprobación administrativa."
        ),
        back="catalog:vendedor_productos",
        multipart=True,
    )
