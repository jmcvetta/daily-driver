import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { mkdtempSync, writeFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { createTaskStateController } from "../extensions/task-state.mjs";
import { handleTaskEvent } from "../hooks/task-state.mjs";

function fixture() {
	const root = mkdtempSync(join(tmpdir(), "task-evidence-"));
	const git = (...args) => execFileSync("git", ["-C", root, ...args], { encoding: "utf8", stdio: ["ignore", "pipe", "pipe"] }).trim();
	git("init", "--initial-branch=master");
	git("config", "user.name", "Offline Fixture"); git("config", "user.email", "fixture@example.invalid");
	writeFileSync(join(root, "subject.txt"), "original\n"); git("add", "subject.txt"); git("commit", "-m", "Record fixture");
	return { root, git, remove: () => rmSync(root, { recursive: true, force: true }) };
}

async function driver(harness, root, overrides = {}) {
	let ledger;
	const entries = [];
	const ctx = { cwd: root, agent: { kind: "main" }, sessionManager: { getSessionId: () => "evidence-session", getBranch: () => entries }, ui: { notify() {} } };
	const controller = createTaskStateController({ appendEntry: (customType, data) => entries.push({ type: "custom", customType, data }), getActiveTools: () => ["daily_driver_task_state"] });
	const call = async (action, record) => {
		if (harness === "omp") return controller.execute("state", { action, record: record && JSON.stringify(record) }, null, null, ctx);
		const result = await handleTaskEvent({ harness, sessionId: "evidence-session", cwd: root, ledger, action, record }); ledger = result.ledger; return result.output;
	};
	const event = async (name, extra = {}) => {
		if (harness !== "omp") {
			const result = await handleTaskEvent({ harness, sessionId: "evidence-session", cwd: root, ledger, event: { hook_event_name: name, ...extra } }); ledger = result.ledger; return result.output;
		}
		if (name === "UserPromptSubmit") controller.input({ text: extra.prompt, source: "rpc", eventId: extra.turn_id }, ctx);
		if (name === "PreToolUse") controller.delegateCall({ toolCallId: extra.tool_use_id, toolName: extra.tool_name, input: extra.tool_input }, ctx);
		if (name === "PostToolUse") controller.toolResult({ toolCallId: extra.tool_use_id, toolName: extra.tool_name, input: extra.tool_input, content: [{ type: "text", text: JSON.stringify(extra.tool_response) }], result: extra.tool_response, isError: extra.isError }, ctx);
		if (name === "Interrupt") controller.cancel(ctx);
		if (name === "Stop") return controller.stop({}, ctx);
	};
	await event("UserPromptSubmit", { prompt: "Implement the offline fixture. Verify the result and obtain independent review.", turn_id: "request", origin: { kind: "composer" } });
	const initial = (await call("status")).details;
	const source = initial.sources[0];
	const ref = { sourceId: source.sourceId, quote: source.text };
	const verification = { kinds: ["check", "judgment"], toolName: "fixture-check", input: { root }, subject: { kind: "repository", root }, ...overrides };
	const grounded = await call("contract", { expectedRevision: initial.state.contract.revision, change: "Ground the required offline check and review", sourceRefs: [ref], contract: {
		criteria: initial.state.contract.criteria.map((item) => ({ ...item, verification })), requiredEvidenceKinds: verification.kinds.filter((kind) => ["command", "check"].includes(kind)), requiredReviewKinds: verification.kinds.filter((kind) => kind === "judgment"), approvalRequirements: [],
	} });
	assert.equal(grounded.isError, undefined, JSON.stringify(grounded));
	const observe = async (id, response, input = verification.input, pre = true) => {
		const data = { tool_use_id: id, tool_name: "fixture-check", tool_input: input, tool_response: response };
		if (pre) await event("PreToolUse", data);
		await event("PostToolUse", data);
		return (await call("status", { sourceId: `tool:${id}` })).details.source;
	};
	const evidence = async (id, source, overrides = {}) => {
		const state = (await call("status")).details.state;
		return call("evidence", { id, taskId: state.taskId, criterionId: "request", contractRevision: state.contract.revision,
			subject: source.execution?.subject, source: { sourceId: source.sourceId, quote: source.text }, kind: "check", result: "passed", ...overrides });
	};
	return { call, event, observe, evidence, verification, ref, entries };
}

/** registerTaskEvidenceChecks prevents transport success and stale artifacts from becoming verified completion. */
export default function registerTaskEvidenceChecks(check) {
	for (const harness of ["omp", "claude", "codex"]) {
		/** A successful transport, unrelated operation, missing start or old head must not establish required behavior. */
		check(`${harness} rejects missing unrelated failed truncated and wrong-task completion evidence`, async () => {
			const f = fixture();
			try {
				const d = await driver(harness, f.root);
				assert.equal((await d.call("complete", { summary: "done" })).isError, true);
				const headRefOid = f.git("rev-parse", "HEAD");
				const success = { headRefOid, statusCheckRollup: [{ conclusion: "SUCCESS" }] };
				const unrelated = await d.observe("unrelated", success, { command: "unrelated" });
				assert.equal((await d.evidence("unrelated", unrelated)).isError, true);
				const failed = await d.observe("failed", { headRefOid, exitCode: 0, statusCheckRollup: [{ conclusion: "FAILURE" }] });
				assert.equal((await d.evidence("hidden-failure", failed)).isError, true);
				assert.equal((await d.evidence("failure", failed, { result: "failed" })).isError, undefined);
				assert.equal((await d.call("receipt")).details.criteria[0].disposition, "failed");
				const truncated = await d.observe("truncated", { ...success, omitted: "x".repeat(10000) });
				assert.equal((await d.evidence("truncated", truncated)).isError, true);
				const noStart = await d.observe("no-start", success, d.verification.input, false);
				assert.equal((await d.evidence("no-start", noStart)).isError, true);
				const current = await d.observe("current", success);
				assert.equal((await d.evidence("wrong-task", current, { taskId: "another-task" })).isError, true);
				assert.equal((await d.evidence("wrong-revision", current, { contractRevision: 999 })).isError, true);
				assert.equal((await d.call("complete", { summary: "done" })).isError, true);
			} finally { f.remove(); }
		});

		/** Terminal check failures must remain failed in receipts, while pending and unknown outcomes stay unresolved. */
		check(`${harness} records startup and case-normalized failures without resolving incomplete checks`, async () => {
			const f = fixture();
			try {
				const d = await driver(harness, f.root, { kinds: ["check"] });
				const headRefOid = f.git("rev-parse", "HEAD");
				for (const conclusion of [null, "PENDING", "in_progress", "UNKNOWN"]) {
					const source = await d.observe(`incomplete-${conclusion}`, { headRefOid, statusCheckRollup: [{ conclusion }] });
					assert.equal((await d.evidence(`incomplete-${conclusion}`, source, { result: "failed" })).isError, true);
					assert.equal((await d.call("receipt")).details.criteria[0].disposition, "unresolved");
				}
				for (const failure of ["FAILURE", "FAILED", "ERROR", "CANCELLED", "TIMED_OUT", "ACTION_REQUIRED", "STARTUP_FAILURE"]) {
					for (const conclusion of [failure, failure.toLowerCase()]) {
						const source = await d.observe(conclusion, { headRefOid, statusCheckRollup: [{ conclusion }] });
						assert.equal((await d.evidence(`passed-${conclusion}`, source)).isError, true);
						assert.equal((await d.evidence(`failed-${conclusion}`, source, { result: "failed" })).isError, undefined);
						const receipt = (await d.call("receipt")).details;
						assert.equal(receipt.criteria[0].disposition, "failed");
						assert.equal(receipt.criteria[0].evidence.some((item) => item.id === `failed-${conclusion}` && item.result === "failed"), true);
					}
				}
				assert.equal((await d.call("complete", { summary: "Failed checks remain unfinished." })).isError, true);
			} finally { f.remove(); }
		});

		/** A valid check alone must not replace required review, and edits must invalidate a completed receipt. */
		check(`${harness} completes only current evidence and attributed judgments then invalidates changed artifacts`, async () => {
			const f = fixture();
			try {
				const d = await driver(harness, f.root);
				const source = await d.observe("success", { headRefOid: f.git("rev-parse", "HEAD"), statusCheckRollup: [{ conclusion: "SUCCESS" }] });
				assert.equal((await d.evidence("check", source)).isError, undefined);
				assert.equal((await d.call("complete", { summary: "done" })).isError, true);
				assert.equal((await d.evidence("no-attribution", source, { kind: "judgment" })).isError, true);
				const judgment = { reviewer: "independent fixture reviewer", rationale: "Inspected the fixture behavior.\nRetained the required records.", artifacts: [`${f.git("rev-parse", "HEAD")}:subject.txt`] };
				assert.equal((await d.evidence("invented-review", source, { kind: "judgment", judgment })).isError, true);
				const oldJudgment = { ...judgment, artifacts: ["old-head:subject.txt"] };
				const oldReview = await d.observe("old-review", { judgment: oldJudgment });
				assert.equal((await d.evidence("old-review", oldReview, { kind: "judgment", judgment: oldJudgment })).isError, true);
				const review = await d.observe("review", { judgment });
				assert.equal((await d.evidence("review", review, { kind: "judgment", judgment })).isError, undefined);
				const receipt = (await d.call("receipt")).details;
				assert.equal(receipt.verified, true); assert.equal(receipt.criteria[0].evidence.length, 2);
				assert.equal(JSON.stringify(receipt).includes('"quote"'), false);
				assert.equal((await d.call("complete", { summary: "Offline check and attributed review recorded." })).details.state.status, "verified-complete");
				writeFileSync(join(f.root, "subject.txt"), "changed\n");
				assert.equal((await d.call("receipt")).details.criteria[0].disposition, "stale");
				await d.event("Stop");
				assert.equal((await d.call("status")).details.state.status, "active");
			} finally { f.remove(); }
		});

		/** A result arriving after commit or contract change must retain its original execution identity. */
		check(`${harness} rejects late old-head evidence and preserves cancellation bounds without complete`, async () => {
			const f = fixture();
			try {
				const d = await driver(harness, f.root);
				const original = f.git("rev-parse", "HEAD");
				await d.event("PreToolUse", { tool_use_id: "late", tool_name: "fixture-check", tool_input: d.verification.input });
				writeFileSync(join(f.root, "subject.txt"), "changed\n"); f.git("add", "subject.txt"); f.git("commit", "-m", "Change fixture");
				const late = await d.observe("late", { headRefOid: original, statusCheckRollup: [{ conclusion: "SUCCESS" }] }, d.verification.input, false);
				assert.equal(late.execution.subject.commit, original);
				assert.equal((await d.evidence("late", late)).isError, true);
				await d.event("Stop"); await d.event("Stop"); await d.event("Stop");
				const bounded = (await d.call("status")).details.state;
				assert.equal(bounded.corrections, 2); assert.ok(bounded.stopFailure);
				await d.event("Interrupt"); await d.event("Stop");
				assert.equal((await d.call("status")).details.state.status, "cancelled");
				assert.equal((await d.call("complete", { summary: "done" })).isError, true);
			} finally { f.remove(); }
		});

		/** Contract changes must invalidate existing results even when the repository head does not move. */
		check(`${harness} retains prior evidence but rejects a changed contract revision`, async () => {
			const f = fixture();
			try {
				const d = await driver(harness, f.root);
				const source = await d.observe("current", { headRefOid: f.git("rev-parse", "HEAD"), statusCheckRollup: [{ conclusion: "SUCCESS" }] });
				assert.equal((await d.evidence("original-check", source)).isError, undefined);
				const before = (await d.call("status")).details.state;
				assert.equal((await d.call("contract", { expectedRevision: before.contract.revision, change: "Ground the existing offline constraint", sourceRefs: [d.ref], contract: { constraints: ["Offline fixture only"] } })).isError, undefined);
				const receipt = (await d.call("receipt")).details;
				assert.equal(receipt.criteria[0].disposition, "stale");
				assert.equal(receipt.criteria[0].evidence[0].id, "original-check");
				assert.equal((await d.evidence("relabeled-old-check", source)).isError, true);
				assert.equal((await d.call("complete", { summary: "done" })).isError, true);
			} finally { f.remove(); }
		});

		/** Relative file identities must bind to execution cwd, not the controller process's working directory. */
		check(`${harness} uses file content identity and native exit outcomes without inheriting changed content`, async () => {
			const f = fixture();
			try {
				const d = await driver(harness, f.root, { kinds: ["command"], subject: { kind: "artifact", path: "subject.txt" } });
				const source = await d.observe("file-command", { exit_code: 0, output: "Offline assertion passed." });
				assert.equal((await d.evidence("file-command", source, { kind: "command" })).isError, undefined);
				assert.equal((await d.call("complete", { summary: "File assertion passed." })).details.state.status, "verified-complete");
				writeFileSync(join(f.root, "subject.txt"), "changed\n");
				assert.equal((await d.call("receipt")).details.criteria[0].disposition, "stale");
			} finally { f.remove(); }
		});

		/** An agent waiver or unrelated approval must not satisfy a contract-required signoff. */
		check(`${harness} requires sourced approval for the named requirement`, async () => {
			const f = fixture();
			try {
				const d = await driver(harness, f.root, { kinds: ["check", "approval"] });
				await d.event("UserPromptSubmit", { prompt: "Require maintainer signoff for this fixture.", turn_id: "approval-requirement", origin: { kind: "composer" } });
				const status = (await d.call("status")).details;
				const decision = status.sources.at(-1);
				const ref = { sourceId: decision.sourceId, quote: decision.text };
				assert.equal((await d.call("contract", { expectedRevision: status.state.contract.revision, change: "Retain the requested signoff", sourceRefs: [ref], authoritySource: ref, contract: { approvalRequirements: ["maintainer signoff"] } })).isError, undefined);
				const head = f.git("rev-parse", "HEAD");
				const source = await d.observe("check", { headRefOid: head, statusCheckRollup: [{ conclusion: "SUCCESS" }] });
				assert.equal((await d.evidence("check", source)).isError, undefined);
				assert.equal((await d.call("complete", { summary: "done", notApplicable: ["maintainer signoff"] })).isError, true);
				const judgment = { reviewer: "fixture maintainer", rationale: "Approved the recorded fixture.", artifacts: [`${head}:subject.txt`] };
				const approval = await d.observe("approval", { judgment });
				assert.equal((await d.evidence("wrong-approval", approval, { kind: "approval", judgment, requirement: "another requirement" })).isError, undefined);
				assert.deepEqual((await d.call("receipt")).details.outstandingApprovals, ["maintainer signoff"]);
				assert.equal((await d.evidence("approval", approval, { kind: "approval", judgment, requirement: "maintainer signoff" })).isError, undefined);
				assert.equal((await d.call("complete", { summary: "Check and attributed signoff recorded." })).details.state.status, "verified-complete");
			} finally { f.remove(); }
		});

		/** A later success must not silently erase a contradictory failure on the same artifact. */
		check(`${harness} retains contradictory failures until explicit observed supersession`, async () => {
			const f = fixture();
			try {
				const d = await driver(harness, f.root, { kinds: ["check"] });
				const headRefOid = f.git("rev-parse", "HEAD");
				const failed = await d.observe("failure", { headRefOid, statusCheckRollup: [{ conclusion: "FAILURE" }] });
				assert.equal((await d.evidence("failure", failed, { result: "failed" })).isError, undefined);
				const passed = await d.observe("rerun", { headRefOid, statusCheckRollup: [{ conclusion: "SUCCESS" }] });
				assert.equal((await d.evidence("rerun", passed)).isError, undefined);
				assert.equal((await d.call("receipt")).details.criteria[0].disposition, "failed");
				assert.equal((await d.call("complete", { summary: "done" })).isError, true);
				assert.equal((await d.evidence("confirmed-rerun", passed, { supersedes: "failure" })).isError, undefined);
				assert.equal((await d.call("complete", { summary: "Recorded rerun supersedes the failure." })).details.state.status, "verified-complete");
				assert.equal((await d.call("status")).details.state.criterionEvidence.length, 3);
			} finally { f.remove(); }
		});
	}

	/** A bounded preview must not force replay when the exact native tool result is already retained. */
	check("Omp recovers exact native evidence without treating its truncated preview as a pass", async () => {
		const f = fixture();
		try {
			const d = await driver("omp", f.root, { kinds: ["check"] });
			const payload = { headRefOid: f.git("rev-parse", "HEAD"), statusCheckRollup: [{ conclusion: "SUCCESS" }], padding: "x".repeat(10000) };
			const truncated = await d.observe("retained-result", payload);
			assert.equal(truncated.textTruncated, true);
			assert.equal((await d.evidence("preview", truncated)).isError, true);
			d.entries.push({ type: "message", message: { role: "toolResult", toolCallId: "retained-result", content: [{ type: "text", text: JSON.stringify(payload) }] } });
			const recovered = (await d.call("status", { sourceId: "tool:retained-result" })).details.source;
			assert.equal(recovered.textTruncated, false);
			assert.equal(recovered.recoveredFromNativeEntry, true);
			assert.equal((await d.evidence("exact-result", recovered)).isError, undefined);
			assert.equal((await d.call("complete", { summary: "Exact retained check result recorded." })).details.state.status, "verified-complete");
			assert.equal(d.entries.find((entry) => entry.customType === "daily-driver.task-observation").data.observation.textTruncated, true);
		} finally { f.remove(); }
	});
}
