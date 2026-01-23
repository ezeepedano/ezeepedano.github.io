@echo off
echo Activando entorno virtual...
call venv\Scripts\activate.bat
echo Ejecutando migraciones de base de datos...
python manage.py migrate
echo.
echo Cargando Plan de Cuentas estándar...
python scripts/seed_chart_of_accounts.py
echo.
echo ==========================================
echo       PROCESO COMPLETADO
echo ==========================================
echo.
pause
