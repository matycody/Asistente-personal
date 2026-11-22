@echo off
REM Instala Jarvis: crea el entorno, instala dependencias y lo deja arrancando con Windows.
cd /d "%~dp0"
where py >nul 2>nul || (echo Necesitas Python 3.10 o mas: https://www.python.org/downloads/ & pause & exit /b 1)
py -3 -m venv .venv || (echo No pude crear el entorno & pause & exit /b 1)
call .venv\Scripts\python.exe -m pip install --upgrade pip
call .venv\Scripts\python.exe -m pip install -r requirements.txt || (echo Fallo la instalacion & pause & exit /b 1)
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0autoarranque.ps1" instalar
echo.
echo Listo. Para probar sin microfono: .venv\Scripts\python.exe -m jarvis --text --dry-run
echo Para probar con voz:               .venv\Scripts\python.exe -m jarvis
pause
