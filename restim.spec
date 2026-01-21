# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['restim.py'],
    pathex=['.'],
    binaries=[],
    datas=[
        ('resources/phase diagram bg.svg', 'resources/'),
        ('resources/favicon.png', 'resources/'),
        ('resources/favicon.ico', 'resources/'),
        ('resources/favicon.svg', 'resources/'),
        ('resources/*.svg', 'resources/'),
        ('resources/*.ico', 'resources/'),
        ('resources/*.png', 'resources/'),
        ('resources/icons/*', 'resources/icons/'),
        ('resources/wizard/*', 'resources/wizard/'),
        ('resources/media_players/*', 'resources/media_players/'),
        ('resources/*.qrc', 'resources/'),
    ],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
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
