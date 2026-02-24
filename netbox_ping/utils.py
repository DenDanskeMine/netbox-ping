import logging
import re
import socket
import subprocess
import time
import concurrent.futures
from ipaddress import ip_network

import dns.resolver
from django.utils import timezone

logger = logging.getLogger('netbox.netbox_ping')


def ping_host(ip, count=1, timeout=1):
    """
    Ping a single IP address.

    Returns dict with 'is_reachable' (bool) and 'response_time_ms' (float or None).
    """
    try:
        result = subprocess.run(
            ['ping', '-c', str(count), '-W', str(timeout), str(ip)],
            capture_output=True, text=True, timeout=timeout + 2,
        )
        is_reachable = result.returncode == 0
        rtt = None
        if is_reachable:
            match = re.search(r'rtt min/avg/max/mdev = [\d.]+/([\d.]+)/', result.stdout)
            if match:
                rtt = float(match.group(1))
        return {'is_reachable': is_reachable, 'response_time_ms': rtt}
    except (subprocess.TimeoutExpired, Exception) as e:
        logger.debug(f'Ping failed for {ip}: {e}')
        return {'is_reachable': False, 'response_time_ms': None}


def resolve_dns(ip, servers=None):
    """
    Reverse DNS lookup for an IP address.

    Returns the resolved hostname (str) or empty string.
    """
    try:
        resolver = dns.resolver.Resolver()
        if servers:
            resolver.nameservers = [s for s in servers if s]
        hostname = socket.gethostbyaddr(str(ip))[0]
        return hostname.lower()
    except (socket.herror, dns.resolver.NXDOMAIN, Exception) as e:
        logger.debug(f'DNS lookup failed for {ip}: {e}')
        return ''


def _compute_dns_sync(dns_name, is_reachable, dns_attempted, current_netbox_dns, settings):
    """
    Decide whether to update IPAddress.dns_name and what the new value should be.

    Returns (should_update, new_value).
    """
    if not settings or not settings.dns_sync_to_netbox:
        return False, ''

    if not dns_attempted:
        # DNS not attempted (e.g. host down and lookup skipped) → don't touch
        return False, ''

    if dns_name:
        # DNS found → write it
        if dns_name != current_netbox_dns:
            return True, dns_name
        return False, ''

    # DNS empty
    if is_reachable and settings.dns_preserve_if_alive:
        # Host alive + preserve enabled → don't touch
        return False, ''

    if settings.dns_clear_on_missing and current_netbox_dns:
        # Clear enabled and there's something to clear
        return True, ''

    return False, ''


