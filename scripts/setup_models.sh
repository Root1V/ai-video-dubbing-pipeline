#!/usr/bin/env bash
# Descarga el modelo LLM open source por defecto en Ollama.
# Uso: ./scripts/setup_models.sh [nombre_modelo]
set -euo pipefail

MODEL="${1:-qwen2.5:14b-instruct}"

if ! command -v ollama >/dev/null 2>&1; then
  echo "Ollama no esta instalado. Instalalo desde https://ollama.com/download" >&2
  exit 1
fi

echo "Descargando modelo '${MODEL}' en Ollama..."
ollama pull "${MODEL}"

echo "Listo. Modelos disponibles:"
ollama list
