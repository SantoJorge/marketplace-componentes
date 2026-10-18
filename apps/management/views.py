"""Vistas administrativas; utilizan los modelos existentes de las otras apps."""

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

from apps.catalog.forms import CategoryForm



@allowed("ADMINISTRADOR")
def admin_dashboard(request):
    from decimal import Decimal
    from django.db.models import Count, Sum

    # Estadísticas reales de usuarios
    total_usuarios = User.objects.count()

    total_compradores = Profile.objects.filter(
        role="COMPRADOR"
    ).count()

    total_vendedores = Profile.objects.filter(
        role="VENDEDOR"
    ).count()

    # Solicitudes de vendedores pendientes
    solicitudes_pendientes = SellerRequest.objects.filter(
        status="PENDIENTE"
    ).count()

    # Estadísticas de productos
    total_productos = Product.objects.count()

    productos_pendientes = Product.objects.filter(
        approval_status="PENDIENTE"
    ).count()

    # Órdenes y valor de las no canceladas
    total_ordenes = PurchaseOrder.objects.count()

    ventas_totales = (
        PurchaseOrder.objects
        .exclude(status="CANCELADO")
        .aggregate(total=Sum("total"))["total"]
        or Decimal("0.00")
    )

    # Agrupación real por categoría para el gráfico
    # Igual al INDEX: todos los productos registrados.
    categorias_agrupadas = (
        Product.objects
        .values("category__name")
        .annotate(cantidad=Count("id"))
        .order_by("-cantidad", "category__name")[:7]
    )

    grafica_categorias = [
        {
            "label": fila["category__name"] or "Otros",
            "value": fila["cantidad"],
        }
        for fila in categorias_agrupadas
    ]

    return screen(
        request,
        "management/dashboard.html",

        # Estadísticas
        users=total_usuarios,
        buyers=total_compradores,
        sellers=total_vendedores,
        products=total_productos,
        pending_requests=solicitudes_pendientes,
        pending_products=productos_pendientes,
        orders=total_ordenes,
        revenue=ventas_totales,

        # Variable existente conservada
        categories=Category.objects.filter(
            active=True
        ).count(),

        # Datos del gráfico
        chart_data=grafica_categorias,
    )




@allowed("ADMINISTRADOR")
def admin_users(request):
    from django.db.models import Count, Q, Value
    from django.db.models.functions import Concat

    q = request.GET.get("q", "").strip()[:80]
    selected_role = (
        request.GET.get("role", "")
        .strip()
        .upper()
    )

    valid_roles = {
        "",
        "COMPRADOR",
        "VENDEDOR",
        "ADMINISTRADOR",
    }

    if selected_role not in valid_roles:
        selected_role = ""

    # Total sin filtros, igual que en el INDEX.
    users_total = User.objects.count()

    queryset = (
        User.objects
        .select_related(
            "profile",
            "seller_profile",
        )
        .order_by("-date_joined")
    )

    # Búsqueda por nombre completo, nombre de usuario
    # y correo electrónico.
    if q:
        queryset = queryset.annotate(
            _full_name=Concat(
                "first_name",
                Value(" "),
                "last_name",
            )
        ).filter(
            Q(username__icontains=q)
            | Q(first_name__icontains=q)
            | Q(last_name__icontains=q)
            | Q(email__icontains=q)
            | Q(_full_name__icontains=q)
        )

    # Filtrado de roles.
    # Un superusuario siempre se muestra como ADMINISTRADOR.
    if selected_role == "ADMINISTRADOR":
        queryset = queryset.filter(
            Q(is_superuser=True)
            | Q(profile__role="ADMINISTRADOR")
        )

    elif selected_role == "VENDEDOR":
        queryset = queryset.filter(
            is_superuser=False,
            profile__role="VENDEDOR",
        )

    elif selected_role == "COMPRADOR":
        queryset = queryset.filter(
            is_superuser=False
        ).filter(
            Q(profile__role="COMPRADOR")
            | Q(profile__isnull=True)
        )

    users_filtered_total = queryset.count()

    # Cantidades reales para el modal del INDEX.
    queryset = queryset.annotate(
        admin_orders_count=Count(
            "market_orders",
            distinct=True,
        ),
        admin_products_count=Count(
            "products",
            distinct=True,
        ),
    )

    users = list(queryset[:150])

    for item in users:
        profile = getattr(item, "profile", None)
        seller_profile = getattr(
            item,
            "seller_profile",
            None,
        )

        if item.is_superuser:
            item.admin_role = "ADMINISTRADOR"
        elif profile is not None:
            item.admin_role = profile.role
        else:
            item.admin_role = "COMPRADOR"

        # Estado efectivo, considerando usuario y perfil.
        item.admin_active = (
            item.is_active
            and (
                profile.active
                if profile is not None
                else True
            )
        )

        # Protección de cuentas administrativas y propias.
        item.admin_can_toggle = (
            item.pk != request.user.pk
            and not item.is_superuser
            and not item.is_staff
            and item.admin_role != "ADMINISTRADOR"
        )

        item.admin_phone = (
            profile.phone if profile else ""
        )

        item.admin_province = (
            profile.province if profile else ""
        )

        item.admin_business_name = (
            seller_profile.business_name
            if seller_profile else ""
        )

        item.admin_display_name = (
            item.get_full_name().strip()
            or item.username
        )

        item.admin_initials = (
            "".join(
                part[:1].upper()
                for part in (
                    item.first_name,
                    item.last_name,
                )
                if part.strip()
            )
            or item.username[:2].upper()
        )

    return screen(
        request,
        "management/usuarios.html",
        users=users,
        users_total=users_total,
        users_filtered_total=users_filtered_total,
        query=q,
        selected_role=selected_role,
    )


