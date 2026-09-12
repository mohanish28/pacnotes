"""Local transcription with faster-whisper. Uses CUDA when available, else CPU."""
from pathlib import Path

from faster_whisper import WhisperModel


def _format_timestamp(seconds: float) -> str:
    minutes, secs = divmod(int(seconds), 60)
    return f"{minutes:02d}:{secs:02d}"


def _run(model: WhisperModel, wav_path: Path) -> list[str]:
    segments, _info = model.transcribe(str(wav_path))
    return [
        f"[{_format_timestamp(s.start)} - {_format_timestamp(s.end)}] {s.text.strip()}"
        for s in segments
    ]


def transcribe(wav_path: Path, model_size: str) -> str:
    try:
        lines = _run(WhisperModel(model_size, device="cuda", compute_type="float16"), wav_path)
    except Exception:
        # ctranslate2 can load the CUDA model optimistically and only fail once
        # real inference needs cuBLAS/cuDNN (observed: model construction
        # succeeds, then .transcribe() raises "libcublas.so.12 is not found").
        # So the CPU fallback has to wrap actual use, not just model loading.
        lines = _run(WhisperModel(model_size, device="cpu", compute_type="int8"), wav_path)

    if not lines:
        raise RuntimeError("Transcription produced no speech segments.")
    return "\n".join(lines)
