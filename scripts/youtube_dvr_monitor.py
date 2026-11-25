"""
youtube_dvr_monitor.py
Monitor verificado de YouTube Live / DVR por secuencia (/sq/N/) para sesiones de
Comisión y Sala del Congreso Nacional de Chile (Cámara y respaldo TV Senado).

Características:
- Auto-detección de duración de segmento desde #EXTINF en el playlist HLS.
- Modo catchup acelerado (bloques grandes) -> transición automática a modo vivo.
- Refresh automático del playlist firmado cada 20 min y reintento ante segmentos faltantes.
- Conversión a WAV 16 kHz mono + validación de duración real con wave.open.
- Estado persistente en monitor_state.json para reanudar sin pérdida ni duplicados.
- Transcripción incremental con faster-whisper (vad_filter=True, condition_on_previous_text=False).
- Alertas en tiempo real por regex en doble formato (.md y .json).
- Detección automática de fin de transmisión (#EXT-X-ENDLIST + yt-dlp is_live).
"""

import argparse
import json
import os
import re
import subprocess
import time
import urllib.request
import wave
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta

try:
    import requests
    SESSION = requests.Session()
    SESSION.headers.update({"User-Agent": "Mozilla/5.0"})
except ImportError:
    SESSION = None

DEFAULT_ALERT_PATTERNS = {
    "VOTACION": [
        r"\ben\s+votaci[oó]n\b",
        r"\bse\s+vota\b",
        r"\babrir\s+(?:la\s+)?votaci[oó]n\b",
        r"\bresultado\s+de\s+la\s+votaci[oó]n\b",
        r"\bse\s+aprueba\b",
        r"\bse\s+rechaza\b",
        r"\bvotaci[oó]n\s+separada\b",
        r"\bpor\s+la\s+afirmativa\b",
        r"\bpor\s+la\s+negativa\b",
    ],
    "TRAMITACION": [
        r"\bindicaci[oó]n\b",
        r"\binadmisib(?:le|ilidad)\b",
        r"\breserva\s+de\s+constitucionalidad\b",
        r"\bse\s+levanta\s+la\s+sesi[oó]n\b",
        r"\bdespachad[ao]\b",
    ],
}


def http_get(url, timeout=15):
    if SESSION is not None:
        r = SESSION.get(url, timeout=timeout)
        r.raise_for_status()
        return r.content
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def get_audio_playlist_url(stream_url, cookies_path=None):
    cmd = ["yt-dlp", "--no-update", "-f", "234/ba[protocol^=m3u8]/ba/b", "-g", "--no-warnings"]
    if cookies_path and os.path.isfile(cookies_path):
        cmd += ["--cookies", cookies_path]
    cmd.append(stream_url)
    res = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    if res.returncode != 0 or not res.stdout.strip():
        raise RuntimeError(f"yt-dlp falló al resolver playlist HLS: {res.stderr.strip()}")
    return res.stdout.strip().splitlines()[0]


def fetch_playlist(m3u8_url):
    text = http_get(m3u8_url, timeout=15).decode("utf-8", errors="ignore")
    segments = {}
    extinfs = []
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("#EXTINF:"):
            m_dur = re.search(r"#EXTINF:([\d.]+)", line)
            if m_dur:
                extinfs.append(float(m_dur.group(1)))
        elif line.startswith("http"):
            m = re.search(r"/sq/(\d+)/", line)
            if m:
                segments[int(m.group(1))] = line
    ended = "#EXT-X-ENDLIST" in text
    seg_seconds = round(sum(extinfs) / len(extinfs), 2) if extinfs else 2.0
    return segments, ended, seg_seconds


def check_still_live(stream_url, cookies_path=None):
    try:
        cmd = ["yt-dlp", "--no-update", "--dump-single-json", "--no-warnings"]
        if cookies_path and os.path.isfile(cookies_path):
            cmd += ["--cookies", cookies_path]
        cmd.append(stream_url)
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if res.returncode == 0 and res.stdout.strip():
            data = json.loads(res.stdout)
            return bool(data.get("is_live", False))
    except Exception:
        pass
    return True


