from __future__ import annotations

from cryptography.fernet import Fernet

_fernet = Fernet(Fernet.generate_key())
_session_state: bytes | None = None


import json


def store_session_state(state: dict) -> None:
    global _session_state
    payload = json.dumps(state).encode("utf-8")
    _session_state = _fernet.encrypt(payload)


def get_session_state() -> dict | None:
    if _session_state is None:
        return None
    decrypted = _fernet.decrypt(_session_state).decode("utf-8")
    return json.loads(decrypted)


def clear_session_state() -> None:
    global _session_state
    _session_state = None
