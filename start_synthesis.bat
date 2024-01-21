@echo off

echo.
echo Forecast synthesis module startup Script
echo.
echo ______________________________
chcp 437
SET mypath=%~dp0
set mypath=%mypath:~0,-1%

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

set QT_AUTO_SCREEN_SCALE_FACTOR=1
set CPL_ZIP_ENCODING=UTF-8
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
echo.
echo PATH: %PATH%
echo.
echo PYTHONPATH: %PYTHONPATH%
echo.
python forecast_synthesis.py
pause
