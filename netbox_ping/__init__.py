from netbox.plugins import PluginConfig


class NetBoxPingConfig(PluginConfig):
    name = 'netbox_ping'
    verbose_name = 'NetBox Ping'
    description = 'Ping and discover IP addresses in NetBox'
    version = '2.6.0'
    author = 'Christian Rose'
    base_url = 'netbox-ping'
    min_version = '4.5.0'
    default_settings = {}
    required_settings = []

    def ready(self):
        super().ready()
        from . import jobs    # noqa: F401
        from . import tables  # noqa: F401 — registers columns on core tables

        from django.db.models.signals import post_save, post_delete
        from .models import PluginSettings, PrefixSchedule
        from .signals import (
            on_plugin_settings_saved,
            on_prefix_schedule_saved,
            on_prefix_schedule_deleted,
        )
        post_save.connect(on_plugin_settings_saved, sender=PluginSettings)
        post_save.connect(on_prefix_schedule_saved, sender=PrefixSchedule)
        post_delete.connect(on_prefix_schedule_deleted, sender=PrefixSchedule)


config = NetBoxPingConfig
