from __future__ import annotations

import logging
import math
import random
from dataclasses import dataclass
from typing import Tuple

from device.coyote.common import clamp, normalize
from device.coyote.config import PulseTuning
from device.coyote.constants import (
    HARDWARE_MAX_FREQ_HZ,
    HARDWARE_MIN_FREQ_HZ,
    MAX_PULSE_DURATION_MS,
    MIN_PULSE_DURATION_MS,
)
from device.coyote.types import CoyotePulse
from stim_math.audio_gen.params import CoyoteAlgorithmParams, CoyoteChannelParams

logger = logging.getLogger("restim.coyote")


@dataclass
class TextureInfo:
    offset_ms: float
    mode: str
    headroom_up_ms: float
    headroom_down_ms: float


@dataclass
class PulseDebug:
    sequence_index: int
    raw_frequency_hz: float
    normalised_frequency: float
    mapped_frequency_hz: float
    frequency_limits: Tuple[float, float]
    base_duration_ms: float
    duration_limits: Tuple[int, int]
    jitter_fraction: float
    jitter_factor: float
    width_normalised: float
    texture_mode: str
    texture_headroom_up_ms: float
    texture_headroom_down_ms: float
    texture_applied_ms: float
    desired_duration_ms: float
    residual_ms: float


class PulseGenerator:
    """Builds hardware-friendly pulses for a single Coyote channel."""

    def __init__(
        self,
        name: str,
        params: CoyoteAlgorithmParams,
        channel_params: CoyoteChannelParams,
        carrier_freq_limits: Tuple[float, float],
        pulse_freq_limits: Tuple[float, float],
        pulse_width_limits: Tuple[float, float],
        tuning: PulseTuning,
    ) -> None:
        self.name = name
        self.params = params
        self.channel_params = channel_params
        self._carrier_limits = carrier_freq_limits
        self._pulse_freq_limits = pulse_freq_limits
        self._pulse_width_limits = pulse_width_limits
        self._tuning = tuning

        self._phase = 0.0
        self._residual_ms = 0.0

    @property
    def carrier_limits(self) -> Tuple[float, float]:
        return self._carrier_limits

    def advance_phase(self, texture_speed_hz: float, delta_time_s: float) -> None:
        if delta_time_s <= 0 or texture_speed_hz <= 0:
            return
        phase_delta = delta_time_s * texture_speed_hz * 2 * math.pi
        self._phase = (self._phase + phase_delta) % (2 * math.pi)

    def create_pulse(self, time_s: float, intensity: int, sequence_index: int) -> Tuple[CoyotePulse, PulseDebug]:

        # Determine if using funscript or spinbox by checking axis type
        # WriteProtectedAxis = funscript, DynamicSpinboxAxis = internal spinbox
        from stim_math.axis import WriteProtectedAxis
        using_funscript = (self.channel_params.pulse_frequency is not None and 
                          isinstance(self.channel_params.pulse_frequency, WriteProtectedAxis))
        
        # Get the raw value (0-100 for funscript, or frequency in Hz for spinbox)
        # Always use channel_params.pulse_frequency if available (for both funscript and internal spinbox)
        # Fall back to params.pulse_frequency only if channel-specific is not set
        if self.channel_params.pulse_frequency is not None:
            raw_value = float(self.channel_params.pulse_frequency.interpolate(time_s))
        else:
            raw_value = float(self.params.pulse_frequency.interpolate(time_s))

        # Get min/max frequency from channel config (in Hz)
        user_freq_min = self.channel_params.minimum_frequency.get()
        user_freq_max = self.channel_params.maximum_frequency.get()
        
        # Map to frequency (Hz)
        if using_funscript:
            # Funscript values: 0-100 → normalize to 0-1 → map to [user_freq_min, user_freq_max] Hz
            normalized = raw_value / 100.0
            requested_frequency = user_freq_min + (normalized * (user_freq_max - user_freq_min))
        else:
            # Internal media player: spinbox provides frequency in Hz, clamp to [user_freq_min, user_freq_max]
            requested_frequency = clamp(raw_value, user_freq_min, user_freq_max)

        # Clamp to hardware limits (5-240ms = 4.17-200 Hz)
        requested_frequency = max(1, requested_frequency)
        base_duration = 1000.0 / requested_frequency
        base_duration = clamp(base_duration, MIN_PULSE_DURATION_MS, MAX_PULSE_DURATION_MS)
        # Convert duration back to frequency for display
        display_frequency = int(max(1, round(1000.0 / base_duration)))
        final_intensity = int(clamp(intensity, 0, 100))

        debug = PulseDebug(
            sequence_index=sequence_index,
            raw_frequency_hz=display_frequency,
            normalised_frequency=1.0,
            mapped_frequency_hz=display_frequency,
            frequency_limits=(user_freq_min, user_freq_max),
            base_duration_ms=base_duration,
            duration_limits=(MIN_PULSE_DURATION_MS, MAX_PULSE_DURATION_MS),
            jitter_fraction=0.0,
            jitter_factor=0.0,
            width_normalised=0.0,
            texture_mode='none',
            texture_headroom_up_ms=0.0,
            texture_headroom_down_ms=0.0,
            texture_applied_ms=0.0,
            desired_duration_ms=base_duration,
            residual_ms=0.0,
        )

        return CoyotePulse(duration=int(base_duration), intensity=final_intensity, frequency=display_frequency), debug

    def _channel_frequency_window(self) -> Tuple[float, float]:
        minimum = max(float(self.channel_params.minimum_frequency.get()), HARDWARE_MIN_FREQ_HZ)
        maximum = min(float(self.channel_params.maximum_frequency.get()), HARDWARE_MAX_FREQ_HZ)
        if minimum >= maximum:
            return HARDWARE_MIN_FREQ_HZ, HARDWARE_MAX_FREQ_HZ
        return minimum, maximum

    def _pulse_width_normalised(self, time_s: float) -> float:
        # Deprecated - pulse width no longer used
        return 0.0

    def _texture_offset(
        self,
        base_duration: float,
        width_norm: float,
        min_freq: float,
        max_freq: float,
    ) -> TextureInfo:
        # Deprecated - texture no longer used, always return zero offset
        return TextureInfo(offset_ms=0.0, mode="none", headroom_up_ms=0.0, headroom_down_ms=0.0)

    def _apply_residual(self, desired_ms: float) -> Tuple[int, float]:
        accum = desired_ms + self._residual_ms
        rounded = int(round(accum))
        residual = accum - rounded
        bound = self._tuning.residual_bound
        residual = clamp(residual, -bound, bound)
        self._residual_ms = residual
        return max(1, rounded), residual

    def _duration_limits(self, min_freq: float, max_freq: float) -> Tuple[int, int]:
        minimum = max(MIN_PULSE_DURATION_MS, int(round(1000.0 / max_freq)))
        maximum = min(MAX_PULSE_DURATION_MS, int(round(1000.0 / min_freq)))
        if minimum > maximum:
            return MIN_PULSE_DURATION_MS, MAX_PULSE_DURATION_MS
        return minimum, maximum

    def _clamp_duration(self, duration_ms: int, limits: Tuple[int, int]) -> Tuple[int, bool]:
        low, high = limits
        clamped_duration = int(clamp(duration_ms, low, high))
        clamped = clamped_duration != duration_ms
        if clamped:
            self._residual_ms = 0.0
        return clamped_duration, clamped
