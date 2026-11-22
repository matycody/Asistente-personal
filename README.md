# Jarvis — asistente de voz local para Windows

Escucha tu micrófono, entiende órdenes en español y maneja la PC. **Todo corre en tu
máquina y es gratis**: no hay cuentas, ni claves de API, ni audio que salga a internet.
Arranca solo con Windows.

```
Vos hablás  →  Whisper (local)  →  órdenes fijas  →  acciones en Windows
                                   └→ Ollama (local, opcional) para órdenes libres
Jarvis responde  ←  Piper o la voz de Windows (local)
```

---

## 1. Instalar

1. Instalá **Python 3.10 o más** desde python.org (tildá *"Add python.exe to PATH"*).
2. Hacé doble clic en **`instalar.bat`**.
3. Probalo **sin micrófono y sin ejecutar nada**:
   ```
   .venv\Scripts\python.exe -m jarvis --text --dry-run
   ```
4. Probalo con voz:
   ```
   .venv\Scripts\python.exe -m jarvis
   ```
   La primera vez baja el modelo de voz (unos 500 MB). Eso necesita internet una sola vez.

> **No lo dejes dentro de OneDrive.** OneDrive puede mover o liberar los archivos y romper
> el arranque automático. Movelo a `C:\Jarvis` y volvé a correr `instalar.bat`.

Para traer mejoras: `git pull` y listo.

---

## 2. Qué le podés decir

Empezá con **"Jarvis"**. Suena un pitido corto cuando te escuchó, y después de una orden
sigue atento 6 segundos sin que repitas el nombre.

### La PC
| Decís | Hace |
|---|---|
| "Jarvis, abrí Brave" | abre Brave |
| "abrí el explorador y entrá al disco H" | dos acciones seguidas |
| "abrí YouTube" / "abrí Computrabajo" | abre el sitio |
| "buscá recetas de milanesa" / "buscá lofi en YouTube" | búsqueda web |
| "subí / bajá el volumen", "silencio", "pausa", "siguiente canción" | multimedia |
| "minimizá todo", "cerrá esta ventana", "captura de pantalla" | ventanas |
| "bloqueá la PC" | bloquea la sesión |
| "apagá la PC" / "reiniciá" | pide que digas **"confirmo"** |
| "dejá de escuchar" | se pausa (lo reanudás desde la ventana o el ícono) |

### Tu día
| Decís | Hace |
|---|---|
| "Jarvis, buenos días" / "¿cómo viene el día?" | fecha, hora, clima y tus pendientes |
| "¿qué tiempo hace?" / "¿va a llover?" | clima de tu zona |
| "¿qué hora es?" / "¿qué día es hoy?" | te contesta al toque |
| "anotá que el lunes entrego el TP" | lo guarda en pendientes |
| "¿qué tengo pendiente?" | te los lee |
| "listo el dos" | marca el pendiente 2 como hecho |
| "borrá todos los pendientes" | pide **"confirmo"** |
| "buscá empleo" / "buscame trabajo de electricidad" | abre las búsquedas en varios sitios |
| "modo facultad" | abre tus sitios y carpetas de la cursada |

Los pendientes quedan en `%LOCALAPPDATA%\Jarvis\pendientes.json`.

---

## 3. La ventana y el ícono

Al arrancar se abre una ventana chica que muestra el estado (escuchando, procesando,
hablando), lo último que te escuchó y qué hizo. Sirve para ver por qué no entendió algo.

- Botón **Pausar** para que deje de escuchar, **Ocultar** para sacarla de encima.
- Queda un **ícono al lado del reloj**: clic para pausar o reanudar, clic derecho para el menú.
- Si no querés ventana: `python -m jarvis --sin-hud`, o `"hud": false` en `config.json`.

---

## 4. Órdenes libres (opcional, con Ollama)

