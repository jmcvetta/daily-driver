import { randomUUID } from "node:crypto";

const FIELDS = ["objective", "scope", "exclusions", "constraints", "criteria", "requiredEvidenceKinds", "requiredReviewKinds", "approvalRequirements"];
const copy = (value) => JSON.parse(JSON.stringify(value));
const nonblank = (value) => typeof value === "string" && Boolean(value.trim());
export const sourceReference = (source, quote) => ({ sourceId: source.sourceId, quote, sourceClass: source.kind,
	origin: source.origin ?? null, version: source.version ?? source.fingerprint ?? null });

/**
 * criterionDefinitionsMatch reports whether two criteria keep the complete definition.
 *
 * @param {object} left - The historical or current criterion.
 * @param {object} right - The criterion to compare.
 * @returns {boolean} Whether id, description, sources and verification match.
 */
export function criterionDefinitionsMatch(left, right) {
	return JSON.stringify([left.id, left.description, left.sourceRefs.map((ref) => [ref?.sourceId, ref?.quote]), left.verification ?? null]) ===
		JSON.stringify([right.id, right.description, right.sourceRefs.map((ref) => [ref?.sourceId, ref?.quote]), right.verification ?? null]);
}

/** Recovery guidance for a failed initial grounding that replaces the auto-captured request criterion. */
const GROUNDING_RECOVERY = "Initial grounding must keep the auto-captured request criterion: retain `request`, append sourced acceptance criteria, populate the unknown fields, and declare each criterion's verification before execution. Evidence for a criterion remains valid across revisions only while its complete definition is unchanged and the cited revision exists in contract history. Replacing or removing `request` is a material amendment that needs a later original user decision (authoritySource) and removedCriteria with the user-authorized reason.";

/** createContract retains a request without inventing unspecified acceptance or approval requirements. */
export function createContract(taskId, source) {
	const reference = sourceReference(source, source.text);
	return {
		schemaVersion: 1, contractId: `contract:${randomUUID()}`, taskId, revision: 1,
		objective: source.text, scope: null, exclusions: null, constraints: null,
		criteria: [{ id: "request", description: source.text, sourceRefs: [reference], interpretation: true }],
		requiredEvidenceKinds: null, requiredReviewKinds: null, approvalRequirements: null,
		sourceRefs: [reference],
	};
}

/** migrateContractState preserves historical reports and leaves unsourced contract fields unknown. */
export function migrateContractState(state, sources) {
	if (!state || state.contractSchemaVersion === 1) return state;
	const source = sources.find((item) => item.sourceId === state.externalSourceId);
	const contract = source ? createContract(state.taskId, source) : {
		schemaVersion: 1, contractId: `contract:${randomUUID()}`, taskId: state.taskId, revision: 1,
		objective: null, scope: null, exclusions: null, constraints: null, criteria: null,
		requiredEvidenceKinds: null, requiredReviewKinds: null, approvalRequirements: null, sourceRefs: [],
	};
	return {
		...state, contractSchemaVersion: 1, contract, executionBound: true,
		contractHistory: [{ revision: 1, contract: copy(contract), change: "Explicit migration from task evidence state", sourceRefs: contract.sourceRefs }],
		plan: null, migration: { from: "task-evidence-state", completion: state.status === "reported-complete" ? "reported, not verified" : null },
	};
}

