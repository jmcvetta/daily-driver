# Repository instructions

## Adding a skill

When adding a skill under `skills/`, update both `README.md` and
`skills/README.md` in the same change. Add the skill to the root README's
compact overview and the skill catalog, with its purpose and a link to its
`SKILL.md`. Keep the task-based groups and workflow order; do not alphabetize
the lists. This keeps new skills discoverable without making the root README
a detailed manual.

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
