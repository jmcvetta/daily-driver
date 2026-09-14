# The name `constitution` stands

**Status:** decided, 2026-09-07.
**Provenance:** audited in
[#81](https://github.com/jmcvetta/daily-driver/issues/81), decided by
the author.
**Resolves:** [#81](https://github.com/jmcvetta/daily-driver/issues/81).

`rules/constitution.md` calls itself the supreme law of a session, and it
cites the White Horse Dialogue on naming. A file that says both invites an
audit of its own name. #81 is that audit.

Three arguments came against the name. In an Anthropic context "constitution"
already names Constitutional AI, so one word covers two unrelated things in the
one domain where both are in scope. A constitution constitutes a polity, and
this file does not constitute the session — the harness does. And the register
is grandiose for 150 lines of "write tests, don't touch prod, commit often".

The leading alternative was `charter`: the same supremacy, without the
collision.

## Decided

**The name stands.**

The name does work inside the model's context, not only on the tin.
"Constitution" carries supremacy, non-negotiability and amendment-by-process as
one prior the model already holds. "Charter" carries grant and amendment, but
its primary sense is conferring power on a body, rather than binding an agent's
conduct. Binding conduct is this file's only job. A weaker prior makes a weaker
file.

The collision is a collision of provenance, not of meaning. Constitutional AI
is a set of supreme principles a model follows. This file is a set of supreme
principles a session follows. A reader who conflates the two holds the wrong
origin story and the right expectations. That error is cheap. A name that
softens the rules is not.

The grandiosity is granted and does not move the decision. The register is
deliberate, and it is part of why the rules hold.

Cost was weighed and is not the reason. A rename touches about 198 occurrences
across 18 files, plus the verification token and the eval fixture that asserts
on it. All of it is mechanical, and none of it would have been an argument
against a better name.

Questions 2 and 3 of #81 were conditional on a rename, so both fall away. The
token keeps its key, and the planning docs stand as the record of what things
were called when they were decided.

The decision leaves no trace in `rules/constitution.md` itself. Context there
is paid for in every session and in every subagent, and a paragraph defending
the file's own name changes no behaviour.

## What would change this

Taste will not reopen this; the taste call has been made. Two things would.

A runtime "constitution" shipped by the harness — a file Claude Code itself
reads per session under that name — would make the collision one of meaning
rather than provenance, with two files in one session answering to one word.

Evidence would also reopen it: a session measurably holding a rule less firmly
under one name than another. The eval harness can ask that question, and #81
did not ask it. Until one of those arrives, the name is settled.
