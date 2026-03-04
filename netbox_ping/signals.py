"""
Django signals to re-schedule jobs when PluginSettings or PrefixSchedule are saved.
Connected in NetBoxPingConfig.ready().
"""
import logging

logger = logging.getLogger('netbox.netbox_ping')


def on_plugin_settings_saved(sender, instance, **kwargs):
    """
    When PluginSettings are saved, re-schedule all prefixes according to
    the updated global settings. Also handles enabling/disabling email digest.
    """
    from django.db import transaction

    def _reschedule():
        try:
            from ipam.models import Prefix
            from .models import PrefixSchedule, SubnetScanResult
            from .jobs import _schedule_next_scan, _schedule_next_discover, _schedule_next_digest

            prefix_schedules = {
                ps.prefix_id: ps for ps in PrefixSchedule.objects.all()
            }

            prefixes = Prefix.objects.filter(
                prefix__net_mask_length__gte=instance.max_prefix_size
            )

            for prefix in prefixes:
                schedule = prefix_schedules.get(prefix.pk)
                # Only reschedule if this prefix follows global settings
                # (custom_on/custom_off prefixes manage their own schedule)
                if schedule and schedule.scan_mode != 'follow_global':
                    pass
                else:
                    _schedule_next_scan(prefix, instance)

                if schedule and schedule.discover_mode != 'follow_global':
                    pass
                else:
                    _schedule_next_discover(prefix, instance)

            _schedule_next_digest(instance)
            logger.info('Rescheduled all prefixes after PluginSettings change')

        except Exception as e:
            logger.error(f'Error rescheduling after settings save: {e}')

    # Run after the DB transaction commits so enqueue_once sees the new settings
    transaction.on_commit(_reschedule)


def on_prefix_schedule_saved(sender, instance, **kwargs):
    """
    When a PrefixSchedule is saved, re-schedule that specific prefix only.
    """
    from django.db import transaction

    def _reschedule():
        try:
            from .models import PluginSettings
            from .jobs import _schedule_next_scan, _schedule_next_discover

            settings = PluginSettings.load()
            prefix = instance.prefix
            _schedule_next_scan(prefix, settings)
            _schedule_next_discover(prefix, settings)
            logger.info(f'Rescheduled {prefix.prefix} after PrefixSchedule change')

        except Exception as e:
            logger.error(f'Error rescheduling prefix after schedule save: {e}')

    transaction.on_commit(_reschedule)


def on_prefix_schedule_deleted(sender, instance, **kwargs):
    """
    When a PrefixSchedule is deleted, fall back to global settings for that prefix.
    """
    from django.db import transaction

    def _reschedule():
        try:
            from .models import PluginSettings
            from .jobs import _schedule_next_scan, _schedule_next_discover

            settings = PluginSettings.load()
            prefix = instance.prefix
            _schedule_next_scan(prefix, settings)
            _schedule_next_discover(prefix, settings)
            logger.info(f'Rescheduled {prefix.prefix} after PrefixSchedule deletion (reverting to global)')

        except Exception as e:
            logger.error(f'Error rescheduling prefix after schedule delete: {e}')

    transaction.on_commit(_reschedule)
