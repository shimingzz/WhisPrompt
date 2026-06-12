# WhisPrompt

把 iPhone 變成電腦的智慧麥克風:在手機上錄音,Windows 端用本地 Whisper 轉錄、
本地 LLM(Ollama)優化成乾淨的 prompt,自動複製到剪貼簿,直接貼給任何 AI 工具。

```
iPhone(PWA / 原生 App)──錄音──▶ Windows(FastAPI + GUI)
                                    │ faster-whisper(GPU)→ 逐字稿
                                    │ Ollama(gemma 等)  → 優化 prompt
                                    ▼
                              剪貼簿 / GUI / 紀錄欄
```

全程在區網內完成,語音與文字不離開你的電腦。

## 需求

- Windows + Python 3.10+(建議有 NVIDIA GPU;無 GPU 自動改用 CPU)
- [Ollama](https://ollama.com) 並至少安裝一個模型,例如 `ollama pull gemma4:12b`
- iPhone 與電腦在同一個 Wi-Fi

## 安裝(Windows)

```bat
windows\setup.bat   :: 建立 .venv 並安裝相依套件
windows\run.bat     :: 啟動 GUI(加 --headless 只跑伺服器)
```

第一次啟動會自動下載 Whisper 模型(`large-v3-turbo`)並產生本機憑證。

### 防火牆(必要,一次性)

以系統管理員執行 `windows\scripts\allow_firewall.ps1`,開放 8443/8000 進站連線;
否則手機會出現 `ERR_CONNECTION_TIMED_OUT`。
另外確認 Wi-Fi 網路設定檔是「私人」而非「公用」。

## iPhone 設定(PWA,免 Mac)

1. 開 GUI 點「iPhone 連線 / QR code」,用 iPhone Safari 開啟 **http** 設定頁網址
2. 下載並安裝憑證:設定 → 一般 → VPN 與裝置管理 → 安裝 **WhisPrompt Local CA**
3. 設定 → 一般 → 關於本機 → 憑證信任設定 → 開啟該憑證
4. 掃 QR code 開啟 **https** 錄音頁,可「加入主畫面」當成 App 使用

之後:點按鈕開始錄音(可暫停/繼續)→ 點「完成」→ 轉錄與優化結果直接顯示,
Windows 端同步顯示並(預設)自動複製 prompt 到剪貼簿。
手機與電腦端也都可以直接輸入文字按「優化」,不必錄音。

## 紀錄(記事本)

每一筆 prompt 都會永久保存(`windows/data/history.json`),
GUI 左側與手機頁面下方都有聊天式紀錄欄,可逐筆**複製 / 封存 / 刪除**,
「封存區」分頁可查看與還原已封存的紀錄。兩端共用同一份資料,即時同步。

## iPhone 原生 App(需要 Mac)

`ios/WhisPrompt/` 是完整的 Xcode 專案(Xcode 16+):

1. 在 Mac 開啟 `WhisPrompt.xcodeproj`,Signing 選自己的 Apple ID
2. 接上 iPhone 直接 Run(免費帳號的簽章每 7 天需重新安裝)
3. App 內設定填入 Windows 顯示的 `https://<IP>:8443`(憑證安裝步驟同上)

## 設定

GUI 可切換:處理模式(優化為 prompt / 僅修正錯漏字 / 原始轉錄)、
**思考等級(關/低/中/高)**、Ollama 模型、自動複製、**明暗主題**。
思考等級越高,模型會花更多推理時間補全執行細節與洞察;「關」最快。
進階設定存於 `windows/data/settings.json`(Whisper 模型、連接埠可改;
`custom_prompt_system` 留空表示使用內建的 prompt 工程提示詞)。

### 為什麼先轉文字再給 LLM?

Gemma 等本地小模型不收音訊輸入;Whisper 專職轉錄(含中英混講),
LLM 再依上下文補漏字、去贅詞、整理結構,兩段式品質最穩定。
12GB VRAM 建議搭配 q4 量化的 12B 模型,讓 Whisper 與 LLM 同時留在 GPU。
