/** Default model selectors for Omp task capability classes. */
export const MODEL_CLASS_ROLE_DEFAULTS = Object.freeze({
	mechanical: "openai-codex/gpt-6-luna:low",
	routine: "openai-codex/gpt-6-luna:high",
	intermediate: "openai-codex/gpt-6.1-terra:medium",
	complex: "openai-codex/gpt-6.1-sol:high",
	frontier: "openai-codex/gpt-6-astra:high",
});

/** Display metadata for task capability roles in the Omp Roles view. */
export const MODEL_CLASS_ROLE_TAGS = Object.freeze({
	mechanical: Object.freeze({ name: "Mechanical" }),
	routine: Object.freeze({ name: "Routine" }),
	intermediate: Object.freeze({ name: "Intermediate" }),
	complex: Object.freeze({ name: "Complex" }),
	frontier: Object.freeze({ name: "Frontier" }),
	reviewer: Object.freeze({ name: "Reviewer" }),
});

/** Install only absent class selectors and role tags on one Omp settings instance. */
export function installModelClassDefaults(settings, modelTagsSetting) {
	const missingRoles = {};
	for (const [role, selector] of Object.entries(MODEL_CLASS_ROLE_DEFAULTS)) {
		if (settings.getModelRole(role) === undefined &&
			(!settings.getModelRoleProvenance || settings.getModelRoleProvenance(role) === "default")) {
			missingRoles[role] = selector;
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
