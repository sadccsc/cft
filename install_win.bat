@echo off
setlocal enabledelayedexpansion

REM === CONFIG ===
set ENV_NAME=cft-v5.0.0
set MAMBA_DIR=%USERPROFILE%\micromamba
set MAMBA_BIN=%MAMBA_DIR%\micromamba.exe
set ENV_FILE=environment.yml
set SCRIPT_DIR=%~dp0
set DESKTOP=%USERPROFILE%\Desktop
set SHORTCUT_NAME=cft.lnk
set TARGET_BAT=%USERPROFILE%\cft.bat

REM === DOWNLOAD MICROMAMBA IF NOT INSTALLED ===
if not exist "%MAMBA_BIN%" (
    echo Micromamba not found. Installing...
    mkdir "%MAMBA_DIR%"
    curl -L https://micro.mamba.pm/api/micromamba/win-64/latest -o "%MAMBA_DIR%\micromamba.tar.bz2"
    tar -xvjf "%MAMBA_DIR%\micromamba.tar.bz2" -C "%MAMBA_DIR%" --strip-components=1 bin/micromamba.exe
) else (
    echo Micromamba already installed.
)

REM === CREATE ENVIRONMENT ===
"%MAMBA_BIN%" create -y -f "%SCRIPT_DIR%%ENV_FILE%" -r "%MAMBA_DIR%"

REM === CREATE LAUNCHER BATCH FILE ===
echo @echo off > "%TARGET_BAT%"
echo "%MAMBA_BIN%" activate %ENV_NAME% >> "%TARGET_BAT%"
echo python "%SCRIPT_DIR%cft.py" >> "%TARGET_BAT%"
echo pause >> "%TARGET_BAT%"

REM === CREATE DESKTOP SHORTCUT ===
powershell -command "$s=(New-Object -COM WScript.Shell).CreateShortcut('%DESKTOP%\%SHORTCUT_NAME%');$s.TargetPath='%TARGET_BAT%';$s.Save()"

echo Installation complete. Shortcut created on desktop.
pause

