import { createHash, randomUUID } from "node:crypto";
import { amendContract, contractHandoff, createContract, migrateContractState, sourceReference } from "./task-contract.mjs";
import { captureSubject, completionReceipt, observedOutcome, recordEvidence } from "./task-evidence.mjs";

const STATE = "daily-driver.task-state";
const SOURCE = "daily-driver.task-source";
const OBSERVATION = "daily-driver.task-observation";
const RULE = "Continue authorized unfinished work. Diagnose ordinary failures and use permitted alternatives. Before asking for approval, inspect applicable original sources and their limits. A record does not grant permission or override harness or safety restrictions. Stop only for evidence-backed completion, cancellation, an evidenced external prerequisite after independent work, or the bounded execution failure.";
const REQUEST = /^(?:\s*(?:please\s+)?(?:implement|fix|update|add|remove|refactor|complete|resolve|undertake|build|create|change|investigate|debug|repair|migrate|address|test|verify)\b|\s*\/(?:skill:)?undertake\b|\s*(?:can|could|would) you\s+(?:please\s+)?(?:implement|fix|update|add|remove|refactor|complete|resolve|build|create|change|investigate|debug|repair|migrate|address|test|verify)\b)/iu;
const CANCEL = /^\s*(?:please\s+)?(?:\/(?:skill:)?stand-down\b|stand[ -]down\b|wrap\s+up\b|cancel(?:[.!\s]*$|\s+(?:(?:this|the)\s+)?(?:task|work|undertaking)(?=\s|[.!;,]|$))|stop(?:[.!\s]*$|\s+(?:work(?:ing)?(?=\s|[.!;,]|$)|now\b|here\b|(?:this|the)\s+(?:task|work|undertaking)(?=\s|[.!;,]|$))))/iu;
const EVIDENCE_TEXT_LIMIT = 8192;
const EVIDENCE_INPUT_LIMIT = 2048;
const AUTHORIZATION_KINDS = ["user", "workflow"];
const BLOCKER_KINDS = ["external", "authorization", "safety", "execution"];
const ROUTE_DISPOSITIONS = ["failed", "prohibited", "unavailable"];
// Renders an enum as prose for the device description so it cannot drift from validation.
const oneOf = (items) => items.length === 2 ? items.map((item) => `"${item}"`).join(" or ")
	: `${items.slice(0, -1).map((item) => `"${item}"`).join(", ")}, or "${items.at(-1)}"`;

/** stripContractTags removes contract tags from model-written task input, wherever the harness renders it. */
function stripContractTags(value) {
	if (typeof value === "string") {
		// Repeat until stable: removing an inner tag must not join its neighbours into a new one.
		let text = value;
		for (let previous; previous !== text;) { previous = text; text = text.replace(/<\/?daily-driver-task-contract>/gu, ""); }
		return text;
	}
	if (Array.isArray(value)) return value.map(stripContractTags);
	if (value && typeof value === "object") return Object.fromEntries(Object.entries(value).map(([key, item]) => [key, stripContractTags(item)]));
	return value;
}

function digest(value) {
	return createHash("sha256").update(JSON.stringify(value)).digest("hex");
}

function text(content) {
	return typeof content === "string" ? content : Array.isArray(content)
		? content.filter((part) => part?.type === "text").map((part) => part.text).join("\n") : "";
}

function required(value, name) {
	if (typeof value !== "string" || !value.trim()) throw new Error(`${name} must be nonblank`);
	return value;
}

