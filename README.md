# OpenLLM-AI-VTuber-HongYi-Li

這個專案整理了一個以 `Open-LLM-VTuber` 為前端、以課程蒸餾成果與檢索代理為後端的實驗型 AI VTuber 工作流。目標不是重做上游，而是把目前可用的整合層、額外功能，以及對上游的本地 patch 明確保存下來。

## Disclaimer

This is an unofficial AI teaching assistant inspired by Professor Hung-Yi Lee's public teaching style.

- It is not Professor Hung-Yi Lee.
- It is not an official project.
- It is not endorsed by Professor Hung-Yi Lee.

## 目前做的實驗

### 1. 將蒸餾結果接入 OpenLLM-AI-VTuber

目前的做法不是把蒸餾內容硬塞進單一 prompt，而是把 `hung-yi-lee-skill` 產出的檢索結果接到一個本地 `OpenAI-compatible` proxy，再讓 `Open-LLM-VTuber` 把它當成一般 LLM endpoint 使用。

流程如下：

```text
Open-LLM-VTuber
  -> hungyi-rag-proxy (/v1/chat/completions)
  -> hung-yi-lee-skill CLI / fallback file search
  -> upstream LLM (OpenAI-compatible API or Ollama)
  -> TTS + Live2D frontend
```

這一層的重點是：

- `hungyi-rag-proxy` 提供 `/health`、`/v1/models`、`/v1/chat/completions`
- 可以走 `openai_compatible` 或 `ollama_native`
- 先取回課程相關上下文，再轉送到上游 LLM
- 保留「非官方、非本人」的 system prompt 與對外說明

### 2. 主動播報系統，以 BTC 價格為例

新增一個獨立的 `market-announcer` 模組，用免費公開行情來源輪詢 `BTC-USDT`，再透過本地播報 API 把文字交給 VTuber 說出來。

目前版本的行為：

- 每分鐘抓一次價格並寫入本地 CSV
- 比較基準是「上一次實際播報時的價格」
- 只有當前價格和播報基準相差超過門檻才開口
- 播報內容會附帶方向與短線趨勢，例如上漲、下跌、震盪
- 文字會先清理 `_`、`#` 等不該被唸出的符號

### 3. Open-LLM-VTuber 本地播報與音訊修補

為了讓主動播報能直接進到前端，我對 `Open-LLM-VTuber` 做了兩個本地 patch：

- 新增 `/local/announce` API，能把任意文字轉成 TTS 並推送到已連線的前端
- 修補 `stream_audio`，讓 Edge TTS 產生的音訊可穩定轉成前端需要的 WAV payload，並配合嘴型音量資料

### 4. Python 3.9 相容修補

`hung-yi-lee-skill` 在這台機器上有數個 Python 3.9 與編碼相容性問題，因此補了本地 patch，包含：

- `datetime.UTC` 改為 `timezone.utc`
- 多處 `read_text()` / `write_text()` 明確指定 `encoding="utf-8"`
- `networkx` 讀圖方式調整成較保守的呼叫方式

## Repo 內容

這個 repo 目前保存的是整合層與 patch，不直接把上游 repo 重新 vendor 進來。

- [hungyi-rag-proxy](./hungyi-rag-proxy): 本地 OpenAI-compatible RAG proxy
- [market-announcer](./market-announcer): 主動播報模組，現以 BTC 價格為例
- [obs-assets](./obs-assets): OBS overlay 與公開展示用 disclaimer
- [patches](./patches): 對上游 repo 的本地修改 patch

## 為什麼用 patch

目前工作目錄同時包含兩個獨立 git repo：

- `Open-LLM-VTuber`
- `hung-yi-lee-skill`

直接把它們當一般資料夾塞進同一個新 repo，會留下 embedded repository 問題，之後 clone 下來也無法還原完整歷史與維護關係。這裡改用 patch 保存本地修改，比較誠實，也比較能長期維護。

## 如何套用

1. 先 clone 上游專案
2. 把本 repo 的 `hungyi-rag-proxy`、`market-announcer`、`obs-assets` 放到同一工作區
3. 進入各上游 repo 套用對應 patch

範例：

```powershell
git clone https://github.com/Open-LLM-VTuber/Open-LLM-VTuber --recursive
git clone https://github.com/voidful/hung-yi-lee-skill.git

cd Open-LLM-VTuber
git apply ..\patches\open-llm-vtuber.patch

cd ..\hung-yi-lee-skill
git apply ..\patches\hung-yi-lee-skill.patch
```

之後再依 [hungyi-rag-proxy/README_MVP.md](./hungyi-rag-proxy/README_MVP.md) 與 [market-announcer/README.md](./market-announcer/README.md) 啟動。

## 參考專案

- [Open-LLM-VTuber](https://github.com/Open-LLM-VTuber/Open-LLM-VTuber)
- [hung-yi-lee-skill](https://github.com/voidful/hung-yi-lee-skill)
- [FastAPI](https://github.com/fastapi/fastapi)
- [Ollama](https://github.com/ollama/ollama)

## 目前限制

- 這是一個實驗性整合，不是上游的正式分支
- `hungyi-rag-proxy` 的 `.env` 不會進版控，實際 API key 需自行配置
- `market-announcer` 目前示範的是 BTC 即時播報，不含歷史分析
