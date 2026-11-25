"""
grab_chyrons.py
Captura fotogramas/chyrons para identificar oradores, cargos y votaciones sin descargar el video completo.

Modos:
1. youtube: Usa HLS 480p (-f 231) y descarga 3-4 segmentos consecutivos por punto para asegurar
   un IDR keyframe antes de extraer 1 PNG con ffmpeg. Soporta lista de --sqs o modo --loop continuo.
2. senado: Descarga directamente los thumbnails históricos de Janus Media
   (https://janux-{ch}-jhs.senado.cl/hls/thumb/.../*.jpg) cada N segundos.
"""

import argparse
import datetime
import json
import os
import re
import ssl
import subprocess
import time
import urllib.request

from live_stream_monitor import resolve_senado_host

HEADERS = {"User-Agent": "Mozilla/5.0"}


def _ssl_ctx():
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


def get_yt_video_m3u8(url, fmt="231"):
    return subprocess.check_output(
        ["yt-dlp", "--no-update", "-f", fmt, "-g", "--no-warnings", url],
        text=True, timeout=30,
    ).strip().splitlines()[0]


def fetch_yt_segments(m3u8_url):
    txt = urllib.request.urlopen(
        urllib.request.Request(m3u8_url, headers=HEADERS), timeout=15
    ).read().decode("utf-8", errors="ignore")
    segs = {}
    for line in txt.splitlines():
        line = line.strip()
        if line.startswith("http"):
            m = re.search(r"/sq/(\d+)/", line)
            if m:
                segs[int(m.group(1))] = line
    return segs, ("#EXT-X-ENDLIST" in txt)


def extract_yt_frame(segs, target_sq, out_dir, span=4):
    """Concatena 3-4 segmentos consecutivos para garantizar IDR keyframe y extrae 1 PNG."""
    png_path = os.path.join(out_dir, f"frame_sq{target_sq:05d}.png")
    if os.path.exists(png_path):
        return png_path
    ts_path = os.path.join(out_dir, f"tmp_{target_sq}.ts")
    wrote = 0
    with open(ts_path, "wb") as f:
        for k in range(target_sq, target_sq + span):
            if k in segs:
                data = urllib.request.urlopen(
                    urllib.request.Request(segs[k], headers=HEADERS), timeout=15
                ).read()
                f.write(data)
                wrote += 1
    if wrote:
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", ts_path, "-vframes", "1", png_path], check=False)
    try:
        os.remove(ts_path)
    except OSError:
        pass
    return png_path if os.path.exists(png_path) else None


def run_youtube(args):
    os.makedirs(args.out_dir, exist_ok=True)
    m3u8_v = get_yt_video_m3u8(args.url, args.format)
    last_refresh = time.time()

    if args.sqs:
        segs, _ = fetch_yt_segments(m3u8_v)
        for sq in args.sqs:
            saved = extract_yt_frame(segs, sq, args.out_dir, span=args.span)
            print(f"[FRAME] sq={sq} -> {saved or 'FALLO'}", flush=True)
        return

    # Modo loop continuo
    last_sq = args.start_sq
    while True:
        try:
            if time.time() - last_refresh > 1200:
                m3u8_v = get_yt_video_m3u8(args.url, args.format)
                last_refresh = time.time()
            segs, ended = fetch_yt_segments(m3u8_v)
            if segs:
                max_s = max(segs)
                start_from = max(min(segs), last_sq + args.step_sq) if last_sq else min(segs)
                for sq in range(start_from, max_s - 2, args.step_sq):
                    saved = extract_yt_frame(segs, sq, args.out_dir, span=args.span)
                    if saved:
                        print(f"[FRAME] {os.path.basename(saved)}", flush=True)
                    last_sq = sq
            if ended:
                print("[FIN] Transmisión finalizada.", flush=True)
                break
        except Exception as e:
            print(f"[FRAME ERR] {e}", flush=True)
            time.sleep(10)
            try:
                m3u8_v = get_yt_video_m3u8(args.url, args.format)
                last_refresh = time.time()
            except Exception:
                pass
        time.sleep(args.poll_seconds)


def run_senado(args):
    os.makedirs(args.out_dir, exist_ok=True)
    host = resolve_senado_host(args.channel)
    m = re.search(r"https?://(janux-[a-z0-9]+)\.senado\.cl", host)
    prefix = m.group(1) if m else "janux-tv"

    end_ep = args.end_epoch
    if not end_ep:
        req = urllib.request.Request(f"{host}/playlist/limits.json", headers=HEADERS)
        limits = json.loads(urllib.request.urlopen(req, timeout=8, context=_ssl_ctx()).read().decode("utf-8"))
        end_ep = int(limits["last"])

    start_ep = args.start_epoch or (end_ep - 1800)
    print(f"[SENADO THUMBS] {prefix} de {start_ep} a {end_ep} cada {args.step_seconds}s", flush=True)
    for t in range(start_ep, end_ep + 1, args.step_seconds):
        t_round = t - (t % 10)
        url = (
            f"https://{prefix}-jhs.senado.cl/hls/thumb/"
            f"{t_round - t_round % 86400}/{t_round - t_round % 3600}/{t_round - t_round % 60}/{t_round}.jpg"
        )
        time_str = datetime.datetime.fromtimestamp(t).strftime("%H-%M-%S")
        out_file = os.path.join(args.out_dir, f"thumb_{time_str}_{t_round}.jpg")
        try:
            data = urllib.request.urlopen(urllib.request.Request(url, headers=HEADERS), timeout=5, context=_ssl_ctx()).read()
            with open(out_file, "wb") as f:
                f.write(data)
            print(f"[OK] {os.path.basename(out_file)} ({len(data)} bytes)", flush=True)
        except Exception:
            print(f"[MISS] {time_str}", flush=True)


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Captura de chyrons/fotogramas para YouTube Live y Senado Janus.")
    sub = p.add_subparsers(dest="mode", required=True)

    py = sub.add_parser("youtube", help="Extrae frames PNG desde YouTube Live/DVR (-f 231).")
    py.add_argument("--url", required=True)
    py.add_argument("--out-dir", default="frames")
    py.add_argument("--sqs", type=int, nargs="*", help="Lista puntual de números /sq/ a capturar")
    py.add_argument("--start-sq", type=int, default=0, help="Inicio para modo loop continuo")
    py.add_argument("--step-sq", type=int, default=10, help="Salto de segmentos entre frames en loop (default: 10)")
    py.add_argument("--span", type=int, default=4, help="Segmentos consecutivos para asegurar IDR keyframe (default: 4)")
    py.add_argument("--poll-seconds", type=int, default=20)
    py.add_argument("--format", default="231", help="Formato video HLS yt-dlp (default: 231 = 480p)")

    ps = sub.add_parser("senado", help="Descarga thumbnails históricos JPEG de Janus Media.")
    ps.add_argument("--channel", default="1", help="Alias tv, 1, 2, 3, 5 o URL tv.senado.cl")
    ps.add_argument("--out-dir", default="thumbs_session")
    ps.add_argument("--start-epoch", type=int, default=None)
    ps.add_argument("--end-epoch", type=int, default=None)
    ps.add_argument("--step-seconds", type=int, default=120)

    parsed = p.parse_args()
    if parsed.mode == "youtube":
        run_youtube(parsed)
    else:
        run_senado(parsed)
