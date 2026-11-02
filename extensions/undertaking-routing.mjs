import { createHash } from "node:crypto";
import { MODEL_CLASS_ROUTES, explicitModelClassRole } from "./role-default-helper.mjs";

const ENTRY = "daily-driver-undertaking-route";
const CLASSES = ["mechanical", "implementation", "reasoning", "frontier"];
const EFFORT = /:(off|minimal|low|medium|high|xhigh|max|auto|inherit)$/u;
const GUARDED_APIS = ["openai-completions", "openai-responses", "openai-codex-responses", "anthropic-messages", "google-generative-ai", "google-gemini-cli", "google-vertex"];
const SPECIALISTS = new Set(["reviewer", "scout", "security-reviewer", "seance"]);
// Agent names are process-local, not globally unique. A shared auth store and
// an unambiguous live parent session are both required for inheritance.
const roots = new WeakMap();
const pendingChildren = new Map();

function selector(model) {
	return model && typeof model.provider === "string" && typeof model.id === "string"
		? `${model.provider}/${model.id}` : null;
}

function frontier(model) {
	return /(?:^|[-/])(?:astra|fable)(?:[-/]|$)/iu.test(selector(model) ?? "");
}

function origin(model) {
	if (!selector(model) || !model.api || !model.baseUrl) throw new Error("Model backend identity is unavailable");
	return {
		provider: model.provider, model: model.id, api: model.api, baseUrl: model.baseUrl,
		headersDigest: createHash("sha256").update(JSON.stringify(Object.entries(model.headers ?? {}).sort())).digest("hex"),
	};
}

function source(ctx, provider) {
	const value = ctx.modelRegistry?.authStorage?.keys?.source(provider, { env: "aliases" });
	if (!value?.kind || (value.kind === "env" && !value.envVar)) throw new Error("Authentication route is unavailable");
	return value.kind === "env" ? `env:${value.envVar}` : value.kind;
}

function pool(ctx, provider) {
	const auth = ctx.modelRegistry.authStorage;
	if (typeof auth.sessions?.permits !== "function" || typeof auth.sessions?.isRestricted !== "function") {
		throw new Error("Session OAuth restriction controls are unavailable");
	}
	return auth.credentials.snapshot().credentials
		.filter(row => row.provider === provider && row.credential.type === "oauth" && row.identityKey &&
			auth.sessions.permits(provider, ctx.sessionManager.getSessionId(), row.id))
		.map(row => row.identityKey);
}

function scope(ctx) {
	const auth = ctx.modelRegistry?.authStorage;
	if (!auth || typeof auth !== "object") return null;
	let sessions = roots.get(auth);
	if (!sessions) { sessions = new Map(); roots.set(auth, sessions); }
	return sessions;
}

function routeError(state, message) {
	state.status = "blocked";
	state.reason = message;
	return new Error(`Undertaking route gap: ${message}`);
}

function checkModel(ctx, state, model, routingOnly = false) {
	const candidate = origin(model);
	const original = state.origin;
	if (candidate.provider !== original.provider) throw new Error("Provider must remain unchanged");
	if (candidate.api !== original.api || candidate.baseUrl !== original.baseUrl || candidate.headersDigest !== original.headersDigest) {
		throw new Error("Model backend must remain unchanged");
	}
	const family = ctx.models.family(model);
	const reference = ctx.models.resolve(`${original.provider}/${original.model}`);
	if (!family || !reference || family !== ctx.models.family(reference)) throw new Error("Model family must remain unchanged");
	if (!GUARDED_APIS.includes(model.api)) throw new Error("Transport has no verified undertaking request guard");
	if (!routingOnly && frontier(model) && !state.frontierApproval) throw new Error("Frontier execution requires recorded approval and its bounded envelope");
	if (!routingOnly && frontier(model) && state.modelClass !== "frontier") throw new Error("Ordinary work cannot use a frontier fallback");
}

