"""Utilidades para agrupar segmentos largos en lotes manejables por el LLM.

Un video de mas de una hora puede generar cientos o miles de segmentos de
transcripcion. Enviarlos todos en una sola peticion al LLM excederia la ventana
de contexto y degradaria la calidad. Se agrupan en lotes acotados por numero de
caracteres, preservando el orden y los limites de segmento.
"""

from __future__ import annotations

from video_translator.domain.models import TranscriptSegment


def batch_segments(
    segments: list[TranscriptSegment], max_chars: int = 1800, max_segments: int = 40
) -> list[list[TranscriptSegment]]:
    """Divide la lista de segmentos en lotes que no excedan ``max_chars`` caracteres.

    Nunca divide un segmento individual; si un segmento por si solo supera
    ``max_chars`` se envia igualmente como lote propio (no se trunca el texto).
    """
    batches: list[list[TranscriptSegment]] = []
    current: list[TranscriptSegment] = []
    current_chars = 0

    for seg in segments:
        seg_len = len(seg.text)
        would_exceed_chars = current and (current_chars + seg_len) > max_chars
        would_exceed_count = len(current) >= max_segments
        if would_exceed_chars or would_exceed_count:
            batches.append(current)
            current = []
            current_chars = 0
        current.append(seg)
        current_chars += seg_len

    if current:
        batches.append(current)

    return batches
