import assert from "node:assert/strict";
import { installUndertakingRouting } from "../extensions/undertaking-routing.mjs";

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
const DEFAULT_ROLES = {
	mechanical: `${qualified(MECHANICAL)}:low`,
	implementation: `${qualified(MECHANICAL)}:high`,
	reasoning: `${qualified(REASONING)}:high`,
	frontier: `${qualified(FRONTIER)}:high`,
};
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
	const roles = { ...DEFAULT_ROLES, ...options.roles };
	const entries = options.entries ?? [];
	const models = options.models ?? MODELS;
	const tools = new Map();
	const handlers = new Map();
	const calls = { models: [], effort: [], aborts: 0, keyLookups: [] };
	let current = options.current ?? MECHANICAL;
	let effort = options.effort ?? "high";
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
		isIdle: () => false,
		ui: { notify() {}, setStatus() {} },
	};
	Object.defineProperty(ctx, "model", { get: () => current });
	const api = installUndertakingRouting(pi, async () => ({ getModelRole: (role) => roles[role] }));
	async function fire(event, payload = {}, selected = current) {
		const eventContext = event === "before_provider_request"
			? { ...ctx, model: selected, models: { ...ctx.models, current: () => selected } }
			: ctx;
		const results = [];
		for (const handler of handlers.get(event) ?? []) results.push(await handler({ type: event, ...payload }, eventContext));
		return results.find((result) => result !== undefined);
	}
	return {
		ctx, pi, api, auth, roles, entries, calls, sessionId, agentId,
		fire,
		start: () => fire("session_start"),
		setCurrent: (value) => { current = value; },
		setEffort: (value) => { effort = value; },
		describe: () => api.describe(ctx),
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
		assistant: (selected = current) => fire("assistant_message", { message: { role: "assistant", provider: selected.provider, model: selected.id, content: [{ type: "text", text: "Offline routing response" }] } }),
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
	if (result.details?.undertaking) assert.equal(result.details.undertaking.status, "blocked");
	const reason = result.details?.undertaking?.reason
		?? result.content?.filter((item) => item.type === "text").map((item) => item.text).join("\n");
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
					await parents[0].spawn([qualified(session.ctx.models.current())], options.agentName ?? "implementation", session.agentId);
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
			observedModel: qualified(MECHANICAL), status: "verified",
		});
		assert.equal(result.details.provider, PROVIDER);
		assert.equal(result.details.authenticationRoute, "oauth");
		assert.equal(s.calls.models.length, 0);
		assert.equal(s.calls.effort.length, 0);
		assert.equal(s.describe().undertaking.status, "verified");
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
			assertBlocked(await s.tool("bash", { command: "git worktree add ../task -b task" }));
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
	});

	// Missing and cleared roles must not silently restore defaults or fabricate a selector.
	for (const selector of [undefined, "", "openai-codex/missing-model:high"]) {
		routingCheck(`unavailable class selector ${String(selector)} reports a gap`, async (create) => {
			const s = await create({ roles: { implementation: selector } });
			assertGap(await s.route());
			assert.equal(s.calls.models.length, 0);
		});
	}

	// Direct tool callers must not bypass the finite class set by skipping schema validation.
	routingCheck("unknown model class cannot select arbitrary models", async (create) => {
		const s = await create();
		assertGap(await s.route({ modelClass: "unrestricted" }));
		assert.equal(s.calls.models.length, 0);
	});

	// A rejected or throwing model setter must not let implementation continue on the old route.
	for (const failure of ["false", "throw"]) {
		routingCheck(`model setter ${failure} leaves a blocked route`, async (create) => {
			const s = await create({ setModel: async () => {
				if (failure === "throw") throw new Error("fixture model setter failure");
				return false;
			} });
			assertGap(await s.route({ modelClass: "reasoning" }));
			assertBlocked(await s.tool("write", { path: "implementation.js", content: "change" }));
		});
	}

	// An effort setter failure must not verify a model with the wrong reasoning budget.
	routingCheck("effort setter failure is a configuration gap", async (create) => {
		const s = await create({ setThinkingLevel: () => { throw new Error("fixture effort setter failure"); } });
		assertGap(await s.route({ modelClass: "mechanical" }));
		assertBlocked(await s.tool("write", { path: "implementation.js", content: "change" }));
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

	// A thrown hook alone is swallowed by Omp, so mismatched inference must explicitly abort.
	for (const [name, drift] of [
		["class", MECHANICAL],
		["provider", model(REASONING.id, { provider: "other-provider" })],
		["backend", model(REASONING.id, { baseUrl: "https://other.example.invalid/v1" })],
		["transport", model(REASONING.id, { api: "openai-completions" })],
		["headers", model(REASONING.id, { headers: { "x-routing-region": "other-region" } })],
	]) {
		routingCheck(`${name} request drift explicitly aborts`, async (create) => {
			const s = await create();
			await s.route({ modelClass: "reasoning" });
			s.setCurrent(drift);
			await assert.rejects(s.request());
			assert.equal(s.calls.aborts, 1);
			assert.equal(s.describe().undertaking.status, "blocked");
		});
	}

	// A lower effort on the same model must not silently weaken the configured class route.
	routingCheck("same-model effort drift aborts before inference", async (create) => {
		const s = await create();
		await s.route();
		s.setEffort("low");
		await assert.rejects(s.request(), /effort/iu);
		assert.equal(s.calls.aborts, 1);
		assert.equal(s.describe().undertaking.status, "blocked");
	});

	// Refreshable OAuth is allowed, but retrying through a configured API key is not.
	routingCheck("authentication source drift explicitly aborts", async (create) => {
		const s = await create();
		await s.route();
		s.auth.source = { kind: "config", concrete: true };
		await assert.rejects(s.request());
		assert.equal(s.calls.aborts, 1);
		assert.equal(s.describe().undertaking.status, "blocked");
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
			data: { schema: 1, issue: 755, completed: true },
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
}