@require_POST
@allowed("ADMINISTRADOR")
def admin_user_toggle(request, pk):
    from django.urls import reverse
    from urllib.parse import urlencode

    q = request.POST.get("q", "").strip()[:80]
    selected_role = (
        request.POST.get("role", "")
        .strip()
        .upper()
    )

    if selected_role not in {
        "",
        "COMPRADOR",
        "VENDEDOR",
        "ADMINISTRADOR",
    }:
        selected_role = ""

    with transaction.atomic():
        target = get_object_or_404(
            User.objects.select_for_update(),
            pk=pk,
        )

        profile = getattr(target, "profile", None)

        # Comprobar el rol persistente directamente.
        # role(target) no serviría para administradores
        # inactivos, porque devolvería BLOQUEADO.
        is_administrator = (
            target.is_superuser
            or (
                profile is not None
                and profile.role == "ADMINISTRADOR"
            )
        )

        if (
            target.pk == request.user.pk
            or target.is_superuser
            or target.is_staff
            or is_administrator
        ):
            return HttpResponseForbidden(
                "No puedes modificar esta cuenta administrativa."
            )

        active_now = (
            target.is_active
            and (
                profile.active
                if profile is not None
                else True
            )
        )

        new_active = not active_now

        target.is_active = new_active
        target.save(update_fields=["is_active"])

        if profile is None:
            profile = Profile.objects.create(
                user=target,
                active=new_active,
            )
        else:
            profile.active = new_active
            profile.save(update_fields=["active"])

    messages.success(
        request,
        "Usuario activado correctamente."
        if new_active
        else "Usuario desactivado correctamente.",
    )

    # Regresar a los filtros que tenía abiertos.
    params = {}

    if q:
        params["q"] = q

    if selected_role:
        params["role"] = selected_role

    url = reverse("management:usuarios")

    if params:
        url += "?" + urlencode(params)

    return redirect(url)



@allowed('ADMINISTRADOR')
def admin_requests(request):
    return screen(request,'management/solicitudes.html',requests=SellerRequest.objects.select_related('user'))



