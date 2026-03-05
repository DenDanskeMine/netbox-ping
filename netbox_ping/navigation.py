from netbox.plugins import PluginMenu, PluginMenuItem

menu = PluginMenu(
    label='Ping',
    groups=(
        ('Results', (
            PluginMenuItem(
                link='plugins:netbox_ping:pingresult_list',
                link_text='Ping Results',
                permissions=('netbox_ping.view_pingresult',),
            ),
            PluginMenuItem(
                link='plugins:netbox_ping:pinghistory_list',
                link_text='Ping History',
                permissions=('netbox_ping.view_pinghistory',),
            ),
            PluginMenuItem(
                link='plugins:netbox_ping:subnetscanresult_list',
                link_text='Scan Results',
                permissions=('netbox_ping.view_subnetscanresult',),
            ),
        )),
        ('Configuration', (
            PluginMenuItem(
                link='plugins:netbox_ping:settings',
                link_text='Settings',
            ),
            PluginMenuItem(
                link='plugins:netbox_ping:sshjumphost_list',
                link_text='SSH Jumphosts',
            ),
        )),
    ),
    icon_class='mdi mdi-lan-check',
)
