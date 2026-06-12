# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

WhisPrompt turns an iPhone into a wireless microphone for a Windows PC: audio is recorded on
the phone, uploaded over LAN HTTPS, transcribed locally with faster-whisper, then post-processed
by a local Ollama LLM into a clean prompt that lands in the Windows clipboard.

## Commands

```bat
windows\setup.bat                          :: create .venv + install deps
windows\run.bat                            :: launch GUI (servers start inside it)
windows\run.bat --headless                 :: servers only, no GUI
F:\WhisPrompt\.venv\Scripts\python -m whisprompt.main   :: same, from windows/ as cwd
```

There is no test suite yet. Quick pipeline check without an iPhone:
generate a speech WAV (e.g. PowerShell `System.Speech` TTS), then POST it to
`https://localhost:8443/api/audio` with `-SkipCertificateCheck`/`curl -k`.

## Architecture

Two clients, one Python backend (`windows/whisprompt/`):

- `server.py` is the hub: `Pipeline` (audio file → `Transcriber` → `OllamaClient` → `Result`),
  the FastAPI upload/status API, and `ServerManager` which runs TWO uvicorn servers in daemon
  threads — HTTPS :8443 (PWA + API; mic access requires a secure context) and plain HTTP :8000
  (one-time page for installing the local CA on the iPhone).
- `certs.py` generates a local CA + server cert (SAN = current LAN IPs, auto-regenerated when
  the IP changes). The CA must be installed/trusted on the iPhone once.
- `transcriber.py` wraps faster-whisper; tries CUDA float16, falls back to CPU int8. On Windows
  the cuBLAS/cuDNN DLLs come from the pip `nvidia-*` packages via `os.add_dll_directory`.
- `llm.py` calls the Ollama HTTP API. Mode strings: `prompt` (rewrite as clean prompt),
  `clean` (fix typos only), `raw` (skip LLM). System prompts live in `config.py`.
- `gui/main_window.py` (PySide6): worker threads communicate with Qt ONLY via signals
  (`result_ready`/`status_changed`/`models_loaded`); `Pipeline.on_result` is wired to a signal emit.
- `web/` is the PWA served by StaticFiles at `/` — plain JS, no build step.
- `ios/WhisPrompt/` is a SwiftUI Xcode project (objectVersion 77, filesystem-synchronized
  groups — new source files are picked up automatically, no pbxproj edits needed). It talks to
  the same `/api/audio` + `/api/status` endpoints.

Runtime state (settings.json, recordings, certs) lives in `windows/data/` — gitignored, never
commit it.

## Constraints

- Whisper + LLM share a 12 GB GPU: prefer q4-quant 12B Ollama models; `llm.py`
  `pick_default_model` encodes that preference.
- UI text is Traditional Chinese (zh-Hant); keep new user-facing strings consistent.
- Python is 3.14 — check wheel availability before adding native-extension deps.
