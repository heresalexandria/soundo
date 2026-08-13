<div align="center">
  <img src="soundslo/static/soundslo-icon.svg" alt="Soundslo icon" width="104" height="104" />
  <h1>Soundslo</h1>
  <p><em>Generate private, six-minute instrumental soundtracks from text on your Apple Silicon Mac.</em></p>
  <p><strong>Powered by Stability AI.</strong></p>
</div>

<p align="center">
  <img src="docs/assets/soundslo-app.jpg" alt="Soundslo's local music generation workbench" width="1100" />
</p>

Soundslo is a model-aware, local-first music workbench for the **Stable Audio 3** family. Describe
an instrumental in ordinary language, choose the quality/privacy/storage tradeoff you want, queue
one or more renders, and manage the resulting WAV files from a browser. Medium remains the default
and runs entirely on your Mac; Small Music is an optional lighter local model, and Large is an
explicitly opt-in hosted model.

Soundslo is an independent project and is not affiliated with, sponsored by, or endorsed by
Stability AI.

The app uses Stability AI's native MLX runtime rather than PyTorch. It is pinned to a tested
runtime and model snapshot, stores its history in SQLite, and generates 44.1 kHz 16-bit stereo
WAVs.

## What it includes

- Text-to-music with arbitrary aesthetic, era, mood, instrumentation, and arrangement prompts
- Exact 1–380 second renders, entered as minutes and seconds with an optional fine-tuning slider
- A collapsed model manager with install status, selection, model size, duration, quality, privacy,
  credential, and cost tradeoffs
- Local Stable Audio 3 Small Music and Medium through native MLX, plus optional hosted Large
- Medium with the SAME-L decoder, FP16 DiT, and memory-conscious model unloading
- Negative prompting for vocals, configurable guidance, steps, duration, and reproducible seeds
- A durable, one-at-a-time generation queue with real stage and sampling-step progress
- Persistent history, in-browser playback, download, reveal in Finder, rename, retry, cancel,
  prompt reuse, runtime logs, and deletion of both the record and WAV
- A loopback-only web server; Small and Medium prompts/audio stay local, while Large clearly marks
  that its prompt is sent to Stability AI and its result is downloaded back to this Mac

## Quick start

On an Apple Silicon Mac, clone or download this repository, open Terminal in its folder, and run:

```bash
bash scripts/setup.sh && bash scripts/run.sh
```

