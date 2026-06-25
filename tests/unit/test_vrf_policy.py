"""Unit tests for per-VRF auto-scan/discover policy and its precedence.

Following the convention in test_models.py, we mirror the decision logic as
standalone functions that match the implementations in models.py and jobs.py
exactly. This keeps the tests fast and free of the NetBox dependency chain.

Precedence, most specific first:
    per-prefix PrefixSchedule > per-VRF VrfPolicy > global PluginSettings
"""

from types import SimpleNamespace


# ── Mirror VrfPolicy (models.py) ───────────────────────────────────────

def vrf_scan_enabled(policy, g):
    if policy.scan_mode == "always":
        return True
    if policy.scan_mode == "never":
        return False
    return g.auto_scan_enabled


def vrf_discover_enabled(policy, g):
    if policy.discover_mode == "always":
        return True
    if policy.discover_mode == "never":
        return False
    return g.auto_discover_enabled


# ── Mirror PrefixSchedule with baseline (models.py) ─────────────────────────

def prefix_scan_enabled(s, g, base=None):
    if s.scan_mode == "custom_on":
        return True
    if s.scan_mode == "custom_off":
        return False
    return g.auto_scan_enabled if base is None else base


def prefix_discover_enabled(s, g, base=None):
    if s.discover_mode == "custom_on":
        return True
    if s.discover_mode == "custom_off":
        return False
    return g.auto_discover_enabled if base is None else base


# ── Mirror the scheduler resolution (jobs.py) ───────────────────────────────

def effective_scan_enabled(g, vrf_policy=None, schedule=None):
    base = vrf_scan_enabled(vrf_policy, g) if vrf_policy else g.auto_scan_enabled
    if schedule:
        return prefix_scan_enabled(schedule, g, base=base)
    return base


def effective_discover_enabled(g, vrf_policy=None, schedule=None):
    base = vrf_discover_enabled(vrf_policy, g) if vrf_policy else g.auto_discover_enabled
    if schedule:
        return prefix_discover_enabled(schedule, g, base=base)
    return base


# ── Helpers ─────────────────────────────────────────────────────────────────

def _policy(scan_mode="follow_global", discover_mode="follow_global"):
    return SimpleNamespace(scan_mode=scan_mode, discover_mode=discover_mode)


def _schedule(scan_mode="follow_global", discover_mode="follow_global"):
    return SimpleNamespace(scan_mode=scan_mode, discover_mode=discover_mode)


def _global(scan_enabled=True, discover_enabled=True):
    return SimpleNamespace(
        auto_scan_enabled=scan_enabled,
        auto_discover_enabled=discover_enabled,
    )


# ── VRF policy in isolation ─────────────────────────────────────────────────

def test_vrf_follow_global_inherits_on():
    assert vrf_scan_enabled(_policy(scan_mode="follow_global"), _global(scan_enabled=True)) is True


def test_vrf_follow_global_inherits_off():
    assert vrf_scan_enabled(_policy(scan_mode="follow_global"), _global(scan_enabled=False)) is False


def test_vrf_never_overrides_global_on():
    assert vrf_scan_enabled(_policy(scan_mode="never"), _global(scan_enabled=True)) is False


def test_vrf_always_overrides_global_off():
    assert vrf_scan_enabled(_policy(scan_mode="always"), _global(scan_enabled=False)) is True


def test_vrf_discover_never_overrides_global_on():
    assert vrf_discover_enabled(_policy(discover_mode="never"), _global(discover_enabled=True)) is False


# ── Default behaviour is unchanged (no policy, no schedule) ─────────────────

def test_no_policy_no_schedule_follows_global_on():
    assert effective_scan_enabled(_global(scan_enabled=True)) is True


def test_no_policy_no_schedule_follows_global_off():
    assert effective_scan_enabled(_global(scan_enabled=False)) is False


def test_global_table_prefix_ignores_vrf_policies():
    # Prefix with no VRF -> vrf_policy is None -> pure global baseline.
    assert effective_scan_enabled(_global(scan_enabled=True), vrf_policy=None) is True


