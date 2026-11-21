"""Shared billing-source rules for eval records and renderers."""

# Exact Omp Codex model IDs recorded with subscription billing.
OMP_CODEX_SUBSCRIPTION_MODELS = frozenset(
    {
        "openai-codex/gpt-6-luna",
        "openai-codex/gpt-6-sol",
        "openai-codex/gpt-6.1-sol",
        "openai-codex/gpt-6.1-terra",
        "openai-codex/gpt-5.6-terra",
    }
)


def uses_omp_codex_subscription(client_name: str, route: str, model: str) -> bool:
    """Whether an Omp Codex route has the approved subscription source."""
    return (
        client_name == "omp"
        and route == "omp"
        and model in OMP_CODEX_SUBSCRIPTION_MODELS
    )


def uses_codex_cli_subscription(client_name: str) -> bool:
    """Whether the client is the subscription-authenticated Codex CLI driver.

    The driver refuses an API-key environment variable and any login it cannot
    identify as a subscription, so a completed turn on this kind consumed
    allowance, not cash. The CLI reports no charge for that allowance; a list
    price is not a bill, so the record keeps tokens and no dollar figure.
    """
    return client_name == "codex-daily-driver"
