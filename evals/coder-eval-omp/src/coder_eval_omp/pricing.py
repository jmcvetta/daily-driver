"""Hand-maintained per-million-token USD rates for the models the Omp arm runs.

Nothing here is fetched at run time: `coder_eval`'s model catalog reports
which providers exist, not what they charge, and catalog presence is not a
price. `prices.json` beside this module is a dated snapshot a person updates
by hand, keyed by the model identifier exactly as `omp_configs/*.yml` and an
experiment's `agent.model` spell it (`<gateway>/<provider>/<model>`, for
example `vercel-ai-gateway/zai/glm-5.3`).

Pure — no `coder_eval` import, same reasoning as `rpc.py` — so
`scripts/check-omp-agent.py` can drive it in `make check`.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import NamedTuple

def _default_prices_path() -> Path:
    """Where `prices.json` sits: beside this module once installed, or beside
    `pyproject.toml` in this checkout.

    `[tool.hatch.build.targets.wheel.force-include]` copies the committed
    `evals/coder-eval-omp/prices.json` to `coder_eval_omp/prices.json` at
    build time, so an installed package finds it as this module's own
    sibling. Running from source (this repo, via `scripts/check-omp-agent.py`
    and `sys.path`) never runs that build step, so the committed path is
    tried first and this checkout's is the fallback.
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


class Price(NamedTuple):
    """One model's rate card: USD per million tokens, and when it was recorded."""

    input_usd_per_million: float
    output_usd_per_million: float
    recorded: str


def load_prices(path: Path = PRICES_PATH) -> dict[str, Price]:
    """The price table at `path`, keyed by model identifier."""
    raw = json.loads(path.read_text(encoding="utf-8"))
    return {
        model: Price(
            input_usd_per_million=row["input_usd_per_million"],
            output_usd_per_million=row["output_usd_per_million"],
            recorded=row["recorded"],
        )
        for model, row in raw.items()
    }


def cost_usd(model: str, usage: dict[str, int], prices: dict[str, Price] | None = None) -> float | str:
    """The dollar cost of `usage` on `model`, from the hand-maintained table.

    Bills `uncached_input_tokens` and `output_tokens` — `coder_eval`'s
    `TokenUsage` buckets, the same ones `rpc.USAGE_KEYS` fills — at `model`'s
    rate. Cache tokens are not priced: the table carries one input and one
    output rate per model, not the cache-read/cache-write split some
    providers bill separately.

    `prices` defaults to `load_prices()`; a caller may pass its own table
    (the unit tests do) to avoid touching the file.

    Returns `UNREPORTED`, never `0.0`, for a model absent from the table —
    a silent zero would read as a free run instead of a gap in the table.
    """
    table = prices if prices is not None else load_prices()
    price = table.get(model)
    if price is None:
        return UNREPORTED
    input_tokens = usage.get("uncached_input_tokens", 0)
    output_tokens = usage.get("output_tokens", 0)
    return (input_tokens * price.input_usd_per_million + output_tokens * price.output_usd_per_million) / 1_000_000
