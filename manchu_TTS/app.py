import os
import sys
import uuid
from pathlib import Path
from typing import Dict, Any

import numpy as np
import soundfile as sf
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.requests import Request
from pydantic import BaseModel

# Optional plotting dependency for spectrogram preview.
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent
GENERATED_DIR = BASE_DIR / "generated"
GENERATED_DIR.mkdir(parents=True, exist_ok=True)

# Fixed demo assets (single-speaker demo).
MODEL_GPT = PROJECT_ROOT / "GPT_weights_v2Pro" / "manchu_speaker-e15.ckpt"
MODEL_SOVITS = PROJECT_ROOT / "SoVITS_weights_v2Pro" / "manchu_speaker_e8_s5928.pth"
REF_WAV = PROJECT_ROOT / "output" / "manchu_data" / "manchu_label_v4" / "00000016.wav"
REF_TXT = PROJECT_ROOT / "output" / "manchu_data" / "manchu_label_v4" / "00000016.txt"

# Reuse GPT-SoVITS modules directly.
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "GPT_SoVITS"))
sys.path.insert(0, str(PROJECT_ROOT / "GPT_SoVITS" / "eres2net"))

from GPT_SoVITS.TTS_infer_pack.TTS import TTS, TTS_Config  # noqa: E402
from text.manchu import text_normalize, g2p  # noqa: E402


class ConvertRequest(BaseModel):
    text: str


class SynthesizeRequest(BaseModel):
    text: str


class ManchuDemoService:
    def __init__(self) -> None:
        if not MODEL_GPT.exists() or not MODEL_SOVITS.exists():
            raise FileNotFoundError("Model files not found. Please check fixed model paths.")
        if not REF_WAV.exists() or not REF_TXT.exists():
            raise FileNotFoundError("Reference audio/text not found. Please check fixed demo assets.")

        self.prompt_text = REF_TXT.read_text(encoding="utf-8").strip()
        self.tts = self._build_tts_pipeline()

    def _build_tts_pipeline(self) -> TTS:
        cfg = TTS_Config(str(PROJECT_ROOT / "GPT_SoVITS" / "configs" / "tts_infer.yaml"))
        cfg.update_version("v2Pro")
        cfg.t2s_weights_path = str(MODEL_GPT)
        cfg.vits_weights_path = str(MODEL_SOVITS)
        cfg.update_configs()
        return TTS(cfg)

    def convert(self, text: str) -> Dict[str, Any]:
        source_text = (text or "").strip()
        if not source_text:
            raise ValueError("请输入满语文本")

        latin_text = text_normalize(source_text)
        cmu_tokens = g2p(latin_text)

        return {
            "source_text": source_text,
            "latin_text": latin_text,
            "cmudict_tokens": cmu_tokens,
            "cmudict_text": " ".join(cmu_tokens),
        }

    def synthesize(self, text: str) -> Dict[str, str]:
        converted = self.convert(text)

        req = {
            "text": converted["source_text"],
            "text_lang": "all_man",
            "ref_audio_path": str(REF_WAV),
            "prompt_text": self.prompt_text,
            "prompt_lang": "all_man",
            "top_k": 5,
            "top_p": 1.0,
            "temperature": 1.0,
            "text_split_method": "cut5",
            "batch_size": 1,
            "batch_threshold": 0.75,
            "split_bucket": True,
            "speed_factor": 1.0,
            "fragment_interval": 0.3,
            "seed": -1,
            "media_type": "wav",
            "streaming_mode": False,
            "parallel_infer": True,
            "repetition_penalty": 1.35,
            "sample_steps": 32,
            "super_sampling": False,
            "overlap_length": 2,
            "min_chunk_length": 16,
        }

        generator = self.tts.run(req)
        sr, audio = next(generator)

        uid = uuid.uuid4().hex[:12]
        wav_path = GENERATED_DIR / f"manchu_{uid}.wav"
        png_path = GENERATED_DIR / f"manchu_{uid}_spec.png"

        sf.write(str(wav_path), audio, sr)
        self._save_spectrogram(audio, sr, png_path)

        return {
            "audio_url": f"/generated/{wav_path.name}",
            "spectrogram_url": f"/generated/{png_path.name}",
            "latin_text": converted["latin_text"],
            "cmudict_text": converted["cmudict_text"],
            "reference_audio": str(REF_WAV),
            "reference_text": self.prompt_text,
        }

    @staticmethod
    def _save_spectrogram(audio: np.ndarray, sr: int, out_path: Path) -> None:
        plt.figure(figsize=(11, 4), dpi=120)
        plt.specgram(audio, Fs=sr, NFFT=1024, noverlap=768, cmap="magma")
        plt.title("Synthesized Audio Spectrogram")
        plt.xlabel("Time (s)")
        plt.ylabel("Frequency (Hz)")
        plt.colorbar(label="dB")
        plt.tight_layout()
        plt.savefig(out_path)
        plt.close()


app = FastAPI(title="Manchu TTS Demo", version="0.1.0")
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
app.mount("/generated", StaticFiles(directory=str(GENERATED_DIR)), name="generated")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

_service: ManchuDemoService | None = None


def get_service() -> ManchuDemoService:
    global _service
    if _service is None:
        _service = ManchuDemoService()
    return _service


@app.get("/")
def index(request: Request):
    return templates.TemplateResponse(
        name="index.html",
        request=request,
        context={
            "project_title": "满语语音合成演示系统（Manchu TTS Demo）",
            "model_gpt": str(MODEL_GPT),
            "model_sovits": str(MODEL_SOVITS),
            "ref_wav": str(REF_WAV),
            "ref_txt": str(REF_TXT),
        },
    )


@app.post("/api/convert")
def api_convert(body: ConvertRequest):
    try:
        return get_service().convert(body.text)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/synthesize")
def api_synthesize(body: SynthesizeRequest):
    try:
        return get_service().synthesize(body.text)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/healthz")
def healthz():
    return {"ok": True}


@app.get("/favicon.ico")
def favicon():
    # No custom favicon; avoid browser 404 noise.
    return FileResponse(str(BASE_DIR / "static" / "placeholder.ico")) if (BASE_DIR / "static" / "placeholder.ico").exists() else {"ok": True}


if __name__ == "__main__":
    import uvicorn

    print("Starting Manchu TTS demo on http://127.0.0.1:7868")
    uvicorn.run("manchu_TTS.app:app", host="0.0.0.0", port=7868, reload=False)
