from app.business.minifig_suffixes import (
    SuffixProbe,
    drop_unstickered_shells,
    letters_if_unknown,
)


def _walk(found: set[str], max_miss: int = 2) -> list[str]:
    probe = SuffixProbe(max_miss)
    seen: list[str] = []
    while True:
        letter = probe.next_letter()
        if letter is None:
            return seen
        seen.append(letter)
        probe.observe(letter, letter in found)
    return seen


def test_unknown_number_still_reaches_sticker_and_plain():
    # a и b пустые — раньше обход на этом заканчивался и s не спрашивали
    assert _walk(set()) == ["a", "b", "s", "i"]
    assert letters_if_unknown() == ["a", "b", "s", "i"]


def test_hit_resets_misses_then_still_checks_detached():
    # a есть, b и c пустые → стоп ряда, но s и i всё равно
    assert _walk({"a"}) == ["a", "b", "c", "s", "i"]


def test_detached_not_requested_twice_if_sequence_reached_it():
    probe = SuffixProbe(max_consecutive_miss=30)
    seen: list[str] = []
    while True:
        letter = probe.next_letter()
        if letter is None:
            break
        seen.append(letter)
        probe.observe(letter, True)
    assert seen.count("s") == 1
    assert seen[0] == "a"
    assert "s" in seen and "i" in seen


def test_drop_without_sticker_shell_when_s_variant_present():
    records = [
        ("bob009", "Robot SpongeBob without Sticker"),
        ("bob009s", "Robot SpongeBob with Sticker"),
        ("bob010", "Robot Customer without Stickers"),
        ("bob010s", "Robot Customer with Stickers"),
        ("bob016", "SpongeBob Squarepants with Bandages"),
        ("bob024", "Plankton"),
        ("bob024s", "Plankton with Sticker"),
    ]
    kept = dict(drop_unstickered_shells(records))
    assert "bob009" not in kept
    assert "bob010" not in kept
    assert kept["bob009s"].startswith("Robot SpongeBob")
    assert "bob016" in kept
    assert "bob024" in kept
    assert "bob024s" in kept


def test_keep_shell_if_sticker_variant_missing():
    records = [("bob009", "Robot SpongeBob without Sticker")]
    assert drop_unstickered_shells(records) == [
        ("bob009", "Robot SpongeBob without Sticker")
    ]


def test_series_prefix_stops_at_digit():
    from app.business.bricklink_ids import is_series_item

    assert is_series_item("sw0001a", "sw")
    assert is_series_item("bob009s", "bob")
    assert is_series_item("col012", "col")
    assert not is_series_item("colhp01", "col")
    assert is_series_item("colhp01", "colhp")
    assert not is_series_item("sw0001", "s")
