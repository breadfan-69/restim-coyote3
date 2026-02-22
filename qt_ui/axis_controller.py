from __future__ import unicode_literals
import time
from typing import Optional

from PySide6 import QtCore, QtWidgets

from stim_math.axis import AbstractAxis, WriteProtectedAxis


class AxisController(QtCore.QObject):
    def __init__(self, control: QtWidgets.QDoubleSpinBox):
        super(AxisController, self).__init__()
        self.control = control
        self.timer = QtCore.QTimer()
        self.timer.setInterval(16)  # ~60Hz update rate for responsive UI
        self.script_axis: Optional[AbstractAxis] = None
        self.internal_axis: Optional[AbstractAxis] = None
        self._updating_control = False
        self._external_control_active = False
        self._last_external_axis_update_time = 0.0
        self._external_control_timeout_seconds = 1.0
        self.timer.timeout.connect(self.timeout)
        self.control.valueChanged.connect(self.value_changed)
        self.last_user_entered_value = self.get_control_value()

    def timeout(self):
        axis = self.axis
        if axis is None:
            return

        now = time.time()
        value = axis.interpolate(now)
        if value != self.get_control_value():
            # Internal axis changed without direct user input in this control.
            # Treat as external control (e.g. TCode) and lock editing while it is active.
            if self.internal_axis is not None and not self._updating_control:
                self._last_external_axis_update_time = now
                if not self._external_control_active and self.control.isEnabled():
                    self._external_control_active = True
                    self.control.setEnabled(False)

            self._updating_control = True
            try:
                self.set_control_value(value)
            finally:
                self._updating_control = False

        if self._external_control_active and (now - self._last_external_axis_update_time) > self._external_control_timeout_seconds:
            # External stream became idle; return control to the user.
            self._external_control_active = False
            if self.script_axis is None:
                self.control.setEnabled(True)

    def value_changed(self):
        # TODO: what happens on tcode control?
        if self._updating_control:
            return

        if self.internal_axis is not None:    # if: not funscript control
            self.internal_axis.add(self.get_control_value())
            self.last_user_entered_value = self.get_control_value()
            self.modified_by_user.emit()

    def set_control_value(self, value):
        self.control.setValue(value)

    def get_control_value(self):
        return self.control.value()

    def link_axis(self, axis):
        if isinstance(axis, WriteProtectedAxis):    # HACK: is funcript axis?
            self.link_to_funscript(axis)
        else:
            self.link_to_internal_axis(axis)

    def link_to_funscript(self, script_axis):
        """
        Behavior: the control gets disables. Periodically, the value shown in the control updates.
        """
        self.control.setEnabled(False)
        self.script_axis = script_axis
        self.internal_axis = None
        self._external_control_active = False
        self._last_external_axis_update_time = 0.0
        self.timer.start()

    def link_to_internal_axis(self, internal_axis):
        """
        Behavior: control enabled. Whenever user modifies the control, value is inserted in axis.
        """
        self.script_axis = None
        self.internal_axis = internal_axis
        self._external_control_active = False
        self._last_external_axis_update_time = 0.0
        if self.internal_axis is not None:
            self.set_control_value(self.internal_axis.interpolate(time.time()))
        self.control.setEnabled(True)
        self.timer.start()

    @property
    def axis(self) -> Optional[AbstractAxis]:
        """Get the active axis (script_axis if available, otherwise internal_axis)"""
        if self.script_axis:
            return self.script_axis
        return self.internal_axis

    modified_by_user = QtCore.Signal()


class PercentAxisController(AxisController):
    def __init__(self, control):
        super(PercentAxisController, self).__init__(control)

    def set_control_value(self, value):
        self.control.setValue(value * 100)

    def get_control_value(self):
        return self.control.value() / 100


class GroupboxAxisController(QtCore.QObject):
    def __init__(self, control: QtWidgets.QGroupBox):
        super(GroupboxAxisController, self).__init__()
        self.control = control
        self.script_axis: Optional[AbstractAxis] = None
        self.internal_axis: Optional[AbstractAxis] = None
        self.control.toggled.connect(self.value_changed)
        self.last_user_entered_value = self.control.isChecked()

    def value_changed(self):
        # TODO: what happens on tcode control?
        if self.internal_axis is not None:    # if: not funscript control
            self.internal_axis.add(self.control.isChecked())
            self.last_user_entered_value = self.control.isChecked()
            self.modified_by_user.emit()

    def link_axis(self, axis):
        if isinstance(axis, WriteProtectedAxis):    # HACK: is funcript axis?
            self.link_to_funscript(axis)
        else:
            self.link_to_internal_axis(axis)

    def link_to_funscript(self, script_axis):
        """
        Behavior: the control gets disables. Periodically, the value shown in the control updates.
        """
        self.internal_axis = None
        self.control.setCheckable(False)
        self.script_axis = script_axis

    def link_to_internal_axis(self, internal_axis):
        """
        Behavior: control enabled. Whenever user modifies the control, value is inserted in axis.
        """
        self.script_axis = None
        self.internal_axis = None
        self.control.setCheckable(True)
        self.control.setChecked(self.last_user_entered_value)
        self.internal_axis = internal_axis

    modified_by_user = QtCore.Signal()
