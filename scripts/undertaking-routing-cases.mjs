import assert from "node:assert/strict";
import { installUndertakingRouting } from "../extensions/undertaking-routing.mjs";
import { installModelClassDefaults } from "../extensions/role-default-helper.mjs";

const model = (id, provider = "openai-codex", api = "openai-codex-responses") => ({
	id, name: id, provider, api, baseUrl: "https://routing.example.invalid/v1", headers: {},
});
const MECHANICAL = model("gpt-6-luna");
const TERRA = model("gpt-6.1-terra");
const REASONING = model("gpt-6.1-sol");
const FRONTIER = model("gpt-6-astra");
const FOREIGN = model("claude-sonnet", "anthropic", "anthropic-messages");
const MODELS = [MECHANICAL, TERRA, REASONING, FRONTIER, FOREIGN];
const qualified = value => `${value.provider}/${value.id}`;
let nextSession = 0;

function deferred() {
	let resolve;
	const promise = new Promise(complete => { resolve = complete; });
	return { promise, resolve };
}

function fakeAuth() {
	const calls = { restrict: [], unrestrict: [] };
	const auth = {
		calls, source: { kind: "oauth" },
		keys: { source: () => auth.source },
		sessions: {
			restrict: (...args) => { calls.restrict.push(args); return Symbol("lease"); },
			unrestrict: (...args) => calls.unrestrict.push(args),
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
		getModelRole: role => roles[role],
		getModelRoleProvenance: role => Object.hasOwn(options.roles ?? {}, role) ? "user" : "default",
		overrideModelRoles: values => Object.assign(roles, values),
	};
	installModelClassDefaults(settings, { get: () => ({}), override() {} });
	const entries = options.entries ?? [];
	const models = options.models ?? MODELS;
	const handlers = new Map();
	const tools = new Map();
	const commands = new Map();
	const calls = { models: [], effort: [], aborts: 0, notifications: [] };
	let current = options.current ?? MECHANICAL;
	let effort = options.effort ?? "high";
	let closed = false;
	const schema = () => ({ describe() { return this; }, int() { return this; }, min() { return this; }, optional() { return this; } });
	const pi = {
		zod: { object: value => value, string: schema, number: schema },
		on(name, handler) { const list = handlers.get(name) ?? []; list.push(handler); handlers.set(name, list); },
		registerTool: tool => tools.set(tool.name, tool),
		registerCommand: (name, command) => commands.set(name, command),
		appendEntry: async (customType, data) => entries.push({ type: "custom", customType, data: structuredClone(data) }),
		async setModel(value) {
			calls.models.push(value);
			if (options.setModel) return options.setModel(value, selected => { current = selected; });
			current = value;
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
		agent: options.parentId ? { kind: "sub", id: agentId, parentId: options.parentId } : { kind: "main", id: agentId },
		sessionManager: { getSessionId: () => sessionId, getBranch: () => entries },
		models: {
			current: () => current,
			list: () => models,
			resolve(reference) {
				const value = reference?.startsWith("@") ? roles[reference.slice(1)] : reference;
				const base = value?.replace(/:(?:off|minimal|low|medium|high|xhigh|max|auto|inherit)$/, "");
				return models.find(candidate => qualified(candidate) === base || candidate.id === base);
			},
			family: candidate => options.family ? options.family(candidate) : candidate.provider === "anthropic" ? "claude" : "gpt",
		},
		modelRegistry: { authStorage: auth, getApiKey: options.getApiKey ?? (async () => "offline-key") },
		abort: () => { calls.aborts++; },
		isIdle: () => options.isIdle?.() ?? true,
		waitForIdle: async () => { if (options.waitForIdle) await options.waitForIdle(); },
		ui: { notify: (message, type) => calls.notifications.push({ message, type }), setStatus() {} },
	};
	Object.defineProperty(ctx, "model", { get: () => current });
	const api = installUndertakingRouting(pi, async () => settings, options.routes ? () => options.routes : undefined,
		options.candidates ?? (async (_ctx, _settings, patterns) => patterns));
	async function fire(name, payload = {}) {
		for (const handler of handlers.get(name) ?? []) {
			const result = await handler({ type: name, ...payload }, ctx);
			if (result !== undefined) return result;
		}
	}
	return {
		ctx, pi, auth, entries, calls, sessionId, agentId, roles, fire,
		start: () => fire("session_start"),
		current: () => current,
		effort: () => effort,
		setCurrent: value => { current = value; },
		setEffort: value => { effort = value; },
		describe: () => api.describe(ctx),
		route: (params = {}) => tools.get("daily_driver_route_undertaking").execute("route", { issue: 755, modelClass: "implementation", ...params }, undefined, undefined, ctx),
		finish: (issue = 755) => tools.get("daily_driver_finish_undertaking").execute("finish", { issue }, undefined, undefined, ctx),
		command: args => commands.get("undertaking").handler(args, ctx),
		tool: (toolName, input = {}) => fire("tool_call", { toolName, input }),
		prompt: () => fire("before_agent_start", { prompt: "Continue" }),
		request: () => fire("before_provider_request", { payload: { model: current.id } }),
		assistant: () => fire("assistant_message", { message: { role: "assistant", provider: current.provider, model: current.id, content: [{ type: "text", text: "Response" }] } }),
		spawn: (key, patterns = [qualified(FOREIGN)]) => fire("before_subagent_spawn", { agent: "implementation", modelRole: "implementation", patterns, spawnKey: key }),
		async close() { if (!closed) { closed = true; await fire("session_shutdown"); } },
	};
}

function assertGap(result, pattern) {
	assert.equal(result.isError, true);
	if (pattern) assert.match(result.content.map(item => item.text).join("\n"), pattern);
}
function assertAllowed(result) { assert.notEqual(result?.block, true, result?.reason); }
function assertBlocked(result) { assert.equal(result?.block, true); }

/** Register offline regressions for one-time undertaking selection and ownership. */
export default function registerUndertakingRoutingChecks(check) {
	function routingCheck(name, run) {
		check(`undertaking routing: ${name}`, async () => {
			const sessions = [];
			const create = async options => {
				const session = fakeSession(options);
				sessions.push(session);
				await session.start();
				return session;
			};
			try { await run(create); }
			finally { for (const session of sessions.reverse()) await session.close(); }
		});
	}

	// Re-selecting an already matching route would overwrite the operator's selection unnecessarily.
	routingCheck("matching route performs no setter calls", async create => {
		const s = await create();
		assert.notEqual((await s.route()).isError, true);
		assert.deepEqual(s.calls.models, []);
		assert.deepEqual(s.calls.effort, []);
		assertAllowed(await s.tool("write", { path: "task.txt" }));
	});

	// A new undertaking must still apply the configured model and effort once.
	routingCheck("initial selection switches model and effort", async create => {
		const s = await create({ current: REASONING });
		assert.notEqual((await s.route({ modelClass: "mechanical" })).isError, true);
		assert.deepEqual(s.calls.models, [MECHANICAL]);
		assert.deepEqual(s.calls.effort, ["low"]);
		assert.equal(s.current(), MECHANICAL);
		assert.equal(s.effort(), "low");
	});

	for (const afterResponse of [false, true]) {
		for (const change of ["effort", "model", "provider"]) {
			// A pending or previously observed admission must never restore or reject the operator's route.
			routingCheck(`${change} change ${afterResponse ? "after" : "before"} first response remains authoritative`, async create => {
				const s = await create();
				await s.route({ modelClass: "reasoning" });
				if (afterResponse) { await s.request(); await s.assistant(); }
				if (change === "effort") s.setEffort("low");
				if (change === "model") s.setCurrent(TERRA);
				if (change === "provider") { s.setCurrent(FOREIGN); s.setEffort("medium"); }
				const selected = s.current();
				const selectedEffort = s.effort();
				const modelCalls = s.calls.models.length;
				const effortCalls = s.calls.effort.length;
				await s.prompt();
				await s.request();
				assertAllowed(await s.tool("write", { path: "task.txt" }));
				assertAllowed(await s.spawn(`child-${change}-${afterResponse}`));
				assert.equal(s.current(), selected);
				assert.equal(s.effort(), selectedEffort);
				assert.equal(s.calls.models.length, modelCalls);
				assert.equal(s.calls.effort.length, effortCalls);
				assert.equal(s.calls.aborts, 0);
			});
		}
	}

	// Re-entry is not a new undertaking, even when the requested class changes.
	routingCheck("same issue re-entry preserves operator selection", async create => {
		const s = await create();
		await s.route({ modelClass: "reasoning" });
		s.setCurrent(FOREIGN); s.setEffort("low");
		const modelCalls = s.calls.models.length;
		const effortCalls = s.calls.effort.length;
		assert.notEqual((await s.route({ modelClass: "mechanical" })).isError, true);
		assert.equal(s.current(), FOREIGN);
		assert.equal(s.effort(), "low");
		assert.equal(s.calls.models.length, modelCalls);
		assert.equal(s.calls.effort.length, effortCalls);
		assertAllowed(await s.tool("write", { path: "task.txt" }));
	});

	for (const schema of [1, 2]) {
		// Legacy recovery flags must not revive the old model or reinstall authentication restrictions.
		routingCheck(`legacy schema ${schema} reload preserves the current route`, async create => {
			const first = await create();
			await first.route({ modelClass: "reasoning" });
			const entries = structuredClone(first.entries);
			const saved = entries.at(-1).data;
			saved.schema = schema;
			if (schema === 1) delete saved.lifecycle;
			saved.recovery = true;
			saved.reason = "legacy route mismatch";
			const resumed = await create({ entries, current: FOREIGN, effort: "medium" });
			assert.equal(resumed.describe().undertaking.issue, 755);
			await resumed.prompt(); await resumed.request();
			await resumed.fire("session_tree");
			await resumed.prompt(); await resumed.request();
			assert.notEqual((await resumed.route()).isError, true);
			assertAllowed(await resumed.tool("write", { path: "task.txt" }));
			assert.equal(resumed.current(), FOREIGN);
			assert.equal(resumed.effort(), "medium");
			assert.deepEqual(resumed.calls.models, []);
			assert.deepEqual(resumed.calls.effort, []);
			assert.deepEqual(resumed.auth.calls.restrict, []);
			assert.equal(resumed.calls.aborts, 0);
		});
	}

	// Finishing an owner must allow the next issue to perform a fresh selection.
	routingCheck("new issue selects its own initial route after finish", async create => {
		const s = await create();
		await s.route({ modelClass: "reasoning" });
		assert.notEqual((await s.finish()).isError, true);
		s.setCurrent(MECHANICAL); s.setEffort("low");
		assert.notEqual((await s.route({ issue: 756, modelClass: "integration" })).isError, true);
		assert.equal(s.current(), TERRA);
		assert.equal(s.effort(), "medium");
		assert.equal(s.describe().undertaking.issue, 756);
	});

	for (const selector of [undefined, "", "openai-codex/missing-model:high"]) {
		// Missing explicit mappings must not silently fall back to a different class.
		routingCheck(`invalid class mapping ${String(selector)} fails admission`, async create => {
			const s = await create({ roles: { implementation: selector } });
			assertGap(await s.route());
			assert.deepEqual(s.calls.models, []);
			assertBlocked(await s.tool("write", { path: "task.txt" }));
		});
	}

	// The initial route remains constrained to the invoking provider and family.
	routingCheck("foreign initial class target fails admission", async create => {
		const s = await create({ roles: { implementation: qualified(FOREIGN) } });
		assertGap(await s.route(), /provider|family/iu);
		assert.deepEqual(s.calls.models, []);
	});

	// An unmapped family must continue on the invoking model rather than adopt default roles.
	routingCheck("unmapped family warns without switching", async create => {
		const unknown = model("unmapped-model", "unknown", "openai-completions");
		const s = await create({ current: unknown, models: [unknown, ...MODELS], family: value => value.provider === "unknown" ? "unmapped" : "gpt" });
		const result = await s.route();
		assert.notEqual(result.isError, true);
		assert.match(result.content[0].text, /WARNING/iu);
		assert.equal(s.current(), unknown);
		assert.deepEqual(s.calls.models, []);
	});

	// An explicit frontier assignment must not bypass its approval requirement.
	routingCheck("frontier admission requires approval", async create => {
		const s = await create();
		assertGap(await s.route({ modelClass: "frontier" }), /frontier|approval/iu);
		assert.deepEqual(s.calls.models, []);
	});

	// Approved frontier work must still select its configured initial class.
	routingCheck("approved frontier admission selects its target", async create => {
		const s = await create();
		assert.notEqual((await s.route({ modelClass: "frontier", frontierApproval: "Explicit bounded approval" })).isError, true);
		assert.equal(s.current(), FRONTIER);
	});

	// An unavailable authentication source must not masquerade as an admitted route.
	routingCheck("missing initial authentication source fails admission", async create => {
		const auth = fakeAuth();
		auth.source = undefined;
		const s = await create({ auth });
		assertGap(await s.route(), /authentication/iu);
		assert.deepEqual(s.calls.models, []);
	});

	// Admission errors remain repairable without authorizing task mutations.
	routingCheck("failed admission permits retry after mapping repair", async create => {
		const s = await create({ roles: { implementation: "" } });
		assertGap(await s.route());
		assertBlocked(await s.tool("write", { path: "task.txt" }));
		await s.request();
		s.roles.implementation = `${qualified(TERRA)}:high`;
		assert.notEqual((await s.route()).isError, true);
		assertAllowed(await s.tool("write", { path: "task.txt" }));
	});

	// A host fallback list must not be treated as an undertaking model lock.
	routingCheck("initial selection does not preflight unrelated fallback candidates", async create => {
		const s = await create({ candidates: async () => [qualified(FOREIGN)] });
		assert.notEqual((await s.route({ modelClass: "reasoning" })).isError, true);
		assert.equal(s.current(), REASONING);
	});

	// A selection made during asynchronous preflight must win over later setters.
	routingCheck("operator change during preflight prevents late setters", async create => {
		const entered = deferred();
		const proceed = deferred();
		let first = true;
		const s = await create({ getApiKey: async () => {
			if (first) { first = false; entered.resolve(); await proceed.promise; }
			return "offline-key";
		} });
		const routing = s.route({ modelClass: "reasoning" });
		await entered.promise;
		s.setCurrent(FOREIGN); s.setEffort("medium");
		proceed.resolve();
		assert.notEqual((await routing).isError, true);
		assert.equal(s.current(), FOREIGN);
		assert.equal(s.effort(), "medium");
		assert.deepEqual(s.calls.models, []);
		assert.deepEqual(s.calls.effort, []);
		await s.prompt(); await s.request();
		assertAllowed(await s.tool("write", { path: "task.txt" }));
	});

	// A crash while a model setter is pending must not persist a completed selection.
	routingCheck("pending setter has no active saved admission", async create => {
		const entered = deferred();
		const proceed = deferred();
		const s = await create({ setModel: async (selected, update) => {
			entered.resolve(); await proceed.promise; update(selected); return true;
		} });
		const routing = s.route({ modelClass: "reasoning" });
		await entered.promise;
		assert.equal(s.entries.some(entry => entry.data?.lifecycle === "active"), false);
		proceed.resolve();
		assert.notEqual((await routing).isError, true);
		assert.equal(s.entries.at(-1).data.lifecycle, "active");
	});

	for (const failure of ["model", "effort", "credential"]) {
		// Setter and credential failures must not be reported as a successful admission.
		routingCheck(`${failure} failure reports an admission gap`, async create => {
			const options = failure === "model" ? { setModel: async () => false } : failure === "effort"
				? { setThinkingLevel: () => { throw new Error("fixture effort failure"); } }
				: { getApiKey: async () => undefined };
			const s = await create(options);
			assertGap(await s.route({ modelClass: failure === "effort" ? "mechanical" : "reasoning" }));
			assertBlocked(await s.tool("write", { path: "task.txt" }));
			assert.notEqual(s.entries.at(-1)?.data?.lifecycle, "active");
			const resumed = await create({ entries: structuredClone(s.entries) });
			assert.equal(resumed.describe().undertaking, null);
			assert.notEqual((await resumed.route()).isError, true);
		});
	}

	// A different issue or wrong finish must not displace the active owner.
	routingCheck("owner rejects another issue and mismatched finish", async create => {
		const s = await create();
		await s.route();
		assertGap(await s.route({ issue: 756 }), /owns/iu);
		assertGap(await s.finish(756), /matching/iu);
		assert.equal(s.describe().undertaking.issue, 755);
		assertAllowed(await s.tool("write", { path: "task.txt" }));
	});

	// Cancellation must not finish the task or accept a different issue as owner.
	routingCheck("cancellation checks ownership and records cancellation", async create => {
		const s = await create();
		await s.route();
		const before = s.entries.length;
		await s.command("cancel 756");
		assert.equal(s.calls.aborts, 0);
		assert.equal(s.entries.length, before);
		assert.equal(s.describe().undertaking.issue, 755);
		await s.command("cancel 755");
		assert.equal(s.calls.aborts, 1);
		assert.equal(s.describe().undertaking, null);
		assert.equal(s.entries.at(-1).data.lifecycle, "cancelled");
	});

	// Cancellation must wait for in-flight work before releasing ownership.
	routingCheck("cancellation waits for idle", async create => {
		const idle = deferred();
		let quiescent = false;
		const s = await create({ waitForIdle: () => idle.promise, isIdle: () => quiescent });
		await s.route();
		const cancelling = s.command("cancel 755");
		assert.equal(s.describe().undertaking.issue, 755);
		quiescent = true; idle.resolve();
		await cancelling;
		assert.equal(s.describe().undertaking, null);
	});

	// Child model choice is independent, but cancellation still revokes an owned child.
	routingCheck("child uses its own route and is retired on parent cancellation", async create => {
		const parent = await create();
		await parent.route();
		const childId = `child-${++nextSession}`;
		assertAllowed(await parent.spawn(childId));
		const child = await create({ auth: parent.auth, parentId: parent.agentId, agentId: childId, current: FOREIGN });
		await child.request();
		assertAllowed(await child.tool("write", { path: "task.txt" }));
		assert.equal(child.current(), FOREIGN);
		await parent.command("cancel 755");
		assertBlocked(await child.tool("write", { path: "task.txt" }));
		await assert.rejects(child.request(), /cancelled/iu);
		assert.equal(child.entries.at(-1).data.retired, true);
	});

	// OAuth restrictions owned by the host must not be created or released by routing.
	routingCheck("admission and finish do not modify authentication restrictions", async create => {
		const s = await create();
		await s.route();
		await s.finish();
		assert.deepEqual(s.auth.calls.restrict, []);
		assert.deepEqual(s.auth.calls.unrestrict, []);
	});
}
