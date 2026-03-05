"""Unit tests for ping_host() in netbox_ping/utils.py.

subprocess.run is mocked — no real pings sent.
"""

import subprocess
from unittest.mock import MagicMock, patch

from netbox_ping.utils import ping_host


def _mock_run(returncode, stdout=""):
    result = MagicMock()
    result.returncode = returncode
    result.stdout = stdout
    return result


# ── Reachable host ────────────────────────────────────────────────────────

def test_ping_host_reachable():
    stdout = "rtt min/avg/max/mdev = 0.500/1.000/2.000/0.500 ms"
    with patch("subprocess.run", return_value=_mock_run(0, stdout)):
        result = ping_host("192.168.1.1")

    assert result["is_reachable"] is True
    assert result["response_time_ms"] == 1.0


def test_ping_host_reachable_no_rtt_in_output():
    """Reachable but stdout has no rtt line → response_time_ms is None."""
    with patch("subprocess.run", return_value=_mock_run(0, "")):
        result = ping_host("192.168.1.1")

    assert result["is_reachable"] is True
    assert result["response_time_ms"] is None


# ── Unreachable host ──────────────────────────────────────────────────────

def test_ping_host_unreachable():
    with patch("subprocess.run", return_value=_mock_run(1, "")):
        result = ping_host("192.168.1.1")

    assert result["is_reachable"] is False
    assert result["response_time_ms"] is None


# ── Timeout ───────────────────────────────────────────────────────────────

def test_ping_host_timeout():
    with patch("subprocess.run", side_effect=subprocess.TimeoutExpired(["ping"], 3)):
        result = ping_host("192.168.1.1")

    assert result["is_reachable"] is False
    assert result["response_time_ms"] is None


# ── Return shape ──────────────────────────────────────────────────────────

def test_ping_host_returns_dict_shape():
    """Result always contains both expected keys."""
    stdout = "rtt min/avg/max/mdev = 0.5/1.0/2.0/0.5 ms"
    with patch("subprocess.run", return_value=_mock_run(0, stdout)):
        result = ping_host("10.0.0.1")

    assert "is_reachable" in result
    assert "response_time_ms" in result
