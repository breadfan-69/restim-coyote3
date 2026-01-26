from PySide6.QtWidgets import QWizardPage

from qt_ui.device_wizard.coyote_waveform_select_ui import Ui_WizardPageCoyote


class WizardPageCoyoteWaveformSelect(QWizardPage, Ui_WizardPageCoyote):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setupUi(self)

        self.three_phase_radio.toggled.connect(self.completeChanged)
        self.two_channel_radio.toggled.connect(self.completeChanged)

    def isComplete(self) -> bool:
        return any([
            self.three_phase_radio.isChecked() and self.three_phase_radio.isEnabled(),
            self.two_channel_radio.isChecked() and self.two_channel_radio.isEnabled(),
        ])

    def is_three_phase(self) -> bool:
        """Check if Simulated Three-Phase mode is selected"""
        return self.three_phase_radio.isChecked()

    def is_two_channel(self) -> bool:
        """Check if 2-Channel mode is selected"""
        return self.two_channel_radio.isChecked()
