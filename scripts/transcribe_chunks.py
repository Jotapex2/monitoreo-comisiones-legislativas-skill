"""
transcribe_chunks.py
Transcriptor Incremental para Monitoreo de Sesiones Parlamentarias (Comisiones y Salas).
Utiliza faster-whisper con Silero VAD y condition_on_previous_text=False para evitar
bucles de texto o alucinaciones durante pausas, placas de espera o votaciones silenciosas.
"""

import argparse
import os
from datetime import timedelta


def transcribe_and_append(
    audio_path,
    markdown_path,
    start_time_offset=0,
    model_size="small",
    speaker_label="Intervención",
    device="cpu",
    compute_type="int8",
    beam_size=5,
):
    """Transcribe un archivo de audio y agrega los segmentos al archivo Markdown en tiempo real."""
    from faster_whisper import WhisperModel

    print(f"[Whisper] Cargando modelo '{model_size}' (device={device}, compute_type={compute_type}, beam={beam_size})...")
    model = WhisperModel(model_size, device=device, compute_type=compute_type)

    # vad_filter=True + condition_on_previous_text=False evitan bucles alucinatorios en sesiones largas
    segments, info = model.transcribe(
        audio_path,
        language="es",
        beam_size=beam_size,
        vad_filter=True,
        vad_parameters=dict(min_silence_duration_ms=500),
        condition_on_previous_text=False,
    )

    print(f"[Whisper] Idioma detectado: {info.language} (probabilidad: {info.language_probability:.2f})")

    os.makedirs(os.path.dirname(os.path.abspath(markdown_path)), exist_ok=True)
    if not os.path.exists(markdown_path):
        with open(markdown_path, "w", encoding="utf-8") as f:
            f.write("# Seguimiento en Vivo de Sesión Legislativa\n\n")
            f.write("Registro incremental de intervenciones transcritas en tiempo real.\n\n---\n\n")

    count = 0
    with open(markdown_path, "a", encoding="utf-8") as f:
        for seg in segments:
            text = seg.text.strip()
            if not text:
                continue

            abs_start = start_time_offset + seg.start
            abs_end = start_time_offset + seg.end
            str_start = str(timedelta(seconds=int(abs_start)))
            str_end = str(timedelta(seconds=int(abs_end)))

            line = f"**[{str_start} - {str_end}] {speaker_label}:** {text}\n\n"
            f.write(line)
            f.flush()
            count += 1
            print(f"[{str_start}] {text[:80]}...")

    print(f"[OK] {count} segmentos guardados en: {markdown_path}")
    return count


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Transcripción incremental de audios parlamentarios a Markdown.")
    parser.add_argument("--audio", required=True, help="Ruta al archivo de audio (.wav, .m4a, .mp3, .mp4)")
    parser.add_argument("--markdown", required=True, help="Ruta al archivo Markdown de seguimiento")
    parser.add_argument("--offset", type=float, default=0, help="Offset de tiempo acumulado en segundos")
    parser.add_argument("--model", default="small", help="Modelo faster-whisper (base rápido, small alta calidad)")
    parser.add_argument("--speaker", default="Intervención", help="Etiqueta del orador si es conocida")
    parser.add_argument("--device", default="cpu", help="cpu o auto")
    parser.add_argument("--compute-type", default="int8", help="int8 (CPU rápido) o default")
    parser.add_argument("--beam-size", type=int, default=5, help="beam_size (5 precisión, 1 máxima velocidad)")
    args = parser.parse_args()

    transcribe_and_append(
        args.audio,
        args.markdown,
        args.offset,
        args.model,
        args.speaker,
        args.device,
        args.compute_type,
        args.beam_size,
    )
