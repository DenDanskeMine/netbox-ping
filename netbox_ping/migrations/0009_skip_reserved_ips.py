from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('netbox_ping', '0008_dns_sync_features'),
    ]

    operations = [
        migrations.AddField(
            model_name='pingresult',
            name='is_skipped',
            field=models.BooleanField(
                default=False,
                help_text='IP was skipped during scan (e.g. reserved status)',
                verbose_name='Skipped',
            ),
        ),
        migrations.AddField(
            model_name='subnetscanresult',
            name='hosts_skipped',
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name='pluginsettings',
            name='skip_reserved_ips',
            field=models.BooleanField(
                default=False,
                help_text='Skip pinging IPs with "reserved" status during scans (they will show as Skipped)',
                verbose_name='Skip Reserved IPs',
            ),
        ),
    ]
