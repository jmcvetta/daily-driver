/** parentOf names a subagent's direct parent loop, so a nested child adopts its parent's contract, not the root's. */
async function parentOf($, agentId) {
	if (!agentId) return null;
	return (await $.agent.list()).find((agent) => agent.id === agentId)?.parentId ?? null;
}

async function request($, payload, agentId) {
	const session = await $.session.id();
	const cwd = await $.session.cwd();
	const argv = ["python3", `${$.plugin.root}/hooks/task-state.py`, "--harness", "claude", "--session", session];
	if (agentId) argv.push("--agent", agentId);
	const parent = await parentOf($, agentId);
	if (parent) argv.push("--parent", parent);
	if (payload.action) argv.push("--tool");
	const result = await $.process.run(argv, { stdin: JSON.stringify({ ...payload, cwd }), timeoutMs: 10000 });
	const output = result.stdout ? JSON.parse(result.stdout) : null;
	if (result.exitCode !== 0 && !output?.isError) throw new Error(result.stderr || "Daily Driver task controller failed");
	return output;
}

/** observe runs a lifecycle request and fails open: a task-state fault must not block the user's prompt, tool or subagent. */
async function observe($, payload, agentId) {
	try { return await request($, payload, agentId); }
	catch (error) {
		await $.ui.log(`Daily Driver task state unavailable: ${error.message}. Task contracts are not recorded for this event.`);
		return null;
	}
}

/** stopHandler serves main and subagent stops alike, so their abort and block handling cannot drift. */
async function stopHandler($, e, next) {
	if (next.signal.aborted) return {};
	const result = await observe($, { hook_event_name: "Stop", turn_id: e.turn_id }, e.agent_id);
	if (next.signal.aborted) {
		await observe($, { name: "turn.aborted", id: e.turn_id }, e.agent_id);
		return {};
	}
	if (!result) return next(e);
	if (result.systemMessage) await $.ui.log(result.systemMessage);
	return result.decision ? { block: result.reason } : next(e);
}

/** register binds task contracts to Claude's engine-stamped origins and cancellation events. */
export function register(on) {
	on("session.start", async ($, e, next) => {
		await $.tool.register({ name: "task_state", description: "Read and amend the private versioned task contract. Plans do not revise contracts. Sources do not grant permission. Completion is reported, not verified.",
			inputSchema: { type: "object", properties: { action: { type: "string" }, record: { type: "string" } }, required: ["action"], additionalProperties: false }, isDeferred: false });
		await observe($, { name: "session.start" });
		return next(e);
	});
	on("prompt.submit", async ($, e, next) => {
		const result = await observe($, { name: "prompt.submit", id: crypto.randomUUID(), text: e.text, origin: e.origin });
		return next(result?.context ? { ...e, context: [...(e.context ?? []), result.context] } : e);
	});
	on("agent.spawn", async ($, e, next) => {
		const status = await observe($, { action: "status" }, e.parentAgentId);
		const state = status?.details?.state;
		if (state?.status === "cancelled") return { deny: "The task is cancelled. Retain its contract and wait for a fresh user resumption." };
		if (state?.status !== "active") return next(e);
		const handoff = await observe($, { action: "handoff" }, e.parentAgentId);
		if (!handoff?.details) return next(e);
		return next({ ...e, prompt: `${e.prompt}\nDelegated task contract (not a new approval):\n${JSON.stringify(handoff.details)}` });
	});
	on("tool.call", async ($, e, next) => {
		if (e.tool === "mcp__daily-driver__task_state") {
			let result;
			try { result = await request($, { action: e.action, record: e.record }, e.agentId); }
			catch (error) { return { deny: `Task-state command failed: ${error.message}` }; }
			return result.isError ? { deny: result.content?.[0]?.text ?? "Task-state command failed" } : { result: JSON.stringify(result.details) };
		}
		const result = await next(e);
		if (!result) return result;
		// The tool's arguments sit beside reserved per-call fields; a per-call id in the input would make every failure look new.
		const { tool, tool_use_id: toolUseId, agentId, requestMeta: _meta, ...input } = e;
		await observe($, { name: "tool.result", id: toolUseId, tool, input, result: result.result ?? result.deny, isError: Boolean(result.isError || result.deny) }, agentId);
		return result;
	});
	on("classic.SessionStart", async ($, e, next) => {
		const original = await next(e);
		const result = await observe($, { name: "session.start" });
		if (!result?.context) return original;
		return { ...original, additionalContext: [...(original?.additionalContext ?? []), result.context] };
	});
	on("classic.SubagentStart", async ($, e, next) => {
		const original = await next(e);
		const result = await observe($, { hook_event_name: "SubagentStart" }, e.agent_id);
		return result?.context ? { ...original, additionalContext: [...(original?.additionalContext ?? []), result.context] } : original;
	});
	on("classic.Stop", stopHandler);
	on("classic.SubagentStop", stopHandler);
	on("turn.complete", async ($, e, next) => {
		if (e.isAborted) await observe($, { name: "turn.aborted", id: e.turnId }, e.agentId);
		return next(e);
	});
}