function classSelection(ctx, settings, routes, model, modelClass) {
	const family = ctx.models.family(model);
	if (!family) throw new Error("Invoking model family is unavailable");
	const sameFamily = reference => {
		const resolved = ctx.models.resolve(reference);
		return resolved && ctx.models.family(resolved) === family;
	};
	const familyRows = routes.filter(row => sameFamily(row.referenceModel));
	// Explicit roles can qualify an operator's family without changing plugin defaults.
	const operatorFamily = CLASSES.some(name => {
		const role = explicitModelClassRole(settings, name);
		return role.assigned && typeof role.value === "string" && sameFamily(role.value);
	});
	if (!familyRows.length && !operatorFamily) return { target: model, capability: "unverified" };
	const role = explicitModelClassRole(settings, modelClass);
	const providerRows = familyRows.filter(row => ctx.models.resolve(row.referenceModel)?.provider === model.provider);
	if (providerRows.length > 1) throw new Error("Model class routes are ambiguous for the invoking family and provider");
	const configured = role.assigned ? role.value : providerRows[0]?.classes[modelClass];
	if (typeof configured !== "string" || !configured.trim()) throw new Error("Required class has no configured model route on the invoking family and provider");
	const target = ctx.models.resolve(configured);
	if (!target || !ctx.models.list().some(available => selector(available) === selector(target))) {
		throw new Error("Configured class model is unavailable");
	}
	return { target, configured, capability: "mapped" };
}

function installPool(ctx, state) {
	const auth = ctx.modelRegistry.authStorage;
	if (state.authenticationRoute !== "oauth") return;
	const eligible = pool(ctx, state.origin.provider);
	const allowed = state.identities ? eligible.filter(key => state.identities.includes(key)) : eligible;
	if (!allowed.length) throw new Error("No eligible OAuth account remains on the original route");
	if (auth.sessions.isRestricted(state.origin.provider, state.sessionId)) {
		// Replacing someone else's lease would erase its ownership and could
		// widen it when our session ends. Retain it only when already adequate.
		if (eligible.some(key => !allowed.includes(key))) throw new Error("Existing OAuth pool is incompatible with the inherited route");
	} else {
		state.lease = auth.sessions.restrict(state.origin.provider, state.sessionId, allowed);
	}
	state.identities = allowed;
}

function publicState(state) {
	if (!state) return null;
	return {
		issue: state.issue, modelClass: state.modelClass, selectedModel: state.selectedModel,
		observedModel: state.observedModel ?? null, status: state.status,
		...(state.reason ? { reason: state.reason } : {}),
		capability: state.capability ?? "mapped",
		...(state.warning ? { warning: state.warning } : {}),
	};
}

function storedState(ctx) {
	const entries = ctx.sessionManager.getBranch?.() ?? [];
	const saved = entries.filter(entry => entry.type === "custom" && entry.customType === ENTRY).at(-1)?.data;
	if (!saved) return null;
	if (saved.completed === true && saved.schema === 1) return null;
	if (saved.schema !== 1 || !CLASSES.includes(saved.modelClass) || !Number.isSafeInteger(saved.issue) ||
		!saved.origin?.provider || !saved.selectedModel || !saved.authenticationRoute) {
		throw new Error("Saved undertaking route is invalid; recover the original execution identity before work");
	}
	return saved;
}

