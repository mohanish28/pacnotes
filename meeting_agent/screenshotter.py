"""On-demand full-screen screenshots, saved next to the meeting's audio/PDF."""
import time
from pathlib import Path

import mss


def take_screenshot(output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    filename = output_dir / f"screenshot_{int(time.time() * 1000)}.png"
    with mss.mss() as sct:
        sct.shot(mon=0, output=str(filename))
    return filename
