/**
 * Omp runtime adapter for daily-driver.
 *
 * This is the thin Oh My Pi half of the daily-driver plugin. Claude Code gets
 * the same behaviour from `hooks/hooks.json` + `hooks/ask-in-chat.py`; this
 * module brings that behaviour to Omp (Oh My Pi) as an `ExtensionAPI` factory,
 * where hooks are not the mechanism. The two harnesses share the skills and
 * the one marketplace catalog (`.claude-plugin/marketplace.json` — Omp reads
 * that Claude-compatible catalog, so there is deliberately no
 * `.omp-plugin/marketplace.json`).
 *
 * Two jobs:
 *
 * 1. Block Omp's `ask` tool, the way Claude Code denies `AskUserQuestion`.
 *    The model is told not to retry and to ask the question in chat instead,
 *    putting the question, the options, and the recommendation in the reply.
 *    See `docs/notes/0009-deny-the-question-widget.md` for the reasoning on
 *    the Claude side; the same reason closes the Omp widget: on a phone it is
 *    harder to work with than prose, and the operator's answer is the same
 *    every time.
 *
 * 2. Provide session-title, scheduled-reminder, and session-info tools that
 *    Omp's `ExtensionAPI` makes natural. `daily_driver_set_session_title`,
 *    `daily_driver_schedule` / `daily_driver_cancel_schedule`, and
 *    `daily_driver_get_session`, are the Omp runtime-adapter surface that
 *    Wave 2 (harness-portable skills) consumes.
 *
 * This file is deliberately dependency-free: it runs as a plain `.js` module
 * under Omp, with no build step and no package install between this repo and
 * a user's `~/.omp`. All per-session state lives in the factory closure so two
 * sessions in one process never share a trigger map.
 */

/**
 * What the model is told when it calls Omp's `ask` tool. Mirrors the wording
 * of `hooks/ask-in-chat.py`'s REASON so the two harnesses deny the widget the
 * same way.
 */
export const ASK_BLOCK_REASON =
	"The ask tool is closed in this configuration. Calling it again will be " +
	"denied in the same way, so do not retry it.\n\n" +
	"Ask the same question in your chat reply instead. Write the question as " +
	"prose, give the options as a short list, and name the one you recommend " +
	"and why. The user answers in chat.\n\n" +
	"Check first whether the question needs asking at all. The " +
	"`judgement-call` skill's gate settles most of these — where the correct, " +
	"standard way already picks the answer, make the call, say in one line " +
	"which way it went, and carry on. This adapter governs how a question that " +
	"survives that gate is put, not whether it is worth putting.";

/**
 * The customType namespacing scheduled reminders. Omp delivers a reminder as
 * a custom message via `pi.sendMessage`; a distinct namespaced customType is
 * what keeps `daily-driver` reminders identifiable and separate from
 * user/assistant turns.
 */
export const REMINDER_CUSTOM_TYPE = "daily-driver.reminder";

/**
 * New trigger ids. `crypto.randomUUID` is a modern Node global with no
 * import; fall back to a counter where the runtime lacks it (defensive, and
 * the only place randomness is needed).
 */
let __fallbackId = 0;
function newTriggerId() {
	if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
		return `dd-${crypto.randomUUID()}`;
	}
	return `dd-fallback-${++__fallbackId}`;
}

