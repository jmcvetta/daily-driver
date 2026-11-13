# Runtime integration measurements

Historical record of the progressive-disclosure delivery measurements behind
[harness-integration.md](harness-integration.md). The checkpoints below are
dated; each earlier one is superseded by the later one, and the numbers are
preserved as recorded rather than updated. The compact-core captures are the
latest applicable delivery evidence; the current guide states the standing
limits and links here instead of inlining every experiment.

### Initial measurement (superseded)

Offline installed-runtime captures used Omp 18.15.0, Claude Code 2.1.267, and
Codex 0.160.0. Providers listened on loopback only and used disposable homes
with no external credentials. Scripted replies exercised actual native tools
and request construction; they do not establish model compliance or behavioral
parity.

The recorded base is `42b5bddb42cffffeab14678b446eed52a3c6bb23`.
UTF-8 byte counts, not tokenizer counts, are used:

| Complete source/delivery unit | Base | Candidate |
| --- | ---: | ---: |
| Constitution file, including frontmatter | 13,913 | 8,429 |
| Omp body, excluding frontmatter | 13,883 | 8,399 |
| Rendered hook core, including standing-authority header | 14,197 | 8,713 |

Actual delivery differs from the complete-source comparison:

- Omp main and native child requests each contained one complete core in both
  arms. Candidate native task completion, task transition, manual RPC compaction,
  and a new resumed process were observed. The resumed request retained the
  complete core and executed the CI-policy read.
- Claude baseline startup supplied a roughly 2 KB preview of a persisted hook
  output, not the full core. Its startup hook wrapper occupied 2,532 UTF-8 bytes
  in the recorded request; candidate complete delivery occupied 8,770 bytes.
  Baseline child requests carried a full prompt-prepended core plus another
  startup preview. Candidate child requests carried one complete core and the
  original delegated prompt without a rewrite. Startup delivery grows when the
  missing safety instructions are restored; source reduction does not satisfy
  a literal decrease in actual startup bytes.
- Codex baseline main and child requests each carried one truncated hook block
  of 10,107 bytes. Candidate main and child requests each carried the complete
  8,713-byte core once. Its default `additionalContext` threshold is 2,500
  approximate tokens; the manifest explicitly uses a finite 5,000-token budget.

The delivery suite bounds the rendered core to 9,000 UTF-8 bytes. Do not raise
that budget or lengthen the core without a new installed-runtime proof of
complete delivery. Reintroducing a preview is not a context saving. Restore or
relocate any control needed by a failing comparison; do not weaken the rubric.

### Reconciled measurement — 2026-11-07 (superseded)

The current baseline is `f053d4ce63b97ee51abec43da0a86d1df4f8bc6a`.
The reconciled candidate retains the baseline's headless execution, protected
handoff, CI-scope, and bounded-experiment requirements. Measurements use UTF-8
bytes, not estimated tokens. The earlier measurements above remain historical.
That reconciled candidate core has SHA-256
`39075eb1cd25647ebc32b84f94ceb10e46251f16a37f263199991ea25ccb1076`.

| Delivered unit | Current base | Reconciled candidate |
| --- | ---: | ---: |
| Constitution file | 18,502 | 8,761 |
| Omp core body, main and child | 18,474 | 8,733 |
| Claude raw startup hook wrapper | 2,564, preview only | 8,955, complete |
| Codex startup/child hook block | 10,107, truncated | 8,880, complete |

Loopback providers and disposable credential-free homes exercised Omp 18.18.0,
Claude Code 2.1.267, and Codex CLI 0.160.0. Candidate captures contain one
complete core on main and native child subject requests, task switching, and
Omp/Claude resume after compaction. Codex resume retains two complete hook
blocks (17,760 bytes); after native compaction both remain. Baseline Codex also
accumulates two truncated blocks. This is actual repeated delivery, not a
single-copy measurement. Summarizer and skill-preparation requests are not
subject-core delivery. Scripted providers prove delivery and workflow access,
not autonomous compliance; their fabricated usage counters are not inference
cost evidence.
Task-private `disclosure_omp_probe.py`, `disclosure_claude_probe.py`, and
`disclosure_probe.py` produced the captures under ignored `evals/runs/`.
The candidate runs used 35, 11, and 12 local provider requests respectively.
Their main, child, switch, compact, and resume phases completed. These are
request-construction experiments, not inference-cost or model-behavior results.

