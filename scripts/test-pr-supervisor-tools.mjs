#!/usr/bin/env node
/** Exercise opt-in runtime PR registration and owner controls without GitHub. */
import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { mkdtempSync, mkdirSync, writeFileSync, chmodSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, delimiter } from "node:path";
import { installPrSupervisorTools } from "../extensions/pr-supervisor-tools.mjs";

const root = mkdtempSync(join(tmpdir(), "pr-supervisor-tools-"));
const priorPath = process.env.PATH;
const priorDatabase = process.env.DAILY_DRIVER_PR_SUPERVISOR;
try {
	const primary = join(root, "repository");
	const worktree = join(root, "task");
	const bin = join(root, "bin");
	mkdirSync(primary);
	mkdirSync(bin);
	execFileSync("git", ["init", "--initial-branch=master", primary], {stdio:"pipe"});
	execFileSync("git", ["-C", primary, "-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid", "commit", "--allow-empty", "-m", "Fixture base"], {stdio:"pipe"});
	execFileSync("git", ["-C", primary, "worktree", "add", "-b", "task", worktree], {stdio:"pipe"});
	const fake = join(bin, "gh");
	writeFileSync(fake, `#!/usr/bin/env python3
import json, sys
args = sys.argv[1:]
assert args[:5] == ["api","--hostname","isolated.example","--method","GET"], args
if args[5] == "user":
 print("fixture-author")
elif args[5] == "/repos/fixture/project/pulls/7":
 print(json.dumps({"head":{"ref":"task"}}))
else:
 raise SystemExit("unexpected fixture endpoint")
`);
	chmodSync(fake, 0o755);
	process.env.PATH = bin + delimiter + priorPath;
	process.env.DAILY_DRIVER_PR_SUPERVISOR = join(root, "private", "supervisor.sqlite");
	const node = {optional() { return this; }, int() { return this; }};
	const tools = new Map();
	const pi = {zod:{object:value=>value,string:()=>node,number:()=>node,array:()=>node,enum:()=>node},
		registerTool:tool=>tools.set(tool.name,tool)};
	let timersTaken = 0;
	const service = installPrSupervisorTools(pi, {takeTimers() { timersTaken++; return []; },restoreTimers() { return []; }});
	await service.initialize();
	const ctx = {cwd:primary,hasPendingMessages:()=>false,
		sessionManager:{getSessionId:()=>"fixture-owner",getSessionFile:()=>join(root,"owner.jsonl")}};
	const url = "https://isolated.example/fixture/project/pull/7";
	const register = tools.get("daily_driver_pr_supervisor_register");
	const result = await register.execute("register", {url}, undefined, undefined, ctx);
	assert.equal(result.details.authority.state, "shadow");
	assert.equal(result.details.identity, "isolated.example/fixture/project/7");
	assert.equal(result.details.delivery, null);
	await service.afterWrite(["pr","create"], url + "\n", ctx);
	await service.afterWrite(["pr","edit","7"], url + "\n", ctx);
	const control = tools.get("daily_driver_pr_supervisor_control");
	const status = await control.execute("status", {operation:"status",identity:result.details.identity}, undefined, undefined, ctx);
	assert.equal(status.details.authority.state, "shadow");
	assert.equal(status.details.authority.legacy, undefined);
	await assert.rejects(control.execute("transfer", {operation:"transfer",identity:result.details.identity}, undefined, undefined, ctx), /No active lifecycle controller/);
	assert.equal(timersTaken, 0, "host absence must not cancel existing owner continuation");
	const other = {...ctx,sessionManager:{...ctx.sessionManager,getSessionId:()=>"another-owner"}};
	await assert.rejects(control.execute("hold", {operation:"hold",identity:result.details.identity,reason:"wrong owner"}, undefined, undefined, other), /recorded live owner/);
	await control.execute("hold", {operation:"hold",identity:result.details.identity,reason:"explicit hold"}, undefined, undefined, ctx);
	assert.equal(await service.allowsLegacy(result.details.identity), false);
	await control.execute("release", {operation:"release",identity:result.details.identity,reason:"explicit release"}, undefined, undefined, ctx);
	assert.equal(await service.allowsLegacy(result.details.identity), true);
	await control.execute("stop", {operation:"stop",identity:result.details.identity,reason:"explicit stop"}, undefined, undefined, ctx);
	assert.equal(await service.allowsLegacy(result.details.identity), false);
	await register.execute("adopt", {url}, undefined, undefined, other);
	const stopped = await control.execute("status", {operation:"status",identity:result.details.identity}, undefined, undefined, ctx);
	assert.equal(stopped.details.stopped, "explicit stop");
	await assert.rejects(service.afterWrite(["pr","create"], "", ctx), /no registration identity/);
	console.log("PR runtime controls: registration/adoption, owner isolation, missing host, holds/stops and safe metadata passed");
} finally {
	process.env.PATH = priorPath;
	if (priorDatabase === undefined) delete process.env.DAILY_DRIVER_PR_SUPERVISOR;
	else process.env.DAILY_DRIVER_PR_SUPERVISOR = priorDatabase;
	rmSync(root, {recursive:true,force:true});
}
