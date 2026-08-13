# Soundslo

Soundslo is a private, local-first music workbench for **Stable Audio 3 Medium** on Apple
Silicon. Describe an instrumental in ordinary language, queue one or more renders, and manage
the resulting WAV files from a browser.

The app uses Stability AI's native MLX runtime rather than PyTorch. It is pinned to a tested
upstream revision, stores its history in SQLite, and generates 44.1 kHz 16-bit stereo WAVs.

## What it includes

- Text-to-music with arbitrary aesthetic, era, mood, instrumentation, and arrangement prompts
- 5–380 second renders (six minutes is 360 seconds)
- Stable Audio 3 Medium with the SAME-L decoder, FP16 DiT, and memory-conscious model unloading
- Negative prompting for vocals, configurable guidance, steps, duration, and reproducible seeds
- A durable, one-at-a-time generation queue with real stage and sampling-step progress
- Persistent history, in-browser playback, download, reveal in Finder, rename, retry, cancel,
  prompt reuse, runtime logs, and deletion of both the record and WAV
- A loopback-only web server; prompts and audio are not sent to a service

## First-time setup

Requirements: an Apple Silicon Mac, macOS, internet access for setup, Git, and roughly 7 GB of
free disk space for the runtime, Python environment, and text-to-audio weights. Generated WAVs
use about 10 MB per minute.

```bash
./scripts/setup.sh
```

The setup script installs `uv` if needed, installs Soundslo, checks out the official Stability AI
runtime at revision `a0b57f5483c4588f827f3552b7d5c6ca2a9687be`, creates its isolated MLX
environment, and downloads only the files Medium needs for text-to-audio. It deliberately skips
the SAME-L encoder used only for audio-to-audio and inpainting.

The weights come from `stabilityai/stable-audio-3-optimized` on Hugging Face. A cached Hugging
Face read token improves download reliability. If access is denied, sign in with `hf auth login`
and make sure your account can access the model repository, then rerun setup.

## Run

```bash
./scripts/run.sh
```

Soundslo opens at [http://127.0.0.1:8733](http://127.0.0.1:8733). Stop it with `Ctrl-C`. To use a
different port:

```bash
SOUNDSLO_PORT=9000 ./scripts/run.sh
```

Always use the local URL or `./scripts/run.sh`; `soundslo/static/index.html` is an application
template, not a standalone webpage. If it is accidentally opened directly, it redirects to the
default local URL automatically.

History and WAVs live in `data/` and are intentionally excluded from Git. The upstream runtime
and weights live in `.runtime/`, also excluded.

## Prompting tips

A useful prompt usually covers five things: genre or reference era, instrumentation, mood,
tempo or energy, and how the piece develops. For video backgrounds, also say whether it should
be sparse, unobtrusive, loop-like, climactic, or leave room for narration.

Example:

> 1960s speculative-science orchestral score, tense low strings and bass clarinet, distant brass
> swells, subtle analog electronic pulses, slow 72 BPM, mysterious and spacious, gradual build,
> instrumental, no melody competing with narration

The default guidance value of 3 enables the negative prompt and gives stronger text alignment,
but it is roughly twice as expensive as guidance 1. Eight sampling steps is the upstream model's
intended setting; more steps are not guaranteed to improve quality.

## Development

```bash
uv sync --dev
uv run pytest
uv run ruff check .
```

The app is FastAPI plus plain HTML, CSS, and JavaScript—there is no Node build step. Its local API
documentation is available at `/docs` while the server is running.

## Current scope and natural next steps

This first version intentionally focuses on testing Medium's raw text-to-instrumental quality.
The downloaded decoder can render finished audio, but audio-to-audio variation and inpainting
also need the skipped SAME-L encoder. Logical follow-ons are timeline-aware multi-section prompt
planning, continuation/overlap assembly for longer scores, loudness normalization, stems or MIDI
companions, video-duration fitting, and LoRA style adapters trained on licensed material.
