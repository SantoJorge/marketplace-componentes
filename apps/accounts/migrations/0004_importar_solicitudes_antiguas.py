"""Copia solicitudes del módulo anterior sin destruir sus tablas antiguas."""
from django.db import migrations


def importar(apps, schema_editor):
    connection = schema_editor.connection
    if "marketplace_ext_sellerrequest" not in connection.introspection.table_names():
        return
    SellerRequest = apps.get_model("accounts", "SellerRequest")
    columns = ("id", "user_id", "business_name", "business_description", "business_phone",
               "location", "status", "review_note", "created_at", "reviewed_at")
    quote = connection.ops.quote_name
    with connection.cursor() as cursor:
        cursor.execute("SELECT " + ", ".join(map(quote, columns)) + " FROM " + quote("marketplace_ext_sellerrequest"))
        rows = cursor.fetchall()
    db = connection.alias
    for values in rows:
        data = dict(zip(columns, values))
        pk = data.pop("id")
        date = data.pop("created_at")
        if not SellerRequest.objects.using(db).filter(pk=pk).exists():
            SellerRequest.objects.using(db).create(pk=pk, **data)
            SellerRequest.objects.using(db).filter(pk=pk).update(created_at=date)


class Migration(migrations.Migration):
    dependencies = [("accounts", "0003_sellerrequest")]
    operations = [migrations.RunPython(importar, migrations.RunPython.noop)]
