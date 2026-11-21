#!/usr/bin/env python3
"""Generate `evals/coder-eval-omp/prices.json` from provider catalogs.

Reads pinned Vercel AI Gateway models from their provider endpoint cards, and
pinned OpenCode Go models from its public model catalog. Vercel arms must name
one allowed upstream; Go arms must publish zero text input, output, and cache
read rates. Missing or ambiguous models, changed required shapes, or nonzero
rates fail rather than guessing.

Rows carry published buckets and source dates. A cache-write bucket the Go
catalog does not publish remains null. The output is validated through the
adapter's own loader before replacing the committed snapshot.

USAGE

    python3 scripts/evals-fetch-prices.py            # rewrite the snapshot
    python3 scripts/evals-fetch-prices.py --check    # fail if it is stale

Every invocation runs the offline self-tests first, against inline API and
experiment fixtures. They need no network and no credential.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
import tempfile
import urllib.error
import urllib.request
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Callable

try:
    import yaml
except ImportError:  # pragma: no cover - the repository's uv environment has PyYAML.
    yaml = None

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_EXPERIMENTS_DIR = ROOT / "evals" / "experiments"
DEFAULT_OUTPUT = ROOT / "evals" / "coder-eval-omp" / "prices.json"
PRICING_MODULE = ROOT / "evals" / "coder-eval-omp" / "src" / "coder_eval_omp" / "pricing.py"

GATEWAY_PREFIX = "vercel-ai-gateway/"
ENDPOINTS_URL = "https://ai-gateway.vercel.sh/v1/models/{provider}/{model}/endpoints"
OPENCODE_GO_PREFIX = "opencode-go/"
GO_MODELS_URL = "https://opencode.ai/inference/go/v1/models"

#: Our row field, and the API field it is converted from. The API publishes
#: USD per token as a decimal string; every row here is USD per million.
RATE_FIELDS = (
    ("input_usd_per_million", "prompt"),
    ("output_usd_per_million", "completion"),
    ("cache_read_usd_per_million", "input_cache_read"),
    ("cache_write_usd_per_million", "input_cache_write"),
)
TIER_FIELDS = (
    ("input_usd_per_million", "prompt_tiers"),
    ("output_usd_per_million", "completion_tiers"),
    ("cache_read_usd_per_million", "input_cache_read_tiers"),
    ("cache_write_usd_per_million", "input_cache_write_tiers"),
)
BASE_FIELD = dict(RATE_FIELDS)


class PriceError(Exception):
    """The API cannot price an arm's restricted upstream, or a shape moved."""


def per_million(value: Any) -> float:
    """A per-token decimal string from the API as USD per million tokens."""
    if not isinstance(value, str):
        raise PriceError(f"rate {value!r} is not a decimal string")
    try:
        amount = Decimal(value)
    except InvalidOperation as exc:
        raise PriceError(f"rate {value!r} is not a decimal") from exc
    if amount < 0:
        raise PriceError(f"rate {value!r} is negative")
    return float(amount * 1_000_000)


def optional_per_million(value: Any) -> float | None:
    """The same conversion, for a bucket the API may omit.

    A missing bucket is `None`: the upstream does not publish that rate, which
    the loader treats as a bucket that costs nothing. It is never a guessed 0.
    """
    if value is None:
        return None
    return per_million(value)


def price_key(model: str) -> str:
    """The table key for a requested model: the id without its thinking suffix."""
    return model.rsplit(":", 1)[0] if ":" in model.rsplit("/", 1)[-1] else model


def split_model(key: str) -> tuple[str, str]:
    """`(provider, model)` for the endpoints URL, from a table key."""
    if not key.startswith(GATEWAY_PREFIX):
        raise PriceError(f"{key} is not a {GATEWAY_PREFIX} model")
    parts = key[len(GATEWAY_PREFIX) :].split("/")
    if len(parts) != 2 or not all(parts):
        raise PriceError(f"{key} does not name one provider and model")
    return parts[0], parts[1]


