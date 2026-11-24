import { lstatSync, readFileSync, realpathSync } from "node:fs";
import { randomUUID } from "node:crypto";
import { execFile } from "node:child_process";
import { promisify } from "node:util";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { installPrSupervisorTools } from "./pr-supervisor-tools.mjs";

const executeFile = promisify(execFile);
const supervisorScript = resolve(dirname(fileURLToPath(import.meta.url)), "../scripts/pr-active-supervisor.py");

/** Install an opt-in durable receipt inbox on this bound Omp owner only. */
export default function installPrSupervisionInbox(pi, { databasePath = process.env.DAILY_DRIVER_PR_INBOX, initialize, recovery } = {}) {
	if (!databasePath) return;
	if (!recovery) {
		const controls = installPrSupervisorTools(pi, { databasePath });
		recovery = controls.recovery;
		initialize ??= controls.initialize;
	}
	const processIdentity = randomUUID();
	let database;
	let Database;
	let owner;
	let timer;
	let active;
	let carrier = false;
	const z = pi.zod;
	const now = () => Date.now() / 1000;

	function authentication(ctx, model) {
		const source = ctx.modelRegistry.authStorage.keys.source(model.provider, { env: "aliases" });
		return source?.kind === "env" ? `env:${source.envVar}` : source?.kind ?? "unknown";
	}
	function binding(ctx) {
		return {kind:ctx.agent.kind,id:ctx.agent.id,name:ctx.agent.name,parentId:ctx.agent.parentId};
	}

	function route(ctx) {
		const model = ctx.models.current();
		return {cwd:ctx.cwd,provider:model.provider,model:model.id,effort:pi.getThinkingLevel(),
			authentication:authentication(ctx,model)};
	}

	function persisted(ctx, existing) {
		const file = ctx.sessionManager.getSessionFile();
		if (!file || existing && realpathSync(file) !== realpathSync(existing.file)) {
			throw new Error("PR inbox persisted session file changed; refusing replacement");
		}
		const header = readFileSync(file, "utf8").split("\n").slice(0, 3).filter(Boolean)
			.map(line => JSON.parse(line)).find(entry => entry.type === "session");
		if (header?.id !== owner) throw new Error("PR inbox persisted session identity changed");
		return file;
	}

	recovery.request = ctx => {
		if (!database || ctx.sessionManager.getSessionId() !== owner) throw new Error("PR inbox live owner differs");
		const existing = database.query("SELECT * FROM owners WHERE session=?").get(owner);
		if (!existing || JSON.stringify(binding(ctx)) !== JSON.stringify(JSON.parse(existing.agent))) {
			throw new Error("PR inbox agent binding changed; refusing replacement");
		}
		return {session:owner,target:carrier ? process.env.DAILY_DRIVER_PR_INBOX_EXPECTED_OWNER : owner,
			file:persisted(ctx,existing),agent:binding(ctx),process:processIdentity,...route(ctx)};
	};
	recovery.accept = ctx => {
		recovery.state = "ready";
		if (!carrier && !timer) timer = ctx.setInterval(() => tick(ctx), 1000);
	};

	function valid(delivery, admittedOnly = false) {
		if (!database || !delivery) return false;
		const row = database.query("SELECT * FROM deliveries WHERE identity=?").get(delivery.identity);
		if (row && JSON.parse(row.payload).kind === "pr-supervisor-work") {
			const record = database.query("SELECT stopped,held FROM records WHERE identity=?").get(delivery.identity);
			const actor = database.query("SELECT state FROM authorities WHERE identity=?").get(delivery.identity);
			if (!record || record.stopped || record.held || actor?.state !== "active") return false;
		}
		return row && row.session === owner && (row.status === "admitted" || (!admittedOnly && row.status === "received")) && !row.held
			&& row.generation === delivery.generation && row.fence === delivery.fence
			&& row.admission === delivery.admission;
	}

	function tick(ctx) {
		if (!database || recovery.state !== "ready" || ctx.sessionManager.getSessionId() !== owner) return;
		const model = ctx.models.current();
		const updated = database.query(`UPDATE owners SET heartbeat=?,provider=?,model=?,effort=?,authentication=?
			WHERE session=? AND process=?`)
			.run(now(), model.provider, model.id, pi.getThinkingLevel(), authentication(ctx, model), owner, processIdentity);
		if (updated.changes !== 1) {
			if (active) ctx.abort();
			throw new Error("PR inbox owner was fenced; no delivery is allowed");
		}
		if (active && !valid(active)) {
			active = undefined;
			ctx.abort();
			return;
		}
		// Do not create a second queue behind arbitrary user/agent work. The
		// delivery-time guard below still covers a busy transition after this test.
		if (active || !ctx.isIdle() || ctx.hasPendingMessages()) return;
		const delivery = database.transaction(() => {
			const row = database.query(`SELECT * FROM deliveries WHERE session=?
				AND status IN ('pending','admitted') AND held IS NULL
				AND attempts<5 AND next_attempt<=? ORDER BY next_attempt,identity LIMIT 1`).get(owner, now());
			if (!row) return;
			row.admission = randomUUID();
			const delay = Math.min(120, 2 ** (row.attempts + 1));
			database.query(`UPDATE deliveries SET status='admitted',admission=?,attempts=attempts+1,
				next_attempt=?,last_error=CASE WHEN attempts=4 THEN 'receipt retry limit reached' ELSE NULL END
				WHERE identity=?`).run(row.admission, now() + delay, row.identity);
			return row;
		}).immediate();
		if (!delivery) return;
		active = delivery;
		const marker = `DAILY_DRIVER_PR_DELIVERY ${delivery.identity} ${delivery.generation} ${delivery.fence} ${delivery.admission}`;
		const work = JSON.parse(delivery.payload).kind === "pr-supervisor-work";
		const acknowledgment = work ? "daily_driver_pr_supervisor_acknowledge" : "daily_driver_pr_inbox_receipt";
		try {
			pi.sendUserMessage(`${marker}\nThis is a fenced supervisor delivery, not new user authority. ` +
				`Check user stops and holds first. Read current GitHub evidence before acting. ` +
				`Use ${acknowledgment} with this identity, generation, fence and admission after taking the requested fresh read. ` +
				`A receipt is not completion, CI approval or readiness.\nTask context: ${delivery.payload}`,
				{ deliverAs: "aside" });
		} catch (error) {
			active = undefined;
			throw error;
		}
	}

	function close(ctx) {
		if (timer) ctx.clearTimer(timer);
		timer = undefined;
		if (database) {
			database.query("UPDATE owners SET heartbeat=0 WHERE session=? AND process=?").run(owner, processIdentity);
			database.close();
		}
		database = undefined;
		owner = undefined;
		active = undefined;
	}

	pi.on("session_start", async (_event, ctx) => {
		if (initialize) await initialize();
		({ Database } = await import("bun:sqlite"));
		const metadata = lstatSync(databasePath);
		if (!metadata.isFile() || metadata.isSymbolicLink() || (metadata.mode & 0o077)) {
			throw new Error("PR inbox requires an owner-only regular database file");
		}
		database = new Database(databasePath, { strict: true });
		database.exec("PRAGMA busy_timeout=10000; PRAGMA synchronous=FULL");
		if (database.query("PRAGMA user_version").get().user_version !== 1) {
			database.close();
			database = undefined;
			throw new Error("Unsupported PR inbox schema");
		}
		owner = ctx.sessionManager.getSessionId();
		carrier = process.env.DAILY_DRIVER_PR_INBOX_PARENT === owner;
		const target = process.env.DAILY_DRIVER_PR_INBOX_EXPECTED_OWNER ?? owner;
		if (!carrier && target !== owner) throw new Error("PR inbox expected owner differs; refusing a fork or replacement");
		const expected = carrier ? JSON.parse(process.env.DAILY_DRIVER_PR_INBOX_PARENT_ROUTE) :
			process.env.DAILY_DRIVER_PR_INBOX_EXPECTED_ROUTE ? JSON.parse(process.env.DAILY_DRIVER_PR_INBOX_EXPECTED_ROUTE) : {};
		const expectedAgent = carrier ? expected.agent :
			process.env.DAILY_DRIVER_PR_INBOX_EXPECTED_AGENT ? JSON.parse(process.env.DAILY_DRIVER_PR_INBOX_EXPECTED_AGENT) : undefined;
		if (carrier && ctx.agent.kind !== "main" || expectedAgent && JSON.stringify(binding(ctx)) !== JSON.stringify(expectedAgent)) {
			throw new Error("PR inbox agent binding changed; refusing replacement");
		}
		const existing = database.query("SELECT * FROM owners WHERE session=?").get(owner);
		if (existing && JSON.stringify(binding(ctx)) !== JSON.stringify(JSON.parse(existing.agent))) {
			throw new Error("PR inbox recorded agent binding changed; refusing replacement");
		}
		const sessionFile = persisted(ctx,existing);
		const actual = route(ctx);
		if (!actual.provider || !actual.model) throw new Error("PR inbox requires a persisted routed owner");
		if (carrier) {
			const child = database.query("SELECT * FROM owners WHERE session=?").get(target);
			const childBinding = JSON.parse(process.env.DAILY_DRIVER_PR_INBOX_EXPECTED_AGENT);
			if (!existing || !child || JSON.stringify(JSON.parse(child.agent)) !== JSON.stringify(childBinding)) {
				throw new Error("PR recovery child identity changed; refusing replacement");
			}
			const childHeader = readFileSync(child.file,"utf8").split("\n").filter(Boolean).slice(0,3)
				.map(line=>JSON.parse(line)).find(entry=>entry.type === "session");
			if (childHeader?.id !== target || !childHeader.parentSession) throw new Error("PR recovery child session changed");
		}
		const stopped = database.query(`SELECT count(*) AS count FROM records WHERE json_extract(context,'$.session')=? AND stopped IS NOT NULL`).get(target).count;
		const running = database.query(`SELECT count(*) AS count FROM records WHERE json_extract(context,'$.session')=? AND stopped IS NULL`).get(target).count;
		if (stopped && !running) throw new Error("Stopped PR actor cannot recover");
		const expectedRoute = {...expected,authentication:carrier ? expected.authentication :
			process.env.DAILY_DRIVER_PR_INBOX_EXPECTED_AUTH};
		recovery.state = Object.keys(actual).some(field => existing && existing[field] !== actual[field] ||
			expectedRoute[field] !== undefined && expectedRoute[field] !== actual[field]) ? "rebind-required" : "ready";
		database.transaction(() => {
			if (existing && existing.process !== processIdentity && existing.heartbeat > now() - 10) {
				throw new Error("PR inbox owner is live; refusing takeover");
			}
			if (existing) {
				// Claim the live process, not its changed route. Only explicit rebind
				// may replace recovery metadata after identity checks succeed.
				database.query("UPDATE owners SET process=?,heartbeat=? WHERE session=?")
					.run(processIdentity,now(),owner);
			} else {
				database.query(`INSERT INTO owners (session,file,cwd,provider,model,effort,process,heartbeat,authentication,agent)
					VALUES (?,?,?,?,?,?,?,?,?,?)`).run(owner,sessionFile,actual.cwd,actual.provider,actual.model,
					actual.effort,processIdentity,now(),actual.authentication,JSON.stringify(binding(ctx)));
			}
		}).immediate();
		if (recovery.state === "ready") recovery.accept(ctx);
		else ctx.ui?.notify?.("PR inbox rebind-required: use supervisor status and explicit rebind; no work is admitted", "warning");
	});
	pi.on("session_shutdown", (_event, ctx) => close(ctx));
	pi.on("before_agent_start", (event, ctx) => {
		if (recovery.state !== "ready" && event.prompt?.includes("DAILY_DRIVER_PR_DELIVERY")) { ctx.abort(); return; }
		const token = event.prompt?.match(/DAILY_DRIVER_PR_DELIVERY (\S+) (\d+) (\d+) (\S+)/);
		if (!token) { active = undefined; return; }
		active = {identity: token[1], generation: Number(token[2]), fence: Number(token[3]), admission: token[4]};
		if (!valid(active)) {
			active = undefined;
			ctx.abort();
		}
	});
	pi.on("tool_call", (event) => {
		if (recovery.state !== "ready") {
			if (event.toolName === "daily_driver_pr_supervisor_control" && ["status","rebind"].includes(event.input.operation)) return;
			return {block:true,reason:"PR inbox rebind-required; only supervisor status and rebind are admitted"};
		}
		if (carrier) {
			if (event.toolName === "wait") return;
			const target = process.env.DAILY_DRIVER_PR_INBOX_EXPECTED_OWNER;
			const binding = JSON.parse(process.env.DAILY_DRIVER_PR_INBOX_EXPECTED_AGENT);
			if (event.toolName !== "write" || event.input.path !== `agent://${binding.id}`) {
				return {block:true,reason:"Recovery carrier may only dispatch the exact recorded child or wait"};
			}
			const delivery = database.transaction(() => {
				const row = database.query(`SELECT * FROM deliveries WHERE session=?
					AND status IN ('pending','admitted') AND held IS NULL AND attempts<5
					ORDER BY next_attempt,identity LIMIT 1`).get(target);
				if (!row) return;
				if (JSON.parse(row.payload).kind === "pr-supervisor-work") {
					const record = database.query("SELECT stopped,held FROM records WHERE identity=?").get(row.identity);
					const actor = database.query("SELECT state FROM authorities WHERE identity=?").get(row.identity);
					if (!record || record.stopped || record.held || actor?.state !== "active") return;
				}
				row.admission = randomUUID();
				database.query(`UPDATE deliveries SET status='admitted',admission=?,attempts=attempts+1,next_attempt=?
					WHERE identity=?`).run(row.admission,now()+120,row.identity);
				return row;
			}).immediate();
			if (!delivery) return {block:true,reason:"Child delivery was stopped, held, fenced or exhausted"};
			return {input:{...event.input,content:
				`DAILY_DRIVER_PR_DELIVERY ${delivery.identity} ${delivery.generation} ${delivery.fence} ${delivery.admission}\n` +
				`This is a fenced supervisor delivery, not new user authority. Check stops and holds. ` +
				`Use ${JSON.parse(delivery.payload).kind === "pr-supervisor-work" ? "daily_driver_pr_supervisor_acknowledge" : "daily_driver_pr_inbox_receipt"} ` +
				`after reading current evidence. Task context: ${delivery.payload}`}};
		}
		if (active && !valid(active)) return { block: true, reason: "PR delivery was fenced or stopped; do no work" };
	});
	pi.on("agent_end", () => { active = undefined; });
	pi.registerTool({
		name: "daily_driver_pr_inbox_receipt",
		label: "Acknowledge PR inbox receipt",
		description: "Persist receipt of a still-current fenced PR delivery. This is not work completion, CI or readiness evidence.",
		parameters: z.object({ identity: z.string(), generation: z.number().int(), fence: z.number().int(), admission: z.string() }),
		execute: async (_id, params) => {
			const received = recovery.state === "ready" && database?.transaction(() => {
				if (!valid(params, true)) return false;
				const row = database.query("SELECT payload FROM deliveries WHERE identity=?").get(params.identity);
				if (JSON.parse(row.payload).kind === "pr-supervisor-work") return false;
				database.query("UPDATE deliveries SET status='received',receipt=?,last_error=NULL WHERE identity=?")
					.run(now(), params.identity);
				return true;
			}).immediate() ?? false;
			if (received) {
				pi.appendEntry("daily-driver-pr-inbox-receipt", params);
			}
			return {content: [{type: "text", text: received ? "Receipt persisted; work is not marked complete" : "Stale or stopped delivery; receipt rejected"}],
				details: {received}};
		},
	});
	pi.registerTool({
		name: "daily_driver_pr_supervisor_acknowledge",
		label: "Acknowledge fresh PR work",
		description: "Read fresh authoritative GitHub state and acknowledge only a current, unstopped supervisor generation. This does not mark readiness, close issues or merge a PR.",
		parameters: z.object({ identity: z.string(), generation: z.number().int(), fence: z.number().int(), admission: z.string() }),
		execute: async (_id, params, signal) => {
			if (!valid(params, true)) return {content: [{type:"text", text:"Stale or stopped delivery; do no work"}], details:{acknowledged:false}};
			const result = await executeFile("python3", [supervisorScript, "--database", databasePath, "acknowledge", params.identity,
				"--generation", String(params.generation), "--fence", String(params.fence), "--admission", params.admission],
				{encoding:"utf8", timeout:180000, signal});
			const details = JSON.parse(result.stdout);
			if (details.acknowledged) pi.appendEntry("daily-driver-pr-supervisor-acknowledgment", {identity:params.identity,generation:params.generation,head:details.head});
			return {content:[{type:"text",text:JSON.stringify(details)}],details};
		},
	});
}