/** createTaskStateController applies shared contract, authority and continuation transitions to a native session ledger. */
export function createTaskStateController(pi) {
	// Each native session keeps its own pending stop, so a subagent cannot release the main session's abort listener.
	const pendingStops = new Map();

	function releaseStop(key) {
		const pending = pendingStops.get(key);
		if (!pending) return;
		pending.signal.removeEventListener("abort", pending.onAbort);
		pendingStops.delete(key);
	}

	function agentEnd(event, ctx) {
		if (!available(ctx)) return;
		if (ctx.agent.kind === "sub" && event.messages?.at(-1)?.stopReason === "aborted") cancel(ctx, "subagent-abort");
		if (!event.willContinue) releaseStop(sessionId(ctx));
	}

	function shutdown() {
		for (const key of [...pendingStops.keys()]) releaseStop(key);
	}
	const available = (ctx) => ["main", "sub"].includes(ctx?.agent?.kind) &&
		typeof ctx.sessionManager?.getBranch === "function" &&
		typeof ctx.sessionManager?.getSessionId === "function";

	function capability() {
		if (typeof pi.getActiveTools !== "function") return { enforced: false, reason: "Active tool visibility is unavailable." };
		const active = pi.getActiveTools();
		if (active.includes("daily_driver_task_state")) return { enforced: true, route: "direct" };
		if (active.includes("write") && typeof pi.getAllTools === "function" &&
			pi.getAllTools().some((tool) => tool.name === "daily_driver_task_state")) {
			return { enforced: true, route: "write-device" };
		}
		return { enforced: false, reason: "The task-state tool is not exposed directly and its write device is unavailable in this tool scope." };
	}
	const branch = (ctx) => available(ctx) ? ctx.sessionManager.getBranch() : [];
	const sessionId = (ctx) => ctx.sessionManager.getSessionId();
	const entries = (ctx, type) => branch(ctx).filter((entry) => entry.type === "custom" &&
		entry.customType === type && entry.data?.sessionId === sessionId(ctx));
	const read = (ctx) => {
		const state = entries(ctx, STATE).at(-1)?.data?.state ?? null;
		if (!state || state.contractSchemaVersion === 1) return state;
		const migrated = migrateContractState(state, sources(ctx));
		pi.appendEntry(STATE, { sessionId: sessionId(ctx), state: migrated });
		return migrated;
	};
	const save = (ctx, state) => pi.appendEntry(STATE, { sessionId: sessionId(ctx), state });
	const sources = (ctx) => entries(ctx, SOURCE).map((entry) => entry.data.source);
	const observations = (ctx) => entries(ctx, OBSERVATION).map((entry) => entry.data.observation);

	function retainedObservation(ctx, source) {
		if (!source?.textTruncated) return source;
		const message = branch(ctx).find((entry) => entry.type === "message" && entry.message?.role === "toolResult" && `tool:${entry.message.toolCallId}` === source.sourceId)?.message;
		const output = message ? text(message.content) : null;
		if (output === null || digest(output) !== source.outputFingerprint) return source;
		return { ...source, text: output, textTruncated: false, recoveredFromNativeEntry: true };
	}

	function reference(ctx, ref, authority = false) {
		if (!ref || typeof ref.sourceId !== "string") throw new Error("A real sourceId and exact quote are required");
		const source = retainedObservation(ctx, sources(ctx).find((item) => item.sourceId === ref.sourceId) ??
			(!authority && observations(ctx).find((item) => item.sourceId === ref.sourceId)) ?? pi.resolveSource?.(ref.sourceId));
		const retained = source?.kind === "tool" && source.textTruncated
			? [source.text.slice(0, source.prefixLength), source.text.slice(source.prefixLength + 1)]
			: [source?.text ?? ""];
		if (!source || !required(ref.quote, "source quote").trim() || !retained.some((part) => part.includes(ref.quote))) {
			throw new Error(`Source reference ${ref.sourceId} does not match active-branch evidence`);
		}
		return source;
	}

	function authorizationStatus(ctx, state, item) {
		try { reference(ctx, item.source, true); } catch { return "source-unavailable"; }
		if (item.taskId !== state.taskId || item.operation !== state.operation || item.target !== state.target) return "out-of-scope";
		if (state.authorizations.some((other) => other.revokes === item.id)) return "revoked";
		if (state.authorizations.some((other) => other.supersedes === item.id)) return "superseded";
		if (item.revokes || item.supersedes) return "amendment";
		if (item.expiresAt && Date.parse(item.expiresAt) <= Date.now()) return "expired";
		if (item.freshConfirmation) return "fresh-confirmation-required";
		return "source-anchored-review-conditions";
	}

	function status(ctx, request = {}) {
		const state = read(ctx);
		const excerpt = (item) => ({ ...item, text: item.text.slice(0, 2000), truncated: item.text.length > 2000 });
		const source = request.sourceId
			? retainedObservation(ctx, [...sources(ctx), ...observations(ctx)].find((item) => item.sourceId === request.sourceId) ?? pi.resolveSource?.(request.sourceId)) : undefined;
		return {
			state,
			receipt: state ? completionReceipt(state, ctx.cwd) : null,
			capability: capability(),
			tasks: [...new Map(entries(ctx, STATE).map((entry) => [entry.data.state.contract?.contractId ?? entry.data.state.taskId, {
				taskId: entry.data.state.taskId, contractId: entry.data.state.contract?.contractId ?? null, status: entry.data.state.status,
			}])).values()],
			authorizations: state?.authorizations.map((item) => ({ ...item, applicability: authorizationStatus(ctx, state, item) })) ?? [],
			sources: sources(ctx).slice(-8).map(excerpt),
			evidence: observations(ctx).filter((item) => item.taskSourceId === state?.externalSourceId).slice(-8).map(excerpt),
			...(request.sourceId ? { source: source ?? null } : {}),
			limits: "References prove provenance, not semantic approval or route exhaustion. Completion requires applicable criterion evidence; judgments remain attributed judgments, not deterministic proof. Handoffs carry locators, never private source excerpts.",
		};
	}

	function begin(ctx, record, source) {
		const current = read(ctx);
		if (current?.status === "cancelled" && current.externalSourceId === source.sourceId) {
			throw new Error("Cancelled work requires fresh external user input");
		}
		// A newTask begin on the request that already opened the task binds it rather than duplicating it.
		if (current && (!record.newTask || current.externalSourceId === source.sourceId)) {
			if (current.status !== "active") throw new Error("A settled task requires an explicit sourced resume or newTask");
			if ((current.executionBound || current.contract.scope !== null) && ["taskId", "operation", "target"].some((key) => record[key] && record[key] !== current[key])) {
				throw new Error("begin cannot rewrite contracted scope; use a sourced contract amendment");
			}
			const next = { ...current, taskId: record.taskId ?? current.taskId,
				operation: record.operation ?? current.operation, target: record.target ?? current.target };
			if (!current.executionBound && (record.taskId || record.operation || record.target)) {
				const contract = { ...current.contract, taskId: next.taskId, revision: current.contract.revision + 1 };
				next.executionBound = true;
				next.contract = contract;
				next.contractHistory = [...current.contractHistory, { revision: contract.revision, contract,
					change: "Bind request to its execution operation and target", sourceRefs: [sourceReference(source, source.text)] }];
			}
			save(ctx, next);
			return;
		}
		const taskId = record.taskId ?? source.sourceId;
		const contract = createContract(taskId, source);
		save(ctx, {
			taskId, operation: record.operation ?? source.text,
			target: record.target ?? ctx.cwd, externalSourceId: source.sourceId,
			status: "active", authorizations: [], blocker: null, corrections: 0, condition: null,
			contractSchemaVersion: 1, contract, plan: null,
			executionBound: Boolean(record.taskId || record.operation || record.target),
			contractHistory: [{ revision: 1, contract, change: "Capture original request", sourceRefs: contract.sourceRefs }],
		});
	}

	function adopt(ctx, handoff, eventId) {
		if (read(ctx)) return;
		if (!handoff?.contract || handoff.contract.schemaVersion !== 1 ||
			typeof handoff.contract.contractId !== "string" || !Number.isInteger(handoff.contract.revision)) throw new Error("Unsupported delegated task contract");
		// A distinct namespace keeps the child's own prompt on the same turn from being dropped as a duplicate.
		const sourceId = `interpretation:delegation:${eventId ?? randomUUID()}`;
		pi.appendEntry(SOURCE, { sessionId: sessionId(ctx), source: {
			sourceId, kind: "interpretation", text: handoff.contract.objective ?? "Delegated contract",
			origin: handoff.origin, taskSourceId: sourceId, delegatedSourceRefs: handoff.contract.sourceRefs,
		} });
		save(ctx, {
			taskId: handoff.contract.taskId, operation: handoff.operation, target: handoff.target,
			externalSourceId: sourceId, status: handoff.status, executionBound: true,
			contractSchemaVersion: 1, contract: handoff.contract, contractHistory: handoff.history,
			plan: handoff.plan, authorizations: handoff.authorityReferences.map((item) => ({ ...item, taskId: handoff.contract.taskId })),
			blocker: null, corrections: handoff.corrections, condition: handoff.condition,
			correctionIdentity: handoff.correctionIdentity, inheritedFailures: handoff.correctionFailures ?? [],
			authorityTaskIds: handoff.authorityTaskIds, delegationOrigin: handoff.origin,
		});
	}

	function input(event, ctx) {
		if (!available(ctx)) return;
		const kind = ["interactive", "rpc"].includes(event.source) ? "user" : "interpretation";
		const sourceId = event.eventId ? `${kind}:${event.eventId}` : `${kind}:${randomUUID()}`;
		if (sources(ctx).some((item) => item.sourceId === sourceId)) return;
		const current = read(ctx);
		const source = { sourceId, kind, text: event.text,
			origin: event.origin ?? { harness: event.harness ?? "omp", sessionId: sessionId(ctx), channel: event.source },
			version: digest(event.text), // A fresh request after a settled or cancelled task starts its own authority scope.
			taskSourceId: current?.status === "active" || !(kind === "user" && REQUEST.test(event.text)) ? current?.externalSourceId ?? sourceId : sourceId };
		pi.appendEntry(SOURCE, { sessionId: sessionId(ctx), source });
		if (kind !== "user") {
			if (event.allowTask && !current && REQUEST.test(event.text)) begin(ctx, {}, source);
			return;
		}
		if (CANCEL.test(event.text)) {
			if (current?.status === "active") save(ctx, { ...current, status: "cancelled", cancellationSource: source.sourceId });
			return;
		}
		if (REQUEST.test(event.text) && current?.status !== "active") begin(ctx, current ? { newTask: true } : {}, source);
	}

	function toolResult(event, ctx) {
		const state = read(ctx);
		if (!available(ctx) || !read(ctx) ||
			["daily_driver_task_state", "daily_driver_get_session", "daily_driver_set_session_title"].includes(event.toolName) ||
			event.input?.path === "xd://daily_driver_task_state") return;
		const output = text(event.content);
		const input = JSON.stringify(event.input ?? {});
		const textTruncated = output.length > EVIDENCE_TEXT_LIMIT;
		const prefixLength = EVIDENCE_TEXT_LIMIT / 2;
		const observation = {
			sourceId: `tool:${event.toolCallId}`, kind: "tool", toolName: event.toolName,
			input: input.slice(0, EVIDENCE_INPUT_LIMIT), inputTruncated: input.length > EVIDENCE_INPUT_LIMIT,
			text: textTruncated ? `${output.slice(0, prefixLength)}\n${output.slice(-(EVIDENCE_TEXT_LIMIT - prefixLength - 1))}` : output,
			textTruncated, prefixLength, originalTextLength: output.length,
			fingerprint: digest([event.toolName, event.input, output]), isError: Boolean(event.isError),
			outputFingerprint: digest(output),
			outcome: observedOutcome(event),
			execution: entries(ctx, "daily-driver.task-execution").find((entry) => entry.data.toolCallId === event.toolCallId)?.data.execution ?? null,
			origin: { sessionId: sessionId(ctx), toolCallId: event.toolCallId, input: input.slice(0, EVIDENCE_INPUT_LIMIT) },
			taskSourceId: entries(ctx, "daily-driver.task-execution").find((entry) => entry.data.toolCallId === event.toolCallId)?.data.externalSourceId ?? state.externalSourceId,
		};
		if (!observations(ctx).some((item) => item.sourceId === observation.sourceId)) {
			pi.appendEntry(OBSERVATION, { sessionId: sessionId(ctx), observation });
		}
	}

	function instructions(ctx) {
		const state = read(ctx);
		const handoff = state ? {
			taskId: state.taskId, operation: state.operation, target: state.target, status: state.status,
			externalSourceId: state.externalSourceId, authorizations: state.authorizations,
			blocker: state.blocker, corrections: state.corrections, stopFailure: state.stopFailure,
			contract: state.contract, contractHistory: state.contractHistory.slice(-4).map(({ revision, change, sourceRefs }) => ({ revision, change, sourceRefs })), plan: state.plan,
			receipt: completionReceipt(state, ctx.cwd),
		} : null;
		const support = capability();
		if (!support.enforced) return `${RULE}\nRuntime task-state stop enforcement is unavailable: ${support.reason} The shared continuation rule still applies. Do not expand tool permissions, invent a human blocker, or claim record-based enforcement. Retain authorization and blocker evidence in the normal handoff.\nCurrent private task handoff:\n${JSON.stringify(handoff)}`;
		return `${RULE}\nUse daily_driver_task_state status before an unfinished stop. Ground criterion verification as {kinds: [command|check|judgment|approval|report], toolName, input}. Unknown requirements remain unresolved. Record evidence with taskId, criterionId, contractRevision, captured subject, source, kind and result. Command/check passes require actual outcomes for the declared operation. Judgments require reviewer, rationale and inspected artifacts. Reports cannot establish a pass. receipt renders current dispositions without publishing or completing. complete requires every criterion, review and approval; it cannot waive absent, stale or failed evidence. Use contract for sourced amendments, plan for execution changes, and blocker for legitimate external waits. Cancellation and bounded corrections remain available. Never publish private sources.\nCurrent private task handoff:\n${JSON.stringify(handoff)}`;
	}

	const shouldExpose = (ctx) => available(ctx) && ["active", "cancelled"].includes(read(ctx)?.status);

	function beforeAgentStart(event, ctx) {
		if (!available(ctx)) return;
		if (ctx.agent.kind === "sub" && !read(ctx) && event.prompt) {
			const delegatedContext = [...(event.systemPrompt ?? []), event.prompt].join("\n");
			// delegateCall strips tags from every model-written field, so only a lone tag is genuine; more than one adopts nothing.
			const tags = [...delegatedContext.matchAll(/<daily-driver-task-contract>([A-Za-z0-9_-]+)<\/daily-driver-task-contract>/gu)];
			const encoded = tags.length === 1 ? tags[0][1] : undefined;
			// Only a parent contract makes a child a task; a delegated prompt alone is not a user request.
			if (encoded) adopt(ctx, JSON.parse(Buffer.from(encoded, "base64url").toString("utf8")));
		}
		const systemPrompt = event.systemPrompt ?? [];
		const policy = systemPrompt.join("\n\n");
		const source = { sourceId: `system:${digest(policy)}`, kind: "workflow", text: policy,
			origin: event.origin ?? { harness: "omp", sessionId: sessionId(ctx), channel: "system-prompt" }, version: digest(policy) };
		if (policy && !sources(ctx).some((item) => item.sourceId === source.sourceId)) {
			pi.appendEntry(SOURCE, { sessionId: sessionId(ctx), source });
		}
		if (!shouldExpose(ctx)) return;
		return { systemPrompt: [...systemPrompt, instructions(ctx)] };
	}
	function context(event, ctx) {
		if (!shouldExpose(ctx)) return;
		return { messages: [...event.messages, {
			role: "custom", customType: STATE, content: instructions(ctx), display: false, timestamp: Date.now(),
		}] };
	}
	const compacting = (_event, ctx) => shouldExpose(ctx) ? { context: [instructions(ctx)] } : undefined;

	function delegateCall(event, ctx) {
		const state = available(ctx) ? read(ctx) : null;
		if (state?.status === "active" && event.toolCallId && event.toolName !== "daily_driver_task_state" && event.input?.path !== "xd://daily_driver_task_state") {
			const cwd = event.input?.cwd ?? ctx.cwd;
			const criterion = state.contract.criteria?.find((item) => item.verification?.toolName === event.toolName && JSON.stringify(item.verification.input) === JSON.stringify(event.input ?? {}));
			pi.appendEntry("daily-driver.task-execution", { sessionId: sessionId(ctx), toolCallId: event.toolCallId, externalSourceId: state.externalSourceId,
				execution: { taskId: state.taskId, contractId: state.contract.contractId, contractRevision: state.contract.revision,
					sessionId: sessionId(ctx), inputFingerprint: digest(event.input ?? {}), subject: captureSubject(cwd, criterion?.verification.subject) } });
		}
		if (event.toolName !== "task" || !state || state.status !== "active") return;
		const handoff = contractHandoff(state, { harness: "omp", sessionId: sessionId(ctx), sourceId: state.externalSourceId });
		const input = stripContractTags(event.input ?? {});
		return { input: { ...input, context: `${input.context ?? ""}\n<daily-driver-task-contract>${Buffer.from(JSON.stringify(handoff)).toString("base64url")}</daily-driver-task-contract>` } };
	}

	async function execute(_id, params, _signal, _update, ctx) {
			try {
				if (!available(ctx)) throw new Error("Durable task state requires the native session branch API");
				if (_signal?.aborted && !["status", "receipt"].includes(params.action)) {
					cancel(ctx, "task-state-abort");
					throw new Error("Task-state action cancelled");
				}
				const record = params.record ? JSON.parse(params.record) : {};
				if (!record || typeof record !== "object" || Array.isArray(record)) throw new Error("record must be a JSON object");
				const state = read(ctx);
				if (params.action === "begin") {
					const source = record.source ? reference(ctx, record.source, true) : sources(ctx).filter((item) => item.kind === "user").at(-1);
					if (!source || source.kind !== "user") throw new Error("Task initiation requires an external user source");
					if (source.sourceId !== sources(ctx).filter((item) => item.kind === "user").at(-1)?.sourceId) throw new Error("Task initiation requires the latest external user source");
					if (CANCEL.test(source.text)) throw new Error("Cancellation is not a fresh work request");
					begin(ctx, record, source);
				} else if (params.action === "resume") {
					const source = reference(ctx, record.source, true);
					const selected = record.contractId ? entries(ctx, STATE).map((entry) => entry.data.state).filter((item) => item.contract?.contractId === record.contractId).at(-1) : state;
					if (!selected || source.kind !== "user" || source.sourceId === selected.externalSourceId || CANCEL.test(source.text) ||
						source.sourceId !== sources(ctx).filter((item) => item.kind === "user").at(-1)?.sourceId) throw new Error("Resume requires fresh original user input and an existing task");
					// Correction counts survive; the old blocker, completion and failure describe the previous run.
					save(ctx, { ...selected, status: "active", resumeSource: record.source,
						blocker: null, completion: undefined, stopFailure: undefined, cancellationSource: undefined });
				} else if (params.action !== "status") {
					if (params.action === "receipt") {
						const receipt = state ? completionReceipt(state, ctx.cwd) : null;
						return { content: [{ type: "text", text: JSON.stringify(receipt) }], details: receipt };
					}
					if (!state || state.status !== "active") throw new Error("No active unfinished task");
					if (params.action === "contract") {
						save(ctx, amendContract(state, record, (ref, authority = false) => reference(ctx, ref, authority)));
					} else if (params.action === "plan") {
						required(record.summary, "plan summary");
						save(ctx, { ...state, plan: record });
					} else if (params.action === "handoff") {
						const handoff = contractHandoff(state, { sessionId: sessionId(ctx), sourceId: state.externalSourceId });
						handoff.receipt = completionReceipt(state, ctx.cwd);
						handoff.unresolved = handoff.receipt.notVerified;
						return { content: [{ type: "text", text: JSON.stringify(handoff) }], details: handoff };
					} else
					if (params.action === "authorization") {
						const source = reference(ctx, record.source, true);
						if (source.kind === "user" && source.sourceId !== state.externalSourceId && source.sourceId !== state.resumeSource?.sourceId &&
							source.taskSourceId !== state.externalSourceId && !state.authorityTaskIds?.includes(source.taskSourceId)) throw new Error("Authorization source belongs to another task");
						if (!AUTHORIZATION_KINDS.includes(record.kind) || record.kind !== source.kind) throw new Error("Authorization kind must match the original user or system source");
						for (const key of ["id", "operation", "target", "limits", "conditions"]) required(record[key], key);
						if (state.authorizations.some((item) => item.id === record.id)) throw new Error("Authorization ids are immutable; use a new superseding or revoking record");
						if (record.expiresAt && !Number.isFinite(Date.parse(record.expiresAt))) throw new Error("expiresAt must be an ISO date");
						for (const key of ["revokes", "supersedes"]) if (record[key] && !state.authorizations.some((item) => item.id === record[key])) throw new Error(`${key} must reference an existing task authorization`);
						save(ctx, { ...state, authorizations: [...state.authorizations, { ...record, taskId: state.taskId }] });
					} else if (params.action === "blocker") {
						// Validate now and again at stop time, when expiry and branch evidence may differ.
						validateBlocker(ctx, state, record);
						save(ctx, { ...state, blocker: record });
					} else if (params.action === "evidence") {
						const source = reference(ctx, record.source);
						const evidence = recordEvidence(state, record, source, sessionId(ctx));
						save(ctx, { ...state, criterionEvidence: [...(state.criterionEvidence ?? []), evidence] });
					} else if (params.action === "complete") {
						required(record.summary, "completion summary");
						const receipt = completionReceipt(state, ctx.cwd);
						if (!receipt.verified) throw new Error(`Completion rejected: ${JSON.stringify({ criteria: receipt.criteria.map(({ id, disposition }) => ({ id, disposition })), missingKinds: receipt.missingKinds, unknownRequirements: receipt.unknownRequirements, outstandingApprovals: receipt.outstandingApprovals })}`);
						save(ctx, { ...state, status: "verified-complete", completion: record.summary, completionReceipt: receipt });
					} else throw new Error("Unknown task-state action");
				}
				const details = status(ctx, params.action === "status" ? record : {});
				return { content: [{ type: "text", text: JSON.stringify(details) }], details };
			} catch (error) {
				return { content: [{ type: "text", text: error.message }], isError: true };
			}
	}

	function validateBlocker(ctx, state, blocker) {
		if (!blocker) throw new Error("Record a blocker with observed evidence, permitted routes, authorization checked, independent work and resumption path; or report completion explicitly");
		if (blocker.operation !== state.operation || blocker.target !== state.target) throw new Error("Blocker operation and target must match the active task scope");
		if (!BLOCKER_KINDS.includes(blocker.kind)) throw new Error("Name the blocker kind");
		for (const key of ["externalContribution", "resume"]) required(blocker[key], key);
		if (!Array.isArray(blocker.evidence) || !blocker.evidence.length) throw new Error("Reference an observed failure or exact authority restriction");
		const evidence = blocker.evidence.map((ref) => reference(ctx, ref));
		if (evidence.some((item) => item.kind === "tool" && item.taskSourceId !== state.externalSourceId)) throw new Error("Evidence belongs to another task");
		if (["execution", "external"].includes(blocker.kind) && !evidence.some((item) => item.kind === "tool")) throw new Error("An execution failure or external wait requires observed tool evidence");
		if (blocker.kind === "execution" && !evidence.some((item) => item.isError)) throw new Error("The referenced result does not report an execution failure");
		if (["safety", "authorization"].includes(blocker.kind) && !evidence.some((item) => ["user", "workflow"].includes(item.kind))) throw new Error("A restriction requires its original authority source; tool text is not authority");
		if (!Array.isArray(blocker.authorizationIds)) throw new Error("List authorizationIds checked, including an empty list when none exist");
		if (state.authorizations.some((item) => !blocker.authorizationIds.includes(item.id))) throw new Error("Review every retained task authorization, including revocations and conditions");
		if (blocker.authorizationIds.some((id) => !state.authorizations.some((item) => item.id === id))) throw new Error("Unknown authorization reference");
		if (!Array.isArray(blocker.routes) || !blocker.routes.length) throw new Error("Record the disposition and evidence for available permitted routes");
		for (const route of blocker.routes) {
			required(route.route, "route");
			if (!ROUTE_DISPOSITIONS.includes(route.disposition)) throw new Error("A route remains actionable");
			const source = reference(ctx, route.evidence);
			if (source.kind === "tool" && source.taskSourceId !== state.externalSourceId) throw new Error("Route evidence belongs to another task");
			if (route.disposition === "failed" && !source.isError) throw new Error("A failed route requires an observed error");
			if (route.disposition === "prohibited" && source.kind === "tool") throw new Error("A prohibited route requires original authority, not a probe");
		}
		if (!Array.isArray(blocker.independentWork?.pending) || !Array.isArray(blocker.independentWork?.completed)) throw new Error("Account for independent pending and completed work");
		if (blocker.kind !== "safety" && blocker.independentWork.pending.length) throw new Error(`Complete independent permitted work first: ${blocker.independentWork.pending.join(", ")}`);
		return evidence;
	}

	function stop(event, ctx) {
		if (!available(ctx)) return;
		let state = read(ctx);
		if (state?.status === "verified-complete") {
			if (completionReceipt(state, ctx.cwd).verified) return;
			state = { ...state, status: "active", completion: undefined };
			save(ctx, state);
		}
		if (state?.status === "reported-complete") {
			state = { ...state, status: "active" };
			save(ctx, state);
		}
		if (!state || state.status !== "active") return;
		const key = sessionId(ctx);
		releaseStop(key);
		const onAbort = () => {
			if (read(ctx)?.externalSourceId === state.externalSourceId) cancel(ctx, "session-stop-abort");
			releaseStop(key);
		};
		if (event.signal?.aborted) { onAbort(); return; }
		if (event.signal) {
			pendingStops.set(key, { signal: event.signal, onAbort });
			event.signal.addEventListener("abort", onAbort, { once: true });
		}
		const support = capability();
		if (!support.enforced) {
			if (state.enforcementUnavailable !== support.reason) {
				save(ctx, { ...state, enforcementUnavailable: support.reason });
				const warning = `Daily Driver stop enforcement unavailable: ${support.reason} Shared continuation instructions still apply; this is not a missing user approval.`;
				if (typeof ctx.ui?.notify === "function") ctx.ui.notify(warning, "warning");
				else console.error(`daily-driver: ${warning}`);
			}
			return;
		}
		let reason;
		try {
			validateBlocker(ctx, state, state.blocker);
			// An execution failure is not an external prerequisite. Correct it within the bound.
			if (state.blocker.kind !== "execution") return;
			reason = "Diagnose the observed execution failure and use any permitted alternative; do not rename it as missing approval";
		} catch (error) { reason = error.message; }
		// Agent labels, record rewrites, status calls and duplicate observations cannot reset this count.
		const failures = [...new Set([...(state.inheritedFailures ?? []), ...observations(ctx).filter((item) => item.taskSourceId === state.externalSourceId && item.isError)
			.map((item) => item.fingerprint ?? digest([item.toolName, item.input, item.text]))])].sort();
		const condition = digest([state.correctionIdentity ?? state.externalSourceId, failures]);
		const count = state.condition === condition ? state.corrections : 0;
		if (count >= 2) {
			const failure = `Execution failure: the same unsupported unfinished stop reached the two-correction limit. ${reason}. This is not completion or missing user approval. Evidence remains in daily_driver_task_state status.`;
			save(ctx, { ...state, condition, correctionFailures: failures, corrections: count, stopFailure: failure });
			if (typeof ctx.ui?.notify === "function") ctx.ui.notify(failure, "error");
			else console.error(`daily-driver: ${failure}`);
			return;
		}
		if (event.signal?.aborted || read(ctx)?.status !== "active") return;
		save(ctx, { ...state, condition, correctionFailures: failures, corrections: count + 1 });
		return { continue: true, additionalContext: `Daily Driver unfinished-task correction ${count + 1}/2: ${reason}. Inspect status and receipt for criterion-level feedback. Continue permitted independent work; do not repeat established failures, expand scope, or bypass safety restrictions. complete requires current evidence for every criterion. A blocker, cancellation or bounded execution failure is not verified completion.` };
	}

	function cancel(ctx, source = "external-interrupt") {
		if (!available(ctx)) return;
		const current = read(ctx);
		if (current?.status === "active") save(ctx, { ...current, status: "cancelled", cancellationSource: source });
	}

	return { input, toolResult, beforeAgentStart, context, compacting, execute, stop, cancel, adopt, delegateCall,
		agentEnd, shutdown, instructions };
}