def restricted_arms(experiments_dir: Path) -> dict[str, tuple[str, ...]]:
    """Every gateway model an experiment restricts to named upstreams.

    Reads `defaults.agent` and each variant's own `agent`, because a variant
    may override the model. A `vercel_gateway_only` mapping names several
    routes — the parent and the reviewer role — and each one becomes its own
    row. A model restricted to different upstreams by two experiments cannot
    have one row, so that is an error rather than a pick.
    """
    arms: dict[str, tuple[str, ...]] = {}

    def add(key: str, upstreams: Any, where: Path) -> None:
        if not isinstance(upstreams, list) or not all(isinstance(name, str) and name for name in upstreams):
            raise PriceError(f"{where}: vercel_gateway_only must be a list of upstream names or a mapping of them")
        key = price_key(key)
        split_model(key)
        restriction = tuple(upstreams)
        if key in arms and arms[key] != restriction:
            raise PriceError(
                f"{where}: {key} is restricted to {sorted(restriction)} here and "
                f"{sorted(arms[key])} elsewhere; one row cannot price both"
            )
        arms[key] = restriction

    for path in sorted(experiments_dir.glob("*.yaml")):
        document = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        agents = [(document.get("defaults") or {}).get("agent")]
        for variant in document.get("variants") or []:
            if isinstance(variant, dict):
                agents.append(variant.get("agent"))
        for agent in agents:
            if not isinstance(agent, dict):
                continue
            model = agent.get("model")
            restriction = agent.get("vercel_gateway_only")
            if not model or not restriction:
                continue
            if isinstance(restriction, dict):
                for selector, upstreams in restriction.items():
                    add(str(selector), upstreams, path)
                continue
            add(str(model), restriction, path)
    return dict(sorted(arms.items()))


def split_opencode_go_model(key: str) -> str:
    """The OpenCode Go catalog id for a pinned Omp model."""
    if not key.startswith(OPENCODE_GO_PREFIX):
        raise PriceError(f"{key} is not an {OPENCODE_GO_PREFIX} model")
    model_id = key[len(OPENCODE_GO_PREFIX) :]
    if not model_id or "/" in model_id:
        raise PriceError(f"{key} does not name one OpenCode Go model")
    return model_id


def opencode_go_arms(experiments_dir: Path) -> tuple[str, ...]:
    """Every pinned OpenCode Go model in experiment defaults or variants."""
    models: set[str] = set()
    for path in sorted(experiments_dir.glob("*.yaml")):
        document = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        agents = [(document.get("defaults") or {}).get("agent")]
        for variant in document.get("variants") or []:
            if isinstance(variant, dict):
                agents.append(variant.get("agent"))
        for agent in agents:
            if not isinstance(agent, dict):
                continue
            model = agent.get("model")
            if isinstance(model, str) and model.startswith(OPENCODE_GO_PREFIX):
                key = price_key(model)
                split_opencode_go_model(key)
                models.add(key)
    return tuple(sorted(models))


def select_opencode_go_model(payload: Any, key: str) -> dict:
    """The one exact model record in the OpenCode Go catalog."""
    model_id = split_opencode_go_model(key)
    if not isinstance(payload, dict) or payload.get("object") != "list" or not isinstance(payload.get("data"), list):
        raise PriceError(f"{key}: the OpenCode Go models catalog changed shape")
    matches = [model for model in payload["data"] if isinstance(model, dict) and model.get("id") == model_id]
    if not matches:
        raise PriceError(f"{key}: the OpenCode Go catalog does not publish this model")
    if len(matches) != 1:
        raise PriceError(f"{key}: the OpenCode Go catalog publishes this model more than once")
    if matches[0].get("object") != "model":
        raise PriceError(f"{key}: the OpenCode Go model record changed shape")
    return matches[0]


def _zero_catalog_rate(value: Any, key: str, field: str) -> float:
    """A published numeric Go price, which this free-arm snapshot requires to be zero."""
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise PriceError(f"{key}: the OpenCode Go catalog has no numeric `{field}` price")
    if value != 0:
        raise PriceError(f"{key}: the OpenCode Go catalog publishes nonzero `{field}` price {value!r}")
    return 0.0


