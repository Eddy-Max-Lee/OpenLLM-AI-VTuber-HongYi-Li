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
APP_CONFIG_ROOT = ROOT.parent / "app_config"
STATE_PATH = APP_CONFIG_ROOT / "state.json"
PERSONAS_DIR = APP_CONFIG_ROOT / "personas"
ANNOUNCES_DIR = APP_CONFIG_ROOT / "announces"

DEFAULT_TEMPLATES = [
    "{label} 相對上次播報{direction}約 {change} USDT，目前約 {price} USDT，{trend}。",
    "{label} 跟上次播報相比{direction} {change_pct}%，現價約 {price} USDT，{trend}。",
    "{label} 現在約 {price} USDT，相對上次播報{direction}約 {change} USDT，{trend}。",
    "{label} 從上次播報到現在變動約 {change_pct}%，目前在 {price} USDT 附近，{trend}。",
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


def read_json(path: Path, default):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def load_state() -> dict:
    return read_json(
        STATE_PATH,
        {
            "selected_persona_id": "hungyi_tutor",
            "selected_skin_id": "mao_pro",
            "enabled_announce_ids": ["btc_usdt"],
        },
    )


def load_persona() -> dict:
    state = load_state()
    persona_id = str(state.get("selected_persona_id", "hungyi_tutor")).strip()
    return read_json(PERSONAS_DIR / f"{persona_id}.json", {})


def load_enabled_sources() -> list[dict]:
    state = load_state()
    enabled_ids = [
        str(item).strip()
        for item in state.get("enabled_announce_ids", [])
        if str(item).strip()
    ]
    sources = []
    for source_id in enabled_ids:
        data = read_json(ANNOUNCES_DIR / f"{source_id}.json", {})
        if data:
            sources.append(data)
    return sources


def get_json(url: str, timeout: int = 10) -> dict:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "hongyi-vtuber-market-announcer/0.3",
            "Accept": "application/json",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def decimal_price(value: object) -> Decimal:
    return Decimal(str(value))


def fetch_price_for_source(source: dict) -> tuple[Decimal, str]:
    provider = str(source.get("provider", "binance_ticker")).strip()
    if provider != "binance_ticker":
        raise RuntimeError(f"Unsupported provider: {provider}")

    symbol = str(source.get("symbol", "")).strip().upper()
    if not symbol:
        raise RuntimeError("symbol is required for binance_ticker source")

    data = get_json(f"https://api.binance.com/api/v3/ticker/price?symbol={symbol}")
    return decimal_price(data["price"]), "Binance"


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
    return DEFAULT_TEMPLATES


def sanitize_for_speech(text: str) -> str:
    replacements = {
        "BTC-USDT": "BTC USDT",
        "BTC_USDT": "BTC USDT",
        "ETH-USDT": "ETH USDT",
        "ETH_USDT": "ETH USDT",
        "SOL-USDT": "SOL USDT",
        "SOL_USDT": "SOL USDT",
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
    source: dict,
    price: Decimal,
    reference_price: Decimal | None,
    trend: str,
) -> str:
    template = random.choice(load_templates())
    label = str(source.get("speak_label", source.get("label", source.get("id", "市場"))))
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
            label=label,
            price=format_price(price),
            change=format_price(abs(change)),
            change_pct=format_pct(change_pct),
            direction=direction,
            trend=trend,
        )
    )


def speaker_name() -> str:
    persona = load_persona()
    return str(persona.get("speaker_name", os.getenv("SPEAKER_NAME", "市場播報"))).strip()


