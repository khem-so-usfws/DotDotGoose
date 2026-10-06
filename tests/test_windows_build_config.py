"""Regression tests for the checked-in Windows release configuration."""

from __future__ import annotations

from pathlib import Path


PROJECT_ROOT: Path = Path(__file__).resolve().parents[1]
SPEC_PATH: Path = PROJECT_ROOT / "DotDotGoose.spec"
BUILD_SCRIPT_PATH: Path = PROJECT_ROOT / "build_windows.bat"
README_PATH: Path = PROJECT_ROOT / "README.md"
BUILD_REQUIREMENTS_PATH: Path = PROJECT_ROOT / "requirements-build.txt"


def test_windows_spec_bundles_runtime_resources() -> None:
    """The PyInstaller spec should include every runtime-loaded resource."""
    spec_text: str = SPEC_PATH.read_text(encoding="utf-8")
    required_resources: tuple[str, ...] = (
        "about_dialog.ui",
        "central_widget.ui",
        "chip_dialog.ui",
        "point_widget.ui",
        '"icons"',
        '"i18n"',
    )
    resource: str
    for resource in required_resources:
        assert resource in spec_text


def test_windows_build_script_uses_spec_and_versioned_zip() -> None:
    """The build script should create a versioned x64 ZIP from the spec."""
    script_text: str = BUILD_SCRIPT_PATH.read_text(encoding="utf-8")
    assert "DotDotGoose.spec" in script_text
    assert "DDG_VERSION" in script_text
    assert "windows-x64" in script_text
    assert "Compress-Archive" in script_text


def test_readme_documents_windows_build_and_release_workflow() -> None:
    """The README should explain local Windows builds and GitHub releases."""
    readme_text: str = README_PATH.read_text(encoding="utf-8")
    assert "build_windows.bat" in readme_text
    assert "DotDotGoose.spec" in readme_text
    assert "GitHub Release" in readme_text


def test_build_requirements_pin_release_toolchain() -> None:
    """The build requirements should pin the tested release-tool versions."""
    requirements_text: str = BUILD_REQUIREMENTS_PATH.read_text(encoding="utf-8")
    assert "pytest==9.1.1" in requirements_text
    assert "pytest-qt==4.5.0" in requirements_text
    assert "pyinstaller==6.22.3" in requirements_text