def scan_prefix(prefix_obj, dns_servers=None, perform_dns=True, max_workers=100, ping_timeout=1, dns_settings=None, job_logger=None, skip_reserved=False):
    """
    Ping all existing IPs in a prefix. Creates/updates PingResult and SubnetScanResult.

    Pings run in a thread pool for speed; DB writes happen on the main thread
    to avoid exhausting PostgreSQL connections.

    Returns dict: {'total': int, 'up': int, 'down': int, 'skipped': int}
    """
    from .models import PingResult, PingHistory, SubnetScanResult, DnsHistory, ScanEvent

    log = job_logger or logger
    ip_addresses = list(prefix_obj.get_child_ips().select_related())

    # Partition: skip reserved IPs if setting is enabled
    if skip_reserved:
        pingable_ips = [ip for ip in ip_addresses if ip.status != 'reserved']
        skipped_ips = [ip for ip in ip_addresses if ip.status == 'reserved']
    else:
        pingable_ips = ip_addresses
        skipped_ips = []

    if skipped_ips:
        msg = f'Skipping {len(skipped_ips)} reserved IPs'
        log.info(msg)
        print(f'[Scan] {msg}', flush=True)

    # Phase 1: ping + DNS in parallel (no DB access)
    def _ping_ip(ip_obj):
        ip_str = str(ip_obj.address.ip)
        ping_data = ping_host(ip_str, timeout=ping_timeout)
        dns_name = ''
        dns_attempted = False
        if perform_dns and ping_data['is_reachable']:
            dns_attempted = True
            dns_name = resolve_dns(ip_str, dns_servers)
        return ip_obj, ping_data, dns_name, dns_attempted

    ping_results = []
    total_ips = len(pingable_ips)
    last_log_time = time.monotonic()
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(_ping_ip, ip_obj): ip_obj for ip_obj in pingable_ips}
        for future in concurrent.futures.as_completed(futures):
            try:
                ping_results.append(future.result())
            except Exception as e:
                log.error(f'Error pinging IP: {e}')
            now_mono = time.monotonic()
            if now_mono - last_log_time >= 60 or len(ping_results) == total_ips:
                up_so_far = sum(1 for _, r, _, _ in ping_results if r['is_reachable'])
                msg = f'Ping progress: {len(ping_results)}/{total_ips} ({up_so_far} up)'
                log.info(msg)
                print(f'[Scan] {msg}', flush=True)
                last_log_time = now_mono

    # Phase 2: bulk DB writes on the main thread
    now = timezone.now()

    # Pre-fetch all existing PingResults for all IPs (pingable + skipped)
    all_ip_ids = [ip_obj.pk for ip_obj in ip_addresses]
    existing_results = {}
    for i in range(0, len(all_ip_ids), 5000):
        batch = all_ip_ids[i:i + 5000]
        for pr in PingResult.objects.filter(ip_address_id__in=batch):
            existing_results[pr.ip_address_id] = pr

    to_update = []
    to_create = []
    history_records = []
    ips_to_dns_update = []
    dns_history_records = []
    scan_events = []

    for ip_obj, ping_data, dns_name, dns_attempted in ping_results:
        existing = existing_results.get(ip_obj.pk)

        if existing:
            # Capture state change before overwriting
            was_reachable = existing.is_reachable
            is_now_reachable = ping_data['is_reachable']
            if not existing.is_skipped:
                if was_reachable and not is_now_reachable:
                    scan_events.append(ScanEvent(
                        event_type='ip_went_down',
                        prefix=prefix_obj,
                        ip_address=ip_obj,
                        detail={
                            'dns_name': existing.dns_name or '',
                            'last_response_ms': existing.response_time_ms,
                        },
                    ))
                elif not was_reachable and is_now_reachable:
                    scan_events.append(ScanEvent(
                        event_type='ip_came_up',
                        prefix=prefix_obj,
                        ip_address=ip_obj,
                        detail={
                            'dns_name': dns_name or existing.dns_name or '',
                            'response_time_ms': ping_data['response_time_ms'],
                        },
                    ))

            existing.is_reachable = ping_data['is_reachable']
            existing.is_skipped = False
            existing.response_time_ms = ping_data['response_time_ms']
            existing.dns_name = dns_name if dns_name else (existing.dns_name or '')
            existing.last_checked = now
            if ping_data['is_reachable']:
                existing.last_seen = now
            to_update.append(existing)
        else:
            to_create.append(PingResult(
                ip_address=ip_obj,
                is_reachable=ping_data['is_reachable'],
                is_skipped=False,
                response_time_ms=ping_data['response_time_ms'],
                dns_name=dns_name,
                last_checked=now,
                last_seen=now if ping_data['is_reachable'] else None,
            ))

        history_records.append(PingHistory(
            ip_address=ip_obj,
            is_reachable=ping_data['is_reachable'],
            response_time_ms=ping_data['response_time_ms'],
            dns_name=dns_name,
            checked_at=now,
        ))

        # DNS sync logic
        if dns_settings and dns_settings.dns_sync_to_netbox:
            current_netbox_dns = ip_obj.dns_name or ''
            should_update, new_value = _compute_dns_sync(
                dns_name, ping_data['is_reachable'], dns_attempted,
                current_netbox_dns, dns_settings,
            )
            if should_update:
                ip_obj.dns_name = new_value
                ips_to_dns_update.append(ip_obj)
                dns_history_records.append(DnsHistory(
                    ip_address=ip_obj,
                    old_dns_name=current_netbox_dns,
                    new_dns_name=new_value,
                    changed_at=now,
                ))
                scan_events.append(ScanEvent(
                    event_type='dns_changed',
                    prefix=prefix_obj,
                    ip_address=ip_obj,
                    detail={
                        'old_dns': current_netbox_dns,
                        'new_dns': new_value,
                    },
                ))

    # Phase 2b: create/update PingResult for skipped IPs (no history)
    for ip_obj in skipped_ips:
        existing = existing_results.get(ip_obj.pk)
        if existing:
            existing.is_reachable = False
            existing.is_skipped = True
            existing.response_time_ms = None
            existing.last_checked = now
            to_update.append(existing)
        else:
            to_create.append(PingResult(
                ip_address=ip_obj,
                is_reachable=False,
                is_skipped=True,
                response_time_ms=None,
                dns_name='',
                last_checked=now,
                last_seen=None,
            ))

    BATCH = 1000
    if to_update:
        update_fields = ['is_reachable', 'is_skipped', 'response_time_ms', 'dns_name', 'last_checked', 'last_seen']
        for i in range(0, len(to_update), BATCH):
            PingResult.objects.bulk_update(to_update[i:i + BATCH], update_fields)
        msg = f'Bulk updated {len(to_update)} existing results'
        log.info(msg)
        print(f'[Scan] {msg}', flush=True)

    if to_create:
        for i in range(0, len(to_create), BATCH):
            PingResult.objects.bulk_create(to_create[i:i + BATCH])
        msg = f'Bulk created {len(to_create)} new results'
        log.info(msg)
        print(f'[Scan] {msg}', flush=True)

    for i in range(0, len(history_records), BATCH):
        PingHistory.objects.bulk_create(history_records[i:i + BATCH])
    msg = f'Bulk created {len(history_records)} history records'
    log.info(msg)
    print(f'[Scan] {msg}', flush=True)

    # DNS sync: bulk update IPAddress.dns_name and create DnsHistory
    if ips_to_dns_update:
        from ipam.models import IPAddress as IPAddressModel
        for i in range(0, len(ips_to_dns_update), BATCH):
            IPAddressModel.objects.bulk_update(ips_to_dns_update[i:i + BATCH], ['dns_name'])
        msg = f'DNS sync: updated {len(ips_to_dns_update)} IPAddress dns_name fields'
        log.info(msg)
        print(f'[Scan] {msg}', flush=True)

    if dns_history_records:
        for i in range(0, len(dns_history_records), BATCH):
            DnsHistory.objects.bulk_create(dns_history_records[i:i + BATCH])
        msg = f'DNS sync: created {len(dns_history_records)} DNS history records'
        log.info(msg)
        print(f'[Scan] {msg}', flush=True)

    # Phase 3: create ScanEvent records for digest notifications
    if scan_events:
        for i in range(0, len(scan_events), BATCH):
            ScanEvent.objects.bulk_create(scan_events[i:i + BATCH])
        msg = f'Created {len(scan_events)} scan event(s) for digest'
        log.info(msg)
        print(f'[Scan] {msg}', flush=True)

    total = len(ip_addresses)
    up = sum(1 for _, r, _, _ in ping_results if r['is_reachable'])
    skipped = len(skipped_ips)
    down = total - up - skipped

    SubnetScanResult.objects.update_or_create(
        prefix=prefix_obj,
        defaults={
            'total_hosts': total,
            'hosts_up': up,
            'hosts_down': down,
            'hosts_skipped': skipped,
            'last_scanned': timezone.now(),
        },
    )

    state_changes = {}
    for event in scan_events:
        state_changes[event.event_type] = state_changes.get(event.event_type, 0) + 1

    return {'total': total, 'up': up, 'down': down, 'skipped': skipped, 'state_changes': state_changes}