/** installTaskState binds the shared controller to Omp lifecycle and tool APIs. */
export function installTaskState(pi) {
	const controller = createTaskStateController(pi);
	for (const [name, handler] of [
		["input", controller.input], ["tool_result", controller.toolResult],
		["tool_call", controller.delegateCall],
		["before_agent_start", controller.beforeAgentStart], ["context", controller.context],
		["session.compacting", controller.compacting], ["session_stop", controller.stop],
		["agent_end", controller.agentEnd], ["session_shutdown", controller.shutdown],
	]) pi.on(name, handler);
	pi.registerTool({
		name: "daily_driver_task_state", label: "Task evidence state",
		description: `Read and record versioned task contracts and private task evidence on the active main-session branch. The record parameter is a JSON-encoded object string; omit it for status. The tool records provenance and reported state, not permission, semantic approval, route exhaustion, or proof of completion. A contract (objective, scope, exclusions, constraints, stable criterion IDs, required evidence/review kinds, approval requirements and source references) is distinct from the mutable plan; unknown contract fields are null, not fulfilled.

For the write device, send {"path":"xd://daily_driver_task_state","content":"{\\"action\\":\\"status\\"}"}. For other actions, content encodes {"action": action, "record": JSON.stringify(record)}.

Start with status {}. Its sources and evidence contain recent retained entries and real sourceId values. To retrieve an entry, call status with record JSON.stringify({sourceId: entry.sourceId}); an unknown ID returns null. A reference is {sourceId, quote}, where quote is nonblank text copied exactly from that entry. Never invent an ID. Sources must remain on this session's active branch. User authorization must belong to the active task; tool evidence and route evidence must be associated with its externalSourceId. Status excerpts can be truncated: retrieve the entry before quoting. Tool output can itself be truncated; when textTruncated is true, quotes must fit entirely in the prefix before prefixLength or the suffix after its separator, never across the omitted gap. Omitted output cannot be recovered here.

Actions and records:
- status: optional {sourceId}; without it, returns state, source and evidence excerpts, authorization applicability and capability.
- begin: optional {taskId, operation, target, source, newTask}. source is a user reference and defaults to the latest external user source. It must be the latest external user input and not a cancellation. New-task defaults are taskId = sourceId, operation = source text, target = current working directory. The first labelled begin binds execution labels to the captured request and creates a contract revision; a later begin cannot rewrite bound labels or contracted scope, so use a contract amendment. newTask: true starts another task and requires fresh external user input. Cancelled or settled work needs resume or newTask; a cancellation is not a fresh request.
- resume: {source, contractId?}. source references fresh external user input that is not the task's original request or a cancellation. contractId selects an earlier contract; otherwise the current one resumes. Correction counts survive; the old blocker and completion clear.
- contract: {expectedRevision, change, sourceRefs, contract, authoritySource?, removedCriteria?, operation?, target?}. expectedRevision must equal the current revision. contract holds only the changed fields. sourceRefs is a nonempty reference array. A material scope or authorization change needs authoritySource: a later original user decision for this task. Removing a criterion needs removedCriteria: [{id, reason}].
- plan: {summary, ...details}. Records execution state without a contract revision.
- handoff: returns the contract, history, plan, unresolved criterion IDs, authority locators and correction identity/count. It grants no authority.
- receipt: renders objective, revision, artifact identities, criterion dispositions, evidence references, unknowns, recorded decisions, risks and outstanding approvals. It never publishes or completes a task.
- evidence: {id, taskId, criterionId, contractRevision, subject, source, kind, result, judgment?, requirement?, supersedes?}. source is a retained observation reference. subject must equal its execution.subject. kind is command, check, judgment, approval or report; result is passed, failed or unresolved. Declare criterion verification {kinds, toolName, input} through contract before execution. Commands/checks must match that operation and actual outcomes. A judgment/approval requires {reviewer, rationale, artifacts} under judgment. approval also names its requirement. report cannot pass a criterion. supersedes explicitly replaces evidence for the same criterion, kind and subject.
- authorization: {id, kind, operation, target, limits, conditions, source}, all required; strings except source must be nonblank. kind is ${oneOf(AUTHORIZATION_KINDS)} and must match the original user or workflow source. User sources must be associated with the active task. Optional expiresAt is a parseable date; freshConfirmation marks confirmation required; revokes and supersedes name existing authorization IDs. IDs are immutable: use a new ID for amendments. Applicability reports scope, expiry, revocation and confirmation; review the original conditions.
- blocker: {kind, operation, target, evidence, authorizationIds, routes, independentWork, externalContribution, resume}. operation and target exactly match active state. kind is ${oneOf(BLOCKER_KINDS)}. evidence is a nonempty reference array: external and execution require tool evidence; execution requires an error; safety and authorization require user or workflow authority. authorizationIds lists every retained authorization ID, including amendments, or [] if none. routes is a nonempty array of {route, disposition, evidence}; route is nonblank, disposition is ${oneOf(ROUTE_DISPOSITIONS)}, and evidence is a reference. Failed needs an observed error; prohibited needs original authority, not a tool probe. independentWork is {pending: [], completed: []}; pending must be empty except for safety. externalContribution and resume are nonblank strings. Validation checks references, not whether routes are truly exhausted.
- complete: {summary}. Requires a receipt with every criterion passed, declared evidence/review kinds and approvals satisfied, and no unknown requirements. Records verified-complete, not arbitrary semantic correctness. Missing, failed, stale and truncated evidence rejects completion and leaves the task active. Existing reported-complete history is never upgraded.

Example sequence in an isolated fixture: let s = status(); let u = s.sources.find(x => x.kind === "user"); retrieve u with status({sourceId:u.sourceId}); let ref = {sourceId:u.sourceId, quote: an exact nonblank substring of u.text}. Call begin({taskId:"fixture", operation:"verify", target:"fixture", source:ref}); then authorization({id:"fixture-approval", kind:"user", operation:"verify", target:"fixture", limits:"offline", conditions:"fixture only", source:ref}) only if the original source actually supports it. After an observed fixture error, retrieve its real entry e through status and use r = {sourceId:e.sourceId, quote: an exact retained error substring}; blocker({kind:"execution", operation:"verify", target:"fixture", evidence:[r], authorizationIds:["fixture-approval"], routes:[{route:"fixture", disposition:"failed", evidence:r}], independentWork:{pending:[], completed:[]}, externalContribution:"Provide fixture access.", resume:"Retry the fixture."}). Finally complete({summary:"Fixture work completed."}) only when work is complete. Serialize each object into record; the example identifiers label records, not source authority.`,
		parameters: pi.zod.object({ action: pi.zod.string(), record: pi.zod.string().optional() }),
		execute: controller.execute,
	});
}
