# The orchestrator lands the wave

**Status:** decided, 2026-09-21.
**Provenance:** requested and specified in
[#326](https://github.com/jmcvetta/daily-driver/issues/326).
**Resolves:** [#326](https://github.com/jmcvetta/daily-driver/issues/326).
**Amends:** [`0021`](0021-the-gate-is-a-read.md), by applying its read-before-
action rule to landing; and `embark`'s former rule that landing and closing an
epic always belonged to a person. It leaves [`0022`](0022-the-merge-is-mechanical.md)
unchanged: that note governs merging the base into a task branch, not landing
the task branch into the base.

A fleet used to stop with every task pull request green and ready. A person
then merged each pull request and closed the epic. The orchestrator already
held the facts that made both actions safe, so the handoff added manual work
without adding a decision.

## Decided

**`embark` lands each merge-ready task pull request by default.** The landing
gate is an ordered read. The pull request must not be a draft. Its merge state
must be clean. Every review thread must be resolved. It must carry no `human`
label and no human-action notice. The first failed read stops that pull request
and names the reason in one line.

When the reads hold, the orchestrator squash-merges in the same turn. The
repository is squash-only and uses the pull request title as the squash
subject. This keeps release-please's input unchanged. The orchestrator does
not enable auto-merge, because auto-merge could land a head that the
orchestrator did not read.

**Landing is not driving the pull request.** The task session still fixes a
check, answers a review, resolves a conflict, and keeps its branch current.
The orchestrator performs one read-only gate and one merge call. Landing one
sibling can move the base for another; each sibling's `undertake` cadence
handles that movement without serialising the fleet.

**The user can keep landing by hand.** The invocation is read once. An
explicit opt-out writes `Landing: by hand` into the muster roll. The default
writes `Landing: orchestrator`. Every resumed watcher reads that record rather
than choosing again. In by-hand mode, a merge-ready pull request is reported
once and left open.

**`embark` closes the epic when the fleet delivers its `Summary`.** After the
last task issue closes, each claim in the epic's `Summary` must be delivered
by at least one merged task pull request. When all claims are delivered, the
orchestrator comments with the landed pull requests and closes the epic as
completed. A missing claim is named and the epic stays open. By-hand mode also
leaves the epic open.

The backstop carries this split in its own prompt. Task sessions drive their
pull requests. The orchestrator lands merge-ready pull requests, marks waves
done, and closes a delivered epic.
