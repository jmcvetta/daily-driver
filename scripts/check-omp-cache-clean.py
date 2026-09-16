#!/usr/bin/env python3
"""Check the local Omp plugin cache refresh target without touching Omp state."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TARGET = "omp-update-daily-driver"
EXPECTED_CALLS = (
    ("plugin", "marketplace", "update", "daily-driver"),
    ("plugin", "upgrade", "daily-driver@daily-driver"),
)
FAKE_OMP = """#!/usr/bin/env python3
import json
import os
import sys

args = sys.argv[1:]
with open(os.environ["OMP_CALL_LOG"], "a", encoding="utf-8") as stream:
    json.dump(args, stream)
    stream.write("\\n")

fail_on = os.environ.get("OMP_FAIL_ON")
if fail_on is not None and args == json.loads(fail_on):
    raise SystemExit(23)
"""


def fail(message: str) -> None:
    """Print one assertion failure and terminate with a nonzero status."""
    print(f"check-omp-cache-clean: {message}", file=sys.stderr)
    raise SystemExit(1)


def run_target(
    bin_dir: Path,
    call_log: Path,
    fail_on: tuple[str, ...] | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run the target against the fake Omp executable."""
    env = os.environ.copy()
    env["PATH"] = f"{bin_dir}{os.pathsep}{env['PATH']}"
    env["OMP_CALL_LOG"] = str(call_log)
    if fail_on is None:
        env.pop("OMP_FAIL_ON", None)
    else:
        env["OMP_FAIL_ON"] = json.dumps(fail_on)
    return subprocess.run(
        ["make", "--no-print-directory", "--silent", TARGET],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def read_calls(call_log: Path) -> tuple[tuple[str, ...], ...]:
    """Read the fake Omp argument vectors in execution order."""
    return tuple(tuple(json.loads(line)) for line in call_log.read_text(encoding="utf-8").splitlines())


def main() -> None:
    """Require a complete refresh and fail-fast command ordering."""
    with tempfile.TemporaryDirectory(prefix="check-omp-cache-clean-") as temp_dir:
        root = Path(temp_dir)
        bin_dir = root / "bin"
        bin_dir.mkdir()
        fake_omp = bin_dir / "omp"
        fake_omp.write_text(FAKE_OMP, encoding="utf-8")
        fake_omp.chmod(0o755)
        call_log = root / "calls.log"

        result = run_target(bin_dir, call_log)
        if result.returncode != 0:
            fail(f"target failed against fake Omp: {result.stderr.strip()}")
        if read_calls(call_log) != EXPECTED_CALLS:
            fail(f"expected calls {EXPECTED_CALLS}, got {read_calls(call_log)}")

        for failed_index, failed_call in enumerate(EXPECTED_CALLS):
            call_log.unlink()
            result = run_target(bin_dir, call_log, failed_call)
            if result.returncode == 0:
                fail(f"target ignored failure from `{failed_call}`")
            expected_prefix = EXPECTED_CALLS[: failed_index + 1]
            if read_calls(call_log) != expected_prefix:
                fail(f"failure from `{failed_call}` should stop after {expected_prefix}, got {read_calls(call_log)}")

    print("check-omp-cache-clean: target refreshes the marketplace and plugin cache in order")


if __name__ == "__main__":
    main()
