"""Email digest builder for NetBox Ping scan events."""

from collections import defaultdict
from datetime import timedelta
from html import escape

from django.utils import timezone


# ── State transition mapping ─────────────────────────────────
# Each event type implies a "from" state and a "to" state.
EVENT_TRANSITIONS = {
    'ip_went_down': ('Up', 'Down'),
    'ip_came_up': ('Down', 'Up'),
    'ip_discovered': ('New', 'Up'),
    'ip_went_stale': ('Down', 'Stale'),
    'ip_removed_stale': ('Stale', 'Deleted'),
}

STATE_COLORS = {
    'Up': '#28a745',
    'Down': '#dc3545',
    'Stale': '#e67e22',
    'Deleted': '#6c757d',
    'New': '#007bff',
}


def _ip_display(event):
    """Format an IP address with optional DNS name for display."""
    ip_str = str(event.ip_address.address.ip) if event.ip_address else 'Unknown'
    dns = event.detail.get('dns_name', '')
    if dns:
        return f'{ip_str} ({dns})'
    return ip_str


def _ip_key(event):
    """Get a stable key for grouping events by IP."""
    return str(event.ip_address.address.ip) if event.ip_address else 'Unknown'


def _build_ip_transitions(events):
    """
    Build per-IP state transition chains from events.

    Returns dict of:
        {prefix_str: {ip_str: {'display': str, 'chain': [(state, timestamp|None), ...], 'current': str}}}

    The first entry in the chain is the "from" state (no timestamp).
    Each subsequent entry is the "to" state with the event's created_at timestamp.
    Events must be ordered by created_at.
    """
    # Group by prefix, then by IP
    prefix_ip_events = defaultdict(lambda: defaultdict(list))
    for event in events:
        if event.event_type == 'dns_changed':
            continue
        prefix_str = str(event.prefix.prefix) if event.prefix else 'No Prefix'
        ip = _ip_key(event)
        prefix_ip_events[prefix_str][ip].append(event)

    result = {}
    for prefix_str in sorted(prefix_ip_events):
        result[prefix_str] = {}
        for ip_str, ip_events in sorted(prefix_ip_events[prefix_str].items()):
            # Build chain: (state, timestamp) tuples
            chain = []
            display = _ip_display(ip_events[0])
            for event in ip_events:
                transition = EVENT_TRANSITIONS.get(event.event_type)
                if not transition:
                    continue
                from_state, to_state = transition
                ts = getattr(event, 'created_at', None)
                if not chain:
                    chain.append((from_state, None))
                chain.append((to_state, ts))

            if chain:
                result[prefix_str][ip_str] = {
                    'display': display,
                    'chain': chain,
                    'current': chain[-1][0],
                }

    return result


def _state_badge_html(state, ts=None):
    """Render an inline HTML badge for a state, with optional timestamp inside."""
    color = STATE_COLORS.get(state, '#6c757d')
    ts_html = ''
    if ts:
        ts_str = _fmt_ts(ts)
        ts_html = (
            f'<br><span style="font-size:9px;font-weight:normal;'
            f'opacity:0.85;">{escape(ts_str)}</span>'
        )
    return (
        f'<span style="display:inline-block;padding:3px 8px;border-radius:4px;'
        f'font-size:12px;font-weight:bold;color:white;background:{color};'
        f'text-align:center;vertical-align:top;">'
        f'{escape(state)}{ts_html}</span>'
    )


def _fmt_ts(ts):
    """Format a timestamp for display (short datetime), in the configured timezone."""
    if ts is None:
        return ''
    return timezone.localtime(ts).strftime('%b %d %H:%M')



def _chain_html(chain):
    """Render a state transition chain as HTML badges with arrows and timestamps."""
    arrow = ' <span style="color:#999;font-size:14px;vertical-align:top;">&rarr;</span> '
    parts = []
    for state, ts in chain:
        parts.append(_state_badge_html(state, ts))
    return arrow.join(parts)


def _chain_text(chain):
    """Render a state transition chain as plain text with timestamps."""
    parts = []
    for state, ts in chain:
        if ts:
            parts.append(f'{state} ({_fmt_ts(ts)})')
        else:
            parts.append(state)
    return ' -> '.join(parts)


