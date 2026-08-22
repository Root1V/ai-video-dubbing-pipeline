# AI Video Dubbing Pipeline — EN → ES Video Dubbing with 100% Open Source AI

[![CI](https://github.com/USERNAME/REPO_NAME/actions/workflows/ci.yml/badge.svg)](https://github.com/USERNAME/REPO_NAME/actions/workflows/ci.yml)
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
│   ├── synthesis_job.py                  <- TTS job DTO, dispatched sequentially or in parallel
│   └── use_cases/translate_video.py     <- pipeline orchestrator (timing-instrumented)
├── infrastructure/     # Concrete adapters (implement the ports)
│   ├── media/ffmpeg_processor.py
│   ├── transcription/faster_whisper_transcriber.py
│   ├── translation/ollama_translator.py  <- context prompt applied here
│   ├── synthesis/
│   │   ├── index_tts2_synthesizer.py     <- single-pass inference
│   │   ├── parallel_tts_pool.py          <- multi-process TTS dispatch
│   │   └── coqui_tts_synthesizer.py
│   ├── diarization/subprocess_diarizer.py  <- isolated venv, subprocess-based
│   └── subtitles/srt_writer.py
├── utils/
│   ├── timing.py                          <- per-stage timing / observability
│   ├── synthesis_grouping.py              <- merges same-speaker segments before TTS
│   └── text_batching.py
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

## Performance: keeping a 1h video under ~1h of processing

A 1-hour video can produce **1000+ transcript segments**. Naively processing
each one sequentially — especially through an autoregressive TTS model for
dubbing — is what turns a video into a 10-hour job. Four independent
optimizations attack this:

1. **Transcription and diarization run concurrently.** They're independent
   (both only need the extracted audio), and each can take tens of minutes
   on its own — running them sequentially just adds their times together for
   no reason. They now run in two threads (`_transcribe_and_diarize` in
   `translate_video.py`); the pipeline report shows both as
   `concurrent_stage_groups` so it's clear they overlapped.
2. **One TTS inference pass per segment, not two.** An earlier version
   generated speech once "at natural pace," measured the result, and — if it
   missed the target duration by more than 15% — generated it a *second*
   time with a corrected `duration_factor`. That's up to 2x the most
   expensive step in the whole pipeline, for every segment. Now a
   `duration_factor` is estimated upfront from a cheap chars-per-second
   heuristic (no generation needed to compute it), one inference pass runs,
   and the final precision fit is handled by `ffmpeg` (`fit_to_duration`,
   uncapped chained `atempo`, see the dubbing section above) — far cheaper
   than a second model call.
3. **Segments get grouped before synthesis** (`utils/synthesis_grouping.py`,
   `TTS_GROUP_SEGMENTS=true` by default). Consecutive lines from the *same
   confirmed speaker* (requires `--diarize`; segments without a resolved
   speaker are never merged, to avoid guessing) with little silence between
   them are merged into a single, longer TTS call instead of one call per
   short Whisper segment. Every TTS call has a fixed startup cost on top of
   the per-character cost; with 1000+ short segments that fixed cost
   dominates, so cutting the call count directly cuts wall time.
4. **TTS synthesis runs in a parallel process pool**
   (`infrastructure/synthesis/parallel_tts_pool.py`, `TTS_PARALLEL_WORKERS`,
   default `0` = auto-detect: half the available cores, capped at 6). Each
   worker process loads its own persistent copy of the model once and then
   processes jobs from a shared queue — on a multi-core machine with enough
   RAM (each worker needs its own model in memory, roughly 4-6GB for
   IndexTTS-2.5) this scales close to linearly with worker count. The use
   case builds every `SynthesisJob` upfront and dispatches them all via
   `synthesize_batch` when the configured synthesizer supports it (duck-typed
   via `hasattr`), falling back to the original one-at-a-time loop otherwise
   — so a plain, non-pooled synthesizer keeps working exactly as before.
5. **Each TTS worker process is capped to its fair share of CPU threads**
   (`parallel_tts_pool._init_worker`, via `OMP_NUM_THREADS`/`MKL_NUM_THREADS`/
   `torch.set_num_threads`). Without this, every worker process defaults to
   using *all* CPU cores for its own PyTorch/BLAS calls, so N workers end up
   oversubscribing the machine and competing with each other — measured on a
   real run, 3 CPU workers took exactly as long as running the same jobs
   sequentially. Splitting the core budget evenly across workers is what lets
   the parallelism in point 4 actually pay off.

None of this changes the anti-overlap/no-content-loss guarantees described
above — grouping and parallelism only change *how many* TTS calls happen and
*in what order*, never the final per-segment timing math.

### macOS: parallel TTS and GPU (Metal) safety

**Do not force `INDEX_TTS2_DEVICE=mps` together with `TTS_PARALLEL_WORKERS > 1`.**
IndexTTS-2.5 auto-selects Metal (MPS) on Apple Silicon when no device is
specified, and several *separate processes* each grabbing their own Metal
context at the same time is a known-unstable combination on macOS — it can
crash the GPU driver and **force a full system reboot** (not a normal Python
exception you can catch or recover from). The project handles this
automatically: whenever `TTS_PARALLEL_WORKERS`/`--tts-workers` is above 1 on
macOS and you haven't explicitly set `INDEX_TTS2_DEVICE`, it forces `cpu` for
every worker process, logging a warning so it's clear why. Parallelism still
helps — you get real speedup from multiple CPU processes on a multi-core
Mac — it just doesn't also try to share the GPU across them. A single worker
(`--tts-workers 1`) is unaffected and keeps using MPS normally, since that's
the officially supported single-process use case.

**Quick tuning knobs**, no `.env` editing required:
```bash
video-translator translate -i video.mp4 --mode dubbed --diarize \
  --tts-workers 8 --group-segments -v
```
On a machine with plenty of cores and RAM (e.g. an Apple Silicon Max/Ultra
chip with 64GB+ unified memory), pushing `--tts-workers` well above the
auto-detected default is usually the single biggest lever left — on macOS
this now safely runs on CPU workers rather than risking the GPU driver.

### macOS: transcription and diarization on the GPU

`faster-whisper` (the default transcription engine) runs on CTranslate2,
which has **no Metal/MPS backend** — on a Mac it is always CPU-bound,
regardless of configuration. If you install the `transcription-mlx` extra
(`pip install "video-translator[transcription-mlx]"`, Apple Silicon only) you
can switch to [`mlx-whisper`](https://github.com/ml-explore/mlx-examples)
instead, which runs on the GPU via Apple's MLX framework:

```bash
# .env
WHISPER_BACKEND=mlx
MLX_WHISPER_MODEL=mlx-community/whisper-large-v3-mlx
```

The rest of the `WHISPER_*` settings (`compute_type`, `cpu_threads`, ...) are
specific to the `faster_whisper` backend and don't apply when using `mlx`.
pyannote.audio's diarization also isn't officially certified for MPS, but
running it there works in practice — just set `DIARIZATION_DEVICE=mps`, no
code changes needed.

Measured on an M4 Max with a real 3-minute, single-speaker clip (warm model
cache; the very first `mlx` run also pays a one-time ~3GB Hugging Face
download):

| Stage | CPU (default) | GPU (Metal/MPS) | Result |
|---|---|---|---|
| Transcription (`WHISPER_BACKEND=mlx`) | 136s (faster-whisper) | **8.6s** (mlx-whisper) | ~16x faster |
| Diarization (`DIARIZATION_DEVICE=mps`) | 166s | **10s** | ~17x faster |
| TTS (`TTS_PARALLEL_WORKERS=1`, `INDEX_TTS2_DEVICE=mps`) | 328s (6 CPU workers) | 1059s (1 GPU worker) | **3.2x *slower* — don't use** |

Transcription and diarization run concurrently (point 1 above), so together
they went from a ~166s critical-path block down to ~10-14s. TTS is the
exception: IndexTTS-2.5's autoregressive generation step didn't reliably
speed up on MPS (sometimes matching CPU speed), and losing the 6-way process
parallelism outweighed whatever the GPU saved on the non-autoregressive
parts of the model (`s2mel`/`bigvgan`, which *did* speed up substantially).
Keep TTS on CPU with multiple workers; only try MPS there if you have a
different TTS backend/model where this trade-off might not hold.

End to end, on the same clip, this took the total pipeline time from ~530s
down to ~416s (`realtime_factor` 2.31) — with TTS now representing ~88% of
the remaining time, by far the biggest lever left if you want to go faster
still.

## Observability: where did the time go?

Every stage is timed (`utils/timing.py`) and reported two ways:
- **A summary table** printed at the end of the run (order, durations, % of total,
  and a note on which stages ran concurrently or were resumed from a previous run).
- **A JSON report** written to `<output_dir>/pipeline_timings.json` and
  **updated incrementally after every stage** (and even when a stage starts, via
  `current_stage`), so a crashed run still leaves an accurate partial snapshot
  (`"completed": false`). You can diff timings between runs (e.g. after tuning
  `--tts-workers`) instead of guessing from scrollback logs.

```json
{
  "run_id": "a1b2c3d4e5f6",
  "run_ids": ["9f8e7d6c5b4a", "a1b2c3d4e5f6"],
  "started_at": "2026-08-21T10:00:00+00:00",
  "generated_at": "2026-08-21T10:35:40+00:00",
  "completed": true,
  "resumed_run": false,
  "total_seconds": 2140.3,
  "num_stages": 9,
  "sum_of_stage_seconds": 5411.7,
  "overhead_seconds": 3.2,
  "parallel_time_saved_seconds": 1802.5,
  "concurrent_stage_groups": [["transcription", "diarization"]],
  "input": {"video": "video/lecture.mp4", "duration_seconds": 3615.2},
  "realtime_factor": 0.59,
  "effective_config": {
    "whisper_model": "large-v3", "whisper_device": "cpu", "whisper_compute_type": "int8",
    "translation_backend": "llama_server", "llm_model": "gpt-oss-20b-mxfp4",
    "diarize_enabled": true, "tts_backend": "index_tts2", "tts_workers": 3,
    "tts_device_forced_cpu": true
  },
  "warnings": [
    {"source": "audio_mixing.overflow_after_compression", "segment_index": 2, "overflow_seconds": 0.27}
  ],
  "stages": [
    {"order": 1, "name": "audio_extraction", "status": "completed", "seconds": 4.1, "percent_of_total": 0.2, "started_at": "...", "ended_at": "..."},
    {"order": 2, "name": "transcription", "status": "completed", "seconds": 1802.5, "percent_of_total": 84.2, "ran_concurrently": true, "num_segments": 1284},
    {"order": 3, "name": "diarization", "status": "completed", "seconds": 1950.7, "percent_of_total": 91.1, "ran_concurrently": true, "num_speakers": 2, "num_turns": 340},
    {"order": 4, "name": "speaker_profile_building", "status": "completed", "seconds": 8.3, "percent_of_total": 0.4, "num_speakers": 2},
    {"order": 5, "name": "translation", "status": "completed", "seconds": 95.2, "percent_of_total": 4.4, "num_segments": 1284, "num_batches": 42},
    {"order": 6, "name": "subtitles_writing", "status": "completed", "seconds": 0.1, "percent_of_total": 0.0},
    {"order": 7, "name": "rendering_dubbed", "status": "completed", "seconds": 1620.4, "percent_of_total": 75.7},
    {"order": 8, "name": "tts_synthesis", "status": "completed", "seconds": 1540.8, "percent_of_total": 72.0, "num_jobs": 412, "num_segments_input": 1284, "num_groups": 412, "grouping_reduction_pct": 67.9},
    {"order": 9, "name": "audio_mixing_and_muxing", "status": "completed", "seconds": 79.6, "percent_of_total": 3.7}
  ]
}
```
Each stage carries an `order` (execution sequence), a `status`
(`"completed"` or `"resumed"`), and `started_at`/`ended_at` UTC timestamps.
When you relaunch with `--resume`, skipped stages keep the **real duration they
had in the previous run** (`"status": "resumed"`) — the report is adopted from
the existing file instead of resetting them to 0.0s — so the final report is
still a faithful profile of the total work.
(`percent_of_total` is computed against `sum_of_stage_seconds` — the total
recorded work, including durations inherited from a previous run on resume —
so stage percentages always add up to ~100%; note that `rendering_dubbed`
nests `tts_synthesis`/`audio_mixing_and_muxing` inside it, so those overlap.
The top-level `total_seconds` remains the real wall-clock number.) Every
stage's start/end is also logged with `-v`, tagged
with a `run_id` shared across the whole run, so log lines from concurrent
stages (or, eventually, multiple runs interleaved in a shared log stream)
can be told apart. The report also carries `run_ids`: the full chain of runs
that produced the result (one per `--resume` relaunch), current run last.

**Every log line is also persisted to a file**, not just printed to the
terminal: `<output_dir>/logs/run_<timestamp>.log` (plain text, no ANSI color
codes, so it's readable in any editor or `grep`-able). The CLI prints its
path both at the start and end of the run. This means you don't need `-v`
open in a terminal you can't lose — a long run's full log (including any
error, if the pipeline fails partway through) survives in the output
directory alongside the subtitles and the timings report. Set
`LOG_JSON=true` in your `.env` if you'd rather have the file (and console) in
structured JSON-lines instead of the human-readable format.

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

Result in `./output/lecture.dubbed.mp4` (the output name derives from the
input file name plus a mode suffix, so two different videos translated into
the same folder never overwrite each other): the original video with a second
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
git clone <this-repo>
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
Add `--resume`/`-r` to any command to automatically skip stages already
completed from a prior (possibly interrupted) run — see the
[Resumabilidad](#resumabilidad-reanudar-un-procesamiento-interrumpido) section.

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

## Resumabilidad: reanudar un procesamiento interrumpido

Los videos de una hora pueden tardar 12+ horas en procesarse. Si el pipeline
se interrumpe (corte de energia, Ctrl-C, crash, reinicio), puedes reanudirlo
desde la ultima etapa completada con `--resume` / `-r`:

```bash
video-translator translate -i video.mp4 --mode dubbed --diarize --resume -v
```

El pipeline guarda automaticamente un checkpoint (`_work/checkpoint.json`)
dentro del directorio de salida despues de cada etapa clave:

| Etapa | Que se guarda |
|---|---|
| Extraccion de audio | El archivo WAV extraido (verificado por existencia) |
| Transcripcion | Segmentos de transcripcion + segmentos de diarizacion (serializados en JSON) |
| Perfiles de hablantes | Perfiles con genero y clips de referencia (solo con `--diarize`) |
| Traduccion | Segmentos traducidos (serializados en JSON) |
| Subtitulos | Los archivos SRT (verificados por existencia) |
| Sintesis TTS | Cada archivo `tts_segments/group_NNNNNN.wav` verificado individualmente |
| Video final | El archivo MP4 de salida (verificado por existencia) |

Al reanudar:
- Las etapas ya completadas se saltan automaticamente (aparece `pipeline.resume_skipping` en los logs).
- Para TTS, cada archivo WAV ya generado se verifica individualmente: solo se sintetizan los que faltan.
- El checkpoint se valida contra el video de entrada, el modo y la bandera `--diarize`: si cambiaste alguno, se ignora y se reinicia desde cero.
- Al completarse el pipeline con exito, el checkpoint se elimina automaticamente.

**Consejo**: siempre usa `--resume`; no cuesta nada cuando no hay checkpoint previo y te salva horas si el procesamiento se interrumpe.

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
