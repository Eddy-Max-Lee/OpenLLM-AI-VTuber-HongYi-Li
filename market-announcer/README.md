# Market Announcer

This helper reads shared control state from `app_config/state.json` and announces every enabled source through Open-LLM-VTuber.

Current sample sources:

- `btc_usdt`
- `eth_usdt`
- `sol_usdt`

Behavior:

- Poll enabled sources every `60` seconds by default.
- Keep one reference price per source.
- Speak only when the latest price crosses that source's configured absolute or percentage threshold.
- Reset the reference only after a real announcement for that source.
- Use the currently selected persona's `speaker_name` as the display name.

Configuration is in `.env`:

```env
POLL_INTERVAL_SECONDS=60
LARGE_MOVE_ABS_USDT=100
LARGE_MOVE_PCT=0.25
PRICE_LOG_PATH=btc_price_log.csv
SPEAK_ON_FIRST_SAMPLE=false
```

Start the managed background announcer:

```powershell
cd E:\VTUBER\hong-yi\market-announcer
powershell -ExecutionPolicy Bypass -File .\start_announcer.ps1
```

Stop it:

```powershell
powershell -ExecutionPolicy Bypass -File .\stop_announcer.ps1
```

Check status:

```powershell
powershell -ExecutionPolicy Bypass -File .\status_announcer.ps1
```

Dry run one sample without speaking:

```powershell
..\Open-LLM-VTuber\.venv\Scripts\python.exe .\btc_price_announcer.py --once --dry-run
```

Force one test sentence without waiting for a large move:

```powershell
..\Open-LLM-VTuber\.venv\Scripts\python.exe .\btc_price_announcer.py --once --dry-run --force-speak
```
