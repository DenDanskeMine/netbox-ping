from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('netbox_ping', '0005_pinghistory_pluginsettings_ping_history_max_records'),
    ]

    operations = [
        migrations.AddField(
            model_name='pluginsettings',
            name='ping_concurrency',
            field=models.IntegerField(
                default=100,
                help_text='Number of simultaneous ping threads per scan job (increase if you raised LimitNOFILE for netbox-rq)',
                verbose_name='Concurrent Pings',
            ),
        ),
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
