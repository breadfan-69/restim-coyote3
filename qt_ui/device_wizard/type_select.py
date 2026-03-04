from PySide6.QtWidgets import QWizardPage

from qt_ui.device_wizard.type_select_ui import Ui_WizardPageDeviceType


class WizardPageDeviceType(QWizardPage, Ui_WizardPageDeviceType):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setupUi(self)

        self.audio_based_radio.setChecked(True)

        self._device_type_radios = [
            self.audio_based_radio,
            self.focstim_radio,
            self.neostim_radio,
        ]

        if hasattr(self, 'coyote_radio'):
            self._device_type_radios.append(self.coyote_radio)

        for radio in self._device_type_radios:
            radio.toggled.connect(self.completeChanged)

    def isComplete(self) -> bool:
        return any(radio.isChecked() for radio in self._device_type_radios)
