import os
import sys
from PySide6 import QtGui


def load_icon_theme(window, settings_module, logger):
    icon_theme = settings_module.icon_theme.get()

    base_path = getattr(
        sys,
        '_MEIPASS',
        os.path.join(os.path.dirname(os.path.abspath(__file__)), os.path.pardir),
    )
    icons_dir = os.path.join(base_path, 'resources', 'icons')
    icon_path = os.path.join(icons_dir, f'{icon_theme}.png')

    if os.path.exists(icon_path):
        icon = QtGui.QIcon()
        icon.addPixmap(QtGui.QPixmap(icon_path), QtGui.QIcon.Mode.Normal, QtGui.QIcon.State.Off)
        window.setWindowIcon(icon)
    else:
        logger.warning(f"Icon theme '{icon_theme}' not found at {icon_path}, using default")


def update_taskbar_icon_windows_api(window, settings_module, logger):
    try:
        import ctypes
        import platform

        if platform.system() != 'Windows':
            return

        hwnd = int(window.winId())
        icon_theme = settings_module.icon_theme.get()
        ico_path = os.path.join(
            os.path.dirname(__file__),
            '..', 'resources',
            f'{icon_theme}.ico'
        )

        if not os.path.exists(ico_path):
            logger.debug(f"Icon file not found: {ico_path}")
            return

        WM_SETICON = 0x0080
        ICON_SMALL = 0
        ICON_BIG = 1
        IMAGE_ICON = 1
        LR_LOADFROMFILE = 0x00000010

        user32 = ctypes.windll.user32

        h_icon = user32.LoadImageW(
            None,
            os.path.abspath(ico_path),
            IMAGE_ICON,
            0,
            0,
            LR_LOADFROMFILE
        )

        if h_icon == 0:
            logger.debug(f"Failed to load icon: {ico_path}")
            return

        user32.SendMessageW(hwnd, WM_SETICON, ICON_SMALL, h_icon)
        user32.SendMessageW(hwnd, WM_SETICON, ICON_BIG, h_icon)

        logger.info(f"Updated taskbar icon to: {icon_theme}")

    except Exception as e:
        logger.debug(f"Failed to update taskbar icon: {e}")
