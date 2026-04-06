#!/usr/bin/env python3
"""Control TDB dev board LEDs via CoAP through S200 SSH.

Usage:
  s200_tdb_led.py <dev_addr> on
  s200_tdb_led.py <dev_addr> off
  s200_tdb_led.py <dev_addr> color <r> <g> <b>
  s200_tdb_led.py <dev_addr> level <0-255>
  s200_tdb_led.py <dev_addr> status

dev_addr = TDB mesh-local IPv6 address (fd4d:...)
Output: JSON from CoAP response

Requires SSH key-based auth to S200 (no password prompt).
Set up with: ssh-copy-id root@YOUR_S200_IP
"""
import json
import subprocess
import sys

# ── Configuration (replace with your S200 IP) ──
S200_IP = "YOUR_S200_IP"
SSH_OPTS = ["-o", "StrictHostKeyChecking=no", "-o", "ConnectTimeout=5", "-o", "BatchMode=yes"]


def ssh_coap(cmd_json, dev_addr):
    """Send a CoAP PUT command to the TDB via SSH to S200."""
    coap_cmd = f"coap_cli -N -e '{cmd_json}' -m put coap://[{dev_addr}]/cmd"
    result = subprocess.run(
        ["ssh"] + SSH_OPTS + [f"root@{S200_IP}", coap_cmd],
        capture_output=True, text=True, timeout=15
    )
    out = result.stdout.strip()
    if out:
        try:
            return json.loads(out)
        except json.JSONDecodeError:
            return {"raw": out}
    return {"err_code": result.returncode, "stderr": result.stderr.strip()}


def main():
    if len(sys.argv) < 3:
        print(json.dumps({"error": "Usage: s200_tdb_led.py <dev_addr> on|off|color R G B|level N|status"}))
        sys.exit(1)

    dev_addr = sys.argv[1]
    action = sys.argv[2]

    if action == "on":
        r = ssh_coap('{"cmd":"onoff","obj":"all","val":1}', dev_addr)
    elif action == "off":
        r = ssh_coap('{"cmd":"onoff","obj":"all","val":0}', dev_addr)
    elif action == "color" and len(sys.argv) == 6:
        red, green, blue = int(sys.argv[3]), int(sys.argv[4]), int(sys.argv[5])
        red = max(0, min(255, red))
        green = max(0, min(255, green))
        blue = max(0, min(255, blue))
        r = ssh_coap(
            f'{{"cmd":"change_color","obj":"all","r":{red},"g":{green},"b":{blue}}}',
            dev_addr,
        )
    elif action == "level" and len(sys.argv) == 4:
        val = int(sys.argv[3])
        val = max(0, min(255, val))
        r = ssh_coap(
            f'{{"cmd":"set_level","obj":"all","val":{val}}}',
            dev_addr,
        )
    elif action == "status":
        r = ssh_coap('{"cmd":"get_led_status"}', dev_addr)
    else:
        print(json.dumps({"error": f"Unknown action: {action}"}))
        sys.exit(1)

    print(json.dumps(r))


if __name__ == "__main__":
    main()
