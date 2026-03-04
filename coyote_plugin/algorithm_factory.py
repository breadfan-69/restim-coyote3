from coyote_plugin.device.algorithm import CoyoteAlgorithm, CoyoteDigletAlgorithm
from qt_ui.device_wizard.axes import AxisEnum
from qt_ui.device_wizard.enums import DeviceType
import qt_ui.settings as settings
from stim_math.audio_gen.params import SafetyParams, ThreephasePositionParams, VolumeParams

from coyote_plugin.params import CoyoteAlgorithmParams, CoyoteChannelParams


def _build_common_params(factory, use_threephase_calibration=False):
    if use_threephase_calibration:
        transform_params = factory.mainwindow.tab_threephase.transform_params
        calibrate_params = factory.mainwindow.tab_threephase.calibrate_params
    else:
        transform_params = factory.mainwindow.tab_coyote_calibration.transform_params
        calibrate_params = factory.mainwindow.tab_coyote_calibration.calibrate_params

    return CoyoteAlgorithmParams(
        position=ThreephasePositionParams(
            factory.get_axis_alpha(),
            factory.get_axis_beta(),
        ),
        transform=transform_params,
        calibrate=calibrate_params,
        volume=VolumeParams(
            api=factory.get_axis_volume_api(),
            master=factory.get_axis_volume_master(),
            inactivity=factory.get_axis_volume_inactivity(),
            external=factory.get_axis_volume_external(),
        ),
        carrier_frequency=factory.get_axis_pulse_carrier_frequency(),
        pulse_frequency=factory.get_axis_pulse_frequency(),
        pulse_width=factory.get_axis_pulse_width(),
        pulse_interval_random=factory.get_axis_pulse_interval_random(),
        pulse_rise_time=factory.get_axis_pulse_rise_time(),
        max_intensity_change_per_pulse=settings.coyote_max_intensity_change_per_pulse,
        channel_a=CoyoteChannelParams(
            minimum_frequency=settings.coyote_channel_a_freq_min,
            maximum_frequency=settings.coyote_channel_a_freq_max,
            maximum_strength=settings.coyote_channel_a_strength_max,
            vibration=factory.get_axis_vib1_all(),
            pulse_frequency=factory.get_axis_coyote_channel_a_pulse_frequency(),
        ),
        channel_b=CoyoteChannelParams(
            minimum_frequency=settings.coyote_channel_b_freq_min,
            maximum_frequency=settings.coyote_channel_b_freq_max,
            maximum_strength=settings.coyote_channel_b_strength_max,
            vibration=factory.get_axis_vib2_all(),
            pulse_frequency=factory.get_axis_coyote_channel_b_pulse_frequency(),
        ),
    )


def _create_coyote_two_channel(factory, device):
    carrier_freq_limits = factory.kit.limits_for_axis(AxisEnum.CARRIER_FREQUENCY)
    pulse_freq_limits = factory.kit.limits_for_axis(AxisEnum.PULSE_FREQUENCY)
    pulse_width_limits = factory.kit.limits_for_axis(AxisEnum.PULSE_WIDTH)
    pulse_rise_time_limits = factory.kit.limits_for_axis(AxisEnum.PULSE_RISE_TIME)

    return CoyoteAlgorithm(
        factory.media_sync,
        _build_common_params(factory, use_threephase_calibration=False),
        safety_limits=SafetyParams(
            device.min_frequency,
            device.max_frequency,
        ),
        carrier_freq_limits=carrier_freq_limits,
        pulse_freq_limits=pulse_freq_limits,
        pulse_width_limits=pulse_width_limits,
        pulse_rise_time_limits=pulse_rise_time_limits,
        is_three_phase=False,
    )


def _create_coyote_diglet(factory, device):
    carrier_freq_limits = factory.kit.limits_for_axis(AxisEnum.CARRIER_FREQUENCY)
    pulse_freq_limits = factory.kit.limits_for_axis(AxisEnum.PULSE_FREQUENCY)
    pulse_width_limits = factory.kit.limits_for_axis(AxisEnum.PULSE_WIDTH)
    pulse_rise_time_limits = factory.kit.limits_for_axis(AxisEnum.PULSE_RISE_TIME)

    return CoyoteDigletAlgorithm(
        factory.media_sync,
        _build_common_params(factory, use_threephase_calibration=True),
        safety_limits=SafetyParams(
            device.min_frequency,
            device.max_frequency,
        ),
        carrier_freq_limits=carrier_freq_limits,
        pulse_freq_limits=pulse_freq_limits,
        pulse_width_limits=pulse_width_limits,
        pulse_rise_time_limits=pulse_rise_time_limits,
        is_three_phase=factory.mainwindow.wizard.page_coyote_waveform_select.is_three_phase(),
    )


def register_coyote_algorithm_factories(register_factory):
    register_factory(DeviceType.COYOTE_TWO_CHANNEL, _create_coyote_two_channel)
    register_factory(DeviceType.COYOTE_THREE_PHASE, _create_coyote_diglet)