@require_POST
@allowed('ADMINISTRADOR')
def admin_request_action(request,pk):
    action=request.POST.get('action')
    if action not in ('approve','reject'): return HttpResponseBadRequest('Acción inválida.')
    with transaction.atomic():
        obj=get_object_or_404(SellerRequest.objects.select_for_update().select_related('user'),pk=pk,status='PENDIENTE')
        if action=='approve':
            if not obj.user.is_active or obj.user.is_superuser:
                return HttpResponseForbidden('La cuenta no puede recibir rol vendedor.')
            profile,_=Profile.objects.get_or_create(user=obj.user)
            profile.role='VENDEDOR'; profile.active=True; profile.save(update_fields=['role','active'])
            SellerProfile.objects.update_or_create(user=obj.user,defaults={'business_name':obj.business_name,'business_description':obj.business_description,'business_phone':obj.business_phone,'location':obj.location,'active':True})
            obj.status='APROBADA'
        else:
            obj.status='RECHAZADA'
        obj.review_note=request.POST.get('note','').strip()[:255]
        obj.reviewed_at=timezone.now(); obj.save(update_fields=['status','review_note','reviewed_at'])
    messages.success(request,'Solicitud revisada.')
    return redirect('management:solicitudes')



@allowed("ADMINISTRADOR")
def admin_products(request):
    status = request.GET.get("status", "TODOS").upper()

    estados_validos = {
        "TODOS",
        "PENDIENTE",
        "APROBADO",
        "RECHAZADO",
    }

    if status not in estados_validos:
        status = "TODOS"

    products = (
        Product.objects
        .select_related(
            "seller",
            "seller__seller_profile",
            "category",
        )
        .order_by("-created_at")
    )

    if status != "TODOS":
        products = products.filter(
            approval_status=status
        )

    products_total = products.count()

    return screen(
        request,
        "management/productos.html",
        products=products[:150],
        products_total=products_total,
        status=status,
        is_pending=(status == "PENDIENTE"),
    )


@require_POST
@allowed("ADMINISTRADOR")
def admin_product_action(request, pk):
    action = request.POST.get("action", "").strip()

    if action not in {
        "APROBADO",
        "RECHAZADO",
        "PENDIENTE",
    }:
        return HttpResponseBadRequest("Acción inválida.")

    with transaction.atomic():
        product = get_object_or_404(
            Product.objects.select_for_update(),
            pk=pk,
        )

        product.approval_status = action

        if action == "APROBADO":
            product.active = True
            product.save(
                update_fields=[
                    "approval_status",
                    "active",
                    "updated_at",
                ]
            )
        else:
            product.save(
                update_fields=[
                    "approval_status",
                    "updated_at",
                ]
            )

    mensajes = {
        "APROBADO": "Producto aprobado correctamente.",
        "RECHAZADO": "Producto rechazado correctamente.",
        "PENDIENTE": "Producto devuelto a revisión.",
    }

    messages.success(request, mensajes[action])

    response = redirect("management:productos")

    if request.POST.get("return_to_pending") == "1":
        response["Location"] += "?status=PENDIENTE"

    return response


@require_POST
@allowed("ADMINISTRADOR")
def admin_product_delete(request, pk):
    from django.db.models.deletion import (
        ProtectedError,
        RestrictedError,
    )

    try:
        with transaction.atomic():
            product = get_object_or_404(
                Product.objects.select_for_update(),
                pk=pk,
            )

            nombre = product.name
            product.delete()

    except (ProtectedError, RestrictedError):
        messages.error(
            request,
            "Este producto no se puede eliminar porque "
            "tiene registros asociados, como ventas o pedidos. "
            "Se conservó su información.",
        )
    else:
        messages.success(
            request,
            f'Producto "{nombre}" eliminado correctamente.',
        )

    response = redirect("management:productos")

    if request.POST.get("return_to_pending") == "1":
        response["Location"] += "?status=PENDIENTE"

    return response



@allowed("ADMINISTRADOR")
def admin_categories(request):
    from django.db.models import Count

    categories = (
        Category.objects
        .annotate(product_count=Count("products", distinct=True))
        .order_by("name")
    )

    return screen(
        request,
        "management/categorias.html",
        categories=categories,
    )


