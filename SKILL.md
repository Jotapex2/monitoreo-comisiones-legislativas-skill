---
name: monitoreo-comisiones-legislativas
description: "Monitoreo en vivo, catchup DVR, alertas en tiempo real, transcripción incremental y redacción de Minutas Ejecutivas e Informes de Comisión y de Sala para el Congreso Nacional de Chile (Cámara de Diputadas y Diputados y Senado). Ingesta dual avanzada: YouTube Live/DVR por secuencia /sq/ con captura de chyrons (IDR keyframes) y tv.senado.cl / Janus Media (janux-tv y janux-1..5 con limits.json, .ts, API de cápsulas MP4 y thumbnails históricos). Transcripción local (faster-whisper + Silero VAD + condition_on_previous_text=False) o en nube (Groq Whisper). Integración con datos-congreso y generación de entregables en .md y Word (.docx): Minuta Ejecutiva (~2.5 págs), Informe de Comisión e Informe de Sesión de Sala."
---

# Monitoreo de Comisiones y Salas Legislativas (En Vivo, Alertas, Minutas e Informes)

Esta skill cubre el ciclo completo de inteligencia legislativa en tiempo real e histórica para sesiones de **Comisiones** y **Salas** de la **Cámara de Diputadas y Diputados** y del **Senado de la República de Chile**, desde la captura de transmisión hasta la entrega de documentos ejecutivos e institucionales en Markdown y Word (`.docx`).

---

## 1. Arquitectura de Ingesta Dual (Cámara vs. Senado)

### A. Cámara de Diputadas y Diputados (YouTube Live & DVR `/sq/`)
* **Plataforma:** Canales oficiales de YouTube (`CamaraDiputadosChile`, señales `Online 01` a `Online 13+` y Sala).
* **Motor recomendado (`scripts/youtube_dvr_monitor.py`):**
  - Resuelve el playlist HLS solo audio con `yt-dlp --no-update -f 234 -g` (fallback `ba[protocol^=m3u8]/ba/b`).
  - Descarga por secuencia monotónica **`/sq/N/`** con estado persistente (`monitor_state.json`), **auto-detección de duración de segmento desde `#EXTINF:`** (1 s, 2 s o 5 s según stream) y **refresh automático del playlist cada 20 min**.
  - Convierte a WAV 16 kHz mono y valida duración real con `wave.open`.
  - **Catchup + Vivo automático:** procesa bloques grandes (~5 min) si la sesión ya empezó y baja a bloques cortos (~90 s) al llegar al borde en vivo; detecta cierre vía `#EXT-X-ENDLIST` y `yt-dlp --dump-single-json` (`is_live`).
* **Detalle técnico y bypass anti-bot en VPS:** ver `references/youtube-dvr-chyrons.md`.

### B. Senado de la República (`tv.senado.cl` / Janus Media)
* **Servidores conocidos:** `janux-tv.senado.cl` (Sala/TV Senado), `janux-1`, `janux-2`, `janux-3`, **`janux-5`** (y auto-descubrimiento desde el HTML de cualquier página de `tv.senado.cl` vía `scripts/live_stream_monitor.py`).
* **Verificación de señal activa (`limits.json`):**
  - `https://janux-{ch}.senado.cl/playlist/limits.json` → si `time.time() - last > 90`, el canal está fuera del aire.
* **Tres vías de extracción en Janus** (detalle completo en `references/janus-senado-endpoints.md`):
  1. **Monitor continuo por `.ts` (`scripts/senado_live_monitor.py`):** lee `stream.m3u8?s=sd` (o histórico `&t={epoch}`), descarga `sd_{ts}.ts` en paralelo con `ThreadPoolExecutor`, remuxea con `ffmpeg` y persiste `last_ts`.
  2. **API nativa de Cápsulas MP4 (`scripts/live_stream_monitor.py capsule`):** `POST /api/get_front_capsule.rb` + poll `GET /api/get_front_status.rb/{pid}` para descargar tramos históricos exactos en MP4. Combinable con `ffmpeg -af volumedetect` (`live_stream_monitor.py volume`) para detectar en qué minuto exacto termina la placa silenciosa e inicia el debate.
  3. **Respaldo YouTube de TV Senado:** útil cuando se necesita DVR más largo (~1–2 h) que la ventana corta del playlist vivo de `janux-tv`.

---

## 2. Flujo de Trabajo en Vivo, Alertas y Chyrons

```
[YouTube /sq/ o Janus .ts] ─► [Bloques verificados + monitor_state.json]
        │                                       │
        ├─► [faster-whisper + Silero VAD        ├─► [seguimiento_en_vivo_YYYY-MM-DD.md]
        │    + condition_on_previous_text=False]└─► [alertas_detectadas.md + .json]
        │
        └─► [grab_chyrons.py] ────────────────────► [Frames PNG / Thumbnails Janus]
```

