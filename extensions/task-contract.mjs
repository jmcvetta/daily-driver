import { randomUUID } from "node:crypto";

const FIELDS = ["objective", "scope", "exclusions", "constraints", "criteria", "requiredEvidenceKinds", "requiredReviewKinds", "approvalRequirements"];
const copy = (value) => JSON.parse(JSON.stringify(value));
const nonblank = (value) => typeof value === "string" && Boolean(value.trim());
const sourceReference = (source, quote) => ({ sourceId: source.sourceId, quote, sourceClass: source.kind,
	origin: source.origin ?? null, version: source.version ?? source.fingerprint ?? null });

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
	for (const criterion of next.criteria) {
		if (!nonblank(criterion.id) || !nonblank(criterion.description) || ids.has(criterion.id)) throw new Error("Criterion ids must be nonblank and unique");
		ids.add(criterion.id);
		if (!Array.isArray(criterion.sourceRefs) || !criterion.sourceRefs.length) throw new Error("Every criterion requires retained source references");
		criterion.sourceRefs = criterion.sourceRefs.map(normalize);
	}
	const changedKnown = FIELDS.some((key) => state.contract[key] !== null && JSON.stringify(state.contract[key]) !== JSON.stringify(next[key]));
	const previous = state.contract.criteria ?? [];
	const removed = previous.filter((criterion) => !ids.has(criterion.id));
	const changedCriteria = previous.some((criterion) => ids.has(criterion.id) && JSON.stringify(criterion) !== JSON.stringify(next.criteria.find((item) => item.id === criterion.id)));
	const changesObjective = state.contract.objective !== null && next.objective !== state.contract.objective;
	// Adding sourced detail to unknown fields and appending criteria is not a scope reduction.
	const changesBinding = ["operation", "target"].some((key) => record[key] !== undefined && record[key] !== state[key]);
	for (const key of ["operation", "target"]) if (record[key] !== undefined && !nonblank(record[key])) throw new Error(`${key} must be nonblank`);
	const requiresDecision = changesBinding || changesObjective || changedCriteria || removed.length > 0 ||
		FIELDS.filter((key) => !["objective", "criteria"].includes(key)).some((key) => state.contract[key] !== null && JSON.stringify(state.contract[key]) !== JSON.stringify(next[key]));
	if (requiresDecision) {
		const authority = reference(record.authoritySource, true);
		if (authority.kind !== "user" || authority.sourceId === state.externalSourceId) throw new Error("A material contract amendment requires the applicable later original user decision");
		if (authority.taskSourceId !== state.externalSourceId && authority.sourceId !== state.externalSourceId) throw new Error("The amendment decision belongs to another task");
	}
	if (removed.length && (!Array.isArray(record.removedCriteria) || removed.some((criterion) => !record.removedCriteria.some((item) => item.id === criterion.id && nonblank(item.reason))))) throw new Error("Record each removed criterion and its user-authorized reason");
	if (!changesBinding && !changedKnown && FIELDS.every((key) => JSON.stringify(state.contract[key]) === JSON.stringify(next[key]))) return state;
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
