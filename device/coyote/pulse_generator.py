"""Backward-compatibility shim - real code lives in coyote_plugin.device.pulse_generator"""
from coyote_plugin.device.pulse_generator import *  # noqa: F401,F403
from coyote_plugin.device.pulse_generator import PulseGenerator, PulseDebug, TextureInfo  # noqa: F401

