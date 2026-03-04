"""Backward-compatibility shim - real code lives in coyote_plugin.device.config"""
from coyote_plugin.device.config import *  # noqa: F401,F403
from coyote_plugin.device.config import PulseTuning, load_pulse_tuning  # noqa: F401

