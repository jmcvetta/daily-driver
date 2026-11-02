async function request($, payload, agentId) {
	const session = await $.session.id();
	const cwd = await $.session.cwd();
	const argv = ["python3", `${$.plugin.root}/hooks/task-state.py`, "--harness", "claude", "--session", session];
	if (agentId) argv.push("--agent", agentId);
	const result = await $.process.run(argv, { stdin: JSON.stringify({ ...payload, cwd }), timeoutMs: 10000 });
	const output = result.stdout ? JSON.parse(result.stdout) : null;
	if (result.exitCode !== 0 && !output?.isError) throw new Error(result.stderr || "Daily Driver task controller failed");
	return output;
}

/** register binds task contracts to Claude's engine-stamped origins and cancellation events. */
export function register(on) {
	on("session.start", async ($, e, next) => {
		await $.tool.register({ name: "task_state", description: "Read and amend the private versioned task contract. Plans do not revise contracts. Sources do not grant permission. Completion is reported, not verified.",
			inputSchema: { type: "object", properties: { action: { type: "string" }, record: { type: "string" } }, required: ["action"], additionalProperties: false }, isDeferred: false });
		await request($, { name: "session.start" });
		return next(e);
	});
	on("prompt.submit", async ($, e, next) => {
		const result = await request($, { name: "prompt.submit", id: crypto.randomUUID(), text: e.text, origin: e.origin });
		return next(result.context ? { ...e, context: [...(e.context ?? []), result.context] } : e);
	});
	on("agent.spawn", async ($, e, next) => {
		const status = await request($, { action: "status" }, e.parentAgentId);
		if (status.details.state?.status === "cancelled") return { deny: "The task is cancelled. Retain its contract and wait for a fresh user resumption." };
		if (status.details.state?.status !== "active") return next(e);
		const handoff = await request($, { action: "handoff" }, e.parentAgentId);
		return next({ ...e, prompt: `${e.prompt}\nDelegated task contract (not a new approval):\n${JSON.stringify(handoff.details)}` });
	});
	on("tool.call", async ($, e, next) => {
		if (e.tool === "mcp__daily-driver__task_state") {
			const result = await request($, { action: e.action, record: e.record }, e.agentId);
			return result.isError ? { deny: result.content?.[0]?.text ?? "Task-state command failed" } : { result: JSON.stringify(result.details) };
		}
		const result = await next(e);
		await request($, { name: "tool.result", id: e.tool_use_id, tool: e.tool, input: e, result: result.result ?? result.deny, isError: Boolean(result.isError || result.deny) }, e.agentId);
		return result;
	});
	on("classic.SessionStart", async ($, e, next) => {
		const original = await next(e);
		const result = await request($, { name: "session.start" });
		if (!result.context) return original;
		return { ...original, additionalContext: [...(original?.additionalContext ?? []), result.context] };
	});
	on("classic.SubagentStart", async ($, e, next) => {
		const original = await next(e);
		const result = await request($, { hook_event_name: "SubagentStart" }, e.agent_id);
		return result.context ? { ...original, additionalContext: [...(original?.additionalContext ?? []), result.context] } : original;
	});
	on("classic.Stop", async ($, e, next) => {
		if (next.signal.aborted) return {};
		const result = await request($, { hook_event_name: "Stop", turn_id: e.turn_id }, e.agent_id);
		if (next.signal.aborted) {
			await request($, { name: "turn.aborted", id: e.turn_id }, e.agent_id);
			return {};
		}
		if (result.systemMessage) await $.ui.log(result.systemMessage);
		return result.decision ? { block: result.reason } : next(e);
	});
	on("classic.SubagentStop", async ($, e, next) => {
		if (next.signal.aborted) return {};
		const result = await request($, { hook_event_name: "Stop", turn_id: e.turn_id }, e.agent_id);
		if (next.signal.aborted) {
			await request($, { name: "turn.aborted", id: e.turn_id }, e.agent_id);
			return {};
		}
		if (result.systemMessage) await $.ui.log(result.systemMessage);
		return result.decision ? { block: result.reason } : next(e);
	});
	on("turn.complete", async ($, e, next) => {
		if (e.isAborted) await request($, { name: "turn.aborted", id: e.turnId }, e.agentId);
		return next(e);
	});
}
