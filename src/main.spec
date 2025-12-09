# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[('resources/icons/check.svg', 'resources/icons'), ('resources/icons/menu.svg', 'resources/icons'), ('resources/icons/star.svg', 'resources/icons'), ('resources/icons/line.svg', 'resources/icons'), ('resources/icons/redo.svg', 'resources/icons'), ('resources/icons/zoom-in.svg', 'resources/icons'), ('resources/icons/plus.svg', 'resources/icons'), ('resources/icons/delete.svg', 'resources/icons'), ('resources/icons/layers.svg', 'resources/icons'), ('resources/icons/arrow.svg', 'resources/icons'), ('resources/icons/export.svg', 'resources/icons'), ('resources/icons/text.svg', 'resources/icons'), ('resources/icons/zoom-out.svg', 'resources/icons'), ('resources/icons/cross.svg', 'resources/icons'), ('resources/icons/edit.svg', 'resources/icons'), ('resources/icons/circle.svg', 'resources/icons'), ('resources/icons/pen.svg', 'resources/icons'), ('resources/icons/rectangle.svg', 'resources/icons'), ('resources/icons/eye-off.svg', 'resources/icons'), ('resources/icons/download.svg', 'resources/icons'), ('resources/icons/highlighter.svg', 'resources/icons'), ('resources/icons/save.svg', 'resources/icons'), ('resources/icons/attach.svg', 'resources/icons'), ('resources/icons/eraser.svg', 'resources/icons'), ('resources/icons/undo.svg', 'resources/icons'), ('resources/icons/open.svg', 'resources/icons'), ('resources/icons/next.svg', 'resources/icons'), ('resources/icons/new.svg', 'resources/icons'), ('resources/icons/heart.svg', 'resources/icons'), ('resources/icons/pencil.svg', 'resources/icons'), ('resources/icons/image.svg', 'resources/icons'), ('resources/icons/copy.svg', 'resources/icons'), ('resources/icons/prev.svg', 'resources/icons'), ('resources/icons/eye.svg', 'resources/icons'), ('resources/icons/settings.svg', 'resources/icons')],
    hiddenimports=['main', 'ui.interactive_canvas', 'ui.main_window'],
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
    name='main',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
