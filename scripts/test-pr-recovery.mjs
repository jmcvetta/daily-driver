#!/usr/bin/env node
/** Reject stolen recovery and keep deliberate same-owner route changes operable offline. */
import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { mkdtempSync, mkdirSync, writeFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import installInbox from "../extensions/pr-supervision-inbox.mjs";
import { installPrSupervisorTools } from "../extensions/pr-supervisor-tools.mjs";

// Node's built-in SQLite runs the same persisted queries in the ordinary offline
// gate. Bun runs this file unchanged against the production database API.
if (!process.versions.bun) {
	const { registerHooks } = await import("node:module");
	const source = `import { DatabaseSync } from "node:sqlite";
export class Database {
 constructor(path) { this.db = new DatabaseSync(path); }
 exec(sql) { return this.db.exec(sql); }
 query(sql) { return this.db.prepare(sql); }
 close() { this.db.close(); }
 transaction(fn) { return { immediate: () => {
  this.db.exec("BEGIN IMMEDIATE");
  try { const result = fn(); this.db.exec("COMMIT"); return result; }
  catch (error) { this.db.exec("ROLLBACK"); throw error; }
 } }; }
}`;
	registerHooks({ resolve(specifier, context, next) {
		return specifier === "bun:sqlite" ? { url: `data:text/javascript,${encodeURIComponent(source)}`, shortCircuit: true } : next(specifier, context);
	} });
}
const { Database } = await import("bun:sqlite");
const script = new URL("./pr-active-supervisor.py", import.meta.url).pathname;
const identity = "isolated.example/fixture/project/7";
const parentAgent = { kind: "main", id: "Main", name: "Main" };
const childAgent = { kind: "sub", id: "RecoveryChild", name: "RecoveryChild", parentId: "Main" };
const environmentKeys = ["DAILY_DRIVER_PR_INBOX_EXPECTED_OWNER", "DAILY_DRIVER_PR_INBOX_EXPECTED_AGENT",
	"DAILY_DRIVER_PR_INBOX_EXPECTED_ROUTE", "DAILY_DRIVER_PR_INBOX_EXPECTED_AUTH", "DAILY_DRIVER_PR_INBOX_PARENT",
	"DAILY_DRIVER_PR_INBOX_PARENT_ROUTE"];
const originalEnvironment = Object.fromEntries(environmentKeys.map(key => [key, process.env[key]]));

function fixture() {
	const root = mkdtempSync(join(tmpdir(), "pr-recovery-"));
	const primary = join(root, "repository");
	const worktree = join(root, "task");
	const databasePath = join(root, "private", "supervisor.sqlite");
	mkdirSync(primary);
	const git = (...args) => execFileSync("git", ["-C", primary, ...args], { encoding: "utf8", stdio: "pipe" });
	git("init", "--initial-branch=master");
	git("-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid", "commit", "--allow-empty", "-m", "Fixture");
	git("worktree", "add", "-b", "task", worktree);
	const backend = (operation, args = [], request) => JSON.parse(execFileSync("python3", [script, "--database", databasePath,
		operation, ...args, ...(request === undefined ? [] : ["--request", "-"])],
		{ encoding: "utf8", input: request === undefined ? undefined : JSON.stringify(request), stdio: ["pipe", "pipe", "pipe"] }));
	const file = session => join(root, `${session}.jsonl`);
	writeFileSync(file("owner"), JSON.stringify({ type: "session", id: "owner" }) + "\n", { mode: 0o600 });
	writeFileSync(file("parent"), JSON.stringify({ type: "session", id: "parent" }) + "\n", { mode: 0o600 });
	backend("register", [], { host: "isolated.example", repository: "fixture/project", number: 7, login: "fixture",
		context: { session: "owner", sessionFile: file("owner"), worktree, branch: "task", task: "issue://7" } });
	const database = new Database(databasePath);
	const sessions = [];
	function start(options = {}) {
		for (const key of environmentKeys) delete process.env[key];
		Object.assign(process.env, options.environment ?? {});
		const handlers = new Map();
		const tools = new Map();
		const timers = new Map();
		const messages = [];
		const notifications = [];
		const session = options.session ?? "owner";
		const model = { provider: options.provider ?? "old-provider", id: options.model ?? "old-model" };
		const schema = () => ({ optional() { return this; }, int() { return this; } });
		const pi = { zod: { object: schema, string: schema, number: schema, array: schema, enum: schema },
			on(name, handler) { const list = handlers.get(name) ?? []; list.push(handler); handlers.set(name, list); },
			registerTool(tool) { tools.set(tool.name, tool); }, getThinkingLevel: () => options.effort ?? "low",
			sendUserMessage(message) { messages.push(message); }, appendEntry() {} };
		const ctx = { cwd: options.cwd ?? worktree, agent: options.agent ?? parentAgent,
			sessionManager: { getSessionId: () => session, getSessionFile: () => options.file ?? file(session) },
			models: { current: () => model }, modelRegistry: { authStorage: { keys: { source: () => ({ kind: options.authentication ?? "oauth" }) } } },
			isIdle: () => true, hasPendingMessages: () => false, abort() { ctx.aborted = true; },
			setInterval(callback) { const id = timers.size + 1; timers.set(id, callback); return id; },
			clearTimer(id) { timers.delete(id); }, ui: { notify: (...args) => notifications.push(args) } };
		const controls = installPrSupervisorTools(pi, { databasePath });
		installInbox(pi, controls);
		const fire = async (name, event = {}) => {
			let result;
			for (const handler of handlers.get(name) ?? []) result = await handler(event, ctx) ?? result;
			return result;
		};
		const runtime = { controls, ctx, messages, notifications, timers, fire,
			startup: () => fire("session_start"), close: () => fire("session_shutdown"),
			tick() { for (const callback of timers.values()) callback(); },
			call: (operation, reason = "deliberate route change", key = identity) => tools.get("daily_driver_pr_supervisor_control")
				.execute("control", { identity: key, operation, reason }, undefined, undefined, ctx),
			tool: name => tools.get(name) };
		sessions.push(runtime);
		return runtime;
	}
	return { root, worktree, primary, backend, database, file, git, start,
		owner: (session = "owner") => database.query("SELECT * FROM owners WHERE session=?").get(session),
		async close() { for (const session of sessions) await session.close(); database.close(); rmSync(root, { recursive: true, force: true }); } };
}

try {
	// A route mismatch must not deliver, mutate the route, or allow normal controls.
	for (const changes of [{ model: "new-model" }, { provider: "new-provider" }, { effort: "high" }, { authentication: "api-key" }]) {
		const f = fixture();
		try {
			const first = f.start(); await first.startup(); await first.close();
			const old = f.owner();
			const resumed = f.start(changes); await resumed.startup();
			assert.equal(resumed.controls.recovery.state, "rebind-required");
			assert.equal((await resumed.call("status")).details.recovery, "rebind-required");
			assert.equal((await resumed.fire("tool_call", { toolName: "bash", input: {} })).block, true);
			assert.equal(await resumed.fire("tool_call", { toolName: "daily_driver_pr_supervisor_control", input: { operation: "status" } }), undefined);
			await assert.rejects(resumed.call("hold"), /explicit rebind/);
			await assert.rejects(resumed.call("rebind", " "), /nonempty/);
			await assert.rejects(resumed.tool("daily_driver_pr_supervisor_register").execute("register", { url: "https://isolated.example/fixture/project/pull/7" }, undefined, undefined, resumed.ctx), /explicit rebind/);
			f.database.query("UPDATE owners SET heartbeat=0 WHERE session='owner'").run();
			resumed.tick();
			assert.ok(f.owner().heartbeat > 0, "degraded recovery must retain its live process lease");
			for (const field of ["cwd", "provider", "model", "effort", "authentication"]) assert.equal(f.owner()[field], old[field]);
			assert.deepEqual(resumed.messages, []);
			const ack = await resumed.tool("daily_driver_pr_supervisor_acknowledge").execute("ack", {});
			assert.equal(ack.details.acknowledged, false);
			f.backend("hold", [identity, "--reason", "existing user hold"]);
			const rebound = await resumed.call("rebind");
			assert.equal(rebound.details.recovery, "ready");
			assert.equal(rebound.details.held, "existing user hold");
			for (const [field, value] of Object.entries(changes)) assert.equal(f.owner()[field], value);
			assert.equal(await resumed.fire("tool_call", { toolName: "bash", input: {} }), undefined);
		} finally { await f.close(); }
	}
	// Successful rebind resumes real queued delivery, not merely a status flag.
	{
		const f = fixture();
		try {
			const original = f.start(); await original.startup(); await original.close();
			f.database.query("INSERT INTO deliveries (identity,session,generation,fence,payload,status,next_attempt) VALUES (?,'owner',1,1,?,'pending',0)")
				.run(identity, JSON.stringify({ kind: "transport-fixture" }));
			const resumed = f.start({ model: "new-model" }); await resumed.startup(); resumed.tick();
			assert.deepEqual(resumed.messages, []);
			await resumed.call("rebind"); resumed.tick();
			assert.equal(resumed.messages.length, 1);
			assert.match(resumed.messages[0], /DAILY_DRIVER_PR_DELIVERY/);
		} finally { await f.close(); }
	}
	// Even a valid repository, branch name, and owner cannot substitute another worktree.
	{
		const f = fixture();
		try {
			const first = f.start(); await first.startup(); await first.close();
			const other = join(f.root, "other");
			f.git("worktree", "add", "-b", "other", other);
			const resumed = f.start({ cwd: other }); await resumed.startup();
			assert.equal(resumed.controls.recovery.state, "rebind-required");
			await assert.rejects(resumed.call("rebind"), /rebind failed/);
			assert.equal(f.owner().cwd, f.worktree);
			await resumed.close();
			const moved = join(f.root, "moved task");
			f.git("worktree", "move", f.worktree, moved);
			const relocated = f.start({ cwd: moved }); await relocated.startup();
			assert.equal((await relocated.call("rebind")).details.recovery, "ready");
			assert.equal(f.owner().cwd, moved);
			assert.equal(JSON.parse(f.backend("status", [identity]).context).worktree, moved);
		} finally { await f.close(); }
	}
	// Identity and stop failures must reject startup before process ownership changes.
	for (const invalid of ["owner", "agent", "header", "file", "stop"]) {
		const f = fixture();
		try {
			const first = f.start(); await first.startup(); await first.close();
			const before = f.owner();
			const options = invalid === "owner" ? { environment: { DAILY_DRIVER_PR_INBOX_EXPECTED_OWNER: "another-owner" } } :
				invalid === "agent" ? { agent: { ...parentAgent, id: "Other" } } :
				invalid === "file" ? { file: f.file("other") } : {};
			if (invalid === "header") writeFileSync(f.file("owner"), '{"type":"session","id":"other"}\n');
			if (invalid === "file") writeFileSync(f.file("other"), JSON.stringify({ type: "session", id: "owner" }) + "\n");
			if (invalid === "stop") f.backend("stop", [identity, "--reason", "explicit stop"]);
			const resumed = f.start(options);
			await assert.rejects(resumed.startup(), /owner differs|binding changed|session file changed|identity changed|Stopped PR/);
			assert.equal(f.owner().process, before.process);
			await assert.rejects(resumed.call("hold"), /explicit rebind/);
			await assert.rejects(resumed.call("rebind"), /live owner differs/);
			assert.deepEqual(resumed.messages, []);
		} finally { await f.close(); }
	}
	// A rebind request cannot substitute another process for the recorded live owner.
	{
		const f = fixture();
		try {
			const first = f.start(); await first.startup(); await first.close();
			const resumed = f.start({ model: "new-model" }); await resumed.startup();
			const request = resumed.controls.recovery.request(resumed.ctx);
			assert.throws(() => f.backend("rebind", [identity, "--reason", "invalid process"],
				{ ...request, process: "substituted-process" }),
				error => /recorded live owner process differs/u.test(String(error.stderr)));
			assert.equal(f.owner().model, "old-model");
			assert.equal((await resumed.call("rebind")).details.recovery, "ready");
			assert.equal(f.owner().model, "new-model");
		} finally { await f.close(); }
	}
	// A parent carrier must explicitly rebind its route and retain its exact child.
	for (const invalidChain of [false, true]) {
		const f = fixture();
		try {
			const parent = f.start({ session: "parent" }); await parent.startup(); await parent.close();
			writeFileSync(f.file("owner"), JSON.stringify({ type: "session", id: "owner", parentSession: f.file("parent") }) + "\n");
			const child = f.start({ agent: childAgent }); await child.startup(); await child.close();
			const beforeChild = f.owner();
			if (invalidChain) f.database.query("UPDATE owners SET agent=? WHERE session='owner'").run(JSON.stringify({ ...childAgent, parentId: "Other" }));
			const environment = { DAILY_DRIVER_PR_INBOX_PARENT: "parent", DAILY_DRIVER_PR_INBOX_EXPECTED_OWNER: "owner",
				DAILY_DRIVER_PR_INBOX_EXPECTED_AGENT: JSON.stringify(invalidChain ? { ...childAgent, parentId: "Other" } : childAgent),
				DAILY_DRIVER_PR_INBOX_PARENT_ROUTE: JSON.stringify({ agent: parentAgent, model: "old-model", provider: "old-provider", effort: "low", authentication: "oauth" }) };
			const resumed = f.start({ session: "parent", model: "new-model", environment });
			if (invalidChain) await assert.rejects(resumed.startup(), /parent\/child identity/);
			else {
				await resumed.startup();
				assert.equal((await resumed.call("status")).details.recovery, "rebind-required");
				assert.equal((await resumed.fire("tool_call", { toolName: "write", input: { path: "agent://RecoveryChild" } })).block, true);
				assert.equal((await resumed.call("rebind")).details.recovery, "ready");
				assert.equal(f.owner("parent").model, "new-model");
				assert.deepEqual(f.owner(), beforeChild);
				assert.equal((await resumed.fire("tool_call", { toolName: "write", input: { path: "agent://Other" } })).block, true);
				resumed.tick(); assert.deepEqual(resumed.messages, []);
			}
		} finally { await f.close(); }
	}
	console.log("PR recovery: degraded startup, deliberate route rebind, identity/worktree isolation, holds/stops and exact parent carriers passed");
} finally {
	for (const [key, value] of Object.entries(originalEnvironment)) {
		if (value === undefined) delete process.env[key]; else process.env[key] = value;
	}
}
