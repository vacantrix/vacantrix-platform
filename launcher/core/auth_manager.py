import json
import sys
from pathlib import Path
from datetime import datetime, timezone

from . import supabase_api as api


def _session_file_path() -> Path:
    if getattr(sys, "frozen", False):
        return Path.home() / "AppData" / "Local" / "VacantrixPlatform" / "data" / "session.json"
    return Path(__file__).parent.parent.parent / "data" / "session.json"


_SESSION_FILE = _session_file_path()


class AuthManager:
    def __init__(self):
        self._session: dict | None = None
        _SESSION_FILE.parent.mkdir(exist_ok=True)

    # ── Persistence ───────────────────────────────────────────────────────────

    def _save(self) -> None:
        if self._session:
            _SESSION_FILE.write_text(json.dumps(self._session), encoding="utf-8")

    def _load(self) -> dict | None:
        if not _SESSION_FILE.exists():
            return None
        try:
            return json.loads(_SESSION_FILE.read_text(encoding="utf-8"))
        except Exception:
            return None

    def _clear(self) -> None:
        self._session = None
        try:
            _SESSION_FILE.unlink(missing_ok=True)
        except Exception:
            pass

    # ── Token helpers ─────────────────────────────────────────────────────────

    @property
    def access_token(self) -> str | None:
        return self._session.get("access_token") if self._session else None

    @property
    def user(self) -> dict | None:
        return self._session.get("user") if self._session else None

    def _is_expired(self) -> bool:
        if not self._session:
            return True
        exp = self._session.get("expires_at")
        if not exp:
            return True
        return datetime.fromtimestamp(exp, tz=timezone.utc) <= datetime.now(tz=timezone.utc)

    # ── Public API ────────────────────────────────────────────────────────────

    def restore_session(self) -> bool:
        """Try to restore session from keyring. Returns True if logged in."""
        saved = self._load()
        if not saved:
            return False
        self._session = saved
        if self._is_expired():
            try:
                refreshed = api.refresh_session(saved["refresh_token"])
                self._session = refreshed
                self._save()
                return True
            except Exception:
                self._clear()
                return False
        return True

    def sign_in(self, email: str, password: str) -> dict:
        data = api.sign_in(email, password)
        self._session = data
        self._save()
        return data

    def sign_up(self, email: str, password: str) -> dict:
        data = api.sign_up(email, password)
        # Auto sign-in if session returned (email confirm disabled)
        if data.get("access_token"):
            self._session = data
            self._save()
        return data

    def sign_out(self) -> None:
        if self.access_token:
            try:
                api.sign_out(self.access_token)
            except Exception:
                pass
        self._clear()

    def is_logged_in(self) -> bool:
        return bool(self._session and self.access_token)
