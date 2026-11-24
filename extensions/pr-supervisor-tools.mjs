import { spawn, execFileSync } from "node:child_process";
import { dirname, resolve, isAbsolute } from "node:path";
import { fileURLToPath } from "node:url";

const script = resolve(dirname(fileURLToPath(import.meta.url)), "../scripts/pr-active-supervisor.py");

/** Install opt-in PR authority controls and return the attributed-write hook. */
export function installPrSupervisorTools(pi, { takeTimers, restoreTimers, takeWatches, stopWatches, restoreWatches }) {
	let legacyAdmissionReader;
	const databasePath = process.env.DAILY_DRIVER_PR_SUPERVISOR;
	if (!databasePath) return undefined;
	if (!isAbsolute(databasePath)) throw new Error("PR supervisor database must be an absolute owner-only path");
	const z = pi.zod;

	function run(command, args, input, signal) {
		return new Promise((resolveResult, reject) => {
			const child = spawn(command, args, {stdio: ["pipe", "pipe", "pipe"], signal});
			let stdout = "";
			child.stdout.setEncoding("utf8").on("data", chunk => { stdout += chunk; });
			// Error text can contain credential-command output. Do not forward it.
			child.stderr.resume();
			child.on("error", reject);
			child.on("close", code => code === 0 ? resolveResult(stdout) : reject(new Error(`Supervisor operation failed (exit ${code}); no success is claimed`)));
			child.stdin.end(input ?? "");
		});
	}
	async function backend(operation, args = [], request, signal) {
		try {
			const result = await run("python3", [script, "--database", databasePath, operation, ...args,
				...(request === undefined ? [] : ["--request", "-"])], request === undefined ? undefined : JSON.stringify(request), signal);
			return JSON.parse(result);
		} catch (error) {
			throw new Error(`Supervisor ${operation} failed; no success is claimed`, {cause:error});
		}
	}
	const initialize = () => backend("initialize");

	function publicResult(result) {
		if (!result.authority) return result;
		return {identity:result.identity, stopped:result.stopped, held:result.held,
			generation:result.generation, degraded:result.degraded, control:result.control,
			authority:{state:result.authority.state,epoch:result.authority.epoch,acknowledged:result.authority.acknowledged,error:result.authority.error},
			delivery:result.delivery ? {generation:result.delivery.generation,status:result.delivery.status,
				attempts:result.delivery.attempts,last_error:result.delivery.last_error} : null};
	}

	async function register(url, ctx, worktree, signal) {
		const match = /^https:\/\/([^/]+)\/([^/]+\/[^/]+)\/pull\/(\d+)\/?$/.exec(url.trim());
		if (!match) throw new Error("Registration requires an exact GitHub PR URL");
		const [, host, repository, numberText] = match;
		const number = Number(numberText);
		const pr = JSON.parse(await run("gh", ["api", "--hostname", host, "--method", "GET", `/repos/${repository}/pulls/${number}`], undefined, signal));
		const login = (await run("gh", ["api", "--hostname", host, "--method", "GET", "user", "--jq", ".login"], undefined, signal)).trim();
		const base = worktree ?? ctx.cwd;
		const records = execFileSync("git", ["-C", base, "worktree", "list", "--porcelain"], {encoding: "utf8"}).split("\n\n");
		const selected = records.find(record => record.split("\n").includes(`branch refs/heads/${pr.head.ref}`));
		if (!selected) throw new Error("No registered task worktree matches the PR head; provide its repository worktree explicitly");
		const path = selected.split("\n").find(line => line.startsWith("worktree ")).slice(9);
		const context = {
			session: ctx.sessionManager.getSessionId(), sessionFile: ctx.sessionManager.getSessionFile(),
			worktree: path, branch: pr.head.ref, task: url,
		};
		if (!context.sessionFile) throw new Error("PR supervision needs a persisted owner session");
		return backend("register", [], {host, repository, number, login, context}, signal);
	}

	pi.registerTool({
		name: "daily_driver_pr_supervisor_register",
		label: "Register PR supervision",
		description: "Register a created or adopted PR in read-only shadow mode with actual owner/worktree context. This does not transfer ownership or install a host.",
		parameters: z.object({url: z.string(), worktree: z.string().optional()}),
		execute: async (_id, params, signal, _onUpdate, ctx) => {
			const result = await register(params.url, ctx, params.worktree, signal);
			return {content: [{type: "text", text: `PR registered; authority=${result.authority.state}`}], details: publicResult(result)};
		},
	});
	pi.registerTool({
		name: "daily_driver_pr_supervisor_control",
		label: "Control PR supervision",
		description: "Read, hold, release, stop, transfer or roll back one registered PR. Stop/hold records a durable fence before waiting for prior work. Only control.drain=complete permits a stop-time push; pending/failed retains the fence and diagnostic. Already-issued remote requests cannot be undone. Transfer cancels supplied live owner timer IDs and verified owned Omp services; it never installs a host. A readiness-only hold is not a supervision hold.",
		parameters: z.object({identity: z.string(), operation: z.enum(["status", "stop", "hold", "release", "transfer", "rollback"]),
			reason: z.string().optional(), services: z.array(z.string()).optional(), timerIds: z.array(z.string()).optional()}),
		execute: async (_id, params, signal, _onUpdate, ctx) => {
			let result;
			const state = await backend("status", [params.identity], undefined, signal);
			if (params.operation !== "status" && JSON.parse(state.context).session !== ctx.sessionManager.getSessionId()) {
				throw new Error("Only the recorded live owner can control its PR");
			}
			if (params.operation === "transfer") {
				if (ctx.hasPendingMessages()) throw new Error("Drain queued owner work before transferring supervision");
				if (!state.host_running) throw new Error("No active lifecycle controller holds this ledger; prior maintenance stays authoritative");
				const timers = takeTimers(params.timerIds ?? [], ctx, {cancel:false,identity:params.identity});
				const request = {services:params.services ?? [],cancelled_timers:timers,watches:takeWatches(ctx,params.identity)};
				await backend("prepare-transfer", [params.identity], request, signal);
				stopWatches(ctx,params.identity);
				if (ctx.hasPendingMessages()) throw new Error("Legacy watch work queued during transfer; drain it before activation");
				takeTimers(params.timerIds ?? [], ctx);
				result = await backend("transfer", [params.identity], request, signal);
			} else if (params.operation === "rollback") {
				result = await backend("rollback", [params.identity], undefined, signal);
				if (result.restored && (result.timers.length || result.watches.length)) {
					if (result.timers.length) result.timerIds = restoreTimers(result.timers.map(timer => ({...timer,identity:params.identity})), ctx);
					if (result.watches.length) result.watchKeys = restoreWatches(ctx,result.watches);
					await backend("complete-rollback", [params.identity], {timer_ids:result.timerIds,watch_keys:result.watchKeys}, signal);
				}
				delete result.timers;
				delete result.watches;
			} else {
				const args = [params.identity];
				if (params.operation !== "status") {
					if (!params.reason?.trim()) throw new Error("A nonempty control reason is required");
					args.push("--reason", params.reason);
				}
				result = await backend(params.operation, args, undefined, signal);
				if (params.operation === "stop") stopWatches(ctx,params.identity);
			}
			const outcome = result.control ? `fence=${result.control.fence}; drain=${result.control.drain}` : "recorded";
			return {content: [{type: "text", text: `Supervisor ${params.operation}: ${outcome}; no readiness or merge decision was made`}], details: publicResult(result)};
		},
	});

	return {
		databasePath, initialize,
		bindLegacyAdmissionReader(reader) {
			legacyAdmissionReader = typeof reader === "function" ? reader : undefined;
		},
		async legacyWake(identity, operation, token, epoch, context) {
			if (operation === "check") {
				if (!legacyAdmissionReader) return {authorized:false,reason:"Legacy admission reader is not bound"};
				try {
					return await legacyAdmissionReader(identity, token, epoch);
				} catch {
					return {authorized:false,reason:"Legacy admission reader failed; authorization denied"};
				}
			}
			return backend("legacy-wake", [identity], {operation,token,epoch,context});
		},
		recoverLegacy(session) {
			return backend("recover-legacy", [session]);
		},
		async allowsLegacy(identity) {
			const state = await backend("status", [identity]);
			return !state.stopped && !state.held && state.authority.state === "shadow";
		},
		async afterWrite(args, stdout, ctx, signal) {
			if (args[0] !== "pr" || !["create", "edit"].includes(args[1])) return;
			const url = stdout.match(/https:\/\/[^\s]+\/pull\/\d+/)?.[0];
			if (!url) throw new Error("PR write succeeded but returned no registration identity; register the PR explicitly");
			await register(url, ctx, undefined, signal);
		},
	};
}
