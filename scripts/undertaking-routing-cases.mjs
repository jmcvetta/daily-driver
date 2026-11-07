import assert from "node:assert/strict";
import { installUndertakingRouting } from "../extensions/undertaking-routing.mjs";
import { installModelClassDefaults } from "../extensions/role-default-helper.mjs";

const PROVIDER = "openai-codex";
const qualified = (model) => `${model.provider}/${model.id}`;
const model = (id, overrides = {}) => ({
	id,
	name: id,
	provider: PROVIDER,
	api: "openai-codex-responses",
	baseUrl: "https://routing.example.invalid/v1",
	headers: { "x-routing-region": "fixture-region" },
	...overrides,
});
const MECHANICAL = model("gpt-6-luna");
const REASONING = model("gpt-6.1-sol");
const FRONTIER = model("gpt-6-astra");
const FOREIGN = model("claude-sonnet", { provider: "anthropic" });
const MODELS = [MECHANICAL, REASONING, FRONTIER, FOREIGN];
const DEEPSEEK_PRO = model("deepseek-v4-pro", { provider: "deepseek-go", api: "openai-completions" });
const DEEPSEEK_FLASH = model("deepseek-v4-flash", { provider: "deepseek-go", api: "openai-completions" });
const GATEWAY_FLASH = model("deepseek/deepseek-v4-flash", { provider: "vercel-ai-gateway", api: "openai-completions" });
const GATEWAY_OTHER = model("other/variant", { provider: "vercel-ai-gateway", api: "openai-completions" });
const deepseekFamily = (candidate) => candidate.id.includes("deepseek") ? "deepseek" : "other";
const deepseekRoutes = [{ referenceModel: qualified(DEEPSEEK_PRO), classes: { implementation: `${qualified(DEEPSEEK_FLASH)}:low` } }];
let nextSession = 0;

function deferred() {
	let resolve;
	const promise = new Promise((complete) => { resolve = complete; });
	return { promise, resolve };
}

function fakeAuth() {
	const restrictions = new Map();
	const calls = { restrict: [], unrestrict: [] };
	const rows = [
		{ id: 1, provider: PROVIDER, identityKey: "account:eligible-one", credential: { type: "oauth" } },
		{ id: 2, provider: PROVIDER, identityKey: "account:eligible-two", credential: { type: "oauth" } },
		{ id: 3, provider: PROVIDER, identityKey: "account:ineligible", credential: { type: "oauth" } },
		{ id: 4, provider: PROVIDER, credential: { type: "api_key" } },
	];
	const key = (provider, sessionId) => `${provider}/${sessionId}`;
	const auth = {
		calls,
		rows,
		source: { kind: "oauth", concrete: true },
		keys: { source: () => auth.source },
		credentials: { snapshot: () => ({ generation: 1, credentials: rows }) },
		oauth: {
			accounts: (provider, sessionId) => rows
				.filter((row) => row.provider === provider && row.credential.type === "oauth"
					&& auth.sessions.permits(provider, sessionId, row.id))
				.map((row, position) => ({ credentialId: row.id, position, accountId: row.identityKey.slice(8), active: position === 0 })),
		},
		sessions: {
			isRestricted: (provider, sessionId) => restrictions.has(key(provider, sessionId)),
			permits(provider, sessionId, credentialId) {
				const restriction = restrictions.get(key(provider, sessionId));
				const row = rows.find((candidate) => candidate.id === credentialId && candidate.provider === provider);
				return !restriction || (row?.credential.type === "oauth" && restriction.identities.includes(row.identityKey));
			},
			restrict(provider, sessionId, identities) {
				const lease = Symbol("session-restriction");
				restrictions.set(key(provider, sessionId), { lease, identities: [...identities] });
				calls.restrict.push({ provider, sessionId, identities: [...identities], lease });
				return lease;
			},
			unrestrict(provider, sessionId, lease) {
				calls.unrestrict.push({ provider, sessionId, lease });
				if (restrictions.get(key(provider, sessionId))?.lease === lease) restrictions.delete(key(provider, sessionId));
			},
		},
	};
	return auth;
}

function fakeSession(options = {}) {
	const sessionId = options.sessionId ?? `routing-session-${++nextSession}`;
	const agentId = options.agentId ?? `routing-agent-${sessionId}`;
	const auth = options.auth ?? fakeAuth();
	const roles = { ...options.roles };
	const settings = {
		getModelRole: (role) => roles[role],
		getModelRoleProvenance: (role) => Object.hasOwn(options.roles ?? {}, role) ? "user" : "default",
		overrideModelRoles: (values) => Object.assign(roles, values),
	};
	installModelClassDefaults(settings, { get: () => ({}), override() {} });
	const entries = options.entries ?? [];
	const models = options.models ?? MODELS;
	const tools = new Map();
	const commands = new Map();
	const handlers = new Map();
	const calls = { models: [], effort: [], aborts: 0, keyLookups: [], resolutions: [], notifications: [], statuses: [] };
	let current = options.current ?? MECHANICAL;
	let effort = options.effort ?? "high";
	if (!options.auth) for (const row of auth.rows) row.provider = current.provider;
	let closed = false;
	const schema = () => ({
		describe() { return this; },
		int() { return this; },
		min() { return this; },
		optional() { return this; },
	});
	const pi = {
		zod: { object: (spec) => spec, string: schema, number: schema, enum: schema },
		on(event, handler) {
			const registered = handlers.get(event) ?? [];
			registered.push(handler);
			handlers.set(event, registered);
		},
		registerTool: (definition) => tools.set(definition.name, definition),
		registerCommand: (name, definition) => commands.set(name, definition),
		appendEntry: async (customType, data) => { entries.push({ type: "custom", customType, data: structuredClone(data) }); },
		async setModel(selected) {
			calls.models.push(selected);
			if (options.setModel) return options.setModel(selected, (value) => { current = value; });
			current = selected;
			return true;
		},
		getThinkingLevel: () => effort,
		setThinkingLevel(value) {
			calls.effort.push(value);
			if (options.setThinkingLevel) options.setThinkingLevel(value);
			effort = value;
		},
	};
	const ctx = {
		cwd: "/offline-routing-fixture",
		agent: options.parentId
			? { kind: "sub", id: agentId, name: options.agentName ?? "implementation", depth: 1, parentId: options.parentId }
			: { kind: "main", id: agentId, name: "Main", depth: 0 },
		sessionManager: {
			getSessionId: () => sessionId,
			getEntries: () => entries,
			getBranch: () => entries,
			getSessionFile: () => `/offline-routing-fixture/${sessionId}.jsonl`,
		},
		models: {
			current: () => current,
			list: () => models,
			resolve(selector) {
				calls.resolutions.push(selector);
				const value = selector.startsWith("@") ? roles[selector.slice(1)] : selector;
				if (!value) return undefined;
				const base = value.replace(/:(?:off|minimal|low|medium|high|xhigh)$/, "");
				if (base.endsWith("/*")) return models.find((candidate) => candidate.provider === base.slice(0, -2));
				return models.find((candidate) => qualified(candidate) === base || candidate.id === base);
			},
			family: (candidate) => options.family ? options.family(candidate) : candidate.provider === "anthropic" ? "claude" : "gpt",
		},
		modelRegistry: {
			authStorage: auth,
			async getApiKey(selected, id) {
				calls.keyLookups.push({ model: selected, sessionId: id });
				if (options.getApiKey) return options.getApiKey(selected, id);
				return "offline-fixture-key";
			},
		},
		abort: () => { calls.aborts++; },
		isIdle: () => options.isIdle?.() ?? true,
		waitForIdle: async () => { if (options.waitForIdle) await options.waitForIdle(); },
		ui: {
			notify: (message, type) => calls.notifications.push({ message, type }),
			setStatus: (key, value) => calls.statuses.push({ key, value }),
		},
	};
	Object.defineProperty(ctx, "model", { get: () => current });
	const api = installUndertakingRouting(pi, async () => settings, options.routes ? () => options.routes : undefined,
		options.candidates ?? (async (_ctx, _settings, patterns) => patterns));
	async function fire(event, payload = {}, selected = current) {
		const eventContext = event === "before_provider_request"
			? { ...ctx, model: selected, models: { ...ctx.models, current: () => selected } }
			: ctx;
		const results = [];
		for (const handler of handlers.get(event) ?? []) results.push(await handler({ type: event, ...payload }, eventContext));
		return results.find((result) => result !== undefined);
	}
	return {
		ctx, pi, api, auth, roles, entries, calls, sessionId, agentId, tools,
		fire,
		start: () => fire("session_start"),
		setCurrent: (value) => { current = value; },
		selectCurrent(value, transition = {}) {
			current = value;
			entries.push({ type: "model_change", model: qualified(value), resolvedModelIsFallback: false, ...transition });
		},
		setEffort: (value) => { effort = value; },
		describe: () => api.describe(ctx),
		command: (args) => commands.get("undertaking").handler(args, ctx),
		inspection: async () => {
			await commands.get("undertaking").handler("status", ctx);
			return JSON.parse(calls.notifications.at(-1).message);
		},
		route: (params = {}) => {
			const tool = tools.get("daily_driver_route_undertaking");
			assert.ok(tool, "undertaking route tool must be registered");
			return tool.execute("routing-call", { issue: 755, modelClass: "implementation", ...params }, undefined, undefined, ctx);
		},
		finish: (issue = 755) => {
			const tool = tools.get("daily_driver_finish_undertaking");
			assert.ok(tool, "undertaking finish tool must be registered");
			return tool.execute("finish-call", { issue }, undefined, undefined, ctx);
		},
		tool: (toolName, input = {}) => fire("tool_call", { toolCallId: "queued-call", toolName, input }),
		request: () => fire("before_provider_request", { payload: { model: current.id } }),
		helperRequest: (selected) => fire("before_provider_request", { payload: { model: selected.id } }, selected),
		response: (status = 200) => fire("after_provider_response", { status, headers: {} }),
		async assistant(selected = current) {
			if (selected === current) await fire("before_provider_request", { payload: { model: current.id } });
			return fire("assistant_message", { message: { role: "assistant", provider: selected.provider, model: selected.id, content: [{ type: "text", text: "Offline routing response" }] } });
		},
		spawn: (patterns, modelRole = "implementation", spawnKey = `routing-child-${sessionId}`, agent = modelRole) => fire("before_subagent_spawn", { agent, invocationKind: "task", modelRole, patterns, spawnKey }),
		async close() {
			if (!closed) {
				closed = true;
				await fire("session_shutdown");
			}
		},
	};
}

function assertGap(result, pattern) {
	assert.equal(result.isError, true, "unsupported route must return an error tool result");
	assert.notEqual(result.details?.undertaking?.status, "blocked", "preflight failure must not publish a blocked route");
	const reason = result.content?.filter((item) => item.type === "text").map((item) => item.text).join("\n");
	assert.equal(typeof reason, "string");
	assert.ok(reason.length > 0, "blocked route must name the configuration gap");
	if (pattern) assert.match(reason, pattern);
}

function assertAllowed(result) {
	assert.notEqual(result?.block, true, result?.reason);
}

function assertBlocked(result) {
	assert.equal(result?.block, true, "mutating work must remain blocked until execution is verified");
	assert.equal(typeof result.reason, "string");
}

