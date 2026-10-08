#===============================================================================
#
# Makefile
#
#===============================================================================

SHELL := /bin/bash
.SHELLFLAGS := -o pipefail -c

.PHONY: __git_sync_run check-git-sync omp-update-daily-driver check check-plugin check-skills check-agents check-scripts \
	check-manifests check-manifest-fixtures check-release-paths check-constitution check-ask-in-chat check-title-gate \
	check-omp-extension check-omp-guard-differential check-omp-plugin check-model-class-roles \
	check-omp-cache-clean \
	check-omp-agent check-omp-eval-guard check-omp-eval-guard-live check-omp-embark-title-live check-omp-agent-settle check-codex-agent check-eval-fixtures check-model-classes-grader \
	check-task-worktree-fixture check-evals-setup-omp check-eval-arms check-agent-judges check-evals-judge check-ci-scope check-step-names \
	check-worktrunk-install check-evals-preflight check-evals-provenance check-evals-results check-labels check-labels-fixtures \
	check-infra check-plugin-validity check-runtime \
	check-eval-tooling check-issue-infra check-model-telemetry model-telemetry \
	evals-install evals-setup-omp evals-plan \
	evals-judge-preflight evals-judge-calibrate \
	evals-variants evals-preflight evals-record evals-render-routes evals-render-results evals-run evals-run-omp \
	evals-run-omp-glm-5-3 evals-run-omp-glm-5-3-flash evals-run-omp-deepseek-v4-pro \
	check-claude-dependency \
	evals-run-omp-gpt-5-6-sol evals-run-omp-gpt-6-sol evals-run-omp-gpt-6-luna evals-run-codex evals-run-comparison evals-run-classes mcp-usage

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
#
# CREDENTIALS: Claude arms and judges inherit this shell's subscription auth.
# Never run an Anthropic model through the API or the Vercel AI Gateway, and
# set no ANTHROPIC_* variable. See "Credentials" in evals/README.md.
CODER_EVAL := TELEMETRY_ENABLED=false coder-eval

# The Omp arms' environment, for every target. Omp reads the Vercel AI Gateway
# key from AI_GATEWAY_API_KEY; a Claude Code cloud container exports it as
# VERCEL_AI_GATEWAY_API_KEY, so the second name fills the first when it is
# unset. Omp's installer puts `omp` in ~/.local/bin, or in ~/.bun/bin when it
# installs through Bun; both are appended, so they shadow nothing. See
# scripts/evals-setup-omp.sh for the source of the key name.
AI_GATEWAY_API_KEY ?= $(VERCEL_AI_GATEWAY_API_KEY)
ifneq ($(AI_GATEWAY_API_KEY),)
export AI_GATEWAY_API_KEY
endif
export PATH := $(PATH):$(HOME)/.local/bin:$(HOME)/.bun/bin

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

# __git_sync_run: implementation for `wt sync`, which first switches the caller
# to master's worktree. Offer gone-upstream branches to Worktrunk for cleanup.
# Worktrunk decides whether each branch is integrated; it refuses dirty or
# locked worktrees and keeps branches that still add changes.
__git_sync_run:
	git pull
	git fetch --prune
	@git branch -vv | awk '/: gone\]/ {sub(/^\+ /, ""); print $$1}' | \
	while read -r b; do \
		wt=$$(git worktree list --porcelain | awk -v b="$$b" '/^worktree /{p = substr($$0, 10)} /^branch /{if (substr($$0, 8) == "refs/heads/" b) {print p; exit}}'); \
		if [ -n "$$wt" ]; then \
			if ! wt remove --foreground "$$wt"; then \
				printf 'WARN: worktree for gone-upstream branch %s could not be removed; kept: %s\n' "$$b" "$$wt" >&2; \
				continue; \
			fi; \
			printf 'removed stale worktree: %s\n' "$$wt"; \
		else \
			wt remove --foreground "$$b"; \
		fi; \
	done

# omp-update-daily-driver: refresh this repository's installed Omp plugin
# without deleting Omp's shared plugin state. Updating the marketplace replaces
# its cached clone; upgrading force-reinstalls the plugin's cached bytes.
omp-update-daily-driver:
	omp plugin marketplace update daily-driver
	omp plugin upgrade daily-driver@daily-driver


