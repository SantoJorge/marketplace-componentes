"""Migra pedidos y líneas legados sin tocar su respaldo físico."""
from django.db import migrations


def importar(apps, schema_editor):
    connection = schema_editor.connection
    existing = set(connection.introspection.table_names())
    if not {"marketplace_ext_purchaseorder", "marketplace_ext_purchaseline"}.issubset(existing):
        return
    Order = apps.get_model("orders", "PurchaseOrder")
    Line = apps.get_model("orders", "PurchaseLine")
    q = connection.ops.quote_name
    db = connection.alias
    def fetch(table, fields):
        with connection.cursor() as cursor:
            cursor.execute("SELECT " + ", ".join(map(q, fields)) + " FROM " + q(table))
            return [dict(zip(fields, row)) for row in cursor.fetchall()]
    order_fields = ("id", "buyer_id", "status", "contact_name", "contact_phone",
                    "province", "address", "comments", "total", "created_at", "updated_at")
    for data in fetch("marketplace_ext_purchaseorder", order_fields):
        pk = data.pop("id"); created = data.pop("created_at"); updated = data.pop("updated_at")
        if not Order.objects.using(db).filter(pk=pk).exists():
            Order.objects.using(db).create(pk=pk, **data)
            Order.objects.using(db).filter(pk=pk).update(created_at=created, updated_at=updated)
    line_fields = ("id", "order_id", "product_id", "seller_id", "product_name", "unit_price", "quantity", "status")
    for data in fetch("marketplace_ext_purchaseline", line_fields):
        pk = data.pop("id")
        if not Line.objects.using(db).filter(pk=pk).exists():
            Line.objects.using(db).create(pk=pk, **data)


class Migration(migrations.Migration):
    dependencies = [("orders", "0002_purchaseorder_purchaseline"), ("accounts", "0004_importar_solicitudes_antiguas")]
    operations = [migrations.RunPython(importar, migrations.RunPython.noop)]
