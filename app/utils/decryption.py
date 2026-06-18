"""Decrypt fields written by soundbox-backend typeorm-encrypted (AES-256-CBC)."""

from __future__ import annotations

import base64
import os
import re

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

DEFAULT_IV_LENGTH = 16
_PLAINTEXT_RE = re.compile(r"^[\w\s\-\.@',/&()]+$", re.UNICODE)


def _pkcs7_unpad(data: bytes) -> bytes:
    if not data:
        return data
    pad_len = data[-1]
    if pad_len < 1 or pad_len > 16:
        return data
    return data[:-pad_len]


def _looks_encrypted(value: str) -> bool:
    if not value or len(value) < 20:
        return False
    if _PLAINTEXT_RE.match(value.strip()):
        return False
    try:
        raw = base64.b64decode(value, validate=True)
        return len(raw) > DEFAULT_IV_LENGTH
    except Exception:
        return False


def decrypt_field(value: str | None) -> str | None:
    if value is None or value == "":
        return value
    if not _looks_encrypted(value):
        return value

    key_hex = os.getenv("ENCRYPTION_KEY", "")
    if not key_hex:
        return value

    try:
        raw = base64.b64decode(value)
        iv_length = int(os.getenv("ENCRYPTION_IV_LENGTH", str(DEFAULT_IV_LENGTH)))
        if len(raw) <= iv_length:
            return value

        iv = raw[:iv_length]
        ciphertext = raw[iv_length:]
        key = bytes.fromhex(key_hex)

        cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
        decryptor = cipher.decryptor()
        padded = decryptor.update(ciphertext) + decryptor.finalize()
        return _pkcs7_unpad(padded).decode("utf-8")
    except Exception:
        return value
