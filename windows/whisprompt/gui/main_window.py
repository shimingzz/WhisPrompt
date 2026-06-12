"""PySide6 desktop UI: notebook-style prompt history, live results, clipboard."""
import io
import threading

import qrcode
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QGuiApplication, QPixmap
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QDialog, QGroupBox, QHBoxLayout,
    QLabel, QListWidget, QListWidgetItem, QMainWindow, QMessageBox,
    QPlainTextEdit, QPushButton, QSplitter, QStatusBar, QTabBar,
    QVBoxLayout, QWidget,
)

from ..config import MODES
from ..server import Pipeline, Result, ServerManager


def _qr_pixmap(url: str, size: int = 280) -> QPixmap:
    img = qrcode.make(url)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    pix = QPixmap()
    pix.loadFromData(buf.getvalue())
    return pix.scaled(size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation)


class QRDialog(QDialog):
    def __init__(self, app_url: str, helper_url: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("iPhone 連線")
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("1. 首次使用:先用 iPhone 開啟下方網址安裝憑證"))
        helper = QLabel(f"<b>{helper_url}</b>")
        helper.setTextInteractionFlags(Qt.TextSelectableByMouse)
        layout.addWidget(helper)
        layout.addWidget(QLabel("2. 之後掃描 QR code 開啟錄音頁(可加入主畫面):"))
        qr = QLabel()
        qr.setPixmap(_qr_pixmap(app_url))
        qr.setAlignment(Qt.AlignCenter)
        layout.addWidget(qr)
        link = QLabel(f"<b>{app_url}</b>")
        link.setTextInteractionFlags(Qt.TextSelectableByMouse)
        link.setAlignment(Qt.AlignCenter)
        layout.addWidget(link)


class HistoryItemWidget(QWidget):
    """One chat-bubble-style entry: time + preview + archive/delete buttons."""

    def __init__(self, entry: dict, on_archive, on_delete):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(2)

        head = QHBoxLayout()
        time_label = QLabel(entry["timestamp"])
        time_label.setStyleSheet("color: gray; font-size: 11px;")
        head.addWidget(time_label)
        head.addStretch()

        archive_btn = QPushButton("還原" if entry.get("archived") else "封存")
        archive_btn.setFixedHeight(22)
        archive_btn.setStyleSheet("font-size: 11px; padding: 1px 8px;")
        archive_btn.clicked.connect(lambda: on_archive(entry))
        head.addWidget(archive_btn)

        delete_btn = QPushButton("刪除")
        delete_btn.setFixedHeight(22)
        delete_btn.setStyleSheet("font-size: 11px; padding: 1px 8px; color: #c0392b;")
        delete_btn.clicked.connect(lambda: on_delete(entry))
        head.addWidget(delete_btn)
        layout.addLayout(head)

        preview = (entry.get("prompt") or "").replace("\n", " ")
        if len(preview) > 90:
            preview = preview[:90] + "…"
        text = QLabel(preview or "(空白)")
        text.setWordWrap(True)
        layout.addWidget(text)


