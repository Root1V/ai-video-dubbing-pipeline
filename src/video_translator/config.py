"""Configuracion de la aplicacion, cargada desde variables de entorno / archivo .env.

Centralizar la configuracion tipada evita "magic strings" desperdigados por el
codigo y permite validar valores al arrancar (fail-fast) en vez de fallar a
mitad de un procesamiento de una hora de video.
"""

from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Whisper / transcripcion
    whisper_model_size: str = Field(default="large-v3")
    whisper_device: str = Field(default="cuda")
    whisper_compute_type: str = Field(default="float16")
    whisper_beam_size: int = Field(default=5)
    whisper_vad_filter: bool = Field(default=True)

    # Ollama / traduccion
    translation_backend: str = Field(default="ollama")  # "ollama" | "llama_server"
    ollama_host: str = Field(default="http://localhost:11434")
    ollama_model: str = Field(default="qwen2.5:14b-instruct")
    ollama_temperature: float = Field(default=0.2)
    ollama_timeout_seconds: float = Field(default=120.0)
    translation_batch_max_chars: int = Field(default=1800)
    translation_context_window_segments: int = Field(default=6)

    # llama-server (llama.cpp) / cualquier backend compatible con la API de OpenAI
    llama_server_host: str = Field(default="http://localhost:8080")
    llama_server_model: str = Field(default="gpt-oss-20b-mxfp4")
    llama_server_max_tokens: int = Field(default=4096)
    llama_server_api_key: str | None = Field(default=None)

    # TTS / doblaje
    tts_backend: str = Field(default="index_tts2")  # "index_tts2" (recomendado) | "coqui_xtts"

    # IndexTTS-2.5 (recomendado): control nativo de duracion, ideal para doblaje
    index_tts2_model_dir: str = Field(default="third_party/index-tts/checkpoints")
    index_tts2_cfg_path: str = Field(default="third_party/index-tts/checkpoints/config.yaml")
    index_tts2_use_bf16: bool = Field(default=True)

    # Coqui TTS / XTTS v2 (alternativa mas liviana de instalar, requiere Python < 3.12)
    tts_model_name: str = Field(default="tts_models/multilingual/multi-dataset/xtts_v2")
    tts_device: str = Field(default="cuda")

    # Diarizacion de hablantes (opcional): quien habla, y clonacion de voz por hablante.
    # Corre en un venv AISLADO (ver scripts/setup_diarization_env.sh) via
    # subprocess, no como dependencia directa de este proyecto: pyannote.audio
    # y IndexTTS-2.5 tienen un conflicto real de version de protobuf que no
    # se puede resolver dentro de un unico entorno.
    diarization_python_bin: str = Field(default=".venv-diarization/bin/python")
    diarization_worker_script: str = Field(default="scripts/diarization_worker.py")
    diarization_model: str = Field(default="pyannote/speaker-diarization-community-1")
    diarization_device: str = Field(default="cpu")
    hf_token: str | None = Field(default=None)
    gender_detection_enabled: bool = Field(default=True)
    # macOS: carpeta "lib" de un entorno conda-forge con ffmpeg < 8 (ver README,
    # seccion de torchcodec/Homebrew). Se inyecta SOLO en el subprocess de
    # diarizacion, nunca en el proceso principal, para no romper el ffmpeg de
    # Homebrew que usa el resto del proyecto (DYLD_LIBRARY_PATH afecta a
    # cualquier binario que lo herede, por eso no se exporta globalmente).
    diarization_dyld_library_path: str | None = Field(default=None)

    # Medios
    ffmpeg_binary: str = Field(default="ffmpeg")
    ffprobe_binary: str = Field(default="ffprobe")
    audio_sample_rate: int = Field(default=16000)

    # General
    output_dir: Path = Field(default=Path("./output"))
    workdir: Path = Field(default=Path("./.work"))
    log_level: str = Field(default="INFO")
    log_json: bool = Field(default=False)


def load_settings() -> Settings:
    return Settings()
