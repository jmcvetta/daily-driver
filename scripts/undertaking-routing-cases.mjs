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
const DEEPSEEK = model("deepseek/deepseek-v4.1-flash-1017", "vercel-ai-gateway", "openai-compatible");
const DEEPSEEK_PRO = model("deepseek-v4-pro-0813", "vercel-ai-gateway", "openai-compatible");
const GATEWAY_LUNA = model("openai/gpt-6-luna", "vercel-ai-gateway", "openai-compatible");
const GATEWAY_SOL = model("openai/gpt-6.1-sol", "vercel-ai-gateway", "openai-compatible");
const BACKEND_MISMATCH = model("gpt-luna-other-api", "openai-codex", "openai-completions");
const FOREIGN = model("claude-sonnet", "anthropic", "anthropic-messages");
const MODELS = [MECHANICAL, TERRA, REASONING, FRONTIER, FOREIGN, DEEPSEEK, DEEPSEEK_PRO, BACKEND_MISMATCH];
const familyOf = value => value.provider === "anthropic" ? "claude"
	: value.id.includes("deepseek") ? "deepseek" : "gpt";
const gatewayFamily = value => value.provider === "anthropic" ? "claude"
	: value.id.includes("deepseek") ? "deepseek"
	: value.provider === "vercel-ai-gateway" || value.provider === "openai-codex" ? "openai" : "gpt";
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
		appendEntry: async (customType, data) => {
			if (options.appendEntry) await options.appendEntry(customType, data);
			entries.push({ type: "custom", customType, data: structuredClone(data) });
		},
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
			family: candidate => options.family ? options.family(candidate) : familyOf(candidate),
		},
		modelRegistry: { authStorage: auth, getApiKey: options.getApiKey ?? (async () => "offline-key") },
		abort: () => { calls.aborts++; },
		isIdle: () => options.isIdle?.() ?? true,
		waitForIdle: async () => { if (options.waitForIdle) await options.waitForIdle(); },
		ui: { notify: (message, type) => calls.notifications.push({ message, type }), setStatus() {} },
	};
	Object.defineProperty(ctx, "model", { get: () => current });
	const api = installUndertakingRouting(pi, async () => settings, options.routes ? () => options.routes : undefined,
		options.onCompleted);
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
		route: (params = {}) => tools.get("daily_driver_route_undertaking").execute("route", { issue: 755, modelClass: "routine", ...params }, undefined, undefined, ctx),
		finish: (issue = 755) => tools.get("daily_driver_finish_undertaking").execute("finish", { issue }, undefined, undefined, ctx),
		command: args => commands.get("undertaking").handler(args, ctx),
		tool: (toolName, input = {}) => fire("tool_call", { toolName, input }),
		prompt: () => fire("before_agent_start", { prompt: "Continue" }),
		request: () => fire("before_provider_request", { payload: { model: current.id } }),
		assistant: () => fire("assistant_message", { message: { role: "assistant", provider: current.provider, model: current.id, content: [{ type: "text", text: "Response" }] } }),
		spawn: (key, patterns = [qualified(FOREIGN)], agent = "routine", modelRole = "routine") =>
			fire("before_subagent_spawn", { agent, modelRole, patterns, spawnKey: key }),
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

	// Former class tokens must not select a route after the cutover.
	for (const modelClass of ["implementation", "integration", "reasoning"]) {
		routingCheck(`rejects former class ${modelClass}`, async create => {
			const s = await create();
			assertGap(await s.route({ modelClass }));
			assert.deepEqual(s.calls.models, []);
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
				await s.route({ modelClass: "complex" });
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
		await s.route({ modelClass: "complex" });
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
			await first.route({ modelClass: "complex" });
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

	// Removed authorization fields must not be required to continue a saved route.
	routingCheck("saved record without obsolete route fields resumes", async create => {
		const first = await create();
		await first.route({ modelClass: "complex" });
		const entries = structuredClone(first.entries);
		const saved = entries.at(-1).data;
		delete saved.origin;
		delete saved.authenticationRoute;
		delete saved.frontierApproval;
		const resumed = await create({ entries, current: FOREIGN, effort: "medium" });
		assert.equal(resumed.describe().undertaking.issue, 755);
		assert.equal(resumed.describe().undertaking.modelClass, "complex");
		assertAllowed(await resumed.tool("write", { path: "task.txt" }));
		assert.equal(resumed.current(), FOREIGN);
		assert.equal(resumed.effort(), "medium");
	});

	// Existing session records must resume without accepting old tokens for new admissions.
	for (const [oldClass, newClass] of [["implementation", "routine"], ["integration", "intermediate"], ["reasoning", "complex"]]) {
		routingCheck(`legacy ${oldClass} session resumes as ${newClass}`, async create => {
			const first = await create();
			await first.route({ modelClass: newClass });
			const entries = structuredClone(first.entries);
			entries.at(-1).data.schema = 2;
			entries.at(-1).data.modelClass = oldClass;
			const resumed = await create({ entries });
			assert.equal(resumed.describe().undertaking.modelClass, newClass);
			assertAllowed(await resumed.tool("write", { path: "task.txt" }));
		});
	}

	// Finishing an owner must allow the next issue to perform a fresh selection.
	routingCheck("new issue selects its own initial route after finish", async create => {
		const s = await create();
		await s.route({ modelClass: "complex" });
		assert.notEqual((await s.finish()).isError, true);
		s.setCurrent(MECHANICAL); s.setEffort("low");
		assert.notEqual((await s.route({ issue: 756, modelClass: "intermediate" })).isError, true);
		assert.equal(s.current(), TERRA);
		assert.equal(s.effort(), "medium");
		assert.equal(s.describe().undertaking.issue, 756);
	});

	for (const selector of [undefined, "", "openai-codex/missing-model:high"]) {
		// Invalid explicit roles must fall back to a valid family route.
		routingCheck(`invalid explicit class role ${String(selector)} falls back to family route`, async create => {
			const s = await create({ roles: { routine: selector } });
			const result = await s.route();
			assert.notEqual(result.isError, true, JSON.stringify(result));
			assert.equal(s.describe().undertaking.capability, "mapped");
			assert.equal(s.describe().undertaking.selectedModel, qualified(MECHANICAL));
			assert.deepEqual(s.calls.models, []);
			assertAllowed(await s.tool("write", { path: "task.txt" }));
		});
	}
	// A compatible explicit role keeps the expected same-family downgrade.
	routingCheck("same-family explicit role still downgrades", async create => {
		const s = await create({ current: REASONING, roles: { routine: `${qualified(MECHANICAL)}:low` } });
		assert.notEqual((await s.route()).isError, true);
		assert.equal(s.current(), MECHANICAL);
		assert.equal(s.effort(), "low");
		assert.deepEqual(s.calls.models, [MECHANICAL]);
	});

	// A cross-family explicit role falls back to the family-mapped route.
	routingCheck("cross-family explicit role falls back to family route", async create => {
		const s = await create({ roles: { routine: qualified(FOREIGN) } });
		assert.notEqual((await s.route()).isError, true);
		assert.equal(s.current(), MECHANICAL);
		assert.equal(s.describe().undertaking.capability, "mapped");
		assert.deepEqual(s.calls.models, []);
	});

	// The measured DeepSeek mapping selects mechanical and routine within the invoking provider.
	for (const [modelClass, expectedEffort, effortCalls] of [["mechanical", "low", ["low"]], ["routine", "high", []]]) {
		routingCheck(`mapped DeepSeek family selects ${modelClass}`, async create => {
			const s = await create({ current: DEEPSEEK_PRO, family: familyOf });
			const result = await s.route({ modelClass });
			assert.notEqual(result.isError, true, JSON.stringify(result));
			assert.doesNotMatch(result.content[0].text, /WARNING/iu);
			assert.equal(s.current(), DEEPSEEK);
			assert.equal(s.current().provider, DEEPSEEK_PRO.provider);
			assert.equal(s.effort(), expectedEffort);
			assert.equal(s.describe().undertaking.capability, "mapped");
			assert.equal(s.describe().undertaking.selectedModel, qualified(DEEPSEEK));
			assert.deepEqual(s.calls.models, [DEEPSEEK]);
			assert.deepEqual(s.calls.effort, effortCalls);
		});
	}

	// An already selected Flash model must change only the effort its class requires.
	routingCheck("already selected Flash model changes only effort", async create => {
		const s = await create({ current: DEEPSEEK, effort: "low", family: familyOf });
		assert.notEqual((await s.route({ modelClass: "routine" })).isError, true);
		assert.equal(s.current(), DEEPSEEK);
		assert.equal(s.effort(), "high");
		assert.deepEqual(s.calls.models, []);
		assert.deepEqual(s.calls.effort, ["high"]);
	});

	// Unmeasured classes on a mapped family warn and continue instead of failing admission.
	for (const modelClass of ["intermediate", "complex"]) {
		routingCheck(`omitted DeepSeek ${modelClass} class warns and continues`, async create => {
			const s = await create({ current: DEEPSEEK, family: familyOf });
			const result = await s.route({ modelClass });
			assert.notEqual(result.isError, true, JSON.stringify(result));
			assert.match(result.content[0].text,
				new RegExp(`WARNING: Family deepseek has no ${modelClass} route for provider vercel-ai-gateway`, "iu"));
			assert.equal(s.current(), DEEPSEEK);
			assert.equal(s.effort(), "high");
			assert.equal(s.describe().undertaking.capability, "unverified");
			assert.deepEqual(s.calls.models, []);
		});
	}

	// An explicitly cleared class on the DeepSeek row stays a precise configuration gap.
	routingCheck("mapped DeepSeek family rejects an explicitly cleared class", async create => {
		const s = await create({ current: DEEPSEEK_PRO, family: familyOf,
			routes: [{ referenceModel: qualified(DEEPSEEK), classes: { routine: null } }] });
		assertGap(await s.route(), /cleared for routine/iu);
		assert.equal(s.current(), DEEPSEEK_PRO);
		assert.deepEqual(s.calls.models, []);
	});

	// The mapping must not invent a Flash target in a provider that does not carry it.
	routingCheck("DeepSeek mapping does not manufacture a target in another provider", async create => {
		const elsewherePro = model("deepseek-v4-pro-0813", "other-gateway", "openai-compatible");
		const s = await create({ current: elsewherePro, models: [elsewherePro, ...MODELS], family: familyOf });
		assertGap(await s.route({ modelClass: "routine" }), /unavailable in the invoking provider/iu);
		assert.equal(s.current(), elsewherePro);
		assert.deepEqual(s.calls.models, []);
	});

	// A family mapping resolves its configured class identity through the invoking provider.
	routingCheck("mapped family selects the matching model through the invoking provider", async create => {
		const models = [...MODELS, GATEWAY_LUNA, GATEWAY_SOL];
		const s = await create({ current: GATEWAY_SOL, models, family: gatewayFamily });
		const result = await s.route();
		assert.notEqual(result.isError, true, JSON.stringify(result));
		assert.doesNotMatch(result.content[0].text, /WARNING/iu);
		assert.equal(s.current(), GATEWAY_LUNA);
		assert.equal(s.current().provider, GATEWAY_SOL.provider);
		assert.equal(s.describe().undertaking.capability, "mapped");
		assert.equal(s.describe().undertaking.selectedModel, qualified(GATEWAY_LUNA));
		assert.deepEqual(s.calls.models, [GATEWAY_LUNA]);
	});

	// A mapped family with no matching provider model remains an admission gap.
	routingCheck("mapped family rejects an unavailable provider model", async create => {
		const s = await create({ current: GATEWAY_SOL,
			models: [...MODELS, GATEWAY_SOL],
			family: gatewayFamily });
		assertGap(await s.route(), /unavailable in the invoking provider/iu);
		assert.equal(s.current(), GATEWAY_SOL);
		assert.deepEqual(s.calls.models, []);
	});

	// Multiple same-identity catalog candidates must not make target selection arbitrary.
	routingCheck("mapped family rejects an ambiguous provider model", async create => {
		const duplicate = { ...GATEWAY_LUNA };
		const s = await create({ current: GATEWAY_SOL,
			models: [...MODELS, GATEWAY_LUNA, duplicate, GATEWAY_SOL],
			family: gatewayFamily });
		assertGap(await s.route(), /ambiguous in the invoking provider/iu);
		assert.equal(s.current(), GATEWAY_SOL);
		assert.deepEqual(s.calls.models, []);
	});

	// A cleared class in a mapped family is a configuration gap, not an unverified route.
	routingCheck("mapped family rejects a cleared class", async create => {
		const s = await create({ routes: [{ referenceModel: qualified(MECHANICAL), classes: { routine: null } }] });
		assertGap(await s.route(), /cleared for routine/iu);
		assert.equal(s.current(), MECHANICAL);
		assert.deepEqual(s.calls.models, []);
	});

	// A mapped target on another backend is a model choice, not a route violation.
	routingCheck("mapped class target may use another backend", async create => {
		const s = await create({
			models: [...MODELS],
			routes: [{ referenceModel: qualified(MECHANICAL), classes: { routine: qualified(BACKEND_MISMATCH) } }],
		});
		assert.notEqual((await s.route()).isError, true);
		assert.equal(s.current(), BACKEND_MISMATCH);
		assertAllowed(await s.tool("write", { path: "task.txt" }));
		await s.request();
		assertAllowed(await s.tool("task", {}));
	});

	// An unmapped family must continue on the invoking model rather than adopt default roles.
	routingCheck("unmapped family warns without switching", async create => {
		const unknown = model("unmapped-model", "unknown", "openai-completions");
		const s = await create({ current: unknown, models: [unknown, ...MODELS], family: value => value.provider === "unknown" ? "unmapped" : familyOf(value) });
		const result = await s.route();
		assert.notEqual(result.isError, true);
		assert.match(result.content[0].text, /WARNING/iu);
		assert.equal(s.current(), unknown);
		assert.deepEqual(s.calls.models, []);
	});

	// A frontier class is an initial selection, not a separate approval event.
	routingCheck("frontier class selection needs no approval", async create => {
		const s = await create();
		assert.notEqual((await s.route({ modelClass: "frontier" })).isError, true);
		assert.equal(s.current(), FRONTIER);
		assert.equal(s.describe().undertaking.modelClass, "frontier");
	});

	// Authentication-source metadata is reported, never used to reject a selection.
	routingCheck("missing authentication route metadata does not block selection", async create => {
		const auth = fakeAuth();
		auth.source = undefined;
		const s = await create({ auth });
		assert.notEqual((await s.route()).isError, true);
		assertAllowed(await s.tool("write", { path: "task.txt" }));
		assertAllowed(await s.tool("task", {}));
	});

	// The router selects once and never preflights a worker or fallback list.
	routingCheck("initial selection does not inspect fallback candidates", async create => {
		const s = await create();
		assert.notEqual((await s.route({ modelClass: "complex" })).isError, true);
		assert.equal(s.current(), REASONING);
		assertAllowed(await s.spawn("fallback-target", [qualified(FOREIGN)]));
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
		const routing = s.route({ modelClass: "complex" });
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
		const routing = s.route({ modelClass: "complex" });
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
			assertGap(await s.route({ modelClass: failure === "effort" ? "mechanical" : "complex" }));
			assertAllowed(await s.tool("write", { path: "task.txt" }));
			await s.request();
			assertAllowed(await s.tool("task", {}));
			assert.notEqual(s.entries.at(-1)?.data?.lifecycle, "active");
			const resumed = await create({ entries: structuredClone(s.entries) });
			assert.equal(resumed.describe().undertaking, null);
			assert.notEqual((await resumed.route()).isError, true);
		});
	}

	// A completion notification must follow both durable completion and release.
	routingCheck("completion callback runs only after persistence and owner release", async create => {
		const callbacks = [];
		let s;
		s = await create({ onCompleted: async (ctx, issue) => {
			callbacks.push({ ctx, issue, lifecycle: s.entries.at(-1)?.data?.lifecycle, owner: s.describe().undertaking });
		} });
		await s.route();
		assert.notEqual((await s.finish()).isError, true);
		assert.deepEqual(callbacks, [{ ctx: s.ctx, issue: 755, lifecycle: "completed", owner: null }]);
	});

	// Failed or cancelled ownership must never announce successful completion.
	routingCheck("wrong owner, cancellation and failed persistence do not call completion", async create => {
		const callbacks = [];
		let rejectCompletion = false;
		const s = await create({
			onCompleted: (...args) => callbacks.push(args),
			appendEntry: (_type, data) => {
				if (rejectCompletion && data.lifecycle === "completed") throw new Error("completion persistence failed");
			},
		});
		await s.route();
		assertGap(await s.finish(756));
		rejectCompletion = true;
		await assert.rejects(() => s.finish(), /completion persistence failed/u);
		assert.deepEqual(callbacks, []);
		rejectCompletion = false;
		await s.command("cancel 755");
		assert.deepEqual(callbacks, []);
	});

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

	// Cancellation failures must not block ordinary tools or prevent a retry.
	routingCheck("failed cancellation leaves tools available and can retry", async create => {
		const entered = deferred();
		const proceed = deferred();
		let fail = true;
		const s = await create({ waitForIdle: async () => {
			if (!fail) return;
			entered.resolve();
			await proceed.promise;
			throw new Error("fixture cancellation failure");
		} });
		await s.route();
		const cancelling = s.command("cancel 755");
		await entered.promise;
		assertAllowed(await s.tool("write", { path: "task.txt" }));
		assertAllowed(await s.tool("task", {}));
		proceed.resolve();
		await cancelling;
		assert.equal(s.describe().undertaking.issue, 755);
		assertAllowed(await s.tool("write", { path: "task.txt" }));
		fail = false;
		await s.command("cancel 755");
		assert.equal(s.describe().undertaking, null);
		assertAllowed(await s.tool("write", { path: "task.txt" }));
	});

	// An ordinary undertaking may dispatch any configured worker, provider or fallback.
	for (const worker of [FOREIGN, FRONTIER]) {
		routingCheck(`ordinary undertaking dispatches ${worker.id} without route approval`, async create => {
			const s = await create();
			await s.route();
			assertAllowed(await s.spawn(`worker-${worker.id}`, [qualified(worker)]));
		});
	}

	// A frontier undertaking dispatches ordinary workers the same way.
	routingCheck("frontier undertaking dispatches an ordinary worker", async create => {
		const s = await create();
		await s.route({ modelClass: "frontier" });
		assertAllowed(await s.spawn("ordinary", [qualified(TERRA)]));
	});

	// Native mentions and independently configured helpers are not route-gated.
	routingCheck("native mention and independent helper stay unrestricted", async create => {
		const s = await create();
		await s.route();
		s.entries.push({ type: "custom", customType: "model_mention", data: { agent: "m1", selector: qualified(FRONTIER), name: "Astra" } });
		assertAllowed(await s.spawn("mention", [qualified(FRONTIER)], "m1"));
		assertAllowed(await s.spawn("reviewer", [qualified(FRONTIER)], "reviewer", "reviewer"));
	});

	// Parent cancellation keeps ordinary child tools available but retires worker dispatch.
	routingCheck("child ordinary tools remain usable after parent cancellation", async create => {
		const parent = await create();
		await parent.route();
		const childId = `child-${++nextSession}`;
		assertAllowed(await parent.spawn(childId));
		const child = await create({ auth: parent.auth, parentId: parent.agentId, agentId: childId, current: FOREIGN });
		await child.request();
		assertAllowed(await child.tool("write", { path: "task.txt" }));
		assert.equal(child.current(), FOREIGN);
		await parent.command("cancel 755");
		assertAllowed(await child.tool("write", { path: "task.txt" }));
		await child.request();
		const dispatch = await child.spawn("cancelled-grandchild");
		assertBlocked(dispatch);
		assert.match(dispatch.reason, /cancelled/iu);
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

	// Ordinary tools remain available while route admission awaits credentials.
	routingCheck("pending selection leaves ordinary tools available", async create => {
		const entered = deferred();
		const proceed = deferred();
		const s = await create({ getApiKey: async () => {
			entered.resolve();
			await proceed.promise;
			return "offline-key";
		} });
		const routing = s.route({ modelClass: "complex" });
		await entered.promise;
		assertAllowed(await s.tool("write", { path: "task.txt" }));
		assertAllowed(await s.tool("task", {}));
		proceed.resolve();
		assert.notEqual((await routing).isError, true);
	});
}
