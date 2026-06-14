from __future__ import annotations

import argparse
import csv
import json
import os
import random
import re
import signal
import time
import urllib.request
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path


ROOT = Path(__file__).resolve().parent
DEFAULT_TEMPLATES = [
    "市場波動提醒，BTC USDT 相對上次播報{direction}約 {change} USDT，目前約 {price} USDT，{trend}。",
    "BTC USDT 跟上次播報相比{direction} {change_pct}%，現價約 {price} USDT，{trend}。",
    "價格跳動比較明顯，BTC USDT 目前約 {price} USDT，相對上次播報{direction}約 {change} USDT，{trend}。",
    "更新一下，BTC USDT 從上次播報到現在變動約 {change_pct}%，目前在 {price} USDT 附近，{trend}。",
]


def load_env() -> None:
    env_path = ROOT / ".env"
    if not env_path.exists():
        env_path = ROOT / ".env.example"
    if not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


def env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


def env_decimal(name: str, default: str) -> Decimal:
    try:
        return Decimal(os.getenv(name, default))
    except (InvalidOperation, TypeError):
        return Decimal(default)


def get_json(url: str, timeout: int = 10) -> dict:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "hongyi-vtuber-market-announcer/0.2",
            "Accept": "application/json",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def decimal_price(value: object) -> Decimal:
    return Decimal(str(value))


def fetch_binance_btcusdt() -> tuple[Decimal, str]:
    data = get_json("https://api.binance.com/api/v3/ticker/price?symbol=BTCUSDT")
    return decimal_price(data["price"]), "Binance"


def fetch_coingecko_btc_usd() -> tuple[Decimal, str]:
    data = get_json(
        "https://api.coingecko.com/api/v3/simple/price"
        "?ids=bitcoin&vs_currencies=usd"
    )
    return decimal_price(data["bitcoin"]["usd"]), "CoinGecko"


def fetch_coinbase_btc_usdt() -> tuple[Decimal, str]:
    data = get_json("https://api.exchange.coinbase.com/products/BTC-USDT/ticker")
    return decimal_price(data["price"]), "Coinbase"


def fetch_price() -> tuple[Decimal, str]:
    errors: list[str] = []
    for fetcher in (fetch_binance_btcusdt, fetch_coingecko_btc_usd, fetch_coinbase_btc_usdt):
        try:
            return fetcher()
        except Exception as exc:
            errors.append(f"{fetcher.__name__}: {type(exc).__name__}: {exc}")
    raise RuntimeError("All price sources failed: " + " | ".join(errors))


def format_price(price: Decimal) -> str:
    quantized = price.quantize(Decimal("0.01"))
    whole, dot, frac = f"{quantized:f}".partition(".")
    groups = []
    while whole:
        groups.append(whole[-3:])
        whole = whole[:-3]
    return ",".join(reversed(groups)) + dot + frac


def format_pct(value: Decimal) -> str:
    return f"{value.quantize(Decimal('0.01')):f}"


def load_templates() -> list[str]:
    raw_templates = os.getenv("SPEAK_TEMPLATES", "").strip()
    if raw_templates:
        templates = [
            item.strip()
            for item in re.split(r"\r?\n|\|", raw_templates)
            if item.strip()
        ]
        if templates:
            return templates

    single_template = os.getenv("SPEAK_TEMPLATE", "").strip()
    if single_template:
        return [single_template]
    return DEFAULT_TEMPLATES


def sanitize_for_speech(text: str) -> str:
    replacements = {
        "BTC-USDT": "BTC USDT",
        "BTC_USDT": "BTC USDT",
        "#": "",
        "_": " ",
        "*": "",
        "`": "",
        "[": "",
        "]": "",
        "(": "",
        ")": "",
        "{": "",
        "}": "",
        "<": "",
        ">": "",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"\s+([，。！？、,.!?])", r"\1", text)
    return text.strip()


def describe_trend(samples: list[Decimal]) -> str:
    if len(samples) < 3:
        return "短線趨勢還不明顯"

    first = samples[0]
    last = samples[-1]
    change_pct = (abs(last - first) / first * Decimal("100")) if first else Decimal("0")
    if change_pct < Decimal("0.03"):
        return "短線還在震盪"
    return "短線趨勢偏上" if last > first else "短線趨勢偏下"


def build_sentence(
    price: Decimal,
    reference_price: Decimal | None = None,
    trend: str = "短線趨勢還不明顯",
) -> str:
    template = random.choice(load_templates())
    if reference_price is None:
        change = Decimal("0")
        change_pct = Decimal("0")
        direction = "更新"
    else:
        change = price - reference_price
        change_pct = (abs(change) / reference_price * Decimal("100")) if reference_price else Decimal("0")
        direction = "上漲" if change > 0 else "下跌"

    return sanitize_for_speech(
        template.format(
            price=format_price(price),
            change=format_price(abs(change)),
            change_pct=format_pct(change_pct),
            direction=direction,
            trend=trend,
        )
    )


