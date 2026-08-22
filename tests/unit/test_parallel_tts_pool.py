from __future__ import annotations

from pathlib import Path

from video_translator.application.synthesis_job import SynthesisJob
from video_translator.infrastructure.synthesis import parallel_tts_pool as mod


class FakeFuture:
    def __init__(self, value):
        self._value = value

    def result(self):
        return self._value


class FakeExecutor:
    """Sustituye a ProcessPoolExecutor en los tests: ejecuta las tareas de
    forma sincrona, en el mismo proceso, para poder verificar la logica de
    despacho de ParallelTTSPool sin pagar el costo (y la fragilidad en CI)
    de spawnear procesos reales."""

    def __init__(self, max_workers=None, initializer=None, initargs=()):
        self.max_workers = max_workers
        if initializer is not None:
            initializer(*initargs)

    def submit(self, fn, *args, **kwargs):
        return FakeFuture(fn(*args, **kwargs))

    def shutdown(self, wait=True):
        pass


class FakeSynth:
    """Se instancia UNA VEZ por "worker" (aqui, una vez, ya que FakeExecutor
    no crea procesos de verdad); simula un motor de TTS liviano."""

    def __init__(self):
        self.calls: list[str] = []

    def synthesize_segment(self, text, output_path, target_duration_seconds, speaker_reference_wav=None, language="es"):
        self.calls.append(text)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"wav")
        return output_path


def _job(tmp_path: Path, name: str, text: str, start: float) -> SynthesisJob:
    return SynthesisJob(
        output_path=tmp_path / name,
        text=text,
        target_duration_seconds=1.0,
        speaker_reference_wav=None,
        language="es",
        start_seconds=start,
        max_duration_seconds=1.0,
    )


def test_synthesize_batch_dispatches_every_job(tmp_path, monkeypatch):
    monkeypatch.setattr(mod, "ProcessPoolExecutor", FakeExecutor)
    # Reinicia el estado global del "worker" entre tests.
    mod._worker_synth = None

    pool = mod.ParallelTTSPool(synthesizer_factory=FakeSynth, num_workers=2)
    jobs = [_job(tmp_path, "a.wav", "hola", 0.0), _job(tmp_path, "b.wav", "mundo", 1.0)]

    pool.synthesize_batch(jobs)

    assert (tmp_path / "a.wav").exists()
    assert (tmp_path / "b.wav").exists()


def test_synthesize_batch_with_empty_list_is_a_noop(tmp_path, monkeypatch):
    monkeypatch.setattr(mod, "ProcessPoolExecutor", FakeExecutor)
    mod._worker_synth = None
    pool = mod.ParallelTTSPool(synthesizer_factory=FakeSynth, num_workers=2)
    pool.synthesize_batch([])  # no debe lanzar ni bloquear


def test_synthesize_segment_single_call_uses_executor_too(tmp_path, monkeypatch):
    monkeypatch.setattr(mod, "ProcessPoolExecutor", FakeExecutor)
    mod._worker_synth = None
    pool = mod.ParallelTTSPool(synthesizer_factory=FakeSynth, num_workers=1)

    result = pool.synthesize_segment(
        text="hola", output_path=tmp_path / "solo.wav", target_duration_seconds=1.0
    )
    assert result.exists()


def test_concatenate_segments_bypasses_the_executor(tmp_path, monkeypatch):
    """La mezcla final es una operacion barata (solo ffmpeg): no debe pasar
    por el pool de procesos, se ejecuta directo en el proceso principal."""
    monkeypatch.setattr(mod, "ProcessPoolExecutor", FakeExecutor)
    mod._worker_synth = None

    captured = {}

    def fake_concatenate(segment_audio_paths, total_duration, output_path, ffmpeg_binary="ffmpeg"):
        captured["called"] = True
        captured["args"] = (segment_audio_paths, total_duration, output_path)
        return output_path

    monkeypatch.setattr(mod.audio_mixing, "concatenate_segments", fake_concatenate)

    pool = mod.ParallelTTSPool(synthesizer_factory=FakeSynth, num_workers=2)
    out = tmp_path / "mix.wav"
    pool.concatenate_segments([(0.0, tmp_path / "a.wav", 1.0)], 5.0, out)

    assert captured["called"] is True
    assert captured["args"][2] == out
