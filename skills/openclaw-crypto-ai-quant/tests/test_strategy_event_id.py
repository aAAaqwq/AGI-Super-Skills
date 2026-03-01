from __future__ import annotations

from strategy.event_id import generate_event_id

_ULID_ALPHABET = set("0123456789ABCDEFGHJKMNPQRSTVWXYZ")


def test_generate_event_id_has_expected_shape() -> None:
    event_id = generate_event_id()
    assert len(event_id) == 26
    assert set(event_id).issubset(_ULID_ALPHABET)


def test_generate_event_id_is_unique_across_small_batch() -> None:
    ids = {generate_event_id() for _ in range(200)}
    assert len(ids) == 200