/** amendContract validates a sourced revision without changing mutable execution progress. */
export function amendContract(state, record, reference) {
	if (record.expectedRevision !== state.contract.revision) throw new Error("Contract revision changed; read status before amending");
	if (!nonblank(record.change)) throw new Error("Describe the contract change");
	if (!Array.isArray(record.sourceRefs) || !record.sourceRefs.length) throw new Error("Contract amendments require retained original source references");
	const normalize = (ref) => sourceReference(reference(ref), ref.quote);
	const sourceRefs = record.sourceRefs.map(normalize);
	const patch = record.contract;
	if (!patch || typeof patch !== "object" || Array.isArray(patch)) throw new Error("contract must contain the changed contract fields");
	if (Object.keys(patch).some((key) => !FIELDS.includes(key))) throw new Error("Contract identity, revision and source references are controller-owned");
	const next = { ...copy(state.contract), ...copy(patch) };
	if (!nonblank(next.objective)) throw new Error("A sourced contract objective is required");
	for (const key of FIELDS.filter((key) => !["objective", "criteria"].includes(key))) {
		if (next[key] !== null && (!Array.isArray(next[key]) || next[key].some((item) => !nonblank(item)))) throw new Error(`${key} must be an array of nonblank requirements or null for unknown`);
	}
	if (!Array.isArray(next.criteria) || !next.criteria.length) throw new Error("A contract needs stable acceptance-criterion ids");
	const ids = new Set();
	// Key order and controller-added fields are not requirement changes.
	const previousById = new Map((state.contract.criteria ?? []).map((criterion) => [criterion.id, criterion]));
	next.criteria = next.criteria.map((criterion) => {
		if (!nonblank(criterion?.id) || !nonblank(criterion.description) || ids.has(criterion.id)) throw new Error("Criterion ids must be nonblank and unique");
		ids.add(criterion.id);
		if (!Array.isArray(criterion.sourceRefs) || !criterion.sourceRefs.length) throw new Error("Every criterion requires retained source references");
		if (criterion.verification !== undefined) {
			const verification = criterion.verification;
			const example = 'Example: {kinds:["command"],toolName:"bash",input:{command:"make check",cwd:"/path/to/worktree"},subject:{kind:"repository",root:"/path/to/worktree"}}';
			const invalid = (reason) => { throw new Error(`${reason}. ${example} For an established declaration, correction requires a later original user decision (authoritySource).`); };
			if (!verification || typeof verification !== "object" || Array.isArray(verification) ||
				!Array.isArray(verification.kinds) || !verification.kinds.length ||
				verification.kinds.some((kind) => !["command", "check", "judgment", "approval", "report"].includes(kind))) invalid("verification.kinds must be a nonempty array of supported evidence kinds");
			const subject = verification.subject;
			if (!subject || typeof subject !== "object" || Array.isArray(subject) ||
				!((subject.kind === "repository" && nonblank(subject.root)) || (subject.kind === "artifact" && nonblank(subject.path)))) invalid("verification.subject requires a repository root or artifact path");
			if (verification.kinds.some((kind) => kind === "command" || kind === "check")) {
				if (!nonblank(verification.toolName)) invalid("Command/check verification requires a nonblank toolName");
				if (!verification.input || typeof verification.input !== "object" || Array.isArray(verification.input)) invalid("Command/check verification.input must be the actual tool input object, not a command string");
				if (verification.toolName === "bash" && verification.kinds.includes("check")) invalid("Native bash supplies command evidence, not check conclusions; use command instead of check");
			}
		}
		// An unchanged criterion keeps its recorded form; a delegated child may not hold the parent's sources.
		const previous = previousById.get(criterion.id);
		return previous && criterionDefinitionsMatch(previous, criterion) ? previous : { ...criterion, sourceRefs: criterion.sourceRefs.map(normalize) };
	});
	const previous = state.contract.criteria ?? [];
	const removed = previous.filter((criterion) => !ids.has(criterion.id));
	let changedGroundedRequest = false;
	const changedCriteria = previous.some((criterion) => {
		const nextCriterion = next.criteria.find((item) => item.id === criterion.id);
		if (!nextCriterion) return false;
		// Grounding an unknown verification contract adds detail; changing an established one changes the requirement.
		const changed = !criterionDefinitionsMatch(criterion.verification === undefined ? { ...criterion, verification: nextCriterion.verification } : criterion, nextCriterion);
		if (changed && criterion.id === "request" && criterion.interpretation === true) changedGroundedRequest = true;
		return changed;
	});
	const changesObjective = state.contract.objective !== null && next.objective !== state.contract.objective;
	// Adding sourced detail to unknown fields and appending criteria is not a scope reduction.
	const changesBinding = ["operation", "target"].some((key) => record[key] !== undefined && record[key] !== state[key]);
	for (const key of ["operation", "target"]) if (record[key] !== undefined && !nonblank(record[key])) throw new Error(`${key} must be nonblank`);
	const requiresDecision = changesBinding || changesObjective || changedCriteria || removed.length > 0 ||
		FIELDS.filter((key) => !["objective", "criteria"].includes(key)).some((key) => state.contract[key] !== null && JSON.stringify(state.contract[key]) !== JSON.stringify(next[key]));
	if (requiresDecision) {
		const groundedRequest = previous.find((criterion) => criterion.id === "request" && criterion.interpretation === true);
		const touchedGroundedRequest = groundedRequest && (removed.some((item) => item.id === groundedRequest.id) || changedGroundedRequest);
		if (touchedGroundedRequest) {
			const candidate = record.authoritySource ? reference(record.authoritySource, true) : null;
			const authorized = Boolean(candidate) && candidate.kind === "user" && candidate.sourceId !== state.externalSourceId &&
				(candidate.taskSourceId === state.externalSourceId || candidate.sourceId === state.resumeSource?.sourceId);
			if (!authorized) throw new Error(GROUNDING_RECOVERY);
		}
		const authority = reference(record.authoritySource, true);
		if (authority.kind !== "user" || authority.sourceId === state.externalSourceId) throw new Error("A material contract amendment requires the applicable later original user decision");
		if (authority.taskSourceId !== state.externalSourceId && authority.sourceId !== state.resumeSource?.sourceId) throw new Error("The amendment decision belongs to another task");
	}
	if (removed.length && (!Array.isArray(record.removedCriteria) || removed.some((criterion) => !record.removedCriteria.some((item) => item.id === criterion.id && nonblank(item.reason))))) throw new Error("Record each removed criterion and its user-authorized reason");
	if (!changesBinding && FIELDS.every((key) => JSON.stringify(state.contract[key]) === JSON.stringify(next[key]))) return state;
	next.revision += 1;
	next.sourceRefs = [...state.contract.sourceRefs, ...sourceRefs];
	return {
		...state, contract: next, operation: record.operation ?? state.operation, target: record.target ?? state.target,
		contractHistory: [...state.contractHistory, { revision: next.revision, contract: copy(next), change: record.change,
			sourceRefs, authoritySource: record.authoritySource ? sourceReference(reference(record.authoritySource, true), record.authoritySource.quote) : null, removedCriteria: record.removedCriteria ?? [] }],
	};
}

/** contractHandoff carries scope and authority locators, never a new grant of approval. */
export function contractHandoff(state, origin) {
	return {
		schemaVersion: 1, origin, contract: copy(state.contract), history: copy(state.contractHistory),
		plan: copy(state.plan), status: state.status, corrections: state.corrections, condition: state.condition,
		operation: state.operation, target: state.target,
		correctionIdentity: state.correctionIdentity ?? state.externalSourceId, correctionFailures: state.correctionFailures ?? [],
		authorityTaskIds: [...new Set([state.externalSourceId, ...(state.authorityTaskIds ?? [])])],
		unresolved: state.contract.criteria?.map((item) => item.id) ?? null,
		authorityReferences: state.authorizations.map((item) => ({ id: item.id, kind: item.kind, source: item.source, operation: item.operation,
			target: item.target, limits: item.limits, conditions: item.conditions, expiresAt: item.expiresAt,
			revokes: item.revokes, supersedes: item.supersedes, freshConfirmation: item.freshConfirmation })),
		notice: "Scope is delegated. Authority remains at the original retained sources and must be revalidated there. No criterion is verified by this handoff.",
	};
}
