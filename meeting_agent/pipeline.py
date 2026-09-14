"""End-to-end processing: audio -> transcript -> Gemini notes -> PDF -> storage -> email."""
import time
from pathlib import Path

from . import drive_storage, emailer, enhancer, meetings, pdf_report, storage, transcriber


class PipelineError(Exception):
    """Raised with a message naming which step failed, for tray notifications."""

    def __init__(self, step: str, original: Exception):
        super().__init__(f"{step} failed: {original}")
        self.step = step
        self.original = original


class PipelineResult:
    def __init__(self, pdf_path: Path, pdf_url: str):
        self.pdf_path = pdf_path
        self.pdf_url = pdf_url


def _storage_backend(cfg: dict):
    return drive_storage if cfg["storage_backend"] == "drive" else storage


def run_pipeline(
    wav_path: Path, screenshots: list[Path], cfg: dict, platform: str, meeting_title: str | None = None
) -> PipelineResult:
    label = meeting_title or platform

    try:
        transcript = transcriber.transcribe(wav_path, cfg["whisper_model"])
    except Exception as e:
        raise PipelineError("Transcription", e) from e

    try:
        notes_md = enhancer.enhance_notes(transcript, cfg["gemini_api_key"], cfg["gemini_model"])
    except Exception as e:
        raise PipelineError("Note enhancement (Gemini)", e) from e

    try:
        output_dir = Path(cfg["output_dir"])
        stamp = time.strftime("%Y%m%d-%H%M%S")
        pdf_path = output_dir / f"meeting-notes-{stamp}.pdf"
        pdf_report.render_pdf(notes_md, screenshots, pdf_path)
    except Exception as e:
        raise PipelineError("PDF rendering", e) from e

    backend = _storage_backend(cfg)
    try:
        pdf_url = backend.upload_and_get_link(pdf_path, cfg)
        audio_url = backend.upload_and_get_link(wav_path, cfg) if cfg["keep_audio"] else None
    except Exception as e:
        raise PipelineError(f"{cfg['storage_backend'].upper()} upload", e) from e

    if cfg["auto_email"]:
        try:
            emailer.send_notification_email(cfg, label, pdf_url, audio_url)
        except Exception as e:
            raise PipelineError("Email delivery", e) from e

    if not cfg["keep_audio"]:
        try:
            wav_path.unlink(missing_ok=True)
        except OSError:
            pass  # best-effort cleanup, not worth failing the pipeline over

    meetings.add_meeting(label, pdf_path, pdf_url, audio_url)
    return PipelineResult(pdf_path, pdf_url)
