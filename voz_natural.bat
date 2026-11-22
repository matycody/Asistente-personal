@echo off
REM Opcional: voz neural local (Piper). Gratis, sin cuenta y sin internet una vez bajada.
REM Sin esto Jarvis habla con la voz que ya trae Windows.
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (echo Primero corre instalar.bat & pause & exit /b 1)

echo [1/2] Instalando Piper...
call .venv\Scripts\python.exe -m pip install piper-tts || (echo No se pudo instalar Piper & pause & exit /b 1)

echo [2/2] Bajando la voz argentina (unos 100 MB)...
if not exist "voces" mkdir voces
set BASE=https://huggingface.co/rhasspy/piper-voices/resolve/main/es/es_AR/daniela/high
curl -L -o "voces\es_AR-daniela-high.onnx" "%BASE%/es_AR-daniela-high.onnx" || goto :error
curl -L -o "voces\es_AR-daniela-high.onnx.json" "%BASE%/es_AR-daniela-high.onnx.json" || goto :error

echo.
echo Listo. Reinicia Jarvis y va a usar la voz nueva.
echo Para volver a la voz de Windows, en config.json: "voz": { "motor": "sapi" }
pause
exit /b 0

:error
echo.
echo No se pudo bajar la voz. Revisa tu conexion y volve a intentar.
pause
exit /b 1
