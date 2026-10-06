#!/usr/bin/env python3
"""Hold the three eval arms in step: one tag each way, and a pair for every fork.

Rows under `evals/tasks/` that cannot be graded identically on every harness are
forked. Each fork is its own file carrying the arm tag of the arm it belongs to
— `claude-only`, `omp-only` or `codex-only` — and `make evals-run`,
`make evals-run-omp` and `make evals-run-codex` each exclude the other two arms'
tags. The tag is what routes a row to its arm.

A row that runs in some arms but not all of them cannot say so with an arm tag,
because an arm tag claims exactly one arm. `skip:<arm>` is the tag for that: it
takes the row out of the named arm and leaves it in the rest. Today the
`constitution` rows carry `skip:codex`, because `coder_eval`'s Codex agent links
skills and installs no hooks, so no constitution reaches that arm.

The `review-depth` rows are tagged `claude-only` without a counterpart: they pin
`agent.type: claude-code` and drive Claude's own settings and hooks, so they
have no form on another harness. Untagged, they would run inside the other arms
as Claude sessions and be billed and reported as those arms' results.

Nothing else checks any of that. A fork whose tag is missing runs in EVERY arm
and grades one harness's route under another's, which fails for a reason that
has nothing to do with the skill. A sibling that loses its own tag does the same
in the other direction. Neither is visible in a report; both are visible here,
in `make check`, for free.

WHAT IT ASSERTS

    No task carries more than one arm tag.
    Every row outside the `claude` arm names the row it forks, as a
    `forks:<task_id>` tag, and that row exists and carries an arm tag of its
    own. Most forks are not their sibling's name plus a suffix -- the sibling's
    name states one harness's route, which on another is the wrong answer -- so
    the pairing is declared rather than inferred from a filename. It is also
    what catches the sibling losing its own tag, which would run its route in
    every arm. The `claude` arm is exempt because its rows are the originals.
    A `forks:` tag belongs to a row that carries an arm tag, and never points at
    a row in its own arm.
    Every `task_id` in the tree is unique. Forking a file and forgetting its
    `task_id` is the easy mistake, and `coder_eval` keys its report on that id.
    A `task_id` whose suffix names an arm carries that arm's tag, and no other
    task carries it. The name and the tag are two statements of the same fact.
    A `skip:<arm>` names a known arm, is not contradicted by the row's own arm
    tag, and does not take the row out of every arm -- a row in no arm is a row
    nothing runs, which is spelled by deleting it.
    A task that pins `agent.type` names a kind one of the arms owns, and is
    tagged for that arm. The `review-depth` rows pin `claude-code` because they
    drive Claude's own settings and hooks, and an untagged one would run in the
    other arms as a Claude session -- billed to them, and reported as them. A
    kind NO arm owns fails outright: the built-in `codex` is registered, so
    every other guard passes it, and it would run in all three arms and score
    0.0 on every judged criterion.
    Each arm's `make evals-run…` target excludes every other arm's tag and its
    own `skip:`, in ONE comma-separated `--exclude-tags` value. The routing is
    stated in this file and in the Makefile, and neither half reads the other.
    Every experiment file exists, declares variants, and names its OWN arm's
    agent kind in each -- read with `evals-variants.py`'s own parser, so the
    parser that guards a paid run is itself exercised here. A registered but
    wrong kind is the case no other guard catches: `codex.yaml` set to the
    built-in `codex` resolves cleanly and then scores 0.0 on every judged row.

WHAT IT DOES NOT ASSERT

    That an arm resolves to a registered agent. That needs a `coder-eval`
    install, so it is `make evals-plan`'s guard (`scripts/evals-variants.py`)
    rather than a `check` leg.
    That the halves of a fork grade equivalent rules. Nothing but reading them
    can say that.

No third-party imports beyond PyYAML, declared in the root `pyproject.toml`'s
dev group and run under `uv run --frozen` (see the Makefile).
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path
from unittest.mock import patch


try:
    import yaml
except ImportError as exc:  # pragma: no cover - `make check` installs it first
    print(
        "error: PyYAML is required to read task YAML -- it is declared in the"
        " root pyproject.toml's dev group; run 'make check', which runs the"
        f" legs under uv (installed into .venv from uv.lock) ({exc})",
        file=sys.stderr,
    )
    sys.exit(1)

ROOT = Path(__file__).resolve().parent.parent
TASKS = ROOT / "evals" / "tasks"
EXPERIMENTS = ROOT / "evals" / "experiments"

# Every arm, by its short name. This table is the routing: the tag that claims a
# row for the arm, the `task_id` suffix that says so a second time, the
# `agent.type` kinds that belong to it, the experiment files that run it, and
# the Makefile targets that invoke those files. Every check below reads it, and
# two of them read it against something outside this script -- the Makefile's
# exclusions, and the experiments' own variants -- because the routing is
# stated in three places and none of them reads the others.
#
# `claude` has no id suffix because it is where the suites started and its rows
# are the ones the others fork.
ARMS: dict[str, dict[str, object]] = {
    "claude": {
        "tag": "claude-only",
        "id_suffix": None,
        "kinds": ("claude-code",),
        "experiment": "with-without.yaml",
        "run_target": "evals-run",
    },
    "omp": {
        "tag": "omp-only",
        "id_suffix": "-omp",
        "kinds": ("omp",),
        "ablation": True,
        # Focused skill-behavior probes cannot produce a meaningful bare-arm control.
        "focused_variants": {"omp-gpt-6.1-sol.yaml": "with-plugin"},
        "experiments": {
            "omp-glm-5.3.yaml": "vercel-ai-gateway/zai/glm-5.3",
            "omp-glm-5.3-flash.yaml": "vercel-ai-gateway/zai/glm-5.3-flash",
            "omp-deepseek-v4-pro.yaml": "vercel-ai-gateway/deepseek/deepseek-v4-pro",
            "omp-gpt-5.6-sol.yaml": "openai-codex/gpt-5.6-sol",
            "omp-gpt-6-sol.yaml": "vercel-ai-gateway/openai/gpt-6-sol",
            "omp-gpt-6-luna.yaml": "vercel-ai-gateway/openai/gpt-6-luna",
            "omp-gpt-6.1-sol.yaml": "openai-codex/gpt-6.1-sol",
        },
        "run_targets": {
            "evals-run-omp-glm-5-3": "omp-glm-5.3.yaml",
            "evals-run-omp-glm-5-3-flash": "omp-glm-5.3-flash.yaml",
            "evals-run-omp-deepseek-v4-pro": "omp-deepseek-v4-pro.yaml",
            "evals-run-omp-gpt-5-6-sol": "omp-gpt-5.6-sol.yaml",
            "evals-run-omp-gpt-6-sol": "omp-gpt-6-sol.yaml",
            "evals-run-omp-gpt-6-luna": "omp-gpt-6-luna.yaml",
            "evals-run-omp-gpt-6-1-sol": "omp-gpt-6.1-sol.yaml",
        },
        "bundle_target": "evals-run-omp",
    },
    "codex": {
        "tag": "codex-only",
        "id_suffix": "-codex",
        "kinds": ("codex-daily-driver",),
        "experiment": "codex.yaml",
        "run_target": "evals-run-codex",
    },
    # Measures models, not a harness, so it runs on Omp or on Claude Code:
    # each experiment file names its own kind and owns its model pin, and its
    # rows pin no kind. Personal Omp overlays are not inputs to this
    # validation. One parameterized Make target selects the experiment by
    # filename.
    "model-classes": {
        "tag": "model-classes",
        "id_suffix": None,
        "kinds": ("omp", "claude-code"),
        "ablation": False,
        "experiments": lambda: _model_classes_experiments(),
        "parameterized_target": "evals-run-classes",
        "parameterized_pattern": "-e experiments/classes-$(MODEL).yaml",
    },
}


def _model_classes_experiments() -> dict[str, None]:
    """Discover model-class experiments from the eval suite itself."""
    experiments = {path.name: None for path in EXPERIMENTS.glob("classes-*.yaml")}
    if not experiments:
        raise CheckFailed("no model-class experiments under evals/experiments")
    return experiments


def arm_experiments(spec: dict[str, object]) -> dict[str, str | None]:
    """Name each arm's experiment files and any independently pinned model."""
    experiments = spec.get("experiments")
    if callable(experiments):
        return {str(path): model for path, model in experiments().items()}
    if isinstance(experiments, dict):
        return {str(path): str(model) for path, model in experiments.items()}
    return {str(spec["experiment"]): None}


