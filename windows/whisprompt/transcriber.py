"""Local speech-to-text via faster-whisper (CTranslate2)."""
import logging
import os
import threading
from pathlib import Path

log = logging.getLogger(__name__)


def _add_cuda_dll_dirs() -> None:
    """Make pip-installed cuBLAS/cuDNN DLLs visible to CTranslate2 on Windows."""
    if os.name != "nt":
        return
    try:
        import nvidia  # namespace package from nvidia-cublas-cu12 / nvidia-cudnn-cu12
    except ImportError:
        return
    for base in nvidia.__path__:
        for bin_dir in Path(base).glob("*/bin"):
            os.add_dll_directory(str(bin_dir))
            # CTranslate2 loads cuBLAS lazily via plain LoadLibrary, which
            # ignores add_dll_directory — it searches PATH instead.
            os.environ["PATH"] = str(bin_dir) + os.pathsep + os.environ.get("PATH", "")


class Transcriber:
    """Lazy-loading wrapper around WhisperModel; safe to call from many threads."""

    def __init__(self, model_name: str = "large-v3-turbo"):
        self.model_name = model_name
        self.device = "unloaded"
        self._model = None
        self._lock = threading.Lock()

    def load(self) -> None:
        with self._lock:
            self._load_locked()

    def _load_locked(self) -> None:
        if self._model is not None:
            return
        _add_cuda_dll_dirs()
        from faster_whisper import WhisperModel

        try:
            self._model = WhisperModel(self.model_name, device="cuda", compute_type="float16")
            self.device = "cuda"
        except Exception as e:  # missing CUDA libs, OOM, no GPU...
            log.warning("CUDA load failed (%s); falling back to CPU int8", e)
            self._model = WhisperModel(self.model_name, device="cpu", compute_type="int8")
            self.device = "cpu"
        log.info("Whisper %s loaded on %s", self.model_name, self.device)

    def set_model(self, model_name: str) -> None:
        with self._lock:
            if model_name != self.model_name:
                self.model_name = model_name
                self._model = None
                self.device = "unloaded"

    def transcribe(self, audio_path: str | Path, language: str | None = None) -> dict:
        """Return {"text", "language", "duration"}. Blocking; one job at a time."""
        with self._lock:
            self._load_locked()
            segments, info = self._model.transcribe(
                str(audio_path),
                language=language or None,
                vad_filter=True,
                beam_size=5,
            )
            text = "".join(seg.text for seg in segments).strip()
        return {"text": text, "language": info.language, "duration": info.duration}