The opt-in `codex-daily-driver` adapter was also exercised through its actual SDK
and bundled Codex 0.154.0, with reviewed native hook trust. Its five parent/child
requests each contained one complete 8,880-byte core. Read-only and
workspace-write confinement, blocked network access, and disabled shell/child
tools were observed. Injected HTTP errors and broken streams each produced a
crashed partial record rather than a false success. Native zero-retry provider
settings made one request per injected failure, but the unchanged runner made
four HTTP-error attempts and three broken-stream attempts. Its maximum is six
communication attempts for rate-limit errors, not an API-request cap.
The final task-private proof is
`evals/runs/disclosure-codex-adapter-final-core-isolated/proof-evidence.json`;
earlier overlapping-home captures are preserved but excluded.

At that checkpoint, the hook payload had 120 bytes below the 9,000-byte ceiling.
Claude's raw startup grew when the missing safety core was restored. The literal
startup-decrease criterion was not met. Those captures remain historical; the
later relocation below addresses the original criterion without an amendment.


### Compact delivery — 2026-11-07

The final relocated core has SHA-256
`ba084cdc07418d019805603a536431e1a0d5f4f286480802248ea7dd7d6c169b`.
The baseline remains `f053d4ce63b97ee51abec43da0a86d1df4f8bc6a`.
Counts are UTF-8 bytes from actual request strings, not token estimates:

| Delivered unit | Base | Compact candidate |
| --- | ---: | ---: |
| Constitution source | 18,502 | 2,473 |
| Omp main/child core body | 18,474 | 2,445 |
| Claude PATH CLI 2.1.267 startup wrapper | 2,568, preview | 2,557, complete |
| Claude SDK CLI 2.1.273 startup wrapper | 2,570, preview | 2,557, complete |
| Codex CLI 0.160.0 / SDK 0.154.0 startup/child block | 10,107, truncated | 2,482, complete |
| Codex CLI 0.160.0 resumed/compacted blocks | 20,214, truncated | 4,964, complete |

The Claude startup reduction is small, but the candidate delivers the full core.
The earlier baseline wrapper was 2,564 bytes; the candidate is also smaller
than that capture. Persisted-output paths affect preview overhead. Both controlled
Claude sandboxes are empty Git repositories; native system text is identical in
length. Do not count an inherited repository's conflict status as an instruction
saving.

New credential-free loopback captures are `disclosure-{omp,claude,codex}-release-proof`
under ignored `evals/runs/`. They exercised startup, native children, task
switching, compaction and resume on Omp 18.18.0, Claude Code 2.1.267 and Codex
CLI 0.160.0. They used 35, 11 and 12 local requests. Subject requests retain
one complete core, except Codex resume's two observed blocks. Omp preparation
and summarizer requests, and Claude/Codex summarizer/title requests, are not
subject delivery. These captures prove access, not autonomous policy compliance.

The actual Claude subject SDK selects its bundled 2.1.273 binary, not PATH's
2.1.267. A separate loopback lifecycle capture used that binary with the SDK's
empty system-prompt and project-setting options: 11 candidate requests and ten
baseline requests. Candidate subject requests, including native children and
post-compaction resume, retained one complete core. The captures are
`disclosure-claude-sdk-proof-{base,cand}` under ignored `evals/runs/`.

The actual Codex SDK/bundled 0.154.0 baseline was also measured with reviewed
frozen hooks: five parent/child requests each contained one 10,107-byte truncated
block, not its complete 18,786-byte rendered core. Its proof is
`disclosure-release-20261107/codex-preparation/base-sdk-parent-child-delivery/`.

