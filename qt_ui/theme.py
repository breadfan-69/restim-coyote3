"""Theme management for dark and light modes"""
from PySide6.QtWidgets import QApplication, QGraphicsView
from PySide6.QtGui import QColor
from qt_ui import settings

# Import resources to register Qt resource paths
try:
    from qt_ui import restim_rc  # noqa: F401
except ImportError:
    pass


# Light mode stylesheet - matches original diglet48 styling (mostly default)
LIGHT_STYLESHEET = """
/* Light mode uses mostly default Qt styling */
QMainWindow, QWidget {
    background-color: #ffffff;
    color: #000000;
}

QFrame {
    background-color: #ffffff;
    color: #000000;
}

QMenuBar {
    background-color: #f0f0f0;
    color: #000000;
}

QMenuBar::item:selected {
    background-color: #e0e0e0;
}

QMenu {
    background-color: #ffffff;
    color: #000000;
    border: 1px solid #cccccc;
}

QMenu::item:selected {
    background-color: #0d47a1;
    color: #ffffff;
}

QPushButton {
    background-color: #0d47a1;
    color: #ffffff;
    border: none;
    border-radius: 4px;
    padding: 5px 15px;
}

QPushButton:hover {
    background-color: #0d3f7f;
}

QLineEdit {
    background-color: #ffffff;
    color: #000000;
    border: 1px solid #cccccc;
    border-radius: 4px;
    padding: 5px;
}

QLineEdit:focus {
    border: 1px solid #0d47a1;
}

QSpinBox, QDoubleSpinBox {
    background-color: #ffffff;
    color: #000000;
    border: 1px solid #cccccc;
    border-radius: 4px;
    padding: 5px;
}

QSpinBox::up-button, QDoubleSpinBox::up-button,
QSpinBox::down-button, QDoubleSpinBox::down-button {
    background-color: #f0f0f0;
    border: 1px solid #cccccc;
    width: 20px;
}

QSpinBox::up-button:hover, QDoubleSpinBox::up-button:hover,
QSpinBox::down-button:hover, QDoubleSpinBox::down-button:hover {
    background-color: #e0e0e0;
}

QSpinBox::up-arrow, QDoubleSpinBox::up-arrow {
    image: url(:/restim/arrow-up-light.svg);
    width: 16px;
    height: 16px;
}

QSpinBox::down-arrow, QDoubleSpinBox::down-arrow {
    image: url(:/restim/arrow-down-light.svg);
    width: 16px;
    height: 16px;
}

QSpinBox:focus, QDoubleSpinBox:focus {
    border: 1px solid #0d47a1;
}

QCheckBox {
    color: #000000;
}

QCheckBox::indicator {
    width: 18px;
    height: 18px;
}

QCheckBox::indicator:unchecked {
    image: url(:/restim/checkbox-unchecked.svg);
}

QCheckBox::indicator:checked {
    image: url(:/restim/checkbox-checked.svg);
}

QRadioButton {
    color: #000000;
}

QRadioButton::indicator {
    width: 18px;
    height: 18px;
}

QRadioButton::indicator:unchecked {
    background-color: #ffffff;
    border: 2px solid #cccccc;
    border-radius: 9px;
}

QRadioButton::indicator:checked {
    background-color: #0d47a1;
    border: 2px solid #0d47a1;
    border-radius: 9px;
}

QSlider::groove:horizontal {
    background-color: #e0e0e0;
    height: 8px;
    border-radius: 4px;
}

QSlider::handle:horizontal {
    background-color: #0d47a1;
    width: 18px;
    margin: -5px 0;
    border-radius: 9px;
}

QComboBox {
    background-color: #ffffff;
    color: #000000;
    border: 1px solid #cccccc;
    border-radius: 4px;
    padding: 5px;
}

QComboBox::drop-down {
    background-color: #f0f0f0;
    border: none;
    width: 20px;
}

QComboBox::down-arrow {
    image: url(:/restim/arrow-down-light.svg);
    width: 16px;
    height: 16px;
}

QTabBar::tab {
    background-color: #f0f0f0;
    color: #000000;
    padding: 5px 15px;
    border: 1px solid #cccccc;
    border-bottom: none;
}

QTabBar::tab:selected {
    background-color: #ffffff;
    color: #000000;
}

QTabWidget::pane {
    border: 1px solid #cccccc;
}

QGroupBox {
    color: #000000;
    border: 1px solid #cccccc;
    border-radius: 4px;
    margin-top: 10px;
    padding-top: 10px;
}

QGroupBox::title {
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 3px 0 3px;
}
"""

