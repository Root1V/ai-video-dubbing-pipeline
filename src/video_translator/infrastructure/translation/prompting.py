"""Construccion de prompts y parseo de respuesta, compartido entre backends LLM.

Tanto OllamaTranslator como LlamaServerTranslator (o cualquier otro backend que
hable con un LLM instructivo) usan exactamente la misma estrategia de prompting:
solo cambia el transporte HTTP (API nativa de Ollama vs. API compatible con
OpenAI de llama.cpp/llama-server, vLLM, LM Studio, etc.).
"""

from __future__ import annotations

import re

from video_translator.domain.exceptions import TranslationError
from video_translator.domain.models import TranscriptSegment, TranslationContext

SYSTEM_PROMPT_TEMPLATE = """Eres un traductor profesional especializado en subtitulado y \
doblaje de video, traduciendo de {source_lang} a {target_lang}.

Reglas estrictas de formato:
- Recibiras lineas de texto numeradas (1, 2, 3, ...). Algunas pueden incluir una etiqueta de \
hablante entre corchetes al inicio, p.ej. "[Hablante SPEAKER_00 - voz masculina]".
- Debes devolver EXACTAMENTE el mismo numero de lineas, en el mismo orden, cada una \
precedida por su numero y un punto, en el formato "N. traduccion" — SIN repetir la \
etiqueta de hablante en tu respuesta, solo la traduccion del texto.
- Traduce el SENTIDO y el REGISTRO, no palabra por palabra; que suene natural al hablarse.
- No agregues explicaciones, notas, ni texto fuera de las lineas numeradas.
- Conserva nombres propios, siglas y numeros tal como aparecen salvo que el glosario \
indique lo contrario.
- Manten la coherencia terminologica con las traducciones previas mostradas como contexto.
- Estas lineas se usaran para generar voz sintetica que debe encajar en el mismo tiempo que \
duraba la frase original: prioriza traducciones CONCISAS, de longitud similar al original en \
numero de silabas/palabras, evitando rodeos o formulas mas largas cuando haya una opcion mas \
corta con el mismo significado. Esto es mas importante aun que sonar perfectamente idiomatico.
- Cuando una linea indique el genero del hablante, ajusta la concordancia gramatical del \
espanol en consecuencia (p.ej. adjetivos y participios: "estoy cansado" vs "estoy cansada"). \
Si no se indica genero, usa formas neutras o el masculino generico solo cuando sea inevitable.
- Si varios hablantes distintos participan, manten el registro y las muletillas de cada uno \
consistentes a lo largo de sus propias lineas (no mezcles el estilo de un hablante con el de otro).
"""

_GENDER_LABELS_ES = {"male": "voz masculina", "female": "voz femenina", "unknown": "genero no determinado"}


def build_system_prompt(context: TranslationContext) -> str:
    base = SYSTEM_PROMPT_TEMPLATE.format(
        source_lang=context.source_lang, target_lang=context.target_lang
    )
    extras = []
    if context.tone:
        extras.append(f"Tono deseado: {context.tone}.")
    if context.prompt:
        extras.append(f"Contexto del contenido (usalo para mejorar la calidad):\n{context.prompt}")
    if context.glossary:
        glossary_lines = "\n".join(f"- \"{k}\" -> \"{v}\"" for k, v in context.glossary.items())
        extras.append(
            f"Glosario obligatorio (usa siempre esta traduccion para estos terminos):\n{glossary_lines}"
        )
    if context.speaker_genders:
        speaker_lines = "\n".join(
            f"- {label}: {_GENDER_LABELS_ES.get(gender, gender)}"
            for label, gender in context.speaker_genders.items()
        )
        extras.append(
            "Genero estimado de cada hablante detectado (usalo para la concordancia "
            f"gramatical en espanol):\n{speaker_lines}"
        )
    if extras:
        base += "\n" + "\n\n".join(extras)
    return base


def build_user_prompt(
    segments: list[TranscriptSegment],
    rolling_history: list[str],
    speaker_genders: dict[str, str] | None = None,
) -> str:
    parts = []
    if rolling_history:
        history_block = "\n".join(rolling_history)
        parts.append(
            "Traducciones recientes (solo como referencia de estilo, no las repitas):\n"
            f"{history_block}"
        )
    numbered = "\n".join(
        f"{i}. {_format_line(seg, speaker_genders)}" for i, seg in enumerate(segments, start=1)
    )
    parts.append(f"Traduce estas {len(segments)} lineas:\n{numbered}")
    return "\n\n".join(parts)


def _format_line(seg: TranscriptSegment, speaker_genders: dict[str, str] | None) -> str:
    if not seg.speaker_id:
        return seg.text
    gender = (speaker_genders or {}).get(seg.speaker_id, "unknown")
    gender_label = _GENDER_LABELS_ES.get(gender, gender)
    return f"[Hablante {seg.speaker_id} - {gender_label}] {seg.text}"


def translate_batch_with_recovery(
    segments: list[TranscriptSegment],
    translate_fn,
    max_split_depth: int = 6,
) -> list[str]:
    """Envoltorio de resiliencia alrededor de una funcion "traducir este lote".

    Si el LLM trunca su respuesta antes de completar todas las lineas (p.ej.
    por llegar al limite de max_tokens en una respuesta larga), ``translate_fn``
    lanza ``TranslationError`` por desalineacion. En vez de abortar todo el
    pipeline — desperdiciando trabajo previo costoso como la diarizacion —
    se parte el lote a la mitad y se reintenta cada mitad por separado,
    recursivamente, hasta que cada sub-lote sea lo bastante chico para caber
    en la respuesta del modelo (o hasta llegar a un solo segmento, caso en el
    que un fallo si se propaga: ya no hay como dividir mas).
    """
    if not segments:
        return []
    try:
        return translate_fn(segments)
    except TranslationError:
        if len(segments) == 1 or max_split_depth <= 0:
            raise
        mid = len(segments) // 2
        left = translate_batch_with_recovery(segments[:mid], translate_fn, max_split_depth - 1)
        right = translate_batch_with_recovery(segments[mid:], translate_fn, max_split_depth - 1)
        return left + right


def parse_numbered_lines(raw_text: str, expected: int) -> list[str]:
    pattern = re.compile(r"^\s*(\d+)\.\s?(.*)$")
    found: dict[int, str] = {}
    for line in raw_text.splitlines():
        match = pattern.match(line)
        if match:
            idx = int(match.group(1))
            found[idx] = match.group(2).strip()

    if len(found) != expected:
        raise TranslationError(
            f"Desalineacion en la respuesta del LLM: se esperaban {expected} lineas "
            f"numeradas y se encontraron {len(found)}. Respuesta cruda: {raw_text[:300]!r}"
        )

    return [found[i] for i in range(1, expected + 1)]
