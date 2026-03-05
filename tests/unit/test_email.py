"""Unit tests for netbox_ping/email.py.

All tests use mock objects — no database, no NetBox stack required.
"""

import datetime
import pytest

from tests.conftest import make_event, make_mock_ssr


# ── _fmt_ts ───────────────────────────────────────────────────────────────

@pytest.mark.django_db
def test_fmt_ts_uses_localtime(settings):
    """_fmt_ts should format in the configured timezone, not raw UTC."""
    settings.TIME_ZONE = "America/New_York"  # UTC-5 in January
    from netbox_ping.email import _fmt_ts

    # 2025-01-15 12:00 UTC  →  07:00 America/New_York (UTC-5, no DST in Jan)
    dt = datetime.datetime(2025, 1, 15, 12, 0, tzinfo=datetime.timezone.utc)
    result = _fmt_ts(dt)
    assert "07:00" in result
    assert "12:00" not in result


def test_fmt_ts_none_returns_empty():
    from netbox_ping.email import _fmt_ts

    assert _fmt_ts(None) == ""


# ── period_fmt timezone name ──────────────────────────────────────────────

def test_period_fmt_shows_timezone_name(settings):
    """The digest period header should include the configured timezone name."""
    settings.TIME_ZONE = "Europe/Copenhagen"
    from netbox_ping.email import build_digest_email

    now = datetime.datetime(2025, 3, 5, 12, 0, tzinfo=datetime.timezone.utc)
    _, html, text = build_digest_email(
        events=[],
        high_util_prefixes=[],
        include_details=False,
        period_start=now - datetime.timedelta(hours=1),
        period_end=now,
        utilization_threshold=90,
    )
    assert "Europe/Copenhagen" in html
    assert "Europe/Copenhagen" in text


# ── _build_ip_transitions ─────────────────────────────────────────────────

def test_build_ip_transitions_single_event():
    """One ip_went_down event produces a two-entry chain: Up → Down."""
    from netbox_ping.email import _build_ip_transitions

    evt = make_event("ip_went_down", ip="10.0.0.1", prefix="10.0.0.0/24")
    result = _build_ip_transitions([evt])

    assert "10.0.0.0/24" in result
    ip_data = result["10.0.0.0/24"]["10.0.0.1"]
    assert len(ip_data["chain"]) == 2
    assert ip_data["chain"][0] == ("Up", None)   # from-state, no timestamp
    assert ip_data["chain"][1][0] == "Down"       # to-state
    assert ip_data["current"] == "Down"


def test_build_ip_transitions_multi_hop():
    """IP went down then came back up → three-entry chain, current='Up'."""
    from netbox_ping.email import _build_ip_transitions

    evt_down = make_event("ip_went_down", ip="10.0.0.1", prefix="10.0.0.0/24", minutes_ago=30)
    evt_up = make_event("ip_came_up", ip="10.0.0.1", prefix="10.0.0.0/24", minutes_ago=15)
    result = _build_ip_transitions([evt_down, evt_up])

    ip_data = result["10.0.0.0/24"]["10.0.0.1"]
    assert len(ip_data["chain"]) == 3           # Up(init) → Down → Up
    assert ip_data["current"] == "Up"
    states = [s for s, _ in ip_data["chain"]]
    assert states == ["Up", "Down", "Up"]


def test_build_ip_transitions_skips_dns_changed():
    """dns_changed events must not appear in the state transition chain."""
    from netbox_ping.email import _build_ip_transitions

    evt_down = make_event("ip_went_down", ip="10.0.0.1", prefix="10.0.0.0/24", minutes_ago=20)
    evt_dns = make_event("dns_changed", ip="10.0.0.1", prefix="10.0.0.0/24", minutes_ago=10)
    result = _build_ip_transitions([evt_down, evt_dns])

    # dns_changed is filtered — only the ip_went_down contributes
    ip_data = result["10.0.0.0/24"]["10.0.0.1"]
    assert len(ip_data["chain"]) == 2
    states = [s for s, _ in ip_data["chain"]]
    assert "dns_changed" not in states


def test_build_ip_transitions_all_dns_no_entries():
    """If all events are dns_changed, the result should be empty."""
    from netbox_ping.email import _build_ip_transitions

    evt_dns = make_event("dns_changed", ip="10.0.0.1", prefix="10.0.0.0/24")
    result = _build_ip_transitions([evt_dns])
    assert result == {}


# ── build_digest_email ────────────────────────────────────────────────────

def test_build_digest_email_returns_tuple():
    """build_digest_email must return a non-empty (subject, html, text) tuple."""
    from netbox_ping.email import build_digest_email

    now = datetime.datetime(2025, 3, 5, 12, 0, tzinfo=datetime.timezone.utc)
    result = build_digest_email(
        events=[],
        high_util_prefixes=[],
        include_details=True,
        period_start=now - datetime.timedelta(hours=1),
        period_end=now,
        utilization_threshold=90,
    )
    assert len(result) == 3
    subject, html, text = result
    assert subject
    assert html
    assert text


def test_subject_reflects_events():
    """Subject should summarise counts: '2 down, 1 up'."""
    from netbox_ping.email import build_digest_email

    now = datetime.datetime.now(tz=datetime.timezone.utc)
    events = [
        make_event("ip_went_down", ip="10.0.0.1", prefix="10.0.0.0/24"),
        make_event("ip_went_down", ip="10.0.0.2", prefix="10.0.0.0/24"),
        make_event("ip_came_up", ip="10.0.0.3", prefix="10.0.0.0/24"),
    ]
    subject, _, _ = build_digest_email(
        events=events,
        high_util_prefixes=[],
        include_details=False,
        period_start=now - datetime.timedelta(hours=1),
        period_end=now,
        utilization_threshold=90,
    )
    assert "2 down" in subject
    assert "1 up" in subject


def test_subject_no_changes():
    """Empty events → subject says 'No changes'."""
    from netbox_ping.email import build_digest_email

    now = datetime.datetime.now(tz=datetime.timezone.utc)
    subject, _, _ = build_digest_email(
        events=[],
        high_util_prefixes=[],
        include_details=False,
        period_start=now - datetime.timedelta(hours=1),
        period_end=now,
        utilization_threshold=90,
    )
    assert "No changes" in subject


def test_html_contains_period():
    """HTML body should include the formatted period string."""
    from netbox_ping.email import build_digest_email

    now = datetime.datetime.now(tz=datetime.timezone.utc)
    _, html, _ = build_digest_email(
        events=[],
        high_util_prefixes=[],
        include_details=False,
        period_start=now - datetime.timedelta(hours=1),
        period_end=now,
        utilization_threshold=90,
    )
    assert "Period:" in html


def test_text_contains_summary():
    """Plaintext body should include the SUMMARY section."""
    from netbox_ping.email import build_digest_email

    now = datetime.datetime.now(tz=datetime.timezone.utc)
    _, _, text = build_digest_email(
        events=[],
        high_util_prefixes=[],
        include_details=False,
        period_start=now - datetime.timedelta(hours=1),
        period_end=now,
        utilization_threshold=90,
    )
    assert "SUMMARY" in text


# ── build_test_email smoke test ───────────────────────────────────────────

def test_build_test_email_runs_without_error():
    """build_test_email should return a valid (subject, html, text) without raising."""
    from netbox_ping.email import build_test_email

    subject, html, text = build_test_email()
    assert "[TEST]" in subject
    assert html
    assert text
    # Smoke-check that state transition content is present
    assert "10.0.1." in html