DARK_STYLESHEET = """
/* Main Window and Widgets */
QMainWindow, QWidget {
    background-color: #3d3d3d;
    color: #e0e0e0;
}

QFrame {
    background-color: #3d3d3d;
    color: #e0e0e0;
}

/* Menu Bar */
QMenuBar {
    background-color: #4d4d4d;
    color: #e0e0e0;
    border-bottom: 1px solid #5d5d5d;
}

QMenuBar::item:selected {
    background-color: #5d5d5d;
}

/* Menus */
QMenu {
    background-color: #4d4d4d;
    color: #e0e0e0;
    border: 1px solid #5d5d5d;
}

QMenu::item:selected {
    background-color: #0d47a1;
    color: #ffffff;
}

/* Buttons */
QPushButton {
    background-color: #0d47a1;
    color: #ffffff;
    border: none;
    border-radius: 4px;
    padding: 5px 15px;
}

QPushButton:hover {
    background-color: #1565c0;
}

QPushButton:pressed {
    background-color: #0c3f8f;
}

QPushButton:disabled {
    background-color: #424242;
    color: #757575;
}

/* Labels */
QLabel {
    color: #e0e0e0;
}

/* Line Edit */
QLineEdit {
    background-color: #4d4d4d;
    color: #e0e0e0;
    border: 1px solid #5d5d5d;
    border-radius: 4px;
    padding: 5px;
}

QLineEdit:focus {
    border: 1px solid #0d47a1;
}

/* Spin Box */
QSpinBox, QDoubleSpinBox {
    background-color: #4d4d4d;
    color: #e0e0e0;
    border: 1px solid #5d5d5d;
    border-radius: 4px;
    padding: 5px;
}

QSpinBox::up-button, QDoubleSpinBox::up-button,
QSpinBox::down-button, QDoubleSpinBox::down-button {
    background-color: #3d3d3d;
    border: 1px solid #2d2d2d;
    width: 20px;
}

QSpinBox::up-button:hover, QDoubleSpinBox::up-button:hover,
QSpinBox::down-button:hover, QDoubleSpinBox::down-button:hover {
    background-color: #4d4d4d;
}

QSpinBox::up-arrow, QDoubleSpinBox::up-arrow {
    image: url(:/restim/arrow-up.svg);
    width: 16px;
    height: 16px;
}

QSpinBox::down-arrow, QDoubleSpinBox::down-arrow {
    image: url(:/restim/arrow-down.svg);
    width: 16px;
    height: 16px;
}

QSpinBox:focus, QDoubleSpinBox:focus {
    border: 1px solid #0d47a1;
}

/* Sliders */
QSlider::groove:horizontal {
    background-color: #5d5d5d;
    height: 8px;
    border-radius: 4px;
}

QSlider::handle:horizontal {
    background-color: #0d47a1;
    width: 18px;
    margin: -5px 0;
    border-radius: 9px;
}

QSlider::handle:horizontal:hover {
    background-color: #1565c0;
}

/* ComboBox */
QComboBox {
    background-color: #4d4d4d;
    color: #e0e0e0;
    border: 1px solid #5d5d5d;
    border-radius: 4px;
    padding: 5px;
}

QComboBox:focus {
    border: 1px solid #0d47a1;
}

QComboBox::drop-down {
    border: none;
    width: 20px;
}

QComboBox::down-arrow {
    image: url(:/restim/arrow-down.svg);
    width: 16px;
    height: 16px;
}

/* CheckBox and RadioButton */
QCheckBox, QRadioButton {
    color: #e0e0e0;
}

QCheckBox::indicator, QRadioButton::indicator {
    width: 18px;
    height: 18px;
}

QCheckBox::indicator:unchecked, QRadioButton::indicator:unchecked {
    image: url(:/restim/checkbox-unchecked-dark.svg);
}

QCheckBox::indicator:checked, QRadioButton::indicator:checked {
    image: url(:/restim/checkbox-checked-dark.svg);
}

/* GroupBox */
QGroupBox {
    color: #e0e0e0;
    border: 1px solid #5d5d5d;
    border-radius: 4px;
    margin-top: 10px;
    padding-top: 10px;
}

QGroupBox::title {
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 3px 0 3px;
}

/* Tabs */
QTabBar::tab {
    background-color: #4d4d4d;
    color: #e0e0e0;
    border: 1px solid #5d5d5d;
    padding: 8px 20px;
}

QTabBar::tab:selected {
    background-color: #0d47a1;
    color: #ffffff;
}

QTabWidget::pane {
    border: 1px solid #5d5d5d;
}

/* ScrollBar */
QScrollBar:vertical {
    background-color: #3d3d3d;
    width: 12px;
    border: none;
}

QScrollBar::handle:vertical {
    background-color: #626262;
    border-radius: 6px;
    min-height: 20px;
}

QScrollBar::handle:vertical:hover {
    background-color: #727272;
}

QScrollBar:horizontal {
    background-color: #3d3d3d;
    height: 12px;
    border: none;
}

QScrollBar::handle:horizontal {
    background-color: #626262;
    border-radius: 6px;
    min-width: 20px;
}

QScrollBar::handle:horizontal:hover {
    background-color: #727272;
}

/* ProgressBar */
QProgressBar {
    background-color: #4d4d4d;
    color: #e0e0e0;
    border: 1px solid #5d5d5d;
    border-radius: 4px;
    text-align: center;
}

QProgressBar::chunk {
    background-color: #0d47a1;
    border-radius: 3px;
}

/* Text Edit */
QTextEdit, QPlainTextEdit {
    background-color: #4d4d4d;
    color: #e0e0e0;
    border: 1px solid #5d5d5d;
    border-radius: 4px;
}

/* List View and Table View */
QListView, QTableView, QTreeView {
    background-color: #4d4d4d;
    color: #e0e0e0;
    border: 1px solid #5d5d5d;
    gridline-color: #5d5d5d;
}

QListView::item:selected, QTableView::item:selected, QTreeView::item:selected {
    background-color: #0d47a1;
}

QHeaderView::section {
    background-color: #4d4d4d;
    color: #e0e0e0;
    padding: 5px;
    border: 1px solid #5d5d5d;
}

/* Dialogs */
QDialog {
    background-color: #3d3d3d;
    color: #e0e0e0;
}

QFileDialog, QColorDialog {
    background-color: #1e1e1e;
}
"""


