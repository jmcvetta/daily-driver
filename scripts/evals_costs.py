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


def uses_codex_cli_subscription(client_name: str, billing_source: str | None) -> bool:
    """Whether a Codex CLI run recorded the subscription as its billing source.

    The driver refuses an API-key environment variable and any login it cannot
    identify as a subscription, and writes `codex_billing_source: subscription`
    into the run only when that check passed. Requiring the recorded field —
    rather than the agent kind alone — keeps a historical SDK run of the same
    kind, or a test that disabled the guard, from being relabelled as
    subscription allowance.
    """
    return client_name == "codex-daily-driver" and billing_source == "subscription"
