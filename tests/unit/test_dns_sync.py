"""Unit tests for _compute_dns_sync() in netbox_ping/utils.py.

Pure logic tests — no database, no subprocess, no Django models.
"""

from types import SimpleNamespace

from netbox_ping.utils import _compute_dns_sync


def _settings(**kwargs):
    defaults = dict(
        dns_sync_to_netbox=True,
        dns_preserve_if_alive=True,
        dns_clear_on_missing=False,
    )
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def test_sync_updates_when_dns_found_and_alive():
    s = _settings()
    should_update, value = _compute_dns_sync(
        dns_name="host.example.com",
        is_reachable=True,
        dns_attempted=True,
        current_netbox_dns="",
        settings=s,
    )
    assert should_update is True
    assert value == "host.example.com"


def test_sync_skips_when_host_down():
    """When the host is down, dns_attempted=False — no change."""
    s = _settings()
    should_update, _ = _compute_dns_sync(
        dns_name="",
        is_reachable=False,
        dns_attempted=False,
        current_netbox_dns="old.host",
        settings=s,
    )
    assert should_update is False


def test_sync_preserves_existing_when_alive_but_no_dns():
    """Host alive + no DNS found + dns_preserve_if_alive=True → no change."""
    s = _settings(dns_preserve_if_alive=True, dns_clear_on_missing=False)
    should_update, _ = _compute_dns_sync(
        dns_name="",
        is_reachable=True,
        dns_attempted=True,
        current_netbox_dns="preserved.host",
        settings=s,
    )
    assert should_update is False


def test_sync_clears_when_clear_on_missing_enabled():
    """dns_clear_on_missing=True, no DNS, host down-ish → clear it."""
    s = _settings(dns_preserve_if_alive=False, dns_clear_on_missing=True)
    should_update, value = _compute_dns_sync(
        dns_name="",
        is_reachable=False,
        dns_attempted=True,
        current_netbox_dns="old.host",
        settings=s,
    )
    assert should_update is True
    assert value == ""


def test_sync_no_update_when_same_value():
    """DNS found but identical to current value → no write."""
    s = _settings()
    should_update, _ = _compute_dns_sync(
        dns_name="same.host",
        is_reachable=True,
        dns_attempted=True,
        current_netbox_dns="same.host",
        settings=s,
    )
    assert should_update is False


def test_sync_skips_when_dns_not_attempted():
    """dns_attempted=False always means no change, regardless of other flags."""
    s = _settings(dns_clear_on_missing=True)
    should_update, _ = _compute_dns_sync(
        dns_name="",
        is_reachable=True,
        dns_attempted=False,
        current_netbox_dns="old.host",
        settings=s,
    )
    assert should_update is False


def test_sync_disabled_when_sync_to_netbox_false():
    """dns_sync_to_netbox=False → never update."""
    s = _settings(dns_sync_to_netbox=False)
    should_update, _ = _compute_dns_sync(
        dns_name="new.host",
        is_reachable=True,
        dns_attempted=True,
        current_netbox_dns="old.host",
        settings=s,
    )
    assert should_update is False