def opencode_go_price_row(model: dict, key: str, source: str, read_on: str) -> dict:
    """One strict zero-rate row from an OpenCode Go model record."""
    cost = model.get("cost")
    text = cost.get("text") if isinstance(cost, dict) else None
    input_cost = text.get("input") if isinstance(text, dict) else None
    output_cost = text.get("output") if isinstance(text, dict) else None
    cache = input_cost.get("cache") if isinstance(input_cost, dict) else None
    if not isinstance(input_cost, dict) or not isinstance(output_cost, dict) or not isinstance(cache, dict):
        raise PriceError(f"{key}: the OpenCode Go text pricing block changed shape")

    return {
        "input_usd_per_million": _zero_catalog_rate(input_cost.get("price"), key, "text input"),
        "output_usd_per_million": _zero_catalog_rate(output_cost.get("price"), key, "text output"),
        "cache_read_usd_per_million": _zero_catalog_rate(cache.get("read"), key, "cache read"),
        "cache_write_usd_per_million": (
            _zero_catalog_rate(cache["write"], key, "cache write") if "write" in cache else None
        ),
        "source": source,
        "read_on": read_on,
        "recorded": read_on,
    }


def select_endpoint(payload: Any, key: str, upstreams: tuple[str, ...]) -> dict:
    """The one endpoint card for `key` served by one of `upstreams`."""
    endpoints = ((payload or {}).get("data") or {}).get("endpoints")
    if not isinstance(endpoints, list) or not endpoints:
        raise PriceError(f"{key}: the endpoints API returned no endpoint list")
    matches = [endpoint for endpoint in endpoints if endpoint.get("provider_name") in upstreams]
    if not matches:
        published = sorted(str(endpoint.get("provider_name")) for endpoint in endpoints)
        raise PriceError(f"{key}: no endpoint served by {sorted(upstreams)}; published upstreams are {published}")
    if len(matches) > 1:
        raise PriceError(f"{key}: {len(matches)} endpoints are served by {sorted(upstreams)}; refusing to guess")
    endpoint = matches[0]
    status = endpoint.get("status", 0)
    if status != 0:
        raise PriceError(f"{key}: the {endpoint.get('provider_name')} endpoint reports status {status!r}")
    pricing = endpoint.get("pricing")
    if not isinstance(pricing, dict):
        raise PriceError(f"{key}: the {endpoint.get('provider_name')} endpoint publishes no pricing block")
    return pricing


def _tier_block(pricing: dict, key: str) -> dict | None:
    """The published tier as one prompt threshold and the rates above it.

    The API publishes one array per bucket with a low card (`max`) and a high
    one (`min`). The loader models exactly one boundary, so a shape with more
    boundaries, a low card that disagrees with the base rate, or arrays that
    disagree on the boundary is a hard failure rather than a partial mapping.
    """
    blocks: dict[str, float | None] = {}
    thresholds: set[int] = set()
    published = False
    for field, api_field in TIER_FIELDS:
        tiers = pricing.get(api_field)
        if not tiers:
            blocks[field] = None
            continue
        if not isinstance(tiers, list) or len(tiers) != 2:
            raise PriceError(f"{key}: {api_field} is not a two-tier array")
        published = True
        low, high = sorted(tiers, key=lambda tier: int(tier.get("min", 0)))
        threshold = high.get("min")
        if not isinstance(threshold, int) or isinstance(threshold, bool) or threshold <= 0:
            raise PriceError(f"{key}: {api_field} publishes no positive high-tier `min`")
        if low.get("max") is not None and (
            not isinstance(low["max"], int) or isinstance(low["max"], bool) or low["max"] != threshold
        ):
            raise PriceError(f"{key}: {api_field} tiers do not meet at one boundary")
        base = pricing.get(BASE_FIELD[field])
        if base is not None and per_million(low.get("cost")) != per_million(base):
            raise PriceError(f"{key}: {api_field} low card disagrees with the base rate")
        thresholds.add(threshold)
        blocks[field] = per_million(high.get("cost"))
    if not published:
        return None
    if len(thresholds) != 1:
        raise PriceError(f"{key}: tier arrays disagree on the prompt boundary {sorted(thresholds)}")
    block: dict[str, float | None] = {"prompt_tokens_at_least": thresholds.pop()}
    block.update(blocks)
    return block


