from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('netbox_ping', '0012_stale_ip_detection'),
    ]

    operations = [
        migrations.AddField(
            model_name='pingresult',
            name='is_new',
            field=models.BooleanField(default=False, help_text='IP was recently auto-discovered', verbose_name='New'),
        ),
        migrations.AddField(
            model_name='pingresult',
            name='discovered_at',
            field=models.DateTimeField(blank=True, help_text='When this IP was first auto-discovered', null=True, verbose_name='Discovered At'),
        ),
        migrations.AddField(
            model_name='pluginsettings',
            name='new_ip_days_threshold',
            field=models.PositiveIntegerField(default=7, help_text='Show "New" badge on auto-discovered IPs for this many days (0 = disabled)', verbose_name='New IP Badge Duration (days)'),
        ),
        migrations.AddField(
            model_name='subnetscanresult',
            name='hosts_new',
            field=models.IntegerField(default=0),
        ),
    ]
