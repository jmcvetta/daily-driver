# Repository instructions

## Adding a skill

When adding a skill under `skills/`, add it to `skills/README.md` in the
matching task-based group, in workflow order; do not alphabetize the lists.
That catalog is the authoritative index of every published skill, with its
purpose and a link to its `SKILL.md`.

The root `README.md` is an entry point, not a second catalog. Do not recreate
a per-skill table there. Update it only when the new skill changes a
representative entry workflow the root README names.

## Breaking-change classification

These rules apply only when contributing to Daily Driver. They override the
published classification skill for this repository, not for its consumers.

Do not mark ordinary skill, rule, agent-decision, or internal-workflow changes
with `!` or a `BREAKING CHANGE:` footer. Changing agent instructions is this
product's purpose, not by itself a compatibility break. Keep the normal `fix`
or `feat` type for changes to shipped behavior; do not call them `docs`.

Use a breaking marker only for concrete user-facing disruption, such as
removing a user-invoked command or requiring configuration migration. Name the
previously supported use that fails and the action the user must take.
Without that evidence, omit both markers.

A wholesale revert uses `revert`. Reverting released instructions does not
automatically make it `revert!`; apply the same user-disruption test.
