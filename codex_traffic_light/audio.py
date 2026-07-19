from __future__ import annotations

import threading

try:
    import winsound
except ImportError:  # pragma: no cover - Windows is the target platform.
    winsound = None  # type: ignore[assignment]


PATTERNS: dict[str, tuple[tuple[int, int], ...]] = {
    "approval": ((880, 160), (659, 130), (880, 240)),
    "completed": ((523, 100), (659, 110), (784, 190)),
    "error": ((784, 140), (587, 150), (392, 260)),
    "test": ((523, 90), (659, 90), (784, 120)),
}


def play_async(kind: str) -> None:
    pattern = PATTERNS.get(kind)
    if not pattern or winsound is None:
        return

    def play() -> None:
        try:
            for frequency, duration in pattern:
                winsound.Beep(frequency, duration)
        except RuntimeError:
            try:
                winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)
            except RuntimeError:
                pass

    threading.Thread(target=play, name=f"sound-{kind}", daemon=True).start()