class MainWindow(QMainWindow):
    result_ready = Signal(object)
    status_changed = Signal(str)
    models_loaded = Signal(list, str)
    history_changed = Signal()

    def __init__(self, pipeline: Pipeline, manager: ServerManager):
        super().__init__()
        self.pipeline = pipeline
        self.manager = manager
        self.settings = pipeline.settings
        self.view_archived = False
        self.setWindowTitle("WhisPrompt")
        self.resize(1080, 680)

        pipeline.on_result = self.result_ready.emit
        pipeline.on_status = self.status_changed.emit
        pipeline.on_history_changed = self.history_changed.emit
        self.result_ready.connect(self._on_result)
        self.status_changed.connect(self._on_status)
        self.models_loaded.connect(self._apply_models)
        self.history_changed.connect(lambda: self._refresh_history(keep_selection=True))

        self._build_ui()
        self._refresh_history()
        self._load_ollama_models()
        threading.Thread(target=self._preload_whisper, daemon=True).start()

    # ---- UI construction -------------------------------------------------
    def _build_ui(self) -> None:
        central = QWidget()
        root = QVBoxLayout(central)

        top = QHBoxLayout()
        self.conn_btn = QPushButton("📱 iPhone 連線 / QR code")
        self.conn_btn.clicked.connect(self._show_qr)
        top.addWidget(self.conn_btn)
        top.addStretch()

        top.addWidget(QLabel("模式:"))
        self.mode_combo = QComboBox()
        for key, label in MODES.items():
            self.mode_combo.addItem(label, key)
        self.mode_combo.setCurrentIndex(list(MODES).index(self.settings.mode))
        self.mode_combo.currentIndexChanged.connect(self._mode_changed)
        top.addWidget(self.mode_combo)

        top.addWidget(QLabel("LLM:"))
        self.model_combo = QComboBox()
        self.model_combo.setMinimumWidth(220)
        self.model_combo.currentTextChanged.connect(self._model_changed)
        top.addWidget(self.model_combo)

        self.auto_copy = QCheckBox("自動複製 prompt")
        self.auto_copy.setChecked(self.settings.auto_copy)
        self.auto_copy.toggled.connect(self._auto_copy_changed)
        top.addWidget(self.auto_copy)
        root.addLayout(top)

        split = QSplitter()

        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        self.tabs = QTabBar()
        self.tabs.addTab("紀錄")
        self.tabs.addTab("封存區")
        self.tabs.currentChanged.connect(self._tab_changed)
        left_layout.addWidget(self.tabs)
        self.history_list = QListWidget()
        self.history_list.setWordWrap(True)
        self.history_list.currentRowChanged.connect(self._show_history_item)
        left_layout.addWidget(self.history_list)
        split.addWidget(left)

        right = QWidget()
        right_layout = QVBoxLayout(right)

        prompt_box = QGroupBox("優化後 Prompt")
        pb_layout = QVBoxLayout(prompt_box)
        self.prompt_edit = QPlainTextEdit()
        self.prompt_edit.setReadOnly(True)
        pb_layout.addWidget(self.prompt_edit)
        btn_row = QHBoxLayout()
        copy_prompt = QPushButton("複製 Prompt")
        copy_prompt.clicked.connect(lambda: self._copy(self.prompt_edit.toPlainText()))
        btn_row.addWidget(copy_prompt)
        copy_raw = QPushButton("複製原始轉錄")
        copy_raw.clicked.connect(lambda: self._copy(self.transcript_edit.toPlainText()))
        btn_row.addWidget(copy_raw)
        btn_row.addStretch()
        pb_layout.addLayout(btn_row)
        right_layout.addWidget(prompt_box, stretch=3)

        tr_box = QGroupBox("原始轉錄")
        tr_layout = QVBoxLayout(tr_box)
        self.transcript_edit = QPlainTextEdit()
        self.transcript_edit.setReadOnly(True)
        tr_layout.addWidget(self.transcript_edit)
        right_layout.addWidget(tr_box, stretch=2)

        split.addWidget(right)
        split.setSizes([340, 740])
        root.addWidget(split)

        self.setCentralWidget(central)
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("啟動中...")

    # ---- history panel ---------------------------------------------------
    def _tab_changed(self, index: int) -> None:
        self.view_archived = index == 1
        self._refresh_history()

    def _refresh_history(self, select_id: str | None = None,
                         keep_selection: bool = False) -> None:
        if keep_selection and select_id is None:
            current = self.history_list.currentItem()
            if current:
                select_id = current.data(Qt.UserRole)["id"]

        self.history_list.blockSignals(True)
        self.history_list.clear()
        entries = self.pipeline.store.list(archived=self.view_archived)
        select_row = 0
        for row, entry in enumerate(reversed(entries)):  # newest first
            item = QListWidgetItem()
            item.setData(Qt.UserRole, entry)
            widget = HistoryItemWidget(entry, self._archive_entry, self._delete_entry)
            item.setSizeHint(widget.sizeHint())
            self.history_list.addItem(item)
            self.history_list.setItemWidget(item, widget)
            if select_id and entry["id"] == select_id:
                select_row = row
        self.history_list.blockSignals(False)

        if self.history_list.count():
            self.history_list.setCurrentRow(select_row)
        else:
            self.prompt_edit.clear()
            self.transcript_edit.clear()

    def _archive_entry(self, entry: dict) -> None:
        self.pipeline.store.set_archived(entry["id"], not entry.get("archived", False))
        self._refresh_history()

    def _delete_entry(self, entry: dict) -> None:
        preview = (entry.get("prompt") or "")[:40]
        if QMessageBox.question(self, "刪除紀錄", f"確定刪除這筆紀錄?\n\n{preview}…") \
                == QMessageBox.StandardButton.Yes:
            self.pipeline.store.delete(entry["id"])
            self._refresh_history()

    def _show_history_item(self, row: int) -> None:
        if row < 0:
            return
        entry: dict = self.history_list.item(row).data(Qt.UserRole)
        self.prompt_edit.setPlainText(entry.get("prompt", ""))
        self.transcript_edit.setPlainText(entry.get("transcript", ""))

    # ---- slots -----------------------------------------------------------
    def _show_qr(self) -> None:
        QRDialog(self.manager.app_url, self.manager.helper_url, self).exec()

    def _mode_changed(self) -> None:
        self.settings.mode = self.mode_combo.currentData()
        self.settings.save()

    def _model_changed(self, name: str) -> None:
        if name:
            self.settings.ollama_model = name
            self.settings.save()

    def _auto_copy_changed(self, checked: bool) -> None:
        self.settings.auto_copy = checked
        self.settings.save()

    def _copy(self, text: str) -> None:
        QGuiApplication.clipboard().setText(text)
        self.status_bar.showMessage("已複製到剪貼簿", 2000)

    def _on_status(self, msg: str) -> None:
        self.status_bar.showMessage(msg)

    def _on_result(self, result: Result) -> None:
        if self.view_archived:
            self.tabs.setCurrentIndex(0)  # jump back to active view
        self._refresh_history(select_id=result.id)
        if self.settings.auto_copy and result.prompt:
            self._copy(result.prompt)

    def _apply_models(self, models: list, default: str) -> None:
        self.model_combo.blockSignals(True)
        self.model_combo.clear()
        self.model_combo.addItems(models)
        if default in models:
            self.model_combo.setCurrentText(default)
        self.model_combo.blockSignals(False)
        if default and not self.settings.ollama_model:
            self.settings.ollama_model = default
            self.settings.save()

    # ---- background ------------------------------------------------------
    def _load_ollama_models(self) -> None:
        def work():
            models = self.pipeline.llm.list_models()
            default = self.settings.ollama_model or self.pipeline.llm.pick_default_model()
            self.models_loaded.emit(models, default)

        threading.Thread(target=work, daemon=True).start()

    def _preload_whisper(self) -> None:
        self.status_changed.emit(f"載入 Whisper 模型 {self.settings.whisper_model} 中...")
        self.pipeline.transcriber.load()
        self.status_changed.emit(
            f"就緒 — Whisper ({self.pipeline.transcriber.device}) · iPhone 連線: {self.manager.app_url}"
        )


def run_gui(pipeline: Pipeline) -> int:
    app = QApplication([])
    manager = ServerManager(pipeline)
    manager.start()
    win = MainWindow(pipeline, manager)
    win.show()
    code = app.exec()
    manager.stop()
    return code
