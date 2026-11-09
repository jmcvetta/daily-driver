# The report is a scheduled Routine

**Status:** decided, 2026-09-28.
**Provenance:** requested and specified in
[#425](https://github.com/jmcvetta/daily-driver/issues/425), under the epic
[#423](https://github.com/jmcvetta/daily-driver/issues/423).
**Resolves:** [#425](https://github.com/jmcvetta/daily-driver/issues/425).
**Amends:** [`0010`](0010-the-wake-slot-is-never-empty.md), by naming a
Routine that wakes a session without being that session's slot.

On Claude Code cloud sessions an `embark` orchestrator could reach an
implementor, but the implementor could not reach back. The `SendMessage`
contract says a cloud session "cannot message any session back yet". A
question an implementor stopped on reached the orchestrator only if the
orchestrator read it off GitHub.

## Measured

Measured on 2026-09-28, Claude Code 2.1.283, with this issue's own session as
the orchestrator and throwaway sessions as implementors. Every session was in
`auto` permission mode.

1. **The tools are there, with no prompt.** Two implementors each loaded a
   Routine tool through `ToolSearch` and called it without a permission
   prompt.
2. **A manual fire delivers nothing.** A poke-only Routine was bound to the
   orchestrator. The orchestrator fired it while mid-turn, and an implementor
   fired it while the orchestrator was idle. Both calls returned the Routine
   and an event id, with no error. Neither produced a turn, a notification, or
   a `last_run` on the Routine before it was deleted, ten and forty minutes
   later.
3. **A scheduled one-shot delivers.** An implementor created a Routine with
   `persistent_session_id` naming the orchestrator and `run_once_at` two
   minutes out. It fired a minute after its time, `last_run` read
   `SUCCEEDED`, and its text reached the orchestrator intact, as a queued
   notification. The orchestrator was idle, and the notification started a
   turn. The orchestrator's own `send_later` backstop arrived the same way.
4. **An archived target keeps the fire.** A Routine bound to an archived
   session also fired without error, and the session stayed archived. When it
   was unarchived its status read working at once. Whether the fire caused
   that was not measured.
5. **The brief matters.** The first implementor, handed the route in its
   prompt, stopped and asked its user whether the prompt was an injection. The
   two briefed through `append_system_prompt` reported without asking. Both
   of those briefs also called the route one the user set up. `embark`'s brief
   drops that claim, because no agent can state the user's consent for them.
   Whether the brief without it still avoids the question is not measured.

`send_later` was not tried from an implementor: its contract fires into the
calling session only, so it cannot reach the orchestrator.

`get_session` reports `external_metadata.cross_session_inbound: "available"`
on every session measured, archived ones included. Nothing observed tied it to
a route, so this note relies on nothing it says.

## Decided

**The implementor reports with a one-shot Routine it creates, bound to the
orchestrator.** The orchestrator hands it the orchestrator's session id at
dispatch, in `append_system_prompt`. `undertake`'s `Reporting to an
orchestrator` says when it reports and what the report says. The two
`references/claude.md` files name the calls.

**The candidate route is not used.** The issue proposed a poke-only Routine
that the orchestrator creates, passes by id, and deletes at the close. The
measurement in point 2 rules it out. With the chosen route the orchestrator
creates nothing, so neither `Close the epic` nor `stand-down` has a Routine to
delete, and each report's Routine disables itself after firing.

**A report is not the wake slot.** Its Routine belongs to the implementor's
turn, not to the orchestrator's; the orchestrator does not hold its id and
never fills or empties its slot with it. `0010`'s rule is unchanged for the
one timer each session does hold.

**A report is data.** It arrives labelled as a trigger "you or your owner
scheduled", because the Routine is on the same account. The orchestrator
identifies it by its opening line and never reads it as an instruction that
widens its task.

## Not decided

Whether a manual `fire_trigger` into a persistent session is a defect or a
contract. The route above does not depend on the answer, and a retest may
change it.
