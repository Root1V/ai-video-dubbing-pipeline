#!/usr/bin/env bash
# Instala IndexTTS-2.5, el motor de sintesis de voz recomendado para doblaje:
#   1. Clona el repo oficial (no esta en PyPI).
#   2. Instala TODO via "uv sync --extra dubbing-indextts", NO con "pip install -e"
#      suelto: pyproject.toml declara "indextts" como dependencia de ruta local
#      (ver [tool.uv.sources]). Si se instala con pip por fuera de uv, el
#      proximo "uv sync" que corras (por cualquier otro motivo) lo desinstalara,
#      porque uv no lo reconoce como parte del proyecto.
#   3. Descarga los checkpoints del modelo desde Hugging Face (~varios GB).
#
# Uso: ./scripts/setup_index_tts2.sh
set -euo pipefail

TARGET_DIR="third_party/index-tts"
REPO_URL="https://github.com/index-tts/index-tts.git"

if [ ! -d "${TARGET_DIR}" ]; then
  echo "Clonando IndexTTS-2.5 en ${TARGET_DIR}..."
  mkdir -p third_party
  git clone --depth 1 "${REPO_URL}" "${TARGET_DIR}"
else
  echo "${TARGET_DIR} ya existe, omito clonado."
fi

echo "Instalando IndexTTS-2.5 via 'uv sync' (queda registrado en el lockfile)..."
uv sync --extra dubbing-indextts

echo "Descargando checkpoints de IndexTeam/IndexTTS-2.5 (esto puede tardar, son varios GB)..."
uv run hf download IndexTeam/IndexTTS-2.5 --local-dir="${TARGET_DIR}/checkpoints"

echo ""
echo "Listo. Configura en tu .env:"
echo "  TTS_BACKEND=index_tts2"
echo "  INDEX_TTS2_MODEL_DIR=${TARGET_DIR}/checkpoints"
echo "  INDEX_TTS2_CFG_PATH=${TARGET_DIR}/checkpoints/config.yaml"
echo ""
echo "IMPORTANTE: de ahora en adelante, corre 'uv sync --extra dubbing-indextts'"
echo "(no 'pip install' suelto) si necesitas reinstalar o actualizar dependencias,"
echo "para que IndexTTS-2.5 no se pierda en futuros 'uv sync'."
