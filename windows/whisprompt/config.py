"""Persistent settings stored as JSON under windows/data/."""
import json
from dataclasses import dataclass, asdict, field
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
RECORDINGS_DIR = DATA_DIR / "recordings"
CERTS_DIR = DATA_DIR / "certs"
SETTINGS_FILE = DATA_DIR / "settings.json"

DEFAULT_PROMPT_SYSTEM = """\
你是資深的 prompt 工程師。使用者提供一段原始需求描述(可能來自語音辨識,\
含辨識錯誤、漏字與口語贅詞),你要把它改寫成一份高品質、可直接交給 AI 工具執行的 prompt。

改寫方法:
1. 修正辨識錯誤與漏字,去除口語贅詞。
2. 釐清目標:推斷使用者真正想完成的事,把模糊的描述明確化。
3. 主動補全執行所需的合理細節:具體做法或步驟、輸入與輸出格式、技術選型、\
限制條件、品質與驗收標準。原則:站在「執行這個任務的 AI」的角度,\
思考它需要知道什麼才能一次做對,把這些資訊合理地寫進 prompt;\
但不可偏離使用者原意,不可虛構使用者沒提過的具體事實(如檔名、數字)。
4. 結構化輸出:先一句話講清楚任務目標,再依需要分段或條列說明要求與細節。\
簡單的需求就保持簡潔,不要硬塞結構。
5. 使用與輸入相同的語言輸出(中文輸入就輸出繁體中文)。
6. 只輸出改寫後的 prompt 本身,不要任何解釋、前言或 markdown 圍欄。

示範:
輸入:「我想要做一個網站可以讓大家上傳食譜然後可以搜尋」
輸出:
「請幫我設計並實作一個食譜分享網站,需求如下:

功能需求:
1. 使用者可以註冊登入,上傳自己的食譜(標題、食材清單、步驟說明、成品照片)。
2. 提供搜尋功能:可依關鍵字、食材、料理分類搜尋食譜。
3. 食譜列表頁與詳細頁,支援手機瀏覽(響應式設計)。

技術建議:
- 請先提出技術選型(前端框架、後端語言、資料庫)並說明理由,再開始實作。
- 圖片上傳需要做大小限制與格式驗證。

請先規劃資料模型與頁面結構,確認後再逐步實作。」"""

TITLE_SYSTEM = """\
為使用者提供的內容取一個簡短的標題,要能代表其核心主題,不超過 12 個字。\
使用與內容相同的語言。只輸出標題本身,不要引號、句號或任何其他文字。"""

REFINE_SYSTEM = """\
你是資深的 prompt 工程師。使用者提供一份「現有 prompt」與一段「補充說明」\
(補充可能來自語音辨識,含辨識錯誤與口語贅詞)。
請把補充說明融合進現有 prompt,輸出更新後的完整 prompt:
1. 保留現有 prompt 的目標與結構,除非補充內容明確要求改變。
2. 修正補充說明中的辨識錯誤與贅詞,把其要求合理整合到適當的段落。
3. 若補充與原內容衝突,以補充說明為準。
4. 使用與輸入相同的語言輸出。
5. 只輸出更新後的完整 prompt 本身,不要任何解釋或前言。"""

CLEAN_SYSTEM = """\
你是一個語音轉文字的後處理助手。修正下面逐字稿中明顯的辨識錯誤、漏字與口語贅詞,\
但保持原本的語句結構與語氣,不要改寫或重組。\
使用與逐字稿相同的語言。只輸出修正後的文字,不要任何解釋。"""

MODES = {
    "prompt": "優化為 prompt",
    "clean": "僅修正錯漏字",
    "raw": "原始轉錄",
}

# Ollama `think` values; gemma4 accepts low/medium/high natively.
THINK_LEVELS = {
    "off": "關",
    "low": "低",
    "medium": "中",
    "high": "高",
}


@dataclass
class Settings:
    whisper_model: str = "large-v3-turbo"
    whisper_language: str = ""  # "" = auto-detect
    ollama_url: str = "http://127.0.0.1:11434"
    ollama_model: str = ""  # "" = auto-pick at startup
    mode: str = "prompt"
    think_level: str = "low"
    theme: str = "light"
    https_port: int = 8443
    http_port: int = 8000
    auto_copy: bool = True
    # Empty = use the built-in DEFAULT_PROMPT_SYSTEM (so improvements to the
    # default reach existing installs; set a value here only to customize).
    custom_prompt_system: str = ""

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
