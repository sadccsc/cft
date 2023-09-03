@echo off
echo.
echo CFT Installation Script
echo.
echo ______________________________
chcp 437
SET mypath=%~dp0
set mypath=%mypath:~0,-1%

rem Detect QGIS Version
FOR /F "tokens=* USEBACKQ" %%g in (`dir /b "%PROGRAMFILES(X86)%\QGIS 3*" 2^>NUL`) do (
  set QGISDIR=%%g
)
if not "%QGISDIR%" == "" set OSGEO4W_ROOT=%PROGRAMFILES(X86)%\%QGISDIR%

FOR /F "tokens=* USEBACKQ" %%g in (`dir /b "%PROGRAMFILES%\QGIS 3*" 2^>NUL`) do (
  set QGISDIR=%%g
)
if not "%QGISDIR%" == "" set OSGEO4W_ROOT=%PROGRAMFILES%\%QGISDIR%

if "%QGISDIR%" == "" (
  echo.
  echo could not find any QGIS v3 installation.
  pause
  exit
)

rem write the OSGEO4W_ROOT variable to qgis_env.bat
echo set OSGEO4W_ROOT=%OSGEO4W_ROOT%> "%mypath%\qgis_env.bat"

FOR /F "tokens=* USEBACKQ" %%g in (`dir /b "%OSGEO4W_ROOT%\apps\qgis*" 2^>NUL`) do (
  set QGISAP=%%g
)
if not "%QGISAP%" == ""  set QGISAPP=%OSGEO4W_ROOT%\apps\%QGISAP%

FOR /F "tokens=* USEBACKQ" %%g in (`dir /b "%OSGEO4W_ROOT%\apps\qt*" 2^>NUL`) do (
  set QTAP=%%g
)
if not "%QTAP%" == "" set QTAPP=%OSGEO4W_ROOT%\apps\%QTAP%
set PYAPP=""
FOR /F "tokens=* USEBACKQ" %%g in (`dir /b "%OSGEO4W_ROOT%\apps\Python*" 2^>NUL`) do (
  set PYAP=%%g
)
if not "%QTAP%" == "" set PYAPP=%OSGEO4W_ROOT%\apps\%PYAP%

rem write the environment variables to qgis_env.bat
if exist "%QGISAPP%" echo set QGISAPP=%QGISAPP%>> "%mypath%\qgis_env.bat"
if exist "%QGISAPP%" echo set QGISAP=%QGISAP%>> "%mypath%\qgis_env.bat"
if exist "%OSGEO4W_ROOT%" echo set HDF5_DIR=%OSGEO4W_ROOT%>> "%mypath%\qgis_env.bat"
if exist "%OSGEO4W_ROOT%" echo set NETCDF4_DIR=%OSGEO4W_ROOT%>> "%mypath%\qgis_env.bat"
if exist "%QTAPP%" echo set QTAPP=%QTAPP%>> "%mypath%\qgis_env.bat"
if exist "%PYAPP%" echo set PYAPP=%PYAPP%>> "%mypath%\qgis_env.bat"

rem load the environment
if exist "%mypath%\qgis_env.bat" goto envexists
echo qgis_env.bat not found in the CFT folder. run the install-qgis-modules.bat again
pause
exit

:envexists
call "%mypath%\qgis_env.bat"
if exist "%OSGEO4W_ROOT%"  goto qgisexists
echo QGIS folder does not exist, check QGIS and run the install-qgis-modules.bat again
pause
exit

:qgisexists
if not exist "%QGISAPP%" echo QGISAPP folder does not exist
if not exist "%PYAPP%" echo PYAPP folder does not exist
if not exist "%QTAPP%" echo QTAPP folder does not exist
if not exist "%OSGEO4W_ROOT%\bin\o4w_env.bat" echo o4w_env.bat does not exist
if not exist "%OSGEO4W_ROOT%\bin\qt5_env.bat" echo qt5_env.bat does not exist
if not exist "%OSGEO4W_ROOT%\bin\py3_env.bat" echo py3_env.bat does not exist
if exist "%OSGEO4W_ROOT%\bin\o4w_env.bat" call "%OSGEO4W_ROOT%\bin\o4w_env.bat"

if not exist "%OSGEO4W_ROOT%\bin\qt5_env.bat" goto setqtenv
call "%OSGEO4W_ROOT%\bin\qt5_env.bat"
goto setpyenv

:setqtenv
if exist "%QGISAPP%\qtplugins" set QT_PLUGIN_PATH=%QGISAPP%\qtplugins;%QTAPP%\plugins
if not exist "%QGISAPP%\qtplugins" echo QT env not set

:setpyenv
if not exist "%OSGEO4W_ROOT%\bin\py3_env.bat" goto setpyenvexp
call "%OSGEO4W_ROOT%\bin\py3_env.bat"
goto startapp

