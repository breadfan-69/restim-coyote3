# -*- mode: python ; coding: utf-8 -*-

from PyInstaller.utils.hooks import collect_data_files


a = Analysis(
    ['restim.py'],
    pathex=[],
    binaries=[],
    datas=[('resources', 'resources'), *collect_data_files('ahrs')],
    hiddenimports=[
        'pyqtgraph',
        'ahrs',
        'ahrs.common.orientation',
        'ahrs.common.quaternion',
        'ahrs.filters',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'numba',
        'llvmlite',
        'numba.*',
        'llvmlite.*',
        'scipy',
        'scipy.*',
        'matplotlib.tests',
        'numpy.tests',
        'PIL.tests',
        'PIL.AvifImagePlugin',
        'PIL._avif',
        'PySide6.QtQml',
        'PySide6.QtQuick',
        'PySide6.QtPdf',
        'PySide6.QtVirtualKeyboard',
    ],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='restim',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['resources\\favicon.ico'],
)
