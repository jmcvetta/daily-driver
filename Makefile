#===============================================================================
#
# Makefile
#
#===============================================================================

SHELL := /bin/bash
.SHELLFLAGS := -o pipefail -c

.PHONY: git_sync omp-update-daily-driver check check-plugin check-skills check-agents check-scripts \
	check-manifests check-manifest-fixtures check-constitution check-ask-in-chat \
	check-omp-extension check-omp-guard-differential check-omp-plugin \
	check-omp-cache-clean check-omp-review-cycle-route \
	check-review-cycle-fix-delta-route \
	check-omp-agent check-codex-agent check-eval-fixtures \
	check-task-worktree-fixture check-eval-arms check-step-names \
	check-evals-preflight check-labels check-labels-fixtures \
	check-story-fixtures check-infra evals-install evals-plan \
	evals-run-omp-glm-5-3 evals-run-omp-deepseek-v4-pro \
	evals-run-omp-gpt-5-6-sol evals-run-codex mcp-usage

# The `coder_eval` release the eval suites are written against. Pinned on
# purpose: being able to hold a version back is the whole reason the suites are
# not written for `claude plugin eval`, which ships inside the CLI and moves
# when it does. See docs/notes/0002-eval-harness.md.
CODER_EVAL_VERSION := 0.11.6

# Usage telemetry is ON by default in `coder_eval`, to a UiPath-controlled
# Application Insights endpoint, via a connection string baked into the
# package. It is ingestion-only and documented, and it is still not something a
# tool that may one day gate a merge should do without being asked. The
# decision here is OFF, and it is made in the one place both eval targets go
# through so it cannot be forgotten at a prompt.
CODER_EVAL := TELEMETRY_ENABLED=false coder-eval

# Dev dependencies of the Python legs, managed with uv. The repository has no
# Python packaging -- the root `pyproject.toml` declares no package, only the
# dev dependency group the legs read from -- and the legs that import nothing
# third-party stay that way. PyYAML is the one declared exception: the dev
# group names it, and the three scripts that read YAML import it
# (`scripts/check-eval-arms.py`, `scripts/evals-preflight.py`,
# `scripts/evals-variants.py`).
#
# The legs run under `uv run --frozen`: uv syncs the environment from
# `uv.lock` into `.venv/` at the repository root before the script starts.
# A venv interpreter's imports resolve from the venv's own site-packages --
# not from the user site, which resolves from `HOME`, and which
# `scripts/check-evals-preflight.py` redirects -- so the venv carries
# PyYAML into exactly the subprocess a user-site install cannot reach.
# `--frozen` refuses to run against a `uv.lock` that disagrees with
# `pyproject.toml` rather than re-resolving it: a drift is a loud failure
# for whoever edits the declaration next, not a silent environment change.
#
# CI installs uv itself -- one step in ci.yml, before `make check` -- and
# installs nothing else Python: the legs sync their own environment, so the
# laptop and CI get PyYAML from the same lock and cannot drift apart.

# git_sync: sync master with origin and delete local branches whose upstream
# is gone. A gone branch still checked out in a linked worktree has the
# worktree removed first; `git worktree remove` refuses a worktree holding
# uncommitted or untracked files (or one that is locked), and any refused
# worktree is warned about and kept, branch included.
git_sync:
	git checkout master
	git pull
	git fetch --prune
	@git branch -vv | awk '/: gone\]/ {sub(/^\+ /, ""); print $$1}' | \
	while read -r b; do \
		wt=$$(git worktree list --porcelain | awk -v b="$$b" '/^worktree /{p = substr($$0, 10)} /^branch /{if (substr($$0, 8) == "refs/heads/" b) {print p; exit}}'); \
		if [ -n "$$wt" ]; then \
			if ! git worktree remove "$$wt"; then \
				printf 'WARN: worktree for gone-upstream branch %s could not be removed; kept: %s\n' "$$b" "$$wt" >&2; \
				continue; \
			fi; \
			printf 'removed stale worktree: %s\n' "$$wt"; \
		fi; \
		git branch -D "$$b"; \
	done

