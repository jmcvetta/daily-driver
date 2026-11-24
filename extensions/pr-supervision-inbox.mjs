import { lstatSync } from "node:fs";
import { randomUUID } from "node:crypto";
import { execFile } from "node:child_process";
import { promisify } from "node:util";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const executeFile = promisify(execFile);
const supervisorScript = resolve(dirname(fileURLToPath(import.meta.url)), "../scripts/pr-active-supervisor.py");

/** Install an opt-in durable receipt inbox on this bound Omp owner only. */
export default function installPrSupervisionInbox(pi, { databasePath = process.env.DAILY_DRIVER_PR_INBOX, initialize, bindLegacyAdmissionReader } = {}) {
	if (!databasePath) return;
	const processIdentity = randomUUID();
	let database;
	let legacyAdmissionQuery;
	let Database;
	let owner;
	let timer;
	let active;
	let running;
	let carrier = false;
	const z = pi.zod;
	const now = () => Date.now() / 1000;
	bindLegacyAdmissionReader?.((identity, token, epoch) => {
		if (!database) {
			return {authorized:false,reason:"Legacy admission database is not initialized or is closed"};
		}
		if (!legacyAdmissionQuery) {
			return {authorized:false,reason:"Legacy admission query is unavailable; authorization denied"};
		}
		if (typeof identity !== "string" || !identity || typeof token !== "string" || !token ||
			!Number.isSafeInteger(epoch) || epoch < 0) {
			return {authorized:false,reason:"Legacy admission identity, token or epoch is invalid"};
		}
		try {
			const row = legacyAdmissionQuery.get(identity, token, epoch, now());
			return row ? {authorized:true} :
				{authorized:false,reason:"Legacy admission is stopped, held, stale, expired or unauthorized"};
		} catch {
			return {authorized:false,reason:"Legacy admission query failed; authorization denied"};
		}
	});

	function authentication(ctx, model) {
		const source = ctx.modelRegistry.authStorage.keys.source(model.provider, { env: "aliases" });
		return source?.kind === "env" ? `env:${source.envVar}` : source?.kind ?? "unknown";
	}

	function authorityAllows(row) {
		if (JSON.parse(row.payload).kind !== "pr-supervisor-work") return true;
		const record = database.query("SELECT stopped,held FROM records WHERE identity=?").get(row.identity);
		const actor = database.query("SELECT state FROM authorities WHERE identity=?").get(row.identity);
		return record && !record.stopped && !record.held && actor?.state === "active";
	}

	function valid(delivery, admittedOnly = false) {
		if (!database || !delivery) return false;
		try {
			const row = database.query("SELECT * FROM deliveries WHERE identity=?").get(delivery.identity);
			return row && authorityAllows(row) && row.session === owner &&
				(row.status === "admitted" || (!admittedOnly && row.status === "received")) && !row.held
				&& row.generation === delivery.generation && row.fence === delivery.fence
				&& row.admission === delivery.admission;
		} catch {
			return false;
		}
	}

	function endWork() {
		if (database && running) {
			database.query("UPDATE deliveries SET running=NULL WHERE identity=? AND running=?")
				.run(running.identity, running.admission);
		}
		running = undefined;
		active = undefined;
	}

	function tick(ctx) {
		if (!database || ctx.sessionManager.getSessionId() !== owner) return;
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
			if (!row || !authorityAllows(row) || row.running) return;
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
		const workInstruction = work
			? "Use its returned observed evidence as the work input; do not act first and acknowledge afterward as a substitute for pre-action evidence. If rejected, do no work. "
			: "A receipt confirms delivery only; it is not work evidence. ";
		try {
			pi.sendUserMessage(`${marker}\nThis is a fenced supervisor delivery, not new user authority. ` +
				`Check user stops and holds first. Use ${acknowledgment} with this identity, generation, fence and admission. ` +
				`${workInstruction}A receipt is not completion, CI approval or readiness.\nTask context: ${delivery.payload}`,
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
		legacyAdmissionQuery = undefined;
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
		try {
			legacyAdmissionQuery = database.query(`SELECT 1 AS authorized
				FROM records AS r
				JOIN authorities AS a ON a.identity = r.identity
				WHERE r.identity = ?
				  AND r.stopped IS NULL AND r.held IS NULL
				  AND a.state = 'shadow'
				  AND a.legacy_delivery = ? AND a.epoch = ?
				  AND (a.legacy_running = 1 OR a.legacy_deadline > ?)`);
		} catch {
			legacyAdmissionQuery = undefined;
		}
		owner = ctx.sessionManager.getSessionId();
		carrier = process.env.DAILY_DRIVER_PR_INBOX_PARENT === owner;
		if (carrier) {
			const expected = JSON.parse(process.env.DAILY_DRIVER_PR_INBOX_PARENT_ROUTE);
			const model = ctx.models.current();
			const binding = {kind:ctx.agent.kind,id:ctx.agent.id,name:ctx.agent.name,parentId:ctx.agent.parentId};
			if (ctx.agent.kind !== "main" || JSON.stringify(binding) !== JSON.stringify(expected.agent) ||
				model.provider !== expected.provider || model.id !== expected.model || pi.getThinkingLevel() !== expected.effort ||
				authentication(ctx,model) !== expected.authentication) {
				throw new Error("PR recovery parent identity, route or effort changed; refusing fallback");
			}
			return;
		}
		if (process.env.DAILY_DRIVER_PR_INBOX_EXPECTED_OWNER &&
			owner !== process.env.DAILY_DRIVER_PR_INBOX_EXPECTED_OWNER) {
			database.close();
			database = undefined;
			throw new Error("PR inbox expected owner differs; refusing a fork or replacement");
		}
		const sessionFile = ctx.sessionManager.getSessionFile();
		const model = ctx.models.current();
		if (!sessionFile || !model?.provider || !model?.id) throw new Error("PR inbox requires a persisted routed owner");
		const route = authentication(ctx, model);
		if (process.env.DAILY_DRIVER_PR_INBOX_EXPECTED_AUTH &&
			route !== process.env.DAILY_DRIVER_PR_INBOX_EXPECTED_AUTH) {
			throw new Error("PR inbox authentication route changed; refusing fallback");
		}
		if (process.env.DAILY_DRIVER_PR_INBOX_EXPECTED_ROUTE) {
			const expected = JSON.parse(process.env.DAILY_DRIVER_PR_INBOX_EXPECTED_ROUTE);
			if (model.provider !== expected.provider || model.id !== expected.model ||
				pi.getThinkingLevel() !== expected.effort || ctx.cwd !== expected.cwd) {
				throw new Error("PR inbox model, provider or effort changed; refusing fallback");
			}
		}
		const binding = {kind:ctx.agent.kind,id:ctx.agent.id,name:ctx.agent.name,parentId:ctx.agent.parentId};
		if (process.env.DAILY_DRIVER_PR_INBOX_EXPECTED_AGENT &&
			JSON.stringify(binding) !== process.env.DAILY_DRIVER_PR_INBOX_EXPECTED_AGENT) {
			throw new Error("PR inbox agent binding changed; refusing replacement");
		}
		database.transaction(() => {
			const existing = database.query("SELECT * FROM owners WHERE session=?").get(owner);
			if (existing && existing.process !== processIdentity && existing.heartbeat > now() - 10) {
				throw new Error("PR inbox owner is live; refusing takeover");
			}
			database.query(`INSERT INTO owners (session,file,cwd,provider,model,effort,process,heartbeat,authentication,agent)
				VALUES (?,?,?,?,?,?,?,?,?,?) ON CONFLICT(session) DO UPDATE SET file=excluded.file,
				cwd=excluded.cwd,provider=excluded.provider,model=excluded.model,effort=excluded.effort,
				process=excluded.process,heartbeat=excluded.heartbeat,authentication=excluded.authentication,agent=excluded.agent`)
				.run(owner, sessionFile, ctx.cwd, model.provider, model.id, pi.getThinkingLevel(), processIdentity, now(), route, JSON.stringify(binding));
		}).immediate();
		timer = ctx.setInterval(() => tick(ctx), 1000);
	});
	pi.on("session_shutdown", (_event, ctx) => close(ctx));
	pi.on("before_agent_start", (event, ctx) => {
		const token = event.prompt?.match(/DAILY_DRIVER_PR_DELIVERY (\S+) (\d+) (\d+) (\S+)/);
		if (!token) { active = undefined; return; }
		active = {identity: token[1], generation: Number(token[2]), fence: Number(token[3]), admission: token[4]};
		const admitted = database?.transaction(() => {
			if (!valid(active)) return false;
			database.query("UPDATE deliveries SET running=? WHERE identity=?")
				.run(active.admission, active.identity);
			return true;
		}).immediate();
		if (!admitted) {
			active = undefined;
			ctx.abort();
		} else {
			running = active;
		}
	});
	pi.on("tool_call", (event) => {
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
				if (!authorityAllows(row) || row.running) return;
				row.admission = randomUUID();
				database.query(`UPDATE deliveries SET status='admitted',admission=?,attempts=attempts+1,next_attempt=?
					WHERE identity=?`).run(row.admission,now()+120,row.identity);
				return row;
			}).immediate();
			if (!delivery) return {block:true,reason:"Child delivery was stopped, held, fenced or exhausted"};
			const work = JSON.parse(delivery.payload).kind === "pr-supervisor-work";
			const acknowledgment = work ? "daily_driver_pr_supervisor_acknowledge" : "daily_driver_pr_inbox_receipt";
			const workInstruction = work
				? "Use its returned observed evidence as the work input; do not act first and acknowledge afterward as a substitute for pre-action evidence. If rejected, do no work. "
				: "A receipt confirms delivery only; it is not work evidence. ";
			return {input:{...event.input,content:
				`DAILY_DRIVER_PR_DELIVERY ${delivery.identity} ${delivery.generation} ${delivery.fence} ${delivery.admission}\n` +
				`This is a fenced supervisor delivery, not new user authority. Check stops and holds. ` +
				`Use ${acknowledgment} with this identity, generation, fence and admission. ` +
				`${workInstruction}Task context: ${delivery.payload}`}};
		}
		if (active && !valid(active)) return { block: true, reason: "PR delivery was fenced or stopped; do no work" };
	});
	pi.on("agent_end", event => { if (event.isTerminal !== false) endWork(); });
	pi.registerTool({
		name: "daily_driver_pr_inbox_receipt",
		label: "Acknowledge PR inbox receipt",
		description: "Persist receipt of a still-current fenced PR delivery. This is not work completion, CI or readiness evidence.",
		parameters: z.object({ identity: z.string(), generation: z.number().int(), fence: z.number().int(), admission: z.string() }),
		execute: async (_id, params) => {
			const received = database?.transaction(() => {
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
		description: "Freshly read authoritative GitHub state and acknowledge only a current, unstopped supervisor generation. Use the returned observed evidence as work input; this does not mark readiness, close issues or merge a PR.",
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
