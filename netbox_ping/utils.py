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
        # Debug: log failures for known-good IPs
        if not is_reachable and '10.0.254.1' in ip:
            print(f'[DEBUG] {ip} returncode={result.returncode} stderr={result.stderr[:200]} stdout={result.stdout[:200]}', flush=True)
        return {'is_reachable': is_reachable, 'response_time_ms': rtt}
    except (subprocess.TimeoutExpired, Exception) as e:
        if '10.0.254.1' in ip:
            print(f'[DEBUG] {ip} exception: {type(e).__name__}: {e}', flush=True)
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


def scan_prefix(prefix_obj, dns_servers=None, perform_dns=True, max_workers=100, job_logger=None):
    """
    Ping all existing IPs in a prefix. Creates/updates PingResult and SubnetScanResult.

    Pings run in a thread pool for speed; DB writes happen on the main thread
    to avoid exhausting PostgreSQL connections.

    Returns dict: {'total': int, 'up': int, 'down': int}
    """
    from .models import PingResult, PingHistory, SubnetScanResult

    log = job_logger or logger
    ip_addresses = list(prefix_obj.get_child_ips().select_related())

    # Phase 1: ping + DNS in parallel (no DB access)
    def _ping_ip(ip_obj):
        ip_str = str(ip_obj.address.ip)
        ping_data = ping_host(ip_str)
        dns_name = ''
        if perform_dns and ping_data['is_reachable']:
            dns_name = resolve_dns(ip_str, dns_servers)
        return ip_obj, ping_data, dns_name

    ping_results = []
    total_ips = len(ip_addresses)
    last_log_time = time.monotonic()
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(_ping_ip, ip_obj): ip_obj for ip_obj in ip_addresses}
        for future in concurrent.futures.as_completed(futures):
            try:
                ping_results.append(future.result())
            except Exception as e:
                log.error(f'Error pinging IP: {e}')
            now_mono = time.monotonic()
            if now_mono - last_log_time >= 60 or len(ping_results) == total_ips:
                up_so_far = sum(1 for _, r, _ in ping_results if r['is_reachable'])
                msg = f'Ping progress: {len(ping_results)}/{total_ips} ({up_so_far} up)'
                log.info(msg)
                print(f'[Scan] {msg}', flush=True)
                last_log_time = now_mono

    # Phase 2: bulk DB writes on the main thread
    now = timezone.now()

    # Pre-fetch all existing PingResults for these IPs
    ip_ids = [ip_obj.pk for ip_obj, _, _ in ping_results]
    existing_results = {}
    for i in range(0, len(ip_ids), 5000):
        batch = ip_ids[i:i + 5000]
        for pr in PingResult.objects.filter(ip_address_id__in=batch):
            existing_results[pr.ip_address_id] = pr

    to_update = []
    to_create = []
    history_records = []

    for ip_obj, ping_data, dns_name in ping_results:
        existing = existing_results.get(ip_obj.pk)

        if existing:
            existing.is_reachable = ping_data['is_reachable']
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

    BATCH = 1000
    if to_update:
        update_fields = ['is_reachable', 'response_time_ms', 'dns_name', 'last_checked', 'last_seen']
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

    total = len(ping_results)
    up = sum(1 for _, r, _ in ping_results if r['is_reachable'])
    down = total - up

    SubnetScanResult.objects.update_or_create(
        prefix=prefix_obj,
        defaults={
            'total_hosts': total,
            'hosts_up': up,
            'hosts_down': down,
            'last_scanned': timezone.now(),
        },
    )

    return {'total': total, 'up': up, 'down': down}


def discover_prefix(prefix_obj, dns_servers=None, perform_dns=True, max_workers=100, job_logger=None):
    """
    Ping entire network range to discover new hosts not yet in NetBox.
    Creates new IPAddress + PingResult for any discovered hosts.

    Pings run in a thread pool for speed; DB writes happen on the main thread
    to avoid exhausting PostgreSQL connections.

    Safety: refuses prefixes larger than /20 (4094 hosts).

    Returns dict: {'discovered': list[str], 'total_scanned': int, 'total_up': int}
    """
    from ipam.models import IPAddress
    from .models import PingResult, PingHistory, SubnetScanResult

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
        return str(host_ip), ping_host(str(host_ip))

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
