# NAS Home Automation Homelab — Docker + Smart Home on btrfs

A reference guide for running Docker and a complete home automation stack on a **Ugreen DXP 2800 NAS** with multiple satellite SBCs — covering Zigbee, Z-Wave, Thread/Matter, and monitoring.

## What This Repo Is

**This is not a "clone and run" project.** It's a reference guide for anyone building a self-hosted home automation lab on a UGOS NAS (or similar overlay-on-overlay system). The README is the product. The config files are supporting evidence.

If you're searching for "ugreen docker overlay btrfs", "DXP 2800 homelab", "Z-Wave JS UI Docker NAS", or "Thread Matter Home Assistant Docker" — you're in the right place.

## What's Inside

| File | Purpose |
|------|---------|
| `README.md` | Full walkthrough — btrfs fix, 12 deployment steps, Odroid SBC setup |
| `docker/docker-compose.yml` | Single compose file for all NAS services |
| `docker/daemon.json` | Docker engine config (btrfs driver + data-root) |
| `configs/homeassistant/configuration.yaml` | HA reverse-proxy trust + panel_custom config |
| `configs/homeassistant/www/iframe-panel.js` | Custom HA sidebar panel — embeds URL in iframe |
| `configs/homeassistant/www/newtab-panel.js` | Custom HA sidebar panel — opens URL in new tab |
| `configs/homeassistant/scripts/s200_tdb_sensors.py` | GL-S200 TDB sensor bridge script (JSON-RPC auth) |
| `configs/homeassistant/scripts/s200_tdb_led.py` | GL-S200 TDB LED control script (SSH + CoAP) |
| `odroid/docker-compose.network.yml` | Odroid #1 compose — AdGuard, Grist, Vaultwarden, Beszel, Portainer |
| `odroid/docker-compose.media.yml` | Odroid #2 compose — Jellyfin, Beszel Agent, Portainer |
| `odroid/daemon.json` | Odroid Docker engine config (SD card data-root) |
| `.env.example` | Template for site-specific values |

## The Stack

### NAS (primary Docker host)

