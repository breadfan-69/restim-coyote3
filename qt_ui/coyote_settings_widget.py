import asyncio
import logging
import time
from dataclasses import dataclass
from typing import Dict, Optional
from PySide6 import QtWidgets
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QLabel, QSlider, QHBoxLayout,
                            QGraphicsView, QGraphicsScene, QGraphicsLineItem, QSpinBox,
                            QGraphicsRectItem, QToolTip, QGraphicsEllipseItem, QPushButton)
from PySide6.QtCore import QSettings, Qt, QTimer
from PySide6.QtGui import QPen, QColor, QBrush, QPainterPath
from device.coyote.device import CoyoteDevice, CoyotePulse, CoyotePulses, CoyoteStrengths
from qt_ui import settings
from qt_ui.axis_controller import AxisController
from stim_math.axis import create_constant_axis

class CoyoteSettingsWidget(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.device: Optional[CoyoteDevice] = None
        self.channel_controls: Dict[str, ChannelControl] = {}
        self.coyote_logger = logging.getLogger('restim.coyote')
        self._base_log_level = self.coyote_logger.getEffectiveLevel()
        self.graph_window = settings.coyote_graph_window
        self.setupUi()
        self.apply_debug_logging(settings.coyote_debug_logging.get())

    def setupUi(self):
        self.setLayout(QVBoxLayout())

        self.label_connection_status = QLabel("Device: Disconnected")
        self.label_connection_stage = QLabel("Stage: Waiting")
        self.label_battery_level = QLabel("Battery: —")
        
        self.button_reset_connection = QPushButton("Reset Connection")
        self.button_reset_connection.setMaximumWidth(120)
        self.button_reset_connection.clicked.connect(self.on_reset_connection_clicked)
        
        status_layout = QHBoxLayout()
        status_layout.addWidget(self.label_connection_status)
        status_layout.addWidget(self.label_connection_stage)
        status_layout.addWidget(self.label_battery_level)
        status_layout.addStretch()
        status_layout.addWidget(self.button_reset_connection)
        self.layout().addLayout(status_layout)

        configs = (
            ChannelConfig(
                channel_id='A',
                freq_min_setting=settings.coyote_channel_a_freq_min,
                freq_max_setting=settings.coyote_channel_a_freq_max,
                strength_max_setting=settings.coyote_channel_a_strength_max,
            ),
            ChannelConfig(
                channel_id='B',
                freq_min_setting=settings.coyote_channel_b_freq_min,
                freq_max_setting=settings.coyote_channel_b_freq_max,
                strength_max_setting=settings.coyote_channel_b_strength_max,
            ),
        )

        for config in configs:
            control = ChannelControl(self, config)
            self.channel_controls[config.channel_id] = control
            self.layout().addLayout(control.build_ui())
            control.reset_volume()

    def setup_device(self, device: CoyoteDevice):
        self.device = device

        self.device.connection_status_changed.connect(self.on_connection_status_changed)
        self.device.battery_level_changed.connect(self.on_battery_level_changed)
        self.device.parameters_changed.connect(self.on_parameters_changed)
        self.device.power_levels_changed.connect(self.on_power_levels_changed)
        self.device.pulse_sent.connect(self.on_pulse_sent)

        for control in self.channel_controls.values():
            control.reset_volume()

        if device.strengths:
            for control in self.channel_controls.values():
                control.update_from_device(device.strengths)

    def cleanup(self):
        """Clean up widget resources when device is being switched"""
        if self.device:
            for signal, slot in (
                (self.device.connection_status_changed, self.on_connection_status_changed),
                (self.device.battery_level_changed, self.on_battery_level_changed),
                (self.device.parameters_changed, self.on_parameters_changed),
                (self.device.power_levels_changed, self.on_power_levels_changed),
                (self.device.pulse_sent, self.on_pulse_sent),
            ):
                try:
                    signal.disconnect(slot)
                except (TypeError, RuntimeError):
                    pass
            self.device = None

    def update_channel_strength(self, control: 'ChannelControl', value: int):
        if not self.device or not self.device._event_loop:
            return

        strengths = control.with_strength(self.device.strengths, value)

        asyncio.run_coroutine_threadsafe(
            self.device.send_command(strengths),
            self.device._event_loop
        )

        self.device.strengths = strengths

    def on_connection_status_changed(self, connected: bool, stage: str = None):
        self.label_connection_status.setText("Device: Connected" if connected else "Device: Disconnected")
        if stage:
            normalized_stage = stage.strip()
            if connected and normalized_stage.lower() == "connected":
                stage_text = "Ready"
            else:
                stage_text = normalized_stage
            self.label_connection_stage.setText(f"Stage: {stage_text}")
        else:
            self.label_connection_stage.setText("Stage: —")

    def on_battery_level_changed(self, level: int):
        self.label_battery_level.setText(f"Battery: {level}%")

    def on_parameters_changed(self):
        pass

    def on_power_levels_changed(self, strengths: CoyoteStrengths):
        for control in self.channel_controls.values():
            control.update_from_device(strengths)

    def on_pulse_sent(self, pulses: CoyotePulses):
        if not self.device:
            return

        for control in self.channel_controls.values():
            control.apply_pulses(pulses, self.device.strengths)

    def on_reset_connection_clicked(self):
        """Reset the Bluetooth connection by disconnecting and letting the connection loop restart"""
        if not self.device:
            self.coyote_logger.warning("Device not initialized")
            return
        
        self.coyote_logger.info("User initiated connection reset")
        self.button_reset_connection.setEnabled(False)
        self.button_reset_connection.setText("Resetting...")
        
        # Trigger temporary disconnect in the event loop (will auto-reconnect)
        self.device.reset_connection()
        
        # Re-enable button after a short delay
        QTimer.singleShot(1000, lambda: self._reset_button_ready())
    
    def _reset_button_ready(self):
        """Re-enable the reset button after disconnect"""
        self.button_reset_connection.setEnabled(True)
        self.button_reset_connection.setText("Reset Connection")

    def apply_debug_logging(self, enabled: bool):
        new_level = logging.DEBUG if enabled else logging.INFO
        self.coyote_logger.setLevel(new_level)

    def set_pulse_frequency_from_funscript(self, enabled: bool):
        """Enable/disable pulse_frequency spinboxes based on funscript availability"""
        for control in self.channel_controls.values():
            if enabled:
                # Funscript loaded: disable spinbox, ensure range is set
                control.set_pulse_frequency_enabled(False)
                control.update_pulse_freq_limits()  # Ensure range is correct
            else:
                # No funscript: enable spinbox for user control
                control.set_pulse_frequency_enabled(True)
                control.update_pulse_freq_limits()  # Ensure range is correct

    def get_pulse_frequency_controller(self, channel_id: str) -> Optional[AxisController]:
        """Get the pulse_frequency axis controller for a specific channel"""
        control = self.channel_controls.get(channel_id.upper())
        return control.pulse_frequency_controller if control else None

    def get_channel_a_pulse_frequency_controller(self) -> Optional[AxisController]:
        """Get the pulse_frequency axis controller for channel A"""
        return self.get_pulse_frequency_controller('A')

    def get_channel_b_pulse_frequency_controller(self) -> Optional[AxisController]:
        """Get the pulse_frequency axis controller for channel B"""
        return self.get_pulse_frequency_controller('B')

@dataclass(frozen=True)
class ChannelConfig:
    channel_id: str
    freq_min_setting: settings.Setting
    freq_max_setting: settings.Setting
    strength_max_setting: settings.Setting

class ChannelControl:

    def update_pulse_freq_limits(self):
        if self.pulse_min and self.pulse_max and self.pulse_duration:
            min_val = self.pulse_min.value()
            max_val = self.pulse_max.value()
            # Ensure min <= max
            actual_min = min(min_val, max_val)
            actual_max = max(min_val, max_val)
            
            # Update spinbox range based on mode
            if not self.pulse_duration.isEnabled():
                # Funscript mode: full hardware range to allow mapped values to display
                self.pulse_duration.blockSignals(True)
                self.pulse_duration.setRange(4, 200)
                self.pulse_duration.blockSignals(False)
            else:
                # Internal player mode: constrain range to [freq_min, freq_max]
                # Only setValue if the current value would be clamped by the new range
                current_value = self.pulse_duration.value()
                clamped_value = max(actual_min, min(current_value, actual_max))
                
                self.pulse_duration.blockSignals(True)
                # First, always update the range
                self.pulse_duration.setRange(actual_min, actual_max)
                # Then, only setValue if it was clamped (needs to change)
                if clamped_value != current_value:
                    self.pulse_duration.setValue(clamped_value)
                self.pulse_duration.blockSignals(False)

    def __init__(self, parent: 'CoyoteSettingsWidget', config: ChannelConfig):
        self.parent = parent
        self.config = config

        self.pulse_min: Optional[QSpinBox] = None
        self.pulse_max: Optional[QSpinBox] = None
        self.pulse_duration: Optional[QSpinBox] = None
        self.pulse_frequency_controller: Optional[AxisController] = None
        self.strength_max: Optional[QSpinBox] = None
        self.volume_slider: Optional[QSlider] = None
        self.volume_label: Optional[QLabel] = None
        self.pulse_graph: Optional[PulseGraphContainer] = None
        self.stats_label: Optional[QLabel] = None

    @property
    def channel_id(self) -> str:
        return self.config.channel_id

    @property
    def _is_channel_a(self) -> bool:
        return self.channel_id.upper() == 'A'

    def build_ui(self) -> QHBoxLayout:
        # Create a group box for this channel
        group_box = QtWidgets.QGroupBox(f"Channel {self.channel_id}")
        group_layout = QHBoxLayout()

        left = QVBoxLayout()

        # Create a group box for freq and strength controls
        freq_strength_group = QtWidgets.QGroupBox("Max/Min")
        freq_strength_group.setCheckable(True)
        freq_strength_group.setChecked(False)
        freq_strength_layout = QVBoxLayout()

        pulse_min_layout = QHBoxLayout()
        self.pulse_min = QSpinBox()
        self.pulse_min.setRange(4, 200)
        self.pulse_min.setSingleStep(10)
        self.pulse_min.setValue(self.config.freq_min_setting.get())
        self.pulse_min.valueChanged.connect(self.on_pulse_min_changed)
        self.pulse_min.valueChanged.connect(self.update_pulse_freq_limits)
        pulse_min_layout.addWidget(QLabel("Min Freq (Hz)"))
        pulse_min_layout.addWidget(self.pulse_min)
        freq_strength_layout.addLayout(pulse_min_layout)

        pulse_max_layout = QHBoxLayout()
        self.pulse_max = QSpinBox()
        self.pulse_max.setRange(4, 200)
        self.pulse_max.setSingleStep(10)
        self.pulse_max.setValue(self.config.freq_max_setting.get())
        self.pulse_max.valueChanged.connect(self.on_pulse_max_changed)
        self.pulse_max.valueChanged.connect(self.update_pulse_freq_limits)
        pulse_max_layout.addWidget(QLabel("Max Freq (Hz)"))
        pulse_max_layout.addWidget(self.pulse_max)
        freq_strength_layout.addLayout(pulse_max_layout)

        strength_layout = QHBoxLayout()
        strength_layout.addWidget(QLabel("Max Strength"))
        self.strength_max = QSpinBox()
        self.strength_max.setRange(1, 200)
        self.strength_max.setSingleStep(1)
        self.strength_max.setValue(self.config.strength_max_setting.get())
        self.strength_max.valueChanged.connect(self.on_strength_max_changed)
        strength_layout.addWidget(self.strength_max)
        freq_strength_layout.addLayout(strength_layout)

        freq_strength_group.setLayout(freq_strength_layout)
        left.addWidget(freq_strength_group)

        # Enable/disable mouse interaction based on group box checkbox
        def set_mouse_interaction(enabled):
            self.pulse_min.setEnabled(enabled)
            self.pulse_max.setEnabled(enabled)
            self.strength_max.setEnabled(enabled)
        freq_strength_group.toggled.connect(set_mouse_interaction)
        set_mouse_interaction(True)

        pulse_duration_layout = QHBoxLayout()
        self.pulse_duration = QSpinBox()
        # Initialize with the configured freq_min/freq_max range (will be [4,200] if not set)
        freq_min = self.config.freq_min_setting.get()
        freq_max = self.config.freq_max_setting.get()
        self.pulse_duration.setRange(freq_min, freq_max)
        self.pulse_duration.setSingleStep(1)
        # Set initial value, clamped to the range
        initial_value = max(freq_min, min(50, freq_max))
        self.pulse_duration.setValue(initial_value)
        pulse_duration_layout.addWidget(QLabel("Pulse Freq (Hz)"))
        pulse_duration_layout.addWidget(self.pulse_duration)
        left.addLayout(pulse_duration_layout)

        # Create axis controller for this channel's pulse_duration
        self.pulse_frequency_controller = AxisController(self.pulse_duration)
        # Link to an axis that reads the current spinbox value dynamically
        self.pulse_frequency_controller.link_to_internal_axis(
            self.create_pulse_duration_axis()
        )

        group_layout.addLayout(left)

        self.pulse_graph = PulseGraphContainer(self.parent.graph_window, self.pulse_min, self.pulse_max)
        self.pulse_graph.plot.setMinimumHeight(100)

        graph_column = QVBoxLayout()
        graph_column.addWidget(self.pulse_graph)

        self.stats_label = QLabel("Intensity: 0%")
        self.stats_label.setAlignment(Qt.AlignHCenter)
        self.pulse_graph.attach_stats_label(self.stats_label)
        graph_column.addWidget(self.stats_label)

        group_layout.addLayout(graph_column)

        volume_layout = QVBoxLayout()
        self.volume_slider = QSlider(Qt.Vertical)
        self.volume_slider.setRange(0, self.config.strength_max_setting.get())
        self.volume_slider.valueChanged.connect(self.on_volume_changed)
        self.volume_label = QLabel()
        self.volume_label.setAlignment(Qt.AlignHCenter)
        volume_layout.addWidget(self.volume_slider)
        volume_layout.addWidget(self.volume_label)
        group_layout.addLayout(volume_layout)

        self.update_volume_label(self.volume_slider.value())
        group_box.setLayout(group_layout)

        # Return a layout containing just the group box for this channel
        layout = QHBoxLayout()
        layout.addWidget(group_box)
        return layout

    def reset_volume(self):
        self.set_strength_from_device(0)

    def select_strength(self, strengths: CoyoteStrengths) -> int:
        return strengths.channel_a if self._is_channel_a else strengths.channel_b

    def with_strength(self, strengths: CoyoteStrengths, value: int) -> CoyoteStrengths:
        if self._is_channel_a:
            return CoyoteStrengths(channel_a=value, channel_b=strengths.channel_b)
        return CoyoteStrengths(channel_a=strengths.channel_a, channel_b=value)

    def extract_pulses(self, pulses: CoyotePulses) -> list[CoyotePulse]:
        return pulses.channel_a if self._is_channel_a else pulses.channel_b

    def update_from_device(self, strengths: CoyoteStrengths):
        self.set_strength_from_device(self.select_strength(strengths))

    def apply_pulses(self, pulses: CoyotePulses, strengths: CoyoteStrengths):
        channel_pulses = self.extract_pulses(pulses)
        if not channel_pulses:
            return
        self.handle_pulses(channel_pulses, self.select_strength(strengths))

    def create_pulse_duration_axis(self):
        """Create a dynamic axis that reads the current pulse_duration spinbox value."""
        class DynamicSpinboxAxis:
            """An axis that dynamically reads from a spinbox."""
            def __init__(self, spinbox):
                self.spinbox = spinbox
            
            def interpolate(self, time_s):
                """Always return the current spinbox value."""
                return float(self.spinbox.value())
            
            def add(self, value, interval=0.0):
                """No-op for dynamic axis."""
                pass
        
        return DynamicSpinboxAxis(self.pulse_duration)

    def on_volume_changed(self, value: int):
        self.update_volume_label(value)
        self.parent.update_channel_strength(self, value)

    def update_volume_label(self, value: int):
        max_strength = max(1, self.config.strength_max_setting.get())
        percentage = int((value / max_strength) * 100)
        self.volume_label.setText(f"{value} ({percentage}%)")

    def set_strength_from_device(self, value: int):
        if self.volume_slider is None:
            return
        self.volume_slider.blockSignals(True)
        self.volume_slider.setValue(value)
        self.volume_slider.blockSignals(False)

    def set_pulse_frequency_enabled(self, enabled: bool):
        """Enable or disable the pulse duration spinbox"""
        if self.pulse_duration:
            self.pulse_duration.setEnabled(enabled)
        # Update the label with current slider value
        if self.volume_slider:
            self.update_volume_label(self.volume_slider.value())

    def on_strength_max_changed(self, value: int):
        self.config.strength_max_setting.set(value)

        current_value = self.volume_slider.value() if self.volume_slider else 0
        if self.volume_slider:
            self.volume_slider.blockSignals(True)
            self.volume_slider.setRange(0, value)
            clamped_value = min(current_value, value)
            self.volume_slider.setValue(clamped_value)
            self.volume_slider.blockSignals(False)
            self.update_volume_label(clamped_value)
            current_value = clamped_value

        self.parent.update_channel_strength(self, current_value)

    def on_pulse_min_changed(self, value: int):
        if self.pulse_min is None or self.pulse_max is None:
            return

        corrected = value
        if value >= self.pulse_max.value():
            corrected = max(self.pulse_max.value() - self.pulse_min.singleStep(), self.pulse_min.minimum())
        if corrected != value:
            self.pulse_min.blockSignals(True)
            self.pulse_min.setValue(corrected)
            self.pulse_min.blockSignals(False)
        self.config.freq_min_setting.set(corrected)
        self.update_pulse_freq_limits()

    def on_pulse_max_changed(self, value: int):
        if self.pulse_min is None or self.pulse_max is None:
            return

        corrected = value
        if value <= self.pulse_min.value():
            corrected = min(self.pulse_min.value() + self.pulse_max.singleStep(), self.pulse_max.maximum())
        if corrected != value:
            self.pulse_max.blockSignals(True)
            self.pulse_max.setValue(corrected)
            self.pulse_max.blockSignals(False)
        self.config.freq_max_setting.set(corrected)
        self.update_pulse_freq_limits()

    def handle_pulses(self, pulses: list[CoyotePulse], strength: int):
        if not self.pulse_graph or not pulses:
            return

        channel_limit = self.config.strength_max_setting.get()
        for pulse in pulses:
            self.pulse_graph.add_pulse(
                frequency=pulse.frequency,
                intensity=pulse.intensity,
                duration=pulse.duration,
                current_strength=strength,
                channel_limit=channel_limit,
            )
            # Update the pulse_duration spinbox to show current frequency (Hz)
            # Only update if spinbox is disabled (funscript mode)
            if self.pulse_duration and not self.pulse_duration.isEnabled():
                self.pulse_duration.blockSignals(True)
                # Clamp to current range to avoid pinning at boundaries
                clamped_value = max(self.pulse_duration.minimum(), 
                                   min(pulse.frequency, self.pulse_duration.maximum()))
                self.pulse_duration.setValue(clamped_value)
                self.pulse_duration.blockSignals(False)
                # Force visual update even if spinbox is disabled
                self.pulse_duration.repaint()

class PulseGraphContainer(QWidget):
    def __init__(self, window_seconds: settings.Setting, freq_min: QSpinBox, freq_max: QSpinBox, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Store frequency range controls
        self.freq_min = freq_min
        self.freq_max = freq_max

        # Initialize entries list to store CoyotePulse objects
        self.entries = []

        # Time window for stats display (in seconds)
        self.stats_window = window_seconds

        # Create layout
        self.layout = QVBoxLayout(self)

        # Create plot widget
        self.plot = PulseGraph(window_seconds, *args, **kwargs)
        self.layout.addWidget(self.plot)

        # Optional stats label managed by parent component
        self.stats_label: Optional[QLabel] = None

    def attach_stats_label(self, label: QLabel):
        self.stats_label = label
        self.stats_label.setText("Intensity: 0%")
        
    def get_frequency_range_text(self, entries) -> str:
        """Get the frequency range text from the given entries."""
        if not entries:
            return "N/A"
        frequencies = [entry.frequency for entry in entries]
        avg_frequency = sum(frequencies) / len(frequencies)
        min_freq = min(frequencies)
        max_freq = max(frequencies)
        
        # If min, max, and average are all the same, just show the single value
        if min_freq == max_freq == round(avg_frequency):
            return f"{int(avg_frequency)} Hz"
        # If min and max differ, show average with range
        return f"{avg_frequency:.0f} Hz ({min_freq} – {max_freq})"

    def format_intensity_text(self, intensities) -> str:
        """Format intensity text with smart range display."""
        if not intensities:
            return "N/A"
        avg_intensity = sum(intensities) / len(intensities)
        min_intensity = min(intensities)
        max_intensity = max(intensities)
        
        # If min, max, and average are all the same, just show the single value
        if min_intensity == max_intensity == round(avg_intensity):
            return f"{int(avg_intensity)}%"
        # If min and max differ, show average with range
        return f"{avg_intensity:.0f}% ({min_intensity} – {max_intensity})"
    
    def clean_old_entries(self):
        """Remove entries outside the time window"""
        current_time = time.time()
        stats_window = self.stats_window.get()
        self.entries = [e for e in self.entries if current_time - e.timestamp <= stats_window]

    def update_label_text(self):
        # Clean up old entries
        self.clean_old_entries()
        # Calculate stats using pulses from the time window
        recent_entries = self.entries
        # Get intensity range
        intensities = [entry.intensity for entry in recent_entries]
        intensity_text = self.format_intensity_text(intensities)
        if self.stats_label:
            self.stats_label.setText(f"Intensity: {intensity_text}")

    def add_pulse(self, frequency, intensity, duration, current_strength, channel_limit):
        # Calculate effective intensity after applying current strength
        effective_intensity = intensity * (current_strength / 100)
        
        # For zero intensity pulses, still create them but with zero intensity
        # This shows empty space in the graph
        
        # Create a CoyotePulse object
        pulse = CoyotePulse(
            frequency=frequency, 
            intensity=intensity,
            duration=duration
        )
        
        # Add timestamp for time-window filtering
        pulse.timestamp = time.time()
        
        # Store pulse data
        self.entries.append(pulse)
        
        self.update_label_text()
        
        # Update the plot - even zero intensity pulses are sent through for visualization
        self.plot.add_pulse(pulse, effective_intensity, channel_limit)

class PulseGraph(QWidget):
    def __init__(self, window_seconds: settings.Setting, parent=None):
        super().__init__(parent)
        self.setLayout(QVBoxLayout())
        
        self.view = QGraphicsView()
        self.scene = QGraphicsScene()
        self.view.setScene(self.scene)
        
        # Set background based on theme
        from qt_ui import settings as qt_settings
        dark_mode = qt_settings.dark_mode_enabled.get()
        if dark_mode:
            self.view.setBackgroundBrush(QColor("#2d2d2d"))
        else:
            self.view.setBackgroundBrush(QColor("#ffffff"))
        
        # Completely disable scrolling and user interaction
        self.view.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.view.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.view.setInteractive(True)  # Enable interaction for tooltips
        self.view.setDragMode(QGraphicsView.NoDrag)
        self.view.setTransformationAnchor(QGraphicsView.NoAnchor)
        self.view.setResizeAnchor(QGraphicsView.NoAnchor)
        self.view.setViewportUpdateMode(QGraphicsView.FullViewportUpdate)
        
        # Prevent wheel events
        self.view.wheelEvent = lambda event: None
        
        self.layout().addWidget(self.view)
        
        # Configuration for time window (in seconds)
        self.time_window = window_seconds
        
        # Store pulses for visualization
        self.pulses = []
        self.channel_limit = 200  # Default channel limit
        
        # Packet tracking for FIFO visualization
        self.current_packet_index = 0  # Which 4-pulse packet is currently active
        self.last_packet_time = 0     # When the last packet was received
        self.pulse_fingerprints = {}  # Track pulse fingerprints to avoid duplicates
        
        # Initialize the scene size
        self.updateSceneRect()

        self.timer = QTimer()
        self.timer.timeout.connect(self.refresh)
        self.timer.start(50)
        
        # Colors for visualization
        self.pulse_color = QColor(0, 255, 0, 200)  # Semi-transparent lime
        self.pulse_border_color = QColor("darkgreen")
        
        # Time scaling factor - how many pixels per ms of duration
        self.time_scale_factor = 0.5  # pixels per ms
        
        # Frequency range for color gradient mapping
        self.freq_min = 10  # Hz - default low frequency
        self.freq_max = 200  # Hz - default high frequency
    
    def resizeEvent(self, event):
        """Handle resize events by updating the scene rectangle"""
        super().resizeEvent(event)
        self.updateSceneRect()
        # Force a refresh after resize
        self.refresh()
    
    def updateSceneRect(self):
        """Update the scene rectangle to match the view size"""
        if self.view:
            width = self.view.viewport().width()
            height = self.view.viewport().height()
            self.view.setSceneRect(0, 0, width, height)
    
    def get_pulse_fingerprint(self, pulse: CoyotePulse) -> str:
        """Generate a fingerprint for a pulse to detect duplicates"""
        return f"{pulse.frequency}_{pulse.intensity}_{pulse.duration}"
    
    def get_color_for_frequency(self, frequency: float) -> QColor:
        """
        Calculate color based on frequency using green→yellow→red→purple gradient.
        1 Hz (green) → 30 Hz (green) → 70 Hz (yellow) → 100 Hz (red) → 200 Hz (purple)
        Always uses fixed range 1-200 Hz for color mapping.
        """
        # Fixed normalization range
        freq_min = 1
        freq_max = 200
        freq_range = freq_max - freq_min
        if freq_range <= 0:
            normalized = 0.5
        else:
            normalized = (frequency - freq_min) / freq_range
            normalized = max(0, min(1, normalized))  # Clamp to 0-1
        # Calculate normalized frequencies for key points
        # 20 Hz = (20-1)/(200-1) ≈ 0.095
        # 30 Hz = (30-1)/(200-1) ≈ 0.146
        # 70 Hz = (70-1)/(200-1) ≈ 0.346
        # 100 Hz = (100-1)/(200-1) ≈ 0.497
        if normalized <= 0.095:  # 1-20 Hz: Blue
            r = 0
            g = 100
            b = 255
        elif normalized <= 0.146:  # 20-30 Hz: Blue to Green
            t = (normalized - 0.095) / (0.146 - 0.095)
            r = 0
            g = int(100 + (155 * t))
            b = int(255 - (255 * t))
        elif normalized <= 0.346:  # 30-70 Hz: Green to Deep Yellow
            t = (normalized - 0.146) / (0.346 - 0.146)
            r = int(255 * t)
            g = int(255 - 80 * t)  # 255→175 (deeper yellow)
            b = 0
        else:  # 70-200 Hz: Deep Yellow/Red to Purple
            t = (normalized - 0.346) / (1.0 - 0.346)
            r = 255
            g = int(175 * max(0, 1 - t * 1.3))  # Green decreases faster to 0
            b = int(150 * t)  # Blue increases from 0 to 150 (more purple)
        return QColor(r, g, b, 200)
    
    def clean_old_pulses(self):
        """Remove pulses outside the time window"""
        current_time = time.time()
        time_window = self.time_window.get()
        self.pulses = [p for p in self.pulses if current_time - p.timestamp <= time_window]
        
        # Also clean up old fingerprints
        for fingerprint, timestamp in list(self.pulse_fingerprints.items()):
            if current_time - timestamp > time_window:
                self.pulse_fingerprints.pop(fingerprint)

    def add_pulse(self, pulse: CoyotePulse, applied_intensity: float, channel_limit: int):
        """Add a new pulse to the visualization"""
        # Don't skip zero intensity pulses, but display them differently
        self.channel_limit = channel_limit
        
        # Update frequency range based on actual pulses (keep min adaptive, keep max fixed at 200)
        if pulse.frequency > 0:
            self.freq_min = min(self.freq_min, pulse.frequency)
            # Don't update freq_max - keep it fixed at 200 Hz for consistent red mapping
        
        # Show every pulse - no deduplication
        current_time = time.time()
        
        # Store the CoyotePulse with additional metadata
        pulse_copy = CoyotePulse(
            frequency=pulse.frequency,
            intensity=pulse.intensity,
            duration=pulse.duration
        )
        
        # Add additional attributes to the pulse
        pulse_copy.applied_intensity = applied_intensity
        pulse_copy.packet_index = self.current_packet_index
        pulse_copy.timestamp = current_time
        
        # Add the pulse
        self.pulses.append(pulse_copy)
        
        # Clean up old pulses that are outside our time window
        self.clean_old_pulses()

    def refresh(self):
        """Redraw the pulse visualization"""
        self.scene.clear()
        
        # Always ensure we're using the current viewport size
        self.updateSceneRect()
        
        width = self.view.viewport().width()
        height = self.view.viewport().height()
        
        # Clean up old pulses again (in case the timer fired without any new pulses added)
        self.clean_old_pulses()
        
        if not self.pulses:
            return
        
        # Sort pulses by timestamp so they display in chronological order
        sorted_pulses = sorted(self.pulses, key=lambda p: p.timestamp)
        
        # Use channel_limit for scaling, do not average or smooth
        scale_max = self.channel_limit
        
        # Get the time span of the visible pulses
        now = time.time()
        time_window = self.time_window.get()
        oldest_time = now - time_window
        newest_time = now
        time_span_sec = time_window
        
        # Calculate total width available for all pulses
        usable_width = width - 10  # Leave small margin on right side
        
        # Scale based on the time window, not the pulse count
        # This ensures consistent scaling regardless of pulse frequency
        time_scale = usable_width / (time_span_sec * 1000)  # Convert to ms
        
        # Group pulses by packet for continuous display
        pulses_by_packet = {}
        for pulse in sorted_pulses:
            packet_idx = pulse.packet_index
            if packet_idx not in pulses_by_packet:
                pulses_by_packet[packet_idx] = []
            pulses_by_packet[packet_idx].append(pulse)
        
        # Get sorted list of packet indices
        packet_indices = sorted(pulses_by_packet.keys())
        
        # Draw each packet's pulses as a continuous sequence
        for i, packet_idx in enumerate(packet_indices):
            packet_pulses = sorted(pulses_by_packet[packet_idx], key=lambda p: p.timestamp)
            
            # Determine the time range this packet covers
            if i < len(packet_indices) - 1:
                # This packet runs until the next packet starts
                next_packet_idx = packet_indices[i + 1]
                next_packet_start = min(p.timestamp for p in pulses_by_packet[next_packet_idx])
                packet_end_time = next_packet_start
            else:
                # This is the last packet, it runs until now
                packet_end_time = now
            
            # Calculate packet colors
            packet_color = QColor(0, 255, 0, 200) if packet_idx % 2 == 0 else QColor(100, 255, 100, 200)
            
            # Draw each pulse in this packet
            for j, pulse in enumerate(packet_pulses):
                # Calculate time positions
                pulse_start_time = pulse.timestamp
                
                # For continuity, calculate the end time:
                if j < len(packet_pulses) - 1:
                    # If there's another pulse in this packet, it extends to that pulse
                    pulse_end_time = packet_pulses[j + 1].timestamp
                else:
                    # If this is the last pulse in the packet, it extends to the packet end
                    pulse_end_time = packet_end_time
                
                # Ensure we're within the visible time window
                pulse_start_time = max(pulse_start_time, oldest_time)
                pulse_end_time = min(pulse_end_time, newest_time)
                
                # Calculate positions and dimensions
                time_position_start = (pulse_start_time - oldest_time) / time_span_sec
                time_position_end = (pulse_end_time - oldest_time) / time_span_sec
                
                x_start = 5 + (time_position_start * usable_width)
                x_end = 5 + (time_position_end * usable_width)
                rect_width = max(3, min(6, x_end - x_start))  # Keep bars narrow (3-6 pixels)
                
                # Calculate height based on intensity (always define rect_height)
                height_ratio = pulse.applied_intensity / scale_max if scale_max > 0 else 0
                rect_height = height * height_ratio
                
                # Get color based on frequency
                pulse_color = self.get_color_for_frequency(pulse.frequency)

                # For zero-intensity pulses, still show something to indicate timing
                if pulse.applied_intensity <= 0:
                    # Draw a thin line or empty rectangle to show timing without intensity
                    empty_rect = QGraphicsRectItem(
                        x_start, height - 2,  # Just a thin line at the bottom
                        rect_width, 2
                    )
                    empty_rect.setPen(QPen(QColor(100, 100, 100, 100), 1))  # Very light gray
                    empty_rect.setBrush(QBrush(QColor(100, 100, 100, 50)))  # Almost transparent
                    self.scene.addItem(empty_rect)
                else:
                    # Create rectangle for the pulse
                    rect = PulseRectItem(
                        x_start, height - rect_height,  # x, y (bottom-aligned)
                        rect_width, rect_height,        # width, height
                        pulse                           # pass pulse data for tooltip
                    )
                    
                    rect.setPen(QPen(self.pulse_border_color, 1))
                    rect.setBrush(QBrush(pulse_color))
                    
                    # Add rectangle to scene
                    self.scene.addItem(rect)
                
                # Frequency tick marks removed as color already encodes frequency

class PulseRectItem(QGraphicsRectItem):
    def __init__(self, x, y, width, height, pulse):
        super().__init__(x, y, width, height)
        self.pulse = pulse
        self.setAcceptHoverEvents(True)
        
    def hoverEnterEvent(self, event):
        # Show tooltip with pulse information
        freq = self.pulse.frequency
        intensity = self.pulse.intensity
        duration = self.pulse.duration
        
        tooltip_text = f"Frequency: {freq} Hz\nIntensity: {intensity}%\nDuration: {duration} ms"
        QToolTip.showText(event.screenPos(), tooltip_text)
        
        # Change appearance on hover
        current_pen = self.pen()
        current_pen.setWidth(2)  # Make border thicker
        self.setPen(current_pen)
        
    def hoverLeaveEvent(self, event):
        # Restore original appearance
        current_pen = self.pen()
        current_pen.setWidth(1)  # Restore original border width
        self.setPen(current_pen)
        
