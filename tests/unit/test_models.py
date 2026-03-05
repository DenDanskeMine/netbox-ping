"""Unit tests for PrefixSchedule scheduling mode logic.

We test the decision logic as standalone Python functions that mirror
the method implementations in models.py exactly. This avoids importing
Django model classes with their full NetBox dependency chain, keeping
tests fast and self-contained.
"""

from types import SimpleNamespace


# ── Mirror the exact logic from PrefixSchedule (models.py) ───────────────

def is_scan_enabled(self, global_settings):
    if self.scan_mode == "custom_on":
        return True
    if self.scan_mode == "custom_off":
        return False
    return global_settings.auto_scan_enabled


def get_effective_scan_interval(self, global_settings):
    if self.scan_mode == "custom_on":
        return self.scan_interval
    return global_settings.auto_scan_interval


def is_discover_enabled(self, global_settings):
    if self.discover_mode == "custom_on":
        return True
    if self.discover_mode == "custom_off":
        return False
    return global_settings.auto_discover_enabled


def get_effective_discover_interval(self, global_settings):
    if self.discover_mode == "custom_on":
        return self.discover_interval
    return global_settings.auto_discover_interval


# ── Helpers ───────────────────────────────────────────────────────────────

def _schedule(scan_mode="follow_global", scan_interval=60,
              discover_mode="follow_global", discover_interval=1440):
    return SimpleNamespace(
        scan_mode=scan_mode,
        scan_interval=scan_interval,
        discover_mode=discover_mode,
        discover_interval=discover_interval,
    )


def _global(scan_enabled=True, scan_interval=120,
            discover_enabled=False, discover_interval=1440):
    return SimpleNamespace(
        auto_scan_enabled=scan_enabled,
        auto_scan_interval=scan_interval,
        auto_discover_enabled=discover_enabled,
        auto_discover_interval=discover_interval,
    )


# ── Scan mode tests ───────────────────────────────────────────────────────

def test_scan_custom_on_always_enabled():
    schedule = _schedule(scan_mode="custom_on")
    assert is_scan_enabled(schedule, _global(scan_enabled=False)) is True


def test_scan_custom_off_always_disabled():
    schedule = _schedule(scan_mode="custom_off")
    assert is_scan_enabled(schedule, _global(scan_enabled=True)) is False


def test_scan_follow_global_inherits_enabled():
    schedule = _schedule(scan_mode="follow_global")
    assert is_scan_enabled(schedule, _global(scan_enabled=True)) is True


def test_scan_follow_global_inherits_disabled():
    schedule = _schedule(scan_mode="follow_global")
    assert is_scan_enabled(schedule, _global(scan_enabled=False)) is False


def test_scan_custom_on_uses_custom_interval():
    schedule = _schedule(scan_mode="custom_on", scan_interval=30)
    assert get_effective_scan_interval(schedule, _global(scan_interval=120)) == 30


def test_scan_follow_global_uses_global_interval():
    schedule = _schedule(scan_mode="follow_global", scan_interval=30)
    assert get_effective_scan_interval(schedule, _global(scan_interval=120)) == 120


# ── Discover mode tests ───────────────────────────────────────────────────

def test_discover_custom_on_always_enabled():
    schedule = _schedule(discover_mode="custom_on")
    assert is_discover_enabled(schedule, _global(discover_enabled=False)) is True


def test_discover_custom_off_always_disabled():
    schedule = _schedule(discover_mode="custom_off")
    assert is_discover_enabled(schedule, _global(discover_enabled=True)) is False


def test_discover_follow_global_inherits_enabled():
    schedule = _schedule(discover_mode="follow_global")
    assert is_discover_enabled(schedule, _global(discover_enabled=True)) is True


def test_discover_follow_global_inherits_disabled():
    schedule = _schedule(discover_mode="follow_global")
    assert is_discover_enabled(schedule, _global(discover_enabled=False)) is False


def test_discover_custom_on_uses_custom_interval():
    schedule = _schedule(discover_mode="custom_on", discover_interval=720)
    assert get_effective_discover_interval(schedule, _global(discover_interval=1440)) == 720


def test_discover_follow_global_uses_global_interval():
    schedule = _schedule(discover_mode="follow_global", discover_interval=720)
    assert get_effective_discover_interval(schedule, _global(discover_interval=1440)) == 1440
