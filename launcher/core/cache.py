import json
from pathlib import Path

_CACHE_FILE = Path(__file__).parent.parent.parent / "data" / "catalog_cache.json"
_CACHE_FILE.parent.mkdir(exist_ok=True)


def load() -> tuple[list, list] | None:
    if not _CACHE_FILE.exists():
        return None
    try:
        data = json.loads(_CACHE_FILE.read_text(encoding="utf-8"))
        return data["tools"], data["subs"]
    except Exception:
        return None


def save(tools: list, subs: list) -> None:
    try:
        _CACHE_FILE.write_text(
            json.dumps({"tools": tools, "subs": subs}, ensure_ascii=False),
            encoding="utf-8",
        )
    except Exception:
        pass


def clear() -> None:
    try:
        _CACHE_FILE.unlink(missing_ok=True)
    except Exception:
        pass