# omp-update-daily-driver: refresh this repository's installed Omp plugin
# without deleting Omp's shared plugin state. Updating the marketplace replaces
# its cached clone; upgrading force-reinstalls the plugin's cached bytes.
omp-update-daily-driver:
	omp plugin marketplace update daily-driver
	omp plugin upgrade daily-driver@daily-driver


# check: everything CI asserts about this plugin. CI runs this target rather
# than restating its legs, so a leg added here is a leg CI gains — and there
# is no second command line to fall behind this one.
check: check-plugin check-skills check-agents check-scripts check-manifests \
	check-manifest-fixtures check-constitution check-ask-in-chat \
	check-omp-extension check-omp-guard-differential check-omp-cache-clean \
	check-omp-review-cycle-route \
	check-review-cycle-fix-delta-route check-omp-agent check-codex-agent \
	check-eval-fixtures check-task-worktree-fixture check-eval-arms \
	check-step-names check-evals-preflight check-labels check-labels-fixtures \
	check-story-fixtures

# `claude plugin validate --strict` reads one manifest at a time and picks the
# marketplace when handed a directory, so the plugin manifest is named
# separately. --strict is what turns its warnings — unrecognized fields, a
# marketplace entry whose version disagrees with plugin.json — into failures.
check-plugin:
	claude plugin validate --strict .
	claude plugin validate --strict .claude-plugin/plugin.json

check-skills:
	claude plugin validate --strict skills

# `validate` reads one directory at a time, and skills and agents are separate
# component kinds, so the agent panel needs its own invocation or it is never
# checked at all.
#
# The guard is what keeps that true in both directions. The plugin ships no
# agents today -- the four reviewers live in `attic/agents/` -- and handed a
# directory with no components `validate` falls back to looking for a manifest,
# finds none, and fails. Deleting the leg instead would mean an agent revived
# by `git mv` comes back unvalidated and nothing says so, which is exactly the
# silent failure the attic's cheap-move promise must not buy.
check-agents:
	@if compgen -G 'agents/*.md' > /dev/null; then \
		claude plugin validate --strict agents; \
	else \
		echo 'no agents/ to validate; the panel is in attic/agents/'; \
	fi

# `validate --strict` is a floor, not a ceiling: measured against the CLI, it
# passes an agent with an empty description, one whose name disagrees with its
# filename, and two agents claiming the same name — the last of which makes one
# of them permanently unreachable. This is the leg that catches those, for
# skills and agents alike.
#
# It is also the leg that holds `0011`'s split: no SKILL.md description or
# body names a harness's own tool routes, every reference file is linked from
# the body, and every reference link resolves. A route written back into a
# description or a body reads correctly on the harness it was written for, so
# nothing else catches it. See the docstring in the script.
check-manifests:
	python3 scripts/check-manifests.py

# check-manifest-fixtures: the acceptance test for the route half of
# check-manifests -- folded-description rejection, body rejection with its
# line number, neutral and invocation acceptance, routes allowed in reference
# files, and every route pattern exercised by name. Part of `check` because
# the guard itself is credential-free: a pattern that stops matching fails
# here rather than letting routes back into every description. See the
# script's docstring.
check-manifest-fixtures:
	python3 scripts/check-manifest-fixtures.py

# The credential-free half of the constitution's acceptance test: run both
# delivery hooks against synthetic event JSON and assert the constitution's
# body comes back, identically, from each — with the Omp `alwaysApply`
# frontmatter validated and stripped. The live half needs a model and therefore
# credentials, so it is `make evals-run TASKS='tasks/constitution/*.yaml'`
# rather than a leg here -- see the script's docstring for where the seam is
# and why.
check-constitution:
	python3 scripts/check-constitution.py

