const ENTRY = "daily-driver-notification";
const UNDERTAKING_ENTRY = "daily-driver-undertaking-route";
const EMBARK_ENTRY = "daily-driver-embark-title";
const REASONS = new Set(["attention_required", "work_complete"]);

/** Install Omp toast suppression and one deduplicated human-notification tool. */
export function installNotificationPolicy(pi, getSettings, dependencies = {}) {
	const lookup = dependencies.lookup ?? (id =>
		import("@oh-my-pi/pi-coding-agent/config/registry").then(module => module.lookup(id)));
	const getTransport = dependencies.getTransport ?? (() =>
		import("@oh-my-pi/pi-tui").then(module => module.TERMINAL));
	const pending = new Map();
	const z = pi.zod;

	async function suppress(ctx) {
		if (!pi.settingsManagerFactory && !pi.pi?.settings && !ctx?.settings) return;
		const scope = await getSettings(ctx);
		const [completion, error] = await Promise.all([
			Promise.resolve(lookup("completion.notify")),
			Promise.resolve(lookup("error.notify")),
		]);
		if (!completion || !error) throw new Error("Omp notification settings are unavailable");
		completion.override(scope, "off");
		error.override(scope, "off");
	}

	for (const event of ["session_start", "session_switch", "session_branch", "session_tree", "before_agent_start"]) {
		pi.on(event, (_event, ctx) => suppress(ctx));
	}

	function workIdentity(ctx, sessionId, params) {
		if (params.workIdentity) return params.workIdentity;
		const entries = ctx.sessionManager?.getBranch?.() ?? [];
		for (let index = entries.length - 1; index >= 0; index--) {
			const entry = entries[index];
			if (entry?.type !== "custom") continue;
			if (entry.customType === EMBARK_ENTRY && entry.data?.sessionId === sessionId) {
				const number = entry.data.state?.target?.number;
				if (Number.isSafeInteger(number)) return `epic:${number}`;
			}
			if (entry.customType === UNDERTAKING_ENTRY && entry.data?.lifecycle === "active" &&
				Number.isSafeInteger(entry.data.issue)) return `undertaking:${entry.data.issue}`;
		}
		const title = ctx.sessionManager?.getSessionName?.() ?? "";
		const epic = /^⛵ EPIC #(\d+)\b/u.exec(title);
		if (epic) return `epic:${epic[1]}`;
		const issue = /^#(\d+)\b/u.exec(title);
		if (issue) return `issue:${issue[1]}`;
		return `session:${sessionId}`;
	}

	async function notify(ctx, params) {
		const sessionId = ctx.sessionManager?.getSessionId?.();
		if (ctx.agent?.kind !== "main") return { accepted: false, suppressed: "subagent" };
		if (!ctx.hasUI || !["tui", "rpc"].includes(ctx.mode)) return { accepted: false, suppressed: "headless" };
		if (typeof sessionId !== "string" || !sessionId) return { accepted: false, suppressed: "session-unavailable" };
		const identity = workIdentity(ctx, sessionId, params);
		const dedupeKey = JSON.stringify([sessionId, identity, params.reason, params.key]);
		if (pending.has(dedupeKey)) return pending.get(dedupeKey);
		const operation = (async () => {
			const entries = ctx.sessionManager?.getBranch?.() ?? [];
			const duplicate = entries.some(entry => entry?.type === "custom" && entry.customType === ENTRY &&
				entry.data?.schema === 1 && entry.data.sessionId === sessionId &&
				entry.data.workIdentity === identity && entry.data.reason === params.reason &&
				entry.data.key === params.key);
			if (duplicate) return { accepted: false, duplicate: true };
			await pi.appendEntry(ENTRY, { schema: 1, sessionId, workIdentity: identity, reason: params.reason, key: params.key });
			try {
				const terminal = await getTransport();
				if (typeof terminal?.sendNotification !== "function") throw new Error("Omp notification transport is unavailable");
				terminal.sendNotification({
					title: ctx.sessionManager.getSessionName?.() || "omp",
					body: params.message,
					type: params.reason === "work_complete" ? "completion" : "permission",
					urgency: params.reason === "work_complete" ? "low" : "normal",
					actions: "focus",
				});
				return { accepted: true };
			} catch (error) {
				console.error(`daily-driver: notification delivery failed: ${error.message}`);
				return { accepted: false, suppressed: "delivery-failed" };
			}
		})();
		pending.set(dedupeKey, operation);
		try { return await operation; }
		finally { pending.delete(dedupeKey); }
	}

	pi.registerTool({
		name: "daily_driver_notify",
		label: "Notify the user",
		description: "Send one human-facing system notification for a concrete action the user must take, or for completion of the whole undertaking/embark operation. This is not an internal wake-up, progress update, log, or ordinary final answer. Use a stable key for the semantic transition; repeated keys do not notify again.",
		parameters: z.object({
			reason: z.string().describe("attention_required or work_complete"),
			key: z.string().min(1).max(160).describe("Stable semantic-transition key; reuse it for repeats of the same unresolved state"),
			message: z.string().min(1).max(400).describe("Brief human-facing message naming the action required or completed work"),
		}),
		async execute(_id, params, _signal, _update, ctx) {
			if (!REASONS.has(params.reason)) {
				return { isError: true, content: [{ type: "text", text: "reason must be attention_required or work_complete" }] };
			}
			if (typeof params.key !== "string" || !params.key.trim() || params.key.length > 160 || /[\u0000-\u001f\u007f]/u.test(params.key) ||
				typeof params.message !== "string" || !params.message.trim() || params.message.length > 400 || /[\u0000-\u001f\u007f]/u.test(params.message)) {
				return { isError: true, content: [{ type: "text", text: "key and message must be nonempty, bounded text without control characters" }] };
			}
			const result = await notify(ctx, params);
			return { content: [{ type: "text", text: result.accepted ? "Notification sent." : result.duplicate ? "Notification already sent for this transition." : `Notification not sent (${result.suppressed}).` }], details: result };
		},
	});

	return { notify };
}
