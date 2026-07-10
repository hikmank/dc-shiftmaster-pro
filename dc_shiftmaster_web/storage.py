"""StorageAdapter - browser localStorage persistence via Flet shared_preferences."""
from __future__ import annotations
import asyncio, json
from datetime import datetime
from dc_shiftmaster.models import Override, ShiftWindow, Teammate

_KEY_TEAMMATES = "dcshift.teammates"
_KEY_SHIFT_WINDOWS = "dcshift.shift_windows"
_KEY_OVERRIDES = "dcshift.overrides"
_KEY_YEAR = "dcshift.year"
_KEY_REGION = "dcshift.region"
_ALL_KEYS = [_KEY_TEAMMATES, _KEY_SHIFT_WINDOWS, _KEY_OVERRIDES, _KEY_YEAR, _KEY_REGION]

class StorageAdapter:
    def __init__(self, page) -> None:
        self._storage = getattr(page, "shared_preferences", None) or getattr(page, "client_storage", None)
        self._cache: dict[str, str | None] = {}
        self._async_mode = False
        try:
            for key in _ALL_KEYS:
                val = self._storage.get(key)
                if asyncio.iscoroutine(val):
                    val.close()
                    self._async_mode = True
                    break
                self._cache[key] = val
        except Exception:
            pass
        if not self._async_mode:
            self._seed_defaults()

    @classmethod
    async def async_init(cls, page) -> "StorageAdapter":
        obj = cls.__new__(cls)
        obj._storage = page.shared_preferences
        obj._cache = {}
        obj._async_mode = True
        for key in _ALL_KEYS:
            obj._cache[key] = await obj._storage.get(key)
        obj._seed_defaults()
        return obj

    def _seed_defaults(self) -> None:
        if self._cache.get(_KEY_SHIFT_WINDOWS) is None:
            d = {"day": {"shift_type": "day", "start_time": "06:00", "end_time": "18:30"},
                 "night": {"shift_type": "night", "start_time": "18:00", "end_time": "06:30"}}
            self._put(_KEY_SHIFT_WINDOWS, json.dumps(d))

    def _get(self, key: str) -> str | None:
        return self._cache.get(key)

    def _put(self, key: str, value: str) -> None:
        self._cache[key] = value
        if self._async_mode:
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(self._storage.set(key, value))
            except RuntimeError:
                pass
        else:
            try:
                self._storage.set(key, value)
            except Exception:
                pass

    @staticmethod
    def _serialize_teammates(teammates):
        return json.dumps([{"id": t.id, "name": t.name, "shift_type": t.shift_type, "custom_start": t.custom_start} for t in teammates])

    @staticmethod
    def _deserialize_teammates(json_str):
        return [Teammate(id=d["id"], name=d["name"], shift_type=d["shift_type"], custom_start=d.get("custom_start", "")) for d in json.loads(json_str)]

    @staticmethod
    def _serialize_overrides(overrides):
        return json.dumps([{"date": o.date, "shift_type": o.shift_type, "name": o.name} for o in overrides])

    @staticmethod
    def _deserialize_overrides(json_str):
        return [Override(date=d["date"], shift_type=d["shift_type"], name=d["name"]) for d in json.loads(json_str)]

    @staticmethod
    def _serialize_shift_windows(windows):
        return json.dumps({k: {"shift_type": sw.shift_type, "start_time": sw.start_time, "end_time": sw.end_time} for k, sw in windows.items()})

    @staticmethod
    def _deserialize_shift_windows(json_str):
        return {k: ShiftWindow(shift_type=d["shift_type"], start_time=d["start_time"], end_time=d["end_time"]) for k, d in json.loads(json_str).items()}

    def get_shift_windows(self):
        raw = self._get(_KEY_SHIFT_WINDOWS)
        return {} if raw is None else self._deserialize_shift_windows(raw)

    def update_shift_window(self, shift_type, start, end):
        w = self.get_shift_windows()
        w[shift_type] = ShiftWindow(shift_type=shift_type, start_time=start, end_time=end)
        self._put(_KEY_SHIFT_WINDOWS, self._serialize_shift_windows(w))

    def get_teammates(self):
        raw = self._get(_KEY_TEAMMATES)
        return [] if raw is None else self._deserialize_teammates(raw)

    def add_teammate(self, name, shift_type, custom_start=""):
        if not name or not name.strip():
            raise ValueError("Teammate name must not be empty or whitespace-only.")
        teammates = self.get_teammates()
        new_id = max((t.id for t in teammates), default=0) + 1
        teammates.append(Teammate(id=new_id, name=name, shift_type=shift_type, custom_start=custom_start))
        self._put(_KEY_TEAMMATES, self._serialize_teammates(teammates))
        return new_id

    def update_teammate(self, teammate_id, name, shift_type, custom_start=""):
        if not name or not name.strip():
            raise ValueError("Teammate name must not be empty or whitespace-only.")
        teammates = self.get_teammates()
        for t in teammates:
            if t.id == teammate_id:
                t.name, t.shift_type, t.custom_start = name, shift_type, custom_start
                break
        self._put(_KEY_TEAMMATES, self._serialize_teammates(teammates))

    def delete_teammate(self, teammate_id):
        self._put(_KEY_TEAMMATES, self._serialize_teammates([t for t in self.get_teammates() if t.id != teammate_id]))

    def _get_all_overrides(self):
        raw = self._get(_KEY_OVERRIDES)
        return [] if raw is None else self._deserialize_overrides(raw)

    def get_overrides(self, year):
        prefix = str(year)
        return [o for o in self._get_all_overrides() if o.date.startswith(prefix)]

    def set_override(self, date, shift_type, name):
        overrides = [o for o in self._get_all_overrides() if not (o.date == date and o.shift_type == shift_type)]
        overrides.append(Override(date=date, shift_type=shift_type, name=name))
        self._put(_KEY_OVERRIDES, self._serialize_overrides(overrides))

    def remove_override(self, date, shift_type):
        self._put(_KEY_OVERRIDES, self._serialize_overrides([o for o in self._get_all_overrides() if not (o.date == date and o.shift_type == shift_type)]))

    def get_year(self):
        raw = self._get(_KEY_YEAR)
        return datetime.now().year if raw is None else int(raw)

    def set_year(self, year):
        self._put(_KEY_YEAR, str(year))

    def get_region(self):
        raw = self._get(_KEY_REGION)
        return "" if raw is None else raw

    def set_region(self, region):
        self._put(_KEY_REGION, region)
