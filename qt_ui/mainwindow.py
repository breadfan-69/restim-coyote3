import os
import sys
from enum import Enum
import asyncio

from PySide6 import QtGui, QtCore
from PySide6.QtCore import QTimer
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QSizePolicy, QFrame, QStyleFactory
)
import logging

# Import restim_rc to register Qt resources
import restim_rc

from net.media_source.interface import MediaConnectionState
from qt_ui.algorithm_factory import AlgorithmFactory
from qt_ui.device_wizard.axes import AxisEnum
from qt_ui.audio_write_dialog import AudioWriteDialog
from qt_ui.main_window_ui import Ui_MainWindow
import qt_ui.patterns.threephase_patterns
import qt_ui.patterns.fourphase_patterns
from device.audio.audio_stim_device import AudioStimDevice
import net.websocketserver
import net.tcpudpserver
import qt_ui.funscript_conversion_dialog
import qt_ui.simfile_conversion_dialog
import qt_ui.focstim_flash_dialog
import qt_ui.funscript_decomposition_dialog
import qt_ui.preferences_dialog
import qt_ui.about_dialog
import qt_ui.settings
import net.serialproxy
import net.buttplug_wsdm_client
from qt_ui import resources
from qt_ui.models.funscript_kit import FunscriptKitModel
from device.focstim.proto_device import FOCStimProtoDevice, LSM6DSOX_SAMPLERATE_HZ
from device.neostim.neostim_device import NeoStim
from device.coyote.device import CoyoteDevice, CoyoteParams
from device.coyote.constants import DEVICE_NAME
from qt_ui.widgets.icon_with_connection_status import IconWithConnectionStatus
from stim_math.axis import create_temporal_axis
from qt_ui.theme import apply_theme, update_graphics_views


import sounddevice as sd

from qt_ui.device_wizard.wizard import DeviceSelectionWizard
from qt_ui.device_wizard.enums import DeviceConfiguration, DeviceType, WaveformType

from qt_ui.tcode_command_router import TCodeCommandRouter

logger = logging.getLogger('restim.main')


class PlayState(Enum):
    STOPPED = 0
    PLAYING = 1
    WAITING_ON_LOAD = 2  # the audio is stopped, but is ready to be auto-started once funscripts are loaded.


