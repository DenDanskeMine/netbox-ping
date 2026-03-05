from datetime import timedelta

from django.db import migrations, models
from django.utils import timezone


def populate_next_scan_times(apps, schema_editor):
    """
    Populate next_scan_at / next_discover_at for existing prefixes that have
    auto-scan/discover enabled, based on last_scanned + interval.
    Also sets next_digest_at if email notifications are enabled.
    """
    PluginSettings = apps.get_model('netbox_ping', 'PluginSettings')
    SubnetScanResult = apps.get_model('netbox_ping', 'SubnetScanResult')
    PrefixSchedule = apps.get_model('netbox_ping', 'PrefixSchedule')

    try:
        settings = PluginSettings.objects.get(pk=1)
    except PluginSettings.DoesNotExist:
        return

    now = timezone.now()
    prefix_schedules = {ps.prefix_id: ps for ps in PrefixSchedule.objects.all()}

    for ssr in SubnetScanResult.objects.all():
        schedule = prefix_schedules.get(ssr.prefix_id)

        # Determine effective scan settings
        if schedule and schedule.scan_mode == 'custom_on':
            scan_enabled = True
            scan_interval = schedule.scan_interval
        elif schedule and schedule.scan_mode == 'custom_off':
            scan_enabled = False
            scan_interval = 0
        else:
            scan_enabled = settings.auto_scan_enabled
            scan_interval = settings.auto_scan_interval

        # Determine effective discover settings
        if schedule and schedule.discover_mode == 'custom_on':
            discover_enabled = True
            discover_interval = schedule.discover_interval
        elif schedule and schedule.discover_mode == 'custom_off':
            discover_enabled = False
            discover_interval = 0
        else:
            discover_enabled = settings.auto_discover_enabled
            discover_interval = settings.auto_discover_interval

        changed = False

        if scan_enabled and scan_interval > 0:
            if ssr.last_scanned:
                next_at = ssr.last_scanned + timedelta(minutes=scan_interval)
                # If already past due, schedule from now
                if next_at < now:
                    next_at = now + timedelta(minutes=1)
            else:
                next_at = now + timedelta(minutes=scan_interval)
            ssr.next_scan_at = next_at
            changed = True

        if discover_enabled and discover_interval > 0:
            if ssr.last_discovered:
                next_at = ssr.last_discovered + timedelta(minutes=discover_interval)
                if next_at < now:
                    next_at = now + timedelta(minutes=1)
            else:
                next_at = now + timedelta(minutes=discover_interval)
            ssr.next_discover_at = next_at
            changed = True

        if changed:
            ssr.save()

    # Populate next_digest_at for email if enabled
    if settings.email_notifications_enabled and settings.email_digest_interval > 0:
        if settings.email_last_digest_sent:
            next_at = settings.email_last_digest_sent + timedelta(minutes=settings.email_digest_interval)
            if next_at < now:
                next_at = now + timedelta(minutes=settings.email_digest_interval)
        else:
            next_at = now + timedelta(minutes=settings.email_digest_interval)
        settings.next_digest_at = next_at
        settings.save()


class Migration(migrations.Migration):

    dependencies = [
        ('netbox_ping', '0013_new_ip_badge'),
    ]

    operations = [
        migrations.AddField(
            model_name='subnetscanresult',
            name='next_scan_at',
            field=models.DateTimeField(
                blank=True,
                null=True,
                verbose_name='Next Scan At',
                help_text='When this prefix is next scheduled to be auto-scanned',
            ),
        ),
        migrations.AddField(
            model_name='subnetscanresult',
            name='next_discover_at',
            field=models.DateTimeField(
                blank=True,
                null=True,
                verbose_name='Next Discover At',
                help_text='When this prefix is next scheduled to be auto-discovered',
            ),
        ),
        migrations.AddField(
            model_name='pluginsettings',
            name='next_digest_at',
            field=models.DateTimeField(
                blank=True,
                null=True,
                verbose_name='Next Digest At',
                help_text='When the next email digest is scheduled to be sent',
            ),
        ),
        migrations.RunPython(populate_next_scan_times, migrations.RunPython.noop),
    ]