Retrieval is not free. Current full source sizes are 8,493 bytes for `provenance`,
8,033 for `pr`, and 82,361 for `undertake`. Read only the relevant policy when
the issue sequence is not needed; retain retrieved context instead of repeating
reads. Report actual returned context, truncation and repeated reads in behavioral
records. Lower always-loaded bytes do not establish lower total cost or better
reliability. Scripted usage counters are not inference-cost evidence.

The [valid Omp comparison retrieval record](progressive-disclosure-retrieval.json)
contains all 36 slots, their input hashes, returned bytes, tool duration and task
wall time. It counts successful skill results, including repeated reads and
returned wrappers, not complete source files or hidden preparation:

| Across nine cases and two replicates per arm | Base | Candidate |
| --- | ---: | ---: |
| Successful skill reads | 20 | 45 |
| Returned UTF-8 bytes | 416,941 | 631,617 |

Some `undertake` results were truncated. The increased explicit retrieval is
not hidden by the smaller standing core; these counts establish no total-cost
or latency improvement. Per-slot token usage and separate judge usage remain
in the linked behavioral records.

The actual SDK/bundled Codex 0.154.0 adapter also delivered the 2,482-byte core
once in each of five parent/child loopback requests. Two containment requests
confirmed read access and denied writes and shell network access. All 16 invalid
reviewed-payload cases failed as non-retryable configuration errors before any
provider request. Unrelated host hooks and MCP processes stayed absent, without
requiring a native-home `hooks.json` or changing shared configuration.
The frozen `bd089b6` proof is under
`disclosure-release-20261107/codex-preparation/compact-core-adapter-proof-bd089b6/`
in ignored `evals/runs/`. It does not prove Git-write capability or model behavior.

The later Omp discovery repair was exercised through the actual `omp/18.18.0`
RPC executable: nine native traversal cases and 68 guarded cases passed
(27 admitted, 41 refused), including a real virtual environment. This supersedes
module-only traversal evidence from a separately installed 18.13.3 package.
The proof is `omp-executable-discovery-proof-cerftbik/evidence.json` under ignored
`evals/runs/`. Link names are directory metadata, not permission to read targets.

A later Codex adapter proof exercised the official runner's `DIRECT_WRITE`
layout with the opt-in owned fixture envelope. Native Worktrunk created an
initially absent sibling, staged a named file, committed it, and ran the
canonical verifier. The scripted run passed its two deterministic criteria.
The native home configuration stayed byte-identical and no hook file appeared.
The exact-cwd project trust is derived per thread; this prevents native
workspace-write startup from persisting project trust to the shared account
configuration. Inherited permission-profile additions fail before inference.
The owned-envelope and trust proof used adapter SHA-256
`20e3a3c5c165785486db8660d6c5c05366c0d4ab0db4cd70fdc8eef11852e99c`.
Proofs are under
`disclosure-release-20261107/codex-preparation/task-trust-repair-report.json`
and `official-runner-task-trust-fixed/` in ignored `evals/runs/`.
These credential-free scripted proofs establish integration behavior, not
model compliance or inference cost.

The subsequent native comparison exposed genuine visible-tool caps despite
upstream deterministic `SUCCESS` statuses. The adapter now marks capped partial
output with an `ERROR` result anchor; it does not erase the cap or change the
criteria. A replay through the changed wrapper checked preserved capped and
completed records without starting a native runtime. The adapter SHA-256 is
`78d93eff434f44bb3928c0139f6b031688603a90df1f59b0ea0166c0eae53ab5`.
The [native attempt inventory](progressive-disclosure-native-attempts.json)
keeps the original statuses and per-slot context/latency limits.

The Omp adapter now supplies `--session-dir` inside its private home by
default, while honoring explicit separated and inline options. This avoids
native startup failure when the encoded task path exceeds one directory
component. The actual Omp 18.18.3 executable returned ready and state frames
for all three forms at a long cwd, without a model turn or provider request.
The proof is `disclosure-omp-private-session-proof-20261109/report.json` under
ignored `evals/runs/`; its Omp adapter SHA-256 is
`fe414c50222423c3bbb9fcacf68e9b6f12741fa4da35369448817ac3d6205334`.

