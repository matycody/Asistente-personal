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

Decí **"Jarvis"** en cualquier parte de la frase: al principio, al final o en el medio.
"Jarvis, abrí Brave", "abrí Brave, Jarvis" y "abrí, Jarvis, el Brave" son lo mismo.
Suena un pitido corto cuando te escuchó, y después de una orden sigue atento 6 segundos
sin que repitas el nombre.

### La PC
| Decís | Hace |
|---|---|
| "Jarvis, abrí Brave" | abre Brave |
| "abrí el eFootball, Jarvis" | abre un juego de Steam |
| "abrí la papelera de reciclaje" | carpetas del sistema |
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

## 3. La interfaz

Al arrancar, Jarvis abre su propia interfaz en el navegador. Es una página que sirve él
mismo, **en tu PC**: no sale a internet y nadie más la puede ver.

```
  ┌──────────────────────────────────────────────────────┐
  │ J.A.R.V.I.S.   ● escuchando                   00:42  │
  ├──────────┬───────────────────────────────────────────┤
  │ Monitor  │        ╭───────────╮      Pendientes      │
  │ Pendient.│        │  reactor  │      1 entregar TP   │
  │ Registro │        ╰───────────╯      2 comprar cable │
  │ Órdenes  │     ▁▃▅█▇▅▃▁ onda en vivo                 │
  │          │     TE ESCUCHÉ: abrí brave                │
  │ oído ·   │                           Sistema         │
  │ cerebro ·│                           whisper · small │
  ├──────────┴───────────────────────────────────────────┤
  │ Escribile una orden…            [Pausar]  [Salir]    │
  └──────────────────────────────────────────────────────┘
```

- El **reactor y la onda** se mueven con tu voz de verdad: la barra central reacciona al
  nivel del micrófono, y todo cambia de color según el estado (cian escuchando, ámbar
  pensando, verde hablando, gris en pausa).
- **Monitor**: lo último que te escuchó, tus pendientes y qué motores está usando.
- **Pendientes**: la lista, con un ✓ para marcar cada uno como hecho.
- **Registro**: todo lo que pasó en la sesión.
- **Órdenes**: la lista de lo que podés decir, por si te olvidás.
- Abajo podés **escribirle** una orden en vez de hablarla: hace exactamente lo mismo.
- Queda un **ícono al lado del reloj** para pausar o cerrar sin buscar la ventana.

Se abre como ventana propia (sin barra de direcciones) si tenés Brave, Chrome o Edge.
Jarvis busca el ejecutable en el registro de Windows y en las carpetas habituales; si no
lo encuentra, usa el navegador predeterminado. La dirección siempre queda impresa en la
consola, así la podés pegar a mano.

**Seguridad.** El servidor escucha solo en `127.0.0.1`, así que no se ve desde otra
computadora. Además, cada arranque genera un código al azar que va en la dirección: sin
ese código no se puede ni mirar el estado ni mandarle órdenes, ni siquiera desde tu
propia PC.

Si preferís otra cosa, en `config.json`:
`"interfaz": "ventana"` (una ventana simple de tkinter) o `"interfaz": "ninguna"`.
Para que no se abra sola al arrancar: `"abrir_al_arrancar": false`.
La dirección queda siempre en la consola y en el log.

---

## 4. Todo lo que hay en tu PC

La primera vez que arranca, Jarvis hace un inventario de la máquina en segundo plano:

- **todo el menú Inicio**: programas de escritorio y apps de la Microsoft Store
- **los accesos directos** del escritorio
- **los juegos de Steam**, con su identificador para lanzarlos
- **los discos conectados**, por letra y por etiqueta ("abrí el disco de juegos")
- **carpetas del sistema**: papelera, panel de control, impresoras, descargas…

Después alcanza con nombrarlos: *"Jarvis, abrí el eFootball"*, *"abrí la papelera, Jarvis"*.

En la sección **Programas** de la interfaz están todos listados, con buscador. Tocá
cualquiera para abrirlo, o para ver cómo se llama exactamente.

Para rearmar la lista cuando instalás algo nuevo:

