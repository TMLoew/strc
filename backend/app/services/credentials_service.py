from __future__ import annotations

from dataclasses import dataclass
from typing import Dict
from uuid import uuid4

from cryptography.fernet import Fernet


@dataclass
class SwissquoteCreds:
    username: str
    password: str


_fernet = Fernet(Fernet.generate_key())
_sq_creds: Dict[str, bytes] = {}


def store_swissquote_creds(username: str, password: str) -> str:
    token = str(uuid4())
    payload = f"{username}\n{password}".encode("utf-8")
    _sq_creds[token] = _fernet.encrypt(payload)
    return token


def pop_swissquote_creds(token: str) -> SwissquoteCreds | None:
    encrypted = _sq_creds.pop(token, None)
    if not encrypted:
        return None
    decrypted = _fernet.decrypt(encrypted).decode("utf-8")
    username, password = decrypted.split("\n", 1)
    return SwissquoteCreds(username=username, password=password)
