# Imagen con soporte GPU (CUDA) para faster-whisper y Coqui TTS.
# Para CPU-only, cambia la imagen base por python:3.11-slim y usa
# WHISPER_DEVICE=cpu / WHISPER_COMPUTE_TYPE=int8 en el .env.
FROM nvidia/cuda:12.1.1-cudnn8-runtime-ubuntu22.04

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    python3.11 python3-pip python3.11-venv \
    ffmpeg \
    git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml requirements.txt ./
RUN python3.11 -m pip install --upgrade pip \
    && python3.11 -m pip install -r requirements.txt

COPY src/ ./src/
COPY tests/ ./tests/
RUN python3.11 -m pip install -e .

ENTRYPOINT ["video-translator"]
CMD ["--help"]
