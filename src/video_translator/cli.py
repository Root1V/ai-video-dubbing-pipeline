"""Interfaz de linea de comandos (CLI) de Video Translator."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from video_translator.config import load_settings
from video_translator.container import build_translate_video_use_case
from video_translator.domain.exceptions import VideoTranslatorError
from video_translator.domain.models import OutputMode, TranslateVideoRequest, TranslationContext
from video_translator.utils.logging_config import configure_logging, get_logger

app = typer.Typer(
    name="video-translator",
    help="Traduce videos MP4 largos de ingles a espanol usando IA open source.",
    add_completion=False,
)
console = Console()
logger = get_logger(__name__)


@app.command()
def translate(
    input: Path = typer.Option(..., "--input", "-i", exists=True, help="Ruta al video .mp4 de entrada."),
    output_dir: Path = typer.Option(Path("./output"), "--output-dir", "-o", help="Carpeta de salida."),
    context: Optional[str] = typer.Option(
        None,
        "--context",
        "-c",
        help=(
            "Prompt de contexto en lenguaje natural para mejorar la traduccion "
            "(dominio, tono, audiencia). Tambien puede ser la ruta a un .txt."
        ),
    ),
    glossary: Optional[Path] = typer.Option(
        None, "--glossary", "-g", help="Ruta a un JSON {'termino_en': 'termino_es'}."
    ),
    tone: Optional[str] = typer.Option(None, "--tone", help="Tono deseado: formal, informal, tecnico..."),
    mode: OutputMode = typer.Option(
        OutputMode.SOFT_SUBTITLES, "--mode", "-m", help="Modo de salida del video."
    ),
    keep_original_audio: bool = typer.Option(
        True, "--keep-original-audio/--no-keep-original-audio", help="Solo aplica a --mode dubbed."
    ),
    speaker_reference: Optional[Path] = typer.Option(
        None, "--speaker-wav", help="Muestra de voz .wav para clonar el timbre en el doblaje (fallback si no hay diarizacion, o para video de un solo hablante)."
    ),
    diarize: bool = typer.Option(
        False,
        "--diarize/--no-diarize",
        help="Detecta multiples hablantes y clona la voz/estima el genero de cada uno por separado.",
    ),
    min_speakers: Optional[int] = typer.Option(None, "--min-speakers", help="Pista opcional para la diarizacion."),
    max_speakers: Optional[int] = typer.Option(None, "--max-speakers", help="Pista opcional para la diarizacion."),
    source_lang: str = typer.Option("en", help="Idioma de origen (codigo ISO)."),
    target_lang: str = typer.Option("es", help="Idioma de destino (codigo ISO)."),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Traduce un video completo: transcribe, traduce con contexto y genera subtitulos/doblaje."""
    settings = load_settings()
    configure_logging(level="DEBUG" if verbose else settings.log_level, json_logs=settings.log_json)

    context_prompt = _resolve_context_text(context)
    glossary_dict = _load_glossary(glossary)

    translation_context = TranslationContext(
        prompt=context_prompt or "",
        glossary=glossary_dict,
        source_lang=source_lang,
        target_lang=target_lang,
        tone=tone,
    )

    request = TranslateVideoRequest(
        input_video=input,
        output_dir=output_dir,
        context=translation_context,
        output_mode=mode,
        keep_original_audio_track=keep_original_audio,
        speaker_reference_wav=speaker_reference,
        source_lang_hint=source_lang,
        diarize=diarize,
        min_speakers=min_speakers,
        max_speakers=max_speakers,
    )

    use_case = build_translate_video_use_case(
        settings, enable_dubbing=(mode == OutputMode.DUBBED), enable_diarization=diarize
    )

    console.rule("[bold cyan]Video Translator")
    console.print(f"[bold]Entrada:[/bold] {input}")
    console.print(f"[bold]Modo:[/bold] {mode.value}")
    if diarize:
        console.print("[bold]Diarizacion:[/bold] activada (multi-hablante)")
    if context_prompt:
        console.print(f"[bold]Contexto:[/bold] {context_prompt[:120]}{'...' if len(context_prompt) > 120 else ''}")

    try:
        with console.status("[bold green]Procesando video (esto puede tardar segun la duracion)..."):
            result = use_case.execute(request)
    except VideoTranslatorError as exc:
        console.print(f"[bold red]Error:[/bold red] {exc}")
        raise typer.Exit(code=1) from exc

    _print_summary(result)


