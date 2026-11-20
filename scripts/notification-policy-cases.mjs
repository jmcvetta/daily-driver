import assert from "node:assert/strict";
import { installNotificationPolicy } from "../extensions/notification-policy.mjs";

function fixture(options = {}) {
	const handlers = new Map();
	const tools = new Map();
	const sent = [];
	const entries = options.entries ?? [];
	let branch = entries;
	let sessionId = options.sessionId ?? "session-1";
	let title = options.title ?? "#755 Repair notifications";
	const settings = options.settings ?? {};
	const schema = () => ({ describe() { return this; }, min() { return this; }, max() { return this; } });
	const pi = {
		zod: { object: value => value, string: schema },
		on(name, handler) { const list = handlers.get(name) ?? []; list.push(handler); handlers.set(name, list); },
		registerTool(tool) { tools.set(tool.name, tool); },
		async appendEntry(customType, data) {
			if (options.appendEntry) await options.appendEntry(customType, data);
			branch.push({ type: "custom", customType, data: structuredClone(data) });
		},
	};
	const ctx = {
		cwd: "/offline-notification-fixture", agent: { kind: "main" }, hasUI: true, mode: "tui", ui: {},
		sessionManager: { getSessionId: () => sessionId, getSessionName: () => title, getBranch: () => branch },
	};
	const lookup = options.lookup ?? (() => ({ override() {} }));
	const getTransport = options.getTransport ?? (() => ({ sendNotification: notification => sent.push(notification) }));
	const service = installNotificationPolicy(pi, async current => current.settings ?? settings, { lookup, getTransport });
	return {
		ctx, entries, sent, service, tools,
		setBranch(value) { branch = value; },
		setSessionId(value) { sessionId = value; },
		setTitle(value) { title = value; },
		async fire(name, context = ctx) {
			for (const handler of handlers.get(name) ?? []) await handler({ type: name }, context);
		},
		call(params, context = ctx) {
			return tools.get("daily_driver_notify").execute("notify", params, undefined, undefined, context);
		},
	};
}

const attention = (key = "approval") => ({ reason: "attention_required", key, message: "Approval is required." });
const active = issue => ({ type: "custom", customType: "daily-driver-undertaking-route", data: { schema: 2, lifecycle: "active", issue } });

