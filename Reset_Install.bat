@echo off
TITLE Propel ERP - Resetear Instalacion
color 0C
CLS

echo ======================================================================
echo   PROPEL ERP - RESETEO DE INSTALACION
echo ======================================================================
echo.
echo ESTO BORRARA:
echo   1. El entorno virtual (carpeta '%VENV_NAME%').
echo   2. El acceso directo del Escritorio.
echo.
echo ESTO NO BORRARA:
echo   - Tu base de datos (tus ventas, productos, etc).
echo   - El codigo fuente del sistema.
echo.
echo Utiliza esto para probar el proceso de instalacion (Install_and_Run.bat)
echo desde cero.
echo.
PAUSE

cd /d "%~dp0"

:: 1. Delete venv
set VENV_NAME=venv_%COMPUTERNAME%
echo.
echo [1/2] Eliminando entorno virtual (%VENV_NAME%)...
IF EXIST "%VENV_NAME%" (
    rmdir /s /q "%VENV_NAME%"
    IF EXIST "%VENV_NAME%" (
        echo [ERROR] No se pudo borrar '%VENV_NAME%'. Intenta cerrar cualquier ventana de Python/Servidor.
    ) ELSE (
        echo [OK] Carpeta '%VENV_NAME%' eliminada.
    )
) ELSE (
    echo [INFO] La carpeta '%VENV_NAME%' no existe.
)

:: 2. Delete Shortcut
echo.
echo [2/2] Eliminando acceso directo...
for /f "usebackq tokens=*" %%A in (`powershell -command "[Environment]::GetFolderPath('Desktop')"`) do set "DESKTOP_DIR=%%A"
set "SHORTCUT_PATH=%DESKTOP_DIR%\Propel ERP.lnk"

IF EXIST "%SHORTCUT_PATH%" (
    del "%SHORTCUT_PATH%"
    echo [OK] Acceso directo eliminado de: %SHORTCUT_PATH%
) ELSE (
    echo [INFO] No se encontro el acceso directo en el Escritorio.
)

echo.
echo ======================================================================
echo   LISTO
echo   Ahora puedes ejecutar 'Install_and_Run.bat' para probar la instalacion.
echo ======================================================================
PAUSE
