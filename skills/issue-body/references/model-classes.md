# Model classes

Task issues name the minimum capability needed to implement their settled
handoff. They do not name a provider, a price tier, a context window, or a
reasoning-effort setting.

## Classes

| Class | Suitable work | Boundary |
| --- | --- | --- |
| `mechanical` | A bounded transformation with an explicit rule, identified scope, existing example, and direct check. | No substantive implementation choice or diagnosis remains. |
| `standard` | Settled design using repository patterns, routine local choices, ordinary multi-file coordination, meaningful tests, and local failure diagnosis. | The normal class for a specified feature or bug fix. |
| `advanced` | A settled design with sustained reasoning about interacting invariants or difficult failure modes. | State the irreducible reason, such as concurrency correctness, security boundaries, or data integrity. File count, a security filename, and missing specification are not reasons. |

Improve the task specification before raising its class. A stronger model does
not make an underspecified task ready.

