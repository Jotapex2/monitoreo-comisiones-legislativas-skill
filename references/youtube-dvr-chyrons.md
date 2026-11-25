# Referencia Técnica: YouTube Live / DVR (`/sq/`) y Captura de Chyrons

Las transmisiones de la **Cámara de Diputadas y Diputados** (`CamaraDiputadosChile`, señales `Online 01` a `Online 13+`, además de Sala) y el respaldo de **TV Senado** operan sobre YouTube Live con DVR HLS.

---

## 1. Por qué usar DVR por secuencia (`/sq/`) en lugar de `ffmpeg -t`

Capturar con `ffmpeg -i <url> -t 300` solo graba hacia adelante en tiempo real y pierde audio si el enlace expira o si el monitoreo comienza tarde. El motor por secuencia `/sq/` (`scripts/youtube_dvr_monitor.py`) resuelve esto:

1. **Resolución del playlist HLS de solo audio:**
   ```bash
   yt-dlp --no-update -f 234 -g --no-warnings "<YOUTUBE_URL>"
   ```
   *(Formato `234` es HLS solo audio AAC de YouTube Live; si no existe, usar fallback `-f "ba[protocol^=m3u8]/b[protocol^=m3u8]/ba/b"`).*
2. **Estructura del playlist (`index.m3u8`):**
   - Cada URL de segmento contiene `/sq/(\d+)/` (número de secuencia monotónico).
   - **Duración variable por segmento:** Según la transmisión, cada segmento puede durar **1 s, 2 s o 5 s**. Leer siempre la etiqueta `#EXTINF:<dur>,` del `.m3u8` en lugar de asumir un valor fijo, para calcular correctamente las marcas de tiempo (`sq * seg_seconds`).
   - El fin definitivo del stream se detecta con `#EXT-X-ENDLIST` en el playlist y confirmación vía `yt-dlp --dump-single-json` (`is_live == False`).
3. **Catchup automático + modo en vivo:**
   - Si hay gran backlog disponible (ej. sesión iniciada hace 1 hora), procesar bloques grandes (ej. ~5 minutos) hasta alcanzar el borde en vivo.
   - Cerca del live edge, cambiar automáticamente a bloques cortos (ej. 90 a 180 segundos) para entregar lectura en tiempo real.
4. **Descarga verificada y refresh de playlist:**
   - Las URLs firmadas de `googlevideo.com` expiran periódicamente. Refrescar el `m3u8` cada **20 minutos** o automáticamente cuando falle la descarga de algún segmento.
   - Convertir los `.ts` concatenados a WAV 16 kHz mono (`ffmpeg -y -i chunk.ts -vn -ar 16000 -ac 1 chunk.wav`) y verificar su duración real con `wave.open`.
   - Persistir progreso (`next_sq`, `chunk_idx`) en `monitor_state.json` para reanudar sin duplicados ni vacíos tras cualquier interrupción.

---

## 2. Captura de Fotogramas y Chyrons sin Descargar el Video Completo

Para identificar oradores, autoridades, invitados o tableros de votación en pantalla (especialmente en sesiones de Sala con 20+ intervenciones):

1. Resolver el playlist HLS de video 480p (liviano y nítido para leer generadores de caracteres):
   ```bash
   yt-dlp --no-update -f 231 -g --no-warnings "<YOUTUBE_URL>"
   ```
2. **Truco del Keyframe IDR:** Un solo segmento `.ts` de 1–2 s a menudo no contiene un cuadro clave (IDR), provocando que `ffmpeg` falle o genere un PNG vacío. Descargar siempre **3 a 4 segmentos consecutivos (`sq` a `sq + 3`)**, concatenarlos en un `.ts` temporal y extraer un único fotograma:
   ```bash
   ffmpeg -y -loglevel error -i tmp.ts -vframes 1 frame_sq01234.png
   ```
3. **Modo paralelo en vivo (`scripts/grab_chyrons.py youtube --loop`):** Ejecutar un recolector liviano cada ~20 segundos durante sesiones largas de Sala o Comisión para tener una galería de chyrons indexada por `sq`.

---

## 3. Evasión Limpia de Bloqueos de YouTube en VPS / Servidores Cloud

En IPs de datacenter (VPS), YouTube suele responder `ERROR: Sign in to confirm you're not a bot`.

1. **Flags recomendados para `yt-dlp`:**
   ```bash
   yt-dlp --ignore-config --force-ipv4 --impersonate chrome --no-playlist \
          --cookies /etc/congreso-youtube.cookies \
          -f "ba[protocol^=m3u8]/b[protocol^=m3u8]/ba/b" --dump-single-json "<URL>"
   ```
   Requiere `yt-dlp[default,curl-cffi]` y **Deno** disponible en el `PATH` (para resolución EJS de YouTube).
2. **Cookies dedicadas:** Exportar únicamente las cookies de `youtube.com` en formato Netscape desde una cuenta dedicada y guardarlas con permisos `600`.
3. **Respaldo Chromium + Playwright (`scripts/congreso_browser.py`):**
   - Si falla la ruta directa `yt-dlp`, abrir Chromium headless con un perfil persistente e importar las cookies de YouTube.
   - Capturar el audio directo desde el elemento `<video>` mediante `video.captureStream().getAudioTracks()` + `MediaRecorder('audio/webm;codecs=opus', {audioBitsPerSecond: 48000})`.
   - Vigilar automáticamente anuncios (`#movie_player.ad-showing`), estancamientos de `video.currentTime` (>30 s), fin de transmisión (`video.ended`) y pantallas de login.
