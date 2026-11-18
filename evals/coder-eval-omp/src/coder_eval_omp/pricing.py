"""Hand-maintained per-million-token USD rates for the models the Omp arm runs.

Nothing here is fetched at run time: `coder_eval`'s model catalog reports
which providers exist, not what they charge, and catalog presence is not a
price. `prices.json` beside this module is a dated snapshot a person updates
by hand, keyed by the model identifier exactly as `omp_configs/*.yml` and an
experiment's `agent.model` spell it (`<gateway>/<provider>/<model>`, for
example `vercel-ai-gateway/zai/glm-5.3`).

A row may carry more than one rate per bucket. The gateway's own endpoints
publish prompt-length tiers (Luna steps at 272,001 prompt tokens) and
peak-hour multipliers (DeepSeek's first-party endpoint doubles its rates
inside two UTC windows on weekdays). Both are properties of the request, and
the reducer keeps each assistant message's own token counts and timestamp, so
`cost_usd` can apply them per message instead of averaging across a run.

Pure — no `coder_eval` import, same reasoning as `rpc.py`.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import NamedTuple

def _default_prices_path() -> Path:
    """Where `prices.json` sits: beside this module once installed, or beside
    `pyproject.toml` in this checkout.

    `[tool.hatch.build.targets.wheel.force-include]` copies the committed
    `evals/coder-eval-omp/prices.json` to `coder_eval_omp/prices.json` at
    build time, so an installed package finds it as this module's own
    sibling. Running from source in this repo never runs that build step, so
    the committed path is tried first and this checkout's is the fallback.
    """
    installed = Path(__file__).parent / "prices.json"
    if installed.is_file():
        return installed
    return Path(__file__).parent.parent.parent / "prices.json"


#: The table this module loads by default. A caller passing its own `prices`
#: (the unit tests) never touches the file.
PRICES_PATH = _default_prices_path()

#: `cost_usd`'s return for a model with no row in the table. Never a silent
#: `0.0` — a missing price and a free run must not read the same.
UNREPORTED = "unreported"

#: The buckets `rpc.USAGE_KEYS` fills, in the order a rate card names them.
BUCKETS = (
    "uncached_input_tokens",
    "output_tokens",
    "cache_read_input_tokens",
    "cache_creation_input_tokens",
)

_BUCKET_RATE_FIELDS = {
    "uncached_input_tokens": "input_usd_per_million",
    "output_tokens": "output_usd_per_million",
    "cache_read_input_tokens": "cache_read_usd_per_million",
    "cache_creation_input_tokens": "cache_write_usd_per_million",
}


class Price(NamedTuple):
    """One model's rate card: USD per million tokens, and when it was recorded."""

    input_usd_per_million: float
    output_usd_per_million: float
    cache_read_usd_per_million: float | None
    cache_write_usd_per_million: float | None
    tier: dict | None
    peak: dict | None
    recorded: str


