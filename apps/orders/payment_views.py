from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import HttpResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST
from apps.accounts.permissions import role
from .models import PaymentReceipt, PurchaseOrder
from .services import OrderStateError, transition_order

MAX_BYTES = 450 * 1024

@require_POST
@login_required
def subir_comprobante(request, pk):
    if role(request.user) not in ('COMPRADOR', 'ADMINISTRADOR'):
        return HttpResponseForbidden('Acceso denegado')
    try:
        with transaction.atomic():
            order = get_object_or_404(PurchaseOrder.objects.select_for_update(), pk=pk)
            if role(request.user) == 'COMPRADOR' and order.buyer_id != request.user.pk:
                return HttpResponseForbidden('Pedido ajeno')
            if order.status != 'PENDIENTE_PAGO':
                raise OrderStateError('El pedido no admite comprobantes ahora.')
            if order.receipts.filter(status__in=('PENDIENTE', 'APROBADO')).exists():
                raise OrderStateError('Ya existe un comprobante en revisión o aprobado.')
            f = request.FILES.get('comprobante')
            if f is None or f.size < 1 or f.size > MAX_BYTES:
                raise OrderStateError('Adjunta JPG, PNG o PDF de hasta 450 KB.')
            data = f.read(MAX_BYTES + 1)
            if len(data) != f.size or len(data) > MAX_BYTES:
                raise OrderStateError('El tamaño del archivo no es válido.')
            ext = f.name.rsplit('.', 1)[-1].lower() if '.' in f.name else ''
            mime = ('application/pdf' if ext == 'pdf' and data.startswith(b'%PDF-') else
                    'image/png' if ext == 'png' and data.startswith(b'\x89PNG\r\n\x1a\n') else
                    'image/jpeg' if ext in ('jpg', 'jpeg') and data.startswith(b'\xff\xd8\xff') else None)
            if mime is None:
                raise OrderStateError('Archivo inválido. Usa JPG, PNG o PDF auténtico.')
            name = f.name.replace('\\', '/').split('/')[-1][:255]
            PaymentReceipt.objects.create(order=order, uploaded_by=request.user,
                                          file_name=name, mime_type=mime,
                                          file_size=len(data), file_data=data)
            transition_order(pk, 'PAGO_EN_REVISION', request.user, 'Comprobante recibido')
    except OrderStateError as exc:
        messages.error(request, str(exc))
    else:
        messages.success(request, 'Comprobante enviado para revisión.')
    return redirect('orders:pedido_detalle', pk=pk)

@require_POST
@login_required
def revisar_comprobante(request, pk, receipt_id):
    if role(request.user) != 'ADMINISTRADOR':
        return HttpResponseForbidden('Solo administradores')
    try:
        with transaction.atomic():
            order = get_object_or_404(PurchaseOrder.objects.select_for_update(), pk=pk)
            rec = get_object_or_404(PaymentReceipt.objects.select_for_update(), pk=receipt_id, order=order)
            if order.status != 'PAGO_EN_REVISION' or rec.status != 'PENDIENTE':
                raise OrderStateError('Este comprobante no está pendiente de revisión.')
            decision = request.POST.get('decision', '')
            observation = request.POST.get('observation', '').strip()[:2000]
            if decision not in ('APROBADO', 'RECHAZADO'):
                raise OrderStateError('Decisión inválida.')
            if decision == 'RECHAZADO' and not observation:
                raise OrderStateError('Indica el motivo del rechazo.')
            rec.status = decision
            rec.observation = observation
            rec.reviewed_by = request.user
            rec.reviewed_at = timezone.now()
            rec.save(update_fields=['status', 'observation', 'reviewed_by', 'reviewed_at'])
            target = 'PAGADA' if decision == 'APROBADO' else 'PENDIENTE_PAGO'
            transition_order(pk, target, request.user, observation or 'Comprobante aprobado')
    except OrderStateError as exc:
        messages.error(request, str(exc))
    else:
        messages.success(request, 'Comprobante revisado correctamente.')
    return redirect('orders:pedido_detalle', pk=pk)

@require_GET
@login_required
def descargar_comprobante(request, pk, receipt_id):
    order = get_object_or_404(PurchaseOrder, pk=pk)
    if role(request.user) != 'ADMINISTRADOR' and order.buyer_id != request.user.pk:
        return HttpResponseForbidden('Acceso   denegado')
    rec = get_object_or_404(PaymentReceipt, pk=receipt_id, order=order)
    response = HttpResponse(bytes(rec.file_data), content_type=rec.mime_type)
    response['Content-Disposition'] = 'attachment; filename="comprobante-%s-%s"' % (pk, rec.pk)
    response['X-Content-Type-Options'] = 'nosniff'
    return response