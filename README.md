# NetBox Ping

![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)
![NetBox](https://img.shields.io/badge/netbox-4.5%2B-blue.svg)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE)
[![PyPI](https://img.shields.io/pypi/v/netbox-ping.svg)](https://pypi.org/project/netbox-ping/)

A NetBox plugin for pinging, discovering, and monitoring IP addresses directly from your NetBox instance.

## Features

- **Ping individual IPs** — one-click ping from any IP address detail page
- **Scan prefixes** — ping all existing IPs in a prefix at once
- **Discover new hosts** — scan entire subnets to find and add active IPs not yet in NetBox
- **Bulk operations** — select multiple prefixes from the list view and scan/discover in bulk
- **Auto-scan scheduling** — configure recurring scans and discovery globally or per-prefix
- **Per-prefix schedule overrides** — three modes: Follow Global, Custom On, or Custom Off
- **DNS resolution** — automatic reverse DNS lookups with configurable DNS servers
- **Ping Status columns** — sortable status columns injected into the core IP Address and Prefix tables
- **Status panels** — ping results shown on IP Address and Prefix detail pages
- **Background jobs** — all scan/discover operations run as NetBox background jobs
- **Dark mode compatible**

## Requirements

- NetBox **4.5.0** or later
- Python **3.12** or later
- `ping` command available on the NetBox server
- NetBox background worker running (`netbox-rq`)

## Installation

### From PyPI

```bash
source /opt/netbox/venv/bin/activate
pip install netbox-ping
```

### From source

```bash
source /opt/netbox/venv/bin/activate
pip install git+https://github.com/DenDanskeMine/netbox-ping.git
```

### Enable the plugin

Add `netbox_ping` to your NetBox `configuration.py`:

```python
PLUGINS = [
    'netbox_ping',
]
```

### Apply migrations

```bash
cd /opt/netbox/netbox
python3 manage.py migrate
```

### Restart services

```bash
sudo systemctl restart netbox netbox-rq
```

## Usage

### New settings Page

<img width="2549" height="880" alt="image" src="https://github.com/user-attachments/assets/7eb011aa-d210-4b60-912b-bb69aa4679e8" />


### Ping a single IP

Navigate to any IP address in NetBox. Click the **Ping Now** button to ping it immediately. Results appear in the side panel showing reachability, response time, DNS name, and last seen time.

<img width="2266" height="858" alt="image" src="https://github.com/user-attachments/assets/493e4efd-0e65-41fa-93ce-4e51f7822a2a" />

### Scan a prefix

Navigate to a prefix and click the **Ping Subnet** button to ping all existing IPs in that prefix. Or click **Discover IPs** to scan the entire subnet range and automatically create new IP addresses for any responding hosts.

<img width="2256" height="860" alt="image" src="https://github.com/user-attachments/assets/7ed8a9bc-6af6-41ad-94e1-a42688c7455a" />

### Bulk operations

From the prefix list view, select one or more prefixes using the checkboxes, then click **Ping Selected** or **Discover Selected** to scan them all.

<img width="2283" height="389" alt="image" src="https://github.com/user-attachments/assets/149ff73d-0de0-402e-b71c-a070708a317d" />

### Custom Status badge

<img width="2257" height="556" alt="image" src="https://github.com/user-attachments/assets/f2792d6e-e2a1-4ce4-869e-9a57b574d518" />


<img width="731" height="441" alt="image" src="https://github.com/user-attachments/assets/45156d3c-d858-4e40-9304-e895ac4897e1" />



### View results

- **Plugins > Ping > Ping Results** — table of all individual IP ping results
- **Plugins > Ping > Scan Results** — table of all prefix scan summaries
- **Ping Status column** — enable the "Ping Status" column in the IP Address or Prefix table column configuration

### Auto-scan scheduling

1. Go to **Plugins > Ping > Settings**
2. Enable **Auto-Scan** and/or **Auto-Discover** and choose an interval
3. Set the **Minimum Prefix Length** to control which prefixes are scanned (default: /24)
4. The system job runs every minute and dispatches scans for prefixes that are due

### Per-prefix schedule overrides

From a prefix's **Ping Status** tab, you can override the global schedule:

| Mode | Behavior |
|------|----------|
| **Follow Global** | Uses whatever the global setting is (default) |
| **Custom On** | Always scans at a custom interval, regardless of global setting |
| **Custom Off** | Never auto-scans, even if global is enabled |

## Configuration

### DNS settings

Configure up to three DNS servers for reverse lookups in **Plugins > Ping > Settings**. DNS lookups are performed on reachable IPs to resolve their hostname.

### Auto-scan intervals

Available intervals: 5 minutes, 15 minutes, 30 minutes, hourly, every 6 hours, every 12 hours, daily, weekly.

## Development

```bash
git clone https://github.com/DenDanskeMine/netbox-ping.git
cd netbox-ping
pip install -e .
```

## License

This project is licensed under the Apache License 2.0 — see the [LICENSE](LICENSE) file for details.

## Support

- [Open an issue](https://github.com/DenDanskeMine/netbox-ping/issues) on GitHub
- Check existing issues for answers