@app.command()
def check() -> None:
    """Verifica que las dependencias externas (ffmpeg, ollama) esten disponibles."""
    import shutil

    import httpx

    settings = load_settings()
    table = Table(title="Diagnostico de dependencias")
    table.add_column("Componente")
    table.add_column("Estado")

    ffmpeg_ok = shutil.which(settings.ffmpeg_binary) is not None
    table.add_row("ffmpeg", "[green]OK[/green]" if ffmpeg_ok else "[red]NO ENCONTRADO[/red]")

    ffprobe_ok = shutil.which(settings.ffprobe_binary) is not None
    table.add_row("ffprobe", "[green]OK[/green]" if ffprobe_ok else "[red]NO ENCONTRADO[/red]")

    backend = settings.translation_backend.lower()
    if backend == "llama_server":
        try:
            r = httpx.get(f"{settings.llama_server_host}/v1/models", timeout=5.0)
            llm_ok = r.status_code == 200
        except Exception:
            llm_ok = False
        table.add_row(f"llama-server ({settings.llama_server_model})", "[green]OK[/green]" if llm_ok else "[red]NO DISPONIBLE[/red]")
    else:
        try:
            r = httpx.get(f"{settings.ollama_host}/api/tags", timeout=5.0)
            llm_ok = r.status_code == 200
        except Exception:
            llm_ok = False
        table.add_row("Ollama", "[green]OK[/green]" if llm_ok else "[red]NO DISPONIBLE[/red]")

    console.print(table)
    if not (ffmpeg_ok and ffprobe_ok and llm_ok):
        console.print("[yellow]Revisa el README.md para instrucciones de instalacion.[/yellow]")
        raise typer.Exit(code=1)


def _resolve_context_text(context: Optional[str]) -> Optional[str]:
    if context is None:
        return None
    maybe_path = Path(context)
    if maybe_path.exists() and maybe_path.is_file():
        return maybe_path.read_text(encoding="utf-8").strip()
    return context.strip()


def _load_glossary(glossary_path: Optional[Path]) -> dict[str, str]:
    if glossary_path is None:
        return {}
    if not glossary_path.exists():
        raise typer.BadParameter(f"No existe el archivo de glosario: {glossary_path}")
    data = json.loads(glossary_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise typer.BadParameter("El glosario debe ser un objeto JSON {termino: traduccion}.")
    return {str(k): str(v) for k, v in data.items()}


def _print_summary(result) -> None:
    console.rule("[bold green]Completado")
    table = Table(show_header=False)
    table.add_row("Duracion procesada", f"{result.duration_seconds / 60:.1f} min")
    table.add_row("Segmentos traducidos", str(len(result.segments)))
    table.add_row("Subtitulos EN", str(result.subtitles_source_path))
    table.add_row("Subtitulos ES", str(result.subtitles_target_path))
    if result.output_video:
        table.add_row("Video de salida", str(result.output_video))
    console.print(table)

    if result.speakers:
        speaker_table = Table(title="Hablantes detectados")
        speaker_table.add_column("ID")
        speaker_table.add_column("Genero estimado")
        speaker_table.add_column("Voz de referencia")
        for sp in result.speakers:
            speaker_table.add_row(
                sp.speaker_id,
                sp.gender or "desconocido",
                str(sp.reference_wav) if sp.reference_wav else "[red]sin muestra suficiente[/red]",
            )
        console.print(speaker_table)


if __name__ == "__main__":
    app()
