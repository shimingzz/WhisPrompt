"""Persistent settings stored as JSON under windows/data/."""
import json
from dataclasses import dataclass, asdict, field
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
RECORDINGS_DIR = DATA_DIR / "recordings"
CERTS_DIR = DATA_DIR / "certs"
SETTINGS_FILE = DATA_DIR / "settings.json"

DEFAULT_PROMPT_SYSTEM = """\
你是一個語音轉文字的後處理助手。使用者會給你一段由語音辨識產生的逐字稿,\
可能包含辨識錯誤、漏字、贅字與口語填充詞。
你的任務:將它整理成一段清晰、結構化、可直接貼給 AI 工具使用的 prompt。
規則:
1. 依上下文修正明顯的辨識錯誤與漏字。
2. 移除「嗯」「呃」「然後就是」等口語贅詞。
3. 保留使用者的原意與所有具體要求,不要新增使用者沒說的需求。
4. 使用與逐字稿相同的語言輸出。
5. 只輸出整理後的 prompt 本身,不要任何解釋、前言或 markdown 圍欄。"""

CLEAN_SYSTEM = """\
你是一個語音轉文字的後處理助手。修正下面逐字稿中明顯的辨識錯誤、漏字與口語贅詞,\
但保持原本的語句結構與語氣,不要改寫或重組。\
使用與逐字稿相同的語言。只輸出修正後的文字,不要任何解釋。"""

MODES = {
    "prompt": "優化為 prompt",
    "clean": "僅修正錯漏字",
    "raw": "原始轉錄",
}


@dataclass
class Settings:
    whisper_model: str = "large-v3-turbo"
    whisper_language: str = ""  # "" = auto-detect
    ollama_url: str = "http://127.0.0.1:11434"
    ollama_model: str = ""  # "" = auto-pick at startup
    mode: str = "prompt"
    https_port: int = 8443
    http_port: int = 8000
    auto_copy: bool = True
    prompt_system: str = DEFAULT_PROMPT_SYSTEM

    @classmethod
    def load(cls) -> "Settings":
        if SETTINGS_FILE.exists():
            try:
                data = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
                known = {f.name for f in cls.__dataclass_fields__.values()}
                return cls(**{k: v for k, v in data.items() if k in known})
            except (json.JSONDecodeError, TypeError):
                pass
        return cls()

    def save(self) -> None:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        SETTINGS_FILE.write_text(
            json.dumps(asdict(self), ensure_ascii=False, indent=2), encoding="utf-8"
        )


def ensure_dirs() -> None:
    for d in (DATA_DIR, RECORDINGS_DIR, CERTS_DIR):
        d.mkdir(parents=True, exist_ok=True)
