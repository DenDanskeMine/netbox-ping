from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('netbox_ping', '0016_sshjumphost'),
    ]

    operations = [
        migrations.AddField(
            model_name='pluginsettings',
            name='ping_count',
            field=models.PositiveSmallIntegerField(
                default=2,
                verbose_name='Ping Count',
                help_text='Number of ICMP packets per host. Higher values reduce false "down" results on busy networks (default: 2)',
            ),
        ),
    ]
