"""Ollama client: turn raw transcripts into clean, paste-ready prompts."""
import logging

import httpx

from .config import CLEAN_SYSTEM, Settings

log = logging.getLogger(__name__)

class OllamaClient:
    def __init__(self, settings: Settings):
        self.settings = settings

    def _list_models_full(self) -> list[dict]:
        try:
            r = httpx.get(f"{self.settings.ollama_url}/api/tags", timeout=5)
            r.raise_for_status()
            return r.json().get("models", [])
        except (httpx.HTTPError, KeyError) as e:
            log.warning("Cannot list Ollama models: %s", e)
            return []

    def list_models(self) -> list[str]:
        return [m["name"] for m in self._list_models_full()]

    def pick_default_model(self) -> str:
        """Prefer a q4-quant model that leaves VRAM headroom for Whisper.

        On a 12 GB card a q8 12B alone fills the GPU, so rank by: fits in
        ~9 GB first, then lower quant level, then the largest such model.
        """
        models = self._list_models_full()
        if not models:
            return ""

        def score(m: dict) -> tuple:
            quant = (m.get("details", {}).get("quantization_level") or "").upper()
            size_gb = m.get("size", 0) / 1e9
            quant_rank = 0 if quant.startswith("Q4") else 1 if quant.startswith(("Q5", "Q6")) else 2
            fits = 0 if 0 < size_gb <= 9 else 1
            return (fits, quant_rank, -size_gb)

        return min(models, key=score)["name"]

    def resolve_model(self) -> str:
        return self.settings.ollama_model or self.pick_default_model()

    def optimize(self, transcript: str, mode: str | None = None) -> str:
        """Post-process a transcript. mode: prompt | clean | raw."""
        mode = mode or self.settings.mode
        if mode == "raw" or not transcript.strip():
            return transcript
        model = self.resolve_model()
        if not model:
            log.warning("No Ollama model available; returning raw transcript")
            return transcript

        system = self.settings.prompt_system if mode == "prompt" else CLEAN_SYSTEM
        try:
            r = httpx.post(
                f"{self.settings.ollama_url}/api/chat",
                json={
                    "model": model,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": transcript},
                    ],
                    "stream": False,
                    # gemma4 is a thinking model; reasoning tokens add ~7 s per
                    # call and contribute nothing to transcript cleanup.
                    "think": False,
                    # 8k ctx is plenty for transcripts and keeps the KV cache
                    # small enough to coexist with Whisper in 12 GB VRAM
                    # (Ollama's 128k default slows generation ~10x here).
                    "options": {"temperature": 0.2, "num_ctx": 8192},
                },
                timeout=180,
            )
            r.raise_for_status()
            out = r.json()["message"]["content"].strip()
            return out or transcript
        except (httpx.HTTPError, KeyError) as e:
            log.error("Ollama optimize failed: %s", e)
            return transcript