# The acceptance test for the other hook: run `hooks/ask-in-chat.py` against
# synthetic event JSON and assert the AskUserQuestion widget is denied, with a
# reason that sends the question to the chat reply. Credential-free like
# check-constitution, and needed for the same reason -- a hook that stops
# firing does not fail, it just quietly gives the widget back. Unlike the
# constitution there is no live half: a denial is enforced by the harness
# rather than believed by a session. See the script's docstring.
check-ask-in-chat:
	python3 scripts/check-ask-in-chat.py

# The acceptance test for the Omp runtime adapter: import extensions/
# daily-driver.js with a fake ExtensionAPI and assert the `ask` deny, the
# primary/detached-worktree mutation guard, the four tools, and package wiring.
# Credential-free like the other script legs, so it runs on a laptop and CI.
# Node ships with the harness; no package install is involved.
check-omp-extension:
	node scripts/check-omp-extension.mjs

# check-omp-guard-differential: the worktree guard measured against bash rather
# than against what somebody thought of. Each command shape is run for real in
# a throwaway repository, and the guard's verdict is checked against whether
# the primary checkout actually moved. Credential-free and network-free, but it
# runs git and bash dozens of times, so it is its own leg.
check-omp-guard-differential:
	node scripts/check-omp-guard-differential.mjs

# check-omp-plugin: the discovery half of the Omp story, which
# check-omp-extension cannot reach. It starts a real `omp --mode rpc` and asks
# the running agent what it got -- the skills on both the `--plugin-dir` and
# the installed-plugin routes, and the extension on the one route that loads
# it. Credential-free, against a throwaway HOME. See the script's docstring.
#
# Not part of `check`, for the reason check-infra is not: it needs a toolchain
# -- here a whole second harness -- and `check` must not start requiring Omp on
# a laptop that is only editing a skill. CI's `omp` job runs it, gated on the
# files that can actually break the Omp integration, and reports into
# `CI Success` either way so a break blocks a merge.
#
# No guard on `omp` either, and that is the same decision as check-infra's. A
# target nobody runs by accident should fail loudly when its toolchain is
# absent; a target inside `check` would have needed the guard, and the guard is
# what would have let it silently check nothing.
check-omp-plugin:
	python3 scripts/check-omp-plugin.py

# The cache refresh target changes user state in a real run. This check puts a
# fake `omp` first on PATH and asserts the command order and fail-fast behavior.
check-omp-cache-clean:
	python3 scripts/check-omp-cache-clean.py

# The Omp review-cycle reference is executable guidance. This credential-free
# check rejects a route that reaches for optional `github` instead of the
# essential `hub` and `bash` surface, and holds its cap and empty-result rules.
check-omp-review-cycle-route:
	python3 scripts/check-omp-review-cycle-route.py

# Every harness's fix-delta route is executable guidance too. This
# credential-free check rejects a blanket "unavailable on this harness" notice
# for `Verify the fix delta`, holds the briefed-subagent route and the brief's
# required elements in place across all three references, and holds the
# pointers `undertake` keeps to them. See the script's docstring.
check-review-cycle-fix-delta-route:
	python3 scripts/check-review-cycle-fix-delta-route.py

