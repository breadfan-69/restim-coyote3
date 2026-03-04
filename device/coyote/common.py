"""Backward-compatibility shim - real code lives in coyote_plugin.device.common"""
from coyote_plugin.device.common import *  # noqa: F401,F403
from coyote_plugin.device.common import clamp, normalize, volume_at, split_seconds  # noqa: F401