def _number(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def price_key(model: str) -> str:
    """The table key for a requested model: the id without a trailing
    `:<level>` thinking suffix, which changes the tokens spent, not the rate."""
    return model.rsplit(":", 1)[0] if ":" in model.rsplit("/", 1)[-1] else model


def load_prices(path: Path = PRICES_PATH) -> dict[str, Price]:
    """The price table at `path`, keyed by model identifier.

    A row's base `input_usd_per_million` and `output_usd_per_million` are
    required. `cache_read_usd_per_million` and `cache_write_usd_per_million`
    are optional; a JSON `null` records a bucket the upstream does not bill,
    distinct from a rate nobody looked up, and both cost nothing here. A
    `tier` block must carry a positive `prompt_tokens_at_least` and the rates
    that replace the base card at or above it. A `peak` block must carry a
    positive `multiplier` and at least one closed `[start, end)` UTC minute
    window, with optional ISO weekdays (1 = Monday).
    """
    raw = json.loads(path.read_text(encoding="utf-8"))
    table: dict[str, Price] = {}
    for model, row in raw.items():
        if not isinstance(row, dict):
            raise ValueError(f"{path}: {model} must be a mapping")
        if not _number(row.get("input_usd_per_million")) or not _number(row.get("output_usd_per_million")):
            raise ValueError(f"{path}: {model} needs numeric input and output rates")
        for field in ("cache_read_usd_per_million", "cache_write_usd_per_million"):
            if field in row and row[field] is not None and not _number(row[field]):
                raise ValueError(f"{path}: {model}.{field} must be a number or null")
        tier = row.get("tier")
        if tier is not None:
            threshold = tier.get("prompt_tokens_at_least")
            if not isinstance(threshold, int) or isinstance(threshold, bool) or threshold <= 0:
                raise ValueError(f"{path}: {model}.tier.prompt_tokens_at_least must be a positive integer")
            for field in _BUCKET_RATE_FIELDS.values():
                value = tier.get(field)
                if value is not None and not _number(value):
                    raise ValueError(f"{path}: {model}.tier.{field} must be a number or null")
        peak = row.get("peak")
        if peak is not None:
            multiplier = peak.get("multiplier")
            windows = peak.get("windows")
            if not _number(multiplier) or multiplier <= 0:
                raise ValueError(f"{path}: {model}.peak.multiplier must be positive")
            if not isinstance(windows, list) or not windows:
                raise ValueError(f"{path}: {model}.peak.windows must be a non-empty list")
            for window in windows:
                start = window.get("start_minute_utc")
                end = window.get("end_minute_utc")
                if not isinstance(start, int) or not isinstance(end, int) or not (0 <= start < end <= 1440):
                    raise ValueError(f"{path}: {model}.peak window must satisfy 0 <= start < end <= 1440")
                days = window.get("days_of_week")
                if days is not None and (
                    not isinstance(days, list)
                    or not days
                    or any(not isinstance(day, int) or not 1 <= day <= 7 for day in days)
                ):
                    raise ValueError(f"{path}: {model}.peak.days_of_week must list ISO weekdays 1-7")
        table[model] = Price(
            input_usd_per_million=row["input_usd_per_million"],
            output_usd_per_million=row["output_usd_per_million"],
            cache_read_usd_per_million=row.get("cache_read_usd_per_million"),
            cache_write_usd_per_million=row.get("cache_write_usd_per_million"),
            tier=tier,
            peak=peak,
            recorded=str(row.get("recorded", "")),
        )
    return table


def peak_multiplier(peak: dict | None, timestamp_ms: int | float | None) -> float | None:
    """The multiplier that applies at `timestamp_ms`, or `None` when unknown.

    A card without `peak` is always `1.0`. A card with `peak` needs the
    message's own timestamp: without one the window cannot be decided, and
    the caller must report the cost as unreported rather than assume off-peak.
    """
    if peak is None:
        return 1.0
    if not _number(timestamp_ms):
        return None
    moment = datetime.fromtimestamp(float(timestamp_ms) / 1000, tz=timezone.utc)
    minute = moment.hour * 60 + moment.minute
    day = moment.isoweekday()
    for window in peak["windows"]:
        days = window.get("days_of_week")
        if days is not None and day not in days:
            continue
        if window["start_minute_utc"] <= minute < window["end_minute_utc"]:
            return float(peak["multiplier"])
    return 1.0


def _bucket_rates(price: Price, prompt_tokens: int) -> dict[str, float | None]:
    """The rates for a message with `prompt_tokens` input tokens.

    The published tier applies to the whole prompt once it reaches the
    threshold, not only to the tokens above it.
    """
    tier = price.tier
    if tier is not None and prompt_tokens >= tier["prompt_tokens_at_least"]:
        return {field: tier.get(field) for field in _BUCKET_RATE_FIELDS.values()}
    return {
        "input_usd_per_million": price.input_usd_per_million,
        "output_usd_per_million": price.output_usd_per_million,
        "cache_read_usd_per_million": price.cache_read_usd_per_million,
        "cache_write_usd_per_million": price.cache_write_usd_per_million,
    }


def cost_usd(
    model: str,
    messages: list[dict],
    prices: dict[str, Price] | None = None,
) -> float | str:
    """The dollar cost of one turn's assistant messages on `model`.

    Each entry in `messages` is `{"tokens": {bucket: count}, "timestamp": ms}`
    as `rpc.TurnReducer` records it. Tier selection uses that message's own
    prompt size and the peak multiplier its own timestamp, because a run's
    aggregate counts cannot tell which request crossed either boundary.
    Cache buckets with no published rate cost nothing: `null` records an
    upstream that does not bill that bucket, never a missing number.

    `prices` defaults to `load_prices()`; a caller may pass its own table
    (the unit tests do) to avoid touching the file.

    Returns `UNREPORTED`, never `0.0`, when the model is absent from the
    table, when a message has no tokens, or when a peak-priced message has no
    timestamp.
    """
    table = prices if prices is not None else load_prices()
    price = table.get(price_key(model))
    if price is None or not messages:
        return UNREPORTED
    total = 0.0
    for message in messages:
        tokens = message.get("tokens")
        if not isinstance(tokens, dict):
            return UNREPORTED
        counts = {bucket: tokens.get(bucket, 0) for bucket in BUCKETS}
        if any(not isinstance(count, int) or isinstance(count, bool) or count < 0 for count in counts.values()):
            return UNREPORTED
        prompt_tokens = sum(counts[bucket] for bucket in ("uncached_input_tokens", "cache_read_input_tokens", "cache_creation_input_tokens"))
        rates = _bucket_rates(price, prompt_tokens)
        multiplier = peak_multiplier(price.peak, message.get("timestamp"))
        if multiplier is None:
            return UNREPORTED
        subtotal = 0.0
        for bucket in BUCKETS:
            rate = rates[_BUCKET_RATE_FIELDS[bucket]]
            if rate is None:
                continue
            subtotal += counts[bucket] * rate
        total += subtotal * multiplier
    return total / 1_000_000
