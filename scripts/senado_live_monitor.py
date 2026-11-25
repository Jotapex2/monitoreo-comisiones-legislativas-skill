"""
senado_live_monitor.py
Monitor en vivo y catchup por segmentos .ts para el Senado de Chile (tv.senado.cl / Janus Media).

Soporta:
- Canales: tv, 1, 2, 3, 5 (o URL directa de janux-*.senado.cl).
- Modo vivo continuo con descarga paralela de .ts, estado persistente y alertas (.md + .json).
- Modo catchup histórico por rango de epoch (--start-epoch .. --end-epoch).
- Transcripción con faster-whisper (vad_filter=True, condition_on_previous_text=False).
"""

import argparse
import json
import os
import re
import ssl
import subprocess
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta

from live_stream_monitor import resolve_senado_host

DEFAULT_ALERT_PATTERNS = {
    "VOTACION": [
        r"\ben\s+votaci[oó]n\b",
        r"\bse\s+vota\b",
        r"\babrir\s+(?:la\s+)?votaci[oó]n\b",
        r"\bresultado\s+de\s+la\s+votaci[oó]n\b",
        r"\bse\s+aprueba\b",
        r"\bse\s+rechaza\b",
        r"\bpor\s+la\s+afirmativa\b",
        r"\bpor\s+la\s+negativa\b",
    ],
    "TRAMITACION": [
        r"\bindicaci[oó]n\b",
        r"\binadmisib(?:le|ilidad)\b",
        r"\breserva\s+de\s+constitucionalidad\b",
        r"\bse\s+levanta\s+la\s+sesi[oó]n\b",
        r"\bpartida\s+\d+\b",
        r"\bglosa\s+\d+\b",
    ],
}

SSL_CTX = ssl.create_default_context()
SSL_CTX.check_hostname = False
SSL_CTX.verify_mode = ssl.CERT_NONE


def compile_alerts(alerts_config_path=None, extra_keywords=None):
    raw = {k: list(v) for k, v in DEFAULT_ALERT_PATTERNS.items()}
    if alerts_config_path and os.path.isfile(alerts_config_path):
        with open(alerts_config_path, "r", encoding="utf-8") as f:
            for cat, pats in json.load(f).items():
                raw[cat] = list(pats)
    if extra_keywords:
        raw["PERSONALIZADAS"] = [rf"(?<!\w){re.escape(w.strip())}(?!\w)" for w in extra_keywords if w.strip()]
    return {cat: [re.compile(p, re.IGNORECASE) for p in pats] for cat, pats in raw.items()}


def get_janux_segments(stream_url):
    try:
        req = urllib.request.Request(stream_url, headers={"User-Agent": "Mozilla/5.0", "Referer": "https://tv.senado.cl/"})
        lines = urllib.request.urlopen(req, timeout=8, context=SSL_CTX).read().decode("utf-8", errors="ignore").splitlines()
        seg_dict = {}
        for l in lines:
            l = l.strip()
            if l.startswith("http"):
                m = re.search(r"sd_(\d+)\.ts", l)
                if m:
                    seg_dict[int(m.group(1))] = l
        return seg_dict
    except Exception as e:
        print(f"[WARN] Error leyendo m3u8 Janus: {e}", flush=True)
        return {}


