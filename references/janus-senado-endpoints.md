# Referencia Técnica: Senado de Chile (`tv.senado.cl` / Janus Media)

El Senado de la República utiliza la plataforma de streaming **Janus Media**, independiente de YouTube, con múltiples servidores de emisión y APIs nativas para stream en vivo, DVR histórico, generación de cápsulas MP4 y miniaturas (thumbnails).

---

## 1. Servidores y Canales Conocidos

| Alias | Host Base | Uso Habitual |
|---|---|---|
| `tv` | `https://janux-tv.senado.cl` | Señal principal TV Senado / Sala del Senado |
| `1` | `https://janux-1.senado.cl` | Sala de Comisiones 1 |
| `2` | `https://janux-2.senado.cl` | Sala de Comisiones 2 |
| `3` | `https://janux-3.senado.cl` | Sala de Comisiones 3 |
| `5` | `https://janux-5.senado.cl` | Sala de Comisiones 5 (y otras salas habilitadas) |

> **Auto-descubrimiento desde una página de `tv.senado.cl`:** Si el usuario comparte una URL de página (ej. `https://tv.senado.cl/tvsenado/comisiones/...`), descargar el HTML con `User-Agent: Mozilla/5.0` y buscar patrones `https?://janux[^\s"'<>]+` o etiquetas `<iframe src="...">` para identificar el servidor `janux-{ch}` exacto.

> **Nota SSL/Headers:** En algunos entornos Windows/Python, las peticiones directas a `janux-*.senado.cl` requieren `User-Agent: Mozilla/5.0`, `Referer: https://tv.senado.cl/` y opcionalmente un contexto SSL tolerante si falla la validación de cadena intermedia.

---

## 2. Verificación de Señal Activa (`limits.json`)

```
GET https://janux-{ch}.senado.cl/playlist/limits.json
```

Respuesta JSON típica:
```json
{"first": 1794320000, "last": 1794327277}
```

- `first` y `last` son timestamps **Unix epoch (UTC en segundos)**.
- **Regla de señal activa:** Si `time.time() - float(last) > 90`, el canal está **fuera del aire** (sesión aún no iniciada o finalizada).

---

## 3. Captura en Vivo y DVR por Segmentos HLS (`.ts`)

- **Playlist en vivo:** `https://janux-{ch}.senado.cl/playlist/stream.m3u8?s=sd`
- **Playlist histórico desde un epoch específico:** `https://janux-{ch}.senado.cl/playlist/stream.m3u8?s=sd&t={start_epoch}`
- Cada segmento tiene nombre `sd_{ts}.ts` y dura ~2 segundos.
- **Flujo recomendado para monitoreo continuo (`scripts/senado_live_monitor.py`):**
  1. Consultar `stream.m3u8?s=sd` cada ~4 segundos.
  2. Acumular 6 a 12 segmentos nuevos (`ts > last_ts`), descargarlos en paralelo (`ThreadPoolExecutor(max_workers=8)`).
  3. Concatenar bytes `.ts`, remuxear audio con `ffmpeg -y -i batch.ts -vn -c:a copy batch.m4a` (o decodificar a WAV 16 kHz mono).
  4. Transcribir con `faster-whisper` (`vad_filter=True`, `condition_on_previous_text=False`) y persistir `last_ts` en `monitor_state.json`.

---

## 4. API Nativa de Cápsulas MP4 (Catchup Histórico Exacto)

Cuando se necesita descargar un tramo histórico completo y exacto (ej. los primeros 30 minutos de una comisión ya iniciada) sin recorrer segmento por segmento:

### Paso 1: Solicitar generación de cápsula
```http
POST https://janux-{ch}.senado.cl/api/get_front_capsule.rb
Content-Type: application/json
Referer: https://tv.senado.cl/

{
  "start": 1794325041,
  "end": 1794325341,
  "stream": "sd",
  "type": "mp4",
  "from": "front"
}
```
Respuesta: `{"status": "OK", "processId": "<pid>"}`.

### Paso 2: Consultar estado hasta `FINISHED`
```http
GET https://janux-{ch}.senado.cl/api/get_front_status.rb/{pid}
```
Cuando `stage == "FINISHED"`, descargar el MP4 desde:
```
https://janux-{ch}.senado.cl{fileInfo.file_path}
```

### Truco: Ubicar el inicio real del audio hablado (`volumedetect`)
Para evitar descargar y transcribir 20-40 minutos de placa de espera silenciosa, solicitar mini-cápsulas de 20 segundos cada 3-5 minutos y medir volumen con FFmpeg:
```bash
ffmpeg -i clip.mp4 -af volumedetect -vn -f null -
```
Buscar `max_volume` en stderr: valores cercanos a `-91 dB` indican silencio/placa; valores sobre `-35 dB` indican audio de sala activo.

---

## 5. Miniaturas Históricas (Thumbnails para Chyrons)

Janus expone fotogramas JPEG cada 10 segundos sin necesidad de descargar video:

```
t_round = epoch - (epoch % 10)
url = f"https://janux-{ch}-jhs.senado.cl/hls/thumb/{t_round - t_round%86400}/{t_round - t_round%3600}/{t_round - t_round%60}/{t_round}.jpg"
```

Usar `scripts/grab_chyrons.py senado --channel 1 --start-epoch ... --end-epoch ...` para recolectar una galería rápida e identificar parlamentarios, invitados y resultados en pantalla.

---

## 6. Respaldo YouTube de TV Senado

El playlist vivo de `janux-tv.senado.cl` mantiene una ventana deslizante corta; si se requiere retroceder 1 a 2 horas en una sesión de Sala del Senado (por ejemplo, Presupuestos), verificar la señal simultánea de **TV Senado en YouTube** y aplicar el motor DVR `/sq/` (`scripts/youtube_dvr_monitor.py`).
