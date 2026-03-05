"""Shared fixtures and helpers for the netbox-ping test suite."""

import datetime
import sys
from types import ModuleType


# ── Stub unavailable NetBox/IPAM packages ─────────────────────────────────
# netbox_ping/__init__.py does `from netbox.plugins import PluginConfig`.
# We stub it with a plain Python class so the package can be imported without
# a full NetBox installation. Stubs are registered BEFORE any netbox_ping
# sub-module is imported (conftest.py is loaded first by pytest).


def _make_module(name):
    mod = ModuleType(name)
    sys.modules.setdefault(name, mod)
    return mod


class _FakePluginConfig:
    """Minimal stand-in for netbox.plugins.PluginConfig."""
    default_settings = {}
    required_settings = []

    def ready(self):
        pass


netbox_pkg = _make_module("netbox")
netbox_plugins = _make_module("netbox.plugins")
netbox_plugins.PluginConfig = _FakePluginConfig
netbox_pkg.plugins = netbox_plugins

netbox_models = _make_module("netbox.models")
netbox_models.NetBoxModel = object  # plain base, never subclassed in our tests

_make_module("ipam")
_make_module("ipam.models")
_make_module("dcim")
_make_module("dcim.models")
_make_module("netbox.jobs")


# ── Mock event builder ────────────────────────────────────────────────────

def make_event(event_type, ip="10.0.1.1", prefix="10.0.1.0/24", detail=None, minutes_ago=0):
    """Create a lightweight ScanEvent-like object (no DB)."""
    from django.utils import timezone

    class _MockAddress:
        def __init__(self, ip_str):
            self.ip = ip_str

    class _MockIPAddress:
        def __init__(self, ip_str):
            self.address = _MockAddress(ip_str)

    class _MockPrefix:
        def __init__(self, prefix_str):
            self.prefix = prefix_str

    class _MockEvent:
        pass

    evt = _MockEvent()
    evt.event_type = event_type
    evt.ip_address = _MockIPAddress(ip)
    evt.prefix = _MockPrefix(prefix)
    evt.detail = detail if detail is not None else {}
    evt.created_at = timezone.now() - datetime.timedelta(minutes=minutes_ago)
    return evt


# ── Mock SubnetScanResult builder ─────────────────────────────────────────

def make_mock_ssr(prefix_str="10.0.0.0/24", hosts_up=200, total_hosts=254, utilization=78.7):
    """Create a lightweight SubnetScanResult-like object (no DB)."""

    class _MockPrefix:
        def __init__(self, s):
            self.prefix = s

    class _MockSSR:
        pass

    ssr = _MockSSR()
    ssr.prefix = _MockPrefix(prefix_str)
    ssr.hosts_up = hosts_up
    ssr.total_hosts = total_hosts
    ssr.utilization = utilization
    return ssr


# ── Plugin settings helper ────────────────────────────────────────────────

def make_plugin_settings(**kwargs):
    """Create a SimpleNamespace mimicking PluginSettings (no DB)."""
    from types import SimpleNamespace

    defaults = dict(
        dns_sync_to_netbox=True,
        dns_clear_on_missing=False,
        dns_preserve_if_alive=True,
    )
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


# ── PrefixSchedule helper ─────────────────────────────────────────────────

def make_prefix_schedule(scan_mode="follow_global", scan_interval=60,
                         discover_mode="follow_global", discover_interval=1440):
    """Create a SimpleNamespace mimicking a PrefixSchedule instance (no DB)."""
    from types import SimpleNamespace

    return SimpleNamespace(
        scan_mode=scan_mode,
        scan_interval=scan_interval,
        discover_mode=discover_mode,
        discover_interval=discover_interval,
    )
