from PySide6.QtWidgets import QWizardPage

from qt_ui.device_wizard.safety_limits_ui import Ui_WizardPageSafetyLimits


class WizardPageSafetyLimits(QWizardPage, Ui_WizardPageSafetyLimits):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setupUi(self)

        self.min_frequency_spinbox.setRange(500, 2000)
        self.max_frequency_spinbox.setRange(500, 2000)
        self.min_frequency_spinbox.setValue(500)
        self.max_frequency_spinbox.setValue(2000)

    def validatePage(self) -> bool:
        return self.min_frequency_spinbox.value() < self.max_frequency_spinbox.value()