/** Register offline regressions for human-facing notification policy. */
export default function registerNotificationPolicyChecks(check, { makeSession }) {
	// Runtime and live settings must be suppressed without saving user configuration.
	check("notification policy overrides generic notifications in each live scope", async () => {
		const writes = [];
		const lookup = id => ({ override(scope, value) { scope.effective[id] = value; }, set() { writes.push(id); } });
		const f = fixture({ lookup });
		const scopes = [
			{ effective: {} },
			{ effective: { "completion.notify": "on", "error.notify": "on" } },
			{ effective: { "completion.notify": "on", "error.notify": "on" } },
		];
		for (const [index, event] of ["session_start", "session_switch", "session_branch", "session_tree", "before_agent_start"].entries()) {
			const scope = scopes[index % scopes.length];
			if (index !== 0) {
				scope.effective["completion.notify"] = "on";
				scope.effective["error.notify"] = "on";
			}
			await f.fire(event, { ...f.ctx, settings: scope, agent: index === 4 ? { kind: "sub" } : f.ctx.agent });
			assert.equal(scope.effective["completion.notify"], "off");
			assert.equal(scope.effective["error.notify"], "off");
		}
		assert.deepEqual(writes, []);
	});

	// Reminder wakes and ordinary runtime events must not turn into system toasts.
	check("reminder wakes and ordinary activity do not notify the terminal", async () => {
		const notifications = [];
		const s = makeSession({}, { notificationDependencies: { getTransport: () => ({ sendNotification: value => notifications.push(value) }) } });
		const schedule = s.tools.get("daily_driver_schedule");
		await schedule.execute("schedule", { delaySeconds: 1, message: "Check progress" }, undefined, undefined, s.pi);
		s.timers.advance(1000);
		assert.equal(s.rec.sent.length, 1);
		assert.equal(s.rec.sent[0].msg.content, "Check progress");
		assert.equal(s.rec.sent[0].opts.deliverAs, "followUp");
		for (const event of ["agent_end", "async_result", "subagent_end"]) await s.fire(event, { type: event }, {});
		assert.deepEqual(notifications, []);
	});

	// A persisted transition must not be replayed after repeat, resume, or a concurrent request.
	check("attention is deduplicated across concurrent calls and resume", async () => {
		let release;
		const gate = new Promise(resolve => { release = resolve; });
		let entered;
		const started = new Promise(resolve => { entered = resolve; });
		const f = fixture({ appendEntry: async () => { entered(); await gate; } });
		const first = f.call(attention());
		await started;
		const concurrent = f.call(attention());
		release();
		await Promise.all([first, concurrent]);
		assert.equal(f.sent.length, 1);
		assert.equal(f.sent[0].title, "#755 Repair notifications");
		assert.equal(f.sent[0].body, "Approval is required.");
		assert.equal(f.sent[0].type, "permission");
		assert.equal((await f.call(attention())).details.duplicate, true);
		const resumed = fixture({ entries: structuredClone(f.entries) });
		assert.equal((await resumed.call(attention())).details.duplicate, true);
		assert.equal(resumed.sent.length, 0);
		assert.equal(JSON.stringify(f.entries).includes("Approval is required."), false);
		assert.equal((await f.call(attention("different"))).details.accepted, true);
		assert.equal(f.sent.length, 2);
	});

	// A branch or session switch must not reuse another branch's recorded transition.
	check("notification deduplication follows active branch and session identity", async () => {
		const f = fixture({ title: "Untitled" });
		const firstBranch = [active(755)];
		const otherBranch = [active(756)];
		f.setBranch(firstBranch);
		await f.call(attention());
		f.setBranch(otherBranch);
		await f.call(attention());
		assert.equal(f.sent.length, 2);
		f.setBranch(firstBranch);
		assert.equal((await f.call(attention())).details.duplicate, true);
		f.setSessionId("session-2");
		assert.equal((await f.call(attention())).details.accepted, true);
		assert.equal(f.sent.length, 3);
	});

	// Named issues and epics are different work even without an undertaking route.
	check("title identity and completion use the appropriate work transition", async () => {
		const f = fixture({ title: "#755 First issue" });
		await f.call(attention());
		f.setTitle("#756 Second issue");
		assert.equal((await f.call(attention())).details.accepted, true);
		f.setTitle("⛵ EPIC #757 Larger work");
		assert.equal((await f.call(attention())).details.accepted, true);
		const result = await f.call({ reason: "work_complete", key: "complete", message: "Ready for review." });
		assert.equal(result.details.accepted, true);
		assert.equal(f.sent.at(-1).type, "completion");
		assert.equal(f.sent.length, 4);
	});

	// Completion keeps the undertaking identity after its route is released.
	check("internal completion identity survives release and supports RPC", async () => {
		const f = fixture({ title: "Untitled" });
		const request = { reason: "work_complete", key: "complete", message: "Ready for review.", workIdentity: "undertaking:755" };
		const rpc = { ...f.ctx, mode: "rpc" };
		assert.equal((await f.service.notify(rpc, request)).accepted, true);
		assert.equal((await f.service.notify(rpc, request)).duplicate, true);
		assert.equal((await f.service.notify(rpc, { ...request, workIdentity: "undertaking:756" })).accepted, true);
		assert.equal(f.sent.length, 2);
	});

	// A transport observer must see the durable entry before the toast is sent.
	check("notification records its transition before transport", async () => {
		let f;
		let recordedAtSend = false;
		f = fixture({ getTransport: () => ({ sendNotification() {
			recordedAtSend = f.entries.some(entry => entry.customType === "daily-driver-notification");
		} }) });
		assert.equal((await f.call(attention())).details.accepted, true);
		assert.equal(recordedAtSend, true);
	});

	// Sending before durable recording can duplicate a notification after a crash.
	check("persistence failure sends nothing; transport failure is not replayed", async () => {
		const failed = fixture({ appendEntry: () => { throw new Error("disk unavailable"); } });
		await assert.rejects(() => failed.call(attention()), /disk unavailable/u);
		assert.equal(failed.sent.length, 0);
		let attempts = 0;
		const transport = fixture({ getTransport: () => ({ sendNotification() { attempts++; throw new Error("terminal unavailable"); } }) });
		const result = await transport.call(attention());
		assert.equal(result.details.suppressed, "delivery-failed");
		assert.equal((await transport.call(attention())).details.duplicate, true);
		assert.equal(attempts, 1);
	});

	// Children and headless execution cannot interrupt the user, even through internal completion calls.
	check("children and headless contexts never send notifications", async () => {
		const f = fixture();
		for (const ctx of [{ ...f.ctx, agent: { kind: "sub" } }, { ...f.ctx, hasUI: false }, { ...f.ctx, mode: "print" }]) {
			assert.equal((await f.service.notify(ctx, { reason: "work_complete", key: "complete", message: "Done.", workIdentity: "undertaking:755" })).accepted, false);
		}
		assert.deepEqual(f.sent, []);
		assert.deepEqual(f.entries, []);
	});

	// Tool callers cannot smuggle invalid reasons or control characters past schema handling.
	check("notification tool rejects invalid text and reasons at runtime", async () => {
		const f = fixture();
		for (const params of [
			{ ...attention(), reason: "progress" }, { ...attention(), key: "  " },
			{ ...attention(), key: "x".repeat(161) }, { ...attention(), key: "bad\nkey" },
			{ ...attention(), message: "\t" }, { ...attention(), message: "x".repeat(401) },
			{ ...attention(), message: "bad\u007fmessage" },
		]) assert.equal((await f.call(params)).isError, true);
		assert.deepEqual(f.sent, []);
		assert.deepEqual(f.entries, []);
	});
}
