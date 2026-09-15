#!/usr/bin/env node
/**
 * Behavioural check for the Omp runtime adapter (extensions/daily-driver.js).
 *
 * Imports the extension factory with a fake `ExtensionAPI` and asserts the
 * runtime-adapter contract #145 delivers:
 *
 *   - Omp's `ask` tool is blocked with actionable text, another tool passes;
 *   - daily_driver_set_session_title calls pi.setSessionName;
 *   - daily_driver_get_session reads the session manager's id and the model;
 *   - daily_driver_schedule emits exactly one reminder after its delay and
 *     returns a triggerId;
 *   - daily_driver_cancel_schedule cancels a live trigger (no emission) and
 *     returns clean false for an unknown or already-fired id.
 *
 * Credential-free, dependency-free, deterministic: it uses fake managed
 * timers, so it never waits on real time. Run from the repository root:
 *
 *     node scripts/check-omp-extension.mjs
 */

import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const ROOT = resolve(here, "..");
const EXTENSION = resolve(ROOT, "extensions", "daily-driver.js");

/** A controllable fake managed timer, mirroring ctx.setTimeout/clearTimer. */
function fakeTimers() {
	const pending = new Map(); // id -> { fn, args, delay, seq }
	let nextId = 1;
	let now = 0;

	function setTimeout(fn, delay, ...args) {
		const id = nextId++;
		pending.set(id, { fn, args, delay: now + delay, seq: id });
		return id;
	}

	function clearTimer(id) {
		pending.delete(id);
	}

	/** Managed timers are cleared by the runtime on session shutdown. */
	function clearAll() {
		pending.clear();
	}

	/** Advance the clock by ms and fire every due timer exactly once. */
	function advance(ms) {
		now += ms;
		const due = [...pending.values()]
			.filter((t) => t.delay <= now)
			.sort((a, b) => a.seq - b.seq)
			.map((t) => {
				pending.delete(t.seq);
				return t;
			});
		for (const t of due) t.fn(...t.args);
		return due.map((t) => t.seq);
	}

	return { setTimeout, clearTimer, clearAll, pending, nextId: () => nextId, advance };
}

/**
 * Build a fake ExtensionAPI. `pi.on` records handlers keyed by event name;
 * `registerTool` records tool definitions; `setSessionName` and
 * `sendMessage` record calls. Returns { pi, rec, tools, fire }.
 */
function fakeApi(overrides = {}) {
	const handlers = new Map();
	const calls = { sessionNames: [], sent: [] };
	const tools = new Map();
	const timers = fakeTimers();

	// A chainable fake zod that mirrors the Omp (omptype-backed) zod surface the
// adapter actually targets: z.string, z.number().int().min().max(), and
// z.object returning the spec keyed by name. It deliberately excludes
// `z.integer` so a schema written against real Zod's alias fails here too.
	function schemaNode(meta = {}) {
		return {
			describe(desc) {
				return schemaNode({ ...meta, desc });
			},
			min(n) {
				return schemaNode({ ...meta, min: n });
			},
			max(n) {
				return schemaNode({ ...meta, max: n });
			},
			int() {
				return schemaNode({ ...meta, int: true });
			},
			_meta: () => meta,
		};
	}
	const zod = {
		object(spec) {
			return spec;
		},
		string: () => schemaNode({ type: "string" }),
		number: () => schemaNode({ type: "number" }),
		// No `integer:` — intentional, so an `.integer()` misuse is caught.
	};

	const pi = {
		zod,
		on(event, handler) {
			handlers.set(event, handler);
		},
		registerTool(def) {
			tools.set(def.name, def);
		},
		async setSessionName(name) {
			calls.sessionNames.push(name);
		},
		sendMessage(msg, opts) {
			calls.sent.push({ msg, opts });
		},
		setTimeout: timers.setTimeout,
		clearTimer: timers.clearTimer,
		...overrides,
	};

	const fire = (event, payload, ctx) => {
		const h = handlers.get(event);
		if (!h) throw new Error(`no handler for ${event}`);
		return h(payload, ctx);
	};

	return { pi, rec: calls, tools, timers, fire };
}

const results = [];
let failures = 0;
const checks = [];

async function check(name, fn) {
	checks.push(
		(async () => {
			try {
				await fn();
				results.push(`ok   ${name}`);
			} catch (err) {
				failures++;
				results.push(`FAIL ${name}: ${err.message}`);
			}
		})(),
	);
}