def build_digest_email(events, high_util_prefixes, include_details, period_start, period_end, utilization_threshold):
    """
    Build HTML and plaintext digest email content.

    Args:
        events: QuerySet/list of ScanEvent objects (select_related ip_address, prefix)
        high_util_prefixes: QuerySet/list of SubnetScanResult objects above threshold
        include_details: bool — include per-IP change tables
        period_start: datetime — digest period start
        period_end: datetime — digest period end
        utilization_threshold: int — % threshold shown in header

    Returns:
        (subject, html_body, text_body) tuple
    """
    # Categorize events
    went_down = [e for e in events if e.event_type == 'ip_went_down']
    came_up = [e for e in events if e.event_type == 'ip_came_up']
    discovered = [e for e in events if e.event_type == 'ip_discovered']
    dns_changed = [e for e in events if e.event_type == 'dns_changed']
    went_stale = [e for e in events if e.event_type == 'ip_went_stale']
    removed_stale = [e for e in events if e.event_type == 'ip_removed_stale']

    tz_name = timezone.get_current_timezone_name()
    local_start = timezone.localtime(period_start)
    local_end = timezone.localtime(period_end)
    period_fmt = f'{local_start:%Y-%m-%d %H:%M} — {local_end:%Y-%m-%d %H:%M} ({tz_name})'

    # Build per-IP transition data (excluding dns_changed)
    transitions = _build_ip_transitions(events)

    # Subject line
    parts = []
    if went_down:
        parts.append(f'{len(went_down)} down')
    if came_up:
        parts.append(f'{len(came_up)} up')
    if discovered:
        parts.append(f'{len(discovered)} discovered')
    if went_stale:
        parts.append(f'{len(went_stale)} stale')
    if removed_stale:
        parts.append(f'{len(removed_stale)} removed')
    if dns_changed:
        parts.append(f'{len(dns_changed)} DNS changes')
    if high_util_prefixes:
        parts.append(f'{len(high_util_prefixes)} high-util')

    if parts:
        subject = f'NetBox Ping Digest: {", ".join(parts)}'
    else:
        subject = 'NetBox Ping Digest: No changes'

    # ── Build HTML ──
    html = _build_html(
        went_down, came_up, discovered, dns_changed,
        went_stale, removed_stale, transitions,
        high_util_prefixes, include_details, period_fmt,
        utilization_threshold,
    )

    # ── Build plaintext ──
    text = _build_text(
        went_down, came_up, discovered, dns_changed,
        went_stale, removed_stale, transitions,
        high_util_prefixes, include_details, period_fmt,
        utilization_threshold,
    )

    return subject, html, text


