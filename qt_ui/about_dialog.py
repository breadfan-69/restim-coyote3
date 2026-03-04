import logging
from PySide6.QtWidgets import QDialog

from qt_ui.about_dialog_ui import Ui_AboutDialog
from version import VERSION

logger = logging.getLogger('restim.bake_audio')

class AboutDialog(QDialog, Ui_AboutDialog):
    def __init__(self, parent):
        super().__init__(parent)

        self.setupUi(self)

        self.label.setText(
            f"""
<html>
  <head/>
  <body>
    <p><span style=\" font-size:18pt; font-weight:700;\">Restim - Coyote3</span></p>
    <p>version: {VERSION}</p>
    <p>-Coyote Three-Phase algorithm by Diglet48</p>
    <p>-Coyote Two-Channel algorithm by voltmouse69</p>
    <p>Latest version:<br/>
      <a href=\"https://github.com/breadfan-69/restim-coyote3/releases\">https://github.com/breadfan-69/restim-coyote3/releases</a>
    </p>
    <p>Based on:<br/>
      <a href=\"https://github.com/voltmouse69/restim\">https://github.com/voltmouse69/restim</a><br/>
      <a href=\"https://github.com/diglet48/restim\">https://github.com/diglet48/restim</a>
    </p>
    <p>Wiki:<br/>
      <a href=\"https://github.com/diglet48/restim/wiki\">https://github.com/diglet48/restim/wiki</a>
    </p>
  </body>
</html>
            """
        )
        self.label.setOpenExternalLinks(True)