# ── Real-world scenarios from the hstl NetBox ───────────────────────────────

def test_walnet_never_excludes_partner_vrf():
    """WALNET set to 'never' must not be scanned even with global auto-scan on."""
    g = _global(scan_enabled=True, discover_enabled=True)
    walnet = _policy(scan_mode="never", discover_mode="never")
    assert effective_scan_enabled(g, vrf_policy=walnet) is False
    assert effective_discover_enabled(g, vrf_policy=walnet) is False


def test_hostline_mgmt_follow_global_still_scanned():
    """HOSTLINE-MGMT left at follow_global keeps being scanned."""
    g = _global(scan_enabled=True)
    mgmt = _policy(scan_mode="follow_global")
    assert effective_scan_enabled(g, vrf_policy=mgmt) is True


# ── Precedence: per-prefix override beats VRF policy ────────────────────────

def test_prefix_custom_on_beats_vrf_never():
    """A single prefix can be force-included even if its VRF says never."""
    g = _global(scan_enabled=True)
    walnet = _policy(scan_mode="never")
    one_prefix = _schedule(scan_mode="custom_on")
    assert effective_scan_enabled(g, vrf_policy=walnet, schedule=one_prefix) is True


def test_prefix_custom_off_beats_vrf_always():
    """A single prefix can be force-excluded even if its VRF says always."""
    g = _global(scan_enabled=False)
    vrf = _policy(scan_mode="always")
    one_prefix = _schedule(scan_mode="custom_off")
    assert effective_scan_enabled(g, vrf_policy=vrf, schedule=one_prefix) is False


def test_prefix_follow_global_defers_to_vrf_policy():
    """A follow_global prefix inherits the VRF baseline, not raw global."""
    g = _global(scan_enabled=True)
    walnet = _policy(scan_mode="never")
    inherit = _schedule(scan_mode="follow_global")
    # VRF says never -> baseline False -> follow_global prefix is False
    assert effective_scan_enabled(g, vrf_policy=walnet, schedule=inherit) is False


def test_prefix_follow_global_defers_to_vrf_always_when_global_off():
    g = _global(scan_enabled=False)
    vrf = _policy(scan_mode="always")
    inherit = _schedule(scan_mode="follow_global")
    assert effective_scan_enabled(g, vrf_policy=vrf, schedule=inherit) is True


def test_discover_full_precedence_matrix():
    g = _global(discover_enabled=True)
    walnet = _policy(discover_mode="never")
    assert effective_discover_enabled(g, vrf_policy=walnet) is False
    assert effective_discover_enabled(g, vrf_policy=walnet,
                                      schedule=_schedule(discover_mode="custom_on")) is True


# ── Bulk/manual exclusion (mirrors jobs.is_scan_excluded / is_discover_excluded) ──
# "Excluded" means explicitly never-scan (per-prefix custom_off or per-VRF never),
# which bulk "Scan all" must honour. A follow_global prefix is NOT excluded even
# when global auto-scan is off (a manual bulk scan may still run it).

def scan_excluded(schedule=None, vrf_policy=None):
    if schedule and schedule.scan_mode == "custom_on":
        return False
    if schedule and schedule.scan_mode == "custom_off":
        return True
    if vrf_policy and vrf_policy.scan_mode == "never":
        return True
    return False


def test_never_vrf_is_excluded_from_bulk():
    assert scan_excluded(vrf_policy=_policy(scan_mode="never")) is True


def test_follow_global_not_excluded_even_if_global_off():
    # The whole point: bulk scan of a follow_global prefix is allowed; only
    # explicit 'never'/'custom_off' is excluded.
    assert scan_excluded(vrf_policy=_policy(scan_mode="follow_global")) is False
    assert scan_excluded() is False


def test_prefix_custom_off_excluded():
    assert scan_excluded(schedule=_schedule(scan_mode="custom_off")) is True


def test_prefix_custom_on_beats_vrf_never_for_bulk():
    assert scan_excluded(schedule=_schedule(scan_mode="custom_on"),
                         vrf_policy=_policy(scan_mode="never")) is False