### Paso 1: Transcripción Incremental y Perfiles de Whisper
* Activar **siempre** `vad_filter=True` (`min_silence_duration_ms=500`) y **`condition_on_previous_text=False`** para evitar bucles alucinatorios durante placas de espera, silencios o votaciones.
* **Perfiles locales (`faster-whisper` en CPU `int8`):**
  - **Alta precisión** (`--model small --beam-size 5`): ideal para sesiones de Comisión o Sala de las que se redactará Informe completo.
  - **Alta velocidad / maratón** (`--model base --beam-size 1`): ideal para sesiones extensas (ej. Ley de Presupuestos 8–12 h) donde prima velocidad de alerta en vivo.
* **Nube (Groq Whisper):** modelo `whisper-large-v3-turbo` (`temperature=0`, `response_format="verbose_json"`), filtrando segmentos con `no_speech_prob > 0.6 and avg_logprob < -1`.

### Paso 2: Alertas en Tiempo Real (Regex)
* Tanto `youtube_dvr_monitor.py` como `senado_live_monitor.py` admiten `--keywords "palabra1, palabra2"` o `--alerts-config archivo.json` (sumados a las alertas automáticas de votación, indicaciones, inadmisibilidad, reserva de constitucionalidad y cierre de sesión).
* Cada coincidencia se imprime en consola y se registra simultáneamente en **`alertas_detectadas.md`** y **`alertas_detectadas.json`** con marca horaria y texto exacto.

### Paso 3: Identificación de Oradores (Chyrons + `datos-congreso`)
1. **Chyrons sin bajar video completo (`scripts/grab_chyrons.py`):**
   - **YouTube (`grab_chyrons.py youtube`):** usa formato `-f 231` (480p HLS) y concatena **3 a 4 segmentos consecutivos** por punto objetivo para garantizar un **IDR keyframe** antes de extraer 1 PNG. Soporta lista puntual (`--sqs`) o loop paralelo continuo cada ~20 s.
   - **Senado (`grab_chyrons.py senado`):** descarga directo los thumbnails JPEG de Janus cada 10–120 s (`janux-{ch}-jhs.senado.cl/hls/thumb/...`).
2. **Servidor MCP `datos-congreso` (ver `references/cruce-datos-congreso.md`):**
   - `search_politicians` / `get_politician_by_id` para confirmar nombre legal completo, partido exacto (`PS`, `RN`, `UDI`, `PC`, `REP`, `PL`, `PDG`, `FA`, `PNL`, `PR`, `PPD`, `DC`, `EVOP`, `Ind.`) y distrito/circunscripción.
   - `get_bill_by_id` / `list_tramitaciones` para título oficial del boletín, trámite, urgencia y mensajes.

---

## 3. Cierre de Sesión y Generación de Entregables

Al cerrar la transmisión (o cuando el usuario solicite corte parcial/final), consolidar los productos en `.md` y `.docx` usando `scripts/generate_commission_docs.py`:

```
                     ┌──► MINUTA EJECUTIVA (~2.5 págs / o Cierre Presupuestos) ──► .docx + .md
[Seguimiento +       │
 Chyrons + MCP] ─────┼──► INFORME DE COMISIÓN (Institucional completo) ──────────► .docx + .md
                     │
                     └──► INFORME DE SESIÓN DE SALA (Pleno por punto en tabla) ──► .docx + .md
```

### Producto 1: MINUTA EJECUTIVA (~2.5 páginas)
* **Plantilla completa:** `references/plantilla-minuta.md`.
* **Estructura fija:** Encabezado y tabla de metadatos (clásica o ampliada con horario, sala, parlamentarios y autoridades) → `I. Antecedentes Generales y Objeto` → `II. Intervenciones y Posiciones por Expositor` → `III. Artículos Leídos por Secretaría y Votaciones` (admite `quote_box` para lecturas textuales y `tabla` para resúmenes multi-votación) → `IV. Resolución Final y Próximos Pasos`.
* **En cierres parciales / Presupuestos:** separar explícitamente **Confirmado**, **Anunciado (no confirmado)** y **Pendiente / tramos sin transcripción**.
* **Formato Word:** Calibri 10.5pt, interlineado 1.15, paleta Navy Institucional (`#1A365D`, `#2B6CB0`), recuadros con borde izquierdo y tablas limpias.

### Producto 2: INFORME DE COMISIÓN (Institucional Completo)
* **Plantilla completa:** `references/plantilla-informe.md`.
* **Estructura:** Encabezado (Comisión, Cámara, Fecha) → Orden del día (con Boletines e invitados convocados) → Asistentes (parlamentarios con partido, reemplazos certificados, autoridades del Ejecutivo, invitados, secretaría) → Puntos en Tabla (Exposiciones individualizadas y Debate cronológico en **primera persona** estilo transcripción editada `[Nombre] ([PARTIDO]):`, Indicaciones y Votaciones con conteo exacto) → Estado Final / Despacho.

