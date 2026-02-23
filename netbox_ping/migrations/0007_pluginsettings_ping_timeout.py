from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('netbox_ping', '0006_pluginsettings_ping_concurrency'),
    ]

    operations = [
        migrations.AddField(
            model_name='pluginsettings',
            name='ping_timeout',
            field=models.FloatField(
                default=1.0,
                help_text='How long to wait for a ping response before marking as down (e.g. 0.5 for LAN, 1.0 for WAN)',
                verbose_name='Ping Timeout (seconds)',
            ),
        ),
    ]
