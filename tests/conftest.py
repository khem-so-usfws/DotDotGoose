"""Shared setup for tests that exercise DotDotGoose application preferences."""

from pathlib import Path
from typing import Any

import pytest
from PyQt6 import QtCore
from PyQt6.QtCore import QSettings


@pytest.fixture(autouse=True)
def isolate_ddg_settings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Give each test a private settings file, including on Windows.

    Args:
        tmp_path: Temporary directory owned by the test.
        monkeypatch: Fixture that restores the original Qt constructor.
    """
    settings_path: str = str(tmp_path / "DotDotGoose.ini")

    class IsolatedSettings(QSettings):
        """Redirect DDG's application settings to the test directory."""

        def __init__(self, *args: Any, **kwargs: Any) -> None:
            """Preserve other QSettings overloads, including explicit files."""
            if args == ("AMNH", "DotDotGoose") and not kwargs:
                # An explicit INI path avoids the native registry on Windows.
                super().__init__(settings_path, QSettings.Format.IniFormat)
            else:
                super().__init__(*args, **kwargs)

    monkeypatch.setattr(QtCore, "QSettings", IsolatedSettings)