/** The `daily-driver` Omp extension factory. */
export default function dailyDriverExtension(pi) {
	const z = pi.zod;

	// Per-session trigger bookkeeping: triggerId -> { ctx, handle }. Managed
	// timers are cleared on session_shutdown by the runtime itself; this map
	// only exists to honour cancel_schedule, forget fired triggers, and be
	// dropped wholesale on shutdown.
	const TRIGGERS = new Map();

	/** Idempotently cancel a live trigger. Clean false otherwise. */
	function cancelTrigger(triggerId) {
		if (typeof triggerId !== "string" || triggerId.length === 0) {
			return false;
		}
		const entry = TRIGGERS.get(triggerId);
		if (!entry) {
			// Unknown, or already fired (firing removed the entry). Either
			// way there is nothing live to cancel — clean false, never throws.
			return false;
		}
		TRIGGERS.delete(triggerId);
		try {
			entry.ctx.clearTimer(entry.handle);
		} catch {
			// The runtime may already have cleared the timer (e.g. shutdown).
			// Nothing left to do; the entry is gone either way.
		}
		return true;
	}

	// Close Omp's `ask` widget, exactly as Claude Code closes AskUserQuestion.
	pi.on("tool_call", (event, _ctx) => {
		if (event.toolName === "ask") {
			return { block: true, reason: ASK_BLOCK_REASON };
		}
		return undefined;
	});

	pi.registerTool({
		name: "daily_driver_set_session_title",
		label: "Set session title",
		description:
			"Set the title of the current session. Use it to keep the session " +
			"name meaningful while work is under way, so the session list shows " +
			"what this session is for.",
		parameters: z.object({
			title: z.string().describe("The new session title"),
		}),
		execute: async (_toolCallId, params, _signal, _onUpdate, _ctx) => {
			await pi.setSessionName(params.title);
			return {
				content: [{ type: "text", text: `Session titled: ${params.title}` }],
				details: { titled: params.title },
			};
		},
	});

	// The read half of the session surface. Claude Code answers
	// `mcp__Claude_Code_Remote__get_session`; Omp has no such call, and before
	// this tool it had no model-readable route to its own session id at all —
	// which made an undertake claim comment invent "session: unavailable"
	// diagnostics about a surface that does exist. The id lives in the
	// session manager, and the tool `ctx` exposes it read-only.
	pi.registerTool({
		name: "daily_driver_get_session",
		label: "Get session info",
		description:
			"Read this session's own id, name, and model. The id is what an " +
			"undertake claim comment records; the name and model are the " +
			"session's current values.",
		parameters: z.object({}),
		execute: async (_toolCallId, _params, _signal, _onUpdate, ctx) => {
			const model = ctx.model?.id ?? null;
			const info = {
				sessionId: ctx.sessionManager.getSessionId(),
				sessionName: ctx.sessionManager.getSessionName() ?? null,
				model,
			};
			return {
				content: [
					{
						type: "text",
						text: `Session ${info.sessionId}${info.sessionName ? ` (${info.sessionName})` : ""}, model ${model ?? "unknown"}`,
					},
				],
				details: info,
			};
		},
	});

	pi.registerTool({
		name: "daily_driver_schedule",
		label: "Schedule a reminder",
		description:
			"Schedule a reminder in this session, delivered as a follow-up " +
			"message after delaySeconds. Returns a triggerId you can pass to " +
			"daily_driver_cancel_schedule to cancel it before it fires.",
		parameters: z.object({
			delaySeconds: z
				.number()
				.int()
				.min(1)
				.max(86400)
				.describe("Seconds until the reminder fires, 1 to 86400"),
			message: z.string().describe("The reminder text to deliver"),
		}),
		execute: async (_toolCallId, params, _signal, _onUpdate, ctx) => {
			const triggerId = newTriggerId();
			const handle = ctx.setTimeout(
				() => {
					// Firing removes the trigger first so a cancel racing the
					// expiry is a clean false, never a double-send.
					TRIGGERS.delete(triggerId);
					pi.sendMessage(
						{
							customType: REMINDER_CUSTOM_TYPE,
							content: params.message,
							display: true,
							// User-attributed, the way the operator would have
							// typed it, rather than a tool the model ran.
							attribution: "user",
						},
						{ deliverAs: "followUp" },
					);
				},
				params.delaySeconds * 1000,
			);
			TRIGGERS.set(triggerId, { ctx, handle });
			return {
				content: [
					{
						type: "text",
						text: `Scheduled in ${params.delaySeconds}s as ${triggerId}`,
					},
				],
				details: { triggerId },
			};
		},
	});

	pi.registerTool({
		name: "daily_driver_cancel_schedule",
		label: "Cancel a scheduled reminder",
		description:
			"Idempotently cancel a reminder previously returned by " +
			"daily_driver_schedule. Returns whether a live trigger was " +
			"cancelled.",
		parameters: z.object({
			triggerId: z.string().describe("The triggerId to cancel"),
		}),
		execute: async (_toolCallId, params, _signal, _onUpdate, _ctx) => {
			const cancelled = cancelTrigger(params.triggerId);
			return {
				content: [
					{
						type: "text",
						text: cancelled
							? `Cancelled trigger ${params.triggerId}`
							: `No live trigger ${params.triggerId} to cancel`,
					},
				],
				details: { cancelled },
			};
		},
	});

	// Managed timers are cleared automatically on shutdown by the runtime;
	// this just forgets our per-trigger bookkeeping so nothing stale survives.
	pi.on("session_shutdown", () => {
		TRIGGERS.clear();
	});
}