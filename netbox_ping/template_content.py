from django.urls import reverse
from netbox.plugins import PluginTemplateExtension
from .models import PingResult


class PrefixPingExtension(PluginTemplateExtension):
    """Inject Ping/Discover buttons onto Prefix detail and list pages."""
    models = ['ipam.prefix']

    def buttons(self):
        prefix = self.context['object']
        scan_url = reverse('plugins:netbox_ping:prefix_scan', args=[prefix.pk])
        discover_url = reverse('plugins:netbox_ping:prefix_discover', args=[prefix.pk])
        return (
            f'<a href="{scan_url}" class="btn btn btn-primary">'
            f'<span class="mdi mdi-lan-check" aria-hidden="true"></span> Ping Subnet</a> '
            f'<a href="{discover_url}" class="btn btn btn-success">'
            f'<span class="mdi mdi-magnify-scan" aria-hidden="true"></span> Discover IPs</a>'
        )

    def list_buttons(self):
        bulk_scan_url = reverse('plugins:netbox_ping:bulk_prefix_scan')
        bulk_discover_url = reverse('plugins:netbox_ping:bulk_prefix_discover')
        return (
            f'<button type="button" class="btn btn btn-primary netbox-ping-bulk-btn" '
            f'data-action-url="{bulk_scan_url}">'
            f'<span class="mdi mdi-lan-check"></span> Ping Selected</button> '
            f'<button type="button" class="btn btn btn-success netbox-ping-bulk-btn" '
            f'data-action-url="{bulk_discover_url}">'
            f'<span class="mdi mdi-magnify-scan"></span> Discover Selected</button>'
            f'''
            <script>
            document.addEventListener('DOMContentLoaded', function() {{
                document.querySelectorAll('.netbox-ping-bulk-btn').forEach(function(btn) {{
                    btn.addEventListener('click', function() {{
                        var checked = document.querySelectorAll('input[name="pk"]:checked');
                        var pks = Array.from(checked).map(function(cb) {{ return cb.value; }});
                        var url = this.dataset.actionUrl;
                        if (pks.length > 0) {{
                            url += '?pk=' + pks.join('&pk=');
                        }}
                        // If nothing selected, it will scan all
                        window.location.href = url;
                    }});
                }});
            }});
            </script>
            '''
        )

    def right_page(self):
        prefix = self.context['object']
        try:
            scan_result = prefix.scan_result
        except Exception:
            scan_result = None
        return self.render(
            'netbox_ping/inc/prefix_scan_panel.html',
            extra_context={'scan_result': scan_result},
        )


class IPAddressPingExtension(PluginTemplateExtension):
    """Inject a ping status panel onto IPAddress detail pages."""
    models = ['ipam.ipaddress']

    def right_page(self):
        ip = self.context['object']
        try:
            ping_result = ip.ping_result
        except PingResult.DoesNotExist:
            ping_result = None

        uptime_pct = None
        uptime_color = 'secondary'
        uptime_up = 0
        uptime_total = 0
        if ping_result:
            stats = ping_result.uptime_percentage(hours=None)  # all-time
            if stats:
                uptime_pct = stats['percentage']
                uptime_up = stats['up']
                uptime_total = stats['total']
                uptime_color = ping_result.uptime_color(uptime_pct)

        return self.render(
            'netbox_ping/inc/ipaddress_ping_panel.html',
            extra_context={
                'ping_result': ping_result,
                'uptime_pct': uptime_pct,
                'uptime_up': uptime_up,
                'uptime_total': uptime_total,
                'uptime_color': uptime_color,
            },
        )

    def buttons(self):
        ip = self.context['object']
        ping_url = reverse('plugins:netbox_ping:ip_ping', args=[ip.pk])
        return (
            f'<a href="{ping_url}" class="btn btn btn-primary">'
            f'<span class="mdi mdi-lan-check" aria-hidden="true"></span> Ping Now</a>'
        )


template_extensions = [PrefixPingExtension, IPAddressPingExtension]
