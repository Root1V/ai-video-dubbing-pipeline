from __future__ import annotations

from video_translator.domain.models import TranslatedSegment
from video_translator.utils.synthesis_grouping import group_segments_for_synthesis


def _seg(id_, start, end, text, speaker_id=None):
    return TranslatedSegment(id=id_, start=start, end=end, source_text="x", translated_text=text, speaker_id=speaker_id)


def test_merges_consecutive_same_speaker_with_small_gap():
    segments = [
        _seg(0, 0.0, 1.0, "Hola.", speaker_id="A"),
        _seg(1, 1.2, 2.0, "Como estas.", speaker_id="A"),
    ]
    groups = group_segments_for_synthesis(segments, max_gap_seconds=0.5, max_group_chars=200)
    assert len(groups) == 1
    assert groups[0].text == "Hola. Como estas."
    assert groups[0].start == 0.0
    assert groups[0].end == 2.0
    assert groups[0].member_ids == (0, 1)


def test_does_not_merge_different_speakers():
    segments = [
        _seg(0, 0.0, 1.0, "Hola.", speaker_id="A"),
        _seg(1, 1.1, 2.0, "Hola tambien.", speaker_id="B"),
    ]
    groups = group_segments_for_synthesis(segments, max_gap_seconds=0.5, max_group_chars=200)
    assert len(groups) == 2


def test_does_not_merge_when_speaker_id_is_none():
    """Sin diarizacion (speaker_id=None) nunca se fusiona, aunque el hueco
    sea chico: no hay garantia de que sea la misma persona hablando."""
    segments = [
        _seg(0, 0.0, 1.0, "Hola."),
        _seg(1, 1.1, 2.0, "Como estas."),
    ]
    groups = group_segments_for_synthesis(segments, max_gap_seconds=0.5, max_group_chars=200)
    assert len(groups) == 2


def test_does_not_merge_when_gap_too_large():
    segments = [
        _seg(0, 0.0, 1.0, "Hola.", speaker_id="A"),
        _seg(1, 5.0, 6.0, "Volvi.", speaker_id="A"),  # 4s de silencio: no es continuo
    ]
    groups = group_segments_for_synthesis(segments, max_gap_seconds=0.5, max_group_chars=200)
    assert len(groups) == 2


def test_does_not_merge_beyond_char_limit():
    long_text_a = "x" * 150
    long_text_b = "y" * 100
    segments = [
        _seg(0, 0.0, 1.0, long_text_a, speaker_id="A"),
        _seg(1, 1.1, 2.0, long_text_b, speaker_id="A"),
    ]
    groups = group_segments_for_synthesis(segments, max_gap_seconds=0.5, max_group_chars=200)
    assert len(groups) == 2  # 150 + 1 + 100 > 200, no entra en un solo grupo


def test_empty_input_returns_empty_list():
    assert group_segments_for_synthesis([]) == []


def test_chain_of_three_merges_into_one_group():
    segments = [
        _seg(0, 0.0, 1.0, "Uno.", speaker_id="A"),
        _seg(1, 1.1, 2.0, "Dos.", speaker_id="A"),
        _seg(2, 2.1, 3.0, "Tres.", speaker_id="A"),
    ]
    groups = group_segments_for_synthesis(segments, max_gap_seconds=0.5, max_group_chars=200)
    assert len(groups) == 1
    assert groups[0].member_ids == (0, 1, 2)
    assert groups[0].text == "Uno. Dos. Tres."
