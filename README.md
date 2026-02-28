# NetBox Ping

![Python](https://img.shields.io/badge/python-3.12%2B-blue.svg)
![NetBox](https://img.shields.io/badge/netbox-4.5%2B-blue.svg)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE)
[![PyPI](https://img.shields.io/pypi/v/netbox-ping.svg)](https://pypi.org/project/netbox-ping/)
[![PyPI Downloads](https://static.pepy.tech/personalized-badge/netbox-ping?period=total&units=INTERNATIONAL_SYSTEM&left_color=BLACK&right_color=GREEN&left_text=downloads)](https://pepy.tech/projects/netbox-ping)

A NetBox plugin for pinging, discovering, and monitoring IP addresses directly from your NetBox instance.

**Other plugins:** [NetBox Map](https://github.com/DenDanskeMine/netbox-map) | [Website](https://www.danbyte.net/) | [Demo](https://demo.danbyte.net/)

## Features

**Scanning and Discovery**
- Ping individual IPs with one click from any IP address page
- Scan all existing IPs in a prefix, or discover new hosts across entire subnets
- Bulk scan/discover from the prefix list view
- Auto-scan scheduling with per-prefix overrides (Follow Global / Custom On / Custom Off)
- Skip reserved IPs during scans

**Monitoring**
- Stale IP detection -- tag IPs as stale after X failed scans or X days offline
- Auto-remove stale IPs from NetBox after a configurable threshold
- Per-prefix exclusion from stale detection for critical infrastructure
- Ping history with full audit trail per IP
- Quick filter tabs on the Ping Results page (All / Up / Down / Stale / Skipped)

**DNS**
- Automatic reverse DNS lookups with up to 3 configurable servers
- Sync resolved names back to NetBox IPAddress records
- DNS change history tracked per IP

**Notifications**
- Email digest with IP state transition badges (Up -> Down, Down -> Stale, etc.)
- High utilization prefix alerts
- Configurable intervals (5 min to weekly), send on change only option

**Integration**
- Ping Status columns on core IP Address and Prefix tables
- Status tabs on IP Address and Prefix detail pages
- All operations run as background jobs
- REST API for ping results, history, and scan results
- Dark mode compatible

## Screenshots

### Settings

<img width="2549" alt="Settings page" src="https://github.com/user-attachments/assets/7eb011aa-d210-4b60-912b-bb69aa4679e8" />

### IP Address Ping Tab

<img width="2266" alt="IP ping tab" src="https://github.com/user-attachments/assets/493e4efd-0e65-41fa-93ce-4e51f7822a2a" />

### Prefix Ping Tab

<img width="2256" alt="Prefix ping tab" src="https://github.com/user-attachments/assets/7ed8a9bc-6af6-41ad-94e1-a42688c7455a" />

### Bulk Operations

<img width="2283" alt="Bulk operations" src="https://github.com/user-attachments/assets/149ff73d-0de0-402e-b71c-a070708a317d" />

### Status Badges on Core Tables

<img width="2257" alt="Status badges on IP table" src="https://github.com/user-attachments/assets/f2792d6e-e2a1-4ce4-869e-9a57b574d518" />

<img width="731" alt="Status badges on prefix table" src="https://github.com/user-attachments/assets/45156d3c-d858-4e40-9304-e895ac4897e1" />

## Installation

```bash
source /opt/netbox/venv/bin/activate
pip install netbox-ping
```

Or from source:

```bash
source /opt/netbox/venv/bin/activate
pip install git+https://github.com/DenDanskeMine/netbox-ping.git
```

Add to `configuration.py`:

```python
PLUGINS = [
    'netbox_ping',
]
```

Apply migrations and restart:

```bash
cd /opt/netbox/netbox
python3 manage.py migrate
sudo systemctl restart netbox netbox-rq
```

### Upgrading from v1

If you get migration errors when upgrading from v1, reset the migration state:

```bash
sudo -u postgres psql netbox -c "DELETE FROM django_migrations WHERE app = 'netbox_ping';"
sudo /opt/netbox/venv/bin/python manage.py migrate netbox_ping
```

## Configuration

All settings are in **Plugins > Ping > Settings**.

### DNS

| Setting | Description |
|---------|-------------|
| DNS Servers (1-3) | Custom nameservers for reverse lookups |
| Sync DNS to NetBox | Write resolved names back to IPAddress.dns_name |
| Clear DNS on Missing | Clear DNS field when lookup returns empty |
| Preserve DNS if Alive | Keep existing DNS if host is up but lookup fails |

### Auto-Scan

| Setting | Description |
|---------|-------------|
| Auto-Scan / Auto-Discover | Enable recurring scans with configurable interval |
| Min Prefix Length | Only scan prefixes of this size or smaller (default: /24) |
| Per-Prefix Overrides | Follow Global, Custom On, or Custom Off per prefix |

Available intervals: 5 min, 15 min, 30 min, hourly, 6h, 12h, daily, weekly.

### Stale IP Detection

| Setting | Description |
|---------|-------------|
| Enable Stale Tagging | Tag IPs as stale when thresholds are met |
| Scans Threshold | Consecutive failed scans before tagging (0 = ignore) |
| Days Threshold | Days since last seen before tagging (0 = ignore) |
| Enable Auto-Remove | Delete stale IPs after a separate days threshold |
| Remove After Days | Days since last seen before deletion |

Per-prefix exclusion is available on each prefix's Ping Status tab.

### Email Notifications

Uses NetBox's existing `EMAIL` settings from `configuration.py`.

| Setting | Description |
|---------|-------------|
| Recipients | Comma-separated email addresses |
| Digest Interval | How often to send (5 min to weekly) |
| Include Details | Show per-IP state transitions grouped by prefix |
| Utilization Threshold | Alert on prefixes at or above this % (0 = disabled) |
| Send on Change Only | Skip sending if nothing happened |

Emails show state transitions per IP (e.g. Up -> Down, Down -> Stale, Stale -> Deleted) so you can see the current state at a glance.

## Navigation

| Menu Item | Description |
|-----------|-------------|
| Plugins > Ping > Ping Results | Current state of all tracked IPs with quick filter tabs |
| Plugins > Ping > Ping History | Full audit trail of all ping checks |
| Plugins > Ping > Scan Results | Per-prefix scan summaries with utilization |
| Plugins > Ping > Settings | All plugin configuration |

## Performance

Concurrent pings per job defaults to 100 threads. To go higher (~240+), raise the file descriptor limit:

```ini
# /etc/systemd/system/netbox-rq.service
[Service]
LimitNOFILE=65535
```

```bash
sudo systemctl daemon-reload
sudo systemctl restart netbox-rq
```

## Requirements

- NetBox 4.5.0+
- Python 3.12+
- `ping` command on the server
- `netbox-rq` worker running

## Development

```bash
git clone https://github.com/DenDanskeMine/netbox-ping.git
cd netbox-ping
pip install -e .
```

## License

Apache License 2.0 -- see [LICENSE](LICENSE).

## Support

[Open an issue](https://github.com/DenDanskeMine/netbox-ping/issues) on GitHub.
