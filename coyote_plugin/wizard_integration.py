from enum import Enum

from coyote_plugin.device import constants as coyote_constants
from qt_ui.device_wizard.coyote_waveform_select import WizardPageCoyoteWaveformSelect
from qt_ui.device_wizard.enums import DeviceConfiguration, DeviceType, WaveformType


class CoyoteWizardPages(Enum):
    PAGE_COYOTE_WAVEFORM = 7


class CoyoteWizardPlugin:
    def register_pages(self, wizard):
        wizard.page_coyote_waveform_select = WizardPageCoyoteWaveformSelect()
        wizard.page_coyote_waveform_select.setFinalPage(True)
        wizard.setPage(CoyoteWizardPages.PAGE_COYOTE_WAVEFORM.value, wizard.page_coyote_waveform_select)

        if hasattr(wizard.page_device_type, 'coyote_radio'):
            wizard.page_device_type.coyote_radio.toggled.connect(wizard.page_device_type.completeChanged)

    def next_id(self, wizard, current_id):
        from qt_ui.device_wizard.wizard import WizardPage

        if current_id == WizardPage.Page_device.value:
            if hasattr(wizard.page_device_type, 'coyote_radio') and wizard.page_device_type.coyote_radio.isChecked():
                return CoyoteWizardPages.PAGE_COYOTE_WAVEFORM.value
        return None

    def get_configuration(self, wizard):
        if not hasattr(wizard.page_device_type, 'coyote_radio'):
            return None
        if not wizard.page_device_type.coyote_radio.isChecked():
            return None

        if wizard.page_coyote_waveform_select.is_two_channel():
            device_type = DeviceType.COYOTE_TWO_CHANNEL
        else:
            device_type = DeviceType.COYOTE_THREE_PHASE

        return DeviceConfiguration(
            device_type,
            WaveformType.PULSE_BASED,
            coyote_constants.HARDWARE_MIN_FREQ_HZ,
            coyote_constants.HARDWARE_MAX_FREQ_HZ,
            0.0,
        )

    def set_configuration(self, wizard, config):
        if not hasattr(wizard.page_device_type, 'coyote_radio'):
            return
        if config.device_type == DeviceType.COYOTE_THREE_PHASE:
            wizard.page_device_type.coyote_radio.setChecked(True)
            wizard.page_coyote_waveform_select.three_phase_radio.setChecked(True)
        if config.device_type == DeviceType.COYOTE_TWO_CHANNEL:
            wizard.page_device_type.coyote_radio.setChecked(True)
            wizard.page_coyote_waveform_select.two_channel_radio.setChecked(True)


def register_coyote_wizard_plugin(register_plugin):
    register_plugin(CoyoteWizardPlugin())