:setpyenvexp
if exist "%OSGEO4W_ROOT%\apps\%QGISAP%\bin" set PATH=%OSGEO4W_ROOT%\apps\%QGISAP%\bin;%OSGEO4W_ROOT%\bin;%PATH%
if exist "%OSGEO4W_ROOT%\apps\%QGISAP%\bin" path %OSGEO4W_ROOT%\apps\%QGISAP%\bin;%PATH%
if exist "%QGISAPP%\bin" set QGIS_PREFIX_PATH=%OSGEO4W_ROOT:\=/%/apps/%QGISAP%
set GDAL_FILENAME_IS_UTF8=YES
set VSI_CACHE=TRUE
set VSI_CACHE_SIZE=1000000
if exist "%OSGEO4W_ROOT%\apps\%QGISAP%\python" set PYTHONPATH=%OSGEO4W_ROOT%\apps\%QGISAP%\python;%PYTHONPATH%

:startapp
echo QGIS installation to be used: %OSGEO4W_ROOT%
echo.
echo installing the python modules...
echo.
echo upgrading pip...
python -m pip install --upgrade pip
if %errorlevel% equ 0 (
 echo pip upgraded successfully
)
echo.
echo upgrading wheel...
python -m pip install --upgrade wheel
if %errorlevel% equ 0 (
 echo wheel upgraded successfully
)
echo.
echo upgrading setuptools...
python -m pip install --upgrade setuptools
if %errorlevel% equ 0 (
 echo setuptools upgraded successfully
)
echo.
echo upgrading untangle...
python -m pip install --upgrade untangle
if %errorlevel% equ 0 (
 echo untangle upgraded successfully
)
echo.
echo upgrading numpy...
python -m pip install --upgrade numpy
if %errorlevel% equ 0 (
 echo numpy upgraded successfully
)
echo.
echo upgrading netCDF4...
python -m pip install netCDF4==1.5.7
if %errorlevel% equ 0 (
 echo netCDF4 upgraded successfully
)
echo.
echo upgrading pandas...
python -m pip install --upgrade pandas
if %errorlevel% equ 0 (
 echo pandas upgraded successfully
)
echo.
echo upgrading scikit-learn...
python -m pip install --upgrade scikit-learn
if %errorlevel% equ 0 (
 echo sscikit-learn upgraded successfully
)
echo.
echo upgrading statsmodels...
python -m pip install --upgrade statsmodels
if %errorlevel% equ 0 (
 echo statsmodels upgraded successfully
)
echo.
echo upgrading scipy...
python -m pip install --upgrade scipy
if %errorlevel% equ 0 (
 echo scipy upgraded successfully
)
echo.
echo upgrading geojson...
python -m pip install --upgrade geojson
if %errorlevel% equ 0 (
 echo geojson upgraded successfully
)
echo.
echo upgrading shapely...
python -m pip install --upgrade shapely
if %errorlevel% equ 0 (
 echo shapely upgraded successfully
)
echo.
echo upgrading descartes...
python -m pip install --upgrade descartes
if %errorlevel% equ 0 (
 echo descartes upgraded successfully
)
echo.
echo upgrading threadpoolctl...
python -m pip install --upgrade threadpoolctl>=3.0.0
if %errorlevel% equ 0 (
 echo threadpoolctl upgraded successfully
)
echo.

echo upgrading xarray...
python -m pip install --upgrade xarray
if %errorlevel% equ 0 (
 echo xarray upgraded successfully
)
echo.

echo upgrading geocube...
python -m pip install --upgrade geocube
if %errorlevel% equ 0 (
 echo geocube upgraded successfully
)
echo.

echo upgrading geopandas...
python -m pip install --upgrade geopandas
if %errorlevel% equ 0 (
 echo geopandas upgraded successfully
)
echo.

echo upgrading cartopy...
python -m pip install --upgrade cartopy
if %errorlevel% equ 0 (
 echo cartopy upgraded successfully
)
echo.

echo upgrading rasterstats...
python -m pip install --upgrade rasterstats
if %errorlevel% equ 0 (
 echo rasterstats upgraded successfully
)
echo.

echo upgrading webbrowser...
python -m pip install --upgrade webbrowser
if %errorlevel% equ 0 (
 echo webbrowser upgraded successfully
)
echo.






rem create desktop launcher
set mypath=%mypath:'=''%
set TARGET='%mypath%\startup.bat'
set SHORTCUT='%mypath%\CFT.lnk'
set ICON='%mypath%\icon\cft.ico'
set WD='%mypath%'
set PWS=powershell.exe -ExecutionPolicy Bypass -NoLogo -NonInteractive -NoProfile

START /B %PWS% -Command "$ws = New-Object -ComObject WScript.Shell; $s = $ws.CreateShortcut(%SHORTCUT%); $S.TargetPath = %TARGET%; $S.IconLocation = %ICON%; $S.WorkingDirectory = %WD%; $S.Save()"

pause
