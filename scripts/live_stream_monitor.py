"""
live_stream_monitor.py
Motor de Ingesta Dual y Utilidades para Monitoreo Legislativo de Chile.
Soporta:
1. Cámara de Diputadas y Diputados: YouTube Live/DVR vía yt-dlp + ffmpeg.
2. Senado de Chile (tv.senado.cl / Janus Media):
   - Auto-descubrimiento de servidor janux-N desde páginas de tv.senado.cl.
   - Verificación de señal activa (playlist/limits.json).
   - Captura HLS en vivo o histórica (stream.m3u8?s=sd[&t=epoch]).
   - Descarga de cápsulas MP4 exactas (api/get_front_capsule.rb + get_front_status.rb).
   - Detección de volumen de audio (ffmpeg volumedetect) para ubicar inicio real de sesión.
"""

import argparse
import json
import os
import re
import ssl
import subprocess
import time
import urllib.request

SENADO_SERVERS = {
    "tv": "https://janux-tv.senado.cl",
    "1": "https://janux-1.senado.cl",
    "2": "https://janux-2.senado.cl",
    "3": "https://janux-3.senado.cl",
    "5": "https://janux-5.senado.cl",
    "comision1": "https://janux-1.senado.cl",
    "comision2": "https://janux-2.senado.cl",
    "comision3": "https://janux-3.senado.cl",
    "comision5": "https://janux-5.senado.cl",
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    "Referer": "https://tv.senado.cl/",
}


def _ssl_context():
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


def resolve_senado_host(url_or_channel):
    """Devuelve el host base https://janux-<ch>.senado.cl desde alias o URL."""
    val = str(url_or_channel).strip()
    low = val.lower()
    if low in SENADO_SERVERS:
        return SENADO_SERVERS[low]

    m = re.search(r"https?://(janux-[a-z0-9]+)\.senado\.cl", low)
    if m:
        return f"https://{m.group(1)}.senado.cl"

    m_com = re.search(r"comision[-_]?(\d+)", low)
    if m_com:
        return f"https://janux-{m_com.group(1)}.senado.cl"

    if "tv.senado.cl" in low and val.startswith("http"):
        # Auto-descubrir servidor janux desde el HTML de la página
        req = urllib.request.Request(val, headers=HEADERS)
        html = urllib.request.urlopen(req, timeout=10, context=_ssl_context()).read().decode("utf-8", errors="ignore")
        found = re.findall(r"https?://janux-[a-z0-9]+\.senado\.cl", html, re.IGNORECASE)
        if found:
            return found[0].lower()

    return SENADO_SERVERS["tv"]


def resolve_senado_url(url_or_channel, start_epoch=None):
    """Resuelve la URL HLS directa (en vivo o histórica con &t=epoch)."""
    val = str(url_or_channel).strip()
    if "janux" in val.lower() and ".m3u8" in val.lower():
        return val
    host = resolve_senado_host(val)
    suffix = f"&t={int(start_epoch)}" if start_epoch else ""
    return f"{host}/playlist/stream.m3u8?s=sd{suffix}"


def check_senado_limits(url_or_channel, max_age_seconds=90):
    """Consulta limits.json y determina si el canal del Senado está al aire."""
    host = resolve_senado_host(url_or_channel)
    req = urllib.request.Request(f"{host}/playlist/limits.json", headers=HEADERS)
    with urllib.request.urlopen(req, timeout=8, context=_ssl_context()) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    last_ep = float(data["last"])
    age = time.time() - last_ep
    return {
        "host": host,
        "first": int(data.get("first", 0)),
        "last": int(last_ep),
        "age_seconds": round(age, 1),
        "is_live": age <= max_age_seconds,
    }


