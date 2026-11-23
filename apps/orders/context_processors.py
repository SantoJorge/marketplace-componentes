
# ============================================================
# CR-14 - CONTADOR GLOBAL DE NOTIFICACIONES
# FASE 10G - INTEGRACION CON BASE.HTML
# ============================================================

from .models import Notification


def navbar_notifications(request):
    """
    Devuelve el numero de notificaciones sin leer
    del usuario autenticado.
    """

    user = getattr(request, "user", None)

    if user is None or not user.is_authenticated:
        return {"navbar_unread_count": 0}

    pendientes = Notification.objects.filter(
        recipient=user,
        is_read=False,
    ).count()

    return {
        "navbar_unread_count": pendientes,
    }