# `check` remains the local all-groups convenience target. CI selects leaf
# checks from changed inputs and runs each selected check as a named step.
check: check-ci-scope check-step-names check-release-paths check-plugin-validity check-runtime check-eval-tooling check-issue-infra

check-ci-scope:
	node scripts/check-ci-scope.mjs

check-plugin-validity: check-plugin check-skills check-agents \
	check-manifests check-manifest-fixtures check-claude-dependency

check-runtime: check-constitution check-ask-in-chat check-title-gate check-omp-extension check-model-class-roles \
	check-omp-guard-differential check-omp-cache-clean check-git-sync \
	check-task-worktree-fixture check-worktrunk-install check-scripts

# Exercise the shell-integrated alias in isolated Git repositories only.
check-git-sync:
	python3 scripts/check-git-sync.py

check-eval-tooling: check-omp-agent check-omp-eval-guard check-codex-agent check-eval-fixtures check-model-classes-grader \
	check-eval-arms check-agent-judges check-evals-judge check-evals-preflight check-evals-provenance \
	check-evals-results check-model-telemetry check-evals-setup-omp


check-issue-infra: check-labels check-labels-fixtures

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

# check-release-paths: every tracked top-level directory is either shipped or
# named in release-please's `exclude-paths`, and every excluded entry is a real
# top-level directory. The list is a denylist, so this is what makes a new
# directory's release status a decision rather than a default. See the
# docstring in the script. It runs in CI's always-on repository-wide job, since
# deleting a top-level directory selects no path-filtered job.
check-release-paths:
	python3 scripts/check-release-paths.py

# check-manifest-fixtures: the acceptance test for the route half of
# check-manifests -- folded-description rejection, body rejection with its
# line number, neutral and invocation acceptance, routes allowed in reference
# files, and every route pattern exercised by name. Part of `check` because
# the guard itself is credential-free: a pattern that stops matching fails
# here rather than letting routes back into every description. See the
# script's docstring.
check-manifest-fixtures:
	python3 scripts/check-manifest-fixtures.py

# Catch a plugin marketplace install that returns success without installing
# its dependency, and a migration that leaves both Worktrunk identities enabled.
check-claude-dependency:
	bash scripts/check-claude-dependency.sh

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

# The acceptance test for the title gate: run `hooks/title-gate.py` against
# synthetic event JSON in both modes and assert the session's first issue
# comment and first dispatch are denied until it is titled. Credential-free
# like check-ask-in-chat, and needed for the same reason -- a gate that stops
# firing does not fail, it just gives the step back to the prose. See the
# script's docstring.
check-title-gate:
	python3 scripts/check-title-gate.py

# The acceptance test for the Omp runtime adapter: import extensions/
# daily-driver.js with a fake ExtensionAPI and assert the `ask` deny, the
# primary/detached-worktree mutation guard, the four tools, and package wiring.
# Credential-free like the other script legs, so it runs on a laptop and CI.
# Node ships with the harness; no package install is involved.
check-omp-extension:
	node scripts/check-omp-extension.mjs

check-model-class-roles:
	node scripts/check-model-class-role-defaults.mjs

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
# a laptop that is only editing a skill. The `CI Success` job runs it when the
# component filter selects Omp integration, so a break blocks a merge.
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

# check-scripts: ShellCheck the shell under skills, scripts, and eval fixtures.
# It belongs to check-runtime because eval-fixture scripts are runtime inputs;
# skills and top-level scripts select that group as well.
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

# check-omp-eval-guard: the Omp eval arm's sandbox guard, driven with a fake
# `pi` against every bypass issue #461 measured -- a `;` list, scheme case, a
# `write` the row did not grant. Each one fails open: the row reaches GitHub
# and nothing reports it. Node only, like check-omp-extension.
check-omp-eval-guard:
	node scripts/check-omp-eval-guard.mjs