def fetch_janus_capsule(url_or_channel, start_epoch, end_epoch, output_path, stream="sd", timeout_sec=60):
    """Solicita y descarga una cápsula MP4 exacta vía la API nativa de Janus Media."""
    host = resolve_senado_host(url_or_channel)
    payload = {
        "start": int(start_epoch),
        "end": int(end_epoch),
        "stream": stream,
        "type": "mp4",
        "from": "front",
    }
    req = urllib.request.Request(
        f"{host}/api/get_front_capsule.rb",
        data=json.dumps(payload).encode("utf-8"),
        headers={**HEADERS, "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=15, context=_ssl_context()) as resp:
        res = json.loads(resp.read().decode("utf-8"))
    pid = res.get("processId")
    if not pid:
        raise RuntimeError(f"Janus no devolvió processId: {res}")

    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    for _ in range(timeout_sec):
        time.sleep(1)
        st_req = urllib.request.Request(f"{host}/api/get_front_status.rb/{pid}", headers=HEADERS)
        with urllib.request.urlopen(st_req, timeout=10, context=_ssl_context()) as st_resp:
            st = json.loads(st_resp.read().decode("utf-8"))
        stage = st.get("stage")
        if stage == "FINISHED":
            fpath = st["fileInfo"]["file_path"]
            dl_req = urllib.request.Request(f"{host}{fpath}", headers=HEADERS)
            tmp_path = f"{output_path}.tmp"
            with urllib.request.urlopen(dl_req, timeout=60, context=_ssl_context()) as dl_resp, open(tmp_path, "wb") as out_f:
                while chunk := dl_resp.read(1024 * 1024):
                    out_f.write(chunk)
            if os.path.exists(output_path):
                os.remove(output_path)
            os.rename(tmp_path, output_path)
            print(f"[Cápsula OK] {output_path} ({os.path.getsize(output_path)} bytes)")
            return output_path
        if stage == "FAIL":
            raise RuntimeError(f"Falló generación de cápsula Janus: {st}")

    raise TimeoutError(f"Tiempo agotado esperando cápsula Janus (pid={pid})")


def scan_volume_db(media_path):
    """Mide max_volume (dB) con ffmpeg volumedetect para distinguir silencio de audio hablado."""
    null_sink = "NUL" if os.name == "nt" else "/dev/null"
    proc = subprocess.run(
        ["ffmpeg", "-i", media_path, "-af", "volumedetect", "-vn", "-f", "null", null_sink],
        capture_output=True, text=True,
    )
    for line in proc.stderr.splitlines():
        if "max_volume:" in line:
            m = re.search(r"max_volume:\s*([-\d.]+)\s*dB", line)
            if m:
                return float(m.group(1))
    return None


def capture_audio_chunk(stream_url, output_path, duration_seconds=300, start_epoch=None):
    """Captura un fragmento de audio AAC de duración específica desde YouTube o Senado HLS."""
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

    if "youtube.com" in stream_url or "youtu.be" in stream_url:
        print(f"[Cámara/YouTube] Capturando {duration_seconds}s de audio desde: {stream_url}")
        cmd_get_url = ["yt-dlp", "--no-update", "-f", "234/ba[protocol^=m3u8]/ba/b", "-g", "--no-warnings", stream_url]
        res = subprocess.run(cmd_get_url, capture_output=True, text=True)
        if res.returncode != 0 or not res.stdout.strip():
            raise RuntimeError(f"Error al resolver URL de YouTube: {res.stderr}")
        direct_url = res.stdout.strip().splitlines()[0]
        cmd_ffmpeg = [
            "ffmpeg", "-y", "-i", direct_url,
            "-t", str(duration_seconds),
            "-vn", "-c:a", "aac", output_path,
        ]
    else:
        resolved_url = resolve_senado_url(stream_url, start_epoch=start_epoch)
        print(f"[Senado/Janus Media] Capturando {duration_seconds}s de audio desde: {resolved_url}")
        cmd_ffmpeg = [
            "ffmpeg", "-y", "-i", resolved_url,
            "-t", str(duration_seconds),
            "-vn", "-c:a", "aac", output_path,
        ]

    proc = subprocess.run(cmd_ffmpeg, capture_output=True, text=True)
    if proc.returncode != 0 and not os.path.exists(output_path):
        raise RuntimeError(f"Error ffmpeg al capturar audio: {proc.stderr}")

    print(f"[Captura OK] Guardado fragmento en: {output_path}")
    return output_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingesta dual y utilidades Janus/YouTube para el Congreso de Chile.")
    sub = parser.add_subparsers(dest="cmd")

    p_cap = sub.add_parser("capture", help="Captura un bloque de audio AAC con ffmpeg.")
    p_cap.add_argument("--url", required=True, help="URL YouTube o canal/URL Senado (tv, 1, 2, 3, 5)")
    p_cap.add_argument("--output", required=True, help="Ruta de salida (.m4a)")
    p_cap.add_argument("--duration", type=int, default=300, help="Duración en segundos (default: 300)")
    p_cap.add_argument("--start-epoch", type=int, default=None, help="Epoch histórico opcional (solo Senado)")

    p_lim = sub.add_parser("limits", help="Consulta limits.json de un canal del Senado.")
    p_lim.add_argument("--channel", required=True, help="Alias (tv, 1, 2, 3, 5) o URL de tv.senado.cl")

    p_c = sub.add_parser("capsule", help="Descarga una cápsula MP4 exacta vía API de Janus.")
    p_c.add_argument("--channel", required=True, help="Alias (tv, 1, 2, 3, 5) o URL de tv.senado.cl")
    p_c.add_argument("--start-epoch", type=int, required=True)
    p_c.add_argument("--end-epoch", type=int, required=True)
    p_c.add_argument("--output", required=True, help="Ruta del archivo .mp4 de salida")

    p_vol = sub.add_parser("volume", help="Mide max_volume (dB) de un audio/video.")
    p_vol.add_argument("--file", required=True)

    # Retrocompatibilidad con llamada directa (--url --output --duration)
    parser.add_argument("--url", help="Modo directo retrocompatible: URL de stream")
    parser.add_argument("--output", help="Modo directo retrocompatible: archivo .m4a")
    parser.add_argument("--duration", type=int, default=300)

    args = parser.parse_args()
    if args.cmd == "limits":
        print(json.dumps(check_senado_limits(args.channel), indent=2, ensure_ascii=False))
    elif args.cmd == "capsule":
        fetch_janus_capsule(args.channel, args.start_epoch, args.end_epoch, args.output)
    elif args.cmd == "volume":
        print(f"max_volume_db={scan_volume_db(args.file)}")
    elif args.cmd == "capture":
        capture_audio_chunk(args.url, args.output, args.duration, args.start_epoch)
    elif args.url and args.output:
        capture_audio_chunk(args.url, args.output, args.duration)
    else:
        parser.print_help()
