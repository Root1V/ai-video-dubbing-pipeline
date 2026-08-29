"""Division de texto libre en fragmentos, compartida entre casos de uso que
sintetizan voz a partir de texto (`SynthesizeTextUseCase`, `GenerateMicroVideoUseCase`)."""

from __future__ import annotations

import re


def split_into_chunks(text: str, max_chars: int) -> list[str]:
    """Divide el texto en fragmentos por oracion, agrupando de forma codiciosa
    hasta `max_chars`. No es una tokenizacion linguistica precisa -- solo
    evita mandarle al modelo un texto arbitrariamente largo en una sola
    pasada."""
    sentences = [s for s in re.split(r"(?<=[.!?])\s+", text.strip()) if s]
    if not sentences:
        return [text.strip()]

    chunks: list[str] = []
    current = ""
    for sentence in sentences:
        candidate = f"{current} {sentence}".strip() if current else sentence
        if len(candidate) > max_chars and current:
            chunks.append(current)
            current = sentence
        else:
            current = candidate
    if current:
        chunks.append(current)
    return chunks