def discover_prefix(prefix_obj, dns_servers=None, perform_dns=True, max_workers=100, ping_timeout=1, dns_settings=None, job_logger=None):
    """
    Ping entire network range to discover new hosts not yet in NetBox.
    Creates new IPAddress + PingResult for any discovered hosts.

    Pings run in a thread pool for speed; DB writes happen on the main thread
    to avoid exhausting PostgreSQL connections.

    Safety: refuses prefixes larger than /20 (4094 hosts).

    Returns dict: {'discovered': list[str], 'total_scanned': int, 'total_up': int}
    """
    from ipam.models import IPAddress
    from .models import PingResult, PingHistory, SubnetScanResult, DnsHistory, ScanEvent

    log = job_logger or logger
    network = ip_network(prefix_obj.prefix)
    prefix_length = prefix_obj.prefix.prefixlen

    if prefix_length < 20:
        log.warning(f'Refusing to discover {prefix_obj.prefix}: prefix too large (>{4094} hosts)')
        return {'discovered': [], 'total_scanned': 0, 'total_up': 0}

    hosts = list(network.hosts()) if network.prefixlen < 31 else list(network)

    existing_ips = set(
        str(ip.address.ip) for ip in prefix_obj.get_child_ips()
    )

    # Phase 1: ping in parallel (no DB access)
    def _check_host(host_ip):
        return str(host_ip), ping_host(str(host_ip), timeout=ping_timeout)

    ping_results = []
    total_hosts = len(hosts)
    last_log_time = time.monotonic()
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(_check_host, ip): ip for ip in hosts}
        for future in concurrent.futures.as_completed(futures):
            try:
                ping_results.append(future.result())
            except Exception as e:
                log.error(f'Error during discovery: {e}')
            now_mono = time.monotonic()
            if now_mono - last_log_time >= 60 or len(ping_results) == total_hosts:
                up_so_far = sum(1 for _, r in ping_results if r['is_reachable'])
                msg = f'Discovery ping progress: {len(ping_results)}/{total_hosts} ({up_so_far} up)'
                log.info(msg)
                print(f'[Discover] {msg}', flush=True)
                last_log_time = now_mono

    # Phase 2: DB writes on the main thread
    discovered = []
    total_up = 0
    now = timezone.now()

    for ip_str, ping_data in ping_results:
        if ping_data['is_reachable']:
            total_up += 1
            if ip_str not in existing_ips:
                dns_name = ''
                if perform_dns:
                    dns_name = resolve_dns(ip_str, dns_servers)

                try:
                    ip_obj = IPAddress.objects.create(
                        address=f'{ip_str}/{prefix_length}',
                        status='active',
                        dns_name=dns_name,
                    )
                    PingResult.objects.create(
                        ip_address=ip_obj,
                        is_reachable=True,
                        response_time_ms=ping_data['response_time_ms'],
                        dns_name=dns_name,
                        last_checked=now,
                        last_seen=now,
                    )
                    PingHistory.objects.create(
                        ip_address=ip_obj,
                        is_reachable=True,
                        response_time_ms=ping_data['response_time_ms'],
                        dns_name=dns_name,
                        checked_at=now,
                    )
                    # Create DNS history if dns_name was set on a new IP
                    if dns_name and dns_settings and dns_settings.dns_sync_to_netbox:
                        DnsHistory.objects.create(
                            ip_address=ip_obj,
                            old_dns_name='',
                            new_dns_name=dns_name,
                            changed_at=now,
                        )
                    ScanEvent.objects.create(
                        event_type='ip_discovered',
                        prefix=prefix_obj,
                        ip_address=ip_obj,
                        detail={
                            'dns_name': dns_name,
                            'response_time_ms': ping_data['response_time_ms'],
                        },
                    )
                    discovered.append(ip_str)
                except Exception as e:
                    logger.error(f'Failed to create IP {ip_str}: {e}')

    SubnetScanResult.objects.update_or_create(
        prefix=prefix_obj,
        defaults={
            'total_hosts': len(hosts),
            'hosts_up': total_up,
            'hosts_down': len(hosts) - total_up,
            'last_discovered': timezone.now(),
        },
    )

    return {'discovered': discovered, 'total_scanned': len(hosts), 'total_up': total_up}
