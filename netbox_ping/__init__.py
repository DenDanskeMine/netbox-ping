from netbox.plugins import PluginConfig


class NetBoxPingConfig(PluginConfig):
    name = 'netbox_ping'
    verbose_name = 'NetBox Ping'
    description = 'Ping and discover IP addresses in NetBox'
    version = '2.1.0'
    author = 'Christian Rose'
    base_url = 'netbox-ping'
    min_version = '4.5.0'
    default_settings = {}
    required_settings = []

    def ready(self):
        super().ready()
        from . import jobs    # noqa: F401
        from . import tables  # noqa: F401 — registers columns on core tables


config = NetBoxPingConfig
