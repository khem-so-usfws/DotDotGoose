@echo off
setlocal EnableExtensions

rem Always build relative to the repository root, even when launched elsewhere.
cd /d "%~dp0"

set "RUN_TESTS=1"
if "%~1"=="" goto :args_done
if /I "%~1"=="--skip-tests" (
    set "RUN_TESTS=0"
    goto :args_done
)
goto :usage

:args_done
where python >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not available in this prompt.
    echo Activate the DDG build environment and try again.
    exit /b 1
)

python -c "import struct,sys; sys.exit(0 if struct.calcsize('P') * 8 == 64 else 1)"
if errorlevel 1 (
    echo ERROR: The release script expects a 64-bit Python environment.
    exit /b 1
)

python -m PyInstaller --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: PyInstaller is not installed in the active environment.
    echo Install build tools with: python -m pip install -r requirements-build.txt
    exit /b 1
)

if "%RUN_TESTS%"=="1" (
    echo.
    echo === Running tests ===
    python -m pytest -q
    if errorlevel 1 (
        echo ERROR: Tests failed. Windows release build aborted.
        exit /b 1
    )
) else (
    echo WARNING: Tests were skipped by request.
)

for /f "delims=" %%V in ('python -c "import ddg; print(ddg.__version__)"') do (
    set "DDG_VERSION=%%V"
)
if not defined DDG_VERSION (
    echo ERROR: Could not determine the DotDotGoose version.
    exit /b 1
)

set "PACKAGE_NAME=DotDotGoose-%DDG_VERSION%-windows-x64"
set "PACKAGE_DIR=dist\%PACKAGE_NAME%"
set "ZIP_PATH=dist\%PACKAGE_NAME%.zip"

rem Remove only generated build products. Source files are never modified here.
if exist "build" rmdir /s /q "build"
if exist "dist\DotDotGoose" rmdir /s /q "dist\DotDotGoose"
if exist "%PACKAGE_DIR%" rmdir /s /q "%PACKAGE_DIR%"
if exist "%ZIP_PATH%" del /q "%ZIP_PATH%"

echo.
echo === Building DotDotGoose %DDG_VERSION% ===
python -m PyInstaller --clean --noconfirm DotDotGoose.spec
if errorlevel 1 (
    echo ERROR: PyInstaller build failed.
    exit /b 1
)

if not exist "dist\DotDotGoose\DotDotGoose.exe" (
    echo ERROR: Expected executable was not produced.
    exit /b 1
)

move /Y "dist\DotDotGoose" "%PACKAGE_DIR%" >nul
if errorlevel 1 (
    echo ERROR: Could not stage the versioned release directory.
    exit /b 1
)

rem Ship the license and user documentation beside the executable bundle.
copy /Y "LICENSE" "%PACKAGE_DIR%\LICENSE" >nul
copy /Y "README.md" "%PACKAGE_DIR%\README.md" >nul
copy /Y "changelog.md" "%PACKAGE_DIR%\changelog.md" >nul
if exist "docs" xcopy /E /I /Y "docs" "%PACKAGE_DIR%\docs" >nul

powershell.exe -NoProfile -ExecutionPolicy Bypass -Command ^
    "Compress-Archive -Path '%PACKAGE_DIR%' -DestinationPath '%ZIP_PATH%' -CompressionLevel Optimal -Force"
if errorlevel 1 (
    echo ERROR: Could not create the release ZIP.
    exit /b 1
)

echo.
echo === Windows release build complete ===
echo Application: %PACKAGE_DIR%\DotDotGoose.exe
echo Release ZIP: %ZIP_PATH%
echo.
echo Test the ZIP on a Windows machine without Python before publishing it.
exit /b 0

:usage
echo Usage: build_windows.bat [--skip-tests]
echo.
echo Default behavior runs the test suite before building.
echo Use --skip-tests only when the same source revision was already tested.
exit /b 2
