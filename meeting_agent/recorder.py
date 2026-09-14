"""Captures speaker loopback + microphone, mixes to 16 kHz mono, writes a WAV."""
import threading
import wave
from pathlib import Path

import numpy as np
import soundcard as sc
from scipy.signal import resample_poly

SAMPLE_RATE = 16000  # what faster-whisper wants and what the final WAV is written at
# PipeWire's shared graph runs at 48kHz (its documented default clock rate).
# Requesting SAMPLE_RATE directly from soundcard means every chunk gets resampled
# 48kHz->16kHz inline in the live capture path. Capturing at the graph's native
# rate instead means zero client-side resampling while audio is actually being
# streamed, and a single proper polyphase resample (see stop()) afterward.
CAPTURE_RATE = 48000
# 12288 frames = 256ms at the 48kHz capture rate: fewer, larger blocking record()
# calls per second means less exposure to GIL contention with the Qt UI thread
# between calls -- a stall inside a narrow window risks a buffer xrun (audible as
# a click/crackle); a wider window has far more slack. Costs ~256ms of extra
# latency on Stop, which is unnoticeable for a "stop the recording" button.
CHUNK_FRAMES = 12288

# Loopback (system/meeting audio) and mic (room noise) are rarely at comparable
# volume -- e.g. system volume at 38% vs. a normally-gained mic means a flat
# `loopback + mic` sum lets mic room noise bury the actual meeting audio. Bring
# each source to the same target RMS before summing so neither drowns the other.
TARGET_RMS = 0.05
MIN_RMS_TO_NORMALIZE = 0.001  # below this, treat as silence -- don't amplify noise floor
MAX_GAIN = 10.0  # cap so a near-silent channel doesn't get blown up into full-scale hiss
# Ceiling on the boosted peak, not just RMS: two channels each normalized by RMS
# alone can still have a high crest factor (quiet body, loud transients), and
# summing two such boosted signals can exceed +-1 and hard-clip -- audible as
# harsh crackle. Capping each channel's peak to 0.45 guarantees their sum can't
# exceed 0.9, so the final np.clip below is never actually reached by real audio.
PEAK_HEADROOM = 0.45


def _normalize(x: np.ndarray) -> np.ndarray:
    rms = np.sqrt(np.mean(x.astype(np.float64) ** 2))
    if rms < MIN_RMS_TO_NORMALIZE:
        return x
    gain = min(TARGET_RMS / rms, MAX_GAIN)
    peak = np.abs(x).max()
    if peak > 0:
        gain = min(gain, PEAK_HEADROOM / peak)
    return x * gain


class Recorder:
    """Records loopback + mic in parallel threads until stop() is called."""

    def __init__(self):
        self._stop_event = threading.Event()
        self._paused_event = threading.Event()
        self._loopback_chunks: list[np.ndarray] = []
        self._mic_chunks: list[np.ndarray] = []
        self._threads: list[threading.Thread] = []
        self.loopback_error: str | None = None

    def start(self):
        self._stop_event.clear()
        self._paused_event.clear()
        self._loopback_chunks = []
        self._mic_chunks = []
        self.loopback_error = None
        self._threads = [
            threading.Thread(target=self._record_loopback, daemon=True),
            threading.Thread(target=self._record_mic, daemon=True),
        ]
        for t in self._threads:
            t.start()

    def pause(self):
        self._paused_event.set()

    def resume(self):
        self._paused_event.clear()

    def _record_loopback(self):
        try:
            speaker = sc.default_speaker()
            loopback_mic = sc.get_microphone(id=str(speaker.name), include_loopback=True)
            with loopback_mic.recorder(samplerate=CAPTURE_RATE, channels=1) as rec:
                while not self._stop_event.is_set():
                    # Still call record() while paused (draining the device at
                    # the same cadence) rather than stopping the stream -- that
                    # keeps the connection alive so resume is instant instead of
                    # paying the ~1.5-2s reconnect latency measured earlier.
                    # Paused audio is simply not kept.
                    chunk = rec.record(numframes=CHUNK_FRAMES)
                    if not self._paused_event.is_set():
                        self._loopback_chunks.append(chunk)
        except Exception as e:
            # Loopback is mandatory per spec (mic-only misses everyone else on the
            # call) -- record why it failed instead of silently degrading, so the
            # caller can warn the user rather than hand them a mic-only recording
            # that looks like a full meeting capture.
            self.loopback_error = f"{type(e).__name__}: {e}"

    def _record_mic(self):
        try:
            mic = sc.default_microphone()
            with mic.recorder(samplerate=CAPTURE_RATE, channels=1) as rec:
                while not self._stop_event.is_set():
                    chunk = rec.record(numframes=CHUNK_FRAMES)
                    if not self._paused_event.is_set():
                        self._mic_chunks.append(chunk)
        except Exception:
            pass  # no mic available -> loopback-only recording

    def stop(self, output_path: Path) -> Path:
        self._stop_event.set()
        for t in self._threads:
            t.join(timeout=5)

        loopback = np.concatenate(self._loopback_chunks, axis=0) if self._loopback_chunks else np.zeros((0, 1), dtype=np.float32)
        mic = np.concatenate(self._mic_chunks, axis=0) if self._mic_chunks else np.zeros((0, 1), dtype=np.float32)

        if not self._loopback_chunks and not self.loopback_error:
            self.loopback_error = "No loopback audio captured (0 chunks)."

        # Single clean polyphase resample 48kHz -> 16kHz now, instead of the
        # continuous inline resampling soundcard would otherwise do per chunk
        # during live capture (see CAPTURE_RATE comment above).
        assert CAPTURE_RATE % SAMPLE_RATE == 0, "resample_poly needs an integer ratio"
        down = CAPTURE_RATE // SAMPLE_RATE
        if len(loopback) > 0:
            loopback = resample_poly(loopback, up=1, down=down, axis=0)
        if len(mic) > 0:
            mic = resample_poly(mic, up=1, down=down, axis=0)

        length = max(len(loopback), len(mic))
        if length == 0:
            raise RuntimeError("No audio captured from loopback or microphone.")
        if len(loopback) < length:
            loopback = np.pad(loopback, ((0, length - len(loopback)), (0, 0)))
        if len(mic) < length:
            mic = np.pad(mic, ((0, length - len(mic)), (0, 0)))

        mixed = np.clip(_normalize(loopback) + _normalize(mic), -1.0, 1.0)
        pcm16 = (mixed * 32767).astype(np.int16)

        output_path.parent.mkdir(parents=True, exist_ok=True)
        with wave.open(str(output_path), "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(SAMPLE_RATE)
            wf.writeframes(pcm16.tobytes())

        return output_path