# check-omp-eval-guard-live: the same guard inside a real `omp --mode rpc`,
# with the plugin linked and a local mock model scripting the tool calls. It
# proves what the fake `pi` cannot: that Omp loads `-e` beside the plugin and
# honours the refusals, and that `fetch.enabled: false` refuses a URL read.
# Needs `omp`, so it runs in CI's Omp job, for check-omp-plugin's reason.
check-omp-eval-guard-live:
	python3 scripts/check-omp-eval-guard-live.py

# The live embark barrier needs a real Omp but not the eval guard: issue://
# must reach its offline fixture client to provide the canonical issue metadata.
check-omp-embark-title-live:
	python3 scripts/check-omp-embark-title-live.py

# check-omp-agent-settle: the acceptance test for the Omp arm's early-stop
# record -- that a replicate which early-stops on `skill_triggered` cannot
# final-score 0 on that same criterion, the failure the first live run
# measured (2026-09-16, issue #206): the watcher latched a pass on the
# in-flight skill call while the abort settle dropped every event the frozen
# trajectory is built from. It drives `coder_eval_omp.agent` against a fake
# `omp --mode rpc`, so unlike check-omp-agent it needs the pinned
# `coder_eval` install -- `make evals-install` provides it -- and no network.
# Not a `check` leg, for the toolchain reason check-omp-plugin's comment
# records; the evals that need it installed are the ones it protects.
check-omp-agent-settle:
	uv run --python 3.13 --with coder-eval==$(CODER_EVAL_VERSION) \
		--with ./evals/coder-eval-omp \
		python3 scripts/check-omp-agent-settle.py

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

# check-agent-judges: every `agent_judge` denies itself the built-in tools, so
# it grades the transcript it was given instead of reading the sandbox and
# timing out without a verdict. See the script's docstring.
check-agent-judges:
	uv run --frozen python3 scripts/check-agent-judges.py

# check-evals-judge: the offline acceptance test for `scripts/evals-judge.py` --
# independent subject/judge selection, unavailable-judge refusal, no fallback,
# verdict errors and timeouts, transcript-only isolation and judge provenance,
# against a fake `omp`. No model, no credentials, no network.
check-evals-judge:
	uv run --frozen python3 scripts/check-evals-judge.py

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

# check-model-classes-grader: the model-classes grader applies the answer key
# over an agent's tree -- same-hunk edits, a test file both created, committed
# work -- instead of scoring a correct change 0. Needs git and bash only. See
# the script's header.
check-model-classes-grader:
	scripts/check-model-classes-grader.sh

# check-task-worktree-fixture: prove the linked and detached repositories used
# by the task-worktree behavior rows can satisfy every invariant they grade.
# The model-driven rows remain outside CI; their test instrument does not.
check-task-worktree-fixture:
	scripts/check-task-worktree-fixture.sh

# Conditional user-scope installation is tested with stub package managers;
# the fixtures never invoke a real installer or access the network.
check-worktrunk-install:
	scripts/check-worktrunk-install.sh

# check-evals-setup-omp: evals-setup-omp's key resolution, exact model match
# and no-reinstall rule, against a stub `omp` and `curl` in a throwaway HOME.
# Offline: it never runs the real installer or calls the gateway.
check-evals-setup-omp:
	scripts/check-evals-setup-omp.sh

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
# See the script's docstring and docs/notes/0014-the-judge-runs-on-the-subscription.md
# for the no-metered-API boundary.
check-evals-preflight:
	uv run --frozen python3 scripts/check-evals-preflight.py

# check-evals-provenance: validate committed records and exercise the recorder
# against synthetic run artifacts. It never starts a model or reads a paid run.
check-evals-provenance:
	uv run --frozen python3 scripts/check-evals-provenance.py

# check-evals-results: `evals/RESULTS.md` matches a fresh render of every
# committed record, so a record cannot land without its row. Standard library
# only, so plain `python3`.
check-evals-results:
	python3 scripts/evals-render-results.py --check

