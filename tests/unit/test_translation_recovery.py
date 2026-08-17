from __future__ import annotations

import pytest

from video_translator.domain.exceptions import TranslationError
from video_translator.domain.models import TranscriptSegment
from video_translator.infrastructure.translation.prompting import translate_batch_with_recovery


def _segments(n: int) -> list[TranscriptSegment]:
    return [TranscriptSegment(id=i, start=i, end=i + 1, text=f"line {i}") for i in range(n)]


def test_returns_directly_when_translate_fn_succeeds():
    calls = []

    def translate_fn(subset):
        calls.append(len(subset))
        return [f"t{s.id}" for s in subset]

    result = translate_batch_with_recovery(_segments(5), translate_fn)

    assert result == ["t0", "t1", "t2", "t3", "t4"]
    assert calls == [5]  # nunca tuvo que partir el lote


def test_splits_batch_on_translation_error_and_recovers():
    """Simula una respuesta truncada del LLM para el lote completo, pero que
    si funciona una vez partido en mitades mas chicas."""

    def translate_fn(subset):
        if len(subset) > 2:
            raise TranslationError("respuesta truncada, simulando max_tokens")
        return [f"t{s.id}" for s in subset]

    result = translate_batch_with_recovery(_segments(5), translate_fn)

    assert result == ["t0", "t1", "t2", "t3", "t4"]


def test_propagates_error_when_even_a_single_segment_fails():
    def translate_fn(subset):
        raise TranslationError("el LLM esta caido")

    with pytest.raises(TranslationError):
        translate_batch_with_recovery(_segments(3), translate_fn)


def test_respects_max_split_depth():
    """Si el limite de particiones se agota antes de llegar a lotes de 1,
    el error original se propaga en vez de reintentar indefinidamente."""
    calls = []

    def translate_fn(subset):
        calls.append(len(subset))
        raise TranslationError("siempre falla")

    with pytest.raises(TranslationError):
        translate_batch_with_recovery(_segments(8), translate_fn, max_split_depth=1)

    # Con profundidad 1 solo se permite UNA particion (2 mitades de 4), no
    # bajar hasta lotes de 1.
    assert max(calls) == 8
    assert all(c > 1 for c in calls)
