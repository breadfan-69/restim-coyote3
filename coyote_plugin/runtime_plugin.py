import asyncio
import logging

from PySide6.QtWidgets import QLabel

import qt_ui.settings
from coyote_plugin.device.constants import DEVICE_NAME
from coyote_plugin.device.device import CoyoteDevice, CoyoteParams
from qt_ui.device_wizard.axes import AxisEnum
from qt_ui.device_wizard.enums import DeviceType

logger = logging.getLogger('restim.main')


class CoyoteDevicePlugin:
    def __init__(self):
        self._mode_label = None

    @staticmethod
    def _is_coyote_device(device_type):
        return device_type in (DeviceType.COYOTE_THREE_PHASE, DeviceType.COYOTE_TWO_CHANNEL)

    @staticmethod
    def _set_tab_visible(mainwindow, widget, state):
        index = mainwindow.tabWidget.indexOf(widget)
        if index < 0:
            return
        mainwindow.tabWidget.setTabVisible(index, state)
        mainwindow.tabWidget.setTabEnabled(index, state)

    def _ensure_mode_label(self, mainwindow):
        if self._mode_label is not None:
            return
        self._mode_label = QLabel("Mode: Two-Channel")
        self._mode_label.setStyleSheet("color: #8B3A3A; font-weight: bold; padding: 5px 15px;")
        mainwindow.statusBar().addPermanentWidget(self._mode_label)
        self._mode_label.hide()

    @staticmethod
    def _disconnect_coyote_device(mainwindow):
        coyote_device = None
        if isinstance(mainwindow.output_device, CoyoteDevice):
            coyote_device = mainwindow.output_device
        elif hasattr(mainwindow, 'tab_coyote') and isinstance(getattr(mainwindow.tab_coyote, 'device', None), CoyoteDevice):
            coyote_device = mainwindow.tab_coyote.device

        if coyote_device is None:
            return

        coyote_device.stop_updates()
        if coyote_device._event_loop:
            asyncio.run_coroutine_threadsafe(coyote_device.disconnect(), coyote_device._event_loop)
        if hasattr(mainwindow, 'tab_coyote'):
            mainwindow.tab_coyote.cleanup()
        if mainwindow.output_device is coyote_device:
            mainwindow.output_device = None

    def extend_tcode_axis_controller_map(self, mainwindow, mapping):
        if not hasattr(mainwindow, 'tab_coyote'):
            return
        mapping[mainwindow.tab_coyote.get_shared_pulse_frequency_axis()] = [
            mainwindow.tab_coyote.get_channel_a_pulse_frequency_controller(),
            mainwindow.tab_coyote.get_channel_b_pulse_frequency_controller(),
        ]

    def on_funscript_mapping_changed(self, mainwindow, algorithm_factory):
        if not hasattr(mainwindow, 'tab_coyote') or mainwindow.tab_coyote.device is None:
            return
        has_pulse_frequency_funscript = (
            not mainwindow.page_media.is_internal()
            and algorithm_factory.get_axis_from_script_mapping(AxisEnum.PULSE_FREQUENCY) is not None
        )
        mainwindow.tab_coyote.set_pulse_frequency_from_funscript(has_pulse_frequency_funscript)

    def on_device_changed(self, mainwindow, config):
        self._ensure_mode_label(mainwindow)

        if self._is_coyote_device(config.device_type):
            self._set_tab_visible(mainwindow, mainwindow.tab_coyote, True)
            self._set_tab_visible(mainwindow, mainwindow.tab_vibrate, False)
            self._set_tab_visible(mainwindow, mainwindow.tab_pulse_settings, False)
            self._set_tab_visible(mainwindow, mainwindow.tab_details, False)

            if config.device_type == DeviceType.COYOTE_THREE_PHASE:
                self._set_tab_visible(mainwindow, mainwindow.tab_threephase, True)
                self._set_tab_visible(mainwindow, mainwindow.tab_coyote_calibration, False)
                mode_name = "Three-Phase"
            else:
                self._set_tab_visible(mainwindow, mainwindow.tab_threephase, False)
                self._set_tab_visible(mainwindow, mainwindow.tab_coyote_calibration, True)
                mode_name = "Two-Channel"

            mainwindow.tab_carrier.set_safety_limits(1, 200)
            mainwindow.tab_pulse_settings.set_safety_limits(1, 200)
            mainwindow.tcode_command_router.set_pulse_frequency_axis(mainwindow.tab_coyote.get_shared_pulse_frequency_axis())
            mainwindow.tcode_command_router.set_carrier_limits(1, 200)
            mainwindow.tcode_command_router.set_allowed_axes({
                AxisEnum.POSITION_ALPHA,
                AxisEnum.POSITION_BETA,
                AxisEnum.VOLUME_API,
                AxisEnum.PULSE_FREQUENCY,
            })
            mainwindow.tcode_command_router.set_pulse_frequency_limits(1, 100)

            if self._mode_label is not None:
                self._mode_label.setText(f"Mode: {mode_name}")
                self._mode_label.show()

            if mainwindow.output_device is not None and not isinstance(mainwindow.output_device, CoyoteDevice):
                try:
                    mainwindow.output_device.stop()
                except Exception:
                    pass
                mainwindow.output_device = None

            if not isinstance(mainwindow.output_device, CoyoteDevice):
                params = CoyoteParams(
                    channel_a_limit=qt_ui.settings.coyote_channel_a_limit.get(),
                    channel_b_limit=qt_ui.settings.coyote_channel_b_limit.get(),
                    channel_a_freq_balance=qt_ui.settings.coyote_channel_a_freq_balance.get(),
                    channel_b_freq_balance=qt_ui.settings.coyote_channel_b_freq_balance.get(),
                    channel_a_intensity_balance=qt_ui.settings.coyote_channel_a_intensity_balance.get(),
                    channel_b_intensity_balance=qt_ui.settings.coyote_channel_b_intensity_balance.get(),
                )
                mainwindow.output_device = CoyoteDevice(DEVICE_NAME, params)
                mainwindow.tab_coyote.setup_device(mainwindow.output_device)

            logger.info("Coyote mode label shown: %s", mode_name)
            return

        if self._mode_label is not None:
            self._mode_label.hide()
        self._disconnect_coyote_device(mainwindow)

    def before_start(self, mainwindow, device):
        if not self._is_coyote_device(device.device_type):
            self._disconnect_coyote_device(mainwindow)

    def on_start(self, mainwindow, device, algorithm):
        if not self._is_coyote_device(device.device_type):
            return False

        if not mainwindow.output_device:
            logger.warning("Coyote device is no longer initialized")
            return True

        mainwindow.output_device.start_updates(algorithm)
        mainwindow.playstate = type(mainwindow.playstate).PLAYING
        mainwindow.tab_volume.set_play_state(mainwindow.playstate)
        mainwindow.refresh_play_button_icon()
        return True

    def on_stop(self, mainwindow, new_playstate):
        if isinstance(mainwindow.output_device, CoyoteDevice):
            mainwindow.output_device.stop_updates()
            mainwindow.playstate = new_playstate
            mainwindow.tab_volume.set_play_state(mainwindow.playstate)
            mainwindow.refresh_play_button_icon()
            return True
        return False

    def on_close(self, mainwindow):
        self._disconnect_coyote_device(mainwindow)
