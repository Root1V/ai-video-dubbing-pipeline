# AI Video Dubbing Pipeline — EN → ES Video Dubbing with 100% Open Source AI

[![CI](https://github.com/Root1V/ai-video-dubbing-pipeline/actions/workflows/ci.yml/badge.svg)](https://github.com/Root1V/ai-video-dubbing-pipeline/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue)](pyproject.toml)

A production-grade pipeline that turns an **hour-plus** English video with
**multiple speakers** into a dubbed Spanish video — with each person's voice
cloned individually, respecting their gender and timbre, and with
context-aware translation (domain, tone, glossary). Runs 100% locally on
open source models: no paid APIs, no data leaving your machine.

**End-to-end pipeline:**
1. **Transcribes** the original audio (Whisper via `faster-whisper`, streaming/VAD for long audio).
2. **Detects who's speaking and when** (diarization with `pyannote.audio`) and estimates each speaker's gender.
3. **Translates with context** using a local LLM (Ollama or `llama.cpp`), not a generic NMT translator: you can specify domain, tone, a glossary of mandatory terms, and it respects per-speaker gender agreement.
4. **Clones each speaker's voice individually** (IndexTTS-2.5, zero-shot voice cloning with native duration control) and syncs every line to its real time slot, adaptively compressing audio per-segment instead of cutting content off.
5. **Renders the final video** with dubbed audio (or subtitles, if preferred), via `ffmpeg`.

Built with **hexagonal architecture** (domain/application/infrastructure
decoupled via `Protocol` + dependency injection), unit tests with test
doubles, CI on GitHub Actions, and Python environment isolation for the case
where two AI stacks have unresolvable dependency conflicts (diarization vs.
dubbing) — a real-world AI systems engineering problem, not just a
single-file script.

## AI Stack

| Stage | Technology | Why |
|---|---|---|
| Transcription (STT) | [faster-whisper](https://github.com/SYSTRAN/faster-whisper) (Whisper large-v3 on CTranslate2) | Fast, accurate, built-in VAD for long audio without manual chunking |
| Diarization (optional) | [pyannote.audio](https://github.com/pyannote/pyannote-audio) (`speaker-diarization-community-1`) | Open source standard for detecting who's speaking and when, the basis for per-speaker voice cloning |
| Translation | Open source LLM via [Ollama](https://ollama.com) or [`llama-server`](https://github.com/ggerganov/llama.cpp) (Qwen2.5, Llama 3.1, gpt-oss, Mistral...) | Unlike a classic NMT model (NLLB/M2M100), an instruction-tuned LLM lets you **guide the translation with a natural-language context prompt**, and respect speaker/gender agreement |
| Dubbing (Spanish audio) | [IndexTTS-2.5](https://github.com/index-tts/index-tts) (recommended) or XTTS v2 (Coqui) | Zero-shot per-speaker voice cloning + **native duration control**, purpose-built for audiovisual sync in dubbing |
| Media | ffmpeg | Audio extraction, subtitles, remuxing, track mixing |

Everything runs locally; no paid external API is ever called.

## Architecture

Hexagonal architecture (Clean Architecture) with dependency inversion:

```
src/video_translator/
├── domain/            # Pure entities and exceptions (no external dependencies)
│   ├── models.py
│   └── exceptions.py
├── application/        # Use cases + ports (interfaces/Protocols)
│   ├── interfaces.py
│   └── use_cases/translate_video.py     <- pipeline orchestrator
├── infrastructure/     # Concrete adapters (implement the ports)
│   ├── media/ffmpeg_processor.py
│   ├── transcription/faster_whisper_transcriber.py
│   ├── translation/ollama_translator.py  <- context prompt applied here
│   ├── synthesis/coqui_tts_synthesizer.py
│   └── subtitles/srt_writer.py
├── config.py           # Typed configuration (pydantic-settings)
├── container.py        # Composition root (dependency injection)
└── cli.py               # Command-line interface (Typer)
```

**Why this structure:** the business logic (`application/`) never imports
anything from `infrastructure/`, only interfaces (`Protocol`). This allows:
- Swapping the LLM, STT engine, or TTS engine without touching the pipeline.
- Testing `TranslateVideoUseCase` with in-memory test doubles (see `tests/unit`), no ffmpeg/GPU required.
- Scaling the team: each adapter is developed and tested in isolation.

## Handling long videos (>1h)

- `faster-whisper` uses VAD (voice activity detection) internally, streaming the audio without manually chunking it or loading it fully into memory.
- Translation happens in **batches** (`utils/text_batching.py`), bounded by character count, to stay within the LLM's context window. A **rolling history** of recent translations is kept across batches to preserve terminology and style consistency throughout the whole video.
- Every batch is validated 1:1 (same number of input/output lines) and automatically retried (exponential backoff) on network errors or LLM misalignment.

## Dubbing: generate a new video with translated audio (`--mode dubbed`)

This mode completely replaces the video's audio with a Spanish voice cloned
from the original speaker, synced in time — not just subtitles, a brand new
`.mp4` you can play as-is, with the same video and Spanish audio.

**Recommended engine: IndexTTS-2.5** ([index-tts/index-tts](https://github.com/index-tts/index-tts),
Bilibili/IndexTeam, open code and weights). It's the current state of the art
in open source TTS for this exact use case because:
- **Zero-shot** voice cloning: clones a speaker's timbre from just 6-15s of reference audio.
- Native Spanish support (plus English, Chinese, Japanese, Arabic).
- **Explicit duration control** (`duration_factor`): unlike XTTS v2, which generates at a free
  pace and depends on stretching/compressing the audio afterward with ffmpeg, IndexTTS-2.5 can
  generate voice aiming directly at the original segment's target duration — better
  lip/timing sync and less prosody distortion.
- Emotion control, useful so the dub doesn't sound flat in narrative content.

### Installing IndexTTS-2.5

Not on PyPI; it's resolved as a local path dependency pointing at the cloned
repo (`[tool.uv.sources]` in `pyproject.toml`). The script automates everything:

```bash
./scripts/setup_index_tts2.sh
```

This clones the repo into `third_party/index-tts`, runs `uv sync --extra dubbing-indextts`
(which installs it AND registers it in the `uv` lockfile), and downloads the checkpoints.

> **Important:** from now on always use `uv sync --extra <whatever>` to
> install or update dependencies, never a bare `pip install` / `uv pip install`.
> `uv sync` makes the environment match *exactly* what its lockfile knows —
> any package installed outside that mechanism (including `indextts`, if you
> installed it with a plain `pip install -e` instead of this script)
> **disappears the next time you run `uv sync`** for any other reason,
> because `uv` treats it as "foreign" to the project.

### Usage

```bash
# extract a 6-15s clean audio sample of the original speaker
ffmpeg -i original_video.mp4 -ss 00:00:10 -t 12 -vn -ar 24000 -ac 1 voice_sample.wav

video-translator translate \
  -i original_video.mp4 \
  -o ./output \
  --mode dubbed \
  --speaker-wav voice_sample.wav \
  --context "This is a programming tutorial video, warm but professional tone." \
  -v
```

Result in `./output/video.dubbed.mp4`: the original video with a second
Spanish audio track (the original is kept as a secondary track by default,
`--no-keep-original-audio` to replace it entirely) generated by IndexTTS-2.5,
with the original speaker's timbre, synced segment by segment with the
original transcription timing.

### How overlapping voices are avoided

Each line is synthesized aiming at the real gap available until the next one
starts (not the original transcription duration), in three layers that kick
in in order:
1. The TTS engine itself tries to generate the voice directly at that duration
   (IndexTTS-2.5's native duration control).
2. If it still runs long, speed is adjusted with `ffmpeg` within a range that
   doesn't distort the voice too much.
3. If it *still* doesn't fit, it's trimmed to the exact limit with a short
   fade-out (~80ms) — but **only when it's actually needed**, never
   unconditionally, so a clip that already fit well is left untouched.

The translation LLM is also asked to favor concise phrasing (similar length
to the source), specifically so layer 3 rarely has to kick in. If you notice
frequent voice cutoffs, check the `-v` logs
(`audio_mixing.segment_truncated`) — it tells you exactly how much each
segment overran its available slot, useful for deciding whether to ask for
even shorter translations via `--context`.

### Simpler-to-install alternative: XTTS v2 (Coqui TTS)

If you'd rather avoid cloning repos and manually downloading checkpoints,
XTTS v2 installs directly with `pip`/`uv` (though without native duration
control, only post-hoc ffmpeg adjustment, so sync is somewhat less precise):

```bash
uv sync --extra dubbing-coqui        # requires Python < 3.12
```
```dotenv
TTS_BACKEND=coqui_xtts
```

> **Incompatible with `--extra dubbing-indextts`:** `TTS==0.22.0` (Coqui)
> requires `pandas<2.0`/`numpy<2.0`, and IndexTTS-2.5's transitive
> dependencies require newer versions — they're mutually exclusive extras
> (`uv` will explicitly block installing both). Use one or the other, not
> both in the same environment.

## Multiple speakers: per-person voice and gender (`--diarize`)

If the video has several people speaking, `--diarize` enables an extra
**diarization** step (detecting who speaks and when) with
[pyannote.audio](https://github.com/pyannote/pyannote-audio), the open
source standard for this. From there, the pipeline:

1. Assigns each transcript line to the corresponding speaker (by maximum temporal overlap).
2. Automatically extracts, for each detected speaker, their longest speaking turn (6-15s) as a voice reference sample.
3. Estimates each speaker's gender by voice pitch (F0), and passes it to the LLM as context so it adjusts Spanish grammatical gender agreement (e.g. "listo" vs "lista").
4. In `--mode dubbed`, **each speaker is cloned with their own voice** (not one generic voice for the whole video): person A's lines are synthesized with A's timbre, B's with B's.

### Installation: isolated venv (important)

`pyannote.audio` **is not a dependency of the main project**. It runs in a
**completely separate venv** invoked via subprocess, for a concrete reason:
`pyannote.audio` requires `protobuf>=5.0` (via its telemetry client
`pyannoteai-sdk`), and **IndexTTS-2.5 requires `protobuf<3.20`** (via
`descript-audiotools`) — this is a real version conflict with no possible
combination that satisfies both at once. If you ever see a `uv` "no solution
found" error mentioning `protobuf` when mixing diarization with dubbing,
that's this conflict: the fix isn't to look for another version, it's to
keep them in separate processes, which is exactly what this project does.

```bash
./scripts/setup_diarization_env.sh    # creates .venv-diarization/ with pyannote.audio + librosa
```

This script **does not touch your main venv** (`.venv/`); it creates a new
one (`.venv-diarization/`) just for this. The project invokes it via
subprocess when you use `--diarize` (see
`infrastructure/diarization/subprocess_diarizer.py` and
`scripts/diarization_worker.py`), so your main environment never imports
`pyannote.audio` directly and never clashes with `indextts`.

`pyannote.audio` also requires a Hugging Face token with terms accepted:
1. Create a token at [hf.co/settings/tokens](https://hf.co/settings/tokens).
2. Accept the model's terms on its page: [pyannote/speaker-diarization-community-1](https://huggingface.co/pyannote/speaker-diarization-community-1).
3. Set `HF_TOKEN` in your main project's `.env` (the subprocess receives it automatically).

### macOS: if you see a `libtorchcodec` / `libavutil.NN.dylib not loaded` error

`pyannote.audio >= 4.0` uses [`torchcodec`](https://github.com/pytorch/torchcodec)
to read audio, which on macOS has a **known, unresolved incompatibility with
Homebrew's FFmpeg** ([torchcodec#570](https://github.com/meta-pytorch/torchcodec/issues/570)) —
it's not fixed by installing a different Homebrew version. The fix that
actually works (recommended by the torchcodec team itself) is to use
**conda-forge** to get the FFmpeg libraries, **without exporting
`DYLD_LIBRARY_PATH` in your shell** (that would break the Homebrew
`ffmpeg`/`ffprobe` the rest of the project uses — it affects any binary that
inherits it, not just torchcodec). Instead, the project injects that
variable **only inside the isolated diarization subprocess**, via
`DIARIZATION_DYLD_LIBRARY_PATH` in your `.env`:

```bash
brew install miniforge
conda init zsh                       # restart your terminal after this

conda create -n ffmpeg-libs -c conda-forge "ffmpeg<8" -y   # <8: what torchcodec 0.7.0 supports

conda env list   # copy the path shown next to "ffmpeg-libs"
```

Set that path (+ `/lib`) in your `.env`:
```dotenv
DIARIZATION_DYLD_LIBRARY_PATH=/opt/homebrew/Caskroom/miniforge/base/envs/ffmpeg-libs/lib
```

Verify the library actually exists there before retrying:
```bash
ls "/opt/homebrew/Caskroom/miniforge/base/envs/ffmpeg-libs/lib" | grep libavutil
```
With that configured, `video-translator` works from any terminal — no need
to manually export anything each session.

### Usage

```bash
video-translator translate \
  -i interview.mp4 \
  --mode dubbed \
  --diarize \
  --context "This is an interview between two people about artificial intelligence." \
  -v
```

No need to pass `--speaker-wav`: the system automatically extracts a voice
sample for each detected speaker. `--speaker-wav` is still available as a
*fallback* if a speaker doesn't have enough clean audio to generate their own
sample, or to force a single voice if you'd rather disable per-speaker
cloning.

If you know upfront how many people are speaking, narrow the search:
```bash
video-translator translate -i video.mp4 --mode dubbed --diarize --min-speakers 2 --max-speakers 2
```

When done, the CLI prints a table with the detected speakers, their
estimated gender, and whether a usable voice sample was successfully
extracted for each.

**Note on gender estimation:** it's a heuristic based on voice pitch
(fundamental frequency), not a precise demographic identification — it's
used solely as an auxiliary signal for Spanish grammatical agreement, not to
label people. `--diarize` is also useful without dubbing (e.g. with `--mode
soft_subtitles`) so the translation reflects each speaker's register in the
subtitles.

## Context-driven translation (applies to both subtitles and dubbing)

The `--context` parameter (or `TranslationContext.prompt`) is injected into
the LLM's *system prompt* along with:
- Desired **tone** (`--tone formal|informal|technical`).
- Mandatory **glossary** term→translation (`--glossary glossary.json`), to force consistency in product names, technical jargon, etc.

Example:

```bash
video-translator translate \
  --input pycon_talk.mp4 \
  --context "This is a technical PyCon talk about async Python. \
Use a warm but professional tone, aimed at developers. \
Keep terms like 'async', 'coroutine', 'event loop' in English." \
  --glossary glossary.json \
  --mode soft_subtitles
```

`glossary.json`:
```json
{
  "event loop": "event loop",
  "coroutine": "corrutina",
  "pull request": "pull request"
}
```

## Installation

### Requirements
- Python 3.10, 3.11, or 3.12 (**not 3.13**: `TTS`/Coqui, used for dubbing, doesn't support 3.13 yet; the rest of the project would work fine on 3.13, but `pyproject.toml` pins it to `<3.13` to avoid the build failure). The repo includes `.python-version` set to `3.11`.
- [ffmpeg](https://ffmpeg.org/download.html) installed and on `PATH`
- A local LLM backend: [Ollama](https://ollama.com/download) **or** [`llama-server`](https://github.com/ggerganov/llama.cpp) (see section below)
- NVIDIA GPU recommended for long videos (CPU works but is much slower)

### Steps with `uv` (recommended)

```bash
git clone https://github.com/Root1V/ai-video-dubbing-pipeline.git
cd video-translator

uv python install 3.11     # if you don't already have it (uv downloads it for you)
uv sync                    # uses .python-version -> installs with Python 3.11

# optional dubbing (requires Python < 3.12, already covered by .python-version):
uv sync --extra dubbing

cp .env.example .env
```

### Steps with `pip` / classic venv

```bash
python3.11 -m venv .venv    # explicitly use 3.11 or 3.12, not 3.13
source .venv/bin/activate

pip install -e ".[dev]"          # base install + dev tools
pip install -e ".[dubbing]"      # optional: enables dubbing with Coqui TTS

cp .env.example .env             # adjust for your hardware

./scripts/setup_models.sh qwen2.5:14b-instruct   # downloads the LLM into Ollama

video-translator check           # verify ffmpeg / ollama (or llama-server)
```

## Usage

### Subtitles only (fastest, no powerful GPU required)
```bash
video-translator translate -i video.mp4 -o ./output \
  --context "Nature documentary, slow narrative tone." \
  --mode subtitles_only
```

### Subtitles burned into the video
```bash
video-translator translate -i video.mp4 --mode burn_subtitles
```

### Subtitles as a selectable track (default)
```bash
video-translator translate -i video.mp4 --mode soft_subtitles
```

### Full dubbing with voice cloning
```bash
video-translator translate -i video.mp4 --mode dubbed \
  --speaker-wav original_speaker_sample.wav \
  --context "Corporate video, formal and professional tone."
```

## Using `llama-server` (llama.cpp) instead of Ollama

If you already have a model running with `llama-server` (e.g.
`gpt-oss-20b-mxfp4`), you don't need Ollama. The project ships a second
adapter (`LlamaServerTranslator`) that talks to the OpenAI-compatible API
`llama-server` exposes (`POST /v1/chat/completions`), instead of Ollama's
native API (`/api/chat`).

```dotenv
TRANSLATION_BACKEND=llama_server
LLAMA_SERVER_HOST=http://localhost:8080
LLAMA_SERVER_MODEL=gpt-oss-20b-mxfp4
LLAMA_SERVER_MAX_TOKENS=4096
```

With your server already running (`llama-server -m gpt-oss-20b-mxfp4.gguf --port 8080 -c 8192`):

```bash
video-translator check          # now validates llama-server instead of Ollama
video-translator translate -i video.mp4 --mode soft_subtitles
```

Nothing else in the pipeline needs to change: `TranslateVideoUseCase` only
knows the `Translator` `Protocol`, so it doesn't matter whether Ollama,
llama-server, vLLM, or any other OpenAI-compatible backend sits underneath.
`container.py` decides which adapter to build based on
`TRANSLATION_BACKEND`.

A couple of things to watch with `llama-server`:
- Tune `-c` (context size) when starting the server based on your
  translation batch size (`TRANSLATION_BATCH_MAX_CHARS`); if a batch +
  history + system prompt exceeds the context, the server will truncate or
  fail.
- If you see `Error: LLM response misalignment: expected N lines...` with
  the raw response cut off mid-sentence, generation hit the
  `LLAMA_SERVER_MAX_TOKENS` limit (default 4096) before finishing the batch
  — raise that value in your `.env`, and make sure the server's `-c` is
  larger than `LLAMA_SERVER_MAX_TOKENS` + the input prompt size. The
  translator also automatically retries by splitting the batch in half when
  this happens (see `translate_batch_with_recovery` in `prompting.py`), so
  one unusually long batch shouldn't bring down the whole pipeline — but it's
  still worth raising the limit if you see it often, for efficiency.
- `gpt-oss-20b-mxfp4` is a model quantized in MXFP4 format: on an M4 Max
  with 128GB you have plenty of memory headroom; the bottleneck is usually
  generation speed, not memory.

## macOS (Apple Silicon: M1/M2/M3/M4)

There's no NVIDIA/CUDA GPU on Mac, so **don't use the `Dockerfile`/
`docker-compose.yml`** (they're built for CUDA, and Docker Desktop on Mac
can't pass Metal through to the container anyway). On Mac everything runs
natively, with a venv:

```bash
brew install ffmpeg ollama

python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pip install -e ".[dubbing]"      # optional, dubbing

cp .env.macos.example .env       # config already tuned for Apple Silicon

ollama serve &                    # if it's not already running as a service
./scripts/setup_models.sh qwen2.5:32b-instruct

video-translator check
video-translator translate -i video.mp4 --mode soft_subtitles
```

**Key differences from an NVIDIA GPU machine:**

| Component | On your Mac | Why |
|---|---|---|
| faster-whisper | `WHISPER_DEVICE=cpu`, `WHISPER_COMPUTE_TYPE=int8` | CTranslate2 doesn't support Metal/MPS, CPU only. On Apple Silicon it uses Accelerate and `int8` runs well even on `large-v3` |
| Ollama (LLM) | No code changes, automatically Metal-accelerated | Ollama does support Apple Silicon natively |
| LLM model | You can use larger models: `qwen2.5:32b-instruct` or even `qwen2.5:72b-instruct` / `llama3.1:70b-instruct` | With 128GB of unified memory you have plenty of headroom; larger models = better translation quality |
| Coqui TTS (dubbing) | `TTS_DEVICE=cpu` | XTTS v2 on MPS is unstable (unimplemented operators); CPU is slower but reliable |
| Docker | Don't use the included Dockerfile/compose | They're based on `nvidia/cuda`; on Mac everything runs natively |

With your hardware (M4 Max, 128GB), the best quality-per-effort move is
upgrading the LLM model rather than worrying about Whisper's hardware:
CPU transcription with `int8` is reasonably fast, and Ollama with Metal
moves large models smoothly.

## Docker (Linux / Windows with NVIDIA GPU)

```bash
docker compose up --build
```

This spins up Ollama and the app together. Put your video at
`./data/video.mp4` and your context at `./data/context.txt`; output appears
in `./output`. Requires Docker with NVIDIA support
(nvidia-container-toolkit); **doesn't apply to macOS**.

## Testing

```bash
pytest --cov=video_translator --cov-report=term-missing
ruff check src tests
mypy src
```

Unit tests use test doubles (fakes) for the four core interfaces
(`MediaProcessor`, `Transcriber`, `Translator`, `SubtitleWriter`), so they
run in seconds without needing ffmpeg, a GPU, or a real LLM.

## Extensibility

- **Another translation LLM**: create a new class implementing `Translator`
  (e.g. using local `transformers` instead of Ollama) and register it in `container.py`.
- **Another STT engine**: implement `Transcriber` (e.g. `whisper.cpp` via bindings).
- **Other languages**: the pipeline is agnostic to the language pair; change
  `source_lang`/`target_lang` in `TranslationContext`.

## License

MIT — see [LICENSE](LICENSE).
