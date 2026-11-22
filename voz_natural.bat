@echo off
REM Opcional: voz neural local (Piper). Gratis, sin cuenta y sin internet una vez bajada.
REM Sin esto Jarvis habla con la voz que ya trae Windows.
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (echo Primero corre instalar.bat & pause & exit /b 1)

echo.
echo  Que voz queres?
echo    1^) Hombre latinoamericano  (es_MX-ald)      ^<-- recomendada
echo    2^) Hombre de Espana        (es_ES-davefx)
echo    3^) Mujer argentina         (es_AR-daniela)
echo.
set "OPCION="
set /p OPCION=Elegi 1, 2 o 3 (Enter = 1): 
if "%OPCION%"=="" set OPCION=1

if "%OPCION%"=="2" (
  set "RUTA=es/es_ES/davefx/medium" & set "VOZ=es_ES-davefx-medium"
) else if "%OPCION%"=="3" (
  set "RUTA=es/es_AR/daniela/high" & set "VOZ=es_AR-daniela-high"
) else (
  set "RUTA=es/es_MX/ald/medium" & set "VOZ=es_MX-ald-medium"
)

echo.
echo [1/3] Instalando Piper...
call .venv\Scripts\python.exe -m pip install piper-tts || (echo No se pudo instalar Piper & pause & exit /b 1)

echo [2/3] Bajando la voz %VOZ%...
if not exist "voces" mkdir voces
set "BASE=https://huggingface.co/rhasspy/piper-voices/resolve/main/%RUTA%"
curl -L --fail -o "voces\%VOZ%.onnx"      "%BASE%/%VOZ%.onnx"      || goto :error
curl -L --fail -o "voces\%VOZ%.onnx.json" "%BASE%/%VOZ%.onnx.json" || goto :error

echo [3/3] Dejandola configurada...
call .venv\Scripts\python.exe -c "import json,io,os; p='config.json'; d=json.load(io.open(p,encoding='utf-8')) if os.path.exists(p) else {}; d.setdefault('voz',{})['modelo']='voces/%VOZ%.onnx'; d['voz']['motor']='auto'; io.open(p,'w',encoding='utf-8').write(json.dumps(d,ensure_ascii=False,indent=2))" || goto :error

echo.
echo  Listo. Reinicia Jarvis y va a usar la voz %VOZ%.
echo  Para volver a la voz de Windows, en config.json:  "voz": { "motor": "sapi" }
echo  Para que hable mas rapido:                        "voz": { "ritmo": 0.9 }
pause
exit /b 0

:error
echo.
echo  No se pudo bajar la voz. Revisa tu conexion y volve a intentar.
pause
exit /b 1
