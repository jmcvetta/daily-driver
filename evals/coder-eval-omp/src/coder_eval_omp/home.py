"""Which files of a real Omp home the throwaway home may borrow, and how a
borrowed model configuration is restricted.

Pure on purpose, like `rpc`; it imports no `coder_eval` dependency.

A run needs a model, and Omp keeps the model and its credentials in the real
`~/.omp/agent/`. Everything else in that directory is a person's own setup, and
borrowing it makes the bare arm stop being bare. So the home is inherited by
allow list, never by "everything except".
"""

from __future__ import annotations

import os
from collections.abc import Sequence
from pathlib import Path

import yaml


#: The files that carry providers and credentials, in Omp 18.4.10:
#:
#: - `models.yml` holds custom providers.
#: - `agent.db` is Omp's "SQLite database for settings and auth storage"
#:   (`pi-utils/src/dirs.ts`, `getAgentDbPath`); the `-wal` and `-shm` siblings
#:   are its write-ahead log and shared memory, which a database in WAL mode
#:   needs beside it to read the same state.
#: - `secrets.yml` holds secrets that `models.yml` can reference.
#:
#: Left out by name, so a later "just add this one" meets the reason:
#:
#: - `mcp.json` is a person's MCP servers. Omp enables every connected MCP tool
#:   whatever `--tools` says, so an inherited one reaches both arms and escapes
#:   the row's tool list (measured, `docs/notes/0013-the-omp-arm.md`).
#: - `AGENTS.md`, `SYSTEM.md`, `SYSTEM_TEMPLATE.md`, `PERSONALITY.md` and
#:   `RULES.md` are a person's own instructions. Inherited, they load into the
#:   bare arm and into the treated arm's baseline alike.
#: - Caches and everything else the directory accumulates.
#:
#: `config.yml` is written by the agent instead of borrowed.
PROVIDER_FILES: tuple[str, ...] = (
    "models.yml",
    "agent.db",
    "agent.db-wal",
    "agent.db-shm",
    "secrets.yml",
)

#: The one file of the agent directory that carries provider and per-model
#: routing configuration (Omp 18.14.0, `packages/coding-agent/src/config/
#: models-config.ts`). Omp relocates its config root, and this file with it,
#: when `PI_CONFIG_DIR` or `OMP_PROFILE` is set; `launch.child_env` clears both
#: so the throwaway home is the configuration the session actually reads.
MODEL_CONFIG_FILE = "models.yml"

#: Model-override fields that name a second model for auxiliary work. On the
#: selected route they are a fallback away from it, so the restriction refuses
#: them rather than letting a run reach a model the experiment does not measure.
ALTERNATE_MODEL_FIELDS: tuple[str, ...] = ("compactionModel", "contextPromotionTarget")

#: The transport that can carry a Vercel gateway restriction. Omp's catalog
#: gives every `vercel-ai-gateway` model `api: anthropic-messages`, and that
#: provider never serializes `compat.vercelGatewayRouting`; only the Chat
#: Completions and Responses providers apply it (`applyOpenAIGatewayRouting`,
#: `packages/ai/src/providers/openai-shared.ts` in Omp 18.14.0). A restricted
#: model therefore selects Chat Completions, or the allowlist is silently
#: dropped and the request runs on whatever upstream the gateway picks.
GATEWAY_ROUTING_API = "openai-completions"

#: Request-body keys an inherited `compat.extraBody` must not set. Omp merges
#: the extra body over the built request, so either one replaces the enforced
#: model or upstream instead of adding to it.
EXTRA_BODY_CONFLICTS: tuple[str, ...] = ("model", "providerOptions")


def inherited_files(real_agent_dir: Path) -> list[Path]:
    """The files of `real_agent_dir` the throwaway home symlinks in.

    Only regular files named in `PROVIDER_FILES` that exist there; directories
    were never linked and stay unlinked.
    """
    return [
        real_agent_dir / name
        for name in PROVIDER_FILES
        if (real_agent_dir / name).is_file()
    ]


def restrict_model_upstreams(
    agent_dir: Path,
    provider: str,
    model_id: str,
    only: Sequence[str],
) -> Path:
    """Write `agent_dir/models.yml` with `model_id` restricted to `only`.

    The inherited `models.yml` is read and merged into a private copy, so the
    caller's file is never written through the symlink that borrows it. Only the
    selected model's Vercel gateway routing changes: unrelated providers,
    credentials, models and compatibility settings survive, and the model's
    upstream allowlist is replaced rather than unioned with what the operator
    configured. A personal `order` preference is dropped, because it names
    alternate upstreams for a route that now allows exactly `only`. The
    override also selects `GATEWAY_ROUTING_API`, because Omp's catalog
    transport for these models drops the allowlist instead of sending it.

    `provider` must be `vercel-ai-gateway` and `model_id` the exact catalog
    entry, which `rpc.model_commands` resolves from the experiment's selector.
    Duplicates in `only` collapse in first-seen order.

    Raises `ValueError` for an unreadable or malformed configuration, an empty
    allowlist, a selected model that names an alternate model in its override
    or its `models:` definition, or an inherited `compat.extraBody` that would
    replace the enforced model or upstream.
    """
    allowed = list(dict.fromkeys(only))
    if not allowed:
        raise ValueError("an upstream restriction must name at least one provider")
    path = agent_dir / MODEL_CONFIG_FILE
    document = _read_models(path)
    providers = _mapping(document, "providers", str(path))
    block = _mapping(providers, provider, f"{path}: providers")
    override = _selected_override(block, provider, model_id, path)
    _refuse_alternate_model(override, provider, model_id, path, "modelOverrides")
    _refuse_alternate_model(_custom_model(block, model_id, path), provider, model_id, path, "models")
    _refuse_extra_body(block, override, model_id, path)
    compat = _mapping(override, "compat", f"{path}: {provider}/{model_id}")
    routing = _mapping(compat, "vercelGatewayRouting", f"{path}: {provider}/{model_id}.compat")
    routing.pop("order", None)
    routing["only"] = allowed
    override["api"] = GATEWAY_ROUTING_API
    _write_private(path, document)
    return path


