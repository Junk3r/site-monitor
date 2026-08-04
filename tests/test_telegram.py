from site_monitor.notifications.telegram import (
    MAX_MESSAGE_LENGTH,
    build_chunks,
)


def test_empty_entries_produce_no_message():
    """Пустой чанк Telegram отклоняет с ошибкой."""

    assert build_chunks("", []) == []


def test_header_only_survives():

    assert build_chunks("Digest", []) == ["Digest"]


def test_short_digest_fits_one_message():

    chunks = build_chunks("Digest", ["one", "two", "three"])

    assert len(chunks) == 1

    assert chunks[0].startswith("Digest")

    assert "three" in chunks[0]


def test_long_digest_splits_within_limit():

    entries = ["x" * 500 for _ in range(20)]

    chunks = build_chunks("Digest", entries)

    assert len(chunks) > 1

    assert all(len(chunk) <= MAX_MESSAGE_LENGTH for chunk in chunks)


def test_oversized_single_entry_is_truncated_not_dropped():

    chunks = build_chunks("", ["y" * (MAX_MESSAGE_LENGTH * 2)])

    assert len(chunks) == 1

    assert len(chunks[0]) <= MAX_MESSAGE_LENGTH

    assert chunks[0].endswith("...")


def test_every_entry_survives_the_split():

    entries = [f"entry-{index} " + "z" * 300 for index in range(30)]

    joined = "\n".join(build_chunks("Digest", entries))

    for index in range(30):
        assert f"entry-{index} " in joined
