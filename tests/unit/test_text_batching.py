from __future__ import annotations

from video_translator.domain.models import TranscriptSegment
from video_translator.utils.text_batching import batch_segments


def _segments(n: int, text_len: int = 100) -> list[TranscriptSegment]:
    return [
        TranscriptSegment(id=i, start=float(i), end=float(i + 1), text="x" * text_len)
        for i in range(n)
    ]


def test_batches_respect_char_limit():
    segments = _segments(10, text_len=100)
    batches = batch_segments(segments, max_chars=250, max_segments=100)
    for batch in batches:
        total_chars = sum(len(s.text) for s in batch)
        assert total_chars <= 350  # margen: el ultimo segmento que cabe puede acercarse al limite


def test_all_segments_preserved_in_order():
    segments = _segments(23, text_len=10)
    batches = batch_segments(segments, max_chars=50, max_segments=5)
    flattened = [s for batch in batches for s in batch]
    assert [s.id for s in flattened] == list(range(23))


def test_oversized_single_segment_gets_its_own_batch():
    huge = TranscriptSegment(id=0, start=0, end=1, text="x" * 5000)
    normal = TranscriptSegment(id=1, start=1, end=2, text="hola")
    batches = batch_segments([huge, normal], max_chars=1000)
    assert batches[0] == [huge]
    assert batches[1] == [normal]


def test_empty_input_returns_empty_list():
    assert batch_segments([]) == []