def _peak_block(pricing: dict, key: str) -> dict | None:
    """The published peak multiplier and its UTC windows, or `None`."""
    peak = pricing.get("peak_pricing")
    if not peak:
        return None
    multiplier = peak.get("multiplier")
    if not isinstance(multiplier, (int, float)) or isinstance(multiplier, bool) or multiplier <= 0:
        raise PriceError(f"{key}: peak_pricing.multiplier must be positive")
    windows = []
    for window in peak.get("windows") or []:
        start = window.get("start_minute_utc")
        end = window.get("end_minute_utc")
        if not isinstance(start, int) or not isinstance(end, int) or not 0 <= start < end <= 1440:
            raise PriceError(f"{key}: peak window {start!r}-{end!r} is not a closed UTC range")
        block: dict[str, Any] = {"start_minute_utc": start, "end_minute_utc": end}
        days = window.get("days_of_week")
        if days:
            block["days_of_week"] = [int(day) for day in days]
        windows.append(block)
    if not windows:
        raise PriceError(f"{key}: peak_pricing publishes no window")
    block = {"multiplier": float(multiplier), "windows": windows}
    if peak.get("holiday_calendar"):
        block["holiday_calendar"] = str(peak["holiday_calendar"])
    return block


def price_row(pricing: dict, key: str, source: str, read_on: str) -> dict:
    """One `prices.json` row from one endpoint's pricing block."""
    row: dict[str, Any] = {}
    for field, api_field in RATE_FIELDS:
        if api_field not in pricing and field in ("input_usd_per_million", "output_usd_per_million"):
            raise PriceError(f"{key}: pricing publishes no `{api_field}` rate")
        row[field] = optional_per_million(pricing.get(api_field))
    tier = _tier_block(pricing, key)
    if tier is not None:
        row["tier"] = tier
    peak = _peak_block(pricing, key)
    if peak is not None:
        row["peak"] = peak
    row["source"] = source
    row["read_on"] = read_on
    row["recorded"] = read_on
    return row


def fetch_endpoints(provider: str, model: str) -> Any:
    """The endpoints payload for one gateway model, over HTTPS."""
    url = ENDPOINTS_URL.format(provider=provider, model=model)
    request = urllib.request.Request(url, headers={"User-Agent": "daily-driver-evals-fetch-prices"})
    try:
        with urllib.request.urlopen(request, timeout=30) as response:  # noqa: S310 - fixed https URL
            return json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise PriceError(f"{url}: {exc}") from exc


def fetch_opencode_go_catalog() -> Any:
    """The public OpenCode Go model catalog, over HTTPS."""
    request = urllib.request.Request(GO_MODELS_URL, headers={"User-Agent": "daily-driver-evals-fetch-prices"})
    try:
        with urllib.request.urlopen(request, timeout=30) as response:  # noqa: S310 - fixed https URL
            return json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise PriceError(f"{GO_MODELS_URL}: {exc}") from exc


def build_table(
    experiments_dir: Path,
    read_on: str,
    fetcher: Callable[[str, str], Any] = fetch_endpoints,
    go_fetcher: Callable[[], Any] = fetch_opencode_go_catalog,
) -> dict[str, dict]:
    """The whole `prices.json` document for pinned supported provider arms."""
    table: dict[str, dict] = {}
    for key, upstreams in restricted_arms(experiments_dir).items():
        provider, model = split_model(key)
        payload = fetcher(provider, model)
        pricing = select_endpoint(payload, key, upstreams)
        table[key] = price_row(pricing, key, ENDPOINTS_URL.format(provider=provider, model=model), read_on)

    go_arms = opencode_go_arms(experiments_dir)
    if go_arms:
        catalog = go_fetcher()
        for key in go_arms:
            model = select_opencode_go_model(catalog, key)
            table[key] = opencode_go_price_row(model, key, GO_MODELS_URL, read_on)
    if not table:
        raise PriceError(f"{experiments_dir}: no pinned supported model-price arms")
    return dict(sorted(table.items()))


def _load_loader() -> Callable[[Path], dict]:
    """The adapter's own `load_prices`, imported by path so no package init runs."""
    spec = importlib.util.spec_from_file_location("coder_eval_omp_pricing", PRICING_MODULE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module.load_prices


def write_table(table: dict[str, dict], output: Path) -> None:
    """Write `table` through the adapter's loader, then replace `output`.

    The temporary file beside the target means a document the loader rejects is
    never left where a run would read it as the snapshot.
    """
    document = json.dumps(table, indent=2, sort_keys=False) + "\n"
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=output.parent, suffix=".json", delete=False) as handle:
        handle.write(document)
        candidate = Path(handle.name)
    try:
        _load_loader()(candidate)
        candidate.replace(output)
    finally:
        candidate.unlink(missing_ok=True)


