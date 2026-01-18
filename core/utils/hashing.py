import hashlib
from pathlib import Path


def sha256_file(path: str | Path) -> str:
    sha256 = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(8192), b""):
            sha256.update(chunk)
    return sha256.hexdigest()


def sha256_text(value: str) -> str:
    sha256 = hashlib.sha256()
    sha256.update(value.encode("utf-8"))
    return sha256.hexdigest()
