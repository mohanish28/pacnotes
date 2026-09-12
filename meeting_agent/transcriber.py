"""Local transcription with faster-whisper. Uses CUDA when available, else CPU."""
from pathlib import Path

from faster_whisper import WhisperModel


def _load_model(model_size: str) -> WhisperModel:
    try:
        return WhisperModel(model_size, device="cuda", compute_type="float16")
    except Exception:
        return WhisperModel(model_size, device="cpu", compute_type="int8")


def _format_timestamp(seconds: float) -> str:
    minutes, secs = divmod(int(seconds), 60)
    return f"{minutes:02d}:{secs:02d}"


def transcribe(wav_path: Path, model_size: str) -> str:
    model = _load_model(model_size)
    segments, _info = model.transcribe(str(wav_path))

    lines = []
    for segment in segments:
        start = _format_timestamp(segment.start)
        end = _format_timestamp(segment.end)
        lines.append(f"[{start} - {end}] {segment.text.strip()}")

    if not lines:
        raise RuntimeError("Transcription produced no speech segments.")
    return "\n".join(lines)