def main(argv: list[str]) -> int:
    _run_self_tests()

    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--experiments-dir", type=Path, default=DEFAULT_EXPERIMENTS_DIR)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--read-on",
        default=datetime.now(tz=timezone.utc).date().isoformat(),
        help="the day the cards were read, ISO date (default: today, UTC)",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="compare a fresh fetch with the committed snapshot and exit 1 when they differ",
    )
    args = parser.parse_args(argv)

    try:
        table = build_table(args.experiments_dir, args.read_on)
        document = json.dumps(table, indent=2, sort_keys=False) + "\n"
        if args.check:
            if not args.output.is_file() or args.output.read_text(encoding="utf-8") != document:
                print(f"evals-fetch-prices: {args.output} is stale; rerun without --check", file=sys.stderr)
                return 1
            return 0
        write_table(table, args.output)
    except PriceError as exc:
        print(f"evals-fetch-prices: {exc}", file=sys.stderr)
        return 1
    print(f"evals-fetch-prices: wrote {len(table)} row(s) to {args.output}", file=sys.stderr)
    return 0


# ---------------------------------------------------------------------------
# Self-tests: offline, inline fixtures shaped like the real payloads.
# ---------------------------------------------------------------------------

LUNA_PRICING = {
    "prompt": "0.0000001",
    "prompt_tiers": [
        {"cost": "0.0000001", "min": 0, "max": 272001},
        {"cost": "0.0000002", "min": 272001},
    ],
    "completion": "0.0000005",
    "completion_tiers": [
        {"cost": "0.0000005", "min": 0, "max": 272001},
        {"cost": "0.00000075", "min": 272001},
    ],
    "input_cache_read": "0.00000001",
    "input_cache_read_tiers": [
        {"cost": "0.00000001", "min": 0, "max": 272001},
        {"cost": "0.00000002", "min": 272001},
    ],
    "input_cache_write": "0.000000125",
    "input_cache_write_tiers": [
        {"cost": "0.000000125", "min": 0, "max": 272001},
        {"cost": "0.00000025", "min": 272001},
    ],
}

DEEPSEEK_PRICING = {
    "prompt": "0.00000015",
    "completion": "0.0000006",
    "input_cache_read": "0.000000003",
    "peak_pricing": {
        "multiplier": 2,
        "windows": [
            {"start_minute_utc": 60, "end_minute_utc": 240, "days_of_week": [1, 2, 3, 4, 5]},
            {"start_minute_utc": 360, "end_minute_utc": 600, "days_of_week": [1, 2, 3, 4, 5]},
        ],
        "holiday_calendar": "cn",
    },
}


GO_PRICING = {
    "text": {
        "input": {"price": 0, "cache": {"read": 0}},
        "output": {"price": 0},
    },
}

GO_CATALOG = {
    "object": "list",
    "data": [
        {"object": "model", "id": "beam-free", "cost": GO_PRICING},
        {"object": "model", "id": "iceman-contributor-free", "cost": GO_PRICING},
        {"object": "model", "id": "longcat-2.5-free", "cost": GO_PRICING},
    ],
}


def _payload(*endpoints: tuple[str, dict, int]) -> dict:
    return {
        "data": {
            "endpoints": [
                {"provider_name": name, "pricing": pricing, "status": status} for name, pricing, status in endpoints
            ]
        }
    }


def _test_per_million() -> None:
    assert per_million("0.0000001") == 0.1
    assert per_million("0.000000125") == 0.125
    assert per_million("0.000000003") == 0.003
    assert optional_per_million(None) is None
    assert price_key("vercel-ai-gateway/openai/gpt-6-luna:high") == "vercel-ai-gateway/openai/gpt-6-luna"
    assert split_model("vercel-ai-gateway/deepseek/deepseek-v4.1-flash-1017") == (
        "deepseek",
        "deepseek-v4.1-flash-1017",
    )
    for bad in ("vercel-ai-gateway/openai", "openai-codex/gpt-6-luna", "vercel-ai-gateway/a/b/c"):
        try:
            split_model(bad)
        except PriceError:
            continue
        raise AssertionError(f"split_model accepted {bad}")


