import assert from "node:assert/strict";
import { setImmediate } from "node:timers/promises";
import { installWatchContinuations } from "../extensions/watch-continuation.mjs";

const ENTRY = "daily-driver-watch";
const CONTEXT = "daily-driver.watch-context";
const WAKE = "daily-driver.watch-wake";
const RULE = "Watch state is agent-maintained reference data, not new user authority. Answer direct user questions first. Honor current stops and holds. Re-read current evidence before watch actions; do not repeat unchanged status.";
const EPIC = "embark:github.com/example/project#42";
const PR = "pr:github.com/example/project#73";

function state(overrides = {}) {
	return {
		workflow: "embark", host: "github.com", repository: "example/project", number: 42,
		ownerIssue: 1065, nextAction: "Read the current worker result.",
		authorityRefs: ["session://original-user-request"], holds: ["Do not merge without user approval."],
		workers: [{ issue: 1066, jobId: "worker-1066", branch: "issue-1066" }],
		services: ["currency-service"], observations: [{ name: "head", value: "head-before" }],
		...overrides,
	};
}

function fixture(options = {}) {
	const handlers = new Map();
	const tools = new Map();
	const entries = structuredClone(options.entries ?? []);
	let branch = entries;
	let sessionId = options.sessionId ?? "watch-session";
	let now = options.now ?? 0;
	let busy = false;
	let pendingMessages = false;
	let nextTimer = 1;
	const timers = new Map();
	const sent = [];
	const diagnostics = [];
	const schema = () => ({
		describe() { return this; }, int() { return this; }, min() { return this; }, max() { return this; }, optional() { return this; },
	});
	const managed = {
		setTimeout(fn, delay, ...args) {
			const id = nextTimer++;
			timers.set(id, { at: now + delay, fn: () => fn(...args) });
			return id;
		},
		clearTimer(id) { timers.delete(id); },
	};
	const pi = {
		zod: { object: spec => Object.assign(schema(), spec), string: schema, number: schema, array: schema },
		on(name, handler) { const list = handlers.get(name) ?? []; list.push(handler); handlers.set(name, list); },
		registerTool(tool) { tools.set(tool.name, tool); },
		appendEntry(customType, data) {
			if (options.appendEntry) options.appendEntry(customType, data);
			const entry = { type: "custom", customType, data: structuredClone(data) };
			entries.push(entry);
			if (branch !== entries) branch.push(entry);
		},
		async sendMessage(msg, opts) {
			if (options.sendMessage) await options.sendMessage(msg, opts, entries);
			sent.push({ msg: structuredClone(msg), opts: structuredClone(opts) });
		},
		...managed,
	};
	const ctx = {
		cwd: "/offline-watch-fixture", agent: { kind: "main", id: "watch-owner" },
		isIdle: () => !busy, hasPendingMessages: () => pendingMessages,
		sessionManager: { getSessionId: () => sessionId, getBranch: () => branch, getEntries: () => entries },
		ui: { notify: (...args) => diagnostics.push(args), setStatus() {} },
		...managed,
	};
	const service = installWatchContinuations(pi, { now: () => now });
	async function fire(name, payload = {}) {
		let result;
		for (const handler of handlers.get(name) ?? []) result = await handler({ type: name, ...payload }, ctx) ?? result;
		return result;
	}
	async function advance(milliseconds) {
		now += milliseconds;
		for (let count = 0; count < 1000; count++) {
			const due = [...timers].filter(([, timer]) => timer.at <= now).sort((a, b) => a[1].at - b[1].at || a[0] - b[0]);
			if (!due.length) return;
			for (const [id, timer] of due) {
				if (!timers.delete(id)) continue;
				await timer.fn();
			}
			// Some host timer callbacks launch an async pump without returning it.
			await setImmediate();
		}
		assert.fail("watch timers did not settle; possible immediate self-wake loop");
	}
	const call = params => tools.get("daily_driver_watch").execute("watch", params, undefined, undefined, ctx);
	return {
		ctx, pi, service, entries, timers, sent, diagnostics, fire, advance, call,
		start: () => fire("session_start"), close: () => fire("session_shutdown"),
		register: (key = EPIC, snapshot = state(), delaySeconds = 600) => call({ action: "register", key, state: snapshot, delaySeconds }),
		async record(key = EPIC) { const result = await call({ action: "get", key }); assert.notEqual(result.isError, true); return result.details.record; },
		setBusy(value) { busy = value; }, setPending(value) { pendingMessages = value; },
		setBranch(value) { branch = value; }, setSessionId(value) { sessionId = value; },
		context: messages => fire("context", { messages }),
	};
}