/** Install undertaking selection and enforce its worker route without changing host helper roles. */
export function installUndertakingRouting(pi, getSettings, getRoutes = () => MODEL_CLASS_ROUTES) {
	const states = new Map();
	const selecting = new Set();
	const failures = new Map();

	function status(ctx, text) { ctx.ui?.setStatus?.("daily-driver-routing", text); }

	pi.on("before_agent_start", (event, ctx) => {
		if (!current(ctx) && !/(?:^|\n)(?:\/skill:|\/)?undertake\b/iu.test(event.prompt ?? "")) return;
		return {
			systemPrompt: [...event.systemPrompt, "Undertaking routing: call daily_driver_route_undertaking alone, with no other tool calls in that assistant response (including device calls). If pending, report normal verification status, then let the selected worker respond before task work. A pending switch is not an error. Never batch routing with worktree creation, claims, or implementation."],
		};
	});

	function current(ctx) { return states.get(ctx.sessionManager?.getSessionId?.()); }

	function publish(ctx, state) {
		state.workerModels ??= ctx.models;
		const previous = states.get(state.sessionId);
		for (const handoff of pendingChildren.values()) {
			if (handoff.state === previous) handoff.state = state;
		}
		states.set(state.sessionId, state);
		const sessions = scope(ctx);
		if (sessions) sessions.set(state.sessionId, { agentId: ctx.agent?.id, state });
	}

	function describe(ctx) {
		let authenticationRoute = null;
		try { authenticationRoute = source(ctx, ctx.models?.current?.()?.provider ?? ctx.model?.provider); } catch { /* Unknown identity is reported, not invented. */ }
		return {
			provider: ctx.models?.current?.()?.provider ?? ctx.model?.provider ?? null,
			authenticationRoute,
			undertaking: publicState(current(ctx)),
		};
	}

	async function save(state) {
		await pi.appendEntry(ENTRY, {
			schema: 1, issue: state.issue, modelClass: state.modelClass, selectedModel: state.selectedModel,
			origin: state.origin, authenticationRoute: state.authenticationRoute,
			selectedEffort: state.selectedEffort,
			capability: state.capability ?? "mapped",
			...(state.warning ? { warning: state.warning } : {}),
			...(state.recovery ? { recovery: true } : {}),
			...(state.identities ? { identities: state.identities } : {}),
			...(state.frontierApproval ? { frontierApproval: state.frontierApproval } : {}),
		});
	}

	async function start(_event, ctx) {
		const sessionId = ctx.sessionManager?.getSessionId?.();
		if (!sessionId || states.has(sessionId)) return;
		let state;
		try {
			const sessions = scope(ctx);
			const expected = ctx.agent?.kind === "sub" ? pendingChildren.get(ctx.agent.id) : undefined;
			const parents = ctx.agent?.kind === "sub" && ctx.agent.parentId
				? [...(sessions?.values() ?? [])].filter(record => record.agentId === ctx.agent.parentId) : [];
			if (parents.length > 1) throw new Error("Parent undertaking identity is ambiguous");
			const saved = storedState(ctx);
			if (expected && (expected.auth !== ctx.modelRegistry.authStorage || expected.parentId !== ctx.agent.parentId)) {
				throw new Error("Child cannot inherit an undertaking from another root or authentication scope");
			}
			if (!expected && parents.length && !saved) throw new Error("Child undertaking handoff identity is missing");
			if (expected?.specialist) {
				if (expected.state.status !== "verified") throw new Error("Parent undertaking route is not verified");
				pendingChildren.delete(ctx.agent.id);
				return;
			}
			const parent = expected?.state;
			if (!parent && !saved) return;
			if (expected) pendingChildren.delete(ctx.agent.id);
			state = {
				...(parent ?? saved), sessionId, lease: undefined, status: "pending", observedModel: null,
				workerModels: ctx.models,
				selectedModel: parent ? selector(ctx.models.current()) : saved.selectedModel,
				selectedEffort: parent ? pi.getThinkingLevel() : saved.selectedEffort,
				identities: (parent ?? saved).identities ? [...(parent ?? saved).identities] : undefined,
			};
			publish(ctx, state);
			if (parent?.status !== undefined && parent.status !== "verified") throw new Error("Parent undertaking route is not verified");
			checkModel(ctx, state, ctx.models.current());
			if (parent?.capability === "unverified" && selector(ctx.models.current()) !== parent.selectedModel) {
				throw new Error("An unmapped-family worker must retain the invoking model");
			}
			if (source(ctx, state.origin.provider) !== state.authenticationRoute) throw new Error("Authentication route changed before session recovery");
			installPool(ctx, state);
			if (parent) await save(state);
		} catch (error) {
			state ??= { sessionId, status: "blocked", issue: null, modelClass: null, selectedModel: null };
			publish(ctx, state);
			routeError(state, error.message);
			ctx.abort();
		}
	}

	pi.on("session_start", start);
	pi.on("session_switch", start);
	pi.on("session_branch", start);
	pi.on("session_tree", start);

	pi.registerTool({
		name: "daily_driver_route_undertaking",
		label: "Select undertaking model class",
		description: "Route the issue on its invoking family and provider. Call this tool ALONE in an assistant response, never batched with other tools. Pending identity verification is normal progress; the next worker response must verify before task work. An unmapped family warns and retains the invoking model.",
		parameters: pi.zod.object({
			issue: pi.zod.number().int().min(1),
			modelClass: pi.zod.string(),
			frontierApproval: pi.zod.string().optional(),
		}),
		execute: async (_id, params, _signal, _update, ctx) => {
			const previous = current(ctx);
			const sessionId = ctx.sessionManager.getSessionId();
			if (previous && previous.issue !== params.issue) {
				selecting.delete(sessionId);
				return {
					isError: true,
					content: [{ type: "text", text: "Another undertaking owns this session; finish or resume it before selecting a different issue." }],
					details: describe(ctx),
				};
			}
			const invoking = ctx.models.current();
			const invokingEffort = pi.getThinkingLevel();
			let state;
			let switching = false;
			selecting.add(sessionId);
			try {
				if (!Number.isSafeInteger(params.issue) || params.issue < 1 || !CLASSES.includes(params.modelClass)) {
					throw new Error("A valid issue and required model class are mandatory");
				}
				// A retained unmapped route is a decision, not a fresh global-role lookup.
				const selection = previous?.capability === "unverified" && previous.modelClass === params.modelClass
					? { target: ctx.models.resolve(previous.selectedModel), capability: "unverified" }
					: classSelection(ctx, await getSettings(ctx), await getRoutes(ctx), invoking, params.modelClass);
				const { target, configured, capability } = selection;
				if (!target) throw new Error("Invoking model is unavailable");
				state = {
					...previous,
					issue: params.issue, modelClass: params.modelClass, sessionId,
					origin: previous?.origin ?? origin(invoking),
					authenticationRoute: previous?.authenticationRoute ?? source(ctx, invoking.provider),
					workerModels: ctx.models, capability, recovery: undefined,
					frontierApproval: params.frontierApproval?.trim() || previous?.frontierApproval,
				};
				checkModel(ctx, state, invoking, true);
				checkModel(ctx, state, target);
				if (params.modelClass === "frontier" && !state.frontierApproval) throw new Error("Frontier execution requires recorded approval and its bounded envelope");
				if (source(ctx, state.origin.provider) !== state.authenticationRoute) throw new Error("Authentication route must remain unchanged");
				if (!(await ctx.modelRegistry.getApiKey(invoking, sessionId))) throw new Error("Current route has no available credentials");
				const effort = configured?.match(EFFORT)?.[1];
				const nextEffort = effort && effort !== "inherit" ? effort : invokingEffort;
				const changed = selector(invoking) !== selector(target) || nextEffort !== invokingEffort;
				if (changed && typeof pi.setModel !== "function") throw new Error("Model selection control is unavailable");
				if (nextEffort !== invokingEffort && typeof pi.setThinkingLevel !== "function") throw new Error("Effort selection control is unavailable");
				if (!state.lease) installPool(ctx, state);
				state.selectedModel = selector(target);
				state.selectedEffort = nextEffort;
				state.observedModel = changed ? null : selector(invoking);
				state.status = changed ? "pending" : "verified";
				state.reason = undefined;
				state.warning = capability === "unverified"
					? previous?.warning ?? `WARNING: Family ${ctx.models.family(invoking)} has no model-class mapping. Suitability for ${params.modelClass} is unverified. Continuing with the invoking model: ${selector(invoking)}.`
					: undefined;
				await save(state);
				publish(ctx, state);
				switching = changed;
				if (selector(invoking) !== selector(target) && !(await pi.setModel(target))) throw new Error("Harness rejected the session model switch");
				if (nextEffort !== invokingEffort) await pi.setThinkingLevel(nextEffort);
				failures.delete(sessionId);
				selecting.delete(sessionId);
				if (state.warning && !previous?.warning) ctx.ui?.notify?.(state.warning, "warning");
				status(ctx, state.status === "pending" ? `Waiting for ${state.selectedModel} identity verification` : undefined);
				return {
					content: [{ type: "text", text: state.warning ?? (changed
						? "Model selected. Waiting for the selected worker's next response to verify execution before task work."
						: "Undertaking execution identity is verified.") }],
					details: describe(ctx),
				};
			} catch (error) {
				// A failed selection blocks task admission, not the conversation needed to repair it.
				failures.set(sessionId, error.message);
				selecting.delete(sessionId);
				status(ctx, undefined);
				let restored = !switching;
				if (switching) {
					try {
						if (selector(ctx.models.current()) !== selector(invoking) && !(await pi.setModel(invoking))) throw new Error("Model restoration rejected");
						if (pi.getThinkingLevel() !== invokingEffort) await pi.setThinkingLevel(invokingEffort);
						restored = true;
					} catch { /* Retain the actual route for recovery, never certify implementation. */ }
				}
				if (restored) {
					if (state?.lease && state.lease !== previous?.lease) ctx.modelRegistry.authStorage.sessions.unrestrict(state.origin.provider, sessionId, state.lease);
					if (previous) publish(ctx, previous);
					else { states.delete(sessionId); scope(ctx)?.delete(sessionId); }
					if (state?.selectedModel) {
						if (previous) await save(previous);
						else await pi.appendEntry(ENTRY, { schema: 1, issue: params.issue, completed: true });
					}
				} else {
					state.status = "blocked";
					state.reason = error.message;
					state.recovery = true;
					publish(ctx, state);
					await save(state);
				}
				return { isError: true, content: [{ type: "text", text: `Undertaking route gap: ${error.message}` }], details: describe(ctx) };
			}
		},
	});

	pi.registerTool({
		name: "daily_driver_finish_undertaking",
		label: "Finish undertaking model route",
		description: "Release this completed undertaking's owned route restriction before reusing the session. Does not change the selected model or shared roles.",
		parameters: pi.zod.object({ issue: pi.zod.number().int().min(1) }),
		execute: async (_id, params, _signal, _update, ctx) => {
			const state = current(ctx);
			if (!state || state.issue !== params.issue) return {
				isError: true, content: [{ type: "text", text: "No matching undertaking owns this session." }], details: describe(ctx),
			};
			await pi.appendEntry(ENTRY, { schema: 1, issue: state.issue, completed: true });
			release(ctx, state);
			return { content: [{ type: "text", text: "Undertaking route finished." }], details: describe(ctx) };
		},
	});

	pi.on("before_provider_request", (_event, ctx) => {
		const state = current(ctx);
		if (!state) return;
		// Side requests on independently selected helper models are not undertaking workers.
		// Keep the live query captured outside this request: request contexts bind
		// both model accessors to the request model, including helper requests.
		if (selector(ctx.model) !== selector(state.workerModels.current())) return;
		try {
			if (state.recovery) {
				checkModel(ctx, state, ctx.model, true);
			} else {
				if (state.status === "blocked") throw new Error(state.reason);
				checkModel(ctx, state, ctx.model);
				if (selector(ctx.model) !== state.selectedModel) throw new Error("Execution fallback does not match the selected worker class route");
				if (state.selectedEffort !== undefined && pi.getThinkingLevel() !== state.selectedEffort) throw new Error("Worker effort no longer matches its selected class route");
			}
			if (source(ctx, state.origin.provider) !== state.authenticationRoute) throw new Error("Worker authentication route changed");
		} catch (error) {
			routeError(state, error.message);
			ctx.abort();
			throw error;
		}
	});

	pi.on("assistant_message", (event, ctx) => {
		const sessionId = ctx.sessionManager?.getSessionId?.();
		if (!sessionId) return;
		const message = event.message;
		// Tool admission may run for the whole batch before any tool executes.
		// Reserve selection before admitting even a preceding sibling mutation.
		const requestsSelection = message?.content?.some(part => part.type === "toolCall" &&
			(part.name === "daily_driver_route_undertaking" ||
				(part.name === "write" && part.arguments?.path === "xd://daily_driver_route_undertaking")));
		if (requestsSelection) selecting.add(sessionId);
		const state = current(ctx);
		if (state?.status === "verified" && !requestsSelection &&
			`${message?.provider}/${message?.model}` === state.selectedModel) selecting.delete(sessionId);
		if (!state || state.status !== "pending") return;
		if (message?.role === "assistant" && `${message.provider}/${message.model}` === state.selectedModel &&
			selector(ctx.models.current()) === state.selectedModel) {
			state.status = "verified";
			state.observedModel = state.selectedModel;
			if (!requestsSelection) selecting.delete(sessionId);
			status(ctx, undefined);
		}
	});

	pi.on("tool_call", (event, ctx) => {
		const state = current(ctx);
		const failure = failures.get(ctx.sessionManager?.getSessionId?.());
		if (!failure && (!state || state.status === "verified") && !selecting.has(ctx.sessionManager?.getSessionId?.())) return;
		if (["read", "grep", "glob", "daily_driver_get_session", "daily_driver_route_undertaking", "daily_driver_finish_undertaking"].includes(event.toolName)) return;
		if (event.toolName === "write" && ["xd://daily_driver_get_session", "xd://daily_driver_route_undertaking", "xd://daily_driver_finish_undertaking"].includes(event.input?.path)) return;
		return { block: true, reason: failure ?? state?.reason ?? "Task work requires the selected worker's verified identity. Call routing alone and wait for its next response." };
	});

	pi.on("before_subagent_spawn", (event, ctx) => {
		const state = current(ctx);
		if (!state) return;
		try {
			if (state.status !== "verified") throw new Error("Parent undertaking route is not verified");
			if (!event.patterns?.length) throw new Error("Child effective model route is unavailable");
			const specialist = SPECIALISTS.has(event.agent);
			if (!specialist) for (const pattern of event.patterns) {
				if (typeof pattern !== "string" || /[*?,]/u.test(pattern)) throw new Error("Child route must use concrete, verifiable candidates");
				const model = ctx.models.resolve(pattern);
				if (!model) throw new Error("Child model route cannot be resolved");
				checkModel(ctx, state, model);
				if (state.capability === "unverified" && selector(model) !== state.selectedModel) throw new Error("An unmapped-family worker must retain the invoking model");
			}
			const parents = [...(scope(ctx)?.values() ?? [])].filter(record => record.agentId === ctx.agent?.id);
			if (parents.length !== 1) throw new Error("Parent undertaking identity is ambiguous");
			if (!event.spawnKey) throw new Error("Child stable handoff identity is unavailable");
			const previous = pendingChildren.get(event.spawnKey);
			if (previous && previous.state !== state && previous.state.status !== "closed") throw new Error("Child handoff identity belongs to another undertaking");
			pendingChildren.set(event.spawnKey, { state, specialist, parentId: ctx.agent?.id, auth: ctx.modelRegistry.authStorage });
		} catch (error) { return { block: true, reason: `Undertaking route gap: ${error.message}` }; }
	});

	function release(ctx, state) {
		if (state.lease) ctx.modelRegistry.authStorage.sessions.unrestrict(state.origin.provider, state.sessionId, state.lease);
		state.status = "closed";
		scope(ctx)?.delete(state.sessionId);
		states.delete(state.sessionId);
		selecting.delete(state.sessionId);
		failures.delete(state.sessionId);
		status(ctx, undefined);
	}

	pi.on("session_shutdown", (_event, ctx) => {
		const state = current(ctx);
		if (state) release(ctx, state);
	});

	return { describe };
}