```
.venv\Scripts\python.exe -m jarvis --indexar
```

**Cómo elige.** Primero lo que vos pusiste en `config.json` (eso siempre manda), después
el nombre exacto, después el nombre completo dentro de la frase y recién al final algo
parecido, con un criterio exigente para que no abra cualquier cosa. Si no está seguro,
prefiere decirte que no lo encontró.

**Qué NO hace.** Abre cosas, no las borra ni las desinstala. Apagar, reiniciar y borrar
pendientes siguen pidiendo que digas "confirmo".

---

## 5. Órdenes libres (opcional, con Ollama)

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

## 6. La voz

Para elegirla, corré **`voz_natural.bat`** y seguí el menú. Todas son gratis y ninguna
pide cuenta ni clave.

| | Voz | Cómo suena | Dónde corre |
|---|---|---|---|
| 1 | **Tomás, argentino** — recomendada | muy natural | internet |
| 2 | Jorge, mexicano | muy natural | internet |
| 3 | Álvaro, de España | muy natural | internet |
| 4 | Elena, argentina | muy natural | internet |
| 5 | Hombre latinoamericano (Piper) | aceptable | tu PC |
| 6 | Hombre de España (Piper) | aceptable | tu PC |
| 7 | Mujer argentina (Piper) | aceptable | tu PC |
| 8 | La que trae Windows | robótica | tu PC |

**Sobre las primeras cuatro.** Son las voces neurales de Microsoft Edge, las mismas que
usan los videos que andan dando vuelta. Son gratis y sin cuenta, pero **no son locales**:
el texto de las respuestas de Jarvis viaja a Microsoft para que lo devuelva hablado.
Lo que decís por el micrófono **nunca sale de tu PC**: eso lo sigue resolviendo Whisper
acá. Si se corta internet, Jarvis pasa solo a una voz local y sigue andando.

Si querés que **nada** salga de tu PC, usá la 5. Suena peor, pero es totalmente offline.

### Si no se escucha nada

```
.venv\Scripts\python.exe -m jarvis --voz
```

Lista las voces instaladas, prueba cada motor y dice cuál anda. Si ninguno suena, pegame
lo que imprime.

### Los motores, por dentro

| Motor | Qué es | Hace falta |
|---|---|---|
| `edge` | voces neurales de Microsoft | `pip install edge-tts soundfile` + internet |
| `piper` | voz neural local | bajar el modelo (lo hace `voz_natural.bat`) |
| `powershell` | la voz que trae Windows (System.Speech) | nada |
| `pyttsx3` | el paquete de Python | a veces queda mudo desde otro hilo |

Con `"motor": "edge"` prueba Edge y, si falla, cae a los locales en ese orden.
Con `"motor": "auto"` **nunca** sale de tu PC.

Otros ajustes en `config.json`:
- otra voz de Edge: `"voz": { "nombre_voz": "es-MX-JorgeNeural" }`
- más rápida: `"voz": { "velocidad": 210 }`, o `"ritmo": 0.9` en Piper

---

## 7. Que vaya más rápido

Medí cuánto tarda **en tu PC**:

```
.venv\Scripts\python.exe -m jarvis --banco
```

Graba 3 segundos tuyos, mide la escucha y el modelo, y te dice qué conviene cambiar.

Lo que ya viene optimizado:

- **El modelo se precarga al arrancar** y se queda en memoria 30 minutos, así la primera
  orden no espera a que cargue.
- **Whisper usa todos los núcleos** de tu CPU, y la placa de video si tenés una NVIDIA
  (`"whisper_device": "auto"`).
- **Corta antes la frase**: espera 0.65 s de silencio en vez de 0.9 s.
- **Tope a lo que escribe el modelo**, para que no se vaya en respuestas largas.

Si aún así va lento, en `config.json`:

| Cambio | Efecto |
|---|---|
| `"whisper_model": "base"` | entiende 2 o 3 veces más rápido, un poco menos preciso |
| `"llm": { "model": "qwen2.5:1.5b" }` | órdenes libres mucho más rápidas, menos listas |
| `"silencio_final": 0.5` | responde antes, pero te puede cortar si hacés pausas |
| `"llm": { "enabled": false }` | apaga las órdenes libres: todo lo de las tablas sigue instantáneo |

