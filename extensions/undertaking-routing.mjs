import { createHash } from "node:crypto";
import { MODEL_CLASS_ROUTES, explicitModelClassRole, readExecutionCandidates } from "./role-default-helper.mjs";

const ENTRY = "daily-driver-undertaking-route";
const CLASSES = ["mechanical", "implementation", "reasoning", "frontier"];
const EFFORT = /:(off|minimal|low|medium|high|xhigh|max|auto|inherit)$/u;
const GUARDED_APIS = ["openai-completions", "openai-responses", "openai-codex-responses", "anthropic-messages", "google-generative-ai", "google-gemini-cli", "google-vertex"];
const SPECIALISTS = new Set(["reviewer", "scout", "security-reviewer", "seance"]);
// Agent names are process-local, not globally unique. A shared auth store and
// an unambiguous live parent session are both required for inheritance.
const roots = new WeakMap();
const pendingChildren = new Set();
const retiredChildren = new WeakMap();

function retireChild(record) {
	pendingChildren.delete(record);
	let retired = retiredChildren.get(record.auth);
	if (!retired) { retired = new Set(); retiredChildren.set(record.auth, retired); }
	// Retain denial, not the parent's state or authorization, for a late startup.
	retired.add(JSON.stringify([record.parentId, record.key]));
}

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

function sameOrigin(left, right) {
	return left.provider === right.provider && left.model === right.model && left.api === right.api &&
		left.baseUrl === right.baseUrl && left.headersDigest === right.headersDigest;
}

function modelMention(ctx, agent) {
	const agents = new Set();
	const selectors = new Set();
	for (const entry of ctx.sessionManager.getBranch?.() ?? []) {
		if (entry.type !== "custom" || entry.customType !== "model_mention") continue;
		const mention = entry.data;
		if (!mention || typeof mention.agent !== "string" || !/^m\d+$/u.test(mention.agent) ||
			typeof mention.selector !== "string" || typeof mention.name !== "string" ||
			agents.has(mention.agent) || selectors.has(mention.selector)) continue;
		agents.add(mention.agent);
		selectors.add(mention.selector);
		if (mention.agent === agent) return mention;
	}
	return null;
}