def _build_html(went_down, came_up, discovered, dns_changed,
                went_stale, removed_stale, transitions,
                high_util_prefixes, include_details, period_fmt,
                utilization_threshold):
    """Build HTML email body with inline styles."""

    # Styles
    body_style = 'font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; max-width: 700px; margin: 0 auto; color: #333;'
    header_style = 'background: #2c3e50; color: white; padding: 20px; border-radius: 8px 8px 0 0;'
    section_style = 'padding: 20px; border: 1px solid #dee2e6; border-top: none;'
    table_style = 'width: 100%; border-collapse: collapse; margin: 10px 0;'
    th_style = 'text-align: left; padding: 8px 12px; background: #f8f9fa; border: 1px solid #dee2e6; font-size: 13px;'
    td_style = 'padding: 8px 12px; border: 1px solid #dee2e6; font-size: 13px;'
    footer_style = 'padding: 15px 20px; background: #f8f9fa; border: 1px solid #dee2e6; border-top: none; border-radius: 0 0 8px 8px; text-align: center; color: #6c757d; font-size: 12px;'

    h = []
    h.append(f'<div style="{body_style}">')

    # Header
    h.append(f'<div style="{header_style}">')
    h.append('<h2 style="margin: 0 0 5px 0;">NetBox Ping Report</h2>')
    h.append(f'<div style="opacity: 0.8; font-size: 14px;">Period: {escape(period_fmt)}</div>')
    h.append('</div>')

    # Summary section
    h.append(f'<div style="{section_style}">')
    h.append('<h3 style="margin-top: 0; color: #2c3e50;">Summary</h3>')
    h.append(f'<table style="{table_style}">')
    summary_rows = [
        ('IPs Went Down', len(went_down), '#dc3545'),
        ('IPs Came Up', len(came_up), '#28a745'),
        ('New IPs Discovered', len(discovered), '#007bff'),
        ('IPs Went Stale', len(went_stale), '#e67e22'),
        ('Stale IPs Removed', len(removed_stale), '#e67e22'),
        ('DNS Changes', len(dns_changed), '#6c757d'),
    ]
    for label, count, color in summary_rows:
        count_style = f'padding: 8px 12px; border: 1px solid #dee2e6; font-size: 13px; font-weight: bold; color: {color};' if count > 0 else td_style
        h.append(f'<tr><td style="{td_style}">{label}</td><td style="{count_style}">{count}</td></tr>')
    h.append('</table>')
    h.append('</div>')

    # State transitions detail (if enabled)
    if include_details and transitions:
        h.append(f'<div style="{section_style}">')
        h.append('<h3 style="margin-top: 0; color: #2c3e50;">State Changes</h3>')

        for prefix_str, ips in transitions.items():
            h.append(f'<h4 style="margin: 10px 0 5px 0; color: #555;">[{escape(prefix_str)}]</h4>')
            h.append(f'<table style="{table_style}">')
            h.append(f'<tr><th style="{th_style}">IP Address</th><th style="{th_style}">Transition</th></tr>')
            for ip_str, data in ips.items():
                chain_badges = _chain_html(data['chain'])
                h.append(
                    f'<tr><td style="{td_style}">{escape(data["display"])}</td>'
                    f'<td style="{td_style}">{chain_badges}</td></tr>'
                )
            h.append('</table>')

        h.append('</div>')

    # DNS changes detail (if enabled)
    if include_details and dns_changed:
        h.append(f'<div style="{section_style}">')
        h.append('<h3 style="margin-top: 0; color: #6c757d;">DNS Changes</h3>')
        h.append(f'<table style="{table_style}">')
        h.append(f'<tr><th style="{th_style}">IP Address</th><th style="{th_style}">Old DNS</th><th style="{th_style}">New DNS</th></tr>')
        for event in dns_changed:
            ip_str = str(event.ip_address.address.ip) if event.ip_address else 'Unknown'
            old_dns = event.detail.get('old_dns', '')
            new_dns = event.detail.get('new_dns', '')
            h.append(f'<tr><td style="{td_style}">{escape(ip_str)}</td>'
                      f'<td style="{td_style}">{escape(old_dns) or "<em>empty</em>"}</td>'
                      f'<td style="{td_style}">{escape(new_dns) or "<em>empty</em>"}</td></tr>')
        h.append('</table>')
        h.append('</div>')

    # High utilization section
    if high_util_prefixes:
        h.append(f'<div style="{section_style}">')
        h.append(f'<h3 style="margin-top: 0; color: #e67e22;">Prefixes &ge; {utilization_threshold}% Utilization</h3>')
        h.append(f'<table style="{table_style}">')
        h.append(f'<tr><th style="{th_style}">Prefix</th><th style="{th_style}">Hosts Up</th><th style="{th_style}">Total</th><th style="{th_style}">Utilization</th></tr>')
        for ssr in high_util_prefixes:
            util_pct = ssr.utilization
            h.append(f'<tr><td style="{td_style}">{escape(str(ssr.prefix.prefix))}</td>'
                      f'<td style="{td_style}">{ssr.hosts_up}</td>'
                      f'<td style="{td_style}">{ssr.total_hosts}</td>'
                      f'<td style="{td_style}; font-weight: bold; color: #e67e22;">{util_pct}%</td></tr>')
        h.append('</table>')
        h.append('</div>')

    # Footer
    h.append(f'<div style="{footer_style}">Sent by NetBox Ping plugin</div>')
    h.append('</div>')

    return '\n'.join(h)


def _build_text(went_down, came_up, discovered, dns_changed,
                went_stale, removed_stale, transitions,
                high_util_prefixes, include_details, period_fmt,
                utilization_threshold):
    """Build plaintext email body."""
    lines = []
    lines.append('NetBox Ping Report')
    lines.append(f'Period: {period_fmt}')
    lines.append('=' * 50)
    lines.append('')

    # Summary
    lines.append('SUMMARY')
    lines.append('-' * 30)
    lines.append(f'  IPs Went Down:      {len(went_down)}')
    lines.append(f'  IPs Came Up:        {len(came_up)}')
    lines.append(f'  New IPs Discovered: {len(discovered)}')
    lines.append(f'  IPs Went Stale:     {len(went_stale)}')
    lines.append(f'  Stale IPs Removed:  {len(removed_stale)}')
    lines.append(f'  DNS Changes:        {len(dns_changed)}')
    lines.append('')

    # State transitions detail
    if include_details and transitions:
        lines.append('STATE CHANGES')
        lines.append('-' * 30)
        for prefix_str, ips in transitions.items():
            lines.append(f'  [{prefix_str}]')
            for ip_str, data in ips.items():
                chain_str = _chain_text(data['chain'])
                lines.append(f'    {data["display"]:40s}  {chain_str}')
        lines.append('')

    # DNS changes detail
    if include_details and dns_changed:
        lines.append('DNS CHANGES')
        lines.append('-' * 30)
        for event in dns_changed:
            ip_str = str(event.ip_address.address.ip) if event.ip_address else 'Unknown'
            old_dns = event.detail.get('old_dns', '') or '(empty)'
            new_dns = event.detail.get('new_dns', '') or '(empty)'
            lines.append(f'  {ip_str}: {old_dns} -> {new_dns}')
        lines.append('')

    if high_util_prefixes:
        lines.append(f'PREFIXES >= {utilization_threshold}% UTILIZATION')
        lines.append('-' * 30)
        for ssr in high_util_prefixes:
            lines.append(f'  {ssr.prefix.prefix}  {ssr.hosts_up}/{ssr.total_hosts}  ({ssr.utilization}%)')
        lines.append('')

    lines.append('--')
    lines.append('Sent by NetBox Ping plugin')
    return '\n'.join(lines)


