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

DIGEST_INTERVAL_CHOICES = [
    (0, 'Disabled'),
    (60, 'Hourly'),
    (360, 'Every 6 hours'),
    (720, 'Every 12 hours'),
    (1440, 'Daily'),
    (10080, 'Weekly'),
]

SCAN_EVENT_TYPE_CHOICES = [
    ('ip_went_down', 'IP Went Down'),
    ('ip_came_up', 'IP Came Up'),
    ('ip_discovered', 'IP Discovered'),
    ('dns_changed', 'DNS Changed'),
    ('ip_went_stale', 'IP Went Stale'),
    ('ip_removed_stale', 'Stale IP Removed'),
]

STALE_MODE_CHOICES = [
    ('follow_global', 'Follow Global'),
    ('exclude', 'Exclude'),
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
    consecutive_down_count = models.IntegerField(
        default=0,
        verbose_name='Consecutive Down Count',
        help_text='Number of consecutive scans where this IP was unreachable',
    )
    is_stale = models.BooleanField(
        default=False,
        verbose_name='Stale',
        help_text='IP has been unreachable beyond the configured stale threshold',
    )
    is_new = models.BooleanField(
        default=False,
        verbose_name='New',
        help_text='IP was recently auto-discovered',
    )
    discovered_at = models.DateTimeField(
        blank=True,
        null=True,
        verbose_name='Discovered At',
        help_text='When this IP was first auto-discovered',
    )

    class Meta:
        ordering = ['-last_checked']
        verbose_name = 'Ping Result'
        verbose_name_plural = 'Ping Results'

    def __str__(self):
        if self.is_skipped:
            status = 'Skipped'
        elif self.is_stale:
            status = 'Stale'
        elif self.is_reachable:
            status = 'Up'
        else:
            status = 'Down'
        if self.is_new:
            status += ' (New)'
        return f'{self.ip_address} — {status}'

    def get_absolute_url(self):
        return reverse('plugins:netbox_ping:pingresult', args=[self.pk])

    def get_status_color(self):
        if self.is_skipped:
            return 'warning'
        if self.is_stale:
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
    hosts_stale = models.IntegerField(default=0)
    hosts_new = models.IntegerField(default=0)
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
    next_scan_at = models.DateTimeField(
        blank=True,
        null=True,
        verbose_name='Next Scan At',
        help_text='When this prefix is next scheduled to be auto-scanned',
    )
    next_discover_at = models.DateTimeField(
        blank=True,
        null=True,
        verbose_name='Next Discover At',
        help_text='When this prefix is next scheduled to be auto-discovered',
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


class ScanEvent(models.Model):
    """Lightweight event accumulator for email digest notifications."""

    event_type = models.CharField(
        max_length=20,
        choices=SCAN_EVENT_TYPE_CHOICES,
    )
    prefix = models.ForeignKey(
        to='ipam.Prefix',
        on_delete=models.CASCADE,
        related_name='+',
        blank=True,
        null=True,
    )
    ip_address = models.ForeignKey(
        to='ipam.IPAddress',
        on_delete=models.CASCADE,
        related_name='+',
        blank=True,
        null=True,
    )
    detail = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    digest_sent = models.BooleanField(default=False)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Scan Event'
        verbose_name_plural = 'Scan Events'
        indexes = [
            models.Index(fields=['digest_sent', '-created_at']),
        ]

    def __str__(self):
        return f'{self.get_event_type_display()} — {self.ip_address or self.prefix}'


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

    # ── Email Notifications ──
    email_notifications_enabled = models.BooleanField(
        default=False,
        verbose_name='Enable Email Notifications',
        help_text='Send periodic digest emails summarizing scan results and changes',
    )
    email_recipients = models.TextField(
        blank=True,
        default='',
        verbose_name='Email Recipients',
        help_text='Comma-separated email addresses to receive digest reports',
    )
    email_digest_interval = models.IntegerField(
        default=1440,
        choices=DIGEST_INTERVAL_CHOICES,
        verbose_name='Digest Interval',
        help_text='How often to send digest emails (0 = disabled)',
    )
    email_include_details = models.BooleanField(
        default=True,
        verbose_name='Include Details',
        help_text='Include per-IP change tables in digest emails',
    )
    email_utilization_threshold = models.IntegerField(
        default=90,
        verbose_name='Utilization Alert Threshold (%)',
        help_text='Include prefixes at or above this utilization in digests (0 = disabled)',
    )
    email_on_change_only = models.BooleanField(
        default=True,
        verbose_name='Send on Change Only',
        help_text='Skip sending digest if there are no events or high-utilization alerts',
    )
    email_last_digest_sent = models.DateTimeField(
        blank=True,
        null=True,
        verbose_name='Last Digest Sent',
    )
    next_digest_at = models.DateTimeField(
        blank=True,
        null=True,
        verbose_name='Next Digest At',
        help_text='When the next email digest is scheduled to be sent',
    )

    # ── Stale IP Detection ──
    stale_enabled = models.BooleanField(
        default=False,
        verbose_name='Enable Stale Tagging',
        help_text='Mark IPs as stale when they have been unreachable beyond the configured thresholds',
    )
    stale_scans_threshold = models.IntegerField(
        default=0,
        verbose_name='Scans Threshold',
        help_text='Tag IP as stale after this many consecutive failed scans (0 = ignore scan count)',
    )
    stale_days_threshold = models.IntegerField(
        default=0,
        verbose_name='Days Threshold',
        help_text='Tag IP as stale after this many days since last seen online (0 = ignore days)',
    )
    stale_remove_enabled = models.BooleanField(
        default=False,
        verbose_name='Enable Auto-Remove',
        help_text='Automatically delete IPs from NetBox when they have been offline beyond the remove threshold',
    )
    stale_remove_days = models.IntegerField(
        default=30,
        verbose_name='Remove After Days',
        help_text='Delete IP from NetBox after this many days since last seen online',
    )

    # ── New IP Badge ──
    new_ip_days_threshold = models.PositiveIntegerField(
        default=7,
        verbose_name='New IP Badge Duration (days)',
        help_text='Show "New" badge on auto-discovered IPs for this many days (0 = disabled)',
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
    stale_mode = models.CharField(
        max_length=20,
        choices=STALE_MODE_CHOICES,
        default='follow_global',
        verbose_name='Stale Detection',
        help_text='Follow global stale settings or exclude this prefix from stale tagging and auto-removal',
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