| Service | Purpose |
|---------|---------|
| [Home Assistant](https://www.home-assistant.io/) | Home automation platform |
| [Nginx Proxy Manager](https://nginxproxymanager.com/) | Reverse proxy with auto TLS |
| [ESPHome](https://esphome.io/) | ESP32/ESP8266 firmware platform |
| [HACS](https://hacs.xyz/) | HA community integration store (not a container) |
| [python-matter-server](https://github.com/home-assistant-libs/python-matter-server) | Matter-over-Thread bridge for HA Docker |
| [Z-Wave JS UI](https://github.com/zwave-js/zwave-js-ui) | Z-Wave controller UI + WebSocket server |

### Hardware Integrations (network devices — no USB passthrough)

| Device | Protocol | Connection | Purpose |
|--------|----------|------------|---------|
| [SLZB-06MU](https://smlight.tech/) | Zigbee | `socket://IP:6638` via ZHA | Zigbee coordinator (PoE Ethernet) |
| [TubesZB Z-Wave PoE](https://tubeszb.com/) | Z-Wave | `tcp://IP:6638` via Z-Wave JS UI | Z-Wave coordinator (PoE Ethernet) |
| [GL-S200](https://docs.gl-inet.com/iot/en/thread_board_router/gl-s200/) | Thread/Matter | OTBR API `:8081` + JSON-RPC + SSH | Thread Border Router + CoAP dev boards |

### Odroid #1 — Network Core

| Service | Purpose |
|---------|---------|
| [AdGuard Home](https://adguard.com/adguard-home/overview.html) | Network-wide DNS ad blocking |
| [Grist](https://www.getgrist.com/) | Self-hosted spreadsheet/database |
| [Vaultwarden](https://github.com/dani-garcia/vaultwarden) | Self-hosted Bitwarden password manager |
| [Beszel](https://github.com/henrygd/beszel) | Server monitoring hub + agent |
| [Portainer](https://www.portainer.io/) | Docker management UI |

### Odroid #2 — Media Server

| Service | Purpose |
|---------|---------|
| [Jellyfin](https://jellyfin.org/) | Media streaming server |
| [Beszel Agent](https://github.com/henrygd/beszel) | Server monitoring agent |
| [Portainer](https://www.portainer.io/) | Docker management UI |

---

## System Info

| Detail       | Value                          |
|--------------|--------------------------------|
| Device       | Ugreen DXP 2800 NAS           |
| OS           | Debian GNU/Linux 12 (bookworm) |
| Architecture | x86_64 (amd64)                 |
| CPUs         | 4                              |
| RAM          | 7.5 GiB                        |

---

## The Problem — Why Docker Doesn't Work Out of the Box

Docker fails on this NAS with a cryptic `mount: invalid argument`. The root cause is a chain of three incompatibilities:

### 1. Overlay-on-overlay is illegal

The NAS root filesystem (`/`) is already a two-layer overlay:

```
Layer 2 (top):  overlay on /
                  upperdir = /overlay/upper  (ext4 on eMMC, 19 GB, writable, root-only)
                  lowerdir = /rom

Layer 1 (base): overlay on /rom
                  upperdir = /tmp/rom_upper  (tmpfs, lost on reboot)
                  lowerdir = 5 stacked read-only squashfs images:
                    /rootfs/oem    ← Ugreen OEM customizations
                    /rootfs/fw     ← Firmware/services
                    /rootfs/apt    ← APT package cache
                    /rootfs/kernel ← Kernel modules
                    /rootfs/base   ← Debian 12 base system
```

Docker's default `overlay2` storage driver tries to create its own overlay mounts. The Linux kernel rejects overlay-on-overlay. **Docker's `overlay2` driver cannot work anywhere on this NAS** — the root overlay poisons the entire mount namespace.

### 2. The `btrfs` driver requires a btrfs filesystem

The only alternative storage driver that works without overlay is `btrfs`, but it requires the underlying filesystem to actually be btrfs.

### 3. Your NVMe volume might be ext4

If you formatted your NVMe pool as ext4 (the factory default on some UGOS versions), then both `overlay2` and `btrfs` drivers fail. Docker cannot run on that volume at all.

### Decision Matrix

| Volume     | Filesystem | overlay2 driver      | btrfs driver    | Docker? |
|------------|------------|----------------------|-----------------|---------|
| `/` (root) | overlay    | ✗ overlay-on-overlay | ✗ not btrfs     | **No**  |
| Volume (ext4) | ext4    | ✗ overlay-on-overlay | ✗ not btrfs     | **No**  |
| Volume (btrfs) | btrfs  | ✗ overlay-on-overlay | **✓**           | **Yes** |

---

## The Fix

Reformat your storage pool(s) as **btrfs** through the UGOS management UI, then configure Docker to use the `btrfs` storage driver.

### Recommended Layout

| Pool   | RAID   | Drives       | Mount      | FS    | Purpose                                         |
|--------|--------|--------------|------------|-------|--------------------------------------------------|
| Pool 1 | RAID 0 | 2× NVMe SSD | `/volume1` | btrfs | Docker data, compose files, configs, active work |
| Pool 2 | RAID 1 | 2× SATA      | `/volume2` | btrfs | Backups, snapshots, video, long-term storage     |

### Docker Engine Config

**File:** `/etc/docker/daemon.json`

```json
{
  "data-root": "/volume1/@docker",
  "storage-driver": "btrfs"
}
```

See [`docker/daemon.json`](docker/daemon.json) for reference.

> **Lesson learned:** On this NAS, Docker can only use the `btrfs` storage driver on a btrfs-formatted volume. The `overlay2` driver will never work. Any new volume must be btrfs if Docker will use it.

---

## Storage Layout — 3 Hardware Tiers

```
TIER 1: eMMC (mmcblk0) — 32 GB internal soldered chip
  Partitions:
    p1  /boot          256 MB  vfat   ← EFI boot + kernel
    p2  /rootfs        2.0 GB  ext4   ← squashfs staging
    p3  /mnt/factory   8.6 MB  ext4   ← factory defaults
    p5  [SWAP]         swap
    p6  /ugreen        3.9 GB  ext4   ← Ugreen app store
    p7  /overlay       19 GB   ext4   ← Overlay upper (label: USER-DATA)
──────────────────────────────────────────────────────────
TIER 2: NVMe SSDs — RAID 0
    → /volume1         btrfs          ← Storage Pool 1 — Docker, active workloads
──────────────────────────────────────────────────────────
TIER 3: SATA drives — RAID 1
    → /volume2         btrfs          ← Storage Pool 2 — Backups, snapshots, video
    → /home            (btrfs subvolume @home on same pool)
```

### Where to Put Things

| What                                 | Where              | Why                                        |
|--------------------------------------|--------------------|--------------------------------------------|
| Docker data (images, containers)     | `/volume1/@docker` | Fast NVMe RAID 0, btrfs compatible         |
| Docker compose files & configs       | `/volume1/docker/` | Same fast pool as Docker data              |
| Backups, snapshots, media, big files | `/volume2/`        | Redundant SATA RAID 1                      |
| System configs (`daemon.json`)       | `/etc/docker/`     | Required location, use `sudo`              |
| Temporary/scratch                    | `/tmp`             | Auto-cleared, no sudo needed               |
| **NEVER** put data on               | `/` root directly  | Small eMMC, root-only, overlay quirks      |

### Why VS Code Can't Create Files Everywhere

VS Code Remote SSH runs as your NAS user (uid 1000). This user cannot write to most paths because the overlay upper at `/overlay/upper` is owned by root. To create a user-writable area:

```bash
sudo mkdir -p /volume1/docker
sudo chown -R YOUR_USER:admin /volume1/docker
```

---

## Docker Installation

Install from **Docker's official APT repository** (not Debian's `docker.io` package):

```bash
# Add Docker's official GPG key
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/debian/gpg -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg

# Add the repository
echo \
  "deb [arch=amd64 signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/debian \
  bookworm stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# Install
sudo apt-get update
sudo apt-get install docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# Add your user to docker group
sudo usermod -aG docker YOUR_USER
```

> **Note:** `sudo apt install docker.io` does NOT work on this system.

---

## Deployment — Step by Step

All NAS services are managed from a single compose file: [`docker/docker-compose.yml`](docker/docker-compose.yml)

### Directory Layout

```
/volume1/docker/
├── compose/
│   └── docker-compose.yml        ← single compose file, all services
└── configs/
    ├── homeassistant/            ← HA config volume
    ├── nginx-proxy-manager/      ← NPM data + letsencrypt
    ├── esphome/                  ← ESPHome config volume
    ├── matter-server/            ← Matter server data
    └── zwavejsui/                ← Z-Wave JS UI store
```

### Rules

- **1 reverse proxy** — Nginx Proxy Manager only, no duplicates
- **1 compose file** — manages all NAS services
- **No random ports** — all external access goes through the reverse proxy
- **All data on `/volume1/docker/`** — nothing on root overlay

---

### Step 1: Home Assistant

| Setting        | Value                                          |
|----------------|-------------------------------------------------|
| Container name | `homeassistant`                                |
| Image          | `ghcr.io/home-assistant/home-assistant:stable` |
| Network        | `host` (required for mDNS device discovery)    |
| Port           | 8123                                           |
| Config volume  | `/volume1/docker/configs/homeassistant:/config` |

```bash
sudo mkdir -p /volume1/docker/{compose,configs/homeassistant}
sudo chown -R YOUR_USER:admin /volume1/docker
cd /volume1/docker/compose && sudo docker compose up -d
```

Verify: `http://YOUR_NAS_IP:8123`

---

### Step 2: Nginx Proxy Manager

| Setting        | Value                                                    |
|----------------|----------------------------------------------------------|
| Container name | `npm`                                                    |
| Image          | `jc21/nginx-proxy-manager:latest`                        |
| Ports          | 80:80, 443:443, 8181:81 (admin UI)                       |

```bash
sudo mkdir -p /volume1/docker/configs/nginx-proxy-manager/{data,letsencrypt}
cd /volume1/docker/compose && sudo docker compose up -d
```

Default login: `admin@example.com` / `changeme` (change immediately)

---

### Step 3: HTTPS — Cloudflare + NPM + Home Assistant

Route: `Browser → Cloudflare DNS (gray cloud) → NPM (TLS termination) → HA`

#### A. Cloudflare DNS

| Type | Name | Content       | Proxy status          |
|------|------|---------------|-----------------------|
| A    | `ha` | `YOUR_NAS_IP` | DNS only (gray cloud) |

> **DNS only is required** — Cloudflare's proxy cannot reach a private LAN IP.

#### B. SSL Certificate (in NPM UI)

| Setting              | Value                                |
|----------------------|--------------------------------------|
| Domain Names         | `*.yourdomain.com`, `yourdomain.com` |
| DNS Challenge        | Yes — Cloudflare                     |
| Credentials Content  | `dns_cloudflare_api_token = YOUR_CF_API_TOKEN` |
| Propagation Seconds  | `250`                                |

#### C. NPM Proxy Host

| Setting              | Value                |
|----------------------|----------------------|
| Domain Names         | `ha.yourdomain.com`  |
| Scheme               | `http`               |
| Forward Hostname/IP  | `YOUR_NAS_IP`        |
| Forward Port         | `8123`               |
| Websockets Support   | ON                   |
| SSL Certificate      | `*.yourdomain.com`   |
| Force SSL / HTTP/2   | ON                   |

#### D. Home Assistant Trusted Proxy

Add to `configuration.yaml` (see [`configs/homeassistant/configuration.yaml`](configs/homeassistant/configuration.yaml)):

```yaml
http:
  use_x_forwarded_for: true
  trusted_proxies:
    - 172.16.0.0/12     # Docker bridge networks
    - 192.168.0.0/16    # LAN subnet (adjust to yours)
```

---

### Step 4: HACS — Home Assistant Community Store

Not a Docker container — installed inside HA:

```bash
sudo docker exec -it homeassistant bash -c "wget -O - https://get.hacs.xyz | bash -"
cd /volume1/docker/compose && sudo docker compose restart homeassistant
```

Then: **Settings → Devices & Services → Add Integration → "HACS"** → authorize with GitHub.

---

### Step 5: ESPHome

| Setting        | Value                                    |
|----------------|------------------------------------------|
| Container name | `esphome`                                |
| Image          | `ghcr.io/esphome/esphome:stable`         |
| Port           | 6052                                     |

```bash
sudo mkdir -p /volume1/docker/configs/esphome
cd /volume1/docker/compose && sudo docker compose up -d
```

NPM Proxy: `esphome.yourdomain.com` → `esphome:6052` (websockets ON, Force SSL)

---

### Step 6: NPM Admin HTTPS Proxy

Proxy NPM's own admin UI: `npm.yourdomain.com` → `npm:81` (websockets ON, Force SSL)

---

### Step 7: HA Sidebar Links

> **Do not** use `panel_iframe` in `configuration.yaml` — it was removed in HA 2026.x. Use `panel_custom` with custom JS elements instead.

Two reusable panel components (see [`configs/homeassistant/www/`](configs/homeassistant/www/)):

| Component      | File                | Behavior                |
|----------------|---------------------|-------------------------|
| `iframe-panel` | `www/iframe-panel.js` | Embeds URL in iframe   |
| `newtab-panel` | `www/newtab-panel.js` | Opens URL in new tab   |

Use **iframe** when the service sends no `X-Frame-Options` or CSP headers. Use **new tab** when it does (most services block iframing).

Add to `configuration.yaml` under `panel_custom:`:

```yaml
panel_custom:
  # Iframe example (service allows embedding)
  - name: iframe-panel
    url_path: grist
    sidebar_title: "Grist"
    sidebar_icon: "mdi:table-large"
    module_url: /local/iframe-panel.js
    config:
      url: "http://YOUR_GRIST_IP:8484"

  # New-tab example (service blocks iframing)
  - name: newtab-panel
    url_path: adguard
    sidebar_title: "AdGuard Home"
    sidebar_icon: "mdi:shield-check"
    module_url: /local/newtab-panel.js
    config:
      url: "http://YOUR_ADGUARD_IP:8053"
      name: "AdGuard Home"
```

---

### Step 8: Zigbee Coordinator (SLZB-06MU via PoE Ethernet + ZHA)

The SLZB-06MU connects over **PoE Ethernet** — no USB passthrough needed. HA connects via TCP socket.

| Setting | Value |
|---------|-------|
| Device | SMLIGHT SLZB-06MU |
| Connection | `socket://ZIGBEE_COORDINATOR_IP:6638` |
| HA Integration | ZHA (Zigbee Home Automation) |
| Radio type | EZSP (Silicon Labs) |

#### Setup

1. Connect the SLZB-06MU to a PoE Ethernet port
2. Find its IP and set a DHCP reservation
3. Access the web UI at `http://ZIGBEE_COORDINATOR_IP` — verify firmware, coordinator mode, Ethernet active
4. In HA: **Settings → Devices & Services → Add Integration** → the SLZB-06MU should auto-discover via SMLIGHT. If not, add ZHA manually with the socket path above.

#### Docker Changes

**None.** HA is on `network_mode: host` with `privileged: true` — full network access. No compose changes needed.

#### NPM Proxy (optional)

`zigbee.yourdomain.com` → `ZIGBEE_COORDINATOR_IP:80` (websockets ON, Force SSL)

> NPM proxies the HTTP web UI only. The ZHA socket connection (port 6638) goes directly to the device IP.

---

### Step 9: Home Assistant Companion App

Install the **Home Assistant** app on your phone for push notifications, location tracking, and remote access.

#### A. Install & Connect

1. Install from iOS App Store or Google Play
2. Enter your HA URL (local or external)
3. Sign in with your HA account
4. Allow notifications when prompted

#### B. Correct URL Settings

Configure both URLs so the app auto-switches based on network:

1. Companion App → **Settings → Companion App → Server Settings**
2. Set:

| Setting        | Value                           | When used                     |
|----------------|----------------------------------|-------------------------------|
| Internal URL   | `http://YOUR_NAS_IP:8123`       | When on home WiFi             |
| External URL   | `https://ha.yourdomain.com`     | When on mobile data / VPN     |

3. Under **Internal Connection** → set your **Home WiFi SSID**

> With Teleport VPN (Step 10), the internal URL also works remotely since the VPN gives full LAN access.

#### C. Verify Notify Service

In HA: **Developer Tools → Services** → type `notify.` → you should see `notify.mobile_app_<your_phone>`.

---

### Step 10: Remote Access via UniFi Teleport + WiFiman

Use **UniFi Teleport** (built into UDM/UDR/UCG) with the **WiFiman** app for one-tap remote VPN access. No port forwarding, works behind CGNAT.

> **Why Teleport instead of WireGuard?** WireGuard requires manual profile export, QR scanning, and port forwarding (UDP 51820). Teleport is zero-config — enable it in UniFi OS, install WiFiman, connect. Full LAN access.

#### Setup

1. **UniFi OS → Settings → Teleport & VPN** → enable **Teleport**
2. Install **WiFiman** app → Teleport tab → sign in with Ubiquiti account → connect
3. Test: disconnect WiFi → WiFiman Teleport connect → HA Companion App connects via internal URL

---

### Step 11: GL-S200 Thread Border Router + Thread Dev Boards + Matter

Adds a Thread mesh network using the GL.iNet GL-S200, with two parallel communication paths:
- **Matter** for standard Thread devices (via `python-matter-server`)
- **CoAP** for GL.iNet's proprietary Thread Dev Boards (via JSON-RPC + SSH bridge)

#### python-matter-server Container

| Setting | Value |
|---------|-------|
| Container name | `matter-server` |
| Image | `ghcr.io/matter-js/python-matter-server:stable` |
| Network | `host` (required for mDNS) |
| WebSocket Port | 5580 |
| Data volume | `/volume1/docker/configs/matter-server/data:/data` |
| D-Bus mount | `/run/dbus:/run/dbus:ro` (required for BLE commissioning) |

#### HA Integrations

1. **OpenThread Border Router** → `http://S200_IP:8081`
2. **Thread** → configure, set preferred network
3. **Matter** → uncheck "use the add-on" → WebSocket URL: `ws://localhost:5580/ws`

#### CoAP Dev Board Bridge (TDB Sensors + LEDs + PIR)

Since the TDB boards use proprietary CoAP (not Matter), three bridge paths are needed:

| Feature | Path | Script |
|---------|------|--------|
| **Sensors** | `command_line` sensor → Python → HTTPS JSON-RPC → S200 → UBUS | [`scripts/s200_tdb_sensors.py`](configs/homeassistant/scripts/s200_tdb_sensors.py) |
| **RGB LEDs** | `shell_command` → Python → SSH → S200 → `coap_cli` → CoAP | [`scripts/s200_tdb_led.py`](configs/homeassistant/scripts/s200_tdb_led.py) |
| **PIR Motion** | S200 webhook automation → HTTP POST → HA webhook trigger | Configured in S200 web UI |

The S200's JSON-RPC API requires multi-step challenge-response auth (challenge → crypt hash → MD5 → login → session). HA's built-in REST platform can't handle this, hence the Python helper scripts.

#### Architecture Evolution: s200-bridge + Custom Component

The original Python-script architecture (above table) was replaced by a unified **s200-bridge** daemon + **s200_tdb** custom HA component:

- **s200-bridge** — async Python daemon (Docker container, host network, port 8765). Handles JSON-RPC auth/session, persistent SSH for CoAP LED commands, sensor polling (3s), LED status polling (10s), WebSocket server for HA.
- **s200_tdb custom component** — HA integration that connects to the bridge via WebSocket. Exposes sensors, RGB lights, connectivity, and PIR motion binary sensors. Registers webhooks for PIR events (posted directly by S200 firmware, not through the bridge).

PIR motion flow: `TDB PIR sensor → S200 firmware automation → HTTP POST webhook → HA s200_tdb component → binary_sensor.tdb_X_motion (30s auto-reset timer) → automation → light.tdb_X_leds`

#### Bug Fix: PIR Dual-Timer Desync (April 7, 2026)

**Symptom:** After the 30-second LED timeout, the PIR sensor would not re-trigger LEDs for an unpredictable delay — sometimes minutes. One board consistently worse than the other.

**Root cause:** Two independent 30-second timers ran in parallel — one in the custom component's webhook handler (`async_call_later` with cancel-and-restart) controlling `binary_sensor.tdb_X_motion`, and one in the HA automation (`delay: 30s` with `mode: restart`) controlling the LED. When a PIR event fired mid-window, the webhook timer restarted but the automation's `binary_sensor` trigger (which requires a state *change* to `on`) did not re-fire because motion was already `on`. This caused the timers to drift: the automation's LED-off fired first, then subsequent PIR webhooks arrived while motion was still `True` (no state change), so the automation ignored them until the webhook timer finally expired and reset motion to `False`.

**Fix:** Removed `delay: 30s` from both LED reaction automations. Made them purely reactive — trigger on `binary_sensor.tdb_X_motion` changing to **either** `on` or `off`, with an `if/then/else` mirroring the state to the LED. The custom component's 30s cancel-and-restart timer is now the single source of truth.

#### Refactor: Dynamic Device Discovery (April 7, 2026)

Replaced hardcoded device registries with dynamic discovery so new TDB boards can be added through the HA UI.

**Bridge:** Removed hardcoded `DEVICES` dict. Bridge now calls `otbr-gateway.get_device_list` via JSON-RPC on startup + every 60s to discover TDB boards and their IPv6 addresses. Sends `device_list` message to WebSocket clients on connect and on changes. Handles IPv6 changes on Thread network rejoin automatically.

**Custom component:** Config flow v1→v2 migration. Added options flow with Add Device (queries bridge for discovered devices, user selects, sets name + webhook ID) and Remove Device. All platform files read devices from `entry.options["devices"]` via coordinator instead of hardcoded constants. Existing TDB 1 + TDB 2 are auto-migrated preserving webhook IDs.

**Adding a new board:**
1. Flash v1.3.0 firmware via USB and commission on the S200 (see [gl-thread-dev-board README](https://github.com/coyotegd/gl-thread-dev-board) Recovery section for full procedure)
2. Once the board joins Thread, the bridge auto-discovers it within 60 seconds
3. In HA: **Settings → Devices & Services → S200 TDB Boards** — click the **cog wheel (⚙)** on the `S200 TDB Boards` line item (not the `+ Add Entry` button — that creates a second integration instance)
4. Select **Add Device** → choose the board from the discovered list → set a name and webhook ID → Submit
5. All sensor entities and the RGB light entity appear automatically — no manual YAML

> **Note:** The `+ Add Entry` button at the bottom of the Integrations page adds a new independent instance of the whole integration (a second WebSocket connection to a second bridge). This would only be relevant if you had a **second GL-S200** on a separate Thread network, each running its own `s200-bridge` instance on a different port. In a single-S200 setup there is no use for it — ignore it and always use the **cog wheel → Configure → Add Device** path to add boards to the existing integration.

---

### Step 12: TubesZB Z-Wave PoE Kit + Z-Wave JS UI

Adds Z-Wave support using a **TubesZB Z-Wave PoE Kit** (with Zooz ZAC93 800-series Long Range module). Connects over PoE Ethernet — same pattern as the Zigbee coordinator (no USB passthrough).

```
HA (Z-Wave integration)
     │ WebSocket (ws://localhost:3000)
     ▼
Z-Wave JS UI (Docker, host network)
     │ TCP serial (tcp://ZWAVE_COORDINATOR_IP:6638)
     ▼
TubesZB Z-Wave PoE Kit (ESP32-PoE + Zooz ZAC93)
     │ Z-Wave radio (908.42 MHz, 800-series Long Range)
     ▼
Z-Wave devices
```

#### Container

| Setting | Value |
|---------|-------|
| Container name | `zwave-js-ui` |
| Image | `zwavejs/zwave-js-ui:latest` |
| Network | `host` (matches HA, enables `ws://localhost:3000`) |
| Web UI Port | 8091 |
| WebSocket Port | 3000 |
| Config volume | `/volume1/docker/configs/zwavejsui:/usr/src/app/store` |
| Session secret | `SESSION_SECRET=<openssl rand -hex 32>` |

> **No `devices:` section needed** — the Z-Wave radio is accessed over TCP, not USB.

#### Setup

1. Connect the TubesZB kit to a PoE Ethernet port
2. Find IP, set DHCP reservation. ESPHome web UI loads at `http://ZWAVE_COORDINATOR_IP` (HTTP only)
3. Deploy the container:
   ```bash
   sudo mkdir -p /volume1/docker/configs/zwavejsui
   cd /volume1/docker/compose && sudo docker compose up -d zwave-js-ui
   ```
4. Open Z-Wave JS UI at `http://YOUR_NAS_IP:8091`
5. **Settings → General** → enable **WS Server** (port 3000, leave host blank)
6. **Settings → Z-Wave** → Serial Port: `tcp://ZWAVE_COORDINATOR_IP:6638`
7. Generate all **six** security keys (S2 Access Control, S2 Authenticated, S2 Unauthenticated, S0 Legacy, + two Long Range variants). **Save them in your password manager.**
8. Click Save

#### Connect HA

1. **Settings → Devices & Services → Add Integration → Z-Wave**
2. Uncheck "Use the Z-Wave Supervisor add-on"
3. WebSocket URL: `ws://localhost:3000`

#### NPM Proxy (optional)

`zwave.yourdomain.com` → `YOUR_NAS_IP:8091` (websockets ON, Force SSL)

Z-Wave JS UI sends no `X-Frame-Options` headers — it can be embedded as an iframe sidebar panel.

#### Important Notes

- **Register your Zooz ZAC93** at [getzooz.com/register](https://getzooz.com/register) within 30 days for a 5-year warranty + firmware access
- **ESPHome entities** from the TubesZB gateway should be **ignored/disabled** in HA — toggling them could reset the Z-Wave module

---

## Network Infrastructure — UDM-SE + USW Flex 2.5G

### The Problem — UDM-SE Internal Switch Limitations

The **UniFi Dream Machine SE** has a built-in 8-port switch, but it has two critical limitations for a homelab with PoE-powered IoT coordinators and SBCs:

1. **1 Gbps backplane** — The internal switch ports share a 1 Gbps backplane to the router core. With multiple active PoE devices, throughput bottlenecks appear under load.
2. **Unreliable PoE negotiation** — Sensitive devices like PoE Zigbee/Z-Wave coordinators and Thread border routers experience occasional PoE flapping and timeouts during 802.3af/at negotiation on the UDM-SE's internal switch.

### The Fix — Dedicated USW Flex 2.5G

A **USW Flex 2.5G** was added as the dedicated switch for all IoT and SBC devices. This moves high-draw and sensitive PoE gear off the UDM-SE's internal switch onto a purpose-built PoE switch with a much larger power budget.

### Physical Topology

```
Internet
  │
  ▼
UDM-SE
  │
  ├── Port 1 (10G SFP+) ──► NAS
  │                           └── 10G backbone for Docker, HA, NFS
  │
  ├── Port 9 (2.5G RJ45) ──► USW Flex 2.5G
  │                           │
  │                           ├── Port 1 ──► Odroid N2+ #1 — Network Core
  │                           ├── Port 2 ──► Odroid N2+ #2 — Media Server
  │                           ├── Port 3 ──► Zigbee Coordinator    [100M FE]
  │                           ├── Port 4 ──► Z-Wave Coordinator    [100M FE]
  │                           └── Port 5 ──► Thread Border Router  [100M FE]
  │
  └── Remaining ports ──► APs, other LAN devices
```

### Speed Tiers

| Connection | Speed | Devices | Why |
|-----------|-------|---------|-----|
| UDM-SE → NAS | 10G SFP+ | NAS | Maximum throughput for Docker pulls, NFS media, backups |
| UDM-SE → USW Flex | 2.5G RJ45 | Uplink | Aggregate headroom for all downstream devices |
| USW Flex → Odroids | 1G RJ45 | Odroid N2+ #1, #2 | Full line rate — Docker, Jellyfin streaming, DNS |
| USW Flex → IoT | 100M FE | Zigbee, Z-Wave, Thread coordinators | Hard-coded to 100 Mbps Fast Ethernet (see below) |

### IoT Device Optimization — 100 Mbps + STP Disabled

The three IoT coordinators (Zigbee, Z-Wave, Thread) are hard-coded to **100 Mbps Full Duplex (Amber LED)** with **STP disabled** on their switch ports:

| Setting | Value | Why |
|---------|-------|-----|
| Link speed | 100 Mbps FE (forced) | These devices have 100M NICs — auto-negotiation to 1G causes link flapping |
| STP | Disabled | Prevents Spanning Tree Protocol handshake timeouts that cause 30-second delays on link-up |
| PoE | 802.3af (15.4W) | Standard PoE — all three devices draw <5W each |

**How to configure in UniFi:**
1. UniFi OS → **Network → Devices → USW Flex 2.5G → Ports**
2. Select each IoT port
3. **Port Profile** → Edit → Link Speed: **100 Mbps FE**
4. **STP** → Disable (per-port toggle)

### Result

| Tier | Speed | What's on it |
|------|-------|-------------|
| Backbone | 10G SFP+ | NAS ↔ UDM-SE (Docker, NFS, all traffic) |
| Aggregate | 2.5G RJ45 | UDM-SE ↔ USW Flex uplink |
| Compute | 1G RJ45 | Odroids (DNS, media, monitoring) |
| IoT | 100M FE | Zigbee, Z-Wave, Thread coordinators (stable, no flapping) |

> The network is now running at its theoretical peak: 10G backbone, 2.5G aggregate to the switch, stable 1G for SBCs, and locked 100M for IoT controllers that no longer flap or time out during PoE/STP negotiation.

---

## Odroid N2+ SBC Deployment

Two **Hardkernel Odroid N2+** single-board computers serve as dedicated Docker hosts, offloading network and media services from the NAS.

### Why Separate SBCs

- NAS stays focused on home automation
- Isolated failure domains — DNS going down doesn't take down HA
- Docker storage on SD cards — keeps Docker I/O off boot media

### Hardware

| Detail       | Value                                       |
|--------------|---------------------------------------------|
| Board        | Hardkernel Odroid N2+ (aarch64)             |
| OS           | Ubuntu Server 24.04 LTS (Noble)             |
| Boot media   | 64GB eMMC module                            |
| Docker media | 128GB Samsung Pro Endurance microSD (ext4)  |

### Docker Storage

Both Odroids use the same `daemon.json` (see [`odroid/daemon.json`](odroid/daemon.json)):

```json
{
  "data-root": "/mnt/docker",
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "10m",
    "max-file": "3"
  }
}
```

SD card mounted via fstab:
```
UUID=<sd-card-uuid> /mnt/docker ext4 defaults,noatime 0 2
```

### Odroid #1 — Network Core

See [`odroid/docker-compose.network.yml`](odroid/docker-compose.network.yml)

| Service        | Port(s)              | Notes                          |
|----------------|----------------------|---------------------------------|
| AdGuard Home   | 53 (DNS), 8053 (UI)  | Disable `systemd-resolved` first |
| Grist          | 8484                 |                                 |
| Vaultwarden    | 8001 (HTTPS)         | Self-signed cert via `ROCKET_TLS` |
| Beszel Hub     | 8090                 |                                 |
| Beszel Agent   | 45876 (host network) |                                 |
| Portainer      | 9443 (HTTPS)         |                                 |

### Odroid #2 — Media Server

See [`odroid/docker-compose.media.yml`](odroid/docker-compose.media.yml)

| Service        | Port(s)              | Notes                          |
|----------------|----------------------|---------------------------------|
| Jellyfin       | 8096                 | Media via NFS from NAS          |
| Beszel Agent   | 45876 (host network) |                                 |
| Portainer      | 9443 (HTTPS)         |                                 |

#### NFS Media Mount (on Odroid #2)

```bash
# NAS /etc/exports:
/volume1/media ODROID2_IP(ro,sync,no_subtree_check,no_root_squash)

# Odroid #2 /etc/fstab:
NAS_IP:/volume1/media /mnt/nas_media nfs ro,soft,timeo=30,retrans=3 0 0
```

---

## HA Sidebar Integration

Services are accessible from the HA sidebar via `panel_custom`. Two reusable JS panel components:

| Service           | Panel Type | Why not iframe?                      |
|-------------------|-----------|---------------------------------------|
| Z-Wave JS UI      | iframe    | Works — no blocking headers           |
| Grist             | iframe    | Works — no blocking headers           |
| Beszel            | new tab   | `X-Frame-Options: SAMEORIGIN`        |
| AdGuard Home      | new tab   | Login cookies don't persist in iframe |
| Vaultwarden       | new tab   | Blocks iframing                      |
| Portainer         | new tab   | Blocks iframing                      |
| Jellyfin          | new tab   | Blocks iframing                      |

Services that send `X-Frame-Options` or have login cookie issues **must** use the new-tab panel.

---

## Verification

```bash
docker --version                                          # Docker version 29.x
docker compose version                                    # Docker Compose version v5.x
sudo systemctl is-active docker                           # active
sudo docker ps                                            # all containers running
sudo docker info | grep -E 'Storage Driver|Docker Root'   # btrfs, /volume1/@docker
curl -s http://localhost:8091/health                      # Z-Wave JS UI healthy
```

---

## Troubleshooting Quick Reference

| Problem | Solution |
|---------|----------|
| Docker `mount: invalid argument` | Root is overlay-on-overlay. Use `btrfs` storage driver on a btrfs volume |
| `overlay2` fails on any volume | Expected on this NAS — overlay-on-overlay is illegal. Use `btrfs` driver |
| Z-Wave JS UI WS port 3000 not listening | Enable WS Server in Settings → General (disabled by default) |
| ZHA can't connect to Zigbee coordinator | Verify coordinator IP, check port 6638 is open, check radio type (EZSP vs ZNP) |
| HA returns 400 through reverse proxy | Add `http: trusted_proxies` to `configuration.yaml` |
| `panel_iframe` not found in HA 2026.x | Removed — use `panel_custom` with `iframe-panel.js` or `newtab-panel.js` |
| VS Code can't write files | Overlay root is root-owned. `sudo chown` a directory on `/volume1/` |
| Port 53 in use (AdGuard on Odroid) | Disable `systemd-resolved`: `sudo systemctl disable --now systemd-resolved` |
| Matter integration can't connect | Verify `matter-server` container is running, check `ws://localhost:5580/ws` |
| TubesZB ESPHome UI only serves HTTP | Expected — ESP32-PoE firmware serves HTTP only, not HTTPS |

---

## License

This project is provided as-is for reference purposes. Use at your own risk.