def post_announcement(text: str) -> dict:
    url = os.getenv("VTUBER_ANNOUNCE_URL", "http://127.0.0.1:12393/local/announce")
    payload = json.dumps(
        {
            "text": text,
            "name": os.getenv("SPEAKER_NAME", "市場播報"),
        },
        ensure_ascii=False,
    ).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=payload,
        method="POST",
        headers={
            "Content-Type": "application/json; charset=utf-8",
            "Accept": "application/json",
        },
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def append_price_log(
    path: Path,
    source: str,
    price: Decimal,
    reference_price: Decimal | None,
    action: str,
    reason: str,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    file_exists = path.exists()
    change = price - reference_price if reference_price is not None else Decimal("0")
    change_pct = (
        (abs(change) / reference_price * Decimal("100"))
        if reference_price not in (None, Decimal("0"))
        else Decimal("0")
    )

    with path.open("a", encoding="utf-8", newline="") as file:
        writer = csv.writer(file)
        if not file_exists:
            writer.writerow(
                [
                    "timestamp_utc",
                    "source",
                    "price",
                    "reference_price",
                    "change_since_reference_usdt",
                    "change_since_reference_pct",
                    "action",
                    "reason",
                ]
            )
        writer.writerow(
            [
                datetime.now(timezone.utc).isoformat(timespec="seconds"),
                source,
                f"{price:f}",
                f"{reference_price:f}" if reference_price is not None else "",
                f"{change:f}",
                f"{change_pct.quantize(Decimal('0.0001')):f}",
                action,
                reason,
            ]
        )


def should_announce(
    price: Decimal,
    reference_price: Decimal | None,
    abs_threshold: Decimal,
    pct_threshold: Decimal,
    speak_on_first_sample: bool,
) -> tuple[bool, str]:
    if reference_price is None:
        if speak_on_first_sample:
            return True, "first-sample"
        return False, "initial-reference"

    abs_change = abs(price - reference_price)
    pct_change = (abs_change / reference_price * Decimal("100")) if reference_price else Decimal("0")
    if abs_threshold > 0 and abs_change >= abs_threshold:
        return True, f"abs-change>={abs_threshold}"
    if pct_threshold > 0 and pct_change >= pct_threshold:
        return True, f"pct-change>={pct_threshold}"
    return False, f"below-threshold abs={format_price(abs_change)} pct={format_pct(pct_change)}"


def announce_price(
    price: Decimal,
    source: str,
    reference_price: Decimal | None,
    trend: str,
    dry_run: bool = False,
) -> str:
    sentence = build_sentence(price, reference_price, trend)
    if dry_run:
        print(f"[dry-run] {source}: {sentence}", flush=True)
    else:
        result = post_announcement(sentence)
        print(f"[sent] {source}: {sentence} -> {result}", flush=True)
    return sentence


def main() -> int:
    load_env()
    parser = argparse.ArgumentParser(description="Announce BTC-USDT price through Open-LLM-VTuber.")
    parser.add_argument("--once", action="store_true", help="Fetch one price sample and exit.")
    parser.add_argument("--dry-run", action="store_true", help="Print the sentence without speaking.")
    parser.add_argument("--force-speak", action="store_true", help="Speak even if no large move is detected.")
    parser.add_argument("--pid-file", help="Write the current process id to this file while running.")
    args = parser.parse_args()

    poll_interval = max(5, env_int("POLL_INTERVAL_SECONDS", 60))
    abs_threshold = env_decimal("LARGE_MOVE_ABS_USDT", "100")
    pct_threshold = env_decimal("LARGE_MOVE_PCT", "0.25")
    speak_on_first_sample = env_bool("SPEAK_ON_FIRST_SAMPLE", False)
    log_path = ROOT / os.getenv("PRICE_LOG_PATH", "btc_price_log.csv")
    reference_price: Decimal | None = None
    recent_samples: list[Decimal] = []
    stop_requested = False

    def request_stop(signum, frame):
        nonlocal stop_requested
        stop_requested = True

    signal.signal(signal.SIGTERM, request_stop)
    signal.signal(signal.SIGINT, request_stop)

    pid_path = Path(args.pid_file) if args.pid_file else None
    if pid_path:
        pid_path.write_text(str(os.getpid()), encoding="utf-8")

    try:
        while not stop_requested:
            try:
                price, source = fetch_price()
                recent_samples.append(price)
                recent_samples = recent_samples[-5:]
                trend = describe_trend(recent_samples)
                speak, reason = should_announce(
                    price,
                    reference_price,
                    abs_threshold,
                    pct_threshold,
                    speak_on_first_sample,
                )
                if args.force_speak:
                    speak, reason = True, "force-speak"

                if speak:
                    announce_price(price, source, reference_price, trend, dry_run=args.dry_run)
                    action = "speak-dry-run" if args.dry_run else "speak"
                else:
                    print(f"[record] {source}: {format_price(price)} USDT ({reason})", flush=True)
                    action = "record"

                append_price_log(log_path, source, price, reference_price, action, reason)
                if reference_price is None or speak:
                    reference_price = price
            except Exception as exc:
                print(f"[error] {type(exc).__name__}: {exc}", flush=True)

            if args.once:
                return 0

            for _ in range(poll_interval):
                if stop_requested:
                    break
                time.sleep(1)
    finally:
        if pid_path and pid_path.exists() and pid_path.read_text(encoding="utf-8").strip() == str(os.getpid()):
            pid_path.unlink()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