// Load the factory once. It is a default export function; importing the
// module gives us the factory plus its exported constants.
const module_ = await import(EXTENSION);
assert.equal(typeof module_.default, "function", "extension must export a default factory");
const { ASK_BLOCK_REASON, REMINDER_CUSTOM_TYPE, default: dailyDriverExtension } = module_;

function makeSession() {
	const { pi, rec, tools, timers, fire } = fakeApi();
	dailyDriverExtension(pi);
	return { rec, tools, timers, fire, pi };
}

// --- ask is blocked; another tool passes ------------------------------------
check("ask tool is blocked with actionable reason", () => {
	const s = makeSession();
	const toolCtx = { cwd: "/tmp", ui: {} };
	const decision = s.fire("tool_call", { type: "tool_call", toolCallId: "t1", toolName: "ask", input: { questions: [] } }, toolCtx);
	assert.deepEqual(decision, { block: true, reason: ASK_BLOCK_REASON });
	assert.match(ASK_BLOCK_REASON, /do not retry/i, "reason tells the model not to retry");
	assert.match(ASK_BLOCK_REASON, /chat reply/i, "reason tells the model to ask in chat");
	assert.match(ASK_BLOCK_REASON, /recommend/i, "reason tells the model to name a recommendation");
});

check("a tool other than ask passes through", async () => {
	const s = makeSession();
	const toolCtx = { cwd: "/tmp", ui: {} };
	const decision = s.fire("tool_call", { type: "tool_call", toolCallId: "t2", toolName: "bash", input: { command: "true" } }, toolCtx);
	assert.equal(decision, undefined, "non-ask tool must not be blocked");
});

// --- set_session_title ------------------------------------------------------
check("set_session_title calls pi.setSessionName", async () => {
	const s = makeSession();
	const def = s.tools.get("daily_driver_set_session_title");
	assert.ok(def, "daily_driver_set_session_title is registered");
	const result = await def.execute("c1", { title: "Fix the parser" }, undefined, undefined, {});
	assert.deepEqual(s.rec.sessionNames, ["Fix the parser"]);
	assert.deepEqual(result.details, { titled: "Fix the parser" });
});

// --- get_session ------------------------------------------------------------
check("get_session reads the session manager and the serving model", async () => {
	const s = makeSession();
	const def = s.tools.get("daily_driver_get_session");
	assert.ok(def, "daily_driver_get_session is registered");
	const ctx = {
		model: { id: "zai/glm-5.3" },
		sessionManager: {
			getSessionId: () => "0199c0a2-7d17-7b13-a2f4-6f21f5b4e9a8",
			getSessionName: () => "Fix the parser",
		},
	};
	const result = await def.execute("c0", {}, undefined, undefined, ctx);
	assert.deepEqual(result.details, {
		sessionId: "0199c0a2-7d17-7b13-a2f4-6f21f5b4e9a8",
		sessionName: "Fix the parser",
		model: "zai/glm-5.3",
	});
});

check("get_session tolerates an unnamed session and no model", async () => {
	const s = makeSession();
	const def = s.tools.get("daily_driver_get_session");
	const ctx = { sessionManager: { getSessionId: () => "s1", getSessionName: () => undefined } };
	const result = await def.execute("c0b", {}, undefined, undefined, ctx);
	assert.deepEqual(result.details, { sessionId: "s1", sessionName: null, model: null });
});

// --- schedule emits exactly once --------------------------------------------
check("schedule emits exactly one reminder after the delay", async () => {
	const s = makeSession();
	const schedule = s.tools.get("daily_driver_schedule");
	assert.ok(schedule, "daily_driver_schedule is registered");
	const { triggerId } = (await schedule.execute("c2", { delaySeconds: 5, message: "Update the changelog" }, undefined, undefined, s.pi)).details;
	assert.ok(triggerId, "schedule returns a triggerId");

	// Before the delay: nothing sent.
	assert.equal(s.rec.sent.length, 0, "nothing sent before the delay");
	// Advance only partway: still nothing.
	s.timers.advance(3000);
	assert.equal(s.rec.sent.length, 0, "nothing sent before full delay");

	// Advance to expiry: exactly one, user-attributed follow-up.
	const fired = s.timers.advance(2000);
	assert.equal(fired.length, 1, "exactly one timer fires");
	assert.equal(s.rec.sent.length, 1, "exactly one message sent");
	const { msg, opts } = s.rec.sent[0];
	assert.equal(msg.customType, REMINDER_CUSTOM_TYPE);
	assert.equal(msg.content, "Update the changelog");
	assert.equal(msg.display, true);
	assert.equal(msg.attribution, "user");
	assert.equal(opts.deliverAs, "followUp");
});