That is the entire setup. The script installs everything into this folder, downloads the model,
and opens Soundslo at [http://127.0.0.1:8733](http://127.0.0.1:8733). First setup needs internet
access, Git, and roughly 7 GB of free disk space. Generated WAVs use about 10 MB per minute.

After the first setup, start Soundslo with:

```bash
bash scripts/run.sh
```

Stop it with `Ctrl-C` in Terminal.

<details>
<summary>Setup details and troubleshooting</summary>

The setup script installs `uv` if needed, installs Soundslo, checks out the official Stability AI
runtime at revision `a0b57f5483c4588f827f3552b7d5c6ca2a9687be`, creates its isolated MLX
environment, and downloads model snapshot `6736003cb57d06b7b1fdc36fad31b2a3709e4774`.
It downloads only the files Medium needs for text-to-audio and deliberately skips the SAME-L
encoder used only for audio-to-audio and inpainting.

The weights come from `stabilityai/stable-audio-3-optimized` on Hugging Face. A cached Hugging
Face read token improves download reliability. If access is denied, sign in with `hf auth login`
and make sure your account can access the model repository, then rerun setup.

To use a different port:

```bash
SOUNDSLO_PORT=9000 ./scripts/run.sh
```

Always use the local URL or `bash scripts/run.sh`; `soundslo/static/index.html` is an application
template, not a standalone webpage. If it is accidentally opened directly, it redirects to the
default local URL automatically.

History and WAVs live in `data/` and are intentionally excluded from Git. The upstream runtime
and weights live in `.runtime/`, also excluded.

</details>

## Models, storage, and credentials

The model manager is collapsed under **Settings** in the app so these decisions remain available
without crowding the composer. Soundslo reports what is actually installed and never sends an API
key to the browser.

| Model | Where it runs | Parameters | Maximum | Weight download | Best reason to use it |
|---|---|---:|---:|---:|---|
| [Small Music](https://huggingface.co/stabilityai/stable-audio-3-small) | This Mac | 433M | 2:00 | about 1.7 GB | Lowest local storage and memory use; faster, but less coherent than Medium |
| [Medium](https://huggingface.co/stabilityai/stable-audio-3-medium) | This Mac | 1.4B | 6:20 | about 5.2 GB | Best quality with publicly downloadable local weights |
| [Large](https://platform.stability.ai/docs/api-reference#tag/Stable-Audio-3.0) | Stability AI API | 2.7B | 6:20 | none | Highest musicality; requires internet, an API key, and 26 credits per successful generation |

The local download totals are the pinned MLX DiT, decoder, and shared T5Gemma files. Hugging Face
caches each file once, so installing Small after Medium adds about 1.1 GB rather than another full
1.7 GB. Keep additional free space for the runtime, cache metadata, temporary downloads, and WAVs.

Stability AI's [official model overview](https://github.com/Stability-AI/stable-audio-3#models)
lists Large as API-only and unsupported by the public runtime. In other words, Medium is already
the “bigger local model”; there is no public Large Hugging Face checkpoint that Soundslo can honestly
download. Enterprise self-hosting is a separate arrangement with Stability AI.

### Install or repair a local model

Medium is installed by Quick start. The Settings panel can install another available local model,
or the same downloads can be run directly:

```bash
bash scripts/install_model.sh small-music
bash scripts/install_model.sh medium
```

The downloads use `stabilityai/stable-audio-3-optimized` at Soundslo's pinned revision. If Hugging
Face requests credentials, accept the repository's license terms in your Hugging Face account and
sign in, then retry:

```bash
.runtime/stable-audio-3/optimized/mlx/.venv/bin/hf auth login
```

Tokens are handled by Hugging Face's own credential store and are never saved in this repository.
Running `bash scripts/install_model.sh large` deliberately exits with an explanation instead of
silently downloading a different or mislabeled model.

### Opt in to hosted Large

Create a Stability AI API key and start Soundslo with the hidden-input helper:

```bash
bash scripts/run_with_large.sh
```

The script keeps the key only in the server process environment. It does not write the key to
disk or shell history. Once the app reports **API ready**, open Settings and select Large. Large
text-to-audio is asynchronous, costs 26 credits per successful generation, and supports 1–380
seconds at 44.1 kHz stereo. The API does not expose a separate negative prompt, so include
“instrumental, no vocals” in the main prompt. Cancelling in Soundslo stops local polling, but it may
not cancel or refund a hosted job that Stability AI has already accepted.

## Prompting tips

A useful prompt usually covers five things: genre or reference era, instrumentation, mood,
tempo or energy, and how the piece develops. For video backgrounds, also say whether it should
be sparse, unobtrusive, loop-like, climactic, or leave room for narration.

Example:

> 1960s speculative-science orchestral score, tense low strings and bass clarinet, distant brass
> swells, subtle analog electronic pulses, slow 72 BPM, mysterious and spacious, gradual build,
> instrumental, no melody competing with narration

For local models, the default guidance value of 3 enables the negative prompt and gives stronger
text alignment, but it is roughly twice as expensive as guidance 1. Eight sampling steps is the
upstream model's intended setting; more steps are not guaranteed to improve quality. Hosted Large
supports 4–8 steps and no separate negative-prompt field.

## Development

```bash
uv sync --dev
uv run pytest
uv run ruff check .
```

The app is FastAPI plus plain HTML, CSS, and JavaScript—there is no Node build step. Its local API
documentation is available at `/docs` while the server is running.

## Licensing

The original Soundslo source code in this repository is available under the [MIT License](LICENSE).
That license does **not** relicense Stable Audio 3, T5Gemma, downloaded model weights, or other
third-party components.

The setup and model-install processes download third-party materials rather than committing or
redistributing them:

- Stability AI's `stable-audio-3` runtime is downloaded from its official repository under its
  MIT software license.
- Stable Audio 3 model weights are downloaded separately under the
  [Stability AI Community License](licenses/STABILITY_AI_COMMUNITY_LICENSE.md). Commercial users
  must [register with Stability AI](https://stability.ai/community-license). If the user and its
  affiliates exceed USD $1 million in aggregate annual revenue, commercial model use requires a
  separate [Enterprise License](https://stability.ai/enterprise). Model use and outputs are also
  subject to Stability AI's [Acceptable Use Policy](https://stability.ai/use-policy).
- The downloaded text encoder contains T5Gemma weights governed by the
  [Gemma Terms of Use](licenses/GEMMA_TERMS_OF_USE.md) and its incorporated prohibited-use policy.
- Optional hosted Large use is also governed by the Stability AI API terms, pricing, and policies
  attached to the user's own account. Soundslo does not include, proxy, or redistribute API access.

Required third-party attributions are retained in [NOTICE](NOTICE). As between users and
Stability AI, users own generated outputs to the extent permitted by law, but they remain
responsible for the outputs and their uses.

Python packages resolved by `uv` are installed as separate dependencies and retain their own
licenses; their code is not vendored into this repository. Anyone producing a future standalone
application bundle should repeat the dependency audit and include all notices required by the
versions actually bundled. Contributions are accepted under the terms in
[CONTRIBUTING.md](CONTRIBUTING.md).

Only Soundslo's source code is offered as OSI-style open-source software. The complete installed
application depends on model weights with use and revenue restrictions, so the full model stack
should be described as an **open-source application using separately licensed open-weight
models**, not as an entirely MIT-licensed or entirely open-source distribution.

## Current scope and natural next steps

Soundslo currently focuses on raw text-to-instrumental quality across the available Stable Audio 3
music tiers. The downloaded decoders can render finished audio, but audio-to-audio variation and
inpainting also need the skipped encoders. Logical follow-ons are timeline-aware multi-section
prompt planning, continuation/overlap assembly for longer scores, loudness normalization, stems or
MIDI companions, video-duration fitting, and LoRA style adapters trained on licensed material.
