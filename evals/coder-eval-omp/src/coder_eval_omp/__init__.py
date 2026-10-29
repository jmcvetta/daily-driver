"""An `omp` agent kind for `coder_eval`, so the eval suites can run on Omp.

Import nothing from here at module scope that reaches `coder_eval`; `rpc` is
pure on purpose. `agent` and `plugin` are imported by name where they are needed.
"""

from __future__ import annotations


__all__ = ["__version__"]

#: Its own version, deliberately not the plugin's. This package is a test
#: instrument installed beside `coder-eval`; it is never published and never
#: released, so tying it to the plugin's version would put a fourth number in
#: front of `check-manifests.py` for release-please to keep in step.
__version__ = "0.1.0"
