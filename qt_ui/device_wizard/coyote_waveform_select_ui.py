# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'coyote_waveform_select.ui'
##
## Created by: Qt User Interface Compiler version 6.10.1
##
## WARNING! All changes made in this file will be lost when recompiling UI file!
################################################################################

from PySide6.QtCore import (QCoreApplication, QDate, QDateTime, QLocale,
    QMetaObject, QObject, QPoint, QRect,
    QSize, QTime, QUrl, Qt)
from PySide6.QtGui import (QBrush, QColor, QConicalGradient, QCursor,
    QFont, QFontDatabase, QGradient, QIcon,
    QImage, QKeySequence, QLinearGradient, QPainter,
    QPalette, QPixmap, QRadialGradient, QTransform)
from PySide6.QtWidgets import (QApplication, QLabel, QRadioButton, QSizePolicy,
    QSpacerItem, QVBoxLayout, QWidget, QWizardPage)

class Ui_WizardPageCoyote(object):
    def setupUi(self, WizardPageCoyote):
        if not WizardPageCoyote.objectName():
            WizardPageCoyote.setObjectName(u"WizardPageCoyote")
        WizardPageCoyote.resize(611, 497)
        self.verticalLayout = QVBoxLayout(WizardPageCoyote)
        self.verticalLayout.setObjectName(u"verticalLayout")
        self.three_phase_radio = QRadioButton(WizardPageCoyote)
        self.three_phase_radio.setObjectName(u"three_phase_radio")

        self.verticalLayout.addWidget(self.three_phase_radio)

        self.label = QLabel(WizardPageCoyote)
        self.label.setObjectName(u"label")
        self.label.setWordWrap(True)

        self.verticalLayout.addWidget(self.label)

        self.verticalSpacer = QSpacerItem(20, 40, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)

        self.verticalLayout.addItem(self.verticalSpacer)

        self.two_channel_radio = QRadioButton(WizardPageCoyote)
        self.two_channel_radio.setObjectName(u"two_channel_radio")

        self.verticalLayout.addWidget(self.two_channel_radio)

        self.label_2 = QLabel(WizardPageCoyote)
        self.label_2.setObjectName(u"label_2")
        self.label_2.setWordWrap(True)

        self.verticalLayout.addWidget(self.label_2)

        self.verticalSpacer_2 = QSpacerItem(20, 40, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)

        self.verticalLayout.addItem(self.verticalSpacer_2)


        self.retranslateUi(WizardPageCoyote)

        QMetaObject.connectSlotsByName(WizardPageCoyote)
    # setupUi

    def retranslateUi(self, WizardPageCoyote):
        WizardPageCoyote.setWindowTitle(QCoreApplication.translate("WizardPageCoyote", u"WizardPage", None))
        self.three_phase_radio.setText(QCoreApplication.translate("WizardPageCoyote", u"Simulated Three-Phase", None))
        self.label.setText(QCoreApplication.translate("WizardPageCoyote", u"<html><head/><body>\n"
"      <p>A = left<br/>B = right<br/>C = neutral</p>\n"
"      <p>Connect A- and B- to a shared common electrode (e.g. a conductive rubber loop).</p>\n"
"      </body></html>", None))
        self.two_channel_radio.setText(QCoreApplication.translate("WizardPageCoyote", u"2-Channel", None))
        self.label_2.setText(QCoreApplication.translate("WizardPageCoyote", u"Place channel electrodes in alternate order, aka soft threephase", None))
    # retranslateUi