class Window(QMainWindow, Ui_MainWindow):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setupUi(self)

        # Set a unique AppUserModelID for every instance to prevent taskbar stacking
        try:
            import ctypes
            import uuid
            unique_id = f"restim.stimulation.app.{uuid.uuid4()}"
            shell32 = ctypes.windll.shell32
            shell32.SetCurrentProcessExplicitAppUserModelID(unique_id)
        except Exception as e:
            logger.debug(f"Failed to set AppUserModelID: {e}")

        self.playstate = PlayState.STOPPED
        self.tab_volume.set_play_state(self.playstate)
        self.refresh_play_button_icon()

        # Offset widget toolbar action storage
        self.funscript_offset_action = None

        # set the first tab as active tab, in case we forgot to set it in designer
        self.tabWidget.setCurrentIndex(0)

        icon = QtGui.QIcon()
        icon.addPixmap(QtGui.QPixmap(resources.favicon), QtGui.QIcon.Normal, QtGui.QIcon.Off)
        self.setWindowIcon(icon)

        # Load icon theme from settings
        self._load_icon_theme()

        # TODO: credit https://glyphs.fyi/ for icons
        spacer = QWidget()
        spacer.sizePolicy()
        spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.toolBar.insertWidget(self.actionStart, spacer)
        line = QFrame()
        # line->setObjectName(QString::fromUtf8("line"));
        # line->setGeometry(QRect(320, 150, 118, 3));
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Sunken)
        self.toolBar.insertWidget(self.actionStart, line)

        self.doubleSpinBox_volume.setValue(qt_ui.settings.volume_default_level.get())
        self.tab_volume.link_volume_controls(self.doubleSpinBox_volume, self.progressBar_volume)

        # Initialize funscript offset widget (lazy loaded)
        self.funscript_offset_container = None

        # default alpha/beta axis. Used by:
        # pattern generator
        # network stuff (intiface, tcode)
        self.alpha = create_temporal_axis(0.0)
        self.beta = create_temporal_axis(0.0)
        self.gamma = create_temporal_axis(0.0)

        self.tcode_command_router = TCodeCommandRouter(
            self.alpha,
            self.beta,
            self.gamma,
            self.tab_volume.axis_api_volume,
            self.tab_volume.axis_external_volume,

            self.tab_carrier.axis_carrier,  # this gets set to the device-specific axis later

            self.tab_pulse_settings.axis_pulse_frequency,
            self.tab_pulse_settings.axis_pulse_width,
            self.tab_pulse_settings.axis_pulse_interval_random,
            self.tab_pulse_settings.axis_pulse_rise_time,

            self.tab_vibrate.vibration_1.frequency,
            self.tab_vibrate.vibration_1.strength,
            self.tab_vibrate.vibration_1.left_right_bias,
            self.tab_vibrate.vibration_1.high_low_bias,
            self.tab_vibrate.vibration_1.random,

            self.tab_vibrate.vibration_2.frequency,
            self.tab_vibrate.vibration_2.strength,
            self.tab_vibrate.vibration_2.left_right_bias,
            self.tab_vibrate.vibration_2.high_low_bias,
            self.tab_vibrate.vibration_2.random,

            # TODO: neostim
        )

        # threephase view
        self.motion_3 = qt_ui.patterns.threephase_patterns.ThreephaseMotionGenerator(self, self.alpha, self.beta)
        self.graphicsView_threephase.set_transform_params(self.tab_threephase.transform_params)
        self.graphicsView_threephase.mousePositionChanged.connect(self.motion_3.mouse_event)
        self.motion_3.position_updated.connect(self.graphicsView_threephase.set_cursor_position_ab)
        self.graphicsView_threephase.set_sensor_widget(self.page_sensors)

        # fourphase view
        self.motion_4 = qt_ui.patterns.fourphase_patterns.FourphaseMotionGenerator(self, self.alpha, self.beta, self.gamma)
        self.graphicsView_fourphase.mousePositionChanged.connect(self.motion_4.mouse_event)
        self.motion_4.position_updated.connect(self.graphicsView_fourphase.set_cursor_position_abc)

        # TODO: implement details for 4-phase
        self.tab_details.set_axis(
            self.alpha,
            self.beta,
            self.tab_threephase.calibrate_params,
            self.tab_threephase.transform_params,
        )
        # self.tab_details.set_config_manager(self.threephase_parameters)

        self.comboBox_patternSelect.currentIndexChanged.connect(self.pattern_selection_changed)
        self.motion_3.set_pattern(self.comboBox_patternSelect.currentText())
        self.doubleSpinBox.valueChanged.connect(self.motion_3.set_velocity)
        self.doubleSpinBox.valueChanged.connect(self.motion_4.set_velocity)
        self.motion_3.set_velocity(self.doubleSpinBox.value())

        self.output_device = None

        self.websocket_server = net.websocketserver.WebSocketServer(self)
        self.websocket_server.new_tcode_command.connect(self.tcode_command_router.route_command)

        self.tcpudp_server = net.tcpudpserver.TcpUdpServer(self)
        self.tcpudp_server.new_tcode_command.connect(self.tcode_command_router.route_command)

        self.serial_proxy = net.serialproxy.SerialProxy(self)
        self.serial_proxy.new_tcode_command.connect(self.tcode_command_router.route_command)

        self.buttplug_wsdm_client = net.buttplug_wsdm_client.ButtplugWsdmClient(self)
        self.buttplug_wsdm_client.new_tcode_command.connect(self.tcode_command_router.route_command)

        self.tab_volume.set_monitor_axis([
            self.alpha,
            self.beta,
            self.gamma,
        ])

        # stop audio when user modifies settings in media tab
        self.page_media.dialogOpened.connect(self.signal_stop)
        self.page_media.funscriptMappingChanged.connect(self.funscript_mapping_changed)
        self.page_media.connectionStatusChanged.connect(self.media_connection_status_changed)
        self.page_media.mediaPlayerSourceChanged.connect(self._on_media_player_source_changed)
        self.page_media.bake_audio_button.clicked.connect(self.open_write_audio_dialog)

        # Initialize offset widget visibility based on initial media player
        self._update_funscript_offset_visibility()

        # trigger updates.... maybe not all needed?
        # self.tab_carrier.settings_changed()
        self.tab_pulse_settings.settings_changed()
        self.tab_threephase.settings_changed()
        self.tab_volume.refresh_master_volume()
        self.tab_vibrate.settings_changed()

        self.wizard = DeviceSelectionWizard(self)
        self.actionDevice_selection_wizard.triggered.connect(self.open_setup_wizard)

        self.dialog = qt_ui.funscript_conversion_dialog.FunscriptConversionDialog()
        self.actionFunscript_conversion.triggered.connect(self.open_funscript_conversion_dialog)

        self.simfile_conversion_dialog = qt_ui.simfile_conversion_dialog.SimfileConversionDialog()
        self.actionSimfile_conversion.triggered.connect(self.open_simfile_conversion_dialog)

        self.focstim_flash_dialog = qt_ui.focstim_flash_dialog.FocStimFlashDialog()
        self.actionFirmware_updater.triggered.connect(self.open_focstim_flash_dialog)

        self.funscript_decomposition_dialog = qt_ui.funscript_decomposition_dialog.FunscriptDecompositionDialog()
        self.actionFunscript_decomposition.triggered.connect(self.open_funscript_decomposition_dialog)

        self.settings_dialog = qt_ui.preferences_dialog.PreferencesDialog(self)
        self.actionPreferences.triggered.connect(self.open_preferences_dialog)

        # Dark mode is always enabled

        self.iconMedia = IconWithConnectionStatus(self.actionMedia.icon(), self.toolBar.widgetForAction(self.actionMedia))
        self.actionMedia.setIcon(QIcon(self.iconMedia))
        # self.iconDevice = IconWithConnectionStatus(self.actionDevice.icon(), self.toolBar.widgetForAction(self.actionDevice))
        # self.actionDevice.setIcon(QIcon(self.iconDevice))

        self.connect_signals_slots_actionbar()
        
        # Add Coyote mode label in status bar (only visible for Coyote devices)
        from PySide6.QtWidgets import QLabel
        self.coyote_mode_label = QLabel("Mode: Two-Channel")
        self.coyote_mode_label.setStyleSheet("color: #8B3A3A; font-weight: bold; padding: 5px 15px;")
        self.statusBar().addPermanentWidget(self.coyote_mode_label)
        self.coyote_mode_label.hide()  # Hidden by default, shown only for Coyote devices

        self.refresh_device_type()

        config = DeviceConfiguration.from_settings()
        if config.device_type == DeviceType.NONE:
            self.timer = QTimer()
            self.timer.setSingleShot(True)
            self.timer.timeout.connect(self.open_setup_wizard)
            self.timer.start(0)

        self.autostart_timer = QTimer()
        self.autostart_timer.setSingleShot(True)
        self.autostart_timer.timeout.connect(self.autostart_timeout)
        self.autostart_timer.setInterval(5000)

    def connect_signals_slots_actionbar(self):
        def uncheck():
            self.actionControl.setChecked(False)
            self.actionMedia.setChecked(False)
            self.actionSensors.setChecked(False)
            # self.actionDevice.setChecked(False)
            # self.actionLog.setChecked(False)

        def show_control():
            uncheck()
            self.actionControl.setChecked(True)
            self.stackedWidget.setCurrentIndex(self.stackedWidget.indexOf(self.page_control))

        def show_media():
            uncheck()
            self.actionMedia.setChecked(True)
            self.stackedWidget.setCurrentIndex(self.stackedWidget.indexOf(self.page_media))

        def show_sensors():
            uncheck()
            self.actionSensors.setChecked(True)
            self.stackedWidget.setCurrentIndex(self.stackedWidget.indexOf(self.page_sensors))

        # def show_device():
        #     uncheck()
        #     self.actionDevice.setChecked(True)
        #     self.stackedWidget.setCurrentIndex(self.stackedWidget.indexOf(self.page_device))

        # def show_log():
        #     uncheck()
        #     self.actionLog.setChecked(True)
        #     self.stackedWidget.setCurrentIndex(self.stackedWidget.indexOf(self.page_log))

        self.actionControl.triggered.connect(show_control)
        self.actionMedia.triggered.connect(show_media)
        self.actionSensors.triggered.connect(show_sensors)
        # self.actionDevice.triggered.connect(show_device)
        # self.actionLog.triggered.connect(show_log)
        self.actionStart.triggered.connect(self.signal_start_stop)

    def media_connection_status_changed(self, status: MediaConnectionState):
        """
        Called whenever the media connection status changes.
        """
        if status.is_playing():
            self.iconMedia.set_playing()
        elif status.is_connected():
            self.iconMedia.set_connected()
        else:
            self.iconMedia.set_not_connected()

    def funscript_mapping_changed(self):
        """
        Called whenever the loaded funscripts change
        """
        logger.info('funscript mapping changed, re-linking scripts.')
        if self.page_media.autostart_enabled():
            if self.playstate == PlayState.PLAYING:
                self.signal_stop(PlayState.WAITING_ON_LOAD)
                self.autostart_timer.start()
        else:
            self.signal_stop(PlayState.STOPPED)

        device = DeviceConfiguration.from_settings()
        algorithm_factory = AlgorithmFactory(
            self,
            FunscriptKitModel.load_from_settings(),
            self.page_media.model,
            self.page_media.current_media_sync(),
            self.page_media.current_media_sync(),
            load_funscripts=not self.page_media.is_internal(),
        )

        # 3-phase visualization
        self.motion_3.set_scripts(
            algorithm_factory.get_axis_alpha(),
            algorithm_factory.get_axis_beta(),
        )

        # 4-phase visualization
        self.motion_4.set_scripts(
            algorithm_factory.get_axis_alpha(),
            algorithm_factory.get_axis_beta(),
            algorithm_factory.get_axis_gamma(),
        )

        # volume tab
        self.tab_volume.set_monitor_axis([
            algorithm_factory.get_axis_alpha(),
            algorithm_factory.get_axis_beta(),
        ])
        self.tab_volume.axis_funscript_volume = algorithm_factory.get_axis_volume_api()

        # continuous tab
        self.tab_carrier.carrier_controller.link_axis(algorithm_factory.get_axis_continuous_carrier_frequency())

        # pulse tab
        self.tab_pulse_settings.carrier_controller.link_axis(algorithm_factory.get_axis_pulse_carrier_frequency())
        self.tab_pulse_settings.pulse_frequency_controller.link_axis(algorithm_factory.get_axis_pulse_frequency())
        self.tab_pulse_settings.pulse_width_controller.link_axis(algorithm_factory.get_axis_pulse_width())
        self.tab_pulse_settings.pulse_interval_random_controller.link_axis(algorithm_factory.get_axis_pulse_interval_random())
        self.tab_pulse_settings.pulse_rise_time_controller.link_axis(algorithm_factory.get_axis_pulse_rise_time())

        # coyote tab - disable pulse_frequency spinboxes if funscript is controlling them
        # Only do this if we have a coyote device and it has a device reference
        if hasattr(self, 'tab_coyote') and self.tab_coyote.device is not None:
            # Only link pulse_frequency from funscript if media player is external (not internal)
            has_pulse_frequency_funscript = (not self.page_media.is_internal() and 
                                            algorithm_factory.get_axis_from_script_mapping(AxisEnum.PULSE_FREQUENCY) is not None)
            self.tab_coyote.set_pulse_frequency_from_funscript(has_pulse_frequency_funscript)
            
            # NOTE: Per-channel pulse_frequency controllers are already linked in coyote_settings_widget.py
            # Do NOT re-link them here as it would override the DynamicSpinboxAxis setup

        # vibration tab
        self.tab_vibrate.vib1_enabled_controller.link_axis(algorithm_factory.get_axis_vib1_enabled())
        self.tab_vibrate.vib1_freq_controller.link_axis(algorithm_factory.get_axis_vib1_frequency())
        self.tab_vibrate.vib1_strength_controller.link_axis(algorithm_factory.get_axis_vib1_strength())
        self.tab_vibrate.vib1_left_right_bias_controller.link_axis(algorithm_factory.get_axis_vib1_left_right_bias())
        self.tab_vibrate.vib1_high_low_bias_controller.link_axis(algorithm_factory.get_axis_vib1_high_low_bias())
        self.tab_vibrate.vib1_random_controller.link_axis(algorithm_factory.get_axis_vib1_random())
        self.tab_vibrate.vib2_enabled_controller.link_axis(algorithm_factory.get_axis_vib2_enabled())
        self.tab_vibrate.vib2_freq_controller.link_axis(algorithm_factory.get_axis_vib2_frequency())
        self.tab_vibrate.vib2_strength_controller.link_axis(algorithm_factory.get_axis_vib2_strength())
        self.tab_vibrate.vib2_left_right_bias_controller.link_axis(algorithm_factory.get_axis_vib2_left_right_bias())
        self.tab_vibrate.vib2_high_low_bias_controller.link_axis(algorithm_factory.get_axis_vib2_high_low_bias())
        self.tab_vibrate.vib2_random_controller.link_axis(algorithm_factory.get_axis_vib2_random())

        # neostim tab
        # TODO

        if all((not self.page_media.is_internal(),
                self.page_media.has_media_file_loaded(),
                self.page_media.autostart_enabled(),
                self.playstate == PlayState.WAITING_ON_LOAD)):
            logger.info("autostart audio")
            self.signal_start()

    def refresh_device_type(self):
        def set_visible(widget, state):
            self.tabWidget.setTabVisible(self.tabWidget.indexOf(widget), state)
            self.tabWidget.setTabEnabled(self.tabWidget.indexOf(widget), state)

        all_tabs = {self.tab_threephase,
                    self.tab_fourphase,
                    self.tab_pulse_settings,
                    self.tab_carrier,
                    self.tab_coyote_calibration,
                    self.tab_volume,
                    self.tab_vibrate,
                    self.tab_details,
                    self.tab_a_b_testing,
                    self.tab_neostim,
                    self.tab_coyote}

        visible = {self.tab_threephase, self.tab_volume, self.tab_vibrate, self.tab_details}

        config = DeviceConfiguration.from_settings()

        # determine tab visibility
        if config.device_type == DeviceType.AUDIO_THREE_PHASE:
            if config.waveform_type == WaveformType.CONTINUOUS:
                visible |= {self.tab_carrier}
            if config.waveform_type == WaveformType.PULSE_BASED:
                visible |= {self.tab_pulse_settings}
            if config.waveform_type == WaveformType.A_B_TESTING:
                visible |= {self.tab_a_b_testing}
        if config.device_type == DeviceType.FOCSTIM_THREE_PHASE:
            visible |= {self.tab_pulse_settings}
            visible -= {self.tab_vibrate}
        if config.device_type == DeviceType.FOCSTIM_FOUR_PHASE:
            visible |= {self.tab_pulse_settings, self.tab_fourphase}
            visible -= {self.tab_vibrate, self.tab_threephase, self.tab_details}
        if config.device_type == DeviceType.NEOSTIM_THREE_PHASE:
            visible |= {self.tab_neostim}
            visible -= {self.tab_vibrate, self.tab_details}
        if config.device_type in (DeviceType.COYOTE_THREE_PHASE, DeviceType.COYOTE_TWO_CHANNEL):
            visible |= {self.tab_coyote}
            # Show appropriate calibration tab based on mode
            if config.device_type == DeviceType.COYOTE_THREE_PHASE:
                visible |= {self.tab_threephase}
                visible -= {self.tab_coyote_calibration}
            else:  # COYOTE_TWO_CHANNEL
                visible |= {self.tab_coyote_calibration}
                visible -= {self.tab_threephase}
            visible -= {self.tab_vibrate, self.tab_pulse_settings, self.tab_details}

        for tab in all_tabs:
            set_visible(tab, tab in visible)

        # set safety limits
        self.tab_carrier.set_safety_limits(config.min_frequency, config.max_frequency)
        self.tab_pulse_settings.set_safety_limits(config.min_frequency, config.max_frequency)
        self.tab_a_b_testing.set_safety_limits(config.min_frequency, config.max_frequency)

        # configure tcode router
        if config.waveform_type == WaveformType.CONTINUOUS:
            self.tcode_command_router.set_carrier_axis(self.tab_carrier.axis_carrier)
        if config.waveform_type == WaveformType.PULSE_BASED:
            self.tcode_command_router.set_carrier_axis(self.tab_pulse_settings.axis_carrier_frequency)

        # populate motion generator and patterns combobox
        if config.device_type in (DeviceType.AUDIO_THREE_PHASE, DeviceType.NEOSTIM_THREE_PHASE, DeviceType.FOCSTIM_THREE_PHASE, DeviceType.COYOTE_THREE_PHASE, DeviceType.COYOTE_TWO_CHANNEL):
            self.motion_3.set_enable(True)
            self.motion_4.set_enable(False)
            self.stackedWidget_visual.setCurrentIndex(
                self.stackedWidget_visual.indexOf(self.page_threephase)
            )

        if config.device_type == DeviceType.FOCSTIM_FOUR_PHASE:
            self.motion_3.set_enable(False)
            self.motion_4.set_enable(True)
            self.stackedWidget_visual.setCurrentIndex(
                self.stackedWidget_visual.indexOf(self.page_fourphase)
            )
        
        if config.device_type in (DeviceType.COYOTE_THREE_PHASE, DeviceType.COYOTE_TWO_CHANNEL):
            # Show Coyote mode label
            mode_name = "Three-Phase" if config.device_type == DeviceType.COYOTE_THREE_PHASE else "Two-Channel"
            self.coyote_mode_label.setText(f"Mode: {mode_name}")
            self.coyote_mode_label.show()
            logger.info(f"Coyote mode label shown: {mode_name}")
            
            # Only disconnect if switching to a device type that is NOT 8 or 9
            prev_type = None
            if self.output_device and isinstance(self.output_device, CoyoteDevice):
                # Try to get previous device type from settings or state
                prev_type = qt_ui.settings.device_config_device_type.get()
            if self.output_device and isinstance(self.output_device, CoyoteDevice):
                # Only disconnect if the new device type is not 8 or 9
                if config.device_type not in (DeviceType.COYOTE_THREE_PHASE, DeviceType.COYOTE_TWO_CHANNEL) or (prev_type not in (8, 9)):
                    logger.info("Coyote mode changed, disconnecting old device...")
                    self.output_device.stop_updates()
                    if self.output_device._event_loop:
                        asyncio.run_coroutine_threadsafe(self.output_device.disconnect(), self.output_device._event_loop)
                    if hasattr(self, 'tab_coyote'):
                        self.tab_coyote.cleanup()
                    self.output_device = None
                    import time
                    time.sleep(0.5)
            if self.output_device is None:
                self.output_device = CoyoteDevice(DEVICE_NAME)
                self.output_device.parameters = CoyoteParams(
                    channel_a_limit=qt_ui.settings.coyote_channel_a_limit.get(),
                    channel_b_limit=qt_ui.settings.coyote_channel_b_limit.get(),
                    channel_a_freq_balance=qt_ui.settings.coyote_channel_a_freq_balance.get(),
                    channel_b_freq_balance=qt_ui.settings.coyote_channel_b_freq_balance.get(),
                    channel_a_intensity_balance=qt_ui.settings.coyote_channel_a_intensity_balance.get(),
                    channel_b_intensity_balance=qt_ui.settings.coyote_channel_b_intensity_balance.get()
                )
                self.tab_coyote.setup_device(self.output_device)
        else:
            # Hide Coyote mode label for non-Coyote devices
            self.coyote_mode_label.hide()

        self.refresh_pattern_combobox()

        if config.device_type == DeviceType.AUDIO_THREE_PHASE:
            self.graphicsView_threephase.set_background(stereo=True)
            self.tab_threephase.phase_widget_calibration.set_background(stereo=True)
        else:
            self.graphicsView_threephase.set_background(foc=True)
            self.tab_threephase.phase_widget_calibration.set_background(foc=True)

        self.refresh_pattern_combobox()

    def pattern_selection_changed(self, index):
        pattern = self.comboBox_patternSelect.currentData()
        self.motion_3.set_pattern(pattern)
        self.motion_4.set_pattern(pattern)

    def signal_start_stop(self):
        if self.playstate == PlayState.STOPPED:
            self.signal_start()
        else:
            self.signal_stop(PlayState.STOPPED)

    def signal_start(self):
        self.autostart_timer.stop()
        device = DeviceConfiguration.from_settings()

        # Clean up previous device if switching away
        if self.output_device and device.device_type not in (DeviceType.COYOTE_THREE_PHASE, DeviceType.COYOTE_TWO_CHANNEL):
            self.output_device = None
            # Clean up Coyote widget resources if switching away from Coyote
            if hasattr(self, 'tab_coyote'):
                self.tab_coyote.cleanup()

        assert (self.output_device is None or device.device_type in (DeviceType.COYOTE_THREE_PHASE, DeviceType.COYOTE_TWO_CHANNEL))

        algorithm_factory = AlgorithmFactory(
            self,
            FunscriptKitModel.load_from_settings(),
            self.page_media.model,
            self.page_media.current_media_sync(),
            self.page_media.current_media_sync(),
            load_funscripts=not self.page_media.is_internal(),
        )
        algorithm = algorithm_factory.create_algorithm(device)

        if device.device_type in [
            DeviceType.AUDIO_THREE_PHASE,
        ]: # is audio device
            api_name = qt_ui.settings.audio_api.get() or sd.query_hostapis(sd.default.hostapi)['name']
            output_device_name = qt_ui.settings.audio_output_device.get() or sd.query_devices(sd.default.device[1])['name']
            latency = qt_ui.settings.audio_latency.get() or 'high'
            try:
                latency = float(latency)
            except ValueError:
                pass

            output_device = AudioStimDevice(None)
            mapping_parameters = output_device.auto_detect_channel_mapping_parameters(algorithm)
            output_device.start(api_name, output_device_name, latency, algorithm, mapping_parameters)
            if output_device.is_connected_and_running():
                self.output_device = output_device
                self.playstate = PlayState.PLAYING
                self.tab_volume.set_play_state(self.playstate)
                self.refresh_play_button_icon()
        elif device.device_type in (DeviceType.FOCSTIM_THREE_PHASE, DeviceType.FOCSTIM_FOUR_PHASE):
            output_device = FOCStimProtoDevice()
            use_teleplot = qt_ui.settings.focstim_use_teleplot.get()
            dump_notifications = qt_ui.settings.focstim_dump_notifications_to_file.get()
            comms_wifi = qt_ui.settings.focstim_communication_wifi.get()
            if not comms_wifi:
                serial_port_name = qt_ui.settings.focstim_serial_port.get()
                output_device.start_serial(serial_port_name, use_teleplot, dump_notifications, algorithm)
            else:
                ip = qt_ui.settings.focstim_ip.get()
                output_device.start_tcp(ip, 55533, use_teleplot, dump_notifications, algorithm)

            if output_device.is_connected_and_running():
                self.output_device = output_device
                self.playstate = PlayState.PLAYING
                self.tab_volume.set_play_state(self.playstate)
                self.refresh_play_button_icon()

                output_device.new_as5311_sensor_data.connect(self.page_sensors.new_as5311_sensor_data)
                output_device.new_imu_sensor_data.connect(self.page_sensors.new_imu_sensor_data)
                output_device.new_pressure_sensor_data.connect(self.page_sensors.new_pressure_sensor_data)
                algorithm.sensor_node = self.page_sensors


        elif device.device_type == DeviceType.NEOSTIM_THREE_PHASE:
            output_device = NeoStim()
            serial_port_name = qt_ui.settings.neostim_serial_port.get()
            output_device.start(serial_port_name, algorithm)
            if output_device.is_connected_and_running():
                self.output_device = output_device
                self.playstate = PlayState.PLAYING
                self.tab_volume.set_play_state(self.playstate)
                self.refresh_play_button_icon()
        elif device.device_type in (DeviceType.COYOTE_THREE_PHASE, DeviceType.COYOTE_TWO_CHANNEL):
            if not self.output_device:
                logger.warning("Coyote device is no longer initialized")
                return

            self.output_device.start_updates(algorithm)
            self.playstate = PlayState.PLAYING
            self.refresh_play_button_icon()
        else:
            raise RuntimeError("Unknown device type")

    def signal_stop(self, new_playstate: PlayState = PlayState.STOPPED):
        """Stop signal generation."""
        if self.output_device is not None:
            if isinstance(self.output_device, CoyoteDevice):
                self.output_device.stop_updates()  # Only stop sending to device
            else:
                self.output_device.stop()  # Other devices may need full stop
                self.output_device = None
        self.playstate = new_playstate
        self.tab_volume.set_play_state(self.playstate)
        self.refresh_play_button_icon()

    def _load_icon_theme(self):
        """Load the icon theme from settings"""
        icon_theme = qt_ui.settings.icon_theme.get()
        
        # Determine base path - works for dev and PyInstaller
        base_path = getattr(sys, '_MEIPASS', os.path.join(os.path.dirname(os.path.abspath(__file__)), os.path.pardir))
        icons_dir = os.path.join(base_path, 'resources', 'icons')
        icon_path = os.path.join(icons_dir, f'{icon_theme}.png')
        
        if os.path.exists(icon_path):
            icon = QtGui.QIcon()
            icon.addPixmap(QtGui.QPixmap(icon_path), QtGui.QIcon.Normal, QtGui.QIcon.Off)
            self.setWindowIcon(icon)
        else:
            logger.warning(f"Icon theme '{icon_theme}' not found at {icon_path}, using default")

    def update_window_icon(self):
        """Update the window icon (called from preferences dialog when theme changes)"""
        self._load_icon_theme()
        # Try to update taskbar icon using Windows API
        self._update_taskbar_icon_windows_api()

    def _update_taskbar_icon_windows_api(self):
        """Update taskbar icon using Windows API (experimental)"""
        try:
            import ctypes
            import platform
            
            if platform.system() != 'Windows':
                return
            
            # Get window handle
            hwnd = int(self.winId())
            
            # Get icon path
            icon_theme = qt_ui.settings.icon_theme.get()
            ico_path = os.path.join(
                os.path.dirname(__file__), 
                '..', 'resources', 
                f'{icon_theme}.ico'
            )
            
            if not os.path.exists(ico_path):
                logger.debug(f"Icon file not found: {ico_path}")
                return
            
            # Windows API constants
            WM_SETICON = 0x0080
            ICON_SMALL = 0
            ICON_BIG = 1
            IMAGE_ICON = 1
            LR_LOADFROMFILE = 0x00000010
            
            user32 = ctypes.windll.user32
            
            # Load icon from file
            h_icon = user32.LoadImageW(
                None,
                ico_path,
                IMAGE_ICON,
                0,
                0,
                LR_LOADFROMFILE
            )
            
            if h_icon == 0:
                logger.debug(f"Failed to load icon: {ico_path}")
                return
            
            # Set both small and big icons
            user32.SendMessageW(hwnd, WM_SETICON, ICON_SMALL, h_icon)
            user32.SendMessageW(hwnd, WM_SETICON, ICON_BIG, h_icon)
            
            logger.info(f"Updated taskbar icon to: {icon_theme}")
            
        except Exception as e:
            logger.debug(f"Failed to update taskbar icon: {e}")

    def autostart_timeout(self):
        print('autostart timeout')
        if self.playstate == PlayState.WAITING_ON_LOAD:
            logger.info("autostart timeout reached. No longer starting audio on file load")
            self.signal_stop(PlayState.STOPPED)

    def refresh_play_button_icon(self):
        if self.playstate in (PlayState.PLAYING, PlayState.WAITING_ON_LOAD):
            self.actionStart.setIcon(QtGui.QIcon(":/restim/stop-sign_poly.svg"))
            self.actionStart.setText("Stop")
        else:
            # Create icon from pixmap with custom dark green color
            pixmap = QtGui.QPixmap(65, 48)
            pixmap.fill(QtCore.Qt.transparent)
            painter = QtGui.QPainter(pixmap)
            painter.setRenderHint(QtGui.QPainter.Antialiasing)
            # Draw a dark green triangle play button
            polygon = QtGui.QPolygon([
                QtCore.QPoint(15, 10),
                QtCore.QPoint(15, 38),
                QtCore.QPoint(50, 24)
            ])
            painter.setBrush(QtGui.QBrush(QtGui.QColor("#3ec941")))
            painter.setPen(QtGui.QPen(QtGui.QColor("#3ec941")))
            painter.drawPolygon(polygon)
            painter.end()
            self.actionStart.setIcon(QtGui.QIcon(pixmap))
            self.actionStart.setText("Start")

    def open_setup_wizard(self):
        self.signal_stop(PlayState.STOPPED)
        self.wizard.exec()
        self.refresh_device_type()
        # Delay reload_settings to allow new Coyote device to initialize
        QTimer.singleShot(100, self.reload_settings)

    def open_funscript_conversion_dialog(self):
        self.signal_stop(PlayState.STOPPED)
        self.dialog.exec()

    def open_simfile_conversion_dialog(self):
        self.signal_stop(PlayState.STOPPED)
        self.simfile_conversion_dialog.exec()

    def open_focstim_flash_dialog(self):
        self.signal_stop(PlayState.STOPPED)
        self.focstim_flash_dialog.exec()

    def open_funscript_decomposition_dialog(self):
        self.signal_stop(PlayState.STOPPED)
        self.funscript_decomposition_dialog.exec()

    def open_preferences_dialog(self):
        self.signal_stop(PlayState.STOPPED)
        self.settings_dialog.exec()
        self.reload_settings()

    def open_about_dialog(self):
        self.signal_stop(PlayState.STOPPED)
        self.about_dialog.exec()

    def open_write_audio_dialog(self):
        device = DeviceConfiguration.from_settings()
        kit = FunscriptKitModel.load_from_settings()
        filename = self.page_media.loaded_media_path
        dialog = AudioWriteDialog(self, kit, self.page_media.model, device, filename)
        dialog.exec()

    def reload_settings(self):
        """
        Reload everything that is stored in settings and may be changed
        by the preferences dialog
        """
        self.tcode_command_router.reload_kit()
        self.tab_volume.refreshSettings()
        self.buttplug_wsdm_client.refreshSettings()
        self.funscript_mapping_changed()  # reload funscript axis
        self.tab_a_b_testing.refreshSettings()
        self.motion_3.refreshSettings()
        self.motion_4.refreshSettings()
        self.refresh_pattern_combobox()
        self._load_icon_theme()  # reload icon if theme changed

    def refresh_pattern_combobox(self):
        config = DeviceConfiguration.from_settings()
        currently_selected_text = self.comboBox_patternSelect.currentText()

        if config.device_type in (DeviceType.AUDIO_THREE_PHASE, DeviceType.NEOSTIM_THREE_PHASE, DeviceType.FOCSTIM_THREE_PHASE, DeviceType.COYOTE_THREE_PHASE, DeviceType.COYOTE_TWO_CHANNEL):
            self.comboBox_patternSelect.clear()
            for pattern in self.motion_3.patterns:
                self.comboBox_patternSelect.addItem(pattern.name(), pattern)
        else:
            self.comboBox_patternSelect.clear()
            for pattern in self.motion_4.patterns:
                self.comboBox_patternSelect.addItem(pattern.name(), pattern)

        # try to select pattern with similar name as was previously selected
        index = self.comboBox_patternSelect.findText(currently_selected_text)
        if index == -1:
            index = 0
        self.comboBox_patternSelect.setCurrentIndex(index)


    def save_settings(self):
        """
        Save everything that is stored in settings but isn't immediately saved
        for performance reasons.
        """
        self.tab_threephase.save_settings()
        self.tab_fourphase.save_settings()
        self.tab_carrier.save_settings()
        self.tab_vibrate.save_settings()
        self.tab_pulse_settings.save_settings()
        self.tab_volume.save_settings()

    def closeEvent(self, event):
        logger.warning('Shutting down')
        if self.output_device is not None:
            self.output_device.stop()
        self.save_settings()
        event.accept()

    def _on_media_player_source_changed(self):
        """Handle media player source changes - update offset widget visibility"""
        logger.info(f"_on_media_player_source_changed called, is_internal={self.page_media.is_internal()}")
        self._update_funscript_offset_visibility()
        
        # Stop playback when switching to internal player
        if self.page_media.is_internal() and self.playstate == PlayState.PLAYING:
            self.signal_stop(PlayState.STOPPED)

    def _update_funscript_offset_visibility(self):
        """Show/hide funscript offset widget based on media player type (internal/external)"""
        if not self.page_media.is_internal():
            # External media player - create widget if needed and show it
            if self.funscript_offset_container is None:
                self._create_funscript_offset_widget()
            if self.funscript_offset_action is not None:
                self.funscript_offset_action.setVisible(True)
        else:
            # Internal media player - hide offset widget
            if self.funscript_offset_action is not None:
                self.funscript_offset_action.setVisible(False)

    def _create_funscript_offset_widget(self):
        """Create and configure the funscript offset widget"""
        from PySide6.QtWidgets import QGroupBox, QDoubleSpinBox, QVBoxLayout
        
        self.funscript_offset_container = QGroupBox("Offset (s)")
        layout = QVBoxLayout()
        layout.setContentsMargins(4, 4, 4, 4)
        
        self.funscript_offset_spinbox = QDoubleSpinBox()
        self.funscript_offset_spinbox.setRange(-1.0, 1.0)
        self.funscript_offset_spinbox.setSingleStep(0.0125)
        self.funscript_offset_spinbox.setDecimals(4)
        self.funscript_offset_spinbox.setValue(qt_ui.settings.media_sync_funscript_offset.get())
        self.funscript_offset_spinbox.setToolTip("Adjust funscript sync offset (±1.0 seconds)")
        self.funscript_offset_spinbox.valueChanged.connect(self._on_funscript_offset_changed)
        
        layout.addWidget(self.funscript_offset_spinbox)
        self.funscript_offset_container.setLayout(layout)
        
        # Add to toolbar right after Media button
        # Find the index of actionMedia and insert the widget right after it
        actions = self.toolBar.actions()
        media_index = actions.index(self.actionMedia) if self.actionMedia in actions else -1
        if media_index >= 0 and media_index < len(actions) - 1:
            # Insert before the next action after Media
            self.funscript_offset_action = self.toolBar.insertWidget(actions[media_index + 1], self.funscript_offset_container)
        else:
            # Fallback: insert before the first separator or action we encounter after Media
            self.funscript_offset_action = self.toolBar.insertWidget(self.actionStart, self.funscript_offset_container)
        
        # Apply current theme
        self._apply_funscript_offset_theme()

    def _apply_funscript_offset_theme(self):
        """Apply light/dark mode theming to offset widget"""
        if self.funscript_offset_container is None:
            return
        
        palette = self.palette()
        bg_color = palette.color(self.backgroundRole())
        text_color = palette.color(self.foregroundRole())
        
        stylesheet = f"""
            QGroupBox {{
                color: {text_color.name()};
                border: 1px solid {text_color.name()};
                border-radius: 3px;
                margin-top: 0.5em;
                padding-top: 0.5em;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 3px 0 3px;
            }}
            QDoubleSpinBox {{
                background-color: {bg_color.name()};
                color: {text_color.name()};
            }}
        """
        self.funscript_offset_container.setStyleSheet(stylesheet)

    def _on_funscript_offset_changed(self, value: float):
        """Handle funscript offset spinbox value changes"""
        qt_ui.settings.media_sync_funscript_offset.set(value)


def run():
    log_path = os.getcwd()
    logging.basicConfig(filename=os.path.join(log_path, 'restim.log'), filemode='w')
    logging.getLogger().addHandler(logging.StreamHandler())
    logger = logging.getLogger('restim')
    logger.setLevel(logging.DEBUG)
    logging.getLogger('matplotlib').setLevel(logging.WARN)

    def excepthook(exc_type, exc_value, exc_tb):
        exc_info = (exc_type, exc_value, exc_tb)
        logger.critical('Exception occurred', exc_info=exc_info)
        QApplication.quit()

    sys.excepthook = excepthook

    app = QApplication(sys.argv)
    apply_theme(app)
    win = Window()
    win.show()
    sys.exit(app.exec())