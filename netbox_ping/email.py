"""Email digest builder for NetBox Ping scan events."""

from collections import defaultdict
from datetime import timedelta
from html import escape

from django.utils import timezone


def _ip_display(event):
    """Format an IP address with optional DNS name for display."""
    ip_str = str(event.ip_address.address.ip) if event.ip_address else 'Unknown'
    dns = event.detail.get('dns_name', '')
    if dns:
        return f'{ip_str} ({dns})'
    return ip_str


def _group_events_by_prefix(events):
    """Group events by prefix display string, returns dict of prefix_str -> list of events."""
    groups = defaultdict(list)
    for event in events:
        prefix_str = str(event.prefix.prefix) if event.prefix else 'No Prefix'
        groups[prefix_str].append(event)
    return dict(sorted(groups.items()))


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

    total_events = len(events)
    period_fmt = f'{period_start:%Y-%m-%d %H:%M} — {period_end:%Y-%m-%d %H:%M} UTC'

    # Subject line
    parts = []
    if went_down:
        parts.append(f'{len(went_down)} down')
    if came_up:
        parts.append(f'{len(came_up)} up')
    if discovered:
        parts.append(f'{len(discovered)} discovered')
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
        high_util_prefixes, include_details, period_fmt,
        total_events, utilization_threshold,
    )

    # ── Build plaintext ──
    text = _build_text(
        went_down, came_up, discovered, dns_changed,
        high_util_prefixes, include_details, period_fmt,
        total_events, utilization_threshold,
    )

    return subject, html, text


def _build_html(went_down, came_up, discovered, dns_changed,
                high_util_prefixes, include_details, period_fmt,
                total_events, utilization_threshold):
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
        ('DNS Changes', len(dns_changed), '#6c757d'),
    ]
    for label, count, color in summary_rows:
        count_style = f'padding: 8px 12px; border: 1px solid #dee2e6; font-size: 13px; font-weight: bold; color: {color};' if count > 0 else td_style
        h.append(f'<tr><td style="{td_style}">{label}</td><td style="{count_style}">{count}</td></tr>')
    h.append('</table>')
    h.append('</div>')

    # Detail sections (if enabled)
    if include_details:
        if went_down:
            h.append(_html_event_section('IPs Went Down', went_down, '#dc3545', td_style, th_style, table_style, section_style))
        if came_up:
            h.append(_html_event_section('IPs Came Up', came_up, '#28a745', td_style, th_style, table_style, section_style))
        if discovered:
            h.append(_html_event_section('Newly Discovered IPs', discovered, '#007bff', td_style, th_style, table_style, section_style))
        if dns_changed:
            h.append(_html_dns_section(dns_changed, td_style, th_style, table_style, section_style))

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


def _html_event_section(title, events, color, td_style, th_style, table_style, section_style):
    """Build an HTML section for a group of IP events, grouped by prefix."""
    lines = []
    lines.append(f'<div style="{section_style}">')
    lines.append(f'<h3 style="margin-top: 0; color: {color};">{escape(title)}</h3>')

    grouped = _group_events_by_prefix(events)
    for prefix_str, prefix_events in grouped.items():
        lines.append(f'<h4 style="margin: 10px 0 5px 0; color: #555;">[{escape(prefix_str)}]</h4>')
        lines.append(f'<table style="{table_style}">')
        lines.append(f'<tr><th style="{th_style}">IP Address</th><th style="{th_style}">Details</th></tr>')
        for event in prefix_events:
            ip_str = _ip_display(event)
            detail_parts = []
            rtt = event.detail.get('response_time_ms')
            if rtt is not None:
                detail_parts.append(f'RTT: {rtt:.1f}ms')
            last_rtt = event.detail.get('last_response_ms')
            if last_rtt is not None:
                detail_parts.append(f'Last RTT: {last_rtt:.1f}ms')
            detail_str = ', '.join(detail_parts) if detail_parts else '—'
            lines.append(f'<tr><td style="{td_style}">{escape(ip_str)}</td><td style="{td_style}">{escape(detail_str)}</td></tr>')
        lines.append('</table>')

    lines.append('</div>')
    return '\n'.join(lines)


def _html_dns_section(events, td_style, th_style, table_style, section_style):
    """Build HTML section for DNS change events."""
    lines = []
    lines.append(f'<div style="{section_style}">')
    lines.append('<h3 style="margin-top: 0; color: #6c757d;">DNS Changes</h3>')
    lines.append(f'<table style="{table_style}">')
    lines.append(f'<tr><th style="{th_style}">IP Address</th><th style="{th_style}">Old DNS</th><th style="{th_style}">New DNS</th></tr>')
    for event in events:
        ip_str = str(event.ip_address.address.ip) if event.ip_address else 'Unknown'
        old_dns = event.detail.get('old_dns', '')
        new_dns = event.detail.get('new_dns', '')
        lines.append(f'<tr><td style="{td_style}">{escape(ip_str)}</td>'
                      f'<td style="{td_style}">{escape(old_dns) or "<em>empty</em>"}</td>'
                      f'<td style="{td_style}">{escape(new_dns) or "<em>empty</em>"}</td></tr>')
    lines.append('</table>')
    lines.append('</div>')
    return '\n'.join(lines)


def _build_text(went_down, came_up, discovered, dns_changed,
                high_util_prefixes, include_details, period_fmt,
                total_events, utilization_threshold):
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
    lines.append(f'  DNS Changes:        {len(dns_changed)}')
    lines.append('')

    if include_details:
        if went_down:
            lines.append('IPS WENT DOWN')
            lines.append('-' * 30)
            lines.extend(_text_event_lines(went_down))
            lines.append('')

        if came_up:
            lines.append('IPS CAME UP')
            lines.append('-' * 30)
            lines.extend(_text_event_lines(came_up))
            lines.append('')

        if discovered:
            lines.append('NEWLY DISCOVERED IPS')
            lines.append('-' * 30)
            lines.extend(_text_event_lines(discovered))
            lines.append('')

        if dns_changed:
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


def _text_event_lines(events):
    """Build plaintext lines for IP events grouped by prefix."""
    lines = []
    grouped = _group_events_by_prefix(events)
    for prefix_str, prefix_events in grouped.items():
        lines.append(f'  [{prefix_str}]')
        for event in prefix_events:
            lines.append(f'    {_ip_display(event)}')
    return lines


def build_test_email():
    """
    Build a test digest email with sample data to verify SMTP settings.

    Returns (subject, html_body, text_body).
    """
    now = timezone.now()

    # Create lightweight mock events (no DB access)
    class _MockIP:
        class address:
            ip = '10.0.1.5'

    class _MockPrefix:
        prefix = '10.0.1.0/24'

    class _MockEvent:
        def __init__(self, event_type, detail):
            self.event_type = event_type
            self.ip_address = _MockIP()
            self.prefix = _MockPrefix()
            self.detail = detail

        def get_event_type_display(self):
            return self.event_type

    sample_events = [
        _MockEvent('ip_went_down', {'dns_name': 'switch-core.example.com', 'last_response_ms': 1.2}),
        _MockEvent('ip_came_up', {'dns_name': 'server01.example.com', 'response_time_ms': 0.8}),
        _MockEvent('ip_discovered', {'dns_name': 'printer.example.com', 'response_time_ms': 3.1}),
        _MockEvent('dns_changed', {'old_dns': 'old-host.example.com', 'new_dns': 'new-host.example.com'}),
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
