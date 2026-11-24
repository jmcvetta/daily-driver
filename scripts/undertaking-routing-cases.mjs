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
		async setThinkingLevel(value) {
			calls.effort.push(value);
			if (options.setThinkingLevel) return options.setThinkingLevel(value, selected => { effort = selected; });
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
	const api = installUndertakingRouting(pi, async () => settings, options.onCompleted, options.onStopping);
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
		route: (params = {}, signal) => tools.get("daily_driver_route_undertaking").execute("route", { issue: 755, modelClass: "routine", ...params }, signal, undefined, ctx),
		finish: (issue = 755) => tools.get("daily_driver_finish_undertaking").execute("finish", { issue }, undefined, undefined, ctx),
		command: args => commands.get("undertaking").handler(args, ctx),
		tool: (toolName, input = {}) => fire("tool_call", { toolName, input }),
		prompt: () => fire("before_agent_start", { prompt: "Continue" }),
		request: () => fire("before_provider_request", { payload: { model: current.id } }),
		assistant: () => fire("assistant_message", { message: { role: "assistant", provider: current.provider, model: current.id, content: [{ type: "text", text: "Response" }] } }),
		emitRoute: () => fire("assistant_message", { message: { content: [{ type: "toolCall", name: "daily_driver_route_undertaking" }] } }),
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

	for (const schema of [1, 2, 3]) {
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

	// A missing, cleared, invalid or unavailable effective role must not revive a family map.
	for (const value of [undefined, "", null, 42, "openai-codex/missing-model:high"]) {
		routingCheck(`unusable effective role ${String(value)} continues without substitution`, async create => {
			const s = await create({ current: REASONING, roles: { routine: value } });
			const result = await s.route();
			assert.notEqual(result.isError, true);
			assert.match(result.content[0].text, /routine.*Actual route:.*Ordinary work can continue/su);
			assert.equal(s.describe().undertaking.status, "informational");
			assert.equal(s.current(), REASONING);
			assert.deepEqual(s.calls.models, []);
			assert.deepEqual(s.calls.effort, []);
			assertAllowed(await s.tool("write", { path: "task.txt" }));
			s.roles.routine = qualified(FOREIGN);
			await s.route();
			assert.deepEqual(s.calls.models, []);
		});
	}

	// Effective assignments are authoritative, even across providers or for unfamiliar model names.
	for (const target of [MECHANICAL, FOREIGN, model("foobar-gigalarge-7", "catalog")]) {
		routingCheck(`DeepSeek uses configured mechanical ${target.id} and paired effort`, async create => {
			const s = await create({ current: DEEPSEEK, effort: "high",
				models: [...MODELS, target], roles: { mechanical: `${qualified(target)}:low` } });
			assert.notEqual((await s.route({ modelClass: "mechanical" })).isError, true);
			assert.equal(s.current(), target);
			assert.equal(s.effort(), "low");
			assert.equal(s.describe().undertaking.selectedModel, qualified(target));
		});
	}

	// No suffix and inherit preserve invoking effort; other supported suffixes go to the host.
	for (const suffix of ["", ":inherit", ":off", ":minimal", ":medium", ":xhigh", ":max", ":auto"]) {
		routingCheck(`effective role effort ${suffix || "absent"} uses host semantics`, async create => {
			const s = await create({ current: REASONING, effort: "low",
				roles: { routine: `${qualified(MECHANICAL)}${suffix}` } });
			await s.route();
			assert.equal(s.current(), MECHANICAL);
			assert.equal(s.effort(), !suffix || suffix === ":inherit" ? "low" : suffix.slice(1));
		});
	}

	// A Roles UI edit affects new issues, not re-entry on previously selected work.
	routingCheck("live role edits apply only to the next issue", async create => {
		const s = await create({ current: REASONING });
		await s.route();
		s.roles.routine = `${qualified(FOREIGN)}:low`;
		await s.route();
		assert.equal(s.current(), MECHANICAL);
		await s.route({ issue: 756 });
		assert.equal(s.current(), FOREIGN);
		assert.equal(s.effort(), "low");
		await s.route({ issue: 755 });
		assert.equal(s.current(), FOREIGN);
	});

	// Model and effort controls must both be present before the first mutation.
	for (const control of ["setModel", "setThinkingLevel"]) {
		routingCheck(`missing ${control} continues without partial mutation`, async create => {
			const s = await create({ current: REASONING });
			s.pi[control] = undefined;
			const result = await s.route({ modelClass: "mechanical" });
			assert.notEqual(result.isError, true);
			assert.match(result.content[0].text, /control is unavailable/u);
			assert.equal(s.current(), REASONING);
			assert.equal(s.effort(), "high");
			assert.deepEqual(s.calls.models, []);
			assert.deepEqual(s.calls.effort, []);
		});
	}

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
		// Failure remains diagnostic and idempotent, not an admission barrier.
		routingCheck(`${failure} failure continues and survives resume without reselection`, async create => {
			const options = failure === "model" ? { setModel: async () => false } : failure === "effort"
				? { setThinkingLevel: () => { throw new Error("fixture effort failure"); } }
				: { getApiKey: async () => undefined };
			const s = await create(options);
			const result = await s.route({ modelClass: failure === "effort" ? "mechanical" : "complex" });
			assert.notEqual(result.isError, true);
			assert.match(result.content[0].text, /Ordinary work can continue/u);
			assert.equal(s.current(), MECHANICAL);
			assert.equal(s.effort(), "high");
			assertAllowed(await s.tool("write", { path: "task.txt" }));
			await s.request();
			assertAllowed(await s.tool("task", {}));
			assert.equal(s.entries.at(-1)?.data?.status, "informational");
			const resumed = await create({ entries: structuredClone(s.entries), current: FOREIGN, effort: "medium" });
			assert.equal(resumed.describe().undertaking.issue, 755);
			assert.notEqual((await resumed.route()).isError, true);
			assert.deepEqual(resumed.calls.models, []);
			assert.deepEqual(resumed.calls.effort, []);
			assert.equal(resumed.current(), FOREIGN);
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

	// Selecting another issue must retain old cancellation ownership without false completion.
	routingCheck("new issue needs no finish and retains old owned children", async create => {
		const completions = [];
		const s = await create({ onCompleted: (_ctx, issue) => completions.push(issue) });
		await s.route();
		const childId = `older-child-${++nextSession}`;
		await s.spawn(childId);
		const child = await create({ auth: s.auth, parentId: s.agentId, agentId: childId });
		assert.notEqual((await s.route({ issue: 756, modelClass: "complex" })).isError, true);
		assert.equal(s.current(), REASONING);
		assert.equal(s.describe().undertaking.issue, 756);
		assertGap(await s.finish(757), /matching/iu);
		assert.deepEqual(completions, []);
		await s.command("cancel 755");
		assert.equal(child.calls.aborts, 1);
		assertBlocked(await child.spawn("retired-old-grandchild"));
		assert.equal(s.describe().undertaking.issue, 756);
		assert.deepEqual(completions, []);
		const resumed = await create({ entries: structuredClone(s.entries), current: FOREIGN });
		await resumed.route({ issue: 756 });
		assert.deepEqual(resumed.calls.models, []);
		assert.equal(resumed.current(), FOREIGN);
		assert.notEqual((await s.finish(756)).isError, true);
		assertGap(await s.finish(756));
		assert.deepEqual(completions, [756]);
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

	// A failed watch stop must leave cancellation retryable and must not abort work.
	routingCheck("watch stop precedes cancellation and reports failure", async create => {
		let reject = true;
		const s = await create({ onStopping: async (_ctx, issue) => {
			assert.equal(issue, 755);
			assert.equal(s.calls.aborts, 0);
			if (reject) throw new Error("watch stop failed");
		} });
		await s.route();
		await s.command("cancel 756");
		await s.command("cancel 755");
		assert.equal(s.calls.aborts, 0);
		assert.equal(s.describe().undertaking.issue, 755);
		assert.match(s.calls.notifications.at(-1).message, /watch stop failed/u);
		reject = false;
		await s.command("cancel 755");
		assert.equal(s.calls.aborts, 1);
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

	// Tool emission cannot leave a phantom selection after a completed early return.
	for (const outcome of ["completed", "invalid", "cancelled", "aborted"]) {
		routingCheck(`emitted ${outcome} re-entry reports no phantom selection`, async create => {
			const s = await create();
			await s.route();
			if (outcome === "cancelled") await s.command("cancel 755");
			else await s.finish();
			await s.emitRoute();
			const controller = new AbortController();
			if (outcome === "aborted") controller.abort();
			const result = await s.route(outcome === "invalid" ? { modelClass: "invalid" } : {}, controller.signal);
			if (outcome !== "completed") assertGap(result);
			else assert.notEqual(result.isError, true);
			await s.command("status");
			const info = JSON.parse(s.calls.notifications.at(-1).message);
			assert.equal(info.state, outcome === "cancelled" ? "cancelled" : "none");
			await s.command("cancel 755");
			assert.match(s.calls.notifications.at(-1).message, /No active undertaking/u);
		});
	}

	// An early return must not clear the marker for another selector that is actually pending.
	routingCheck("emitted re-entry preserves a genuinely in-flight selection", async create => {
		const entered = deferred();
		const proceed = deferred();
		const s = await create({ getApiKey: async () => {
			entered.resolve(); await proceed.promise; return "fixture";
		} });
		const selection = s.route({ modelClass: "complex" });
		await entered.promise;
		await s.emitRoute();
		const result = await s.route();
		assert.match(result.content[0].text, /already in progress/u);
		await s.command("status");
		assert.equal(JSON.parse(s.calls.notifications.at(-1).message).state, "selecting");
		proceed.resolve();
		await selection;
		await s.finish();
		await s.command("status");
		assert.equal(JSON.parse(s.calls.notifications.at(-1).message).state, "none");
		await s.command("cancel 755");
		assert.match(s.calls.notifications.at(-1).message, /No active undertaking/u);
	});

	// A failure after either setter must restore only selector-owned changes.
	for (const mutatedEffort of [false, true]) {
		routingCheck(`partial switch restores invoking route after effort ${mutatedEffort ? "mutation" : "rejection"}`, async create => {
			let first = true;
			const s = await create({ current: REASONING,
				setThinkingLevel: (value, update) => {
					if (first) {
						first = false;
						if (mutatedEffort) update(value);
						throw new Error("effort rejected");
					}
					update(value);
				} });
			const result = await s.route({ modelClass: "mechanical" });
			assert.notEqual(result.isError, true);
			assert.equal(s.current(), REASONING);
			assert.equal(s.effort(), "high");
			assert.deepEqual(s.calls.models, [MECHANICAL, REASONING]);
			assert.equal(s.describe().undertaking.observedModel, qualified(REASONING));
		});
	}

	// Restoration failure must name the actual partial route, not claim retention.
	routingCheck("rejected restoration reports actual partial route", async create => {
		const s = await create({ current: REASONING,
			setModel: async (value, update) => {
				if (value === REASONING) return false;
				update(value); return true;
			},
			setThinkingLevel: () => { throw new Error("effort unavailable"); } });
		const result = await s.route({ modelClass: "mechanical" });
		assert.notEqual(result.isError, true);
		assert.equal(s.current(), MECHANICAL);
		assert.equal(s.effort(), "high");
		assert.match(result.content[0].text, /restoration failed.*Actual route: openai-codex\/gpt-6-luna\/high/u);
		assert.equal(s.describe().undertaking.selectedModel, null);
	});

	// Operator changes during an asynchronous setter must survive failure cleanup.
	routingCheck("operator change during pending effort survives failure", async create => {
		const entered = deferred();
		const proceed = deferred();
		const s = await create({ current: REASONING, setThinkingLevel: async () => {
			entered.resolve(); await proceed.promise; throw new Error("late effort rejection");
		} });
		const selection = s.route({ modelClass: "mechanical" });
		await entered.promise;
		s.setCurrent(FOREIGN); s.setEffort("medium");
		proceed.resolve();
		assert.notEqual((await selection).isError, true);
		assert.equal(s.current(), FOREIGN);
		assert.equal(s.effort(), "medium");
		assert.deepEqual(s.calls.models, [MECHANICAL]);
		assert.equal(s.describe().undertaking.observedModel, qualified(FOREIGN));
	});

	// Failure to store a result cannot require repair or cause same-issue reselection.
	for (const permanent of [false, true]) {
		routingCheck(`${permanent ? "permanent" : "transient"} persistence failure is informational`, async create => {
			let attempts = 0;
			const s = await create({ current: REASONING, appendEntry: () => {
				if (permanent || attempts++ === 0) throw new Error("storage unavailable");
			} });
			const result = await s.route({ modelClass: "mechanical" });
			assert.notEqual(result.isError, true);
			assert.match(result.content[0].text, /storage unavailable.*Ordinary work can continue/u);
			assert.equal(s.current(), REASONING);
			assert.equal(s.effort(), "high");
			const calls = s.calls.models.length;
			await s.route();
			assert.equal(s.calls.models.length, calls);
			assertAllowed(await s.tool("write"));
			await s.route({ issue: 756 });
			assert.equal(s.describe().undertaking.issue, 756);
		});
	}

	// A corrupt routing record does not disable work or require cancellation before a new issue.
	routingCheck("malformed metadata has local recovery and allows new work", async create => {
		const s = await create({ entries: [{type:"custom",customType:"daily-driver-undertaking-route",data:{schema:99}}] });
		assert.equal(s.describe().undertaking.status, "informational");
		assertAllowed(await s.tool("write"));
		assert.notEqual((await s.route({ issue: 756 })).isError, true);
		assert.equal(s.describe().undertaking.issue, 756);
	});

	// Cancellation during preflight is not informational continuation and cannot restart on reload.
	routingCheck("cancellation during selection preserves tombstone", async create => {
		const entered = deferred();
		const proceed = deferred();
		const s = await create({ getApiKey: async () => {
			entered.resolve(); await proceed.promise; return "fixture";
		} });
		const selection = s.route({ modelClass: "complex" });
		await entered.promise;
		await s.command("cancel 755");
		proceed.resolve();
		assertGap(await selection, /stopped/u);
		assert.deepEqual(s.calls.models, []);
		assertGap(await s.route());
		const resumed = await create({ entries: structuredClone(s.entries) });
		assertGap(await resumed.route());
		assert.deepEqual(resumed.calls.models, []);
	});

	// An aborted tool signal must retain a stop even when a model setter is pending.
	routingCheck("aborted pending setter stays stopped", async create => {
		const entered = deferred();
		const proceed = deferred();
		const controller = new AbortController();
		const s = await create({ setModel: async (value, update) => {
			entered.resolve(); await proceed.promise; update(value); return true;
		} });
		const selection = s.route({ modelClass: "complex" }, controller.signal);
		await entered.promise; controller.abort(); proceed.resolve();
		assertGap(await selection, /stopped/u);
		assertBlocked(await s.spawn("aborted-child"));
		assertGap(await s.route());
		assert.equal(s.entries.at(-1).data.lifecycle, "cancelled");
	});

	// All owned children stop before cancellation completes; unrelated sessions remain untouched.
	routingCheck("cancellation waits for children and isolates unrelated work", async create => {
		const parent = await create();
		const unrelated = await create({ auth: parent.auth });
		await parent.route();
		await unrelated.route({ issue: 900 });
		const childId = `waiting-child-${++nextSession}`;
		await parent.spawn(childId);
		const entered = deferred();
		const proceed = deferred();
		const child = await create({ auth: parent.auth, parentId: parent.agentId, agentId: childId,
			waitForIdle: async () => { entered.resolve(); await proceed.promise; } });
		const cancellation = parent.command("cancel 755");
		await entered.promise;
		assert.equal(parent.describe().undertaking.issue, 755);
		assert.equal(child.calls.aborts, 1);
		assert.equal(unrelated.calls.aborts, 0);
		proceed.resolve(); await cancellation;
		assert.equal(parent.describe().undertaking, null);
		assertAllowed(await unrelated.spawn("unrelated-child"));
		const entries = structuredClone(child.entries);
		entries.at(-1).data.schema = 999;
		const resumed = await create({ entries, auth: parent.auth, parentId: parent.agentId, agentId: childId });
		assertBlocked(await resumed.spawn("corrupt-retired-child"));
		assertGap(await resumed.route());
	});
}
