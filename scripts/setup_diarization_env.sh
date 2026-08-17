#!/usr/bin/env bash
# Crea un entorno virtual AISLADO solo para diarizacion (pyannote.audio +
# librosa), separado del venv principal del proyecto.
#
# Por que un venv separado: pyannote.audio (via pyannoteai-sdk) exige
# protobuf>=5.0, e IndexTTS-2.5 (via descript-audiotools) exige protobuf<3.20.
# Es un conflicto real sin solucion de versiones posible; deben vivir en
# procesos con dependencias distintas. video-translator invoca este entorno
# via subprocess (ver infrastructure/diarization/subprocess_diarizer.py),
# nunca importa pyannote.audio directamente en el proceso principal.
#
# NOTA IMPORTANTE PARA macOS: pyannote.audio >= 4.0 usa torchcodec para leer
# audio, que en Mac tiene un problema de compatibilidad CONOCIDO Y SIN
# SOLUCION con el ffmpeg de Homebrew (ver github.com/meta-pytorch/torchcodec
# issue #570). No lo intentes arreglar con Homebrew: usa conda-forge.
#   brew install miniforge && conda init zsh   # reinicia la terminal despues
#   conda create -n ffmpeg-libs -c conda-forge "ffmpeg<8" -y
#   conda env list   # copia la ruta junto a "ffmpeg-libs"
# Configura esa ruta (+ /lib) como DIARIZATION_DYLD_LIBRARY_PATH en tu .env.
# NO uses "export DYLD_LIBRARY_PATH=..." en tu shell: rompe el ffmpeg de
# Homebrew que usa el resto del proyecto (afecta a cualquier proceso que lo
# herede). El proyecto la inyecta solo en el subprocess aislado de diarizacion.
#
# Uso: ./scripts/setup_diarization_env.sh
set -euo pipefail

VENV_DIR=".venv-diarization"

echo "Creando entorno aislado de diarizacion en ${VENV_DIR}..."
uv venv "${VENV_DIR}" --python 3.11

echo "Instalando pyannote.audio + librosa (aislados del venv principal)..."
uv pip install --python "${VENV_DIR}/bin/python" "pyannote.audio>=4.0.0" "librosa>=0.10.0"

echo ""
echo "Listo. Configura en tu .env:"
echo "  DIARIZATION_PYTHON_BIN=${VENV_DIR}/bin/python"
echo ""
echo "No instales pyannote.audio en el venv principal del proyecto (.venv):"
echo "chocara con las dependencias de IndexTTS-2.5 si tambien usas doblaje."
echo ""
echo "macOS: si al correr diarizacion ves un error de 'libtorchcodec' /"
echo "'libavutil.NN.dylib not loaded', es el problema conocido de torchcodec"
echo "con el ffmpeg de Homebrew. Usa conda-forge y configura"
echo "DIARIZATION_DYLD_LIBRARY_PATH en tu .env (NO 'export DYLD_LIBRARY_PATH'"
echo "en la shell: rompe el ffmpeg de Homebrew del resto del proyecto)."
echo "Ver seccion correspondiente en el README."