def build_test_email():
    """
    Build a test digest email with sample data to verify SMTP settings.

    Returns (subject, html_body, text_body).
    """
    now = timezone.now()

    # Create lightweight mock events (no DB access)
    class _MockIP:
        def __init__(self, ip='10.0.1.5'):
            self.address = type('addr', (), {'ip': ip})()

    class _MockPrefix:
        prefix = '10.0.1.0/24'

    class _MockEvent:
        def __init__(self, event_type, detail, ip='10.0.1.5', minutes_ago=0):
            self.event_type = event_type
            self.ip_address = _MockIP(ip)
            self.prefix = _MockPrefix()
            self.detail = detail
            self.created_at = timezone.localtime(now - timedelta(minutes=minutes_ago))

    # Sample events showing various transitions — each IP has a unique address
    sample_events = [
        _MockEvent('ip_went_down', {'dns_name': 'switch-core.example.com', 'last_response_ms': 1.2}, ip='10.0.1.1', minutes_ago=45),
        _MockEvent('ip_came_up', {'dns_name': 'server01.example.com', 'response_time_ms': 0.8}, ip='10.0.1.2', minutes_ago=30),
        _MockEvent('ip_discovered', {'dns_name': 'printer.example.com', 'response_time_ms': 3.1}, ip='10.0.1.3', minutes_ago=50),
        _MockEvent('ip_went_stale', {'dns_name': 'old-server.example.com', 'consecutive_down_count': 10, 'last_seen': '2025-01-15 12:00:00'}, ip='10.0.1.4', minutes_ago=20),
        _MockEvent('ip_removed_stale', {'dns_name': 'decomm.example.com', 'ip_address': '10.0.1.99/24', 'last_seen': None}, ip='10.0.1.5', minutes_ago=15),
        # Multi-transition: went down then came back up (with timestamps)
        _MockEvent('ip_went_down', {'dns_name': 'flaky-host.example.com', 'last_response_ms': 2.5}, ip='10.0.1.6', minutes_ago=40),
        _MockEvent('ip_came_up', {'dns_name': 'flaky-host.example.com', 'response_time_ms': 1.1}, ip='10.0.1.6', minutes_ago=25),
        # Long flapping chain (tests collapse logic)
        _MockEvent('ip_went_down', {'dns_name': 'phone.example.com'}, ip='10.0.1.7', minutes_ago=55),
        _MockEvent('ip_came_up', {'dns_name': 'phone.example.com'}, ip='10.0.1.7', minutes_ago=50),
        _MockEvent('ip_went_down', {'dns_name': 'phone.example.com'}, ip='10.0.1.7', minutes_ago=45),
        _MockEvent('ip_came_up', {'dns_name': 'phone.example.com'}, ip='10.0.1.7', minutes_ago=40),
        _MockEvent('ip_went_down', {'dns_name': 'phone.example.com'}, ip='10.0.1.7', minutes_ago=35),
        _MockEvent('ip_came_up', {'dns_name': 'phone.example.com'}, ip='10.0.1.7', minutes_ago=30),
        _MockEvent('ip_went_down', {'dns_name': 'phone.example.com'}, ip='10.0.1.7', minutes_ago=25),
        _MockEvent('ip_came_up', {'dns_name': 'phone.example.com'}, ip='10.0.1.7', minutes_ago=20),
        _MockEvent('ip_went_down', {'dns_name': 'phone.example.com'}, ip='10.0.1.7', minutes_ago=15),
        _MockEvent('ip_went_stale', {'dns_name': 'phone.example.com'}, ip='10.0.1.7', minutes_ago=5),
        # DNS change (separate section)
        _MockEvent('dns_changed', {'old_dns': 'old-host.example.com', 'new_dns': 'new-host.example.com'}, ip='10.0.1.8', minutes_ago=10),
    ]

    class _MockSSR:
        class prefix:
            prefix = '10.0.2.0/24'
        hosts_up = 240
        total_hosts = 254
        utilization = 94.5

    subject, html, text = build_digest_email(
        events=sample_events,
        high_util_prefixes=[_MockSSR()],
        include_details=True,
        period_start=now - timedelta(hours=1),
        period_end=now,
        utilization_threshold=90,
    )

    return f'[TEST] {subject}', html, text