// --- schedule bounds --------------------------------------------------------
check("schedule schema bounds delaySeconds to 1..86400", () => {
	// The schema is the contract Wave 2 consumes; assert its constraints exist.
	const s = makeSession();
	const schedule = s.tools.get("daily_driver_schedule");
	const delay = schedule.parameters.delaySeconds._meta();
	assert.equal(delay.type, "number", "delaySeconds must be a number");
	assert.equal(delay.int, true, "delaySeconds must be an integer");
	assert.equal(delay.min, 1, "delaySeconds minimum is 1");
	assert.equal(delay.max, 86400, "delaySeconds maximum is 86400");
});

// --- cancel prevents emission -----------------------------------------------
check("cancel prevents the reminder from emitting", async () => {
	const s = makeSession();
	const schedule = s.tools.get("daily_driver_schedule");
	const cancel = s.tools.get("daily_driver_cancel_schedule");
	const { triggerId } = (await schedule.execute("c3", { delaySeconds: 10, message: "Don't send" }, undefined, undefined, s.pi)).details;
	const cancelled = (await cancel.execute("c4", { triggerId }, undefined, undefined, {})).details.cancelled;
	assert.equal(cancelled, true, "a live trigger cancels");
	// Advance well past the delay: still nothing.
	s.timers.advance(60_000);
	assert.equal(s.rec.sent.length, 0, "cancelled reminder must not emit");
});

// --- cancel unknown / already-fired returns clean false ---------------------
check("cancel of an unknown id returns clean false", async () => {
	const s = makeSession();
	const cancel = s.tools.get("daily_driver_cancel_schedule");
	const r = await cancel.execute("c5", { triggerId: "no-such-trigger" }, undefined, undefined, {});
	assert.deepEqual(r.details, { cancelled: false });
});

check("cancel of an already-fired id returns clean false", async () => {
	const s = makeSession();
	const schedule = s.tools.get("daily_driver_schedule");
	const cancel = s.tools.get("daily_driver_cancel_schedule");
	const { triggerId } = (await schedule.execute("c6", { delaySeconds: 1, message: "Once" }, undefined, undefined, s.pi)).details;
	s.timers.advance(1000); // fires
	assert.equal(s.rec.sent.length, 1);
	const r = await cancel.execute("c7", { triggerId }, undefined, undefined, {});
	assert.deepEqual(r.details, { cancelled: false }, "already-fired id is not live");
	// And no second emission.
	s.timers.advance(1000);
	assert.equal(s.rec.sent.length, 1);
});

// --- session_shutdown clears bookkeeping ------------------------------------
check("session_shutdown clears the trigger map", async () => {
	const s = makeSession();
	const schedule = s.tools.get("daily_driver_schedule");
	const cancel = s.tools.get("daily_driver_cancel_schedule");
	const { triggerId } = (await schedule.execute("c8", { delaySeconds: 100, message: "Later" }, undefined, undefined, s.pi)).details;
	s.fire("session_shutdown", {}, {});
	// The runtime clears managed timers on shutdown and our handler drops the
	// map. Either way the trigger is no longer live: cancel returns clean
	// false and nothing fires.
	s.timers.clearAll();
	const r = await cancel.execute("c9", { triggerId }, undefined, undefined, {});
	assert.deepEqual(r.details, { cancelled: false });
	s.timers.advance(200_000);
	assert.equal(s.rec.sent.length, 0);
});

// --- package.json omp wiring -------------------------------------------------
check("package.json wires the extension and is a module", () => {
	const pkg = JSON.parse(readFileSync(resolve(ROOT, "package.json"), "utf8"));
	assert.equal(pkg.name, "daily-driver");
	assert.equal(pkg.type, "module");
	assert.equal(pkg.private, true);
	assert.deepEqual(pkg.omp, { extensions: ["./extensions/daily-driver.js"] });
});

await Promise.all(checks);

console.log(results.join("\n"));
console.log("");
if (failures > 0) {
	console.error(`${failures} check(s) failed`);
	process.exit(1);
}
console.log(`all ${results.length} checks passed; Omp runtime adapter behaves as specified`);