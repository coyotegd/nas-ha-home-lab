"""Constants for the LD1125H Matter Radar integration."""

DOMAIN = "ld1125h_matter"

# Matter OccupancySensing cluster ID
CLUSTER_OCCUPANCY_SENSING = 0x0406  # 1030 decimal

# Vendor-specific attribute IDs (on OccupancySensing cluster, VID 0xFFF1)
# Must match the firmware in main/app_main.cpp
ATTR_DISTANCE_CM = 0xFFF10001  # read-only nullable uint16 — distance in cm
ATTR_TH1_MOV     = 0xFFF10002  # writable uint8  — motion threshold zone 1
ATTR_TH2_MOV     = 0xFFF10003  # writable uint8  — motion threshold zone 2
ATTR_TH3_MOV     = 0xFFF10004  # writable uint8  — motion threshold zone 3
ATTR_TH1_OCC     = 0xFFF10005  # writable uint8  — occupancy threshold zone 1
ATTR_TH2_OCC     = 0xFFF10006  # writable uint8  — occupancy threshold zone 2
ATTR_TH3_OCC     = 0xFFF10007  # writable uint8  — occupancy threshold zone 3
ATTR_RMAX_CM     = 0xFFF10008  # writable uint16 — max range in cm (40–1200)
ATTR_OCC_ST_MS   = 0xFFF10009  # writable uint16 — chirp interval in ms

ALL_VENDOR_ATTRS = [
    ATTR_DISTANCE_CM,
    ATTR_TH1_MOV, ATTR_TH2_MOV, ATTR_TH3_MOV,
    ATTR_TH1_OCC, ATTR_TH2_OCC, ATTR_TH3_OCC,
    ATTR_RMAX_CM, ATTR_OCC_ST_MS,
]

CONF_NODE_ID = "node_id"
CONF_ENDPOINT_ID = "endpoint_id"