# check-model-telemetry: `scripts/model-telemetry.py`'s claim, readiness and
# review-verification comment parsers, checked against fixture text -- no
# credentials, no network. `model-telemetry.py` itself imports nothing beyond
# the standard library, so unlike its `uv run --frozen` neighbours above it
# runs under plain `python3`. See the script's docstring.
check-model-telemetry:
	python3 scripts/check-model-telemetry.py

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
#
# Both local agents keep one version, so uv would reuse its cached build and an
# edit to either would never reach the harness. `--reinstall-package` rebuilds
# them from the working tree every time.
evals-install:
	uv tool install --python 3.13 coder-eval==$(CODER_EVAL_VERSION) \
		--with ./evals/coder-eval-omp \
		--with ./evals/coder-eval-codex \
		--reinstall-package coder-eval-omp \
		--reinstall-package coder-eval-codex

# evals-setup-omp: everything a gateway-routed `evals-run-omp-*` target needs
# beyond evals-install -- `omp` installed with CI's command when missing, the
# gateway key resolved, and each arm's pinned model proven listed by Omp. Run
# `make evals-install && make evals-setup-omp` in a cloud session or on a fresh
# laptop. Idempotent, free, and writes no credential. The openai-codex arm
# needs Omp's own Codex login and is reported, not failed.
evals-setup-omp:
	scripts/evals-setup-omp.sh evals/experiments/omp-*.yaml

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
# Laptop-only, unlike check-git-sync: the cases need a live model, and this
# repository's CI is deliberately credential-free.
evals-plan: evals-variants
	cd evals && $(CODER_EVAL) plan -e experiments/with-without.yaml tasks/*/*.yaml
	cd evals && $(CODER_EVAL) plan -e experiments/omp-glm-5.3.yaml tasks/*/*.yaml
	cd evals && $(CODER_EVAL) plan -e experiments/omp-glm-5.3-flash.yaml tasks/*/*.yaml
	cd evals && $(CODER_EVAL) plan -e experiments/omp-deepseek-v4-pro.yaml tasks/*/*.yaml
	cd evals && $(CODER_EVAL) plan -e experiments/omp-gpt-5.6-sol.yaml tasks/*/*.yaml
	cd evals && $(CODER_EVAL) plan -e experiments/omp-gpt-6-sol.yaml tasks/*/*.yaml
	cd evals && $(CODER_EVAL) plan -e experiments/omp-gpt-6-luna.yaml tasks/*/*.yaml
	cd evals && $(CODER_EVAL) plan -e experiments/omp-gpt-6.1-sol.yaml tasks/*/*.yaml
	cd evals && $(CODER_EVAL) plan -e experiments/codex.yaml tasks/*/*.yaml
	cd evals && $(CODER_EVAL) plan -e experiments/classes-cheaper.yaml tasks/*/*.yaml
	cd evals && $(CODER_EVAL) plan -e experiments/classes-cocktail.yaml tasks/*/*.yaml
	cd evals && $(CODER_EVAL) plan -e experiments/classes-cocktail.gpts-choice.yaml tasks/*/*.yaml
	cd evals && $(CODER_EVAL) plan -e experiments/classes-glm.yaml tasks/*/*.yaml
	cd evals && $(CODER_EVAL) plan -e experiments/classes-gpt.yaml tasks/*/*.yaml
	cd evals && $(CODER_EVAL) plan -e experiments/classes-kimi.yaml tasks/*/*.yaml
	cd evals && $(CODER_EVAL) plan -e experiments/classes-minimax.yaml tasks/*/*.yaml
	cd evals && $(CODER_EVAL) plan -e experiments/classes-opus-low.yaml tasks/*/*.yaml
	cd evals && $(CODER_EVAL) plan -e experiments/classes-sonnet-high.yaml tasks/*/*.yaml
	cd evals && $(CODER_EVAL) plan -e experiments/classes-sonnet-low.yaml tasks/*/*.yaml

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

# JOBS: how many replicates a run target executes at once (`coder-eval run
# --max-parallel`). One by default. Runs are bound by model calls, not by the
# container, e.g.
#   make evals-run-omp-gpt-6-luna JOBS=12
JOBS ?= 1

# JUDGE= selects the judge of the semantic (`agent_judge`) criteria, apart from
# the subject; see scripts/evals-judge.py and "Choosing the judge" in
# evals/README.md. Unset, nothing changes: each task's pinned Claude Code
# `agent_judge` runs inside `coder_eval`, from a Claude Code session.
#
#   make evals-run-omp-gpt-5-6-sol JUDGE=omp-glm-5.3     # a non-Claude judge, no Claude session
#   make evals-run JUDGE=claude-code-sonnet-5            # the pinned route, named
#
# A non-Claude judge runs the subject over `tasks-judged/` (the same tasks with
# `agent_judge` disabled -- the preflight writes it), and `evals-record` then
# grades the preserved transcripts with that judge before it records the run.
# An unavailable judge fails in `evals-judge-preflight`, ahead of the subject.
JUDGE ?=
JUDGE_ROUTE := $(if $(JUDGE),$(shell uv run --frozen python3 scripts/evals-judge.py route $(JUDGE)))
RUN_TASKS = $(if $(filter omp,$(JUDGE_ROUTE)),$(patsubst tasks/%,tasks-judged/%,$(TASKS)),$(TASKS))

# evals-judge-preflight: with JUDGE= set, refuse a judge that cannot run here
# (no omp, a model omp does not list, a Claude judge outside a Claude Code
# session, a task pinning a different Claude judge) before any subject runs, and
# write the `tasks-judged/` tree for a non-Claude judge. A no-op without JUDGE=.
evals-judge-preflight:
	$(if $(JUDGE),uv run --frozen python3 scripts/evals-judge.py preflight --judge $(JUDGE),@true)

# evals-judge-calibrate: measure a judge against the committed labelled
# transcripts (evals/judges/calibration/labels.yaml) and write the observed
# outcome beside them. Needs the judge's route; costs a few cents on omp.
#   make evals-judge-calibrate JUDGE=omp-glm-5.3
evals-judge-calibrate:
	test -n "$(JUDGE)"
	uv run --frozen python3 scripts/evals-judge.py calibrate --judge $(JUDGE)

# evals-preflight: refuse every enabled `llm_judge` criterion. `llm_judge`
# calls Anthropic's metered API, which this project does not use even when a
# key or alternate transport is present. Claude judges use `agent_judge` from
# a Claude Code web or CLI session; see evals/README.md for the route.
# This is not a `check` leg: it needs task YAML in hand, while `make check`
# runs with none.
#
# Runs from `evals/`, same as the model call below, so `$(TASKS)`'s default
# glob and any override resolve identically in both places.
evals-preflight:
	cd evals && uv run --project $(CURDIR) --frozen python3 ../scripts/evals-preflight.py $(TASKS)

# evals-record: commit provenance for an existing run. Pass its experiment
# explicitly so a record cannot pair one run's scores with another model pin.
RUN ?= evals/runs/latest
evals-record:
	test -n "$(EXPERIMENT)"
	$(if $(filter omp,$(JUDGE_ROUTE)),uv run --frozen python3 scripts/evals-judge.py judge-run "$(RUN)" --judge $(JUDGE))
	uv run --frozen python3 scripts/evals-record.py "$(RUN)" \
		--experiment "$(EXPERIMENT)" --output evals/provenance \
		$(if $(filter 1,$(POST_COMMENTS)),--post-comments)

# evals-render-routes: rewrite the `Measured routes` table in model-classes.md
# from every committed record under evals/provenance/. Reads no run directory.
evals-render-routes:
	uv run --frozen python3 scripts/evals-render-routes.py

# evals-render-results: rewrite `evals/RESULTS.md`, one row per committed
# record under evals/provenance/. Reads no run directory.
evals-render-results:
	python3 scripts/evals-render-results.py

# Each arm excludes the other two arms' forks, plus any row tagged out of it
# with `skip:<arm>`. The tag is what routes a row to its arm, and
# `make check-eval-arms` is what keeps the three sets in step.
#
# ONE COMMA-SEPARATED VALUE, never a repeated flag. `--exclude-tags` is a single
# `str` option that `coder_eval` splits on commas, so a second `--exclude-tags`
# replaces the first rather than adding to it -- and the exclusions it dropped
# come back as rows run in the wrong arm, silently, at full price.
evals-run: evals-judge-preflight evals-plan evals-preflight
	cd evals && $(CODER_EVAL) run --max-parallel $(JOBS) -e experiments/with-without.yaml \
		--exclude-tags omp-only,codex-only,skip:claude,model-classes $(RUN_TASKS); status=$$?; \
	$(MAKE) -C .. evals-record RUN=evals/runs/latest EXPERIMENT=evals/experiments/with-without.yaml; \
	record_status=$$?; test $$status -ne 0 && exit $$status; exit $$record_status

# evals-run-omp: run every registered Omp experiment. Ablation targets compare
# bare and treated variants; the focused acceptance target measures with-plugin only.
evals-run-omp: evals-run-omp-glm-5-3 evals-run-omp-glm-5-3-flash evals-run-omp-deepseek-v4-pro evals-run-omp-gpt-5-6-sol evals-run-omp-gpt-6-sol evals-run-omp-gpt-6-luna evals-run-omp-gpt-6-1-sol

# evals-run-omp-*: the same suites on Oh My Pi, per configured model. Needs
# `omp` on PATH and the provider's credentials -- `make evals-setup-omp` sets up
# and checks both for the gateway arms. The agent borrows the caller's
# `~/.omp/agent/` rather than copies it -- see evals/coder-eval-omp/README.md.
# Costs real money, like its siblings, and narrows the same way with TASKS=.
#
# OMP_RUN_LIMITS overrides every row's turn cap and turn timeout on this arm.
# Omp's agent takes more turns than the Claude Code arm to reach the same
# reply, and the caps sized for that arm (5 to 10) cut it off before its
# reply. A 30-turn calibration of GPT 6 Luna on the judged
# `undertake` rows finished 97 of 100 replicates on their own: 11 turns at the
# median, 27 at the 95th percentile, 358 s at the slowest.
OMP_RUN_LIMITS := -D run_limits.max_turns=30 -D run_limits.turn_timeout=600 -D run_limits.task_timeout=1200
evals-run-omp-glm-5-3: evals-judge-preflight evals-plan evals-preflight
	cd evals && $(CODER_EVAL) run --max-parallel $(JOBS) $(OMP_RUN_LIMITS) -e experiments/omp-glm-5.3.yaml \
		--exclude-tags claude-only,codex-only,skip:omp,model-classes $(RUN_TASKS); status=$$?; \
	$(MAKE) -C .. evals-record RUN=evals/runs/latest EXPERIMENT=evals/experiments/omp-glm-5.3.yaml; \
	record_status=$$?; test $$status -ne 0 && exit $$status; exit $$record_status

evals-run-omp-glm-5-3-flash: evals-judge-preflight evals-plan evals-preflight
	cd evals && $(CODER_EVAL) run --max-parallel $(JOBS) $(OMP_RUN_LIMITS) -e experiments/omp-glm-5.3-flash.yaml \
		--exclude-tags claude-only,codex-only,skip:omp,model-classes $(RUN_TASKS); status=$$?; \
	$(MAKE) -C .. evals-record RUN=evals/runs/latest EXPERIMENT=evals/experiments/omp-glm-5.3-flash.yaml; \
	record_status=$$?; test $$status -ne 0 && exit $$status; exit $$record_status

evals-run-omp-deepseek-v4-pro: evals-judge-preflight evals-plan evals-preflight
	cd evals && $(CODER_EVAL) run --max-parallel $(JOBS) $(OMP_RUN_LIMITS) -e experiments/omp-deepseek-v4-pro.yaml \
		--exclude-tags claude-only,codex-only,skip:omp,model-classes $(RUN_TASKS); status=$$?; \
	$(MAKE) -C .. evals-record RUN=evals/runs/latest EXPERIMENT=evals/experiments/omp-deepseek-v4-pro.yaml; \
	record_status=$$?; test $$status -ne 0 && exit $$status; exit $$record_status

evals-run-omp-gpt-5-6-sol: evals-judge-preflight evals-plan evals-preflight
	cd evals && $(CODER_EVAL) run --max-parallel $(JOBS) $(OMP_RUN_LIMITS) -e experiments/omp-gpt-5.6-sol.yaml \
		--exclude-tags claude-only,codex-only,skip:omp,model-classes $(RUN_TASKS); status=$$?; \
	$(MAKE) -C .. evals-record RUN=evals/runs/latest EXPERIMENT=evals/experiments/omp-gpt-5.6-sol.yaml; \
	record_status=$$?; test $$status -ne 0 && exit $$status; exit $$record_status

evals-run-omp-gpt-6-sol: evals-judge-preflight evals-plan evals-preflight
	cd evals && $(CODER_EVAL) run --max-parallel $(JOBS) $(OMP_RUN_LIMITS) -e experiments/omp-gpt-6-sol.yaml \
		--exclude-tags claude-only,codex-only,skip:omp,model-classes $(RUN_TASKS); status=$$?; \
	$(MAKE) -C .. evals-record RUN=evals/runs/latest EXPERIMENT=evals/experiments/omp-gpt-6-sol.yaml; \
	record_status=$$?; test $$status -ne 0 && exit $$status; exit $$record_status

evals-run-omp-gpt-6-luna: evals-judge-preflight evals-plan evals-preflight
	cd evals && $(CODER_EVAL) run --max-parallel $(JOBS) $(OMP_RUN_LIMITS) -e experiments/omp-gpt-6-luna.yaml \
		--exclude-tags claude-only,codex-only,skip:omp,model-classes $(RUN_TASKS); status=$$?; \
	$(MAKE) -C .. evals-record RUN=evals/runs/latest EXPERIMENT=evals/experiments/omp-gpt-6-luna.yaml; \
	record_status=$$?; test $$status -ne 0 && exit $$status; exit $$record_status

evals-run-omp-gpt-6-1-sol: evals-judge-preflight evals-plan evals-preflight
	cd evals && $(CODER_EVAL) run --max-parallel $(JOBS) $(OMP_RUN_LIMITS) -e experiments/omp-gpt-6.1-sol.yaml \
		--exclude-tags claude-only,codex-only,skip:omp,model-classes $(RUN_TASKS); status=$$?; \
	$(MAKE) -C .. evals-record RUN=evals/runs/latest EXPERIMENT=evals/experiments/omp-gpt-6.1-sol.yaml; \
	record_status=$$?; test $$status -ne 0 && exit $$status; exit $$record_status

# evals-run-codex: the same suites on Codex. Needs the Codex SDK, which
# `evals-install` brings in with `coder-eval-codex`, and OpenAI credentials the
# SDK can authenticate with. Costs real money, like its siblings, and narrows
# the same way with TASKS=.
#
# `skip:codex` is not a spare exclusion: `tasks/constitution/*` carries it,
# because `coder_eval`'s Codex agent links skills and installs no hooks, so no
# constitution reaches that arm and every row there would score 0 for the wrong
# reason. See docs/notes/0015-the-codex-arm.md.
evals-run-codex: evals-judge-preflight evals-plan evals-preflight
	cd evals && $(CODER_EVAL) run --max-parallel $(JOBS) -e experiments/codex.yaml \
		--exclude-tags claude-only,omp-only,skip:codex,model-classes $(RUN_TASKS); status=$$?; \
	$(MAKE) -C .. evals-record RUN=evals/runs/latest EXPERIMENT=evals/experiments/codex.yaml; \
	record_status=$$?; test $$status -ne 0 && exit $$status; exit $$record_status

# evals-run-comparison: the same suites with the plugin at a base revision and at
# this checkout, both loaded. Use it when the question is whether a change to the
# constitution text changed behaviour once a constitution is already delivered;
# `evals-run`'s ablation cannot answer that, because its control carries no
# constitution. Needs a sibling checkout the experiment cannot create:
#
#   git worktree add ../daily-driver-base <base-revision>
#
# Costs real money, like its siblings, and narrows the same way with TASKS=.
# Both arms are Claude sessions, so it excludes what `evals-run` excludes.
# Record both revisions with the results -- see evals/README.md.
# The sibling is asserted here because this is the ONLY place that can: the
# plugin path is resolved in the agent at run time, so without the checkout the
# run pays for both arms and measures plugin-versus-nothing.
# Runs 16 tasks at once (`coder-eval run -j`); override with JOBS=. The 16 is
# this target's own default, so it applies unless JOBS= is given.

evals-run-comparison: evals-judge-preflight evals-plan evals-preflight
	@test -d ../daily-driver-base/skills || { \
		echo "error: ../daily-driver-base is missing or is not a plugin root;" >&2; \
		echo "  run: git worktree add ../daily-driver-base <base-revision>" >&2; \
		exit 1; }
	cd evals && $(CODER_EVAL) run -e experiments/base-vs-candidate.yaml -j $(if $(filter file,$(origin JOBS)),16,$(JOBS)) \
		--exclude-tags omp-only,codex-only,skip:claude,model-classes $(RUN_TASKS); status=$$?; \
	$(MAKE) -C .. evals-record RUN=evals/runs/latest EXPERIMENT=evals/experiments/base-vs-candidate.yaml; \
	record_status=$$?; test $$status -ne 0 && exit $$status; exit $$record_status

# evals-run-classes: the model-class capability suite, built from real merged
# pull requests (scripts/evals-cases-from-prs.py) and run on one Omp model at
# a time -- MODEL= names the eval experiment stem, e.g.
#   make evals-run-classes MODEL=glm
# Each evals/experiments/classes-*.yaml file pins its own model, independent
# of the personal omp_configs/ overlays. One Make target selects the matching
# filename instead of maintaining one target per model.
# `TASKS` is overridden here, not narrowed with the usual TASKS= override
# -- the default `tasks/*/*.yaml` would also hand every other arm's rows to
# this one, and `--exclude-tags` only screens out three of the four arms this
# repository actually runs (`claude-only`, `omp-only`, `codex-only`); the
# suite's own rows carry no arm tag of that shape to exclude BY, only
# `model-classes` itself, which every other arm already excludes. Still
# overridable by a caller who wants one case: `TASKS=tasks/model-classes/career-462.yaml`.
evals-run-classes: TASKS = tasks/model-classes/*.yaml
evals-run-classes: evals-judge-preflight evals-plan evals-preflight
	@if [ -z "$(MODEL)" ]; then \
		echo "evals-run-classes: set MODEL=<classes experiment stem>, e.g. MODEL=glm" >&2; \
		exit 1; \
	fi
	cd evals && $(CODER_EVAL) run --max-parallel $(JOBS) -e experiments/classes-$(MODEL).yaml \
		--exclude-tags claude-only,omp-only,codex-only,skip:model-classes $(RUN_TASKS); status=$$?; \
	$(MAKE) -C .. evals-record RUN=evals/runs/latest EXPERIMENT=evals/experiments/classes-$(MODEL).yaml; \
	record_status=$$?; test $$status -ne 0 && exit $$status; exit $$record_status

# mcp-usage: which GitHub MCP tools were actually called, rolled up to the
# toolsets that supply them. Laptop-only — it reads Claude
# Code's session transcripts, which CI does not have — and deliberately not
# part of `check`. See docs/github-mcp.md for what the answer is for.
mcp-usage:
	python3 scripts/github-mcp-usage.py

# model-telemetry: mine `undertake`'s claim/readiness comments and
# `review-cycle`'s `Review verification` comments for one repository's
# production rework, and re-render evals/provenance/production/README.md
# over every repository's records on disk. Needs GITHUB_TOKEN or GH_TOKEN,
# so like mcp-usage it is laptop-only and deliberately not part of `check`.
#   make model-telemetry REPO=owner/repo
#   make model-telemetry REPO=owner/repo REFRESH=1
model-telemetry:
	@if [ -z "$(REPO)" ]; then \
		echo "model-telemetry: set REPO=owner/repo, e.g. REPO=jmcvetta/daily-driver" >&2; \
		exit 1; \
	fi
	python3 scripts/model-telemetry.py $(REPO) $(if $(REFRESH),--refresh,) $(if $(SINCE),--since $(SINCE),)
