import { createHash, randomUUID } from "node:crypto";

const STATE = "daily-driver.task-state";
const SOURCE = "daily-driver.task-source";
const OBSERVATION = "daily-driver.task-observation";
const RULE = "Continue authorized unfinished work. Diagnose ordinary failures and use permitted alternatives. Before asking for approval, inspect applicable original sources and their limits. A record does not grant permission or override harness or safety restrictions. Stop only for reported completion, cancellation, an evidenced external prerequisite after independent work, or the bounded execution failure.";
const REQUEST = /^(?:\s*(?:please\s+)?(?:implement|fix|update|add|remove|refactor|complete|resolve|undertake|build|create|change|investigate|debug|repair|migrate|address|test|verify)\b|\s*\/(?:skill:)?undertake\b|\s*(?:can|could|would) you\s+(?:please\s+)?(?:implement|fix|update|add|remove|refactor|complete|resolve|build|create|change|investigate|debug|repair|migrate|address|test|verify)\b)/iu;
const CANCEL = /^\s*(?:please\s+)?(?:\/(?:skill:)?stand-down\b|stand[ -]down\b|wrap\s+up\b|cancel\b|stop(?:\s+(?:work|working|this|the|now|here)|[.!\s]*$))/iu;

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

/**
 * createTaskStateController shares task policy across trusted lifecycle transports.
 * The transport must append branch entries synchronously and supply authentic
 * external input and tool-result events. Agent commands may call execute only.
 */
