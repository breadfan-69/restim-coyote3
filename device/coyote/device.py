"""Backward-compatibility shim - real code lives in coyote_plugin.device.device"""
from coyote_plugin.device.device import *  # noqa: F401,F403
from coyote_plugin.device.device import CoyoteDevice  # noqa: F401
# Re-export types that consumers import from this module
from coyote_plugin.device.types import CoyoteParams, CoyotePulse, CoyotePulses, CoyoteStrengths  # noqa: F401

