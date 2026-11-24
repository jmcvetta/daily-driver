const ENTRY = "daily-driver-undertaking-route";
const CLASSES = ["mechanical", "routine", "intermediate", "complex", "frontier"];
const EFFORT = /:(off|minimal|low|medium|high|xhigh|max|auto|inherit)$/u;
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

function source(ctx, provider) {
	const value = ctx.modelRegistry?.authStorage?.keys?.source(provider, { env: "aliases" });
	if (!value?.kind || (value.kind === "env" && !value.envVar)) throw new Error("Authentication route is unavailable");
	return value.kind === "env" ? `env:${value.envVar}` : value.kind;
}


function scope(ctx) {
	const auth = ctx.modelRegistry?.authStorage;
	if (!auth || typeof auth !== "object") return null;
	let sessions = roots.get(auth);
	if (!sessions) { sessions = new Map(); roots.set(auth, sessions); }
	return sessions;
}


function classSelection(ctx, settings, modelClass) {
	const configured = settings?.getModelRole(modelClass);
	if (typeof configured !== "string" || !configured.trim()) {
		throw new Error(`Effective ${modelClass} assignment is missing, cleared, or invalid`);
	}
	const target = ctx.models.resolve(configured);
	if (!target) throw new Error(`Configured class model ${configured} is unavailable`);
	return { target, configured };
}