# check-scripts: lint the shell a skill ships. `claude plugin validate` reads
# manifests and never opens a `scripts/` file, so without this leg the plugin's
# executable half is the only part of the repository nothing checks.
#
# Unlike check-infra, this *is* part of `check`: shellcheck is a single small
# package present in the CI image, not a toolchain, so the laptop cost is one
# `apt install` rather than a reason to split the target.
#
# `-x` follows `source` directives so the eval fixtures' shared `lib.sh` is
# actually read rather than warned about; `--source-path=SCRIPTDIR` is what
# makes the `# shellcheck source=./lib.sh` annotations resolve beside the
# script rather than beside the caller's working directory.
check-scripts:
	shellcheck -x --source-path=SCRIPTDIR \
		skills/*/scripts/*.sh scripts/*.sh \
		evals/fixtures/*/shared/*.sh evals/fixtures/*/cases/*/*.sh

# check-omp-agent: the acceptance test for the Omp eval arm's frame reduction
# -- the skill-URL normalisation, the tool and argument renames, and the
# transcript shape every llm_judge rubric here anchors on. Part of `check`
# because `evals/coder-eval-omp/src/coder_eval_omp/rpc.py` imports nothing:
# neither coder-eval nor omp is needed to run it, and every one of the things
# it asserts fails as a silent zero rather than as an error. See the script's
# docstring, and evals/coder-eval-omp/README.md for the arm.
check-omp-agent:
	python3 scripts/check-omp-agent.py

# check-codex-agent: the acceptance test for the Codex eval arm's one
# normalisation -- the `[RESULT - ...]` transcript every judge rubric here
# anchors on. Part of `check` for the same reason check-omp-agent is:
# `evals/coder-eval-codex/src/coder_eval_codex/transcript.py` imports nothing,
# so neither coder-eval nor the Codex SDK is needed to run it, and the failure
# it catches is a row scored 0.0 rather than an error. It also asserts the
# rendering agrees byte for byte with the Omp arm's, which is what holds one
# rubric readable on both harnesses without either package depending on the
# other. See the script's docstring, and evals/coder-eval-codex/README.md for
# the arm.
check-codex-agent:
	python3 scripts/check-codex-agent.py

# check-eval-arms: the two arms are routed by tag, and nothing else holds the
# tags in step. A fork that loses its tag runs in both arms and grades one
# harness's route under the other's. Credential-free like the other script
# legs. See the script's docstring.
check-eval-arms:
	uv run --frozen python3 scripts/check-eval-arms.py

# check-eval-fixtures: build every review-depth fixture repository and assert
# it has the shape the `review` skill needs. Part of `check` because it needs
# only git and bash -- no model, no credentials -- and because a fixture that
# stops building does not turn the eval suite red, it turns every case into a
# silent 0 that reads exactly like a skill that never fires. See the script's
# docstring.
#
# This is not eval CI gating, which stays out of scope: nothing here runs a
# case or scores a model.
check-eval-fixtures:
	scripts/check-eval-fixtures.sh

# check-task-worktree-fixture: prove the linked and detached repositories used
# by the task-worktree behavior rows can satisfy every invariant they grade.
# The model-driven rows remain outside CI; their test instrument does not.
check-task-worktree-fixture:
	scripts/check-task-worktree-fixture.sh

# check-step-names: no file may cite a step of a numbered sequence by its
# number. The numbers are positional, so inserting a step silently invalidates
# every citation after it -- and a stale `step 7` reads exactly like a correct
# one. Part of `check` because it needs nothing but git and Python, and because
# the drift it catches is invisible to every other leg. See the script's
# docstring and docs/notes/0005-steps-are-cited-by-name.md.
check-step-names:
	python3 scripts/check-step-names.py

# check-evals-preflight: the acceptance test for `scripts/evals-preflight.py`
# -- synthetic task YAML in a temp dir, no credentials, no model. Part of
# `check` for the same reason as the other script legs: the guard it tests is
# itself credential-free, so nothing stops it running on a laptop and in CI.
# See the script's docstring for what it does and does not catch, and
# docs/notes/0012-the-judge-needs-its-own-transport.md for why the guard
# exists.
check-evals-preflight:
	uv run --frozen python3 scripts/check-evals-preflight.py

# check-labels: the issue-label standard is written twice -- the table in
# `issue-labels` and the resources in infra/github/labels.tf -- and this leg
# asserts the two say the same thing. Part of `check` because it needs nothing
# but Python, and because neither half's own tooling reads the other: `claude
# plugin validate` never opens a .tf file and `tofu validate` never opens a
# skill, so a row that has fallen behind reads exactly like one that has not.
# See the script's docstring.
check-labels:
	python3 scripts/check-labels.py

# check-labels-fixtures: exercise both marked skill tables against temporary
# Tofu fixtures. The real-tree checker alone cannot prove that a supplemental
# marker is still parsed or that its silent drift failures remain failures.
check-labels-fixtures:
	python3 scripts/check-labels-fixtures.py

# check-story-fixtures: execute offline direct-parent scenarios for the
# supplemental marker. It proves no live issue, label, or graph write is needed
# to cover additions, removals, graph failures, closure, and kind invariants.
check-story-fixtures:
	python3 scripts/check-story-fixtures.py

# check-infra: parse the OpenTofu stack without credentials. Not part of
# `check`, which must not start requiring OpenTofu on a laptop that is only
# editing a skill.
check-infra:
	$(MAKE) -C infra/github check-fmt validate

# evals-install: the pinned harness, from PyPI. `uv` fetches Python 3.13 itself,
# so this is the whole setup.
# Each `--with` puts an agent kind in the same environment as the pinned
# `coder-eval`, which is where `coder_eval` looks for its plugin entry points.
# Without them `agent: {type: omp}` and `agent: {type: codex-daily-driver}` do
# not resolve, and `plan` says so and exits 0 anyway -- which is what
# `evals-variants` is for.
#
# `coder-eval-codex` declares `coder-eval[codex]`, so the Codex SDK arrives with
# it. The pin above stays extras-free on purpose: the extra belongs to the one
# arm that needs it, not to the two that do not.
evals-install:
	uv tool install --python 3.13 coder-eval==$(CODER_EVAL_VERSION) \
		--with ./evals/coder-eval-omp \
		--with ./evals/coder-eval-codex

# evals-plan: validate every eval case without calling a model. Free, and it
# catches the config errors that otherwise cost a paid run to discover -- so
# run it before every `evals-run`.
#
# Both eval targets `cd evals` first, and that is load-bearing twice over. The
# plugin path in the experiment is relative and resolves against the process
# working directory, and `-e` must be passed explicitly because a wheel install
# of `coder-eval` resolves its default experiment to the one packaged inside
# the wheel and never looks in the working directory. Get either wrong and the
# suite runs -- against no plugin, or as a single unlabelled arm.
#
# Laptop-only, like git_sync: the cases need a live model, and this
# repository's CI is deliberately credential-free.
evals-plan: evals-variants
	cd evals && $(CODER_EVAL) plan -e experiments/with-without.yaml tasks/*/*.yaml
	cd evals && $(CODER_EVAL) plan -e experiments/omp-glm-5.3.yaml tasks/*/*.yaml
	cd evals && $(CODER_EVAL) plan -e experiments/omp-deepseek-v4-pro.yaml tasks/*/*.yaml
	cd evals && $(CODER_EVAL) plan -e experiments/omp-gpt-5.6-sol.yaml tasks/*/*.yaml
	cd evals && $(CODER_EVAL) plan -e experiments/codex.yaml tasks/*/*.yaml

