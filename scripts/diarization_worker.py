#!/usr/bin/env python3
"""Worker standalone: corre diarizacion (pyannote.audio) y estimacion de genero
por tono (librosa) en un entorno Python AISLADO del proyecto principal.

Por que existe este archivo separado:
    pyannote.audio depende (via pyannoteai-sdk, su cliente de telemetria) de
    opentelemetry-exporter-otlp, que exige protobuf>=5.0. IndexTTS-2.5 depende
    (via descript-audiotools) de protobuf<3.20. No existe ninguna version de
    protobuf que satisfaga ambas a la vez: es un conflicto real, no resoluble
    fijando otra combinacion de versiones. La unica forma de usar diarizacion
    y doblaje con IndexTTS-2.5 en el mismo pipeline es que vivan en procesos
    con entornos de paquetes distintos. Este script no importa nada del
    paquete video_translator (para poder vivir en un venv que ni siquiera lo
    tiene instalado) y se comunica con el proceso principal por stdout/JSON.

Uso:
    python diarization_worker.py diarize <audio.wav> [--model M] [--device D]
        [--min-speakers N] [--max-speakers N]
        -> imprime JSON: {"segments": [{"start":.., "end":.., "speaker_label":".."}, ...]}

    python diarization_worker.py gender <clip.wav>
        -> imprime JSON: {"gender": "male"|"female"|"unknown"}

Se invoca desde SubprocessDiarizer / SubprocessGenderClassifier usando el
interprete del venv aislado (ver scripts/setup_diarization_env.sh), nunca
directamente.
"""

from __future__ import annotations

import argparse
import json
import os
import sys


def _patch_torchaudio_audiometadata_compat(torchaudio_module) -> None:
    """Mismo parche de compatibilidad descrito en pyannote_diarizer.py del
    proyecto principal (torchaudio >= 2.9 elimino AudioMetaData / cambio
    list_audio_backends); se repite aqui porque este script es standalone.
    """
    if not hasattr(torchaudio_module, "AudioMetaData"):
        torchaudio_module.AudioMetaData = object  # type: ignore[attr-defined]
    if not hasattr(torchaudio_module, "list_audio_backends"):
        torchaudio_module.list_audio_backends = lambda: ["soundfile"]  # type: ignore[attr-defined]


def _patch_huggingface_hub_use_auth_token_compat(hub_module) -> None:
    """Mismo parche descrito en pyannote_diarizer.py del proyecto principal."""
    import inspect

    for name in ("hf_hub_download", "snapshot_download"):
        original = getattr(hub_module, name, None)
        if original is None:
            continue
        try:
            accepts_use_auth_token = "use_auth_token" in inspect.signature(original).parameters
        except (TypeError, ValueError):
            accepts_use_auth_token = False
        if accepts_use_auth_token:
            continue

        def _make_wrapper(fn):
            def wrapper(*args, **kwargs):
                if "use_auth_token" in kwargs:
                    kwargs.setdefault("token", kwargs.pop("use_auth_token"))
                return fn(*args, **kwargs)
            return wrapper

        setattr(hub_module, name, _make_wrapper(original))


def cmd_diarize(args: argparse.Namespace) -> None:
    import torch

    try:
        import torchaudio

        _patch_torchaudio_audiometadata_compat(torchaudio)
    except ImportError:
        pass

    import huggingface_hub

    _patch_huggingface_hub_use_auth_token_compat(huggingface_hub)

    from pyannote.audio import Pipeline

    hf_token = os.environ.get("HF_TOKEN") or os.environ.get("HUGGING_FACE_HUB_TOKEN")
    if not hf_token:
        print(json.dumps({"error": "HF_TOKEN no configurado en el entorno"}), file=sys.stderr)
        sys.exit(1)
    os.environ.setdefault("HF_TOKEN", hf_token)
    os.environ.setdefault("HUGGING_FACE_HUB_TOKEN", hf_token)

    try:
        pipeline = Pipeline.from_pretrained(args.model, use_auth_token=hf_token)
    except TypeError:
        pipeline = Pipeline.from_pretrained(args.model, token=hf_token)

    if args.device != "cpu":
        pipeline.to(torch.device(args.device))

    kwargs = {}
    if args.min_speakers is not None:
        kwargs["min_speakers"] = args.min_speakers
    if args.max_speakers is not None:
        kwargs["max_speakers"] = args.max_speakers

    output = pipeline(args.audio, **kwargs)
    annotation = getattr(output, "speaker_diarization", output)

    segments = []
    if hasattr(annotation, "itertracks"):
        for turn, _track, speaker_label in annotation.itertracks(yield_label=True):
            segments.append({"start": turn.start, "end": turn.end, "speaker_label": speaker_label})
    else:
        for turn, speaker_label in annotation:
            segments.append({"start": turn.start, "end": turn.end, "speaker_label": speaker_label})

    print(json.dumps({"segments": segments}))


def cmd_gender(args: argparse.Namespace) -> None:
    import librosa
    import numpy as np

    y, sr = librosa.load(args.wav_path, sr=16000, mono=True)
    f0, voiced_flag, _ = librosa.pyin(
        y, fmin=librosa.note_to_hz("C2"), fmax=librosa.note_to_hz("C6"), sr=sr
    )
    if f0 is None:
        print(json.dumps({"gender": "unknown"}))
        return

    voiced_f0 = f0[voiced_flag] if voiced_flag is not None else f0[~np.isnan(f0)]
    voiced_fraction = len(voiced_f0) / max(1, len(f0))
    if voiced_fraction < 0.15 or len(voiced_f0) == 0:
        print(json.dumps({"gender": "unknown"}))
        return

    median_f0 = float(np.nanmedian(voiced_f0))
    if median_f0 <= 0 or np.isnan(median_f0):
        print(json.dumps({"gender": "unknown"}))
        return

    gender = "female" if median_f0 >= 165.0 else "male"
    print(json.dumps({"gender": gender}))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    p_diarize = subparsers.add_parser("diarize")
    p_diarize.add_argument("audio")
    p_diarize.add_argument("--model", default="pyannote/speaker-diarization-community-1")
    p_diarize.add_argument("--device", default="cpu")
    p_diarize.add_argument("--min-speakers", type=int, default=None)
    p_diarize.add_argument("--max-speakers", type=int, default=None)
    p_diarize.set_defaults(func=cmd_diarize)

    p_gender = subparsers.add_parser("gender")
    p_gender.add_argument("wav_path")
    p_gender.set_defaults(func=cmd_gender)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