function publicState(state) {
	if (!state || state.consultation) return null;
	return {
		issue: state.issue, modelClass: state.modelClass, selectedModel: state.selectedModel,
		observedModel: state.observedModel ?? null, status: state.status,
		attemptedModel: state.attemptedModel ?? null,
		selectedEffort: state.selectedEffort ?? null,
		observedEffort: state.observedEffort ?? null,
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
	if ([2, 3, 4].includes(saved?.schema) && ["completed", "cancelled"].includes(saved.lifecycle)) {
		return saved.retired === true ? saved : null;
	}
	// Older session records retain their original class tokens across the cutover.
	const legacyClasses = { implementation: "routine", integration: "intermediate", reasoning: "complex" };
	const modelClass = legacyClasses[saved?.modelClass] ?? saved?.modelClass;
	if (![1, 2, 3, 4].includes(saved?.schema) || saved.schema >= 2 && saved.lifecycle !== "active" ||
		!CLASSES.includes(modelClass) || !Number.isSafeInteger(saved.issue) || saved.issue < 1) {
		throw new Error("Saved undertaking route is invalid; use /undertaking status for local recovery");
	}
	return { ...saved, modelClass };
}

/** Block reasons name the owning issue where known and a concrete recovery route. */
function guardReason(condition, issue) {
	const known = Number.isSafeInteger(issue) && issue > 0;
	return `${condition}${known ? ` for issue #${issue}` : ""}. Use /undertaking status for current state and recovery.`;
}

function isCancelled(state) {
	for (let owner = state; owner; owner = owner.ownerState) {
		if (owner.cancelled || owner.retired) return true;
	}
	return false;
}

function ownedBy(state, owner) {
	for (let parent = state.ownerState; parent; parent = parent.ownerState) {
		if (parent === owner) return true;
	}
	return false;
}

/** Install one-time undertaking model selection without changing host helper roles. */
export function installUndertakingRouting(pi, getSettings, onCompleted = () => {}) {
	const states = new Map();
	const owners = new Map();
	function history(sessionId) {
		if (!owners.has(sessionId)) owners.set(sessionId, new Map());
		return owners.get(sessionId);
	}
	const selecting = new Set();
	const inFlightSelections = new Set();
	const rejections = new Map();

	function status(ctx, text) { ctx.ui?.setStatus?.("daily-driver-routing", text); }

	function current(ctx) { return states.get(ctx.sessionManager?.getSessionId?.()); }


	function publish(ctx, state) {
		state.workerModels ??= ctx.models;
		history(state.sessionId).set(state.issue, state);
		states.set(state.sessionId, state);
		const sessions = scope(ctx);
		if (sessions) {
			sessions.set(state.sessionId, {
				agentId: ctx.agent?.id, state, ctx,
				persistCancellation: () => pi.appendEntry(ENTRY, {
					schema: 3, issue: state.issue, lifecycle: "cancelled", retired: true,
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
		let authenticationRoute = "unreported";
		try { authenticationRoute = source(ctx, ctx.models?.current?.()?.provider).split(":")[0]; } catch { /* Report missing observation. */ }
		return {
			issue: state?.issue ?? null,
			requiredClass: state?.modelClass ?? null,
			selectedModel: state?.selectedModel ?? null,
			selectedEffort: state?.selectedEffort ?? null,
			hostModel: selector(ctx.models?.current?.() ?? ctx.model),
			hostEffort: pi.getThinkingLevel?.() ?? "unreported",
			observedModel: state?.observedModel ?? "unreported",
			authenticationRoute,
			state: state?.status ?? (selecting.has(ctx.sessionManager.getSessionId()) ? "selecting" : saved?.lifecycle === "cancelled" ? "cancelled" : "none"),
			lastRejection: rejections.get(ctx.sessionManager.getSessionId()) ?? state?.reason ?? null,
			cancelOwner: state ? String(state.issue ?? "invalid") : null,
			owners: [...history(ctx.sessionManager.getSessionId()).values()]
				.filter(owner => !owner.completed && !owner.cancelled)
				.map(owner => owner.issue),
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
			const sessionId = ctx.sessionManager.getSessionId();
			const state = [...history(sessionId).values()].find(owner =>
				String(owner.issue ?? "invalid") === parts[1] && !owner.completed &&
				(!owner.cancelled || !owner.cancellationSaved));
			if (!state) {
				if (selecting.has(ctx.sessionManager.getSessionId())) {
					ctx.ui.notify("Cancellation refused: route selection is in progress and ownership is not yet established. Use /undertaking status after selection stops.", "warning");
					return;
				}
				ctx.ui.notify("No active undertaking owns this session. Nothing was cancelled.", "info");
				return;
			}
			if (state.sessionId !== sessionId || state.cancelling) {
				ctx.ui.notify("Cancellation refused: ownership does not match this session. Use /undertaking status.", "warning");
				return;
			}
			if (state.retired) {
				ctx.ui.notify("This child is already retired by cancellation. Execution remains denied; start a fresh session for a new undertaking.", "info");
				return;
			}
			if (typeof ctx.waitForIdle !== "function") {
				ctx.ui.notify("Cancellation unavailable: the host cannot wait for in-flight work to stop. The undertaking remains active.", "warning");
				return;
			}
			state.cancelling = true;
			try {
				if (current(ctx) === state) {
					ctx.abort();
					await ctx.waitForIdle();
					if (ctx.sessionManager.getSessionId() !== sessionId || !ctx.isIdle()) {
						throw new Error("Ownership changed or in-flight work is not quiescent; cancellation was not completed");
					}
				}
				const children = [...(scope(ctx)?.values() ?? [])].filter(record => ownedBy(record.state, state));
				for (const record of children) {
					record.state.cancelled = true;
					record.state.retired = true;
					record.state.status = "blocked";
					record.state.reason = "The owning undertaking was cancelled; this child cannot resume execution";
					record.ctx.abort();
				}
				await Promise.all(children.map(record => record.ctx.waitForIdle()));
				for (const record of children) await record.persistCancellation();
				const retired = Boolean(state.ownerState) || ctx.agent?.kind === "sub";
				state.cancelled = true;
				state.retired = retired;
				await save(state);
				state.cancellationSaved = true;
				release(ctx, state);
				if (retired) {
					state.retired = true;
					state.status = "blocked";
					state.reason = "This child was cancelled and cannot resume execution";
					publish(ctx, state);
				}
				ctx.ui.notify("Undertaking cancelled, not completed. Transcript, worktree, and unfinished state are unchanged. A new undertaking requires a fresh initial selection.", "info");
			} catch (error) {
				reportRejection(ctx, state, error);
			} finally {
				state.cancelling = false;
			}
		},
	});

	function serialized(state) {
		return {
			lifecycle: state.cancelled ? "cancelled" : state.completed ? "completed" : "active",
			issue: state.issue, modelClass: state.modelClass, selectedModel: state.selectedModel,
			selectedEffort: state.selectedEffort, attemptedModel: state.attemptedModel,
			invokingModel: state.invokingModel, invokingEffort: state.invokingEffort,
			observedModel: state.observedModel, observedEffort: state.observedEffort,
			status: state.status, reason: state.reason, retired: state.retired,
		};
	}

	async function save(state) {
		await pi.appendEntry(ENTRY, {
			schema: 4, ...serialized(states.get(state.sessionId) ?? state),
			owners: [...history(state.sessionId).values()].map(serialized),
		});
	}

	async function start(event, ctx) {
		const sessionId = ctx.sessionManager?.getSessionId?.();
		if (!sessionId) return;
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
			const raw = savedEntry(ctx)?.data;
			const retired = ctx.agent?.kind === "sub" &&
				retiredChildren.get(ctx.modelRegistry.authStorage)?.has(JSON.stringify([ctx.agent.parentId, ctx.agent.id]));
			const saved = raw?.retired || retired
				? { ...raw, retired: true } : storedState(ctx);
			const records = savedEntry(ctx)?.data;
			if (records?.schema === 4 && Array.isArray(records.owners)) {
				for (const record of records.owners) {
					if (!Number.isSafeInteger(record?.issue) || record.issue < 1) continue;
					history(sessionId).set(record.issue, {
						...record, sessionId, completed: record.lifecycle === "completed",
						cancelled: record.lifecycle === "cancelled",
					});
				}
			}
			if (saved?.retired) {
				state = { ...saved, sessionId, cancelled: true, status: "blocked", reason: "The owning undertaking was cancelled; this child cannot resume execution" };
				publish(ctx, state);
				reportRejection(ctx, state, new Error(state.reason));
				return;
			}
			if (!expected && !saved && ctx.agent?.kind === "sub" &&
				([...pendingChildren].some(record => record.key === ctx.agent.id) ||
					retiredChildren.get(ctx.modelRegistry.authStorage)?.has(JSON.stringify([ctx.agent.parentId, ctx.agent.id])) ||
					parents.length)) throw new Error("Child undertaking handoff identity is missing or belongs to another root");
			const parent = expected?.state;
			if (!parent && !saved) return;
			if (expected) pendingChildren.delete(expected);
			state = {
				...(parent ?? saved), sessionId, ownerState: parent,
				status: parent?.status ?? saved?.status ?? "selected", observedModel: null, workerModels: ctx.models,
				recovery: undefined, consultation: undefined,
			};
			publish(ctx, state);
			if (parent) await save(state);
		} catch (error) {
			const saved = savedEntry(ctx)?.data;
			state ??= {
				sessionId, status: "informational",
				issue: Number.isSafeInteger(saved?.issue) && saved.issue > 0 ? saved.issue : null,
				modelClass: null, selectedModel: null,
			};
			publish(ctx, state);
			state.reason = error.message;
			rejections.set(sessionId, error.message);
			ctx.ui?.notify?.(`Undertaking metadata: ${error.message}. Ordinary work can continue.`, "info");
		}
	}

	pi.on("session_start", start);
	pi.on("session_switch", start);
	pi.on("session_branch", start);
	pi.on("session_tree", start);

	pi.registerTool({
		name: "daily_driver_route_undertaking",
		label: "Select undertaking model class",
		description: "Apply the effective Omp class role once for a new undertaking. Selection failures are informational; later operator choices remain authoritative.",
		parameters: pi.zod.object({
			issue: pi.zod.number().int().min(1),
			modelClass: pi.zod.string(),
		}),
		execute: async (_id, params, signal, _update, ctx) => {
			const sessionId = ctx.sessionManager.getSessionId();
			const previous = current(ctx);
			const result = (text, stopped = false) => ({
				...(stopped ? { isError: true } : {}),
				content: [{ type: "text", text }], details: describe(ctx),
			});
			if (signal?.aborted || isCancelled(previous)) return result("Undertaking selection is cancelled.", true);
			if (inFlightSelections.has(sessionId)) return result("Initial selection is already in progress. Ordinary work can continue.");
			if (!Number.isSafeInteger(params.issue) || params.issue < 1 || !CLASSES.includes(params.modelClass)) {
				return result("A valid issue and required model class are mandatory.", true);
			}
			const existing = history(sessionId).get(params.issue);
			if (existing?.cancelled) return result("This undertaking was cancelled and cannot restart.", true);
			if (existing) return result("This undertaking has already attempted initial selection; the current operator route is unchanged.");
			const modelNow = () => ctx.models?.current?.() ?? ctx.model;
			const effortNow = () => pi.getThinkingLevel?.();
			const invoking = modelNow();
			const invokingEffort = effortNow();
			const state = {
				issue: params.issue, modelClass: params.modelClass, sessionId,
				workerModels: ctx.models, ownerState: previous?.ownerState,
				status: "selecting", capability: "configured",
				invokingModel: selector(invoking), invokingEffort,
				selectedModel: null, selectedEffort: null,
			};
			const cancelled = () => signal?.aborted || isCancelled(state) ||
				ctx.sessionManager.getSessionId() !== sessionId || current(ctx) !== state;
			const check = () => { if (cancelled()) throw new Error("Initial selection was cancelled or its owner changed"); };
			let target;
			let nextEffort = invokingEffort;
			let modelAttempted = false;
			let effortAttempted = false;
			let effortCompleted = false;
			let appliedEffort = invokingEffort;
			let message;
			inFlightSelections.add(sessionId);
			selecting.add(sessionId);
			publish(ctx, state);
			try {
				const settings = await getSettings(ctx);
				check();
				state.attemptedModel = settings?.getModelRole(params.modelClass) ?? null;
				const selection = classSelection(ctx, settings, params.modelClass);
				target = selection.target;
				const effort = selection.configured.match(EFFORT)?.[1];
				nextEffort = effort && effort !== "inherit" ? effort : invokingEffort;
				if (!selector(invoking) || invokingEffort === undefined) throw new Error("Invoking model or effort metadata is unavailable");
				if (selector(invoking) !== selector(target) && typeof pi.setModel !== "function") throw new Error("Model selection control is unavailable");
				if (nextEffort !== invokingEffort && typeof pi.setThinkingLevel !== "function") throw new Error("Effort selection control is unavailable");
				if (!(await ctx.modelRegistry.getApiKey(target, sessionId))) throw new Error("Requested model has no available credentials");
				check();
				let operatorChanged = selector(modelNow()) !== selector(invoking) || effortNow() !== invokingEffort;
				if (!operatorChanged && selector(invoking) !== selector(target)) {
					modelAttempted = true;
					if (!(await pi.setModel(target))) throw new Error("Harness rejected the session model switch");
					check();
					operatorChanged = selector(modelNow()) !== selector(target) || effortNow() !== invokingEffort;
				}
				if (!operatorChanged && nextEffort !== invokingEffort) {
					// The host does not provide an atomic model-plus-effort setter.
					check();
					effortAttempted = true;
					await pi.setThinkingLevel(nextEffort);
					appliedEffort = effortNow();
					effortCompleted = true;
				}
				check();
				operatorChanged ||= selector(modelNow()) !== selector(target);
				state.selectedModel = operatorChanged ? null : selector(target);
				state.selectedEffort = operatorChanged ? null : appliedEffort;
				state.status = operatorChanged ? "informational" : "selected";
				message = operatorChanged ? "Operator changes were retained." : "Initial undertaking model and effort selected.";
				state.observedModel = selector(modelNow());
				state.observedEffort = effortNow();
				await save(state);
				check();
			} catch (error) {
				const stopped = cancelled();
				if (stopped) {
					state.cancelled = true;
					state.retired = Boolean(state.ownerState) || ctx.agent?.kind === "sub";
				}
				let failure = error instanceof Error ? error.message : String(error);
				// Restore only a route that still matches this selector's own mutations.
				const expectedModel = modelAttempted ? selector(target) : selector(invoking);
				const actualEffort = effortNow();
				const effortOwned = !effortAttempted ? actualEffort === invokingEffort
					: effortCompleted ? actualEffort === appliedEffort
						: actualEffort === invokingEffort || actualEffort === nextEffort;
				if (!stopped && selector(modelNow()) === expectedModel && effortOwned) {
					try {
						if (effortAttempted && effortNow() !== invokingEffort) await pi.setThinkingLevel(invokingEffort);
						if (modelAttempted && selector(modelNow()) === selector(target) &&
							effortNow() === invokingEffort) {
							if (!(await pi.setModel(invoking))) throw new Error("Harness rejected model restoration");
						}
					} catch (restoreError) { failure += `; restoration failed: ${restoreError.message}`; }
				}
				state.observedModel = selector(modelNow());
				state.observedEffort = effortNow();
				state.reason = failure;
				state.status = stopped ? "blocked" : "informational";
				state.selectedModel = null;
				state.selectedEffort = null;
				rejections.set(sessionId, failure);
				if (ctx.sessionManager.getSessionId() === sessionId && current(ctx) === state) {
					try { await save(state); }
					catch (saveError) { failure += `; persistence failed: ${saveError.message}`; state.reason = failure; }
				}
				message = `${params.modelClass} initial selection${state.attemptedModel ? ` (${state.attemptedModel})` : ""}: ${failure}. Actual route: ${state.observedModel ?? "unreported"}/${state.observedEffort ?? "unreported"}. ${stopped ? "Selection remains stopped." : "Ordinary work can continue."}`;
				ctx.ui?.notify?.(message, "info");
				if (stopped) return result(message, true);
			} finally {
				inFlightSelections.delete(sessionId);
				selecting.delete(sessionId);
				status(ctx, undefined);
			}
			return result(message);
		},
	});

	pi.registerTool({
		name: "daily_driver_finish_undertaking",
		label: "Finish undertaking model route",
		description: "Record truthful completion and notify once. Completion is not required to start another issue.",
		parameters: pi.zod.object({ issue: pi.zod.number().int().min(1) }),
		execute: async (_id, params, _signal, _update, ctx) => {
			const state = history(ctx.sessionManager.getSessionId()).get(params.issue);
			if (!state || state.completed || isCancelled(state)) return {
				isError: true, content: [{ type: "text", text: "No matching unfinished undertaking owns this session." }], details: describe(ctx),
			};
			state.completed = true;
			try { await save(state); }
			catch (error) { state.completed = false; throw error; }
			release(ctx, state);
			try {
				await onCompleted(ctx, state.issue);
			} catch (error) {
				console.error(`daily-driver: undertaking completion notification failed: ${error.message}`);
			}
			return { content: [{ type: "text", text: "Undertaking route finished." }], details: describe(ctx) };
		},
	});

	pi.on("assistant_message", (event, ctx) => {
		if (event.message?.content?.some(part => part.type === "toolCall" &&
			(part.name === "daily_driver_route_undertaking" ||
				(part.name === "write" && part.arguments?.path === "xd://daily_driver_route_undertaking")))) {
			selecting.add(ctx.sessionManager.getSessionId());
		}
	});

	pi.on("before_subagent_spawn", (event, ctx) => {
		const state = current(ctx);
		if (!state) return;
		if (isCancelled(state)) return { block: true, reason: guardReason("The owning undertaking was cancelled; child dispatch is blocked", state?.issue) };
		const dispatchEpoch = state.dispatchEpoch ?? 0;
		if (current(ctx) !== state || (state.dispatchEpoch ?? 0) !== dispatchEpoch) {
			return { block: true, reason: guardReason("The owning undertaking or child dispatch was cancelled or replaced", state?.issue) };
		}
		const parents = [...(scope(ctx)?.values() ?? [])].filter(record => record.agentId === ctx.agent?.id);
		if (parents.length !== 1 || !event.spawnKey) {
			return { block: true, reason: guardReason("Child undertaking ownership identity is unavailable or ambiguous", state?.issue) };
		}
		const auth = ctx.modelRegistry.authStorage;
		for (const record of pendingChildren) {
			if (record.key === event.spawnKey && record.auth === auth && record.parentId === ctx.agent?.id) pendingChildren.delete(record);
		}
		retiredChildren.get(auth)?.delete(JSON.stringify([ctx.agent?.id, event.spawnKey]));
		pendingChildren.add({ key: event.spawnKey, state, parentId: ctx.agent?.id, auth });
	});

	function release(ctx, state) {
		for (const record of pendingChildren) if (record.state === state) retireChild(record);
		state.status = "closed";
		if (current(ctx) === state) {
			scope(ctx)?.delete(state.sessionId);
			states.delete(state.sessionId);
		}
		selecting.delete(state.sessionId);
		rejections.delete(state.sessionId);
		status(ctx, undefined);
	}

	pi.on("tool_result", (event, ctx) => {
		if (event.toolName !== "task" || !event.isError) return;
		const state = current(ctx);
		if (state) state.dispatchEpoch = (state.dispatchEpoch ?? 0) + 1;
		for (const record of pendingChildren) {
			if (record.auth === ctx.modelRegistry.authStorage && record.parentId === ctx.agent?.id) retireChild(record);
		}
	});

	pi.on("session_shutdown", (_event, ctx) => {
		for (const state of history(ctx.sessionManager?.getSessionId?.()).values()) release(ctx, state);
	});

	return { describe };
}
