@echo off
REM Instala Jarvis: crea el entorno, instala dependencias y lo deja arrancando con Windows.
cd /d "%~dp0"
where py >nul 2>nul || (echo Necesitas Python 3.10 o mas: https://www.python.org/downloads/ & pause & exit /b 1)

echo [1/3] Creando el entorno...
py -3 -m venv .venv || (echo No pude crear el entorno & pause & exit /b 1)

echo [2/3] Instalando dependencias (tarda unos minutos la primera vez)...
call .venv\Scripts\python.exe -m pip install --upgrade pip
call .venv\Scripts\python.exe -m pip install -r requirements.txt || (echo Fallo la instalacion & pause & exit /b 1)

echo [3/3] Configurando el arranque con Windows...
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0autoarranque.ps1" instalar

echo.
echo ========================================================
echo  Listo. Probalo asi:
echo.
echo  1) Sin microfono y sin ejecutar nada (lo mas seguro):
echo     .venv\Scripts\python.exe -m jarvis --text --dry-run
echo.
echo  2) Con voz:
echo     .venv\Scripts\python.exe -m jarvis
echo.
echo  Opcional - voz mas natural (gratis y local):  voz_natural.bat
echo  Opcional - ordenes libres con Ollama:         ver README.md
echo ========================================================
pause
