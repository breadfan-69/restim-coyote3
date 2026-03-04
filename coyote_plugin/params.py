"""
Coyote-specific algorithm parameter dataclasses.

Extracted from stim_math/audio_gen/params.py to keep the upstream file clean.
"""
from dataclasses import dataclass

from stim_math.axis import AbstractAxis
from stim_math.audio_gen.params import (
    ThreephasePositionParams,
    ThreephasePositionTransformParams,
    ThreephaseCalibrationParams,
    VibrationParams,
    VolumeParams,
)
from qt_ui import settings


@dataclass
class CoyoteChannelParams:
    minimum_frequency: settings.Setting
    maximum_frequency: settings.Setting
    maximum_strength: settings.Setting
    vibration: VibrationParams  # TODO: modulate channel A/B freq
    pulse_frequency: AbstractAxis = None  # Optional per-channel pulse frequency (if None, uses global)


@dataclass
class CoyoteAlgorithmParams:
    position: ThreephasePositionParams
    transform: ThreephasePositionTransformParams
    calibrate: ThreephaseCalibrationParams
    volume: VolumeParams
    carrier_frequency: AbstractAxis  # Hz
    pulse_frequency: AbstractAxis    # Hz
    pulse_width: AbstractAxis        # carrier cycles
    pulse_interval_random: AbstractAxis
    pulse_rise_time: AbstractAxis
    max_intensity_change_per_pulse: settings.Setting

    channel_a: CoyoteChannelParams
    channel_b: CoyoteChannelParams
