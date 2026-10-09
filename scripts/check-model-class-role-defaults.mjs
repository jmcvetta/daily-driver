import assert from "node:assert/strict";
import { installModelClassDefaults, MODEL_CLASS_ROLE_DEFAULTS, MODEL_CLASS_ROLE_TAGS } from "../extensions/role-default-helper.mjs";

function settingsFixture(initialRoles = {}, initialTags = {}) {
  const roles = { ...initialRoles };
  const tags = { ...initialTags };
  const mutations = [];
  const settings = {
    mutations,
    roles,
    tags,
    getModelRole(role) { return roles[role]; },
    overrideModelRoles(values) {
      Object.assign(roles, values);
      mutations.push(["roles", values]);
    },
  };
  const modelTagsSetting = {
    get(scope) {
      assert.equal(scope, settings);
      return tags;
    },
    override(scope, value) {
      assert.equal(scope, settings);
      Object.assign(tags, value);
      mutations.push(["tags", value]);
    },
  };
  return { settings, modelTagsSetting, roles, tags, mutations };
}

const clean = settingsFixture();
assert.equal(clean.settings.get, undefined, "Omp Settings does not expose generic get");
installModelClassDefaults(clean.settings, clean.modelTagsSetting);
assert.deepEqual(clean.roles, MODEL_CLASS_ROLE_DEFAULTS);
assert.deepEqual(clean.tags, MODEL_CLASS_ROLE_TAGS);
assert.deepEqual(clean.mutations.map(([kind]) => kind), ["roles", "tags"]);

// Without these fixed consumer routes, new sessions send mechanical work to
// high effort, implementation work to Terra, and ordinary reasoning to Astra.
assert.deepEqual(clean.roles, {
  mechanical: "openai-codex/gpt-6-luna:low",
  implementation: "openai-codex/gpt-6-luna:high",
  reasoning: "openai-codex/gpt-6.1-sol:high",
});

const operator = settingsFixture(
  { implementation: "operator/selected:high" },
  { implementation: { name: "Operator's implementation", color: "cyan" }, custom: { name: "Custom" } },
);
installModelClassDefaults(operator.settings, operator.modelTagsSetting);
assert.equal(operator.roles.implementation, "operator/selected:high");
assert.equal(operator.roles.mechanical, MODEL_CLASS_ROLE_DEFAULTS.mechanical);
assert.deepEqual(operator.tags.implementation, { name: "Operator's implementation", color: "cyan" });
assert.deepEqual(operator.tags.mechanical, { name: "Mechanical" });
assert.deepEqual(operator.tags.custom, { name: "Custom" });
const mutationCount = operator.mutations.length;
installModelClassDefaults(operator.settings, operator.modelTagsSetting);
assert.equal(operator.mutations.length, mutationCount, "repeated installation must not rewrite established settings");

const cleared = settingsFixture({ implementation: "" });
installModelClassDefaults(cleared.settings, cleared.modelTagsSetting);
assert.equal(cleared.roles.implementation, MODEL_CLASS_ROLE_DEFAULTS.implementation);

console.log(JSON.stringify({
  installedSelectors: clean.roles,
  preservedOperatorSelector: operator.roles.implementation,
  preservedOperatorMetadata: operator.tags.implementation,
}, null, 2));


