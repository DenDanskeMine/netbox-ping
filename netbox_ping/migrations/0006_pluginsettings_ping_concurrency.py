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
    ]