# evals-variants: refuse to start when an arm's agent kind is not registered.
# `coder-eval plan` PRINTS "Variant 'omp': resolution failed" and then exits 0,
# so plan alone cannot catch an arm that will measure nothing -- measured, and
# the reason this target exists (issue #173). Free: no model, no task file.
# Wired in front of `evals-plan` rather than beside it, so the cheapest command
# anyone runs is the one that catches it. See the script's docstring and
# docs/notes/0013-the-omp-arm.md.
evals-variants:
	uv run --frozen python3 scripts/evals-variants.py evals/experiments/*.yaml

# evals-run: the whole suite on Claude Code, both variants. Costs real money --
# see evals/README.md for what and why. Narrow it with TASKS=, e.g.
#   make evals-run TASKS='tasks/pr/*.yaml'
TASKS ?= tasks/*/*.yaml

# evals-preflight: refuse to start evals-run when an enabled `llm_judge`
# criterion in $(TASKS) has no judge transport to run on -- `coder_eval`
# does not fail that case, it scores the criterion 0.0 and the run
# continues, which reads exactly like a real result and is not one. Not a
# `check` leg, for the same reason `evals-plan` is not one: it needs task
# YAML in hand to mean anything, and `make check` runs with none. See
# docs/notes/0012-the-judge-needs-its-own-transport.md for the defect this
# closes and what it costs to keep this mirroring `coder_eval`'s own rule.
#
# Runs from `evals/`, same as the model call below, so `$(TASKS)`'s default
# glob and any override resolve identically in both places.
evals-preflight:
	cd evals && uv run --project $(CURDIR) --frozen python3 ../scripts/evals-preflight.py $(TASKS)

