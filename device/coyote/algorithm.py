"""Backward-compatibility shim - real code lives in coyote_plugin.device.algorithm"""
from coyote_plugin.device.algorithm import *  # noqa: F401,F403
from coyote_plugin.device.algorithm import CoyoteAlgorithm, CoyoteDigletAlgorithm, ChannelPipeline  # noqa: F401

