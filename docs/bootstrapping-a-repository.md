# Bootstrapping a repository

Installing this plugin is **per-machine — or, in the cloud, per-environment**.
[The README](../README.md#installing-it) has the steps; this page has the
mechanism under them, the measurements they rest on, and how to tell whether
the plugin actually loaded.

It gets a page at all because of the failure mode. There is no error, no
warning and no missing file — a session without the plugin behaves exactly
like a session ignoring its rules. And **nothing inside the plugin can report
its own absence**: a skill that would say so ships inside the plugin, so in
the one session that needs it, it is not there to run. Checking is an act
performed from outside.

## Where an install puts its state

`claude plugin install --scope project daily-driver@daily-driver` — the
explicitly project-scoped form — still splits across two places:

| Written into the repository | Written into `~/.claude` |
| --------------------------- | ------------------------ |
| `enabledPlugins` — a pointer | `extraKnownMarketplaces` — the registration |
| | `plugins/cache/daily-driver/daily-driver/<version>/` — the bytes |

Only the pointer travels with a `git clone`, and a pointer at a cache nothing
filled loads nothing. The bytes land at **user** scope even when project scope
is asked for, and — measured — a user-scope install then loads the plugin in a
repository carrying no settings of its own at all. That is what makes
bootstrapping a once-per-machine act rather than a once-per-repository one.

That last row is a **laptop** measurement and has not been repeated in the
cloud, where every row below was taken against this repository, which carries
the stanza in its own `.claude/settings.json`. So the cloud case for a
second, stanza-less repository in an already-bootstrapped environment is
confounded rather than proven: check it there rather than inheriting it.

## The per-repository stanza, and what it buys

A repository *can* declare that it wants the plugin, with an
`extraKnownMarketplaces` + `enabledPlugins` stanza in `.claude/settings.json`:

```json
{
  "extraKnownMarketplaces": {
    "daily-driver": {
      "source": {
        "source": "github",
        "repo": "jmcvetta/daily-driver"
      }
    }
  },
  "enabledPlugins": {
    "daily-driver@daily-driver": true
  }
}
```

It is neither necessary nor sufficient, and the trust gate is why. Measured
one key at a time, with the same stanza, untrusted and trusted:

| Project-scope key | Untrusted | Trusted |
| ----------------- | --------- | ------- |
| `enabledPlugins` | honoured — all six skills it then carried loaded | honoured |
| `extraKnownMarketplaces` | ignored: `installPluginsForHeadless` logs `no marketplaces declared` | `installed marketplace daily-driver` |

The gate sits on exactly the key that fetches things. The `enabledPlugins` row
was measured with the marketplace already registered and cached in user
config: a pointer is honoured untrusted, and fetching is not. Nor does
registering the marketplace suffice — in a *trusted* folder carrying exactly
the stanza above, on a machine with nothing cached, the marketplace was
registered and the plugin cached during that session and the session still
loaded nothing, its `init` payload reporting `plugins: []`. One `claude plugin
install` flipped it, at user scope, machine-wide.

So the stanza is worth having in a shared repository on laptops that have all
already installed the plugin, where it records the intent in version control.
In the cloud it is worth nothing at all: a container's
`hasTrustDialogAccepted` is permanently false — it clones and starts working,
no dialog is ever presented — so the fetching half is dead there by the table
above, and the pointer half points at a cache nothing filled.

`template/.claude/settings.json` holds exactly that stanza for a repository
with no `.claude/` yet. Copy it as `cp -R .../template/.claude/. .claude/` —
the trailing `/.` matters, since without it a repository that already has a
`.claude/` silently gets `.claude/.claude/settings.json` and the plugin then
loads nowhere. For a repository with settings worth keeping, `python3
scripts/stanza.py --write <repo>` merges instead of replacing, says what it
changed, and is a no-op when the stanza is already there; it runs from *this*
checkout precisely because it must not depend on the plugin being enabled in
the repository it is fixing. `python3 scripts/stanza.py` alone prints the
stanza, and `make check` fails when any copy of it — the template, this
repository's own settings, the block above — has drifted from the manifests.

Two names in it are easy to get wrong, and each fails the same silent way:

- **The marketplace is named after the repository, not after the plugin.** A
  marketplace is named by its manifest's `name`, and here that is
  `daily-driver`. Measured: `claude plugin marketplace add
  jmcvetta/daily-driver` records it under `daily-driver` in
  `~/.claude/plugins/known_marketplaces.json`. The plugin inside it is
  `daily-driver` too, because the repository and the plugin now carry one
  name — so the two halves agreeing here proves nothing, and each still has
  to be read from its own manifest.
- **The enablement key is `plugin@marketplace`**, so
  `daily-driver@daily-driver`. An entry whose marketplace is not registered
  is skipped as orphaned, and nothing says so.

## Codex has no stanza at all

Everything above is Claude Code's. On Codex there is no repository-level enable
of any kind — not a weak one, none. Measured against `codex-cli` 0.154.0:

| Question | Answer |
| -------- | ------ |
| Where `codex plugin marketplace add` and `codex plugin add` write their state | `$CODEX_HOME/config.toml`, in `[marketplaces.<name>]` and `[plugins."<plugin>@<marketplace>"]` |
| Is there a separate install manifest | no — that file is the whole record, and rewriting it uninstalls every plugin silently |
| Is a project `.codex/config.toml` read | no: `codex doctor` names the user file as the only config it loaded, and a `model` line in the project file had no effect |
| …and does a marketplace and plugin declared there load the skills | no |

So `template/.claude/settings.json` has no Codex counterpart to ship, and the
cheapest thing a shared repository can do on that harness is name the two
commands in its own README. A repository *can* carry a
`.agents/plugins/marketplace.json` to **offer** a plugin, but a non-default
marketplace path is not discovered implicitly and still needs `codex plugin
marketplace add`.

One failure mode is Codex's own, and it is the same silent shape this page
exists for: **hooks need persisted trust**. Untrusted, they are skipped with no
warning, no log line and no output, so the constitution and the question
widget's deny are simply absent. `codex exec --dangerously-bypass-hook-trust`
is the documented escape hatch for automation that has already vetted its
sources. [`notes/0016`](notes/0016-three-harnesses-one-skill-tree.md) is where
that and the rest of the third harness's decisions are recorded.

## Cloud environments: the Setup script

Nothing in the container fills the cache on its own. Granted a registered
marketplace, `installed_plugins.json` stays `{"version": 2, "plugins": {}}`
and every later run logs `Plugin "daily-driver" not cached ... run /plugin to
refresh` — `/plugin` being [unavailable in cloud sessions][cloud-docs].
Upstream: [anthropics/claude-code#88214][88214], and [#78119][78119],
[#83422][83422], [#88248][88248].

[cloud-docs]: https://code.claude.com/docs/en/claude-code-on-the-web
[88214]: https://github.com/anthropics/claude-code/issues/88214
[78119]: https://github.com/anthropics/claude-code/issues/78119
[83422]: https://github.com/anthropics/claude-code/issues/83422
[88248]: https://github.com/anthropics/claude-code/issues/88248

The environment's **Setup script** runs before Claude Code launches and is
therefore the only writer that beats the plugin scan. The README carries the
script; three things about it are worth stating once, here:

**The verification line is load-bearing.** Both install commands can return 0
while leaving the plugin uncached, so nothing else in the script can see that
failure. Tested isolated: a working install exits 0, a bad marketplace source
2, a registered-but-never-cached plugin 1.

**It does not verify the version.** The line greps for the plugin key and globs
the cache for *any* version, so a cachebust bump that fetched nothing new
satisfies it, exits 0, and snapshots itself looking exactly like a bump that
worked. Read the version off the cache directory instead.

**No `|| true`**, against the [docs' generic advice][script-requirements],
because the reasoning inverts here. Exiting zero on a failed install snapshots
the failure, and every later session skips the script and starts with no
plugin — silently, which is the failure this page exists to prevent. Exiting
non-zero fails the session, builds no snapshot, and the next attempt re-runs
the script, so a transient failure cures itself. A permanent one fails that
environment until someone clears the field from a browser, which is the right
trade.

[script-requirements]: https://code.claude.com/docs/en/cloud-environments#script-requirements

**The snapshot is why the script carries a cachebust.** `~/.claude` persists:
confirmed over two consecutive sessions in a fresh cloud environment, the
skills, the agents and the constitution hook present in both, the second
skipping the script entirely and booting from the filesystem snapshot.
(#88214's separate claim that the plugin tree rebuilds from empty each boot
did not reproduce.) The snapshot is keyed on the script's *text*, so the
install line runs once, pins whatever release was current that day, and never
runs again; a new release does not reach an existing environment, and a
session inside one cannot update itself out of it, being downstream of the
snapshot rather than the thing that builds it. Changing any byte of the script
invalidates the key. A `# CACHEBUST: n` comment is the cheapest byte to
change, and unlike the `FOO=1` this was first proved with it leaves behind no
dead variable for shellcheck to flag (SC2034).

## Checking whether it loaded

The habit worth having: **when a session feels unusually unconstrained, verify
before assuming it is being disobedient.** A session with no plugin is not
ignoring the rules, it does not have them.

Three checks, in increasing order of what they actually prove:

| Check | What it proves |
| ----- | -------------- |
| `grep -n enabledPlugins .claude/settings.json` | that the file says so — and the file is the half that fetches nothing. Cold-start-proof, works from anywhere. Only meaningful in a repository that carries the stanza at all: on the install path the README documents nothing writes that key, so a miss here proves nothing |
| `claude plugin details daily-driver@daily-driver` | that the names are right and the plugin is on this machine. **Not** that it loaded: measured printing the full component inventory for a session whose `init` reported no plugins at all. Says `not found` anywhere the marketplace was never cached |
| asking a session what it loaded | the question the other two are proxies for |

The third one, headless:

```sh
claude -p "say ok" --output-format stream-json --verbose | python3 -c \
  "import sys,json;[print(d.get('plugins')) for d in map(json.loads,sys.stdin) if d.get('subtype')=='init']"
```

An empty list is the failure, whatever the first two say; a loaded plugin
appears with its name, cache path and version. In a cloud session there is no
shell to run that from before the session exists, so the browser form is to
ask the session in words — what plugins are installed, and what skills they
provide — and then, for the constitution, which arrives by hook rather than as
a skill, to ask for the last line of `rules/constitution.md`.

Two readers are routinely mistaken for one of the three, and are not:

- **The harness `ListPlugins` tool answers a different question.** In two
  separate cloud environments it returned an empty list while the plugin was
  live — skills firing, constitution injected.
- **`claude plugin list` reads one route only.** It reports
  `installed_plugins.json`, so it is honest about a plugin the Setup script
  installed and says nothing about one arriving by stanza. Measured: in the
  trusted stanza-only repository, where the marketplace was registered and the
  plugin cached, it still said `No plugins installed`. Worth reading on a
  cloud container, where `installed_plugins.json` is the file the Setup
  script's verification line greps.

## The route that would be genuinely per-repository, and is blocked

A plugin tree carrying `.claude-plugin/plugin.json` loads as `<name>@skills-dir`
with no marketplace, no install and no network:

| Location | Scope | Trust required | Measured |
| -------- | ----- | -------------- | -------- |
| `~/.claude/skills/<name>/` | user | **no** | `Status: ✓ loaded`, all six skills then in the tree |
| `.claude/skills/<name>/` in the repo | project | **yes** | skipped: *"…was skipped because this workspace was not trusted when plugins were scanned"* |

The second row is the only arrangement in which a repository genuinely carries
its own plugin: fully in-repo, offline, surviving a fork, with no environment
configuration anywhere. Workspace trust is the single thing in the way — which
makes it the thing to re-test whenever Claude Code changes how cloud containers
handle trust.

## Repo-local review rules

A review rule that only one repository's toolchain makes correct goes in that
repository's own `CLAUDE.md` — which every surface reads, and which reaches a
reviewer subagent. There is no plugin-side mechanism to configure, and
[`notes/0003`](notes/0003-repo-local-review-rules.md) is why.

Two such rules used to ship globally. Paste them into the `CLAUDE.md` of a
repository that runs Yor, Checkov, or both:

```markdown
## Review

- **Yor tags are not stale.** Never flag `yor_*` or `git_*` tags in Terraform
  resources as outdated or needing update. Yor rewrites them during the
  release process; the hardcoded values are expected and correct.
- **Checkov suppressions carry a reason.** Every `checkov:skip` comment must
  state why the check is suppressed.
```

## Measurements

Established against Claude Code 2.1.263 by running the CLI, rather than by
reading the documentation: on the laptop with a scratch `HOME` and, for the
rows about what a session loads, headless `claude -p` against a scratch
`CLAUDE_CONFIG_DIR`. An interactive session may behave differently and a later
release may make the install a no-op, so re-run the third check above rather
than inheriting the conclusion. The cloud rows are real cloud sessions.

| Question | Answer |
| -------- | ------ |
| Marketplace name registered from `jmcvetta/daily-driver` | `daily-driver` |
| Where `--scope project` writes its state | `enabledPlugins` in the repository; marketplace and cache in `~/.claude` |
| Stanza in a **trusted** folder | marketplace registered, plugin cached |
| …and what that session loaded | nothing: `init` reports no plugins, no `daily-driver:pr` |
| …after `claude plugin install` once, same repository | plugin loaded, skill present, scope `user` |
| …and in a repository with no stanza after that install | still loaded — the install is per-machine |
| Stanza in an **untrusted** folder, nothing cached | ignored entirely, silently |
| Project `enabledPlugins`, **untrusted**, marketplace already cached | honoured: all six skills loaded |
| Project `extraKnownMarketplaces`, **untrusted** | ignored: `no marketplaces declared` |
| …the same, **trusted** | `installed marketplace daily-driver` |
| Stanza in a real Claude Code **cloud session** | not loaded; `hasTrustDialogAccepted: false`, nothing cached |
| Startup installer, marketplace registered, nothing cached | `installed_plugins.json` stays empty; `Plugin "daily-driver" not cached` |
| Setup script installing the plugin before launch | loaded, all components present |
| …and the next session in that environment, script skipped | still loaded — `~/.claude` survives in the snapshot |
| …and after a release, that same environment | still the old version: the script is skipped, so the install never re-runs |
| …and after editing the script's text | script re-runs, current release installed |
| Setup script verification line, isolated | 0 working, 2 bad marketplace source, 1 registered but never cached |
| Plugin tree at `~/.claude/skills/<name>/` | `Status: ✓ loaded` as `<name>@skills-dir`, no marketplace |
| The same tree at `.claude/skills/<name>/`, untrusted | skipped: workspace not trusted when plugins were scanned |
| `claude plugin list` in the stanza-only repository | `No plugins installed` |
| `claude plugin details daily-driver@daily-driver` in that repository | full component inventory, though nothing had loaded |
| The same command outside it | `not found` |
| Harness `ListPlugins` in a cloud session with the plugin live | empty list |

Rows dated 2026-09-06 and 2026-09-07. The full record, including the four
routes that do not work, is in
[jmcvetta/career#260](https://github.com/jmcvetta/career/issues/260).
