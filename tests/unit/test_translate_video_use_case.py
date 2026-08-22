"""Tests del caso de uso TranslateVideoUseCase usando fakes en memoria.

Al depender la clase solo de Protocols, no se necesita ffmpeg, whisper ni un
LLM real para probar la logica de orquestacion: se inyectan implementaciones
falsas y deterministas.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from video_translator.application.use_cases.translate_video import TranslateVideoUseCase
from video_translator.domain.exceptions import InvalidVideoFileError, VideoTranslatorError
from video_translator.domain.models import (
    OutputMode,
    TranscriptSegment,
    TranslateVideoRequest,
    TranslationContext,
)


class FakeMediaProcessor:
    def __init__(self):
        self.burned = False
        self.soft = False

    def get_duration_seconds(self, media_path: Path) -> float:
        return 5.0

    def extract_audio(self, video_path: Path, output_wav: Path) -> Path:
        output_wav.parent.mkdir(parents=True, exist_ok=True)
        output_wav.write_bytes(b"fake-wav")
        return output_wav

    def extract_audio_clip(self, audio_path: Path, start: float, end: float, output_path: Path) -> Path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"fake-clip")
        return output_path

    def burn_subtitles(self, video_path, srt_path, output_path):
        self.burned = True
        output_path.write_bytes(b"video")
        return output_path

    def attach_soft_subtitles(self, video_path, srt_path, output_path, lang_code="spa"):
        self.soft = True
        output_path.write_bytes(b"video")
        return output_path

    def replace_audio_track(self, video_path, new_audio_path, output_path, keep_original_as_secondary=True):
        output_path.write_bytes(b"video")
        return output_path


class FakeTranscriber:
    def transcribe(self, audio_path: Path, language_hint=None):
        return [
            TranscriptSegment(id=0, start=0.0, end=2.0, text="Hello there."),
            TranscriptSegment(id=1, start=2.0, end=5.0, text="This is a test video."),
        ]


class FakeTranslator:
    def translate_batch(self, segments, context, rolling_history):
        return [f"[ES] {s.text}" for s in segments]


class SpeakerAwareFakeTranslator:
    """Traductor falso que expone en la traduccion la etiqueta de hablante/genero
    que recibio, para poder verificar en el test que el contexto llego completo."""

    def translate_batch(self, segments, context, rolling_history):
        out = []
        for s in segments:
            gender = context.speaker_genders.get(s.speaker_id, "?") if s.speaker_id else "?"
            out.append(f"[ES|{s.speaker_id}|{gender}] {s.text}")
        return out


class MismatchedTranslator:
    def translate_batch(self, segments, context, rolling_history):
        return ["solo una linea"]


class FakeSubtitleWriter:
    def __init__(self):
        self.writes = []

    def write(self, segments, output_path, use_translation):
        self.writes.append((output_path, use_translation))
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text("srt content", encoding="utf-8")
        return output_path


class FakeDiarizer:
    def diarize(self, audio_path, min_speakers=None, max_speakers=None):
        from video_translator.domain.models import DiarizationSegment

        return [
            # Turnos cortos que solapan con los segmentos de FakeTranscriber (0-2s, 2-5s),
            # usados para asignar speaker_id a cada linea de transcripcion.
            DiarizationSegment(start=0.0, end=2.0, speaker_label="SPEAKER_00"),
            DiarizationSegment(start=2.0, end=5.0, speaker_label="SPEAKER_01"),
            # Turnos mas largos (fuera del rango transcrito) que superan el umbral
            # minimo de duracion (6s) para servir como clip de referencia de voz.
            DiarizationSegment(start=10.0, end=20.0, speaker_label="SPEAKER_00"),
            DiarizationSegment(start=25.0, end=35.0, speaker_label="SPEAKER_01"),
        ]


class FakeGenderClassifier:
    def classify(self, wav_path: Path) -> str:
        return "male" if "SPEAKER_00" in wav_path.stem else "female"


@pytest.fixture()
def video_file(tmp_path: Path) -> Path:
    p = tmp_path / "input.mp4"
    p.write_bytes(b"fake-mp4")
    return p


def _make_use_case(translator=None, resume: bool = False):
    return TranslateVideoUseCase(
        media_processor=FakeMediaProcessor(),
        transcriber=FakeTranscriber(),
        translator=translator or FakeTranslator(),
        subtitle_writer=FakeSubtitleWriter(),
        resume=resume,
    )


def test_execute_generates_subtitles_and_result(tmp_path: Path, video_file: Path):
    use_case = _make_use_case()
    request = TranslateVideoRequest(
        input_video=video_file,
        output_dir=tmp_path / "out",
        context=TranslationContext(prompt="Video tutorial de programacion."),
        output_mode=OutputMode.SUBTITLES_ONLY,
    )

    result = use_case.execute(request)

    assert result.output_video is None
    assert result.subtitles_source_path.exists()
    assert result.subtitles_target_path.exists()
    assert len(result.segments) == 2
    assert result.segments[0].translated_text == "[ES] Hello there."


def test_execute_soft_subtitles_mode_produces_video(tmp_path: Path, video_file: Path):
    use_case = _make_use_case()
    request = TranslateVideoRequest(
        input_video=video_file,
        output_dir=tmp_path / "out",
        context=TranslationContext(),
        output_mode=OutputMode.SOFT_SUBTITLES,
    )

    result = use_case.execute(request)

    assert result.output_video is not None
    assert result.output_video.exists()


def test_output_video_name_derives_from_input_stem(video_file: Path, tmp_path: Path):
    """El video de salida ya no se llama siempre 'video.*.mp4': hereda el
    nombre del input con sufijo de modo, para que dos traducciones distintas
    en la misma carpeta no se pisen."""
    stem = video_file.stem
    for mode, expected_suffix in [
        (OutputMode.SOFT_SUBTITLES, "soft_subs"),
        (OutputMode.BURN_SUBTITLES, "dubbed_subs"),
        (OutputMode.DUBBED, "dubbed"),
    ]:
        request = TranslateVideoRequest(
            input_video=video_file,
            output_dir=tmp_path / "out",
            context=TranslationContext(),
            output_mode=mode,
        )
        path = TranslateVideoUseCase._expected_render_output(
            _make_use_case(), request
        )
        assert path is not None
        assert path.name == f"{stem}.{expected_suffix}.mp4"


def test_expected_render_output_is_none_for_subtitles_only(tmp_path: Path):
    request = TranslateVideoRequest(
        input_video=tmp_path / "x.mp4",
        output_dir=tmp_path / "out",
        context=TranslationContext(),
        output_mode=OutputMode.SUBTITLES_ONLY,
    )
    assert _make_use_case()._expected_render_output(request) is None


def test_resume_keeps_real_durations_in_timings_report(tmp_path: Path, video_file: Path):
    """Al reanudar con --resume, las etapas saltadas NO deben aparecer con 0.0s:
    el reporte final debe conservar la duracion real de la primera corrida
    (status="resumed") y un campo order legible."""
    import json as _json

    output_dir = tmp_path / "out"
    request = TranslateVideoRequest(
        input_video=video_file,
        output_dir=output_dir,
        context=TranslationContext(),
        output_mode=OutputMode.SOFT_SUBTITLES,
    )

    # Corrida 1 (sin --resume): deja checkpoint + pipeline_timings.json.
    _make_use_case().execute(request)
    report_path = output_dir / "pipeline_timings.json"
    first_run = _json.loads(report_path.read_text(encoding="utf-8"))
    real_names = [s["name"] for s in first_run["stages"]]
    assert "audio_extraction" in real_names

    # Simular que la corrida 1 costo horas: inflar las duraciones en disco.
    inflated = {
        "audio_extraction": 4.2,
        "transcription": 1802.5,
        "diarization": 1950.7,
        "translation": 95.2,
        "subtitles_writing": 0.1,
        "rendering_soft_subtitles": 33.0,
    }
    for stage in first_run["stages"]:
        stage["seconds"] = inflated[stage["name"]]
    report_path.write_text(_json.dumps(first_run), encoding="utf-8")

    # Corrida 2 con --resume: todo se salta por checkpoint.
    result = _make_use_case(resume=True).execute(request)
    resumed_stages = result.timings["stages"]

    assert result.timings["resumed_run"] is True
    assert [s["order"] for s in resumed_stages] == list(range(1, len(resumed_stages) + 1))
    by_name = {s["name"]: s for s in resumed_stages}
    # Solo se esperan las etapas que la corrida 1 realmente ejecuto (con
    # diarize=False no existe etapa de diarizacion que reanudar).
    expected_names = [s["name"] for s in first_run["stages"]]
    assert [s["name"] for s in resumed_stages] == expected_names
    for name in expected_names:
        assert by_name[name]["status"] == "resumed"
        # La duracion REAL de la corrida anterior, no 0.0s.
        assert by_name[name]["seconds"] == inflated[name]

    on_disk = _json.loads(report_path.read_text(encoding="utf-8"))
    assert on_disk["completed"] is True
    assert on_disk["resumed_run"] is True


def test_timings_report_is_written_incrementally(tmp_path: Path, video_file: Path):
    """El reporte JSON debe existir y actualizarse DURANTE la ejecucion, no solo al final."""
    import json as _json

    output_dir = tmp_path / "out"
    request = TranslateVideoRequest(
        input_video=video_file,
        output_dir=output_dir,
        context=TranslationContext(),
        output_mode=OutputMode.SUBTITLES_ONLY,
    )
    use_case = _make_use_case()

    original_extract = use_case._media.extract_audio

    def spy_extract(video_path, output_wav):
        snapshot = output_dir / "pipeline_timings.json"
        assert snapshot.exists(), "el reporte debe existir ya durante la primera etapa"
        data = _json.loads(snapshot.read_text(encoding="utf-8"))
        assert data["current_stage"]["name"] == "audio_extraction"
        return original_extract(video_path, output_wav)

    use_case._media.extract_audio = spy_extract
    use_case.execute(request)

    final = _json.loads((output_dir / "pipeline_timings.json").read_text(encoding="utf-8"))
    assert final["completed"] is True
    assert "current_stage" not in final


def test_rejects_missing_file(tmp_path: Path):
    use_case = _make_use_case()
    request = TranslateVideoRequest(
        input_video=tmp_path / "no_existe.mp4",
        output_dir=tmp_path / "out",
        context=TranslationContext(),
    )
    with pytest.raises(InvalidVideoFileError):
        use_case.execute(request)


def test_rejects_unsupported_extension(tmp_path: Path):
    bad_file = tmp_path / "audio.mp3"
    bad_file.write_bytes(b"x")
    use_case = _make_use_case()
    request = TranslateVideoRequest(
        input_video=bad_file, output_dir=tmp_path / "out", context=TranslationContext()
    )
    with pytest.raises(InvalidVideoFileError):
        use_case.execute(request)


def test_raises_on_translation_misalignment(tmp_path: Path, video_file: Path):
    use_case = _make_use_case(translator=MismatchedTranslator())
    request = TranslateVideoRequest(
        input_video=video_file,
        output_dir=tmp_path / "out",
        context=TranslationContext(),
        output_mode=OutputMode.SUBTITLES_ONLY,
    )
    with pytest.raises(VideoTranslatorError):
        use_case.execute(request)


def test_diarization_assigns_speaker_and_gender_to_each_segment(tmp_path: Path, video_file: Path):
    """Con --diarize, cada segmento debe llevar su propio speaker_id, y el
    traductor debe recibir el genero estimado de cada hablante via el contexto."""
    use_case = TranslateVideoUseCase(
        media_processor=FakeMediaProcessor(),
        transcriber=FakeTranscriber(),  # seg 0: 0-2s, seg 1: 2-5s
        translator=SpeakerAwareFakeTranslator(),
        subtitle_writer=FakeSubtitleWriter(),
        speaker_diarizer=FakeDiarizer(),  # SPEAKER_00: 0-2s, SPEAKER_01: 2-5s
        gender_classifier=FakeGenderClassifier(),
    )
    request = TranslateVideoRequest(
        input_video=video_file,
        output_dir=tmp_path / "out",
        context=TranslationContext(),
        output_mode=OutputMode.SUBTITLES_ONLY,
        diarize=True,
    )

    result = use_case.execute(request)

    assert result.segments[0].speaker_id == "SPEAKER_00"
    assert result.segments[1].speaker_id == "SPEAKER_01"
    assert "SPEAKER_00|male" in result.segments[0].translated_text
    assert "SPEAKER_01|female" in result.segments[1].translated_text

    assert {p.speaker_id for p in result.speakers} == {"SPEAKER_00", "SPEAKER_01"}
    genders = {p.speaker_id: p.gender for p in result.speakers}
    assert genders["SPEAKER_00"] == "male"
    assert genders["SPEAKER_01"] == "female"


def test_diarization_timing_reflects_its_own_completion_not_transcriptions(
    tmp_path: Path, video_file: Path
):
    """Regresion: transcripcion y diarizacion corren en dos hilos, y el codigo
    llama transcript_future.result() ANTES que diarization_future.result().
    Si la duracion de diarizacion se midiera recien en ese segundo .result()
    (bloqueado esperando a que el hilo principal llegue ahi), una diarizacion
    mucho mas rapida que la transcripcion aparecería con la MISMA duracion
    que esta -- exactamente lo que se veia en una corrida real con
    diarizacion en GPU (8.5s de inferencia real, 130s reportados)."""
    import time as _time

    class SlowFakeTranscriber:
        def transcribe(self, audio_path: Path, language_hint=None):
            _time.sleep(0.15)
            return [TranscriptSegment(id=0, start=0.0, end=2.0, text="Hello there.")]

    class FastFakeDiarizer:
        def diarize(self, audio_path, min_speakers=None, max_speakers=None):
            from video_translator.domain.models import DiarizationSegment

            return [DiarizationSegment(start=0.0, end=2.0, speaker_label="SPEAKER_00")]

    use_case = TranslateVideoUseCase(
        media_processor=FakeMediaProcessor(),
        transcriber=SlowFakeTranscriber(),
        translator=FakeTranslator(),
        subtitle_writer=FakeSubtitleWriter(),
        speaker_diarizer=FastFakeDiarizer(),
    )
    request = TranslateVideoRequest(
        input_video=video_file,
        output_dir=tmp_path / "out",
        context=TranslationContext(),
        output_mode=OutputMode.SUBTITLES_ONLY,
        diarize=True,
    )

    result = use_case.execute(request)
    by_name = {s["name"]: s for s in result.timings["stages"]}

    # La diarizacion "instantanea" no debe heredar el tiempo de espera de la
    # transcripcion lenta: debe quedar muy por debajo, no aproximadamente igual.
    assert by_name["diarization"]["seconds"] < by_name["transcription"]["seconds"] / 2


def test_resume_with_diarize_skips_speaker_profile_building(tmp_path: Path, video_file: Path):
    """Regresion: al reanudar con --diarize, la construccion de perfiles de
    hablantes debe SALTARSE (status resumed con duracion real heredada), no
    reconstruirse; y la diarizacion tampoco debe reportarse si no hubo."""
    import json as _json

    output_dir = tmp_path / "out"
    request = TranslateVideoRequest(
        input_video=video_file,
        output_dir=output_dir,
        context=TranslationContext(),
        output_mode=OutputMode.SOFT_SUBTITLES,
        diarize=True,
    )
    common: dict = {
        "media_processor": FakeMediaProcessor(),
        "transcriber": FakeTranscriber(),
        "translator": SpeakerAwareFakeTranslator(),
        "subtitle_writer": FakeSubtitleWriter(),
        "speaker_diarizer": FakeDiarizer(),
        "gender_classifier": FakeGenderClassifier(),
    }

    TranslateVideoUseCase(**common).execute(request)

    report_path = output_dir / "pipeline_timings.json"
    first = _json.loads(report_path.read_text(encoding="utf-8"))
    for stage in first["stages"]:
        stage["seconds"] = {
            "audio_extraction": 4.2,
            "transcription": 1802.5,
            "diarization": 1950.7,
            "speaker_profile_building": 8.3,
            "translation": 95.2,
            "subtitles_writing": 0.1,
            "rendering_soft_subtitles": 33.0,
        }[stage["name"]]
    report_path.write_text(_json.dumps(first), encoding="utf-8")

    result = TranslateVideoUseCase(**common, resume=True).execute(request)
    by_name = {s["name"]: s for s in result.timings["stages"]}

    assert by_name["speaker_profile_building"]["status"] == "resumed"
    assert by_name["speaker_profile_building"]["seconds"] == 8.3
    assert by_name["speaker_profile_building"]["num_speakers"] == 2
    # Los perfiles restaurados conservan genero y referencia.
    speakers = by_name["speaker_profile_building"]["speakers"]
    assert {s["id"]: (s["gender"], s["reference"]) for s in speakers} == {
        "SPEAKER_00": ("male", True),
        "SPEAKER_01": ("female", True),
    }
    assert by_name["diarization"]["seconds"] == 1950.7
    assert by_name["transcription"]["status"] == "resumed"
    # Transcripcion y diarizacion corrieron en paralelo en la corrida
    # original: el reporte reanudado debe seguir marcandolas como
    # concurrentes (una sola vez, sin duplicar la entrada y doblar
    # parallel_time_saved_seconds), o el tiempo total reportado
    # (sum_of_stage_seconds, overhead_seconds) las contaria como secuenciales.
    assert result.timings["concurrent_stage_groups"] == [["transcription", "diarization"]]
    assert result.timings["parallel_time_saved_seconds"] == 1802.5


def test_dubbed_mode_uses_per_speaker_reference_wav(tmp_path: Path, video_file: Path):
    """En modo doblaje con diarizacion, cada segmento debe sintetizarse con la
    voz de referencia de SU hablante, no una unica voz para todo el video."""

    class RecordingSynthesizer:
        def __init__(self):
            self.calls: list[tuple[str, Path | None]] = []
            self.concat_args: list[tuple[float, Path, float]] = []

        def synthesize_segment(self, text, output_path, target_duration_seconds, speaker_reference_wav=None, language="es"):
            self.calls.append((text, speaker_reference_wav))
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(b"wav")
            return output_path

        def concatenate_segments(self, segment_audio_paths, total_duration, output_path):
            self.concat_args = segment_audio_paths
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(b"wav")
            return output_path

    synthesizer = RecordingSynthesizer()
    use_case = TranslateVideoUseCase(
        media_processor=FakeMediaProcessor(),
        transcriber=FakeTranscriber(),
        translator=SpeakerAwareFakeTranslator(),
        subtitle_writer=FakeSubtitleWriter(),
        speech_synthesizer=synthesizer,
        speaker_diarizer=FakeDiarizer(),
        gender_classifier=FakeGenderClassifier(),
    )
    request = TranslateVideoRequest(
        input_video=video_file,
        output_dir=tmp_path / "out",
        context=TranslationContext(),
        output_mode=OutputMode.DUBBED,
        diarize=True,
    )

    use_case.execute(request)

    assert len(synthesizer.calls) == 2
    _, wav_speaker_0 = synthesizer.calls[0]
    _, wav_speaker_1 = synthesizer.calls[1]
    assert wav_speaker_0 is not None and "SPEAKER_00" in wav_speaker_0.stem
    assert wav_speaker_1 is not None and "SPEAKER_01" in wav_speaker_1.stem
    assert wav_speaker_0 != wav_speaker_1  # cada hablante usa su propia referencia


def test_dubbed_mode_caps_each_segment_to_gap_until_next_start(tmp_path: Path, video_file: Path):
    """El limite de duracion pasado al mezclador debe ser el hueco real hasta
    el siguiente segmento (no la duracion original del segmento), para que el
    mezclador pueda recortar audio que quedo mas largo que su espacio y asi
    nunca se escuchen dos voces superpuestas."""

    class RecordingSynthesizer:
        def __init__(self):
            self.concat_args: list[tuple[float, Path, float]] = []

        def synthesize_segment(self, text, output_path, target_duration_seconds, speaker_reference_wav=None, language="es"):
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(b"wav")
            return output_path

        def concatenate_segments(self, segment_audio_paths, total_duration, output_path):
            self.concat_args = segment_audio_paths
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(b"wav")
            return output_path

    synthesizer = RecordingSynthesizer()
    # FakeTranscriber: seg0 start=0 end=2 ("Hello there."), seg1 start=2 end=5.
    # FakeMediaProcessor.get_duration_seconds() = 5.0 (duracion total del video).
    use_case = TranslateVideoUseCase(
        media_processor=FakeMediaProcessor(),
        transcriber=FakeTranscriber(),
        translator=FakeTranslator(),
        subtitle_writer=FakeSubtitleWriter(),
        speech_synthesizer=synthesizer,
    )
    request = TranslateVideoRequest(
        input_video=video_file,
        output_dir=tmp_path / "out",
        context=TranslationContext(),
        output_mode=OutputMode.DUBBED,
    )

    use_case.execute(request)

    assert len(synthesizer.concat_args) == 2
    start0, _, max_dur0 = synthesizer.concat_args[0]
    start1, _, max_dur1 = synthesizer.concat_args[1]

    assert start0 == 0.0
    assert max_dur0 == 2.0  # hueco hasta que arranca el seg1 (start=2), no seg0.duration
    assert start1 == 2.0
    assert max_dur1 == 3.0  # hueco hasta el final del video (5.0 - 2.0), es el ultimo segmento