def compile_alerts(alerts_config_path=None, extra_keywords=None):
    raw = {k: list(v) for k, v in DEFAULT_ALERT_PATTERNS.items()}
    if alerts_config_path and os.path.isfile(alerts_config_path):
        with open(alerts_config_path, "r", encoding="utf-8") as f:
            loaded = json.load(f)
        for cat, pats in loaded.items():
            raw[cat] = list(pats)
    if extra_keywords:
        raw["PERSONALIZADAS"] = [rf"(?<!\w){re.escape(w.strip())}(?!\w)" for w in extra_keywords if w.strip()]
    return {cat: [re.compile(p, re.IGNORECASE) for p in pats] for cat, pats in raw.items()}


def record_alerts(text, timestamp_str, compiled_alerts, alerts_md_path, alerts_json_path):
    matched = []
    for category, regexes in compiled_alerts.items():
        if any(r.search(text) for r in regexes):
            matched.append(category)
    if not matched:
        return
    cats_str = ", ".join(matched)
    print(f"🚨 ALERTA [{timestamp_str}] [{cats_str}]: {text[:120]}", flush=True)
    with open(alerts_md_path, "a", encoding="utf-8") as f:
        f.write(f"\n### 🚨 ALERTA [{cats_str}] — `{timestamp_str}`\n> \"{text}\"\n\n")
        f.flush()
    data = []
    if os.path.exists(alerts_json_path):
        try:
            with open(alerts_json_path, "r", encoding="utf-8") as jf:
                data = json.load(jf)
        except Exception:
            data = []
    data.append({
        "timestamp": timestamp_str,
        "categories": matched,
        "text": text,
        "detected_at": datetime.now().isoformat(),
    })
    with open(alerts_json_path, "w", encoding="utf-8") as jf:
        json.dump(data, jf, ensure_ascii=False, indent=2)


def _download_one(args):
    sq, seg_url = args
    for attempt in range(4):
        try:
            data = http_get(seg_url, timeout=15)
            if data:
                return sq, data
        except Exception:
            time.sleep(0.35 * (attempt + 1))
    return sq, None


def download_chunk_verified(start_sq, end_sq, segments, m3u8_url_ref, stream_url, out_wav, cookies_path=None, workers=8):
    ts_path = out_wav.replace(".wav", ".ts")
    tasks = [(sq, segments[sq]) for sq in range(start_sq, end_sq + 1) if sq in segments]
    missing = [sq for sq in range(start_sq, end_sq + 1) if sq not in segments]
    blobs = {}

    with ThreadPoolExecutor(max_workers=workers) as ex:
        for sq, data in ex.map(_download_one, tasks):
            if data:
                blobs[sq] = data
            else:
                missing.append(sq)

    if missing:
        print(f"[AVISO] Refrescando playlist para reintentar {len(missing)} segmentos...", flush=True)
        m3u8_url_ref[0] = get_audio_playlist_url(stream_url, cookies_path)
        fresh_segs, _, _ = fetch_playlist(m3u8_url_ref[0])
        segments.update(fresh_segs)
        retry_tasks = [(sq, segments[sq]) for sq in missing if sq in segments]
        with ThreadPoolExecutor(max_workers=workers) as ex:
            for sq, data in ex.map(_download_one, retry_tasks):
                if data:
                    blobs[sq] = data

    with open(ts_path, "wb") as f:
        for sq in range(start_sq, end_sq + 1):
            if sq in blobs:
                f.write(blobs[sq])

    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-i", ts_path, "-vn", "-ar", "16000", "-ac", "1", out_wav],
        check=True,
    )
    try:
        os.remove(ts_path)
    except OSError:
        pass

    with wave.open(out_wav, "rb") as w:
        dur = w.getnframes() / float(w.getframerate())
    return len(blobs), dur