def arm_run_targets(spec: dict[str, object]) -> dict[str, str]:
    """The one-model Make targets that invoke this arm's experiment files."""
    targets = spec.get("run_targets")
    if isinstance(targets, dict):
        return {str(target): str(experiment) for target, experiment in targets.items()}
    return {str(spec["run_target"]): str(spec["experiment"])}

# Experiment files that are not arms. An arm answers "which harness does this
# row run on"; a comparison asks a different question of ONE arm -- the same
# suites under two revisions of the instructions -- so forcing it into the table
# above would blur the concept every check here defends. It is still named,
# because an experiment file nothing claims is one nothing says the agent kind
# of, which is the drift `check_experiments` exists to catch.
#
# `arm` is the arm whose kinds it runs and whose tag exclusions its Make target
# must repeat: a comparison measures one harness, never two.
COMPARISONS: dict[str, dict[str, str]] = {
    "base-vs-candidate.yaml": {"arm": "claude", "run_target": "evals-run-comparison"},
}

ARM_TAGS = {str(arm["tag"]): name for name, arm in ARMS.items()}

# Kind -> every arm that owns it. Almost always one arm, but `model-classes`
# runs on the `omp` and `claude-code` kinds the `omp` and `claude` arms also
# own -- it measures a model, not a harness -- so a kind can have more than one
# owner.
# `KIND_ARMS[kind]` (singular) does not exist for that reason: the pinned-kind
# check below asks "is this row's arm among the kind's owners", never "which
# one arm owns this kind".
KIND_OWNERS: dict[str, list[str]] = {}
for _name, _arm in ARMS.items():
    for _kind in _arm["kinds"]:  # type: ignore[union-attr]
        KIND_OWNERS.setdefault(str(_kind), []).append(_name)

