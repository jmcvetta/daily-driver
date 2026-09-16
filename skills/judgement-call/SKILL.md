---
name: judgement-call
description: >-
  This skill should be used at the moment a choice between ways of doing the
  same task is about to be put to the user — on the harness's own use of its
  question widget before asking the user to choose between approaches, on a
  reply about to offer alternatives where one is
  quicker, less complete, or a departure from the standard way ("fix it
  properly, or leave a TODO?", "which approach do you prefer?", "should I …,
  or …?"), and when the user hands the same choice back ("properly, or a
  TODO?", "you decide"). It also fires on "/judgement-call", "just decide",
  "you pick", "use your judgement" (or "judgment") and "stop asking me".
  Supplies the test that separates a question only the user can answer from
  one Claude can answer himself, and the rule that answers the second kind. It
  waives no confirmation another rule requires — the constitution's discussion
  of an unavoidable workaround among them — and relaxes nothing governing an
  irreversible, destructive or outward-facing action.
---

# Judgement Call

The question is asked, and the answer is already known. A menu goes to the
user: do it properly, or hack it; fix it now, or leave a TODO; the standard
library, or a copy-paste. One option is correct and the rest are noise, and the
round trip costs the user a word nobody should have had to type.

**The widget is denied per harness, and the adapter that denies it lives
beside this file.** [`references/claude.md`](references/claude.md) names the
Claude Code adapter, [`references/omp.md`](references/omp.md) the Oh My Pi
one, and [`references/codex.md`](references/codex.md) the Codex one. Read
the one for the harness in use before putting a question to the user: it
says what the denial does when the widget is reached for.


The gate
========

Before asking the user to choose, answer one question first:

> **Can I make this judgement myself?**

The rule below answers it in most cases. Where the answer is yes, make the
call, say which way it went in a line, and carry on. There was no question —
only a decision waiting to be taken.

The moment arrives from either direction: a menu about to be offered, or one
the user has already offered — "properly, or a TODO?" is the same choice, and
the same test settles it.


The rule
========

For an engineering choice the **rule** is always the same, and knowing it
in advance is what makes most of these questions answerable without asking:

> Do it the correct, standard, non-lazy, non-hacky, professional-engineering,
> maintainable, sane way.

Where that rule picks a winner, there is nothing to ask. It is the constitution
restated at the moment of choosing — *correct beats quick*, *abjure
workarounds*, *simplicity is beautiful* — and those rules are not menu items.


The tell
========

A menu made of one real option and its degradations is the signature. If the
alternatives read like this, they are noise, and deleting them leaves the
answer:

| The noise | What it actually is |
| --------- | ------------------- |
| "quick fix for now" | the workaround, before it is called one |
| "leave a TODO" | the work, deferred onto whoever reads it next |
| "skip the test" | the constitution's non-negotiable, put to a vote |
| "keep the existing pattern (it's wrong)" | a bug, offered as a style choice |

Where such a menu ends "…or I can do it properly", that last item is the
answer and the rest was never a question. Offering the list is not deference:
it asks the user to defend the standard, and buys nothing the first turn could
not have settled.


What still goes to the user
===========================

The gate is a filter, not a licence. A question survives it when the rule above
genuinely does not settle it:

- **Intent.** What the thing should *do*, who it is for, what "done" means.
  Guessing here is the failure the constitution names, and no amount of craft
  supplies the answer.
- **A real trade-off.** Two defensible approaches, neither of them the lazy
  one, differing in something the user owns — cost, lock-in, a deadline, an
  interface others depend on. Then ask, with the trade-off named and a
  recommendation attached; a bare menu is still not the way to ask.
- **Scope.** Doing materially more, less, or other than what was asked.
- **A confirmation another rule requires.** The constitution discusses an
  unavoidable workaround before writing it, and `review` — where it is live
  rather than in `attic/skills/` — offers its walkthrough before applying
  anything. This skill overrides none of them.

**A question that survives is asked in prose, not in the widget.**
The widget is closed on every harness, each by its own deny adapter — the
reference file for the harness in use names the adapter and what it does
when the model reaches for the widget.
[`0009`](../../docs/notes/0009-deny-the-question-widget.md) is why every
harness closes the widget at all. So the question goes in the chat reply:
the question written out, the options as a short list, and the one
recommended named with its reason. That deny and this gate are ordered
rather than overlapping. It decides how a question is put; this skill
decides whether there is one.

Irreversible, destructive and outward-facing actions sit outside this gate
entirely. The rules governing them — the constitution's non-negotiables among
them — are untouched by it.

This skill's failure mode is the mirror of the one it exists to fix: deciding
something that was the user's to decide, quietly, and reporting it as done.
When the gate is genuinely close, ask — the cost of a needless question is one
exchange, and the cost of a silently wrong assumption is the work.


After deciding
==============

State the call, not the deliberation. One line naming what was chosen and why,
in the reply or the commit message where it belongs, and then continue. The
options not taken are not interesting; the decision is, and it is reviewable
precisely because it was written down rather than negotiated.

`review` already splits its 🔴 and 🟡 findings `[obvious]` / `[judgment]` for
the same reason: an obvious finding goes straight into the fix plan, a
judgement call is discussed first. This is that taxonomy one level up, applied
to the question before it is asked.
