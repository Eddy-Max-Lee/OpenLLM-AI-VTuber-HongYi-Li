# BTC Price Announcer

This local helper records the current BTC-USDT price every minute and only speaks through Open-LLM-VTuber when the move from the last announced reference price is large enough.

It uses free public price endpoints and only writes a local CSV log. No paid historical data source is required.

Default source order:

1. Binance public ticker price endpoint
2. CoinGecko simple price endpoint
3. Coinbase product ticker endpoint

Default trigger:

- Record every `60` seconds.
- Speak only when BTC-USDT moves at least `100 USDT` or `0.25%` from the last announced reference price.
- The first sample is only used as the initial reference and is not spoken.
- After a real announcement, the reference price resets to the announced price.
- Spoken templates include the direction and a short recent trend such as `短線趨勢偏上`, `短線趨勢偏下`, or `短線還在震盪`.

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
