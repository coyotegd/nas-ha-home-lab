"""Constants for the GL-S200 TDB Boards integration."""

DOMAIN = "s200_tdb"
DEFAULT_HOST = "localhost"
DEFAULT_PORT = 8765
CONF_DEVICES = "devices"

# Legacy devices for v1→v2 migration only
LEGACY_DEVICES = {
    "9483c4bd45279077": {"name": "TDB 1", "webhook_motion": "tdb1-pir-motion"},
    "9483c48ade56c6ca": {"name": "TDB 2", "webhook_motion": "tdb2-pir-motion"},
}
