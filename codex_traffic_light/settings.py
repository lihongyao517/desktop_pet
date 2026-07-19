from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import os

from .paths import legacy_settings_path, settings_path


@dataclass(slots=True)
class Settings:
    sound_enabled: bool = True
    always_on_top: bool = True
    compact_mode: bool = False
    full_scene_origin_y: int = 55
    approval_repeat_seconds: int = 45
    window_x: int | None = None
    window_y: int | None = None

    @classmethod
    def load(cls) -> "Settings":
        path = settings_path()
        if not path.exists():
            legacy = legacy_settings_path()
            if legacy.exists():
                path = legacy
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return cls()
        if not isinstance(data, dict):
            return cls()
        allowed = {field for field in cls.__dataclass_fields__}
        return cls(**{key: value for key, value in data.items() if key in allowed})

    def save(self) -> None:
        path = settings_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
        temporary.write_text(
            json.dumps(asdict(self), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        os.replace(temporary, path)
