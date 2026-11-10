/** Default model selectors for Omp task capability classes. */
export const MODEL_CLASS_ROLE_DEFAULTS = Object.freeze({
	mechanical: "openai-codex/gpt-6-luna:low",
	implementation: "openai-codex/gpt-6-luna:high",
	integration: "openai-codex/gpt-6.1-terra:medium",
	reasoning: "openai-codex/gpt-6.1-sol:high",
	frontier: "openai-codex/gpt-6-astra:high",
});

/** Provider-scoped class routes, identified by a catalog model from each family. */
export const MODEL_CLASS_ROUTES = Object.freeze([
	Object.freeze({ referenceModel: "openai-codex/gpt-6-luna", classes: MODEL_CLASS_ROLE_DEFAULTS }),
]);

const installedRoles = new WeakMap();

/** Return an operator class assignment without mistaking our installed default for one. */
export function explicitModelClassRole(settings, role) {
	const value = settings?.getModelRole(role);
	const installed = installedRoles.get(settings);
	if (installed?.has(role) && installed.get(role) === value) return { assigned: false };
	const provenance = settings?.getModelRoleProvenance?.(role);
	return { assigned: value !== undefined || (provenance !== undefined && provenance !== "default"), value };
}

/** Read provider-scoped routes through Omp's typed settings registry without persisting changes. */
export async function readModelClassRoutes(settings) {
	const { lookup, register } = await import("@oh-my-pi/pi-coding-agent/config/registry");
	const handle = lookup("dailyDriver.modelClassRoutes") ?? register({
		id: "dailyDriver.modelClassRoutes",
		type: "array",
		default: MODEL_CLASS_ROUTES,
		// The registry validates configured values before applying the default.
		validate: routes => { if (routes !== undefined) validateModelClassRoutes(routes); },
	});
	const routes = handle.get(settings);
	validateModelClassRoutes(routes);
	return routes;
}

function validateModelClassRoutes(routes) {
	if (!Array.isArray(routes)) throw new Error("Model class routes must be an array");
	const references = new Set();
	for (const row of routes) {
		if (!row || typeof row.referenceModel !== "string" || !row.referenceModel.includes("/") ||
			!row.classes || typeof row.classes !== "object" || Array.isArray(row.classes) ||
			references.has(row.referenceModel)) throw new Error("Each class route needs a unique provider/model reference and class map");
		references.add(row.referenceModel);
		for (const [name, value] of Object.entries(row.classes)) {
			if (!Object.hasOwn(MODEL_CLASS_ROLE_DEFAULTS, name) || (value !== null && typeof value !== "string")) {
				throw new Error("Class routes accept only known classes with string or cleared selectors");
			}
		}
	}
}

/** Display metadata for task capability roles in the Omp Roles view. */
export const MODEL_CLASS_ROLE_TAGS = Object.freeze({
	mechanical: Object.freeze({ name: "Mechanical" }),
	implementation: Object.freeze({ name: "Implementation" }),
	integration: Object.freeze({ name: "Integration" }),
	reasoning: Object.freeze({ name: "Reasoning" }),
	frontier: Object.freeze({ name: "Frontier" }),
});

/** Install only absent class selectors and role tags on one Omp settings instance. */
export function installModelClassDefaults(settings, modelTagsSetting) {
	const installed = installedRoles.get(settings) ?? new Map();
	installedRoles.set(settings, installed);
	const missingRoles = {};
	for (const [role, selector] of Object.entries(MODEL_CLASS_ROLE_DEFAULTS)) {
		if (settings.getModelRole(role) === undefined &&
			(!settings.getModelRoleProvenance || settings.getModelRoleProvenance(role) === "default")) {
			missingRoles[role] = selector;
			installed.set(role, selector);
		}
	}
	if (Object.keys(missingRoles).length > 0) settings.overrideModelRoles(missingRoles);

	const existingTags = modelTagsSetting.get(settings);
	const modelTags = { ...existingTags };
	let addedTag = false;
	for (const [role, tag] of Object.entries(MODEL_CLASS_ROLE_TAGS)) {
		if (!Object.hasOwn(existingTags, role)) {
			modelTags[role] = tag;
			addedTag = true;
		}
	}
	if (addedTag) modelTagsSetting.override(settings, modelTags);
}

/** Read visible automatic candidates through Omp's own fallback resolver. */
export async function readExecutionCandidates(ctx, settings, patterns, role, agent) {
	const { getRetryFallbackChains, resolveRetryFallbackChainKey, findRetryFallbackCandidates } =
		await import("@oh-my-pi/pi-coding-agent/session/retry-fallback-chains");
	const { lookup } = await import("@oh-my-pi/pi-coding-agent/config/registry");
	const { resolveAgentPrewalkPattern, resolveConfiguredModelPatterns } =
		await import("@oh-my-pi/pi-coding-agent/config/model-resolver");
	const setting = name => lookup(name)?.get(settings);
	const context = {
		chains: getRetryFallbackChains(settings),
		getModelRole: name => settings.getModelRole(name),
		modelLookup: ctx.modelRegistry,
	};
	const prewalk = agent
		? resolveAgentPrewalkPattern({
			settingsOverride: setting("task.agentPrewalk")?.[agent],
			agentPrewalk: agent === "task" && setting("task.prewalk") ? true : undefined,
		})
		: setting("prewalk.enabled") ? "@smol"
			: setting("prewalk.auto") === "on" ? setting("prewalk.autoTarget") : undefined;
	const candidates = new Set(resolveConfiguredModelPatterns([...patterns, ...(prewalk ? [prewalk] : [])], settings));
	for (const pattern of candidates) {
		const model = ctx.models.resolve(pattern);
		const key = resolveRetryFallbackChainKey(context, pattern, model, role);
		if (key) for (const candidate of findRetryFallbackCandidates(context, key, pattern, model, { wrapAround: true })) {
			candidates.add(candidate.raw);
		}
	}
	return [...candidates];
}

