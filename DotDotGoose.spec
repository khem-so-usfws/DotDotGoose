# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller specification for the DotDotGoose Windows distribution."""

from pathlib import Path
from typing import Any

# PyInstaller injects SPECPATH and its build classes while executing a spec file.
project_root: Path = Path(SPECPATH)

# The application loads these UI files from sys._MEIPASS when frozen, so they
# must live at the root of PyInstaller's bundled data directory.
ui_data: list[tuple[str, str]] = [
    (str(project_root / "ddg" / "about_dialog.ui"), "."),
    (str(project_root / "ddg" / "central_widget.ui"), "."),
    (str(project_root / "ddg" / "chip_dialog.ui"), "."),
    (str(project_root / "ddg" / "point_widget.ui"), "."),
]
resource_data: list[tuple[str, str]] = [
    (str(project_root / "icons"), "icons"),
    (str(project_root / "i18n"), "i18n"),
]
datas: list[tuple[str, str]] = ui_data + resource_data

analysis: Any = Analysis(
    [str(project_root / "main.py")],
    pathex=[str(project_root)],
    binaries=[],
    datas=datas,
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz: Any = PYZ(analysis.pure)

# Build as a windowed one-folder application. One-folder packaging starts
# faster than a one-file bundle and is easier to troubleshoot for a PyQt app.
exe: Any = EXE(
    pyz,
    analysis.scripts,
    [],
    exclude_binaries=True,
    name="DotDotGoose",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    icon=str(project_root / "icons" / "ddg.png"),
)
collection: Any = COLLECT(
    exe,
    analysis.binaries,
    analysis.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="DotDotGoose",
)