Sin esto Jarvis entiende las frases de las tablas de arriba. Con un modelo local además
entiende órdenes **con tus palabras** ("llevame a lo que bajé hoy", "no te olvides de
llamar al taller").

1. Instalá Ollama desde https://ollama.com.
2. Bajá el modelo: `ollama pull qwen2.5:3b` (unos 2 GB).
   Si el comando `ollama` no se reconoce, usá la ruta completa:
   `"%LOCALAPPDATA%\Programs\Ollama\ollama.exe" pull qwen2.5:3b`
3. Reiniciá Jarvis. No hay nada más que configurar.

**Cómo se usa.** Primero prueban las frases fijas, que son instantáneas. Solo si no
entienden, y solo cuando dijiste "Jarvis" directamente, se consulta al modelo.

**Seguridad.** El modelo no ejecuta nada: solo elige entre una lista cerrada de acciones
(abrir cosas que estén en `config.json`, discos, búsquedas, volumen, pendientes). Cualquier
otra cosa que invente se descarta, y apagar, reiniciar o borrar pendientes siguen pidiendo
confirmación.

Para cambiar de modelo o apagarlo, en `config.json`:
`"llm": { "model": "llama3.2:3b" }` o `"llm": { "enabled": false }`.

---

## 5. Voz más natural (opcional, también gratis y local)

Por defecto habla con las voces que ya trae Windows. Para una voz neural argentina,
corré **`voz_natural.bat`**: instala Piper y baja la voz `es_AR-daniela` (unos 115 MB).
Después de eso funciona sin internet.

Para volver atrás: `"voz": { "motor": "sapi" }` en `config.json`.

---

## 6. Configurarlo a tu gusto

Todo se toca en **`config.json`**. Solo escribís lo que querés cambiar; el resto sale de
los valores de fábrica (`jarvis/config.py`).

```json
{
  "browser": "brave",
  "umbral_voz": 5.0,

  "apps":    { "logo soft": "C:\\Program Files (x86)\\Siemens\\LOGOComfort\\LOGOComfort.exe" },
  "folders": { "tesis": "H:\\Facultad\\Tesis" },
  "sites":   { "campus": "https://tu-campus.edu.ar" },

  "ubicacion": { "nombre": "Claypole", "lat": -34.80, "lon": -58.34 },

  "empleo": {
    "por_defecto": "programacion",
    "perfiles": {
      "programacion": { "busqueda": "programador junior", "cv": "H:\\CV\\cv-programacion.pdf" },
      "electricidad": { "busqueda": "electricista",       "cv": "H:\\CV\\cv-electricidad.pdf" }
    }
  },

  "facultad": {
    "sitios":   ["https://tu-campus.edu.ar"],
    "carpetas": ["H:\\Facultad"]
  }
}
```

Después decís "Jarvis, abrí tesis" o "Jarvis, abrí LOGO Soft". Si una app no abre, poné la
ruta completa al `.exe`. El clima sale de Open-Meteo, que es gratis y no pide clave.

---

## 7. Si algo no anda

| Problema | Qué hacer |
|---|---|
| Se activa solo con ruido | subí `"umbral_voz"` a 5 o 6 en `config.json` |
| Te entiende mal | `"whisper_model": "medium"` (más preciso, más lento) |
| No arranca con Windows | `powershell -ExecutionPolicy Bypass -File autoarranque.ps1 estado` |
| Querés sacar el autoarranque | `powershell -ExecutionPolicy Bypass -File autoarranque.ps1 quitar` |
| Quiero ver qué pasó | `notepad %LOCALAPPDATA%\Jarvis\jarvis.log` |

El log anota lo que escuchó, lo que descartó por ruido y cada acción. Si algo falla, ahí está.

---

## 8. Cómo está hecho

| Archivo | Qué hace |
|---|---|
| `jarvis/listener.py` | micrófono + Whisper, y descarta ruido y frases inventadas |
| `jarvis/commands.py` | convierte frases en intenciones (no ejecuta nada) |
| `jarvis/llm.py` | órdenes libres con Ollama, validadas contra una lista cerrada |
| `jarvis/assistant.py` | palabra de activación, ventana de seguimiento, confirmaciones |
| `jarvis/actions.py` | ejecuta las intenciones en Windows |
| `jarvis/tasks.py` | clima, pendientes, empleo, facultad |
| `jarvis/hud.py` / `tray.py` | ventana de estado e ícono del reloj |
| `jarvis/speaker.py` | voz (Piper o Windows) y pitidos |

Para correr las pruebas: `.venv\Scripts\python.exe -m unittest discover -s tests -t .`

## Ideas para más adelante
Recordatorios con aviso a una hora, dictado de texto a la ventana activa, y un modo
"pregunta" que consulte a un modelo más grande solo cuando lo pidas.
