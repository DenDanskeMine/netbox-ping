from datetime import timedelta

from django.db import models
from django.urls import reverse
from django.utils import timezone
from netbox.models import NetBoxModel


INTERVAL_CHOICES = [
    (0, 'Disabled'),
    (5, 'Every 5 minutes'),
    (15, 'Every 15 minutes'),
    (30, 'Every 30 minutes'),
    (60, 'Hourly'),
    (360, 'Every 6 hours'),
    (720, 'Every 12 hours'),
    (1440, 'Daily'),
    (10080, 'Weekly'),
]


class PingResult(NetBoxModel):
    """Stores per-IP ping result. One record per IPAddress."""

    ip_address = models.OneToOneField(
        to='ipam.IPAddress',
        on_delete=models.CASCADE,
        related_name='ping_result',
    )
    is_reachable = models.BooleanField(
        default=False,
        verbose_name='Reachable',
    )
    is_skipped = models.BooleanField(
        default=False,
        verbose_name='Skipped',
        help_text='IP was skipped during scan (e.g. reserved status)',
    )
    last_seen = models.DateTimeField(
        blank=True,
        null=True,
        verbose_name='Last Seen',
        help_text='Last time this IP responded to ping',
    )
    response_time_ms = models.FloatField(
        blank=True,
        null=True,
        verbose_name='RTT (ms)',
    )
    dns_name = models.CharField(
        max_length=255,
        blank=True,
        default='',
        verbose_name='DNS Name',
    )
    last_checked = models.DateTimeField(
        blank=True,
        null=True,
        verbose_name='Last Checked',
    )

    class Meta:
        ordering = ['-last_checked']
        verbose_name = 'Ping Result'
        verbose_name_plural = 'Ping Results'

    def __str__(self):
        if self.is_skipped:
            status = 'Skipped'
        elif self.is_reachable:
            status = 'Up'
        else:
            status = 'Down'
        return f'{self.ip_address} — {status}'

    def get_absolute_url(self):
        return reverse('plugins:netbox_ping:pingresult', args=[self.pk])

    def get_status_color(self):
        if self.is_skipped:
            return 'warning'
        return 'success' if self.is_reachable else 'danger'


class SubnetScanResult(NetBoxModel):
    """Stores per-prefix scan summary."""

    prefix = models.OneToOneField(
        to='ipam.Prefix',
        on_delete=models.CASCADE,
        related_name='scan_result',
    )
    total_hosts = models.IntegerField(default=0)
    hosts_up = models.IntegerField(default=0)
    hosts_down = models.IntegerField(default=0)
    hosts_skipped = models.IntegerField(default=0)
    last_scanned = models.DateTimeField(
        blank=True,
        null=True,
        verbose_name='Last Scanned',
    )
    last_discovered = models.DateTimeField(
        blank=True,
        null=True,
        verbose_name='Last Discovered',
    )

    class Meta:
        ordering = ['-last_scanned']
        verbose_name = 'Subnet Scan Result'
        verbose_name_plural = 'Subnet Scan Results'

    def __str__(self):
        return f'{self.prefix} — {self.hosts_up}/{self.total_hosts} up'

    def get_absolute_url(self):
        return reverse('plugins:netbox_ping:subnetscanresult', args=[self.pk])

    @property
    def utilization(self):
        if self.total_hosts == 0:
            return 0
        return round(self.hosts_up / self.total_hosts * 100, 1)


class PingHistory(NetBoxModel):
    """Stores historical ping records for each IP address."""

    ip_address = models.ForeignKey(
        to='ipam.IPAddress',
        on_delete=models.CASCADE,
        related_name='ping_history',
    )
    is_reachable = models.BooleanField()
    response_time_ms = models.FloatField(blank=True, null=True)
    dns_name = models.CharField(max_length=255, blank=True, default='')
    checked_at = models.DateTimeField()

    class Meta:
        ordering = ['-checked_at']
        verbose_name = 'Ping History'
        verbose_name_plural = 'Ping History'
        indexes = [
            models.Index(fields=['ip_address', '-checked_at']),
        ]

    def __str__(self):
        status = 'Up' if self.is_reachable else 'Down'
        return f'{self.ip_address} — {status} @ {self.checked_at}'

    def get_absolute_url(self):
        return reverse('plugins:netbox_ping:pinghistory', args=[self.pk])

    def get_status_color(self):
        return 'success' if self.is_reachable else 'danger'


class DnsHistory(models.Model):
    """Audit log for DNS name changes synced to IPAddress."""

    ip_address = models.ForeignKey(
        to='ipam.IPAddress',
        on_delete=models.CASCADE,
        related_name='dns_history',
    )
    old_dns_name = models.CharField(max_length=255, blank=True, default='')
    new_dns_name = models.CharField(max_length=255, blank=True, default='')
    changed_at = models.DateTimeField()

    class Meta:
        ordering = ['-changed_at']
        verbose_name = 'DNS History'
        verbose_name_plural = 'DNS History'
        indexes = [
            models.Index(fields=['ip_address', '-changed_at']),
        ]

    def __str__(self):
        return f'{self.ip_address} — "{self.old_dns_name}" → "{self.new_dns_name}"'