/** Register offline cases that catch undertaking route escapes and premature work. */
export default function registerUndertakingRoutingChecks(check) {
	function routingCheck(name, run) {
		check(`undertaking routing: ${name}`, async () => {
			const sessions = [];
			const create = async (options) => {
				const session = fakeSession(options);
				sessions.push(session);
				const parents = options?.parentId ? sessions.filter((candidate) => candidate.agentId === options.parentId) : [];
				if (parents.length === 1 && options?.handoff !== false) {
					await parents[0].spawn([qualified(session.ctx.models.current())], options.agentName ?? (session.ctx.models.current() === REASONING ? "reasoning" : "implementation"), session.agentId);
				}
				await session.start();
				return session;
			};
			try {
				await run(create);
			} finally {
				for (const session of sessions.reverse()) await session.close();
			}
		});
	}

	// A matching route must not switch models, consume another owner, or await a needless request.
	routingCheck("matching model and effort verify without a switch", async (create) => {
		const s = await create();
		const result = await s.route();
		assert.notEqual(result.isError, true);
		assert.deepEqual(result.details.undertaking, {
			issue: 755, modelClass: "implementation", selectedModel: qualified(MECHANICAL),
			observedModel: qualified(MECHANICAL), status: "verified", capability: "mapped",
		});
		assert.equal(result.details.provider, PROVIDER);
		assert.equal(result.details.authenticationRoute, "oauth");
		assert.equal(s.calls.models.length, 0);
		assert.equal(s.calls.effort.length, 0);
		assert.equal(s.describe().undertaking.status, "verified");
		assert.deepEqual(s.calls.notifications, []);
	});

	// Batch admission must not let a preceding mutation run before the sibling route tool executes.
	for (const routeTool of ["daily_driver_route_undertaking", "write"]) {
		routingCheck(`${routeTool} reserves selection before same-message mutation admission`, async (create) => {
			const s = await create();
			const params = { issue: 755, modelClass: "implementation" };
			const routeArguments = routeTool === "write"
				? { path: "xd://daily_driver_route_undertaking", content: JSON.stringify(params) }
				: params;
			assert.equal(s.describe().undertaking, null);
			await s.fire("assistant_message", { message: {
				role: "assistant", provider: PROVIDER, model: MECHANICAL.id,
				content: [
					{ type: "toolCall", id: "preceding-mutation", name: "bash", arguments: { command: "git worktree add ../task -b task" } },
					{ type: "toolCall", id: "route-selection", name: routeTool, arguments: routeArguments },
				],
			} });
			assertBlocked(await s.tool("bash", { command: "git worktree add ../task -b task" }));
			assertBlocked(await s.tool("task", { tasks: [{ task: "implement" }] }));
			assertAllowed(await s.tool("read", { path: "issue://755" }));
			assertAllowed(await s.tool("daily_driver_get_session"));
			assertAllowed(await s.tool("daily_driver_route_undertaking", params));
			assertAllowed(await s.tool("write", { path: "xd://daily_driver_get_session", content: "{}" }));
			assertAllowed(await s.tool("write", { path: "xd://daily_driver_route_undertaking", content: JSON.stringify(params) }));
			const result = await s.route();
			assert.notEqual(result.isError, true);
			assert.equal(result.details.undertaking.status, "verified", "matching route needs no model switch");
			assertAllowed(await s.tool("bash", { command: "git worktree add ../task -b task" }));
			await s.assistant();
			assertAllowed(await s.tool("bash", { command: "git worktree add ../task -b task" }));
			assert.equal(s.calls.models.length, 0);
		});
	}

	// An accepted setter is not evidence that the next request actually used the selected model.
	routingCheck("upward selection waits for the selected worker response", async (create) => {
		const s = await create();
		const result = await s.route({ modelClass: "reasoning" });
		assert.notEqual(result.isError, true);
		assert.equal(result.details.undertaking.selectedModel, qualified(REASONING));
		assert.equal(result.details.undertaking.status, "pending");
		assert.ok(s.calls.statuses.some(({ value }) => /verif/iu.test(value ?? "")));
		assert.deepEqual(s.calls.notifications, []);
		assert.equal(s.calls.models.length, 1);
		assert.equal(s.calls.models[0], REASONING);
		assertBlocked(await s.tool("write", { path: "implementation.js", content: "change" }));
		await s.request();
		assert.equal(s.calls.aborts, 0);
		assert.equal(s.describe().undertaking.status, "pending");
		await s.response();
		assert.equal(s.describe().undertaking.status, "pending", "provider response can belong to an auxiliary request");
		await s.assistant();
		assert.equal(s.describe().undertaking.status, "verified");
		assertAllowed(await s.tool("write", { path: "implementation.js", content: "change" }));
	});

	// A smaller approved class must select its lower effort rather than retain the costly route.
	routingCheck("downward selection applies the configured model and effort", async (create) => {
		const s = await create({ current: REASONING });
		const result = await s.route({ modelClass: "mechanical" });
		assert.notEqual(result.isError, true);
		assert.equal(result.details.undertaking.selectedModel, qualified(MECHANICAL));
		assert.equal(result.details.undertaking.status, "pending");
		assert.equal(s.calls.models[0], MECHANICAL);
		assert.deepEqual(s.calls.effort, ["low"]);
	});

	// Equal model IDs must not make a changed effort appear already verified.
	routingCheck("effort-only changes remain pending until inference", async (create) => {
		const s = await create();
		const result = await s.route({ modelClass: "mechanical" });
		assert.equal(result.details.undertaking.status, "pending");
		assert.deepEqual(s.calls.effort, ["low"]);
		assertBlocked(await s.tool("task", { tasks: [{ task: "implement" }] }));
		await s.request();
		await s.response();
		await s.assistant();
		assert.equal(s.describe().undertaking.status, "verified");
		assert.ok(s.calls.statuses.some(({ value }) => /verif/iu.test(value ?? "")));
		assert.deepEqual(s.calls.notifications, []);
	});

	// Missing and cleared roles must not silently restore defaults or fabricate a selector.
	for (const selector of [undefined, "", "openai-codex/missing-model:high"]) {
		routingCheck(`unavailable class selector ${String(selector)} reports a gap`, async (create) => {
			const s = await create({ roles: { implementation: selector } });
			assertGap(await s.route());
			assert.equal(s.calls.models.length, 0);
		});
	}

	// A gateway copy must not replace the mapped Flash model on the invoking provider.
	routingCheck("mapped family selects its provider-specific variant", async (create) => {
		const s = await create({ current: DEEPSEEK_PRO, models: [DEEPSEEK_PRO, GATEWAY_FLASH, DEEPSEEK_FLASH], family: deepseekFamily, routes: deepseekRoutes });
		const result = await s.route();
		assert.notEqual(result.isError, true);
		assert.equal(result.details.undertaking.capability, "mapped");
		assert.equal(result.details.undertaking.selectedModel, qualified(DEEPSEEK_FLASH));
		assert.deepEqual(s.calls.models, [DEEPSEEK_FLASH]);
		assert.deepEqual(s.calls.effort, ["low"]);
		await s.request();
		await s.assistant();
		assert.equal(s.describe().undertaking.status, "verified");
	});

	// A shared gateway must not make a different model family an eligible class target.
	routingCheck("gateway provider equality cannot substitute for family equality", async (create) => {
		const routes = [{ referenceModel: qualified(GATEWAY_FLASH), classes: { implementation: `${qualified(GATEWAY_OTHER)}:high` } }];
		const s = await create({ current: GATEWAY_FLASH, models: [GATEWAY_FLASH, GATEWAY_OTHER], family: deepseekFamily, routes });
		assertGap(await s.route(), /family/iu);
		assert.equal(s.calls.models.length, 0);
		await s.request();
		assert.equal(s.calls.aborts, 0);
	});

	// Plugin-installed Codex roles must not interrupt or silently redirect an unmapped family.
	routingCheck("unmapped family continues on the invoking model across reentry and reload", async (create) => {
		const options = { current: DEEPSEEK_PRO, models: [DEEPSEEK_PRO, DEEPSEEK_FLASH, ...MODELS], family: deepseekFamily, effort: "medium" };
		const s = await create(options);
		const result = await s.route();
		assert.notEqual(result.isError, true);
		assert.equal(result.details.undertaking.status, "verified");
		assert.equal(result.details.undertaking.capability, "unverified");
		assert.equal(result.details.undertaking.selectedModel, qualified(DEEPSEEK_PRO));
		assert.match(result.details.undertaking.warning, /family\s+deepseek/iu);
		assert.match(result.details.undertaking.warning, /implementation/iu);
		assert.match(result.details.undertaking.warning, /deepseek-go\/deepseek-v4-pro/iu);
		assert.equal(s.calls.notifications.length, 1);
		assert.equal(s.calls.notifications[0].type, "warning");
		assert.deepEqual(s.calls.models, []);
		assert.deepEqual(s.calls.effort, []);
		assertAllowed(await s.tool("task", { tasks: [{ task: "implement" }] }));
		await s.request();
		assert.equal(s.calls.aborts, 0);
		assert.notEqual((await s.route()).isError, true);
		assert.equal(s.calls.notifications.length, 1);
		assert.equal(s.describe().undertaking.capability, "unverified");
		assert.equal(s.calls.resolutions.some((value) => value.startsWith("@")), false);
		assertBlocked(await s.spawn([qualified(DEEPSEEK_FLASH)]));
		const child = await create({ ...options, auth: s.auth, parentId: s.agentId });
		await child.request();
		await child.assistant();
		assert.equal(child.describe().undertaking.capability, "unverified");
		assert.equal(child.describe().undertaking.selectedModel, qualified(DEEPSEEK_PRO));
		assert.equal(child.calls.aborts, 0);
		const entries = structuredClone(s.entries);
		await s.close();
		const resumed = await create({ ...options, auth: s.auth, sessionId: s.sessionId, agentId: s.agentId, entries });
		await resumed.request();
		await resumed.assistant();
		assert.equal(resumed.describe().undertaking.capability, "unverified");
		assert.equal(resumed.describe().undertaking.selectedModel, qualified(DEEPSEEK_PRO));
		assert.equal(resumed.calls.aborts, 0);
		assert.notEqual((await resumed.route()).isError, true);
		assert.equal(resumed.calls.notifications.length, 0);
		assert.deepEqual(resumed.calls.models, []);
	});

	// Explicit operator mappings must be honored, but must not authorize an incompatible provider.
	routingCheck("explicit family assignment selects its variant and rejects another provider", async (create) => {
		const options = { current: DEEPSEEK_PRO, models: [DEEPSEEK_PRO, DEEPSEEK_FLASH, GATEWAY_FLASH, ...MODELS], family: deepseekFamily };
		const good = await create({ ...options, roles: { implementation: `${qualified(DEEPSEEK_FLASH)}:low` } });
		const selected = await good.route();
		assert.notEqual(selected.isError, true);
		assert.equal(selected.details.undertaking.capability, "mapped");
		assert.deepEqual(good.calls.models, [DEEPSEEK_FLASH]);
		const bad = await create({ ...options, roles: { implementation: `${qualified(GATEWAY_FLASH)}:low` } });
		assertGap(await bad.route(), /provider/iu);
		assert.deepEqual(bad.calls.models, []);
		await bad.request();
		assert.equal(bad.calls.aborts, 0);
	});

	// Failed preflight must not poison inference or retain a lease when the operator corrects the route.
	routingCheck("preflight failure permits manual model changes and a corrective retry", async (create) => {
		const s = await create({ roles: { implementation: "" } });
		assertGap(await s.route(), /class|route/iu);
		assert.equal(s.describe().undertaking, null);
		assertBlocked(await s.tool("task", { tasks: [{ task: "implement" }] }));
		await s.request();
		s.setCurrent(REASONING);
		await s.request();
		assert.equal(s.calls.aborts, 0);
		assert.equal(s.auth.calls.restrict.length, 0);
		assert.equal(s.auth.sessions.isRestricted(PROVIDER, s.sessionId), false);
		s.roles.implementation = `${qualified(MECHANICAL)}:high`;
		const corrected = await s.route();
		assert.notEqual(corrected.isError, true);
		assert.equal(corrected.details.undertaking.status, "pending");
		await s.request();
		await s.assistant();
		assertAllowed(await s.tool("task", { tasks: [{ task: "implement" }] }));
	});

	// Direct tool callers must not bypass the finite class set by skipping schema validation.
	routingCheck("unknown model class cannot select arbitrary models", async (create) => {
		const s = await create();
		assertGap(await s.route({ modelClass: "unrestricted" }));
		assert.equal(s.calls.models.length, 0);
	});

	// A rejected or throwing model setter must not let implementation continue on the old route.
	for (const failure of ["false", "throw"]) {
		routingCheck(`model setter ${failure} blocks work without blocking conversation`, async (create) => {
			const s = await create({ setModel: async () => {
				if (failure === "throw") throw new Error("fixture model setter failure");
				return false;
			} });
			assertGap(await s.route({ modelClass: "reasoning" }));
			assertBlocked(await s.tool("write", { path: "implementation.js", content: "change" }));
			assert.equal(s.ctx.models.current(), MECHANICAL);
			assert.equal(s.pi.getThinkingLevel(), "high");
			assert.equal(s.auth.sessions.isRestricted(PROVIDER, s.sessionId), false);
			await s.request();
			assert.equal(s.calls.aborts, 0);
		});
	}

	// A setter that changes the model before rejecting must not leave recovery on the unintended model.
	routingCheck("rejected model switch restores the invoking model", async (create) => {
		const s = await create({ setModel: async (selected, update) => {
			update(selected);
			return selected === MECHANICAL;
		} });
		assertGap(await s.route({ modelClass: "reasoning" }));
		assert.deepEqual(s.calls.models, [REASONING, MECHANICAL]);
		assert.equal(s.ctx.models.current(), MECHANICAL);
		assert.equal(s.auth.sessions.isRestricted(PROVIDER, s.sessionId), false);
		assertBlocked(await s.tool("task", { tasks: [{ task: "implement" }] }));
		await s.request();
		assert.equal(s.calls.aborts, 0);
	});

	// An effort setter failure must not verify a model with the wrong reasoning budget.
	routingCheck("effort setter failure is a configuration gap", async (create) => {
		const s = await create({ setThinkingLevel: () => { throw new Error("fixture effort setter failure"); } });
		assertGap(await s.route({ modelClass: "mechanical" }));
		assertBlocked(await s.tool("write", { path: "implementation.js", content: "change" }));
		assert.equal(s.ctx.models.current(), MECHANICAL);
		assert.equal(s.pi.getThinkingLevel(), "high");
		assert.equal(s.auth.sessions.isRestricted(PROVIDER, s.sessionId), false);
		await s.request();
		assert.equal(s.calls.aborts, 0);
	});

	// A failed replacement must not discard the previous valid owner or prevent its inference.
	routingCheck("failed preflight preserves a verified undertaking", async (create) => {
		const s = await create();
		assert.notEqual((await s.route()).isError, true);
		const previous = s.describe().undertaking;
		s.roles.reasoning = "";
		assertGap(await s.route({ modelClass: "reasoning" }), /class|route/iu);
		assert.deepEqual(s.describe().undertaking, previous);
		assert.equal(s.auth.calls.restrict.length, 1);
		assert.equal(s.auth.calls.unrestrict.length, 0);
		assertBlocked(await s.tool("task", { tasks: [{ task: "implement" }] }));
		await s.request();
		assert.equal(s.calls.aborts, 0);
		s.roles.reasoning = `${qualified(REASONING)}:high`;
		assert.notEqual((await s.route({ modelClass: "reasoning" })).isError, true);
		await s.request();
		await s.assistant();
		assertAllowed(await s.tool("task", { tasks: [{ task: "implement" }] }));
	});

	// A failed effort switch after model selection must restore the invoking identity before recovery.
	routingCheck("effort failure restores an already switched model", async (create) => {
		const s = await create({ current: REASONING, setThinkingLevel: () => { throw new Error("fixture effort setter failure"); } });
		assertGap(await s.route({ modelClass: "mechanical" }));
		assert.deepEqual(s.calls.models, [MECHANICAL, REASONING]);
		assert.equal(s.ctx.models.current(), REASONING);
		assert.equal(s.pi.getThinkingLevel(), "high");
		assert.equal(s.auth.sessions.isRestricted(PROVIDER, s.sessionId), false);
		assertBlocked(await s.tool("task", { tasks: [{ task: "implement" }] }));
		await s.request();
		assert.equal(s.calls.aborts, 0);
	});

	// Reload must not certify a partially applied switch whose model rollback also failed.
	routingCheck("failed restoration remains recovery-only after reload", async (create) => {
		const s = await create({
			effort: "low",
			setModel: async (selected, update) => {
				if (selected === MECHANICAL) throw new Error("fixture model restoration failure");
				update(selected);
				return true;
			},
			setThinkingLevel: () => { throw new Error("fixture effort setter failure"); },
		});
		const failed = await s.route({ modelClass: "reasoning" });
		assert.equal(failed.isError, true);
		assert.equal(failed.details.undertaking.status, "blocked");
		assert.equal(s.ctx.models.current(), REASONING);
		const entries = structuredClone(s.entries);
		await s.close();
		const resumed = await create({
			auth: s.auth, sessionId: s.sessionId, agentId: s.agentId,
			entries, current: REASONING, effort: "low",
		});
		await resumed.request();
		await resumed.assistant();
		assert.equal(resumed.calls.aborts, 0, "recovery must still permit explanation");
		assertBlocked(await resumed.tool("write", { path: "implementation.js", content: "change" }));
		assert.equal(resumed.describe().undertaking.status, "blocked");
		assert.notEqual((await resumed.route({ modelClass: "reasoning" })).isError, true);
		await resumed.request();
		await resumed.assistant();
		assert.equal(resumed.pi.getThinkingLevel(), "high");
		assertAllowed(await resumed.tool("write", { path: "implementation.js", content: "change" }));
	});

	// Same-provider routing must not cross a backend, transport, header route, or model family.
	for (const [name, target, family] of [
		["backend", model(MECHANICAL.id, { baseUrl: "https://other.example.invalid/v1" })],
		["transport", model(MECHANICAL.id, { api: "openai-completions" })],
		["route header", model(MECHANICAL.id, { headers: { "x-routing-region": "other-region" } })],
		["provider", model(MECHANICAL.id, { provider: "other-provider" })],
		["family", model("different-family"), (candidate) => candidate.id === "different-family" ? "other-family" : "gpt"],
	]) {
		routingCheck(`incompatible ${name} is rejected before selection`, async (create) => {
			const s = await create({ models: [target, MECHANICAL], roles: { implementation: `${qualified(target)}:high` }, family });
			assertGap(await s.route());
			assert.equal(s.calls.models.length, 0);
		});
	}

	// Queued work must not outrun an asynchronous model setter before the pending state is stored.
	routingCheck("pending state blocks mutations while the model setter is unresolved", async (create) => {
		const entered = deferred();
		const release = deferred();
		const s = await create({ setModel: async (selected, update) => {
			entered.resolve();
			await release.promise;
			update(selected);
			return true;
		} });
		const routing = s.route({ modelClass: "reasoning" });
		await Promise.race([entered.promise, routing.then(() => { throw new Error("Route returned before invoking the model setter"); })]);
		try {
			for (const [toolName, input] of [
				["write", { path: "implementation.js", content: "change" }],
				["edit", { path: "implementation.js", oldText: "old", newText: "new" }],
				["bash", { command: "git worktree add ../task -b task" }],
				["bash", { command: "gh issue comment 755 --body claimed" }],
				["task", { tasks: [{ task: "implement" }] }],
			]) assertBlocked(await s.tool(toolName, input));
			assertBlocked(await s.spawn([qualified(REASONING)]));
			assertAllowed(await s.tool("read", { path: "issue://755" }));
			assertAllowed(await s.tool("daily_driver_get_session"));
			assertAllowed(await s.tool("daily_driver_route_undertaking", { issue: 755, modelClass: "reasoning" }));
		} finally {
			release.resolve();
			await routing;
		}
	});

	// An unrelated or failed response must not certify that a selected model executed successfully.
	routingCheck("response without a matching request cannot release pending work", async (create) => {
		const s = await create();
		await s.route({ modelClass: "reasoning" });
		await s.response();
		assert.notEqual(s.describe().undertaking.status, "verified");
		assertBlocked(await s.tool("write", { path: "implementation.js", content: "change" }));
	});

	// Auxiliary inference must not verify a pending worker or have its unrelated role rewritten.
	routingCheck("independent helper inference neither routes nor verifies the worker", async (create) => {
		const s = await create();
		await s.route({ modelClass: "reasoning" });
		await s.helperRequest(FOREIGN);
		await s.response();
		await s.assistant(FOREIGN);
		assert.equal(s.calls.aborts, 0);
		assert.equal(s.describe().undertaking.status, "pending");
		assertBlocked(await s.tool("write", { path: "implementation.js", content: "change" }));
		assert.equal(s.calls.models.length, 1);
		await s.request();
		await s.assistant();
		assert.equal(s.describe().undertaking.status, "verified");
	});

	// Rejected inference must not prevent the selected worker from explaining or repairing the failure.
	for (const [name, drift] of [
		["class", MECHANICAL],
		["provider", model(REASONING.id, { provider: "other-provider" })],
		["frontier", FRONTIER],
		["backend", model(REASONING.id, { baseUrl: "https://other.example.invalid/v1" })],
		["transport", model(REASONING.id, { api: "openai-completions" })],
		["headers", model(REASONING.id, { headers: { "x-routing-region": "other-region" } })],
	]) {
		routingCheck(`${name} request drift aborts without poisoning recovery`, async (create) => {
			const s = await create();
			await s.route({ modelClass: "reasoning" });
			const selected = structuredClone(s.describe().undertaking);
			s.setCurrent(drift);
			await assert.rejects(s.request());
			assert.equal(s.calls.aborts, 1);
			assert.deepEqual(s.describe().undertaking, selected);
			s.setCurrent(REASONING);
			await s.request();
			await s.assistant();
			assert.equal(s.calls.aborts, 1, "the restored worker must reach inference");
			assertAllowed(await s.tool("bash", { command: "gh issue comment 755 --body-file recovery.md" }));
		});
	}

	// Refusing an effort mismatch must not require a process restart after the configured effort is restored.
	routingCheck("same-model effort drift aborts before inference", async (create) => {
		const s = await create();
		await s.route();
		s.setEffort("low");
		await assert.rejects(s.request(), /effort/iu);
		assert.equal(s.calls.aborts, 1);
		s.setEffort("high");
		await s.request();
		assert.equal(s.calls.aborts, 1, "restoring the effort must allow the selected worker to continue");
		assertAllowed(await s.tool("write", { path: "recovery.md", content: "Selected route restored." }));
	});

	// A rejected authentication change must not poison the unchanged route after its source is restored.
	routingCheck("authentication source drift explicitly aborts", async (create) => {
		const s = await create();
		await s.route();
		const originalSource = s.auth.source;
		s.auth.source = { kind: "config", concrete: true };
		await assert.rejects(s.request());
		assert.equal(s.calls.aborts, 1);
		s.auth.source = originalSource;
		await s.request();
		assert.equal(s.calls.aborts, 1, "the original authentication route must remain usable");
		assertAllowed(await s.tool("write", { path: "recovery.md", content: "Authentication route restored." }));
	});

	// Supported non-OAuth routes must remain usable without pretending to own an OAuth pool.
	routingCheck("configured key route preserves its source without installing an OAuth lease", async (create) => {
		const auth = fakeAuth();
		auth.source = { kind: "config", concrete: true };
		const s = await create({ auth });
		const result = await s.route();
		assert.notEqual(result.isError, true);
		assert.equal(result.details.authenticationRoute, "config");
		assert.equal(auth.calls.restrict.length, 0);
		await s.request();
		assert.equal(s.calls.aborts, 0);
	});

	// Unknown authentication provenance must not be reported as preserved merely because a key exists.
	routingCheck("missing authentication evidence fails closed", async (create) => {
		const auth = fakeAuth();
		auth.source = undefined;
		const s = await create({ auth });
		assertGap(await s.route());
	});

	// Unsupported controls and transports must not claim that an unenforced route is safe.
	for (const control of ["setModel", "setThinkingLevel"]) {
		routingCheck(`missing ${control} reports a configuration gap`, async (create) => {
			const s = await create();
			s.pi[control] = undefined;
			assertGap(await s.route({ modelClass: control === "setModel" ? "reasoning" : "mechanical" }));
			assertBlocked(await s.tool("write", { path: "implementation.js", content: "change" }));
		});
	}

	// Credentials cannot make a transport safe when the runtime has no request-abort contract for it.
	routingCheck("unsupported provider transport fails closed", async (create) => {
		const unsupported = model(MECHANICAL.id, { api: "unsupported-fixture-transport" });
		const s = await create({ current: unsupported, models: [unsupported] });
		assertGap(await s.route());
	});

	// An exhausted original route must not be accepted on the assumption that another key can serve.
	routingCheck("unavailable original credentials report a route gap", async (create) => {
		const s = await create({ getApiKey: async () => undefined });
		assertGap(await s.route());
		assert.equal(s.calls.models.length, 0);
	});

	// OAuth refresh changes secret bytes, not the non-secret route that an undertaking owns.
	routingCheck("OAuth credential refresh preserves an allowed route", async (create) => {
		const s = await create();
		await s.route();
		s.auth.rows[0].credential = { type: "oauth", access: "refreshed-fixture-token", refresh: "refreshed-fixture-refresh" };
		await s.request();
		assert.equal(s.calls.aborts, 0);
		assert.equal(s.describe().undertaking.status, "verified");
	});

	// Pool ownership must remain with the operator when an existing restriction already protects it.
	routingCheck("operator-owned pool is neither replaced nor released", async (create) => {
		const auth = fakeAuth();
		const sessionId = `operator-pool-${++nextSession}`;
		const lease = auth.sessions.restrict(PROVIDER, sessionId, ["account:eligible-one"]);
		const s = await create({ auth, sessionId });
		await s.route();
		assert.equal(auth.calls.restrict.length, 1);
		assert.equal(auth.sessions.permits(PROVIDER, sessionId, 1), true);
		assert.equal(auth.sessions.permits(PROVIDER, sessionId, 2), false);
		await s.close();
		assert.equal(auth.calls.unrestrict.length, 0);
		assert.equal(auth.sessions.isRestricted(PROVIDER, sessionId), true);
		auth.sessions.unrestrict(PROVIDER, sessionId, lease);
	});

	// Normal shutdown must release an extension-owned lease instead of constraining the next session.
	routingCheck("shutdown releases an extension-owned OAuth restriction", async (create) => {
		const s = await create();
		await s.route();
		const owned = s.auth.calls.restrict[0];
		assert.ok(owned);
		await s.close();
		assert.equal(s.auth.sessions.isRestricted(PROVIDER, s.sessionId), false);
		assert.deepEqual(s.auth.calls.unrestrict, [{ provider: PROVIDER, sessionId: s.sessionId, lease: owned.lease }]);
	});

	// A stale extension owner must not release a newer operator lease at session shutdown.
	routingCheck("shutdown only releases its own current restriction lease", async (create) => {
		const s = await create();
		await s.route();
		assert.equal(s.auth.calls.restrict.length, 1);
		assert.equal(s.auth.calls.restrict[0].sessionId, s.sessionId);
		assert.equal(s.auth.sessions.permits(PROVIDER, s.sessionId, 4), false);
		const newer = s.auth.sessions.restrict(PROVIDER, s.sessionId, ["account:eligible-two"]);
		await s.close();
		assert.equal(s.auth.sessions.isRestricted(PROVIDER, s.sessionId), true);
		assert.equal(s.auth.sessions.permits(PROVIDER, s.sessionId, 1), false);
		s.auth.sessions.unrestrict(PROVIDER, s.sessionId, newer);
	});

	// Completion must remove the worker policy and batch reservation without changing the model.
	routingCheck("completion releases its lease, clears selection, and persists a tombstone", async (create) => {
		const s = await create();
		await s.route();
		const owned = s.auth.calls.restrict[0];
		await s.fire("assistant_message", { message: {
			role: "assistant", provider: PROVIDER, model: MECHANICAL.id,
			content: [{ type: "toolCall", id: "reserved-route", name: "daily_driver_route_undertaking",
				arguments: { issue: 755, modelClass: "implementation" } }],
		} });
		assertBlocked(await s.tool("write", { path: "implementation.js", content: "change" }));
		assertAllowed(await s.tool("daily_driver_finish_undertaking", { issue: 755 }));
		assertAllowed(await s.tool("write", { path: "xd://daily_driver_finish_undertaking", content: '{"issue":755}' }));
		const result = await s.finish();
		assert.notEqual(result.isError, true);
		assert.equal(result.details.undertaking, null);
		assert.equal(s.describe().undertaking, null);
		assert.deepEqual(s.entries.at(-1), {
			type: "custom", customType: "daily-driver-undertaking-route",
			data: { schema: 2, issue: 755, lifecycle: "completed" },
		});
		assert.deepEqual(s.auth.calls.unrestrict, [{ provider: PROVIDER, sessionId: s.sessionId, lease: owned.lease }]);
		assert.equal(s.auth.sessions.isRestricted(PROVIDER, s.sessionId), false);
		assert.equal(s.ctx.models.current(), MECHANICAL);
		assert.equal(s.calls.models.length, 0);
		assert.equal(s.calls.effort.length, 0);
		assertAllowed(await s.tool("write", { path: "implementation.js", content: "change" }));
		s.setCurrent(FOREIGN);
		await s.request();
		assert.equal(s.calls.aborts, 0, "completed routes must not constrain later inference");
		await s.close();
		assert.equal(s.auth.calls.unrestrict.length, 1, "shutdown must not release the completed lease twice");
	});

	// A pending model switch must not retain ownership after the undertaking finishes.
	routingCheck("completion clears a pending route before worker inference", async (create) => {
		const s = await create();
		await s.route({ modelClass: "reasoning" });
		assert.equal(s.describe().undertaking.status, "pending");
		assertAllowed(await s.tool("daily_driver_finish_undertaking", { issue: 755 }));
		assert.notEqual((await s.finish()).isError, true);
		assert.equal(s.describe().undertaking, null);
		assert.equal(s.auth.sessions.isRestricted(PROVIDER, s.sessionId), false);
		assertAllowed(await s.tool("write", { path: "implementation.js", content: "change" }));
		assert.notEqual((await s.route({ issue: 756, modelClass: "reasoning" })).isError, true);
		assert.equal(s.describe().undertaking.issue, 756);
		assert.equal(s.describe().undertaking.status, "verified");
	});

	// A rejected finish must not clear the current owner's policy or release its OAuth restriction.
	routingCheck("finishing another issue preserves the verified owner", async (create) => {
		const s = await create();
		await s.route();
		const before = s.describe().undertaking;
		const entries = structuredClone(s.entries);
		const result = await s.finish(756);
		assert.equal(result.isError, true);
		assert.deepEqual(result.details.undertaking, before);
		assert.deepEqual(s.describe().undertaking, before);
		assert.deepEqual(s.entries, entries);
		assert.equal(s.auth.calls.unrestrict.length, 0);
		assert.equal(s.auth.sessions.isRestricted(PROVIDER, s.sessionId), true);
		await s.request();
		assert.equal(s.calls.aborts, 0);
		assertAllowed(await s.tool("write", { path: "implementation.js", content: "change" }));
	});

	// Selecting another issue must report ownership conflict without poisoning the verified route.
	routingCheck("selecting another issue preserves the verified owner", async (create) => {
		const s = await create();
		await s.route();
		const before = s.describe().undertaking;
		const entries = structuredClone(s.entries);
		const result = await s.route({ issue: 756, modelClass: "reasoning" });
		assert.equal(result.isError, true);
		assert.deepEqual(result.details.undertaking, before);
		assert.deepEqual(s.describe().undertaking, before);
		assert.deepEqual(s.entries, entries);
		assert.equal(s.calls.models.length, 0);
		assert.equal(s.auth.calls.restrict.length, 1);
		assert.equal(s.auth.calls.unrestrict.length, 0);
		await s.request();
		assert.equal(s.calls.aborts, 0);
		assertAllowed(await s.tool("write", { path: "implementation.js", content: "change" }));
	});

	// A completed session must accept a new issue and still require evidence for its model switch.
	routingCheck("completion permits a new issue to select and verify its own route", async (create) => {
		const s = await create();
		await s.route({ modelClass: "reasoning" });
		await s.request();
		await s.assistant();
		assert.notEqual((await s.finish()).isError, true);
		assert.equal(s.ctx.models.current(), REASONING, "completion must not restore an earlier model");
		const result = await s.route({ issue: 756 });
		assert.notEqual(result.isError, true);
		assert.equal(result.details.undertaking.issue, 756);
		assert.equal(result.details.undertaking.selectedModel, qualified(MECHANICAL));
		assert.equal(result.details.undertaking.status, "pending");
		assert.equal(s.auth.calls.restrict.length, 2, "the new undertaking needs a new owned lease");
		assertBlocked(await s.tool("write", { path: "implementation.js", content: "change" }));
		await s.request();
		await s.assistant();
		assert.equal(s.describe().undertaking.status, "verified");
		assertAllowed(await s.tool("write", { path: "implementation.js", content: "change" }));
	});

	// Recovery must honor the latest completion record instead of reviving an earlier saved policy.
	routingCheck("completion tombstone prevents route and lease recovery", async (create) => {
		const first = await create();
		await first.route();
		await first.finish();
		const entries = structuredClone(first.entries);
		await first.close();
		const resumed = await create({
			auth: first.auth, sessionId: first.sessionId, agentId: first.agentId,
			entries, current: REASONING,
		});
		assert.equal(resumed.describe().undertaking, null);
		assert.equal(resumed.auth.sessions.isRestricted(PROVIDER, resumed.sessionId), false);
		assert.equal(resumed.auth.calls.restrict.length, 1);
		await resumed.request();
		assert.equal(resumed.calls.aborts, 0);
		assertAllowed(await resumed.tool("write", { path: "implementation.js", content: "change" }));
		assert.notEqual((await resumed.route({ issue: 756, modelClass: "reasoning" })).isError, true);
		assert.equal(resumed.describe().undertaking.issue, 756);
		assert.equal(resumed.describe().undertaking.status, "verified");
	});

	// Completion must not remove an operator lease, whether it predates or replaces our own lease.
	for (const timing of ["existing", "replacement"]) {
		routingCheck(`completion preserves an ${timing} operator OAuth restriction`, async (create) => {
			const auth = fakeAuth();
			const sessionId = `operator-completion-${++nextSession}`;
			let operator;
			if (timing === "existing") operator = auth.sessions.restrict(PROVIDER, sessionId, ["account:eligible-one"]);
			const s = await create({ auth, sessionId });
			await s.route();
			const owned = timing === "replacement" ? auth.calls.restrict[0] : undefined;
			if (timing === "replacement") operator = auth.sessions.restrict(PROVIDER, sessionId, ["account:eligible-two"]);
			assert.notEqual((await s.finish()).isError, true);
			assert.equal(s.describe().undertaking, null);
			assert.equal(auth.sessions.isRestricted(PROVIDER, sessionId), true);
			assert.equal(auth.sessions.permits(PROVIDER, sessionId, timing === "existing" ? 1 : 2), true);
			assert.equal(auth.sessions.permits(PROVIDER, sessionId, timing === "existing" ? 2 : 1), false);
			assert.deepEqual(auth.calls.unrestrict, owned ? [{ provider: PROVIDER, sessionId, lease: owned.lease }] : []);
			await s.close();
			assert.equal(auth.sessions.isRestricted(PROVIDER, sessionId), true);
			auth.sessions.unrestrict(PROVIDER, sessionId, operator);
		});
	}

	// Worker specialization must survive routing instead of every child becoming an implementor.
	routingCheck("compatible reasoning worker selection preserves specialization", async (create) => {
		const s = await create();
		await s.route();
		const decision = await s.spawn([`${qualified(REASONING)}:high`], "reasoning");
		assertAllowed(decision);
		assert.equal(decision?.model, undefined, "compatible explicit worker patterns must not be replaced");
	});

	// A compatible first worker choice must not hide an incompatible fallback or wildcard expansion.
	for (const patterns of [
		[qualified(REASONING), qualified(FOREIGN)],
		[qualified(REASONING), qualified(FRONTIER)],
		[`${PROVIDER}/*`],
	]) {
		routingCheck(`worker fallback is checked across ${patterns.join(",")}`, async (create) => {
			const s = await create();
			await s.route();
			assertBlocked(await s.spawn(patterns));
		});
	}

	// An incompatible worker role must not bypass the policy or be silently replaced.
	for (const agent of ["implementation", "reasoning", "task"]) {
		routingCheck(`incompatible ${agent} worker cannot escape its undertaking`, async (create) => {
			const s = await create({ roles: { [agent]: qualified(FOREIGN) } });
			await s.route({ modelClass: "mechanical" });
			await s.assistant();
			assert.equal(s.describe().undertaking.status, "verified");
			const decision = await s.spawn([qualified(FOREIGN)], agent);
			assertBlocked(decision);
			assert.equal(decision.model, undefined);
		});
	}

	// Independent specialists must retain their configured models rather than inherit worker constraints.
	for (const agentName of ["reviewer", "scout", "security-reviewer", "seance"]) {
		routingCheck(`${agentName} admission and startup preserve its independent route`, async (create) => {
			const parent = await create({ roles: { [agentName]: qualified(FOREIGN) } });
			await parent.route();
			const childId = `specialist-${agentName}-${++nextSession}`;
			const decision = await parent.spawn([qualified(FOREIGN)], agentName, childId);
			assertAllowed(decision);
			assert.equal(decision?.model, undefined);
			const restrictions = parent.auth.calls.restrict.length;
			const child = await create({
				auth: parent.auth, parentId: parent.agentId, agentId: childId, agentName,
				current: FOREIGN, handoff: false,
			});
			assert.equal(child.describe().undertaking, null);
			assert.equal(child.auth.sessions.isRestricted(PROVIDER, child.sessionId), false);
			assert.equal(child.auth.calls.restrict.length, restrictions, "specialists must not acquire worker leases");
			assert.deepEqual(child.entries, [], "specialists must not persist an inherited worker route");
			assert.equal(child.calls.models.length, 0);
			await child.request();
			assert.equal(child.calls.aborts, 0);
			assertAllowed(await child.tool("write", { path: "review.txt", content: "Review result" }));
			assert.equal(parent.describe().undertaking.status, "verified");
		});
	}

	// A specialist name without a correlated handoff must not bypass child startup authorization.
	routingCheck("specialist startup without a handoff fails closed", async (create) => {
		const parent = await create();
		await parent.route();
		const child = await create({
			auth: parent.auth, parentId: parent.agentId, agentName: "reviewer",
			current: FOREIGN, handoff: false,
		});
		assert.equal(child.describe().undertaking.status, "blocked");
		await assert.rejects(child.request());
		assert.equal(child.calls.aborts, 2);
	});

	// A consumed exemption must not authorize a second child that reuses the same process-local ID.
	routingCheck("specialist startup consumes its handoff exemption", async (create) => {
		const parent = await create();
		await parent.route();
		const child = await create({
			auth: parent.auth, parentId: parent.agentId, agentName: "reviewer", current: FOREIGN,
		});
		assert.equal(child.describe().undertaking, null);
		await child.close();
		const repeated = await create({
			auth: parent.auth, parentId: parent.agentId, agentId: child.agentId,
			agentName: "reviewer", current: FOREIGN, handoff: false,
		});
		assert.equal(repeated.describe().undertaking.status, "blocked");
		await assert.rejects(repeated.request());
	});

	// A valid specialist handoff must not waive the shared-auth and exact-parent checks.
	for (const mismatch of ["authentication scope", "parent identity"]) {
		routingCheck(`specialist handoff rejects another ${mismatch}`, async (create) => {
			const parent = await create();
			await parent.route();
			const childId = `foreign-specialist-${++nextSession}`;
			assertAllowed(await parent.spawn([qualified(FOREIGN)], "reviewer", childId));
			const child = await create({
				auth: mismatch === "authentication scope" ? fakeAuth() : parent.auth,
				parentId: mismatch === "parent identity" ? `other-parent-${++nextSession}` : parent.agentId,
				agentId: childId, agentName: "reviewer", current: FOREIGN, handoff: false,
			});
			assert.equal(child.describe().undertaking.status, "blocked");
			await assert.rejects(child.request());
			assert.equal(child.calls.aborts, 2);
		});
	}

	// A previously admitted specialist must not start after its parent loses verification.
	routingCheck("specialist startup requires a still-verified parent", async (create) => {
		const parent = await create();
		await parent.route();
		const childId = `pending-parent-specialist-${++nextSession}`;
		assertAllowed(await parent.spawn([qualified(FOREIGN)], "reviewer", childId));
		await parent.route({ modelClass: "reasoning" });
		const child = await create({
			auth: parent.auth, parentId: parent.agentId, agentId: childId,
			agentName: "reviewer", current: FOREIGN, handoff: false,
		});
		assert.equal(child.describe().undertaking.status, "blocked");
		await assert.rejects(child.request());
	});

	// A child must install the parent's eligible OAuth pool before its first inference can escape.
	routingCheck("child startup inherits a unique parent policy before inference", async (create) => {
		const parent = await create();
		await parent.route();
		const child = await create({ auth: parent.auth, parentId: parent.agentId, current: REASONING });
		assert.equal(child.auth.sessions.isRestricted(PROVIDER, child.sessionId), true);
		assert.equal(child.auth.sessions.permits(PROVIDER, child.sessionId, 4), false);
		await child.request();
		assert.equal(child.calls.aborts, 0);
		assert.equal(child.describe().undertaking.issue, 755);
	});

	// A child must not borrow OAuth identities excluded by its parent's operator-owned pool.
	routingCheck("child inherits only the parent's eligible OAuth identities", async (create) => {
		const auth = fakeAuth();
		const sessionId = `eligible-parent-${++nextSession}`;
		const lease = auth.sessions.restrict(PROVIDER, sessionId, ["account:eligible-one"]);
		const parent = await create({ auth, sessionId });
		await parent.route();
		const child = await create({ auth, parentId: parent.agentId, current: REASONING });
		assert.equal(auth.sessions.permits(PROVIDER, child.sessionId, 1), true);
		assert.equal(auth.sessions.permits(PROVIDER, child.sessionId, 2), false);
		assert.equal(auth.sessions.permits(PROVIDER, child.sessionId, 3), false);
		assert.equal(auth.sessions.permits(PROVIDER, child.sessionId, 4), false);
		const entries = structuredClone(child.entries);
		await child.close();
		await parent.close();
		auth.sessions.unrestrict(PROVIDER, sessionId, lease);
		const resumed = await create({ auth, sessionId: child.sessionId, agentId: child.agentId, parentId: parent.agentId, entries, current: REASONING });
		assert.equal(auth.sessions.permits(PROVIDER, resumed.sessionId, 1), true);
		assert.equal(auth.sessions.permits(PROVIDER, resumed.sessionId, 2), false, "reload must not widen the inherited pool");
		assert.equal(auth.sessions.permits(PROVIDER, resumed.sessionId, 4), false);
	});

	// Parent IDs are local labels, so two roots named Main must not lend each other authorization.
	routingCheck("ambiguous parent identity fails closed without cross-root binding", async (create) => {
		const auth = fakeAuth();
		const repeatedId = `ambiguous-main-${++nextSession}`;
		const first = await create({ auth, agentId: repeatedId });
		const second = await create({ auth, agentId: repeatedId });
		await first.route();
		await second.route({ issue: 756 });
		const child = await create({ auth, parentId: repeatedId });
		assert.equal(child.describe().undertaking.status, "blocked");
		await assert.rejects(child.request());
		assert.equal(child.calls.aborts, 2, "startup and incompatible inference each abort");
	});

	// One auth store must not let a child's parent label bind policy in a different auth store.
	routingCheck("child cannot inherit a foreign root's authentication policy", async (create) => {
		const parent = await create();
		await parent.route();
		const child = await create({ parentId: parent.agentId });
		assert.equal(child.describe().undertaking.status, "blocked");
		await assert.rejects(child.request());
		assert.equal(child.calls.aborts, 2, "startup and incompatible inference each abort");
	});

	// Failed child constraint installation must never leave the child free to infer without a policy.
	routingCheck("child restriction failure blocks inference and mutations", async (create) => {
		const parent = await create();
		await parent.route();
		const original = parent.auth.sessions.restrict;
		parent.auth.sessions.restrict = () => { throw new Error("fixture child restriction failure"); };
		try {
			const child = await create({ auth: parent.auth, parentId: parent.agentId });
			assert.equal(child.describe().undertaking.status, "blocked");
			await assert.rejects(child.request());
			assert.equal(child.calls.aborts, 2, "startup and incompatible inference each abort");
			assertBlocked(await child.tool("write", { path: "implementation.js", content: "change" }));
		} finally {
			parent.auth.sessions.restrict = original;
		}
	});

	// A child must retain its inherited policy after the parent session has ended.
	routingCheck("inherited child policy outlives parent shutdown", async (create) => {
		const parent = await create();
		await parent.route();
		const child = await create({ auth: parent.auth, parentId: parent.agentId, current: REASONING });
		await parent.close();
		assert.equal(child.auth.sessions.isRestricted(PROVIDER, child.sessionId), true);
		child.setCurrent(FOREIGN);
		await assert.rejects(child.request());
		assert.equal(child.calls.aborts, 1);
	});

	// Reload must restore enforcement, not mistake a saved setter result for new execution evidence.
	routingCheck("pending route survives session reload and verifies only after inference", async (create) => {
		const first = await create();
		await first.route({ modelClass: "reasoning" });
		const entries = structuredClone(first.entries);
		assert.ok(entries.length > 0, "route policy must be persisted in the session");
		await first.close();
		const resumed = await create({ auth: first.auth, sessionId: first.sessionId, agentId: first.agentId, entries, current: REASONING });
		assert.equal(resumed.describe().undertaking.status, "pending");
		assertBlocked(await resumed.tool("write", { path: "implementation.js", content: "change" }));
		await resumed.request();
		await resumed.response();
		await resumed.assistant();
		assert.equal(resumed.describe().undertaking.status, "verified");
	});

	// Child reload must restore inherited constraints even when the parent is no longer in memory.
	routingCheck("inherited policy survives child reload without a live parent", async (create) => {
		const parent = await create();
		await parent.route();
		const child = await create({ auth: parent.auth, parentId: parent.agentId, current: REASONING });
		const entries = structuredClone(child.entries);
		assert.ok(entries.length > 0);
		await child.close();
		await parent.close();
		const resumed = await create({ auth: child.auth, sessionId: child.sessionId, agentId: child.agentId, parentId: parent.agentId, entries, current: REASONING });
		assert.equal(resumed.auth.sessions.isRestricted(PROVIDER, resumed.sessionId), true);
		await resumed.request();
		assert.equal(resumed.calls.aborts, 0);
	});

	// Shutdown must not leave stale parent authorization available to a future child with the same label.
	routingCheck("parent shutdown removes its live inheritance policy", async (create) => {
		const parent = await create();
		await parent.route();
		const childId = `closed-parent-child-${++nextSession}`;
		assertAllowed(await parent.spawn([qualified(MECHANICAL)], "implementation", childId));
		await parent.close();
		const child = await create({ auth: parent.auth, parentId: parent.agentId, agentId: childId });
		assert.equal(child.describe().undertaking.status, "blocked");
		await assert.rejects(child.request());
		assert.equal(child.calls.aborts, 2, "startup and incompatible inference each abort");
	});

	// An operator consultation must not certify a pending worker or require repeated approval.
	routingCheck("operator frontier selection permits successive prompts without verifying the worker", async (create) => {
		const s = await create();
		await s.route({ modelClass: "reasoning" });
		const before = structuredClone(s.describe().undertaking);
		s.selectCurrent(FRONTIER);
		for (let i = 0; i < 2; i++) {
			await s.request();
			await s.assistant();
			assert.deepEqual(s.describe().undertaking, before);
		}
		assertAllowed(await s.tool("bash", { command: "gh issue create --title 'Consultation finding' --body 'Evidence'" }));
		s.selectCurrent(REASONING);
		await s.request();
		assertBlocked(await s.tool("write", { path: "implementation.js", content: "change" }));
		await s.assistant();
		assert.equal(s.describe().undertaking.status, "verified");
		assertAllowed(await s.tool("write", { path: "implementation.js", content: "change" }));
	});

	// Automatic transitions must not use the explicit-selection exception, even with a false fallback flag.
	for (const transition of [
		{ role: "fallback", resolvedModelIsFallback: true },
		{ role: "fallback", resolvedModelIsFallback: false },
		{ role: "prewalk", resolvedModelIsFallback: false },
	]) {
		routingCheck(`operator exception rejects automatic ${transition.role} ${transition.resolvedModelIsFallback}`, async (create) => {
			const s = await create();
			await s.route();
			const before = structuredClone(s.describe().undertaking);
			s.selectCurrent(FRONTIER, transition);
			await assert.rejects(s.request(), /frontier/iu);
			assert.deepEqual(s.describe().undertaking, before);
			s.selectCurrent(FRONTIER);
			await s.request();
			assertAllowed(await s.tool("bash", { command: "gh issue view 755" }));
			s.selectCurrent(MECHANICAL);
			await s.request();
			assertAllowed(await s.tool("bash", { command: "continue assigned work" }));
		});
	}

	// Consultation must retain reporting tools without granting a new frontier worker assignment.
	routingCheck("operator consultation preserves reporting and verified ownership without frontier assignment", async (create) => {
		const s = await create();
		await s.route();
		const before = structuredClone(s.describe().undertaking);
		s.selectCurrent(FRONTIER);
		await s.request();
		assertAllowed(await s.tool("bash", { command: "gh issue create --title 'Consultation finding' --body 'Evidence'" }));
		assert.deepEqual(s.describe().undertaking, before);
		assertGap(await s.route({ modelClass: "frontier" }), /approval/iu);
		assert.deepEqual(s.describe().undertaking, before);
	});

	// Reload must not mistake a selected consultation for a failed or newly verified undertaking worker.
	for (const recovery of [false, true]) {
		routingCheck(`operator consultation resumes while worker recovery is ${recovery}`, async (create) => {
			const first = await create();
			await first.route();
			first.selectCurrent(FRONTIER);
			const entries = structuredClone(first.entries);
			if (recovery) {
				const saved = entries.find(entry => entry.customType === "daily-driver-undertaking-route").data;
				saved.recovery = true;
				saved.reason = "Fixture failed restoration";
			}
			await first.close();
			const resumed = await create({ auth: first.auth, sessionId: first.sessionId, agentId: first.agentId, entries, current: FRONTIER });
			const before = structuredClone(resumed.describe().undertaking);
			assert.equal(before.status, recovery ? "blocked" : "pending");
			await resumed.request();
			await resumed.assistant();
			assert.deepEqual(resumed.describe().undertaking, before);
			assertAllowed(await resumed.tool("bash", { command: "gh issue view 755" }));
			resumed.selectCurrent(MECHANICAL);
			await resumed.request();
			assertBlocked(await resumed.tool("write", { path: "implementation.js", content: "change" }));
			await resumed.assistant();
			assert.equal(resumed.describe().undertaking.status, recovery ? "blocked" : "verified");
		});
	}

	// Native mention dispatch must preserve the selected model despite overrides and keep parent ownership truthful.
	routingCheck("native consultation pins its selector while the parent worker is pending", async (create) => {
		const parent = await create();
		await parent.route({ modelClass: "reasoning" });
		parent.entries.push({ type: "custom", customType: "model_mention", data: { agent: "m1", selector: qualified(FRONTIER), name: "Astra" } });
		const before = structuredClone(parent.describe().undertaking);
		assertAllowed(await parent.tool("task", { tasks: [{ agent: "m1", task: "consult" }] }));
		assertBlocked(await parent.tool("task", { tasks: [{ agent: "m1" }, { agent: "reasoning" }] }));
		const key = `native-child-${++nextSession}`;
		const decision = await parent.spawn([qualified(FOREIGN)], "m1", key, "m1");
		assert.deepEqual(decision.model, [qualified(FRONTIER)]);
		const child = await create({ auth: parent.auth, parentId: parent.agentId, agentId: key, agentName: "m1", current: FRONTIER, handoff: false });
		await child.request();
		await child.assistant();
		assert.equal(child.describe().undertaking, null);
		assert.deepEqual(parent.describe().undertaking, before);
		assert.equal(parent.auth.sessions.isRestricted(PROVIDER, parent.sessionId), true);
		await child.close();
		assert.equal(parent.auth.sessions.isRestricted(PROVIDER, parent.sessionId), true);
	});

	// Authentication-aware startup may substitute an unapproved model without marking it as fallback.
	routingCheck("native consultation rejects a substituted initial child model", async (create) => {
		const parent = await create();
		await parent.route();
		parent.entries.push({ type: "custom", customType: "model_mention", data: { agent: "m1", selector: qualified(FRONTIER), name: "Astra" } });
		const key = `substituted-child-${++nextSession}`;
		await parent.spawn([qualified(FRONTIER)], "m1", key, "m1");
		const child = await create({ auth: parent.auth, parentId: parent.agentId, agentId: key, agentName: "m1", current: REASONING, handoff: false });
		await assert.rejects(child.request(), /consultation/iu);
		assertBlocked(await child.tool("write", { path: "implementation.js", content: "change" }));
	});

	// A successful consultation must not grant subsequent fallback, backend or authentication substitution.
	for (const [name, replacement] of [
		["fallback", REASONING],
		["backend", model(FRONTIER.id, { baseUrl: "https://other.example.invalid/v1" })],
		["headers", model(FRONTIER.id, { headers: { "x-other": "value" } })],
		["authentication", FRONTIER],
	]) {
		routingCheck(`native consultation rejects later ${name} substitution and permits restoration`, async (create) => {
			const parent = await create();
			await parent.route();
			parent.entries.push({ type: "custom", customType: "model_mention", data: { agent: "m1", selector: qualified(FRONTIER), name: "Astra" } });
			const key = `consultation-drift-${++nextSession}`;
			await parent.spawn([qualified(FRONTIER)], "m1", key, "m1");
			const child = await create({ auth: parent.auth, parentId: parent.agentId, agentId: key, agentName: "m1", current: FRONTIER, handoff: false });
			await child.request();
			await child.helperRequest(FOREIGN);
			child.setCurrent(replacement);
			if (name === "authentication") child.auth.source = { kind: "api_key" };
			await assert.rejects(child.request(), /consultation|authentication/iu);
			child.setCurrent(FRONTIER);
			child.auth.source = { kind: "oauth" };
			await child.request();
			assert.equal(child.describe().undertaking, null);
			assertBlocked(await child.spawn([qualified(FRONTIER)], "reasoning", `unbound-descendant-${++nextSession}`));
		});
	}

	// A pseudonym or prompt text without Omp's native branch binding cannot authorize frontier dispatch.
	routingCheck("unbound model pseudonyms cannot grant frontier execution", async (create) => {
		const parent = await create();
		await parent.route();
		await parent.fire("before_agent_start", { prompt: '<model agent="m1" name="Astra"/>', systemPrompt: [] });
		assertBlocked(await parent.spawn([qualified(FRONTIER)], "m1", `unbound-${++nextSession}`, "m1"));
	});

	// Native replay must retain the first valid mapping rather than approve a later duplicate.
	routingCheck("native consultation follows first-valid branch mappings", async (create) => {
		const parent = await create();
		await parent.route();
		for (const data of [
			{ agent: "m1", selector: qualified(FRONTIER) },
			{ agent: "m1", selector: qualified(MECHANICAL), name: "Ordinary" },
			{ agent: "m1", selector: qualified(FRONTIER), name: "Astra" },
			{ agent: "m2", selector: qualified(MECHANICAL), name: "Duplicate" },
		]) parent.entries.push({ type: "custom", customType: "model_mention", data });
		assert.deepEqual((await parent.spawn([qualified(FRONTIER)], "m1", `first-${++nextSession}`, "m1")).model, [qualified(MECHANICAL)]);
		assertBlocked(await parent.spawn([qualified(FRONTIER)], "m2", `duplicate-${++nextSession}`, "m2"));
	});

	// Two parents may use the same child key without replacing or consuming each other's authorization.
	routingCheck("native consultations isolate repeated child names across parent sessions", async (create) => {
		const first = await create();
		const second = await create({ auth: first.auth });
		await first.route();
		await second.route({ issue: 756 });
		for (const parent of [first, second]) parent.entries.push({ type: "custom", customType: "model_mention", data: { agent: "m1", selector: qualified(FRONTIER), name: "Astra" } });
		const key = `shared-native-${++nextSession}`;
		for (const parent of [first, second]) assertAllowed(await parent.spawn([qualified(FRONTIER)], "m1", key, "m1"));
		for (const parent of [first, second]) {
			const child = await create({ auth: parent.auth, parentId: parent.agentId, agentId: key, agentName: "m1", current: FRONTIER, handoff: false });
			await child.request();
			assert.equal(child.describe().undertaking, null);
		}
	});

	// Resume must retain exact consultation bounds even when the parent and its native record are absent.
	routingCheck("native consultation reload retains its exact route without certifying a worker", async (create) => {
		const parent = await create();
		await parent.route();
		parent.entries.push({ type: "custom", customType: "model_mention", data: { agent: "m1", selector: qualified(FRONTIER), name: "Astra" } });
		const key = `resumed-native-${++nextSession}`;
		await parent.spawn([qualified(FRONTIER)], "m1", key, "m1");
		const child = await create({ auth: parent.auth, parentId: parent.agentId, agentId: key, agentName: "m1", current: FRONTIER, handoff: false });
		const entries = structuredClone(child.entries);
		await child.close();
		await parent.close();
		const resumed = await create({ auth: child.auth, sessionId: child.sessionId, agentId: key, agentName: "m1", parentId: parent.agentId, current: FRONTIER, entries, handoff: false });
		await resumed.request();
		resumed.setCurrent(REASONING);
		await assert.rejects(resumed.request(), /consultation/iu);
		assert.equal(resumed.describe().undertaking, null);
	});

	// Rewind and failed dispatch must revoke unconsumed bindings rather than authorize a late child startup.
	for (const change of ["rewind", "failed dispatch"]) {
		routingCheck(`native consultation ${change} revokes unconsumed authorization`, async (create) => {
			const parent = await create();
			await parent.route();
			const entry = { type: "custom", customType: "model_mention", data: { agent: "m1", selector: qualified(FRONTIER), name: "Astra" } };
			parent.entries.push(entry);
			const key = `revoked-native-${++nextSession}`;
			await parent.spawn([qualified(FRONTIER)], "m1", key, "m1");
			if (change === "rewind") {
				parent.entries.splice(parent.entries.indexOf(entry), 1);
				await parent.fire("session_tree");
				assertBlocked(await parent.spawn([qualified(FRONTIER)], "m1", `later-native-${++nextSession}`, "m1"));
			} else await parent.fire("tool_result", { toolName: "task", isError: true });
			const child = await create({ auth: parent.auth, parentId: parent.agentId, agentId: key, agentName: "m1", current: FRONTIER, handoff: false });
			await assert.rejects(child.request());
			assert.equal(child.describe().undertaking.status, "blocked");
		});
	}

	// Frontier gates apply to actual models even when a lower class has been mapped to Astra or Fable.
	for (const frontier of [FRONTIER, model("claude-fable", { provider: "anthropic", api: "anthropic-messages" })]) {
		routingCheck(`effective frontier ${frontier.id} requires approval under a lower class`, async (create) => {
			const current = frontier.provider === PROVIDER ? MECHANICAL : model("claude-sonnet", { provider: "anthropic", api: "anthropic-messages" });
			const auth = fakeAuth();
			for (const row of auth.rows) row.provider = frontier.provider;
			const s = await create({ current, auth, models: [current, frontier], roles: { implementation: `${qualified(frontier)}:high` } });
			assertGap(await s.route(), /frontier|approval/iu);
			assert.equal(s.calls.models.length, 0);
		});
	}

	// A declared frontier class must not infer approval merely from its configured model role.
	routingCheck("frontier class without an approval record is blocked", async (create) => {
		const s = await create();
		assertGap(await s.route({ modelClass: "frontier" }), /frontier|approval/iu);
		assert.equal(s.calls.models.length, 0);
	});

	// A validated explicit frontier exception must permit selection without broadening ordinary fallbacks.
	routingCheck("frontier approval permits the selected frontier route", async (create) => {
		const s = await create();
		const result = await s.route({ modelClass: "frontier", frontierApproval: "Issue #755: explicit user approval for this implementation" });
		assert.notEqual(result.isError, true);
		assert.equal(result.details.undertaking.selectedModel, qualified(FRONTIER));
		assert.equal(result.details.undertaking.status, "pending");
		await s.request();
		await s.response();
		await s.assistant();
		assert.equal(s.describe().undertaking.status, "verified");
		assertAllowed(await s.spawn([qualified(FRONTIER)], "frontier"));
	});

	// A rejected or synthetic response used to certify a pending worker from its model name alone.
	for (const stopReason of [undefined, "error", "aborted"]) {
		routingCheck(`unadmitted ${stopReason ?? "ordinary"} response cannot verify a worker`, async (create) => {
			const s = await create();
			await s.route({ modelClass: "reasoning" });
			if (stopReason) await s.request();
			await s.fire("assistant_message", { message: {
				role: "assistant", provider: REASONING.provider, model: REASONING.id, stopReason, content: [],
			} });
			assert.equal(s.describe().undertaking.status, "pending");
			assertBlocked(await s.tool("write", { path: "implementation.js", content: "change" }));
			await s.assistant();
			assert.equal(s.describe().undertaking.status, "verified");
		});
	}

	// A valid primary selector used to hide an unauthorized automatic candidate until inference dispatch.
	for (const fallback of [qualified(FOREIGN), qualified(FRONTIER), `${qualified(MECHANICAL)}:low`]) {
		routingCheck(`automatic candidate ${fallback} is rejected before selection`, async (create) => {
			const s = await create({ candidates: async (_ctx, _settings, patterns) => [...patterns, fallback] });
			assertGap(await s.route());
			assert.equal(s.calls.models.length, 0);
			assert.equal(s.describe().undertaking, null);
		});
	}

	// A catalog backend change after admission used to be re-resolved instead of compared to the admitted identity.
	routingCheck("admitted backend snapshot survives a catalog replacement", async (create) => {
		const s = await create();
		await s.route({ modelClass: "reasoning" });
		const admitted = structuredClone(s.describe().undertaking);
		s.setCurrent({ ...REASONING, baseUrl: "https://replacement.example.invalid/v1" });
		await assert.rejects(s.request(), /backend/iu);
		await s.fire("assistant_message", { message: { role: "assistant", provider: REASONING.provider, model: REASONING.id, content: [] } });
		assert.deepEqual(s.describe().undertaking, admitted);
		s.setCurrent(REASONING);
		await s.assistant();
		assert.equal(s.describe().undertaking.status, "verified");
	});

	// A rejected request must leave diagnostics accessible without another model response.
	routingCheck("local status distinguishes selection, observation, and rejected host drift", async (create) => {
		const s = await create();
		await s.route({ modelClass: "reasoning" });
		s.setCurrent(MECHANICAL);
		await assert.rejects(s.request(), /selected worker/iu);
		const info = await s.inspection();
		assert.equal(info.issue, 755);
		assert.equal(info.requiredClass, "reasoning");
		assert.equal(info.selectedModel, qualified(REASONING));
		assert.equal(info.selectedEffort, "high");
		assert.equal(info.hostModel, qualified(MECHANICAL));
		assert.equal(info.observedModel, "unreported");
		assert.equal(info.authenticationRoute, "oauth");
		assert.equal(info.state, "pending");
		assert.match(info.lastRejection, /selected worker/iu);
		assert.ok(s.calls.notifications.some(row => /\/undertaking status/u.test(row.message)));
		assert.doesNotMatch(JSON.stringify(info), /account:|credential|headers|fixture-key/u);
	});

	// An empty session must not require a model turn or raise a recovery exception.
	routingCheck("local status and repeated cancellation are ordinary without an owner", async (create) => {
		const s = await create();
		assert.equal((await s.inspection()).state, "none");
		await s.command("cancel 755");
		await s.command("cancel 755");
		assert.equal(s.entries.length, 0);
		assert.equal(s.calls.aborts, 0);
		assert.match(s.calls.notifications.at(-1).message, /No active undertaking/u);
	});

	// Pending and verified routes must both relinquish only their own lease without claiming completion.
	for (const modelClass of ["implementation", "reasoning"]) {
		routingCheck(`local cancellation persists ${modelClass} ownership without completing task state`, async (create) => {
			const s = await create();
			await s.route({ modelClass });
			const task = { type: "custom", customType: "daily-driver.task-state", data: { status: "active", authorizations: ["retained"] } };
			s.entries.push(task);
			const modelBefore = s.ctx.models.current();
			await s.command("cancel 755");
			assert.equal(s.describe().undertaking, null);
			assert.equal(s.auth.sessions.isRestricted(PROVIDER, s.sessionId), false);
			assert.equal(s.calls.aborts, 1);
			assert.equal(s.ctx.models.current(), modelBefore);
			assert.deepEqual(s.entries.at(-1).data, { schema: 2, issue: 755, lifecycle: "cancelled" });
			assert.equal(task.data.status, "active");
			assert.deepEqual(task.data.authorizations, ["retained"]);
			const count = s.entries.length;
			await s.command("cancel 755");
			assert.equal(s.entries.length, count);
			const entries = structuredClone(s.entries);
			await s.close();
			const resumed = await create({ entries, current: modelBefore, sessionId: s.sessionId, auth: s.auth });
			assert.equal(resumed.describe().undertaking, null);
			assert.equal((await resumed.inspection()).state, "cancelled");
			await resumed.assistant();
			assert.equal(resumed.describe().undertaking, null, "cancelled worker must never verify after reload");
			assert.notEqual((await resumed.route({ issue: 756 })).isError, true, "new ownership requires a fresh route call");
		});
	}

	// The wrong issue or an ambiguous cancellation must not release any restriction.
	routingCheck("local cancellation refuses a wrong owner before abort or persistence", async (create) => {
		const s = await create();
		await s.route();
		const entries = structuredClone(s.entries);
		await s.command("cancel 756");
		await s.command("cancel");
		assert.deepEqual(s.entries, entries);
		assert.equal(s.calls.aborts, 0);
		assert.equal(s.auth.calls.unrestrict.length, 0);
		assert.equal(s.describe().undertaking.issue, 755);
	});

	// Releasing a lease before the active tool stops could authorize a late worker request.
	routingCheck("local cancellation waits for quiescence before releasing its lease", async (create) => {
		const idle = deferred();
		let quiescent = false;
		const s = await create({ waitForIdle: () => idle.promise, isIdle: () => quiescent });
		await s.route();
		const cancelling = s.command("cancel 755");
		assert.equal(s.auth.calls.unrestrict.length, 0);
		assertBlocked(await s.tool("write"));
		await assert.rejects(s.request(), /cancelled/iu);
		quiescent = true;
		idle.resolve();
		await cancelling;
		assert.equal(s.auth.calls.unrestrict.length, 1);
	});

	// Restore failures must not strand cancellation behind provider admission or revive invalid state.
	for (const data of [null, { schema: 99 }, { schema: 1, issue: 755 }, {
		schema: 1, issue: 755, modelClass: "implementation", selectedModel: qualified(MECHANICAL),
		origin: { provider: PROVIDER }, authenticationRoute: "changed-auth",
	}]) {
		routingCheck(`malformed or failed restoration remains locally cancellable: ${JSON.stringify(data)}`, async (create) => {
			const s = await create({ entries: [{ type: "custom", customType: "daily-driver-undertaking-route", data }] });
			const info = await s.inspection();
			assert.equal(info.state, "blocked");
			assert.match(info.lastRejection, /invalid|backend|Authentication/iu);
			await s.command(`cancel ${info.cancelOwner}`);
			assert.equal(s.describe().undertaking, null);
			assert.equal(s.entries.at(-1).data.lifecycle, "cancelled");
		});
	}

	// Existing schema-1 records must stay readable while all new writes use one lifecycle format.
	routingCheck("legacy active and completed records retain their recovery meaning", async (create) => {
		const first = await create();
		await first.route();
		const legacy = structuredClone(first.entries);
		legacy[0].data.schema = 1;
		delete legacy[0].data.lifecycle;
		await first.close();
		const active = await create({ entries: legacy });
		assert.equal(active.describe().undertaking.status, "pending");
		const completed = await create({ entries: [...legacy, {
			type: "custom", customType: "daily-driver-undertaking-route", data: { schema: 1, issue: 755, completed: true },
		}] });
		assert.equal(completed.describe().undertaking, null);
	});

	// Cancelling one owner must not release a replacement operator lease or another session's lease.
	routingCheck("local cancellation preserves operator and unrelated-session restrictions", async (create) => {
		const auth = fakeAuth();
		const s = await create({ auth });
		const other = await create({ auth });
		await s.route();
		await other.route();
		auth.sessions.restrict(PROVIDER, s.sessionId, ["account:eligible-two"]);
		const otherBefore = other.describe().undertaking;
		await s.command("cancel 755");
		assert.equal(auth.sessions.isRestricted(PROVIDER, s.sessionId), true);
		assert.equal(auth.sessions.permits(PROVIDER, s.sessionId, 1), false);
		assert.equal(auth.sessions.isRestricted(PROVIDER, other.sessionId), true);
		assert.deepEqual(other.describe().undertaking, otherBefore);
	});

	// Parent cancellation must revoke running children and late handoffs instead of making them unrestricted.
	routingCheck("local cancellation revokes only owned children and survives child reload", async (create) => {
		const auth = fakeAuth();
		const parent = await create({ auth });
		const other = await create({ auth });
		await parent.route();
		await other.route();
		const child = await create({ auth, parentId: parent.agentId, current: REASONING });
		await child.request();
		await child.assistant();
		const lateId = `cancelled-late-child-${++nextSession}`;
		await parent.spawn([qualified(REASONING)], "reasoning", lateId);
		await parent.command("cancel 755");
		assert.equal(child.calls.aborts, 1);
		assert.equal(auth.sessions.isRestricted(PROVIDER, child.sessionId), true, "running child retains its lease until shutdown");
		await assert.rejects(child.request(), /cancelled/iu);
		assertBlocked(await child.tool("write"));
		assertBlocked(await child.spawn([qualified(REASONING)]));
		await child.fire("assistant_message", { message: { role: "assistant", provider: REASONING.provider, model: REASONING.id, content: [] } });
		assert.equal(child.describe().undertaking.status, "blocked");
		assert.equal((await child.route()).isError, true);
		assert.equal((await child.finish()).isError, true);
		assert.equal(other.describe().undertaking.status, "verified");
		const late = await create({ auth, parentId: parent.agentId, agentId: lateId, handoff: false });
		await assert.rejects(late.request());
		const entries = structuredClone(child.entries);
		await child.close();
		const resumed = await create({ auth, entries, sessionId: child.sessionId, current: REASONING });
		await assert.rejects(resumed.request(), /cancelled/iu);
		assertBlocked(await resumed.tool("write"));
	});

	// A lower-class model used to pass child admission whenever its family matched.
	routingCheck("child class selection rejects a same-family lower-class candidate", async (create) => {
		const s = await create();
		await s.route();
		assertBlocked(await s.spawn([qualified(MECHANICAL)], "reasoning"));
		assertAllowed(await s.spawn([`${qualified(REASONING)}:high`], "reasoning"));
	});

	// Cancellation during credential preflight used to publish a new route after its owner was released.
	routingCheck("cancelled owner cannot be restored by a late route admission", async (create) => {
		const pending = deferred();
		let delayed = false;
		const s = await create({ candidates: async (_ctx, _settings, patterns) => {
			if (delayed) await pending.promise;
			return patterns;
		} });
		await s.route();
		delayed = true;
		const admission = s.route({ modelClass: "reasoning" });
		await Promise.resolve();
		await s.command("cancel 755");
		pending.resolve();
		assert.equal((await admission).isError, true);
		assert.equal(s.describe().undertaking, null);
		assert.equal(s.entries.at(-1).data.lifecycle, "cancelled");
	});

	// Two async route calls could otherwise overwrite each other's selected class and lease.
	routingCheck("concurrent route admissions retain one owner", async (create) => {
		const pending = deferred();
		const entered = deferred();
		const s = await create({ candidates: async (_ctx, _settings, patterns) => {
			entered.resolve();
			await pending.promise;
			return patterns;
		} });
		const first = s.route();
		await entered.promise;
		assert.equal((await s.route({ modelClass: "reasoning" })).isError, true);
		pending.resolve();
		assert.notEqual((await first).isError, true);
		assert.equal(s.describe().undertaking.selectedModel, qualified(MECHANICAL));
	});

	// Unspecified child effort used to inherit a different budget instead of the admitted class budget.
	routingCheck("child startup cannot substitute a lower effort", async (create) => {
		const parent = await create();
		await parent.route();
		const childId = `effort-child-${++nextSession}`;
		assertAllowed(await parent.spawn([qualified(REASONING)], "reasoning", childId));
		const child = await create({
			auth: parent.auth, parentId: parent.agentId, agentId: childId, current: REASONING, effort: "low", handoff: false,
		});
		assert.equal(child.describe().undertaking.status, "blocked");
		await assert.rejects(child.request(), /effort/iu);
	});

	// A native consultation's explicit effort must not become permission for another budget.
	routingCheck("native consultation keeps its explicit effort", async (create) => {
		const parent = await create();
		await parent.route();
		const selected = `${qualified(FRONTIER)}:low`;
		parent.entries.push({ type: "custom", customType: "model_mention", data: { agent: "m1", selector: selected, name: "Astra" } });
		const key = `effort-consultation-${++nextSession}`;
		assertAllowed(await parent.spawn([selected], "m1", key, "m1"));
		const child = await create({
			auth: parent.auth, parentId: parent.agentId, agentId: key, agentName: "m1", current: FRONTIER, effort: "low", handoff: false,
		});
		await child.request();
		child.setEffort("high");
		await assert.rejects(child.request(), /effort/iu);
	});

	// An in-progress selection with no published owner must not be mistaken for a cancellable issue.
	routingCheck("local cancellation refuses unresolved selection ownership", async (create) => {
		const entered = deferred();
		const proceed = deferred();
		const s = await create({ getApiKey: async () => {
			entered.resolve();
			await proceed.promise;
			return "offline-fixture-key";
		} });
		const routing = s.route();
		await entered.promise;
		try {
			assert.equal((await s.inspection()).state, "selecting");
			await s.command("cancel 755");
			assert.match(s.calls.notifications.at(-1).message, /ownership is not yet established/u);
			assert.equal(s.calls.aborts, 0);
			assert.equal(s.auth.calls.unrestrict.length, 0);
		} finally {
			proceed.resolve();
			await routing;
		}
	});

	// A child must not turn cancellation into permission to continue outside its parent's policy.
	routingCheck("local child cancellation retires execution instead of removing all admission", async (create) => {
		const parent = await create();
		await parent.route();
		const child = await create({ auth: parent.auth, parentId: parent.agentId, current: REASONING });
		await child.command("cancel 755");
		assert.equal(child.entries.at(-1).data.retired, true);
		await assert.rejects(child.request(), /cancelled/iu);
		assertBlocked(await child.tool("write"));
		await child.command("cancel 755");
		assert.match(child.calls.notifications.at(-1).message, /already retired/u);
		await assert.rejects(child.request(), /cancelled/iu);
		assert.equal(parent.describe().undertaking.status, "verified");
		assert.equal(parent.auth.calls.unrestrict.length, 1, "only the quiescent child's lease is released");
	});

	// An aborted routing tool could otherwise publish a verified route when asynchronous preflight returns.
	routingCheck("aborted route preflight cannot select or verify a worker", async (create) => {
		const entered = deferred();
		const proceed = deferred();
		const s = await create({ candidates: async (_ctx, _settings, patterns) => {
			entered.resolve();
			await proceed.promise;
			return patterns;
		} });
		const controller = new AbortController();
		const admission = s.tools.get("daily_driver_route_undertaking").execute(
			"aborted-route", { issue: 755, modelClass: "reasoning" }, controller.signal, undefined, s.ctx);
		await entered.promise;
		controller.abort();
		proceed.resolve();
		assert.equal((await admission).isError, true);
		assert.equal(s.describe().undertaking, null);
		assert.equal(s.calls.models.length, 0);
		assert.equal(s.auth.calls.restrict.length, 0);
	});

	// Host dispatch cancellation does not stop an awaiting extension handler, which could leave a late handoff.
	routingCheck("failed task dispatch invalidates an awaiting child admission", async (create) => {
		const entered = deferred();
		const proceed = deferred();
		let delayed = false;
		const parent = await create({ candidates: async (_ctx, _settings, patterns) => {
			if (delayed) { entered.resolve(); await proceed.promise; }
			return patterns;
		} });
		await parent.route();
		delayed = true;
		const key = `aborted-child-${++nextSession}`;
		const admission = parent.spawn([qualified(REASONING)], "reasoning", key);
		await entered.promise;
		await parent.fire("tool_result", { toolName: "task", isError: true });
		proceed.resolve();
		assertBlocked(await admission);
		const child = await create({
			auth: parent.auth, parentId: parent.agentId, agentId: key, current: REASONING, handoff: false,
		});
		assert.equal(child.describe().undertaking.status, "blocked");
		await assert.rejects(child.request());
	});
}
