# Jarvis (asistente de voz local para Windows)

Escucha tu micrófono, entiende órdenes en español y maneja la PC. La voz se reconoce
**en tu propia PC** (Whisper) y no se envía audio a ningún servidor. Arranca con Windows.

## Instalar
1. Instalá Python 3.10 o más reciente (tildá "Add python.exe to PATH").
2. Descomprimí esta carpeta donde quieras dejarla (ej. `C:\Jarvis`) y hacé doble clic en `instalar.bat`.
   La primera vez que escuche, descarga el modelo de voz (unos 500 MB con `small`); eso necesita internet una sola vez.
3. Probalo sin micrófono ni riesgo: `.venv\Scripts\python.exe -m jarvis --text --dry-run`
4. Probalo con voz: `.venv\Scripts\python.exe -m jarvis`

Para sacar el autoarranque: `powershell -File autoarranque.ps1 quitar`.
Los registros están en `%LOCALAPPDATA%\Jarvis\jarvis.log`.

## Qué le podés decir
Empezá con "Jarvis". Después de una orden escucha 6 segundos más sin que repitas el nombre.

| Orden | Resultado |
|---|---|
| "Jarvis, abrí Brave" | abre Brave |
| "abrí el explorador de archivos y entrá al disco H" | dos acciones seguidas |
| "abrí YouTube" / "abrí Computrabajo" | abre el sitio en Brave |
| "buscá recetas de milanesa" / "buscá lofi en YouTube" | búsqueda web |
| "subí / bajá el volumen", "silencio", "pausa", "siguiente canción" | multimedia |
| "minimizá todo", "cerrá esta ventana", "captura de pantalla" | ventanas |
| "bloqueá la PC" | bloquea la sesión |
| "apagá la PC" / "reiniciá" | pide que digas "confirmo" |

## Órdenes libres (opcional, con Ollama)
Sin esto Jarvis solo entiende las frases de la tabla. Con un modelo local entiende órdenes "con tus palabras"
("llevame a lo que bajé hoy", "qué hora es") y sigue sin salir de tu PC.
1. Instalá Ollama desde https://ollama.com y en una consola corré `ollama pull qwen2.5:3b` (unos 2 GB).
2. Dejá Ollama abierto (se inicia solo con Windows) y reiniciá Jarvis. No hay nada más que configurar.
3. El modelo se consulta **solo si las frases fijas no entienden** y solo cuando decís "Jarvis" directamente.
4. Seguridad: el modelo no ejecuta nada. Solo elige entre las acciones de la lista (abrir apps/carpetas/sitios
   que existen en `config.json`, discos, búsquedas, volumen, etc.). Cualquier otra cosa se descarta, y
   apagar/reiniciar siguen pidiendo "confirmo".
Para cambiar de modelo o apagarlo: en `config.json` agregá `"llm": {"model": "llama3.2:3b"}` o `"llm": {"enabled": false}`.
Si Ollama no está instalado o está apagado, Jarvis funciona igual y lo anota en el log.

## Agregar tus cosas
Editá `config.json`. Ejemplo:
```json
{
  "browser": "brave",
  "apps": { "logo soft": "C:\\Program Files (x86)\\Siemens\\LOGOComfort\\LOGOComfort.exe" },
  "folders": { "tesis": "H:\\Facultad\\Tesis" },
  "sites": { "campus": "https://tu-campus.edu.ar" }
}
```
Después decís "Jarvis, abrí tesis". Si una app no se abre, poné la ruta completa al `.exe`.

## Seguridad
- Solo hace lo de la tabla de arriba: no ejecuta comandos libres ni escribe/borra archivos.
- Apagar y reiniciar siempre piden confirmación.
- Todo queda anotado en el log.

## Estructura
- `jarvis/commands.py` entiende frases; `actions.py` las ejecuta; `assistant.py` maneja la palabra de activación y confirmaciones;
  `listener.py` es el micrófono + Whisper; `speaker.py` es la voz.

## Pendiente / ideas
Tareas (empleo, facultad, tesis),
ícono en la bandeja y palabra de activación más liviana.