export function createTaskStateController(pi) {
	let pendingStop;

	function releaseStop() {
		if (!pendingStop) return;
		pendingStop.signal.removeEventListener("abort", pendingStop.onAbort);
		pendingStop = undefined;
	}

	function agentEnd(event, ctx) {
		if (ctx?.agent?.kind !== "sub" && !event.willContinue) releaseStop();
	}
	const available = (ctx) => ctx?.agent?.kind === "main" &&
		typeof ctx.sessionManager?.getBranch === "function" &&
		typeof ctx.sessionManager?.getSessionId === "function";
	const branch = (ctx) => available(ctx) ? ctx.sessionManager.getBranch() : [];
	const sessionId = (ctx) => ctx.sessionManager.getSessionId();
	const entries = (ctx, type) => branch(ctx).filter((entry) => entry.type === "custom" &&
		entry.customType === type && entry.data?.sessionId === sessionId(ctx));
	const read = (ctx) => entries(ctx, STATE).at(-1)?.data?.state ?? null;
	const save = (ctx, state) => pi.appendEntry(STATE, { sessionId: sessionId(ctx), state });
	const sources = (ctx) => entries(ctx, SOURCE).map((entry) => entry.data.source);
	const observations = (ctx) => entries(ctx, OBSERVATION).map((entry) => entry.data.observation);

	function reference(ctx, ref, authority = false) {
		if (!ref || typeof ref.sourceId !== "string") throw new Error("A real sourceId and exact quote are required");
		const source = sources(ctx).find((item) => item.sourceId === ref.sourceId) ??
			(!authority && observations(ctx).find((item) => item.sourceId === ref.sourceId));
		if (!source || !required(ref.quote, "source quote").trim() || !source.text.includes(ref.quote)) {
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
			? [...sources(ctx), ...observations(ctx)].find((item) => item.sourceId === request.sourceId) : undefined;
		return {
			state,
			authorizations: state?.authorizations.map((item) => ({ ...item, applicability: authorizationStatus(ctx, state, item) })) ?? [],
			sources: sources(ctx).slice(-8).map(excerpt),
			evidence: observations(ctx).filter((item) => item.taskSourceId === state?.externalSourceId).slice(-8).map(excerpt),
			...(request.sourceId ? { source: source ?? null } : {}),
			limits: "References prove provenance, not semantic approval or route exhaustion. Prose limits and conditions require review against the original source. Completion is agent-reported, not independently proven. Handoffs must carry original source, task, operation, target and conditions; copied agent text cannot create authority in another session.",
		};
	}

	function begin(ctx, record, source) {
		const current = read(ctx);
		if (current?.status === "cancelled" && current.externalSourceId === source.sourceId) {
			throw new Error("Cancelled work requires fresh external user input");
		}
		if (current?.externalSourceId === source.sourceId) {
			if (current.status !== "active") throw new Error("A settled task requires fresh external user input");
			// Refining labels does not renew the correction allowance or discard evidence.
			save(ctx, { ...current, taskId: record.taskId ?? current.taskId,
				operation: record.operation ?? current.operation, target: record.target ?? current.target });
			return;
		}
		save(ctx, {
			taskId: record.taskId ?? source.sourceId, operation: record.operation ?? source.text,
			target: record.target ?? ctx.cwd, externalSourceId: source.sourceId,
			status: "active", authorizations: [], blocker: null, corrections: 0, condition: null,
		});
	}

	function input(event, ctx) {
		if (!available(ctx) || !["interactive", "rpc"].includes(event.source)) return;
		const sourceId = `user:${randomUUID()}`;
		const source = { sourceId, kind: "user", text: event.text,
			taskSourceId: REQUEST.test(event.text) ? sourceId : read(ctx)?.externalSourceId ?? sourceId };
		pi.appendEntry(SOURCE, { sessionId: sessionId(ctx), source });
		const current = read(ctx);
		if (CANCEL.test(event.text)) {
			if (current) save(ctx, { ...current, status: "cancelled", cancellationSource: source.sourceId });
			return;
		}
		if (REQUEST.test(event.text)) begin(ctx, {}, source);
	}

	function toolResult(event, ctx) {
		if (!available(ctx) || !read(ctx) ||
			["daily_driver_task_state", "daily_driver_get_session", "daily_driver_set_session_title"].includes(event.toolName) ||
			event.input?.path === "xd://daily_driver_task_state") return;
		const observation = {
			sourceId: `tool:${event.toolCallId}`, kind: "tool", toolName: event.toolName,
			input: event.input, text: text(event.content), isError: Boolean(event.isError),
			taskSourceId: read(ctx).externalSourceId,
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
		} : null;
		return `${RULE}\nUse daily_driver_task_state(action: status) before an unfinished stop or another approval request. For explicit repository work not already active, call begin with {taskId,operation,target,source:{sourceId,quote}} as a JSON record. Do not activate ordinary Q&A. Authorization records keep user approval separate from workflow; exact source anchoring does not verify arbitrary prose meaning. Keep revocations, expiry and fresh-confirmation conditions. Record a structured blocker before an external pause; complete only when reporting completion. Cancelled state must not restart without fresh external user input. Status returns bounded source/evidence excerpts; status with record {sourceId} returns one full original source for exact anchoring.\nCurrent private task handoff (never publish conversation sources):\n${JSON.stringify(handoff)}`;
	}

	function beforeAgentStart(event, ctx) {
		if (!available(ctx)) return;
		const systemPrompt = event.systemPrompt ?? [];
		const policy = systemPrompt.join("\n\n");
		const source = { sourceId: `system:${digest(policy)}`, kind: "workflow", text: policy };
		if (policy && !sources(ctx).some((item) => item.sourceId === source.sourceId)) {
			pi.appendEntry(SOURCE, { sessionId: sessionId(ctx), source });
		}
		return { systemPrompt: [...systemPrompt, instructions(ctx)] };
	}
	function context(event, ctx) {
		if (!available(ctx)) return;
		return { messages: [...event.messages, {
			role: "custom", customType: STATE, content: instructions(ctx), display: false, timestamp: Date.now(),
		}] };
	}
	const compacting = (_event, ctx) => available(ctx) ? { context: [instructions(ctx)] } : undefined;

	async function execute(_id, params, _signal, _update, ctx) {
			try {
				if (!available(ctx)) throw new Error("Durable task state requires the main Omp session branch API");
				const record = params.record ? JSON.parse(params.record) : {};
				if (!record || typeof record !== "object" || Array.isArray(record)) throw new Error("record must be a JSON object");
				const state = read(ctx);
				if (params.action === "begin") {
					const source = record.source ? reference(ctx, record.source, true) : sources(ctx).filter((item) => item.kind === "user").at(-1);
					if (!source || source.kind !== "user") throw new Error("Task initiation requires an external user source");
					if (source.sourceId !== sources(ctx).filter((item) => item.kind === "user").at(-1)?.sourceId) throw new Error("Task initiation requires the latest external user source");
					if (CANCEL.test(source.text)) throw new Error("Cancellation is not a fresh work request");
					begin(ctx, record, source);
				} else if (params.action !== "status") {
					if (!state || state.status !== "active") throw new Error("No active unfinished task");
					if (params.action === "authorization") {
						const source = reference(ctx, record.source, true);
						if (source.kind === "user" && source.sourceId !== state.externalSourceId &&
							source.taskSourceId !== state.externalSourceId) throw new Error("Authorization source belongs to another task");
						if (!["user", "workflow"].includes(record.kind) || record.kind !== source.kind) throw new Error("Authorization kind must match the original user or system source");
						for (const key of ["id", "operation", "target", "limits", "conditions"]) required(record[key], key);
						if (state.authorizations.some((item) => item.id === record.id)) throw new Error("Authorization ids are immutable; use a new superseding or revoking record");
						if (record.expiresAt && !Number.isFinite(Date.parse(record.expiresAt))) throw new Error("expiresAt must be an ISO date");
						for (const key of ["revokes", "supersedes"]) if (record[key] && !state.authorizations.some((item) => item.id === record[key])) throw new Error(`${key} must reference an existing task authorization`);
						save(ctx, { ...state, authorizations: [...state.authorizations, { ...record, taskId: state.taskId }] });
					} else if (params.action === "blocker") {
						// Validate now and again at stop time, when expiry and branch evidence may differ.
						validateBlocker(ctx, state, record);
						save(ctx, { ...state, blocker: record });
					} else if (params.action === "complete") {
						required(record.summary, "completion summary");
						save(ctx, { ...state, status: "reported-complete", completion: record.summary });
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
		if (!["external", "authorization", "safety", "execution"].includes(blocker.kind)) throw new Error("Name the blocker kind");
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
			if (!["failed", "prohibited", "unavailable"].includes(route.disposition)) throw new Error("A route remains actionable");
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
		const state = read(ctx);
		if (!state || state.status !== "active") return;
		releaseStop();
		const onAbort = () => {
			if (read(ctx)?.externalSourceId === state.externalSourceId) cancel(ctx, "session-stop-abort");
			releaseStop();
		};
		if (event.signal?.aborted) { onAbort(); return; }
		if (event.signal) {
			pendingStop = { signal: event.signal, onAbort };
			event.signal.addEventListener("abort", onAbort, { once: true });
		}
		let reason;
		try {
			validateBlocker(ctx, state, state.blocker);
			// An execution failure is not an external prerequisite. Correct it within the bound.
			if (state.blocker.kind !== "execution") return;
			reason = "Diagnose the observed execution failure and use any permitted alternative; do not rename it as missing approval";
		} catch (error) { reason = error.message; }
		// Agent labels, record rewrites, status calls and duplicate observations cannot reset this count.
		const failures = [...new Set(observations(ctx).filter((item) => item.taskSourceId === state.externalSourceId && item.isError)
			.map((item) => digest([item.toolName, item.input, item.text])))].sort();
		const condition = digest([state.externalSourceId, failures]);
		const count = state.condition === condition ? state.corrections : 0;
		if (count >= 2) {
			save(ctx, { ...state, condition, corrections: count, stopFailure: reason });
			pi.sendMessage({ customType: "daily-driver.task-stop-failure", content: `Execution failure: the same unsupported unfinished stop reached the two-correction limit. ${reason}. This is not completion or missing user approval. Evidence remains in daily_driver_task_state status.`, display: true }, { triggerTurn: false });
			return;
		}
		if (event.signal?.aborted || read(ctx)?.status !== "active") return;
		save(ctx, { ...state, condition, corrections: count + 1 });
		return { continue: true, additionalContext: `Daily Driver unfinished-task correction ${count + 1}/2: ${reason}. Inspect daily_driver_task_state status and its original sources. Continue permitted independent work; do not repeat established failures, expand scope, or bypass safety restrictions. If finished, use complete with a summary. Semantic claims in records still require review.` };
	}

	function cancel(ctx, source = "external-interrupt") {
		if (!available(ctx)) return;
		const current = read(ctx);
		if (current?.status === "active") save(ctx, { ...current, status: "cancelled", cancellationSource: source });
	}

	return { input, toolResult, beforeAgentStart, context, compacting, execute, stop, cancel, status,
		agentEnd, shutdown: releaseStop };
}

/** installTaskState binds the shared controller to Omp lifecycle and tool APIs. */
export function installTaskState(pi) {
	const controller = createTaskStateController(pi);
	for (const [name, handler] of [
		["input", controller.input], ["tool_result", controller.toolResult],
		["before_agent_start", controller.beforeAgentStart], ["context", controller.context],
		["session.compacting", controller.compacting], ["session_stop", controller.stop],
		["agent_end", controller.agentEnd], ["session_shutdown", controller.shutdown],
	]) pi.on(name, handler);
	pi.registerTool({
		name: "daily_driver_task_state", label: "Task evidence state",
		description: "Read durable task scope, original authorization sources and observed evidence. Actions: begin, status, authorization, blocker, complete. Mutations use a JSON-string record. This records provenance and reported state; it never grants permission or verifies arbitrary prose approval semantics.",
		parameters: pi.zod.object({ action: pi.zod.string(), record: pi.zod.string().optional() }),
		execute: controller.execute,
	});
}
