@echo off
echo.
echo CFT Installation Script
echo.
echo ______________________________
chcp 437
SET mypath=%~dp0
set mypath=%mypath:~0,-1%

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
python -m pip install netCDF4
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






rem create desktop launcher
set mypath=%mypath:'=''%
set TARGET='%mypath%\startup.bat'
set SHORTCUT='%mypath%\CFT.lnk'
set ICON='%mypath%\icon\cft.ico'
set WD='%mypath%'
set PWS=powershell.exe -ExecutionPolicy Bypass -NoLogo -NonInteractive -NoProfile

START /B %PWS% -Command "$ws = New-Object -ComObject WScript.Shell; $s = $ws.CreateShortcut(%SHORTCUT%); $S.TargetPath = %TARGET%; $S.IconLocation = %ICON%; $S.WorkingDirectory = %WD%; $S.Save()"

pause


