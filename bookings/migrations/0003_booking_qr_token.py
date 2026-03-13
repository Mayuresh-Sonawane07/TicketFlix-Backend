import uuid
from django.db import migrations, models

def assign_qr_tokens(apps, schema_editor):
    Booking = apps.get_model('bookings', 'Booking')
    for booking in Booking.objects.all():
        booking.qr_token = uuid.uuid4()
        booking.save(update_fields=['qr_token'])

class Migration(migrations.Migration):
    dependencies = [
        ('bookings', '0002_alter_booking_status'),
    ]
    operations = [
        migrations.AddField(
            model_name='booking',
            name='qr_token',
            field=models.UUIDField(default=uuid.uuid4, editable=False, null=True),
        ),
        migrations.RunPython(assign_qr_tokens, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='booking',
            name='qr_token',
            field=models.UUIDField(default=uuid.uuid4, editable=False, unique=True),
        ),
    ]
