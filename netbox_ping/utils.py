import logging
import re
import socket
import subprocess
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


def scan_prefix(prefix_obj, dns_servers=None, perform_dns=True, max_workers=20):
    """
    Ping all existing IPs in a prefix. Creates/updates PingResult and SubnetScanResult.

    Returns dict: {'total': int, 'up': int, 'down': int}
    """
    from .models import PingResult, PingHistory, SubnetScanResult

    ip_addresses = list(prefix_obj.get_child_ips().select_related())
    results = []

    def _process_ip(ip_obj):
        ip_str = str(ip_obj.address.ip)
        ping_data = ping_host(ip_str)
        dns_name = ''
        if perform_dns and ping_data['is_reachable']:
            dns_name = resolve_dns(ip_str, dns_servers)

        now = timezone.now()
        existing_last_seen = None
        try:
            existing = PingResult.objects.get(ip_address=ip_obj)
            existing_last_seen = existing.last_seen
        except PingResult.DoesNotExist:
            pass

        PingResult.objects.update_or_create(
            ip_address=ip_obj,
            defaults={
                'is_reachable': ping_data['is_reachable'],
                'response_time_ms': ping_data['response_time_ms'],
                'dns_name': dns_name if dns_name else (
                    PingResult.objects.filter(ip_address=ip_obj)
                    .values_list('dns_name', flat=True).first() or ''
                ),
                'last_checked': now,
                'last_seen': now if ping_data['is_reachable'] else existing_last_seen,
            },
        )
        PingHistory.objects.create(
            ip_address=ip_obj,
            is_reachable=ping_data['is_reachable'],
            response_time_ms=ping_data['response_time_ms'],
            dns_name=dns_name,
            checked_at=now,
        )
        return ping_data

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_ip = {executor.submit(_process_ip, ip_obj): ip_obj for ip_obj in ip_addresses}
        for future in concurrent.futures.as_completed(future_to_ip):
            try:
                results.append(future.result())
            except Exception as e:
                logger.error(f'Error processing IP: {e}')

    total = len(results)
    up = sum(1 for r in results if r['is_reachable'])
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


def discover_prefix(prefix_obj, dns_servers=None, perform_dns=True, max_workers=20):
    """
    Ping entire network range to discover new hosts not yet in NetBox.
    Creates new IPAddress + PingResult for any discovered hosts.

    Safety: refuses prefixes larger than /20 (4094 hosts).

    Returns dict: {'discovered': list[str], 'total_scanned': int, 'total_up': int}
    """
    from ipam.models import IPAddress
    from .models import PingResult, PingHistory, SubnetScanResult

    network = ip_network(prefix_obj.prefix)
    prefix_length = prefix_obj.prefix.prefixlen

    if prefix_length < 20:
        logger.warning(f'Refusing to discover {prefix_obj.prefix}: prefix too large (>{4094} hosts)')
        return {'discovered': [], 'total_scanned': 0, 'total_up': 0}

    hosts = list(network.hosts()) if network.prefixlen < 31 else list(network)

    existing_ips = set(
        str(ip.address.ip) for ip in prefix_obj.get_child_ips()
    )

    discovered = []
    total_up = 0

    def _check_host(host_ip):
        return str(host_ip), ping_host(str(host_ip))

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(_check_host, ip): ip for ip in hosts}
        for future in concurrent.futures.as_completed(futures):
            try:
                ip_str, ping_data = future.result()
            except Exception as e:
                logger.error(f'Error during discovery: {e}')
                continue

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
                        now = timezone.now()
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

    # Update SubnetScanResult summary
    total_existing = len(existing_ips) + len(discovered)
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