function automaticSelection(ctx, model) {
	const entry = (ctx.sessionManager.getBranch?.() ?? []).filter(item => item.type === "model_change").at(-1);
	if (!entry || entry.model?.replace(EFFORT, "") !== selector(model)) return null;
	return entry.resolvedModelIsFallback === true || entry.role === "fallback" || entry.role === "prewalk";
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

function candidateDecision(ctx, state, patterns, effort) {
	if (!patterns.length) throw new Error("Worker effective model route is unavailable");
	if (source(ctx, state.origin.provider) !== state.authenticationRoute) throw new Error("Authentication route must remain unchanged");
	const candidates = patterns.map(pattern => {
		if (typeof pattern !== "string" || /[*?,]/u.test(pattern)) throw new Error("Worker route must use concrete, verifiable candidates");
		const model = ctx.models.resolve(pattern);
		if (!model || !ctx.models.list().some(available => selector(available) === selector(model))) {
			throw new Error("Worker model route is unavailable");
		}
		checkModel(ctx, state, model);
		if (state.capability === "unverified" && selector(model) !== state.selectedModel) {
			throw new Error("An unmapped-family worker must retain the invoking model");
		}
		const configuredEffort = pattern.match(EFFORT)?.[1];
		return {
			origin: origin(model),
			effort: configuredEffort && configuredEffort !== "inherit" ? configuredEffort : effort,
		};
	});
	return {
		candidates, authenticationRoute: state.authenticationRoute, modelClass: state.modelClass,
		family: ctx.models.family(state.workerModels.current()), frontierApproval: state.frontierApproval ?? null,
	};
}

function workerDecision(ctx, state) {
	// Old saved sessions contain the selected route, not an admission snapshot.
	return state.decision ??= candidateDecision(ctx, state, [state.selectedModel], state.selectedEffort);
}

function checkDecision(ctx, decision, model, effort) {
	const actual = origin(model);
	const candidate = decision.candidates.find(candidate => sameOrigin(candidate.origin, actual));
	if (!candidate) throw new Error("Execution fallback does not match the selected worker class route (model, provider, backend or frontier authorization)");
	if (candidate.effort !== undefined && candidate.effort !== effort) throw new Error("Worker effort no longer matches its admitted class route");
	if (source(ctx, actual.provider) !== decision.authenticationRoute) throw new Error("Worker authentication route changed");
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
	if (!state || state.consultation) return null;
	return {
		issue: state.issue, modelClass: state.modelClass, selectedModel: state.selectedModel,
		observedModel: state.observedModel ?? null, status: state.status,
		...(state.reason ? { reason: state.reason } : {}),
		capability: state.capability ?? "mapped",
		...(state.warning ? { warning: state.warning } : {}),
	};
}

function savedEntry(ctx) {
	return (ctx.sessionManager.getBranch?.() ?? [])
		.filter(entry => entry.type === "custom" && entry.customType === ENTRY).at(-1);
}

function storedState(ctx) {
	const entry = savedEntry(ctx);
	if (!entry) return null;
	const saved = entry.data;
	if (saved?.schema === 1 && saved.completed === true) return null;
	if (saved?.schema === 2 && ["completed", "cancelled"].includes(saved.lifecycle)) {
		return saved.retired === true ? saved : null;
	}
	if (![1, 2].includes(saved?.schema) || saved.schema === 2 && saved.lifecycle !== "active" ||
		!CLASSES.includes(saved.modelClass) || !Number.isSafeInteger(saved.issue) || saved.issue < 1 ||
		!saved.origin?.provider || !saved.selectedModel || !saved.authenticationRoute) {
		throw new Error("Saved undertaking route is invalid; use /undertaking status for local recovery");
	}
	return saved;
}

function isCancelled(state) {
	for (let owner = state; owner; owner = owner.ownerState) {
		if (owner.cancelled || owner.cancelling || owner.retired) return true;
	}
	return false;
}

function ownedBy(state, owner) {
	for (let parent = state.ownerState; parent; parent = parent.ownerState) {
		if (parent === owner) return true;
	}
	return false;
}

/** Install undertaking selection and enforce its worker route without changing host helper roles. */
export function installUndertakingRouting(pi, getSettings, getRoutes = () => MODEL_CLASS_ROUTES, getCandidates = readExecutionCandidates) {
	const states = new Map();
	const selecting = new Set();
	const admissions = new Set();
	const failures = new Map();
	const rejections = new Map();

	function status(ctx, text) { ctx.ui?.setStatus?.("daily-driver-routing", text); }

	function current(ctx) { return states.get(ctx.sessionManager?.getSessionId?.()); }

	async function admitDecision(ctx, state, patterns, effort, modelClass, agent, resolvedSelection) {
		const settings = await getSettings(ctx);
		const selection = state.capability === "unverified" ? null : resolvedSelection ??
			classSelection(ctx, settings, await getRoutes(ctx), state.workerModels.current(), modelClass);
		const visible = await getCandidates(ctx, settings, patterns, modelClass, agent);
		const selectedEffort = selection?.configured?.match(EFFORT)?.[1];
		const effectiveEffort = selectedEffort && selectedEffort !== "inherit" ? selectedEffort : effort ?? state.selectedEffort;
		const decision = candidateDecision(ctx, state, visible, effectiveEffort);
		decision.modelClass = modelClass;
		for (const candidate of decision.candidates) {
			if (selection && (!sameOrigin(candidate.origin, origin(selection.target)) ||
				selectedEffort && selectedEffort !== "inherit" && candidate.effort !== undefined && candidate.effort !== selectedEffort)) {
				throw new Error("Automatic candidate does not match the selected worker class route");
			}
			const model = ctx.models.resolve(`${candidate.origin.provider}/${candidate.origin.model}`);
			if (!(await ctx.modelRegistry.getApiKey(model, ctx.sessionManager.getSessionId()))) {
				throw new Error("Worker candidate has no available credentials");
			}
		}
		return decision;
	}

	function publish(ctx, state) {
		state.workerModels ??= ctx.models;
		const previous = states.get(state.sessionId);
		for (const handoff of pendingChildren.values()) {
			if (handoff.state === previous) handoff.state = state;
		}
		states.set(state.sessionId, state);
		const sessions = scope(ctx);
		if (sessions) {
			for (const record of sessions.values()) {
				if (previous && record.state.ownerState === previous) record.state.ownerState = state;
			}
			sessions.set(state.sessionId, {
				agentId: ctx.agent?.id, state, ctx,
				persistCancellation: () => pi.appendEntry(ENTRY, {
					schema: 2, issue: state.issue, lifecycle: "cancelled", retired: true,
				}),
			});
		}
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

	function reportRejection(ctx, state, error) {
		const reason = error instanceof Error ? error.message : String(error);
		rejections.set(ctx.sessionManager.getSessionId(), reason);
		ctx.ui?.notify?.(`Undertaking request rejected: ${reason}. Use /undertaking status; cancel with /undertaking cancel <issue>.`, "warning");
	}

	function inspect(ctx) {
		const state = current(ctx);
		const saved = savedEntry(ctx)?.data;
		let authenticationRoute = state?.authenticationRoute?.split(":")[0] ?? "unreported";
		if (authenticationRoute === "unreported") {
			try { authenticationRoute = source(ctx, ctx.models?.current?.()?.provider).split(":")[0]; } catch { /* Report missing observation. */ }
		}
		return {
			issue: state?.issue ?? null,
			requiredClass: state?.modelClass ?? null,
			selectedModel: state?.selectedModel ?? null,
			selectedEffort: state?.selectedEffort ?? null,
			hostModel: selector(ctx.models?.current?.() ?? ctx.model),
			hostEffort: pi.getThinkingLevel() ?? "unreported",
			observedModel: state?.observedModel ?? "unreported",
			authenticationRoute,
			state: state?.status ?? (selecting.has(ctx.sessionManager.getSessionId()) ? "selecting" : saved?.lifecycle === "cancelled" ? "cancelled" : "none"),
			lastRejection: rejections.get(ctx.sessionManager.getSessionId()) ?? state?.reason ?? null,
			cancelOwner: state ? String(state.issue ?? "invalid") : null,
		};
	}

	pi.registerCommand("undertaking", {
		description: "Inspect or cancel this session's undertaking locally: status | cancel <issue|invalid>",
		handler: async (args, ctx) => {
			const parts = args.trim().split(/\s+/u);
			if (parts.length === 1 && parts[0] === "status") {
				ctx.ui.notify(JSON.stringify(inspect(ctx), null, 2), "info");
				return;
			}
			if (parts.length !== 2 || parts[0] !== "cancel") {
				ctx.ui.notify("Use /undertaking status or /undertaking cancel <issue>. Use invalid only when status reports cancelOwner: invalid.", "warning");
				return;
			}
			const state = current(ctx);
			if (!state) {
				if (selecting.has(ctx.sessionManager.getSessionId())) {
					ctx.ui.notify("Cancellation refused: route selection is in progress and ownership is not yet established. Use /undertaking status after selection stops.", "warning");
					return;
				}
				ctx.ui.notify("No active undertaking owns this session. Nothing was cancelled.", "info");
				return;
			}
			const sessionId = ctx.sessionManager.getSessionId();
			const shared = scope(ctx)?.get(sessionId);
			if (state.sessionId !== sessionId || shared && shared.state !== state ||
				parts[1] !== String(state.issue ?? "invalid") || state.cancelling) {
				ctx.ui.notify("Cancellation refused: ownership does not match this session. Use /undertaking status.", "warning");
				return;
			}
			if (state.retired) {
				ctx.ui.notify("This child is already retired by cancellation. Execution remains denied; start a fresh session for a new undertaking.", "info");
				return;
			}
			if (typeof ctx.waitForIdle !== "function") {
				ctx.ui.notify("Cancellation unavailable: the host cannot wait for in-flight work to stop. Restrictions remain in place.", "warning");
				return;
			}
			state.cancelling = true;
			try {
				ctx.abort();
				await ctx.waitForIdle();
				if (current(ctx) !== state || ctx.sessionManager.getSessionId() !== sessionId || !ctx.isIdle()) {
					throw new Error("Ownership changed or in-flight work is not quiescent; restrictions remain in place");
				}
				state.cancelled = true;
				for (const record of scope(ctx)?.values() ?? []) {
					if (!ownedBy(record.state, state)) continue;
					record.state.cancelled = true;
					record.state.retired = true;
					record.state.status = "blocked";
					record.state.reason = "The owning undertaking was cancelled; this child cannot resume execution";
					record.ctx.abort();
					await record.persistCancellation();
				}
				const retired = Boolean(state.ownerState) || ctx.agent?.kind === "sub";
				await pi.appendEntry(ENTRY, { schema: 2, issue: state.issue, lifecycle: "cancelled", ...(retired ? { retired: true } : {}) });
				release(ctx, state);
				if (retired) {
					state.retired = true;
					state.status = "blocked";
					state.reason = "This child was cancelled and cannot resume execution";
					publish(ctx, state);
				}
				ctx.ui.notify("Undertaking cancelled, not completed. Transcript, worktree, approval evidence, and unfinished task state are unchanged. A new undertaking requires normal admission.", "info");
			} catch (error) {
				reportRejection(ctx, state, error);
			} finally {
				state.cancelling = false;
			}
		},
	});

	async function save(state) {
		await pi.appendEntry(ENTRY, {
			schema: 2, lifecycle: "active", issue: state.issue, modelClass: state.modelClass, selectedModel: state.selectedModel,
			origin: state.origin, authenticationRoute: state.authenticationRoute,
			selectedEffort: state.selectedEffort,
			capability: state.capability ?? "mapped",
			...(state.warning ? { warning: state.warning } : {}),
			...(state.recovery ? { recovery: true, reason: state.reason } : {}),
			...(state.identities ? { identities: state.identities } : {}),
			...(state.frontierApproval ? { frontierApproval: state.frontierApproval } : {}),
			...(state.consultation ? { consultation: true } : {}),
		});
	}

	async function start(event, ctx) {
		const sessionId = ctx.sessionManager?.getSessionId?.();
		if (!sessionId) return;
		const previous = current(ctx);
		if (event.type !== "session_start" && previous) release(ctx, previous);
		if (states.has(sessionId)) return;
		let state;
		try {
			const sessions = scope(ctx);
			const matches = ctx.agent?.kind === "sub" ? [...pendingChildren].filter(record =>
				record.key === ctx.agent.id && record.auth === ctx.modelRegistry.authStorage &&
				record.parentId === ctx.agent.parentId) : [];
			if (matches.length > 1) throw new Error("Child consultation identity is ambiguous");
			const expected = matches[0];
			const parents = ctx.agent?.kind === "sub" && ctx.agent.parentId
				? [...(sessions?.values() ?? [])].filter(record => record.agentId === ctx.agent.parentId) : [];
			if (parents.length > 1) throw new Error("Parent undertaking identity is ambiguous");
			const saved = storedState(ctx);
			if (saved?.retired) {
				state = { ...saved, sessionId, cancelled: true, status: "blocked", reason: "The owning undertaking was cancelled; this child cannot resume execution" };
				publish(ctx, state);
				reportRejection(ctx, state, new Error(state.reason));
				ctx.abort();
				return;
			}
			if (!expected && !saved && ctx.agent?.kind === "sub" &&
				([...pendingChildren].some(record => record.key === ctx.agent.id) ||
					retiredChildren.get(ctx.modelRegistry.authStorage)?.has(JSON.stringify([ctx.agent.parentId, ctx.agent.id])) ||
					parents.length)) throw new Error("Child undertaking handoff identity is missing or belongs to another root");
			if (expected?.specialist) {
				if (expected.state.status !== "verified") throw new Error("Parent undertaking route is not verified");
				pendingChildren.delete(expected);
				return;
			}
			const parent = expected?.state;
			if (!parent && !saved) return;
			if (expected) pendingChildren.delete(expected);
			state = {
				...(parent ?? saved), sessionId, lease: undefined,
				...(expected?.consultation ?? {}),
				decision: expected?.decision,
				admittedRequest: undefined,
				ownerState: parent,
				status: (expected?.consultation || saved?.consultation) ? "consultation" : saved?.recovery ? "blocked" : "pending", observedModel: null,
				workerModels: ctx.models,
				selectedModel: expected?.consultation?.selectedModel ?? (parent ? selector(ctx.models.current()) : saved.selectedModel),
				selectedEffort: expected?.consultation ? expected.consultation.selectedEffort : parent ? pi.getThinkingLevel() : saved.selectedEffort,
				identities: (expected?.consultation ?? parent ?? saved).identities ? [...(expected?.consultation ?? parent ?? saved).identities] : undefined,
			};
			publish(ctx, state);
			if (!state.consultation && !consultation(ctx, state)) {
				if (parent?.status !== undefined && parent.status !== "verified") throw new Error("Parent undertaking route is not verified");
				checkModel(ctx, state, ctx.models.current(), Boolean(state.recovery));
				if (state.decision) {
					state.decision = {
						...state.decision,
						candidates: state.decision.candidates.map(candidate => ({
							...candidate, effort: candidate.effort ?? pi.getThinkingLevel(),
						})),
					};
					checkDecision(ctx, state.decision, ctx.models.current(), pi.getThinkingLevel());
				}
				if (parent?.capability === "unverified" && selector(ctx.models.current()) !== parent.selectedModel) {
					throw new Error("An unmapped-family worker must retain the invoking model");
				}
			}
			if (state.consultation && !sameOrigin(origin(ctx.models.current()), state.origin)) throw new Error("Consultation model differs from the operator's native selection");
			if (source(ctx, state.origin.provider) !== state.authenticationRoute) throw new Error("Authentication route changed before session recovery");
			installPool(ctx, state);
			if (parent) await save(state);
		} catch (error) {
			const saved = savedEntry(ctx)?.data;
			state ??= {
				sessionId, status: "blocked",
				issue: Number.isSafeInteger(saved?.issue) && saved.issue > 0 ? saved.issue : null,
				modelClass: null, selectedModel: null,
			};
			publish(ctx, state);
			routeError(state, error.message);
			reportRejection(ctx, state, error);
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
			if (admissions.has(sessionId)) return {
				isError: true, content: [{ type: "text", text: "Another route admission is in flight; inspect or cancel the current operation before retrying." }], details: describe(ctx),
			};
			if (previous && isCancelled(previous)) return {
				isError: true, content: [{ type: "text", text: "A cancelled undertaking cannot authorize this child." }], details: describe(ctx),
			};
			if (previous?.consultation) return {
				isError: true, content: [{ type: "text", text: "A model consultation cannot reassign the parent undertaking worker." }], details: describe(ctx),
			};
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
			const admissionRevoked = () => ctx.sessionManager.getSessionId() !== sessionId ||
				isCancelled(previous) || isCancelled(state) ||
				(current(ctx) !== previous && current(ctx) !== state);
			const checkAdmission = () => {
				if (admissionRevoked()) throw new Error("Undertaking admission was cancelled or its owner changed");
			};
			admissions.add(sessionId);
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
				state.selectedModel = selector(target);
				state.selectedEffort = nextEffort;
				state.admittedRequest = undefined;
				state.decision = await admitDecision(ctx, state, [`${state.selectedModel}:${nextEffort}`], nextEffort, params.modelClass, undefined, selection);
				checkAdmission();
				if (changed && typeof pi.setModel !== "function") throw new Error("Model selection control is unavailable");
				if (nextEffort !== invokingEffort && typeof pi.setThinkingLevel !== "function") throw new Error("Effort selection control is unavailable");
				if (!state.lease) installPool(ctx, state);
				state.observedModel = changed ? null : selector(invoking);
				state.status = changed ? "pending" : "verified";
				state.reason = undefined;
				state.warning = capability === "unverified"
					? previous?.warning ?? `WARNING: Family ${ctx.models.family(invoking)} has no model-class mapping. Suitability for ${params.modelClass} is unverified. Continuing with the invoking model: ${selector(invoking)}.`
					: undefined;
				await save(state);
				checkAdmission();
				publish(ctx, state);
				switching = changed;
				if (selector(invoking) !== selector(target) && !(await pi.setModel(target))) throw new Error("Harness rejected the session model switch");
				checkAdmission();
				if (nextEffort !== invokingEffort) await pi.setThinkingLevel(nextEffort);
				checkAdmission();
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
				if (admissionRevoked()) {
					if (state?.lease && state.lease !== previous?.lease && current(ctx) !== state) {
						ctx.modelRegistry.authStorage.sessions.unrestrict(state.origin.provider, sessionId, state.lease);
					}
					return { isError: true, content: [{ type: "text", text: "Undertaking admission cancelled; ownership was not restored." }], details: describe(ctx) };
				}
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
				if (admissionRevoked()) return {
					isError: true, content: [{ type: "text", text: "Undertaking admission cancelled during restoration; ownership was not restored." }], details: describe(ctx),
				};
				if (restored) {
					if (state?.lease && state.lease !== previous?.lease) ctx.modelRegistry.authStorage.sessions.unrestrict(state.origin.provider, sessionId, state.lease);
					if (previous) publish(ctx, previous);
					else { states.delete(sessionId); scope(ctx)?.delete(sessionId); }
					if (state?.selectedModel) {
						if (previous) await save(previous);
						else await pi.appendEntry(ENTRY, { schema: 2, issue: params.issue, lifecycle: "cancelled" });
					}
				} else {
					state.status = "blocked";
					state.reason = error.message;
					state.recovery = true;
					publish(ctx, state);
					await save(state);
				}
				return { isError: true, content: [{ type: "text", text: `Undertaking route gap: ${error.message}. Use /undertaking status for local recovery.` }], details: describe(ctx) };
			} finally {
				admissions.delete(sessionId);
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
			if (!state || state.issue !== params.issue || isCancelled(state)) return {
				isError: true, content: [{ type: "text", text: "No matching undertaking owns this session." }], details: describe(ctx),
			};
			await pi.appendEntry(ENTRY, { schema: 2, issue: state.issue, lifecycle: "completed" });
			release(ctx, state);
			return { content: [{ type: "text", text: "Undertaking route finished." }], details: describe(ctx) };
		},
	});

	function consultation(ctx, state) {
		const live = state.workerModels.current();
		return !state.consultation && ctx.agent?.kind === "main" && frontier(live) &&
			selector(live) !== state.selectedModel && automaticSelection(ctx, live) === false;
	}

	function workerReady(ctx, state) {
		if (isCancelled(state) || state.status !== "verified" || state.consultation ||
			selector(state.workerModels.current()) !== state.selectedModel ||
			(state.selectedEffort !== undefined && pi.getThinkingLevel() !== state.selectedEffort)) return false;
		try {
			checkDecision(ctx, workerDecision(ctx, state), state.workerModels.current(), pi.getThinkingLevel());
			return true;
		} catch { return false; }
	}

	pi.on("before_provider_request", (_event, ctx) => {
		const state = current(ctx);
		if (!state) return;
		// Side requests on independently selected helper models are not undertaking workers.
		// Keep the live query captured outside this request: request contexts bind
		// both model accessors to the request model, including helper requests.
		if (!isCancelled(state) && selector(ctx.model) !== selector(state.workerModels.current())) return;
		try {
			if (isCancelled(state)) throw new Error("The owning undertaking was cancelled; execution is not authorized");
			state.admittedRequest = undefined;
			if (consultation(ctx, state)) return;
			if (state.consultation) {
				if (state.status === "blocked") throw new Error(state.reason);
				if (!sameOrigin(origin(ctx.model), state.origin)) throw new Error("Consultation model differs from the operator's native selection");
				if (state.selectedEffort !== undefined && pi.getThinkingLevel() !== state.selectedEffort) throw new Error("Consultation effort differs from the operator's native selection");
			} else if (state.recovery) {
				checkModel(ctx, state, ctx.model, true);
			} else {
				if (state.status === "blocked") throw new Error(state.reason);
				checkDecision(ctx, workerDecision(ctx, state), ctx.model, pi.getThinkingLevel());
			}
			if (source(ctx, state.origin.provider) !== state.authenticationRoute) throw new Error("Worker authentication route changed");
			state.admittedRequest = state.consultation || state.recovery ? undefined : {
				model: selector(ctx.model), effort: pi.getThinkingLevel(),
			};
		} catch (error) {
			// Reject this request without poisoning the selected route needed for recovery.
			state.admittedRequest = undefined;
			reportRejection(ctx, state, error);
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
		const admitted = state?.admittedRequest;
		if (state) state.admittedRequest = undefined;
		if (isCancelled(state)) return;
		if (state?.status === "verified" && !requestsSelection &&
			`${message?.provider}/${message?.model}` === state.selectedModel) selecting.delete(sessionId);
		if (!state || state.status !== "pending") return;
		if (message?.role === "assistant" && !["error", "aborted"].includes(message.stopReason) &&
			`${message.provider}/${message.model}` === state.selectedModel &&
			selector(ctx.models.current()) === state.selectedModel && !state.recovery &&
			admitted?.model === state.selectedModel && admitted.effort === pi.getThinkingLevel()) {
			try { checkDecision(ctx, workerDecision(ctx, state), ctx.models.current(), pi.getThinkingLevel()); }
			catch { return; }
			state.status = "verified";
			state.observedModel = state.selectedModel;
			if (!requestsSelection) selecting.delete(sessionId);
			status(ctx, undefined);
		}
	});

	pi.on("tool_call", (event, ctx) => {
		const state = current(ctx);
		const failure = failures.get(ctx.sessionManager?.getSessionId?.());
		if (isCancelled(state)) return { block: true, reason: "The owning undertaking was cancelled; execution is not authorized" };
		// Operator consultation tools do not verify or reassign the undertaking worker.
		if (state && consultation(ctx, state) && !selecting.has(ctx.sessionManager?.getSessionId?.())) return;
		if (!failure && (!state || workerReady(ctx, state) || state.consultation && state.status === "consultation") &&
			!selecting.has(ctx.sessionManager?.getSessionId?.())) return;
		if (["read", "grep", "glob", "daily_driver_get_session", "daily_driver_route_undertaking", "daily_driver_finish_undertaking"].includes(event.toolName)) return;
		if (event.toolName === "write" && ["xd://daily_driver_get_session", "xd://daily_driver_route_undertaking", "xd://daily_driver_finish_undertaking"].includes(event.input?.path)) return;
		// A pending worker may still carry the operator's native consultation.
		const tasks = event.input?.tasks ?? (event.input?.agent ? [event.input] : []);
		if (!failure && state && !selecting.has(ctx.sessionManager?.getSessionId?.()) &&
			event.toolName === "task" && tasks.length && tasks.every(task => modelMention(ctx, task.agent))) return;
		return { block: true, reason: failure ?? state?.reason ?? "Task work requires the selected worker's verified identity. Wait for an admitted worker response or restore its route." };
	});

	pi.on("before_subagent_spawn", async (event, ctx) => {
		const state = current(ctx);
		if (!state) return;
		try {
			if (isCancelled(state)) throw new Error("The owning undertaking was cancelled; execution is not authorized");
			const mention = modelMention(ctx, event.agent);
			if (!mention && !workerReady(ctx, state)) throw new Error("Parent undertaking route is not verified on the selected worker");
			if (!event.patterns?.length) throw new Error("Child effective model route is unavailable");
			const specialist = !mention && SPECIALISTS.has(event.agent);
			let selected;
			if (mention) {
				if (/[*?,]/u.test(mention.selector)) throw new Error("Native consultation must select one concrete model");
				const model = ctx.models.resolve(mention.selector);
				if (!model || selector(model) !== mention.selector.replace(EFFORT, "")) throw new Error("Native consultation model cannot be resolved exactly");
				const effort = mention.selector.match(EFFORT)?.[1];
				const visible = await getCandidates(ctx, await getSettings(ctx), [mention.selector], event.modelRole, event.agent);
				if (visible.some(pattern => {
					const candidate = ctx.models.resolve(pattern);
					return !candidate || !sameOrigin(origin(candidate), origin(model)) ||
						(pattern.match(EFFORT)?.[1] ?? effort) !== effort;
				})) throw new Error("Native consultation automatic candidate differs from the operator's exact selection");
				selected = {
					consultation: true, origin: origin(model), selectedModel: selector(model), recovery: undefined,
					selectedEffort: effort && effort !== "inherit" ? effort : undefined,
					authenticationRoute: source(ctx, model.provider),
					identities: model.provider === state.origin.provider ? state.identities : undefined,
				};
			} else if (!specialist) {
				const modelClass = CLASSES.includes(event.modelRole) ? event.modelRole : state.modelClass;
				selected = { decision: await admitDecision(ctx, state, event.patterns, undefined, modelClass, event.agent) };
			}
			if (isCancelled(state) || current(ctx) !== state) throw new Error("The owning undertaking was cancelled or replaced during child admission");
			const parents = [...(scope(ctx)?.values() ?? [])].filter(record => record.agentId === ctx.agent?.id);
			if (parents.length !== 1) throw new Error("Parent undertaking identity is ambiguous");
			if (!event.spawnKey) throw new Error("Child stable handoff identity is unavailable");
			const previous = [...pendingChildren].find(record => record.key === event.spawnKey &&
				record.auth === ctx.modelRegistry.authStorage && record.parentId === ctx.agent?.id);
			if (previous) pendingChildren.delete(previous);
			retiredChildren.get(ctx.modelRegistry.authStorage)?.delete(JSON.stringify([ctx.agent?.id, event.spawnKey]));
			pendingChildren.add({ key: event.spawnKey, state, specialist, consultation: mention ? selected : undefined, decision: selected?.decision, parentId: ctx.agent?.id, auth: ctx.modelRegistry.authStorage });
			if (mention) return { model: [mention.selector], note: "Use the operator's exact native model selection." };
		} catch (error) { return { block: true, reason: `Undertaking route gap: ${error.message}` }; }
	});

	function release(ctx, state) {
		if (state.lease) ctx.modelRegistry.authStorage.sessions.unrestrict(state.origin.provider, state.sessionId, state.lease);
		state.lease = undefined;
		for (const record of pendingChildren) if (record.state === state) retireChild(record);
		state.status = "closed";
		scope(ctx)?.delete(state.sessionId);
		states.delete(state.sessionId);
		selecting.delete(state.sessionId);
		failures.delete(state.sessionId);
		rejections.delete(state.sessionId);
		status(ctx, undefined);
	}

	pi.on("tool_result", (event, ctx) => {
		if (event.toolName !== "task" || !event.isError) return;
		for (const record of pendingChildren) {
			if (record.auth === ctx.modelRegistry.authStorage && record.parentId === ctx.agent?.id) retireChild(record);
		}
	});

	pi.on("session_shutdown", (_event, ctx) => {
		const state = current(ctx);
		if (state) release(ctx, state);
	});

	return { describe };
}
