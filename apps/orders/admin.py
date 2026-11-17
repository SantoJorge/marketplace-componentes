from django.contrib import admin

# Register your models here.

# CR-09: consultas administrativas de solo lectura.
from .models import StockReservation, StockMovement

@admin.register(StockReservation)
class StockReservationAdmin(admin.ModelAdmin):
    list_display = ("id", "line", "product", "quantity", "status", "expires_at")
    list_filter = ("status",)
    readonly_fields = ("line", "product", "quantity", "status", "expires_at", "created_at", "updated_at")
    def has_add_permission(self, request): return False
    def has_delete_permission(self, request, obj=None): return False

@admin.register(StockMovement)
class StockMovementAdmin(admin.ModelAdmin):
    list_display = ("id", "product", "order", "movement_type", "quantity_change", "created_at")
    list_filter = ("movement_type",)
    readonly_fields = ("product", "order", "reservation", "movement_type", "quantity_change", "reason", "created_at")
    def has_add_permission(self, request): return False
    def has_delete_permission(self, request, obj=None): return False
