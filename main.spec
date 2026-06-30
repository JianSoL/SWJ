# -*- mode: python ; coding: utf-8 -*-

import glob


def _first_existing(pattern):
    matches = sorted(glob.glob(pattern))
    return matches[-1] if matches else None


vc90_binaries = []
for dll_pattern in (
    r'C:\Windows\WinSxS\amd64_microsoft.vc90.crt_*\msvcr90.dll',
    r'C:\Windows\WinSxS\amd64_microsoft.vc90.mfc_*\mfc90.dll',
):
    dll_path = _first_existing(dll_pattern)
    if dll_path:
        vc90_binaries.append((dll_path, '.'))


a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[
        ('ControlCAN.dll', '.'),
    ] + vc90_binaries,
    datas=[
        ('conf.yaml', '.'),
        ('UI/release_theme.qss', 'UI'),
        ('UI/style.qss', 'UI'),
        ('alarm.wav', '.'),
        ('IDC.dbc', '.'),
        ('resources/index_catalog.json', 'resources'),
        ('resources/index_custom_template.yaml', 'resources'),
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
    name='main',
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
    icon=['1.ico'],
)
