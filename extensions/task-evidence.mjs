import { createHash } from "node:crypto";
import { execFileSync } from "node:child_process";
import { readFileSync, realpathSync } from "node:fs";
import { resolve } from "node:path";

const hash = (value) => createHash("sha256").update(value).digest("hex");
const equal = (left, right) => JSON.stringify(left) === JSON.stringify(right);
const nonblank = (value) => typeof value === "string" && Boolean(value.trim());
const KINDS = ["command", "check", "judgment", "approval", "report"];

/** captureSubject records repository or file identity before execution, without changing the artifact. */
export function captureSubject(cwd, artifact) {
	try {
		if (artifact?.kind === "artifact") {
			const path = realpathSync(resolve(cwd, artifact.path));
			return { kind: "artifact", path, digest: hash(readFileSync(path)) };
		}
		const git = (...args) => execFileSync("git", ["-C", artifact?.root ?? cwd, ...args], { encoding: "utf8", stdio: ["ignore", "pipe", "ignore"] }).trim();
		const root = git("rev-parse", "--show-toplevel");
		return { kind: "repository", root, commit: git("rev-parse", "HEAD"), dirty: Boolean(git("status", "--porcelain", "--untracked-files=all")) };
	} catch { return null; }
}

/** observedOutcome reads decisive structured outcomes, never transport success or a prose success claim. */
export function observedOutcome(event) {
	const candidates = [event.details, event.result];
	for (const part of event.content ?? []) {
		if (part?.type === "text") {
			try { candidates.push(JSON.parse(part.text)); } catch { /* Unstructured output has no attested outcome. */ }
		}
	}
	if (event.isError) return { result: "failed", basis: "tool-error" };
	for (const value of candidates) {
		if (!value || typeof value !== "object") continue;
		if (value.isError === true) return { result: "failed", basis: "result-error" };
		const checks = Array.isArray(value) ? value : value.statusCheckRollup;
		if (Array.isArray(checks) && checks.length) {
			const results = checks.map((check) => {
				const result = check.conclusion ?? check.state ?? check.status;
				return typeof result === "string" ? result.toUpperCase() : result;
			});
			if (results.some((result) => ["FAILURE", "FAILED", "ERROR", "CANCELLED", "TIMED_OUT", "ACTION_REQUIRED", "STARTUP_FAILURE"].includes(result))) return { result: "failed", basis: "check-conclusions" };
			if (results.every((result) => result === "SUCCESS")) return { result: "passed", basis: "check-conclusions" };
			return { result: "unresolved", basis: "incomplete-checks" };
		}
	}
	for (const value of [event.details, event.result]) {
		if (value?.isError === true) return { result: "failed", basis: "result-error" };
		const code = value?.exitCode ?? value?.exit_code;
		if (Number.isInteger(code)) return { result: code === 0 ? "passed" : "failed", basis: "exit-status", exitCode: code };
	}
	return { result: "unresolved", basis: "outcome-unavailable" };
}

/** recordEvidence binds a criterion claim to a retained execution observation and its captured identity. */
export function recordEvidence(state, record, source, sessionId) {
	const criterion = state.contract.criteria?.find((item) => item.id === record.criterionId);
	if (!criterion || record.taskId !== state.taskId || record.contractRevision !== state.contract.revision) throw new Error("Evidence must name the current task, criterion and contract revision");
	if (!nonblank(record.id) || (state.criterionEvidence ?? []).some((item) => item.id === record.id)) throw new Error("Evidence ids are immutable and unique");
	if (!KINDS.includes(record.kind) || !["passed", "failed", "unresolved"].includes(record.result)) throw new Error("Name an evidence kind and an explicit result");
	const execution = source.execution;
	if (source.kind !== "tool" || !execution || execution.sessionId !== sessionId || execution.taskId !== state.taskId || execution.contractRevision !== state.contract.revision || execution.contractId !== state.contract.contractId) throw new Error("Evidence lacks this task/session's execution-time binding");
	if (!execution.subject || !equal(record.subject, execution.subject)) throw new Error("Evidence must use the subject captured at execution time");
	if (!criterion.verification?.subject || !equal(execution.subject, captureSubject(execution.cwd, criterion.verification.subject))) throw new Error("Evidence subject is not the criterion's declared current artifact");
	if (source.textTruncated) throw new Error("Truncated evidence cannot establish a decisive result; retrieve an exact retained source");
	if (!criterion.verification?.kinds?.includes(record.kind)) throw new Error("Evidence kind does not match the criterion's declared verification");
	if (record.kind === "command" || record.kind === "check") {
		if (!criterion.verification.toolName || criterion.verification.toolName !== source.toolName || hash(JSON.stringify(criterion.verification.input)) !== execution.inputFingerprint) throw new Error("Observed operation does not match the criterion's declared verification operation");
		if (record.result !== source.outcome?.result || !["exit-status", "check-conclusions", "tool-error", "result-error"].includes(source.outcome?.basis)) throw new Error("The actual command/check outcome does not support this result");
		if (record.kind === "check" && source.outcome.basis !== "check-conclusions") throw new Error("Check evidence requires actual check conclusions");
		if (record.kind === "command" && source.outcome.basis === "check-conclusions") throw new Error("Command evidence requires an actual exit status, not check transport success");
		if (record.kind === "check") {
			const value = JSON.parse(source.text);
			const identity = execution.subject.kind === "repository" ? value.headRefOid : value.artifactDigest;
			if (identity !== (execution.subject.commit ?? execution.subject.digest)) throw new Error("Check responses must name the exact checked headRefOid or artifactDigest");
		}
	} else if (record.kind !== "report") {
		if (!nonblank(record.judgment?.reviewer) || !nonblank(record.judgment?.rationale) || !Array.isArray(record.judgment?.artifacts) || !record.judgment.artifacts.length || record.judgment.artifacts.some((item) => !nonblank(item))) throw new Error("An attributed judgment requires reviewer, rationale and inspected artifact references");
		const identity = execution.subject.commit ?? execution.subject.digest;
		if (record.judgment.artifacts.some((item) => !item.includes(identity))) throw new Error("Judgment artifact references must identify the exact inspected commit or content digest");
		const values = (value) => typeof value === "string" ? [value] : value && typeof value === "object" ? Object.values(value).flatMap(values) : [];
		const retained = [source.text];
		try { retained.push(...values(JSON.parse(source.text))); } catch { /* Plain review text remains usable. */ }
		if ([record.judgment.reviewer, record.judgment.rationale, ...record.judgment.artifacts].some((value) => !retained.some((part) => part.includes(value)))) throw new Error("Judgment attribution, rationale and artifacts must appear in the retained review observation");
		if (source.isError) throw new Error("A failed observation cannot support an approving judgment");
	}
	if (record.supersedes && !(state.criterionEvidence ?? []).some((item) => item.id === record.supersedes && item.criterionId === record.criterionId && item.kind === record.kind && equal(item.subject, record.subject))) throw new Error("Supersession must identify evidence for the same criterion, kind and subject");
	return { ...record, contractId: state.contract.contractId, source: { sourceId: source.sourceId, fingerprint: source.fingerprint }, sessionId,
		outcome: source.outcome, recordedAt: new Date().toISOString() };
}

