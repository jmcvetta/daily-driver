---
name: atdd
description: >-
  Use when asked to establish or use ATDD, executable acceptance contracts,
  Gherkin, or Cucumber in a supported TypeScript repository. Supplies the
  runnable npm/pnpm bootstrap and real behavioral red/green execution route.
---

# TypeScript executable acceptance contracts

Use Gherkin with `@cucumber/cucumber` for the initial TypeScript ATDD workflow.
The bundled bootstrap supplies the reusable runner configuration; the target
repository supplies its product scenarios, trusted bindings, fixtures, and
implementation. Do not turn setup into a framework comparison or a product
pilot in another repository.

Read the active harness reference before resolving or invoking the program:
[`references/omp.md`](references/omp.md),
[`references/claude.md`](references/claude.md), or
[`references/codex.md`](references/codex.md). Resource paths belong there, not
in project-relative guesses.

## Supported setup

1. Use the task's worktree. Read `package.json`, the existing acceptance and
   test commands, strict TypeScript configuration, and CI selection rules.
   This bootstrap supports npm (`package-lock.json`) or pnpm
   (`pnpm-lock.yaml`), with exactly one lockfile and an existing manifest.
   Node 22, 24, or a later Node release supported by Cucumber is required.
   Do not invent a lockfile or choose a manager when the evidence is absent
   or ambiguous; establish the repository's intended package manager first.
2. If the repository already has a Cucumber configuration or harness, use it.
   The bootstrap refuses root `cucumber.json`, `cucumber.yaml`,
   `cucumber.yml`, `cucumber.js`, `cucumber.cjs`, or `cucumber.mjs`, and a foreign
   `acceptance/cucumber.json`. It does not migrate or overwrite existing
   configurations, registration files, or a different acceptance command.
3. Resolve the bundled script as the harness reference directs, then run:

   ```text
   node <resolved-skill-path>/scripts/bootstrap-typescript.mjs <target-repository>
   ```

   It reads the exact development dependency versions from Daily Driver's
   bundled root manifest: `@cucumber/cucumber` 13.3.0 and `tsx` 4.23.15.
   For npm it runs `npm install --save-dev --save-exact <name>@<version> ...`;
   for pnpm it runs `pnpm add --save-dev --save-exact <name>@<version> ...`.
   It uses the detected manager's `pkg set` to set
   `scripts.acceptance=cucumber-js --config acceptance/cucumber.json`.
   Use a package-manager version that supports `pkg set`; an unavailable
   command is a setup error, not permission to hand-edit the manifest.
   Dependency and script changes must go through that package manager, never
   direct manifest or lockfile edits.
4. For preinstalled dependencies or offline setup, add `--no-install` before
   the target path. This skips dependency installation but still uses the
   detected package manager to set the command. Supply the exact Cucumber
   and tsx dependencies before execution; this mode does not create a fake
   runner or claim that absent dependencies work.

## Generated harness

The bootstrap creates `acceptance/cucumber.json` and empty
`acceptance/features/`, `acceptance/steps/`, and `acceptance/support/`
directories. It adds no product feature, pending step, domain World, or
placeholder implementation. Preserve existing product files.

Configuration uses `acceptance/features/**/*.feature`, progress output, and
`publish: false`. With CommonJS or an absent package `type`, it uses
`requireModule: ['tsx/cjs']`, then requires the steps and support TypeScript
globs. With `type: 'module'`, its `import` list loads
`acceptance/support/register.mjs` first, followed by those TypeScript globs.
That registration calls `register()` from `tsx/esm/api`. These are Cucumber's
[documented transpilation mechanisms](https://github.com/cucumber/cucumber-js/blob/v13.3.0/docs/transpiling.md);
do not add a competing TypeScript loader.

A second run recognizes only the exact generated configuration, expected
acceptance command, and (for ESM) unchanged registration. It preserves these
files without rewriting them. Foreign or altered configuration is refused
rather than reset. Use an established harness directly once the operator has
customized it.

## Author and execute the contract

For a nontrivial behavioral feature, use `specification` for interactive
scenario agreement on the implementation task branch. Small tasks with
adequate ordinary acceptance and verification need no ATDD ceremony. Planning
notes are non-authoritative; no separate Markdown specification, requirement
registry, mandatory scenario IDs, scenario-SHA gate, or separate specification
PR is required.

Write concise product `.feature` files under `acceptance/features/`. Implement
TypeScript bindings under `acceptance/steps/` and needed hooks or fixtures under
`acceptance/support/`. Bindings call the real product interface and make
consequential assertions; they must not return fixed expected results or
simulate the product. Fixtures must be disposable and offline. Keep unrelated
setup out of scenarios and cover implementation details in lower-level tests.
Review bindings and fixtures independently so broken assertions cannot create
false acceptance.

From the target repository, run its detected command:

```sh
npm run acceptance
# In a pnpm repository, use instead:
pnpm run acceptance
```

Establish a failing agreed scenario for the expected missing or wrong product
behavior, not an undefined step, loader error, or unavailable service. Implement
to green, with required lower-level checks. Keep scenario, bindings, product
implementation, and tests on one task branch and ordinary PR. Record actual
red/green results; never claim execution from generated files alone.

Integrate `acceptance` into the target's established test command, strict
TypeScript checking, and CI path/package selection. Include the feature and
binding paths so their changes select the behavioral check; ensure TypeScript
steps and support are included in strict checking with the repository's
existing conventions. Read `pr` before validation or CI changes. The bootstrap
does not generate or rewrite CI, create another acceptance-evidence gate, or
weaken existing checks. Browser automation is not part of this harness; the
operator adds Playwright later only if a real pilot needs browser execution.

An implementation defect is repaired in implementation. A binding or fixture
that fails to express the agreed scenario is repaired with independent review.
A wrong, incomplete, or ambiguous scenario pauses only affected behavior for
operator agreement, recorded on the task or its specification issue; continue
unaffected work. Review may propose missing cases but cannot silently impose
new acceptance. After agreement, amend the same branch and PR. Use
`undertake`, `review-cycle`, and `epic` for their ordinary delivery gates and
scope boundaries, not a parallel ATDD approval process.
