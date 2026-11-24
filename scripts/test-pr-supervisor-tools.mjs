#!/usr/bin/env node
/** Exercise opt-in runtime PR registration and owner controls without GitHub. */
import assert from "node:assert/strict";
import { execFileSync, spawn } from "node:child_process";
import { mkdtempSync, mkdirSync, readFileSync, writeFileSync, chmodSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, delimiter } from "node:path";
import { installPrSupervisorTools } from "../extensions/pr-supervisor-tools.mjs";
import dailyDriverExtension from "../extensions/daily-driver.js";

const root = mkdtempSync(join(tmpdir(), "pr-supervisor-tools-"));
const priorPath = process.env.PATH;
const priorPythonLog = process.env.PR_SUPERVISOR_TEST_PYTHON_LOG;
const priorDatabase = process.env.DAILY_DRIVER_PR_SUPERVISOR;
try {
	const primary = join(root, "repository");
	const worktree = join(root, "task");
	const bin = join(root, "bin");
	mkdirSync(primary);
	mkdirSync(bin);
	execFileSync("git", ["init", "--initial-branch=master", primary], {stdio:"pipe"});
	execFileSync("git", ["-C", primary, "-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid", "commit", "--allow-empty", "-m", "Fixture base"], {stdio:"pipe"});
	const python = execFileSync("python3", ["-c", "import sys; print(sys.executable)"], {encoding:"utf8"}).trim();
	const pythonLog = join(root, "python-calls.jsonl");
	const pythonShim = join(bin, "python3");
	writeFileSync(pythonShim, `#!${python}
import json, os, sys
with open(os.environ["PR_SUPERVISOR_TEST_PYTHON_LOG"], "a") as log:
 log.write(json.dumps(sys.argv[1:]) + "\\n")
os.execv(${JSON.stringify(python)}, [${JSON.stringify(python)}, *sys.argv[1:]])
`);
	chmodSync(pythonShim, 0o755);
	execFileSync("git", ["-C", primary, "worktree", "add", "-b", "task", worktree], {stdio:"pipe"});
	const fake = join(bin, "gh");
	writeFileSync(fake, `#!/usr/bin/env python3
import json, sys
args = sys.argv[1:]
if args[:4] == ["api","--hostname","isolated.example","graphql"]:
 print(json.dumps([{"data":{"repository":{"pullRequest":{"reviewThreads":{"nodes":[],"pageInfo":{"hasNextPage":False,"endCursor":None}}}}}}]))
else:
 assert args[:5] == ["api","--hostname","isolated.example","--method","GET"], args
 endpoint = "user" if args[5] == "user" else args[-1]
 if endpoint == "user":
  print("fixture-author")
 elif endpoint == "/repos/fixture/project/pulls/7":
  print(json.dumps({"head":{"ref":"task","sha":"a"*40},"base":{"ref":"release","sha":"b"*40},
   "state":"open","merged":False,"mergeable":True,"mergeable_state":"clean"}))
 elif "/compare/" in endpoint:
  print(json.dumps({"merge_base_commit":{"sha":"b"*40},"behind_by":0}))
 elif "/check-runs?" in endpoint:
  print(json.dumps([{"total_count":1,"check_runs":[{"id":1,"status":"completed","conclusion":"success"}]}]))
 elif "/actions/runs?" in endpoint:
  print(json.dumps([{"total_count":0,"workflow_runs":[]}]))
 else:
  assert any(part in endpoint for part in ("/statuses?","/comments?","/reviews?")), endpoint
  print("[[]]")
`);
	chmodSync(fake, 0o755);
	process.env.PATH = bin + delimiter + priorPath;
	process.env.PR_SUPERVISOR_TEST_PYTHON_LOG = pythonLog;
	process.env.DAILY_DRIVER_PR_SUPERVISOR = join(root, "private", "supervisor.sqlite");
	const node = {optional() { return this; },int() { return this; },min() { return this; },
		max() { return this; },describe() { return this; }};
	const tools = new Map();
	const pi = {zod:{object:value=>({...value,optional() {return this;}}),string:()=>node,number:()=>node,array:()=>node,enum:()=>node},
		registerTool:tool=>tools.set(tool.name,tool)};
	let timersTaken = 0;
	const service = installPrSupervisorTools(pi, {takeTimers() { timersTaken++; return []; },restoreTimers() { return []; },
		takeWatches:()=>[],stopWatches() {},restoreWatches:()=>[]});
	await service.initialize();
	const ctx = {cwd:primary,hasPendingMessages:()=>false,
		sessionManager:{getSessionId:()=>"fixture-owner",getSessionFile:()=>join(root,"owner.jsonl")}};
	const url = "https://isolated.example/fixture/project/pull/7";
	const unboundCalls = readFileSync(pythonLog, "utf8");
	assert.deepEqual(await service.legacyWake("isolated.example/fixture/7", "check", "token", 1),
		{authorized:false,reason:"Legacy admission reader is not bound"});
	assert.equal(readFileSync(pythonLog, "utf8"), unboundCalls, "an unbound check fails closed without Python");
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
	const held = await control.execute("hold", {operation:"hold",identity:result.details.identity,reason:"explicit hold"}, undefined, undefined, ctx);
	assert.equal(held.details.control.operation, "hold");
	assert.equal(held.details.control.drain, "complete");
	assert.equal(typeof held.details.control.fence, "number");
	assert.equal(held.details.control.diagnostic, undefined);
	assert.equal(await service.allowsLegacy(result.details.identity), false);
	await control.execute("release", {operation:"release",identity:result.details.identity,reason:"explicit release"}, undefined, undefined, ctx);
	assert.equal(await service.allowsLegacy(result.details.identity), true);
	const identity = result.details.identity;
	const admitted = await service.legacyWake(identity, "admit", undefined, undefined,
		{message:"Fixture legacy wake",delaySeconds:30});
	assert.equal(admitted.authorized, true, "legacy admission remains a durable backend transition");
	const readerCalls = [];
	const deadline = Date.now() + 30_000;
	let running = false;
	let finished = false;
	service.bindLegacyAdmissionReader((candidateIdentity, token, epoch) => {
		readerCalls.push([candidateIdentity,token,epoch]);
		const identityMatches = candidateIdentity === identity && token === admitted.token && epoch === admitted.epoch;
		return {authorized:identityMatches && !finished && (running || Date.now() < deadline)};
	});
	const backendCallsBeforeCheck = readFileSync(pythonLog, "utf8");
	const checked = await service.legacyWake(identity, "check", admitted.token, admitted.epoch);
	assert.deepEqual(checked, {authorized:true}, "the bound admission reader supplies the guarded response");
	assert.deepEqual(readerCalls, [[identity,admitted.token,admitted.epoch]]);
	assert.equal(readFileSync(pythonLog, "utf8"), backendCallsBeforeCheck,
		"the read-only legacy boundary does not start Python");
	assert.equal((await service.legacyWake(identity, "check", "stale-token", admitted.epoch)).authorized, false,
		"a stale token is rejected by the bound reader");
	assert.equal(readFileSync(pythonLog, "utf8"), backendCallsBeforeCheck,
		"stale read-only checks also avoid Python");
	service.bindLegacyAdmissionReader(() => { throw new Error("fixture query failure"); });
	assert.deepEqual(await service.legacyWake(identity, "check", admitted.token, admitted.epoch),
		{authorized:false,reason:"Legacy admission reader failed; authorization denied"},
		"a failed admission read fails closed");
	assert.equal(readFileSync(pythonLog, "utf8"), backendCallsBeforeCheck,
		"a failed read also does not fall back to Python");
	service.bindLegacyAdmissionReader((candidateIdentity, token, epoch) => {
		readerCalls.push([candidateIdentity,token,epoch]);
		const identityMatches = candidateIdentity === identity && token === admitted.token && epoch === admitted.epoch;
		return {authorized:identityMatches && !finished && (running || Date.now() < deadline)};
	});
	const backendCallsBeforeStart = readFileSync(pythonLog, "utf8");
	const started = await service.legacyWake(identity, "start", admitted.token, admitted.epoch);
	assert.equal(started.authorized, true, "legacy start remains a durable backend transition");
	assert.notEqual(readFileSync(pythonLog, "utf8"), backendCallsBeforeStart,
		"legacy start still invokes the mutating backend");
	running = true;
	assert.deepEqual(await service.legacyWake(identity, "check", admitted.token, admitted.epoch), {authorized:true});
	const backendCallsBeforeFinish = readFileSync(pythonLog, "utf8");
	await service.legacyWake(identity, "finish", admitted.token, admitted.epoch);
	assert.notEqual(readFileSync(pythonLog, "utf8"), backendCallsBeforeFinish,
		"legacy finish still invokes the mutating backend");
	finished = true;
	assert.deepEqual(await service.legacyWake(identity, "check", admitted.token, admitted.epoch), {authorized:false},
		"the read-only response can deny finished work without another backend call");
	// Drive the real runtime reminder adapter through transfer, rollback and
	// retransfer. No custom callback stands in for cancellation/restoration.
	const supervisorScript = new URL("./pr-active-supervisor.py", import.meta.url).pathname;
	const host = spawn("python3", [supervisorScript,"--database",process.env.DAILY_DRIVER_PR_SUPERVISOR,"run"], {stdio:["ignore","pipe","pipe"]});
	try {
		await new Promise((resolveReady,reject) => {
			const deadline = setTimeout(()=>reject(new Error("fixture controller did not acquire its lease")),5000);
			host.stdout.once("data",()=>{clearTimeout(deadline);resolveReady();});
			host.once("error",reject);
			host.once("exit",code=>{clearTimeout(deadline);reject(new Error(`fixture controller exited ${code}`));});
		});
		const events = new Map(), runtimeTools = new Map(), timers = new Map(), sent = [], entries = [];
		let nextTimer = 0, aborted = 0;
		const runtime = {zod:pi.zod,on(name,handler) {events.set(name,[...(events.get(name)??[]),handler]);},
			registerTool:tool=>runtimeTools.set(tool.name,tool),registerCommand() {},
			getActiveTools:()=>["read","write"],getAllTools:()=>[...runtimeTools.values()],
			sendUserMessage:(content,options)=>sent.push({content,options}),sendMessage() {},
			appendEntry(customType,data) {entries.push({type:"custom",customType,data});}};
		dailyDriverExtension(runtime,{notificationDependencies:{lookup:()=>({override(){}})}});
		const timerContext = {...ctx,cwd:worktree,model:{id:"fixture-model"},
			models:{current:()=>({id:"fixture-model",provider:"fixture-provider"})},agent:{kind:"main",id:"Main"},
			sessionManager:{...ctx.sessionManager,getSessionName:()=>"#7 Fixture",getBranch:()=>entries,getEntries:()=>entries},
			setTimeout(fn,delay) {timers.set(++nextTimer,{fn,delay});return nextTimer;},
			clearTimer:id=>timers.delete(id),abort:async()=>{aborted++;}};
		const schedule = runtimeTools.get("daily_driver_schedule");
		const original = (await schedule.execute("timer",{delaySeconds:60,message:"Original owner continuation"},undefined,undefined,timerContext)).details.triggerId;
		const watchState = {workflow:"pr",host:"isolated.example",repository:"fixture/project",number:7,
			ownerIssue:7,branch:"task",worktree,nextAction:"Read current fixture evidence",authorityRefs:["issue://7"],
			holds:[],workers:[],services:[],observations:[]};
		const watch = runtimeTools.get("daily_driver_watch");
		const watched = await watch.execute("watch",{action:"register",key:"pr:isolated.example/fixture/project#7",
			delaySeconds:60,state:watchState},undefined,undefined,timerContext);
		assert.equal(watched.details.registered,true);
		let runtimeControl = runtimeTools.get("daily_driver_pr_supervisor_control");
		const invoke = (operation,timerIds=[]) => runtimeControl.execute(operation,
			{operation,identity:result.details.identity,timerIds,services:[]},undefined,undefined,timerContext);
		await invoke("transfer",[original]);
		assert.equal(timers.size,0,"transfer cancels the original timer");
		const rollback = await invoke("rollback");
		assert.equal(rollback.details.timerIds.length,1);
		assert.equal(rollback.details.watchKeys.length,1);
		assert.equal(timers.size,2,"rollback restores the generic timer and structured PR watch");
		const restoredWatch = entries.find(entry=>entry.data.key===rollback.details.watchKeys[0]);
		assert.deepEqual(restoredWatch.data.state,watchState,"structured context survives rollback unchanged");
		await invoke("rollback");
		assert.equal(timers.size,2,"repeated rollback cannot duplicate either wake owner");
		const [restoredId,restored] = [...timers.entries()][0];
		timers.delete(restoredId);
		await restored.fn();
		assert.equal(sent.length,1);
		assert.match(sent[0].content,/Original owner continuation/);
		const lostWake = sent[0].content;
		for (const handler of events.get("session_shutdown")??[]) await handler({},timerContext);
		assert.equal(timers.size,0,"shutdown clears in-memory retry handles, not durable pending work");
		sent.length = 0; // Drop the queued transport delivery before owner admission.
		// Advance only the isolated fixture's persisted lease clock. The Python
		// consumer tests assert the actual 120-second deadline and retry budget.
		const advanceClock = join(root,"advance-legacy-clock.py");
		writeFileSync(advanceClock, `import sqlite3,sys,time
db=sqlite3.connect(sys.argv[1])
changed=db.execute("UPDATE authorities SET legacy_deadline=? WHERE identity=? AND legacy_running=0 AND legacy_delivery IS NOT NULL",
 (time.time()-1,"isolated.example/fixture/project/7")).rowcount
assert changed==1
db.commit()
`);
		execFileSync("python3",[advanceClock,process.env.DAILY_DRIVER_PR_SUPERVISOR]);
		events.clear();
		runtimeTools.clear();
		dailyDriverExtension(runtime,{notificationDependencies:{lookup:()=>({override(){}})}});
		runtimeControl = runtimeTools.get("daily_driver_pr_supervisor_control");
		for (const handler of events.get("session_switch")??[]) await handler({},timerContext);
		const recoveredRetry = [...timers.entries()].find(([,entry])=>entry.delay<=1);
		assert.ok(recoveredRetry,"owner rebind recovers an expired queued admission from the database");
		timers.delete(recoveredRetry[0]);
		await recoveredRetry[1].fn();
		assert.equal(sent.length,1,"lost queued work is redelivered after owner rebind");
		assert.match(sent[0].content,/Original owner continuation/);
		assert.notEqual(sent[0].content,lostWake,"recovery must rotate the queued token");
		for (const handler of events.get("before_agent_start")??[]) await handler({prompt:lostWake},timerContext);
		assert.equal(aborted,1,"the abandoned queued token cannot start after recovery");
		// Transfer after timer admission but before native message delivery:
		// the authority epoch must reject the queued wake before owner work.
		await invoke("transfer");
		for (const handler of events.get("before_agent_start")??[]) {
			await handler({prompt:sent[0].content},timerContext);
		}
		assert.equal(aborted,2,"the recovered queued timer also cannot start work after retransfer");
		assert.equal(timers.size,0,"retransfer also fences the restored structured fallback");
	writeFileSync(fake, `#!/usr/bin/env python3
import json, os, sys
args = sys.argv[1:]
if args[:2] == ["pr","create"]:
 with open(os.environ["DD_WRITE_COUNT"], "a") as count:
  count.write("write\\n")
 print(os.environ["DD_WRITE_URL"])
 sys.exit(int(os.environ.get("DD_WRITE_EXIT", "0")))
else:
 assert args[:5] == ["api","--hostname","isolated.example","--method","GET"], args
 endpoint = "user" if args[5] == "user" else args[-1]
 if endpoint == "user":
  print("fixture-author")
 elif endpoint.startswith("/repos/fixture/project/pulls/"):
  if os.environ.get("DD_FAIL_REGISTRATION") == "1":
   sys.exit(7)
  print(json.dumps({"head":{"ref":"task","sha":"a"*40},"base":{"ref":"release","sha":"b"*40},
   "state":"open","merged":False,"mergeable":True,"mergeable_state":"clean"}))
 else:
  raise AssertionError(endpoint)
`);
	chmodSync(fake, 0o755);
	dailyDriverExtension(runtime,{
		githubWriteDependencies:{versionReader:()=>"omp/fixture"},
		notificationDependencies:{lookup:()=>({override(){}})},
	});
	const ghWriteCount = join(root,"gh-write-count");
	process.env.DD_WRITE_COUNT = ghWriteCount;
	const ghWriter = runtimeTools.get("daily_driver_gh_write");
	const runPrCreate = () => ghWriter.execute("fixture-write",
		{args:["pr","create","--title","fixture","--body","fixture body"]},undefined,undefined,timerContext);

	process.env.DD_WRITE_URL = "https://isolated.example/fixture/project/pull/8";
	delete process.env.DD_WRITE_EXIT;
	delete process.env.DD_FAIL_REGISTRATION;
	const registeredWrite = await runPrCreate();
	assert.equal(registeredWrite.isError, undefined, "a successful write with successful registration remains successful");
	assert.equal(registeredWrite.details.exitCode, 0);
	assert.match(registeredWrite.details.stdout,/pull\/8/u);
	assert.doesNotMatch(registeredWrite.content.map(item=>item.text).join("\n"),/registration failed/u);
	assert.equal(readFileSync(ghWriteCount,"utf8").trim().split("\n").length,1);

	process.env.DD_WRITE_URL = "https://isolated.example/fixture/project/pull/9";
	process.env.DD_FAIL_REGISTRATION = "1";
	const unregisteredWrite = await runPrCreate();
	assert.equal(unregisteredWrite.isError, undefined, "registration failure must not turn a successful PR write into a tool error");
	assert.equal(unregisteredWrite.details.exitCode, 0);
	assert.match(unregisteredWrite.details.stdout,/pull\/9/u);
	assert.match(unregisteredWrite.content.map(item=>item.text).join("\n"),/supervision registration failed/u);
	assert.equal(readFileSync(ghWriteCount,"utf8").trim().split("\n").length,2,"the failed registration does not retry the GitHub write");

	process.env.DD_WRITE_URL = "https://isolated.example/fixture/project/pull/10";
	process.env.DD_WRITE_EXIT = "9";
	const failedWrite = await runPrCreate();
	assert.equal(failedWrite.isError, true, "a failed GitHub write remains a tool error");
	assert.equal(failedWrite.details.exitCode, 9);
	assert.equal(readFileSync(ghWriteCount,"utf8").trim().split("\n").length,3,"a failed GitHub write is not retried automatically");
	delete process.env.DD_WRITE_EXIT;
	delete process.env.DD_FAIL_REGISTRATION;
	delete process.env.DD_WRITE_COUNT;
	delete process.env.DD_WRITE_URL;
	} finally {
		host.kill("SIGTERM");
		await new Promise(resolveExit=>host.once("exit",resolveExit));
	}
	const stopResult = await control.execute("stop", {operation:"stop",identity:result.details.identity,reason:"explicit stop"}, undefined, undefined, ctx);
	assert.equal(stopResult.details.control.operation, "stop");
	assert.equal(stopResult.details.control.drain, "complete");
	assert.match(stopResult.content[0].text, /drain=complete/);
	assert.equal(await service.allowsLegacy(result.details.identity), false);
	await register.execute("adopt", {url}, undefined, undefined, other);
	const stopped = await control.execute("status", {operation:"status",identity:result.details.identity}, undefined, undefined, ctx);
	assert.equal(stopped.details.stopped, "explicit stop");
	assert.deepEqual(stopped.details.control, stopResult.details.control);
	await assert.rejects(service.afterWrite(["pr","create"], "", ctx), /no registration identity/);
	console.log("PR runtime controls: legacy read reuse, registration/adoption, owner isolation, missing host, holds/stops and safe metadata passed");
} finally {
	process.env.PATH = priorPath;
	if (priorDatabase === undefined) delete process.env.DAILY_DRIVER_PR_SUPERVISOR;
	else process.env.DAILY_DRIVER_PR_SUPERVISOR = priorDatabase;
	if (priorPythonLog === undefined) delete process.env.PR_SUPERVISOR_TEST_PYTHON_LOG;
	else process.env.PR_SUPERVISOR_TEST_PYTHON_LOG = priorPythonLog;
	rmSync(root, {recursive:true,force:true});
}