def _test_select_endpoint() -> None:
    payload = _payload(
        ("azure", {"prompt": "0.0000001", "completion": "0.0000005"}, 0),
        ("bedrock", {"prompt": "0.0000001", "completion": "0.0000005"}, 0),
        ("openai", LUNA_PRICING, 0),
    )
    chosen = select_endpoint(payload, "vercel-ai-gateway/openai/gpt-6-luna", ("openai",))
    assert chosen is LUNA_PRICING

    for payload, upstreams, why in (
        (_payload(("azure", LUNA_PRICING, 0)), ("openai",), "missing upstream"),
        (_payload(("openai", LUNA_PRICING, 0), ("openai", LUNA_PRICING, 0)), ("openai",), "ambiguous upstream"),
        (_payload(("openai", LUNA_PRICING, 2)), ("openai",), "unavailable endpoint"),
        ({"data": {"endpoints": []}}, ("openai",), "empty list"),
    ):
        try:
            select_endpoint(payload, "vercel-ai-gateway/openai/gpt-6-luna", upstreams)
        except PriceError:
            continue
        raise AssertionError(f"select_endpoint accepted {why}")


def _test_price_row() -> None:
    read_on = "2026-11-18"
    luna = price_row(LUNA_PRICING, "vercel-ai-gateway/openai/gpt-6-luna", "https://example.invalid/luna", read_on)
    assert luna["input_usd_per_million"] == 0.1
    assert luna["output_usd_per_million"] == 0.5
    assert luna["cache_read_usd_per_million"] == 0.01
    assert luna["cache_write_usd_per_million"] == 0.125
    assert luna["tier"] == {
        "prompt_tokens_at_least": 272001,
        "input_usd_per_million": 0.2,
        "output_usd_per_million": 0.75,
        "cache_read_usd_per_million": 0.02,
        "cache_write_usd_per_million": 0.25,
    }
    assert "peak" not in luna
    assert luna["source"] == "https://example.invalid/luna"
    assert luna["read_on"] == read_on

    deepseek = price_row(
        DEEPSEEK_PRICING, "vercel-ai-gateway/deepseek/deepseek-v4.1-flash-1017", "https://example.invalid/ds", read_on
    )
    assert deepseek["input_usd_per_million"] == 0.15
    assert deepseek["output_usd_per_million"] == 0.6
    assert deepseek["cache_read_usd_per_million"] == 0.003
    assert deepseek["cache_write_usd_per_million"] is None
    assert "tier" not in deepseek
    assert deepseek["peak"] == {
        "multiplier": 2.0,
        "windows": [
            {"start_minute_utc": 60, "end_minute_utc": 240, "days_of_week": [1, 2, 3, 4, 5]},
            {"start_minute_utc": 360, "end_minute_utc": 600, "days_of_week": [1, 2, 3, 4, 5]},
        ],
        "holiday_calendar": "cn",
    }

    # A tier that disagrees on its boundary, and a low card that contradicts
    # the base rate, are shapes the loader cannot express: fail, do not pick.
    for pricing in (
        dict(
            DEEPSEEK_PRICING,
            prompt_tiers=[
                {"cost": "0.00000015", "min": 0, "max": 1000},
                {"cost": "0.0000003", "min": 1000},
                {"cost": "0.0000006", "min": 2000},
            ],
        ),
        dict(DEEPSEEK_PRICING, peak_pricing={"multiplier": 2, "windows": [{"start_minute_utc": 480, "end_minute_utc": 30}]}),
    ):
        try:
            price_row(pricing, "vercel-ai-gateway/deepseek/deepseek-v4.1-flash-1017", "https://example.invalid/ds", read_on)
        except PriceError:
            continue
        raise AssertionError("price_row accepted an unrepresentable card")

    disagreement = dict(LUNA_PRICING)
    disagreement["completion_tiers"] = [
        {"cost": "0.0000005", "min": 0, "max": 99},
        {"cost": "0.00000075", "min": 99},
    ]
    try:
        price_row(disagreement, "vercel-ai-gateway/openai/gpt-6-luna", "https://example.invalid/luna", read_on)
    except PriceError:
        pass
    else:
        raise AssertionError("price_row accepted tier arrays with different boundaries")