# The namespaced tag a forked row names the row it forks with. `coder_eval`
# accepts a `key:value` tag, so the pairing needs no field of its own.
FORK_TAG = "forks:"

# The namespaced tag that takes a row out of ONE arm while leaving it in the
# rest. An arm tag cannot say that: it claims exactly one arm.
SKIP_TAG = "skip:"


class CheckFailed(Exception):
    """A failed assertion, with the detail that explains it."""


def _load_variant_kinds():
    """`evals-variants.py`'s experiment parser, loaded from its own file.

    The guard's filename carries a hyphen, so it is not importable by name.
    Loading it by path is what keeps ONE parser between the free check here and
    the guard that stands in front of a paid run.
    """
    import importlib.util

    path = ROOT / "scripts" / "evals-variants.py"
    spec = importlib.util.spec_from_file_location("evals_variants", path)
    if spec is None or spec.loader is None:
        raise CheckFailed(f"could not load {path.relative_to(ROOT)}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.variant_kinds


def load_tasks() -> list[tuple[Path, dict]]:
    """Every task file under `evals/tasks/`, parsed, with its path."""
    tasks: list[tuple[Path, dict]] = []
    for path in sorted(TASKS.glob("*/*.yaml")):
        try:
            document = yaml.safe_load(path.read_text(encoding="utf-8"))
        except (OSError, yaml.YAMLError) as exc:
            raise CheckFailed(f"{path.relative_to(ROOT)} does not parse: {exc}") from exc
        if not isinstance(document, dict):
            raise CheckFailed(f"{path.relative_to(ROOT)} does not parse as a mapping")
        tasks.append((path, document))
    if not tasks:
        raise CheckFailed(f"no task files under {TASKS.relative_to(ROOT)}")
    return tasks


def _tags(path: Path, document: dict) -> list[str]:
    """The row's tags, checked to be a list before anything reads them."""
    tags = document.get("tags") or []
    if not isinstance(tags, list):
        raise CheckFailed(f"{path.relative_to(ROOT)}: `tags` is not a list")
    return [tag for tag in tags if isinstance(tag, str)]


def _arm_of(path: Path, tags: list[str]) -> str | None:
    """The arm a row is claimed for, or None where it runs in every arm."""
    claimed = [ARM_TAGS[tag] for tag in tags if tag in ARM_TAGS]
    if len(claimed) > 1:
        raise CheckFailed(
            f"{path.relative_to(ROOT)} carries more than one arm tag ({sorted(claimed)}); an arm tag claims "
            f"exactly one arm, every arm is spelled by carrying none, and some-but-not-all is `{SKIP_TAG}<arm>`"
        )
    return claimed[0] if claimed else None


def check_arm_tags(tasks: list[tuple[Path, dict]]) -> None:
    """One arm tag at most per row, and every fork paired with its sibling."""
    arm_of_id: dict[str, str] = {}
    forks: list[tuple[Path, str, str]] = []

    for path, document in tasks:
        tags = _tags(path, document)
        arm = _arm_of(path, tags)
        task_id = document.get("task_id")
        if arm is not None and isinstance(task_id, str):
            arm_of_id[task_id] = arm

        declared = [tag.split(":", 1)[1] for tag in tags if tag.startswith(FORK_TAG)]
        if declared and arm is None:
            raise CheckFailed(
                f"{path.relative_to(ROOT)}: carries a `{FORK_TAG}` tag but no arm tag, so it would run in "
                "every arm and grade one harness's route under the others"
            )
        # The `claude` arm is where the suites started, so its rows are
        # originals and declare nothing. A row in any other arm exists because a
        # Claude row could not be graded there, so it must say which row that
        # was -- which is also what catches the sibling losing its own tag and
        # starting to run in every arm. A genuinely harness-native row with no
        # Claude counterpart would need this rule revisited; there is none, and
        # making that a deliberate decision rather than a silent gap is the
        # point of requiring it.
        if arm is not None and ARMS[arm]["id_suffix"] is not None and len(declared) != 1:
            raise CheckFailed(
                f"{path.relative_to(ROOT)}: an {ARMS[arm]['tag']} row must name the row it forks, as exactly "
                f"one `{FORK_TAG}<task_id>` tag; found {declared}"
            )
        if declared and arm is not None:
            forks.append((path, declared[0], arm))

        pinned = document.get("agent")
        pinned_kind = pinned.get("type") if isinstance(pinned, dict) else None
        if isinstance(pinned_kind, str) and pinned_kind:
            # A pinned kind outside the table is checked FIRST, and it is a
            # failure rather than a row to skip. `codex` -- the built-in, which
            # hands the judge bare text -- is a registered kind with no arm, so
            # gating this check on membership would let it through untagged, run
            # it in all three arms, bill each of them, and score 0.0 on every
            # judged criterion. That is the "registered but wrong kind" failure
            # `check_experiments` catches on the experiment side.
            if pinned_kind not in KIND_OWNERS:
                raise CheckFailed(
                    f"{path.relative_to(ROOT)}: pins `agent.type: {pinned_kind!r}`, which belongs to no arm; "
                    f"the kinds this repository runs are {sorted(KIND_OWNERS)}, and an unowned kind runs in "
                    "every arm, is billed to each, and is reported as each"
                )
            wanted_arms = KIND_OWNERS[pinned_kind]
            if arm not in wanted_arms:
                wanted_tags = sorted(str(ARMS[name]["tag"]) for name in wanted_arms)
                raise CheckFailed(
                    f"{path.relative_to(ROOT)}: pins `agent.type: {pinned_kind}` but is tagged for no arm "
                    f"that owns it ({wanted_tags}), so another arm's run would bill a session to itself "
                    "and report it as one"
                )

    for path, sibling, arm in forks:
        if sibling not in arm_of_id:
            raise CheckFailed(
                f"{path.relative_to(ROOT)} forks {sibling!r}, which is not a task carrying an arm tag; "
                "either the sibling lost its tag — and now runs in every arm — or the id is wrong"
            )
        if arm_of_id[sibling] == arm:
            raise CheckFailed(
                f"{path.relative_to(ROOT)} forks {sibling!r}, which is in the same arm ({arm}); a fork "
                "grades another harness's answer to the same question, so the two sit in different arms"
            )


def check_task_ids(tasks: list[tuple[Path, dict]]) -> None:
    """Ids are unique, and an arm's id suffix means that arm's tag."""
    seen: dict[str, Path] = {}
    for path, document in tasks:
        task_id = document.get("task_id")
        if not isinstance(task_id, str) or not task_id:
            raise CheckFailed(f"{path.relative_to(ROOT)} declares no task_id")
        if task_id in seen:
            raise CheckFailed(
                f"task_id {task_id!r} is used by both {seen[task_id].relative_to(ROOT)} and "
                f"{path.relative_to(ROOT)}; coder_eval keys its report on it"
            )
        seen[task_id] = path

        tags = _tags(path, document)
        arm = _arm_of(path, tags)
        for name, spec in ARMS.items():
            suffix = spec["id_suffix"]
            if not isinstance(suffix, str):
                continue
            if task_id.endswith(suffix) and arm != name:
                raise CheckFailed(
                    f"{path.relative_to(ROOT)}: task_id ends in {suffix} but the row is not tagged "
                    f"{spec['tag']}"
                )
            if arm == name and not task_id.endswith(suffix):
                raise CheckFailed(
                    f"{path.relative_to(ROOT)}: tagged {spec['tag']} but its task_id does not end in {suffix}"
                )


def check_skips(tasks: list[tuple[Path, dict]]) -> None:
    """A `skip:<arm>` names a known arm, and leaves the row in at least one."""
    for path, document in tasks:
        tags = _tags(path, document)
        skipped = {tag.split(":", 1)[1] for tag in tags if tag.startswith(SKIP_TAG)}
        if not skipped:
            continue
        unknown = sorted(skipped - set(ARMS))
        if unknown:
            raise CheckFailed(
                f"{path.relative_to(ROOT)}: `{SKIP_TAG}` names {unknown}, which is not an arm; the arms are "
                f"{sorted(ARMS)}"
            )
        arm = _arm_of(path, tags)
        if arm is not None:
            if arm in skipped:
                raise CheckFailed(
                    f"{path.relative_to(ROOT)}: tagged {ARMS[arm]['tag']} and `{SKIP_TAG}{arm}`, which claims "
                    "the row for an arm and takes it out of the same one"
                )
            raise CheckFailed(
                f"{path.relative_to(ROOT)}: carries an arm tag and a `{SKIP_TAG}` tag; an arm tag already "
                "names the only arm the row runs in, so the skip says nothing the run does not already know"
            )
        if skipped >= set(ARMS):
            raise CheckFailed(
                f"{path.relative_to(ROOT)}: skipped from every arm, so nothing runs it; that is spelled by "
                "deleting the row"
            )


def _check_exclude_tags(makefile: str, target: str, arm: str) -> str:
    """The named target's recipe excludes every other arm's tag and its own
    skip, in one comma-separated `--exclude-tags` value. Shared by the
    per-experiment loop below and the parameterized-target branch, because
    the requirement is the same either way: a target is one arm's route, and
    every row belonging to another arm must be excluded from it.
    """
    start = makefile.find(f"\n{target}:")
    if start < 0:
        raise CheckFailed(f"Makefile declares no `{target}` target, so the {arm} arm cannot be run")
    recipe = makefile[start + 1 :].split("\n\n", 1)[0]

    occurrences = recipe.count("--exclude-tags")
    if occurrences != 1:
        raise CheckFailed(
            f"Makefile `{target}` passes --exclude-tags {occurrences} time(s); it takes ONE "
            "comma-separated value, and a repeated flag silently replaces the earlier one"
        )
    value = recipe.split("--exclude-tags", 1)[1].split()[0]
    excluded = {tag.strip() for tag in value.split(",") if tag.strip()}

    wanted = {str(other["tag"]) for name, other in ARMS.items() if name != arm} | {f"{SKIP_TAG}{arm}"}
    if excluded != wanted:
        raise CheckFailed(
            f"Makefile `{target}` excludes {sorted(excluded)}; the {arm} arm must exclude "
            f"{sorted(wanted)} — every other arm's tag, and its own skip"
        )
    return recipe


def check_makefile_routing() -> None:
    """Each model target runs its experiment and excludes other arms and its skip."""
    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")

    for arm, spec in ARMS.items():
        parameterized_target = spec.get("parameterized_target")
        if parameterized_target is not None:
            # One Make target, parameterised by `MODEL=`, rather than one
            # target per experiment file -- `evals-run-classes` selects
            # `experiments/classes-$(MODEL).yaml` at recipe-expansion time, so
            # there is one recipe to check, not seventeen, and the pattern it
            # must contain names the Make variable literally rather than any
            # one resolved filename.
            target = str(parameterized_target)
            pattern = str(spec["parameterized_pattern"])
            recipe = _check_exclude_tags(makefile, target, arm)
            if pattern not in recipe:
                raise CheckFailed(f"Makefile `{target}` does not run {pattern}, so its model is not recorded")
            continue

        targets = arm_run_targets(spec)
        for target, experiment in targets.items():
            recipe = _check_exclude_tags(makefile, target, arm)
            if f"-e experiments/{experiment}" not in recipe:
                raise CheckFailed(
                    f"Makefile `{target}` does not run experiments/{experiment}, so its model is not recorded"
                )

        bundle_target = spec.get("bundle_target")
        if bundle_target is not None:
            start = makefile.find(f"\n{bundle_target}:")
            if start < 0:
                raise CheckFailed(f"Makefile declares no `{bundle_target}` target for the {arm} model set")
            dependencies = makefile[start + 1 :].splitlines()[0].split(":", 1)[1].split()
            if set(dependencies) != set(targets):
                raise CheckFailed(
                    f"Makefile `{bundle_target}` runs {sorted(dependencies)}; the {arm} model set is "
                    f"{sorted(targets)}"
                )

    for experiment, spec in COMPARISONS.items():
        arm, target = spec["arm"], spec["run_target"]
        recipe = _check_exclude_tags(makefile, target, arm)
        if f"-e experiments/{experiment}" not in recipe:
            raise CheckFailed(f"Makefile `{target}` does not run experiments/{experiment}")
        if "daily-driver-base/skills" not in makefile.split(f"\n{target}:", 1)[1].split("\n\n", 1)[0]:
            raise CheckFailed(
                f"Makefile `{target}` does not assert the base checkout; without it the run pays for "
                "both arms and measures plugin-versus-nothing"
            )


def check_comparison_variants(path: Path, document: dict) -> None:
    """A comparison's arms load different plugin roots, or it measures nothing.

    The one way a comparison fails silently is both arms pointing at the same
    checkout. Every criterion then scores the same by construction and the
    report reads exactly like "the rewrite changed nothing" -- which is the
    conclusion such a run is read for. Mutation-tested: without this, both arms
    set to `..` pass the whole file.
    """
    variants = [variant for variant in document.get("variants", []) if isinstance(variant, dict)]
    if len(variants) < 2:
        raise CheckFailed(
            f"{path.relative_to(ROOT)}: a comparison needs at least two variants to compare; found "
            f"{len(variants)}"
        )
    roots: dict[str, str] = {}
    for variant in variants:
        variant_id = str(variant.get("variant_id"))
        if variant_id in roots:
            # `roots` is keyed by id, so a duplicate would overwrite its twin
            # and the distinctness test below would compare one root against
            # one root and pass. Mutation-tested: two variants sharing an id
            # AND a root exited 0 without this.
            raise CheckFailed(
                f"{path.relative_to(ROOT)}: two variants share the id {variant_id!r}; `coder_eval` keys its "
                "report on that id, and the arms would be indistinguishable in it"
            )
        agent = variant.get("agent")
        plugins = agent.get("plugins") if isinstance(agent, dict) else None
        if not isinstance(plugins, list) or len(plugins) != 1 or not isinstance(plugins[0], dict):
            raise CheckFailed(
                f"{path.relative_to(ROOT)}: variant {variant_id!r} must load exactly one local plugin; a "
                "comparison varies the revision, so an arm loading none is the ablation and not this"
            )
        entry = plugins[0]
        if entry.get("type") != "local" or not entry.get("path"):
            raise CheckFailed(
                f"{path.relative_to(ROOT)}: variant {variant_id!r} must load a local plugin with a path"
            )
        roots[variant_id] = str(entry["path"])
    if len(set(roots.values())) != len(roots):
        raise CheckFailed(
            f"{path.relative_to(ROOT)}: the variants load the same plugin root {sorted(set(roots.values()))}; "
            "both arms would then run identical instructions and the report would read as 'no change' by "
            "construction"
        )

def check_single_arm_experiment(path: Path, document: dict, expected_variant: str) -> None:
    """Require a focused Omp run to measure only the declared plugin variant."""
    if expected_variant != "with-plugin":
        raise CheckFailed(f"{path.relative_to(ROOT)}: focused Omp runs must name `with-plugin`")
    variants = document.get("variants")
    if not isinstance(variants, list):
        raise CheckFailed(f"{path.relative_to(ROOT)}: focused Omp run needs one variant")
    variants_by_id: dict[str, dict] = {}
    for variant in variants:
        if not isinstance(variant, dict) or not isinstance(variant.get("variant_id"), str):
            raise CheckFailed(f"{path.relative_to(ROOT)}: focused Omp run has an invalid variant")
        variant_id = variant["variant_id"]
        if variant_id in variants_by_id:
            raise CheckFailed(f"{path.relative_to(ROOT)}: duplicate variant {variant_id!r}")
        variants_by_id[variant_id] = variant
    if set(variants_by_id) != {expected_variant}:
        raise CheckFailed(
            f"{path.relative_to(ROOT)}: focused Omp run must measure only `{expected_variant}`; "
            f"found {sorted(variants_by_id)}"
        )
    agent = variants_by_id[expected_variant].get("agent")
    if not isinstance(agent, dict) or agent.get("plugins") != [{"type": "local", "path": ".."}]:
        raise CheckFailed(f"{path.relative_to(ROOT)}: focused Omp run must load the daily-driver plugin")



def check_model_class_model(path: Path, document: dict) -> None:
    """Require a usable model pin inside each model-class experiment."""
    defaults = document.get("defaults")
    agent = defaults.get("agent") if isinstance(defaults, dict) else None
    model = agent.get("model") if isinstance(agent, dict) else None
    if not isinstance(model, str) or not model.strip():
        raise CheckFailed(f"{path.relative_to(ROOT)}: model-class experiment needs defaults.agent.model")


def check_experiments() -> None:
    """Every experiment names its arm; Omp pairs ablations and registers focused runs."""
    variant_kinds = _load_variant_kinds()
    arm_of_experiment = {
        experiment: (name, model)
        for name, spec in ARMS.items()
        for experiment, model in arm_experiments(spec).items()
    }
    for arm, spec in ARMS.items():
        focused = spec.get("focused_variants", {})
        if not isinstance(focused, dict) or set(focused) - set(arm_experiments(spec)):
            raise CheckFailed(f"the {arm} arm has an invalid focused-experiment declaration")

    files = sorted(EXPERIMENTS.glob("*.yaml"))
    if not files:
        raise CheckFailed(f"no experiment files under {EXPERIMENTS.relative_to(ROOT)}")
    for experiment, spec in COMPARISONS.items():
        if not (EXPERIMENTS / experiment).is_file():
            raise CheckFailed(
                f"{experiment} is declared a comparison, and there is no such file under "
                f"{EXPERIMENTS.relative_to(ROOT)}"
            )
    for experiment, (arm, _) in arm_of_experiment.items():
        if not (EXPERIMENTS / experiment).is_file():
            raise CheckFailed(
                f"the {arm} arm names {experiment} as its experiment, and there is no such file under "
                f"{EXPERIMENTS.relative_to(ROOT)}"
            )
    for path in files:
        try:
            variants = variant_kinds(path)
            document = yaml.safe_load(path.read_text(encoding="utf-8"))
        except (OSError, ValueError, yaml.YAMLError) as exc:
            raise CheckFailed(f"{path.relative_to(ROOT)}: {exc}") from exc
        if not isinstance(document, dict):
            raise CheckFailed(f"{path.relative_to(ROOT)} does not parse as a mapping")
        arm_and_model = arm_of_experiment.get(path.name)
        comparison = COMPARISONS.get(path.name)
        if arm_and_model is None and comparison is None:
            raise CheckFailed(
                f"{path.relative_to(ROOT)}: no arm and no comparison names this experiment file, so nothing "
                f"says which agent kind it should run; the arms and their files are {sorted(arm_of_experiment)} "
                f"and the comparisons are {sorted(COMPARISONS)}"
            )
        if arm_and_model is not None and comparison is not None:
            raise CheckFailed(
                f"{path.relative_to(ROOT)}: claimed as both an arm's experiment and a comparison; it is one "
                "or the other, and two claims make the agent kind ambiguous"
            )
        if arm_and_model is not None:
            arm, model = arm_and_model
        else:
            arm, model = comparison["arm"], None
            if arm not in ARMS:
                raise CheckFailed(
                    f"{path.relative_to(ROOT)}: declared a comparison on the {arm!r} arm, and there is no "
                    f"such arm; the arms are {sorted(ARMS)}"
                )
        wanted = ARMS[arm]["kinds"]
        for variant_id, kind in variants:
            if not kind:
                raise CheckFailed(f"{path.relative_to(ROOT)}: variant {variant_id!r} names no agent type")
            if kind not in wanted:  # type: ignore[operator]
                raise CheckFailed(
                    f"{path.relative_to(ROOT)}: variant {variant_id!r} names agent kind {kind!r}, which is not "
                    f"the {arm} arm's ({sorted(wanted)}); a registered-but-wrong kind resolves cleanly and "  # type: ignore[arg-type]
                    "then measures the wrong harness at full price"
                )
        if arm == "model-classes":
            check_model_class_model(path, document)
        if comparison is not None:
            check_comparison_variants(path, document)
        if model is not None:
            defaults = document.get("defaults") if isinstance(document, dict) else None
            agent = defaults.get("agent") if isinstance(defaults, dict) else None
            if not isinstance(agent, dict) or agent.get("model") != model:
                raise CheckFailed(f"{path.relative_to(ROOT)}: expected Omp model {model!r}")
            focused_variants = ARMS[arm].get("focused_variants", {})
            if isinstance(focused_variants, dict) and path.name in focused_variants:
                check_single_arm_experiment(path, document, str(focused_variants[path.name]))
                continue
            if not ARMS[arm].get("ablation"):
                continue
            variants_by_id = {
                variant.get("variant_id"): variant
                for variant in document.get("variants", [])
                if isinstance(variant, dict)
            }
            if set(variants_by_id) != {"bare", "with-plugin"}:
                raise CheckFailed(
                    f"{path.relative_to(ROOT)}: Omp must score `bare` and `with-plugin`; found "
                    f"{sorted(str(variant_id) for variant_id in variants_by_id)}"
                )
            bare = variants_by_id["bare"].get("agent")
            treated = variants_by_id["with-plugin"].get("agent")
            if not isinstance(bare, dict) or bare.get("plugins") != []:
                raise CheckFailed(f"{path.relative_to(ROOT)}: `bare` must load no plugins")
            if not isinstance(treated, dict) or treated.get("plugins") != [{"type": "local", "path": ".."}]:
                raise CheckFailed(f"{path.relative_to(ROOT)}: `with-plugin` must load the daily-driver plugin")

def check_model_class_experiment_policy() -> None:
    """Model-class experiments require a model without personal overlays."""
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        experiments = root / "evals" / "experiments"
        experiments.mkdir(parents=True)
        with patch(__name__ + ".ROOT", root), patch(__name__ + ".EXPERIMENTS", experiments):
            try:
                _model_classes_experiments()
            except CheckFailed:
                pass
            else:
                raise CheckFailed("the model-class arm requires an experiment")
            (experiments / "classes-personal.yaml").write_text(
                "defaults:\n  agent:\n    model: example/model\n", encoding="utf-8"
            )
            if _model_classes_experiments() != {"classes-personal.yaml": None}:
                raise CheckFailed("model-class experiments must be discovered without personal overlays")
            experiment = experiments / "classes-personal.yaml"
            try:
                check_model_class_model(experiment, {})
            except CheckFailed:
                pass
            else:
                raise CheckFailed("model-class experiments require their own model pin")
            check_model_class_model(experiment, yaml.safe_load(experiment.read_text(encoding="utf-8")))


def check_the_checks() -> None:
    """Prove the assertions above can fail, against synthetic rows.

    A check that cannot fail is a check that passes for ever, silently, which is
    the same class of defect as the drift it is here to catch. These rows never
    touch the filesystem, so the cost is nothing.
    """
    check_model_class_experiment_policy()
    here = TASKS / "pr"
    cases: list[tuple[str, list[tuple[Path, dict]], object]] = [
        (
            "two arm tags on one row",
            [(here / "x.yaml", {"task_id": "x", "tags": ["claude-only", "omp-only"]})],
            check_arm_tags,
        ),
        (
            "a forked row naming no sibling",
            [(here / "x.yaml", {"task_id": "x-omp", "tags": ["omp-only"]})],
            check_arm_tags,
        ),
        (
            "a forked row whose sibling is not tagged",
            [
                (here / "x.yaml", {"task_id": "x-omp", "tags": ["omp-only", "forks:x"]}),
                (here / "y.yaml", {"task_id": "x", "tags": []}),
            ],
            check_arm_tags,
        ),
        (
            "a forked row pointing inside its own arm",
            [
                (here / "x.yaml", {"task_id": "x-codex", "tags": ["codex-only", "forks:y-codex"]}),
                (here / "y.yaml", {"task_id": "y-codex", "tags": ["codex-only", "forks:y"]}),
                (here / "z.yaml", {"task_id": "y", "tags": ["claude-only"]}),
            ],
            check_arm_tags,
        ),
        (
            "a `forks:` tag on a row in every arm",
            [(here / "x.yaml", {"task_id": "x", "tags": ["forks:y"]})],
            check_arm_tags,
        ),
        (
            "a claude-code task with no arm tag",
            [(here / "x.yaml", {"task_id": "x", "tags": [], "agent": {"type": "claude-code"}})],
            check_arm_tags,
        ),
        (
            "a task pinning a kind no arm owns",
            [(here / "x.yaml", {"task_id": "x", "tags": [], "agent": {"type": "codex"}})],
            check_arm_tags,
        ),
        (
            "a codex task tagged for another arm",
            [
                (
                    here / "x.yaml",
                    {"task_id": "x-omp", "tags": ["omp-only", "forks:x"], "agent": {"type": "codex-daily-driver"}},
                ),
                (here / "y.yaml", {"task_id": "x", "tags": ["claude-only"]}),
            ],
            check_arm_tags,
        ),
        (
            "a duplicated task_id",
            [
                (here / "a.yaml", {"task_id": "same", "tags": []}),
                (here / "b.yaml", {"task_id": "same", "tags": []}),
            ],
            check_task_ids,
        ),
        (
            "an -omp id without the arm tag",
            [(here / "a.yaml", {"task_id": "pr-01-omp", "tags": []})],
            check_task_ids,
        ),
        (
            "an omp-only tag without the -omp id",
            [(here / "a.yaml", {"task_id": "pr-01", "tags": ["omp-only"]})],
            check_task_ids,
        ),
        (
            "a -codex id without the arm tag",
            [(here / "a.yaml", {"task_id": "pr-01-codex", "tags": []})],
            check_task_ids,
        ),
        (
            "a codex-only tag without the -codex id",
            [(here / "a.yaml", {"task_id": "pr-01", "tags": ["codex-only"]})],
            check_task_ids,
        ),
        (
            "a skip naming no arm this repository has",
            [(here / "a.yaml", {"task_id": "x", "tags": ["skip:opencode"]})],
            check_skips,
        ),
        (
            "a skip beside an arm tag",
            [(here / "a.yaml", {"task_id": "x-codex", "tags": ["codex-only", "skip:omp"]})],
            check_skips,
        ),
        (
            "a row skipped from every arm",
            [
                (
                    here / "a.yaml",
                    {"task_id": "x", "tags": [f"{SKIP_TAG}{arm}" for arm in ARMS]},
                )
            ],
            check_skips,
        ),
    ]
    for name, rows, checker in cases:
        try:
            checker(rows)  # type: ignore[operator]
        except CheckFailed:
            continue
        raise CheckFailed(f"the check for {name!r} did not fail on a row that should fail it")

    # `check_comparison_variants` takes a document rather than task rows, so it
    # gets its own loop instead of a fourth column in the table above. Same
    # doctrine: a check nobody has seen fail is a check that passes for ever.
    synthetic = EXPERIMENTS / "synthetic.yaml"
    one = {"type": "local", "path": ".."}
    documents: list[tuple[str, dict]] = [
        (
            "a comparison with one variant",
            {"variants": [{"variant_id": "only", "agent": {"plugins": [one]}}]},
        ),
        (
            "a comparison whose arms load the same root",
            {
                "variants": [
                    {"variant_id": "base", "agent": {"plugins": [one]}},
                    {"variant_id": "candidate", "agent": {"plugins": [one]}},
                ]
            },
        ),
        (
            "a comparison arm loading no plugin",
            {
                "variants": [
                    {"variant_id": "base", "agent": {"plugins": []}},
                    {"variant_id": "candidate", "agent": {"plugins": [one]}},
                ]
            },
        ),
        (
            "a comparison whose variants share an id",
            {
                "variants": [
                    {"variant_id": "base", "agent": {"plugins": [one]}},
                    {"variant_id": "base", "agent": {"plugins": [one]}},
                ]
            },
        ),
        (
            "a comparison arm loading a plugin with no path",
            {
                "variants": [
                    {"variant_id": "base", "agent": {"plugins": [{"type": "local"}]}},
                    {"variant_id": "candidate", "agent": {"plugins": [one]}},
                ]
            },
        ),
    ]
    for name, document in documents:
        try:
            check_comparison_variants(synthetic, document)
        except CheckFailed:
            continue
        raise CheckFailed(f"the check for {name!r} did not fail on a document that should fail it")

    focused_valid = {
        "variants": [
            {
                "variant_id": "with-plugin",
                "agent": {"plugins": [{"type": "local", "path": ".."}]},
            }
        ]
    }
    check_single_arm_experiment(synthetic, focused_valid, "with-plugin")
    focused_invalid = [
        ("focused Omp run with no plugin arm", {"variants": [{"variant_id": "bare", "agent": {"plugins": []}}]}),
        (
            "focused Omp run with an extra ablation arm",
            {
                "variants": [
                    {"variant_id": "bare", "agent": {"plugins": []}},
                    {"variant_id": "with-plugin", "agent": {"plugins": [{"type": "local", "path": ".."}]}},
                ]
            },
        ),
        (
            "focused Omp run without the daily-driver plugin",
            {"variants": [{"variant_id": "with-plugin", "agent": {"plugins": []}}]},
        ),
    ]
    for name, document in focused_invalid:
        try:
            check_single_arm_experiment(synthetic, document, "with-plugin")
        except CheckFailed:
            continue
        raise CheckFailed(f"the check for {name!r} did not fail")


def main() -> None:
    check_the_checks()
    tasks = load_tasks()
    check_arm_tags(tasks)
    check_task_ids(tasks)
    check_skips(tasks)
    check_makefile_routing()
    check_experiments()

    counts = []
    for name, spec in ARMS.items():
        rows = sum(1 for _, document in tasks if str(spec["tag"]) in (document.get("tags") or []))
        counts.append(f"{rows} {name}")
    skipped = sum(
        1 for _, document in tasks if any(str(tag).startswith(SKIP_TAG) for tag in (document.get("tags") or []))
    )
    print(
        f"check-eval-arms: {len(tasks)} task(s), arm-tagged {', '.join(counts)}, "
        f"{skipped} skipped from an arm, every fork paired and every variant named"
    )


if __name__ == "__main__":
    try:
        main()
    except CheckFailed as failure:
        print(f"check-eval-arms: {failure}", file=sys.stderr)
        sys.exit(1)
