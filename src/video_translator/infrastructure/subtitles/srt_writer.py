"""Implementacion de SubtitleWriter: genera archivos de subtitulos en formato SRT."""

from __future__ import annotations

from pathlib import Path

from video_translator.domain.models import TranslatedSegment


class SrtSubtitleWriter:
    def write(
        self, segments: list[TranslatedSegment], output_path: Path, use_translation: bool = True
    ) -> Path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        lines = []
        for idx, seg in enumerate(segments, start=1):
            text = seg.translated_text if use_translation else seg.source_text
            lines.append(str(idx))
            lines.append(f"{self._format_timestamp(seg.start)} --> {self._format_timestamp(seg.end)}")
            lines.append(text)
            lines.append("")
        output_path.write_text("\n".join(lines), encoding="utf-8")
        return output_path

    @staticmethod
    def _format_timestamp(seconds: float) -> str:
        if seconds < 0:
            seconds = 0.0
        total_ms = round(seconds * 1000)
        hours, rem_ms = divmod(total_ms, 3_600_000)
        minutes, rem_ms = divmod(rem_ms, 60_000)
        secs, millis = divmod(rem_ms, 1000)
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"