@allowed("ADMINISTRADOR")
def admin_category_edit(request, pk=None):
    obj = get_object_or_404(Category, pk=pk) if pk else None

    form = CategoryForm(
        request.POST or None,
        instance=obj,
    )

    if request.method == "POST" and form.is_valid():
        nombre = form.cleaned_data["name"].strip()

        duplicados = Category.objects.filter(
            name__iexact=nombre
        )

        if obj is not None:
            duplicados = duplicados.exclude(pk=obj.pk)

        if duplicados.exists():
            form.add_error(
                "name",
                "Ya existe una categoría con ese nombre.",
            )
        else:
            form.save()

            messages.success(
                request,
                "Categoría actualizada correctamente."
                if obj
                else "Categoría creada correctamente.",
            )
            return redirect("management:categorias")

    return screen(
        request,
        "includes/formulario.html",
        form=form,
        title="Editar categoría" if obj else "Nueva categoría",
        hint=(
            "Las categorías existentes con productos "
            "asociados no se eliminan."
        ),
        back="management:categorias",
    )


@require_POST
@allowed("ADMINISTRADOR")
def admin_category_toggle(request, pk):
    with transaction.atomic():
        category = get_object_or_404(
            Category.objects.select_for_update(),
            pk=pk,
        )

        category.active = not category.active
        category.save(update_fields=["active"])

        nombre = category.name
        activa = category.active

    messages.success(
        request,
        f'Categoría "{nombre}" '
        + ("activada." if activa else "desactivada."),
    )

    return redirect("management:categorias")



@allowed("ADMINISTRADOR")
def admin_orders(request):
    from django.db.models import Sum

    queryset = (
        PurchaseOrder.objects
        .select_related("buyer")
        .prefetch_related("lines")
        .annotate(total_articulos=Sum("lines__quantity"))
        .order_by("-created_at")
    )

    orders = list(queryset[:150])

    for order in orders:
        lines = list(order.lines.all())

        order.puede_cancelar = all(
            line.status == "PENDIENTE"
            for line in lines
        )

        order.puede_completar = (
            bool(lines)
            and all(
                line.status == "ENTREGADO"
                for line in lines
            )
        )

    return screen(
        request,
        "management/pedidos.html",
        orders=orders,
        orders_total=PurchaseOrder.objects.count(),
    )


@require_POST
@allowed("ADMINISTRADOR")
def admin_pedido_estado(request, pk):
    nuevo_estado = request.POST.get("status", "").strip()

    estados_validos = {
        estado for estado, nombre in PurchaseOrder.STATUSES
    }

    if nuevo_estado not in estados_validos:
        messages.error(request, "Estado de pedido inválido.")
        return redirect("management:pedidos")

    with transaction.atomic():
        pedido = get_object_or_404(
            PurchaseOrder.objects.select_for_update(),
            pk=pk,
        )

        estado_actual = pedido.status

        if nuevo_estado == estado_actual:
            messages.info(request, "El pedido ya tiene ese estado.")
            return redirect("management:pedidos")

        lineas = list(
            pedido.lines.select_for_update()
        )

        if (
            estado_actual == "PENDIENTE"
            and nuevo_estado == "EN_PROCESO"
        ):
            pedido.status = "EN_PROCESO"

        elif (
            estado_actual == "PENDIENTE"
            and nuevo_estado == "CANCELADO"
        ):
            if any(
                linea.status != "PENDIENTE"
                for linea in lineas
            ):
                messages.error(
                    request,
                    "No puedes cancelar un pedido "
                    "con artículos en preparación o envío.",
                )
                return redirect("management:pedidos")

            for linea in lineas:
                Product.objects.filter(
                    pk=linea.product_id
                ).update(
                    stock=F("stock") + linea.quantity
                )

            pedido.status = "CANCELADO"

        elif (
            estado_actual == "EN_PROCESO"
            and nuevo_estado == "COMPLETADO"
        ):
            if not lineas or any(
                linea.status != "ENTREGADO"
                for linea in lineas
            ):
                messages.error(
                    request,
                    "Todos los artículos deben estar "
                    "entregados antes de completar el pedido.",
                )
                return redirect("management:pedidos")

            pedido.status = "COMPLETADO"

        else:
            messages.error(
                request,
                "La transición solicitada no está permitida.",
            )
            return redirect("management:pedidos")

        pedido.save(update_fields=["status", "updated_at"])

    messages.success(
        request,
        "Estado de la orden actualizado correctamente.",
    )
    return redirect("management:pedidos")
