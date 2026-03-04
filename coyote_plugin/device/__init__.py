"""
Coyote device implementation — BLE protocol, algorithm, pulse generation.

Canonical import path:  ``from coyote_plugin.device.<module> import <name>``

Backward-compatible shims in ``device/coyote/`` re-export everything from here
so existing ``from device.coyote.<module> import …`` still works.
"""

# Re-export the most commonly used names at package level for convenience
from coyote_plugin.device.types import (
    CoyoteParams,
    CoyotePulse,
    CoyotePulses,
    CoyoteStrengths,
    ConnectionStage,
)
from coyote_plugin.device.constants import DEVICE_NAME
from coyote_plugin.device.device import CoyoteDevice
from coyote_plugin.device.algorithm import CoyoteAlgorithm, CoyoteDigletAlgorithm
