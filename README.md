# Monitoreo de Comisiones y Salas Legislativas (Chile)

Skill de inteligencia legislativa en tiempo real e histórica para sesiones de **Comisiones** y **Salas** de la **Cámara de Diputadas y Diputados** y del **Senado de la República de Chile**. Cubre desde la ingesta dual de transmisiones y transcripción incremental hasta la generación de **Minutas Ejecutivas**, **Informes de Comisión** e **Informes de Sesión de Sala** en Markdown y Word (`.docx`).

>Creada por Juan Pablo González Urriola
---

## Características principales

- **Ingesta dual (Cámara + Senado):**
  - **Cámara de Diputadas y Diputados:** Descarga en vivo y *catchup* DVR desde YouTube Live por secuencia monotónica `/sq/` (`yt-dlp` + `ffmpeg`), con estado persistente (`monitor_state.json`) y auto-detección de duración de segmento (`#EXTINF`).
  - **Senado (`tv.senado.cl` / Janus Media):** Monitoreo continuo por segmentos `.ts` en servidores `janux-*`, verificación de señal activa vía `limits.json`, descarga de cápsulas MP4 históricas y detección de inicio de debate con `volumedetect`.
- **Transcripción incremental:**
  - Local con `faster-whisper` + Silero VAD (`vad_filter=True`, `condition_on_previous_text=False`) en perfiles de alta precisión (`small`) o velocidad (`base`).
  - Compatible con transcripción en nube (Groq Whisper `whisper-large-v3-turbo`).
- **Alertas en tiempo real:** Detección por expresiones regulares (`--keywords` / `--alerts-config`) más alertas parlamentarias automáticas (votación, indicaciones, inadmisibilidad, reserva de constitucionalidad, cierre de sesión), registradas en `.md` y `.json`.
- **Identificación de oradores y cruce legislativo:**
  - Extracción ligera de *chyrons* sin bajar el video completo (frames IDR `-f 231` en YouTube y thumbnails de Janus en Senado).
  - Cruce con el servidor MCP `datos-congreso` para validar nombres legales, partidos, distritos/circunscripciones y boletines.
- **Entregables institucionales (`.md` y `.docx`):**
  - **Minuta Ejecutiva** (~2.5 páginas).
  - **Informe de Comisión** (completo, con debate cronológico en primera persona y votaciones).
  - **Informe de Sesión de Sala** (pleno por punto, informes técnicos, votaciones generales y separadas).

---

## Estructura del repositorio

```text
├── SKILL.md                          # Instrucciones principales de la skill
├── scripts/
│   ├── youtube_dvr_monitor.py        # Monitor YouTube Live/DVR (/sq/) + Whisper + alertas
│   ├── senado_live_monitor.py        # Monitor en vivo y catchup .ts para Senado (Janus)
│   ├── live_stream_monitor.py        # Utilidades tv.senado.cl, limits.json y cápsulas MP4
│   ├── grab_chyrons.py               # Extracción de chyrons (YouTube -f 231 / Janus thumbs)
│   ├── transcribe_chunks.py          # Transcriptor incremental standalone (faster-whisper)
│   └── generate_commission_docs.py   # Generador Word (.docx) de Minutas e Informes
└── references/
    ├── janus-senado-endpoints.md     # Endpoints Janus del Senado y cápsulas MP4
    ├── youtube-dvr-chyrons.md        # Detalle técnico /sq/, keyframes IDR y cookies
    ├── plantilla-minuta.md           # Estándar editorial de Minuta Ejecutiva
    ├── plantilla-informe.md          # Estándar editorial de Informe de Comisión y Sala
    ├── cruce-datos-congreso.md       # Integración con MCP datos-congreso
    └── glosario-congreso-chile.md    # Terminología parlamentaria chilena
```

---

## Requisitos

- **Python 3.10+**
- **FFmpeg** y **yt-dlp** en el `PATH`
- Dependencias Python según los scripts que utilices:
  - `faster-whisper` (transcripción local)
  - `python-docx` (compilación de documentos `.docx`)
  - `requests` (consultas HTTP a Janus)

---

## Instalación como skill

Clona este repositorio en tu directorio de skills de Antigravity/agente:

```bash
git clone https://github.com/Jotapex2/monitoreo-comisiones-legislativas-skill.git ~/.gemini/config/skills/monitoreo-comisiones-legislativas
```
Aunque funciona con cualquier agente de IA (Command code, Opencode, Claude, Codex, etc. Solo con pegar el link de github y pedir que lo instale estás listo :)
O consulta [SKILL.md](SKILL.md) para el flujo completo de trabajo y los comandos de cada script.
