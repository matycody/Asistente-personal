@echo off
REM Elegir la voz de Jarvis. Todas son gratis y sin cuenta.
setlocal enabledelayedexpansion
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (echo Primero corre instalar.bat & pause & exit /b 1)

echo.
echo  ============================================================
echo   QUE VOZ QUERES PARA JARVIS
echo  ============================================================
echo.
echo   LAS QUE MEJOR SUENAN  (gratis, sin cuenta; usan internet
echo   para convertir el texto en audio)
echo     1^) Tomas  - hombre ARGENTINO     ^<-- recomendada
echo     2^) Jorge  - hombre mexicano
echo     3^) Alvaro - hombre de Espana
echo     4^) Elena  - mujer argentina
echo.
echo   100%% LOCALES  (no sale nada de tu PC, suenan algo peor)
echo     5^) Hombre latinoamericano  (Piper, 63 MB)
echo     6^) Hombre de Espana        (Piper, 63 MB)
echo     7^) Mujer argentina         (Piper, 115 MB)
echo     8^) La que ya trae Windows  (no baja nada)
echo.
set "OP="
set /p OP=Elegi un numero (Enter = 1): 
if "%OP%"=="" set OP=1

set "MODO=edge"
if "%OP%"=="1" set "VOZ=es-AR-TomasNeural"
if "%OP%"=="2" set "VOZ=es-MX-JorgeNeural"
if "%OP%"=="3" set "VOZ=es-ES-AlvaroNeural"
if "%OP%"=="4" set "VOZ=es-AR-ElenaNeural"
if "%OP%"=="5" ( set "MODO=piper" & set "RUTA=es/es_MX/ald/medium"    & set "VOZ=es_MX-ald-medium" )
if "%OP%"=="6" ( set "MODO=piper" & set "RUTA=es/es_ES/davefx/medium" & set "VOZ=es_ES-davefx-medium" )
if "%OP%"=="7" ( set "MODO=piper" & set "RUTA=es/es_AR/daniela/high"  & set "VOZ=es_AR-daniela-high" )
if "%OP%"=="8" ( set "MODO=windows" & set "VOZ=" )

echo.
if "!MODO!"=="edge" (
  echo [1/2] Instalando lo necesario...
  call .venv\Scripts\python.exe -m pip install edge-tts soundfile || goto :error
  echo [2/2] Dejandola configurada...
  call .venv\Scripts\python.exe -m jarvis --fijar-voz edge "!VOZ!" || goto :error
)
if "!MODO!"=="piper" (
  echo [1/3] Instalando Piper...
  call .venv\Scripts\python.exe -m pip install piper-tts || goto :error
  echo [2/3] Bajando la voz !VOZ! ...
  if not exist "voces" mkdir voces
  set "BASE=https://huggingface.co/rhasspy/piper-voices/resolve/main/!RUTA!"
  curl -L --fail -o "voces\!VOZ!.onnx"      "!BASE!/!VOZ!.onnx"      || goto :error
  curl -L --fail -o "voces\!VOZ!.onnx.json" "!BASE!/!VOZ!.onnx.json" || goto :error
  echo [3/3] Dejandola configurada...
  call .venv\Scripts\python.exe -m jarvis --fijar-voz piper "voces/!VOZ!.onnx" || goto :error
)
if "!MODO!"=="windows" (
  call .venv\Scripts\python.exe -m jarvis --fijar-voz auto "" || goto :error
)

echo.
echo  Listo. Escuchala con:   .venv\Scripts\python.exe -m jarvis --voz
echo  Y arranca Jarvis con:   .venv\Scripts\python.exe -m jarvis
pause
exit /b 0

:error
echo.
echo  Algo fallo. Revisa tu conexion y volve a intentar.
pause
exit /b 1
