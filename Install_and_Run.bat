@echo off
TITLE Propel ERP - Launcher
color 0A
CLS

:: ---------------------------------------------------------
:: 0. Asegurar directorio de trabajo
:: ---------------------------------------------------------
cd /d "%~dp0"

set VENV_NAME=venv_%COMPUTERNAME%

:: ---------------------------------------------------------
:: FASE 1: INSTALACION (primera vez o si falta el flag)
:: ---------------------------------------------------------
set FLAG_FILE=%VENV_NAME%\.installed_ok

IF EXIST "%FLAG_FILE%" GOTO RunSplash

echo ======================================================================
echo   PROPEL ERP - PRIMERA CONFIGURACION (solo ocurre una vez)
echo ======================================================================
echo.

:: 1. Verificar Python
echo [1/5] Verificando Python...
set PYTHON_CMD=python

python --version >nul 2>&1
IF %ERRORLEVEL% EQU 0 GOTO FoundPython

py --version >nul 2>&1
IF %ERRORLEVEL% EQU 0 (
    set PYTHON_CMD=py
    GOTO FoundPython
)

GOTO NoPython

:FoundPython
echo [OK] Python detectado.
GOTO CheckVenv

:NoPython
echo [!] Python NO encontrado.
echo [INFO] Solicitando permisos de Administrador para instalar Python...
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

:: 2. Verificar/Crear venv
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

:VenvExists
echo [OK] Venv encontrado.

echo [INFO] Activando entorno...
CALL "%VENV_NAME%\Scripts\activate"

:: 3. Instalar dependencias (solo primera vez)
echo [INFO] Primera ejecucion: instalando dependencias...
pip install -r requirements.txt
IF %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Fallo al instalar dependencias. Revise requirements.txt.
    PAUSE
    EXIT
)

:: 4. Migraciones
echo [INFO] Aplicando migraciones de base de datos...
python manage.py migrate
IF %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Fallo al aplicar migraciones.
    PAUSE
    EXIT
)

:: Marcar como instalado
echo %DATE% %TIME% > "%FLAG_FILE%"
echo [OK] Instalacion completa.

:: ---------------------------------------------------------
:: 5. Crear Acceso Directo (Solo si no existe)
:: ---------------------------------------------------------
echo [3/5] Verificando Acceso Directo...
IF EXIST "%VENV_NAME%\.shortcut_cache" del "%VENV_NAME%\.shortcut_cache"

set BAT_PATH=%~dp0Install_and_Run.bat
set ICO_PATH=%~dp0static\favicon.ico
set WORK_DIR=%~dp0
powershell -NoProfile -Command ^
  "$desktop = [Environment]::GetFolderPath('Desktop');" ^
  "$lnk = Join-Path $desktop 'Propel ERP.lnk';" ^
  "if (-not (Test-Path $lnk)) {" ^
  "  $ws = New-Object -ComObject WScript.Shell;" ^
  "  $sc = $ws.CreateShortcut($lnk);" ^
  "  $sc.TargetPath = '%BAT_PATH%';" ^
  "  $sc.WorkingDirectory = '%WORK_DIR%';" ^
  "  $sc.IconLocation = '%ICO_PATH%';" ^
  "  $sc.Save();" ^
  "  Write-Host '[OK] Acceso directo creado.'" ^
  "} else { Write-Host '[OK] Acceso directo ya existe.' }"

:: ---------------------------------------------------------
:: FASE 2: ARRANQUE CON SPLASH SCREEN
:: ---------------------------------------------------------
:RunSplash

:: Detectar Python del venv
set VENV_PYTHON=%~dp0%VENV_NAME%\Scripts\python.exe
IF NOT EXIST "%VENV_PYTHON%" set VENV_PYTHON=python

:: Llamar al splash screen - esta ventana CMD queda minimizada/oculta
:: El splash screen Python maneja todo el arranque del servidor
start /min "" "%VENV_PYTHON%" "%~dp0scripts\splash_launcher.py"

:: Cerrar esta ventana CMD (el servidor sigue corriendo via el splash)
EXIT