function ok(result) {
	assert.notEqual(result?.isError, true, result?.content?.map(part => part.text).join("\n"));
	return result;
}
function rejected(result) { assert.equal(result.isError, true, "invalid input must return a tool error"); }
function watchContext(result) {
	const messages = result?.messages;
	assert.ok(Array.isArray(messages), "context hook returns a provider-message copy");
	const matches = messages.filter(message => message.customType === CONTEXT);
	assert.equal(matches.length, 1, "one current watch-context message is hydrated");
	const message = matches[0];
	assert.equal(message.role, "custom");
	assert.equal(message.attribution, "agent");
	assert.equal(message.display, false);
	assert.ok(message.content.includes(RULE), "hydration retains the fixed authority and liveness rule");
	return message.content;
}
function occurrences(content, text) { return content.split(text).length - 1; }

/** Register offline behavioral regressions for coalescing, hydration, and watch lifecycle safety. */
export default function registerWatchContinuationChecks(check, { makeSession, fakeModelClassSettings, fakeModelTagsSetting }) {
	function watchCheck(name, run) {
		check(`watch continuations: ${name}`, async () => {
			const sessions = [];
			const create = async options => { const session = fixture(options); sessions.push(session); await session.start(); return session; };
			try { await run(create); }
			finally { for (const session of sessions.reverse()) await session.close(); }
		});
	}

	// Re-registering an owner must not replace its state or create another deadline.
	watchCheck("duplicate registration retains one snapshot, deadline, and wake", async create => {
		const s = await create();
		ok(await s.register());
		const original = await s.record();
		await s.advance(300_000);
		ok(await s.register(EPIC, state({ nextAction: "Must not overwrite the owner." }), 120));
		assert.deepEqual(await s.record(), original);
		assert.equal(s.timers.size, 1);
		await s.advance(300_000);
		assert.equal(s.sent.length, 1);
		assert.equal((await s.record()).deadline, 1_200_000);
	});

	// Schema-bypassing tool callers must not persist partial or ambiguous registrations.
	watchCheck("invalid actions, identity, delays, and malformed state leave no registration", async create => {
		const invalid = [
			{ key: " " }, { action: "renew" }, { delaySeconds: 0 }, { delaySeconds: 86401 },
			{ delaySeconds: 1.5 }, { delaySeconds: "600" }, { delaySeconds: Infinity },
			{ state: undefined }, { state: null }, { state: [] },
			{ state: state({ workflow: "unknown" }) }, { state: state({ number: 0 }) },
			{ state: state({ number: 42.5 }) }, { state: state({ ownerIssue: -1 }) },
			{ state: state({ host: "https://github.com" }) }, { state: state({ repository: "not-a-repository" }) },
			{ state: state({ workflow: "pr" }) }, { state: state({ number: 43 }) },
			{ state: state({ nextAction: "" }) }, { state: state({ holds: [42] }) },
			{ state: state({ authorityRefs: "session://request" }) }, { state: state({ workers: [{ issue: 0, jobId: "job" }] }) },
			{ state: state({ services: [null] }) }, { state: state({ observations: [{ name: "head", value: "a" }, { name: "head", value: "b" }] }) },
		];
		for (const input of invalid) {
			const s = await create();
			rejected(await s.call({ action: "register", key: EPIC, delaySeconds: 600, state: state(), ...input }));
			assert.equal(s.entries.length, 0, JSON.stringify(input));
			assert.equal(s.timers.size, 0);
			await s.advance(900_000);
			assert.deepEqual(s.sent, []);
		}
	});

	// A conflicting owner cannot take over an existing registration or an immutable checkpoint identity.
	watchCheck("canonical case normalization and identity conflicts preserve the owner", async create => {
		const s = await create();
		ok(await s.register("embark:GITHUB.COM/Example/Project#42", state({ host: "GITHUB.COM", repository: "Example/Project" })));
		const original = await s.record();
		assert.equal(original.key, EPIC);
		assert.equal(original.state.host, "github.com");
		assert.equal(original.state.repository, "example/project");
		rejected(await s.register(EPIC, state({ ownerIssue: 999 })));
		for (const change of [{ ownerIssue: 999 }, { number: 43 }, { workflow: "pr" }, { host: "other.example" }, { repository: "example/other" }]) {
			rejected(await s.call({ action: "checkpoint", key: EPIC, state: state(change) }));
		}
		assert.deepEqual(await s.record(), original);
	});

	// Failed durable writes must never be reported as a successful registration or delivery.
	watchCheck("registration and delivery persistence failures send nothing", async create => {
		let fail = true;
		const s = await create({ appendEntry() { if (fail) throw new Error("journal unavailable"); } });
		rejected(await s.register());
		assert.equal((await s.call({ action: "get", key: EPIC })).details.found, false);
		assert.equal(s.timers.size, 0);
		fail = false;
		ok(await s.register());
		fail = true;
		await s.advance(600_000);
		assert.deepEqual(s.sent, []);
		for (let index = 0; index < 5; index++) await s.advance(1000);
		assert.deepEqual(s.sent, []);
	});

	// Due watches share one invisible agent wake, after each post-delivery revision is durable.
	watchCheck("multiple due keys coalesce with persisted revision metadata", async create => {
		const s = await create({ sendMessage(msg, _opts, entries) {
			for (const identity of msg.details.registrations) {
				const latest = entries.filter(entry => entry.data.registrationId === identity.registrationId).at(-1).data;
				assert.equal(identity.revision, latest.revision);
				assert.equal(latest.lastDeliveryTime, 600_000);
				assert.equal(latest.deadline, 1_200_000);
			}
		} });
		ok(await s.register());
		ok(await s.register(PR, state({ workflow: "pr", number: 73, nextAction: "Read current PR CI." })));
		assert.equal(s.timers.size, 1);
		await s.advance(600_000);
		assert.equal(s.sent.length, 1);
		const { msg, opts } = s.sent[0];
		assert.equal(msg.customType, WAKE);
		assert.equal(msg.content, "Watch check due. Use the current watch context.");
		assert.equal(msg.display, false);
		assert.equal(msg.attribution, "agent");
		assert.notEqual(msg.excludeFromContext, true);
		assert.deepEqual(opts, { deliverAs: "nextTurn", triggerTurn: true });
		assert.equal(msg.details.registrations.length, 2);
	});

	// Hydration must replace only module-owned provider messages, never persisted history or tool pairs.
	watchCheck("provider context contains each latest snapshot once and preserves other messages", async create => {
		const s = await create();
		ok(await s.register());
		ok(await s.register(PR, state({ workflow: "pr", number: 73, nextAction: "Unique PR next action." })));
		ok(await s.call({ action: "checkpoint", key: EPIC, state: state({ nextAction: "Unique updated epic action." }) }));
		const messages = [
			{ role: "user", content: "What changed?" },
			{ role: "assistant", content: [{ type: "toolCall", id: "read-1", name: "read", arguments: { path: "notes" } }] },
			{ role: "toolResult", toolCallId: "read-1", toolName: "read", content: [{ type: "text", text: "Worker requires a decision." }] },
			{ role: "custom", customType: "other-extension", content: "Keep this reference." },
			{ role: "custom", customType: "daily-driver.pr-watch-context", content: "External supervisor context." },
			{ role: "custom", customType: CONTEXT, content: "OLD SNAPSHOT" },
			{ role: "custom", customType: WAKE, content: "OLD WAKE" },
		];
		const original = structuredClone(messages);
		const result = await s.context(messages);
		const text = watchContext(result);
		assert.equal(occurrences(text, "Unique updated epic action."), 1);
		assert.equal(occurrences(text, "Unique PR next action."), 1);
		assert.ok(!text.includes("Read the current worker result."));
		assert.ok(!JSON.stringify(result).includes("OLD WAKE"));
		assert.ok(!JSON.stringify(result).includes("OLD SNAPSHOT"));
		assert.deepEqual(result.messages.filter(message => message.customType !== CONTEXT), original.slice(0, 5));
		assert.deepEqual(messages, original, "provider hydration cannot edit source history");
		assert.notEqual(result.messages, messages);
	});

	// A real worker/service reconciliation covers the old timer without a duplicate model turn.
	watchCheck("599-second native reconciliation moves the fallback to 1199 seconds", async create => {
		for (const nativeEvent of ["subagent_end", "async_result"]) {
			const s = await create();
			ok(await s.register());
			await s.advance(599_000);
			await s.fire(nativeEvent, { result: "Material worker result; read it before proceeding." });
			ok(await s.call({ action: "checkpoint", key: EPIC, state: state({ observations: [{ name: "worker", value: "result-read" }] }) }));
			assert.equal((await s.record()).deadline, 1_199_000);
			await s.advance(1000);
			assert.deepEqual(s.sent, []);
			await s.advance(599_000);
			assert.equal(s.sent.length, 1);
		}
	});

	// Due work during a busy turn must not queue a second request if that turn checkpoints it.
	watchCheck("busy or host-pending expiry is consumed only by reconciliation", async create => {
		for (const busyKind of ["busy", "pending"]) {
			const s = await create();
			ok(await s.register());
			if (busyKind === "busy") s.setBusy(true); else s.setPending(true);
			await s.advance(600_000);
			assert.deepEqual(s.sent, []);
			assert.equal((await s.record()).pending, true);
			ok(await s.call({ action: "checkpoint", key: EPIC }));
			assert.equal((await s.record()).pending, false);
			s.setBusy(false); s.setPending(false);
			await s.fire("agent_end");
			await s.advance(1000);
			assert.deepEqual(s.sent, []);
			assert.equal((await s.record()).deadline, 1_200_000);
		}
	});

	// Answering an unrelated question is not a reconciliation and must not postpone liveness.
	watchCheck("unrelated user input and get do not change the due deadline", async create => {
		const s = await create();
		ok(await s.register());
		await s.advance(599_000);
		await s.fire("input", { source: "interactive", text: "What is the current branch?" });
		const messages = [{ role: "user", content: "What is the current branch?" }];
		assert.deepEqual((await s.context(messages)).messages[0], messages[0]);
		assert.equal((await s.record()).deadline, 600_000);
		await s.advance(1000);
		assert.equal(s.sent.length, 1);
	});

	// Missing checkpoints, model failure, and failed send must never cause one-second request loops.
	watchCheck("idle admission remains single-flight until the turn settles", async create => {
		const s = await create();
		ok(await s.register(EPIC, state(), 120));
		await s.advance(120_000);
		assert.equal(s.sent.length, 1);
		for (let index = 0; index < 5; index++) await s.advance(1000);
		assert.equal(s.sent.length, 1);
		await s.fire("agent_end", { error: "Scripted provider failed before a checkpoint." });
		await s.advance(1000);
		assert.equal(s.sent.length, 1);
		await s.advance(114_000);
		assert.equal(s.sent.length, 2, "normal fallback cadence remains live after a failed turn");
	});

	watchCheck("send failure is recorded and retried only at the next normal deadline", async create => {
		let attempts = 0;
		const s = await create({ sendMessage() { attempts++; throw new Error("scripted send failed"); } });
		ok(await s.register(EPIC, state(), 120));
		await s.advance(120_000);
		assert.equal(attempts, 1);
		assert.deepEqual(s.sent, []);
		assert.match((await s.record()).lastDeliveryError, /scripted send failed/u);
		for (let index = 0; index < 5; index++) { await s.fire("agent_end"); await s.advance(1000); }
		assert.equal(attempts, 1);
		await s.advance(115_000);
		assert.equal(attempts, 2);
	});

	// Stops must invalidate idle and due-but-busy timers and remain terminal on duplicate registration.
	watchCheck("stop is terminal, repeatable, and never implicitly checkpointed or registered", async create => {
		for (const dueBusy of [false, true]) {
			const s = await create();
			ok(await s.register());
			if (dueBusy) { s.setBusy(true); await s.advance(600_000); }
			ok(await s.call({ action: "stop", key: EPIC }));
			const stopped = await s.record();
			assert.equal(stopped.lifecycle, "stopped");
			const count = s.entries.length;
			ok(await s.call({ action: "stop", key: EPIC }));
			ok(await s.call({ action: "stop", key: "pr:github.com/example/project#999" }));
			assert.equal(s.entries.length, count, "repeated and missing stop are truthful no-ops");
			rejected(await s.call({ action: "checkpoint", key: EPIC }));
			rejected(await s.call({ action: "checkpoint", key: PR }));
			ok(await s.register());
			assert.deepEqual(await s.record(), stopped);
			s.setBusy(false);
			await s.fire("agent_end");
			await s.advance(1_800_000);
			assert.deepEqual(s.sent, []);
			assert.equal(s.timers.size, 0);
		}
	});

	// An admitted host wake cannot be deleted, but a terminal record must leave it no watch authority.
	watchCheck("already admitted stale wake has no active context or rearm", async create => {
		const s = await create();
		ok(await s.register());
		await s.advance(600_000);
		const admitted = { role: "custom", ...s.sent[0].msg };
		ok(await s.call({ action: "stop", key: EPIC }));
		const result = await s.context([admitted]);
		assert.ok(!result.messages.some(message => message.customType === WAKE));
		assert.match(JSON.stringify(result), /stopped|no.watch.work|no active watch/iu);
		rejected(await s.call({ action: "checkpoint", key: EPIC }));
		await s.fire("agent_end");
		await s.advance(1_800_000);
		assert.equal(s.sent.length, 1, "an already admitted wake is the only host message");
		assert.equal(s.timers.size, 0);
	});

	// Stopping one registration in a coalesced wake must not authorize that registration.
	watchCheck("mixed stale wake identifies stopped registrations without suppressing active work", async create => {
		const s = await create();
		ok(await s.register());
		ok(await s.register(PR, state({ workflow: "pr", number: 73 })));
		await s.advance(600_000);
		const admitted = { role: "custom", ...s.sent[0].msg };
		const stoppedId = (await s.record()).registrationId;
		ok(await s.call({ action: "stop", key: EPIC }));
		const content = watchContext(await s.context([admitted]));
		assert.match(content, /stopped or superseded/u);
		assert.ok(content.includes(stoppedId));
		assert.ok(content.includes(PR));
	});

	// Late hooks after shutdown must not resurrect a journaled timer.
	watchCheck("late context and tool calls cannot restart a shut down watch", async create => {
		const s = await create();
		ok(await s.register());
		await s.close();
		await s.context([]);
		rejected(await s.call({ action: "checkpoint", key: EPIC }));
		await s.advance(600_000);
		assert.equal(s.timers.size, 0);
		assert.equal(s.sent.length, 0);
	});

	// Reload restores the journal deadline, not a fresh interval or the first snapshot.
	watchCheck("same-session reload restores one latest deadline and overdue recovery coalesces", async create => {
		const original = await create();
		ok(await original.register());
		await original.advance(200_000);
		ok(await original.call({ action: "checkpoint", key: EPIC, state: state({ nextAction: "Latest restored action." }), delaySeconds: 120 }));
		const saved = structuredClone(original.entries);
		await original.close();
		assert.equal(original.timers.size, 0);
		const restored = await create({ entries: saved, now: 250_000 });
		assert.equal(restored.timers.size, 1);
		assert.equal((await restored.record()).deadline, 320_000);
		assert.equal((await restored.record()).state.nextAction, "Latest restored action.");
		await restored.advance(70_000);
		assert.equal(restored.sent.length, 1);
		const overdue = await create({ entries: saved, now: 2_000_000 });
		await overdue.advance(0);
		assert.equal(overdue.sent.length, 1, "missed intervals are not replayed");
		assert.equal((await overdue.record()).deadline, 2_120_000);
	});

	// Compaction/clear must not make a previously injected provider snapshot the source of truth.
	watchCheck("empty and compacted provider histories rehydrate current journal state", async create => {
		const s = await create();
		ok(await s.register());
		const previous = await s.context([]);
		ok(await s.call({ action: "checkpoint", key: EPIC, state: state({ nextAction: "Action after compaction." }) }));
		for (const messages of [[], previous.messages, [{ role: "user", content: "Compacted summary." }]]) {
			const content = watchContext(await s.context(messages));
			assert.equal(occurrences(content, "Action after compaction."), 1);
			assert.ok(!content.includes("Read the current worker result."));
		}
	});

	// Session and ancestry changes invalidate callbacks even when the host already selected one to run.
	for (const event of ["session_switch", "session_branch", "session_tree"]) {
		watchCheck(`${event} rejects old callbacks and foreign session ancestry`, async create => {
			const s = await create();
			ok(await s.register());
			const selected = [...s.timers.values()][0].fn;
			if (event === "session_switch") s.setSessionId("other-session");
			else s.setBranch([]);
			await s.fire(event);
			await selected();
			await setImmediate();
			await s.advance(1_800_000);
			assert.deepEqual(s.sent, []);
			assert.equal(s.timers.size, 0);
		});
	}

	// A fork cannot inherit monitoring authority from its parent's session ID.
	watchCheck("forked history never activates a foreign session registration", async create => {
		const parent = await create();
		ok(await parent.register());
		const child = await create({ sessionId: "forked-session", entries: parent.entries });
		await child.advance(1_800_000);
		assert.deepEqual(child.sent, []);
		assert.equal(child.timers.size, 0);
	});

	// Rewind cannot bypass a stop tombstone elsewhere in the same-session journal.
	watchCheck("rewinding before a stop cannot revive its registration", async create => {
		const s = await create();
		ok(await s.register());
		const activeAncestry = structuredClone(s.entries);
		ok(await s.call({ action: "stop", key: EPIC }));
		s.setBranch(activeAncestry);
		await s.fire("session_tree");
		await s.advance(1_800_000);
		assert.deepEqual(s.sent, []);
		assert.equal(s.timers.size, 0);
	});

	// Corrupt newest records must suspend, not silently roll back to an older active snapshot.
	watchCheck("malformed newest records and unknown schemas cannot revive older state", async create => {
		for (const change of [{ schema: 99 }, { state: null }, { revision: "bad" }, { deadline: "bad" }]) {
			const original = await create();
			ok(await original.register());
			const entries = structuredClone(original.entries);
			entries.push({ type: "custom", customType: ENTRY, data: { ...entries.at(-1).data, revision: 2, ...change } });
			const s = await create({ entries });
			await s.advance(1_800_000);
			assert.deepEqual(s.sent, []);
			assert.equal(s.timers.size, 0);
			const content = JSON.stringify(await s.context([]));
			assert.ok(!content.includes("Read the current worker result."));
			assert.ok(s.diagnostics.length > 0 || /invalid|suspend|schema|corrupt/iu.test(content), "suspension must report a diagnostic");
		}
	});

	// Damaged state must remain diagnosable and stoppable without restoring its payload.
	watchCheck("suspended get and stop preserve a terminal fence across valid and invalid journal entries", async create => {
		for (const damage of [{ schema: 99 }, { state: null }, { revision: "bad" }, { deadline: "bad" }]) {
			const original = await create();
			ok(await original.register());
			const valid = structuredClone(original.entries.at(-1));
			const damaged = { ...structuredClone(valid), data: { ...valid.data, revision: 2, ...damage } };
			const s = await create({ entries: [...original.entries, damaged] });
			const result = ok(await s.call({ action: "get", key: EPIC }));
			assert.equal(result.details.suspended, true);
			assert.equal(result.details.registrationId, valid.data.registrationId);
			assert.equal(result.details.sessionId, valid.data.sessionId);
			assert.ok(result.details.diagnostic);
			assert.equal(result.details.state, undefined);
			rejected(await s.call({ action: "checkpoint", key: EPIC, state: state() }));
			rejected(await s.register());
			ok(await s.call({ action: "stop", key: EPIC }));
			const tombstone = await s.record();
			assert.equal(tombstone.lifecycle, "stopped");
			assert.equal(tombstone.tombstone, true);
			assert.equal(tombstone.state, undefined);
			assert.deepEqual(s.entries[1], damaged, "stopping must not rewrite the damaged payload");
			assert.equal(ok(await s.call({ action: "stop", key: EPIC })).details.stopped, false);
			assert.equal(ok(await s.register()).details.registered, false);
			for (const later of [valid, damaged, { ...damaged, data: { ...damaged.data, lifecycle: "stopped" } }]) {
				s.entries.push(structuredClone(later));
				s.setBranch([later]);
				await s.fire("session_tree");
				assert.deepEqual(await s.record(), tombstone);
				await s.advance(1_800_000);
				assert.equal(s.timers.size, 0);
				assert.deepEqual(s.sent, []);
			}
		}
	});

	// Only explicit stand-down invocation stops embark; prose mentions and PR ownership are unaffected.
	watchCheck("explicit stand-down stops embark only and ignores prose mentions", async create => {
		for (const text of ["stand-down", "/stand-down", "/skill:stand-down", '[IMPORTANT: User invoked the "stand-down" skill; use its instructions.]']) {
			const s = await create();
			ok(await s.register());
			ok(await s.register(PR, state({ workflow: "pr", number: 73 })));
			await s.fire("input", { source: "interactive", text: "Explain what /stand-down does." });
			assert.equal((await s.record()).lifecycle, "active");
			await s.fire("input", { source: "interactive", text });
			assert.equal((await s.record()).lifecycle, "stopped");
			assert.equal((await s.record(PR)).lifecycle, "active");
			await s.advance(600_000);
			assert.equal(s.sent.length, 1);
			assert.equal(s.sent[0].msg.details.registrations.length, 1);
		}
	});

	// Watch activity must preserve meaningful worker/user content and must not generate terminal toasts.
	watchCheck("automated activity stays quiet without filtering user questions or worker failures", async create => {
		const s = await create();
		ok(await s.register());
		await s.advance(600_000);
		for (const name of ["agent_end", "subagent_end", "async_result"]) await s.fire(name, { result: "Worker failed: user decision required." });
		const messages = [{ role: "user", content: "Why did the worker fail?" }, { role: "custom", customType: "native-worker", content: "Worker failed: user decision required." }];
		assert.deepEqual((await s.context(messages)).messages.slice(0, 2), messages);
		assert.deepEqual(s.diagnostics, []);
	});

	// Accepted operational context must not be truncated, mutated by the caller, or echoed in acknowledgments.
	watchCheck("checkpoint retains omitted values and preserves accepted context without echoing it", async create => {
		const s = await create();
		const snapshot = state({ nextAction: `Read the complete evidence: ${"context-".repeat(4096)}`, lastReported: "Prior material change." });
		const expected = structuredClone(snapshot);
		const registered = ok(await s.register(EPIC, snapshot, 120));
		assert.ok(!JSON.stringify(registered).includes("context-context-"));
		snapshot.holds.length = 0;
		snapshot.workers[0].jobId = "caller-mutated";
		await s.advance(30_000);
		const checkpointed = ok(await s.call({ action: "checkpoint", key: EPIC }));
		assert.ok(!JSON.stringify(checkpointed).includes("context-context-"));
		assert.deepEqual((await s.record()).state, expected);
		assert.equal((await s.record()).delaySeconds, 120);
		assert.equal((await s.record()).deadline, 150_000);
		const before = await s.record();
		rejected(await s.call({ action: "checkpoint", key: EPIC, delaySeconds: 0 }));
		assert.deepEqual(await s.record(), before);
		ok(await s.call({ action: "checkpoint", key: EPIC, delaySeconds: 1800 }));
		assert.equal((await s.record()).deadline, 1_830_000);
		assert.deepEqual((await s.record()).state, expected);
		assert.ok(watchContext(await s.context([])).includes(expected.nextAction));
	});

	// A new authorized invocation has a distinct registration; a stale canonical key stays stopped.
	watchCheck("fresh run keys do not revive or replace stopped canonical registrations", async create => {
		const s = await create();
		ok(await s.register());
		const original = await s.record();
		ok(await s.call({ action: "stop", key: EPIC }));
		const run = `${EPIC}:run:12345678-1234-4234-8234-123456789abc`;
		ok(await s.register(run));
		assert.equal((await s.record()).lifecycle, "stopped");
		const fresh = await s.record(run);
		assert.equal(fresh.lifecycle, "active");
		assert.notEqual(fresh.registrationId, original.registrationId);
		await s.advance(600_000);
		assert.equal(s.sent.length, 1);
		assert.deepEqual(s.sent[0].msg.details.registrations.map(item => item.registrationId), [fresh.registrationId]);
	});

	// Lifecycle notifications rebuild from the journal rather than losing state after a clear or compaction.
	watchCheck("compaction and clear callbacks retain the latest active fallback", async create => {
		for (const event of ["session_compact", "session_clear"]) {
			const s = await create();
			ok(await s.register());
			await s.advance(200_000);
			ok(await s.call({ action: "checkpoint", key: EPIC, state: state({ nextAction: "Action after lifecycle change." }) }));
			await s.fire(event);
			assert.equal(s.timers.size, 1);
			assert.equal((await s.record()).deadline, 800_000);
			assert.ok(watchContext(await s.context([])).includes("Action after lifecycle change."));
			await s.advance(600_000);
			assert.equal(s.sent.length, 1);
		}
	});

	// Shutdown cancels selected callbacks without falsely persisting a workflow stop.
	watchCheck("shutdown invalidates captured callbacks and leaves resumable journal state", async create => {
		const s = await create();
		ok(await s.register());
		const selected = [...s.timers.values()][0].fn;
		const before = structuredClone(s.entries);
		await s.close();
		await selected();
		await s.advance(1_800_000);
		assert.equal(s.timers.size, 0);
		assert.deepEqual(s.sent, []);
		assert.deepEqual(s.entries, before);
	});

	registerExtensionIntegrationChecks(check, makeSession, fakeModelClassSettings, fakeModelTagsSetting);
}

