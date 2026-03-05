from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('netbox_ping', '0014_scheduled_jobs'),
    ]

    operations = [
        migrations.AddField(
            model_name='subnetscanresult',
            name='scan_job_id',
            field=models.IntegerField(
                blank=True,
                null=True,
                verbose_name='Scan Job ID',
                help_text='PK of the currently scheduled PrefixScanJob (used for deduplication)',
            ),
        ),
        migrations.AddField(
            model_name='subnetscanresult',
            name='discover_job_id',
            field=models.IntegerField(
                blank=True,
                null=True,
                verbose_name='Discover Job ID',
                help_text='PK of the currently scheduled PrefixDiscoverJob (used for deduplication)',
            ),
        ),
    ]
