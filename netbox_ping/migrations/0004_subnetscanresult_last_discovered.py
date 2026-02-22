from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('netbox_ping', '0003_remove_prefixschedule_auto_discover_enabled_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='subnetscanresult',
            name='last_discovered',
            field=models.DateTimeField(blank=True, null=True, verbose_name='Last Discovered'),
        ),
    ]
