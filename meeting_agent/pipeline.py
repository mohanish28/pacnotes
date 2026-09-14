"""End-to-end processing: audio -> transcript -> Gemini notes -> PDF -> storage -> email."""
import time
from pathlib import Path

from . import drive_storage, emailer, enhancer, meetings, pdf_report, storage, transcriber

RETRY_ATTEMPTS = 3
RETRY_BASE_DELAY_SEC = 2.0  # backs off 2s, 4s between attempts


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


def _retry(fn):
    """Retry a flaky network call a few times with backoff before giving up.

    A DNS blip or a dropped connection shouldn't cost an entire meeting's
    notes on the first bad packet -- but this still raises after exhausting
    attempts, so a real failure still surfaces as a tray notification rather
    than being silently swallowed.
    """
    last_exc = None
    for attempt in range(RETRY_ATTEMPTS):
        try:
            return fn()
        except Exception as e:
            last_exc = e
            if attempt < RETRY_ATTEMPTS - 1:
                time.sleep(RETRY_BASE_DELAY_SEC * (attempt + 1))
    raise last_exc


def run_pipeline(
    wav_path: Path, screenshots: list[Path], cfg: dict, platform: str, meeting_title: str | None = None
) -> PipelineResult:
    label = meeting_title or platform

    try:
        transcript = transcriber.transcribe(wav_path, cfg["whisper_model"])
    except Exception as e:
        raise PipelineError("Transcription", e) from e

    try:
        notes_md = _retry(lambda: enhancer.enhance_notes(transcript, cfg["gemini_api_key"], cfg["gemini_model"]))
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
        pdf_url = _retry(lambda: backend.upload_and_get_link(pdf_path, cfg))
        audio_url = _retry(lambda: backend.upload_and_get_link(wav_path, cfg)) if cfg["keep_audio"] else None
    except Exception as e:
        raise PipelineError(f"{cfg['storage_backend'].upper()} upload", e) from e

    # Register in the dashboard now, not after email: the PDF is already
    # rendered and uploaded at this point, so it must be findable even if
    # email fails below -- otherwise a perfectly good, already-uploaded PDF
    # becomes untraceable (reproduced live: an email failure meant the
    # meeting never appeared in the dashboard despite the PDF existing in
    # R2 the whole time).
    meetings.add_meeting(label, pdf_path, pdf_url, audio_url)

    if cfg["auto_email"]:
        try:
            _retry(lambda: emailer.send_notification_email(cfg, label, pdf_url, audio_url))
        except Exception as e:
            raise PipelineError("Email delivery", e) from e

    if not cfg["keep_audio"]:
        try:
            wav_path.unlink(missing_ok=True)
        except OSError:
            pass  # best-effort cleanup, not worth failing the pipeline over

    return PipelineResult(pdf_path, pdf_url)