function registerExtensionIntegrationChecks(check, makeSession, fakeModelClassSettings, fakeModelTagsSetting) {
	function integrated(options = {}) {
		const commands = new Map();
		const notifications = [];
		const route = { type: "custom", customType: "daily-driver-undertaking-route", data: {
			schema: 2, lifecycle: "active", issue: 1065, modelClass: "intermediate", status: "selected",
		} };
		let session;
		session = makeSession({ entries: [route], registerCommand: (name, command) => commands.set(name, command), settingsManagerFactory: fakeModelClassSettings }, {
			modelTagsSetting: fakeModelTagsSetting,
			notificationDependencies: { getTransport: () => ({ sendNotification(value) {
				if (options.onNotify) options.onNotify(session.rec.entries);
				notifications.push(value);
			} }) },
		});
		const ctx = {
			cwd: "/offline-integrated-watch", agent: { kind: "main", id: "integrated-owner" }, hasUI: true, mode: "tui",
			sessionManager: { getSessionId: () => "integrated-session", getSessionName: () => "#1065 Watch continuations", getBranch: () => session.rec.entries, getEntries: () => session.rec.entries },
			isIdle: () => true, hasPendingMessages: () => false, waitForIdle: async () => {},
			abort() { if (options.onAbort) options.onAbort(session.rec.entries); },
			ui: { notify() {}, setStatus() {} }, setTimeout: session.timers.setTimeout, clearTimer: session.timers.clearTimer,
		};
		const call = params => session.tools.get("daily_driver_watch").execute("watch", params, undefined, undefined, ctx);
		return { ...session, ctx, commands, notifications, call,
			register: (key, snapshot) => call({ action: "register", key, state: snapshot, delaySeconds: 600 }),
			async lifecycle(key) { return (await call({ action: "get", key })).details.record.lifecycle; },
			start: () => session.fire("session_start", {}, ctx), close: () => session.fire("session_shutdown", {}, ctx),
		};
	}

	// Test the shipped factory wiring, not a test-created imitation of its callbacks.
	check("watch continuations: undertaking cancellation stops only its watches before abort", async () => {
		let observedStop = false;
		const s = integrated({ onAbort(entries) {
			assert.equal(entries.filter(entry => entry.customType === ENTRY && entry.data.key === EPIC).at(-1).data.lifecycle, "stopped");
			observedStop = true;
		} });
		try {
			await s.start();
			ok(await s.register(EPIC, state()));
			ok(await s.register(PR, state({ workflow: "pr", number: 73, ownerIssue: 999 })));
			await s.commands.get("undertaking").handler("cancel 999", s.ctx);
			assert.equal(await s.lifecycle(EPIC), "active");
			await s.commands.get("undertaking").handler("cancel 1065", s.ctx);
			assert.equal(observedStop, true);
			assert.equal(await s.lifecycle(EPIC), "stopped");
			assert.equal(await s.lifecycle(PR), "active");
			assert.deepEqual(s.notifications, []);
		} finally { await s.close(); }
	});

	check("watch continuations: undertaking completion stops watches before its normal notification", async () => {
		const s = integrated({ onNotify(entries) {
			assert.equal(entries.filter(entry => entry.customType === ENTRY && entry.data.key === EPIC).at(-1).data.lifecycle, "stopped");
		} });
		try {
			await s.start();
			ok(await s.register(EPIC, state()));
			ok(await s.tools.get("daily_driver_finish_undertaking").execute("finish", { issue: 1065 }, undefined, undefined, s.ctx));
			assert.equal(await s.lifecycle(EPIC), "stopped");
			assert.equal(s.notifications.length, 1);
		} finally { await s.close(); }
	});

	// A failed stop callback must not claim cancellation or emit successful completion.
	for (const operation of ["cancel", "finish"]) {
		check(`watch continuations: ${operation} reports watch-stop persistence failure`, async () => {
			let aborts = 0;
			const reports = [];
			const s = integrated({ onAbort() { aborts++; } });
			s.ctx.ui.notify = (message, type) => reports.push({ message, type });
			try {
				await s.start();
				ok(await s.register(EPIC, state()));
				const append = s.pi.appendEntry;
				s.pi.appendEntry = (customType, data) => {
					if (customType === ENTRY && data.lifecycle === "stopped") throw new Error("scripted stop persistence failure");
					return append(customType, data);
				};
				if (operation === "cancel") {
					await s.commands.get("undertaking").handler("cancel 1065", s.ctx);
					assert.equal(aborts, 0, "failed watch stop must precede and prevent abort/wait");
					assert.ok(reports.some(report => /scripted stop persistence failure/u.test(report.message)));
				} else {
					const result = await s.tools.get("daily_driver_finish_undertaking").execute("finish", { issue: 1065 }, undefined, undefined, s.ctx);
					rejected(result);
					assert.match(result.content.map(part => part.text).join("\n"), /scripted stop persistence failure/u);
				}
				assert.equal(await s.lifecycle(EPIC), "active");
				assert.deepEqual(s.notifications, []);
			} finally { await s.close(); }
		});
	}

	// Requested reminders retain their existing visible, user-attributed follow-up transport.
	check("watch continuations: ordinary reminders remain visible and independently cancellable", async () => {
		const s = integrated();
		try {
			await s.start();
			ok(await s.register(EPIC, state()));
			const schedule = params => s.tools.get("daily_driver_schedule").execute("schedule", params, undefined, undefined, s.ctx);
			const cancelled = await schedule({ delaySeconds: 1, message: "Cancelled ordinary reminder." });
			const cancel = await s.tools.get("daily_driver_cancel_schedule").execute("cancel", { triggerId: cancelled.details.triggerId }, undefined, undefined, s.ctx);
			assert.equal(cancel.details.cancelled, true);
			await schedule({ delaySeconds: 1, message: "Requested ordinary reminder." });
			s.timers.advance(1000);
			assert.equal(s.rec.sent.length, 1);
			const { msg, opts } = s.rec.sent[0];
			assert.equal(msg.content, "Requested ordinary reminder.");
			assert.equal(msg.display, true);
			assert.equal(msg.attribution, "user");
			assert.deepEqual(opts, { deliverAs: "followUp", triggerTurn: true });
			const result = await s.fire("context", { messages: [{ role: "custom", ...msg }] }, s.ctx);
			assert.ok(result.messages.some(message => message.content === msg.content));
			for (const name of ["agent_end", "subagent_end", "async_result"]) await s.fire(name, {}, s.ctx);
			assert.deepEqual(s.notifications, []);
		} finally { await s.close(); }
	});
}