# Each arm excludes the other two arms' forks, plus any row tagged out of it
# with `skip:<arm>`. The tag is what routes a row to its arm, and
# `make check-eval-arms` is what keeps the three sets in step.
#
# ONE COMMA-SEPARATED VALUE, never a repeated flag. `--exclude-tags` is a single
# `str` option that `coder_eval` splits on commas, so a second `--exclude-tags`
# replaces the first rather than adding to it -- and the exclusions it dropped
# come back as rows run in the wrong arm, silently, at full price.
evals-run: evals-plan evals-preflight
	cd evals && $(CODER_EVAL) run -e experiments/with-without.yaml \
		--exclude-tags omp-only,codex-only,skip:claude $(TASKS)

# evals-run-omp: run every recorded Omp model. Each named target keeps one
# model's two-arm result separate, so reports compare the plugin against the
# bare control without conflating model families.
evals-run-omp: evals-run-omp-glm-5-3 evals-run-omp-deepseek-v4-pro evals-run-omp-gpt-5-6-sol

# evals-run-omp-*: the same suites on Oh My Pi, per configured model. Needs
# `omp` on PATH and a model configured in the caller's own `~/.omp/agent/`,
# which the agent borrows rather than copies -- see evals/coder-eval-omp/README.md.
# Costs real money, like its siblings, and narrows the same way with TASKS=.
evals-run-omp-glm-5-3: evals-plan evals-preflight
	cd evals && $(CODER_EVAL) run -e experiments/omp-glm-5.3.yaml \
		--exclude-tags claude-only,codex-only,skip:omp $(TASKS)

evals-run-omp-deepseek-v4-pro: evals-plan evals-preflight
	cd evals && $(CODER_EVAL) run -e experiments/omp-deepseek-v4-pro.yaml \
		--exclude-tags claude-only,codex-only,skip:omp $(TASKS)

evals-run-omp-gpt-5-6-sol: evals-plan evals-preflight
	cd evals && $(CODER_EVAL) run -e experiments/omp-gpt-5.6-sol.yaml \
		--exclude-tags claude-only,codex-only,skip:omp $(TASKS)

# evals-run-codex: the same suites on Codex. Needs the Codex SDK, which
# `evals-install` brings in with `coder-eval-codex`, and OpenAI credentials the
# SDK can authenticate with. Costs real money, like its siblings, and narrows
# the same way with TASKS=.
#
# `skip:codex` is not a spare exclusion: `tasks/constitution/*` carries it,
# because `coder_eval`'s Codex agent links skills and installs no hooks, so no
# constitution reaches that arm and every row there would score 0 for the wrong
# reason. See docs/notes/0015-the-codex-arm.md.
evals-run-codex: evals-plan evals-preflight
	cd evals && $(CODER_EVAL) run -e experiments/codex.yaml \
		--exclude-tags claude-only,omp-only,skip:codex $(TASKS)

# mcp-usage: which GitHub MCP tools were actually called, rolled up to the
# toolsets that supply them. Laptop-only like git_sync — it reads Claude
# Code's session transcripts, which CI does not have — and deliberately not
# part of `check`. See docs/github-mcp.md for what the answer is for.
mcp-usage:
	python3 scripts/github-mcp-usage.py