### Producto 3: INFORME DE SESIÓN DE SALA (Pleno)
* **Plantilla completa:** `references/plantilla-informe.md` (sección *Variante: Informe de Sesión de Sala*).
* **Estructura:** Encabezado con Legislatura, Sesión N°, Boletín, Trámite, Urgencia/Mensaje y Estado → `I. Autoridades del Ejecutivo Presentes` → `II. Informes de Comisiones Técnicas` (diputados/senadores informantes, votaciones en comisión e Informes Financieros DIPRES) → `III. Resumen de Intervenciones en Sala` (cronológico con nombre, partido, distrito/región, marcas horarias y posición) → `IV. Intervención de Cierre del Ejecutivo` → `V. Votaciones (General + Votaciones Separadas con solicitantes) y Despacho`.

---

## 4. Catálogo de Scripts y Referencias

### `scripts/`
| Script | Uso |
|---|---|
| `youtube_dvr_monitor.py` | Monitor verificado YouTube Live/DVR por `/sq/` con catchup, `#EXTINF`, Whisper y alertas `.md`/`.json`. |
| `senado_live_monitor.py` | Monitor en vivo y catchup histórico por `.ts` para Senado (`janux-tv`, `1`, `2`, `3`, `5`) con alertas. |
| `live_stream_monitor.py` | Utilidades duales: captura simple, auto-descubrimiento `tv.senado.cl`, `limits.json`, cápsulas MP4 Janus y `volumedetect`. |
| `grab_chyrons.py` | Extracción de chyrons: YouTube `-f 231` (3–4 segs por keyframe IDR, puntual o loop) y thumbnails Janus Senado. |
| `transcribe_chunks.py` | Transcriptor incremental standalone con `faster-whisper` (`vad_filter=True`, `condition_on_previous_text=False`). |
| `generate_commission_docs.py` | Compilador Word (`.docx`) para Minuta Ejecutiva (con `quote_box`, `tabla` y `metadatos` ampliados) e Informe de Comisión/Sala. |

### `references/`
* `janus-senado-endpoints.md` — Endpoints `janux-*`, `limits.json`, cápsulas MP4, `volumedetect` y thumbnails.
* `youtube-dvr-chyrons.md` — Motor `/sq/`, `#EXTINF`, IDR keyframes `-f 231`, cookies y respaldo Chromium.
* `plantilla-minuta.md` / `plantilla-informe.md` — Estándares editoriales para Minuta, Informe de Comisión e Informe de Sala.
* `cruce-datos-congreso.md` / `glosario-congreso-chile.md` — Verificación MCP `datos-congreso` y terminología parlamentaria chilena.

---

## 5. Reglas de Calidad, Rigor Legislativo y Anti-Alucinación

1. **Nunca inventar ni inferir datos ausentes:** No inventar siglas partidarias, nombres, cifras, resultados numéricos ni respuestas del Ejecutivo que no consten en la transcripción o en `datos-congreso`. Si un dato falta o un tramo quedó sin transcribir, declararlo explícitamente (*"la transcripción no registra respuesta"*, *"bloque sin desglose numérico"*, *"tramo pendiente"*).
2. **Fidelidad a las lecturas de la Secretaría y votaciones:** Transcribir con máxima fidelidad los artículos e indicaciones leídos por secretaría, registrar conteos exactos, quiénes pidieron votación separada y toda **reserva de constitucionalidad (art. 65 inc. 3°)**.
3. **Individualización obligatoria y redacción en primera persona:** Prohibido agrupar bajo rótulos genéricos como *"el Ejecutivo expuso"* o *"los invitados señalaron"*. Individualizar siempre a cada parlamentario (nombre completo y partido), cada autoridad del Ejecutivo (nombre completo y cargo oficial exacto) y cada invitado (nombre, cargo y organización). **Todas las exposiciones, resúmenes de intervenciones, preguntas y respuestas —tanto en informes como en actualizaciones en vivo— deben redactarse en primera persona** (ej.: `**[Nombre] ([Cargo/Partido]):** ...`).
4. **Imparcialidad analítica y extensión:** Tono técnico neutral sin sesgo. La Minuta Ejecutiva se mantiene en torno a 2.5 páginas; el Informe de Comisión o Sala registra todo el detalle sustantivo sin límites artificiales.
5. **Seguridad de credenciales:** Nunca hardcodear claves de API ni cookies de YouTube en scripts; usar siempre variables de entorno o archivos con permisos `600`.