def apply_theme(app: QApplication, dark_mode: bool = None):
    """Apply theme to the application
    
    Args:
        app: QApplication instance
        dark_mode: If True, apply dark mode. If False, apply light mode. If None, use setting.
    """
    if dark_mode is None:
        dark_mode = settings.dark_mode_enabled.get()
    
    app.setStyle('Fusion')
    
    if dark_mode:
        app.setStyleSheet(DARK_STYLESHEET)
    else:
        app.setStyleSheet(LIGHT_STYLESHEET)
    
    settings.dark_mode_enabled.set(dark_mode)
    
    # Update graphics views
    update_graphics_views(app, dark_mode)


def toggle_dark_mode(app: QApplication):
    """Toggle dark mode on/off"""
    current = settings.dark_mode_enabled.get()
    apply_theme(app, not current)


def update_graphics_views(app: QApplication, dark_mode: bool = None):
    """Update all graphics views in the application to match theme"""
    if dark_mode is None:
        dark_mode = settings.dark_mode_enabled.get()
    
    # Get all widgets and update those with theme support
    for widget in app.allWidgets():
        try:
            # Check if widget has a set_theme method (our custom widgets)
            if hasattr(widget, 'set_theme') and callable(getattr(widget, 'set_theme')):
                widget.set_theme(dark_mode)
            # Also update standard QGraphicsView widgets
            elif isinstance(widget, QGraphicsView):
                if dark_mode:
                    widget.setBackgroundBrush(QColor("#2d2d2d"))
                else:
                    widget.setBackgroundBrush(QColor("#ffffff"))
                widget.update()
        except Exception as e:
            # Silently ignore errors updating specific widgets
            pass


