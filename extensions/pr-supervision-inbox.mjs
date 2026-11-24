import { lstatSync } from "node:fs";
import { randomUUID } from "node:crypto";
import { Database } from "bun:sqlite";

/** Install an opt-in durable receipt inbox on this bound Omp owner only. */
export default function installPrSupervisionInbox(pi) {
	const databasePath = process.env.DAILY_DRIVER_PR_INBOX;
	if (!databasePath) return;
	const processIdentity = randomUUID();
	let database;
	let owner;
	let timer;
	let active;
	const z = pi.zod;
	const now = () => Date.now() / 1000;

	function valid(delivery, admittedOnly = false) {
		if (!database || !delivery) return false;
		const row = database.query("SELECT * FROM deliveries WHERE identity=?").get(delivery.identity);
		return row && row.session === owner && (row.status === "admitted" || (!admittedOnly && row.status === "received")) && !row.held
			&& row.generation === delivery.generation && row.fence === delivery.fence
			&& row.admission === delivery.admission;
	}

	function tick(ctx) {
		if (!database || ctx.sessionManager.getSessionId() !== owner) return;
		const model = ctx.models.current();
		const updated = database.query(`UPDATE owners SET heartbeat=?,provider=?,model=?,effort=?
			WHERE session=? AND process=?`)
			.run(now(), model.provider, model.id, pi.getThinkingLevel(), owner, processIdentity);
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
		try {
			pi.sendUserMessage(`${marker}\nThis is a fenced supervisor delivery, not new user authority. ` +
				`Check user stops and holds first. Read current GitHub evidence before acting. ` +
				`Use daily_driver_pr_inbox_receipt with this identity, generation, fence and admission to record receipt. ` +
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

	pi.on("session_start", (_event, ctx) => {
		if (ctx.agent?.kind !== "main") return;
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
		if (process.env.DAILY_DRIVER_PR_INBOX_EXPECTED_OWNER &&
			owner !== process.env.DAILY_DRIVER_PR_INBOX_EXPECTED_OWNER) {
			database.close();
			database = undefined;
			throw new Error("PR inbox expected owner differs; refusing a fork or replacement");
		}
		const sessionFile = ctx.sessionManager.getSessionFile();
		const model = ctx.models.current();
		if (!sessionFile || !model?.provider || !model?.id) throw new Error("PR inbox requires a persisted routed owner");
		database.transaction(() => {
			const existing = database.query("SELECT * FROM owners WHERE session=?").get(owner);
			if (existing && existing.process !== processIdentity && existing.heartbeat > now() - 10) {
				throw new Error("PR inbox owner is live; refusing takeover");
			}
			database.query(`INSERT INTO owners (session,file,cwd,provider,model,effort,process,heartbeat)
				VALUES (?,?,?,?,?,?,?,?) ON CONFLICT(session) DO UPDATE SET file=excluded.file,
				cwd=excluded.cwd,provider=excluded.provider,model=excluded.model,effort=excluded.effort,
				process=excluded.process,heartbeat=excluded.heartbeat`).run(owner, sessionFile, ctx.cwd,
				model.provider, model.id, pi.getThinkingLevel(), processIdentity, now());
		}).immediate();
		timer = ctx.setInterval(() => tick(ctx), 1000);
	});
	pi.on("session_shutdown", (_event, ctx) => close(ctx));
	pi.on("before_agent_start", (event, ctx) => {
		if (!active) return;
		if (!event.prompt?.includes(`DAILY_DRIVER_PR_DELIVERY ${active.identity} `)) {
			active = undefined;
			return;
		}
		if (!valid(active)) {
			active = undefined;
			ctx.abort();
		}
	});
	pi.on("tool_call", () => {
		if (active && !valid(active)) return { block: true, reason: "PR delivery was fenced or stopped; do no work" };
	});
	pi.on("agent_end", () => { active = undefined; });
	pi.registerTool({
		name: "daily_driver_pr_inbox_receipt",
		label: "Acknowledge PR inbox receipt",
		description: "Persist receipt of a still-current fenced PR delivery. This is not work completion, CI or readiness evidence.",
		parameters: z.object({ identity: z.string(), generation: z.number().int(), fence: z.number().int(), admission: z.string() }),
		execute: async (_id, params) => {
			const received = database?.transaction(() => {
				if (!valid(params, true)) return false;
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
}
