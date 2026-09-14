# Two harnesses, one skill tree

**Status:** decided, 2026-09-10.
**Provenance:** decided across
[#148](https://github.com/jmcvetta/daily-driver/issues/148) and its
children, as each part was built. This note records those decisions after the
fact, in one place, because the reasons were spread over an epic and would
otherwise be readable only from its pull requests.
**Resolves:** [#152](https://github.com/jmcvetta/daily-driver/issues/152).
**Amends:** [`0010`](0010-the-wake-slot-is-never-empty.md), whose never-empty
wake slot is a Claude Code rule rather than a rule of this toolkit.

Claude Code was the only harness this plugin ran on. Oh My Pi (`omp`) is the
second, and it reads Claude Code plugins natively. The question the epic
answered is how much of the tree is allowed to know which harness is reading
it.

## Decided

**One repository, one release, two harnesses.** The skills, the marketplace
catalog and the constitution source are shared. `.claude-plugin/marketplace.json`
is the only catalog: Omp reads the Claude-compatible catalog as its fallback,
so there is no `.omp-plugin/` copy to keep in step. `rules/constitution.md` is
the one constitution, and each harness reaches it its own way: Claude Code's
`hooks/inject-constitution.py` reads the file and injects it, while Omp's rule
provider reads `rules/*.md` and injects any file whose frontmatter carries
`alwaysApply: true`. The file therefore carries that frontmatter, and the hook
strips it. `scripts/check-constitution.py` asserts that both paths deliver the
same body.

Only the runtime adapter is per-harness, and it is thin. Claude Code gets
`hooks/`; Omp gets `extensions/daily-driver.js`, whose job is to block the
multiple-choice question widget and to supply the session-title and timer
tools Omp has no hook mechanism for.

**Harness routes belong in reference files, not in `SKILL.md`.** A `SKILL.md`
says what the skill decides and why. The tool routes that carry it out —
which call names a pull request, which call sets a title — go in
`skills/<name>/references/claude.md` and `skills/<name>/references/omp.md`, read
on demand by the session that needs them. This is the shape the skills are
being moved to, and a skill written after this note was recorded is written to
it from the start: `epic` shipped with one.

The `description` frontmatter is the exception. It is the trigger, so it is
read before any reference file can be, and it must be complete for both
harnesses.

*Rejected: both harnesses' routes inline in every `SKILL.md`.* Every session
would then read the other harness's branch, and pay for it, on every skill it
loads.

*Rejected: a generated per-harness skill tree.* It removes the reading cost and
buys two trees to keep in step, which is the cost this repository already
refuses for the marketplace catalog.

**Omp has no durable wake.** `daily_driver_schedule` is an in-process managed
timer. It is unref'd, and the runtime clears it on `session_shutdown`. It does
not survive the session, so it is not `send_later`, and nothing on Omp can wake
a session that has ended.

Two rules follow. `0010`'s never-empty wake slot is Claude Code only. On Omp,
`github.run_watch` blocks in-process instead, and `undertake`'s
`Keep it current` cadence — which outlives the turn that armed it — stops at
`Ready for review`. `0010` is not edited for this: the amendment is recorded
here, as `0010` recorded its own amendments to `0006` and `0007`.

**Omp's review surface leaves no threads.** The `reviewer` task agent returns
its findings to the session. The findings do not land on the pull request, so
the round carries them and nothing on GitHub records that the round happened.
`review-cycle`'s protocol of answering and resolving a thread per finding is
therefore Claude Code only; on Omp the round is answered in the session and in
the commits it produces.

**CI takes Omp from its binary installer** when it takes Omp at all, with
`curl -fsSL https://omp.sh/install | sh`. The binary carries its own runtime,
so CI needs nothing else. No workflow installs it today: the Omp half of
`make check` is `check-omp-extension`, which drives the adapter under Node
with a faked `ExtensionAPI` and needs no Omp at all.

*Rejected: `bun install -g`.* That route needs Bun present at runtime, which
adds a toolchain to every job that runs the Omp half of the checks.
