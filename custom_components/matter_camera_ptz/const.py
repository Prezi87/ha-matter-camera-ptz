"""Constants for Matter Camera PTZ."""

DOMAIN = "matter_camera_ptz"
CONF_URL = "url"
CONF_NODE_ID = "node_id"
CONF_ENDPOINT_ID = "endpoint_id"
CONF_CAMERA_NAME = "camera_name"
CONF_PAN_STEP = "pan_step"
CONF_TILT_STEP = "tilt_step"
CONF_ZOOM_STEP = "zoom_step"
CONF_COOLDOWN = "cooldown"

DEFAULT_URL = "ws://127.0.0.1:5580/ws"
DEFAULT_PAN_STEP = 30
DEFAULT_TILT_STEP = 12
DEFAULT_ZOOM_STEP = 5
DEFAULT_COOLDOWN = 3.2

PTZ_CLUSTER_ID = 1362
PTZ_COMMAND = "mptzRelativeMove"
DIRECTIONS = ("left", "right", "up", "down", "zoom_in", "zoom_out")
DIRECTION_ARGUMENT = {
    "left": ("panDelta", -1),
    "right": ("panDelta", 1),
    "up": ("tiltDelta", 1),
    "down": ("tiltDelta", -1),
    "zoom_in": ("zoomDelta", 1),
    "zoom_out": ("zoomDelta", -1),
}