def _test_restricted_arms() -> None:
    documents = {
        "restricted.yaml": (
            "defaults:\n"
            "  agent:\n"
            "    type: omp\n"
            "    model: vercel-ai-gateway/deepseek/deepseek-v4.1-flash-1017:high\n"
            "    vercel_gateway_only: [deepseek]\n"
        ),
        "variant-override.yaml": (
            "defaults:\n"
            "  agent:\n"
            "    type: omp\n"
            "    model: vercel-ai-gateway/openai/gpt-6-luna:high\n"
            "variants:\n"
            "  - variant_id: default\n"
            "    agent:\n"
            "      model: vercel-ai-gateway/openai/gpt-6-luna:high\n"
            "      vercel_gateway_only: [openai]\n"
        ),
        "unrestricted.yaml": "defaults:\n  agent:\n    model: vercel-ai-gateway/zai/glm-5.3\n",
        "role-mapping.yaml": (
            "defaults:\n"
            "  agent:\n"
            "    type: omp\n"
            "    model: vercel-ai-gateway/openai/gpt-6.1-sol:low\n"
            "    vercel_gateway_only:\n"
            "      vercel-ai-gateway/openai/gpt-6.1-sol: [openai]\n"
            "      vercel-ai-gateway/zai/glm-5.3: [zai]\n"
        ),
    }
    with tempfile.TemporaryDirectory(prefix="prices-selftest-") as tmp:
        directory = Path(tmp)
        for name, text in documents.items():
            (directory / name).write_text(text, encoding="utf-8")
        arms = restricted_arms(directory)
        assert arms == {
            "vercel-ai-gateway/deepseek/deepseek-v4.1-flash-1017": ("deepseek",),
            "vercel-ai-gateway/openai/gpt-6-luna": ("openai",),
            "vercel-ai-gateway/openai/gpt-6.1-sol": ("openai",),
            "vercel-ai-gateway/zai/glm-5.3": ("zai",),
        }, arms

        (directory / "conflict.yaml").write_text(
            "defaults:\n"
            "  agent:\n"
            "    model: vercel-ai-gateway/deepseek/deepseek-v4.1-flash-1017:high\n"
            "    vercel_gateway_only: [deepseek]\n"
            "variants:\n"
            "  - variant_id: x\n"
            "    agent:\n"
            "      model: vercel-ai-gateway/deepseek/deepseek-v4.1-flash-1017:high\n"
            "      vercel_gateway_only: [baseten]\n",
            encoding="utf-8",
        )
        try:
            restricted_arms(directory)
        except PriceError:
            pass
        else:
            raise AssertionError("restricted_arms accepted two upstreams for one model")



def _test_opencode_go_arms() -> None:
    with tempfile.TemporaryDirectory(prefix="prices-go-arms-selftest-") as tmp:
        directory = Path(tmp)
        (directory / "arms.yaml").write_text(
            "defaults:\n"
            "  agent:\n"
            "    model: opencode-go/beam-free:high\n"
            "variants:\n"
            "  - variant_id: default\n"
            "    agent:\n"
            "      model: opencode-go/iceman-contributor-free\n"
            "  - variant_id: longcat\n"
            "    agent:\n"
            "      model: opencode-go/longcat-2.5-free\n",
            encoding="utf-8",
        )
        assert opencode_go_arms(directory) == (
            "opencode-go/beam-free",
            "opencode-go/iceman-contributor-free",
            "opencode-go/longcat-2.5-free",
        )
    assert split_opencode_go_model("opencode-go/beam-free") == "beam-free"
    for bad in ("vercel-ai-gateway/openai/gpt-6-luna", "opencode-go/", "opencode-go/a/b"):
        try:
            split_opencode_go_model(bad)
        except PriceError:
            continue
        raise AssertionError(f"split_opencode_go_model accepted {bad}")