def run_monitor(args):
    from faster_whisper import WhisperModel

    os.makedirs(args.out_dir, exist_ok=True)
    md_path = os.path.abspath(args.markdown or os.path.join(args.out_dir, f"seguimiento_en_vivo_{datetime.now().strftime('%Y-%m-%d')}.md"))
    state_path = os.path.join(args.out_dir, "monitor_state.json")
    alerts_md = os.path.join(args.out_dir, "alertas_detectadas.md")
    alerts_json = os.path.join(args.out_dir, "alertas_detectadas.json")

    compiled_alerts = compile_alerts(args.alerts_config, args.keywords.split(",") if args.keywords else None)

    if not os.path.exists(md_path):
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(f"# Seguimiento en Vivo — {args.title}\n\n")
            f.write(f"- **Fecha:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"- **Fuente:** {args.url}\n\n---\n\n")

    if not os.path.exists(alerts_md):
        with open(alerts_md, "w", encoding="utf-8") as f:
            f.write(f"# Registro de Alertas en Tiempo Real — {args.title}\n\n")
            f.write(f"Iniciado el {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n---\n\n")

    if os.path.exists(state_path):
        with open(state_path, "r", encoding="utf-8") as f:
            state = json.load(f)
    else:
        state = {"next_sq": args.start_sq, "chunk_idx": 0}

    next_sq = state["next_sq"]
    chunk_idx = state["chunk_idx"]

    print(f"[INIT] Cargando faster-whisper '{args.model}' ({args.device}, {args.compute_type}, beam={args.beam_size})...", flush=True)
    model = WhisperModel(args.model, device=args.device, compute_type=args.compute_type)

    m3u8_url_ref = [get_audio_playlist_url(args.url, args.cookies)]
    last_refresh = time.time()

    while True:
        try:
            if time.time() - last_refresh > 1200:
                m3u8_url_ref[0] = get_audio_playlist_url(args.url, args.cookies)
                last_refresh = time.time()
            segments, ended, seg_seconds = fetch_playlist(m3u8_url_ref[0])
        except Exception as e:
            print(f"[WARN] Refrescando playlist tras error: {e}", flush=True)
            time.sleep(5)
            try:
                m3u8_url_ref[0] = get_audio_playlist_url(args.url, args.cookies)
                last_refresh = time.time()
                segments, ended, seg_seconds = fetch_playlist(m3u8_url_ref[0])
            except Exception as e2:
                print(f"[WARN] Falló refresh: {e2}", flush=True)
                time.sleep(15)
                continue

        if not segments:
            time.sleep(10)
            continue

        min_sq, max_sq = min(segments.keys()), max(segments.keys())
        if next_sq < min_sq:
            print(f"[AVISO] Ajustando next_sq de {next_sq} a {min_sq} (inicio de ventana DVR).", flush=True)
            next_sq = min_sq

        catchup_segs = max(10, int(round(args.chunk_seconds / seg_seconds)))
        live_segs = max(10, int(round(args.live_chunk_seconds / seg_seconds)))
        available = max_sq - next_sq + 1
        target_size = catchup_segs if available >= catchup_segs else live_segs

        stream_finished = ended
        if not stream_finished and available < target_size:
            time.sleep(15)
            if available > 0 and not check_still_live(args.url, args.cookies):
                stream_finished = True
            else:
                continue

        if available <= 0:
            if stream_finished:
                print("[FIN] Transmisión finalizada y todos los bloques procesados.", flush=True)
                break
            time.sleep(15)
            continue

        end_sq = min(next_sq + target_size - 1, max_sq) if not stream_finished else max_sq
        expected = end_sq - next_sq + 1
        chunk_idx += 1

        wav_path = os.path.join(args.out_dir, f"chunk_{chunk_idx:03d}_sq{next_sq}_{end_sq}.wav")
        t0 = time.time()
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Bloque {chunk_idx}: sq {next_sq}..{end_sq} ({expected} segs de ~{seg_seconds}s)...", flush=True)
        got_n, wav_dur = download_chunk_verified(
            next_sq, end_sq, segments, m3u8_url_ref, args.url, wav_path, args.cookies
        )
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Descargados {got_n}/{expected} segs ({wav_dur:.1f}s). Transcribiendo...", flush=True)

        segs_iter, _ = model.transcribe(
            wav_path,
            language="es",
            beam_size=args.beam_size,
            vad_filter=True,
            vad_parameters=dict(min_silence_duration_ms=500),
            condition_on_previous_text=False,
        )

        block_start = str(timedelta(seconds=int(next_sq * seg_seconds)))
        block_end = str(timedelta(seconds=int((end_sq + 1) * seg_seconds)))
        lines = [f"### Bloque {chunk_idx} (`{block_start}` – `{block_end}` | sq `{next_sq}`–`{end_sq}` | audio `{wav_dur:.1f}s`)\n\n"]
        seg_count = 0
        for s in segs_iter:
            txt = s.text.strip()
            if not txt:
                continue
            abs_s = str(timedelta(seconds=int(next_sq * seg_seconds + s.start)))
            abs_e = str(timedelta(seconds=int(next_sq * seg_seconds + s.end)))
            lines.append(f"**[{abs_s} - {abs_e}]** {txt}\n\n")
            record_alerts(txt, abs_s, compiled_alerts, alerts_md, alerts_json)
            seg_count += 1

        if seg_count == 0:
            lines.append("*(Silencio / pausa sin audio hablado detectado)*\n\n")

        with open(md_path, "a", encoding="utf-8") as f:
            f.writelines(lines)
            f.flush()

        if not args.keep_wav:
            try:
                os.remove(wav_path)
            except OSError:
                pass

        print(f"[{datetime.now().strftime('%H:%M:%S')}] Bloque {chunk_idx} guardado ({seg_count} segmentos en {time.time() - t0:.1f}s).", flush=True)
        next_sq = end_sq + 1
        with open(state_path, "w", encoding="utf-8") as f:
            json.dump({"next_sq": next_sq, "chunk_idx": chunk_idx, "updated_at": datetime.now().isoformat()}, f, indent=2)

        if stream_finished and next_sq > max_sq:
            break

    with open(md_path, "a", encoding="utf-8") as f:
        f.write("\n---\n\n**Estado:** Transmisión finalizada / Captura completada.\n")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Monitor YouTube Live/DVR por /sq/ con transcripción incremental y alertas.")
    p.add_argument("--url", required=True, help="URL de YouTube Live o DVR")
    p.add_argument("--out-dir", default=".", help="Carpeta de trabajo para estado, alertas y chunks")
    p.add_argument("--markdown", default=None, help="Archivo Markdown de salida")
    p.add_argument("--title", default="Sesión Legislativa", help="Título para encabezados")
    p.add_argument("--start-sq", type=int, default=0, help="Secuencia /sq/ inicial (default: 0 = inicio DVR)")
    p.add_argument("--chunk-seconds", type=int, default=300, help="Duración de bloque en catchup (default: 300s)")
    p.add_argument("--live-chunk-seconds", type=int, default=90, help="Duración de bloque cerca del live edge (default: 90s)")
    p.add_argument("--model", default="small", help="Modelo faster-whisper: base (rápido) o small (alta precisión)")
    p.add_argument("--beam-size", type=int, default=5, help="beam_size Whisper (5 calidad, 1 máxima velocidad)")
    p.add_argument("--device", default="cpu", help="cpu o auto")
    p.add_argument("--compute-type", default="int8", help="int8 (CPU rápido) o default")
    p.add_argument("--alerts-config", default=None, help="JSON opcional {CATEGORIA: [regex1, regex2]}")
    p.add_argument("--keywords", default=None, help="Palabras clave extra separadas por coma")
    p.add_argument("--cookies", default=None, help="Archivo de cookies Netscape para YouTube (opcional)")
    p.add_argument("--keep-wav", action="store_true", help="Conservar archivos .wav temporales")
    run_monitor(p.parse_args())