/** completionReceipt renders recorded dispositions without publishing private source text or granting approval. */
export function completionReceipt(state, cwd) {
	const all = state.criterionEvidence ?? [];
	const superseded = new Set(all.map((item) => item.supersedes).filter(Boolean));
	const applicable = (item) => item.contractRevision === state.contract.revision && item.contractId === state.contract.contractId &&
		equal(item.subject, captureSubject(cwd, item.subject)) && !(item.subject.kind === "repository" && item.subject.dirty);
	const criteria = (state.contract.criteria ?? []).map((criterion) => {
		const records = all.filter((item) => item.criterionId === criterion.id && !superseded.has(item.id));
		const current = records.filter(applicable);
		const kinds = criterion.verification?.kinds;
		let disposition = "unresolved";
		if (current.some((item) => item.result === "failed")) disposition = "failed";
		else if (records.length && !current.length) disposition = "stale";
		else if (kinds?.length && kinds.every((kind) => kind !== "report" && current.some((item) => item.kind === kind && item.result === "passed")) && !current.some((item) => item.result !== "passed")) disposition = "passed";
		return { id: criterion.id, disposition, evidence: records.map((item) => ({ id: item.id, kind: item.kind, result: item.result, source: item.source,
			applicability: applicable(item) ? "current" : "stale", ...(item.judgment ? { judgment: item.judgment } : {}) })) };
	});
	const requiredKinds = [...(state.contract.requiredEvidenceKinds ?? []), ...(state.contract.requiredReviewKinds ?? [])];
	const missingKinds = requiredKinds.filter((kind) => !all.some((item) => item.kind === kind && item.result === "passed" && applicable(item) && !superseded.has(item.id)));
	const approvals = state.contract.approvalRequirements;
	const outstandingApprovals = approvals === null ? null : approvals.filter((requirement) => !all.some((item) => item.kind === "approval" && item.requirement === requirement && item.result === "passed" && applicable(item) && !superseded.has(item.id)));
	const unknownRequirements = ["requiredEvidenceKinds", "requiredReviewKinds", "approvalRequirements"].filter((key) => state.contract[key] === null);
	return { taskId: state.taskId, objective: state.contract.objective, contractId: state.contract.contractId, revision: state.contract.revision,
		artifacts: [...new Map(all.map((item) => [JSON.stringify(item.subject), item.subject])).values()], criteria,
		notVerified: criteria.filter((item) => item.disposition !== "passed").map((item) => item.id), missingKinds, unknownRequirements,
		decisions: state.contractHistory.map(({ revision, change }) => ({ revision, rationale: change })),
		risks: state.plan?.risks === undefined ? null : { kind: "agent-report", items: state.plan.risks }, outstandingApprovals,
		verified: Boolean(criteria.length) && criteria.every((item) => item.disposition === "passed") && !missingKinds.length && !unknownRequirements.length && outstandingApprovals?.length === 0,
		limits: "Command/check outcomes, attributed judgments and agent reports remain distinct. Evidence accounting does not prove arbitrary semantics or the meaning of approval prose. Source excerpts are private; rendering does not publish or complete anything." };
}
