"""Ollama client: turn raw transcripts into clean, paste-ready prompts."""
import logging

import httpx

from .config import (CLEAN_SYSTEM, DEFAULT_PROMPT_SYSTEM, REFINE_SYSTEM,
                     THINK_LEVELS, TITLE_SYSTEM, Settings)

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

    def _chat(self, system: str, user: str, think, timeout: int = 300) -> str | None:
        """One Ollama chat call; returns content or None on failure."""
        model = self.resolve_model()
        if not model:
            return None
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "stream": False,
            "think": think,
            # 8k ctx keeps the KV cache small enough to coexist with
            # Whisper in 12 GB VRAM (Ollama's 128k default is ~10x slower).
            "options": {"temperature": 0.2, "num_ctx": 8192},
        }
        try:
            r = httpx.post(f"{self.settings.ollama_url}/api/chat", json=payload,
                           timeout=timeout)
            if r.status_code == 400 and think not in (False, True):
                # model without named think levels — retry with plain boolean
                payload["think"] = True
                r = httpx.post(f"{self.settings.ollama_url}/api/chat", json=payload,
                               timeout=timeout)
            r.raise_for_status()
            return r.json()["message"]["content"].strip()
        except (httpx.HTTPError, KeyError) as e:
            log.error("Ollama call failed: %s", e)
            return None

    def _resolve_think(self, think_level: str | None):
        think_level = think_level if think_level in THINK_LEVELS else self.settings.think_level
        return False if think_level == "off" else think_level

    def make_title(self, content: str) -> str:
        """Short representative title for a history entry (fast, no thinking)."""
        if not content.strip():
            return ""
        out = self._chat(TITLE_SYSTEM, content[:1500], think=False, timeout=60)
        if not out:
            return ""
        title = out.splitlines()[0].strip().strip("「」\"'。.,!?:;")
        return title[:24]

    def refine(self, existing_prompt: str, supplement: str,
               think_level: str | None = None) -> str:
        """Merge a new voice/text supplement into an existing prompt."""
        user = f"【現有 prompt】\n{existing_prompt}\n\n【補充說明】\n{supplement}"
        out = self._chat(REFINE_SYSTEM, user, self._resolve_think(think_level))
        return out or existing_prompt

    def optimize(self, transcript: str, mode: str | None = None,
                 think_level: str | None = None) -> str:
        """Post-process a transcript. mode: prompt | clean | raw."""
        mode = mode or self.settings.mode
        if mode == "raw" or not transcript.strip():
            return transcript
        model = self.resolve_model()
        if not model:
            log.warning("No Ollama model available; returning raw transcript")
            return transcript

        if mode == "prompt":
            system = self.settings.custom_prompt_system or DEFAULT_PROMPT_SYSTEM
        else:
            system = CLEAN_SYSTEM
        out = self._chat(system, transcript, self._resolve_think(think_level))
        return out or transcript
