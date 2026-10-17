"""Shared billing-source rules for eval records and renderers."""

# Exact Omp Codex model IDs recorded with subscription billing.
OMP_CODEX_SUBSCRIPTION_MODELS = frozenset(
    {
        "openai-codex/gpt-6-luna",
        "openai-codex/gpt-6-sol",
        "openai-codex/gpt-6.1-sol",
    }
)


def uses_omp_codex_subscription(client_name: str, route: str, model: str) -> bool:
    """Whether an Omp Codex route has the approved subscription source."""
    return (
        client_name == "omp"
        and route == "omp"
        and model in OMP_CODEX_SUBSCRIPTION_MODELS
    )