def post_announcement(text: str, name: str) -> dict:
    url = os.getenv("VTUBER_ANNOUNCE_URL", "http://127.0.0.1:12393/local/announce")
    payload = json.dumps(
        {
            "text": text,
            "name": name,
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
    source: dict,
    provider_name: str,
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
                    "announce_id",
                    "label",
                    "provider",
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
                source.get("id", ""),
                source.get("label", ""),
                provider_name,
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
    source: dict,
    provider_name: str,
    price: Decimal,
    reference_price: Decimal | None,
    trend: str,
    dry_run: bool,
) -> str:
    sentence = build_sentence(source, price, reference_price, trend)
    name = speaker_name()
    if dry_run:
        print(f"[dry-run] {source.get('id')} {provider_name}: {sentence}", flush=True)
    else:
        result = post_announcement(sentence, name)
        print(f"[sent] {source.get('id')} {provider_name}: {sentence} -> {result}", flush=True)
    return sentence


def main() -> int:
    load_env()
    parser = argparse.ArgumentParser(description="Run multi-source market announcements through Open-LLM-VTuber.")
    parser.add_argument("--once", action="store_true", help="Fetch one round of enabled sources and exit.")
    parser.add_argument("--dry-run", action="store_true", help="Print the sentence without speaking.")
    parser.add_argument("--force-speak", action="store_true", help="Speak even if no large move is detected.")
    parser.add_argument("--pid-file", help="Write the current process id to this file while running.")
    args = parser.parse_args()

    default_poll_interval = max(5, env_int("POLL_INTERVAL_SECONDS", 60))
    default_abs_threshold = env_decimal("LARGE_MOVE_ABS_USDT", "100")
    default_pct_threshold = env_decimal("LARGE_MOVE_PCT", "0.25")
    speak_on_first_sample = env_bool("SPEAK_ON_FIRST_SAMPLE", False)
    log_path = ROOT / os.getenv("PRICE_LOG_PATH", "btc_price_log.csv")
    reference_prices: dict[str, Decimal] = {}
    recent_samples: dict[str, list[Decimal]] = {}
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
            enabled_sources = load_enabled_sources()
            if not enabled_sources:
                print("[record] no enabled announce sources", flush=True)
            for source in enabled_sources:
                source_id = str(source.get("id", "")).strip()
                if not source_id:
                    continue
                try:
                    price, provider_name = fetch_price_for_source(source)
                    samples = recent_samples.setdefault(source_id, [])
                    samples.append(price)
                    recent_samples[source_id] = samples[-5:]
                    trend = describe_trend(recent_samples[source_id])
                    reference_price = reference_prices.get(source_id)
                    abs_threshold = env_decimal(
                        "LARGE_MOVE_ABS_USDT",
                        str(source.get("threshold_abs_usdt", default_abs_threshold)),
                    )
                    pct_threshold = env_decimal(
                        "LARGE_MOVE_PCT",
                        str(source.get("threshold_pct", default_pct_threshold)),
                    )
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
                        announce_price(
                            source,
                            provider_name,
                            price,
                            reference_price,
                            trend,
                            dry_run=args.dry_run,
                        )
                        action = "speak-dry-run" if args.dry_run else "speak"
                    else:
                        print(
                            f"[record] {source_id} {provider_name}: {format_price(price)} USDT ({reason})",
                            flush=True,
                        )
                        action = "record"

                    append_price_log(
                        log_path,
                        source,
                        provider_name,
                        price,
                        reference_price,
                        action,
                        reason,
                    )
                    if reference_price is None or speak:
                        reference_prices[source_id] = price
                except Exception as exc:
                    print(f"[error] {source_id} {type(exc).__name__}: {exc}", flush=True)

            if args.once:
                return 0

            sleep_seconds = default_poll_interval
            if enabled_sources:
                sleep_seconds = max(
                    5,
                    min(
                        int(source.get("poll_interval_seconds", default_poll_interval))
                        for source in enabled_sources
                    ),
                )
            for _ in range(sleep_seconds):
                if stop_requested:
                    break
                time.sleep(1)
    finally:
        if pid_path and pid_path.exists() and pid_path.read_text(encoding="utf-8").strip() == str(os.getpid()):
            pid_path.unlink()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
