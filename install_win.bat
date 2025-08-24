@echo off

REM Define environment name here
REM note that it has to be the same name as that defined in .yml file
set ENV_NAME=cft-v5.0
set ENV_FILE=environment.yml
set SCRIPT_DIR=%~dp0
set DESKTOP=%USERPROFILE%\Desktop
set SHORTCUT_NAME=cft.lnk
set TARGET_BAT=%SCRIPT_DIR%\cft.bat
set SHORTCUT_PATH=%DESKTOP%\%SHORTCUT_NAME%


echo(
echo ----------------
echo checking if Mamba installed
where mamba >nul 2>nul
if %errorlevel% neq 0 (
    echo Mamba not found. Installing. This might take some time...
    call conda install -y mamba -n base -c conda-forge
) else (
    echo Mamba is already installed.
)

where mamba >nul 2>nul
if %errorlevel% neq 0 (
    echo Mamba could not be installed. Check errors displayed above.
    exit /b 1    
)

REM 1. Create conda environment from the lock file

echo(
echo ----------------
echo checking if Python environment %ENV_NAME% exists

rem conda info --envs |findstr /R /C:"^%ENV_NAME% ">nul

conda env list | findstr /R "\<%ENV_NAME%\>" >nul
if %ERRORLEVEL% EQU 0 (
   echo env %ENV_NAME% exists
) else (
   echo it does not exist, creating...
   call mamba env create -f environment.yml
)

   echo checking if creation successful

   rem conda info --envs |findstr /R /C:"^%ENV_NAME% ">nul
   conda env list | findstr /R "\<%ENV_NAME%\>" >nul

   if %ERRORLEVEL% EQU 0 (
   	echo env %ENV_NAME% created
   ) else (
       echo Python environment was not created. Exiting.
       exit /b 1
   )



REM Create a batch file to run cft.py inside conda env from script directory
echo(
echo ----------------
echo Creating batch file to run CFT - it will be located in the current directory %SCRIPT_DIR% under name %TARGET_BAT%
(
    echo call conda activate %ENV_NAME%
    echo python "%SCRIPT_DIR%cft.py"
) > "%TARGET_BAT%"


IF EXIST "%TARGET_BAT%" (
    echo %TARGET_BAT% created successfuly
) ELSE (
    echo %TARGET_BAT% could not be created. Exiting...
    exit /b 1
)



REM Create shortcut on desktop pointing to the batch file
echo(
echo ----------------
echo Create shortcut on desktop pointing to the batch file

powershell -NoProfile -ExecutionPolicy Bypass ^
"$ws = New-Object -ComObject WScript.Shell; $s = $ws.CreateShortcut('%SHORTCUT_PATH%'); $s.WorkingDirectory = '%SCRIPT_DIR%'; $s.TargetPath='%TARGET_BAT%'; $s.WindowStyle=7; $s.Save()"

IF EXIST "%SHORTCUT_PATH%" (
    echo %SHORTCUT_PATH% created successfuly.

) ELSE (
    echo %SHORTCUT_PATH% could not be created. Error, but not critical.
)

echo =======
echo End of installation process.     
echo Installation appears successful.
echo But inspect messages above to check if all is in order.
echo(
echo To start - use desktop shortcut (if created) or run cft.bat located in installation folder
echo(
echo Happy forecasting!
pause

