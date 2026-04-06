#!/usr/bin/env python3
"""Fetch TDB dev board sensor data from GL-S200 via JSON-RPC.

Usage: s200_tdb_sensors.py [dev_id]
  - With dev_id: returns sensor data for that device
  - Without dev_id: returns all device data
Output: JSON

The GL-S200's JSON-RPC API requires multi-step challenge-response auth:
  1. Request challenge nonce
  2. Compute MD5 hash: md5(username:crypt_password:nonce)
  3. Login with hash → get session ID
  4. Use session ID for subsequent calls

Generate CRYPT_PW with: openssl passwd -1 -salt "YOUR_SALT" "YOUR_PASSWORD"
"""
import hashlib
import json
import ssl
import sys
import urllib.request

# ── Configuration (replace with your values) ──
S200_HOST = "YOUR_S200_IP"
S200_USER = "root"
# Pre-computed: openssl passwd -1 -salt "YOUR_SALT" "YOUR_PASSWORD"
CRYPT_PW = "$1$YOUR_SALT$YOUR_HASH"

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE


def rpc(method, params):
    req = urllib.request.Request(
        f"https://{S200_HOST}/rpc",
        data=json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode(),
        headers={"Content-Type": "application/json"},
    )
    return json.loads(urllib.request.urlopen(req, context=ctx, timeout=10).read())


def login():
    r = rpc("challenge", {"username": S200_USER})
    nonce = r["result"]["nonce"]
    h = hashlib.md5(f"{S200_USER}:{CRYPT_PW}:{nonce}".encode()).hexdigest()
    r = rpc("login", {"username": S200_USER, "hash": h})
    return r["result"]["sid"]


def main():
    sid = login()
    dev_id = sys.argv[1] if len(sys.argv) > 1 else None

    if dev_id:
        r = rpc("call", [sid, "ubus", "call", {
            "object": "otbr-gateway",
            "method": "get_device_status",
            "params": {"dev_id": dev_id},
        }])
        if "result" in r:
            d = r["result"]
            out = d.get("dev_data", {})
            out["connected"] = d.get("connected", False)
            out["dev_id"] = d.get("dev_id", "")
            print(json.dumps(out))
        else:
            print(json.dumps({"error": r.get("error", {}).get("message", "unknown")}))
    else:
        r = rpc("call", [sid, "otbr", "get_device_list", {}])
        if "result" in r:
            print(json.dumps(r["result"]))
        else:
            print(json.dumps({"error": r.get("error", {}).get("message", "unknown")}))


if __name__ == "__main__":
    main()
