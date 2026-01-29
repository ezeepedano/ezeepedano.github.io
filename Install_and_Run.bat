@echo off
TITLE Propel ERP - Auto-Instalador y Launcher
color 0A
CLS

echo ======================================================================
echo   PROPEL ERP - ASISTENTE DE INSTALACION Y EJECUCION
echo ======================================================================
echo.

:: ---------------------------------------------------------
:: 0. Asegurar directorio de trabajo
:: ---------------------------------------------------------
cd /d "%~dp0"

:: ---------------------------------------------------------
:: 1. Verificar Python
:: ---------------------------------------------------------
:: Definir nombre unico para el entorno virtual de ESTA PC
set VENV_NAME=venv_%COMPUTERNAME%

echo [1/5] Verificando instalacion de Python...
set PYTHON_CMD=python

:: Check standard python command
python --version >nul 2>&1
IF %ERRORLEVEL% EQU 0 GOTO FoundPython

:: Check py launcher
py --version >nul 2>&1
IF %ERRORLEVEL% EQU 0 (
    set PYTHON_CMD=py
    GOTO FoundPython
)

GOTO NoPython

:FoundPython
echo [OK] Python detectado: %PYTHON_CMD%
GOTO CheckVenv

:NoPython
echo [!] Python NO encontrado.
echo [INFO] Solicitando permisos de Administrador para instalar Python...
:: Check Admin
>nul 2>&1 "%SYSTEMROOT%\system32\cacls.exe" "%SYSTEMROOT%\system32\config\system"
IF %ERRORLEVEL% NEQ 0 (
    echo Set UAC = CreateObject^("Shell.Application"^) > "%temp%\getadmin.vbs"
    echo UAC.ShellExecute "%~s0", "", "", "runas", 1 >> "%temp%\getadmin.vbs"
    "%temp%\getadmin.vbs"
    EXIT /B
)

echo [!] Descargando instalador de Python...
powershell -Command "Invoke-WebRequest -Uri 'https://www.python.org/ftp/python/3.11.5/python-3.11.5-amd64.exe' -OutFile 'python_installer.exe'"

echo [!] Instalando Python (esto puede tardar)...
python_installer.exe /quiet InstallAllUsers=1 PrependPath=1 Include_test=0
del python_installer.exe

echo [OK] Python instalado.
echo.
echo POR FAVOR, CIERRA ESTA VENTANA Y VUELVE A ABRIR EL ARCHIVO.
PAUSE
EXIT

:: ---------------------------------------------------------
:: 2. Verificar Entorno Virtual (venv)
:: ---------------------------------------------------------
:CheckVenv
echo [2/5] Verificando Entorno Virtual (%VENV_NAME%)...
IF EXIST "%VENV_NAME%" GOTO VenvExists

echo [INFO] Creando entorno virtual '%VENV_NAME%'...
%PYTHON_CMD% -m venv "%VENV_NAME%"
IF %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Fallo al crear venv.
    PAUSE
    EXIT
)
GOTO VenvSetup

:VenvExists
echo [OK] Venv encontrado.
GOTO VenvSetup

:VenvSetup
echo [INFO] Activando entorno...
CALL "%VENV_NAME%\Scripts\activate"

echo [INFO] Verificando dependencias...
python -c "import django" >nul 2>&1
IF %ERRORLEVEL% EQU 0 GOTO Launch

echo [INFO] Instalando/Actualizando dependencias...
python -m pip install --upgrade pip
pip install -r requirements.txt
echo [INFO] Aplicando migraciones...
python manage.py migrate

:: ---------------------------------------------------------
:: 3. Crear Acceso Directo (Solo si no existe)
:: ---------------------------------------------------------
:Launch
echo [3/5] Verificando Acceso Directo...
:: Use PowerShell to find the actual Desktop path (handles OneDrive)
for /f "usebackq tokens=*" %%A in (`powershell -command "[Environment]::GetFolderPath('Desktop')"`) do set "DESKTOP_DIR=%%A"
set "SHORTCUT_PATH=%DESKTOP_DIR%\Propel ERP.lnk"

IF EXIST "%SHORTCUT_PATH%" GOTO RunServer

echo [INFO] Creando acceso directo en: %SHORTCUT_PATH%
powershell -Command "$WS = New-Object -ComObject WScript.Shell; $SC = $WS.CreateShortcut('%SHORTCUT_PATH%'); $SC.TargetPath = '%~dp0Install_and_Run.bat'; $SC.IconLocation = '%~dp0static\favicon.ico'; $SC.Save()"

:: ---------------------------------------------------------
:: 4. Ejecutar Servidor
:: ---------------------------------------------------------
:RunServer
echo [4/5] Iniciando servidor...
echo.
echo ======================================================================
echo   SISTEMA ONLINE
echo   - Abriendo navegador...
echo   - NO CIERRES ESTA VENTANA.
echo ======================================================================

timeout /t 5 >nul
start "" http://127.0.0.1:8000

python manage.py runserver 0.0.0.0:8000

echo.
echo [INFO] El servidor se ha detenido.
PAUSE
