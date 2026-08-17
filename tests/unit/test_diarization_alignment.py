from __future__ import annotations

from video_translator.domain.models import DiarizationSegment, TranscriptSegment
from video_translator.utils.diarization_alignment import (
    assign_speakers,
    select_reference_windows,
    unique_speaker_labels,
)


def test_assign_speakers_picks_max_overlap():
    segments = [
        TranscriptSegment(id=0, start=0.0, end=2.0, text="Hola"),
        TranscriptSegment(id=1, start=2.0, end=5.0, text="Como estas"),
    ]
    diarization = [
        DiarizationSegment(start=0.0, end=2.2, speaker_label="SPEAKER_00"),
        DiarizationSegment(start=2.2, end=5.0, speaker_label="SPEAKER_01"),
    ]
    result = assign_speakers(segments, diarization)
    assert result[0].speaker_id == "SPEAKER_00"
    assert result[1].speaker_id == "SPEAKER_01"
    # No debe mutar los segmentos originales (son inmutables/frozen).
    assert segments[0].speaker_id is None


def test_assign_speakers_without_diarization_returns_same_list():
    segments = [TranscriptSegment(id=0, start=0.0, end=1.0, text="Hi")]
    assert assign_speakers(segments, []) is segments


def test_select_reference_windows_picks_longest_turn_and_respects_min_max():
    diarization = [
        DiarizationSegment(start=0.0, end=2.0, speaker_label="A"),   # 2s, muy corto
        DiarizationSegment(start=10.0, end=30.0, speaker_label="A"),  # 20s, el mas largo
        DiarizationSegment(start=40.0, end=41.0, speaker_label="B"),  # 1s, descartado (< min)
    ]
    windows = select_reference_windows(diarization, min_seconds=6.0, max_seconds=15.0)
    assert "B" not in windows
    start, end = windows["A"]
    assert start == 10.0
    assert end - start == 15.0  # recortado al maximo permitido


def test_unique_speaker_labels_preserves_first_seen_order():
    diarization = [
        DiarizationSegment(start=0, end=1, speaker_label="B"),
        DiarizationSegment(start=1, end=2, speaker_label="A"),
        DiarizationSegment(start=2, end=3, speaker_label="B"),
    ]
    assert unique_speaker_labels(diarization) == ["B", "A"]