def download_single_ts(url, max_retries=3):
    for attempt in range(max_retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0", "Referer": "https://tv.senado.cl/"})
            return urllib.request.urlopen(req, timeout=6, context=SSL_CTX).read()
        except Exception:
            time.sleep(0.1 * (attempt + 1))
    return None


def record_alerts(text, timestamp_str, compiled_alerts, alerts_md_path, alerts_json_path):
    matched = [cat for cat, regs in compiled_alerts.items() if any(r.search(text) for r in regs)]
    if not matched:
        return
    cats_str = ", ".join(matched)
    print(f"🚨 ALERTA SENADO [{timestamp_str}] [{cats_str}]: {text[:120]}", flush=True)
    with open(alerts_md_path, "a", encoding="utf-8") as f:
        f.write(f"\n### 🚨 ALERTA SENADO: [{cats_str}] a las [{timestamp_str}]\n> **Transcripción:** \"{text}\"\n\n")
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


def process_ts_batch(target_ts_list, seg_dict, model, batch_id, out_dir, md_path, compiled_alerts, alerts_md, alerts_json, beam_size):
    if not target_ts_list:
        return
    urls = [seg_dict[ts] for ts in target_ts_list if ts in seg_dict]
    if not urls:
        return

    with ThreadPoolExecutor(max_workers=8) as ex:
        chunks = list(ex.map(download_single_ts, urls))
    valid_chunks = [c for c in chunks if c and len(c) > 500]
    if not valid_chunks:
        return

    ts_path = os.path.join(out_dir, f"senado_{batch_id}.ts")
    m4a_path = os.path.join(out_dir, f"senado_{batch_id}.m4a")
    with open(ts_path, "wb") as f:
        for c in valid_chunks:
            f.write(c)

    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", ts_path, "-vn", "-c:a", "copy", m4a_path], capture_output=True)
    if not os.path.exists(m4a_path) or os.path.getsize(m4a_path) == 0:
        if os.path.exists(ts_path):
            os.remove(ts_path)
        return

    segments, _ = model.transcribe(
        m4a_path,
        language="es",
        vad_filter=True,
        vad_parameters=dict(min_silence_duration_ms=500),
        beam_size=beam_size,
        condition_on_previous_text=False,
    )

    base_epoch = target_ts_list[0]
    with open(md_path, "a", encoding="utf-8") as f:
        for s in segments:
            text = s.text.strip()
            if not text:
                continue
            clock_time = datetime.fromtimestamp(base_epoch + s.start).strftime("%H:%M:%S")
            f.write(f"**[{clock_time}] Intervención:** {text}\n\n")
            f.flush()
            record_alerts(text, clock_time, compiled_alerts, alerts_md, alerts_json)
            print(f"  [{clock_time}] {text[:90]}", flush=True)

    for p in (ts_path, m4a_path):
        try:
            if os.path.exists(p):
                os.remove(p)
        except OSError:
            pass


def run_monitor(args):
    from faster_whisper import WhisperModel

    os.makedirs(args.out_dir, exist_ok=True)
    host = resolve_senado_host(args.channel)
    stream_url = f"{host}/playlist/stream.m3u8?s=sd"
    md_path = os.path.abspath(args.markdown or os.path.join(args.out_dir, f"seguimiento_en_vivo_senado_{datetime.now().strftime('%Y-%m-%d')}.md"))
    state_path = os.path.join(args.out_dir, "monitor_state_senado.json")
    alerts_md = os.path.join(args.out_dir, "alertas_detectadas_senado.md")
    alerts_json = os.path.join(args.out_dir, "alertas_detectadas_senado.json")
    compiled_alerts = compile_alerts(args.alerts_config, args.keywords.split(",") if args.keywords else None)

    if not os.path.exists(md_path):
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(f"# Seguimiento en Vivo — {args.title} (Senado)\n\n")
            f.write(f"- **Fecha:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"- **Canal Janus:** {host}\n\n---\n\n")

    if not os.path.exists(alerts_md):
        with open(alerts_md, "w", encoding="utf-8") as f:
            f.write(f"# Registro de Alertas en Tiempo Real — {args.title}\n\n---\n\n")

    print(f"[INIT] Cargando Whisper '{args.model}' ({args.device}, {args.compute_type}, beam={args.beam_size})...", flush=True)
    model = WhisperModel(args.model, device=args.device, compute_type=args.compute_type)

    # Modo catchup por rango de epochs
    if args.start_epoch and args.end_epoch:
        cur = args.start_epoch
        batch_id = 0
        while cur < args.end_epoch:
            segs = get_janux_segments(f"{stream_url}&t={cur}")
            target = sorted(ts for ts in segs if cur <= ts <= args.end_epoch)[:args.batch_segments]
            if not target:
                cur += args.batch_segments * 2
                continue
            batch_id += 1
            process_ts_batch(target, segs, model, f"catchup_{batch_id}", args.out_dir, md_path, compiled_alerts, alerts_md, alerts_json, args.beam_size)
            cur = target[-1] + 1
        print("[FIN] Catchup histórico del Senado completado.", flush=True)
        return

    # Modo vivo continuo
    last_ts = 0
    if os.path.exists(state_path):
        try:
            with open(state_path, "r", encoding="utf-8") as f:
                last_ts = json.load(f).get("last_ts", 0)
        except Exception:
            pass

    pending = {}
    batch_counter = 0
    while True:
        current = get_janux_segments(stream_url)
        if not current:
            time.sleep(3)
            continue
        sorted_ts = sorted(current.keys())
        if last_ts == 0:
            last_ts = sorted_ts[0] - 1
        for ts_val in sorted_ts:
            if ts_val > last_ts and ts_val not in pending:
                pending[ts_val] = current[ts_val]

        if len(pending) >= args.min_segments:
            to_process = sorted(pending.keys())[:args.batch_segments]
            batch_counter += 1
            process_ts_batch(to_process, pending, model, batch_counter, args.out_dir, md_path, compiled_alerts, alerts_md, alerts_json, args.beam_size)
            last_ts = to_process[-1]
            with open(state_path, "w", encoding="utf-8") as f:
                json.dump({"last_ts": last_ts, "updated_at": datetime.now().isoformat()}, f, indent=2)
            for ts_done in to_process:
                pending.pop(ts_done, None)
        time.sleep(4)


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Monitor en vivo y catchup HLS para el Senado de Chile (Janus Media).")
    p.add_argument("--channel", default="tv", help="Canal Senado: tv, 1, 2, 3, 5 o URL tv.senado.cl / janux")
    p.add_argument("--out-dir", default=".", help="Carpeta de salida")
    p.add_argument("--markdown", default=None, help="Archivo Markdown de seguimiento")
    p.add_argument("--title", default="Senado de Chile", help="Título para encabezados")
    p.add_argument("--start-epoch", type=int, default=None, help="Epoch inicial para modo catchup")
    p.add_argument("--end-epoch", type=int, default=None, help="Epoch final para modo catchup")
    p.add_argument("--min-segments", type=int, default=6, help="Mínimo de segmentos .ts (~2s c/u) para procesar")
    p.add_argument("--batch-segments", type=int, default=12, help="Máximo de segmentos .ts por bloque")
    p.add_argument("--model", default="base", help="Modelo faster-whisper (base o small)")
    p.add_argument("--beam-size", type=int, default=1, help="beam_size Whisper (1 rápido, 5 máxima calidad)")
    p.add_argument("--device", default="cpu")
    p.add_argument("--compute-type", default="int8")
    p.add_argument("--alerts-config", default=None, help="JSON opcional {CATEGORIA: [regex1, regex2]}")
    p.add_argument("--keywords", default=None, help="Palabras clave extra separadas por coma")
    run_monitor(p.parse_args())