**Las órdenes de las tablas no pasan por el modelo**: se resuelven al instante. El modelo
solo entra cuando decís algo que las reglas no conocen.

---

## 8. Que entienda mejor

Jarvis ahora **recuerda las últimas dos vueltas**, así podés encadenar ("abrí Brave"…
"ahora buscá recetas ahí"), y responde preguntas sueltas con voz.

Si tenés 16 GB de RAM o más, un modelo más grande entiende bastante mejor:

```
ollama pull qwen2.5:7b
```
y en `config.json`: `"llm": { "model": "qwen2.5:7b" }`

Va a tardar más por orden. Corré `--banco` antes y después para comparar con números
en vez de a ojo.

---

## 9. Configurarlo a tu gusto

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

  "voz": { "genero": "masculina", "ritmo": 0.95 },
  "llm": { "model": "qwen2.5:3b", "contexto": 2 },

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

## 10. Si algo no anda

| Problema | Qué hacer |
|---|---|
| Se activa solo con ruido | subí `"umbral_voz"` a 5 o 6 en `config.json` |
| Te entiende mal | `"whisper_model": "medium"` (más preciso, más lento) |
| Va lento | `python -m jarvis --banco` y seguí lo que te diga |
| No se escucha la voz | `python -m jarvis --voz` y seguí lo que diga |
| La voz suena robótica | `voz_natural.bat` y elegí la opción 1 |
| La voz suena femenina | tu Windows no tiene voces de hombre: `voz_natural.bat`, opción 1 |
| No arranca con Windows | `powershell -ExecutionPolicy Bypass -File autoarranque.ps1 estado` |
| No encuentra un programa | `python -m jarvis --indexar`, y fijate el nombre exacto en la sección Programas |
| No se abre la interfaz | la dirección queda impresa en la consola: pegala en el navegador |
| No abre Brave | revisá `"browser"` en `config.json`, o dejalo en `""` para el predeterminado |
| Querés sacar el autoarranque | `powershell -ExecutionPolicy Bypass -File autoarranque.ps1 quitar` |
| Quiero ver qué pasó | `notepad %LOCALAPPDATA%\Jarvis\jarvis.log` |

El log anota lo que escuchó, lo que descartó por ruido y cada acción. Si algo falla, ahí está.

---

## 11. Cómo está hecho

| Archivo | Qué hace |
|---|---|
| `jarvis/listener.py` | micrófono + Whisper, y descarta ruido y frases inventadas |
| `jarvis/commands.py` | convierte frases en intenciones (no ejecuta nada) |
| `jarvis/llm.py` | órdenes libres con Ollama, validadas contra una lista cerrada |
| `jarvis/assistant.py` | palabra de activación, ventana de seguimiento, confirmaciones |
| `jarvis/actions.py` | ejecuta las intenciones en Windows |
| `jarvis/tasks.py` | clima, pendientes, empleo, facultad |
| `jarvis/indice.py` | el inventario de la PC: menú Inicio, Steam, discos, carpetas |
| `jarvis/navegador.py` | encuentra y lanza el navegador |
| `jarvis/powershell.py` | corre PowerShell sin que la codificación rompa nada |
| `jarvis/webui.py` + `web/index.html` | la interfaz: servidor local y página |
| `jarvis/hud.py` / `tray.py` | ventana simple de respaldo e ícono del reloj |
| `jarvis/speaker.py` / `voz.py` | los tres motores de voz, el diagnóstico y los pitidos |
| `jarvis/bench.py` | el banco de pruebas de velocidad |

Para correr las pruebas: `.venv\Scripts\python.exe -m unittest discover -s tests -t .`

## Ideas para más adelante
Recordatorios con aviso a una hora, dictado de texto a la ventana activa, y un modo
"pregunta" que consulte a un modelo más grande solo cuando lo pidas.
