@echo off

REM Define environment name here
REM note that it has to be the same name as that defined in .yml file
set ENV_NAME=cft-v5.0.0

where mamba >nul 2>nul
if %errorlevel% neq 0 (
    echo Mamba not found. Installing...
    call conda install -y mamba -n base -c conda-forge
) else (
    echo Mamba is already installed.
)

REM 1. Create conda environment from the lock file
call mamba env create -f environment.yml

REM 2. Create a shortcut on the desktop to run start.py in the created env

REM Define desktop path
set DESKTOP=%USERPROFILE%\Desktop
set SHORTCUT_NAME=cft.lnk
set TARGET_BAT=%USERPROFILE%\cft.bat


REM Get the directory where install.bat resides
set SCRIPT_DIR=%~dp0


REM Create a batch file to run start.py inside conda env from script directory
echo @echo off > "%TARGET_BAT%"
echo call conda activate %ENV_NAME% >> "%TARGET_BAT%"
echo python "%SCRIPT_DIR%cft.py" >> "%TARGET_BAT%"
echo pause >> "%TARGET_BAT%"

REM Create shortcut on desktop pointing to the batch file
powershell -command "$s=(New-Object -COM WScript.Shell).CreateShortcut('%DESKTOP%\%SHORTCUT_NAME%');$s.TargetPath='%TARGET_BAT%';$s.Save()"

echo Installation complete. Shortcut created on desktop.
pause

