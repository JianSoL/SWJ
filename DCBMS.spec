# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path


project_root = Path(SPECPATH)
canfd_dir = project_root / "CANFD"

datas = [
    (str(project_root / "ControlCANFD.dll"), "."),
    (str(project_root / "DCFDV1.3.dbc"), "."),
    (str(canfd_dir / "conf.yaml"), "."),
    (str(canfd_dir / "1.ico"), "."),
    (str(canfd_dir / "alarm.wav"), "."),
    (str(canfd_dir / "UI" / "release_theme.qss"), "UI"),
    (str(canfd_dir / "SINGLE" / "BCU.yaml"), "SINGLE"),
    (str(canfd_dir / "resources" / "index_catalog.json"), "resources"),
]

hiddenimports = [
    "PyQt6.QtMultimedia",
    "matplotlib.backends.backend_qtagg",
    "mpl_toolkits.mplot3d",
]


a = Analysis(
    ["main.py"],
    pathex=[str(project_root), str(canfd_dir)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "scipy",
    ],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="DCBMS",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(canfd_dir / "1.ico"),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="DCBMS",
)
