from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("orders", "0006_paymentreceipt_stockreservation_stockmovement"),
    ]

    operations = [
        migrations.AddField(
            model_name="purchaseorder",
            name="checkout_token",
            field=models.UUIDField(null=True, blank=True, unique=True, editable=False),
        ),
    ]
