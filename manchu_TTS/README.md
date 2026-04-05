# Manchu TTS Demo Web

A minimal Manchu-only inference web system for GPT-SoVITS.

## Fixed demo setup

- GPT model: `GPT_weights_v2Pro/manchu_speaker-e15.ckpt`
- SoVITS model: `SoVITS_weights_v2Pro/manchu_speaker_e8_s5928.pth`
- Reference audio: `output/manchu_data/manchu_label_v4/00000016.wav`
- Reference text: `output/manchu_data/manchu_label_v4/00000016.txt`

## Features

- Manchu-only text synthesis (no other language options)
- Show normalized latin text
- Show CMUdict phoneme sequence
- Synthesize and return playable audio URL
- Display spectrogram image

## Run

From repository root (recommended: use `GPTSoVits` conda env):

```bash
conda run -n GPTSoVits python -m uvicorn manchu_TTS.app:app --host 0.0.0.0 --port 7868
```

Then open:

`http://127.0.0.1:7868`

## Notes

- First synthesis can be slow due to model loading.
- This demo intentionally fixes one reference speaker for school showcase use.

## Environment and system dependencies

Python runtime (inside `GPTSoVits`):

```bash
conda run -n GPTSoVits python -c "import torch,torchaudio,fastapi,uvicorn,jinja2,soundfile,matplotlib,numpy; print('python_deps_ok')"
```

macOS system dependencies:

```bash
brew list --versions ffmpeg sox libsndfile
```