def _test_opencode_go_catalog() -> None:
    key = "opencode-go/beam-free"
    model = select_opencode_go_model(GO_CATALOG, key)
    row = opencode_go_price_row(model, key, GO_MODELS_URL, "2026-11-19")
    assert row == {
        "input_usd_per_million": 0.0,
        "output_usd_per_million": 0.0,
        "cache_read_usd_per_million": 0.0,
        "cache_write_usd_per_million": None,
        "source": GO_MODELS_URL,
        "read_on": "2026-11-19",
        "recorded": "2026-11-19",
    }

    for payload, why in (
        ({"object": "list", "data": []}, "missing model"),
        ({"object": "list", "data": [GO_CATALOG["data"][0], GO_CATALOG["data"][0]]}, "duplicate model"),
        ({"object": "unexpected", "data": []}, "changed catalog shape"),
    ):
        try:
            select_opencode_go_model(payload, key)
        except PriceError:
            continue
        raise AssertionError(f"select_opencode_go_model accepted {why}")

    for cost, why in (
        ({"text": {"input": {"price": 0, "cache": {"read": 0}}, "output": {"price": 0.1}}}, "paid output"),
        ({"text": {"input": {"price": 0.1, "cache": {"read": 0}}, "output": {"price": 0}}}, "paid input"),
        ({"text": {"input": {"price": 0, "cache": {"read": 0.1}}, "output": {"price": 0}}}, "paid cache"),
        ({"text": {"input": {"price": 0, "cache": {"read": 0, "write": 0.1}}, "output": {"price": 0}}}, "paid cache write"),
        ({"text": {"input": {"price": 0}, "output": {"price": 0}}}, "missing cache shape"),
        ({"text": {"input": {"price": "0", "cache": {"read": 0}}, "output": {"price": 0}}}, "changed price type"),
    ):
        try:
            opencode_go_price_row({"cost": cost}, key, GO_MODELS_URL, "2026-11-19")
        except PriceError:
            continue
        raise AssertionError(f"opencode_go_price_row accepted {why}")

def _test_build_table() -> None:
    payloads = {
        ("deepseek", "deepseek-v4.1-flash-1017"): _payload(("baseten", {"prompt": "0.0000003", "completion": "0.0000012"}, 0), ("deepseek", DEEPSEEK_PRICING, 0)),
        ("openai", "gpt-6-luna"): _payload(("azure", LUNA_PRICING, 0), ("openai", LUNA_PRICING, 0)),
    }
    requested: list[tuple[str, str]] = []
    go_catalog_requests: list[str] = []

    def fetcher(provider: str, model: str) -> Any:
        requested.append((provider, model))
        return payloads[(provider, model)]

    def go_fetcher() -> Any:
        go_catalog_requests.append(GO_MODELS_URL)
        return GO_CATALOG

    with tempfile.TemporaryDirectory(prefix="prices-selftest-") as tmp:
        directory = Path(tmp)
        (directory / "arms.yaml").write_text(
            "defaults:\n"
            "  agent:\n"
            "    type: omp\n"
            "    model: vercel-ai-gateway/deepseek/deepseek-v4.1-flash-1017:high\n"
            "    vercel_gateway_only: [deepseek]\n"
            "variants:\n"
            "  - variant_id: default\n"
            "    agent:\n"
            "      model: vercel-ai-gateway/openai/gpt-6-luna:high\n"
            "      vercel_gateway_only: [openai]\n"
            "  - variant_id: go\n"
            "    agent:\n"
            "      type: omp\n"
            "      model: opencode-go/beam-free:high\n",
            encoding="utf-8",
        )
        table = build_table(directory, "2026-11-18", fetcher=fetcher, go_fetcher=go_fetcher)
        assert sorted(requested) == [("deepseek", "deepseek-v4.1-flash-1017"), ("openai", "gpt-6-luna")]
        assert go_catalog_requests == [GO_MODELS_URL]
        assert set(table) == {
            "opencode-go/beam-free",
            "vercel-ai-gateway/deepseek/deepseek-v4.1-flash-1017",
            "vercel-ai-gateway/openai/gpt-6-luna",
        }
        assert table["opencode-go/beam-free"]["source"] == GO_MODELS_URL
        assert table["vercel-ai-gateway/openai/gpt-6-luna"]["source"].endswith(
            "/v1/models/openai/gpt-6-luna/endpoints"
        )

        output = directory / "prices.json"
        write_table(table, output)
        # The generated document is exactly what the adapter's loader reads.
        assert set(_load_loader()(output)) == set(table)

def _run_self_tests() -> None:
    _test_per_million()
    _test_select_endpoint()
    _test_price_row()
    _test_restricted_arms()
    _test_opencode_go_arms()
    _test_opencode_go_catalog()
    _test_build_table()

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
