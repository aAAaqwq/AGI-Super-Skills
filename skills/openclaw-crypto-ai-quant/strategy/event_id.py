from __future__ import annotations

import secrets
import time

_ULID_ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"


def generate_event_id() -> str:
    """Generate a ULID-compatible event id."""
    t = int(time.time() * 1000)
    time_part = ""
    for _ in range(10):
        time_part = _ULID_ALPHABET[t & 0x1F] + time_part
        t >>= 5
    alphabet_len = len(_ULID_ALPHABET)
    rand_part = "".join(_ULID_ALPHABET[secrets.randbelow(alphabet_len)] for _ in range(16))
    return time_part + rand_part