class PluginSettings(models.Model):
    """Singleton model for plugin DNS configuration."""

    dns_server1 = models.CharField(
        max_length=255, blank=True, default='',
        verbose_name='Primary DNS Server',
    )
    dns_server2 = models.CharField(
        max_length=255, blank=True, default='',
        verbose_name='Secondary DNS Server',
    )
    dns_server3 = models.CharField(
        max_length=255, blank=True, default='',
        verbose_name='Tertiary DNS Server',
    )
    perform_dns_lookup = models.BooleanField(
        default=True,
        verbose_name='Perform DNS Lookups',
    )

    # ── Auto-Scan scheduling ──
    auto_scan_enabled = models.BooleanField(
        default=False,
        verbose_name='Enable Auto-Scan',
        help_text='Automatically ping existing IPs in prefixes on a schedule',
    )
    auto_scan_interval = models.IntegerField(
        default=60,
        choices=INTERVAL_CHOICES,
        verbose_name='Auto-Scan Interval',
    )
    auto_discover_enabled = models.BooleanField(
        default=False,
        verbose_name='Enable Auto-Discover',
        help_text='Automatically discover new IPs in prefixes on a schedule',
    )
    auto_discover_interval = models.IntegerField(
        default=1440,
        choices=INTERVAL_CHOICES,
        verbose_name='Auto-Discover Interval',
    )
    max_prefix_size = models.IntegerField(
        default=24,
        verbose_name='Minimum Prefix Length',
        help_text='Only auto-scan prefixes with this length or longer (e.g. 24 = /24 and smaller subnets)',
    )
    ping_history_max_records = models.IntegerField(
        default=50000,
        verbose_name='Max Ping History Records',
        help_text='Maximum number of ping history records to keep (0 = unlimited)',
    )
    ping_concurrency = models.IntegerField(
        default=100,
        verbose_name='Concurrent Pings',
        help_text='Number of simultaneous ping threads per scan job (increase if you raised LimitNOFILE for netbox-rq)',
    )
    ping_timeout = models.FloatField(
        default=1.0,
        verbose_name='Ping Timeout (seconds)',
        help_text='How long to wait for a ping response before marking as down (e.g. 0.5 for LAN, 1.0 for WAN)',
    )
    skip_reserved_ips = models.BooleanField(
        default=False,
        verbose_name='Skip Reserved IPs',
        help_text='Skip pinging IPs with "reserved" status during scans (they will show as Skipped)',
    )

    # ── DNS Sync to NetBox ──
    dns_sync_to_netbox = models.BooleanField(
        default=False,
        verbose_name='Sync DNS to NetBox',
        help_text='Write resolved DNS names back to the built-in IPAddress dns_name field',
    )
    dns_clear_on_missing = models.BooleanField(
        default=False,
        verbose_name='Clear DNS on Missing',
        help_text='Clear IPAddress dns_name when reverse DNS returns empty',
    )
    dns_preserve_if_alive = models.BooleanField(
        default=True,
        verbose_name='Preserve DNS if Alive',
        help_text='Keep existing DNS name if host is alive but DNS lookup fails (overrides clear)',
    )

    class Meta:
        verbose_name = 'Plugin Settings'
        verbose_name_plural = 'Plugin Settings'

    def __str__(self):
        return 'NetBox Ping Settings'

    @classmethod
    def load(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    def get_dns_servers(self):
        return [s for s in [self.dns_server1, self.dns_server2, self.dns_server3] if s]


SCHEDULE_MODE_CHOICES = [
    ('follow_global', 'Follow Global'),
    ('custom_on', 'Custom On'),
    ('custom_off', 'Custom Off'),
]

CUSTOM_INTERVAL_CHOICES = [
    (5, 'Every 5 minutes'),
    (15, 'Every 15 minutes'),
    (30, 'Every 30 minutes'),
    (60, 'Hourly'),
    (360, 'Every 6 hours'),
    (720, 'Every 12 hours'),
    (1440, 'Daily'),
    (10080, 'Weekly'),
]


class PrefixSchedule(models.Model):
    """Per-prefix scheduling overrides for auto-scan/discover."""

    prefix = models.OneToOneField(
        to='ipam.Prefix',
        on_delete=models.CASCADE,
        related_name='ping_schedule',
    )
    scan_mode = models.CharField(
        max_length=20,
        choices=SCHEDULE_MODE_CHOICES,
        default='follow_global',
        verbose_name='Scan Mode',
    )
    scan_interval = models.IntegerField(
        default=60,
        choices=CUSTOM_INTERVAL_CHOICES,
        verbose_name='Scan Interval',
    )
    discover_mode = models.CharField(
        max_length=20,
        choices=SCHEDULE_MODE_CHOICES,
        default='follow_global',
        verbose_name='Discover Mode',
    )
    discover_interval = models.IntegerField(
        default=1440,
        choices=CUSTOM_INTERVAL_CHOICES,
        verbose_name='Discover Interval',
    )

    class Meta:
        verbose_name = 'Prefix Schedule'
        verbose_name_plural = 'Prefix Schedules'

    def __str__(self):
        return f'Schedule for {self.prefix}'

    def is_scan_enabled(self, global_settings):
        if self.scan_mode == 'custom_on':
            return True
        if self.scan_mode == 'custom_off':
            return False
        return global_settings.auto_scan_enabled

    def get_effective_scan_interval(self, global_settings):
        if self.scan_mode == 'custom_on':
            return self.scan_interval
        return global_settings.auto_scan_interval

    def is_discover_enabled(self, global_settings):
        if self.discover_mode == 'custom_on':
            return True
        if self.discover_mode == 'custom_off':
            return False
        return global_settings.auto_discover_enabled

    def get_effective_discover_interval(self, global_settings):
        if self.discover_mode == 'custom_on':
            return self.discover_interval
        return global_settings.auto_discover_interval