def _read_models(path: Path) -> dict[str, object]:
    """The model configuration at `path`, or an empty document where none exists."""
    if not path.exists():
        return {}
    try:
        document = yaml.safe_load(path.read_text(encoding="utf-8"))
    except OSError as error:
        raise ValueError(f"{path}: cannot read the inherited model configuration: {error}") from error
    except yaml.YAMLError as error:
        raise ValueError(f"{path}: the inherited model configuration is not valid YAML: {error}") from error
    if document is None:
        return {}
    if not isinstance(document, dict):
        raise ValueError(f"{path}: the model configuration must be a mapping, not {type(document).__name__}")
    return document


def _selected_override(
    block: dict[str, object], provider: str, model_id: str, path: Path
) -> dict[str, object]:
    """The `modelOverrides` entry for `model_id`, created where it is absent."""
    overrides = _mapping(block, "modelOverrides", f"{path}: providers.{provider}")
    return _mapping(overrides, model_id, f"{path}: providers.{provider}.modelOverrides")


def _custom_model(block: dict[str, object], model_id: str, path: Path) -> dict[str, object]:
    """The `models:` definition for `model_id`, or an empty mapping.

    A provider may define `models:` entries instead of borrowing the catalog.
    They carry the same auxiliary-model fields as an override, and the run
    reads them, so the restriction has to inspect them too.
    """
    models = block.get("models")
    if models is None:
        return {}
    if not isinstance(models, list):
        raise ValueError(f"{path}: providers.<provider>.models must be a list, not {type(models).__name__}")
    for entry in models:
        if not isinstance(entry, dict):
            raise ValueError(f"{path}: providers.<provider>.models entries must be mappings")
        if entry.get("id") == model_id:
            return entry
    return {}


def _refuse_alternate_model(
    definition: dict[str, object], provider: str, model_id: str, path: Path, where: str
) -> None:
    """Refuse an auxiliary-model target that points away from the selected model."""
    for field in ALTERNATE_MODEL_FIELDS:
        value = definition.get(field)
        if value and value != f"{provider}/{model_id}":
            raise ValueError(
                f"{path}: {provider}/{model_id} carries {field}={value!r} in {where}, which "
                "routes auxiliary work to another model; refusing to restrict a route that "
                "falls back away from the selected one"
            )


def _refuse_extra_body(
    block: dict[str, object], override: dict[str, object], model_id: str, path: Path
) -> None:
    """Refuse an inherited request body that could replace the enforced values.

    Omp applies `compat.extraBody` after the gateway routing, with a plain
    `Object.assign`, so an inherited `providerOptions` replaces the allowlist
    and an inherited `model` replaces the selected model. Provider `compat` is
    a baseline and per-model `compat` is merged over it, so a conflicting key
    in either layer is refused rather than silently dropped.
    """
    provider_compat = block.get("compat")
    if provider_compat is not None and not isinstance(provider_compat, dict):
        raise ValueError(f"{path}: providers.<provider>.compat must be a mapping")
    override_compat = override.get("compat")
    if override_compat is not None and not isinstance(override_compat, dict):
        raise ValueError(f"{path}: {model_id}.compat must be a mapping")
    for compat, layer in ((provider_compat, "provider"), (override_compat, "model")):
        if not compat:
            continue
        extra = compat.get("extraBody")
        if extra is None:
            continue
        if not isinstance(extra, dict):
            raise ValueError(f"{path}: the {layer} extraBody must be a mapping")
        for field in EXTRA_BODY_CONFLICTS:
            if field in extra:
                raise ValueError(
                    f"{path}: the {layer} extraBody sets {field!r}, which would replace the "
                    "enforced model or upstream in the outgoing request; refusing to restrict "
                    "a route whose request body is overridden"
                )


def _mapping(parent: dict[str, object], key: str, where: str) -> dict[str, object]:
    """`parent[key]` as a mapping, created when absent, refused when malformed."""
    value = parent.setdefault(key, {})
    if not isinstance(value, dict):
        raise ValueError(f"{where}.{key} must be a mapping, not {type(value).__name__}")
    return value


def _write_private(path: Path, document: dict[str, object]) -> None:
    """Replace `path` with a private copy, even where it is a borrowed symlink.

    `os.replace` swaps the directory entry, so the file the symlink pointed at
    keeps its content; writing through `Path.write_text` would follow the link
    into the operator's own `~/.omp/agent/`. Owner-only permissions match what
    Omp writes for the same file, which can carry a provider's credentials.
    """
    temporary = path.with_name(f"{path.name}.tmp")
    text = yaml.safe_dump(document, sort_keys=False)
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        handle.write(text)
    os.replace(temporary, path)
